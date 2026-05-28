# Requirements Document

## Introduction

CrimecastZA is a South African Crime Hotspot Forecasting System — a web-based, AI-powered predictive analytics platform that ingests historical SAPS crime statistics, socioeconomic indicators, seasonal patterns, and weather data to forecast crime hotspots across South African police regions. The system enables SAPS units, private security firms, neighbourhood watches, and citizens to make data-driven resource deployment and safety decisions.

The system is composed of five integrated components:
1. A Python data ingestion and feature engineering pipeline
2. An XGBoost machine learning forecasting model
3. A PostgreSQL/PostGIS geographic database
4. A Java Spring Boot REST API backend
5. An HTML/JavaScript web dashboard with Leaflet.js map visualisation

All components are containerised with Docker and orchestrated via Docker Compose, with a GitHub Actions CI/CD pipeline automating build, test, and deployment.

---

## Glossary

- **SAPS**: South African Police Service — the national police agency responsible for crime statistics publication.
- **Police_Station**: A SAPS policing unit identified by name, province, and geographic coordinates, used as the base unit of crime reporting.
- **Crime_Category**: A standardised SAPS crime classification (e.g., Assault GBH, Robbery with aggravating circumstances, Burglary at residential premises).
- **Forecast**: A predicted monthly crime count for a given Police_Station and Crime_Category, produced by the ML_Model.
- **Risk_Score**: A normalised integer score (1–5) derived from a Forecast, representing relative crime risk for a Police_Station in a given period.
- **Hotspot**: A Police_Station whose Risk_Score meets or exceeds a configurable threshold for a given Crime_Category and time period.
- **ML_Model**: The trained XGBoost regression model that produces Forecasts from feature vectors.
- **Data_Pipeline**: The Python-based ETL process that downloads, cleans, enriches, and loads source data into the Database.
- **API**: The Spring Boot REST API that exposes Forecast, trend, and Hotspot data to the Dashboard and external consumers.
- **Dashboard**: The HTML/JavaScript single-page web application that visualises Forecasts and Hotspots on an interactive South Africa map.
- **Database**: The PostgreSQL instance with PostGIS extension that stores all ingested, enriched, and forecast data.
- **MAE**: Mean Absolute Error — the average absolute difference between predicted and actual crime counts, expressed as a percentage of the actual value.
- **QLFS**: Stats SA Quarterly Labour Force Survey — the source of provincial unemployment rate data.
- **Open_Meteo**: The free weather API used to retrieve historical and current weather data by geographic coordinates.
- **Province**: One of South Africa's nine administrative provinces (Western Cape, Eastern Cape, Northern Cape, Free State, KwaZulu-Natal, North West, Gauteng, Mpumalanga, Limpopo).
- **Retraining_Job**: A scheduled Spring Boot task that triggers the ML_Model to retrain on the latest available data.
- **Feature_Vector**: The set of input variables (crime history, weather, unemployment, payday flags, seasonal indicators) used by the ML_Model to produce a Forecast.
- **CI/CD_Pipeline**: The GitHub Actions workflow that automates building, testing, and packaging all system components.
- **Docker_Compose**: The container orchestration configuration that starts all system services with a single command.

---

## Requirements

### Requirement 1: SAPS Crime Data Ingestion

**User Story:** As a system administrator, I want the Data_Pipeline to automatically download and store SAPS quarterly crime statistics, so that the Database always contains up-to-date historical crime data without manual intervention.

#### Acceptance Criteria

1. WHEN the Retraining_Job triggers a data refresh, THE Data_Pipeline SHALL download SAPS quarterly crime statistics CSV files from the configured SAPS data portal URL for all nine Provinces.
2. WHEN a SAPS data file is downloaded, THE Data_Pipeline SHALL validate that the file contains the expected columns (police station name, province, crime category, quarterly count) before processing.
3. IF a downloaded SAPS data file fails validation, THEN THE Data_Pipeline SHALL log a descriptive error message including the filename, the missing or malformed columns, and the timestamp, and SHALL skip that file without halting the pipeline.
4. THE Data_Pipeline SHALL clean ingested records by standardising Police_Station names by trimming whitespace, applying title-case, and matching against the SAPS reference station list; removing duplicate rows; and converting quarterly counts to monthly estimates using the formula: monthly_count = floor(quarterly_count / 3).
5. THE Data_Pipeline SHALL load cleaned records for at least 30 Police_Stations across all nine Provinces into the Database.
6. WHEN the Data_Pipeline completes a full ingestion run, THE Data_Pipeline SHALL record a run log entry in the Database containing the run timestamp, number of records processed, number of records skipped, and completion status.
7. WHEN the Retraining_Job triggers a data refresh, THE Data_Pipeline SHALL complete a full ingestion run without requiring human interaction.
8. FOR ALL ingested Police_Station records, THE Data_Pipeline SHALL preserve the original SAPS station name alongside the canonical name to support audit traceability.
9. IF the SAPS data portal is unreachable or returns an HTTP error status during a download attempt, THEN THE Data_Pipeline SHALL log an error message containing the URL, HTTP status code (or connection error description), and timestamp, and SHALL abort the ingestion run without modifying any existing Database records.

---

### Requirement 2: Socioeconomic and Environmental Data Ingestion

**User Story:** As a data scientist, I want the Data_Pipeline to enrich crime records with unemployment, weather, and calendar data, so that the ML_Model has the full Feature_Vector needed to produce accurate Forecasts.

#### Acceptance Criteria

1. WHEN the Retraining_Job triggers a data refresh, THE Data_Pipeline SHALL retrieve provincial unemployment rates from the Stats SA QLFS dataset and store them in the Database, keyed by Province and quarter.
2. IF the Stats SA QLFS source is unreachable or returns an error, THEN THE Data_Pipeline SHALL log a warning containing the URL, error description, and timestamp, and SHALL continue the ingestion run using the most recently stored unemployment rates for the affected Provinces.
3. WHEN the Retraining_Job triggers a data refresh, THE Data_Pipeline SHALL retrieve historical monthly weather data (mean temperature in °C and total precipitation in mm) from the Open_Meteo API for the geographic coordinates of each Police_Station, covering the period from January 2005 to the current month, and store the results in the Database.
4. IF the Open_Meteo API returns an error response for a given Police_Station, THEN THE Data_Pipeline SHALL retry the request up to three times with exponential backoff (waiting 1 second, then 2 seconds, then 4 seconds between attempts) before logging a warning and continuing with the remaining stations.
5. THE Data_Pipeline SHALL load a public holiday and payday calendar for South Africa into the Database, covering at least the years 2005 through 2027, with each entry containing the date, event type (public holiday or payday), and a boolean flag where true indicates the date is a public holiday or payday.
6. WHEN building a Feature_Vector for a given Police_Station, Crime_Category, and month, THE Data_Pipeline SHALL join crime history, provincial unemployment rate, monthly weather averages (mean temperature and total precipitation), and payday/holiday flags into a single enriched record.
7. THE Data_Pipeline SHALL store all enriched Feature_Vectors in the Database as rows in the Feature_Vector table, with each column corresponding to a named feature field, in a format directly loadable by the ML_Model training script using a single SQL SELECT query.

---

### Requirement 3: PostgreSQL Database Schema

**User Story:** As a developer, I want a fully normalised PostgreSQL database with PostGIS support, so that all system components can store and query crime data, forecasts, and geographic information efficiently.

#### Acceptance Criteria

1. THE Database SHALL implement a schema in Third Normal Form (3NF) containing at minimum the following entities: Police_Station, Province, Crime_Category, Monthly_Crime_Record, Weather_Record, Unemployment_Record, Calendar_Event, Feature_Vector, Forecast, and Pipeline_Run_Log.
2. THE Database SHALL store the geographic coordinates (latitude, longitude) of each Police_Station as a PostGIS geometry point to support geospatial queries.
3. WHEN a geospatial query is executed to retrieve all Police_Stations within a given Province boundary, THE Database SHALL return results within 500 milliseconds for a dataset containing at least 1,000 Police_Station records distributed across all nine Provinces.
4. THE Database SHALL enforce referential integrity between all related entities using foreign key constraints, such that any insert or update operation that violates a foreign key constraint is rejected and an error indicating the constraint violation is returned to the caller without modifying any data.
5. THE Database SHALL include indexes on Police_Station identifier, Province identifier, Crime_Category identifier, and forecast period (year, month) to support efficient API query patterns.
6. THE Database schema SHALL be version-controlled and applied via migration scripts that can be executed in sequence to reproduce the full schema from an empty database, where each migration script is idempotent and produces no error when applied to a database that already contains the target schema state.
7. WHEN the Docker_Compose stack is started and no prior migrations have been applied to the database, THE Database SHALL be initialised and all migration scripts SHALL be applied in sequence before any other service accepts connections.
8. IF a migration script fails during Docker_Compose startup, THEN THE Database service SHALL halt, log an error message indicating which migration script failed and the reason for failure, and prevent dependent services from starting.

---

### Requirement 4: Machine Learning Model Training

**User Story:** As a data scientist, I want an XGBoost model trained on enriched historical SAPS data, so that the system can produce monthly crime count Forecasts with a MAPE below 15% on unseen data.

#### Acceptance Criteria

1. THE ML_Model SHALL be trained using XGBoost regression on Feature_Vectors stored in the Database, with Crime_Category monthly count as the target variable.
2. WHEN training is initiated, THE ML_Model SHALL perform a temporal train/test split, using data up to 12 months before the most recent available quarter as training data and the remaining 12 months as holdout test data.
3. WHEN training completes, IF the trained ML_Model achieves a Mean Absolute Percentage Error (MAPE = mean(|actual - predicted| / actual) × 100) below 15% on holdout test data for at least five distinct Crime_Categories, THEN THE ML_Model training script SHALL serialise the trained model artefact to disk using joblib and record the training timestamp, MAPE per Crime_Category, and model file path in the Database.
4. IF the trained ML_Model does not achieve MAPE below 15% for at least five Crime_Categories, THEN THE ML_Model training script SHALL log a warning containing the per-category MAPE values and SHALL NOT replace the previously deployed model artefact; if no prior model artefact exists, THE training script SHALL record a failed-training status in the Database and exit without persisting any model file.
5. THE ML_Model training script SHALL be executable as a standalone Python command (`python train.py`) and SHALL also be triggerable by the Retraining_Job on a quarterly schedule (first day of January, April, July, and October).
6. THE ML_Model SHALL include at minimum the following features in each Feature_Vector: 12-month lagged crime counts for the same Crime_Category and Police_Station, provincial unemployment rate, monthly average temperature, monthly total precipitation, public holiday count in the month, payday count in the month, and month-of-year indicator.
7. WHEN the Retraining_Job completes a successful training run, THE ML_Model SHALL produce a Forecast for every Police_Station in the Database for all trained Crime_Categories for the forthcoming calendar month.

---

### Requirement 5: Crime Forecast Generation

**User Story:** As a system operator, I want the system to generate and store monthly Forecasts for all Police_Stations and Crime_Categories, so that the API and Dashboard always have current predictions available.

#### Acceptance Criteria

1. WHEN the Retraining_Job completes successfully, THE ML_Model SHALL generate Forecasts for all Police_Stations and all trained Crime_Categories for the next calendar month and store them in the Database.
2. THE ML_Model SHALL derive a Risk_Score (integer 1–5) for each Forecast by ranking the predicted crime count against the historical distribution for the same Crime_Category and Province, where 1 represents the lowest 20th percentile and 5 represents the highest 20th percentile.
3. WHEN a Forecast is stored, THE Database SHALL record the Police_Station identifier, Crime_Category identifier, forecast year, forecast month, predicted crime count, Risk_Score, and the model version that produced the Forecast.
4. THE API SHALL serve the most recently generated Forecast for any given Police_Station and Crime_Category combination.
5. WHILE a Retraining_Job is in progress, THE API SHALL continue serving the previously generated Forecasts without interruption.
6. IF no Forecast exists for a requested Police_Station and Crime_Category combination, THE API SHALL return HTTP 404 with a JSON error body indicating that no forecast is available for the specified combination.

---

### Requirement 6: Spring Boot REST API — Forecast Endpoints

**User Story:** As a developer or external consumer, I want documented REST API endpoints for crime forecasts, so that I can retrieve predictions programmatically for any Police_Station, Province, or Crime_Category.

#### Acceptance Criteria

1. THE API SHALL expose a `GET /api/v1/forecasts` endpoint that accepts optional query parameters for `province`, `crimeCategory`, `year`, and `month`, and returns a paginated list of Forecast objects with a default page size of 20 and a maximum page size of 100.
2. THE API SHALL expose a `GET /api/v1/forecasts/{stationId}` endpoint that returns all Forecasts for a specified Police_Station for the current and next calendar month; if a valid `stationId` exists but no forecasts are available, THE API SHALL return HTTP 200 with an empty array.
3. WHEN a request is made to a forecast endpoint with an invalid `stationId`, THE API SHALL return an HTTP 404 response with a JSON error body containing a descriptive message and the invalid identifier.
4. WHEN a request is made to a forecast endpoint with an invalid query parameter value, THE API SHALL return an HTTP 400 response with a JSON error body listing the invalid parameters and their expected formats.
5. THE API SHALL expose a `GET /api/v1/hotspots` endpoint that accepts `province`, `crimeCategory`, and `riskThreshold` (a decimal value in the range [0.0, 1.0] inclusive) parameters and returns all Police_Stations whose current Risk_Score meets or exceeds the threshold.
6. THE API SHALL respond to all forecast and hotspot endpoint requests within 2,000 milliseconds under a load of up to 100 concurrent requests.
7. THE API SHALL document all endpoints using OpenAPI 3.0 annotations, and the Swagger UI SHALL be accessible at `/swagger-ui.html`.
8. THE API SHALL support Cross-Origin Resource Sharing (CORS) for origins specified in the application's CORS configuration property.
9. IF the `riskThreshold` parameter is absent or outside the range [0.0, 1.0], THE API SHALL return HTTP 400 with a JSON error body identifying the parameter and its valid range.

---

### Requirement 7: Spring Boot REST API — Historical Trend Endpoints

**User Story:** As a dashboard user, I want to retrieve historical crime trend data through the API, so that I can compare forecasts against past patterns and understand long-term crime trajectories.

#### Acceptance Criteria

1. THE API SHALL expose a `GET /api/v1/trends/{stationId}` endpoint that accepts required query parameters `crimeCategory` (string), `startMonth` (format `YYYY-MM`), and `endMonth` (format `YYYY-MM`), and returns monthly crime counts for the specified Police_Station and Crime_Category over the requested date range.
2. WHEN a trend request specifies a date range that partially overlaps the available historical data, THE API SHALL return all available records within the overlapping portion and include a `dataRangeNote` field in the response indicating the actual start and end months covered.
3. THE API SHALL expose a `GET /api/v1/trends/province/{provinceId}` endpoint that accepts required query parameters `crimeCategory`, `startMonth`, and `endMonth`, and returns aggregated monthly crime counts for all Police_Stations within the specified Province for the given Crime_Category and date range.
4. WHEN a trend endpoint request is received for a date range of up to 60 months, THE API SHALL return the response within 3,000 milliseconds; for date ranges exceeding 60 months, THE API SHALL return the response within 10,000 milliseconds.
5. THE API SHALL expose a `GET /api/v1/stations` endpoint that returns a list of all Police_Stations with their name, Province, and geographic coordinates expressed as decimal-degree latitude and longitude rounded to six decimal places.
6. IF a request to a trend or stations endpoint contains an invalid `stationId`, `provinceId`, or `crimeCategory` value, THE API SHALL return HTTP 404 with a JSON error body identifying the invalid parameter and its value.
7. IF a trend request specifies a date range that falls entirely outside the available historical data, THE API SHALL return HTTP 200 with an empty records array and a `dataRangeNote` field stating that no data is available for the requested range.

---

### Requirement 8: Scheduled Retraining and Data Refresh

**User Story:** As a system operator, I want the system to automatically refresh data and retrain the model on a quarterly schedule, so that Forecasts remain accurate as new SAPS data becomes available.

#### Acceptance Criteria

1. THE Retraining_Job SHALL execute automatically on the first calendar day of each quarter (1 January, 1 April, 1 July, and 1 October) at 00:00 UTC without human intervention.
2. WHEN the Retraining_Job is triggered, THE Retraining_Job SHALL execute the Data_Pipeline ingestion steps, followed by ML_Model retraining, followed by Forecast generation, in that sequential order.
3. IF any step in the Retraining_Job sequence fails, THEN THE Retraining_Job SHALL halt subsequent steps, log the failure with a timestamp and error description, and retain the previously deployed model artefact and Forecasts; if no prior model artefact exists and the training step fails, THE Retraining_Job SHALL log the failure and exit without persisting any model file.
4. THE Retraining_Job SHALL record the start time, end time, status (success or failure), number of records ingested, number of records skipped, and MAPE per Crime_Category for each run in the Database Pipeline_Run_Log.
5. WHEN a `POST /api/v1/admin/retrain` request is received with valid administrator credentials, THE API SHALL trigger the Retraining_Job immediately outside of the scheduled cycle.
6. IF the `POST /api/v1/admin/retrain` endpoint is called without valid administrator credentials, THEN THE API SHALL return an HTTP 401 response.
7. IF a `POST /api/v1/admin/retrain` request is received while a Retraining_Job is already in progress, THEN THE API SHALL return HTTP 409 with a JSON error body indicating that a retraining run is already active.
8. IF any individual step of the Retraining_Job does not complete within 4 hours, THEN THE Retraining_Job SHALL treat that step as failed, log a timeout error, and halt subsequent steps.

---

### Requirement 9: Web Dashboard — Map Visualisation

**User Story:** As a citizen, neighbourhood watch member, or security professional, I want an interactive map of South Africa showing colour-coded crime risk scores by police station, so that I can quickly identify high-risk areas for any crime type and time period.

#### Acceptance Criteria

1. THE Dashboard SHALL render an interactive map of South Africa using Leaflet.js, with each Police_Station represented as a map marker.
2. THE Dashboard SHALL colour-code each Police_Station marker according to its current Risk_Score using the following fixed colour scale: Risk_Score 1 = #1a9641 (green), Risk_Score 2 = #a6d96a (light green), Risk_Score 3 = #ffffbf (yellow), Risk_Score 4 = #fdae61 (orange), Risk_Score 5 = #d7191c (red).
3. WHEN a user clicks a Police_Station marker on the map, THE Dashboard SHALL display a popup containing the station name, Province, current Risk_Score for the selected Crime_Category and forecast month, predicted crime count, and a sparkline showing monthly crime counts for the past 12 months.
4. WHEN a user changes a filter control (Province, Crime_Category, or forecast month), THE Dashboard SHALL update all map markers and charts to reflect the selected filters within 1,500 milliseconds.
5. THE Dashboard SHALL display a legend explaining the five-level Risk_Score colour scale and the name of the selected Crime_Category.
6. WHEN the Dashboard is loaded for the first time, THE Dashboard SHALL default to displaying all Provinces, the most prevalent Crime_Category by national volume, and the current forecast month.
7. IF no Police_Stations match the currently selected filter combination, THE Dashboard SHALL display an empty map with a visible message stating that no data is available for the selected filters.
8. THE Dashboard map and filter controls SHALL be fully operable using keyboard navigation alone, with all interactive elements reachable via Tab key and activatable via Enter or Space.

---

### Requirement 10: Web Dashboard — Trend Charts

**User Story:** As a security analyst, I want to view historical crime trend charts for selected police stations and provinces, so that I can identify seasonal patterns and compare forecasted values against historical actuals.

#### Acceptance Criteria

1. THE Dashboard SHALL display a line chart using Chart.js showing monthly crime counts for the selected Police_Station and Crime_Category; if 24 or more months of data are available, the chart SHALL display the most recent 24 months; if fewer than 24 months are available, the chart SHALL display all available months. WHEN a Forecast exists for the selected combination, THE Dashboard SHALL plot the Forecast value as a distinct data point at the forecast month position.
2. WHEN a user selects a Province from the filter controls, THE Dashboard SHALL display an aggregated bar chart showing the top 10 Police_Stations by Risk_Score within that Province for the selected Crime_Category; if fewer than 10 stations exist in the Province, THE Dashboard SHALL display all available stations.
3. THE Dashboard SHALL visually distinguish historical actuals from Forecast values in all charts by rendering historical actuals as a solid line with circular markers and Forecast values as a dashed line with filled square markers, with a chart legend identifying each series.
4. WHEN a user hovers over a data point on any chart, THE Dashboard SHALL display a tooltip showing the exact month (format `YYYY-MM`), crime count value, and whether the value is historical or a Forecast.
5. THE Dashboard SHALL provide a button labelled "Export CSV" that downloads the data currently displayed in the line chart as a CSV file containing columns: station_name, month (format `YYYY-MM`), crime_count, data_type (values: "historical" or "forecast").
6. IF no historical data is available for the selected Police_Station and Crime_Category combination, THE Dashboard SHALL display the line chart area with a visible message stating "No historical data available for the selected filters" and SHALL hide the Export CSV button.
7. IF a Province has fewer than 10 Police_Stations with Risk_Score data for the selected Crime_Category, THE Dashboard SHALL display the bar chart with only the available stations and SHALL include a note below the chart stating the number of stations displayed.

---

### Requirement 11: Containerisation and Deployment

**User Story:** As a developer or system operator, I want all system components packaged as Docker containers and orchestrated with Docker Compose, so that the entire system can be started with a single command in any environment.

#### Acceptance Criteria

1. THE Docker_Compose configuration SHALL define services for the following components: PostgreSQL Database, Python Data_Pipeline, ML_Model training and serving, Spring Boot API, and the Dashboard static file server.
2. WHEN `docker-compose up` is executed in the project root directory, THE Docker_Compose configuration SHALL start all services, apply Database migrations, and make the Dashboard accessible at `http://localhost:3000` (returning HTTP 200) and the API accessible at `http://localhost:8080` (returning HTTP 200 on `/actuator/health`) within 120 seconds.
3. THE Docker_Compose configuration SHALL define a named volume for PostgreSQL data persistence so that Database contents survive container restarts, verified by stopping and restarting the stack and confirming previously inserted records are still present.
4. THE Docker_Compose configuration SHALL use environment variables for all configurable values including database credentials, API ports, and model file paths, with a `.env.example` file documenting all required variables and their expected formats.
5. IF a required environment variable is absent when a service starts, THEN THE service SHALL log a descriptive error message identifying the missing variable by name and SHALL exit with a non-zero status code.
6. EACH service Dockerfile SHALL use a minimal base image appropriate for the service's runtime and SHALL not include development dependencies in the production image.
7. THE Docker_Compose configuration SHALL define a health check for the API service that polls `GET /actuator/health` every 10 seconds with a timeout of 5 seconds and marks the service as healthy after 3 consecutive successes, before dependent services are marked as ready.
8. IF a Database migration script fails during Docker_Compose startup, THEN THE Database initialisation container SHALL exit with a non-zero status code, log the name of the failed migration script and the error message, and the Docker_Compose health check for the Database service SHALL remain in an unhealthy state, preventing the API service from starting.

---

### Requirement 12: CI/CD Pipeline

**User Story:** As a developer, I want a GitHub Actions CI/CD pipeline that automatically builds, tests, and packages all components on every push, so that integration issues are caught early and the system is always in a deployable state.

#### Acceptance Criteria

1. THE CI/CD_Pipeline SHALL trigger automatically on every push to the `main` branch and on every pull request targeting `main`.
2. THE CI/CD_Pipeline SHALL execute the following stages in order: dependency installation, unit tests, integration tests, Docker image build, and Docker image push to a container registry.
3. IF any CI/CD_Pipeline stage fails, THEN THE CI/CD_Pipeline SHALL halt subsequent stages and report the failure with the stage name, error output, and commit SHA.
4. WHEN the Spring Boot API integration test suite runs, THE CI/CD_Pipeline SHALL measure line coverage for API endpoint classes; IF line coverage falls below 90%, THEN THE CI/CD_Pipeline SHALL fail the build and report the measured coverage percentage.
5. THE CI/CD_Pipeline SHALL run the Python ML_Model unit tests and SHALL fail the build if any test fails.
6. THE CI/CD_Pipeline SHALL build Docker images for all services defined in the Docker_Compose configuration and SHALL verify that each image reaches a running state and responds to its health check within 30 seconds before the pipeline completes.
7. THE CI/CD_Pipeline SHALL complete all stages within 15 minutes for a standard commit, defined as a commit that does not modify any dependency manifest file (e.g., `pom.xml`, `requirements.txt`, `package.json`).

---

### Requirement 13: API Security and Input Validation

**User Story:** As a system operator, I want the API to validate all inputs and protect administrative endpoints, so that the system is protected against malformed requests and unauthorised access.

#### Acceptance Criteria

1. THE API SHALL validate all query parameters and path variables on every request and SHALL return HTTP 400 with a JSON error body that identifies each invalid parameter by name and states its expected type and valid range for any request containing invalid parameter types or out-of-range values.
2. IF a required query parameter is absent from a request, THE API SHALL return HTTP 400 with a JSON error body identifying the missing parameter by name.
3. THE API SHALL reject requests containing SQL injection patterns in string inputs by returning HTTP 400 with a JSON error body, without passing the input to the Database.
4. THE API SHALL protect all endpoints under `/api/v1/admin/` with HTTP Basic Authentication, requiring a username and password configured via environment variables; WHEN an unauthenticated request (no `Authorization` header) is made to an admin endpoint, THE API SHALL return HTTP 401 with a `WWW-Authenticate: Basic realm="CrimecastZA Admin"` header.
5. IF a request to an admin endpoint provides an `Authorization` header with incorrect credentials, THEN THE API SHALL return HTTP 403 with a JSON error body stating that the provided credentials are not authorised.
6. THE API SHALL enforce a rate limit of 100 requests per fixed 60-second window per client IP address on all public endpoints, resetting the counter at the start of each new 60-second window.
7. WHEN a client exceeds the rate limit, THE API SHALL return HTTP 429 with a `Retry-After` header containing the number of whole seconds remaining in the current 60-second window and a JSON error body stating the rate limit has been exceeded.

---

### Requirement 14: Data Parser and Serialisation Round-Trip

**User Story:** As a developer, I want the Data_Pipeline to correctly parse SAPS CSV files and serialise Feature_Vectors, so that data integrity is preserved throughout the ingestion and model training process.

#### Acceptance Criteria

1. WHEN a valid SAPS CSV file is provided, THE Data_Pipeline SHALL parse it into a list of Monthly_Crime_Record objects where all required fields are non-null, numeric fields are parsed as integers or floats, and string fields are parsed as strings.
2. WHEN an invalid or malformed SAPS CSV file is provided (including files with missing required fields or type mismatches), THE Data_Pipeline SHALL return a descriptive parse error identifying the row number and field name that caused the failure.
3. THE Data_Pipeline SHALL serialise Monthly_Crime_Record objects back into CSV format using identical column names in identical order as the original SAPS files.
4. THE Data_Pipeline SHALL guarantee that for any valid Monthly_Crime_Record object, parsing then serialising then parsing SHALL produce an object with identical field values (round-trip property).
5. THE ML_Model training script SHALL serialise the trained model artefact to a `.joblib` file using joblib.
6. THE ML_Model training script SHALL deserialise the `.joblib` file back to a model object and verify that it produces identical predicted crime counts for a fixed set of reference Feature_Vectors as the original in-memory model.
7. IF serialisation or deserialisation of a model artefact fails, THEN THE ML_Model training script SHALL emit an ERROR-level log entry containing the file path attempted and the exception message, and SHALL exit with a non-zero status code.

---

### Requirement 15: System Observability and Logging

**User Story:** As a system operator, I want structured logs and health check endpoints across all services, so that I can monitor system health and diagnose failures quickly.

#### Acceptance Criteria

1. THE API SHALL expose a `GET /actuator/health` endpoint that returns HTTP 200 with a JSON body containing `{"status": "UP", "components": {"db": {"status": "UP"}}}` when the API service and its Database connection are healthy.
2. WHEN the Database connection is unavailable, THE API health endpoint SHALL return HTTP 503 with a JSON body containing `{"status": "DOWN", "components": {"db": {"status": "DOWN"}}}`.
3. THE API SHALL emit structured JSON log entries for every request, including the fields: `method`, `path`, `statusCode`, `responseTimeMs`, and `correlationId`; the `correlationId` SHALL be sourced from the `X-Correlation-ID` request header if present, or a newly generated UUID if absent.
4. THE Data_Pipeline SHALL emit structured JSON log entries for each processing step, including the fields: `step`, `recordsProcessed`, `recordsSkipped`, and `elapsedMs`.
5. THE ML_Model training script SHALL emit structured JSON log entries recording: training start event, final MAPE per Crime_Category, and the path of the serialised model artefact.
6. IF saving the model artefact to disk fails, THEN THE ML_Model training script SHALL emit an ERROR-level JSON log entry containing the file path attempted and the exception message.
7. WHILE the Docker_Compose stack is running, THE Docker_Compose configuration SHALL capture stdout and stderr from all services and make them accessible via the `docker-compose logs` command.
