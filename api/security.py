"""
API Security: JWT authentication, rate limiting, SQL injection prevention.
"""

import hashlib
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import jwt

# JWT Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "crimecastza-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

security_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# JWT Token Management
# ---------------------------------------------------------------------------

def create_access_token(username: str, role: str = "user") -> str:
    """Create a signed JWT token."""
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[dict]:
    """Extract current user from JWT token. Returns None if no token provided."""
    if credentials is None:
        return None
    return decode_token(credentials.credentials)


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> dict:
    """Require a valid JWT token with admin role."""
    payload = decode_token(credentials.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

class RateLimiter:
    """In-memory per-IP rate limiter using sliding window."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.clients: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, retry_after_seconds)."""
        now = time.time()
        # Prune expired timestamps
        self.clients[client_ip] = [
            t for t in self.clients[client_ip]
            if now - t < self.window
        ]
        if len(self.clients[client_ip]) >= self.max_requests:
            oldest = self.clients[client_ip][0]
            retry_after = int(self.window - (now - oldest)) + 1
            return False, retry_after

        self.clients[client_ip].append(now)
        return True, 0


rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


# ---------------------------------------------------------------------------
# SQL Injection Detection
# ---------------------------------------------------------------------------

_SQL_INJECTION_PATTERNS = [
    r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)",
    r"(;\s*(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE)\b)",
    r"(\bUNION\b\s+\bSELECT\b)",
    r"(--\s*$)",
    r"(/\*.*\*/)",
    r"(\bEXEC\b\s*\()",
    r"(\bxp_\w+)",
]

_SQL_INJECTION_RE = re.compile("|".join(_SQL_INJECTION_PATTERNS), re.IGNORECASE)


def check_sql_injection(value: str) -> bool:
    """Returns True if the value contains a SQL injection pattern."""
    return bool(_SQL_INJECTION_RE.search(value))


def validate_input(value: str, param_name: str) -> str:
    """Validate a string input for SQL injection. Raises HTTPException if detected."""
    if check_sql_injection(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid input detected in parameter '{param_name}'"
        )
    return value


# ---------------------------------------------------------------------------
# Password Hashing (for user management)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt. Use bcrypt in production."""
    salt = os.environ.get("PASSWORD_SALT", "crimecastza-salt")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == hashed
