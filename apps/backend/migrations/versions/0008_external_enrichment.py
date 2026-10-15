"""S7 advisory external enrichment persistence (DATA-001-WP2 + P6-WP6-ADD-001 table external_enrichment_result).

Revision: 0008_external_enrichment
Contract reference and change class: contracts/postgresql/schema-v1.json table external_enrichment_result, including the
P6-WP6 additive INT-001 provenance, outcome, freshness, cache, policy-identity and artifact columns. Columns, nullability,
foreign keys (RESTRICT), named CHECKs, vocabulary CHECKs and indexes are generated from the contract. Rows are immutable
historical provenance (M-IMM): a new observation, cache refresh, policy change or re-analysis inserts a NEW row.
Change class: ADDITIVE. No reference data. The application may SELECT and INSERT only.
"""
from alembic import op

revision = "0008_external_enrichment"
down_revision = "0007_correction_replay"
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
CREATE TABLE trustlens.external_enrichment_result (
    external_enrichment_result_id uuid NOT NULL,
    evaluation_id uuid,
    target_evidence_item_id uuid,
    target_evidence_derivative_id uuid,
    provider_ref text NOT NULL,
    adapter_version text NOT NULL,
    integration_contract_version text NOT NULL,
    request_ref text NOT NULL,
    requested_at timestamptz NOT NULL,
    responded_at timestamptz,
    status text NOT NULL,
    safe_error_category text,
    reputation_result text NOT NULL,
    allowlist_result text NOT NULL,
    domain_matches_claimed_brand text NOT NULL,
    raw_provider_content_policy_ref text NOT NULL,
    consumed_in_governed_artifact boolean NOT NULL,
    created_at timestamptz NOT NULL,
    retention_policy_reference_id uuid NOT NULL,
    indicator_type text NOT NULL,
    normalized_indicator_ref text NOT NULL,
    lookup_outcome text,
    provider_response_category text,
    freshness_state text NOT NULL,
    freshness_policy_ref text,
    cache_used boolean NOT NULL,
    provider_policy_ref text NOT NULL,
    provider_policy_version text NOT NULL,
    provider_policy_digest text NOT NULL,
    parser_schema_version text NOT NULL,
    response_artifact_digest text,
    retained_provider_artifact_ecs_locator text,
    CONSTRAINT pk_external_enrichment_result PRIMARY KEY (external_enrichment_result_id),
    CONSTRAINT fk_external_enrichment_result_evaluation_id FOREIGN KEY (evaluation_id) REFERENCES trustlens.evaluation (evaluation_id) ON DELETE RESTRICT,
    CONSTRAINT fk_external_enrichment_result_target_evidence_item_id FOREIGN KEY (target_evidence_item_id) REFERENCES trustlens.evidence_item (evidence_item_id) ON DELETE RESTRICT,
    CONSTRAINT fk_external_enrichment_result_target_evidence_derivative_id FOREIGN KEY (target_evidence_derivative_id) REFERENCES trustlens.evidence_derivative (evidence_derivative_id) ON DELETE RESTRICT,
    CONSTRAINT fk_external_enrichment_result_retention_policy_reference_id FOREIGN KEY (retention_policy_reference_id) REFERENCES trustlens.retention_policy_reference (retention_policy_reference_id) ON DELETE RESTRICT,
    CONSTRAINT ck_external_enrichment_result_status CHECK (status IN ('SUCCEEDED', 'FAILED', 'TIMED_OUT', 'REJECTED', 'NOT_EVALUATED')),
    CONSTRAINT ck_external_enrichment_result_safe_error_category CHECK (safe_error_category IN ('DNS_FAILURE', 'CONNECTION_FAILURE', 'TLS_FAILURE', 'TIMEOUT', 'PROVIDER_CLIENT_ERROR', 'PROVIDER_SERVER_ERROR', 'RATE_LIMITED', 'INVALID_CONTENT_TYPE', 'OVERSIZED_RESPONSE', 'DECOMPRESSION_LIMIT_EXCEEDED', 'SCHEMA_INVALID_RESPONSE', 'POLICY_REJECTION', 'REDIRECT_POLICY_REJECTION', 'DESTINATION_ADDRESS_REJECTION', 'PROXY_ENFORCEMENT_UNVERIFIED', 'CREDENTIAL_UNAVAILABLE', 'PROVIDER_UNAVAILABLE')),
    CONSTRAINT ck_external_enrichment_result_reputation_result CHECK (reputation_result IN ('MALICIOUS', 'SUSPICIOUS', 'CLEAN', 'UNKNOWN', 'NOT_EVALUATED')),
    CONSTRAINT ck_external_enrichment_result_allowlist_result CHECK (allowlist_result IN ('ALLOWLISTED', 'NOT_ALLOWLISTED', 'NOT_EVALUATED')),
    CONSTRAINT ck_external_enrichment_result_domain_matches_claimed_brand CHECK (domain_matches_claimed_brand IN ('MATCH', 'MISMATCH', 'UNKNOWN')),
    CONSTRAINT ck_external_enrichment_result_indicator_type CHECK (indicator_type IN ('URL', 'HOSTNAME', 'REGISTERED_DOMAIN')),
    CONSTRAINT ck_external_enrichment_result_normalized_indicator_ref_pattern CHECK (normalized_indicator_ref ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_external_enrichment_result_lookup_outcome CHECK (lookup_outcome IN ('FOUND', 'NOT_FOUND', 'UNAVAILABLE', 'POLICY_REJECTED', 'INVALID_RESPONSE')),
    CONSTRAINT ck_external_enrichment_result_provider_response_category CHECK (provider_response_category IN ('HTTP_2XX', 'HTTP_3XX', 'HTTP_4XX', 'HTTP_429', 'HTTP_5XX', 'NO_RESPONSE')),
    CONSTRAINT ck_external_enrichment_result_freshness_state CHECK (freshness_state IN ('FRESH', 'STALE', 'UNKNOWN')),
    CONSTRAINT ck_external_enrichment_result_provider_policy_digest_pattern CHECK (provider_policy_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_external_enrichment_result_response_artifact_digest_pattern CHECK (response_artifact_digest IS NULL OR response_artifact_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_external_enrichment_failure_not_clean CHECK (status = 'SUCCEEDED' OR (reputation_result = 'NOT_EVALUATED' AND allowlist_result = 'NOT_EVALUATED' AND domain_matches_claimed_brand = 'UNKNOWN')),
    CONSTRAINT ck_external_enrichment_not_consumed CHECK (NOT consumed_in_governed_artifact),
    CONSTRAINT ck_external_enrichment_target CHECK (num_nonnulls(evaluation_id, target_evidence_item_id, target_evidence_derivative_id) >= 1),
    CONSTRAINT ck_external_enrichment_outcome_status CHECK ((status = 'NOT_EVALUATED' AND lookup_outcome IS NULL) OR (lookup_outcome IN ('FOUND','NOT_FOUND') AND status = 'SUCCEEDED') OR (lookup_outcome = 'UNAVAILABLE' AND status IN ('FAILED','TIMED_OUT')) OR (lookup_outcome = 'POLICY_REJECTED' AND status = 'REJECTED') OR (lookup_outcome = 'INVALID_RESPONSE' AND status = 'FAILED')),
    CONSTRAINT ck_external_enrichment_not_found_unknown CHECK (lookup_outcome IS DISTINCT FROM 'NOT_FOUND' OR (reputation_result = 'UNKNOWN' AND allowlist_result IN ('NOT_ALLOWLISTED','NOT_EVALUATED') AND domain_matches_claimed_brand = 'UNKNOWN')),
    CONSTRAINT ck_external_enrichment_error_category CHECK ((lookup_outcome IN ('UNAVAILABLE','POLICY_REJECTED','INVALID_RESPONSE') AND safe_error_category IS NOT NULL) OR ((lookup_outcome IS NULL OR lookup_outcome NOT IN ('UNAVAILABLE','POLICY_REJECTED','INVALID_RESPONSE')) AND safe_error_category IS NULL)),
    CONSTRAINT ck_external_enrichment_artifact CHECK (lookup_outcome IS NULL OR lookup_outcome NOT IN ('FOUND','NOT_FOUND') OR response_artifact_digest IS NOT NULL),
    CONSTRAINT ck_external_enrichment_retained_artifact CHECK (retained_provider_artifact_ecs_locator IS NULL OR response_artifact_digest IS NOT NULL)
);
CREATE INDEX ix_external_enrichment_result_evaluation ON trustlens.external_enrichment_result (evaluation_id);
CREATE INDEX ix_external_enrichment_result_item ON trustlens.external_enrichment_result (target_evidence_item_id);
CREATE INDEX ix_external_enrichment_result_derivative ON trustlens.external_enrichment_result (target_evidence_derivative_id);

-- M-IMM: never updated; removed only by the governed deletion executor.
CREATE TRIGGER tr_external_enrichment_result_immutable BEFORE UPDATE ON trustlens.external_enrichment_result
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_immutable_row();
CREATE TRIGGER tr_external_enrichment_result_governed_deletion BEFORE DELETE ON trustlens.external_enrichment_result
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

REVOKE ALL ON trustlens.external_enrichment_result FROM PUBLIC;
GRANT SELECT, INSERT ON trustlens.external_enrichment_result TO tl_app_runtime;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    raise NotImplementedError("Downgrade requires separate review of lossless rollback")
