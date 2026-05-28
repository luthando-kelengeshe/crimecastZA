"""CrimecastZA SAPS CSV parser.

Provides:
  - ParseError: exception raised on malformed CSV rows
  - parse_saps_csv: reads a SAPS CSV file and returns a list of record dicts
  - serialise_to_csv: writes a list of record dicts back to CSV
"""

import csv
from typing import Any

# Required columns in the exact order expected by SAPS source files
REQUIRED_COLUMNS = [
    "police_station_name",
    "province",
    "crime_category",
    "quarterly_count",
]


class ParseError(Exception):
    """Raised when a SAPS CSV row cannot be parsed.

    Attributes:
        row_number: 1-based row number (header = 0, first data row = 1).
        field_name: name of the field that caused the failure.
    """

    def __init__(self, row_number: int, field_name: str, message: str = "") -> None:
        self.row_number = row_number
        self.field_name = field_name
        detail = message or f"Parse failure at row {row_number}, field '{field_name}'"
        super().__init__(detail)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"ParseError(row_number={self.row_number!r}, "
            f"field_name={self.field_name!r})"
        )


def parse_saps_csv(filepath: str) -> list[dict]:
    """Read a SAPS quarterly crime statistics CSV file.

    Parameters
    ----------
    filepath:
        Path to the CSV file to read.

    Returns
    -------
    list[dict]
        Each dict has keys:
          - ``police_station_name`` (str)
          - ``province`` (str)
          - ``crime_category`` (str)
          - ``quarterly_count`` (int)

    Raises
    ------
    ParseError
        If any row is missing a required field or ``quarterly_count`` cannot
        be converted to ``int``.  The exception carries the 1-based
        ``row_number`` and the ``field_name`` that caused the failure.
    """
    records: list[dict] = []

    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        # Validate that all required columns are present in the header
        if reader.fieldnames is None:
            raise ParseError(row_number=0, field_name="<header>",
                             message="CSV file has no header row")

        for col in REQUIRED_COLUMNS:
            if col not in reader.fieldnames:
                raise ParseError(
                    row_number=0,
                    field_name=col,
                    message=f"Required column '{col}' is missing from the CSV header",
                )

        for row_number, raw_row in enumerate(reader, start=1):
            record = _parse_row(raw_row, row_number)
            records.append(record)

    return records


def _parse_row(raw_row: dict[str, Any], row_number: int) -> dict:
    """Parse and validate a single CSV row.

    Parameters
    ----------
    raw_row:
        Dict produced by ``csv.DictReader`` for one data row.
    row_number:
        1-based row index used in error reporting.

    Returns
    -------
    dict
        Validated record with correct Python types.

    Raises
    ------
    ParseError
        On missing field or type mismatch.
    """
    result: dict = {}

    # String fields — must be present (not None) and must be strings
    for field in ("police_station_name", "province", "crime_category"):
        value = raw_row.get(field)
        if value is None:
            raise ParseError(
                row_number=row_number,
                field_name=field,
                message=f"Row {row_number}: required field '{field}' is missing",
            )
        # csv.DictReader always returns str for present fields; cast defensively
        result[field] = str(value)

    # Integer field — must be present and convertible to int
    raw_count = raw_row.get("quarterly_count")
    if raw_count is None:
        raise ParseError(
            row_number=row_number,
            field_name="quarterly_count",
            message=f"Row {row_number}: required field 'quarterly_count' is missing",
        )
    try:
        result["quarterly_count"] = int(raw_count)
    except (ValueError, TypeError):
        raise ParseError(
            row_number=row_number,
            field_name="quarterly_count",
            message=(
                f"Row {row_number}: 'quarterly_count' value {raw_count!r} "
                "cannot be converted to int"
            ),
        )

    return result


def serialise_to_csv(records: list[dict], filepath: str) -> None:
    """Write a list of record dicts to a CSV file.

    The output columns are written in the canonical SAPS source order:
    ``police_station_name``, ``province``, ``crime_category``,
    ``quarterly_count``.

    Parameters
    ----------
    records:
        List of dicts, each containing the four required keys.
    filepath:
        Destination file path.  The file is created or overwritten.
    """
    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=REQUIRED_COLUMNS,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(records)
