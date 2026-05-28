"""
pipeline/ingest.py

Main entry point for the SAPS data ingestion pipeline.

Reads all Excel files from the data/ directory, normalises the records,
loads them into PostgreSQL, and writes a pipeline_run_log entry.

Usage:
    python -m pipeline.ingest                        # uses DATA_DIR env var or ./data
    python -m pipeline.ingest --data-dir /path/data  # explicit path

Environment variables (all required unless --dry-run):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    DATA_DIR  (optional, defaults to ./data)
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import time

# Configure logging before any local imports so all modules pick it up
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

import psycopg2

from pipeline.db_loader import load_records
from pipeline.saps_reader import read_all_saps_files


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pipeline run log helpers
# ---------------------------------------------------------------------------

def _start_run_log(conn) -> int:
    """Insert a 'running' pipeline_run_log row and return its id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_run_log (run_start, status)
            VALUES (NOW(), 'running')
            RETURNING id
            """,
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def _finish_run_log(conn, run_id: int, status: str,
                    processed: int, skipped: int,
                    mape: dict | None = None,
                    error: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pipeline_run_log
            SET run_end           = NOW(),
                status            = %s,
                records_processed = %s,
                records_skipped   = %s,
                mape_per_category = %s,
                error_message     = %s
            WHERE id = %s
            """,
            (
                status,
                processed,
                skipped,
                json.dumps(mape) if mape else None,
                error,
                run_id,
            ),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(data_dir: str, dry_run: bool = False) -> None:
    """Execute the full ingestion pipeline."""
    t0 = time.time()
    logger.info("=== CrimecastZA SAPS Ingestion Pipeline ===")
    logger.info("Data directory: %s", data_dir)

    # 1. Read all Excel files
    logger.info("Step 1/3: Reading SAPS Excel files …")
    records = read_all_saps_files(data_dir)
    logger.info("Loaded %d deduplicated monthly records", len(records))

    if dry_run:
        logger.info("Dry-run mode — skipping database load.")
        logger.info("Sample records:")
        for r in records[:5]:
            logger.info("  %s", r)
        return

    # 2. Connect to DB and start run log
    logger.info("Step 2/3: Connecting to database …")
    conn = _get_connection()
    run_id = _start_run_log(conn)
    logger.info("Pipeline run log id: %d", run_id)

    # 3. Load into DB
    logger.info("Step 3/3: Loading records into database …")
    try:
        stats = load_records(records, conn)
    except Exception as exc:
        logger.error("Fatal error during DB load: %s", exc, exc_info=True)
        _finish_run_log(conn, run_id, "failed", 0, 0, error=str(exc))
        conn.close()
        sys.exit(1)

    elapsed = time.time() - t0
    _finish_run_log(
        conn, run_id,
        status="success",
        processed=stats["processed"],
        skipped=stats["skipped"],
    )
    conn.close()

    logger.info(
        "Pipeline complete in %.1fs — processed=%d inserted=%d skipped=%d",
        elapsed, stats["processed"], stats["inserted"], stats["skipped"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="CrimecastZA SAPS ingestion pipeline")
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("DATA_DIR", "data"),
        help="Directory containing SAPS Excel files (default: ./data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read files and print stats without writing to the database",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.data_dir):
        logger.error("Data directory not found: %s", args.data_dir)
        sys.exit(1)

    run(data_dir=args.data_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
