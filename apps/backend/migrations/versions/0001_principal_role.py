"""S2 trusted principal and role assignment (DATA-001-WP2 principal_reference, role_assignment).

Revision: 0001_principal_role
Contract reference and change class: contracts/postgresql/schema-v1.json tables principal_reference and
role_assignment (columns, CHECKs, unique constraints, RESTRICT foreign keys, mutable/write-once columns, transition
guards) and database_roles tl_app_runtime privileges. Change class: ADDITIVE (new tables in an empty schema).
Requires the bootstrap in migrations/bootstrap/s2_roles_and_schema.sql (roles + schema owned by tl_schema_migrator).
No session table: the accepted contract has none (sessions are server-side in process memory for S2).
"""
from alembic import op

revision = "0001_principal_role"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
CREATE TABLE trustlens.principal_reference (
    principal_reference_id uuid NOT NULL,
    principal_kind text NOT NULL,
    external_issuer text,
    external_subject text,
    status text NOT NULL,
    created_at timestamptz NOT NULL,
    deactivated_at timestamptz,
    CONSTRAINT pk_principal_reference PRIMARY KEY (principal_reference_id),
    CONSTRAINT uq_principal_reference_external_identity UNIQUE (external_issuer, external_subject),
    CONSTRAINT ck_principal_reference_principal_kind CHECK (principal_kind IN ('HUMAN', 'WORKLOAD')),
    CONSTRAINT ck_principal_reference_status CHECK (status IN ('ACTIVE', 'DEACTIVATED', 'MINIMIZED')),
    CONSTRAINT ck_principal_reference_deactivation CHECK ((status = 'ACTIVE') = (deactivated_at IS NULL)),
    CONSTRAINT ck_principal_reference_identity_present
        CHECK (status = 'MINIMIZED' OR (external_issuer IS NOT NULL AND external_subject IS NOT NULL))
);

CREATE TABLE trustlens.role_assignment (
    role_assignment_id uuid NOT NULL,
    principal_reference_id uuid NOT NULL,
    role text NOT NULL,
    assigned_by_principal_id uuid NOT NULL,
    assignment_reason_ref text NOT NULL,
    effective_from timestamptz NOT NULL,
    revoked_at timestamptz,
    revoked_by_principal_id uuid,
    revocation_reason_ref text,
    CONSTRAINT pk_role_assignment PRIMARY KEY (role_assignment_id),
    CONSTRAINT fk_role_assignment_principal FOREIGN KEY (principal_reference_id)
        REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_role_assignment_assigned_by FOREIGN KEY (assigned_by_principal_id)
        REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_role_assignment_revoked_by FOREIGN KEY (revoked_by_principal_id)
        REFERENCES trustlens.principal_reference (principal_reference_id) ON DELETE RESTRICT,
    CONSTRAINT ck_role_assignment_role
        CHECK (role IN ('USER', 'ANALYST', 'KNOWLEDGE_EDITOR', 'KNOWLEDGE_APPROVER', 'ADMINISTRATOR')),
    CONSTRAINT ck_role_assignment_revocation_complete CHECK ((revoked_at IS NULL) = (revoked_by_principal_id IS NULL))
);

CREATE UNIQUE INDEX uq_role_assignment_active
    ON trustlens.role_assignment (principal_reference_id, role) WHERE revoked_at IS NULL;

-- principal_reference (M-OPS, GOVERNED_MINIMIZATION_ONLY): only declared mutable columns change; the external identity
-- may change only to NULL together with status MINIMIZED, by tl_deletion_executor; rows are never deleted.
CREATE FUNCTION trustlens.tg_principal_reference_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'principal_reference rows are never deleted' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.principal_reference_id IS DISTINCT FROM OLD.principal_reference_id
       OR NEW.principal_kind IS DISTINCT FROM OLD.principal_kind
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'principal_reference column is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (NEW.external_issuer IS DISTINCT FROM OLD.external_issuer OR NEW.external_subject IS DISTINCT FROM OLD.external_subject)
       AND NOT (NEW.external_issuer IS NULL AND NEW.external_subject IS NULL AND NEW.status = 'MINIMIZED'
                AND current_user = 'tl_deletion_executor') THEN
        RAISE EXCEPTION 'external identity changes only by governed minimization' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER tr_principal_reference_guard
    BEFORE UPDATE OR DELETE ON trustlens.principal_reference
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_principal_reference_guard();

-- role_assignment (M-APP, delete NEVER): no mutable columns; revocation columns are write-once (NULL -> value).
CREATE FUNCTION trustlens.tg_role_assignment_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'role_assignment rows are never deleted' USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.role_assignment_id IS DISTINCT FROM OLD.role_assignment_id
       OR NEW.principal_reference_id IS DISTINCT FROM OLD.principal_reference_id
       OR NEW.role IS DISTINCT FROM OLD.role
       OR NEW.assigned_by_principal_id IS DISTINCT FROM OLD.assigned_by_principal_id
       OR NEW.assignment_reason_ref IS DISTINCT FROM OLD.assignment_reason_ref
       OR NEW.effective_from IS DISTINCT FROM OLD.effective_from THEN
        RAISE EXCEPTION 'role_assignment column is immutable' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at)
       OR (OLD.revoked_by_principal_id IS NOT NULL AND NEW.revoked_by_principal_id IS DISTINCT FROM OLD.revoked_by_principal_id)
       OR (OLD.revocation_reason_ref IS NOT NULL AND NEW.revocation_reason_ref IS DISTINCT FROM OLD.revocation_reason_ref) THEN
        RAISE EXCEPTION 'role_assignment revocation is write-once' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER tr_role_assignment_guard
    BEFORE UPDATE OR DELETE ON trustlens.role_assignment
    FOR EACH ROW EXECUTE FUNCTION trustlens.tg_role_assignment_guard();

-- Least privilege (DATA-001-WP2 database_roles): tl_app_runtime gets SELECT/INSERT and column-level UPDATE only on
-- declared mutable/write-once columns; no DELETE, no DDL. Nothing is granted to PUBLIC.
REVOKE ALL ON trustlens.principal_reference, trustlens.role_assignment FROM PUBLIC;
REVOKE ALL ON FUNCTION trustlens.tg_principal_reference_guard(), trustlens.tg_role_assignment_guard() FROM PUBLIC;
GRANT SELECT, INSERT ON trustlens.principal_reference, trustlens.role_assignment TO tl_app_runtime;
GRANT UPDATE (status, deactivated_at, external_issuer, external_subject) ON trustlens.principal_reference TO tl_app_runtime;
GRANT UPDATE (revoked_at, revoked_by_principal_id, revocation_reason_ref) ON trustlens.role_assignment TO tl_app_runtime;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    raise NotImplementedError("Downgrade requires separate review of lossless rollback (role history is never deleted)")
