"""Tests for pipeline.downloader — unit tests and Property 4 PBT.

# Feature: crimecast-za, Property 4: Open-Meteo retry with exponential backoff
"""

import io
import os
import tempfile
from unittest.mock import MagicMock, call, patch

import pytest
import requests
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.downloader import DownloadError, download_saps_file, fetch_weather

# ---------------------------------------------------------------------------
# Unit tests — download_saps_file
# ---------------------------------------------------------------------------


class TestDownloadSapsFile:
    """Unit tests for download_saps_file."""

    def test_successful_download_writes_file(self, tmp_path):
        """A 200 response should write the response body to dest_path."""
        dest = str(tmp_path / "output.csv")
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.content = b"col1,col2\n1,2\n"

        with patch("pipeline.downloader.requests.get", return_value=mock_response):
            download_saps_file("https://example.com/data.csv", dest)

        with open(dest, "rb") as fh:
            assert fh.read() == b"col1,col2\n1,2\n"

    def test_http_error_raises_download_error(self):
        """A non-2xx response should raise DownloadError with the status code."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 404

        with patch("pipeline.downloader.requests.get", return_value=mock_response):
            with pytest.raises(DownloadError) as exc_info:
                download_saps_file("https://example.com/missing.csv", "/tmp/out.csv")

        assert exc_info.value.url == "https://example.com/missing.csv"
        assert exc_info.value.status_code == 404

    def test_connection_error_raises_download_error(self):
        """A requests.RequestException should be wrapped in DownloadError."""
        with patch(
            "pipeline.downloader.requests.get",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            with pytest.raises(DownloadError) as exc_info:
                download_saps_file("https://example.com/data.csv", "/tmp/out.csv")

        assert exc_info.value.url == "https://example.com/data.csv"
        assert isinstance(exc_info.value.status_code, str)

    def test_download_error_attributes(self):
        """DownloadError should expose url and status_code attributes."""
        err = DownloadError("https://x.com", 503)
        assert err.url == "https://x.com"
        assert err.status_code == 503


# ---------------------------------------------------------------------------
# Unit tests — fetch_weather (deterministic)
# ---------------------------------------------------------------------------


def _make_ok_response(times, temps, precips):
    """Build a mock requests.Response for a successful Open-Meteo call."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "monthly": {
            "time": times,
            "temperature_2m_mean": temps,
            "precipitation_sum": precips,
        }
    }
    return mock_resp


class TestFetchWeather:
    """Unit tests for fetch_weather."""

    def test_successful_call_returns_records(self):
        """A successful API call should return parsed monthly records."""
        times = ["2020-01", "2020-02"]
        temps = [15.3, 16.1]
        precips = [30.0, 25.5]

        with patch(
            "pipeline.downloader.requests.get",
            return_value=_make_ok_response(times, temps, precips),
        ), patch("pipeline.downloader.time.sleep"):
            result = fetch_weather(-26.0, 28.0, 2020, 2020)

        assert len(result) == 2
        assert result[0] == {
            "year": 2020,
            "month": 1,
            "mean_temp_c": 15.3,
            "total_precip_mm": 30.0,
        }
        assert result[1] == {
            "year": 2020,
            "month": 2,
            "mean_temp_c": 16.1,
            "total_precip_mm": 25.5,
        }

    def test_all_retries_exhausted_returns_empty_list(self):
        """After 3 consecutive failures fetch_weather should return []."""
        with patch(
            "pipeline.downloader.requests.get",
            side_effect=requests.exceptions.ConnectionError("down"),
        ), patch("pipeline.downloader.time.sleep"):
            result = fetch_weather(-26.0, 28.0, 2020, 2020)

        assert result == []

    def test_all_retries_exhausted_does_not_raise(self):
        """fetch_weather must never propagate exceptions to the caller."""
        with patch(
            "pipeline.downloader.requests.get",
            side_effect=Exception("unexpected"),
        ), patch("pipeline.downloader.time.sleep"):
            # Should not raise
            result = fetch_weather(-26.0, 28.0, 2020, 2020)

        assert result == []

    def test_success_on_second_attempt_returns_records(self):
        """If the first call fails but the second succeeds, records are returned."""
        ok_resp = _make_ok_response(["2021-06"], [20.0], [10.0])
        side_effects = [
            requests.exceptions.ConnectionError("first fail"),
            ok_resp,
        ]

        with patch(
            "pipeline.downloader.requests.get", side_effect=side_effects
        ), patch("pipeline.downloader.time.sleep") as mock_sleep:
            result = fetch_weather(-26.0, 28.0, 2021, 2021)

        assert len(result) == 1
        assert result[0]["year"] == 2021
        # One sleep call for the first failure (delay=1s)
        mock_sleep.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# Property 4 — Open-Meteo retry with exponential backoff (Hypothesis PBT)
# ---------------------------------------------------------------------------
# **Validates: Requirements 4**
#
# Property: For any N failures (1 ≤ N ≤ 3) followed by either success or
# continued failure, the pipeline:
#   1. Sleeps with delays [1, 2, 4] seconds in order for each retry.
#   2. Returns [] after all 3 retries fail — without raising.
#   3. Returns data records when a retry eventually succeeds.


@settings(max_examples=100)
@given(st.integers(min_value=1, max_value=3))
def test_property4_retry_backoff_then_failure(n_failures: int):
    """Property 4 — all N retries fail → returns [] and sleeps correctly.

    # Feature: crimecast-za, Property 4: Open-Meteo retry with exponential backoff
    """
    expected_delays = [1, 2, 4]

    # Build a side-effect list: n_failures errors (up to 3), then more errors
    # to ensure all 3 attempts are exhausted.
    side_effects = [
        requests.exceptions.ConnectionError(f"fail {i}") for i in range(3)
    ]

    with patch(
        "pipeline.downloader.requests.get", side_effect=side_effects
    ) as mock_get, patch("pipeline.downloader.time.sleep") as mock_sleep:
        result = fetch_weather(-26.0, 28.0, 2020, 2020)

    # Must return empty list — never raise
    assert result == [], (
        f"Expected [] after all retries exhausted, got {result!r}"
    )

    # Verify sleep was called with the correct backoff delays for each retry
    # that was followed by another attempt (i.e., all but the last attempt).
    actual_sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    # There should be exactly 2 sleep calls (between attempt 1→2 and 2→3)
    assert actual_sleep_calls == expected_delays[:2], (
        f"Expected sleep calls {expected_delays[:2]}, got {actual_sleep_calls}"
    )

    # All 3 attempts must have been made
    assert mock_get.call_count == 3, (
        f"Expected 3 attempts, got {mock_get.call_count}"
    )


@settings(max_examples=100)
@given(st.integers(min_value=1, max_value=2))
def test_property4_retry_backoff_then_success(n_failures: int):
    """Property 4 — N failures (1 or 2) then success → returns records and sleeps correctly.

    # Feature: crimecast-za, Property 4: Open-Meteo retry with exponential backoff
    """
    expected_delays = [1, 2, 4]
    ok_resp = _make_ok_response(["2020-03"], [18.5], [12.0])

    side_effects = [
        requests.exceptions.ConnectionError(f"fail {i}") for i in range(n_failures)
    ] + [ok_resp]

    with patch(
        "pipeline.downloader.requests.get", side_effect=side_effects
    ) as mock_get, patch("pipeline.downloader.time.sleep") as mock_sleep:
        result = fetch_weather(-26.0, 28.0, 2020, 2020)

    # Must return the parsed records
    assert len(result) == 1, (
        f"Expected 1 record after {n_failures} failure(s) then success, got {result!r}"
    )
    assert result[0]["year"] == 2020
    assert result[0]["month"] == 3

    # Sleep should have been called once per failure (with the correct delay)
    actual_sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert actual_sleep_calls == expected_delays[:n_failures], (
        f"Expected sleep calls {expected_delays[:n_failures]}, got {actual_sleep_calls}"
    )

    # Total attempts = n_failures + 1 (the successful one)
    assert mock_get.call_count == n_failures + 1, (
        f"Expected {n_failures + 1} attempts, got {mock_get.call_count}"
    )
