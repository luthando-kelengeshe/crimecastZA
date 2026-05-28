"""
CrimecastZA FastAPI REST API

Usage:
    python -m api.main

Endpoints:
    GET /api/v1/forecasts          — paginated forecasts with filters
    GET /api/v1/forecasts/{id}     — forecasts for a station
    GET /api/v1/hotspots           — stations above risk threshold
    GET /api/v1/trends/{id}        — historical crime trends
    GET /api/v1/trends/province/{id} — provincial aggregated trends
    GET /api/v1/stations           — all stations with coordinates
    GET /docs                      — Swagger UI
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from api.routes import forecasts, hotspots, trends, stations, auth
from api.security import rate_limiter

app = FastAPI(
    title="CrimecastZA API",
    description="South African Crime Hotspot Forecasting System",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = rate_limiter.is_allowed(client_ip)
    if not allowed:
        return Response(
            content='{"detail":"Rate limit exceeded"}',
            status_code=429,
            headers={"Retry-After": str(retry_after), "Content-Type": "application/json"},
        )
    return await call_next(request)


# Register routers
app.include_router(forecasts.router, prefix="/api/v1")
app.include_router(hotspots.router, prefix="/api/v1")
app.include_router(trends.router, prefix="/api/v1")
app.include_router(stations.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")


@app.get("/actuator/health")
def health():
    return {"status": "UP"}


# Serve dashboard static files
dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
if os.path.isdir(dashboard_dir):
    app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8080, reload=True)
