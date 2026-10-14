"""S2 evidence intake: contract tables evidence_item / cross_store_operation plus CANDIDATE addendum P9-S2-ADD-001.

Revision: 0004_evidence_intake
Contract reference and change class:
- evidence_item, cross_store_operation: contracts/postgresql/schema-v1.json, generated exactly (ADDITIVE: first creation).
- evidence_upload_intent and the api_idempotency_record supersession amendment:
  contracts/postgresql/schema-v1-addendum-p9-s2-add-001.json, status CANDIDATE (sponsor-approved in principle; NOT
  independently reviewed). Do not apply this revision to a persistent database before the addendum is activated.
The amendment replaces the full-scope UNIQUE constraint with a partial unique index (WHERE superseded_at IS NULL): a
relaxation flagged for review, required so a key reused after its active window can start a fresh claim (OPS-001 §5)
without deleting the governed record.
"""
from alembic import op

revision = "0004_evidence_intake"
down_revision = "0003_case_submission"
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
CREATE TABLE trustlens.evidence_item (
    evidence_item_id uuid NOT NULL,
    submission_id uuid NOT NULL,
    artifact_kind text NOT NULL,
    content_sha256 text NOT NULL,
    byte_length bigint NOT NULL,
    byte_definition_version text NOT NULL,
    declared_media_type text NOT NULL,
    verified_media_type text,
    ingested_at timestamptz NOT NULL,
    capture_declared_at timestamptz,
    source_channel_ref text,
    ingesting_component_ref text NOT NULL,
    ingesting_principal_id uuid,
    ecs_locator text,
    data_key_version_ref text,
    content_state text NOT NULL,
    state_changed_at timestamptz NOT NULL,
    verified_at timestamptz,
    finalized_at timestamptz,
    idempotency_key uuid NOT NULL,
    retention_policy_reference_id uuid NOT NULL,
    CONSTRAINT pk_evidence_item PRIMARY KEY (evidence_item_id),
    CONSTRAINT fk_evidence_item_submission_id FOREIGN KEY (submission_id) REFERENCES trustlens.submission (submission_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evidence_item_ingesting_principal_id FOREIGN KEY (ingesting_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evidence_item_retention_policy_reference_id FOREIGN KEY (retention_policy_reference_id) REFERENCES trustlens.retention_policy_reference (retention_policy_reference_id) ON DELETE RESTRICT,
    CONSTRAINT uq_evidence_item_idempotency UNIQUE (idempotency_key),
    CONSTRAINT ck_evidence_item_artifact_kind CHECK (artifact_kind IN ('TEXT_BODY', 'URL', 'EMAIL_SOURCE', 'IMAGE', 'DOCUMENT', 'OTHER')),
    CONSTRAINT ck_evidence_item_content_sha256_pattern CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_evidence_item_content_state CHECK (content_state IN ('RECEIVED', 'CONTENT_PENDING', 'CONTENT_STORED', 'INTEGRITY_VERIFIED', 'FINALIZED', 'FAILED_RETRYABLE', 'FAILED_TERMINAL', 'ORPHAN_DETECTED', 'INTEGRITY_FAILED', 'QUARANTINED', 'DELETION_PENDING', 'DELETED')),
    CONSTRAINT ck_evidence_item_byte_length CHECK (byte_length >= 0),
    CONSTRAINT ck_evidence_item_finalized_requires_verified CHECK ((content_state NOT IN ('CONTENT_STORED','INTEGRITY_VERIFIED','FINALIZED') OR (ecs_locator IS NOT NULL AND content_sha256 IS NOT NULL)) AND (content_state NOT IN ('INTEGRITY_VERIFIED','FINALIZED') OR verified_at IS NOT NULL) AND (content_state <> 'FINALIZED' OR finalized_at IS NOT NULL))
);
CREATE INDEX ix_evidence_item_submission ON trustlens.evidence_item (submission_id);
CREATE INDEX ix_evidence_item_incomplete ON trustlens.evidence_item (content_state, state_changed_at) WHERE content_state NOT IN ('FINALIZED','DELETED');

CREATE TABLE trustlens.cross_store_operation (
    cross_store_operation_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    operation_kind text NOT NULL,
    owner_module text NOT NULL,
    target_table text,
    target_id uuid,
    ecs_object_ref text,
    expected_sha256 text,
    state text NOT NULL,
    attempt_count integer NOT NULL,
    last_failure_category text,
    next_attempt_not_before timestamptz,
    created_at timestamptz NOT NULL,
    state_changed_at timestamptz NOT NULL,
    terminal_at timestamptz,
    CONSTRAINT pk_cross_store_operation PRIMARY KEY (cross_store_operation_id),
    CONSTRAINT uq_cross_store_operation_idempotency UNIQUE (operation_kind, idempotency_key),
    CONSTRAINT ck_cross_store_operation_operation_kind CHECK (operation_kind IN ('EVIDENCE_INGEST', 'DERIVATIVE_CREATE', 'ENVELOPE_STORE', 'ARTIFACT_EXTERNALIZE', 'REPORT_GENERATE', 'DELETION_EXECUTE', 'ORPHAN_RECONCILIATION')),
    CONSTRAINT ck_cross_store_operation_owner_module CHECK (owner_module IN ('EVIDENCE', 'GOVERNED_EVALUATION', 'REPORTING', 'PRIVACY_LIFECYCLE')),
    CONSTRAINT ck_cross_store_operation_expected_sha256_pattern CHECK (expected_sha256 IS NULL OR expected_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_cross_store_operation_state CHECK (state IN ('RECEIVED', 'CONTENT_PENDING', 'CONTENT_STORED', 'INTEGRITY_VERIFIED', 'FINALIZED', 'FAILED_RETRYABLE', 'FAILED_TERMINAL', 'ORPHAN_DETECTED', 'INTEGRITY_FAILED', 'QUARANTINED', 'DELETION_PENDING', 'DELETED')),
    CONSTRAINT ck_cross_store_operation_attempts CHECK (attempt_count >= 0),
    CONSTRAINT ck_cross_store_operation_terminal CHECK ((state IN ('FINALIZED','FAILED_TERMINAL','QUARANTINED','DELETED')) = (terminal_at IS NOT NULL))
);
CREATE INDEX ix_cross_store_operation_open ON trustlens.cross_store_operation (owner_module, state, next_attempt_not_before) WHERE state NOT IN ('FINALIZED','FAILED_TERMINAL','QUARANTINED','DELETED');

CREATE TABLE trustlens.evidence_upload_intent (
    evidence_upload_intent_id uuid NOT NULL,
    submission_id uuid NOT NULL,
    initiated_by_principal_id uuid NOT NULL,
    artifact_kind text NOT NULL,
    declared_media_type text NOT NULL,
    declared_byte_length bigint NOT NULL,
    display_filename text,
    capture_declared_at timestamptz,
    client_declared_sha256 text,
    idempotency_key uuid NOT NULL,
    intent_state text NOT NULL,
    last_rejection_category text,
    evidence_item_id uuid,
    created_at timestamptz NOT NULL,
    state_changed_at timestamptz NOT NULL,
    retention_policy_reference_id uuid NOT NULL,
    CONSTRAINT pk_evidence_upload_intent PRIMARY KEY (evidence_upload_intent_id),
    CONSTRAINT fk_evidence_upload_intent_submission_id FOREIGN KEY (submission_id) REFERENCES trustlens.submission (submission_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evidence_upload_intent_initiated_by_principal_id FOREIGN KEY (initiated_by_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evidence_upload_intent_evidence_item_id FOREIGN KEY (evidence_item_id) REFERENCES trustlens.evidence_item (evidence_item_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evidence_upload_intent_retention_policy_reference_id FOREIGN KEY (retention_policy_reference_id) REFERENCES trustlens.retention_policy_reference (retention_policy_reference_id) ON DELETE RESTRICT,
    CONSTRAINT uq_evidence_upload_intent_idempotency UNIQUE (idempotency_key),
    CONSTRAINT uq_evidence_upload_intent_evidence_item UNIQUE (evidence_item_id),
    CONSTRAINT ck_evidence_upload_intent_artifact_kind CHECK (artifact_kind IN ('TEXT_BODY', 'URL', 'EMAIL_SOURCE', 'IMAGE', 'DOCUMENT', 'OTHER')),
    CONSTRAINT ck_evidence_upload_intent_client_declared_sha256_pattern CHECK (client_declared_sha256 IS NULL OR client_declared_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_evidence_upload_intent_intent_state CHECK (intent_state IN ('OPEN', 'MATERIALIZED')),
    CONSTRAINT ck_evidence_upload_intent_last_rejection_category CHECK (last_rejection_category IS NULL OR last_rejection_category IN ('LENGTH_MISMATCH', 'DIGEST_MISMATCH', 'MEDIA_INVALID', 'SIZE_EXCEEDED')),
    CONSTRAINT ck_evidence_upload_intent_materialized CHECK ((intent_state = 'MATERIALIZED') = (evidence_item_id IS NOT NULL)),
    CONSTRAINT ck_evidence_upload_intent_same_identity CHECK (evidence_item_id IS NULL OR evidence_item_id = evidence_upload_intent_id),
    CONSTRAINT ck_evidence_upload_intent_declared_length CHECK (declared_byte_length >= 0),
    CONSTRAINT ck_evidence_upload_intent_bounded_text CHECK (length(declared_media_type) <= 255 AND (display_filename IS NULL OR length(display_filename) <= 255))
);
CREATE INDEX ix_evidence_upload_intent_submission ON trustlens.evidence_upload_intent (submission_id, created_at);
CREATE INDEX ix_evidence_upload_intent_open ON trustlens.evidence_upload_intent (intent_state, state_changed_at) WHERE intent_state = 'OPEN';

-- evidence_item (M-IMM identity and digest): only content_state/state_changed_at change; ecs_locator, verified_at,
-- finalized_at and verified_media_type are write-once; content_state follows the DATA-001-WP2 §11 state machine.
CREATE FUNCTION trustlens.tg_evidence_item_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.evidence_item_id IS DISTINCT FROM OLD.evidence_item_id OR NEW.submission_id IS DISTINCT FROM OLD.submission_id
       OR NEW.artifact_kind IS DISTINCT FROM OLD.artifact_kind OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256
       OR NEW.byte_length IS DISTINCT FROM OLD.byte_length OR NEW.byte_definition_version IS DISTINCT FROM OLD.byte_definition_version
       OR NEW.declared_media_type IS DISTINCT FROM OLD.declared_media_type OR NEW.ingested_at IS DISTINCT FROM OLD.ingested_at
       OR NEW.capture_declared_at IS DISTINCT FROM OLD.capture_declared_at OR NEW.source_channel_ref IS DISTINCT FROM OLD.source_channel_ref
       OR NEW.ingesting_component_ref IS DISTINCT FROM OLD.ingesting_component_ref
       OR NEW.ingesting_principal_id IS DISTINCT FROM OLD.ingesting_principal_id
       OR NEW.data_key_version_ref IS DISTINCT FROM OLD.data_key_version_ref OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.retention_policy_reference_id IS DISTINCT FROM OLD.retention_policy_reference_id THEN
        RAISE EXCEPTION 'evidence_item identity and digest are immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (OLD.ecs_locator IS NOT NULL AND NEW.ecs_locator IS DISTINCT FROM OLD.ecs_locator)
       OR (OLD.verified_at IS NOT NULL AND NEW.verified_at IS DISTINCT FROM OLD.verified_at)
       OR (OLD.finalized_at IS NOT NULL AND NEW.finalized_at IS DISTINCT FROM OLD.finalized_at)
       OR (OLD.verified_media_type IS NOT NULL AND NEW.verified_media_type IS DISTINCT FROM OLD.verified_media_type) THEN
        RAISE EXCEPTION 'evidence_item write-once column changed' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.content_state <> OLD.content_state AND (OLD.content_state, NEW.content_state) NOT IN (
        ('RECEIVED', 'CONTENT_PENDING'), ('CONTENT_PENDING', 'CONTENT_STORED'), ('CONTENT_PENDING', 'FAILED_RETRYABLE'),
        ('CONTENT_STORED', 'INTEGRITY_VERIFIED'), ('CONTENT_STORED', 'FAILED_RETRYABLE'), ('CONTENT_STORED', 'INTEGRITY_FAILED'),
        ('INTEGRITY_VERIFIED', 'FINALIZED'), ('FAILED_RETRYABLE', 'CONTENT_PENDING'), ('FAILED_RETRYABLE', 'FAILED_TERMINAL'),
        ('FINALIZED', 'INTEGRITY_FAILED'), ('INTEGRITY_FAILED', 'QUARANTINED'), ('ORPHAN_DETECTED', 'QUARANTINED'),
        ('ORPHAN_DETECTED', 'FINALIZED'), ('FINALIZED', 'DELETION_PENDING'), ('DELETION_PENDING', 'DELETED')) THEN
        RAISE EXCEPTION 'evidence_item content_state transition % -> % is not allowed', OLD.content_state, NEW.content_state
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_evidence_item_guard BEFORE UPDATE ON trustlens.evidence_item
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_evidence_item_guard();
CREATE TRIGGER tr_evidence_item_governed_deletion BEFORE DELETE ON trustlens.evidence_item
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- cross_store_operation (M-OPS): identity, kind, target and expected digest are immutable.
CREATE FUNCTION trustlens.tg_cross_store_operation_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.cross_store_operation_id IS DISTINCT FROM OLD.cross_store_operation_id OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.operation_kind IS DISTINCT FROM OLD.operation_kind OR NEW.owner_module IS DISTINCT FROM OLD.owner_module
       OR NEW.target_table IS DISTINCT FROM OLD.target_table OR NEW.target_id IS DISTINCT FROM OLD.target_id
       OR NEW.expected_sha256 IS DISTINCT FROM OLD.expected_sha256 OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'cross_store_operation column is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF OLD.terminal_at IS NOT NULL THEN
        RAISE EXCEPTION 'cross_store_operation is terminal' USING ERRCODE = 'restrict_violation';
    END IF;
    -- attempt_count is the content-write fencing token (P9-S2-ADD-001 §4): it never decreases and grows by one per attempt.
    IF NEW.attempt_count < OLD.attempt_count OR NEW.attempt_count > OLD.attempt_count + 1 THEN
        RAISE EXCEPTION 'cross_store_operation attempt_count must advance by exactly one per attempt' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_cross_store_operation_guard BEFORE UPDATE ON trustlens.cross_store_operation
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_cross_store_operation_guard();
CREATE TRIGGER tr_cross_store_operation_governed_deletion BEFORE DELETE ON trustlens.cross_store_operation
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- evidence_upload_intent (CANDIDATE addendum): declared values immutable; OPEN -> MATERIALIZED only; evidence_item_id
-- write-once.
CREATE FUNCTION trustlens.tg_evidence_upload_intent_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.evidence_upload_intent_id IS DISTINCT FROM OLD.evidence_upload_intent_id OR NEW.submission_id IS DISTINCT FROM OLD.submission_id
       OR NEW.initiated_by_principal_id IS DISTINCT FROM OLD.initiated_by_principal_id OR NEW.artifact_kind IS DISTINCT FROM OLD.artifact_kind
       OR NEW.declared_media_type IS DISTINCT FROM OLD.declared_media_type
       OR NEW.declared_byte_length IS DISTINCT FROM OLD.declared_byte_length OR NEW.display_filename IS DISTINCT FROM OLD.display_filename
       OR NEW.capture_declared_at IS DISTINCT FROM OLD.capture_declared_at
       OR NEW.client_declared_sha256 IS DISTINCT FROM OLD.client_declared_sha256 OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.retention_policy_reference_id IS DISTINCT FROM OLD.retention_policy_reference_id THEN
        RAISE EXCEPTION 'evidence_upload_intent declared values are immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF OLD.evidence_item_id IS NOT NULL AND NEW.evidence_item_id IS DISTINCT FROM OLD.evidence_item_id THEN
        RAISE EXCEPTION 'evidence_upload_intent evidence_item_id is write-once' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.intent_state <> OLD.intent_state AND NOT (OLD.intent_state = 'OPEN' AND NEW.intent_state = 'MATERIALIZED') THEN
        RAISE EXCEPTION 'evidence_upload_intent transition % -> % is not allowed', OLD.intent_state, NEW.intent_state
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_evidence_upload_intent_guard BEFORE UPDATE ON trustlens.evidence_upload_intent
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_evidence_upload_intent_guard();
CREATE TRIGGER tr_evidence_upload_intent_governed_deletion BEFORE DELETE ON trustlens.evidence_upload_intent
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- api_idempotency_record amendment (CANDIDATE): write-once superseded_at, only after active_until; at most one
-- governing record per scope.
ALTER TABLE trustlens.api_idempotency_record ADD COLUMN superseded_at timestamptz;
ALTER TABLE trustlens.api_idempotency_record DROP CONSTRAINT uq_api_idempotency_scope;
CREATE UNIQUE INDEX uq_api_idempotency_scope ON trustlens.api_idempotency_record
    (principal_reference_id, operation_id, target_resource_scope, idempotency_key_digest) WHERE superseded_at IS NULL;
CREATE OR REPLACE FUNCTION trustlens.tg_api_idempotency_record_write_once() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.api_idempotency_record_id IS DISTINCT FROM OLD.api_idempotency_record_id
       OR NEW.principal_reference_id IS DISTINCT FROM OLD.principal_reference_id OR NEW.operation_id IS DISTINCT FROM OLD.operation_id
       OR NEW.target_resource_scope IS DISTINCT FROM OLD.target_resource_scope
       OR NEW.idempotency_key_digest IS DISTINCT FROM OLD.idempotency_key_digest
       OR NEW.request_fingerprint_version IS DISTINCT FROM OLD.request_fingerprint_version
       OR NEW.request_semantic_digest IS DISTINCT FROM OLD.request_semantic_digest
       OR NEW.created_at IS DISTINCT FROM OLD.created_at OR NEW.active_until IS DISTINCT FROM OLD.active_until THEN
        RAISE EXCEPTION 'api_idempotency_record scope is write-once' USING ERRCODE = 'restrict_violation';
    END IF;
    IF OLD.superseded_at IS NOT NULL THEN
        RAISE EXCEPTION 'a superseded api_idempotency_record never changes' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.superseded_at IS NOT NULL AND OLD.active_until > now() THEN
        RAISE EXCEPTION 'api_idempotency_record may be superseded only after active_until' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

REVOKE ALL ON trustlens.evidence_item, trustlens.cross_store_operation, trustlens.evidence_upload_intent FROM PUBLIC;
REVOKE ALL ON FUNCTION trustlens.tg_evidence_item_guard(), trustlens.tg_cross_store_operation_guard(),
    trustlens.tg_evidence_upload_intent_guard() FROM PUBLIC;
GRANT SELECT, INSERT ON trustlens.evidence_item, trustlens.cross_store_operation, trustlens.evidence_upload_intent TO tl_app_runtime;
GRANT UPDATE (intent_state, last_rejection_category, state_changed_at, evidence_item_id) ON trustlens.evidence_upload_intent TO tl_app_runtime;
GRANT UPDATE (content_state, state_changed_at, ecs_locator, verified_at, finalized_at, verified_media_type) ON trustlens.evidence_item TO tl_app_runtime;
GRANT UPDATE (state, attempt_count, last_failure_category, next_attempt_not_before, state_changed_at, terminal_at, ecs_object_ref)
    ON trustlens.cross_store_operation TO tl_app_runtime;
GRANT UPDATE (superseded_at) ON trustlens.api_idempotency_record TO tl_app_runtime;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    raise NotImplementedError("Downgrade requires separate review of lossless rollback")
