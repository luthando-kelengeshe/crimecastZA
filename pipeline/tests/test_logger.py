"""Property-based tests for PipelineLogger.

# Feature: crimecast-za, Property 37: pipeline log completeness
"""

import json
import sys
from io import StringIO

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.logger import PipelineLogger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_log(step: str, level: str, message: str,
                 records_processed: int, records_skipped: int) -> dict:
    """Run PipelineLogger.log() and return the parsed JSON entry."""
    buf = StringIO()
    original_stdout = sys.stdout
    sys.stdout = buf
    try:
        logger = PipelineLogger(step=step)
        logger.log(
            level=level,
            message=message,
            records_processed=records_processed,
            records_skipped=records_skipped,
        )
    finally:
        sys.stdout = original_stdout
    return json.loads(buf.getvalue().strip())


# ---------------------------------------------------------------------------
# Property 37: pipeline log completeness
# ---------------------------------------------------------------------------

@given(
    step=st.text(min_size=1),
    records_processed=st.integers(min_value=0),
    records_skipped=st.integers(min_value=0),
)
@settings(max_examples=100)
def test_log_entry_contains_required_non_null_fields(
    step: str, records_processed: int, records_skipped: int
) -> None:
    """Property 37: For any pipeline step name and record counts, the emitted
    log entry SHALL contain non-null values for step, recordsProcessed,
    recordsSkipped, and elapsedMs.

    # Feature: crimecast-za, Property 37: pipeline log completeness
    Validates: Requirements 1.6, 15.4
    """
    entry = _capture_log(
        step=step,
        level="INFO",
        message="test",
        records_processed=records_processed,
        records_skipped=records_skipped,
    )

    # All four required fields must be present and non-null
    assert entry.get("step") is not None, "step must be non-null"
    assert entry.get("recordsProcessed") is not None, "recordsProcessed must be non-null"
    assert entry.get("recordsSkipped") is not None, "recordsSkipped must be non-null"
    assert entry.get("elapsedMs") is not None, "elapsedMs must be non-null"

    # Values must match what was passed in
    assert entry["step"] == step
    assert entry["recordsProcessed"] == records_processed
    assert entry["recordsSkipped"] == records_skipped
    assert isinstance(entry["elapsedMs"], float)
    assert entry["elapsedMs"] >= 0.0


@given(
    step=st.text(min_size=1),
    records_processed=st.integers(min_value=0),
    records_skipped=st.integers(min_value=0),
)
@settings(max_examples=50)
def test_log_entry_is_valid_json(
    step: str, records_processed: int, records_skipped: int
) -> None:
    """For any inputs, PipelineLogger must emit a single valid JSON object.

    # Feature: crimecast-za, Property 37: pipeline log completeness
    Validates: Requirements 1.6, 15.4
    """
    buf = StringIO()
    original_stdout = sys.stdout
    sys.stdout = buf
    try:
        logger = PipelineLogger(step=step)
        logger.log(
            level="DEBUG",
            message="json check",
            records_processed=records_processed,
            records_skipped=records_skipped,
        )
    finally:
        sys.stdout = original_stdout

    raw = buf.getvalue().strip()
    # Must be parseable as JSON
    entry = json.loads(raw)
    assert isinstance(entry, dict)
    # Must contain all seven required top-level keys
    for key in ("timestamp", "level", "step", "recordsProcessed",
                "recordsSkipped", "elapsedMs", "message"):
        assert key in entry, f"Missing key: {key}"
