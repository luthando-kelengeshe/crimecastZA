"""Trend endpoints."""

from fastapi import APIRouter, HTTPException, Query
from api.database import get_conn, put_conn

router = APIRouter()


@router.get("/trends/{station_id}")
def get_station_trends(
    station_id: int,
    crimeCategory: str = Query(..., description="Crime category name"),
    startMonth: str = Query(..., description="Start month (YYYY-MM)"),
    endMonth: str = Query(..., description="End month (YYYY-MM)"),
):
    """Historical crime trend for a station."""
    conn = get_conn()
    try:
        # Parse months
        try:
            start_year, start_month = map(int, startMonth.split("-"))
            end_year, end_month = map(int, endMonth.split("-"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")

        with conn.cursor() as cur:
            # Verify station
            cur.execute("SELECT id FROM police_station WHERE id = %s", (station_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

            # Verify category
            cur.execute("SELECT id FROM crime_category WHERE name = %s", (crimeCategory,))
            cat_row = cur.fetchone()
            if not cat_row:
                raise HTTPException(status_code=404, detail=f"Crime category '{crimeCategory}' not found")
            category_id = cat_row[0]

            # Fetch historical data
            cur.execute("""
                SELECT year, month, monthly_count
                FROM monthly_crime_record
                WHERE station_id = %s AND category_id = %s
                  AND (year * 12 + month) >= %s
                  AND (year * 12 + month) <= %s
                ORDER BY year, month
            """, (station_id, category_id,
                  start_year * 12 + start_month,
                  end_year * 12 + end_month))

            rows = cur.fetchall()

            # Also get forecast data for this range
            cur.execute("""
                SELECT forecast_year, forecast_month, predicted_count
                FROM forecast
                WHERE station_id = %s AND category_id = %s
                  AND (forecast_year * 12 + forecast_month) >= %s
                  AND (forecast_year * 12 + forecast_month) <= %s
                ORDER BY forecast_year, forecast_month
            """, (station_id, category_id,
                  start_year * 12 + start_month,
                  end_year * 12 + end_month))

            forecast_rows = cur.fetchall()

        # Build response
        records = [
            {"month": f"{r[0]}-{r[1]:02d}", "crimeCount": r[2], "dataType": "historical"}
            for r in rows
        ]
        for r in forecast_rows:
            records.append(
                {"month": f"{r[0]}-{r[1]:02d}", "crimeCount": float(r[2]), "dataType": "forecast"}
            )

        # Determine actual data range
        if records:
            actual_start = records[0]["month"]
            actual_end = records[-1]["month"]
        else:
            actual_start = None
            actual_end = None

        response = {"records": records}
        if not records or actual_start != startMonth or actual_end != endMonth:
            response["dataRangeNote"] = (
                f"Data available from {actual_start} to {actual_end}"
                if records else "No data available for the requested range"
            )

        return response
    finally:
        put_conn(conn)


@router.get("/trends/province/{province_id}")
def get_province_trends(
    province_id: int,
    crimeCategory: str = Query(...),
    startMonth: str = Query(...),
    endMonth: str = Query(...),
):
    """Aggregated monthly crime counts for all stations in a province."""
    conn = get_conn()
    try:
        try:
            start_year, start_month = map(int, startMonth.split("-"))
            end_year, end_month = map(int, endMonth.split("-"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM province WHERE id = %s", (province_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Province {province_id} not found")

            cur.execute("SELECT id FROM crime_category WHERE name = %s", (crimeCategory,))
            cat_row = cur.fetchone()
            if not cat_row:
                raise HTTPException(status_code=404, detail=f"Crime category '{crimeCategory}' not found")
            category_id = cat_row[0]

            cur.execute("""
                SELECT mcr.year, mcr.month, SUM(mcr.monthly_count) as total
                FROM monthly_crime_record mcr
                JOIN police_station ps ON ps.id = mcr.station_id
                WHERE ps.province_id = %s AND mcr.category_id = %s
                  AND (mcr.year * 12 + mcr.month) >= %s
                  AND (mcr.year * 12 + mcr.month) <= %s
                GROUP BY mcr.year, mcr.month
                ORDER BY mcr.year, mcr.month
            """, (province_id, category_id,
                  start_year * 12 + start_month,
                  end_year * 12 + end_month))

            rows = cur.fetchall()

        records = [
            {"month": f"{r[0]}-{r[1]:02d}", "crimeCount": int(r[2]), "dataType": "historical"}
            for r in rows
        ]

        response = {"records": records}
        if not records:
            response["dataRangeNote"] = "No data available for the requested range"

        return response
    finally:
        put_conn(conn)
