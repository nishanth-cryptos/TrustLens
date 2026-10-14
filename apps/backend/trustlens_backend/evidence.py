"""S2 evidence intake: createEvidenceUpload, putEvidenceContent, finalizeEvidence, getEvidenceMetadata, listEvidence.

Implements API-001 §12 against CANDIDATE addendum P9-S2-ADD-001 (migration 0004). On a database without 0004, or without
the local key-encryption key, every evidence operation answers 503 DEPENDENCY_UNAVAILABLE: nothing is enabled against an
incompatible schema and there is no plaintext fallback.

- Initiate stores only declared values in evidence_upload_intent; no digest is invented.
- The PUT body is the evidence: the server computes SHA-256 over the exact bytes (TL_EVIDENCE_BYTES_V1) and checks the
  declared length, the advisory client digest, UTF-8 text media and the 64 KiB bound. It creates the evidence_item, then
  CONTENT_PENDING, an encrypted content-store write, and CONTENT_STORED with the EVIDENCE_STORED audit.
- Finalize (202) re-reads, decrypts and verifies digest and length, then INTEGRITY_VERIFIED -> FINALIZED with the custody
  audit in one transaction. A failure means INTEGRITY_FAILED, never FINALIZED.
- No PostgreSQL transaction spans the content store. Every step is a recorded state that an identical retry can resume.
"""
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import psycopg
from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool

from . import idempotency
from .audit import AuditEvent, append as audit_append
from .auth import api_error, current_principal
from .capabilities import evidence_schema_active
from .cases import (_Unavailable, _audit_denial, _connect, _encode_cursor, _idempotent_error, _instant, _json, _json_body,
                    _page_params, _retention_reference, _uuid, _visible_case, is_too_large, read_bounded, read_json_object)
from .content_store import KEK_VERSION_REF, ContentStoreUnavailable, IntegrityFailure, LocalEncryptedContentStore
from .principals import SCHEMA

OPERATIONS = {
    "createEvidenceUpload": {"method": "POST", "path": "/api/v1/submissions/{submission_id}/evidence", "roles": ("USER",),
                             "resource_authorization": "CASE_OWNER"},
    "putEvidenceContent": {"method": "PUT", "path": "/api/v1/evidence/{evidence_id}/content", "roles": ("USER",),
                           "resource_authorization": "CASE_OWNER"},
    "finalizeEvidence": {"method": "POST", "path": "/api/v1/evidence/{evidence_id}/finalize", "roles": ("USER",),
                         "resource_authorization": "CASE_OWNER"},
    "getEvidenceMetadata": {"method": "GET", "path": "/api/v1/evidence/{evidence_id}", "roles": ("USER", "ANALYST"),
                            "resource_authorization": "CASE_ACCESS"},
    "listEvidence": {"method": "GET", "path": "/api/v1/submissions/{submission_id}/evidence", "roles": ("USER", "ANALYST"),
                     "resource_authorization": "CASE_ACCESS"},
}
# api_upload_state.maps_from (api-v1.json): internal cross-store state -> external upload state.
UPLOAD_STATE = {"RECEIVED": "AWAITING_CONTENT", "CONTENT_PENDING": "PROCESSING", "CONTENT_STORED": "PROCESSING",
                "INTEGRITY_VERIFIED": "PROCESSING", "FINALIZED": "FINALIZED", "FAILED_RETRYABLE": "PROCESSING",
                "FAILED_TERMINAL": "REJECTED", "ORPHAN_DETECTED": "REJECTED", "INTEGRITY_FAILED": "REJECTED",
                "QUARANTINED": "REJECTED", "DELETION_PENDING": "DELETION_PENDING", "DELETED": "DELETED"}
API_UPLOAD_STATES = ("AWAITING_CONTENT", "PROCESSING", "FINALIZED", "REJECTED", "DELETION_PENDING", "DELETED")
ARTIFACT_KINDS = ("TEXT_BODY", "URL", "EMAIL_SOURCE", "IMAGE", "DOCUMENT", "OTHER")
# Approved local profile (T09, 2026-10-14): text only, 64 KiB, at most 3 content-write attempts, backoff 1-30 s.
SUPPORTED_ARTIFACT_KINDS = ("TEXT_BODY",)
VERIFIED_MEDIA_TYPE = "text/plain; charset=utf-8"
MAX_EVIDENCE_BYTES = 64 * 1024
MAX_WRITE_ATTEMPTS = 3
WRITE_LEASE = timedelta(seconds=30)          # approved 30 s lease: a content-write attempt older than this may be taken over
BYTE_DEFINITION = "TL_EVIDENCE_BYTES_V1"
COMPONENT_REF = "trustlens-backend/s2-evidence-intake"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class _Refused(Exception):
    def __init__(self, response):
        super().__init__()
        self.response = response


def supported_media(value) -> bool:
    """Exactly text/plain with charset=utf-8 (case-insensitive, optional quotes); nothing else in S2."""
    if not isinstance(value, str) or len(value) > 255:
        return False
    parts = [p.strip() for p in value.split(";")]
    if parts[0].lower() != "text/plain" or len(parts) != 2:
        return False
    name, _, charset = parts[1].partition("=")
    return name.strip().lower() == "charset" and charset.strip().strip('"').lower() == "utf-8"


def backoff_seconds(attempt: int) -> int:
    return max(1, min(30, 2 ** (attempt - 1)))


def get_store(runtime):
    """The encrypted content store, built lazily; None (fail closed) when the key or directory is unavailable."""
    if runtime.evidence_store is not None:
        return runtime.evidence_store
    if not runtime.evidence_store_paths:
        return None
    try:
        runtime.evidence_store = LocalEncryptedContentStore(*runtime.evidence_store_paths)
    except ContentStoreUnavailable:
        return None
    return runtime.evidence_store


_EVIDENCE_COLUMNS = ("i.evidence_upload_intent_id::text, i.submission_id::text, i.artifact_kind, e.content_state,"
                     " e.content_sha256, e.byte_length, i.declared_media_type, e.verified_media_type, i.display_filename,"
                     " i.created_at, e.finalized_at")
_UPLOAD_STATE_SQL = ("CASE WHEN e.evidence_item_id IS NULL THEN 'AWAITING_CONTENT' "
                     + " ".join(f"WHEN e.content_state = '{k}' THEN '{v}'" for k, v in UPLOAD_STATE.items()) + " END")


def _view(row) -> dict:
    evidence_id, submission_id, kind, state, digest, length, declared, verified, filename, created, finalized = row
    return {"evidence_id": evidence_id, "submission_id": submission_id, "artifact_kind": kind,
            "upload_state": UPLOAD_STATE[state] if state else "AWAITING_CONTENT", "content_sha256": digest,
            "byte_length": length, "declared_media_type": declared, "verified_media_type": verified,
            "display_filename": filename, "ingested_at": _instant(created), "finalized_at": _instant(finalized),
            "content_link": None,       # getEvidenceContent is not part of this slice
            "links": {"self": f"/api/v1/evidence/{evidence_id}", "related": {"submission": f"/api/v1/submissions/{submission_id}"}}}


def _evidence_row(cur, evidence_id):
    cur.execute(f"SELECT {_EVIDENCE_COLUMNS} FROM {SCHEMA}.evidence_upload_intent i LEFT JOIN {SCHEMA}.evidence_item e"
                " ON e.evidence_item_id = i.evidence_upload_intent_id WHERE i.evidence_upload_intent_id = %s", (evidence_id,))
    return cur.fetchone()


def _case_of_submission(cur, submission_id):
    cur.execute(f"SELECT case_record_id::text FROM {SCHEMA}.submission WHERE submission_id = %s", (submission_id,))
    row = cur.fetchone()
    return row[0] if row else None


def _case_of_evidence(cur, evidence_id):
    cur.execute(f"SELECT s.case_record_id::text FROM {SCHEMA}.evidence_upload_intent i JOIN {SCHEMA}.submission s"
                " ON s.submission_id = i.submission_id WHERE i.evidence_upload_intent_id = %s", (evidence_id,))
    row = cur.fetchone()
    return row[0] if row else None


def _authorize(request, runtime, principal, cur, operation_id, case_id, needs_content=False):
    """Masked 404 without visibility; 403 for a visible case without role, ownership or content permission."""
    spec = OPERATIONS[operation_id]
    case = _visible_case(cur, case_id, principal.principal_reference_id) if case_id else None
    write = spec["method"] != "GET"
    if case is None:
        if write and case_id:
            _audit_denial(runtime, request, principal, case_id, "NO_CASE_ACCESS", operation_id)
        raise _Refused(api_error(request, "NOT_FOUND"))
    if (not set(principal.roles) & set(spec["roles"]) or (spec["resource_authorization"] == "CASE_OWNER" and case[6] != "OWNER")
            or (needs_content and not case[7])):
        if write:
            _audit_denial(runtime, request, principal, case_id, "ROLE_OWNERSHIP_OR_CONTENT_PERMISSION_REQUIRED", operation_id)
        raise _Refused(api_error(request, "FORBIDDEN"))
    return case


def _open(request, runtime):
    """Connection with the 0004 schema active, or a 503 refusal (never enabled against a 0003 database)."""
    try:
        connection = _connect(runtime)
    except _Unavailable:
        raise _Refused(api_error(request, "DEPENDENCY_UNAVAILABLE")) from None
    try:
        if not evidence_schema_active(connection):
            connection.close()
            raise _Refused(api_error(request, "DEPENDENCY_UNAVAILABLE"))
    except psycopg.Error:
        connection.close()
        raise _Refused(api_error(request, "DEPENDENCY_UNAVAILABLE")) from None
    return connection


def _audit_evidence(cur, request, principal, case_id, evidence_id, event_type, stage=None, outcome="SUCCEEDED"):
    audit_append(cur, AuditEvent(event_type=event_type, outcome=outcome, actor_kind="HUMAN",
                                 actor_principal_id=principal.principal_reference_id, target_kind="EVIDENCE_ITEM",
                                 target_id=evidence_id, case_record_id=case_id, evidence_item_id=evidence_id,
                                 correlation_id=request.state.request_id, safe_metadata={"stage": stage} if stage else None))


# ---------------------------------------------------------------- createEvidenceUpload
def _validate_upload_request(body) -> tuple[dict | None, object]:
    """Returns (values, None) or (None, (error_code, field_errors)). Values are never echoed in errors."""
    if not isinstance(body, dict):
        return None, ("INVALID_REQUEST", [{"field": "body", "code": "MALFORMED", "message": "Body must be a JSON object."}])
    allowed = {"artifact_kind", "declared_media_type", "declared_byte_length", "display_filename", "capture_declared_at",
               "client_declared_sha256"}
    errors = [{"field": k, "code": "UNKNOWN_FIELD", "message": "Field is not accepted."} for k in body if k not in allowed]
    errors += [{"field": k, "code": "REQUIRED", "message": "Field is required."}
               for k in ("artifact_kind", "declared_media_type", "declared_byte_length") if k not in body]
    if errors:
        return None, ("INVALID_REQUEST", errors)
    if body["artifact_kind"] not in ARTIFACT_KINDS:
        return None, ("INVALID_REQUEST", [{"field": "artifact_kind", "code": "INVALID_VALUE", "message": "Value is not in the accepted vocabulary."}])
    length = body["declared_byte_length"]
    if not isinstance(length, int) or isinstance(length, bool) or length < 1:
        return None, ("INVALID_REQUEST", [{"field": "declared_byte_length", "code": "INVALID_VALUE", "message": "Use a positive integer."}])
    checks = [("display_filename", lambda v: isinstance(v, str) and 0 < len(v) <= 255 and v.isprintable()),
              ("client_declared_sha256", lambda v: isinstance(v, str) and _SHA256.match(v) is not None)]
    for field, ok in checks:
        if field in body and body[field] is not None and not ok(body[field]):
            return None, ("INVALID_REQUEST", [{"field": field, "code": "INVALID_VALUE", "message": "Value is not accepted."}])
    capture = None
    if body.get("capture_declared_at") is not None:
        try:
            capture = datetime.fromisoformat(str(body["capture_declared_at"]).replace("Z", "+00:00"))
            if capture.tzinfo is None:
                raise ValueError
        except ValueError:
            return None, ("INVALID_REQUEST", [{"field": "capture_declared_at", "code": "INVALID_TIMESTAMP", "message": "Use RFC 3339 with offset."}])
    if body["artifact_kind"] not in SUPPORTED_ARTIFACT_KINDS or not supported_media(body["declared_media_type"]):
        return None, ("UNSUPPORTED_MEDIA_TYPE", None)
    if length > MAX_EVIDENCE_BYTES:
        return None, ("PAYLOAD_TOO_LARGE", None)
    return dict(body, capture_declared_at=capture), None


async def create_evidence_upload(request: Request):
    runtime, principal, error = current_principal(request, "CREATEEVIDENCEUPLOAD")
    if error is not None:
        return error
    submission_id = _uuid(request.path_params["submission_id"])
    if submission_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "submission_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    key = request.headers.get("idempotency-key")
    if not idempotency.valid_key(key):
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "Idempotency-Key", "code": "REQUIRED", "message": "Send a high-entropy key (16-255 URL-safe characters)."}])
    body, problems = await read_json_object(request)          # field rules: _validate_upload_request
    if is_too_large(problems):
        return api_error(request, "PAYLOAD_TOO_LARGE")          # accepted for createEvidenceUpload
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_create_evidence_upload, request, runtime, principal, submission_id, key, body)


def _create_evidence_upload(request, runtime, principal, submission_id, key, body):
    scope = f"/api/v1/submissions/{submission_id}/evidence"
    try:
        connection = _open(request, runtime)
    except _Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                case_id = _case_of_submission(cur, submission_id)
                case = _authorize(request, runtime, principal, cur, "createEvidenceUpload", case_id)
            values, problem = _validate_upload_request(body)
            if problem:
                return api_error(request, problem[0], field_errors=problem[1])
            if get_store(runtime) is None:
                return api_error(request, "DEPENDENCY_UNAVAILABLE")
            outcome = idempotency.claim(connection, principal.principal_reference_id, "createEvidenceUpload", scope, key,
                                        idempotency.semantic_digest("createEvidenceUpload", scope, body), supersession=True)
        except _Refused as refused:
            return refused.response
        except (idempotency.KeyReused, idempotency.InProgress) as e:
            return _idempotent_error(request, e)
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if isinstance(outcome, idempotency.Replay):
            return _replay(request, connection, outcome)
        evidence_id = str(uuid.uuid4())
        try:
            with connection.transaction(), connection.cursor() as cur:
                if case[1] != "OPEN":
                    idempotency.fail_terminal(cur, outcome, 409, "STATE_CONFLICT")
                    conflict = True
                else:
                    conflict = False
                    retention, ingest_key = _retention_reference(cur), str(uuid.uuid4())
                    cur.execute(f"INSERT INTO {SCHEMA}.evidence_upload_intent (evidence_upload_intent_id, submission_id,"
                                " initiated_by_principal_id, artifact_kind, declared_media_type, declared_byte_length, display_filename,"
                                " capture_declared_at, client_declared_sha256, idempotency_key, intent_state, last_rejection_category,"
                                " evidence_item_id, created_at, state_changed_at, retention_policy_reference_id)"
                                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'OPEN', NULL, NULL, now(), now(), %s)",
                                (evidence_id, submission_id, principal.principal_reference_id, values["artifact_kind"],
                                 values["declared_media_type"], values["declared_byte_length"], values.get("display_filename"),
                                 values["capture_declared_at"], values.get("client_declared_sha256"), ingest_key, retention))
                    cur.execute(f"INSERT INTO {SCHEMA}.cross_store_operation (cross_store_operation_id, idempotency_key, operation_kind,"
                                " owner_module, target_table, target_id, ecs_object_ref, expected_sha256, state, attempt_count,"
                                " last_failure_category, next_attempt_not_before, created_at, state_changed_at, terminal_at)"
                                " VALUES (%s, %s, 'EVIDENCE_INGEST', 'EVIDENCE', 'evidence_item', %s, NULL, %s, 'RECEIVED', 0, NULL, NULL,"
                                " now(), now(), NULL)", (str(uuid.uuid4()), ingest_key, evidence_id, values.get("client_declared_sha256")))
                    _audit_evidence(cur, request, principal, case_id, evidence_id, "EVIDENCE_RECEIVED")
                    idempotency.complete(cur, outcome, 201, "evidence_item", evidence_id)
        except idempotency.StaleClaim:
            return api_error(request, "IDEMPOTENCY_IN_PROGRESS")
        except (psycopg.Error, _Unavailable, ValueError):
            idempotency.release(connection, outcome, 503, "DEPENDENCY_UNAVAILABLE")
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if conflict:
            return api_error(request, "STATE_CONFLICT")
        with connection.cursor() as cur:
            view = _view(_evidence_row(cur, evidence_id))
    return _json(201, view, location=view["links"]["self"])


def _replay(request, connection, replay, status=None):
    if replay.error_code:
        return api_error(request, replay.error_code)
    with connection.cursor() as cur:
        row = _evidence_row(cur, replay.resource_id)
    if row is None:
        return api_error(request, "NOT_FOUND")
    view = _view(row)
    return _json(status or replay.status, view)


# ---------------------------------------------------------------- putEvidenceContent
async def put_evidence_content(request: Request):
    runtime, principal, error = current_principal(request, "PUTEVIDENCECONTENT")
    if error is not None:
        return error
    evidence_id = _uuid(request.path_params["evidence_id"])
    if evidence_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "evidence_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    body = await read_bounded(request, MAX_EVIDENCE_BYTES)     # never buffers more than the 64 KiB bound
    oversize = body is None
    body = body or b""
    media_ok = supported_media(request.headers.get("content-type"))
    return await run_in_threadpool(_put_evidence_content, request, runtime, principal, evidence_id, body, oversize, media_ok)


def _reject_put(cur, request, evidence_id, category, code):
    cur.execute(f"UPDATE {SCHEMA}.evidence_upload_intent SET last_rejection_category = %s, state_changed_at = now()"
                " WHERE evidence_upload_intent_id = %s", (category, evidence_id))
    return api_error(request, code)


def _put_evidence_content(request, runtime, principal, evidence_id, body, oversize, media_ok):
    try:
        connection = _open(request, runtime)
    except _Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                case_id = _case_of_evidence(cur, evidence_id)
                _authorize(request, runtime, principal, cur, "putEvidenceContent", case_id, needs_content=True)
        except _Refused as refused:
            return refused.response
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        store = get_store(runtime)
        if store is None:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        digest, length = hashlib.sha256(body).hexdigest(), len(body)
        try:
            with connection.transaction(), connection.cursor() as cur:
                cur.execute(f"SELECT intent_state, declared_byte_length, client_declared_sha256, artifact_kind, declared_media_type,"
                            " capture_declared_at, created_at, idempotency_key::text, retention_policy_reference_id::text, submission_id::text"
                            f" FROM {SCHEMA}.evidence_upload_intent WHERE evidence_upload_intent_id = %s FOR UPDATE", (evidence_id,))
                (intent_state, declared_length, client_digest, kind, declared_media, capture, created, ingest_key, retention,
                 submission_id) = cur.fetchone()
                cur.execute(f"SELECT content_sha256, byte_length, content_state FROM {SCHEMA}.evidence_item"
                            " WHERE evidence_item_id = %s FOR UPDATE", (evidence_id,))
                item = cur.fetchone()
                if oversize:
                    if item is None:
                        return _reject_put(cur, request, evidence_id, "SIZE_EXCEEDED", "PAYLOAD_TOO_LARGE")
                    return api_error(request, "PAYLOAD_TOO_LARGE")
                if not media_ok or not supported_media(declared_media):
                    if item is None:
                        return _reject_put(cur, request, evidence_id, "MEDIA_INVALID", "UNSUPPORTED_MEDIA_TYPE")
                    return api_error(request, "UNSUPPORTED_MEDIA_TYPE")
                if item is not None:
                    if (item[0], item[1]) != (digest, length):
                        return api_error(request, "STATE_CONFLICT")           # different bytes after content exists
                    if item[2] not in ("RECEIVED", "CONTENT_PENDING", "FAILED_RETRYABLE"):
                        return _current(request, cur, evidence_id, 200)        # identical re-PUT: same state, no effect
                else:
                    try:
                        body.decode("utf-8", errors="strict")
                    except UnicodeDecodeError:
                        return _reject_put(cur, request, evidence_id, "MEDIA_INVALID", "UNSUPPORTED_MEDIA_TYPE")
                    if length != declared_length:
                        return _reject_put(cur, request, evidence_id, "LENGTH_MISMATCH", "INVALID_REQUEST")
                    if client_digest and client_digest != digest:
                        return _reject_put(cur, request, evidence_id, "DIGEST_MISMATCH", "INVALID_REQUEST")
                    cur.execute(f"INSERT INTO {SCHEMA}.evidence_item (evidence_item_id, submission_id, artifact_kind, content_sha256,"
                                " byte_length, byte_definition_version, declared_media_type, verified_media_type, ingested_at,"
                                " capture_declared_at, source_channel_ref, ingesting_component_ref, ingesting_principal_id, ecs_locator,"
                                " data_key_version_ref, content_state, state_changed_at, verified_at, finalized_at, idempotency_key,"
                                " retention_policy_reference_id) VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, NULL, %s, %s, NULL,"
                                " %s, 'RECEIVED', now(), NULL, NULL, %s, %s)",
                                (evidence_id, submission_id, kind, digest, length, BYTE_DEFINITION, declared_media, created, capture,
                                 COMPONENT_REF, principal.principal_reference_id, KEK_VERSION_REF, ingest_key, retention))
                    cur.execute(f"UPDATE {SCHEMA}.evidence_upload_intent SET intent_state = 'MATERIALIZED', evidence_item_id = %s,"
                                " last_rejection_category = NULL, state_changed_at = now() WHERE evidence_upload_intent_id = %s",
                                (evidence_id, evidence_id))
                attempt = _begin_attempt(request, cur, evidence_id, ingest_key)
                if not isinstance(attempt, _Attempt):
                    return attempt                 # refused after committing any state it recorded (e.g. FAILED_TERMINAL)
        except _Refused as refused:
            return refused.response
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        # Outside any transaction: the encrypted, durable content write. Only the attempt holding the fence may record it.
        try:
            stored = store.put(body)
        except ContentStoreUnavailable:
            return _write_failed(request, connection, evidence_id, attempt)
        try:
            with connection.transaction(), connection.cursor() as cur:
                if not _fenced_update(cur, attempt, "CONTENT_STORED", ecs_object_ref=stored.locator):
                    # A newer attempt took over (this one outlived its lease): its object stays an unreferenced orphan.
                    return _superseded_attempt(request, cur, evidence_id)
                cur.execute(f"UPDATE {SCHEMA}.evidence_item SET content_state = 'CONTENT_STORED', ecs_locator = %s, state_changed_at = now()"
                            " WHERE evidence_item_id = %s AND content_state = 'CONTENT_PENDING' AND ecs_locator IS NULL",
                            (stored.locator, evidence_id))
                if cur.rowcount != 1:
                    raise psycopg.errors.RaiseException("evidence_item left CONTENT_PENDING under a live fence")
                _audit_evidence(cur, request, principal, case_id, evidence_id, "EVIDENCE_STORED", stage="CONTENT_STORED")
                return _current(request, cur, evidence_id, 200)
        except psycopg.Error:
            # Content is stored but its metadata did not commit: the item stays CONTENT_PENDING (never reported as stored or
            # finalized). Release this attempt's lease so an identical re-PUT can complete it at once.
            _release_attempt(connection, attempt)
            return api_error(request, "DEPENDENCY_UNAVAILABLE")


@dataclass(frozen=True)
class _Attempt:
    """Durable fencing identity of one content-write attempt: the EVIDENCE_INGEST operation and its attempt_count."""
    operation_id: str
    number: int


def _retry_after(cur, operation_id) -> int:
    cur.execute(f"SELECT ceil(extract(epoch FROM next_attempt_not_before - now()))::int FROM {SCHEMA}.cross_store_operation"
                " WHERE cross_store_operation_id = %s", (operation_id,))
    return max(1, cur.fetchone()[0] or 1)


def _begin_attempt(request, cur, evidence_id, ingest_key):
    """Start (or take over) a content write under a lease. attempt_count is the fencing token: each attempt gets the next
    number by compare-and-swap, and every later outcome is recorded only WHERE attempt_count still equals it. During
    CONTENT_PENDING, next_attempt_not_before is the live attempt's lease; FAILED_RETRYABLE uses it as the backoff.
    Returns the _Attempt, or a refusal response to return (and commit) as is."""
    cur.execute(f"SELECT cross_store_operation_id::text, state, attempt_count, coalesce(next_attempt_not_before > now(), false)"
                f" FROM {SCHEMA}.cross_store_operation WHERE idempotency_key = %s AND operation_kind = 'EVIDENCE_INGEST' FOR UPDATE",
                (ingest_key,))
    operation_id, state, count, waiting = cur.fetchone()
    if state in ("CONTENT_PENDING", "FAILED_RETRYABLE") and waiting:
        return api_error(request, "DEPENDENCY_UNAVAILABLE", retry_after=_retry_after(cur, operation_id))
    if state == "CONTENT_PENDING" and count >= MAX_WRITE_ATTEMPTS:
        # The last permitted attempt never reported back (crash): retries are exhausted (FAILED_RETRYABLE -> FAILED_TERMINAL).
        _terminate(cur, evidence_id, operation_id, count)
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    cur.execute(f"UPDATE {SCHEMA}.cross_store_operation SET state = 'CONTENT_PENDING', attempt_count = attempt_count + 1,"
                " next_attempt_not_before = now() + %s, state_changed_at = now()"
                " WHERE cross_store_operation_id = %s AND attempt_count = %s AND state IN ('RECEIVED', 'CONTENT_PENDING', 'FAILED_RETRYABLE')"
                " RETURNING attempt_count", (WRITE_LEASE, operation_id, count))
    row = cur.fetchone()
    if row is None:
        raise _Refused(api_error(request, "DEPENDENCY_UNAVAILABLE", retry_after=1))
    cur.execute(f"UPDATE {SCHEMA}.evidence_item SET content_state = 'CONTENT_PENDING', state_changed_at = now()"
                " WHERE evidence_item_id = %s AND content_state IN ('RECEIVED', 'CONTENT_PENDING', 'FAILED_RETRYABLE')", (evidence_id,))
    if cur.rowcount != 1:
        raise psycopg.errors.RaiseException("evidence_item not in a writable state")
    return _Attempt(operation_id, row[0])


def _fenced_update(cur, attempt: _Attempt, state: str, ecs_object_ref=None, failure=None, backoff=None) -> bool:
    """Record this attempt's outcome only if it still holds the fence (same attempt number, still CONTENT_PENDING)."""
    terminal = state == "FAILED_TERMINAL"
    cur.execute(f"UPDATE {SCHEMA}.cross_store_operation SET state = %s, ecs_object_ref = coalesce(%s, ecs_object_ref),"
                " last_failure_category = coalesce(%s, last_failure_category),"
                " next_attempt_not_before = CASE WHEN %s::int IS NULL THEN NULL ELSE now() + make_interval(secs => %s::int) END,"
                " terminal_at = CASE WHEN %s THEN now() ELSE NULL END, state_changed_at = now()"
                " WHERE cross_store_operation_id = %s AND attempt_count = %s AND state = 'CONTENT_PENDING'"
                " RETURNING cross_store_operation_id",
                (state, ecs_object_ref, failure, backoff, backoff, terminal, attempt.operation_id, attempt.number))
    return cur.fetchone() is not None


def _terminate(cur, evidence_id, operation_id, count):
    _fenced_update(cur, _Attempt(operation_id, count), "FAILED_TERMINAL", failure="CONTENT_STORE_UNAVAILABLE")
    for step in ("FAILED_RETRYABLE", "FAILED_TERMINAL"):       # §11: FAILED_TERMINAL only via FAILED_RETRYABLE
        cur.execute(f"UPDATE {SCHEMA}.evidence_item SET content_state = %s, state_changed_at = now() WHERE evidence_item_id = %s",
                    (step, evidence_id))


def _superseded_attempt(request, cur, evidence_id):
    """A fenced-out attempt reports the authoritative state, never its own: stored -> 200, otherwise retry later."""
    cur.execute(f"SELECT o.cross_store_operation_id::text, e.content_state FROM {SCHEMA}.evidence_item e"
                f" JOIN {SCHEMA}.cross_store_operation o ON o.idempotency_key = e.idempotency_key AND o.operation_kind = 'EVIDENCE_INGEST'"
                " WHERE e.evidence_item_id = %s", (evidence_id,))
    operation_id, state = cur.fetchone()
    if state in ("CONTENT_STORED", "INTEGRITY_VERIFIED", "FINALIZED"):
        return _current(request, cur, evidence_id, 200)
    if state in ("CONTENT_PENDING", "FAILED_RETRYABLE"):
        return api_error(request, "DEPENDENCY_UNAVAILABLE", retry_after=_retry_after(cur, operation_id))
    return api_error(request, "DEPENDENCY_UNAVAILABLE")


def _release_attempt(connection, attempt: _Attempt):
    """Best effort: end this attempt's lease early (state unchanged). If the database is down the lease simply expires."""
    try:
        with connection.transaction(), connection.cursor() as cur:
            cur.execute(f"UPDATE {SCHEMA}.cross_store_operation SET next_attempt_not_before = now(), state_changed_at = now()"
                        " WHERE cross_store_operation_id = %s AND attempt_count = %s AND state = 'CONTENT_PENDING'",
                        (attempt.operation_id, attempt.number))
    except psycopg.Error:
        pass


def _write_failed(request, connection, evidence_id, attempt: _Attempt):
    terminal = attempt.number >= MAX_WRITE_ATTEMPTS
    try:
        with connection.transaction(), connection.cursor() as cur:
            state = "FAILED_TERMINAL" if terminal else "FAILED_RETRYABLE"
            if not _fenced_update(cur, attempt, state, failure="CONTENT_STORE_UNAVAILABLE",
                                  backoff=None if terminal else backoff_seconds(attempt.number)):
                return _superseded_attempt(request, cur, evidence_id)    # stale failure: never overwrites a newer outcome
            # §11: FAILED_TERMINAL is reached only from FAILED_RETRYABLE ("retries exhausted"), so pass through it.
            for step in ("FAILED_RETRYABLE", "FAILED_TERMINAL")[: 2 if terminal else 1]:
                cur.execute(f"UPDATE {SCHEMA}.evidence_item SET content_state = %s, state_changed_at = now() WHERE evidence_item_id = %s",
                            (step, evidence_id))
    except psycopg.Error:
        _release_attempt(connection, attempt)
    return api_error(request, "DEPENDENCY_UNAVAILABLE", retry_after=None if terminal else backoff_seconds(attempt.number))


def _current(request, cur, evidence_id, status):
    return _json(status, _view(_evidence_row(cur, evidence_id)))


# ---------------------------------------------------------------- finalizeEvidence
async def finalize_evidence(request: Request):
    runtime, principal, error = current_principal(request, "FINALIZEEVIDENCE")
    if error is not None:
        return error
    evidence_id = _uuid(request.path_params["evidence_id"])
    if evidence_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "evidence_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    key = request.headers.get("idempotency-key")
    if not idempotency.valid_key(key):
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "Idempotency-Key", "code": "REQUIRED", "message": "Send a high-entropy key (16-255 URL-safe characters)."}])
    body, problems = await _json_body(request, {}, set())       # EvidenceFinalizeRequest has no fields
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_finalize_evidence, request, runtime, principal, evidence_id, key, body)


def _finalize_evidence(request, runtime, principal, evidence_id, key, body):
    scope = f"/api/v1/evidence/{evidence_id}/finalize"
    try:
        connection = _open(request, runtime)
    except _Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                case_id = _case_of_evidence(cur, evidence_id)
                _authorize(request, runtime, principal, cur, "finalizeEvidence", case_id)
            store = get_store(runtime)
            if store is None:
                return api_error(request, "DEPENDENCY_UNAVAILABLE")
            outcome = idempotency.claim(connection, principal.principal_reference_id, "finalizeEvidence", scope, key,
                                        idempotency.semantic_digest("finalizeEvidence", scope, body), supersession=True)
        except _Refused as refused:
            return refused.response
        except (idempotency.KeyReused, idempotency.InProgress) as e:
            return _idempotent_error(request, e)
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if isinstance(outcome, idempotency.Replay):
            return _replay(request, connection, outcome)
        try:
            with connection.cursor() as cur:
                cur.execute(f"SELECT content_state, ecs_locator, content_sha256, byte_length FROM {SCHEMA}.evidence_item"
                            " WHERE evidence_item_id = %s", (evidence_id,))
                item = cur.fetchone()
            if item is None or item[0] not in ("CONTENT_STORED", "INTEGRITY_VERIFIED", "FINALIZED"):
                with connection.transaction(), connection.cursor() as cur:   # bytes not stored (yet): out of order
                    idempotency.fail_terminal(cur, outcome, 409, "STATE_CONFLICT")
                return api_error(request, "STATE_CONFLICT")
            verified = False
            if item[0] != "FINALIZED":
                try:
                    data = store.get(item[1])                # decrypt + authenticate
                    store.verify(item[1], item[2], item[3])
                    data.decode("utf-8", errors="strict")
                    verified = True
                except (IntegrityFailure, UnicodeDecodeError):
                    verified = False
                except ContentStoreUnavailable:
                    idempotency.release(connection, outcome, 503, "DEPENDENCY_UNAVAILABLE")
                    return api_error(request, "DEPENDENCY_UNAVAILABLE")
            with connection.transaction(), connection.cursor() as cur:
                cur.execute(f"SELECT content_state, idempotency_key::text FROM {SCHEMA}.evidence_item WHERE evidence_item_id = %s FOR UPDATE",
                            (evidence_id,))
                state, ingest_key = cur.fetchone()
                if state == "FINALIZED":
                    idempotency.complete(cur, outcome, 202, "evidence_item", evidence_id)
                    return _current(request, cur, evidence_id, 202)
                if state not in ("CONTENT_STORED", "INTEGRITY_VERIFIED"):
                    idempotency.fail_terminal(cur, outcome, 409, "STATE_CONFLICT")
                    conflict = "STATE_CONFLICT"
                elif not verified:
                    cur.execute(f"UPDATE {SCHEMA}.evidence_item SET content_state = 'INTEGRITY_FAILED', state_changed_at = now()"
                                " WHERE evidence_item_id = %s", (evidence_id,))
                    cur.execute(f"UPDATE {SCHEMA}.cross_store_operation SET state = 'INTEGRITY_FAILED', last_failure_category = 'DIGEST_OR_AUTHENTICATION_FAILED',"
                                " state_changed_at = now() WHERE idempotency_key = %s AND operation_kind = 'EVIDENCE_INGEST'", (ingest_key,))
                    _audit_evidence(cur, request, principal, case_id, evidence_id, "INTEGRITY_FAILURE", stage="FINALIZE_VERIFICATION", outcome="FAILED")
                    idempotency.fail_terminal(cur, outcome, 500, "INTEGRITY_FAILURE")
                    conflict = "INTEGRITY_FAILURE"
                else:
                    if state == "CONTENT_STORED":
                        cur.execute(f"UPDATE {SCHEMA}.evidence_item SET content_state = 'INTEGRITY_VERIFIED', verified_at = now(),"
                                    " verified_media_type = %s, state_changed_at = now() WHERE evidence_item_id = %s",
                                    (VERIFIED_MEDIA_TYPE, evidence_id))
                    cur.execute(f"UPDATE {SCHEMA}.evidence_item SET content_state = 'FINALIZED', finalized_at = now(), state_changed_at = now()"
                                " WHERE evidence_item_id = %s", (evidence_id,))
                    cur.execute(f"UPDATE {SCHEMA}.cross_store_operation SET state = 'FINALIZED', terminal_at = now(), state_changed_at = now()"
                                " WHERE idempotency_key = %s AND operation_kind = 'EVIDENCE_INGEST'", (ingest_key,))
                    _audit_evidence(cur, request, principal, case_id, evidence_id, "EVIDENCE_STORED", stage="FINALIZED")
                    idempotency.complete(cur, outcome, 202, "evidence_item", evidence_id)
                    return _current(request, cur, evidence_id, 202)
            return api_error(request, conflict)
        except idempotency.StaleClaim:
            return api_error(request, "IDEMPOTENCY_IN_PROGRESS")
        except psycopg.Error:
            idempotency.release(connection, outcome, 503, "DEPENDENCY_UNAVAILABLE")
            return api_error(request, "DEPENDENCY_UNAVAILABLE")


# ---------------------------------------------------------------- getEvidenceMetadata / listEvidence
async def get_evidence_metadata(request: Request):
    runtime, principal, error = current_principal(request, "GETEVIDENCEMETADATA")
    if error is not None:
        return error
    evidence_id = _uuid(request.path_params["evidence_id"])
    if evidence_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "evidence_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    return await run_in_threadpool(_get_evidence_metadata, request, runtime, principal, evidence_id)


def _get_evidence_metadata(request, runtime, principal, evidence_id):
    try:
        connection = _open(request, runtime)
    except _Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                case_id = _case_of_evidence(cur, evidence_id)
                _authorize(request, runtime, principal, cur, "getEvidenceMetadata", case_id)
                return _current(request, cur, evidence_id, 200)
        except _Refused as refused:
            return refused.response
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")


async def list_evidence(request: Request):
    runtime, principal, error = current_principal(request, "LISTEVIDENCE")
    if error is not None:
        return error
    submission_id = _uuid(request.path_params["submission_id"])
    if submission_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "submission_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    params, problems = _page_params(request, {"upload_state": API_UPLOAD_STATES, "artifact_kind": ARTIFACT_KINDS})
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_list_evidence, request, runtime, principal, submission_id, params)


def _list_evidence(request, runtime, principal, submission_id, params):
    try:
        connection = _open(request, runtime)
    except _Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                case_id = _case_of_submission(cur, submission_id)
                _authorize(request, runtime, principal, cur, "listEvidence", case_id)
                where, args = ["i.submission_id = %s"], [submission_id]
                if "upload_state" in params:
                    where.append(f"({_UPLOAD_STATE_SQL}) = %s")
                    args.append(params["upload_state"])
                if "artifact_kind" in params:
                    where.append("i.artifact_kind = %s")
                    args.append(params["artifact_kind"])
                if params["cursor"]:
                    where.append("(i.created_at, i.evidence_upload_intent_id) < (%s, %s::uuid)")
                    args += list(params["cursor"])
                cur.execute(f"SELECT {_EVIDENCE_COLUMNS} FROM {SCHEMA}.evidence_upload_intent i LEFT JOIN {SCHEMA}.evidence_item e"
                            " ON e.evidence_item_id = i.evidence_upload_intent_id WHERE " + " AND ".join(where)
                            + " ORDER BY i.created_at DESC, i.evidence_upload_intent_id DESC LIMIT %s", args + [params["limit"] + 1])
                rows = cur.fetchall()
        except _Refused as refused:
            return refused.response
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
    page = {"limit": params["limit"]}
    if len(rows) > params["limit"]:
        rows = rows[:params["limit"]]
        page["next_cursor"] = _encode_cursor(rows[-1][9], rows[-1][0])
    return _json(200, {"items": [_view(r) for r in rows], "page": page})


def install(app: FastAPI):
    app.add_api_route("/api/v1/submissions/{submission_id}/evidence", create_evidence_upload, methods=["POST"])
    app.add_api_route("/api/v1/submissions/{submission_id}/evidence", list_evidence, methods=["GET"])
    app.add_api_route("/api/v1/evidence/{evidence_id}", get_evidence_metadata, methods=["GET"])
    app.add_api_route("/api/v1/evidence/{evidence_id}/content", put_evidence_content, methods=["PUT"])
    app.add_api_route("/api/v1/evidence/{evidence_id}/finalize", finalize_evidence, methods=["POST"])
