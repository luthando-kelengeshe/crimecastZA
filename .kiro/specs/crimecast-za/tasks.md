# Implementation Plan: CrimecastZA — Python Pipeline & ML Model

## Overview

This plan covers the Python data ingestion pipeline and XGBoost ML model service for CrimecastZA. It includes the project scaffold, database schema migrations, all pipeline modules (validator, parser, cleaner, downloader, enricher, feature builder, orchestrator), the ML training and prediction scripts, Docker configuration for Python services, and the GitHub Actions CI workflow for Python components.

## Tasks

- [x] 1. Project scaffold and Python environment setup
  - Create `pipeline/` directory with `__init__.py`
  - Create `model/` directory with `__init__.py`
  - Create `pipeline/requirements.txt` pinning: `psycopg2-binary==2.9.9`, `requests==2.31.0`, `pandas==2.2.2`, `hypothesis==6.100.1`, `pytest==8.2.0`, `python-dotenv==1.0.1`
  - Create `model/requirements.txt` pinning: `xgboost==2.0.3`, `scikit-learn==1.4.2`, `joblib==1.4.2`, `pandas==2.2.2`, `numpy==1.26.4`, `psycopg2-binary==2.9.9`, `hypothesis==6.100.1`, `pytest==8.2.0`, `python-dotenv==1.0.1`
  - Create `pipeline/config.py` that reads all required env vars (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SAPS_DATA_URL`, `QLFS_URL`, `OPEN_METEO_URL`) from environment, logs a descriptive error naming the missing variable, and calls `sys.exit(1)` for any missing variable
  - _Requirements: 1, 2, 11.5_

- [x] 2. Database schema migration scripts
  - Create `db/migrations/V1__create_schema.sql` implementing the full 3NF schema: `province`, `police_station` (with PostGIS geometry point in SRID 4326), `crime_category`, `monthly_crime_record`, `unemployment_record`, `weather_record`, `calendar_event`, `feature_vector` (with columns lag_1 through lag_12), `forecast`, `pipeline_run_log`
  - Include all foreign key constraints, CHECK constraints, and UNIQUE constraints as specified in the design
  - Include all indexes: `idx_station_province`, `idx_station_location` (GIST), `idx_crime_record_station`, `idx_crime_record_category`, `idx_crime_record_period`, `idx_forecast_station`, `idx_forecast_category`, `idx_forecast_period`
  - Create `db/migrations/V2__seed_provinces.sql` inserting all nine South African provinces using `ON CONFLICT DO NOTHING`
  - Each migration script must be idempotent (use `IF NOT EXISTS` and `ON CONFLICT DO NOTHING` throughout)
  - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.6_

- [x] 3. Python data models and structured logger
  - Create `pipeline/models.py` with `@dataclass` definitions for `CleanedRecord`, `FeatureVector`, and `ValidationResult` exactly as specified in the design document
  - Create `pipeline/logger.py` implementing `PipelineLogger` class that emits structured JSON log entries to stdout with fields: `timestamp`, `level`, `step`, `recordsProcessed`, `recordsSkipped`, `elapsedMs`, `message`; accepts an optional `step` name and tracks elapsed time from construction
  - Create `pipeline/tests/__init__.py` and `pipeline/tests/test_logger.py` with Hypothesis property tests for Property 37: for any pipeline step name and record counts, the emitted log entry contains non-null `step`, `recordsProcessed`, `recordsSkipped`, and `elapsedMs` fields
  - _Requirements: 1.6, 15.4_

- [-] 4. SAPS CSV validator
  - Create `pipeline/validator.py` with `validate_saps_file(filepath: str, required_columns: list[str]) -> ValidationResult` that reads only the CSV header row, checks for presence of all required columns (`police_station_name`, `province`, `crime_category`, `quarterly_count`), and returns `ValidationResult(ok=True)` if all present or `ValidationResult(ok=False, errors=[...])` listing missing columns
  - Write `pipeline/tests/test_validator.py` with Hypothesis property tests for Property 1: for any CSV file, the validator accepts if and only if all four required columns are present; for any file missing one or more columns, it returns a failed result identifying the missing columns
  - _Requirements: 1.2, 1.3_

- [-] 5. SAPS CSV parser
  - Create `pipeline/parser.py` with `parse_saps_csv(filepath: str) -> list[dict]` that reads all rows and returns a list of dicts with keys `police_station_name` (str), `province` (str), `crime_category` (str), `quarterly_count` (int); raises `ParseError` with row number and field name on type mismatch or missing field
  - Add `serialise_to_csv(records: list[dict], filepath: str) -> None` that writes records back to CSV with identical column order as source
  - Write `pipeline/tests/test_parser.py` with Hypothesis property tests for Properties 31–34: type correctness, error identification with row/field, column order preservation, and round-trip fidelity (parse → serialise → parse produces identical objects)
  - _Requirements: 1.2, 14.1, 14.2, 14.3, 14.4_

- [-] 6. Data cleaner
  - Create `pipeline/cleaner.py` with `monthly_count(quarterly_count: int) -> int` returning `floor(quarterly_count / 3)`, and `clean_record(raw: dict, reference_stations: list[str]) -> CleanedRecord` that trims whitespace, applies title-case to station name, stores original in `original_name`, stores canonical in `canonical_name`, and computes `monthly_count`
  - Write `pipeline/tests/test_cleaner.py` with Hypothesis property tests for Properties 2 and 3: name cleaning always preserves original and produces trimmed title-cased canonical; quarterly-to-monthly conversion always equals `floor(q/3)` and is always non-negative
  - _Requirements: 1.4, 1.8_

- [-] 7. HTTP downloader with retry logic
  - Create `pipeline/downloader.py` with `download_saps_file(url: str, dest_path: str) -> None` that downloads a CSV to disk and raises `DownloadError(url, status_code)` on HTTP error or connection failure
  - Add `fetch_weather(lat: float, lon: float, start_year: int, end_year: int) -> list[dict]` that calls the Open-Meteo API, retries up to 3 times with exponential backoff (1s, 2s, 4s) on error, logs a warning and returns an empty list after all retries exhausted, and returns a list of `{year, month, mean_temp_c, total_precip_mm}` dicts on success
  - Write `pipeline/tests/test_downloader.py` with Hypothesis property tests for Property 4: for any sequence of N failures (N ≤ 3), retry wait intervals are exactly 1s/2s/4s; after 3 consecutive failures the function returns without raising and without halting the pipeline
  - _Requirements: 1.1, 1.9, 2.3, 2.4_

- [ ] 8. Unemployment and calendar data loaders
  - Create `pipeline/enricher.py` with `fetch_unemployment(qlfs_url: str, db_conn) -> dict` that attempts to fetch QLFS data; on failure logs a warning with URL/error/timestamp and returns the most recently stored rates from the DB keyed by `(province, year, quarter)`
  - Add `load_calendar(db_conn) -> int` that inserts all South African gazetted public holidays for 2005–2027 and payday dates (last working day of each month, excluding public holidays) into `calendar_event` using `ON CONFLICT DO NOTHING`; returns count of rows inserted
  - _Requirements: 2.1, 2.2, 2.5_

- [~] 9. Feature vector builder
  - Create `pipeline/feature_builder.py` with `build_feature_vector(station_id: int, category_id: int, year: int, month: int, db_conn) -> FeatureVector | None` that joins `monthly_crime_record` (12-month lags), `unemployment_record` (by province/quarter), `weather_record`, and `calendar_event` counts into a complete `FeatureVector`; returns `None` if any required source data is missing
  - Add `persist_feature_vectors(vectors: list[FeatureVector], db_conn) -> int` that bulk-inserts into `feature_vector` table using `ON CONFLICT DO UPDATE SET` for all columns; returns count of rows upserted
  - Write `pipeline/tests/test_feature_builder.py` with Hypothesis property tests for Property 5: for any valid `(station_id, category_id, year, month)` with all source data present, the assembled `FeatureVector` has non-null values for all 12 lag fields and all other required fields
  - _Requirements: 2.6, 2.7, 4.6_

- [~] 10. Pipeline orchestrator
  - Create `pipeline/pipeline.py` as the main orchestration entry point that: reads config, opens a psycopg2 DB connection, inserts a `pipeline_run_log` row with `status='running'`, runs all ingestion steps in order (SAPS download → validate → parse → clean → DB upsert; unemployment fetch → DB upsert; weather fetch per station → DB upsert; calendar load; feature vector build → persist), updates the run log with `status='success'` and counts on completion, and on any unhandled exception updates the log with `status='failed'` and `error_message` then exits with code 1
  - Must be runnable as `python -m pipeline.pipeline`
  - _Requirements: 1.1, 1.5, 1.6, 1.7, 1.9, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [~] 11. XGBoost model training script
  - Create `model/train.py` with: `load_feature_vectors(db_conn) -> pd.DataFrame` executing a single `SELECT` joining `feature_vector` with `monthly_crime_record` target; `temporal_split(df, cutoff_months=12) -> tuple[pd.DataFrame, pd.DataFrame]` placing the last 12 months in test and all earlier records in train with no overlap; `train_model(train_df) -> xgb.XGBRegressor` training on features lag_1–lag_12, unemployment_rate, mean_temp_c, total_precip_mm, public_holiday_count, payday_count, month_of_year; `evaluate_mape(model, X_test, y_test) -> dict[str, float]` returning per-category MAPE; `main()` orchestrating load → split → train → evaluate, serialising with joblib if MAPE < 15% for ≥ 5 categories, otherwise logging warning and retaining existing artefact
  - Runnable as `python train.py`
  - Create `model/tests/__init__.py` and `model/tests/test_train.py` with Hypothesis property tests for Properties 8 and 35: temporal split places no record in both sets and respects the 12-month boundary; model serialisation round-trip produces identical predictions for a fixed reference set
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7_

- [~] 12. Risk scorer and forecast generator
  - Create `model/risk_scorer.py` with `compute_risk_score(predicted_count: float, historical_counts: list[float]) -> int` that ranks `predicted_count` against `historical_counts` using 20th-percentile boundaries (bottom 20% → 1, next 20% → 2, ..., top 20% → 5)
  - Create `model/predict.py` with `generate_forecasts(model_path: str, db_conn) -> int` that loads the joblib artefact, queries all `(station_id, category_id)` combinations, builds feature vectors for the next calendar month, generates predictions, computes risk scores, and bulk-inserts into `forecast` table; returns count of forecasts written
  - Write `model/tests/test_risk_scorer.py` with Hypothesis property tests for Property 10: for any set of predicted counts, risk scores correctly reflect 20th-percentile boundaries and always fall in [1, 5]
  - Write `model/tests/test_predict.py` with Hypothesis property tests for Properties 9 and 11: exactly one forecast per `(station_id, category_id)` combination; every forecast record has non-null values for all required fields
  - _Requirements: 5.1, 5.2, 5.3_

- [~] 13. Docker configuration for Python services
  - Create `pipeline/Dockerfile` using `python:3.12-slim` base; copies and installs only `requirements.txt` (no dev deps); sets `PYTHONUNBUFFERED=1`; entrypoint `python -m pipeline.pipeline`
  - Create `model/Dockerfile` using `python:3.12-slim` base; copies and installs only `requirements.txt`; copies `train.py`, `predict.py`, `risk_scorer.py`; default CMD `python train.py`
  - Create `docker-compose.yml` defining: `db` service using `postgis/postgis:16-3.4` with named volume `pgdata` and env vars from `.env`; `pipeline` service building from `pipeline/Dockerfile` with `depends_on: [db]`; `model` service building from `model/Dockerfile` with `depends_on: [db]` and a named volume for the model artefact
  - Create `.env.example` documenting all required variables with expected formats: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SAPS_DATA_URL`, `QLFS_URL`, `OPEN_METEO_URL`, `MODEL_PATH`
  - _Requirements: 11.1, 11.3, 11.4, 11.5, 11.6_

- [~] 14. Python CI/CD pipeline configuration
  - Create `.github/workflows/python-ci.yml` triggering on push to `main` and on pull requests targeting `main`
  - Define stages in order: install pipeline deps, install model deps, run pipeline tests (`pytest pipeline/tests/ --hypothesis-seed=0`), run model tests (`pytest model/tests/ --hypothesis-seed=0`), build pipeline Docker image, build model Docker image
  - Configure each stage to halt subsequent stages on failure and report the stage name and error output
  - _Requirements: 12.1, 12.2, 12.3, 12.5_

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": [1] },
    { "wave": 2, "tasks": [2, 3] },
    { "wave": 3, "tasks": [4, 5, 6, 7, 8] },
    { "wave": 4, "tasks": [9] },
    { "wave": 5, "tasks": [10] },
    { "wave": 6, "tasks": [11] },
    { "wave": 7, "tasks": [12] },
    { "wave": 8, "tasks": [13] },
    { "wave": 9, "tasks": [14] }
  ],
  "dependencies": {
    "2": [1],
    "3": [1],
    "4": [3],
    "5": [3],
    "6": [3],
    "7": [3],
    "8": [3],
    "9": [4, 5, 6, 7, 8],
    "10": [2, 9],
    "11": [10],
    "12": [11],
    "13": [10, 12],
    "14": [13]
  }
}
```

## Notes

- All Python tests use Hypothesis with `--hypothesis-seed=0` for reproducibility in CI.
- The `pipeline/tests/` and `model/tests/` directories each need an `__init__.py`.
- The `feature_vector` table uses individual columns `lag_1` through `lag_12` (not an array) to allow direct SQL SELECT by the training script.
- The `pipeline_run_log.mape_per_category` column is JSONB to store a dict of `{crime_category_name: mape_value}`.
- Docker Compose services for the Spring Boot API and Dashboard are intentionally excluded from this plan — they are covered in a separate tasks file.
