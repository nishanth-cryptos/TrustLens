"""S5 governed evaluation and immutable DetectionResult persistence (DATA-001-WP2 §12, completion protocol).

Revision: 0006_evaluation_result
Contract reference and change class: contracts/postgresql/schema-v1.json tables evidence_derivative, input_envelope_record,
input_envelope_source, evaluation, governed_input_artifact, governed_observation_reference, detection_result and
rule_result_projection. Columns, nullability, primary/foreign keys (RESTRICT, including the (evaluation_id,
execution_fence_token) result-binding key), unique constraints, named CHECKs, vocabulary CHECKs and indexes are generated
from the contract. Triggers implement the declared mutability, write-once columns, transition guards and the
completion_protocol commit invariants. Change class: ADDITIVE. No reference data.
evidence_derivative is created only because input_envelope_source references it (OCR/derivatives are S8); the
application may read it and writes nothing to it.
"""
from alembic import op

revision = "0006_evaluation_result"
down_revision = "0005_knowledge_seam"
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
CREATE TABLE trustlens.evidence_derivative (
    evidence_derivative_id uuid NOT NULL,
    parent_evidence_item_id uuid,
    parent_evidence_derivative_id uuid,
    derivation_kind text NOT NULL,
    transformation_id text NOT NULL,
    transformation_version text NOT NULL,
    producing_component_ref text NOT NULL,
    producing_principal_id uuid,
    derivative_sha256 text,
    byte_length bigint,
    created_at timestamptz NOT NULL,
    ecs_locator text,
    content_state text NOT NULL,
    state_changed_at timestamptz NOT NULL,
    verified_at timestamptz,
    finalized_at timestamptz,
    idempotency_key uuid NOT NULL,
    retention_policy_reference_id uuid NOT NULL,
    CONSTRAINT pk_evidence_derivative PRIMARY KEY (evidence_derivative_id),
    CONSTRAINT fk_evidence_derivative_parent_evidence_item_id FOREIGN KEY (parent_evidence_item_id) REFERENCES trustlens.evidence_item (evidence_item_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evidence_derivative_parent_evidence_derivative_id FOREIGN KEY (parent_evidence_derivative_id) REFERENCES trustlens.evidence_derivative (evidence_derivative_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evidence_derivative_producing_principal_id FOREIGN KEY (producing_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evidence_derivative_retention_policy_reference_id FOREIGN KEY (retention_policy_reference_id) REFERENCES trustlens.retention_policy_reference (retention_policy_reference_id) ON DELETE RESTRICT,
    CONSTRAINT uq_evidence_derivative_idempotency UNIQUE (idempotency_key),
    CONSTRAINT ck_evidence_derivative_derivation_kind CHECK (derivation_kind IN ('NORMALIZED_TEXT', 'OCR_TEXT', 'REDACTED_PRESENTATION', 'PREVIEW', 'URL_OBSERVATION_RECORD', 'OTHER_GOVERNED')),
    CONSTRAINT ck_evidence_derivative_derivative_sha256_pattern CHECK (derivative_sha256 IS NULL OR derivative_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_evidence_derivative_content_state CHECK (content_state IN ('RECEIVED', 'CONTENT_PENDING', 'CONTENT_STORED', 'INTEGRITY_VERIFIED', 'FINALIZED', 'FAILED_RETRYABLE', 'FAILED_TERMINAL', 'ORPHAN_DETECTED', 'INTEGRITY_FAILED', 'QUARANTINED', 'DELETION_PENDING', 'DELETED')),
    CONSTRAINT ck_evidence_derivative_single_parent CHECK (num_nonnulls(parent_evidence_item_id, parent_evidence_derivative_id) = 1),
    CONSTRAINT ck_evidence_derivative_finalized_requires_verified CHECK ((content_state NOT IN ('CONTENT_STORED','INTEGRITY_VERIFIED','FINALIZED') OR (ecs_locator IS NOT NULL AND derivative_sha256 IS NOT NULL)) AND (content_state NOT IN ('INTEGRITY_VERIFIED','FINALIZED') OR verified_at IS NOT NULL) AND (content_state <> 'FINALIZED' OR finalized_at IS NOT NULL))
);
CREATE INDEX ix_evidence_derivative_parent_item ON trustlens.evidence_derivative (parent_evidence_item_id);
CREATE INDEX ix_evidence_derivative_parent_derivative ON trustlens.evidence_derivative (parent_evidence_derivative_id);
CREATE INDEX ix_evidence_derivative_incomplete ON trustlens.evidence_derivative (content_state, state_changed_at) WHERE content_state NOT IN ('FINALIZED','DELETED');

CREATE TABLE trustlens.input_envelope_record (
    input_envelope_record_id uuid NOT NULL,
    submission_id uuid NOT NULL,
    input_id text NOT NULL,
    envelope_version text NOT NULL,
    envelope_sha256 text,
    detected_language text[],
    detected_script text[],
    created_at timestamptz NOT NULL,
    ecs_locator text,
    content_state text NOT NULL,
    state_changed_at timestamptz NOT NULL,
    verified_at timestamptz,
    finalized_at timestamptz,
    idempotency_key uuid NOT NULL,
    retention_policy_reference_id uuid NOT NULL,
    CONSTRAINT pk_input_envelope_record PRIMARY KEY (input_envelope_record_id),
    CONSTRAINT fk_input_envelope_record_submission_id FOREIGN KEY (submission_id) REFERENCES trustlens.submission (submission_id) ON DELETE RESTRICT,
    CONSTRAINT fk_input_envelope_record_retention_policy_reference_id FOREIGN KEY (retention_policy_reference_id) REFERENCES trustlens.retention_policy_reference (retention_policy_reference_id) ON DELETE RESTRICT,
    CONSTRAINT uq_input_envelope_record_input_id UNIQUE (input_id),
    CONSTRAINT uq_input_envelope_record_id_input UNIQUE (input_envelope_record_id, input_id),
    CONSTRAINT uq_input_envelope_record_idempotency UNIQUE (idempotency_key),
    CONSTRAINT ck_input_envelope_record_input_id_pattern CHECK (input_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$'),
    CONSTRAINT ck_input_envelope_record_envelope_version CHECK (envelope_version IN ('1.0.0')),
    CONSTRAINT ck_input_envelope_record_envelope_sha256_pattern CHECK (envelope_sha256 IS NULL OR envelope_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_input_envelope_record_content_state CHECK (content_state IN ('RECEIVED', 'CONTENT_PENDING', 'CONTENT_STORED', 'INTEGRITY_VERIFIED', 'FINALIZED', 'FAILED_RETRYABLE', 'FAILED_TERMINAL', 'ORPHAN_DETECTED', 'INTEGRITY_FAILED', 'QUARANTINED', 'DELETION_PENDING', 'DELETED')),
    CONSTRAINT ck_input_envelope_record_finalized_requires_verified CHECK ((content_state NOT IN ('CONTENT_STORED','INTEGRITY_VERIFIED','FINALIZED') OR (ecs_locator IS NOT NULL AND envelope_sha256 IS NOT NULL)) AND (content_state NOT IN ('INTEGRITY_VERIFIED','FINALIZED') OR verified_at IS NOT NULL) AND (content_state <> 'FINALIZED' OR finalized_at IS NOT NULL))
);
CREATE INDEX ix_input_envelope_record_submission ON trustlens.input_envelope_record (submission_id);

CREATE TABLE trustlens.input_envelope_source (
    input_envelope_source_id uuid NOT NULL,
    input_envelope_record_id uuid NOT NULL,
    evidence_item_id uuid,
    evidence_derivative_id uuid,
    envelope_attachment_id text,
    CONSTRAINT pk_input_envelope_source PRIMARY KEY (input_envelope_source_id),
    CONSTRAINT fk_input_envelope_source_input_envelope_record_id FOREIGN KEY (input_envelope_record_id) REFERENCES trustlens.input_envelope_record (input_envelope_record_id) ON DELETE RESTRICT,
    CONSTRAINT fk_input_envelope_source_evidence_item_id FOREIGN KEY (evidence_item_id) REFERENCES trustlens.evidence_item (evidence_item_id) ON DELETE RESTRICT,
    CONSTRAINT fk_input_envelope_source_evidence_derivative_id FOREIGN KEY (evidence_derivative_id) REFERENCES trustlens.evidence_derivative (evidence_derivative_id) ON DELETE RESTRICT,
    CONSTRAINT ck_input_envelope_source_envelope_attachment_id_pattern CHECK (envelope_attachment_id IS NULL OR envelope_attachment_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$'),
    CONSTRAINT ck_input_envelope_source_single CHECK (num_nonnulls(evidence_item_id, evidence_derivative_id) = 1)
);
CREATE INDEX ix_input_envelope_source_envelope ON trustlens.input_envelope_source (input_envelope_record_id);
CREATE INDEX ix_input_envelope_source_item ON trustlens.input_envelope_source (evidence_item_id);
CREATE INDEX ix_input_envelope_source_derivative ON trustlens.input_envelope_source (evidence_derivative_id);

CREATE TABLE trustlens.evaluation (
    evaluation_id uuid NOT NULL,
    case_record_id uuid NOT NULL,
    submission_id uuid NOT NULL,
    input_envelope_record_id uuid NOT NULL,
    input_id text NOT NULL,
    origin text NOT NULL,
    predecessor_evaluation_id uuid,
    initiated_by_principal_id uuid NOT NULL,
    correlation_id text NOT NULL,
    status text NOT NULL,
    failure_category text,
    requested_at timestamptz NOT NULL,
    started_at timestamptz,
    evaluation_timestamp timestamptz,
    result_computed_at timestamptz,
    completed_at timestamptz,
    failed_at timestamptz,
    execution_lease_expires_at timestamptz,
    execution_fence_token uuid,
    bundle_content_digest text,
    bundle_version text,
    manifest_schema_version text,
    commit_sha text,
    engine_version text,
    result_contract_version text,
    evaluation_profile_id text,
    extraction_confidence_gate text,
    risk_matrix_id text,
    confidence_policy_id text,
    action_policy_version text,
    component_versions jsonb,
    ai_extraction_enabled boolean NOT NULL,
    ai_attempted boolean NOT NULL,
    ai_used boolean NOT NULL,
    ai_fallback_reason text,
    ai_config_ref text,
    input_support_status text,
    language text[],
    script text[],
    replay_material_digest text,
    CONSTRAINT pk_evaluation PRIMARY KEY (evaluation_id),
    CONSTRAINT fk_evaluation_case_record_id FOREIGN KEY (case_record_id) REFERENCES trustlens.case_record (case_record_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evaluation_submission_id FOREIGN KEY (submission_id) REFERENCES trustlens.submission (submission_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evaluation_input_envelope_record_input_id FOREIGN KEY (input_envelope_record_id, input_id) REFERENCES trustlens.input_envelope_record (input_envelope_record_id, input_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evaluation_predecessor_evaluation_id FOREIGN KEY (predecessor_evaluation_id) REFERENCES trustlens.evaluation (evaluation_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evaluation_initiated_by_principal_id FOREIGN KEY (initiated_by_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_evaluation_bundle_content_digest FOREIGN KEY (bundle_content_digest) REFERENCES trustlens.knowledge_bundle_reference (content_digest) ON DELETE RESTRICT,
    CONSTRAINT uq_evaluation_fence UNIQUE (evaluation_id, execution_fence_token),
    CONSTRAINT ck_evaluation_input_id_pattern CHECK (input_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$'),
    CONSTRAINT ck_evaluation_origin CHECK (origin IN ('INITIAL', 'RE_EVALUATION', 'USER_CORRECTION', 'AI_RE_EXTRACTION', 'RETRY_AFTER_FAILURE')),
    CONSTRAINT ck_evaluation_status CHECK (status IN ('REQUESTED', 'RUNNING', 'RESULT_COMPUTED_PERSISTENCE_PENDING', 'COMPLETED', 'FAILED_PRECONDITION', 'FAILED_INTEGRITY', 'FAILED_INFRASTRUCTURE')),
    CONSTRAINT ck_evaluation_failure_category CHECK (failure_category IN ('NO_VALID_ACTIVE_BUNDLE', 'ACTIVE_BUNDLE_WITHDRAWN', 'INVALID_TRUSTED_CONTEXT', 'BUNDLE_INTEGRITY', 'ARTIFACT_INTEGRITY', 'RESULT_ASSEMBLY_REJECTED', 'PERSISTENCE_FAILED', 'RESULT_DURABILITY_UNCONFIRMED', 'EXECUTION_LEASE_EXPIRED')),
    CONSTRAINT ck_evaluation_bundle_content_digest_pattern CHECK (bundle_content_digest IS NULL OR bundle_content_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_evaluation_bundle_version_pattern CHECK (bundle_version IS NULL OR bundle_version ~ '^\d+\.\d+\.\d+$'),
    CONSTRAINT ck_evaluation_manifest_schema_version CHECK (manifest_schema_version IN ('1.0.0', '1.1.0')),
    CONSTRAINT ck_evaluation_commit_sha_pattern CHECK (commit_sha IS NULL OR commit_sha ~ '^[0-9a-f]{7,40}$|^unknown$'),
    CONSTRAINT ck_evaluation_engine_version_pattern CHECK (engine_version IS NULL OR engine_version ~ '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$'),
    CONSTRAINT ck_evaluation_result_contract_version CHECK (result_contract_version IN ('1.1.0')),
    CONSTRAINT ck_evaluation_extraction_confidence_gate CHECK (extraction_confidence_gate IN ('HIGH', 'MEDIUM', 'LOW')),
    CONSTRAINT ck_evaluation_action_policy_version_pattern CHECK (action_policy_version IS NULL OR action_policy_version ~ '^\d+\.\d+\.\d+$'),
    CONSTRAINT ck_evaluation_ai_fallback_reason CHECK (ai_fallback_reason IN ('AI_DISABLED', 'AI_HOST_NOT_EVALUABLE', 'AI_PROVIDER_FAILED', 'AI_RESPONSE_REJECTED', 'AI_GOVERNANCE_FAILED', 'AI_MAPPING_FAILED')),
    CONSTRAINT ck_evaluation_ai_config_ref_pattern CHECK (ai_config_ref IS NULL OR ai_config_ref ~ '^ai-config:sha256:[0-9a-f]{64}$'),
    CONSTRAINT ck_evaluation_input_support_status CHECK (input_support_status IN ('SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED', 'INSUFFICIENT_INFORMATION', 'ERROR')),
    CONSTRAINT ck_evaluation_replay_material_digest_pattern CHECK (replay_material_digest IS NULL OR replay_material_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_evaluation_pins_after_start CHECK (status IN ('REQUESTED','FAILED_PRECONDITION') OR (bundle_content_digest IS NOT NULL AND bundle_version IS NOT NULL AND manifest_schema_version IS NOT NULL AND engine_version IS NOT NULL AND result_contract_version IS NOT NULL AND evaluation_profile_id IS NOT NULL AND extraction_confidence_gate IS NOT NULL AND risk_matrix_id IS NOT NULL AND confidence_policy_id IS NOT NULL AND action_policy_version IS NOT NULL AND component_versions IS NOT NULL AND evaluation_timestamp IS NOT NULL AND input_support_status IS NOT NULL AND language IS NOT NULL AND script IS NOT NULL)),
    CONSTRAINT ck_evaluation_completed CHECK (status <> 'COMPLETED' OR (completed_at IS NOT NULL AND result_computed_at IS NOT NULL AND replay_material_digest IS NOT NULL)),
    CONSTRAINT ck_evaluation_failed CHECK ((status IN ('FAILED_PRECONDITION','FAILED_INTEGRITY','FAILED_INFRASTRUCTURE')) = (failed_at IS NOT NULL AND failure_category IS NOT NULL)),
    CONSTRAINT ck_evaluation_origin_predecessor CHECK ((origin = 'INITIAL') = (predecessor_evaluation_id IS NULL)),
    CONSTRAINT ck_evaluation_ai_consistency CHECK ((NOT ai_attempted OR ai_extraction_enabled) AND (NOT ai_used OR (ai_attempted AND ai_fallback_reason IS NULL))),
    CONSTRAINT ck_evaluation_not_self_predecessor CHECK (predecessor_evaluation_id IS NULL OR predecessor_evaluation_id <> evaluation_id),
    CONSTRAINT ck_evaluation_fence_held_while_executing CHECK (status NOT IN ('RUNNING','RESULT_COMPUTED_PERSISTENCE_PENDING') OR execution_fence_token IS NOT NULL),
    CONSTRAINT ck_evaluation_fence_cleared_when_failed CHECK (status NOT IN ('FAILED_PRECONDITION','FAILED_INTEGRITY','FAILED_INFRASTRUCTURE') OR execution_fence_token IS NULL)
);
CREATE INDEX ix_evaluation_case ON trustlens.evaluation (case_record_id);
CREATE INDEX ix_evaluation_submission ON trustlens.evaluation (submission_id);
CREATE INDEX ix_evaluation_envelope ON trustlens.evaluation (input_envelope_record_id);
CREATE INDEX ix_evaluation_bundle_digest ON trustlens.evaluation (bundle_content_digest);
CREATE INDEX ix_evaluation_in_flight ON trustlens.evaluation (status, execution_lease_expires_at) WHERE status IN ('REQUESTED','RUNNING','RESULT_COMPUTED_PERSISTENCE_PENDING');
CREATE INDEX ix_evaluation_predecessor ON trustlens.evaluation (predecessor_evaluation_id) WHERE predecessor_evaluation_id IS NOT NULL;

CREATE TABLE trustlens.governed_input_artifact (
    governed_input_artifact_id uuid NOT NULL,
    evaluation_id uuid NOT NULL,
    input_envelope_record_id uuid NOT NULL,
    input_id text NOT NULL,
    governed_artifact_digest text NOT NULL,
    canonical_json_version text NOT NULL,
    storage_mode text NOT NULL,
    artifact_canonical_json text,
    ecs_locator text,
    observation_schema_version text NOT NULL,
    indicator_observation_schema_version text NOT NULL,
    created_at timestamptz NOT NULL,
    retention_policy_reference_id uuid NOT NULL,
    CONSTRAINT pk_governed_input_artifact PRIMARY KEY (governed_input_artifact_id),
    CONSTRAINT fk_governed_input_artifact_evaluation_id FOREIGN KEY (evaluation_id) REFERENCES trustlens.evaluation (evaluation_id) ON DELETE RESTRICT,
    CONSTRAINT fk_governed_input_artifact_input_envelope_record_input_id FOREIGN KEY (input_envelope_record_id, input_id) REFERENCES trustlens.input_envelope_record (input_envelope_record_id, input_id) ON DELETE RESTRICT,
    CONSTRAINT fk_governed_input_artifact_retention_policy_reference_id FOREIGN KEY (retention_policy_reference_id) REFERENCES trustlens.retention_policy_reference (retention_policy_reference_id) ON DELETE RESTRICT,
    CONSTRAINT uq_governed_input_artifact_evaluation UNIQUE (evaluation_id),
    CONSTRAINT uq_governed_input_artifact_evaluation_digest UNIQUE (evaluation_id, governed_artifact_digest),
    CONSTRAINT ck_governed_input_artifact_input_id_pattern CHECK (input_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$'),
    CONSTRAINT ck_governed_input_artifact_governed_artifact_digest_pattern CHECK (governed_artifact_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_governed_input_artifact_canonical_json_version CHECK (canonical_json_version IN ('TRUSTLENS_CANONICAL_JSON_V1')),
    CONSTRAINT ck_governed_input_artifact_storage_mode CHECK (storage_mode IN ('INLINE', 'ECS')),
    CONSTRAINT ck_governed_input_artifact_storage CHECK ((storage_mode = 'INLINE' AND artifact_canonical_json IS NOT NULL AND ecs_locator IS NULL) OR (storage_mode = 'ECS' AND artifact_canonical_json IS NULL AND ecs_locator IS NOT NULL))
);
CREATE INDEX ix_governed_input_artifact_envelope ON trustlens.governed_input_artifact (input_envelope_record_id);

CREATE TABLE trustlens.governed_observation_reference (
    governed_observation_reference_id uuid NOT NULL,
    governed_input_artifact_id uuid NOT NULL,
    observation_kind text NOT NULL,
    observation_ref text NOT NULL,
    status text,
    extraction_method text,
    is_model_derived boolean NOT NULL,
    CONSTRAINT pk_governed_observation_reference PRIMARY KEY (governed_observation_reference_id),
    CONSTRAINT fk_governed_observation_reference_governed_input_artifact_id FOREIGN KEY (governed_input_artifact_id) REFERENCES trustlens.governed_input_artifact (governed_input_artifact_id) ON DELETE RESTRICT,
    CONSTRAINT ck_governed_observation_reference_observation_kind CHECK (observation_kind IN ('NORMALIZED_OBSERVATION', 'INDICATOR_OBSERVATION')),
    CONSTRAINT ck_governed_observation_reference_observation_ref_pattern CHECK (observation_ref ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$'),
    CONSTRAINT ck_governed_observation_reference_status CHECK (status IN ('OBSERVED', 'NOT_OBSERVED', 'UNKNOWN', 'AMBIGUOUS', 'NOT_APPLICABLE')),
    CONSTRAINT ck_governed_observation_reference_extraction_method CHECK (extraction_method IN ('DETERMINISTIC_PATTERN', 'PARSER', 'NER_MODEL', 'CLASSIFIER', 'LLM', 'VISION', 'OCR', 'USER_SUPPLIED', 'SYSTEM_METADATA', 'COMPOSED'))
);
CREATE INDEX ix_governed_observation_reference_artifact ON trustlens.governed_observation_reference (governed_input_artifact_id);

CREATE TABLE trustlens.detection_result (
    detection_result_id uuid NOT NULL,
    evaluation_id uuid NOT NULL,
    execution_fence_token uuid NOT NULL,
    result_contract_version text NOT NULL,
    result_digest text NOT NULL,
    canonical_json_version text NOT NULL,
    storage_mode text NOT NULL,
    result_canonical_json text,
    ecs_locator text,
    input_support_status text NOT NULL,
    classification text NOT NULL,
    decision_severity text NOT NULL,
    matched_evidence_strength text NOT NULL,
    risk_level text NOT NULL,
    detection_confidence text NOT NULL,
    degraded boolean NOT NULL,
    engine_version text NOT NULL,
    bundle_version text NOT NULL,
    bundle_content_digest text NOT NULL,
    commit_sha text,
    evaluation_profile_id text NOT NULL,
    extraction_confidence_gate text NOT NULL,
    risk_matrix_id text NOT NULL,
    confidence_policy_id text NOT NULL,
    action_policy_version text NOT NULL,
    component_versions jsonb NOT NULL,
    evaluation_timestamp timestamptz NOT NULL,
    input_id text NOT NULL,
    language text[] NOT NULL,
    script text[] NOT NULL,
    persisted_at timestamptz NOT NULL,
    retention_policy_reference_id uuid NOT NULL,
    CONSTRAINT pk_detection_result PRIMARY KEY (detection_result_id),
    CONSTRAINT fk_detection_result_evaluation_id FOREIGN KEY (evaluation_id) REFERENCES trustlens.evaluation (evaluation_id) ON DELETE RESTRICT,
    CONSTRAINT fk_detection_result_bundle_content_digest FOREIGN KEY (bundle_content_digest) REFERENCES trustlens.knowledge_bundle_reference (content_digest) ON DELETE RESTRICT,
    CONSTRAINT fk_detection_result_retention_policy_reference_id FOREIGN KEY (retention_policy_reference_id) REFERENCES trustlens.retention_policy_reference (retention_policy_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_detection_result_evaluation_execution_fence_token FOREIGN KEY (evaluation_id, execution_fence_token) REFERENCES trustlens.evaluation (evaluation_id, execution_fence_token) ON DELETE RESTRICT,
    CONSTRAINT uq_detection_result_evaluation UNIQUE (evaluation_id),
    CONSTRAINT uq_detection_result_evaluation_digest UNIQUE (evaluation_id, result_digest),
    CONSTRAINT ck_detection_result_result_contract_version CHECK (result_contract_version IN ('1.1.0')),
    CONSTRAINT ck_detection_result_result_digest_pattern CHECK (result_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_detection_result_canonical_json_version CHECK (canonical_json_version IN ('TRUSTLENS_CANONICAL_JSON_V1')),
    CONSTRAINT ck_detection_result_storage_mode CHECK (storage_mode IN ('INLINE', 'ECS')),
    CONSTRAINT ck_detection_result_input_support_status CHECK (input_support_status IN ('SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED', 'INSUFFICIENT_INFORMATION', 'ERROR')),
    CONSTRAINT ck_detection_result_classification CHECK (classification IN ('NO_SCAM_PATTERN', 'INSUFFICIENT_EVIDENCE', 'SCAM_PATTERN_SUSPECTED', 'SCAM_PATTERN_DETECTED', 'UNSUPPORTED', 'ERROR')),
    CONSTRAINT ck_detection_result_decision_severity CHECK (decision_severity IN ('NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CONSTRAINT ck_detection_result_matched_evidence_strength CHECK (matched_evidence_strength IN ('NONE', 'WEAK', 'MODERATE', 'STRONG')),
    CONSTRAINT ck_detection_result_risk_level CHECK (risk_level IN ('NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CONSTRAINT ck_detection_result_detection_confidence CHECK (detection_confidence IN ('NOT_APPLICABLE', 'LOW', 'MEDIUM', 'HIGH')),
    CONSTRAINT ck_detection_result_engine_version_pattern CHECK (engine_version ~ '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$'),
    CONSTRAINT ck_detection_result_bundle_version_pattern CHECK (bundle_version ~ '^\d+\.\d+\.\d+$'),
    CONSTRAINT ck_detection_result_bundle_content_digest_pattern CHECK (bundle_content_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_detection_result_commit_sha_pattern CHECK (commit_sha IS NULL OR commit_sha ~ '^[0-9a-f]{7,40}$|^unknown$'),
    CONSTRAINT ck_detection_result_extraction_confidence_gate CHECK (extraction_confidence_gate IN ('HIGH', 'MEDIUM', 'LOW')),
    CONSTRAINT ck_detection_result_action_policy_version_pattern CHECK (action_policy_version ~ '^\d+\.\d+\.\d+$'),
    CONSTRAINT ck_detection_result_input_id_pattern CHECK (input_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$'),
    CONSTRAINT ck_detection_result_storage CHECK ((storage_mode = 'INLINE' AND result_canonical_json IS NOT NULL AND ecs_locator IS NULL) OR (storage_mode = 'ECS' AND result_canonical_json IS NULL AND ecs_locator IS NOT NULL))
);

CREATE TABLE trustlens.rule_result_projection (
    rule_result_projection_id uuid NOT NULL,
    detection_result_id uuid NOT NULL,
    ordinal integer NOT NULL,
    rule_id text NOT NULL,
    rule_version text NOT NULL,
    kind text NOT NULL,
    evaluation_state text NOT NULL,
    is_governing boolean NOT NULL,
    effective_severity text,
    rule_evidence_strength text,
    rule_detection_confidence text,
    CONSTRAINT pk_rule_result_projection PRIMARY KEY (rule_result_projection_id),
    CONSTRAINT fk_rule_result_projection_detection_result_id FOREIGN KEY (detection_result_id) REFERENCES trustlens.detection_result (detection_result_id) ON DELETE RESTRICT,
    CONSTRAINT uq_rule_result_projection_ordinal UNIQUE (detection_result_id, ordinal),
    CONSTRAINT ck_rule_result_projection_rule_id_pattern CHECK (rule_id ~ '^TL-[A-Z]{3,5}-\d{3}$'),
    CONSTRAINT ck_rule_result_projection_rule_version_pattern CHECK (rule_version ~ '^\d+\.\d+\.\d+$'),
    CONSTRAINT ck_rule_result_projection_kind CHECK (kind IN ('COMPOSITE', 'SUPPRESSION')),
    CONSTRAINT ck_rule_result_projection_evaluation_state CHECK (evaluation_state IN ('MATCHED', 'NOT_MATCHED', 'INDETERMINATE', 'SUPPRESSED', 'NOT_APPLICABLE')),
    CONSTRAINT ck_rule_result_projection_effective_severity CHECK (effective_severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    CONSTRAINT ck_rule_result_projection_rule_evidence_strength CHECK (rule_evidence_strength IN ('NONE', 'WEAK', 'MODERATE', 'STRONG')),
    CONSTRAINT ck_rule_result_projection_rule_detection_confidence CHECK (rule_detection_confidence IN ('LOW', 'MEDIUM', 'HIGH')),
    CONSTRAINT ck_rule_result_projection_ordinal CHECK (ordinal >= 0)
);

-- Shared: rows of an M-IMM table never change after insert.
CREATE FUNCTION trustlens.tg_immutable_row() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
END;
$$;

-- Shared cross-store content state machine (DATA-001-WP2 §11), as on evidence_item.
CREATE FUNCTION trustlens.cross_store_transition_allowed(old_state text, new_state text) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path = pg_catalog AS $$
    SELECT old_state = new_state OR (old_state, new_state) IN (
        ('RECEIVED', 'CONTENT_PENDING'), ('CONTENT_PENDING', 'CONTENT_STORED'), ('CONTENT_PENDING', 'FAILED_RETRYABLE'),
        ('CONTENT_STORED', 'INTEGRITY_VERIFIED'), ('CONTENT_STORED', 'FAILED_RETRYABLE'), ('CONTENT_STORED', 'INTEGRITY_FAILED'),
        ('INTEGRITY_VERIFIED', 'FINALIZED'), ('FAILED_RETRYABLE', 'CONTENT_PENDING'), ('FAILED_RETRYABLE', 'FAILED_TERMINAL'),
        ('FINALIZED', 'INTEGRITY_FAILED'), ('INTEGRITY_FAILED', 'QUARANTINED'), ('ORPHAN_DETECTED', 'QUARANTINED'),
        ('ORPHAN_DETECTED', 'FINALIZED'), ('FINALIZED', 'DELETION_PENDING'), ('DELETION_PENDING', 'DELETED'))
$$;

-- evidence_derivative and input_envelope_record (M-IMM manifests): only content_state/state_changed_at change; the
-- declared write-once columns are set once; identity never changes.
CREATE FUNCTION trustlens.tg_evidence_derivative_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.evidence_derivative_id, NEW.parent_evidence_item_id, NEW.parent_evidence_derivative_id, NEW.derivation_kind,
        NEW.transformation_id, NEW.transformation_version, NEW.producing_component_ref, NEW.producing_principal_id,
        NEW.created_at, NEW.idempotency_key, NEW.retention_policy_reference_id)
       IS DISTINCT FROM (OLD.evidence_derivative_id, OLD.parent_evidence_item_id, OLD.parent_evidence_derivative_id,
        OLD.derivation_kind, OLD.transformation_id, OLD.transformation_version, OLD.producing_component_ref,
        OLD.producing_principal_id, OLD.created_at, OLD.idempotency_key, OLD.retention_policy_reference_id) THEN
        RAISE EXCEPTION 'evidence_derivative identity is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (OLD.ecs_locator IS NOT NULL AND NEW.ecs_locator IS DISTINCT FROM OLD.ecs_locator)
       OR (OLD.derivative_sha256 IS NOT NULL AND NEW.derivative_sha256 IS DISTINCT FROM OLD.derivative_sha256)
       OR (OLD.byte_length IS NOT NULL AND NEW.byte_length IS DISTINCT FROM OLD.byte_length)
       OR (OLD.verified_at IS NOT NULL AND NEW.verified_at IS DISTINCT FROM OLD.verified_at)
       OR (OLD.finalized_at IS NOT NULL AND NEW.finalized_at IS DISTINCT FROM OLD.finalized_at) THEN
        RAISE EXCEPTION 'evidence_derivative write-once column changed' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NOT trustlens.cross_store_transition_allowed(OLD.content_state, NEW.content_state) THEN
        RAISE EXCEPTION 'evidence_derivative content_state transition % -> % is not allowed', OLD.content_state, NEW.content_state
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_evidence_derivative_guard BEFORE UPDATE ON trustlens.evidence_derivative
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_evidence_derivative_guard();
CREATE TRIGGER tr_evidence_derivative_governed_deletion BEFORE DELETE ON trustlens.evidence_derivative
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

CREATE FUNCTION trustlens.tg_input_envelope_record_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.input_envelope_record_id, NEW.submission_id, NEW.input_id, NEW.envelope_version, NEW.created_at,
        NEW.idempotency_key, NEW.retention_policy_reference_id)
       IS DISTINCT FROM (OLD.input_envelope_record_id, OLD.submission_id, OLD.input_id, OLD.envelope_version, OLD.created_at,
        OLD.idempotency_key, OLD.retention_policy_reference_id) THEN
        RAISE EXCEPTION 'input_envelope_record identity is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (OLD.ecs_locator IS NOT NULL AND NEW.ecs_locator IS DISTINCT FROM OLD.ecs_locator)
       OR (OLD.envelope_sha256 IS NOT NULL AND NEW.envelope_sha256 IS DISTINCT FROM OLD.envelope_sha256)
       OR (OLD.verified_at IS NOT NULL AND NEW.verified_at IS DISTINCT FROM OLD.verified_at)
       OR (OLD.finalized_at IS NOT NULL AND NEW.finalized_at IS DISTINCT FROM OLD.finalized_at)
       OR (OLD.detected_language IS NOT NULL AND NEW.detected_language IS DISTINCT FROM OLD.detected_language)
       OR (OLD.detected_script IS NOT NULL AND NEW.detected_script IS DISTINCT FROM OLD.detected_script) THEN
        RAISE EXCEPTION 'input_envelope_record write-once column changed' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NOT trustlens.cross_store_transition_allowed(OLD.content_state, NEW.content_state) THEN
        RAISE EXCEPTION 'input_envelope_record content_state transition % -> % is not allowed', OLD.content_state, NEW.content_state
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_input_envelope_record_guard BEFORE UPDATE ON trustlens.input_envelope_record
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_input_envelope_record_guard();
CREATE TRIGGER tr_input_envelope_record_governed_deletion BEFORE DELETE ON trustlens.input_envelope_record
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- input_envelope_source: the source evidence must belong to the envelope's submission.
CREATE FUNCTION trustlens.tg_input_envelope_source_same_submission() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    envelope_submission uuid;
    source_submission uuid;
BEGIN
    SELECT submission_id INTO envelope_submission FROM trustlens.input_envelope_record
        WHERE input_envelope_record_id = NEW.input_envelope_record_id;
    IF NEW.evidence_item_id IS NOT NULL THEN
        SELECT submission_id INTO source_submission FROM trustlens.evidence_item WHERE evidence_item_id = NEW.evidence_item_id;
    ELSE
        SELECT i.submission_id INTO source_submission FROM trustlens.evidence_derivative d
            JOIN trustlens.evidence_item i ON i.evidence_item_id = d.parent_evidence_item_id
            WHERE d.evidence_derivative_id = NEW.evidence_derivative_id;
    END IF;
    IF source_submission IS DISTINCT FROM envelope_submission THEN
        RAISE EXCEPTION 'input_envelope_source evidence must belong to the envelope submission' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_input_envelope_source_same_submission BEFORE INSERT ON trustlens.input_envelope_source
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_input_envelope_source_same_submission();

-- evaluation (M-OPS, WP2 §12): created REQUESTED; declared transitions only; terminal states never change; write-once
-- pins; AI columns only while REQUESTED/RUNNING; the fence token is set on entering RUNNING, cleared on failure and
-- otherwise never changes; RUNNING requires the governed input artifact.
CREATE FUNCTION trustlens.tg_evaluation_insert_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.status <> 'REQUESTED' OR NEW.execution_fence_token IS NOT NULL OR NEW.started_at IS NOT NULL
       OR NEW.completed_at IS NOT NULL OR NEW.failed_at IS NOT NULL OR NEW.result_computed_at IS NOT NULL
       OR NEW.bundle_content_digest IS NOT NULL OR NEW.replay_material_digest IS NOT NULL THEN
        RAISE EXCEPTION 'an evaluation is created REQUESTED, unpinned and unfenced' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_evaluation_insert_guard BEFORE INSERT ON trustlens.evaluation
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_evaluation_insert_guard();

CREATE FUNCTION trustlens.tg_evaluation_transition_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.evaluation_id, NEW.case_record_id, NEW.submission_id, NEW.input_envelope_record_id, NEW.input_id, NEW.origin,
        NEW.predecessor_evaluation_id, NEW.initiated_by_principal_id, NEW.correlation_id, NEW.requested_at,
        NEW.ai_extraction_enabled)
       IS DISTINCT FROM (OLD.evaluation_id, OLD.case_record_id, OLD.submission_id, OLD.input_envelope_record_id, OLD.input_id,
        OLD.origin, OLD.predecessor_evaluation_id, OLD.initiated_by_principal_id, OLD.correlation_id, OLD.requested_at,
        OLD.ai_extraction_enabled) THEN
        RAISE EXCEPTION 'evaluation identity is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF OLD.status IN ('COMPLETED', 'FAILED_PRECONDITION', 'FAILED_INTEGRITY', 'FAILED_INFRASTRUCTURE') THEN
        RAISE EXCEPTION 'evaluation % is terminal', OLD.status USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.status <> OLD.status AND (OLD.status, NEW.status) NOT IN (
        ('REQUESTED', 'RUNNING'), ('REQUESTED', 'FAILED_PRECONDITION'),
        ('RUNNING', 'RESULT_COMPUTED_PERSISTENCE_PENDING'), ('RUNNING', 'COMPLETED'), ('RUNNING', 'FAILED_INTEGRITY'),
        ('RUNNING', 'FAILED_INFRASTRUCTURE'), ('RESULT_COMPUTED_PERSISTENCE_PENDING', 'COMPLETED'),
        ('RESULT_COMPUTED_PERSISTENCE_PENDING', 'FAILED_INFRASTRUCTURE')) THEN
        RAISE EXCEPTION 'evaluation transition % -> % is not allowed', OLD.status, NEW.status USING ERRCODE = 'check_violation';
    END IF;
    IF (OLD.bundle_content_digest IS NOT NULL AND NEW.bundle_content_digest IS DISTINCT FROM OLD.bundle_content_digest)
       OR (OLD.bundle_version IS NOT NULL AND NEW.bundle_version IS DISTINCT FROM OLD.bundle_version)
       OR (OLD.manifest_schema_version IS NOT NULL AND NEW.manifest_schema_version IS DISTINCT FROM OLD.manifest_schema_version)
       OR (OLD.commit_sha IS NOT NULL AND NEW.commit_sha IS DISTINCT FROM OLD.commit_sha)
       OR (OLD.engine_version IS NOT NULL AND NEW.engine_version IS DISTINCT FROM OLD.engine_version)
       OR (OLD.result_contract_version IS NOT NULL AND NEW.result_contract_version IS DISTINCT FROM OLD.result_contract_version)
       OR (OLD.evaluation_profile_id IS NOT NULL AND NEW.evaluation_profile_id IS DISTINCT FROM OLD.evaluation_profile_id)
       OR (OLD.extraction_confidence_gate IS NOT NULL AND NEW.extraction_confidence_gate IS DISTINCT FROM OLD.extraction_confidence_gate)
       OR (OLD.risk_matrix_id IS NOT NULL AND NEW.risk_matrix_id IS DISTINCT FROM OLD.risk_matrix_id)
       OR (OLD.confidence_policy_id IS NOT NULL AND NEW.confidence_policy_id IS DISTINCT FROM OLD.confidence_policy_id)
       OR (OLD.action_policy_version IS NOT NULL AND NEW.action_policy_version IS DISTINCT FROM OLD.action_policy_version)
       OR (OLD.component_versions IS NOT NULL AND NEW.component_versions IS DISTINCT FROM OLD.component_versions)
       OR (OLD.evaluation_timestamp IS NOT NULL AND NEW.evaluation_timestamp IS DISTINCT FROM OLD.evaluation_timestamp)
       OR (OLD.input_support_status IS NOT NULL AND NEW.input_support_status IS DISTINCT FROM OLD.input_support_status)
       OR (OLD.language IS NOT NULL AND NEW.language IS DISTINCT FROM OLD.language)
       OR (OLD.script IS NOT NULL AND NEW.script IS DISTINCT FROM OLD.script)
       OR (OLD.started_at IS NOT NULL AND NEW.started_at IS DISTINCT FROM OLD.started_at)
       OR (OLD.result_computed_at IS NOT NULL AND NEW.result_computed_at IS DISTINCT FROM OLD.result_computed_at)
       OR (OLD.completed_at IS NOT NULL AND NEW.completed_at IS DISTINCT FROM OLD.completed_at)
       OR (OLD.failed_at IS NOT NULL AND NEW.failed_at IS DISTINCT FROM OLD.failed_at)
       OR (OLD.replay_material_digest IS NOT NULL AND NEW.replay_material_digest IS DISTINCT FROM OLD.replay_material_digest) THEN
        RAISE EXCEPTION 'evaluation write-once pin changed' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (NEW.ai_attempted, NEW.ai_used, NEW.ai_fallback_reason, NEW.ai_config_ref)
       IS DISTINCT FROM (OLD.ai_attempted, OLD.ai_used, OLD.ai_fallback_reason, OLD.ai_config_ref)
       AND OLD.status NOT IN ('REQUESTED', 'RUNNING') THEN
        RAISE EXCEPTION 'evaluation AI columns change only while REQUESTED or RUNNING' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.execution_fence_token IS DISTINCT FROM OLD.execution_fence_token
       AND NOT (OLD.status = 'REQUESTED' AND NEW.status = 'RUNNING' AND NEW.execution_fence_token IS NOT NULL)
       AND NOT (NEW.status IN ('FAILED_PRECONDITION', 'FAILED_INTEGRITY', 'FAILED_INFRASTRUCTURE') AND NEW.execution_fence_token IS NULL) THEN
        RAISE EXCEPTION 'evaluation fence token changes only on entering RUNNING or on failure' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.status = 'RUNNING' AND OLD.status <> 'RUNNING'
       AND NOT EXISTS (SELECT 1 FROM trustlens.governed_input_artifact a WHERE a.evaluation_id = NEW.evaluation_id) THEN
        RAISE EXCEPTION 'an evaluation enters RUNNING only with its governed input artifact' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_evaluation_transition_guard BEFORE UPDATE ON trustlens.evaluation
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_evaluation_transition_guard();
CREATE TRIGGER tr_evaluation_governed_deletion BEFORE DELETE ON trustlens.evaluation
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

CREATE FUNCTION trustlens.tg_evaluation_completed_requires_result() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.status = 'COMPLETED'
       AND NOT EXISTS (SELECT 1 FROM trustlens.detection_result r WHERE r.evaluation_id = NEW.evaluation_id) THEN
        RAISE EXCEPTION 'a COMPLETED evaluation requires its durable result' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER tr_evaluation_completed_requires_result AFTER INSERT OR UPDATE ON trustlens.evaluation
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trustlens.tg_evaluation_completed_requires_result();

-- detection_result (M-IMM): inserted only for the live (evaluation, fence token) of a RUNNING or
-- RESULT_COMPUTED_PERSISTENCE_PENDING evaluation, with pins equal to the evaluation's; persists only under COMPLETED.
CREATE FUNCTION trustlens.tg_detection_result_insert_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    e record;
BEGIN
    SELECT status, execution_fence_token, bundle_content_digest, bundle_version, commit_sha, engine_version,
           result_contract_version, evaluation_profile_id, extraction_confidence_gate, risk_matrix_id, confidence_policy_id,
           action_policy_version, component_versions, evaluation_timestamp, input_id, input_support_status, language, script
        INTO e FROM trustlens.evaluation WHERE evaluation_id = NEW.evaluation_id FOR UPDATE;
    IF NOT FOUND OR e.status NOT IN ('RUNNING', 'RESULT_COMPUTED_PERSISTENCE_PENDING')
       OR e.execution_fence_token IS DISTINCT FROM NEW.execution_fence_token THEN
        RAISE EXCEPTION 'detection_result rejected: evaluation not executing under this fence' USING ERRCODE = 'check_violation';
    END IF;
    IF (NEW.bundle_content_digest, NEW.bundle_version, NEW.engine_version, NEW.result_contract_version,
        NEW.evaluation_profile_id, NEW.extraction_confidence_gate, NEW.risk_matrix_id, NEW.confidence_policy_id,
        NEW.action_policy_version, NEW.component_versions, NEW.evaluation_timestamp, NEW.input_id, NEW.input_support_status,
        NEW.language, NEW.script)
       IS DISTINCT FROM (e.bundle_content_digest, e.bundle_version, e.engine_version, e.result_contract_version,
        e.evaluation_profile_id, e.extraction_confidence_gate, e.risk_matrix_id, e.confidence_policy_id,
        e.action_policy_version, e.component_versions, e.evaluation_timestamp, e.input_id, e.input_support_status,
        e.language, e.script)
       OR (NEW.commit_sha IS NOT NULL AND NEW.commit_sha IS DISTINCT FROM e.commit_sha) THEN
        RAISE EXCEPTION 'detection_result pins must equal the evaluation pins' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_detection_result_insert_guard BEFORE INSERT ON trustlens.detection_result
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_detection_result_insert_guard();

CREATE FUNCTION trustlens.tg_detection_result_requires_completed() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM trustlens.evaluation e WHERE e.evaluation_id = NEW.evaluation_id AND e.status = 'COMPLETED') THEN
        RAISE EXCEPTION 'a detection_result persists only under a COMPLETED evaluation' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER tr_detection_result_requires_completed AFTER INSERT ON trustlens.detection_result
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trustlens.tg_detection_result_requires_completed();
CREATE TRIGGER tr_detection_result_immutable BEFORE UPDATE ON trustlens.detection_result
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_immutable_row();
CREATE TRIGGER tr_detection_result_governed_deletion BEFORE DELETE ON trustlens.detection_result
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- The remaining M-IMM tables never change; deletion is governed only.
CREATE TRIGGER tr_input_envelope_source_immutable BEFORE UPDATE ON trustlens.input_envelope_source
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_immutable_row();
CREATE TRIGGER tr_input_envelope_source_governed_deletion BEFORE DELETE ON trustlens.input_envelope_source
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();
CREATE TRIGGER tr_governed_input_artifact_immutable BEFORE UPDATE ON trustlens.governed_input_artifact
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_immutable_row();
CREATE TRIGGER tr_governed_input_artifact_governed_deletion BEFORE DELETE ON trustlens.governed_input_artifact
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();
CREATE TRIGGER tr_governed_observation_reference_immutable BEFORE UPDATE ON trustlens.governed_observation_reference
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_immutable_row();
CREATE TRIGGER tr_governed_observation_reference_governed_deletion BEFORE DELETE ON trustlens.governed_observation_reference
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();
CREATE TRIGGER tr_rule_result_projection_immutable BEFORE UPDATE ON trustlens.rule_result_projection
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_immutable_row();
CREATE TRIGGER tr_rule_result_projection_governed_deletion BEFORE DELETE ON trustlens.rule_result_projection
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

REVOKE ALL ON trustlens.evidence_derivative, trustlens.input_envelope_record, trustlens.input_envelope_source,
    trustlens.evaluation, trustlens.governed_input_artifact, trustlens.governed_observation_reference,
    trustlens.detection_result, trustlens.rule_result_projection FROM PUBLIC;
REVOKE ALL ON FUNCTION trustlens.tg_immutable_row(), trustlens.cross_store_transition_allowed(text, text),
    trustlens.tg_evidence_derivative_guard(), trustlens.tg_input_envelope_record_guard(),
    trustlens.tg_input_envelope_source_same_submission(), trustlens.tg_evaluation_insert_guard(),
    trustlens.tg_evaluation_transition_guard(), trustlens.tg_evaluation_completed_requires_result(),
    trustlens.tg_detection_result_insert_guard(), trustlens.tg_detection_result_requires_completed() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION trustlens.cross_store_transition_allowed(text, text) TO tl_app_runtime;
GRANT SELECT ON trustlens.evidence_derivative TO tl_app_runtime;
GRANT SELECT, INSERT ON trustlens.input_envelope_record, trustlens.input_envelope_source, trustlens.evaluation,
    trustlens.governed_input_artifact, trustlens.governed_observation_reference, trustlens.detection_result,
    trustlens.rule_result_projection TO tl_app_runtime;
GRANT UPDATE (content_state, state_changed_at, ecs_locator, envelope_sha256, verified_at, finalized_at, detected_language,
    detected_script) ON trustlens.input_envelope_record TO tl_app_runtime;
GRANT UPDATE (status, failure_category, execution_lease_expires_at, ai_attempted, ai_used, ai_fallback_reason, ai_config_ref,
    execution_fence_token, bundle_content_digest, bundle_version, manifest_schema_version, commit_sha, engine_version,
    result_contract_version, evaluation_profile_id, extraction_confidence_gate, risk_matrix_id, confidence_policy_id,
    action_policy_version, component_versions, evaluation_timestamp, input_support_status, language, script, started_at,
    result_computed_at, completed_at, failed_at, replay_material_digest) ON trustlens.evaluation TO tl_app_runtime;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    raise NotImplementedError("Downgrade requires separate review of lossless rollback")
