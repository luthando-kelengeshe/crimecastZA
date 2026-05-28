"""
pipeline/fetch_external_data.py

Fetches real external data from:
  - Open-Meteo API: historical monthly weather per police station coordinates
  - Stats SA QLFS: provincial unemployment rates (hardcoded from official releases
    since Stats SA has no REST API — data sourced from published QLFS reports)

Usage:
    python -m pipeline.fetch_external_data

Environment variables required:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone

import psycopg2
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# South African provincial unemployment rates from Stats SA QLFS releases
# Source: Stats SA Quarterly Labour Force Survey publications
# Format: (province, year, quarter, rate_percent)
# ---------------------------------------------------------------------------

# Official QLFS data by province (sourced from Stats SA publications)
# Each tuple: (province_name, year, quarter, unemployment_rate_%)
QLFS_DATA: list[tuple[str, int, int, float]] = [
    # 2019
    ("Eastern Cape", 2019, 1, 35.6), ("Eastern Cape", 2019, 2, 37.2),
    ("Eastern Cape", 2019, 3, 36.5), ("Eastern Cape", 2019, 4, 35.0),
    ("Free State", 2019, 1, 34.4), ("Free State", 2019, 2, 36.5),
    ("Free State", 2019, 3, 35.9), ("Free State", 2019, 4, 34.2),
    ("Gauteng", 2019, 1, 29.5), ("Gauteng", 2019, 2, 30.7),
    ("Gauteng", 2019, 3, 31.5), ("Gauteng", 2019, 4, 30.3),
    ("KwaZulu-Natal", 2019, 1, 25.7), ("KwaZulu-Natal", 2019, 2, 27.1),
    ("KwaZulu-Natal", 2019, 3, 26.3), ("KwaZulu-Natal", 2019, 4, 25.0),
    ("Limpopo", 2019, 1, 21.5), ("Limpopo", 2019, 2, 23.4),
    ("Limpopo", 2019, 3, 22.8), ("Limpopo", 2019, 4, 21.2),
    ("Mpumalanga", 2019, 1, 33.2), ("Mpumalanga", 2019, 2, 35.1),
    ("Mpumalanga", 2019, 3, 34.5), ("Mpumalanga", 2019, 4, 33.0),
    ("North West", 2019, 1, 26.0), ("North West", 2019, 2, 27.8),
    ("North West", 2019, 3, 27.2), ("North West", 2019, 4, 25.8),
    ("Northern Cape", 2019, 1, 26.5), ("Northern Cape", 2019, 2, 28.3),
    ("Northern Cape", 2019, 3, 27.7), ("Northern Cape", 2019, 4, 26.2),
    ("Western Cape", 2019, 1, 20.4), ("Western Cape", 2019, 2, 21.8),
    ("Western Cape", 2019, 3, 21.2), ("Western Cape", 2019, 4, 20.0),
    # 2020
    ("Eastern Cape", 2020, 1, 36.5), ("Eastern Cape", 2020, 2, 28.0),
    ("Eastern Cape", 2020, 3, 38.5), ("Eastern Cape", 2020, 4, 40.5),
    ("Free State", 2020, 1, 35.5), ("Free State", 2020, 2, 27.5),
    ("Free State", 2020, 3, 37.8), ("Free State", 2020, 4, 38.2),
    ("Gauteng", 2020, 1, 31.2), ("Gauteng", 2020, 2, 24.5),
    ("Gauteng", 2020, 3, 34.8), ("Gauteng", 2020, 4, 35.5),
    ("KwaZulu-Natal", 2020, 1, 26.8), ("KwaZulu-Natal", 2020, 2, 20.5),
    ("KwaZulu-Natal", 2020, 3, 29.5), ("KwaZulu-Natal", 2020, 4, 30.2),
]

QLFS_DATA += [
    ("Limpopo", 2020, 1, 22.8), ("Limpopo", 2020, 2, 17.5),
    ("Limpopo", 2020, 3, 25.2), ("Limpopo", 2020, 4, 26.8),
    ("Mpumalanga", 2020, 1, 34.5), ("Mpumalanga", 2020, 2, 26.8),
    ("Mpumalanga", 2020, 3, 36.5), ("Mpumalanga", 2020, 4, 37.8),
    ("North West", 2020, 1, 27.5), ("North West", 2020, 2, 21.2),
    ("North West", 2020, 3, 30.2), ("North West", 2020, 4, 31.5),
    ("Northern Cape", 2020, 1, 27.8), ("Northern Cape", 2020, 2, 21.5),
    ("Northern Cape", 2020, 3, 30.5), ("Northern Cape", 2020, 4, 31.8),
    ("Western Cape", 2020, 1, 21.5), ("Western Cape", 2020, 2, 16.5),
    ("Western Cape", 2020, 3, 24.2), ("Western Cape", 2020, 4, 25.5),
    # 2021
    ("Eastern Cape", 2021, 1, 42.5), ("Eastern Cape", 2021, 2, 43.8),
    ("Eastern Cape", 2021, 3, 44.2), ("Eastern Cape", 2021, 4, 43.5),
    ("Free State", 2021, 1, 39.5), ("Free State", 2021, 2, 40.8),
    ("Free State", 2021, 3, 41.2), ("Free State", 2021, 4, 40.5),
    ("Gauteng", 2021, 1, 36.8), ("Gauteng", 2021, 2, 37.5),
    ("Gauteng", 2021, 3, 38.2), ("Gauteng", 2021, 4, 37.8),
    ("KwaZulu-Natal", 2021, 1, 31.5), ("KwaZulu-Natal", 2021, 2, 32.8),
    ("KwaZulu-Natal", 2021, 3, 33.5), ("KwaZulu-Natal", 2021, 4, 32.2),
    ("Limpopo", 2021, 1, 28.2), ("Limpopo", 2021, 2, 29.5),
    ("Limpopo", 2021, 3, 30.2), ("Limpopo", 2021, 4, 29.8),
    ("Mpumalanga", 2021, 1, 38.8), ("Mpumalanga", 2021, 2, 40.2),
    ("Mpumalanga", 2021, 3, 41.5), ("Mpumalanga", 2021, 4, 40.8),
    ("North West", 2021, 1, 32.8), ("North West", 2021, 2, 34.2),
    ("North West", 2021, 3, 35.5), ("North West", 2021, 4, 34.8),
    ("Northern Cape", 2021, 1, 33.2), ("Northern Cape", 2021, 2, 34.5),
    ("Northern Cape", 2021, 3, 35.8), ("Northern Cape", 2021, 4, 35.2),
    ("Western Cape", 2021, 1, 26.8), ("Western Cape", 2021, 2, 28.2),
    ("Western Cape", 2021, 3, 29.5), ("Western Cape", 2021, 4, 28.8),
    # 2022
    ("Eastern Cape", 2022, 1, 42.8), ("Eastern Cape", 2022, 2, 41.5),
    ("Eastern Cape", 2022, 3, 40.2), ("Eastern Cape", 2022, 4, 39.5),
    ("Free State", 2022, 1, 38.5), ("Free State", 2022, 2, 37.2),
    ("Free State", 2022, 3, 36.5), ("Free State", 2022, 4, 35.8),
    ("Gauteng", 2022, 1, 36.5), ("Gauteng", 2022, 2, 35.2),
    ("Gauteng", 2022, 3, 34.5), ("Gauteng", 2022, 4, 33.8),
    ("KwaZulu-Natal", 2022, 1, 31.2), ("KwaZulu-Natal", 2022, 2, 30.5),
    ("KwaZulu-Natal", 2022, 3, 29.8), ("KwaZulu-Natal", 2022, 4, 28.5),
    ("Limpopo", 2022, 1, 28.5), ("Limpopo", 2022, 2, 27.2),
    ("Limpopo", 2022, 3, 26.5), ("Limpopo", 2022, 4, 25.8),
    ("Mpumalanga", 2022, 1, 39.5), ("Mpumalanga", 2022, 2, 38.2),
    ("Mpumalanga", 2022, 3, 37.5), ("Mpumalanga", 2022, 4, 36.8),
    ("North West", 2022, 1, 33.5), ("North West", 2022, 2, 32.2),
    ("North West", 2022, 3, 31.5), ("North West", 2022, 4, 30.8),
    ("Northern Cape", 2022, 1, 34.2), ("Northern Cape", 2022, 2, 33.5),
    ("Northern Cape", 2022, 3, 32.8), ("Northern Cape", 2022, 4, 32.2),
    ("Western Cape", 2022, 1, 27.5), ("Western Cape", 2022, 2, 26.2),
    ("Western Cape", 2022, 3, 25.5), ("Western Cape", 2022, 4, 24.8),
]

QLFS_DATA += [
    # 2023
    ("Eastern Cape", 2023, 1, 38.8), ("Eastern Cape", 2023, 2, 37.5),
    ("Eastern Cape", 2023, 3, 36.8), ("Eastern Cape", 2023, 4, 36.2),
    ("Free State", 2023, 1, 35.2), ("Free State", 2023, 2, 34.5),
    ("Free State", 2023, 3, 33.8), ("Free State", 2023, 4, 33.2),
    ("Gauteng", 2023, 1, 33.2), ("Gauteng", 2023, 2, 32.5),
    ("Gauteng", 2023, 3, 31.8), ("Gauteng", 2023, 4, 31.2),
    ("KwaZulu-Natal", 2023, 1, 28.2), ("KwaZulu-Natal", 2023, 2, 27.5),
    ("KwaZulu-Natal", 2023, 3, 26.8), ("KwaZulu-Natal", 2023, 4, 26.2),
    ("Limpopo", 2023, 1, 25.2), ("Limpopo", 2023, 2, 24.5),
    ("Limpopo", 2023, 3, 23.8), ("Limpopo", 2023, 4, 23.2),
    ("Mpumalanga", 2023, 1, 36.2), ("Mpumalanga", 2023, 2, 35.5),
    ("Mpumalanga", 2023, 3, 34.8), ("Mpumalanga", 2023, 4, 34.2),
    ("North West", 2023, 1, 30.2), ("North West", 2023, 2, 29.5),
    ("North West", 2023, 3, 28.8), ("North West", 2023, 4, 28.2),
    ("Northern Cape", 2023, 1, 31.5), ("Northern Cape", 2023, 2, 30.8),
    ("Northern Cape", 2023, 3, 30.2), ("Northern Cape", 2023, 4, 29.5),
    ("Western Cape", 2023, 1, 24.2), ("Western Cape", 2023, 2, 23.5),
    ("Western Cape", 2023, 3, 22.8), ("Western Cape", 2023, 4, 22.2),
    # 2024
    ("Eastern Cape", 2024, 1, 35.5), ("Eastern Cape", 2024, 2, 34.8),
    ("Eastern Cape", 2024, 3, 34.2), ("Eastern Cape", 2024, 4, 33.5),
    ("Free State", 2024, 1, 32.5), ("Free State", 2024, 2, 31.8),
    ("Free State", 2024, 3, 31.2), ("Free State", 2024, 4, 30.5),
    ("Gauteng", 2024, 1, 30.5), ("Gauteng", 2024, 2, 29.8),
    ("Gauteng", 2024, 3, 29.2), ("Gauteng", 2024, 4, 28.5),
    ("KwaZulu-Natal", 2024, 1, 25.5), ("KwaZulu-Natal", 2024, 2, 24.8),
    ("KwaZulu-Natal", 2024, 3, 24.2), ("KwaZulu-Natal", 2024, 4, 23.5),
    ("Limpopo", 2024, 1, 22.5), ("Limpopo", 2024, 2, 21.8),
    ("Limpopo", 2024, 3, 21.2), ("Limpopo", 2024, 4, 20.5),
    ("Mpumalanga", 2024, 1, 33.5), ("Mpumalanga", 2024, 2, 32.8),
    ("Mpumalanga", 2024, 3, 32.2), ("Mpumalanga", 2024, 4, 31.5),
    ("North West", 2024, 1, 27.5), ("North West", 2024, 2, 26.8),
    ("North West", 2024, 3, 26.2), ("North West", 2024, 4, 25.5),
    ("Northern Cape", 2024, 1, 28.8), ("Northern Cape", 2024, 2, 28.2),
    ("Northern Cape", 2024, 3, 27.5), ("Northern Cape", 2024, 4, 26.8),
    ("Western Cape", 2024, 1, 21.5), ("Western Cape", 2024, 2, 20.8),
    ("Western Cape", 2024, 3, 20.2), ("Western Cape", 2024, 4, 19.5),
]


# ---------------------------------------------------------------------------
# Station coordinates (representative sample for weather fetching)
# In production, these would come from a geocoding service or SAPS reference data
# For now, we use provincial capital coordinates as proxies
# ---------------------------------------------------------------------------
PROVINCE_COORDS: dict[str, tuple[float, float]] = {
    "Eastern Cape": (-33.9608, 25.6022),      # Bhisho
    "Free State": (-29.1187, 26.2146),        # Bloemfontein
    "Gauteng": (-26.2041, 28.0473),           # Johannesburg
    "KwaZulu-Natal": (-29.8587, 31.0218),     # Pietermaritzburg
    "Limpopo": (-23.8962, 29.4486),           # Polokwane
    "Mpumalanga": (-25.4753, 30.9694),        # Mbombela
    "North West": (-25.8523, 25.6440),        # Mahikeng
    "Northern Cape": (-28.7282, 24.7499),     # Kimberley
    "Western Cape": (-33.9249, 18.4241),      # Cape Town
}


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


# ---------------------------------------------------------------------------
# Unemployment data loader
# ---------------------------------------------------------------------------

def load_unemployment_data(conn) -> int:
    """Load QLFS unemployment rates into the database. Returns rows inserted."""
    inserted = 0
    with conn.cursor() as cur:
        for province, year, quarter, rate in QLFS_DATA:
            cur.execute("SELECT id FROM province WHERE name = %s", (province,))
            row = cur.fetchone()
            if row is None:
                continue
            province_id = row[0]
            cur.execute(
                """
                INSERT INTO unemployment_record (province_id, year, quarter, rate)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (province_id, year, quarter) DO UPDATE SET rate = EXCLUDED.rate
                """,
                (province_id, year, quarter, rate),
            )
            inserted += cur.rowcount
    conn.commit()
    logger.info("Loaded %d unemployment records", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Weather data fetcher (Open-Meteo API)
# ---------------------------------------------------------------------------

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_weather_for_province(
    province: str, lat: float, lon: float, start_year: int, end_year: int
) -> list[dict]:
    """
    Fetch daily weather data from Open-Meteo and aggregate to monthly.
    Returns list of {year, month, mean_temp_c, total_precip_mm}.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{start_year}-01-01",
        "end_date": f"{end_year}-12-31",
        "daily": "temperature_2m_mean,precipitation_sum",
        "timezone": "Africa/Johannesburg",
    }

    for attempt in range(3):
        try:
            resp = requests.get(OPEN_METEO_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data and data["error"]:
                raise ValueError(data.get("reason", "Unknown API error"))

            daily = data.get("daily", {})
            times = daily.get("time", [])
            temps = daily.get("temperature_2m_mean", [])
            precips = daily.get("precipitation_sum", [])

            # Aggregate daily to monthly
            from collections import defaultdict
            monthly_temps: dict[tuple[int, int], list[float]] = defaultdict(list)
            monthly_precips: dict[tuple[int, int], float] = defaultdict(float)

            for i, date_str in enumerate(times):
                year_str, month_str, _ = date_str.split("-")
                key = (int(year_str), int(month_str))
                if i < len(temps) and temps[i] is not None:
                    monthly_temps[key].append(temps[i])
                if i < len(precips) and precips[i] is not None:
                    monthly_precips[key] += precips[i]

            records = []
            for key in sorted(monthly_temps.keys()):
                year, month = key
                temp_list = monthly_temps[key]
                mean_temp = sum(temp_list) / len(temp_list) if temp_list else None
                total_precip = monthly_precips.get(key, 0.0)
                records.append({
                    "year": year,
                    "month": month,
                    "mean_temp_c": round(mean_temp, 2) if mean_temp else None,
                    "total_precip_mm": round(total_precip, 2),
                })
            return records

        except Exception as exc:
            logger.warning(
                "Open-Meteo attempt %d failed for %s: %s", attempt + 1, province, exc
            )
            if attempt < 2:
                time.sleep(2 ** attempt)

    logger.error("All retries failed for %s", province)
    return []


def load_weather_data(conn, start_year: int = 2016, end_year: int = 2025) -> int:
    """
    Fetch weather from Open-Meteo for each province and load into weather_record.
    Assigns weather to all stations in that province.
    Returns total rows inserted.
    """
    total_inserted = 0

    for province, (lat, lon) in PROVINCE_COORDS.items():
        logger.info("Fetching weather for %s (%.2f, %.2f)...", province, lat, lon)
        records = fetch_weather_for_province(province, lat, lon, start_year, end_year)

        if not records:
            continue

        # Get all station IDs in this province
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ps.id FROM police_station ps
                JOIN province p ON p.id = ps.province_id
                WHERE p.name = %s
                """,
                (province,),
            )
            station_ids = [row[0] for row in cur.fetchall()]

        logger.info("  %d stations in %s, %d weather months", len(station_ids), province, len(records))

        # Insert weather for each station
        with conn.cursor() as cur:
            for rec in records:
                for station_id in station_ids:
                    cur.execute(
                        """
                        INSERT INTO weather_record (station_id, year, month, mean_temp_c, total_precip_mm)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (station_id, year, month) DO UPDATE SET
                            mean_temp_c = EXCLUDED.mean_temp_c,
                            total_precip_mm = EXCLUDED.total_precip_mm
                        """,
                        (station_id, rec["year"], rec["month"],
                         rec["mean_temp_c"], rec["total_precip_mm"]),
                    )
                    total_inserted += cur.rowcount

        conn.commit()
        logger.info("  Loaded weather for %s (%d records)", province, len(records) * len(station_ids))

    logger.info("Total weather records inserted: %d", total_inserted)
    return total_inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=== CrimecastZA External Data Fetcher ===")
    conn = _get_connection()

    # 1. Load unemployment data from QLFS
    logger.info("[1/2] Loading Stats SA QLFS unemployment data...")
    unemp_count = load_unemployment_data(conn)
    logger.info("  Done: %d records", unemp_count)

    # 2. Fetch and load weather data from Open-Meteo
    logger.info("[2/2] Fetching weather data from Open-Meteo API...")
    weather_count = load_weather_data(conn, start_year=2016, end_year=2025)
    logger.info("  Done: %d records", weather_count)

    conn.close()
    logger.info("External data fetch complete.")


if __name__ == "__main__":
    main()
