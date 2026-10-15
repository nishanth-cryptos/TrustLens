"""S6 user corrections and exact historical replay (DATA-001-WP2 tables user_correction and replay_execution).

Revision: 0007_correction_replay
Contract reference and change class: contracts/postgresql/schema-v1.json tables user_correction and replay_execution.
Columns, nullability, primary/foreign keys (RESTRICT), the partial unique index, named CHECKs, vocabulary CHECKs and
indexes are generated from the contract; the text[] vocabulary CHECK is expressed as array containment. Triggers implement
the declared mutability (M-APP, write-once columns) and tg_replay_execution_requires_completed. Change class: ADDITIVE.
"""
from alembic import op

revision = "0007_correction_replay"
down_revision = "0006_evaluation_result"
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
CREATE TABLE trustlens.user_correction (
    user_correction_id uuid NOT NULL,
    case_record_id uuid NOT NULL,
    corrected_evaluation_id uuid NOT NULL,
    resulting_evaluation_id uuid,
    correcting_principal_id uuid NOT NULL,
    correction_description text NOT NULL,
    created_at timestamptz NOT NULL,
    CONSTRAINT pk_user_correction PRIMARY KEY (user_correction_id),
    CONSTRAINT fk_user_correction_case_record_id FOREIGN KEY (case_record_id) REFERENCES trustlens.case_record (case_record_id) ON DELETE RESTRICT,
    CONSTRAINT fk_user_correction_corrected_evaluation_id FOREIGN KEY (corrected_evaluation_id) REFERENCES trustlens.evaluation (evaluation_id) ON DELETE RESTRICT,
    CONSTRAINT fk_user_correction_resulting_evaluation_id FOREIGN KEY (resulting_evaluation_id) REFERENCES trustlens.evaluation (evaluation_id) ON DELETE RESTRICT,
    CONSTRAINT fk_user_correction_correcting_principal_id FOREIGN KEY (correcting_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT ck_user_correction_distinct CHECK (resulting_evaluation_id IS NULL OR resulting_evaluation_id <> corrected_evaluation_id)
);
CREATE UNIQUE INDEX uq_user_correction_resulting ON trustlens.user_correction (resulting_evaluation_id) WHERE resulting_evaluation_id IS NOT NULL;
CREATE INDEX ix_user_correction_corrected ON trustlens.user_correction (corrected_evaluation_id);
CREATE INDEX ix_user_correction_case ON trustlens.user_correction (case_record_id);

CREATE TABLE trustlens.replay_execution (
    replay_execution_id uuid NOT NULL,
    evaluation_id uuid NOT NULL,
    requested_by_principal_id uuid NOT NULL,
    reason_ref text NOT NULL,
    requested_at timestamptz NOT NULL,
    replay_capability_state text,
    missing_material_kinds text[],
    outcome text,
    replayed_result_digest text,
    completed_at timestamptz,
    CONSTRAINT pk_replay_execution PRIMARY KEY (replay_execution_id),
    CONSTRAINT fk_replay_execution_evaluation_id FOREIGN KEY (evaluation_id) REFERENCES trustlens.evaluation (evaluation_id) ON DELETE RESTRICT,
    CONSTRAINT fk_replay_execution_requested_by_principal_id FOREIGN KEY (requested_by_principal_id) REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT ck_replay_execution_replay_capability_state CHECK (replay_capability_state IN ('REPLAY_CAPABLE', 'REPLAY_UNAVAILABLE_REQUIRED_ARTIFACT_MISSING', 'REPLAY_UNAVAILABLE_INTEGRITY_FAILED', 'REPLAY_UNAVAILABLE_BUNDLE_MISSING', 'REPLAY_UNAVAILABLE_ENGINE_UNAVAILABLE')),
    CONSTRAINT ck_replay_execution_missing_material_kinds CHECK (missing_material_kinds <@ ARRAY['EVALUATION_PINS', 'GOVERNED_INPUT_ARTIFACT', 'KNOWLEDGE_BUNDLE', 'ENGINE_VERSION', 'AI_REPLAY_SNAPSHOT', 'DETECTION_RESULT', 'EVIDENCE_MANIFEST', 'EVIDENCE_BYTES', 'EVIDENCE_DERIVATIVE', 'INPUT_ENVELOPE']::text[]),
    CONSTRAINT ck_replay_execution_outcome CHECK (outcome IN ('MATCH', 'MISMATCH', 'FAILED_MISSING_MATERIAL', 'FAILED_INTEGRITY', 'FAILED_ENGINE_UNAVAILABLE', 'FAILED_BUNDLE_UNAVAILABLE')),
    CONSTRAINT ck_replay_execution_replayed_result_digest_pattern CHECK (replayed_result_digest IS NULL OR replayed_result_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_replay_execution_capable_outcomes CHECK (outcome IS NULL OR ((replay_capability_state = 'REPLAY_CAPABLE') = (outcome IN ('MATCH','MISMATCH')))),
    CONSTRAINT ck_replay_execution_match_digest CHECK (outcome NOT IN ('MATCH','MISMATCH') OR replayed_result_digest IS NOT NULL),
    CONSTRAINT ck_replay_execution_missing_listed CHECK (replay_capability_state IS NULL OR replay_capability_state = 'REPLAY_CAPABLE' OR missing_material_kinds IS NOT NULL)
);
CREATE INDEX ix_replay_execution_evaluation ON trustlens.replay_execution (evaluation_id);

-- user_correction (M-APP): append-only; resulting_evaluation_id is write-once and nothing else ever changes.
CREATE FUNCTION trustlens.tg_user_correction_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.user_correction_id, NEW.case_record_id, NEW.corrected_evaluation_id, NEW.correcting_principal_id,
        NEW.correction_description, NEW.created_at)
       IS DISTINCT FROM (OLD.user_correction_id, OLD.case_record_id, OLD.corrected_evaluation_id, OLD.correcting_principal_id,
        OLD.correction_description, OLD.created_at)
       OR (OLD.resulting_evaluation_id IS NOT NULL AND NEW.resulting_evaluation_id IS DISTINCT FROM OLD.resulting_evaluation_id) THEN
        RAISE EXCEPTION 'user_correction is append-only' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_user_correction_guard BEFORE UPDATE ON trustlens.user_correction
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_user_correction_guard();
CREATE TRIGGER tr_user_correction_governed_deletion BEFORE DELETE ON trustlens.user_correction
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

-- replay_execution (M-APP): only a COMPLETED evaluation can be replayed; the request is recorded PENDING and its outcome
-- columns are write-once, set together when the replay completes.
CREATE FUNCTION trustlens.tg_replay_execution_requires_completed() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM trustlens.evaluation e WHERE e.evaluation_id = NEW.evaluation_id AND e.status = 'COMPLETED') THEN
        RAISE EXCEPTION 'only a COMPLETED evaluation can be replayed' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.replay_capability_state IS NOT NULL OR NEW.missing_material_kinds IS NOT NULL OR NEW.outcome IS NOT NULL
       OR NEW.replayed_result_digest IS NOT NULL OR NEW.completed_at IS NOT NULL THEN
        RAISE EXCEPTION 'a replay is recorded before its outcome' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_replay_execution_requires_completed BEFORE INSERT ON trustlens.replay_execution
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_replay_execution_requires_completed();

CREATE FUNCTION trustlens.tg_replay_execution_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF (NEW.replay_execution_id, NEW.evaluation_id, NEW.requested_by_principal_id, NEW.reason_ref, NEW.requested_at)
       IS DISTINCT FROM (OLD.replay_execution_id, OLD.evaluation_id, OLD.requested_by_principal_id, OLD.reason_ref, OLD.requested_at) THEN
        RAISE EXCEPTION 'replay_execution identity is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF OLD.completed_at IS NOT NULL THEN
        RAISE EXCEPTION 'a completed replay never changes' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.completed_at IS NULL OR NEW.outcome IS NULL OR NEW.replay_capability_state IS NULL THEN
        RAISE EXCEPTION 'a replay completes with capability, outcome and completion instant together' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER tr_replay_execution_guard BEFORE UPDATE ON trustlens.replay_execution
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_replay_execution_guard();
CREATE TRIGGER tr_replay_execution_governed_deletion BEFORE DELETE ON trustlens.replay_execution
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_governed_deletion_only();

REVOKE ALL ON trustlens.user_correction, trustlens.replay_execution FROM PUBLIC;
REVOKE ALL ON FUNCTION trustlens.tg_user_correction_guard(), trustlens.tg_replay_execution_requires_completed(),
    trustlens.tg_replay_execution_guard() FROM PUBLIC;
GRANT SELECT, INSERT ON trustlens.user_correction, trustlens.replay_execution TO tl_app_runtime;
GRANT UPDATE (replay_capability_state, missing_material_kinds, outcome, replayed_result_digest, completed_at)
    ON trustlens.replay_execution TO tl_app_runtime;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    raise NotImplementedError("Downgrade requires separate review of lossless rollback")
