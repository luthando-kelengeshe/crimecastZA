-- V3__create_api_user.sql
-- API user table for JWT authentication

CREATE TABLE IF NOT EXISTS api_user (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default admin user (password: admin123 — change in production)
-- Hash generated with: hashlib.sha256("crimecastza-saltadmin123".encode()).hexdigest()
INSERT INTO api_user (username, password_hash, role)
VALUES ('admin', '9af7b249de4cdee0059b9dd48f9befa67c3f6c5783c6597bcab1bce75c4a03e0', 'admin')
ON CONFLICT (username) DO NOTHING;
