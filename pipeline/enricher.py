"""CrimecastZA pipeline enricher.

Provides:
  - fetch_unemployment: fetch QLFS unemployment rates with DB fallback
  - load_calendar: insert SA public holidays and payday dates (2005–2027)
"""

import datetime
import logging
from typing import Any

import requests
from dateutil.easter import easter

from pipeline.logger import PipelineLogger

_log = PipelineLogger(step="enricher")


# ---------------------------------------------------------------------------
# Unemployment loader
# ---------------------------------------------------------------------------

def fetch_unemployment(qlfs_url: str, db_conn) -> dict:
    """Fetch QLFS unemployment rates from *qlfs_url*.

    On any exception (connection error, HTTP error, timeout) logs a warning
    using PipelineLogger and falls back to the most recently stored rates
    from the database.

    Returns
    -------
    dict
        Keyed by ``(province_name, year, quarter)`` → ``rate`` (Decimal/float).
    """
    try:
        response = requests.get(qlfs_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Expected JSON structure: list of objects with keys
        # province, year, quarter, rate
        result: dict = {}
        for row in data:
            key = (str(row["province"]), int(row["year"]), int(row["quarter"]))
            result[key] = float(row["rate"])
        return result

    except Exception as exc:  # noqa: BLE001
        _log.log(
            level="WARNING",
            message=(
                f"Failed to fetch QLFS data from {qlfs_url!r}: "
                f"{type(exc).__name__}: {exc}; "
                f"falling back to stored rates "
                f"(timestamp={datetime.datetime.now(datetime.timezone.utc).isoformat()})"
            ),
        )
        return _fallback_unemployment(db_conn)


def _fallback_unemployment(db_conn) -> dict:
    """Return the most recently stored unemployment rates from the DB."""
    sql = (
        "SELECT p.name, ur.year, ur.quarter, ur.rate "
        "FROM unemployment_record ur "
        "JOIN province p ON p.id = ur.province_id "
        "ORDER BY ur.year DESC, ur.quarter DESC"
    )
    with db_conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    result: dict = {}
    for province_name, year, quarter, rate in rows:
        key = (str(province_name), int(year), int(quarter))
        if key not in result:  # keep most-recent (already ordered DESC)
            result[key] = float(rate)
    return result


# ---------------------------------------------------------------------------
# Calendar loader
# ---------------------------------------------------------------------------

# Fixed-date South African public holidays (month, day)
_FIXED_HOLIDAYS: list[tuple[int, int]] = [
    (1, 1),    # New Year's Day
    (3, 21),   # Human Rights Day
    (4, 27),   # Freedom Day
    (5, 1),    # Workers' Day
    (6, 16),   # Youth Day
    (8, 9),    # National Women's Day
    (9, 24),   # Heritage Day
    (12, 16),  # Day of Reconciliation
    (12, 25),  # Christmas Day
    (12, 26),  # Day of Goodwill
]


def _public_holidays_for_year(year: int) -> set[datetime.date]:
    """Return the full set of public holiday dates for *year*.

    Includes the Monday substitute when a fixed holiday falls on a Sunday.
    Includes Good Friday and Family Day (day after Easter).
    """
    holidays: set[datetime.date] = set()

    # Fixed holidays
    for month, day in _FIXED_HOLIDAYS:
        date = datetime.date(year, month, day)
        holidays.add(date)
        # Sunday → Monday substitute
        if date.weekday() == 6:  # 6 = Sunday
            holidays.add(date + datetime.timedelta(days=1))

    # Easter-based holidays
    easter_sunday = easter(year)
    good_friday = easter_sunday - datetime.timedelta(days=2)
    family_day = easter_sunday + datetime.timedelta(days=1)
    holidays.add(good_friday)
    holidays.add(family_day)

    return holidays


def _last_working_day(year: int, month: int,
                      holidays: set[datetime.date]) -> datetime.date:
    """Return the last Mon–Fri day of *month*/*year* that is not a public holiday."""
    # Start from the last day of the month and walk backwards
    if month == 12:
        last_day = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

    candidate = last_day
    while True:
        # weekday(): 0=Mon … 4=Fri, 5=Sat, 6=Sun
        if candidate.weekday() < 5 and candidate not in holidays:
            return candidate
        candidate -= datetime.timedelta(days=1)


def load_calendar(db_conn) -> int:
    """Insert SA public holidays and payday dates for 2005–2027.

    Uses ``ON CONFLICT (event_date) DO NOTHING`` so the function is
    idempotent.  Returns the total number of rows actually inserted.
    """
    insert_sql = (
        "INSERT INTO calendar_event (event_date, event_type, is_flagged) "
        "VALUES (%s, %s, TRUE) "
        "ON CONFLICT (event_date) DO NOTHING"
    )

    rows_inserted = 0

    with db_conn.cursor() as cur:
        for year in range(2005, 2028):  # 2005 inclusive, 2027 inclusive
            holidays = _public_holidays_for_year(year)

            # Insert public holidays
            for holiday_date in sorted(holidays):
                cur.execute(insert_sql, (holiday_date, "public_holiday"))
                rows_inserted += cur.rowcount

            # Insert payday for each month (last working day, not a holiday)
            for month in range(1, 13):
                payday = _last_working_day(year, month, holidays)
                cur.execute(insert_sql, (payday, "payday"))
                rows_inserted += cur.rowcount

    db_conn.commit()
    return rows_inserted
