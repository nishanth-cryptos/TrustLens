"""S2 accepted API v1 operations for cases and submissions (API-001 §§5, 10–11, 27; DATA-001-WP2; OPS-001 §4).

createCase, getCase, listCases, createSubmission, getSubmission, listSubmissions — exactly as catalogued in
contracts/api/api-v1.json. Authorization is server-side on every request: a case-scoped resource without visibility is
a masked 404; a visible resource without the role or ownership is 403. Owners are always the authenticated principal;
no client field can set ownership. Submissions carry categorical metadata only — never message text.

Evidence operations are not implemented: they wait for the governed DATA-001-WP2 upload-intent revision.
"""
import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from . import idempotency
from .audit import AuditEvent, append as audit_append
from .capabilities import evidence_schema_active
from .auth import NO_STORE, _audit, api_error, current_principal
from .principals import SCHEMA

# Catalogue entries this module implements (asserted equal to api-v1.json by the tests).
OPERATIONS = {
    "createCase": {"method": "POST", "path": "/api/v1/cases", "roles": ("USER",), "resource_authorization": "SELF"},
    "getCase": {"method": "GET", "path": "/api/v1/cases/{case_id}", "roles": ("USER", "ANALYST"), "resource_authorization": "CASE_ACCESS"},
    "listCases": {"method": "GET", "path": "/api/v1/cases", "roles": ("USER", "ANALYST"), "resource_authorization": "CASE_ACCESS"},
    "createSubmission": {"method": "POST", "path": "/api/v1/cases/{case_id}/submissions", "roles": ("USER",),
                         "resource_authorization": "CASE_OWNER"},
    "getSubmission": {"method": "GET", "path": "/api/v1/submissions/{submission_id}", "roles": ("USER", "ANALYST"),
                      "resource_authorization": "CASE_ACCESS"},
    "listSubmissions": {"method": "GET", "path": "/api/v1/cases/{case_id}/submissions", "roles": ("USER", "ANALYST"),
                        "resource_authorization": "CASE_ACCESS"},
}
CASE_STATES = ("OPEN", "UNDER_REVIEW", "CLOSED", "DELETION_PENDING", "DELETED")
SUBMISSION_STATES = ("RECEIVING", "RECEIVED", "PROCESSING", "PROCESSED", "PARTIALLY_FAILED", "FAILED")
VIEWER_RELATIONSHIPS = ("OWNER", "ASSIGNED_ANALYST", "BREAK_GLASS")
INPUT_TYPES = ("TEXT", "SMS", "CHAT_MESSAGE", "EMAIL", "URL", "OCR_TEXT", "SCREENSHOT_DERIVED_TEXT", "DOCUMENT_TEXT", "USER_NARRATIVE")
RELATIONSHIPS_TO_CONTENT = ("RECEIVED", "SENT", "REPORTING_ON_BEHALF", "FORWARDED", "UNKNOWN")
# Approved local-development values (T09, 2026-10-14): JSON request body <= 128 KiB; page size default 20, maximum 100.
MAX_JSON_BODY = 128 * 1024
PAGE_DEFAULT, PAGE_MAX = 20, 100
# S2 local profile handles synthetic data only (G-09): every case and submission is marked synthetic by the server.
SYNTHETIC_ONLY_PROFILE = True
OWNER_GRANT_REASON = "CASE_CREATED_OWNER_GRANT"
_GRANT_ACTIVE = ("g.revoked_at IS NULL AND g.effective_from <= now() AND (g.expires_at IS NULL OR g.expires_at > now())"
                 " AND g.permits_case_metadata")


class _Unavailable(Exception):
    pass


# ---------------------------------------------------------------- helpers
def _instant(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _uuid(value: str) -> str | None:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None
    return str(parsed) if str(parsed) == value.lower() and parsed.version == 4 else None


def _etag(case_id: str, revision: int) -> str:
    return '"' + hashlib.sha256(f"{case_id}:{revision}".encode()).hexdigest()[:32] + '"'


def _connect(runtime):
    if runtime.database is None:
        raise _Unavailable()
    try:
        connection = psycopg.connect(**runtime.database.connection_parameters(), autocommit=True)
        connection.execute("SET statement_timeout = '5s'")
        return connection
    except psycopg.Error:
        raise _Unavailable() from None


TOO_LARGE = {"field": "body", "code": "TOO_LARGE", "message": "Request body exceeds the configured bound."}


async def read_bounded(request: Request, limit: int) -> bytes | None:
    """The request body, or None as soon as it would exceed `limit` bytes.

    Reads incrementally whether Content-Length is present, absent (chunked) or wrong: a chunk that would cross the
    bound is refused before it is appended, so at most `limit` bytes are ever buffered here."""
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.strip().isdigit() or int(declared) > limit):
        return None
    received = bytearray()
    async for chunk in request.stream():
        if len(received) + len(chunk) > limit:
            return None
        received += chunk
    return bytes(received)


async def read_json_object(request: Request) -> tuple[dict | None, list | None]:
    """application/json object, at most MAX_JSON_BODY bytes. Values are never echoed in errors.

    An oversized body yields the field error TOO_LARGE; operations whose accepted contract lists PAYLOAD_TOO_LARGE
    answer 413, the others keep their accepted 400 INVALID_REQUEST (see is_too_large)."""
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        return None, [{"field": "Content-Type", "code": "UNSUPPORTED", "message": "Send application/json."}]
    raw = await read_bounded(request, MAX_JSON_BODY)
    if raw is None:
        return None, [dict(TOO_LARGE)]
    try:
        body = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, ValueError):
        return None, [{"field": "body", "code": "MALFORMED", "message": "Body is not valid JSON."}]
    if not isinstance(body, dict):
        return None, [{"field": "body", "code": "MALFORMED", "message": "Body must be a JSON object."}]
    return body, None


def is_too_large(problems) -> bool:
    return problems == [TOO_LARGE]


async def _json_body(request: Request, allowed: dict, required: set) -> tuple[dict | None, list | None]:
    """Strict JSON object body: bounded size, unknown fields rejected, enum values checked. Values never echoed."""
    body, problems = await read_json_object(request)
    if problems:
        return None, problems
    errors = [{"field": k, "code": "UNKNOWN_FIELD", "message": "Field is not accepted."} for k in body if k not in allowed]
    errors += [{"field": k, "code": "REQUIRED", "message": "Field is required."} for k in sorted(required) if k not in body]
    errors += [{"field": k, "code": "INVALID_VALUE", "message": "Value is not in the accepted vocabulary."}
               for k, vocabulary in allowed.items() if k in body and body[k] not in vocabulary]
    return (None, errors) if errors else (body, None)


def _page_params(request: Request, filters: dict) -> tuple[dict | None, list | None]:
    params, errors = {}, []
    for key, value in request.query_params.multi_items():
        if key in params:
            errors.append({"field": key, "code": "DUPLICATE", "message": "Parameter repeated."})
        params[key] = value
    for key in params:
        if key not in filters and key not in ("limit", "cursor"):
            errors.append({"field": key, "code": "UNKNOWN_PARAMETER", "message": "Parameter is not accepted."})
    out = {"limit": PAGE_DEFAULT, "cursor": None}
    if "limit" in params:
        if not params["limit"].isdigit() or not 1 <= int(params["limit"]) <= PAGE_MAX:
            errors.append({"field": "limit", "code": "OUT_OF_RANGE", "message": f"limit must be 1..{PAGE_MAX}."})
        else:
            out["limit"] = int(params["limit"])
    if "cursor" in params:
        out["cursor"] = _decode_cursor(params["cursor"])
        if out["cursor"] is None:
            errors.append({"field": "cursor", "code": "INVALID", "message": "Cursor is not valid."})
    for key, kind in filters.items():
        if key not in params:
            continue
        if isinstance(kind, tuple):
            if params[key] not in kind:
                errors.append({"field": key, "code": "INVALID_VALUE", "message": "Value is not in the accepted vocabulary."})
            else:
                out[key] = params[key]
        elif kind == "uuid":
            if _uuid(params[key]) is None:
                errors.append({"field": key, "code": "INVALID_UUID", "message": "Not a UUID."})
            else:
                out[key] = _uuid(params[key])
        else:
            try:
                parsed = datetime.fromisoformat(params[key].replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError
                out[key] = parsed
            except ValueError:
                errors.append({"field": key, "code": "INVALID_TIMESTAMP", "message": "Use an RFC 3339 timestamp with offset."})
    return (None, errors) if errors else (out, None)


def _encode_cursor(instant: datetime, identifier: str) -> str:
    raw = json.dumps({"t": instant.astimezone(timezone.utc).isoformat(), "i": identifier}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(value: str):
    """Opaque keyset position. It only moves the page within the caller's own authorized set, never widens it."""
    try:
        if len(value) > 256:
            return None
        data = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode())
        instant = datetime.fromisoformat(data["t"])
        identifier = _uuid(data["i"])
        return (instant, identifier) if identifier and instant.tzinfo else None
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None


def _case_view(row) -> dict:
    case_id, state, synthetic, created, closed, revision, grant_kind, content = row
    return {"case_id": case_id, "state": state, "is_synthetic": synthetic, "created_at": _instant(created),
            "closed_at": _instant(closed),
            "viewer_access": {"relationship": grant_kind, "can_view_evidence_content": bool(content)},
            "etag": _etag(case_id, revision),
            "links": {"self": f"/api/v1/cases/{case_id}", "related": {"submissions": f"/api/v1/cases/{case_id}/submissions"}}}


def _submission_view(row) -> dict:
    submission_id, case_id, input_type, relationship, state, received, synthetic = row
    view = {"submission_id": submission_id, "case_id": case_id, "declared_input_type": input_type, "state": state,
            "received_at": _instant(received), "is_synthetic": synthetic,
            "links": {"self": f"/api/v1/submissions/{submission_id}", "related": {"case": f"/api/v1/cases/{case_id}"}}}
    if relationship is not None:
        view["relationship_to_content"] = relationship
    return view


_CASE_COLUMNS = ("c.case_record_id::text, c.lifecycle_state, c.is_synthetic, c.created_at, c.closed_at, c.mutation_revision,"
                 " g.grant_kind, g.permits_evidence_content")
_VIEWER_GRANT = (f"JOIN LATERAL (SELECT g.grant_kind, g.permits_evidence_content FROM {SCHEMA}.case_access_grant g"
                 f" WHERE g.case_record_id = c.case_record_id AND g.principal_reference_id = %s AND {_GRANT_ACTIVE}"
                 " ORDER BY (g.grant_kind = 'OWNER') DESC LIMIT 1) g ON true")
_SUBMISSION_COLUMNS = ("s.submission_id::text, s.case_record_id::text, s.declared_input_type, s.relationship_to_content,"
                       " s.processing_state, s.received_at, s.is_synthetic")


def _visible_case(cur, case_id: str, principal_id: str):
    cur.execute(f"SELECT {_CASE_COLUMNS} FROM {SCHEMA}.case_record c {_VIEWER_GRANT} WHERE c.case_record_id = %s",
                (principal_id, case_id))
    return cur.fetchone()


def _case_exists(cur, case_id: str) -> bool:
    cur.execute(f"SELECT 1 FROM {SCHEMA}.case_record WHERE case_record_id = %s", (case_id,))
    return cur.fetchone() is not None


def _retention_reference(cur) -> str:
    cur.execute(f"SELECT retention_policy_reference_id::text FROM {SCHEMA}.retention_policy_reference"
                " WHERE retention_class_code = 'UNRESOLVED_OI05_DEFAULT' AND policy_version = '0'")
    row = cur.fetchone()
    if row is None:
        raise _Unavailable()
    return row[0]


def _authorize_case(request, runtime, principal, cur, operation_id: str, case_id: str):
    """API-001 §5: no visibility -> masked 404 (whatever the role); visible without role/ownership -> 403."""
    spec = OPERATIONS[operation_id]
    case = _visible_case(cur, case_id, principal.principal_reference_id)
    write = spec["method"] != "GET"
    if case is None:
        if write and _case_exists(cur, case_id):
            _audit_denial(runtime, request, principal, case_id, "NO_CASE_ACCESS", operation_id)
        return None, api_error(request, "NOT_FOUND")
    if not set(principal.roles) & set(spec["roles"]) or (spec["resource_authorization"] == "CASE_OWNER" and case[6] != "OWNER"):
        if write:
            _audit_denial(runtime, request, principal, case_id, "ROLE_OR_OWNERSHIP_REQUIRED", operation_id)
        return None, api_error(request, "FORBIDDEN")
    return case, None


def _audit_denial(runtime, request, principal, case_id, reason, operation_id):
    try:
        runtime.audit.record(AuditEvent(event_type="AUTHORIZATION_DENIED", outcome="DENIED", actor_kind="HUMAN",
                                        actor_principal_id=principal.principal_reference_id, target_kind="CASE",
                                        target_id=case_id, case_record_id=case_id, correlation_id=request.state.request_id,
                                        safe_metadata={"reason": reason, "operation": operation_id.upper()}))
    except Exception:      # best effort: the request is refused either way
        pass


def _json(status: int, body: dict, etag: str | None = None, location: str | None = None) -> JSONResponse:
    headers = dict(NO_STORE)
    if etag:
        headers["ETag"] = etag
    if location:
        headers["Location"] = location
    return JSONResponse(body, status_code=status, headers=headers)


def _idempotent_error(request, error):
    if isinstance(error, idempotency.KeyReused):
        return api_error(request, "IDEMPOTENCY_KEY_REUSED")
    return api_error(request, "IDEMPOTENCY_IN_PROGRESS")


# ---------------------------------------------------------------- createCase
async def create_case(request: Request):
    runtime, principal, error = current_principal(request, "CREATECASE")
    if error is not None:
        return error
    if "USER" not in principal.roles:
        return api_error(request, "FORBIDDEN")      # API-001 §5: a missing role on a non-case resource is 403
    key = request.headers.get("idempotency-key")
    if not idempotency.valid_key(key):
        return api_error(request, "INVALID_REQUEST",
                         field_errors=[{"field": "Idempotency-Key", "code": "REQUIRED", "message": "Send a high-entropy key (16-255 URL-safe characters)."}])
    body, problems = await _json_body(request, {"relationship_to_content": RELATIONSHIPS_TO_CONTENT}, set())
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_create_case, request, runtime, principal, key, body)


def _create_case(request, runtime, principal, key, body):
    scope = "/api/v1/cases"
    try:
        connection = _connect(runtime)
    except _Unavailable:
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    with connection:
        try:
            outcome = idempotency.claim(connection, principal.principal_reference_id, "createCase", scope, key,
                                        idempotency.semantic_digest("createCase", scope, body),
                                        supersession=evidence_schema_active(connection))
        except (idempotency.KeyReused, idempotency.InProgress) as e:
            return _idempotent_error(request, e)
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if isinstance(outcome, idempotency.Replay):
            return _replay_case(request, connection, principal, outcome)
        case_id = str(uuid.uuid4())
        try:
            with connection.transaction(), connection.cursor() as cur:
                retention = _retention_reference(cur)
                cur.execute(f"INSERT INTO {SCHEMA}.case_record (case_record_id, owner_principal_id, lifecycle_state, is_synthetic,"
                            " created_at, closed_at, retention_policy_reference_id, mutation_revision)"
                            " VALUES (%s, %s, 'OPEN', %s, now(), NULL, %s, 1)",
                            (case_id, principal.principal_reference_id, SYNTHETIC_ONLY_PROFILE, retention))
                cur.execute(f"INSERT INTO {SCHEMA}.case_access_grant (case_access_grant_id, case_record_id, principal_reference_id,"
                            " grant_kind, permits_case_metadata, permits_evidence_content, granted_by_principal_id, grant_reason_ref,"
                            " effective_from) VALUES (%s, %s, %s, 'OWNER', true, true, %s, %s, now())",
                            (str(uuid.uuid4()), case_id, principal.principal_reference_id, principal.principal_reference_id,
                             OWNER_GRANT_REASON))
                audit_append(cur, AuditEvent(event_type="CASE_CREATED", outcome="SUCCEEDED", actor_kind="HUMAN",
                                             actor_principal_id=principal.principal_reference_id, target_kind="CASE",
                                             target_id=case_id, case_record_id=case_id,
                                             correlation_id=request.state.request_id))
                idempotency.complete(cur, outcome, 201, "case_record", case_id)
                case = _visible_case(cur, case_id, principal.principal_reference_id)
        except idempotency.StaleClaim:
            return api_error(request, "IDEMPOTENCY_IN_PROGRESS")
        except (psycopg.Error, _Unavailable, ValueError):
            idempotency.release(connection, outcome, 503, "DEPENDENCY_UNAVAILABLE")
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
    view = _case_view(case)
    return _json(201, view, etag=view["etag"], location=view["links"]["self"])


def _replay_case(request, connection, principal, replay):
    if replay.error_code:
        return api_error(request, replay.error_code)
    with connection.cursor() as cur:
        case = _visible_case(cur, replay.resource_id, principal.principal_reference_id)
    if case is None:                      # the key never authorizes: access is re-checked on replay
        return api_error(request, "NOT_FOUND")
    view = _case_view(case)
    return _json(replay.status, view, etag=view["etag"], location=view["links"]["self"])


# ---------------------------------------------------------------- getCase / listCases
async def get_case(request: Request):
    runtime, principal, error = current_principal(request, "GETCASE")
    if error is not None:
        return error
    case_id = _uuid(request.path_params["case_id"])
    if case_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "case_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    return await run_in_threadpool(_get_case, request, runtime, principal, case_id)


def _get_case(request, runtime, principal, case_id):
    try:
        with _connect(runtime) as connection, connection.cursor() as cur:
            case, denial = _authorize_case(request, runtime, principal, cur, "getCase", case_id)
    except (_Unavailable, psycopg.Error):
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    if denial is not None:
        return denial
    view = _case_view(case)
    return _json(200, view, etag=view["etag"])


async def list_cases(request: Request):
    runtime, principal, error = current_principal(request, "LISTCASES")
    if error is not None:
        return error
    params, problems = _page_params(request, {"state": CASE_STATES, "created_from": "ts", "created_to": "ts",
                                              "relationship": VIEWER_RELATIONSHIPS})
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_list_cases, request, runtime, principal, params)


def _list_cases(request, runtime, principal, params):
    if not set(principal.roles) & {"USER", "ANALYST"}:
        return _json(200, {"items": [], "page": {"limit": params["limit"]}})     # no role -> no visible cases
    where, args = [], [principal.principal_reference_id]
    for key, clause in (("state", "c.lifecycle_state = %s"), ("created_from", "c.created_at >= %s"),
                        ("created_to", "c.created_at < %s"), ("relationship", "g.grant_kind = %s")):
        if key in params:
            where.append(clause)
            args.append(params[key])
    if params["cursor"]:
        where.append("(c.created_at, c.case_record_id) < (%s, %s::uuid)")
        args += list(params["cursor"])
    sql = (f"SELECT {_CASE_COLUMNS} FROM {SCHEMA}.case_record c {_VIEWER_GRANT}"
           + (" WHERE " + " AND ".join(where) if where else "")
           + " ORDER BY c.created_at DESC, c.case_record_id DESC LIMIT %s")
    try:
        with _connect(runtime) as connection, connection.cursor() as cur:
            cur.execute(sql, args + [params["limit"] + 1])
            rows = cur.fetchall()
    except (_Unavailable, psycopg.Error):
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    page = {"limit": params["limit"]}
    if len(rows) > params["limit"]:
        rows = rows[:params["limit"]]
        page["next_cursor"] = _encode_cursor(rows[-1][3], rows[-1][0])
    return _json(200, {"items": [_case_view(r) for r in rows], "page": page})


# ---------------------------------------------------------------- createSubmission
async def create_submission(request: Request):
    runtime, principal, error = current_principal(request, "CREATESUBMISSION")
    if error is not None:
        return error
    case_id = _uuid(request.path_params["case_id"])
    if case_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "case_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    key = request.headers.get("idempotency-key")
    if not idempotency.valid_key(key):
        return api_error(request, "INVALID_REQUEST",
                         field_errors=[{"field": "Idempotency-Key", "code": "REQUIRED", "message": "Send a high-entropy key (16-255 URL-safe characters)."}])
    body, problems = await _json_body(request, {"declared_input_type": INPUT_TYPES,
                                                "relationship_to_content": RELATIONSHIPS_TO_CONTENT}, {"declared_input_type"})
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_create_submission, request, runtime, principal, case_id, key, body)


def _create_submission(request, runtime, principal, case_id, key, body):
    scope = f"/api/v1/cases/{case_id}/submissions"
    try:
        connection = _connect(runtime)
    except _Unavailable:
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    with connection:
        try:
            with connection.cursor() as cur:           # authenticate -> authorize -> claim (the key never authorizes)
                _, denial = _authorize_case(request, runtime, principal, cur, "createSubmission", case_id)
            if denial is not None:
                return denial
            outcome = idempotency.claim(connection, principal.principal_reference_id, "createSubmission", scope, key,
                                        idempotency.semantic_digest("createSubmission", scope, body),
                                        supersession=evidence_schema_active(connection))
        except (idempotency.KeyReused, idempotency.InProgress) as e:
            return _idempotent_error(request, e)
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if isinstance(outcome, idempotency.Replay):
            if outcome.error_code:
                return api_error(request, outcome.error_code)
            return _submission_response(request, connection, principal, outcome.resource_id, outcome.status)
        submission_id = str(uuid.uuid4())
        try:
            with connection.transaction(), connection.cursor() as cur:
                cur.execute(f"SELECT lifecycle_state, is_synthetic FROM {SCHEMA}.case_record WHERE case_record_id = %s FOR SHARE",
                            (case_id,))
                state, synthetic = cur.fetchone()
                if state != "OPEN":
                    idempotency.fail_terminal(cur, outcome, 409, "STATE_CONFLICT")
                    conflict = True
                else:
                    conflict = False
                    cur.execute(f"INSERT INTO {SCHEMA}.submission (submission_id, case_record_id, submitted_by_principal_id,"
                                " received_via, declared_input_type, relationship_to_content, processing_state, is_synthetic,"
                                " received_at, processed_at, retention_policy_reference_id)"
                                " VALUES (%s, %s, %s, 'USER_SUBMISSION', %s, %s, 'RECEIVING', %s, now(), NULL, %s)",
                                (submission_id, case_id, principal.principal_reference_id, body["declared_input_type"],
                                 body.get("relationship_to_content"), synthetic, _retention_reference(cur)))
                    idempotency.complete(cur, outcome, 201, "submission", submission_id)
        except idempotency.StaleClaim:
            return api_error(request, "IDEMPOTENCY_IN_PROGRESS")
        except (psycopg.Error, _Unavailable, TypeError):
            idempotency.release(connection, outcome, 503, "DEPENDENCY_UNAVAILABLE")
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if conflict:
            return api_error(request, "STATE_CONFLICT")
        return _submission_response(request, connection, principal, submission_id, 201)


def _submission_response(request, connection, principal, submission_id, status):
    with connection.cursor() as cur:
        row = _visible_submission(cur, submission_id, principal.principal_reference_id)
    if row is None:
        return api_error(request, "NOT_FOUND")
    view = _submission_view(row[:7])
    return _json(status, view, location=view["links"]["self"] if status == 201 else None)


def _visible_submission(cur, submission_id, principal_id):
    cur.execute(f"SELECT {_SUBMISSION_COLUMNS} FROM {SCHEMA}.submission s JOIN {SCHEMA}.case_record c"
                f" ON c.case_record_id = s.case_record_id {_VIEWER_GRANT} WHERE s.submission_id = %s",
                (principal_id, submission_id))
    return cur.fetchone()


# ---------------------------------------------------------------- getSubmission / listSubmissions
async def get_submission(request: Request):
    runtime, principal, error = current_principal(request, "GETSUBMISSION")
    if error is not None:
        return error
    submission_id = _uuid(request.path_params["submission_id"])
    if submission_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "submission_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    return await run_in_threadpool(_get_submission, request, runtime, principal, submission_id)


def _get_submission(request, runtime, principal, submission_id):
    try:
        with _connect(runtime) as connection, connection.cursor() as cur:
            row = _visible_submission(cur, submission_id, principal.principal_reference_id)
    except (_Unavailable, psycopg.Error):
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    if row is None:
        return api_error(request, "NOT_FOUND")
    if not set(principal.roles) & set(OPERATIONS["getSubmission"]["roles"]):
        return api_error(request, "FORBIDDEN")
    return _json(200, _submission_view(row))


async def list_submissions(request: Request):
    runtime, principal, error = current_principal(request, "LISTSUBMISSIONS")
    if error is not None:
        return error
    case_id = _uuid(request.path_params["case_id"])
    if case_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "case_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    params, problems = _page_params(request, {"state": SUBMISSION_STATES, "received_from": "ts", "received_to": "ts"})
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_list_submissions, request, runtime, principal, case_id, params)


def _list_submissions(request, runtime, principal, case_id, params):
    try:
        with _connect(runtime) as connection, connection.cursor() as cur:
            _, denial = _authorize_case(request, runtime, principal, cur, "listSubmissions", case_id)
            if denial is not None:
                return denial
            where, args = ["s.case_record_id = %s"], [case_id]
            for key, clause in (("state", "s.processing_state = %s"), ("received_from", "s.received_at >= %s"),
                                ("received_to", "s.received_at < %s")):
                if key in params:
                    where.append(clause)
                    args.append(params[key])
            if params["cursor"]:
                where.append("(s.received_at, s.submission_id) < (%s, %s::uuid)")
                args += list(params["cursor"])
            cur.execute(f"SELECT {_SUBMISSION_COLUMNS} FROM {SCHEMA}.submission s WHERE " + " AND ".join(where)
                        + " ORDER BY s.received_at DESC, s.submission_id DESC LIMIT %s", args + [params["limit"] + 1])
            rows = cur.fetchall()
    except (_Unavailable, psycopg.Error):
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    page = {"limit": params["limit"]}
    if len(rows) > params["limit"]:
        rows = rows[:params["limit"]]
        page["next_cursor"] = _encode_cursor(rows[-1][5], rows[-1][0])
    return _json(200, {"items": [_submission_view(r) for r in rows], "page": page})


def install(app: FastAPI):
    app.add_api_route("/api/v1/cases", create_case, methods=["POST"])
    app.add_api_route("/api/v1/cases", list_cases, methods=["GET"])
    app.add_api_route("/api/v1/cases/{case_id}", get_case, methods=["GET"])
    app.add_api_route("/api/v1/cases/{case_id}/submissions", create_submission, methods=["POST"])
    app.add_api_route("/api/v1/cases/{case_id}/submissions", list_submissions, methods=["GET"])
    app.add_api_route("/api/v1/submissions/{submission_id}", get_submission, methods=["GET"])
