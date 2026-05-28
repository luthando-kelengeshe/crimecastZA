"""Database connection pool for the API."""

import os
import sys

import psycopg2
from psycopg2 import pool

_pool: pool.SimpleConnectionPool | None = None


def get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
        missing = [v for v in required if not os.environ.get(v)]
        if missing:
            print(f"Missing env vars: {missing}", file=sys.stderr)
            sys.exit(1)
        _pool = pool.SimpleConnectionPool(
            minconn=2,
            maxconn=10,
            host=os.environ["DB_HOST"],
            port=int(os.environ["DB_PORT"]),
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
        )
    return _pool


def get_conn():
    """Get a connection from the pool."""
    return get_pool().getconn()


def put_conn(conn):
    """Return a connection to the pool."""
    get_pool().putconn(conn)
