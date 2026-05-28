"""CrimecastZA pipeline data cleaner.

Handles name standardisation (trim, title-case, canonical matching)
and quarterly-to-monthly count conversion.
"""

import math

from pipeline.models import CleanedRecord


def monthly_count(quarterly_count: int) -> int:
    """Return the estimated monthly crime count from a quarterly count.

    Args:
        quarterly_count: Non-negative integer quarterly crime count.

    Returns:
        floor(quarterly_count / 3)
    """
    return math.floor(quarterly_count / 3)


def clean_record(raw: dict, reference_stations: list[str]) -> CleanedRecord:
    """Clean a raw SAPS CSV record into a CleanedRecord.

    Trims whitespace from the station name, applies title-case to produce
    the canonical name, and stores the original (pre-trim) name separately.
    The ``reference_stations`` parameter is reserved for future fuzzy
    canonical matching; currently the title-cased name is used directly.

    Args:
        raw: Dict with keys ``police_station_name``, ``province``,
             ``crime_category``, ``year``, ``month``, ``quarterly_count``.
        reference_stations: List of known canonical station names (unused
                            in this implementation — reserved for future
                            canonical matching).

    Returns:
        A :class:`~pipeline.models.CleanedRecord` with ``original_name``
        set to the raw station name (unmodified), ``canonical_name`` set
        to the trimmed, title-cased station name, and ``monthly_count``
        derived from the quarterly count.
    """
    raw_name: str = raw["police_station_name"]
    original_name: str = raw_name
    canonical_name: str = raw_name.strip().title()

    return CleanedRecord(
        original_name=original_name,
        canonical_name=canonical_name,
        province=raw["province"],
        category=raw["crime_category"],
        year=int(raw["year"]),
        month=int(raw["month"]),
        monthly_count=monthly_count(int(raw["quarterly_count"])),
    )
