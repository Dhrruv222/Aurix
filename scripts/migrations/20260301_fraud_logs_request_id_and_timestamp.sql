-- Aurix AI Service MVP migration
-- Adds request correlation and upgrades fraud_logs.timestamp to timestamptz.

BEGIN;

ALTER TABLE fraud_logs
    ADD COLUMN IF NOT EXISTS request_id VARCHAR(64);

ALTER TABLE fraud_logs
    ADD COLUMN IF NOT EXISTS timestamp_raw TEXT;

UPDATE fraud_logs
SET timestamp_raw = timestamp::text
WHERE timestamp_raw IS NULL;

CREATE OR REPLACE FUNCTION _aurix_safe_timestamptz(value text)
RETURNS TIMESTAMPTZ
LANGUAGE plpgsql
AS $$
BEGIN
    IF value IS NULL OR btrim(value) = '' THEN
        RETURN NULL;
    END IF;
    RETURN value::timestamptz;
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'fraud_logs'
          AND column_name = 'timestamp'
          AND data_type IN ('character varying', 'text')
    ) THEN
        ALTER TABLE fraud_logs
            ALTER COLUMN timestamp TYPE TIMESTAMPTZ
            USING _aurix_safe_timestamptz(timestamp);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fraud_logs_request_id
    ON fraud_logs (request_id);

DROP FUNCTION IF EXISTS _aurix_safe_timestamptz(text);

COMMIT;
