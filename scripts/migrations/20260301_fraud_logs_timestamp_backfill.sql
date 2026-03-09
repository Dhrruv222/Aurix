-- Aurix AI Service MVP migration (follow-up)
-- Backfills fraud_logs.timestamp from timestamp_raw for common legacy formats.
-- Safe to re-run; only updates rows where timestamp is NULL.

BEGIN;

CREATE OR REPLACE FUNCTION _aurix_parse_common_timestamptz(value text)
RETURNS TIMESTAMPTZ
LANGUAGE plpgsql
AS $$
DECLARE
    parsed_ts TIMESTAMPTZ;
BEGIN
    IF value IS NULL OR btrim(value) = '' THEN
        RETURN NULL;
    END IF;

    -- Attempt 1: native PostgreSQL cast (handles ISO-8601 variants)
    BEGIN
        parsed_ts := value::timestamptz;
        RETURN parsed_ts;
    EXCEPTION WHEN others THEN
        NULL;
    END;

    -- Attempt 2: unix epoch seconds (10 digits)
    BEGIN
        IF value ~ '^\d{10}$' THEN
            parsed_ts := to_timestamp(value::double precision);
            RETURN parsed_ts;
        END IF;
    EXCEPTION WHEN others THEN
        NULL;
    END;

    -- Attempt 3: unix epoch milliseconds (13 digits)
    BEGIN
        IF value ~ '^\d{13}$' THEN
            parsed_ts := to_timestamp((value::double precision) / 1000.0);
            RETURN parsed_ts;
        END IF;
    EXCEPTION WHEN others THEN
        NULL;
    END;

    -- Attempt 4: "YYYY-MM-DD HH24:MI:SS" (assume UTC)
    BEGIN
        IF value ~ '^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$' THEN
            parsed_ts := to_timestamp(replace(value, 'T', ' '), 'YYYY-MM-DD HH24:MI:SS') AT TIME ZONE 'UTC';
            RETURN parsed_ts;
        END IF;
    EXCEPTION WHEN others THEN
        NULL;
    END;

    -- Attempt 5: "YYYY/MM/DD HH24:MI:SS" (assume UTC)
    BEGIN
        IF value ~ '^\d{4}/\d{2}/\d{2}[ T]\d{2}:\d{2}:\d{2}$' THEN
            parsed_ts := to_timestamp(replace(value, 'T', ' '), 'YYYY/MM/DD HH24:MI:SS') AT TIME ZONE 'UTC';
            RETURN parsed_ts;
        END IF;
    EXCEPTION WHEN others THEN
        NULL;
    END;

    -- Attempt 6: "DD-MM-YYYY HH24:MI:SS" (assume UTC)
    BEGIN
        IF value ~ '^\d{2}-\d{2}-\d{4}[ T]\d{2}:\d{2}:\d{2}$' THEN
            parsed_ts := to_timestamp(replace(value, 'T', ' '), 'DD-MM-YYYY HH24:MI:SS') AT TIME ZONE 'UTC';
            RETURN parsed_ts;
        END IF;
    EXCEPTION WHEN others THEN
        NULL;
    END;

    RETURN NULL;
END;
$$;

UPDATE fraud_logs
SET timestamp = _aurix_parse_common_timestamptz(timestamp_raw)
WHERE timestamp IS NULL
  AND timestamp_raw IS NOT NULL;

DROP FUNCTION IF EXISTS _aurix_parse_common_timestamptz(text);

COMMIT;
