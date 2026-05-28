"""
generate_documentation.py

Generates the CrimecastZA project documentation as a Word document (.docx).
Updated to reflect the actual implementation: Python FastAPI (not Spring Boot),
with security features included.

Requirements:
    pip install python-docx

Usage:
    python generate_documentation.py
"""

import os
import subprocess
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    subprocess.check_call(["pip", "install", "python-docx"])
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH


def set_cell_text(cell, text, bold=False, size=10):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)


def add_heading(doc, text, level=1):
    return doc.add_heading(text, level=level)


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    for i, header in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], header, bold=True)
    for row_idx, row_data in enumerate(rows):
        for col_idx, cell_data in enumerate(row_data):
            set_cell_text(table.rows[row_idx + 1].cells[col_idx], str(cell_data))
    return table


def add_code_block(doc, text, font_size=8):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = "Courier New"
    run.font.size = Pt(font_size)


def create_document():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    # === COVER PAGE ===
    for _ in range(4):
        doc.add_paragraph("")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Faculty of Information and Communication Technology (ICT)")
    run.font.size = Pt(14)
    run.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Computer Science Department")
    run.font.size = Pt(14)
    run.bold = True

    doc.add_paragraph("")
    doc.add_paragraph("")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Project Documentation (Assignment 3): ISJ107V 2026")
    run.font.size = Pt(16)
    run.bold = True

    doc.add_paragraph("")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("CrimecastZA: South African Crime Hotspot Forecasting System")
    run.font.size = Pt(14)
    run.italic = True

    doc.add_paragraph("")
    doc.add_paragraph("")

    info_table = doc.add_table(rows=4, cols=2)
    info_table.style = "Table Grid"
    for i, (label, value) in enumerate([
        ("Student Number", "232199660"),
        ("Student Name", "Luthando Kelengeshe"),
        ("Email", "232199660@tut4life.ac.za"),
        ("Subject Code", "ISJ107V"),
    ]):
        set_cell_text(info_table.rows[i].cells[0], label, bold=True)
        set_cell_text(info_table.rows[i].cells[1], value)

    doc.add_page_break()

    # === TABLE OF CONTENTS ===
    add_heading(doc, "Table of Contents", level=1)
    toc_items = [
        "1. Introduction",
        "2. System Architecture",
        "   2.1 Architecture Overview",
        "   2.2 Component Diagram",
        "   2.3 Deployment Diagram",
        "3. UML Design Models",
        "   3.1 Use Case Diagram",
        "   3.2 Class Diagram",
        "   3.3 Sequence Diagrams",
        "   3.4 Activity Diagram",
        "   3.5 Entity-Relationship Diagram",
        "4. Database Design",
        "   4.1 Schema Overview",
        "   4.2 Table Descriptions",
        "   4.3 Normalisation (3NF)",
        "5. API Design",
        "   5.1 REST Endpoints",
        "   5.2 Request/Response Models",
        "   5.3 Error Handling",
        "   5.4 Security",
        "6. Machine Learning Model",
        "   6.1 Feature Engineering",
        "   6.2 Training Process",
        "   6.3 Evaluation Metrics",
        "7. Data Pipeline",
        "   7.1 Pipeline Architecture",
        "   7.2 Data Flow",
        "8. Security Architecture",
        "   8.1 Authentication and Authorisation",
        "   8.2 Input Validation",
        "   8.3 Rate Limiting",
        "   8.4 SQL Injection Prevention",
        "9. Testing Strategy",
        "10. Deployment and CI/CD",
        "11. Conclusion",
    ]
    for item in toc_items:
        doc.add_paragraph(item)
    doc.add_page_break()

    # === 1. INTRODUCTION ===
    add_heading(doc, "1. Introduction", level=1)
    doc.add_paragraph(
        "CrimecastZA is a South African Crime Hotspot Forecasting System — a web-based, "
        "AI-powered predictive analytics platform that ingests historical South African Police "
        "Service (SAPS) crime statistics, socioeconomic indicators, seasonal patterns, and "
        "weather data to forecast crime hotspots across South African police regions. The system "
        "enables SAPS units, private security firms, neighbourhood watches, and citizens to make "
        "data-driven resource deployment and safety decisions."
    )
    doc.add_paragraph(
        "This document provides comprehensive technical documentation for the CrimecastZA system, "
        "including UML design models, database schema, API specifications, machine learning model "
        "architecture, security design, and deployment configuration."
    )

    add_heading(doc, "1.1 System Components", level=2)
    doc.add_paragraph("The system is composed of five integrated components:")
    for comp in [
        "A Python data ingestion and feature engineering pipeline",
        "An XGBoost machine learning forecasting model",
        "A PostgreSQL/PostGIS geographic database",
        "A Python FastAPI REST API backend with security middleware",
        "An HTML/JavaScript web dashboard with Leaflet.js map visualisation",
    ]:
        doc.add_paragraph(comp, style="List Number")

    add_heading(doc, "1.2 Technology Stack", level=2)
    add_table(doc,
        ["Layer", "Technology", "Purpose"],
        [
            ("Data Pipeline", "Python 3.14, pandas, openpyxl, psycopg2", "ETL processing and feature engineering"),
            ("ML Model", "XGBoost 2.0, scikit-learn, joblib, numpy", "Crime count regression and serialisation"),
            ("Database", "PostgreSQL 16 + PostGIS 3.4", "Geospatial data storage and querying"),
            ("Backend API", "Python FastAPI, uvicorn, pydantic", "REST API with auto-generated OpenAPI docs"),
            ("Security", "FastAPI Security, python-jose (JWT), passlib", "Authentication, rate limiting, input validation"),
            ("Frontend", "HTML5, JavaScript, Leaflet.js, Chart.js", "Interactive map and trend charts"),
            ("Containerisation", "Docker, Docker Compose", "Multi-service orchestration"),
            ("CI/CD", "GitHub Actions", "Automated build, test, and deployment"),
        ]
    )
    doc.add_page_break()

    # === 2. SYSTEM ARCHITECTURE ===
    add_heading(doc, "2. System Architecture", level=1)

    add_heading(doc, "2.1 Architecture Overview", level=2)
    doc.add_paragraph(
        "CrimecastZA follows a layered pipeline architecture with clear separation between "
        "data ingestion, model training, data serving, and presentation. The entire system is "
        "built in Python, with PostgreSQL/PostGIS as the data store and a JavaScript SPA frontend."
    )
    doc.add_paragraph("The system operates in the following flow:")
    for step in [
        "Data Ingestion: The Python pipeline reads SAPS Excel files, cleans, normalises, and loads into PostgreSQL.",
        "External Enrichment: Unemployment rates from Stats SA QLFS and weather data from Open-Meteo API are fetched and stored.",
        "Feature Engineering: SQL window functions build 9.6M feature vectors with 12-month lags, unemployment, weather, and calendar data.",
        "Model Training: XGBoost regressor trains on 9.5M samples with temporal train/test split.",
        "Forecast Generation: The trained model predicts crime counts for all station/category combinations and assigns Risk Scores (1-5).",
        "API Serving: FastAPI serves forecasts, trends, hotspots, and station data via REST endpoints with JWT authentication and rate limiting.",
        "Dashboard: The HTML/JS SPA fetches data from the API and renders a Leaflet.js map with Chart.js trend charts.",
    ]:
        doc.add_paragraph(step, style="List Number")

    add_heading(doc, "2.2 Component Diagram", level=2)
    add_code_block(doc, """
+------------------------------------------------------------------+
|                    CrimecastZA System                              |
|                                                                    |
|  +----------------+    +----------------+    +----------------+   |
|  |  Python Data   |    |  PostgreSQL +  |    |  FastAPI REST  |   |
|  |  Pipeline      |--->|  PostGIS DB    |<---|  API + Auth    |   |
|  +----------------+    +----------------+    +-------+--------+   |
|         |                      ^                     |            |
|  +----------------+            |              +------v---------+  |
|  |  ML Model      |           |              |  Web Dashboard  |  |
|  |  (XGBoost)     |-----------+              |  (Leaflet+Chart)|  |
|  +----------------+                          +----------------+   |
+------------------------------------------------------------------+
         |                    |                    |
         v                    v                    v
  [SAPS Excel Files]   [Stats SA QLFS]    [Open-Meteo API]
""")

    add_heading(doc, "2.3 Deployment Diagram", level=2)
    add_code_block(doc, """
+------------------------------------------------------------------+
|                    Host Machine / Server                           |
|                                                                    |
|  +------------------------------------------------------------+  |
|  |              Docker Compose Stack                           |  |
|  |                                                            |  |
|  |  +----------+  +----------+  +----------+  +----------+  |  |
|  |  | db:5432  |  | api:8080 |  | pipeline |  | model    |  |  |
|  |  | PostGIS  |  | FastAPI  |  | Python   |  | XGBoost  |  |  |
|  |  +----------+  +----------+  +----------+  +----------+  |  |
|  |       |              |              |             |        |  |
|  |       +------- docker-network (crimecast-net) ---+        |  |
|  |                                                            |  |
|  |  +----------------------------------------------------+   |  |
|  |  |  pgdata (named volume) - persistent storage        |   |  |
|  |  +----------------------------------------------------+   |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
""")
    doc.add_page_break()

    # === 3. UML DESIGN MODELS ===
    add_heading(doc, "3. UML Design Models", level=1)

    add_heading(doc, "3.1 Use Case Diagram", level=2)
    doc.add_paragraph(
        "The Use Case Diagram identifies the primary actors and their interactions with CrimecastZA."
    )
    add_code_block(doc, """
Actors:
  [Citizen]           -> View Hotspot Map, Filter Data, View Trends, Export CSV
  [Security Analyst]  -> View Trends, Export CSV, Query API
  [Administrator]     -> Trigger Retraining, Manage Users (JWT)
  [API Consumer]      -> Query Forecast API (authenticated)
  [Scheduler]         -> Quarterly Automated Retraining

Use Cases:
  UC-01: View Crime Hotspot Map (colour-coded risk markers)
  UC-02: Filter by Province / Crime Type / Risk Level
  UC-03: View Historical Crime Trends (line chart)
  UC-04: Export Trend Data as CSV
  UC-05: View Station Risk Score (click marker popup)
  UC-06: Trigger Manual Retraining (admin, JWT required)
  UC-07: Query Forecast API (paginated, filtered)
  UC-08: Authenticate via JWT Token
  UC-09: Quarterly Automated Retraining (cron/scheduler)
""")

    add_heading(doc, "3.2 Class Diagram", level=2)
    doc.add_paragraph("Key domain classes across all system components:")
    add_code_block(doc, """
PYTHON PIPELINE CLASSES:
+------------------------+    +---------------------------+
|    CleanedRecord       |    |      FeatureVector        |
+------------------------+    +---------------------------+
| - original_name: str   |    | - station_id: int         |
| - canonical_name: str  |    | - category_id: int        |
| - province: str        |    | - year, month: int        |
| - category: str        |    | - lags: list[int] (12)    |
| - year, month: int     |    | - unemployment_rate: float|
| - monthly_count: int   |    | - mean_temp_c: float      |
+------------------------+    | - total_precip_mm: float  |
                              | - holiday_count: int      |
+------------------------+    | - payday_count: int       |
|   ValidationResult     |    +---------------------------+
+------------------------+
| - ok: bool             |
| - errors: list[str]    |
+------------------------+

FASTAPI CLASSES:
+---------------------------+    +---------------------------+
|   ForecastResponse        |    |    HotspotResponse        |
+---------------------------+    +---------------------------+
| + stationId: int          |    | + stationId: int          |
| + stationName: str        |    | + stationName: str        |
| + province: str           |    | + province: str           |
| + crimeCategory: str      |    | + latitude: float         |
| + forecastYear: int       |    | + longitude: float        |
| + forecastMonth: int      |    | + riskScore: int          |
| + predictedCount: float   |    | + predictedCount: float   |
| + riskScore: int          |    +---------------------------+
+---------------------------+

+---------------------------+    +---------------------------+
|   TrendRecord             |    |    SecurityMiddleware     |
+---------------------------+    +---------------------------+
| + month: str (YYYY-MM)    |    | + verify_jwt(token)       |
| + crimeCount: int         |    | + rate_limit(ip, window)  |
| + dataType: str           |    | + validate_input(params)  |
+---------------------------+    | + check_sql_injection(s)  |
                                 +---------------------------+
""")

    add_heading(doc, "3.3 Sequence Diagrams", level=2)
    add_heading(doc, "3.3.1 Forecast Request Sequence", level=3)
    add_code_block(doc, """
Dashboard       FastAPI         Database
   |                |               |
   | GET /api/v1/   |               |
   | forecasts?...  |               |
   |--------------->|               |
   |                | verify JWT    |
   |                | rate limit    |
   |                | validate      |
   |                |               |
   |                | SELECT ...    |
   |                |-------------->|
   |                |               |
   |                |  result set   |
   |                |<--------------|
   |                |               |
   | JSON response  |               |
   | (paginated)    |               |
   |<---------------|               |
""")

    add_heading(doc, "3.3.2 Authentication Sequence", level=3)
    add_code_block(doc, """
Client          FastAPI         Database
   |                |               |
   | POST /api/v1/  |               |
   | auth/login     |               |
   | {user, pass}   |               |
   |--------------->|               |
   |                | verify creds  |
   |                |-------------->|
   |                |  user record  |
   |                |<--------------|
   |                |               |
   |                | generate JWT  |
   |                | (exp: 24h)    |
   |                |               |
   | {access_token} |               |
   |<---------------|               |
   |                |               |
   | GET /api/v1/   |               |
   | admin/retrain  |               |
   | Auth: Bearer   |               |
   |--------------->|               |
   |                | decode JWT    |
   |                | check role    |
   |                | execute       |
   |<---------------|               |
""")
    doc.add_page_break()

    # === 3.4 Activity Diagram ===
    add_heading(doc, "3.4 Activity Diagram", level=2)
    doc.add_paragraph("Data pipeline processing workflow:")
    add_code_block(doc, """
[START] --> [Download SAPS Excel Files]
        --> <Portal reachable?> --No--> [Log error, abort]
                |Yes
        --> [Validate file structure]
        --> <Columns valid?> --No--> [Log error, skip file]
                |Yes
        --> [Clean: trim, title-case, deduplicate, quarterly->monthly]
        --> [Normalise provinces and crime categories]
        --> [Load into monthly_crime_record table]
        --> [Fetch unemployment from Stats SA QLFS]
        --> [Fetch weather from Open-Meteo API (with 3x retry)]
        --> [Load calendar events (holidays + paydays)]
        --> [Build feature vectors (SQL window functions)]
        --> [Train XGBoost model]
        --> <MAPE < 15%?> --No--> [Log warning, retain old model]
                |Yes
        --> [Serialise model to .joblib]
        --> [Generate forecasts for all stations]
        --> [Compute Risk Scores (1-5 percentile ranking)]
        --> [Store forecasts in database]
        --> [END]
""")

    add_heading(doc, "3.5 Entity-Relationship Diagram", level=2)
    doc.add_paragraph("Database entity relationships (3NF):")
    add_code_block(doc, """
[province] 1---* [police_station] 1---* [monthly_crime_record] *---1 [crime_category]
                        |
                        1---* [weather_record]
                        1---* [feature_vector] *---1 [crime_category]
                        1---* [forecast] *---1 [crime_category]

[province] 1---* [unemployment_record]
[calendar_event] (standalone - dates with holiday/payday flags)
[pipeline_run_log] (standalone - ETL run history)
[api_user] (standalone - JWT authentication users)
""")
    doc.add_page_break()

    # === 4. DATABASE DESIGN ===
    add_heading(doc, "4. Database Design", level=1)

    add_heading(doc, "4.1 Schema Overview", level=2)
    doc.add_paragraph(
        "The database uses PostgreSQL 16 with PostGIS extension for geospatial queries. "
        "The schema is in Third Normal Form (3NF) with 11 tables."
    )

    add_heading(doc, "4.2 Table Descriptions", level=2)
    add_table(doc,
        ["Table", "Rows", "Purpose"],
        [
            ("province", "9", "South African provinces"),
            ("police_station", "1,207", "SAPS police stations with PostGIS coordinates"),
            ("crime_category", "44", "Normalised SAPS crime classifications"),
            ("monthly_crime_record", "11M+", "Monthly crime counts per station per category"),
            ("unemployment_record", "216", "Provincial quarterly unemployment rates (Stats SA QLFS)"),
            ("weather_record", "120K+", "Monthly temperature and precipitation per station"),
            ("calendar_event", "581", "SA public holidays and paydays (2005-2027)"),
            ("feature_vector", "10M+", "ML training features (12 lags + enrichment)"),
            ("forecast", "51,656", "Predicted crime counts with Risk Scores"),
            ("pipeline_run_log", "varies", "ETL pipeline execution history"),
            ("api_user", "varies", "Authenticated API users (hashed passwords, roles)"),
        ]
    )

    add_heading(doc, "4.3 Normalisation (3NF)", level=2)
    doc.add_paragraph(
        "The schema satisfies Third Normal Form: all non-key attributes depend on the whole "
        "primary key and nothing but the key. Province, station, and category are separate "
        "entities referenced by foreign keys. No transitive dependencies exist."
    )
    doc.add_page_break()

    # === 5. API DESIGN ===
    add_heading(doc, "5. API Design", level=1)

    add_heading(doc, "5.1 REST Endpoints", level=2)
    doc.add_paragraph(
        "The API is built with Python FastAPI, providing automatic OpenAPI/Swagger documentation "
        "at /docs. All endpoints return JSON responses."
    )
    add_table(doc,
        ["Method", "Path", "Auth", "Description"],
        [
            ("GET", "/api/v1/forecasts", "Optional", "Paginated forecasts with province/category/date filters"),
            ("GET", "/api/v1/forecasts/{stationId}", "Optional", "All forecasts for a specific station"),
            ("GET", "/api/v1/hotspots", "Optional", "Stations exceeding a risk threshold"),
            ("GET", "/api/v1/trends/{stationId}", "Optional", "Historical crime trend for a station"),
            ("GET", "/api/v1/trends/province/{id}", "Optional", "Aggregated provincial crime trend"),
            ("GET", "/api/v1/stations", "Optional", "All stations with coordinates"),
            ("POST", "/api/v1/auth/login", "None", "Authenticate and receive JWT token"),
            ("POST", "/api/v1/admin/retrain", "JWT (admin)", "Trigger immediate model retraining"),
            ("GET", "/actuator/health", "None", "Health check for Docker/monitoring"),
            ("GET", "/docs", "None", "Swagger UI (auto-generated OpenAPI docs)"),
        ]
    )

    add_heading(doc, "5.2 Request/Response Models", level=2)
    doc.add_paragraph("Forecast Response:")
    add_code_block(doc, """
{
  "items": [
    {
      "stationId": 42,
      "stationName": "Honeydew",
      "province": "Gauteng",
      "crimeCategory": "Murder",
      "forecastYear": 2026,
      "forecastMonth": 3,
      "predictedCount": 15.2,
      "riskScore": 5,
      "modelVersion": "xgb_20260525_190622"
    }
  ],
  "total": 51656,
  "page": 1,
  "pageSize": 20
}
""")
    doc.add_paragraph("Error Response:")
    add_code_block(doc, """
{
  "detail": "Station 99999 not found"
}
// HTTP 404
""")

    add_heading(doc, "5.3 Error Handling", level=2)
    add_table(doc,
        ["HTTP Status", "Condition", "Response"],
        [
            ("400", "Invalid parameter type or range", "JSON with parameter name and expected format"),
            ("401", "Missing or invalid JWT token", "WWW-Authenticate header"),
            ("403", "Valid token but insufficient role", "Access denied message"),
            ("404", "Station/province/category not found", "JSON identifying the invalid resource"),
            ("429", "Rate limit exceeded (100 req/min)", "Retry-After header with seconds remaining"),
            ("500", "Unhandled server error", "Sanitised error message (no stack traces)"),
        ]
    )

    add_heading(doc, "5.4 Security", level=2)
    doc.add_paragraph(
        "The API implements multiple security layers as described in Section 8."
    )
    doc.add_page_break()

    # === 6. MACHINE LEARNING MODEL ===
    add_heading(doc, "6. Machine Learning Model", level=1)

    add_heading(doc, "6.1 Feature Engineering", level=2)
    doc.add_paragraph("Each feature vector contains 18 features:")
    add_table(doc,
        ["Feature", "Type", "Source"],
        [
            ("lag_1 through lag_12", "int", "12-month lagged crime counts from monthly_crime_record"),
            ("unemployment_rate", "float", "Provincial quarterly rate from Stats SA QLFS"),
            ("mean_temp_c", "float", "Monthly average temperature from Open-Meteo API"),
            ("total_precip_mm", "float", "Monthly total precipitation from Open-Meteo API"),
            ("public_holiday_count", "int", "Number of public holidays in the month"),
            ("payday_count", "int", "Number of paydays in the month"),
            ("month_of_year", "int", "Calendar month (1-12) for seasonality"),
        ]
    )
    doc.add_paragraph(
        "Feature vectors are built in bulk using PostgreSQL LAG() window functions, "
        "processing 10M+ records in under 5 minutes."
    )

    add_heading(doc, "6.2 Training Process", level=2)
    doc.add_paragraph("The training pipeline:")
    for step in [
        "Load all feature vectors joined with target (monthly_count) from PostgreSQL",
        "Temporal train/test split: test = last 12 months, train = everything before",
        "Train XGBoost regressor (200 trees, max_depth=6, learning_rate=0.1)",
        "Evaluate MAPE per crime category on holdout test set",
        "If MAPE < 15% for 5+ categories: serialise model with joblib",
        "Record training metrics in pipeline_run_log",
    ]:
        doc.add_paragraph(step, style="List Number")

    add_heading(doc, "6.3 Evaluation Metrics", level=2)
    doc.add_paragraph(
        "The model is evaluated using Mean Absolute Percentage Error (MAPE) per crime category. "
        "MAPE = mean(|actual - predicted| / actual) x 100. The target threshold is < 15% for "
        "at least 5 crime categories. Current performance ranges from 22% (Murder) to 89% "
        "(rare crime types), reflecting the challenge of predicting low-count events."
    )

    add_heading(doc, "6.4 Risk Score Derivation", level=2)
    doc.add_paragraph(
        "Each forecast receives a Risk Score (1-5) by ranking the predicted count against "
        "the historical distribution for the same crime category and province:"
    )
    add_table(doc,
        ["Score", "Percentile Range", "Meaning"],
        [
            ("1", "0-20th percentile", "Low risk (below average)"),
            ("2", "20-40th percentile", "Moderate risk"),
            ("3", "40-60th percentile", "Medium risk (average)"),
            ("4", "60-80th percentile", "High risk (above average)"),
            ("5", "80-100th percentile", "Extreme risk (hotspot)"),
        ]
    )
    doc.add_page_break()

    # === 7. DATA PIPELINE ===
    add_heading(doc, "7. Data Pipeline", level=1)

    add_heading(doc, "7.1 Pipeline Architecture", level=2)
    add_table(doc,
        ["Module", "File", "Responsibility"],
        [
            ("SAPS Reader", "pipeline/saps_reader.py", "Reads 19 SAPS Excel files (3 format variants), normalises provinces and categories"),
            ("DB Loader", "pipeline/db_loader.py", "Bulk-upserts records into PostgreSQL with connection pooling"),
            ("Enricher", "pipeline/enricher.py", "Fetches unemployment data and loads SA holiday/payday calendar"),
            ("External Data", "pipeline/fetch_external_data.py", "Fetches weather from Open-Meteo API, loads QLFS unemployment rates"),
            ("Feature Builder", "model/build_features.py", "Builds 10M+ feature vectors using SQL window functions"),
            ("Geocoder", "pipeline/geocode_stations.py", "Assigns geographic coordinates to stations by province"),
            ("Ingestion Entry", "pipeline/ingest.py", "Main orchestrator: read -> clean -> load -> log"),
        ]
    )

    add_heading(doc, "7.2 Data Flow", level=2)
    doc.add_paragraph("Data volumes at each stage:")
    add_table(doc,
        ["Stage", "Records", "Time"],
        [
            ("Raw Excel extraction", "34.8M records from 19 files", "~5 minutes"),
            ("Deduplication", "10.3M unique monthly records", "~1 minute"),
            ("Database load", "10.3M rows in monthly_crime_record", "~7 minutes"),
            ("Feature vector build", "10.1M feature vectors", "~5 minutes"),
            ("Model training", "9.5M train + 619K test samples", "~5 minutes"),
            ("Forecast generation", "51,656 forecasts", "~7 minutes"),
        ]
    )
    doc.add_page_break()

    # === 8. SECURITY ARCHITECTURE ===
    add_heading(doc, "8. Security Architecture", level=1)

    add_heading(doc, "8.1 Authentication and Authorisation", level=2)
    doc.add_paragraph(
        "The API uses JSON Web Tokens (JWT) for authentication. Public endpoints (forecasts, "
        "trends, stations, hotspots) are accessible without authentication to support the "
        "dashboard. Administrative endpoints (retraining, user management) require a valid "
        "JWT token with an 'admin' role."
    )
    doc.add_paragraph("Authentication flow:")
    for step in [
        "Client sends POST /api/v1/auth/login with username and password",
        "Server verifies credentials against bcrypt-hashed password in api_user table",
        "On success, server returns a signed JWT token (HS256, 24-hour expiry)",
        "Client includes token in subsequent requests: Authorization: Bearer <token>",
        "Server middleware decodes and validates the token on protected endpoints",
        "If token is expired or invalid, server returns HTTP 401",
    ]:
        doc.add_paragraph(step, style="List Number")

    add_heading(doc, "8.2 Input Validation", level=2)
    doc.add_paragraph(
        "All API inputs are validated using FastAPI's built-in Pydantic validation and "
        "custom middleware:"
    )
    for item in [
        "Query parameters are type-checked and range-validated (e.g., riskThreshold must be 0.0-1.0)",
        "Path parameters are validated as integers where expected",
        "String inputs are checked for SQL injection patterns before reaching the database",
        "Invalid inputs return HTTP 400 with a JSON body identifying the invalid parameter",
        "FastAPI's automatic validation provides clear error messages via Pydantic",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    add_heading(doc, "8.3 Rate Limiting", level=2)
    doc.add_paragraph(
        "The API implements per-IP rate limiting using an in-memory token bucket algorithm. "
        "Each client IP is allowed 100 requests per 60-second window. When the limit is "
        "exceeded, the API returns HTTP 429 with a Retry-After header indicating the number "
        "of seconds until the window resets."
    )
    add_code_block(doc, """
# Rate limit middleware (simplified)
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_requests=100, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.clients = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        # Remove expired timestamps
        self.clients[client_ip] = [
            t for t in self.clients[client_ip]
            if now - t < self.window
        ]
        if len(self.clients[client_ip]) >= self.max_requests:
            return False
        self.clients[client_ip].append(now)
        return True
""")

    add_heading(doc, "8.4 SQL Injection Prevention", level=2)
    doc.add_paragraph(
        "The system prevents SQL injection through multiple layers:"
    )
    for item in [
        "All database queries use parameterised queries (psycopg2 %s placeholders) — user input is never concatenated into SQL strings",
        "String inputs are checked against known SQL injection patterns (OR 1=1, UNION SELECT, DROP TABLE, etc.) before processing",
        "FastAPI's Pydantic models enforce type constraints at the API boundary",
        "Database user has minimal privileges (SELECT, INSERT, UPDATE on application tables only)",
    ]:
        doc.add_paragraph(item, style="List Bullet")
    doc.add_page_break()

    # === 9. TESTING STRATEGY ===
    add_heading(doc, "9. Testing Strategy", level=1)

    doc.add_paragraph(
        "CrimecastZA uses property-based testing (Hypothesis library) for universal correctness "
        "properties and example-based unit tests for specific scenarios."
    )

    add_table(doc,
        ["Property", "Test File", "What It Validates"],
        [
            ("CSV column validation", "test_validator.py", "Validator accepts iff all 4 required columns present"),
            ("Name cleaning", "test_cleaner.py", "Original name preserved, canonical is trimmed title-case"),
            ("Quarterly-to-monthly", "test_cleaner.py", "monthly_count = floor(quarterly / 3), always non-negative"),
            ("Open-Meteo retry", "test_downloader.py", "Retries with 1s/2s/4s backoff, continues after 3 failures"),
            ("Feature completeness", "test_feature_builder.py", "All 12 lags and enrichment fields are non-null"),
            ("Pipeline log", "test_logger.py", "Log entries contain step, recordsProcessed, recordsSkipped, elapsedMs"),
            ("Temporal split", "test_train.py", "No record in both train and test; respects 12-month boundary"),
            ("Risk score range", "test_risk_scorer.py", "Score always 1-5, correctly reflects percentile boundaries"),
        ]
    )

    doc.add_paragraph(
        "All property tests run with --hypothesis-seed=0 for reproducibility in CI. "
        "Each test runs a minimum of 100 iterations."
    )
    doc.add_page_break()

    # === 10. DEPLOYMENT ===
    add_heading(doc, "10. Deployment and CI/CD", level=1)

    add_heading(doc, "10.1 Docker Compose", level=2)
    doc.add_paragraph("The system is containerised with Docker Compose defining:")
    for svc in [
        "db: PostgreSQL 16 + PostGIS 3.4 with named volume for persistence",
        "api: FastAPI application (Python 3.14, uvicorn) on port 8080",
        "pipeline: Python data ingestion service (runs on demand)",
        "model: XGBoost training and prediction service (runs on demand)",
    ]:
        doc.add_paragraph(svc, style="List Bullet")

    add_heading(doc, "10.2 CI/CD Pipeline (GitHub Actions)", level=2)
    doc.add_paragraph("The pipeline triggers on push to main and PRs:")
    for stage in [
        "Install Python dependencies",
        "Run property-based tests (pytest --hypothesis-seed=0)",
        "Run unit tests",
        "Build Docker images",
        "Verify health checks",
        "Push images to container registry (main branch only)",
    ]:
        doc.add_paragraph(stage, style="List Number")

    add_heading(doc, "10.3 Running Locally", level=2)
    add_code_block(doc, """
# Set environment variables
$env:DB_HOST="localhost"
$env:DB_PORT="5432"
$env:DB_NAME="crimecastza"
$env:DB_USER="postgres"
$env:DB_PASSWORD="9966"

# Start the API + Dashboard
python -m api

# Open browser: http://localhost:8080
# API docs: http://localhost:8080/docs
""")
    doc.add_page_break()

    # === 11. CONCLUSION ===
    add_heading(doc, "11. Conclusion", level=1)
    doc.add_paragraph(
        "CrimecastZA demonstrates a complete end-to-end machine learning pipeline for crime "
        "forecasting in South Africa. The system ingests 10+ million historical crime records "
        "from SAPS, enriches them with socioeconomic and environmental data, trains an XGBoost "
        "model to predict monthly crime counts, and presents the results through an interactive "
        "web dashboard with a secure REST API."
    )
    doc.add_paragraph(
        "Key achievements:"
    )
    for item in [
        "Automated ingestion of 19 SAPS Excel files spanning 2008-2026 (34.8M raw records)",
        "10.3 million deduplicated monthly crime records across 1,207 stations and 44 categories",
        "Real-time weather and unemployment data enrichment from external APIs",
        "XGBoost model trained on 9.5M samples with temporal validation",
        "51,656 forecasts with Risk Scores (1-5) for resource deployment decisions",
        "Secure FastAPI backend with JWT authentication, rate limiting, and input validation",
        "Interactive Leaflet.js map with colour-coded risk markers and Chart.js trend visualisation",
        "Property-based testing ensuring correctness across all data transformations",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph(
        "The system provides a practical tool for SAPS, private security, and communities "
        "to make proactive, data-driven safety decisions rather than reacting to crime after "
        "the fact."
    )

    return doc


# === MAIN ===
if __name__ == "__main__":
    doc = create_document()
    output_path = os.path.join(os.path.dirname(__file__), "CrimecastZA_Project_Documentation.docx")
    doc.save(output_path)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"Document saved to: {output_path}")
    print(f"  File size: {size_kb:.1f} KB")
