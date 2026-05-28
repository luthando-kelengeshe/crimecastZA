"""CrimecastZA SAPS CSV validator."""

import csv

from pipeline.models import ValidationResult

REQUIRED_COLUMNS: list[str] = [
    "police_station_name",
    "province",
    "crime_category",
    "quarterly_count",
]


def validate_saps_file(
    filepath: str,
    required_columns: list[str] = REQUIRED_COLUMNS,
) -> ValidationResult:
    """Validate a SAPS CSV file by checking its header row.

    Reads only the first (header) row of the CSV file and checks that all
    required columns are present.

    Args:
        filepath: Path to the CSV file to validate.
        required_columns: Column names that must be present in the header.
            Defaults to the four standard SAPS columns.

    Returns:
        ValidationResult(ok=True) if all required columns are present,
        ValidationResult(ok=False, errors=[...]) listing missing columns otherwise.
    """
    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])

    header_set = set(header)
    missing = [col for col in required_columns if col not in header_set]

    if missing:
        errors = [f"Missing required column: {col}" for col in missing]
        return ValidationResult(ok=False, errors=errors)

    return ValidationResult(ok=True)
