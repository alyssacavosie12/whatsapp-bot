CREATE TABLE IF NOT EXISTS inbox_messages (
    id BIGSERIAL PRIMARY KEY,
    whatsapp_message_id TEXT UNIQUE,
    direction TEXT NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
    sender_phone TEXT NOT NULL DEFAULT '',
    sender_phone_masked TEXT NOT NULL DEFAULT '',
    sender_phone_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    sender_phone_hash TEXT NOT NULL DEFAULT '',
    sender_name TEXT NOT NULL DEFAULT '',
    sender_name_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    sender_name_hash TEXT NOT NULL DEFAULT '',
    message_type TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    body_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    body_length INTEGER NOT NULL DEFAULT 0,
    body_sha256 TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    deleted_by TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS inbox_messages_created_idx
    ON inbox_messages (created_at DESC);

CREATE INDEX IF NOT EXISTS inbox_messages_sender_phone_idx
    ON inbox_messages (sender_phone);

CREATE INDEX IF NOT EXISTS inbox_messages_sender_phone_hash_idx
    ON inbox_messages (sender_phone_hash);

CREATE INDEX IF NOT EXISTS inbox_messages_sender_name_hash_idx
    ON inbox_messages (sender_name_hash);

CREATE TABLE IF NOT EXISTS inbox_audit_events (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    target_message_id BIGINT,
    ip_address TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inbox_audit_created_idx
    ON inbox_audit_events (created_at DESC);

CREATE TABLE IF NOT EXISTS inbox_opt_in_proofs (
    id BIGSERIAL PRIMARY KEY,
    whatsapp_message_id TEXT UNIQUE,
    sender_phone TEXT NOT NULL DEFAULT '',
    sender_phone_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    sender_phone_hash TEXT NOT NULL DEFAULT '',
    proof_type TEXT NOT NULL DEFAULT '',
    proof_source TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    evidence_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_sha256 TEXT NOT NULL DEFAULT '',
    proof_hmac TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inbox_opt_in_proofs_created_idx
    ON inbox_opt_in_proofs (created_at DESC);

CREATE INDEX IF NOT EXISTS inbox_opt_in_proofs_sender_phone_hash_idx
    ON inbox_opt_in_proofs (sender_phone_hash);

CREATE TABLE IF NOT EXISTS inbox_opt_outs (
    id BIGSERIAL PRIMARY KEY,
    sender_phone_hash TEXT NOT NULL UNIQUE,
    sender_phone TEXT NOT NULL DEFAULT '',
    sender_phone_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
    source TEXT NOT NULL DEFAULT '',
    keyword_used TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    evidence_hmac TEXT NOT NULL DEFAULT '',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS inbox_opt_outs_recorded_idx
    ON inbox_opt_outs (recorded_at DESC);
