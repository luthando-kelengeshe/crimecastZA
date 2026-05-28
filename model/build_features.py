"""
model/build_features.py

Builds feature vectors in bulk using SQL window functions.
Much faster than the row-by-row approach in pipeline/feature_builder.py.

Usage:
    python -m model.build_features

This populates the feature_vector table directly from SQL.
"""

from __future__ import annotations

import logging
import os
import sys
import time

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _get_connection():
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        for var in missing:
            logger.error("Required environment variable '%s' is not set.", var)
        sys.exit(1)

    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def build_features_bulk(conn) -> int:
    """
    Build feature vectors using a single SQL INSERT ... SELECT with LAG() window functions.

    This is orders of magnitude faster than building row-by-row.
    Only builds vectors where all 12 lags are available.

    Returns the number of feature vectors inserted.
    """
    logger.info("Building feature vectors in bulk using SQL window functions...")

    sql = """
    INSERT INTO feature_vector (
        station_id, category_id, year, month,
        lag_1, lag_2, lag_3, lag_4, lag_5, lag_6,
        lag_7, lag_8, lag_9, lag_10, lag_11, lag_12,
        unemployment_rate, mean_temp_c, total_precip_mm,
        public_holiday_count, payday_count, month_of_year
    )
    SELECT
        t.station_id, t.category_id, t.year, t.month,
        t.lag_1, t.lag_2, t.lag_3, t.lag_4, t.lag_5, t.lag_6,
        t.lag_7, t.lag_8, t.lag_9, t.lag_10, t.lag_11, t.lag_12,
        COALESCE(ur.rate, 0) as unemployment_rate,
        COALESCE(wr.mean_temp_c, 0) as mean_temp_c,
        COALESCE(wr.total_precip_mm, 0) as total_precip_mm,
        COALESCE(ce_holidays.cnt, 0) as public_holiday_count,
        COALESCE(ce_paydays.cnt, 0) as payday_count,
        t.month as month_of_year
    FROM (
        SELECT
            station_id, category_id, year, month, monthly_count,
            LAG(monthly_count, 1)  OVER w as lag_1,
            LAG(monthly_count, 2)  OVER w as lag_2,
            LAG(monthly_count, 3)  OVER w as lag_3,
            LAG(monthly_count, 4)  OVER w as lag_4,
            LAG(monthly_count, 5)  OVER w as lag_5,
            LAG(monthly_count, 6)  OVER w as lag_6,
            LAG(monthly_count, 7)  OVER w as lag_7,
            LAG(monthly_count, 8)  OVER w as lag_8,
            LAG(monthly_count, 9)  OVER w as lag_9,
            LAG(monthly_count, 10) OVER w as lag_10,
            LAG(monthly_count, 11) OVER w as lag_11,
            LAG(monthly_count, 12) OVER w as lag_12
        FROM monthly_crime_record
        WINDOW w AS (PARTITION BY station_id, category_id ORDER BY year, month)
    ) t
    -- Join province for unemployment
    JOIN police_station ps ON ps.id = t.station_id
    -- Unemployment rate
    LEFT JOIN unemployment_record ur
        ON ur.province_id = ps.province_id
        AND ur.year = t.year
        AND ur.quarter = ((t.month - 1) / 3 + 1)
    -- Weather
    LEFT JOIN weather_record wr
        ON wr.station_id = t.station_id
        AND wr.year = t.year
        AND wr.month = t.month
    -- Holiday count per month
    LEFT JOIN (
        SELECT
            EXTRACT(YEAR FROM event_date)::int as year,
            EXTRACT(MONTH FROM event_date)::int as month,
            COUNT(*) as cnt
        FROM calendar_event
        WHERE event_type = 'public_holiday'
        GROUP BY 1, 2
    ) ce_holidays ON ce_holidays.year = t.year AND ce_holidays.month = t.month
    -- Payday count per month
    LEFT JOIN (
        SELECT
            EXTRACT(YEAR FROM event_date)::int as year,
            EXTRACT(MONTH FROM event_date)::int as month,
            COUNT(*) as cnt
        FROM calendar_event
        WHERE event_type = 'payday'
        GROUP BY 1, 2
    ) ce_paydays ON ce_paydays.year = t.year AND ce_paydays.month = t.month
    -- Only include rows where all 12 lags are available
    WHERE t.lag_12 IS NOT NULL
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

    with conn.cursor() as cur:
        cur.execute(sql)
        count = cur.rowcount

    conn.commit()
    logger.info("Inserted/updated %d feature vectors", count)
    return count


def main() -> None:
    t0 = time.time()
    logger.info("=== CrimecastZA Feature Vector Builder ===")

    conn = _get_connection()
    count = build_features_bulk(conn)
    conn.close()

    elapsed = time.time() - t0
    logger.info("Done in %.1fs — %d feature vectors built", elapsed, count)


if __name__ == "__main__":
    main()
