"""
pipeline/saps_reader.py

Reads SAPS crime statistics from the downloaded Excel files in the data/ directory.

Handles two distinct file formats:
  - RAW Data format  : newer files (2022-Q3 onwards) — header on row 2,
                       columns: Station(4), District(5), Province(6),
                       Crime_Category(7), then datetime columns for monthly counts.
  - Station format   : older files — header on row 1, column positions vary
                       but are detected by header name matching.
  - Annual format    : annual release files — annual totals keyed by financial
                       year string like '2019-2020'; converted to monthly estimates.

All formats produce a unified list of MonthlyRecord dicts:
    {
        'station_name': str,
        'province':     str,
        'district':     str,
        'crime_category': str,
        'year':         int,
        'month':        int,
        'monthly_count': int,
        'source_file':  str,
    }
"""

from __future__ import annotations

import datetime
import logging
import math
import os
import re
from typing import Iterator

import openpyxl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Province name normalisation map
# ---------------------------------------------------------------------------
_PROVINCE_ALIASES: dict[str, str] = {
    "EASTERN CAPE": "Eastern Cape",
    "EASTERN CAPE PROVINCE": "Eastern Cape",
    "EASTERN_CAPE": "Eastern Cape",
    "EC": "Eastern Cape",
    "WESTERN CAPE": "Western Cape",
    "WESTERN_CAPE": "Western Cape",
    "WC": "Western Cape",
    "NORTHERN CAPE": "Northern Cape",
    "NORTHERN_CAPE": "Northern Cape",
    "NC": "Northern Cape",
    "FREE STATE": "Free State",
    "FREE_STATE": "Free State",
    "FS": "Free State",
    "KWAZULU-NATAL": "KwaZulu-Natal",
    "KWAZULU/NATAL": "KwaZulu-Natal",
    "KWAZULU_NATAL": "KwaZulu-Natal",
    "KZN": "KwaZulu-Natal",
    "NORTH WEST": "North West",
    "NORTH_WEST": "North West",
    "NW": "North West",
    "GAUTENG": "Gauteng",
    "GAUTENG_PROVINCE": "Gauteng",
    "GP": "Gauteng",
    "MPUMALANGA": "Mpumalanga",
    "MPUMALANGA_PROVINCE": "Mpumalanga",
    "MP": "Mpumalanga",
    "LIMPOPO": "Limpopo",
    "LIMPOPO_PROVINCE": "Limpopo",
    "LP": "Limpopo",
}

_VALID_PROVINCES = {
    "Eastern Cape", "Western Cape", "Northern Cape", "Free State",
    "KwaZulu-Natal", "North West", "Gauteng", "Mpumalanga", "Limpopo",
}

# ---------------------------------------------------------------------------
# Crime category normalisation map  (raw → canonical)
# ---------------------------------------------------------------------------
_CRIME_CATEGORY_ALIASES: dict[str, str] = {
    # 17 Community Reported Serious Crime variants
    "17 community reported serious crime": "17 Community Reported Serious Crime",
    "17 community reported serious crimes": "17 Community Reported Serious Crime",
    # Attempted sexual offences
    "attempted sexual offences": "Attempted Sexual Offences",
    # Bank robbery
    "bank robbery": "Bank Robbery",
    # Commercial crime
    "commercial crime": "Commercial Crime",
    # Contact crime
    "contact crime": "Contact Crime",
    "contact crime (crimes against the person)": "Contact Crime",
    "contact crimes (crimes against the person)": "Contact Crime",
    # Contact sexual offences
    "contact sexual offences": "Contact Sexual Offences",
    # Contact-related crime
    "contact-related crime": "Contact-Related Crime",
    "contact-related crimes": "Contact-Related Crime",
    # Crimen injuria
    "crimen injuria": "Crimen Injuria",
    # Drug-related crime
    "drug-related crime": "Drug-Related Crime",
    # Other serious crime
    "other serious crime": "Other Serious Crime",
    "other serious crimes": "Other Serious Crime",
    # Property-related crime
    "property-related crime": "Property-Related Crime",
    "property-related crimes": "Property-Related Crime",
    # Sexual assault
    "sexual assault": "Sexual Assault",
    # Sexual offences
    "sexual offences": "Sexual Offences",
    # Sexual offences detected as a result of police action
    "sexual offences detected as a result of police action": "Sexual Offences Detected as a Result of Police Action",
    # Stock-theft
    "stock-theft": "Stock-Theft",
    # TRIO crime
    "trio crime": "TRIO Crime",
}


def _normalise_crime_category(raw: str) -> str:
    """Return a canonical crime category name."""
    key = raw.strip().lower()
    return _CRIME_CATEGORY_ALIASES.get(key, raw.strip())


def _normalise_province(raw: str | None) -> str | None:
    """Return a canonical province name or None if unrecognised."""
    if not raw:
        return None
    key = str(raw).strip().upper()
    if key in _PROVINCE_ALIASES:
        return _PROVINCE_ALIASES[key]
    # Try title-case match
    title = str(raw).strip().title()
    if title in _VALID_PROVINCES:
        return title
    return None


def _clean_str(val: object) -> str:
    """Strip and title-case a string value."""
    if val is None:
        return ""
    return str(val).strip()


def _safe_int(val: object) -> int | None:
    """Convert a cell value to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Financial year string → (start_year, start_month) helper
# ---------------------------------------------------------------------------
_FY_RE = re.compile(r"(\d{4})[/_-](\d{4})")


def _parse_financial_year(fy_str: str) -> tuple[int, int] | None:
    """
    Parse a financial year string like '2019-2020' or '2019/2020'.
    Returns (start_year, start_month=4) — SA financial year starts April.
    """
    m = _FY_RE.match(str(fy_str).strip())
    if not m:
        return None
    return int(m.group(1)), 4  # April start


# ---------------------------------------------------------------------------
# Format A: RAW Data sheet (newer files, 2022-Q3 onwards)
# ---------------------------------------------------------------------------

def _read_raw_data_sheet(ws, source_file: str) -> Iterator[dict]:
    """
    Parse a 'RAW Data' sheet.

    Header is on row 2 (index 1 in 0-based).  Fixed columns:
      col 4 = Station, col 5 = District, col 6 = Province,
      col 7 = Crime_Category.
    Remaining datetime columns are monthly counts.
    """
    rows = ws.iter_rows(values_only=True)

    # Skip rows until we find the header row (contains 'Station' in col 4)
    header: tuple | None = None
    for row in rows:
        if len(row) > 7 and _clean_str(row[4]).lower() == "station":
            header = row
            break

    if header is None:
        logger.warning("RAW Data sheet in %s: could not find header row", source_file)
        return

    # Build index of datetime columns → (year, month)
    date_col_map: dict[int, tuple[int, int]] = {}
    for i, cell in enumerate(header):
        if isinstance(cell, datetime.datetime):
            date_col_map[i] = (cell.year, cell.month)

    if not date_col_map:
        logger.warning("RAW Data sheet in %s: no date columns found", source_file)
        return

    for row in rows:
        if not row or row[4] is None:
            continue

        station = _clean_str(row[4])
        district = _clean_str(row[5]) if len(row) > 5 else ""
        province_raw = _clean_str(row[6]) if len(row) > 6 else ""
        crime_cat = _clean_str(row[7]) if len(row) > 7 else ""

        if not station or not crime_cat:
            continue

        province = _normalise_province(province_raw)
        if province is None:
            logger.debug("Skipping row with unrecognised province '%s' in %s",
                         province_raw, source_file)
            continue

        crime_cat = _normalise_crime_category(crime_cat)

        for col_idx, (year, month) in date_col_map.items():
            if col_idx >= len(row):
                continue
            count = _safe_int(row[col_idx])
            if count is None or count < 0:
                continue
            yield {
                "station_name": station,
                "province": province,
                "district": district,
                "crime_category": crime_cat,
                "year": year,
                "month": month,
                "monthly_count": count,
                "source_file": source_file,
            }


# ---------------------------------------------------------------------------
# Format B: 'station' sheet (older quarterly files)
# ---------------------------------------------------------------------------

# Column names we look for (case-insensitive) to identify key fields
_STATION_COL_NAMES = {"station"}
_PROVINCE_COL_NAMES = {"prov", "province_station", "province"}
_DISTRICT_COL_NAMES = {"district"}
_CRIME_COL_NAMES = {"crime_category", "crime category"}


def _find_col(header: tuple, names: set[str]) -> int | None:
    """Return the first column index whose header matches any name in `names`."""
    for i, h in enumerate(header):
        if h and isinstance(h, str) and h.strip().lower() in names:
            return i
    return None


def _read_station_sheet(ws, source_file: str) -> Iterator[dict]:
    """
    Parse an older 'station' / 'Station' sheet.

    Header is on row 1.  Column positions vary; we detect them by name.
    Datetime columns are monthly counts.
    """
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if header is None:
        return

    station_col = _find_col(header, _STATION_COL_NAMES)
    province_col = _find_col(header, _PROVINCE_COL_NAMES)
    district_col = _find_col(header, _DISTRICT_COL_NAMES)
    crime_col = _find_col(header, _CRIME_COL_NAMES)

    if station_col is None or province_col is None or crime_col is None:
        logger.warning(
            "station sheet in %s: could not identify required columns "
            "(station=%s, province=%s, crime=%s)",
            source_file, station_col, province_col, crime_col,
        )
        return

    # Build date column map
    date_col_map: dict[int, tuple[int, int]] = {}
    for i, cell in enumerate(header):
        if isinstance(cell, datetime.datetime):
            date_col_map[i] = (cell.year, cell.month)

    if not date_col_map:
        logger.warning("station sheet in %s: no date columns found", source_file)
        return

    for row in rows_iter:
        if not row or row[station_col] is None:
            continue

        station = _clean_str(row[station_col])
        province_raw = _clean_str(row[province_col])
        district = _clean_str(row[district_col]) if district_col is not None and district_col < len(row) else ""
        crime_cat = _clean_str(row[crime_col]) if crime_col < len(row) else ""

        if not station or not crime_cat:
            continue

        province = _normalise_province(province_raw)
        if province is None:
            continue

        crime_cat = _normalise_crime_category(crime_cat)

        for col_idx, (year, month) in date_col_map.items():
            if col_idx >= len(row):
                continue
            count = _safe_int(row[col_idx])
            if count is None or count < 0:
                continue
            yield {
                "station_name": station,
                "province": province,
                "district": district,
                "crime_category": crime_cat,
                "year": year,
                "month": month,
                "monthly_count": count,
                "source_file": source_file,
            }


# ---------------------------------------------------------------------------
# Format C: Annual release files ('station data YYYY', 'Station data')
# ---------------------------------------------------------------------------

_ANNUAL_STATION_COL_NAMES = {"station", "station_name"}
_ANNUAL_PROVINCE_COL_NAMES = {"province_station", "prov", "province"}
_ANNUAL_CRIME_COL_NAMES = {"crime category", "crime_category"}


def _read_annual_station_sheet(ws, source_file: str) -> Iterator[dict]:
    """
    Parse an annual station data sheet.

    Header is on row 1.  Financial year columns like '2019-2020' contain
    annual totals; we convert to monthly estimates (floor(annual / 12)).
    """
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if header is None:
        return

    station_col = _find_col(header, _ANNUAL_STATION_COL_NAMES)
    province_col = _find_col(header, _ANNUAL_PROVINCE_COL_NAMES)
    crime_col = _find_col(header, _ANNUAL_CRIME_COL_NAMES)

    if station_col is None or province_col is None or crime_col is None:
        logger.warning(
            "Annual station sheet in %s: could not identify required columns",
            source_file,
        )
        return

    # Build financial year column map: col_idx → list of (year, month) for Apr–Mar
    fy_col_map: dict[int, list[tuple[int, int]]] = {}
    for i, cell in enumerate(header):
        if cell and isinstance(cell, str):
            parsed = _parse_financial_year(cell)
            if parsed:
                start_year, start_month = parsed
                # Generate 12 months: Apr(start_year) … Mar(start_year+1)
                months = []
                for offset in range(12):
                    m = start_month + offset
                    y = start_year + (m - 1) // 12
                    m = ((m - 1) % 12) + 1
                    months.append((y, m))
                fy_col_map[i] = months

    if not fy_col_map:
        logger.warning("Annual station sheet in %s: no financial year columns found", source_file)
        return

    for row in rows_iter:
        if not row or row[station_col] is None:
            continue

        station = _clean_str(row[station_col])
        province_raw = _clean_str(row[province_col])
        crime_cat = _clean_str(row[crime_col]) if crime_col < len(row) else ""

        if not station or not crime_cat:
            continue

        province = _normalise_province(province_raw)
        if province is None:
            continue

        crime_cat = _normalise_crime_category(crime_cat)

        for col_idx, months in fy_col_map.items():
            if col_idx >= len(row):
                continue
            annual_count = _safe_int(row[col_idx])
            if annual_count is None or annual_count < 0:
                continue
            monthly_est = math.floor(annual_count / 12)
            for year, month in months:
                yield {
                    "station_name": station,
                    "province": province,
                    "district": "",
                    "crime_category": crime_cat,
                    "year": year,
                    "month": month,
                    "monthly_count": monthly_est,
                    "source_file": source_file,
                }


# ---------------------------------------------------------------------------
# File dispatcher
# ---------------------------------------------------------------------------

# Map filename patterns to (sheet_name_or_None, reader_function)
# None sheet means we auto-detect.
_FILE_DISPATCH: list[tuple[str, str | None, str]] = [
    # Newer RAW Data files
    ("2022-2023-Q3", "RAW Data", "raw"),
    ("2022-2023-Q4", "RAW Data", "raw"),
    ("2025-2026_-_1st", "RAW Data", "raw"),
    ("2025-2026_-_2nd", "RAW Data", "raw"),
    ("2025-2026_-_3rd", "RAW Data", "raw"),
    ("2025-2026_-_4th", "RAW Data", "raw"),
    # Older quarterly station files
    ("crime_statistics_july_september", "station", "station"),
    ("crime_statistics_third_qaurter", "station", "station"),
    ("crime_statistics_fourth_qaurter", "Station", "station"),
    ("first_quarter 2020_2021", "station", "station"),
    ("First Quarter Crime data 2022_2023", "station", "station"),
    ("First_Quarter_Crime_Data 2021_2022", "station", "station"),
    ("second_quarter_2021_2022", "station", "station"),
    ("third_quarter_2021_2022", "station Redraw", "station"),
    ("fourth_quarter_2021_2022", "station Redraw", "station"),
    ("2022-2023-Q2", "station", "station"),
    # Annual release files
    ("Crime-Statistics-2019_2020", "station data 2020", "annual"),
    ("Crime-Statistics-2020_2021-Release", "station data 2021", "annual"),
    ("Crime-Statistics-2021_2022-latest", "Station data", "annual"),
]


def _dispatch(filename: str) -> tuple[str | None, str] | None:
    """Return (sheet_name, reader_type) for a given filename, or None."""
    basename = os.path.basename(filename)
    for pattern, sheet, reader in _FILE_DISPATCH:
        if pattern in basename:
            return sheet, reader
    return None


def read_saps_file(filepath: str) -> list[dict]:
    """
    Read a single SAPS Excel file and return a list of monthly record dicts.

    Each dict has keys: station_name, province, district, crime_category,
    year, month, monthly_count, source_file.

    Returns an empty list if the file format is unrecognised or an error occurs.
    """
    dispatch = _dispatch(filepath)
    if dispatch is None:
        logger.warning("Unrecognised SAPS file format: %s — skipping", filepath)
        return []

    sheet_name, reader_type = dispatch
    source_file = os.path.basename(filepath)

    try:
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    except Exception as exc:
        logger.error("Failed to open %s: %s", filepath, exc)
        return []

    try:
        if sheet_name not in wb.sheetnames:
            logger.warning("Sheet '%s' not found in %s (available: %s)",
                           sheet_name, filepath, wb.sheetnames)
            return []

        ws = wb[sheet_name]

        if reader_type == "raw":
            records = list(_read_raw_data_sheet(ws, source_file))
        elif reader_type == "station":
            records = list(_read_station_sheet(ws, source_file))
        elif reader_type == "annual":
            records = list(_read_annual_station_sheet(ws, source_file))
        else:
            logger.warning("Unknown reader type '%s' for %s", reader_type, filepath)
            records = []

    finally:
        wb.close()

    logger.info("Read %d records from %s", len(records), source_file)
    return records


def read_all_saps_files(data_dir: str) -> list[dict]:
    """
    Read all SAPS Excel files from `data_dir` and return a deduplicated
    list of monthly record dicts.

    Deduplication key: (station_name, province, crime_category, year, month).
    When duplicates exist, the record with the higher monthly_count is kept
    (newer files generally supersede older ones).
    """
    xlsx_files = sorted(
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.endswith(".xlsx")
    )

    all_records: list[dict] = []
    for filepath in xlsx_files:
        records = read_saps_file(filepath)
        all_records.extend(records)
        logger.info("Loaded %d records from %s", len(records), os.path.basename(filepath))

    # Deduplicate: keep highest count per (station, province, category, year, month)
    dedup: dict[tuple, dict] = {}
    for rec in all_records:
        key = (
            rec["station_name"].upper(),
            rec["province"],
            rec["crime_category"].upper(),
            rec["year"],
            rec["month"],
        )
        existing = dedup.get(key)
        if existing is None or rec["monthly_count"] > existing["monthly_count"]:
            dedup[key] = rec

    result = list(dedup.values())
    logger.info(
        "Total: %d raw records -> %d deduplicated records from %d files",
        len(all_records), len(result), len(xlsx_files),
    )
    return result
