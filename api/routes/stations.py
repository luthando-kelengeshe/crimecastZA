"""Station endpoints."""

from fastapi import APIRouter
from api.database import get_conn, put_conn

router = APIRouter()


@router.get("/stations")
def list_stations():
    """All police stations with coordinates."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ps.id, ps.canonical_name, p.name as province,
                       ROUND(ST_Y(ps.location::geometry)::numeric, 6) as latitude,
                       ROUND(ST_X(ps.location::geometry)::numeric, 6) as longitude
                FROM police_station ps
                JOIN province p ON p.id = ps.province_id
                ORDER BY p.name, ps.canonical_name
            """)
            rows = cur.fetchall()

        return [
            {
                "stationId": r[0],
                "stationName": r[1],
                "province": r[2],
                "latitude": float(r[3]) if r[3] else 0.0,
                "longitude": float(r[4]) if r[4] else 0.0,
            }
            for r in rows
        ]
    finally:
        put_conn(conn)
