"""
pipeline/feature_builder.py

Assembles Feature_Vectors from the database by joining:
  - 12-month lagged crime counts (monthly_crime_record)
  - Provincial unemployment rate (unemployment_record)
  - Monthly weather data (weather_record)
  - Public holiday and payday counts (calendar_event)

Each Feature_Vector is stored in the feature_vector table for direct
consumption by the ML training script via a single SQL SELECT.
"""

from __future__ import annotations

import logging
from typing import Any

from pipeline.models import FeatureVector

logger = logging.getLogger(__name__)


def build_feature_vector(
    station_id: int,
    category_id: int,
    year: int,
    month: int,
    db_conn,
) -> FeatureVector | None:
    """
    Assemble a complete FeatureVector for a given station/category/month.

    Joins:
      - 12-month lagged crime counts from monthly_crime_record
      - Provincial unemployment rate from unemployment_record
      - Weather data from weather_record
      - Holiday/payday counts from calendar_event

    Returns None if any required source data is missing (e.g., not enough
    historical months for all 12 lags).
    """
    with db_conn.cursor() as cur:
        # --- 12-month lags ---
        lags: list[int | None] = []
        for lag in range(1, 13):
            lag_month = month - lag
            lag_year = year
            while lag_month <= 0:
                lag_month += 12
                lag_year -= 1

            cur.execute(
                """
                SELECT monthly_count FROM monthly_crime_record
                WHERE station_id = %s AND category_id = %s
                  AND year = %s AND month = %s
                """,
                (station_id, category_id, lag_year, lag_month),
            )
            row = cur.fetchone()
            if row is None:
                lags.append(None)
            else:
                lags.append(int(row[0]))

        # Require all 12 lags to be present
        if any(lag is None for lag in lags):
            return None

        # --- Unemployment rate ---
        # Get the province for this station
        cur.execute(
            "SELECT province_id FROM police_station WHERE id = %s",
            (station_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        province_id = row[0]

        # Quarter for the target month
        quarter = (month - 1) // 3 + 1
        cur.execute(
            """
            SELECT rate FROM unemployment_record
            WHERE province_id = %s AND year = %s AND quarter = %s
            """,
            (province_id, year, quarter),
        )
        row = cur.fetchone()
        unemployment_rate = float(row[0]) if row else None

        # --- Weather ---
        cur.execute(
            """
            SELECT mean_temp_c, total_precip_mm FROM weather_record
            WHERE station_id = %s AND year = %s AND month = %s
            """,
            (station_id, year, month),
        )
        row = cur.fetchone()
        mean_temp_c = float(row[0]) if row and row[0] is not None else None
        total_precip_mm = float(row[1]) if row and row[1] is not None else None

        # --- Calendar events for the month ---
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'public_holiday') as holiday_count,
                COUNT(*) FILTER (WHERE event_type = 'payday') as payday_count
            FROM calendar_event
            WHERE EXTRACT(YEAR FROM event_date) = %s
              AND EXTRACT(MONTH FROM event_date) = %s
            """,
            (year, month),
        )
        row = cur.fetchone()
        public_holiday_count = int(row[0]) if row else 0
        payday_count = int(row[1]) if row else 0

    return FeatureVector(
        station_id=station_id,
        category_id=category_id,
        year=year,
        month=month,
        lags=lags,
        unemployment_rate=unemployment_rate if unemployment_rate is not None else 0.0,
        mean_temp_c=mean_temp_c if mean_temp_c is not None else 0.0,
        total_precip_mm=total_precip_mm if total_precip_mm is not None else 0.0,
        public_holiday_count=public_holiday_count,
        payday_count=payday_count,
        month_of_year=month,
    )


def build_all_feature_vectors(db_conn) -> list[FeatureVector]:
    """
    Build feature vectors for all (station, category, year, month) combinations
    that have at least 12 months of prior history.

    Returns a list of complete FeatureVector objects.
    """
    vectors: list[FeatureVector] = []

    with db_conn.cursor() as cur:
        # Get all distinct (station_id, category_id, year, month) combos
        # that have data, starting from month 13 onwards (need 12 lags)
        cur.execute(
            """
            SELECT DISTINCT station_id, category_id, year, month
            FROM monthly_crime_record
            ORDER BY station_id, category_id, year, month
            """
        )
        combos = cur.fetchall()

    logger.info("Building feature vectors for %d combinations...", len(combos))

    built = 0
    skipped = 0
    for station_id, category_id, year, month in combos:
        fv = build_feature_vector(station_id, category_id, year, month, db_conn)
        if fv is not None:
            vectors.append(fv)
            built += 1
        else:
            skipped += 1

        if (built + skipped) % 50000 == 0:
            logger.info("  Progress: %d built, %d skipped", built, skipped)

    logger.info("Feature vector build complete: %d built, %d skipped", built, skipped)
    return vectors


def persist_feature_vectors(vectors: list[FeatureVector], db_conn) -> int:
    """
    Bulk-upsert FeatureVector objects into the feature_vector table.

    Uses ON CONFLICT DO UPDATE to overwrite existing rows.
    Returns the number of rows upserted.
    """
    if not vectors:
        return 0

    import psycopg2.extras

    rows = [
        (
            fv.station_id, fv.category_id, fv.year, fv.month,
            fv.lags[0], fv.lags[1], fv.lags[2], fv.lags[3],
            fv.lags[4], fv.lags[5], fv.lags[6], fv.lags[7],
            fv.lags[8], fv.lags[9], fv.lags[10], fv.lags[11],
            fv.unemployment_rate, fv.mean_temp_c, fv.total_precip_mm,
            fv.public_holiday_count, fv.payday_count, fv.month_of_year,
        )
        for fv in vectors
    ]

    sql = """
        INSERT INTO feature_vector (
            station_id, category_id, year, month,
            lag_1, lag_2, lag_3, lag_4, lag_5, lag_6,
            lag_7, lag_8, lag_9, lag_10, lag_11, lag_12,
            unemployment_rate, mean_temp_c, total_precip_mm,
            public_holiday_count, payday_count, month_of_year
        ) VALUES %s
        ON CONFLICT (station_id, category_id, year, month)
        DO UPDATE SET
            lag_1 = EXCLUDED.lag_1, lag_2 = EXCLUDED.lag_2,
            lag_3 = EXCLUDED.lag_3, lag_4 = EXCLUDED.lag_4,
            lag_5 = EXCLUDED.lag_5, lag_6 = EXCLUDED.lag_6,
            lag_7 = EXCLUDED.lag_7, lag_8 = EXCLUDED.lag_8,
            lag_9 = EXCLUDED.lag_9, lag_10 = EXCLUDED.lag_10,
            lag_11 = EXCLUDED.lag_11, lag_12 = EXCLUDED.lag_12,
            unemployment_rate = EXCLUDED.unemployment_rate,
            mean_temp_c = EXCLUDED.mean_temp_c,
            total_precip_mm = EXCLUDED.total_precip_mm,
            public_holiday_count = EXCLUDED.public_holiday_count,
            payday_count = EXCLUDED.payday_count,
            month_of_year = EXCLUDED.month_of_year
    """

    with db_conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur, sql, rows,
            template="(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            page_size=5000,
        )
        count = cur.rowcount

    db_conn.commit()
    logger.info("Persisted %d feature vectors", count)
    return count
