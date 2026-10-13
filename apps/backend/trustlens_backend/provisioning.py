"""Explicit local role provisioning for the single-tenant MVP (DEC-009). Never runs automatically.

    python -m trustlens_backend.provisioning grant-user   --subject <keycloak user id> --confirm
    python -m trustlens_backend.provisioning revoke-user  --subject <keycloak user id> --confirm

The issuer is always the configured, validated TRUSTLENS_OIDC_ISSUER; only the USER role can be granted here. The
grant is attributed to a dedicated WORKLOAD principal for this procedure (role_assignment.assigned_by_principal_id
is mandatory), with a governed reason reference. Each grant or revocation and its ROLE_ASSIGNED / ROLE_REVOKED audit
event commit in one transaction: if the audit append fails, the role change is rolled back. Connects as
tl_app_runtime; no DDL, no identity-provider admin access.
"""
import argparse
import sys
import uuid

import psycopg

from .config import AuthConfigurationError, AuthSettings, load_environment_files
from .database import DatabaseConfigurationError, DatabaseSettings
from .oidc import MAX_SUBJECT_LENGTH
from .audit import AuditEvent, AuditUnavailable, append
from .principals import APP_RUNTIME_ROLE, SCHEMA

PROVISIONER_ISSUER = "urn:trustlens:workload:local-provisioning"
PROVISIONER_SUBJECT = "role-provisioning-cli"
GRANT_REASON = "DEC-009:S2-LOCAL-ROLE-PROVISIONING"
REVOKE_REASON = "DEC-009:S2-LOCAL-ROLE-REVOCATION"


def _principal(cursor, issuer, subject, kind, create):
    cursor.execute(f"SELECT principal_reference_id::text, principal_kind, status FROM {SCHEMA}.principal_reference"
                   " WHERE external_issuer = %s AND external_subject = %s FOR UPDATE", (issuer, subject))
    row = cursor.fetchone()
    if row is None and create:
        new_id = str(uuid.uuid4())
        cursor.execute(f"INSERT INTO {SCHEMA}.principal_reference (principal_reference_id, principal_kind, external_issuer,"
                       " external_subject, status, created_at) VALUES (%s, %s, %s, %s, 'ACTIVE', now())",
                       (new_id, kind, issuer, subject))
        return new_id, True
    if row is None:
        return None, False
    if row[1] != kind or row[2] != "ACTIVE":
        raise SystemExit("The existing principal is not an active principal of the expected kind; no change made.")
    return row[0], False


def _audit_role(cursor, event_type, provisioner, principal, assignment_id, reason, correlation_id):
    append(cursor, AuditEvent(event_type=event_type, outcome="SUCCEEDED", actor_kind="WORKLOAD", actor_principal_id=provisioner,
                              target_kind="ROLE_ASSIGNMENT", target_id=assignment_id, correlation_id=correlation_id,
                              safe_metadata={"role": "USER", "principal_id": principal, "reason_ref": reason}))


def grant_user(cursor, issuer: str, subject: str, correlation_id: str | None = None) -> str:
    provisioner, _ = _principal(cursor, PROVISIONER_ISSUER, PROVISIONER_SUBJECT, "WORKLOAD", create=True)
    principal, created = _principal(cursor, issuer, subject, "HUMAN", create=True)
    cursor.execute(f"SELECT 1 FROM {SCHEMA}.role_assignment WHERE principal_reference_id = %s AND role = 'USER'"
                   " AND revoked_at IS NULL", (principal,))
    if cursor.fetchone():
        return f"USER role already active for principal {principal}; no change made."
    assignment = str(uuid.uuid4())
    cursor.execute(f"INSERT INTO {SCHEMA}.role_assignment (role_assignment_id, principal_reference_id, role,"
                   " assigned_by_principal_id, assignment_reason_ref, effective_from) VALUES (%s, %s, 'USER', %s, %s, now())",
                   (assignment, principal, provisioner, GRANT_REASON))
    _audit_role(cursor, "ROLE_ASSIGNED", provisioner, principal, assignment, GRANT_REASON, correlation_id or str(uuid.uuid4()))
    return f"USER role granted to {'new' if created else 'existing'} principal {principal}."


def revoke_user(cursor, issuer: str, subject: str, correlation_id: str | None = None) -> str:
    provisioner, _ = _principal(cursor, PROVISIONER_ISSUER, PROVISIONER_SUBJECT, "WORKLOAD", create=True)
    principal, _ = _principal(cursor, issuer, subject, "HUMAN", create=False)
    if principal is None:
        return "No principal exists for that identity; no change made."
    cursor.execute(f"UPDATE {SCHEMA}.role_assignment SET revoked_at = now(), revoked_by_principal_id = %s,"
                   " revocation_reason_ref = %s WHERE principal_reference_id = %s AND role = 'USER' AND revoked_at IS NULL"
                   " RETURNING role_assignment_id::text", (provisioner, REVOKE_REASON, principal))
    revoked = cursor.fetchall()
    if not revoked:
        return "No active USER role; no change made."
    correlation_id = correlation_id or str(uuid.uuid4())
    for (assignment,) in revoked:
        _audit_role(cursor, "ROLE_REVOKED", provisioner, principal, assignment, REVOKE_REASON, correlation_id)
    return f"USER role revoked for principal {principal}."


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit local TrustLens USER-role provisioning (DEC-009)")
    parser.add_argument("action", choices=("grant-user", "revoke-user"))
    parser.add_argument("--subject", required=True, help="Validated subject (Keycloak user ID) of the account")
    parser.add_argument("--confirm", action="store_true", help="Required: confirms this explicit, attributed change")
    args = parser.parse_args(argv)
    if not args.confirm:
        parser.error("--confirm is required")
    subject = args.subject.strip()
    if not 0 < len(subject) <= MAX_SUBJECT_LENGTH or not subject.isprintable():
        parser.error("--subject must be 1-255 printable characters")
    try:
        env = load_environment_files()
        issuer = AuthSettings.from_environment(env).issuer
        database = DatabaseSettings.from_environment(env)
    except (AuthConfigurationError, DatabaseConfigurationError) as error:
        print(f"Provisioning refused: {error}", file=sys.stderr)
        return 2
    if database.user != APP_RUNTIME_ROLE:
        print("Provisioning refused: connect as tl_app_runtime (TRUSTLENS_APP_DB_ENV_FILE).", file=sys.stderr)
        return 2
    try:
        with psycopg.connect(**database.connection_parameters()) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '5s'")
                message = (grant_user if args.action == "grant-user" else revoke_user)(cursor, issuer, subject)
    except (psycopg.Error, AuditUnavailable, ValueError):
        print("Provisioning failed; no change and no audit event were committed. Details suppressed.", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
