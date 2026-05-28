"""Property-based tests for the SAPS CSV validator.

# Feature: crimecast-za, Property 1: SAPS CSV column validation is universal
"""

import csv
import os
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.validator import REQUIRED_COLUMNS, validate_saps_file

# All columns that may appear in a generated CSV header (required + extras)
_ALL_POSSIBLE_COLUMNS = REQUIRED_COLUMNS + [
    "station_code",
    "district",
    "year",
    "quarter",
    "report_date",
    "notes",
    "source_url",
]

# **Validates: Requirements 1.2**


@given(
    columns=st.sets(
        st.sampled_from(_ALL_POSSIBLE_COLUMNS),
        min_size=0,
        max_size=len(_ALL_POSSIBLE_COLUMNS),
    )
)
@settings(max_examples=100)
def test_validator_accepts_iff_all_required_columns_present(columns: set[str]) -> None:
    """Property 1: the validator accepts a CSV file if and only if all four
    required columns are present; for any file missing one or more columns it
    returns a failed ValidationResult that identifies every missing column.
    """
    # Write a temporary CSV whose header is exactly the generated column set.
    # Column order is sorted for determinism; the validator must not care about order.
    header = sorted(columns)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        newline="",
        encoding="utf-8",
        delete=False,
    ) as tmp:
        writer = csv.writer(tmp)
        writer.writerow(header)
        tmp_path = tmp.name

    try:
        result = validate_saps_file(tmp_path, REQUIRED_COLUMNS)

        missing = set(REQUIRED_COLUMNS) - columns

        if not missing:
            # All required columns present → must accept
            assert result.ok is True, (
                f"Expected ok=True when all required columns are present, "
                f"got ok=False with errors={result.errors!r}"
            )
            assert result.errors == [], (
                f"Expected no errors when ok=True, got {result.errors!r}"
            )
        else:
            # At least one required column missing → must reject
            assert result.ok is False, (
                f"Expected ok=False when columns {missing!r} are missing, "
                f"but got ok=True"
            )
            # Every missing column must be mentioned in the errors list
            for col in missing:
                assert any(col in err for err in result.errors), (
                    f"Missing column '{col}' not reported in errors: {result.errors!r}"
                )
    finally:
        os.unlink(tmp_path)
