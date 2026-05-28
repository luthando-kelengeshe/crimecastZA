"""
model/predict.py

Generates Forecasts for all police stations and crime categories
for the next calendar month using the trained XGBoost model.

Usage:
    python -m model.predict

Environment variables required:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, MODEL_PATH (optional)
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras

from model.risk_scorer import compute_risk_score
from model.train import DEFAULT_MODEL_PATH, FEATURE_COLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _get_connection():
    """Build a psycopg2 connection from environment variables."""
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


def _get_next_month() -> tuple[int, int]:
    """Return (year, month) for the next calendar month."""
    now = datetime.now(timezone.utc)
    if now.month == 12:
        return now.year + 1, 1
    return now.year, now.month + 1


def _get_forecast_month(db_conn) -> tuple[int, int]:
    """
    Return (year, month) for the forecast period.
    Finds the latest month where all 12 prior months have data
    for at least some stations.
    """
    with db_conn.cursor() as cur:
        # Find months that have data
        cur.execute("""
            SELECT DISTINCT year, month
            FROM monthly_crime_record
            ORDER BY year DESC, month DESC
        """)
        available = set((r[0], r[1]) for r in cur.fetchall())

    if not available:
        return _get_next_month()

    # Find the latest month where all 12 prior months exist in the dataset
    sorted_months = sorted(available, reverse=True)
    for year, month in sorted_months:
        all_lags_exist = True
        for lag in range(1, 13):
            lag_month = month - lag
            lag_year = year
            while lag_month <= 0:
                lag_month += 12
                lag_year -= 1
            if (lag_year, lag_month) not in available:
                all_lags_exist = False
                break

        if all_lags_exist:
            return year, month

    # Fallback
    return sorted_months[0][0], sorted_months[0][1]


def _build_forecast_features(
    station_id: int,
    category_id: int,
    forecast_year: int,
    forecast_month: int,
    db_conn,
) -> dict | None:
    """
    Build a feature dict for forecasting a single (station, category, month).

    Returns None if insufficient lag data exists.
    """
    with db_conn.cursor() as cur:
        # 12-month lags
        lags = {}
        for lag in range(1, 13):
            lag_month = forecast_month - lag
            lag_year = forecast_year
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
                return None  # Not enough history
            lags[f"lag_{lag}"] = int(row[0])

        # Province for unemployment lookup
        cur.execute(
            "SELECT province_id FROM police_station WHERE id = %s",
            (station_id,),
        )
        province_id = cur.fetchone()[0]

        # Unemployment
        quarter = (forecast_month - 1) // 3 + 1
        cur.execute(
            """
            SELECT rate FROM unemployment_record
            WHERE province_id = %s AND year = %s AND quarter = %s
            """,
            (province_id, forecast_year, quarter),
        )
        row = cur.fetchone()
        unemployment_rate = float(row[0]) if row else 0.0

        # Weather (use same month from previous year as proxy)
        cur.execute(
            """
            SELECT mean_temp_c, total_precip_mm FROM weather_record
            WHERE station_id = %s AND year = %s AND month = %s
            """,
            (station_id, forecast_year - 1, forecast_month),
        )
        row = cur.fetchone()
        mean_temp_c = float(row[0]) if row and row[0] else 0.0
        total_precip_mm = float(row[1]) if row and row[1] else 0.0

        # Calendar events
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'public_holiday'),
                COUNT(*) FILTER (WHERE event_type = 'payday')
            FROM calendar_event
            WHERE EXTRACT(YEAR FROM event_date) = %s
              AND EXTRACT(MONTH FROM event_date) = %s
            """,
            (forecast_year, forecast_month),
        )
        row = cur.fetchone()
        public_holiday_count = int(row[0]) if row else 0
        payday_count = int(row[1]) if row else 0

    features = {
        **lags,
        "unemployment_rate": unemployment_rate,
        "mean_temp_c": mean_temp_c,
        "total_precip_mm": total_precip_mm,
        "public_holiday_count": public_holiday_count,
        "payday_count": payday_count,
        "month_of_year": forecast_month,
    }
    return features


def _get_historical_counts(
    category_id: int, province_id: int, db_conn
) -> list[float]:
    """Get historical monthly counts for a category within a province."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT mcr.monthly_count
            FROM monthly_crime_record mcr
            JOIN police_station ps ON ps.id = mcr.station_id
            WHERE mcr.category_id = %s AND ps.province_id = %s
            """,
            (category_id, province_id),
        )
        return [float(row[0]) for row in cur.fetchall()]


def generate_forecasts(model_path: str, db_conn) -> int:
    """
    Generate forecasts for all (station, category) combinations for the
    next calendar month.

    Loads the model artefact, builds features, predicts, computes risk scores,
    and bulk-inserts into the forecast table.

    Returns the number of forecasts written.
    """
    # Load model
    if not os.path.exists(model_path):
        logger.error("Model artefact not found at %s", model_path)
        return 0

    model = joblib.load(model_path)
    model_version = f"xgb_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    logger.info("Loaded model from %s (version: %s)", model_path, model_version)

    forecast_year, forecast_month = _get_forecast_month(db_conn)
    logger.info("Generating forecasts for %d-%02d", forecast_year, forecast_month)

    # Get all (station_id, category_id) combinations
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT station_id, category_id
            FROM monthly_crime_record
            """
        )
        combos = cur.fetchall()

    logger.info("Processing %d (station, category) combinations...", len(combos))

    forecasts: list[tuple] = []
    skipped = 0

    # Cache province lookups
    province_cache: dict[int, int] = {}

    for station_id, category_id in combos:
        features = _build_forecast_features(
            station_id, category_id, forecast_year, forecast_month, db_conn
        )
        if features is None:
            skipped += 1
            continue

        # Predict
        X = pd.DataFrame([features])[FEATURE_COLS]
        predicted_count = float(model.predict(X)[0])
        predicted_count = max(0.0, predicted_count)  # No negative counts

        # Get province for risk scoring
        if station_id not in province_cache:
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT province_id FROM police_station WHERE id = %s",
                    (station_id,),
                )
                province_cache[station_id] = cur.fetchone()[0]

        province_id = province_cache[station_id]

        # Risk score
        historical = _get_historical_counts(category_id, province_id, db_conn)
        risk_score = compute_risk_score(predicted_count, historical)

        forecasts.append((
            station_id, category_id, forecast_year, forecast_month,
            round(predicted_count, 2), risk_score, model_version,
        ))

        if len(forecasts) % 10000 == 0:
            logger.info("  Generated %d forecasts so far...", len(forecasts))

    # Bulk insert
    if forecasts:
        with db_conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO forecast
                    (station_id, category_id, forecast_year, forecast_month,
                     predicted_count, risk_score, model_version)
                VALUES %s
                ON CONFLICT (station_id, category_id, forecast_year, forecast_month, model_version)
                DO UPDATE SET
                    predicted_count = EXCLUDED.predicted_count,
                    risk_score = EXCLUDED.risk_score
                """,
                forecasts,
                template="(%s, %s, %s, %s, %s, %s, %s)",
                page_size=5000,
            )
        db_conn.commit()

    logger.info(
        "Forecast generation complete: %d written, %d skipped (insufficient history)",
        len(forecasts), skipped,
    )
    return len(forecasts)


def main() -> None:
    """Main forecast generation entry point."""
    t0 = time.time()
    logger.info("=== CrimecastZA Forecast Generation ===")

    model_path = os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH)
    conn = _get_connection()

    count = generate_forecasts(model_path, conn)

    conn.close()
    elapsed = time.time() - t0
    logger.info("Done in %.1fs — %d forecasts generated", elapsed, count)


if __name__ == "__main__":
    main()
