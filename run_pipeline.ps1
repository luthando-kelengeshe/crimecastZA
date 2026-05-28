# =============================================================================
# CrimecastZA — Full ETL Pipeline Script (PowerShell)
#
# This script:
#   1. Starts a PostgreSQL/PostGIS database in Docker
#   2. Applies the schema migrations (creates all tables)
#   3. Runs the Python ingestion pipeline (Extract, Transform, Load)
#
# Prerequisites:
#   - Docker Desktop running
#   - Python 3.10+ with pip packages installed:
#       pip install -r pipeline/requirements.txt
#
# Usage:
#   .\run_pipeline.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " CrimecastZA ETL Pipeline" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- Configuration ---
$DB_CONTAINER = "crimecast-db"
$DB_USER = "postgres"
$DB_PASSWORD = "postgres"
$DB_NAME = "crimecastza"
$DB_PORT = "5433"          # Using 5433 to avoid conflict with local PostgreSQL on 5432
$DB_IMAGE = "postgis/postgis:16-3.4"

# --- Step 1: Start PostgreSQL in Docker ---
Write-Host "[1/4] Starting PostgreSQL/PostGIS database..." -ForegroundColor Yellow

# Remove existing container if it exists (stopped)
$existing = docker ps -a --filter "name=$DB_CONTAINER" --format "{{.Names}}" 2>$null
if ($existing -eq $DB_CONTAINER) {
    $running = docker ps --filter "name=$DB_CONTAINER" --format "{{.Names}}" 2>$null
    if ($running -eq $DB_CONTAINER) {
        Write-Host "  Database container already running." -ForegroundColor Green
    } else {
        Write-Host "  Starting existing stopped container..."
        docker start $DB_CONTAINER | Out-Null
    }
} else {
    Write-Host "  Creating new container..."
    docker run -d --name $DB_CONTAINER -p "${DB_PORT}:5432" `
        -e "POSTGRES_USER=$DB_USER" `
        -e "POSTGRES_PASSWORD=$DB_PASSWORD" `
        -e "POSTGRES_DB=$DB_NAME" `
        $DB_IMAGE | Out-Null
}

# Wait for PostgreSQL to be ready
Write-Host "  Waiting for database to be ready..."
$maxWait = 30
$waited = 0
do {
    Start-Sleep -Seconds 2
    $waited += 2
    $ready = docker exec $DB_CONTAINER pg_isready -U $DB_USER 2>$null
} while ($LASTEXITCODE -ne 0 -and $waited -lt $maxWait)

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Database did not become ready within ${maxWait}s" -ForegroundColor Red
    exit 1
}
Write-Host "  Database is ready." -ForegroundColor Green
Write-Host ""

# --- Step 2: Apply schema migrations ---
Write-Host "[2/4] Applying database schema migrations..." -ForegroundColor Yellow

$migrations = Get-ChildItem -Path "db\migrations\*.sql" | Sort-Object Name
foreach ($migration in $migrations) {
    Write-Host "  Applying $($migration.Name)..."
    $sql = Get-Content $migration.FullName -Raw
    docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "$sql" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        # Try with file piping instead
        Get-Content $migration.FullName | docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME 2>&1 | Out-Null
    }
}
Write-Host "  Migrations applied." -ForegroundColor Green
Write-Host ""

# --- Step 3: Verify schema ---
Write-Host "[3/4] Verifying database schema..." -ForegroundColor Yellow
$tableCount = docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>$null
Write-Host "  Tables in database: $($tableCount.Trim())" -ForegroundColor Green

$provinceCount = docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM province;" 2>$null
Write-Host "  Provinces seeded: $($provinceCount.Trim())" -ForegroundColor Green
Write-Host ""

# --- Step 4: Run the Python ETL pipeline ---
Write-Host "[4/4] Running Python ingestion pipeline (Extract, Transform, Load)..." -ForegroundColor Yellow
Write-Host "  This reads all 18 SAPS Excel files and loads into the database."
Write-Host "  Expected time: 5-10 minutes depending on your machine."
Write-Host ""

# Set environment variables for the pipeline
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = $DB_PORT
$env:DB_NAME = $DB_NAME
$env:DB_USER = $DB_USER
$env:DB_PASSWORD = $DB_PASSWORD
$env:SAPS_DATA_URL = "https://www.saps.gov.za/services/crimestats.php"
$env:QLFS_URL = "https://www.statssa.gov.za/publications/P0211/P02114thQuarter2023.pdf"
$env:OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
$env:PYTHONIOENCODING = "utf-8"

python -m pipeline.ingest --data-dir data

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host " Pipeline completed successfully!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now query the database:" -ForegroundColor Cyan
    Write-Host "  docker exec -it $DB_CONTAINER psql -U $DB_USER -d $DB_NAME"
    Write-Host ""
    Write-Host "Example queries:" -ForegroundColor Cyan
    Write-Host "  SELECT p.name, COUNT(*) FROM police_station ps JOIN province p ON p.id=ps.province_id GROUP BY p.name;"
    Write-Host "  SELECT COUNT(*) FROM monthly_crime_record;"
    Write-Host "  SELECT cc.name, COUNT(*) FROM monthly_crime_record mcr JOIN crime_category cc ON cc.id=mcr.category_id GROUP BY cc.name ORDER BY COUNT(*) DESC LIMIT 10;"
} else {
    Write-Host ""
    Write-Host "Pipeline failed. Check the error messages above." -ForegroundColor Red
    exit 1
}
