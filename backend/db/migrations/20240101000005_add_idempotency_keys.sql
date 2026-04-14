-- migrate:up
CREATE TABLE idempotency_keys (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idempotency_key TEXT        NOT NULL,
    response_body   TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, idempotency_key)
);

CREATE INDEX idx_idempotency_keys_user_key ON idempotency_keys (user_id, idempotency_key);

-- migrate:down
DROP TABLE IF EXISTS idempotency_keys;
