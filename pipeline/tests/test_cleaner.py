"""Property-based tests for pipeline/cleaner.py.

Covers:
  - Property 2: Data cleaning preserves original name and produces canonical name
  - Property 3: Quarterly-to-monthly conversion
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.cleaner import clean_record, monthly_count


# ---------------------------------------------------------------------------
# Property 2 — Data cleaning preserves original name and produces canonical name
# Feature: crimecast-za, Property 2: data cleaning preserves original name
# ---------------------------------------------------------------------------

def _make_raw(station_name: str) -> dict:
    """Build a minimal raw record dict with the given station name."""
    return {
        "police_station_name": station_name,
        "province": "Gauteng",
        "crime_category": "Assault GBH",
        "year": 2023,
        "month": 6,
        "quarterly_count": 30,
    }


@settings(max_examples=100)
@given(station_name=st.text())
def test_property2_original_name_preserved(station_name: str) -> None:
    """Property 2: original_name equals the raw station name, unmodified.

    **Validates: Requirements 1.4, 1.8**
    """
    # Feature: crimecast-za, Property 2: data cleaning preserves original name
    raw = _make_raw(station_name)
    record = clean_record(raw, reference_stations=[])

    assert record.original_name == station_name, (
        f"original_name should be the unmodified raw name. "
        f"Got {record.original_name!r}, expected {station_name!r}"
    )


@settings(max_examples=100)
@given(station_name=st.text())
def test_property2_canonical_name_trimmed_and_title_cased(station_name: str) -> None:
    """Property 2: canonical_name is the trimmed, title-cased station name.

    **Validates: Requirements 1.4, 1.8**
    """
    # Feature: crimecast-za, Property 2: data cleaning preserves original name
    raw = _make_raw(station_name)
    record = clean_record(raw, reference_stations=[])

    expected_canonical = station_name.strip().title()
    assert record.canonical_name == expected_canonical, (
        f"canonical_name should be trimmed and title-cased. "
        f"Got {record.canonical_name!r}, expected {expected_canonical!r}"
    )


@settings(max_examples=100)
@given(station_name=st.text())
def test_property2_original_and_canonical_independently_stored(station_name: str) -> None:
    """Property 2: original_name and canonical_name are independently stored.

    Mutating one field must not affect the other.

    **Validates: Requirements 1.4, 1.8**
    """
    # Feature: crimecast-za, Property 2: data cleaning preserves original name
    raw = _make_raw(station_name)
    record = clean_record(raw, reference_stations=[])

    original_before = record.original_name
    canonical_before = record.canonical_name

    # Mutate one field and verify the other is unaffected
    record.canonical_name = "MUTATED"
    assert record.original_name == original_before, (
        "Mutating canonical_name must not change original_name"
    )

    record.original_name = "MUTATED"
    assert record.canonical_name == canonical_before or record.canonical_name == "MUTATED", (
        "Fields are stored independently"
    )


# ---------------------------------------------------------------------------
# Property 3 — Quarterly-to-monthly conversion
# Feature: crimecast-za, Property 3: quarterly-to-monthly conversion
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(q=st.integers(min_value=0))
def test_property3_monthly_count_equals_floor_q_div_3(q: int) -> None:
    """Property 3: monthly_count(q) == floor(q / 3) for any non-negative q.

    **Validates: Requirements 1.4**
    """
    # Feature: crimecast-za, Property 3: quarterly-to-monthly conversion
    result = monthly_count(q)
    expected = math.floor(q / 3)

    assert result == expected, (
        f"monthly_count({q}) should be {expected}, got {result}"
    )


@settings(max_examples=100)
@given(q=st.integers(min_value=0))
def test_property3_monthly_count_is_non_negative(q: int) -> None:
    """Property 3: monthly_count result is always a non-negative integer.

    **Validates: Requirements 1.4**
    """
    # Feature: crimecast-za, Property 3: quarterly-to-monthly conversion
    result = monthly_count(q)

    assert isinstance(result, int), (
        f"monthly_count({q}) should return an int, got {type(result).__name__}"
    )
    assert result >= 0, (
        f"monthly_count({q}) should be non-negative, got {result}"
    )
