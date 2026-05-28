"""Forecast endpoints."""

from fastapi import APIRouter, HTTPException, Query
from api.database import get_conn, put_conn

router = APIRouter()


@router.get("/forecasts")
def list_forecasts(
    province: str | None = None,
    crimeCategory: str | None = None,
    year: int | None = None,
    month: int | None = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
):
    """Paginated forecasts with optional filters."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []

            if province:
                conditions.append("p.name = %s")
                params.append(province)
            if crimeCategory:
                conditions.append("cc.name = %s")
                params.append(crimeCategory)
            if year:
                conditions.append("f.forecast_year = %s")
                params.append(year)
            if month:
                conditions.append("f.forecast_month = %s")
                params.append(month)

            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            offset = (page - 1) * pageSize

            # Count total
            cur.execute(f"""
                SELECT COUNT(*) FROM forecast f
                JOIN police_station ps ON ps.id = f.station_id
                JOIN province p ON p.id = ps.province_id
                JOIN crime_category cc ON cc.id = f.category_id
                {where}
            """, params)
            total = cur.fetchone()[0]

            # Fetch page
            cur.execute(f"""
                SELECT f.station_id, ps.canonical_name, p.name as province,
                       cc.name as crime_category, f.forecast_year, f.forecast_month,
                       f.predicted_count, f.risk_score, f.model_version
                FROM forecast f
                JOIN police_station ps ON ps.id = f.station_id
                JOIN province p ON p.id = ps.province_id
                JOIN crime_category cc ON cc.id = f.category_id
                {where}
                ORDER BY f.risk_score DESC, f.predicted_count DESC
                LIMIT %s OFFSET %s
            """, params + [pageSize, offset])

            rows = cur.fetchall()
            items = [
                {
                    "stationId": r[0], "stationName": r[1], "province": r[2],
                    "crimeCategory": r[3], "forecastYear": r[4], "forecastMonth": r[5],
                    "predictedCount": float(r[6]), "riskScore": r[7], "modelVersion": r[8],
                }
                for r in rows
            ]

        return {"items": items, "total": total, "page": page, "pageSize": pageSize}
    finally:
        put_conn(conn)


@router.get("/forecasts/{station_id}")
def get_station_forecasts(station_id: int):
    """All forecasts for a specific station."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Verify station exists
            cur.execute("SELECT id FROM police_station WHERE id = %s", (station_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Station {station_id} not found")

            cur.execute("""
                SELECT f.station_id, ps.canonical_name, p.name, cc.name,
                       f.forecast_year, f.forecast_month, f.predicted_count,
                       f.risk_score, f.model_version
                FROM forecast f
                JOIN police_station ps ON ps.id = f.station_id
                JOIN province p ON p.id = ps.province_id
                JOIN crime_category cc ON cc.id = f.category_id
                WHERE f.station_id = %s
                ORDER BY f.forecast_year DESC, f.forecast_month DESC, cc.name
            """, (station_id,))

            rows = cur.fetchall()
            return [
                {
                    "stationId": r[0], "stationName": r[1], "province": r[2],
                    "crimeCategory": r[3], "forecastYear": r[4], "forecastMonth": r[5],
                    "predictedCount": float(r[6]), "riskScore": r[7], "modelVersion": r[8],
                }
                for r in rows
            ]
    finally:
        put_conn(conn)
