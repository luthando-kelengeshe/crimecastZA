"""CrimecastZA HTTP downloader with retry logic."""

import time
from typing import Any

import requests

from pipeline.logger import PipelineLogger

_logger = PipelineLogger(step="downloader")

# Open-Meteo archive API endpoint template
_OPEN_METEO_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude={lat}&longitude={lon}"
    "&start_date={start_year}-01-01&end_date={end_year}-12-31"
    "&monthly=temperature_2m_mean,precipitation_sum"
)

# Exponential backoff delays (seconds) for retries 1, 2, 3
_BACKOFF_DELAYS = [1, 2, 4]


class DownloadError(Exception):
    """Raised when an HTTP download fails.

    Attributes:
        url: The URL that was requested.
        status_code: The HTTP status code, or a string describing the error
                     (e.g. "ConnectionError") when no HTTP response was received.
    """

    def __init__(self, url: str, status_code: int | str) -> None:
        self.url = url
        self.status_code = status_code
        super().__init__(f"Download failed for {url!r}: status {status_code}")


def download_saps_file(url: str, dest_path: str) -> None:
    """Download a CSV file from *url* and write it to *dest_path*.

    Args:
        url: The remote URL to download.
        dest_path: Local filesystem path where the file will be saved.

    Raises:
        DownloadError: If the server returns a non-2xx status code or if a
                       connection-level error occurs.
    """
    try:
        response = requests.get(url, timeout=60)
    except requests.exceptions.RequestException as exc:
        raise DownloadError(url, str(exc)) from exc

    if not response.ok:
        raise DownloadError(url, response.status_code)

    with open(dest_path, "wb") as fh:
        fh.write(response.content)


def fetch_weather(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
) -> list[dict[str, Any]]:
    """Fetch monthly weather data from the Open-Meteo archive API.

    Retries up to 3 times with exponential backoff (1 s, 2 s, 4 s) on any
    error.  After all retries are exhausted a warning is logged and an empty
    list is returned so that the caller can continue processing remaining
    stations without halting.

    Args:
        lat: Station latitude.
        lon: Station longitude.
        start_year: First year of the requested date range (inclusive).
        end_year: Last year of the requested date range (inclusive).

    Returns:
        A list of dicts, each with keys:
            ``year``            – int
            ``month``           – int (1–12)
            ``mean_temp_c``     – float | None
            ``total_precip_mm`` – float | None
        Returns an empty list if all retries fail.
    """
    url = _OPEN_METEO_URL.format(
        lat=lat,
        lon=lon,
        start_year=start_year,
        end_year=end_year,
    )

    last_exc: Exception | None = None

    for attempt, delay in enumerate(_BACKOFF_DELAYS, start=1):
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            data = response.json()

            monthly = data.get("monthly", {})
            times: list[str] = monthly.get("time", [])
            temps: list[float | None] = monthly.get("temperature_2m_mean", [])
            precips: list[float | None] = monthly.get("precipitation_sum", [])

            records: list[dict[str, Any]] = []
            for i, ym in enumerate(times):
                year_str, month_str = ym.split("-")
                records.append(
                    {
                        "year": int(year_str),
                        "month": int(month_str),
                        "mean_temp_c": temps[i] if i < len(temps) else None,
                        "total_precip_mm": precips[i] if i < len(precips) else None,
                    }
                )
            return records

        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < len(_BACKOFF_DELAYS):
                # More retries remain — sleep then loop
                time.sleep(delay)
            # On the final attempt the loop ends naturally

    _logger.log(
        "WARNING",
        f"fetch_weather failed after {len(_BACKOFF_DELAYS)} retries for "
        f"lat={lat}, lon={lon}: {last_exc}",
    )
    return []
