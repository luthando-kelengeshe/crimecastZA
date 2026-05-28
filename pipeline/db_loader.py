"""
pipeline/db_loader.py

Loads normalised SAPS crime records into the PostgreSQL database.

Handles upserts for all reference tables (province, police_station,
crime_category) and the monthly_crime_record fact table.

Usage:
    from pipeline.db_loader import load_records
    conn = psycopg2.connect(...)
    stats = load_records(records, conn)
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Province cache
# ---------------------------------------------------------------------------

def _ensure_provinces(conn) -> dict[str, int]:
    """Return a mapping of province_name → province_id, inserting any missing."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM province")
        return {name: pid for pid, name in cur.fetchall()}


def _upsert_province(name: str, cache: dict[str, int], conn) -> int:
    if name in cache:
        return cache[name]
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO province (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id",
            (name,),
        )
        pid = cur.fetchone()[0]
    cache[name] = pid
    return pid


# ---------------------------------------------------------------------------
# Police station cache
# ---------------------------------------------------------------------------

def _ensure_stations(conn) -> dict[tuple[str, int], int]:
    """Return a mapping of (upper_canonical_name, province_id) → station_id."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, UPPER(canonical_name), province_id FROM police_station")
        return {(name, prov_id): sid for sid, name, prov_id in cur.fetchall()}


def _upsert_station(
    canonical_name: str,
    original_name: str,
    province_id: int,
    cache: dict[tuple[str, int], int],
    conn,
) -> int:
    key = (canonical_name.upper(), province_id)
    if key in cache:
        return cache[key]
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO police_station (canonical_name, original_name, province_id, location)
            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(0, 0), 4326))
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (canonical_name, original_name, province_id),
        )
        row = cur.fetchone()
        if row is None:
            # Row already existed — fetch its id
            cur.execute(
                "SELECT id FROM police_station WHERE UPPER(canonical_name)=%s AND province_id=%s",
                (canonical_name.upper(), province_id),
            )
            row = cur.fetchone()
        sid = row[0]
    cache[key] = sid
    return sid


# ---------------------------------------------------------------------------
# Crime category cache
# ---------------------------------------------------------------------------

def _ensure_categories(conn) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM crime_category")
        return {name: cid for cid, name in cur.fetchall()}


def _upsert_category(name: str, cache: dict[str, int], conn) -> int:
    if name in cache:
        return cache[name]
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO crime_category (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id",
            (name,),
        )
        cid = cur.fetchone()[0]
    cache[name] = cid
    return cid


# ---------------------------------------------------------------------------
# Bulk upsert monthly_crime_record
# ---------------------------------------------------------------------------

_BATCH_SIZE = 5000


def _bulk_upsert_records(batch: list[tuple], conn) -> int:
    """
    Bulk-upsert a batch of (station_id, category_id, year, month, monthly_count)
    tuples into monthly_crime_record.

    Returns the number of rows affected.
    """
    if not batch:
        return 0
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO monthly_crime_record
                (station_id, category_id, year, month, monthly_count)
            VALUES %s
            ON CONFLICT (station_id, category_id, year, month)
            DO UPDATE SET monthly_count = EXCLUDED.monthly_count
            """,
            batch,
            template="(%s, %s, %s, %s, %s)",
            page_size=_BATCH_SIZE,
        )
        return cur.rowcount


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_records(records: list[dict], conn) -> dict[str, int]:
    """
    Load a list of monthly record dicts into the database.

    Each dict must have keys:
        station_name, province, crime_category, year, month, monthly_count.
    Optional keys: district (used as original_name fallback).

    Returns a stats dict:
        {
            'processed': int,   # records attempted
            'inserted':  int,   # rows upserted into monthly_crime_record
            'skipped':   int,   # records skipped due to missing/invalid data
        }
    """
    province_cache = _ensure_provinces(conn)
    station_cache = _ensure_stations(conn)
    category_cache = _ensure_categories(conn)

    processed = 0
    skipped = 0
    batch: list[tuple] = []
    total_inserted = 0

    for rec in records:
        processed += 1

        station_name = (rec.get("station_name") or "").strip()
        province_name = (rec.get("province") or "").strip()
        crime_cat = (rec.get("crime_category") or "").strip()
        year = rec.get("year")
        month = rec.get("month")
        count = rec.get("monthly_count")

        if not station_name or not province_name or not crime_cat:
            skipped += 1
            continue
        if year is None or month is None or count is None:
            skipped += 1
            continue
        if not (1 <= month <= 12) or year < 2000:
            skipped += 1
            continue

        try:
            province_id = _upsert_province(province_name, province_cache, conn)
            canonical = station_name.strip().title()
            original = rec.get("district") or station_name
            station_id = _upsert_station(canonical, original, province_id, station_cache, conn)
            category_id = _upsert_category(crime_cat, category_cache, conn)
        except Exception as exc:
            logger.warning("Skipping record due to reference upsert error: %s", exc)
            skipped += 1
            continue

        batch.append((station_id, category_id, year, month, count))

        if len(batch) >= _BATCH_SIZE:
            total_inserted += _bulk_upsert_records(batch, conn)
            conn.commit()
            batch = []
            logger.debug("Committed batch; total inserted so far: %d", total_inserted)

    # Flush remaining
    if batch:
        total_inserted += _bulk_upsert_records(batch, conn)
        conn.commit()

    logger.info(
        "load_records complete: processed=%d inserted=%d skipped=%d",
        processed, total_inserted, skipped,
    )
    return {"processed": processed, "inserted": total_inserted, "skipped": skipped}
