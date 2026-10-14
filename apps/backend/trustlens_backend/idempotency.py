"""Durable API idempotency (OPS-001 §§4–5, DATA-001-WP2 api_idempotency_record).

Order: authenticate -> authorize -> claim. The claim is INSERT ... ON CONFLICT DO NOTHING on the full scope
(principal, operation, target path, key digest); only the inserting request executes. On conflict: a different
semantic digest -> IDEMPOTENCY_KEY_REUSED; same digest and IN_PROGRESS with a live lease -> IDEMPOTENCY_IN_PROGRESS;
same digest and terminal -> the stored outcome is replayed without executing again. Completion commits in the same
transaction as the governed effect, fenced by the claim token, so a stale executor's effect rolls back. Only the key's
SHA-256 is stored, never the key, and no response body is cached.

Approved local-development values (T09, sponsor-approved 2026-10-14): active window 24 h, in-progress claim lease 30 s.

Expiry (OPS-001 §5): after active_until a reused key is a NEW request. With candidate addendum P9-S2-ADD-001 (migration
0004) the expired record is marked superseded (write-once, compare-and-swap, never deleted) and a fresh claim is inserted
in the same transaction; at most one record governs a scope (partial unique index WHERE superseded_at IS NULL). On a
0003 database, which cannot represent supersession, an expired key is refused as IDEMPOTENCY_KEY_REUSED and evidence
intake stays disabled.
"""
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta

from knowledge.ai.governance import canonical_json

from .principals import SCHEMA

ACTIVE_WINDOW = timedelta(hours=24)
CLAIM_LEASE = timedelta(seconds=30)
FINGERPRINT_VERSION = "TRUSTLENS_IDEMPOTENCY_REQUEST_FINGERPRINT_V1"
KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{16,255}$")   # client-generated, high-entropy, opaque, header-safe


class KeyReused(Exception):
    pass


class InProgress(Exception):
    pass


class StaleClaim(Exception):
    """The claim was taken over or completed elsewhere; this executor's effect must roll back."""


@dataclass(frozen=True)
class Claim:
    record_id: str
    claim_token: str


@dataclass(frozen=True)
class Replay:
    status: int
    error_code: str | None
    resource_kind: str | None
    resource_id: str | None


def valid_key(key: str | None) -> bool:
    return isinstance(key, str) and KEY_PATTERN.match(key) is not None


def key_digest(key: str) -> str:
    return hashlib.sha256(key.encode("ascii")).hexdigest()


def semantic_digest(operation_id: str, target_scope: str, body: dict) -> str:
    """TRUSTLENS_IDEMPOTENCY_REQUEST_FINGERPRINT_V1: no transport headers, no key, no request id."""
    return hashlib.sha256(canonical_json({"operation_id": operation_id, "target_resource_scope": target_scope,
                                          "body": body, "headers": {}}).encode("utf-8")).hexdigest()


_INSERT = (f"INSERT INTO {SCHEMA}.api_idempotency_record (api_idempotency_record_id, principal_reference_id, operation_id,"
           " target_resource_scope, idempotency_key_digest, request_fingerprint_version, request_semantic_digest,"
           " execution_state, claim_token, in_progress_lease_until, created_at, active_until)"
           " VALUES (%s, %s, %s, %s, %s, %s, %s, 'IN_PROGRESS', %s, now() + %s, now(), now() + %s)")
# No conflict target: the scope is unique through a constraint on 0003 and a partial unique index on 0004.
_ON_CONFLICT = " ON CONFLICT DO NOTHING"


def claim(connection, principal_id: str, operation_id: str, target_scope: str, key: str, digest: str,
          supersession: bool = False) -> Claim | Replay:
    """Claim the scope or resolve the conflict, in its own short transaction (the claim must be visible to others).
    Times are the database's now(), so expiry and leases never depend on the application clock."""
    token = str(uuid.uuid4())
    scope = (principal_id, operation_id, target_scope, key_digest(key))
    insert = _INSERT + _ON_CONFLICT + " RETURNING api_idempotency_record_id::text"
    insert_args = (str(uuid.uuid4()), *scope, FINGERPRINT_VERSION, digest, token, CLAIM_LEASE, ACTIVE_WINDOW)
    with connection.transaction(), connection.cursor() as cur:
        cur.execute(insert, insert_args)
        inserted = cur.fetchone()
        if inserted:
            return Claim(inserted[0], token)
        cur.execute(
            f"SELECT api_idempotency_record_id::text, request_semantic_digest, execution_state, claim_token::text,"
            " coalesce(in_progress_lease_until > now(), false), active_until <= now(), outcome_http_status,"
            f" outcome_error_code, outcome_resource_kind, outcome_resource_id::text FROM {SCHEMA}.api_idempotency_record"
            " WHERE principal_reference_id = %s AND operation_id = %s AND target_resource_scope = %s"
            " AND idempotency_key_digest = %s" + (" AND superseded_at IS NULL" if supersession else ""), scope)
        row = cur.fetchone()
        if row is None:
            raise InProgress()                       # vanished between statements: let the client retry
        record_id, stored_digest, state, old_token, lease_live, expired, status, error, kind, resource = row
        if expired:
            if not supersession:
                raise KeyReused()                    # 0003 schema: supersession not representable
            cur.execute(f"UPDATE {SCHEMA}.api_idempotency_record SET superseded_at = now()"
                        " WHERE api_idempotency_record_id = %s AND superseded_at IS NULL AND active_until <= now()"
                        " RETURNING api_idempotency_record_id", (record_id,))
            if cur.fetchone() is None:
                raise InProgress()                   # another request superseded it first
            cur.execute(insert, (str(uuid.uuid4()), *insert_args[1:]))
            fresh = cur.fetchone()
            if fresh is None:
                raise InProgress()
            return Claim(fresh[0], token)            # a new request: the expired outcome is never replayed
        if stored_digest != digest:
            raise KeyReused()
        if state in ("COMPLETED", "FAILED_TERMINAL"):
            return Replay(status, error, kind, resource)
        if state == "IN_PROGRESS" and lease_live:
            raise InProgress()
        cur.execute(                                 # RELEASED, or IN_PROGRESS with an expired lease: compare-and-swap
            f"UPDATE {SCHEMA}.api_idempotency_record SET execution_state = 'IN_PROGRESS', claim_token = %s,"
            " in_progress_lease_until = now() + %s, terminal_at = NULL, outcome_http_status = NULL, outcome_error_code = NULL,"
            " outcome_resource_kind = NULL, outcome_resource_id = NULL"
            " WHERE api_idempotency_record_id = %s AND claim_token = %s RETURNING api_idempotency_record_id::text",
            (token, CLAIM_LEASE, record_id, old_token))
        if cur.fetchone() is None:
            raise InProgress()
        return Claim(record_id, token)


def _finish(cursor, claim_: Claim, state: str, status: int, error_code: str | None, kind: str | None, resource_id: str | None):
    cursor.execute(
        f"UPDATE {SCHEMA}.api_idempotency_record SET execution_state = %s, terminal_at = now(), in_progress_lease_until = NULL,"
        " outcome_http_status = %s, outcome_error_code = %s, outcome_resource_kind = %s, outcome_resource_id = %s"
        " WHERE api_idempotency_record_id = %s AND claim_token = %s AND execution_state = 'IN_PROGRESS'",
        (state, status, error_code, kind, resource_id, claim_.record_id, claim_.claim_token))
    if cursor.rowcount != 1:
        raise StaleClaim()


def complete(cursor, claim_: Claim, status: int, kind: str, resource_id: str):
    """Inside the effect's transaction: COMPLETED, fenced by the claim token."""
    _finish(cursor, claim_, "COMPLETED", status, None, kind, resource_id)


def fail_terminal(cursor, claim_: Claim, status: int, error_code: str):
    """A deterministic business refusal (e.g. STATE_CONFLICT) is a terminal outcome and replays identically."""
    _finish(cursor, claim_, "FAILED_TERMINAL", status, error_code, None, None)


def release(connection, claim_: Claim, status: int, error_code: str):
    """Transient failure: RELEASED, so the same request may be retried (nothing was committed)."""
    try:
        with connection.transaction(), connection.cursor() as cur:
            _finish(cur, claim_, "RELEASED", status, error_code, None, None)
    except Exception:               # best effort: an unreleased claim simply expires with its 30 s lease
        pass
