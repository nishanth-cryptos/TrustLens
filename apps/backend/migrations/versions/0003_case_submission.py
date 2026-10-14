"""S2 cases, submissions and durable API idempotency (DATA-001-WP2 + P6-WP6-ADD-001).

Revision: 0003_case_submission
Contract reference and change class: contracts/postgresql/schema-v1.json tables retention_policy_reference, case_record,
case_access_grant, submission and api_idempotency_record. Columns, nullability, primary/foreign keys (RESTRICT), unique
constraints (incl. partial), named CHECKs, vocabulary CHECKs and indexes are generated from the contract. Triggers
implement the declared mutable/write-once columns and transition guards. Change class: ADDITIVE.
Evidence tables are deliberately NOT created: evidence intake awaits the governed DATA-001-WP2 upload-intent revision.
Reference data: one retention_policy_reference row with policy_status UNRESOLVED_OI05 (no duration, no basis; OI-05 open).
"""
from alembic import op

revision = "0003_case_submission"
down_revision = "0002_audit_chain"
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
CREATE TABLE trustlens.retention_policy_reference (
    retention_policy_reference_id uuid NOT NULL,
    retention_class_code text NOT NULL,
    policy_version text NOT NULL,
    policy_status text NOT NULL,
    retention_basis_ref text,
    recorded_at timestamptz NOT NULL,
    CONSTRAINT pk_retention_policy_reference PRIMARY KEY (retention_policy_reference_id),
    CONSTRAINT uq_retention_policy_reference_class_version UNIQUE (retention_class_code, policy_version),
    CONSTRAINT ck_retention_policy_reference_policy_status CHECK (policy_status IN ('UNRESOLVED_OI05', 'GOVERNED')),
    CONSTRAINT ck_retention_policy_unresolved_no_basis CHECK (policy_status <> 'UNRESOLVED_OI05' OR retention_basis_ref IS NULL)
);

CREATE TABLE trustlens.case_record (
    case_record_id uuid NOT NULL,
    owner_principal_id uuid NOT NULL,
    lifecycle_state text NOT NULL,
    is_synthetic boolean NOT NULL,
    created_at timestamptz NOT NULL,
    closed_at timestamptz,
    retention_policy_reference_id uuid NOT NULL,
    mutation_revision bigint NOT NULL,
    CONSTRAINT pk_case_record PRIMARY KEY (case_record_id),
    CONSTRAINT fk_case_record_owner_principal_id FOREIGN KEY (owner_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_case_record_retention_policy_reference_id FOREIGN KEY (retention_policy_reference_id) REFERENCES trustlens.retention_policy_reference (retention_policy_reference_id) ON DELETE RESTRICT,
    CONSTRAINT ck_case_record_lifecycle_state CHECK (lifecycle_state IN ('OPEN', 'UNDER_REVIEW', 'CLOSED', 'DELETION_PENDING', 'DELETED')),
    CONSTRAINT ck_case_record_mutation_revision_positive CHECK (mutation_revision >= 1)
);
CREATE INDEX ix_case_record_owner ON trustlens.case_record (owner_principal_id);

CREATE TABLE trustlens.case_access_grant (
    case_access_grant_id uuid NOT NULL,
    case_record_id uuid NOT NULL,
    principal_reference_id uuid NOT NULL,
    grant_kind text NOT NULL,
    permits_case_metadata boolean NOT NULL,
    permits_evidence_content boolean NOT NULL,
    granted_by_principal_id uuid NOT NULL,
    grant_reason_ref text NOT NULL,
    effective_from timestamptz NOT NULL,
    expires_at timestamptz,
    revoked_at timestamptz,
    revoked_by_principal_id uuid,
    revocation_reason_ref text,
    CONSTRAINT pk_case_access_grant PRIMARY KEY (case_access_grant_id),
    CONSTRAINT fk_case_access_grant_case_record_id FOREIGN KEY (case_record_id) REFERENCES trustlens.case_record (case_record_id) ON DELETE RESTRICT,
    CONSTRAINT fk_case_access_grant_principal_reference_id FOREIGN KEY (principal_reference_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_case_access_grant_granted_by_principal_id FOREIGN KEY (granted_by_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_case_access_grant_revoked_by_principal_id FOREIGN KEY (revoked_by_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT ck_case_access_grant_grant_kind CHECK (grant_kind IN ('OWNER', 'ASSIGNED_ANALYST')),
    CONSTRAINT ck_case_access_grant_owner_metadata CHECK (grant_kind <> 'OWNER' OR permits_case_metadata),
    CONSTRAINT ck_case_access_grant_expiry_order CHECK (expires_at IS NULL OR expires_at > effective_from),
    CONSTRAINT ck_case_access_grant_revocation_complete CHECK ((revoked_at IS NULL) = (revoked_by_principal_id IS NULL))
);
CREATE UNIQUE INDEX uq_case_access_grant_active ON trustlens.case_access_grant (case_record_id, principal_reference_id, grant_kind) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX uq_case_access_grant_single_owner ON trustlens.case_access_grant (case_record_id) WHERE grant_kind = 'OWNER' AND revoked_at IS NULL;
CREATE INDEX ix_case_access_grant_principal_active ON trustlens.case_access_grant (principal_reference_id, case_record_id) WHERE revoked_at IS NULL;
CREATE INDEX ix_case_access_grant_case ON trustlens.case_access_grant (case_record_id);

CREATE TABLE trustlens.submission (
    submission_id uuid NOT NULL,
    case_record_id uuid NOT NULL,
    submitted_by_principal_id uuid NOT NULL,
    received_via text NOT NULL,
    declared_input_type text NOT NULL,
    relationship_to_content text,
    processing_state text NOT NULL,
    is_synthetic boolean NOT NULL,
    received_at timestamptz NOT NULL,
    processed_at timestamptz,
    retention_policy_reference_id uuid NOT NULL,
    CONSTRAINT pk_submission PRIMARY KEY (submission_id),
    CONSTRAINT fk_submission_case_record_id FOREIGN KEY (case_record_id) REFERENCES trustlens.case_record (case_record_id) ON DELETE RESTRICT,
    CONSTRAINT fk_submission_submitted_by_principal_id FOREIGN KEY (submitted_by_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_submission_retention_policy_reference_id FOREIGN KEY (retention_policy_reference_id) REFERENCES trustlens.retention_policy_reference (retention_policy_reference_id) ON DELETE RESTRICT,
    CONSTRAINT ck_submission_received_via CHECK (received_via IN ('USER_SUBMISSION', 'API', 'BATCH_IMPORT', 'TEST_FIXTURE')),
    CONSTRAINT ck_submission_declared_input_type CHECK (declared_input_type IN ('TEXT', 'SMS', 'CHAT_MESSAGE', 'EMAIL', 'URL', 'OCR_TEXT', 'SCREENSHOT_DERIVED_TEXT', 'DOCUMENT_TEXT', 'USER_NARRATIVE')),
    CONSTRAINT ck_submission_relationship_to_content CHECK (relationship_to_content IN ('RECEIVED', 'SENT', 'REPORTING_ON_BEHALF', 'FORWARDED', 'UNKNOWN')),
    CONSTRAINT ck_submission_processing_state CHECK (processing_state IN ('RECEIVING', 'RECEIVED', 'PROCESSING', 'PROCESSED', 'PARTIALLY_FAILED', 'FAILED')),
    CONSTRAINT ck_submission_fixture_synthetic CHECK (received_via <> 'TEST_FIXTURE' OR is_synthetic)
);
CREATE INDEX ix_submission_case ON trustlens.submission (case_record_id);

CREATE TABLE trustlens.api_idempotency_record (
    api_idempotency_record_id uuid NOT NULL,
    principal_reference_id uuid NOT NULL,
    operation_id text NOT NULL,
    target_resource_scope text NOT NULL,
    idempotency_key_digest text NOT NULL,
    request_fingerprint_version text NOT NULL,
    request_semantic_digest text NOT NULL,
    execution_state text NOT NULL,
    claim_token uuid NOT NULL,
    in_progress_lease_until timestamptz,
    outcome_http_status integer,
    outcome_error_code text,
    outcome_resource_kind text,
    outcome_resource_id uuid,
    created_at timestamptz NOT NULL,
    terminal_at timestamptz,
    active_until timestamptz NOT NULL,
    CONSTRAINT pk_api_idempotency_record PRIMARY KEY (api_idempotency_record_id),
    CONSTRAINT fk_api_idempotency_record_principal_reference_id FOREIGN KEY (principal_reference_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT uq_api_idempotency_scope UNIQUE (principal_reference_id, operation_id, target_resource_scope, idempotency_key_digest),
    CONSTRAINT ck_api_idempotency_record_idempotency_key_digest_pattern CHECK (idempotency_key_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_api_idempotency_record_request_semantic_digest_pattern CHECK (request_semantic_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_api_idempotency_record_execution_state CHECK (execution_state IN ('IN_PROGRESS', 'COMPLETED', 'FAILED_TERMINAL', 'RELEASED')),
    CONSTRAINT ck_api_idempotency_state CHECK ((execution_state = 'IN_PROGRESS' AND terminal_at IS NULL AND outcome_http_status IS NULL AND in_progress_lease_until IS NOT NULL) OR (execution_state IN ('COMPLETED','FAILED_TERMINAL','RELEASED') AND terminal_at IS NOT NULL AND outcome_http_status IS NOT NULL AND in_progress_lease_until IS NULL)),
    CONSTRAINT ck_api_idempotency_window CHECK (active_until > created_at),
    CONSTRAINT ck_api_idempotency_http_status CHECK (outcome_http_status IS NULL OR outcome_http_status BETWEEN 100 AND 599)
);
CREATE INDEX ix_api_idempotency_record_active_until ON trustlens.api_idempotency_record (active_until);

-- Shared guard: rows of GOVERNED_DELETION_ONLY tables are removed only by the governed deletion executor.
CREATE FUNCTION trustlens.tg_governed_deletion_only() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF current_user <> 'tl_deletion_executor' THEN
        RAISE EXCEPTION '% rows are removed only by governed deletion', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN OLD;
END;
$$;

-- retention_policy_reference (M-REF, delete NEVER): reference rows never change.
CREATE FUNCTION trustlens.tg_retention_policy_reference_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'retention_policy_reference rows are immutable' USING ERRCODE = 'restrict_violation';
END;
$$;
CREATE TRIGGER tr_retention_policy_reference_immutable BEFORE UPDATE OR DELETE ON trustlens.retention_policy_reference
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_retention_policy_reference_immutable();

-- case_record (M-OPS): mutation_revision starts at 1 and the server advances it by exactly 1 on every update, ignoring any
-- supplied value; owner and identity columns are immutable.
CREATE FUNCTION trustlens.tg_case_record_revision() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.mutation_revision := 1;
        RETURN NEW;
    END IF;
    IF NEW.case_record_id IS DISTINCT FROM OLD.case_record_id OR NEW.owner_principal_id IS DISTINCT FROM OLD.owner_principal_id
       OR NEW.is_synthetic IS DISTINCT FROM OLD.is_synthetic OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.retention_policy_reference_id IS DISTINCT FROM OLD.retention_policy_reference_id THEN
        RAISE EXCEPTION 'case_record column is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    NEW.mutation_revision := OLD.mutation_revision + 1;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_case_record_revision BEFORE INSERT OR UPDATE ON trustlens.case_record
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_case_record_revision();
CREATE TRIGGER tr_case_record_governed_deletion BEFORE DELETE ON trustlens.case_record
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- case_access_grant (M-APP): only the write-once revocation columns may change (NULL -> value).
CREATE FUNCTION trustlens.tg_case_access_grant_write_once() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.case_access_grant_id IS DISTINCT FROM OLD.case_access_grant_id OR NEW.case_record_id IS DISTINCT FROM OLD.case_record_id
       OR NEW.principal_reference_id IS DISTINCT FROM OLD.principal_reference_id OR NEW.grant_kind IS DISTINCT FROM OLD.grant_kind
       OR NEW.permits_case_metadata IS DISTINCT FROM OLD.permits_case_metadata
       OR NEW.permits_evidence_content IS DISTINCT FROM OLD.permits_evidence_content
       OR NEW.granted_by_principal_id IS DISTINCT FROM OLD.granted_by_principal_id
       OR NEW.grant_reason_ref IS DISTINCT FROM OLD.grant_reason_ref OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
       OR NEW.expires_at IS DISTINCT FROM OLD.expires_at THEN
        RAISE EXCEPTION 'case_access_grant column is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at)
       OR (OLD.revoked_by_principal_id IS NOT NULL AND NEW.revoked_by_principal_id IS DISTINCT FROM OLD.revoked_by_principal_id)
       OR (OLD.revocation_reason_ref IS NOT NULL AND NEW.revocation_reason_ref IS DISTINCT FROM OLD.revocation_reason_ref) THEN
        RAISE EXCEPTION 'case_access_grant revocation is write-once' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_case_access_grant_write_once BEFORE UPDATE ON trustlens.case_access_grant
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_case_access_grant_write_once();
CREATE TRIGGER tr_case_access_grant_governed_deletion BEFORE DELETE ON trustlens.case_access_grant
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- case_access_grant transition guards (constraint triggers): an OWNER grant names the case owner; an ASSIGNED_ANALYST
-- grantee holds an active ANALYST role.
CREATE FUNCTION trustlens.tg_case_access_grant_rules() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.grant_kind = 'OWNER' AND NOT EXISTS (
           SELECT 1 FROM trustlens.case_record c
            WHERE c.case_record_id = NEW.case_record_id AND c.owner_principal_id = NEW.principal_reference_id) THEN
        RAISE EXCEPTION 'OWNER grant must name the case owner' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.grant_kind = 'ASSIGNED_ANALYST' AND NOT EXISTS (
           SELECT 1 FROM trustlens.role_assignment r
            WHERE r.principal_reference_id = NEW.principal_reference_id AND r.role = 'ANALYST' AND r.revoked_at IS NULL) THEN
        RAISE EXCEPTION 'ASSIGNED_ANALYST grantee must hold an active ANALYST role' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER tr_case_access_grant_rules AFTER INSERT OR UPDATE ON trustlens.case_access_grant
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_case_access_grant_rules();

-- submission (M-OPS): only processing_state and processed_at change.
CREATE FUNCTION trustlens.tg_submission_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.submission_id IS DISTINCT FROM OLD.submission_id OR NEW.case_record_id IS DISTINCT FROM OLD.case_record_id
       OR NEW.submitted_by_principal_id IS DISTINCT FROM OLD.submitted_by_principal_id OR NEW.received_via IS DISTINCT FROM OLD.received_via
       OR NEW.declared_input_type IS DISTINCT FROM OLD.declared_input_type
       OR NEW.relationship_to_content IS DISTINCT FROM OLD.relationship_to_content OR NEW.is_synthetic IS DISTINCT FROM OLD.is_synthetic
       OR NEW.received_at IS DISTINCT FROM OLD.received_at
       OR NEW.retention_policy_reference_id IS DISTINCT FROM OLD.retention_policy_reference_id THEN
        RAISE EXCEPTION 'submission column is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_submission_immutable BEFORE UPDATE ON trustlens.submission
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_submission_immutable();
CREATE TRIGGER tr_submission_governed_deletion BEFORE DELETE ON trustlens.submission
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- api_idempotency_record (M-OPS): scope, fingerprint and window columns are write-once at claim.
CREATE FUNCTION trustlens.tg_api_idempotency_record_write_once() RETURNS trigger
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
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_api_idempotency_record_write_once BEFORE UPDATE ON trustlens.api_idempotency_record
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_api_idempotency_record_write_once();
CREATE TRIGGER tr_api_idempotency_record_governed_deletion BEFORE DELETE ON trustlens.api_idempotency_record
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- Reference data: retention is undecided (OI-05); one honest unresolved reference, no duration, no basis.
INSERT INTO trustlens.retention_policy_reference
    (retention_policy_reference_id, retention_class_code, policy_version, policy_status, retention_basis_ref, recorded_at)
VALUES (gen_random_uuid(), 'UNRESOLVED_OI05_DEFAULT', '0', 'UNRESOLVED_OI05', NULL, now());

-- Least privilege (DATA-001-WP2 database_roles): SELECT/INSERT on OPS tables; column UPDATE only on declared
-- mutable/write-once columns; no DELETE, no DDL; nothing to PUBLIC.
REVOKE ALL ON trustlens.retention_policy_reference, trustlens.case_record, trustlens.case_access_grant, trustlens.submission,
    trustlens.api_idempotency_record FROM PUBLIC;
REVOKE ALL ON FUNCTION trustlens.tg_governed_deletion_only(), trustlens.tg_retention_policy_reference_immutable(),
    trustlens.tg_case_record_revision(), trustlens.tg_case_access_grant_write_once(), trustlens.tg_case_access_grant_rules(),
    trustlens.tg_submission_immutable(), trustlens.tg_api_idempotency_record_write_once() FROM PUBLIC;
GRANT SELECT, INSERT ON trustlens.retention_policy_reference, trustlens.case_record, trustlens.case_access_grant,
    trustlens.submission, trustlens.api_idempotency_record TO tl_app_runtime;
GRANT UPDATE (lifecycle_state, closed_at, mutation_revision) ON trustlens.case_record TO tl_app_runtime;
GRANT UPDATE (revoked_at, revoked_by_principal_id, revocation_reason_ref) ON trustlens.case_access_grant TO tl_app_runtime;
GRANT UPDATE (processing_state, processed_at) ON trustlens.submission TO tl_app_runtime;
GRANT UPDATE (execution_state, claim_token, in_progress_lease_until, outcome_http_status, outcome_error_code,
    outcome_resource_kind, outcome_resource_id, terminal_at) ON trustlens.api_idempotency_record TO tl_app_runtime;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    raise NotImplementedError("Downgrade requires separate review of lossless rollback")
