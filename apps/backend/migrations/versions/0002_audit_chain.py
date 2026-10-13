"""S2 governed audit chain (DATA-001-WP2 audit_chain_head, audit_event; §15; ADR-0010 §9; ARCH-004 §9.2).

Revision: 0002_audit_chain
Contract reference and change class: contracts/postgresql/schema-v1.json tables audit_chain_head and audit_event
(columns, CHECKs incl. genesis, unique chain_sequence/event_hash, partial indexes, append-only transition guards) and
database_roles tl_app_runtime AUD privileges. Change class: ADDITIVE.
Interpretation flagged for review: appending requires reading the head, so tl_app_runtime gets column-level SELECT on
audit_chain_head(chain_id, last_chain_sequence, last_event_hash) beside the contract's narrow column UPDATE.
One chain per deployment (DATA-001-WP2 §4 tenancy note): the genesis head 'deployment' is created here, because the
application role has no INSERT on audit_chain_head.
"""
from alembic import op

revision = "0002_audit_chain"
down_revision = "0001_principal_role"
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
CREATE TABLE trustlens.audit_chain_head (
    audit_chain_head_id uuid NOT NULL,
    chain_id text NOT NULL,
    last_chain_sequence bigint NOT NULL,
    last_event_hash text NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT pk_audit_chain_head PRIMARY KEY (audit_chain_head_id),
    CONSTRAINT uq_audit_chain_head_chain UNIQUE (chain_id),
    CONSTRAINT ck_audit_chain_head_last_event_hash CHECK (last_event_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_audit_chain_head_sequence CHECK (last_chain_sequence >= 0)
);

CREATE TABLE trustlens.audit_event (
    audit_event_id uuid NOT NULL,
    chain_id text NOT NULL,
    chain_sequence bigint NOT NULL,
    event_schema_version text NOT NULL,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    actor_principal_id uuid,
    actor_kind text NOT NULL,
    outcome text NOT NULL,
    target_kind text NOT NULL,
    target_id uuid,
    case_record_id uuid,
    evaluation_id uuid,
    evidence_item_id uuid,
    bundle_content_digest text,
    correlation_id text NOT NULL,
    safe_metadata jsonb,
    previous_event_hash text NOT NULL,
    event_hash text NOT NULL,
    CONSTRAINT pk_audit_event PRIMARY KEY (audit_event_id),
    CONSTRAINT uq_audit_event_chain_sequence UNIQUE (chain_id, chain_sequence),
    CONSTRAINT uq_audit_event_hash UNIQUE (event_hash),
    CONSTRAINT ck_audit_event_sequence_positive CHECK (chain_sequence >= 1),
    CONSTRAINT ck_audit_event_genesis CHECK ((chain_sequence = 1) = (previous_event_hash = repeat('0', 64))),
    CONSTRAINT ck_audit_event_event_type CHECK (event_type IN (
        'AUTHENTICATION_SUCCEEDED', 'AUTHENTICATION_FAILED', 'AUTHORIZATION_DENIED', 'ROLE_ASSIGNED',
        'ROLE_REVOKED', 'CASE_ACCESS_GRANTED', 'CASE_ACCESS_REVOKED', 'BREAK_GLASS_ACTIVATED',
        'BREAK_GLASS_EXPIRED', 'BREAK_GLASS_REVIEWED', 'SECRET_OR_KEY_ADMINISTERED', 'EGRESS_DENIED',
        'CASE_CREATED', 'CASE_STATE_CHANGED', 'EVIDENCE_ACCESSED', 'EVIDENCE_RECEIVED',
        'EVIDENCE_STORED', 'EVIDENCE_DERIVED', 'EVALUATION_STARTED', 'EVALUATION_COMPLETED',
        'EVALUATION_FAILED', 'AI_ATTEMPTED', 'AI_REJECTED_OR_FAILED', 'RESULT_PERSISTED',
        'USER_CORRECTION', 'ANALYST_ADJUDICATION', 'REPORT_GENERATED', 'REPORT_EXPORTED',
        'REPLAY_EXECUTED', 'DELETION_REQUESTED', 'CONTENT_DELETED', 'RETENTION_ACTION',
        'INTEGRITY_FAILURE', 'KNOWLEDGE_PUBLISHED', 'KNOWLEDGE_DISTRIBUTED', 'KNOWLEDGE_ACTIVATED',
        'KNOWLEDGE_ROLLED_BACK', 'KNOWLEDGE_WITHDRAWN', 'KNOWLEDGE_ACTIVATION_REJECTED',
        'ACTIVE_BUNDLE_WITHDRAWN_REMEDIATED', 'RESTORE_REQUESTED', 'RESTORE_AUTHORIZED',
        'RESTORE_STARTED', 'RESTORE_VERIFIED', 'RESTORE_PROMOTED_OR_REJECTED',
        'CHECKPOINT_SIGNING_TERMINAL_FAILURE', 'ENRICHMENT_REQUESTED', 'PROVIDER_POLICY_SELECTED',
        'ENRICHMENT_ACCEPTED', 'CREDENTIAL_REFERENCE_FAILURE', 'PROVIDER_POLICY_PUBLISHED',
        'PROVIDER_POLICY_ACTIVATED', 'PROVIDER_POLICY_WITHDRAWN', 'AUDIT_LOG_ACCESSED')),
    CONSTRAINT ck_audit_event_actor_kind CHECK (actor_kind IN ('HUMAN', 'WORKLOAD', 'SYSTEM')),
    CONSTRAINT ck_audit_event_outcome CHECK (outcome IN ('SUCCEEDED', 'FAILED', 'DENIED', 'REJECTED')),
    CONSTRAINT ck_audit_event_target_kind CHECK (target_kind IN (
        'PRINCIPAL', 'ROLE_ASSIGNMENT', 'CASE_ACCESS_GRANT', 'BREAK_GLASS_GRANT', 'CASE', 'SUBMISSION',
        'EVIDENCE_ITEM', 'EVIDENCE_DERIVATIVE', 'EVALUATION', 'DETECTION_RESULT', 'ADJUDICATION',
        'REPORT', 'REPLAY', 'KNOWLEDGE_BUNDLE', 'DELETION_REQUEST', 'DELETION_ACTION',
        'AUDIT_CHECKPOINT', 'RESTORE', 'OTHER', 'EXTERNAL_ENRICHMENT', 'PROVIDER_POLICY', 'AUDIT_LOG')),
    CONSTRAINT ck_audit_event_bundle_content_digest CHECK (bundle_content_digest IS NULL OR bundle_content_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_audit_event_previous_event_hash CHECK (previous_event_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_audit_event_event_hash CHECK (event_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_audit_event_safe_metadata_object CHECK (safe_metadata IS NULL OR jsonb_typeof(safe_metadata) = 'object')
);

CREATE INDEX ix_audit_event_case ON trustlens.audit_event (case_record_id, occurred_at) WHERE case_record_id IS NOT NULL;
CREATE INDEX ix_audit_event_target ON trustlens.audit_event (target_kind, target_id) WHERE target_id IS NOT NULL;

-- audit_event: append-only for every role (contract transition guard: BEFORE UPDATE OR DELETE raises unconditionally).
CREATE FUNCTION trustlens.tg_audit_event_append_only() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'audit_event is append-only' USING ERRCODE = 'restrict_violation';
END;
$$;
CREATE TRIGGER tr_audit_event_append_only
    BEFORE UPDATE OR DELETE ON trustlens.audit_event
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_audit_event_append_only();
CREATE TRIGGER tr_audit_event_no_truncate
    BEFORE TRUNCATE ON trustlens.audit_event
    FOR EACH STATEMENT EXECUTE FUNCTION trustlens.tg_audit_event_append_only();

-- audit_event: an append must extend the locked head exactly (sequence + 1, previous hash = head hash).
CREATE FUNCTION trustlens.tg_audit_event_links_head() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    head_sequence bigint;
    head_hash text;
BEGIN
    SELECT last_chain_sequence, last_event_hash INTO head_sequence, head_hash
      FROM trustlens.audit_chain_head WHERE chain_id = NEW.chain_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown audit chain' USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF NEW.chain_sequence <> head_sequence + 1 OR NEW.previous_event_hash <> head_hash THEN
        RAISE EXCEPTION 'audit append does not extend the chain head' USING ERRCODE = 'serialization_failure';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_audit_event_links_head
    BEFORE INSERT ON trustlens.audit_event
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_audit_event_links_head();

-- audit_chain_head (M-OPS, delete NEVER): never deleted; identity immutable; it may only advance by one, to an event
-- that already exists in the same transaction.
CREATE FUNCTION trustlens.tg_audit_chain_head_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'audit_chain_head rows are never deleted' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.audit_chain_head_id IS DISTINCT FROM OLD.audit_chain_head_id OR NEW.chain_id IS DISTINCT FROM OLD.chain_id THEN
        RAISE EXCEPTION 'audit_chain_head identity is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.last_chain_sequence <> OLD.last_chain_sequence + 1 OR NOT EXISTS (
           SELECT 1 FROM trustlens.audit_event e
            WHERE e.chain_id = NEW.chain_id AND e.chain_sequence = NEW.last_chain_sequence
              AND e.event_hash = NEW.last_event_hash AND e.previous_event_hash = OLD.last_event_hash) THEN
        RAISE EXCEPTION 'audit_chain_head may only advance to the appended event' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_audit_chain_head_guard
    BEFORE UPDATE OR DELETE ON trustlens.audit_chain_head
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_audit_chain_head_guard();
CREATE TRIGGER tr_audit_chain_head_no_truncate
    BEFORE TRUNCATE ON trustlens.audit_chain_head
    FOR EACH STATEMENT EXECUTE FUNCTION trustlens.tg_audit_event_append_only();

-- Genesis head for the single deployment chain (sequence 0, 64 zeros); gen_random_uuid() is CSPRNG-backed.
INSERT INTO trustlens.audit_chain_head (audit_chain_head_id, chain_id, last_chain_sequence, last_event_hash, updated_at)
VALUES (gen_random_uuid(), 'deployment', 0, repeat('0', 64), now());

-- Least privilege: INSERT/SELECT on audit_event only; the narrow head UPDATE plus the column reads it needs; nothing
-- else, nothing to PUBLIC.
REVOKE ALL ON trustlens.audit_event, trustlens.audit_chain_head FROM PUBLIC;
REVOKE ALL ON FUNCTION trustlens.tg_audit_event_append_only(), trustlens.tg_audit_event_links_head(),
    trustlens.tg_audit_chain_head_guard() FROM PUBLIC;
GRANT SELECT, INSERT ON trustlens.audit_event TO tl_app_runtime;
GRANT SELECT (chain_id, last_chain_sequence, last_event_hash) ON trustlens.audit_chain_head TO tl_app_runtime;
GRANT UPDATE (last_chain_sequence, last_event_hash, updated_at) ON trustlens.audit_chain_head TO tl_app_runtime;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    raise NotImplementedError("Audit history is never deleted; no downgrade")
