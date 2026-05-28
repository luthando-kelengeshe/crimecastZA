"""
pipeline/geocode_stations.py

Assigns approximate geographic coordinates to police stations based on
their province. Spreads stations across the province area with some
randomization so they appear as distinct points on the map.

Usage:
    python -m pipeline.geocode_stations
"""

import logging
import os
import random
import sys

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Province center coordinates and spread radius (degrees)
PROVINCE_BOUNDS = {
    "Eastern Cape":    {"lat": -32.0, "lon": 27.0, "spread": 2.5},
    "Free State":      {"lat": -29.0, "lon": 26.5, "spread": 2.0},
    "Gauteng":         {"lat": -26.1, "lon": 28.1, "spread": 0.6},
    "KwaZulu-Natal":   {"lat": -29.5, "lon": 30.5, "spread": 2.0},
    "Limpopo":         {"lat": -23.5, "lon": 29.5, "spread": 2.0},
    "Mpumalanga":      {"lat": -25.5, "lon": 30.5, "spread": 1.5},
    "North West":      {"lat": -26.5, "lon": 25.5, "spread": 2.0},
    "Northern Cape":   {"lat": -29.5, "lon": 21.0, "spread": 4.0},
    "Western Cape":    {"lat": -33.5, "lon": 19.5, "spread": 2.5},
}


def geocode_stations():
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        logger.error("Missing env vars: %s", missing)
        sys.exit(1)

    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )

    random.seed(42)  # Reproducible positions
    updated = 0

    with conn.cursor() as cur:
        cur.execute("""
            SELECT ps.id, p.name as province
            FROM police_station ps
            JOIN province p ON p.id = ps.province_id
        """)
        stations = cur.fetchall()

        for station_id, province in stations:
            bounds = PROVINCE_BOUNDS.get(province)
            if not bounds:
                continue

            # Generate a position within the province bounds
            lat = bounds["lat"] + random.uniform(-bounds["spread"], bounds["spread"])
            lon = bounds["lon"] + random.uniform(-bounds["spread"], bounds["spread"])

            cur.execute(
                """
                UPDATE police_station
                SET location = ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                WHERE id = %s
                """,
                (lon, lat, station_id),
            )
            updated += 1

    conn.commit()
    conn.close()
    logger.info("Geocoded %d stations", updated)


if __name__ == "__main__":
    geocode_stations()
