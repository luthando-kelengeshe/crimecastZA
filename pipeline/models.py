"""CrimecastZA pipeline data models."""

from dataclasses import dataclass, field


@dataclass
class CleanedRecord:
    original_name: str
    canonical_name: str
    province: str
    category: str
    year: int
    month: int
    monthly_count: int


@dataclass
class FeatureVector:
    station_id: int
    category_id: int
    year: int
    month: int
    lags: list[int]          # 12 elements
    unemployment_rate: float
    mean_temp_c: float
    total_precip_mm: float
    public_holiday_count: int
    payday_count: int
    month_of_year: int


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
