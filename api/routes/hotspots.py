"""Hotspot endpoints."""

from fastapi import APIRouter, HTTPException, Query
from api.database import get_conn, put_conn

router = APIRouter()


@router.get("/hotspots")
def get_hotspots(
    province: str | None = None,
    crimeCategory: str | None = None,
    riskThreshold: float = Query(..., ge=0.0, le=1.0,
        description="Minimum risk threshold (0.0-1.0). Maps to Risk_Score: 0.2=1, 0.4=2, 0.6=3, 0.8=4, 1.0=5"),
):
    """Stations whose Risk_Score meets or exceeds the threshold."""
    # Convert 0.0-1.0 threshold to 1-5 risk score
    min_score = max(1, int(riskThreshold * 5))

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            conditions = ["f.risk_score >= %s"]
            params = [min_score]

            if province:
                conditions.append("p.name = %s")
                params.append(province)
            if crimeCategory:
                conditions.append("cc.name = %s")
                params.append(crimeCategory)

            where = "WHERE " + " AND ".join(conditions)

            cur.execute(f"""
                SELECT DISTINCT ON (ps.id)
                    ps.id, ps.canonical_name, p.name as province,
                    ST_Y(ps.location::geometry) as latitude,
                    ST_X(ps.location::geometry) as longitude,
                    f.risk_score, cc.name as crime_category,
                    f.predicted_count
                FROM forecast f
                JOIN police_station ps ON ps.id = f.station_id
                JOIN province p ON p.id = ps.province_id
                JOIN crime_category cc ON cc.id = f.category_id
                {where}
                ORDER BY ps.id, f.risk_score DESC
            """, params)

            rows = cur.fetchall()
            return [
                {
                    "stationId": r[0], "stationName": r[1], "province": r[2],
                    "latitude": float(r[3]) if r[3] else 0.0,
                    "longitude": float(r[4]) if r[4] else 0.0,
                    "riskScore": r[5], "crimeCategory": r[6],
                    "predictedCount": float(r[7]),
                }
                for r in rows
            ]
    finally:
        put_conn(conn)
