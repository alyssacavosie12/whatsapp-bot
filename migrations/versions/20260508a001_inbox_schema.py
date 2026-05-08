"""Create admin inbox schema (messages, proofs, opt-outs).

Revision purpose:
- Create the Railway Postgres-backed admin inbox tables.
- Be safe to run against an existing deployment (IF NOT EXISTS / IF EXISTS).

This project does not use SQLAlchemy ORM models; migrations execute raw SQL.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260508a001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # inbox_messages
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inbox_messages (
            id BIGSERIAL PRIMARY KEY,
            whatsapp_message_id TEXT UNIQUE,
            direction TEXT NOT NULL
                CHECK (direction IN ('incoming', 'outgoing')),
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
        )
        """
    )
    op.execute(
        """
        ALTER TABLE inbox_messages
            ADD COLUMN IF NOT EXISTS sender_phone_encrypted BOOLEAN
                NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS sender_phone_hash TEXT
                NOT NULL DEFAULT '',
            ADD COLUMN IF NOT EXISTS sender_name_encrypted BOOLEAN
                NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS sender_name_hash TEXT
                NOT NULL DEFAULT ''
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS inbox_messages_created_idx
            ON inbox_messages (created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS inbox_messages_sender_phone_idx
            ON inbox_messages (sender_phone)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS inbox_messages_sender_phone_hash_idx
            ON inbox_messages (sender_phone_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS inbox_messages_sender_name_hash_idx
            ON inbox_messages (sender_name_hash)
        """
    )

    # inbox_audit_events
    op.execute(
        """
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
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS inbox_audit_created_idx
            ON inbox_audit_events (created_at DESC)
        """
    )

    # inbox_opt_in_proofs
    op.execute(
        """
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
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS inbox_opt_in_proofs_created_idx
            ON inbox_opt_in_proofs (created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS inbox_opt_in_proofs_sender_phone_hash_idx
            ON inbox_opt_in_proofs (sender_phone_hash)
        """
    )

    # inbox_opt_outs
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inbox_opt_outs (
            id BIGSERIAL PRIMARY KEY,
            sender_phone_hash TEXT,
            sender_phone TEXT,
            sender_phone_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
            sender_external_id TEXT,
            sender_external_id_type TEXT NOT NULL DEFAULT 'phone',
            sender_external_id_hash TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            keyword_used TEXT,
            language TEXT,
            evidence_hmac TEXT NOT NULL DEFAULT '',
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # Backward-compatible upgrades for older opt-out schemas.
    op.execute(
        """
        ALTER TABLE inbox_opt_outs
            ADD COLUMN IF NOT EXISTS sender_external_id TEXT,
            ADD COLUMN IF NOT EXISTS sender_external_id_type TEXT
                NOT NULL DEFAULT 'phone',
            ADD COLUMN IF NOT EXISTS sender_external_id_hash TEXT
                NOT NULL DEFAULT ''
        """
    )
    op.execute(
        """
        ALTER TABLE inbox_opt_outs
            DROP CONSTRAINT IF EXISTS inbox_opt_outs_sender_phone_hash_key
        """
    )
    op.execute(
        """
        UPDATE inbox_opt_outs
        SET
            sender_external_id = sender_phone,
            sender_external_id_type = 'phone',
            sender_external_id_hash = sender_phone_hash
        WHERE (sender_external_id_hash IS NULL OR sender_external_id_hash = '')
            AND sender_phone_hash IS NOT NULL
            AND sender_phone_hash != ''
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS inbox_opt_outs_external_id_hash_uniq
            ON inbox_opt_outs (sender_external_id_hash)
            WHERE sender_external_id_hash != ''
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS inbox_opt_outs_recorded_idx
            ON inbox_opt_outs (recorded_at DESC)
        """
    )

    # Prefer NULLs over empty strings for optional columns.
    op.execute(
        """
        ALTER TABLE inbox_opt_outs
            ALTER COLUMN sender_phone_hash DROP NOT NULL,
            ALTER COLUMN sender_phone_hash DROP DEFAULT,
            ALTER COLUMN sender_phone DROP NOT NULL,
            ALTER COLUMN sender_phone DROP DEFAULT,
            ALTER COLUMN sender_external_id DROP NOT NULL,
            ALTER COLUMN sender_external_id DROP DEFAULT,
            ALTER COLUMN keyword_used DROP NOT NULL,
            ALTER COLUMN keyword_used DROP DEFAULT,
            ALTER COLUMN language DROP NOT NULL,
            ALTER COLUMN language DROP DEFAULT
        """
    )
    op.execute(
        """
        UPDATE inbox_opt_outs
        SET
            sender_phone_hash = NULLIF(sender_phone_hash, ''),
            sender_phone = NULLIF(sender_phone, ''),
            sender_external_id = NULLIF(sender_external_id, ''),
            keyword_used = NULLIF(keyword_used, ''),
            language = NULLIF(language, '')
        """
    )


def downgrade() -> None:
    # Destructive rollback: drops the inbox tables.
    op.execute("DROP TABLE IF EXISTS inbox_opt_outs")
    op.execute("DROP TABLE IF EXISTS inbox_opt_in_proofs")
    op.execute("DROP TABLE IF EXISTS inbox_audit_events")
    op.execute("DROP TABLE IF EXISTS inbox_messages")
