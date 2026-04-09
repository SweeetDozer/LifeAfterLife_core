BEGIN;

CREATE TABLE IF NOT EXISTS user_refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_id VARCHAR(128) NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    revoked_at TIMESTAMP,
    replaced_by_token_id VARCHAR(128)
);

ALTER TABLE user_refresh_tokens
    ALTER COLUMN user_id SET NOT NULL,
    ALTER COLUMN token_id SET NOT NULL,
    ALTER COLUMN token_hash SET NOT NULL,
    ALTER COLUMN expires_at SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_user_refresh_tokens_token_id'
    ) THEN
        ALTER TABLE user_refresh_tokens
            ADD CONSTRAINT uq_user_refresh_tokens_token_id UNIQUE (token_id);
    END IF;
END $$;

ALTER TABLE user_refresh_tokens
    DROP CONSTRAINT IF EXISTS user_refresh_tokens_user_id_fkey,
    DROP CONSTRAINT IF EXISTS fk_user_refresh_tokens_user;

ALTER TABLE user_refresh_tokens
    ADD CONSTRAINT fk_user_refresh_tokens_user
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_user_refresh_tokens_user_id
    ON user_refresh_tokens (user_id);

CREATE INDEX IF NOT EXISTS idx_user_refresh_tokens_expires_at
    ON user_refresh_tokens (expires_at);

COMMIT;
