#!/bin/bash
# =============================================================================
# CrimecastZA — Full ETL Pipeline Script (Bash / Git Bash)
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
#   bash run_pipeline.sh
# =============================================================================

set -e

echo "============================================"
echo " CrimecastZA ETL Pipeline"
echo "============================================"
echo ""

# --- Configuration ---
DB_CONTAINER="crimecast-db"
DB_USER="crimecast"
DB_PASSWORD="crimecast"
DB_NAME="crimecastza"
DB_PORT="5432"
DB_IMAGE="postgis/postgis:16-3.4"

# --- Step 1: Start PostgreSQL in Docker ---
echo "[1/4] Starting PostgreSQL/PostGIS database..."

if docker ps --filter "name=$DB_CONTAINER" --format "{{.Names}}" | grep -q "$DB_CONTAINER"; then
    echo "  Database container already running."
elif docker ps -a --filter "name=$DB_CONTAINER" --format "{{.Names}}" | grep -q "$DB_CONTAINER"; then
    echo "  Starting existing stopped container..."
    docker start "$DB_CONTAINER" > /dev/null
else
    echo "  Creating new container..."
    docker run -d --name "$DB_CONTAINER" -p "${DB_PORT}:5432" \
        -e "POSTGRES_USER=$DB_USER" \
        -e "POSTGRES_PASSWORD=$DB_PASSWORD" \
        -e "POSTGRES_DB=$DB_NAME" \
        "$DB_IMAGE" > /dev/null
fi

# Wait for PostgreSQL to be ready
echo "  Waiting for database to be ready..."
MAX_WAIT=30
WAITED=0
until docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" > /dev/null 2>&1; do
    sleep 2
    WAITED=$((WAITED + 2))
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo "  ERROR: Database did not become ready within ${MAX_WAIT}s"
        exit 1
    fi
done
echo "  Database is ready."
echo ""

# --- Step 2: Apply schema migrations ---
echo "[2/4] Applying database schema migrations..."

for migration in db/migrations/*.sql; do
    echo "  Applying $(basename $migration)..."
    docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$migration" > /dev/null 2>&1
done
echo "  Migrations applied."
echo ""

# --- Step 3: Verify schema ---
echo "[3/4] Verifying database schema..."
TABLE_COUNT=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
echo "  Tables in database: $TABLE_COUNT"

PROVINCE_COUNT=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM province;" 2>/dev/null | tr -d ' ')
echo "  Provinces seeded: $PROVINCE_COUNT"
echo ""

# --- Step 4: Run the Python ETL pipeline ---
echo "[4/4] Running Python ingestion pipeline (Extract, Transform, Load)..."
echo "  This reads all 18 SAPS Excel files and loads into the database."
echo "  Expected time: 5-10 minutes depending on your machine."
echo ""

export DB_HOST="localhost"
export DB_PORT="$DB_PORT"
export DB_NAME="$DB_NAME"
export DB_USER="$DB_USER"
export DB_PASSWORD="$DB_PASSWORD"
export SAPS_DATA_URL="https://www.saps.gov.za/services/crimestats.php"
export QLFS_URL="https://www.statssa.gov.za/publications/P0211/P02114thQuarter2023.pdf"
export OPEN_METEO_URL="https://archive-api.open-meteo.com/v1/archive"
export PYTHONIOENCODING="utf-8"

python -m pipeline.ingest --data-dir data

echo ""
echo "============================================"
echo " Pipeline completed successfully!"
echo "============================================"
echo ""
echo "You can now query the database:"
echo "  docker exec -it $DB_CONTAINER psql -U $DB_USER -d $DB_NAME"
echo ""
echo "Example queries:"
echo "  SELECT p.name, COUNT(*) FROM police_station ps JOIN province p ON p.id=ps.province_id GROUP BY p.name;"
echo "  SELECT COUNT(*) FROM monthly_crime_record;"
