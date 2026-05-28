"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.database import get_conn, put_conn
from api.security import create_access_token, hash_password, verify_password, require_admin

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """Authenticate and receive a JWT token."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash, role FROM api_user WHERE username = %s AND is_active = TRUE",
                (request.username,),
            )
            row = cur.fetchone()

        if row is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        stored_hash, role = row
        if not verify_password(request.password, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token(username=request.username, role=role)
        return TokenResponse(access_token=token)
    finally:
        put_conn(conn)


@router.post("/admin/retrain")
def trigger_retrain(user: dict = Depends(require_admin)):
    """Trigger immediate model retraining (admin only)."""
    # In production this would kick off the pipeline asynchronously
    return {
        "message": "Retraining job triggered",
        "triggered_by": user["sub"],
    }
