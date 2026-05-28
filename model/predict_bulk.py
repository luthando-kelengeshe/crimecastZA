"""
model/predict_bulk.py

Bulk forecast generation using pandas + SQL.
Much faster than the row-by-row approach in predict.py.

Usage:
    python -m model.predict_bulk
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
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        for var in missing:
            logger.error("Required env var '%s' is not set.", var)
        sys.exit(1)
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def get_forecast_month(conn) -> tuple[int, int]:
    """Find the latest month with full 12-month lag coverage."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT year, month FROM monthly_crime_record ORDER BY year DESC, month DESC")
        available = set((r[0], r[1]) for r in cur.fetchall())

    sorted_months = sorted(available, reverse=True)
    for year, month in sorted_months:
        all_lags = True
        for lag in range(1, 13):
            lm = month - lag
            ly = year
            while lm <= 0:
                lm += 12
                ly -= 1
            if (ly, lm) not in available:
                all_lags = False
                break
        if all_lags:
            return year, month

    return sorted_months[0][0], sorted_months[0][1]


def build_forecast_features_bulk(conn, forecast_year: int, forecast_month: int) -> pd.DataFrame:
    """
    Build feature vectors for ALL (station, category) combos for the forecast month
    using a single SQL query with LAG window functions.
    """
    sql = f"""
    SELECT
        t.station_id, t.category_id,
        t.lag_1, t.lag_2, t.lag_3, t.lag_4, t.lag_5, t.lag_6,
        t.lag_7, t.lag_8, t.lag_9, t.lag_10, t.lag_11, t.lag_12,
        COALESCE(ur.rate, 0) as unemployment_rate,
        COALESCE(wr.mean_temp_c, 0) as mean_temp_c,
        COALESCE(wr.total_precip_mm, 0) as total_precip_mm,
        COALESCE(ce_h.cnt, 0) as public_holiday_count,
        COALESCE(ce_p.cnt, 0) as payday_count,
        {forecast_month} as month_of_year,
        ps.province_id
    FROM (
        SELECT
            station_id, category_id, year, month,
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
    JOIN police_station ps ON ps.id = t.station_id
    LEFT JOIN unemployment_record ur
        ON ur.province_id = ps.province_id
        AND ur.year = {forecast_year}
        AND ur.quarter = {(forecast_month - 1) // 3 + 1}
    LEFT JOIN weather_record wr
        ON wr.station_id = t.station_id
        AND wr.year = {forecast_year - 1} AND wr.month = {forecast_month}
    LEFT JOIN (
        SELECT EXTRACT(YEAR FROM event_date)::int as yr,
               EXTRACT(MONTH FROM event_date)::int as mo, COUNT(*) as cnt
        FROM calendar_event WHERE event_type = 'public_holiday'
        GROUP BY 1, 2
    ) ce_h ON ce_h.yr = {forecast_year} AND ce_h.mo = {forecast_month}
    LEFT JOIN (
        SELECT EXTRACT(YEAR FROM event_date)::int as yr,
               EXTRACT(MONTH FROM event_date)::int as mo, COUNT(*) as cnt
        FROM calendar_event WHERE event_type = 'payday'
        GROUP BY 1, 2
    ) ce_p ON ce_p.yr = {forecast_year} AND ce_p.mo = {forecast_month}
    WHERE t.year = {forecast_year} AND t.month = {forecast_month}
      AND t.lag_12 IS NOT NULL
    """
    df = pd.read_sql(sql, conn)
    logger.info("Built %d forecast feature vectors", len(df))
    return df


def main() -> None:
    t0 = time.time()
    logger.info("=== CrimecastZA Bulk Forecast Generation ===")

    model_path = os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH)
    if not os.path.exists(model_path):
        logger.error("Model not found at %s. Run model.train first.", model_path)
        sys.exit(1)

    model = joblib.load(model_path)
    model_version = f"xgb_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    logger.info("Loaded model (version: %s)", model_version)

    conn = _get_connection()
    forecast_year, forecast_month = get_forecast_month(conn)
    logger.info("Forecast target: %d-%02d", forecast_year, forecast_month)

    # Build features in bulk
    df = build_forecast_features_bulk(conn, forecast_year, forecast_month)
    if df.empty:
        logger.warning("No feature vectors could be built. Check data coverage.")
        conn.close()
        return

    # Predict
    X = df[FEATURE_COLS].fillna(0)
    predictions = model.predict(X)
    predictions = np.maximum(predictions, 0)  # No negative counts
    df["predicted_count"] = np.round(predictions, 2)

    # Compute risk scores per (category, province)
    logger.info("Computing risk scores...")
    risk_scores = []
    # Get historical counts grouped by (category_id, province_id)
    hist_sql = """
        SELECT mcr.category_id, ps.province_id, array_agg(mcr.monthly_count)
        FROM monthly_crime_record mcr
        JOIN police_station ps ON ps.id = mcr.station_id
        GROUP BY mcr.category_id, ps.province_id
    """
    hist_df = pd.read_sql(hist_sql, conn)
    hist_lookup = {}
    for _, row in hist_df.iterrows():
        hist_lookup[(row["category_id"], row["province_id"])] = row["array_agg"]

    for _, row in df.iterrows():
        key = (row["category_id"], row["province_id"])
        historical = hist_lookup.get(key, [])
        score = compute_risk_score(row["predicted_count"], historical)
        risk_scores.append(score)

    df["risk_score"] = risk_scores

    # Bulk insert into forecast table
    logger.info("Inserting %d forecasts into database...", len(df))
    rows = [
        (int(r.station_id), int(r.category_id), forecast_year, forecast_month,
         float(r.predicted_count), int(r.risk_score), model_version)
        for _, r in df.iterrows()
    ]

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO forecast
                (station_id, category_id, forecast_year, forecast_month,
                 predicted_count, risk_score, model_version)
            VALUES %s
            ON CONFLICT (station_id, category_id, forecast_year, forecast_month, model_version)
            DO UPDATE SET predicted_count = EXCLUDED.predicted_count,
                         risk_score = EXCLUDED.risk_score
            """,
            rows,
            template="(%s, %s, %s, %s, %s, %s, %s)",
            page_size=5000,
        )
    conn.commit()

    conn.close()
    elapsed = time.time() - t0
    logger.info("Done in %.1fs — %d forecasts generated for %d-%02d",
                elapsed, len(df), forecast_year, forecast_month)


if __name__ == "__main__":
    main()
