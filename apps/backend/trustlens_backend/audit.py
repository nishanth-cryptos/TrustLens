"""Governed append-only audit chain (DATA-001-WP2 §15, ADR-0010 §9, ARCH-004 §9.2).

event_hash = SHA-256(TRUSTLENS_CANONICAL_JSON_V1(event_without_hash) || previous_event_hash), where event_without_hash
is every audit_event column except event_hash, UUIDs as lowercase text, instants as RFC 3339 UTC with microseconds.
Appends lock the chain head in the caller's transaction, so an operation and its required audit commit or fail
together. Events carry opaque identifiers and categorical values only: never tokens, codes, passwords, subjects,
issuers, usernames or browser details (safe_metadata is validated against a per-event allowlist).
"""
import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from knowledge.ai.governance import canonical_json

from .database import DatabaseSettings
from .principals import APP_RUNTIME_ROLE, SCHEMA

CHAIN_ID = "deployment"
EVENT_SCHEMA_VERSION = "1"
GENESIS_HASH = "0" * 64
_CATEGORY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

# Per event schema version 1: the only safe_metadata keys each event may carry, and the kind of value allowed.
SAFE_METADATA = {
    "AUTHENTICATION_SUCCEEDED": {"method": "category"},
    "AUTHENTICATION_FAILED": {"method": "category", "reason": "category"},
    "AUTHORIZATION_DENIED": {"reason": "category", "operation": "category"},
    "CASE_CREATED": {},
    "EVIDENCE_RECEIVED": {},
    "EVIDENCE_STORED": {"stage": "category"},
    "INTEGRITY_FAILURE": {"stage": "category"},
    # S4: the server-side read of original bytes for deterministic extraction (API-001 §12 audits every content read);
    # S5: every DetectionResult read (getDetectionResult audit REQUIRED).
    "EVIDENCE_ACCESSED": {"stage": "category"},
    # S5 governed evaluation (createEvaluations audit EVALUATION_STARTED; completion protocol audit rows).
    "EVALUATION_STARTED": {"origin": "category"},
    "EVALUATION_COMPLETED": {},
    "EVALUATION_FAILED": {"reason": "category"},
    "RESULT_PERSISTED": {"result_digest": "sha256"},
    "ROLE_ASSIGNED": {"role": "category", "principal_id": "uuid", "reason_ref": "reference"},
    "ROLE_REVOKED": {"role": "category", "principal_id": "uuid", "reason_ref": "reference"},
    # S3 knowledge activation (ADR-0013 Decision 14): exact digests, deployment, actor (event column), outcome, reason.
    "KNOWLEDGE_ACTIVATED": {"content_digest": "sha256", "previous_content_digest": "sha256", "activation_id": "uuid",
                            "deployment": "deployment", "governance_change_ref": "reference", "authenticity": "category"},
    "KNOWLEDGE_ACTIVATION_REJECTED": {"content_digest": "sha256", "deployment": "deployment", "reason": "category",
                                      "governance_change_ref": "reference"},
}
_REFERENCE = re.compile(r"^[A-Z0-9][A-Z0-9:_-]{0,79}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DEPLOYMENT = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class AuditUnavailable(RuntimeError):
    """A required audit append did not complete; the operation that needed it must fail closed."""


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    outcome: str
    actor_kind: str
    target_kind: str
    correlation_id: str
    actor_principal_id: str | None = None
    target_id: str | None = None
    safe_metadata: dict | None = field(default=None)
    occurred_at: datetime | None = None
    case_record_id: str | None = None
    evidence_item_id: str | None = None
    evaluation_id: str | None = None
    bundle_content_digest: str | None = None


def _instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _validate(event: AuditEvent) -> None:
    allowed = SAFE_METADATA.get(event.event_type)
    if allowed is None:
        raise ValueError("event type not enabled for this audit schema version")
    for key, value in (event.safe_metadata or {}).items():
        kind = allowed.get(key)
        ok = (kind == "category" and isinstance(value, str) and _CATEGORY.match(value)) or \
             (kind == "uuid" and isinstance(value, str) and _UUID.match(value)) or \
             (kind == "reference" and isinstance(value, str) and _REFERENCE.match(value)) or \
             (kind == "sha256" and isinstance(value, str) and _SHA256.match(value)) or \
             (kind == "deployment" and isinstance(value, str) and _DEPLOYMENT.match(value))
        if not ok:
            raise ValueError("safe_metadata key or value is not permitted")
    for ref in (event.actor_principal_id, event.target_id, event.case_record_id, event.evidence_item_id, event.evaluation_id):
        if ref is not None and not _UUID.match(ref):
            raise ValueError("references must be lowercase UUIDv4 text")
    if event.bundle_content_digest is not None and not _SHA256.match(event.bundle_content_digest):
        raise ValueError("bundle_content_digest must be a SHA-256 hex digest")
    if not isinstance(event.correlation_id, str) or not _UUID.match(event.correlation_id):
        raise ValueError("correlation id must be a request or run UUID")


def event_hash(row: dict) -> str:
    """SHA-256(canonical JSON of the row without event_hash || previous_event_hash), lowercase hex."""
    body = {k: v for k, v in row.items() if k != "event_hash"}
    return hashlib.sha256(canonical_json(body).encode("utf-8") + row["previous_event_hash"].encode("ascii")).hexdigest()


def append(cursor, event: AuditEvent, chain_id: str = CHAIN_ID) -> dict:
    """Append one event inside the caller's transaction (head locked until it commits). Returns the stored row."""
    _validate(event)
    cursor.execute(f"SELECT last_chain_sequence, last_event_hash FROM {SCHEMA}.audit_chain_head"
                   " WHERE chain_id = %s FOR UPDATE", (chain_id,))
    head = cursor.fetchone()
    if head is None:
        raise AuditUnavailable("audit chain head missing")
    now = datetime.now(timezone.utc)
    row = {
        "audit_event_id": str(uuid.uuid4()), "chain_id": chain_id, "chain_sequence": head[0] + 1,
        "event_schema_version": EVENT_SCHEMA_VERSION, "event_type": event.event_type,
        "occurred_at": _instant(event.occurred_at or now), "recorded_at": _instant(now),
        "actor_principal_id": event.actor_principal_id, "actor_kind": event.actor_kind, "outcome": event.outcome,
        "target_kind": event.target_kind, "target_id": event.target_id, "case_record_id": event.case_record_id, "evaluation_id": event.evaluation_id,
        "evidence_item_id": event.evidence_item_id, "bundle_content_digest": event.bundle_content_digest, "correlation_id": event.correlation_id,
        "safe_metadata": dict(event.safe_metadata) if event.safe_metadata else None, "previous_event_hash": head[1],
    }
    row["event_hash"] = event_hash(row)
    columns = list(row)
    values = [Jsonb(row[c]) if c == "safe_metadata" and row[c] is not None else row[c] for c in columns]
    cursor.execute(f"INSERT INTO {SCHEMA}.audit_event ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})", values)
    cursor.execute(f"UPDATE {SCHEMA}.audit_chain_head SET last_chain_sequence = %s, last_event_hash = %s, updated_at = %s"
                   " WHERE chain_id = %s", (row["chain_sequence"], row["event_hash"], now, chain_id))
    return row


def stored_rows(cursor, chain_id: str = CHAIN_ID) -> list[dict]:
    cursor.execute(f"SELECT audit_event_id::text, chain_id, chain_sequence, event_schema_version, event_type, occurred_at,"
                   " recorded_at, actor_principal_id::text, actor_kind, outcome, target_kind, target_id::text,"
                   " case_record_id::text, evaluation_id::text, evidence_item_id::text, bundle_content_digest,"
                   " correlation_id, safe_metadata, previous_event_hash, event_hash"
                   f" FROM {SCHEMA}.audit_event WHERE chain_id = %s ORDER BY chain_sequence", (chain_id,))
    names = [d.name for d in cursor.description]
    rows = []
    for values in cursor.fetchall():
        row = dict(zip(names, values))
        row["occurred_at"], row["recorded_at"] = _instant(row["occurred_at"]), _instant(row["recorded_at"])
        rows.append(row)
    return rows


def verify_rows(rows: list[dict], head: tuple | None) -> int:
    """Pure check of one consistent snapshot: genesis, gap-free order, every link and hash, and the head.
    Returns the verified length or raises ValueError at the first break."""
    previous, expected_sequence = GENESIS_HASH, 1
    for row in rows:
        if row["chain_sequence"] != expected_sequence or row["previous_event_hash"] != previous or event_hash(row) != row["event_hash"]:
            raise ValueError(f"audit chain broken at sequence {row['chain_sequence']}")
        previous, expected_sequence = row["event_hash"], expected_sequence + 1
    if head != (len(rows), previous):
        raise ValueError("audit chain head does not match the last event")
    return len(rows)


def verify_chain(cursor, chain_id: str = CHAIN_ID) -> int:
    """Verify the chain from ONE snapshot (round-1 review finding 3).

    Must start a fresh, explicit transaction: the first statement fixes it as READ ONLY + REPEATABLE READ, so the
    event rows and the head come from the same snapshot even while other sessions append and commit. The caller
    ends the transaction (rollback)."""
    connection = cursor.connection
    if connection.autocommit or connection.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise RuntimeError("verify_chain needs a fresh explicit transaction (autocommit off, nothing executed yet)")
    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
    rows = stored_rows(cursor, chain_id)
    cursor.execute(f"SELECT last_chain_sequence, last_event_hash FROM {SCHEMA}.audit_chain_head WHERE chain_id = %s", (chain_id,))
    return verify_rows(rows, cursor.fetchone())


class PostgresAuditSink:
    """Request-path appends, each in its own short transaction, as tl_app_runtime only."""

    def __init__(self, settings: DatabaseSettings):
        if settings.user != APP_RUNTIME_ROLE:
            raise AuditUnavailable("The application must connect as tl_app_runtime")
        self._settings = settings

    def record(self, event: AuditEvent) -> None:
        try:
            with psycopg.connect(**self._settings.connection_parameters()) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '5s'")
                    append(cursor, event)
        except (psycopg.Error, ValueError):
            raise AuditUnavailable("audit append failed") from None


def verify_main() -> int:
    """python -m trustlens_backend.audit — read-only chain verification with the application database credentials."""
    from .config import load_environment_files
    try:
        settings = DatabaseSettings.from_environment(load_environment_files())
        with psycopg.connect(**settings.connection_parameters()) as connection:
            try:
                with connection.cursor() as cursor:
                    count = verify_chain(cursor)
            finally:
                connection.rollback()                       # read-only: nothing to commit
    except (psycopg.Error, ValueError) as error:
        print(f"Audit chain verification FAILED: {error}")
        return 1
    print(f"Audit chain verification PASS: {count} event(s), hashes and links intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(verify_main())
