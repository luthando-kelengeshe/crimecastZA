"""Property-based tests for the SAPS CSV parser.

# Feature: crimecast-za, Property 31: CSV parse type correctness
# Feature: crimecast-za, Property 32: CSV parse error identification
# Feature: crimecast-za, Property 33: CSV serialisation column order
# Feature: crimecast-za, Property 34: CSV round-trip fidelity
"""

import csv
import tempfile
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.parser import ParseError, parse_saps_csv, serialise_to_csv, REQUIRED_COLUMNS

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Printable text that avoids characters that would break CSV parsing
_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters=" -'.",
    ),
    min_size=1,
    max_size=80,
)

_valid_record = st.fixed_dictionaries(
    {
        "police_station_name": _safe_text,
        "province": _safe_text,
        "crime_category": _safe_text,
        "quarterly_count": st.integers(min_value=0, max_value=100_000),
    }
)

_valid_records = st.lists(_valid_record, min_size=1, max_size=50)


def _write_valid_csv(records: list[dict]) -> str:
    """Write records to a temp CSV file and return the file path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(records)
        return fh.name


# ---------------------------------------------------------------------------
# Property 31: CSV parse type correctness
# ---------------------------------------------------------------------------

@given(records=_valid_records)
@settings(max_examples=100)
def test_parse_type_correctness(records: list[dict]) -> None:
    """Property 31: For any valid SAPS CSV file, the parser SHALL produce
    records where ``quarterly_count`` is an int and string fields are str.

    # Feature: crimecast-za, Property 31: CSV parse type correctness
    Validates: Requirements 14.1
    """
    filepath = _write_valid_csv(records)
    try:
        parsed = parse_saps_csv(filepath)
        assert len(parsed) == len(records), (
            "Parsed record count must equal input record count"
        )
        for rec in parsed:
            assert isinstance(rec["police_station_name"], str), (
                "police_station_name must be str"
            )
            assert isinstance(rec["province"], str), (
                "province must be str"
            )
            assert isinstance(rec["crime_category"], str), (
                "crime_category must be str"
            )
            assert isinstance(rec["quarterly_count"], int), (
                "quarterly_count must be int"
            )
    finally:
        os.unlink(filepath)


# ---------------------------------------------------------------------------
# Property 32: CSV parse error identifies row and field
# ---------------------------------------------------------------------------

@given(
    good_records=st.lists(_valid_record, min_size=0, max_size=10),
    bad_field=st.sampled_from(REQUIRED_COLUMNS),
    extra_good=st.lists(_valid_record, min_size=0, max_size=5),
)
@settings(max_examples=100)
def test_parse_error_identifies_row_and_field_missing(
    good_records: list[dict],
    bad_field: str,
    extra_good: list[dict],
) -> None:
    """Property 32 (missing field variant): For any malformed SAPS CSV file
    with a missing required field, the parser SHALL raise ParseError that
    identifies the row number and field name.

    # Feature: crimecast-za, Property 32: CSV parse error identification
    Validates: Requirements 14.2
    """
    # Build a bad row by omitting the chosen field
    bad_row = {
        "police_station_name": "Test Station",
        "province": "Gauteng",
        "crime_category": "Assault GBH",
        "quarterly_count": 10,
    }
    del bad_row[bad_field]

    # Write: good rows, then the bad row, then more good rows
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    ) as fh:
        # Write header with all columns present so the header check passes
        writer = csv.DictWriter(
            fh,
            fieldnames=REQUIRED_COLUMNS,
            extrasaction="ignore",
        )
        writer.writeheader()
        for rec in good_records:
            writer.writerow(rec)
        # Write the bad row — the missing field will appear as empty string
        # We need to write it manually to truly omit the column value
        # csv.DictWriter with restval='' will write empty for missing keys,
        # which the parser treats as an empty string (not None).
        # To test a genuine missing-field scenario we write a row with fewer
        # columns by using a plain csv.writer.
        fh.flush()

    # Re-open and append the bad row with a raw writer that omits the field
    with open(fh.name, "a", newline="", encoding="utf-8") as raw_fh:
        raw_writer = csv.writer(raw_fh)
        # Write only the values for the columns that are NOT the bad field
        remaining_cols = [c for c in REQUIRED_COLUMNS if c != bad_field]
        row_values = []
        for col in remaining_cols:
            if col == "quarterly_count":
                row_values.append("5")
            else:
                row_values.append("SomeValue")
        raw_writer.writerow(row_values)
        for rec in extra_good:
            raw_writer.writerow([
                rec["police_station_name"],
                rec["province"],
                rec["crime_category"],
                str(rec["quarterly_count"]),
            ])

    filepath = fh.name
    try:
        with pytest.raises(ParseError) as exc_info:
            parse_saps_csv(filepath)
        err = exc_info.value
        # The error must carry a row_number and field_name
        assert isinstance(err.row_number, int), "row_number must be int"
        assert isinstance(err.field_name, str), "field_name must be str"
        assert err.field_name != "", "field_name must not be empty"
        assert err.row_number >= 0, "row_number must be non-negative"
    finally:
        os.unlink(filepath)


@given(
    good_records=st.lists(_valid_record, min_size=0, max_size=10),
    bad_value=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
        min_size=1,
        max_size=10,
    ),
)
@settings(max_examples=100)
def test_parse_error_identifies_row_and_field_type_mismatch(
    good_records: list[dict],
    bad_value: str,
) -> None:
    """Property 32 (type mismatch variant): For any malformed SAPS CSV file
    where ``quarterly_count`` is not an integer, the parser SHALL raise
    ParseError that identifies the row number and field name.

    # Feature: crimecast-za, Property 32: CSV parse error identification
    Validates: Requirements 14.2
    """
    # The bad_value strategy produces alphabetic strings — never valid ints
    bad_row = {
        "police_station_name": "Test Station",
        "province": "Gauteng",
        "crime_category": "Assault GBH",
        "quarterly_count": bad_value,  # not an int
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for rec in good_records:
            writer.writerow(rec)
        writer.writerow(bad_row)
        filepath = fh.name

    try:
        with pytest.raises(ParseError) as exc_info:
            parse_saps_csv(filepath)
        err = exc_info.value
        assert isinstance(err.row_number, int), "row_number must be int"
        assert err.row_number == len(good_records) + 1, (
            f"Expected row_number={len(good_records) + 1}, got {err.row_number}"
        )
        assert err.field_name == "quarterly_count", (
            f"Expected field_name='quarterly_count', got {err.field_name!r}"
        )
    finally:
        os.unlink(filepath)


# ---------------------------------------------------------------------------
# Property 33: CSV serialisation column order
# ---------------------------------------------------------------------------

@given(records=_valid_records)
@settings(max_examples=100)
def test_serialise_column_order(records: list[dict]) -> None:
    """Property 33: For any list of records, ``serialise_to_csv`` SHALL
    produce a CSV with columns in order: police_station_name, province,
    crime_category, quarterly_count.

    # Feature: crimecast-za, Property 33: CSV serialisation column order
    Validates: Requirements 14.3
    """
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, encoding="utf-8", mode="w"
    ) as fh:
        filepath = fh.name

    try:
        serialise_to_csv(records, filepath)

        with open(filepath, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader)

        assert header == REQUIRED_COLUMNS, (
            f"Expected column order {REQUIRED_COLUMNS}, got {header}"
        )
    finally:
        os.unlink(filepath)


# ---------------------------------------------------------------------------
# Property 34: CSV round-trip fidelity
# ---------------------------------------------------------------------------

@given(records=_valid_records)
@settings(max_examples=100)
def test_round_trip_fidelity(records: list[dict]) -> None:
    """Property 34: For any valid list of records,
    parse(serialise(records)) SHALL produce records with identical field
    values.

    # Feature: crimecast-za, Property 34: CSV round-trip fidelity
    Validates: Requirements 14.4
    """
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, encoding="utf-8", mode="w"
    ) as fh:
        filepath = fh.name

    try:
        serialise_to_csv(records, filepath)
        parsed = parse_saps_csv(filepath)

        assert len(parsed) == len(records), (
            "Round-trip must preserve record count"
        )
        for i, (original, recovered) in enumerate(zip(records, parsed)):
            assert recovered["police_station_name"] == str(original["police_station_name"]), (
                f"Row {i + 1}: police_station_name mismatch"
            )
            assert recovered["province"] == str(original["province"]), (
                f"Row {i + 1}: province mismatch"
            )
            assert recovered["crime_category"] == str(original["crime_category"]), (
                f"Row {i + 1}: crime_category mismatch"
            )
            assert recovered["quarterly_count"] == int(original["quarterly_count"]), (
                f"Row {i + 1}: quarterly_count mismatch"
            )
    finally:
        os.unlink(filepath)
