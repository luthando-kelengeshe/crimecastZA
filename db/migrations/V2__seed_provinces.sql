-- V2__seed_provinces.sql
-- Seed all nine South African provinces
-- Idempotent: ON CONFLICT DO NOTHING ensures safe re-runs

INSERT INTO province (name) VALUES
    ('Western Cape'),
    ('Eastern Cape'),
    ('Northern Cape'),
    ('Free State'),
    ('KwaZulu-Natal'),
    ('North West'),
    ('Gauteng'),
    ('Mpumalanga'),
    ('Limpopo')
ON CONFLICT (name) DO NOTHING;
