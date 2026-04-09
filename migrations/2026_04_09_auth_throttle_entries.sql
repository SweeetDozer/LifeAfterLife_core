BEGIN;

CREATE TABLE IF NOT EXISTS auth_throttle_entries (
    id SERIAL PRIMARY KEY,
    throttle_key_type VARCHAR(64) NOT NULL,
    throttle_key_value VARCHAR(320) NOT NULL,
    attempt_count INTEGER NOT NULL,
    window_started_at TIMESTAMP NOT NULL,
    last_attempt_at TIMESTAMP NOT NULL,
    locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE auth_throttle_entries
    ALTER COLUMN throttle_key_type SET NOT NULL,
    ALTER COLUMN throttle_key_value SET NOT NULL,
    ALTER COLUMN attempt_count SET NOT NULL,
    ALTER COLUMN window_started_at SET NOT NULL,
    ALTER COLUMN last_attempt_at SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_auth_throttle_entries_key'
    ) THEN
        ALTER TABLE auth_throttle_entries
            ADD CONSTRAINT uq_auth_throttle_entries_key
            UNIQUE (throttle_key_type, throttle_key_value);
    END IF;
END $$;

ALTER TABLE auth_throttle_entries
    DROP CONSTRAINT IF EXISTS ck_auth_throttle_entries_attempt_count;

ALTER TABLE auth_throttle_entries
    ADD CONSTRAINT ck_auth_throttle_entries_attempt_count
    CHECK (attempt_count > 0);

CREATE INDEX IF NOT EXISTS idx_auth_throttle_entries_locked_until
    ON auth_throttle_entries (locked_until);

COMMIT;
