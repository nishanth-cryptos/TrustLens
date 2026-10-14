"""S3 governed knowledge seam: knowledge bundle reference, activation history and deployment state (DATA-001-WP2).

Revision: 0005_knowledge_seam
Contract reference and change class: contracts/postgresql/schema-v1.json tables knowledge_bundle_reference (M-REF),
knowledge_activation_record (M-APP) and knowledge_deployment_state (M-OPS), all delete policy NEVER. Columns,
nullability, keys (RESTRICT), unique constraints, named CHECKs, pattern and vocabulary CHECKs and indexes are generated
from the contract. Change class: ADDITIVE (first creation of accepted contract tables; no contract revision).

Privileges (least privilege for the S3 scope): tl_app_runtime may SELECT all three tables; INSERT bundle references and
activation records (activateKnowledgeBundle, DEC-011); and UPDATE only the pointer columns of knowledge_deployment_state.
It cannot change a bundle reference (so it cannot withdraw or re-qualify one), rewrite history or delete anything.
Rollback and withdrawal stay outside S3 (PLAN-001 §6, S9).

Reference data: one knowledge_deployment_state row for deployment 'local-development' in state NO_ACTIVE_BUNDLE (no
bundle pointer). It records the honest initial state; it is not an activation.
"""
from alembic import op

revision = "0005_knowledge_seam"
down_revision = "0004_evidence_intake"
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
CREATE TABLE trustlens.knowledge_bundle_reference (
    knowledge_bundle_reference_id uuid NOT NULL,
    content_digest text NOT NULL,
    bundle_version text NOT NULL,
    manifest_schema_version text NOT NULL,
    commit_sha text,
    component_versions jsonb NOT NULL,
    release_record_ref text,
    governance_eligibility text NOT NULL,
    eligibility_observed_at timestamptz NOT NULL,
    eligibility_source_ref text NOT NULL,
    first_seen_at timestamptz NOT NULL,
    CONSTRAINT pk_knowledge_bundle_reference PRIMARY KEY (knowledge_bundle_reference_id),
    CONSTRAINT uq_knowledge_bundle_reference_digest UNIQUE (content_digest),
    CONSTRAINT ck_knowledge_bundle_reference_content_digest_pattern CHECK (content_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_knowledge_bundle_reference_bundle_version_pattern CHECK (bundle_version ~ '^\d+\.\d+\.\d+$'),
    CONSTRAINT ck_knowledge_bundle_reference_manifest_schema_version CHECK (manifest_schema_version IN ('1.0.0', '1.1.0')),
    CONSTRAINT ck_knowledge_bundle_reference_commit_sha_pattern CHECK (commit_sha IS NULL OR commit_sha ~ '^[0-9a-f]{7,40}$|^unknown$'),
    CONSTRAINT ck_knowledge_bundle_reference_governance_eligibility CHECK (governance_eligibility IN ('ELIGIBLE', 'WITHDRAWN', 'UNKNOWN')),
    CONSTRAINT ck_knowledge_bundle_reference_component_versions_object CHECK (jsonb_typeof(component_versions) = 'object')
);

CREATE TABLE trustlens.knowledge_activation_record (
    knowledge_activation_record_id uuid NOT NULL,
    deployment_ref text NOT NULL,
    bundle_content_digest text NOT NULL,
    previous_bundle_content_digest text,
    action_kind text NOT NULL,
    lifecycle_state text NOT NULL,
    validation_outcome text NOT NULL,
    authenticity_outcome text NOT NULL,
    actor_principal_id uuid NOT NULL,
    reason_ref text NOT NULL,
    outcome text NOT NULL,
    recorded_at timestamptz NOT NULL,
    CONSTRAINT pk_knowledge_activation_record PRIMARY KEY (knowledge_activation_record_id),
    CONSTRAINT fk_knowledge_activation_record_bundle_content_digest FOREIGN KEY (bundle_content_digest) REFERENCES trustlens.knowledge_bundle_reference (content_digest) ON DELETE RESTRICT,
    CONSTRAINT fk_knowledge_activation_record_previous_bundle_content_digest FOREIGN KEY (previous_bundle_content_digest) REFERENCES trustlens.knowledge_bundle_reference (content_digest) ON DELETE RESTRICT,
    CONSTRAINT fk_knowledge_activation_record_actor_principal_id FOREIGN KEY (actor_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT ck_knowledge_activation_record_bundle_content_digest_pattern CHECK (bundle_content_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_knowledge_activation_record_previous_bundle_content_digest_pattern CHECK (previous_bundle_content_digest IS NULL OR previous_bundle_content_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_knowledge_activation_record_action_kind CHECK (action_kind IN ('ACTIVATION', 'ROLLBACK', 'WITHDRAWAL_REMEDIATION', 'REJECTED_ACTIVATION')),
    CONSTRAINT ck_knowledge_activation_record_lifecycle_state CHECK (lifecycle_state IN ('PUBLISHED', 'DISTRIBUTED', 'VALIDATED', 'ACTIVE', 'REJECTED', 'ACTIVE_BUNDLE_WITHDRAWN')),
    CONSTRAINT ck_knowledge_activation_record_validation_outcome CHECK (validation_outcome IN ('PASSED', 'FAILED', 'NOT_PERFORMED')),
    CONSTRAINT ck_knowledge_activation_record_authenticity_outcome CHECK (authenticity_outcome IN ('VERIFIED', 'FAILED', 'NOT_REQUIRED_BY_POLICY', 'NOT_PERFORMED')),
    CONSTRAINT ck_knowledge_activation_record_outcome CHECK (outcome IN ('SUCCEEDED', 'FAILED')),
    CONSTRAINT ck_knowledge_activation_active_validated CHECK (lifecycle_state <> 'ACTIVE' OR (validation_outcome = 'PASSED' AND authenticity_outcome IN ('VERIFIED','NOT_REQUIRED_BY_POLICY')))
);
CREATE INDEX ix_knowledge_activation_record_deployment ON trustlens.knowledge_activation_record (deployment_ref, recorded_at);

CREATE TABLE trustlens.knowledge_deployment_state (
    knowledge_deployment_state_id uuid NOT NULL,
    deployment_ref text NOT NULL,
    current_activation_record_id uuid,
    active_bundle_content_digest text,
    operational_state text NOT NULL,
    state_changed_at timestamptz NOT NULL,
    CONSTRAINT pk_knowledge_deployment_state PRIMARY KEY (knowledge_deployment_state_id),
    CONSTRAINT fk_knowledge_deployment_state_current_activation_record_id FOREIGN KEY (current_activation_record_id) REFERENCES trustlens.knowledge_activation_record (knowledge_activation_record_id) ON DELETE RESTRICT,
    CONSTRAINT fk_knowledge_deployment_state_active_bundle_content_digest FOREIGN KEY (active_bundle_content_digest) REFERENCES trustlens.knowledge_bundle_reference (content_digest) ON DELETE RESTRICT,
    CONSTRAINT uq_knowledge_deployment_state_deployment UNIQUE (deployment_ref),
    CONSTRAINT ck_knowledge_deployment_state_active_bundle_content_digest_pattern CHECK (active_bundle_content_digest IS NULL OR active_bundle_content_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_knowledge_deployment_state_operational_state CHECK (operational_state IN ('NO_ACTIVE_BUNDLE', 'ACTIVE', 'ACTIVE_BUNDLE_WITHDRAWN')),
    CONSTRAINT ck_knowledge_deployment_state_pointer CHECK ((operational_state = 'NO_ACTIVE_BUNDLE') = (active_bundle_content_digest IS NULL))
);

-- knowledge_bundle_reference (M-REF, delete NEVER): the exact bundle identity is immutable once recorded; only the
-- non-authoritative governance-eligibility mirror may change (mutable_columns).
CREATE FUNCTION trustlens.tg_knowledge_bundle_reference_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'knowledge_bundle_reference rows are never deleted' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.knowledge_bundle_reference_id IS DISTINCT FROM OLD.knowledge_bundle_reference_id
       OR NEW.content_digest IS DISTINCT FROM OLD.content_digest OR NEW.bundle_version IS DISTINCT FROM OLD.bundle_version
       OR NEW.manifest_schema_version IS DISTINCT FROM OLD.manifest_schema_version OR NEW.commit_sha IS DISTINCT FROM OLD.commit_sha
       OR NEW.component_versions IS DISTINCT FROM OLD.component_versions OR NEW.release_record_ref IS DISTINCT FROM OLD.release_record_ref
       OR NEW.first_seen_at IS DISTINCT FROM OLD.first_seen_at THEN
        RAISE EXCEPTION 'knowledge_bundle_reference identity is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_knowledge_bundle_reference_guard BEFORE UPDATE OR DELETE ON trustlens.knowledge_bundle_reference
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_knowledge_bundle_reference_guard();

-- knowledge_activation_record (M-APP, delete NEVER): append-only history.
CREATE FUNCTION trustlens.tg_knowledge_activation_record_append_only() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'knowledge_activation_record is append-only history' USING ERRCODE = 'restrict_violation';
END;
$$;
CREATE TRIGGER tr_knowledge_activation_record_append_only BEFORE UPDATE OR DELETE ON trustlens.knowledge_activation_record
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_knowledge_activation_record_append_only();

-- knowledge_deployment_state (M-OPS, delete NEVER): identity and deployment_ref immutable; only the pointer columns move.
CREATE FUNCTION trustlens.tg_knowledge_deployment_state_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'knowledge_deployment_state rows are never deleted' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.knowledge_deployment_state_id IS DISTINCT FROM OLD.knowledge_deployment_state_id
       OR NEW.deployment_ref IS DISTINCT FROM OLD.deployment_ref THEN
        RAISE EXCEPTION 'knowledge_deployment_state identity is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_knowledge_deployment_state_guard BEFORE UPDATE OR DELETE ON trustlens.knowledge_deployment_state
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_knowledge_deployment_state_guard();

INSERT INTO trustlens.knowledge_deployment_state (knowledge_deployment_state_id, deployment_ref, current_activation_record_id,
                                                  active_bundle_content_digest, operational_state, state_changed_at)
VALUES (gen_random_uuid(), 'local-development', NULL, NULL, 'NO_ACTIVE_BUNDLE', now());

REVOKE ALL ON trustlens.knowledge_bundle_reference, trustlens.knowledge_activation_record, trustlens.knowledge_deployment_state FROM PUBLIC;
REVOKE ALL ON FUNCTION trustlens.tg_knowledge_bundle_reference_guard(), trustlens.tg_knowledge_activation_record_append_only(),
    trustlens.tg_knowledge_deployment_state_guard() FROM PUBLIC;
GRANT SELECT ON trustlens.knowledge_bundle_reference, trustlens.knowledge_activation_record, trustlens.knowledge_deployment_state
    TO tl_app_runtime;
GRANT INSERT ON trustlens.knowledge_bundle_reference, trustlens.knowledge_activation_record TO tl_app_runtime;
GRANT UPDATE (current_activation_record_id, active_bundle_content_digest, operational_state, state_changed_at)
    ON trustlens.knowledge_deployment_state TO tl_app_runtime;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    raise NotImplementedError("Downgrade requires separate review of lossless rollback")
