"""S5 governed evaluation: createEvaluations, listCaseEvaluations, getEvaluation and getDetectionResult (API-001 §13-14).

createEvaluations authorizes the caller (USER/ANALYST with case access), reads the submission's one FINALIZED text item
through the protected evidence store and runs the S4 extractor against the ACTIVE, verified bundle. In one transaction
it records the governed input envelope (bytes in the encrypted store), a REQUESTED evaluation, its single immutable
governed input artifact and the EVALUATION_STARTED audit, then answers 202.

The worker follows the DATA-001-WP2 completion protocol. It verifies the artifact digest and the pinned bundle, takes
the evaluation REQUESTED -> RUNNING with a new fence token and every write-once pin, and calls the existing Phase-3
kernel (evaluate_detection_from_governed). It then commits the DetectionResult, the rule projection, the audit and
COMPLETED together, compare-and-set on the fence token. A stale or fenced worker matches zero rows and rolls back;
the database rejects a result for anything but the live fence. Recovery re-dispatches REQUESTED work and fences RUNNING
work whose lease expired (FAILED_INFRASTRUCTURE); a retry is always a new evaluation.

getDetectionResult returns the exact stored result in the accepted STANDARD/DETAILED views; the stored digest is
re-verified on every read and every read is audited. Nothing here invents a verdict, score or field.
"""
import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import FastAPI, Request
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from knowledge.ai.governance import canonical_json
from knowledge.runtime.engine import ENGINE_VERSION
from knowledge.runtime.evaluator import DEFAULT_PROFILE
from knowledge.runtime.result import RESULT_CONTRACT_VERSION, _translate_component_versions, evaluate_detection_from_governed

from . import extraction, idempotency
from .audit import AuditEvent, AuditUnavailable, append as audit_append
from .auth import api_error, current_principal
from .cases import (_Unavailable, _audit_denial, _connect, _encode_cursor, _idempotent_error, _instant, _json, _page_params,
                    _retention_reference, _uuid, _visible_case, is_too_large, read_json_object)
from .content_store import ContentStoreUnavailable, IntegrityFailure
from .evidence import get_store
from .knowledge_seam import BundleRejected
from .principals import SCHEMA

OPERATIONS = {
    "createEvaluations": {"method": "POST", "path": "/api/v1/submissions/{submission_id}/evaluations", "roles": ("USER", "ANALYST"),
                          "resource_authorization": "CASE_ACCESS"},
    "listCaseEvaluations": {"method": "GET", "path": "/api/v1/cases/{case_id}/evaluations", "roles": ("USER", "ANALYST"),
                            "resource_authorization": "CASE_ACCESS"},
    "getEvaluation": {"method": "GET", "path": "/api/v1/evaluations/{evaluation_id}", "roles": ("USER", "ANALYST"),
                      "resource_authorization": "CASE_ACCESS"},
    "getDetectionResult": {"method": "GET", "path": "/api/v1/evaluations/{evaluation_id}/result", "roles": ("USER", "ANALYST"),
                           "resource_authorization": "CASE_DERIVED_CONTENT"},
}
ANALYSIS_MODES = ("DETERMINISTIC", "AI_ASSISTED_IF_ENABLED")
RESULT_VIEWS = ("STANDARD", "DETAILED")
# listCaseEvaluations filters (api-v1.json list.filters); state and availability map exactly as the responses do.
LIST_FILTERS = {"state": ("QUEUED", "RUNNING", "COMPLETED", "FAILED"), "submission_id": "uuid", "requested_from": "timestamp",
                "requested_to": "timestamp",
                "result_availability": ("NOT_YET_AVAILABLE", "AVAILABLE", "NOT_PRODUCED", "REMOVED_UNDER_GOVERNANCE")}
EXECUTION_LEASE = timedelta(seconds=60)          # implementation profile value; the contract leaves the length open
SCHEMA_VERSION = "1.0.0"                         # observation / indicator-observation contract version (KB-002)
CANONICAL = "TRUSTLENS_CANONICAL_JSON_V1"
EVALUABLE_CASE_STATES = ("OPEN", "UNDER_REVIEW")
TERMINAL = ("COMPLETED", "FAILED_PRECONDITION", "FAILED_INTEGRITY", "FAILED_INFRASTRUCTURE")
API_STATE = {"REQUESTED": "QUEUED", "RUNNING": "RUNNING", "RESULT_COMPUTED_PERSISTENCE_PENDING": "RUNNING",
             "COMPLETED": "COMPLETED", "FAILED_PRECONDITION": "FAILED", "FAILED_INTEGRITY": "FAILED", "FAILED_INFRASTRUCTURE": "FAILED"}
FAILURE_CLASS = {"FAILED_PRECONDITION": "PRECONDITION", "FAILED_INTEGRITY": "INTEGRITY", "FAILED_INFRASTRUCTURE": "INFRASTRUCTURE"}
FAILURE_REASON = {"NO_VALID_ACTIVE_BUNDLE": "KNOWLEDGE_UNAVAILABLE", "ACTIVE_BUNDLE_WITHDRAWN": "KNOWLEDGE_UNAVAILABLE",
                  "INVALID_TRUSTED_CONTEXT": "INPUT_NOT_EVALUABLE", "BUNDLE_INTEGRITY": "INTEGRITY_FAILURE",
                  "ARTIFACT_INTEGRITY": "INTEGRITY_FAILURE", "RESULT_ASSEMBLY_REJECTED": "INTEGRITY_FAILURE",
                  "PERSISTENCE_FAILED": "INFRASTRUCTURE_FAILURE", "RESULT_DURABILITY_UNCONFIRMED": "INFRASTRUCTURE_FAILURE",
                  "EXECUTION_LEASE_EXPIRED": "INFRASTRUCTURE_FAILURE"}
RETRY_GUIDANCE = {"KNOWLEDGE_UNAVAILABLE": "RETRY_AS_NEW_EVALUATION", "INPUT_NOT_EVALUABLE": "NOT_RETRYABLE",
                  "INTEGRITY_FAILURE": "NOT_RETRYABLE", "INFRASTRUCTURE_FAILURE": "RETRY_AS_NEW_EVALUATION"}
# UX-003 classification_presentation[NO_SCAM_PATTERN].meaning: the returned absence-of-finding notice (API-001 §14).
ABSENCE_OF_FINDING_NOTICE = ("No governed scam pattern was established from the evidence evaluated. This is not a "
                             "determination that the content is safe or legitimate.")
_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_dispatch_lock = threading.Lock()
_running: set[str] = set()


class _Refused(Exception):
    def __init__(self, response):
        super().__init__()
        self.response = response


def evaluation_schema_active(cur) -> bool:
    cur.execute("SELECT to_regclass('trustlens.detection_result') IS NOT NULL AND to_regclass('trustlens.evidence_upload_intent') IS NOT NULL")
    return bool(cur.fetchone()[0])


def _open(request, runtime):
    try:
        connection = _connect(runtime)
    except _Unavailable:
        raise _Refused(api_error(request, "DEPENDENCY_UNAVAILABLE")) from None
    try:
        with connection.cursor() as cur:
            if not evaluation_schema_active(cur):
                connection.close()
                raise _Refused(api_error(request, "DEPENDENCY_UNAVAILABLE"))
    except psycopg.Error:
        connection.close()
        raise _Refused(api_error(request, "DEPENDENCY_UNAVAILABLE")) from None
    return connection


def _authorize(request, runtime, principal, cur, operation_id, case_id):
    """API-001 §5: no visibility -> masked 404 (whatever the role); visible without a permitted role -> 403 (audited)."""
    case = _visible_case(cur, case_id, principal.principal_reference_id) if case_id else None
    if case is None:
        raise _Refused(api_error(request, "NOT_FOUND"))
    if not set(principal.roles) & set(OPERATIONS[operation_id]["roles"]):
        _audit_denial(runtime, request, principal, case_id, "ROLE_OWNERSHIP_OR_CONTENT_PERMISSION_REQUIRED", operation_id)
        raise _Refused(api_error(request, "FORBIDDEN"))
    return case


def _instant_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _audit(cur, event_type, outcome, target_kind, target_id, case_id, evaluation_id, correlation_id, *, actor=None,
           metadata=None, bundle=None, evidence_id=None):
    audit_append(cur, AuditEvent(event_type=event_type, outcome=outcome, actor_kind="HUMAN" if actor else "SYSTEM",
                                 actor_principal_id=actor, target_kind=target_kind, target_id=target_id, case_record_id=case_id,
                                 evaluation_id=evaluation_id, bundle_content_digest=bundle, evidence_item_id=evidence_id,
                                 correlation_id=correlation_id, safe_metadata=metadata))


# ---------------------------------------------------------------- views
_EVAL_COLUMNS = ("e.evaluation_id::text, e.case_record_id::text, e.submission_id::text, e.origin, e.predecessor_evaluation_id::text,"
                 " e.status, e.failure_category, e.requested_at, e.completed_at, e.ai_extraction_enabled, e.ai_attempted, e.ai_used,"
                 " e.ai_fallback_reason, e.engine_version, e.result_contract_version, e.bundle_content_digest, e.bundle_version,"
                 " e.evaluation_profile_id, e.evaluation_timestamp,"
                 " EXISTS (SELECT 1 FROM trustlens.detection_result r WHERE r.evaluation_id = e.evaluation_id)")


# Same mapping as _view(): AVAILABLE only for COMPLETED with its stored result, NOT_PRODUCED for failures.
_AVAILABILITY_SQL = ("CASE WHEN e.status = 'COMPLETED' AND EXISTS (SELECT 1 FROM trustlens.detection_result r"
                     " WHERE r.evaluation_id = e.evaluation_id) THEN 'AVAILABLE'"
                     " WHEN e.status IN ('FAILED_PRECONDITION', 'FAILED_INTEGRITY', 'FAILED_INFRASTRUCTURE') THEN 'NOT_PRODUCED'"
                     " ELSE 'NOT_YET_AVAILABLE' END")


def _evaluation_row(cur, evaluation_id):
    cur.execute(f"SELECT {_EVAL_COLUMNS} FROM {SCHEMA}.evaluation e WHERE e.evaluation_id = %s", (evaluation_id,))
    return cur.fetchone()


def _view(row) -> dict:
    (evaluation_id, case_id, submission_id, origin, predecessor, status, category, requested, completed, ai_enabled,
     ai_attempted, ai_used, ai_fallback, engine, contract, digest, bundle_version, profile, timestamp, has_result) = row
    failure = None
    if status in FAILURE_CLASS:
        reason = FAILURE_REASON[category]
        failure = {"failure_class": FAILURE_CLASS[status], "reason": reason, "retry_guidance": RETRY_GUIDANCE[reason]}
    availability = ("AVAILABLE" if status == "COMPLETED" and has_result else "NOT_PRODUCED" if status in FAILURE_CLASS
                    else "NOT_YET_AVAILABLE")
    provenance = None
    if digest:                                    # pinned on entering RUNNING; never a mutable "current" pointer
        provenance = {"engine_version": engine, "result_contract_version": contract, "bundle_content_digest": digest,
                      "bundle_version": bundle_version, "evaluation_profile_id": profile,
                      "evaluation_timestamp": _instant(timestamp)}
    links = {"self": f"/api/v1/evaluations/{evaluation_id}",
             "related": {"submission": f"/api/v1/submissions/{submission_id}", "case": f"/api/v1/cases/{case_id}"}}
    if availability == "AVAILABLE":
        links["related"]["result"] = f"/api/v1/evaluations/{evaluation_id}/result"
    return {"evaluation_id": evaluation_id, "case_id": case_id, "submission_id": submission_id, "origin": origin,
            "predecessor_evaluation_id": predecessor, "state": API_STATE[status], "failure": failure,
            "result_availability": availability, "requested_at": _instant(requested), "completed_at": _instant(completed),
            "ai_usage": {"requested": ai_attempted or ai_fallback is not None, "enabled_by_policy": ai_enabled, "used": ai_used,
                         "fallback_reason": ai_fallback},
            "provenance": provenance, "links": links}


# ---------------------------------------------------------------- createEvaluations
def _validate_create(body) -> tuple[dict | None, list | None]:
    allowed = {"analysis_mode", "predecessor_evaluation_id", "reason_code"}
    errors = [{"field": k, "code": "UNKNOWN_FIELD", "message": "Field is not accepted."} for k in body if k not in allowed]
    if "analysis_mode" in body and body["analysis_mode"] not in ANALYSIS_MODES:
        errors.append({"field": "analysis_mode", "code": "INVALID_VALUE", "message": "Value is not in the accepted vocabulary."})
    if "predecessor_evaluation_id" in body and (not isinstance(body["predecessor_evaluation_id"], str)
                                                or _uuid(body["predecessor_evaluation_id"]) is None):
        errors.append({"field": "predecessor_evaluation_id", "code": "INVALID_UUID", "message": "Not a UUID."})
    if "reason_code" in body and (not isinstance(body["reason_code"], str) or not _REASON_CODE.match(body["reason_code"])):
        errors.append({"field": "reason_code", "code": "INVALID_VALUE", "message": "Use an upper-case reason code."})
    return (None, errors) if errors else (body, None)


async def create_evaluations(request: Request):
    runtime, principal, error = current_principal(request, "CREATEEVALUATIONS")
    if error is not None:
        return error
    submission_id = _uuid(request.path_params["submission_id"])
    if submission_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "submission_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    key = request.headers.get("idempotency-key")
    if not idempotency.valid_key(key):
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "Idempotency-Key", "code": "REQUIRED", "message": "Send a high-entropy key (16-255 URL-safe characters)."}])
    body, problems = await read_json_object(request)
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=[] if is_too_large(problems) else problems)
    body, problems = _validate_create(body)
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_create_evaluations, request, runtime, principal, submission_id, key, body)


def _finalized_items(cur, submission_id):
    cur.execute(f"SELECT e.evidence_item_id::text FROM {SCHEMA}.evidence_item e WHERE e.submission_id = %s"
                " AND e.content_state = 'FINALIZED' AND e.artifact_kind = 'TEXT_BODY' ORDER BY e.finalized_at", (submission_id,))
    return [r[0] for r in cur.fetchall()]


def _origin(cur, submission_id, body):
    """Server-derived origin (API-001 §13); None means the predecessor is not a terminal evaluation of this submission."""
    predecessor = body.get("predecessor_evaluation_id")
    if predecessor is None:
        return "INITIAL", None
    cur.execute(f"SELECT status FROM {SCHEMA}.evaluation WHERE evaluation_id = %s AND submission_id = %s", (predecessor, submission_id))
    row = cur.fetchone()
    if row is None or row[0] not in TERMINAL:
        return None, predecessor
    if row[0] == "FAILED_INFRASTRUCTURE":
        return "RETRY_AFTER_FAILURE", predecessor
    return ("AI_RE_EXTRACTION" if body.get("analysis_mode") == "AI_ASSISTED_IF_ENABLED" else "RE_EVALUATION"), predecessor


def _create_evaluations(request, runtime, principal, submission_id, key, body):
    scope = f"/api/v1/submissions/{submission_id}/evaluations"
    try:
        connection = _open(request, runtime)
    except _Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                cur.execute(f"SELECT case_record_id::text FROM {SCHEMA}.submission WHERE submission_id = %s", (submission_id,))
                row = cur.fetchone()
                case = _authorize(request, runtime, principal, cur, "createEvaluations", row[0] if row else None)
                case_id = case[0]
            outcome = idempotency.claim(connection, principal.principal_reference_id, "createEvaluations", scope, key,
                                        idempotency.semantic_digest("createEvaluations", scope, body), supersession=True)
        except _Refused as refused:
            return refused.response
        except (idempotency.KeyReused, idempotency.InProgress) as e:
            return _idempotent_error(request, e)
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if isinstance(outcome, idempotency.Replay):
            return _replay(request, runtime, connection, outcome)
        try:
            with connection.cursor() as cur:
                items = _finalized_items(cur, submission_id)
                origin, predecessor = _origin(cur, submission_id, body)
            if case[1] not in EVALUABLE_CASE_STATES or len(items) != 1 or origin is None:
                with connection.transaction(), connection.cursor() as cur:
                    idempotency.fail_terminal(cur, outcome, 409, "STATE_CONFLICT")
                return api_error(request, "STATE_CONFLICT")
            governed = extraction.extract_finalized_evidence(runtime, principal, items[0], correlation_id=request.state.request_id)
            envelope_id = _store_envelope(connection, runtime, submission_id, items[0], governed)
            evaluation_id = str(uuid.uuid4())
            with connection.transaction(), connection.cursor() as cur:
                _insert_evaluation(cur, evaluation_id, case_id, submission_id, envelope_id, governed, origin, predecessor, body,
                                   principal, request.state.request_id)
                _audit(cur, "EVALUATION_STARTED", "SUCCEEDED", "EVALUATION", evaluation_id, case_id, evaluation_id,
                       request.state.request_id, actor=principal.principal_reference_id, metadata={"origin": origin},
                       bundle=governed.knowledge_content_digest)
                idempotency.complete(cur, outcome, 202, "evaluation", evaluation_id)
        except extraction.ExtractionRefused:
            idempotency.release(connection, outcome, 409, "STATE_CONFLICT")
            return api_error(request, "STATE_CONFLICT")
        except extraction.ExtractionUnavailable as unavailable:
            if unavailable.category == "INTEGRITY_FAILURE":
                with connection.transaction(), connection.cursor() as cur:
                    idempotency.fail_terminal(cur, outcome, 500, "INTEGRITY_FAILURE")
                return api_error(request, "INTEGRITY_FAILURE")
            idempotency.release(connection, outcome, 503, "DEPENDENCY_UNAVAILABLE")
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        except _EnvelopeConflict:
            with connection.transaction(), connection.cursor() as cur:
                idempotency.fail_terminal(cur, outcome, 500, "INTEGRITY_FAILURE")
            return api_error(request, "INTEGRITY_FAILURE")
        except idempotency.StaleClaim:
            return api_error(request, "IDEMPOTENCY_IN_PROGRESS")
        except (psycopg.Error, _Unavailable, AuditUnavailable, ContentStoreUnavailable, IntegrityFailure, OSError, ValueError):
            idempotency.release(connection, outcome, 503, "DEPENDENCY_UNAVAILABLE")
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        with connection.cursor() as cur:
            view = _view(_evaluation_row(cur, evaluation_id))
    return _accepted(runtime, [view])


def _accepted(runtime, views):
    response = _json(202, {"evaluations": views})
    pending = [v["evaluation_id"] for v in views if v["state"] == "QUEUED"]
    if pending:                                   # after the response; recovery covers a crash before this runs
        response.background = BackgroundTask(dispatch, runtime, pending)
    return response


def _replay(request, runtime, connection, replay):
    if replay.error_code:
        return api_error(request, replay.error_code)
    with connection.cursor() as cur:
        row = _evaluation_row(cur, replay.resource_id)
    if row is None:
        return api_error(request, "NOT_FOUND")
    return _accepted(runtime, [_view(row)])


class _EnvelopeConflict(Exception):
    """The stored envelope for this input differs from the one derived now; never silently replaced."""


def _store_envelope(connection, runtime, submission_id, evidence_id, governed) -> str:
    """The envelope carries raw/normalized text, so its bytes go only to the encrypted store (C2 manifest in the DB).
    One envelope per input_id: an identical envelope is reused; a different one fails closed."""
    try:
        return _store_envelope_once(connection, runtime, submission_id, evidence_id, governed)
    except _Retry:                               # a concurrent request stored it first: reuse it (or fail closed)
        return _store_envelope_once(connection, runtime, submission_id, evidence_id, governed)


def _store_envelope_once(connection, runtime, submission_id, evidence_id, governed) -> str:
    data = canonical_json(extraction._thaw(governed.envelope)).encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    with connection.cursor() as cur:
        cur.execute(f"SELECT input_envelope_record_id::text, envelope_sha256, content_state FROM {SCHEMA}.input_envelope_record"
                    " WHERE input_id = %s", (governed.input_id,))
        existing = cur.fetchone()
    if existing:
        if existing[1] != sha or existing[2] != "FINALIZED":
            raise _EnvelopeConflict()
        return existing[0]
    store = get_store(runtime)
    if store is None:
        raise ContentStoreUnavailable("store unavailable")
    stored = store.put(data)
    store.verify(stored.locator, sha, len(data))
    record_id, key = str(uuid.uuid4()), str(uuid.uuid4())
    with connection.transaction(), connection.cursor() as cur:
        retention = _retention_reference(cur)
        cur.execute(f"INSERT INTO {SCHEMA}.input_envelope_record (input_envelope_record_id, submission_id, input_id, envelope_version,"
                    " envelope_sha256, detected_language, detected_script, created_at, ecs_locator, content_state, state_changed_at,"
                    " verified_at, finalized_at, idempotency_key, retention_policy_reference_id)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, now(), %s, 'FINALIZED', now(), now(), now(), %s, %s)"
                    " ON CONFLICT (input_id) DO NOTHING RETURNING input_envelope_record_id::text",
                    (record_id, submission_id, governed.input_id, extraction.ENVELOPE_VERSION, sha, list(governed.language),
                     list(governed.script), stored.locator, key, retention))
        if cur.fetchone() is None:
            raise _Retry()
        cur.execute(f"INSERT INTO {SCHEMA}.cross_store_operation (cross_store_operation_id, idempotency_key, operation_kind,"
                    " owner_module, target_table, target_id, ecs_object_ref, expected_sha256, state, attempt_count,"
                    " last_failure_category, next_attempt_not_before, created_at, state_changed_at, terminal_at)"
                    " VALUES (%s, %s, 'ENVELOPE_STORE', 'GOVERNED_EVALUATION', 'input_envelope_record', %s, %s, %s, 'FINALIZED',"
                    " 1, NULL, NULL, now(), now(), now())", (str(uuid.uuid4()), key, record_id, stored.locator, sha))
        cur.execute(f"INSERT INTO {SCHEMA}.input_envelope_source (input_envelope_source_id, input_envelope_record_id, evidence_item_id,"
                    " evidence_derivative_id, envelope_attachment_id) VALUES (%s, %s, %s, NULL, NULL)",
                    (str(uuid.uuid4()), record_id, evidence_id))
    return record_id


class _Retry(Exception):
    pass


def _artifact(governed) -> dict:
    return {"observations": extraction._thaw(governed.observations),
            "indicator_observations": extraction._thaw(governed.indicator_observations),
            "evaluation_context": {"input_id": governed.input_id, "input_support_status": governed.input_support_status,
                                   "language": list(governed.language), "script": list(governed.script),
                                   "whole_evaluation_errors": extraction._thaw(governed.whole_evaluation_errors),
                                   "support_gaps": list(governed.support_gaps),
                                   "knowledge_content_digest": governed.knowledge_content_digest,
                                   "extractor": dict(governed.extractor)}}


def _insert_evaluation(cur, evaluation_id, case_id, submission_id, envelope_id, governed, origin, predecessor, body, principal,
                       correlation_id):
    ai_requested = body.get("analysis_mode") == "AI_ASSISTED_IF_ENABLED"
    cur.execute(f"INSERT INTO {SCHEMA}.evaluation (evaluation_id, case_record_id, submission_id, input_envelope_record_id, input_id,"
                " origin, predecessor_evaluation_id, initiated_by_principal_id, correlation_id, status, requested_at,"
                " ai_extraction_enabled, ai_attempted, ai_used, ai_fallback_reason)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'REQUESTED', now(), false, false, false, %s)",
                (evaluation_id, case_id, submission_id, envelope_id, governed.input_id, origin, predecessor,
                 principal.principal_reference_id, correlation_id, "AI_DISABLED" if ai_requested else None))
    text = canonical_json(_artifact(governed))
    artifact_id = str(uuid.uuid4())
    cur.execute(f"INSERT INTO {SCHEMA}.governed_input_artifact (governed_input_artifact_id, evaluation_id, input_envelope_record_id,"
                " input_id, governed_artifact_digest, canonical_json_version, storage_mode, artifact_canonical_json, ecs_locator,"
                " observation_schema_version, indicator_observation_schema_version, created_at, retention_policy_reference_id)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'INLINE', %s, NULL, %s, %s, now(), %s)",
                (artifact_id, evaluation_id, envelope_id, governed.input_id, _digest(text), CANONICAL, text, SCHEMA_VERSION,
                 SCHEMA_VERSION, _retention_reference(cur)))
    refs = [(str(uuid.uuid4()), artifact_id, "NORMALIZED_OBSERVATION", o["observation_id"], o["status"], None, False)
            for o in governed.observations]
    refs += [(str(uuid.uuid4()), artifact_id, "INDICATOR_OBSERVATION", i["indicator_id"], i["matched"], i.get("extraction_method"), False)
             for i in governed.indicator_observations]
    if refs:
        cur.executemany(f"INSERT INTO {SCHEMA}.governed_observation_reference (governed_observation_reference_id,"
                        " governed_input_artifact_id, observation_kind, observation_ref, status, extraction_method, is_model_derived)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s)", refs)


# ---------------------------------------------------------------- the worker (DATA-001-WP2 completion protocol)
class _Stale(Exception):
    """This worker no longer owns the evaluation (claimed, fenced or completed elsewhere): roll back, change nothing."""


def dispatch(runtime, evaluation_ids):
    for evaluation_id in evaluation_ids:
        with _dispatch_lock:
            if evaluation_id in _running:
                continue
            _running.add(evaluation_id)
        try:
            run_evaluation(runtime, evaluation_id)
        except Exception:             # never let a background failure escape; recovery and fencing cover it
            pass
        finally:
            with _dispatch_lock:
                _running.discard(evaluation_id)


def _pins(rk):
    profile = DEFAULT_PROFILE
    return {"bundle_content_digest": rk.content_digest, "bundle_version": rk.bundle_version,
            "manifest_schema_version": rk.manifest_schema_version, "commit_sha": rk.commit_sha, "engine_version": ENGINE_VERSION,
            "result_contract_version": RESULT_CONTRACT_VERSION, "evaluation_profile_id": getattr(profile, "profile_id", "profile-v1"),
            "extraction_confidence_gate": profile.extraction_confidence_gate, "risk_matrix_id": profile.risk_matrix_id,
            "confidence_policy_id": profile.confidence_policy_id, "action_policy_version": rk.action_policy_version,
            "component_versions": _translate_component_versions(rk.component_versions)}


def run_evaluation(runtime, evaluation_id, *, before_completion=None):
    """Execute one REQUESTED evaluation. `before_completion` is a test seam between compute and the fenced commit."""
    correlation = str(uuid.uuid4())
    connection = _connect(runtime)
    with connection:
        with connection.cursor() as cur:
            cur.execute(f"SELECT e.status, e.case_record_id::text, a.artifact_canonical_json, a.governed_artifact_digest"
                        f" FROM {SCHEMA}.evaluation e JOIN {SCHEMA}.governed_input_artifact a ON a.evaluation_id = e.evaluation_id"
                        " WHERE e.evaluation_id = %s", (evaluation_id,))
            row = cur.fetchone()
        if row is None or row[0] != "REQUESTED":
            return
        _, case_id, text, digest = row
        try:
            artifact = json.loads(text)
            intact = _digest(text) == digest and canonical_json(artifact) == text
        except ValueError:
            intact, artifact = False, None
        if not intact:
            return _fail_precondition(connection, evaluation_id, case_id, "ARTIFACT_INTEGRITY", correlation)
        context = artifact["evaluation_context"]
        bundle = context["knowledge_content_digest"]
        with connection.cursor() as cur:
            cur.execute(f"SELECT governance_eligibility FROM {SCHEMA}.knowledge_bundle_reference WHERE content_digest = %s", (bundle,))
            eligibility = cur.fetchone()
        if eligibility is None or eligibility[0] != "ELIGIBLE":
            category = "ACTIVE_BUNDLE_WITHDRAWN" if eligibility and eligibility[0] == "WITHDRAWN" else "NO_VALID_ACTIVE_BUNDLE"
            return _fail_precondition(connection, evaluation_id, case_id, category, correlation)
        if runtime.knowledge_verifier is None:
            return _fail_precondition(connection, evaluation_id, case_id, "NO_VALID_ACTIVE_BUNDLE", correlation)
        try:
            rk = runtime.knowledge_verifier.verify(bundle)       # the exact pinned bundle, re-verified (cached per digest)
        except BundleRejected:
            return _fail_precondition(connection, evaluation_id, case_id, "BUNDLE_INTEGRITY", correlation)
        pins = _pins(rk)
        token, timestamp = str(uuid.uuid4()), datetime.now(timezone.utc)
        with connection.transaction(), connection.cursor() as cur:
            cur.execute(f"UPDATE {SCHEMA}.evaluation SET status = 'RUNNING', started_at = now(), execution_fence_token = %s,"
                        " execution_lease_expires_at = now() + %s, bundle_content_digest = %s, bundle_version = %s,"
                        " manifest_schema_version = %s, commit_sha = %s, engine_version = %s, result_contract_version = %s,"
                        " evaluation_profile_id = %s, extraction_confidence_gate = %s, risk_matrix_id = %s, confidence_policy_id = %s,"
                        " action_policy_version = %s, component_versions = %s, evaluation_timestamp = %s, input_support_status = %s,"
                        " language = %s, script = %s WHERE evaluation_id = %s AND status = 'REQUESTED'",
                        (token, EXECUTION_LEASE, pins["bundle_content_digest"], pins["bundle_version"], pins["manifest_schema_version"],
                         pins["commit_sha"], pins["engine_version"], pins["result_contract_version"], pins["evaluation_profile_id"],
                         pins["extraction_confidence_gate"], pins["risk_matrix_id"], pins["confidence_policy_id"],
                         pins["action_policy_version"], json.dumps(pins["component_versions"]), timestamp,
                         context["input_support_status"], context["language"], context["script"], evaluation_id))
            if cur.rowcount != 1:
                return                                           # another worker claimed it first
        try:
            result = evaluate_detection_from_governed(
                rk, artifact["indicator_observations"], artifact["observations"], evaluation_id=evaluation_id,
                evaluation_timestamp=_instant_text(timestamp), input_id=context["input_id"], language=context["language"],
                script=context["script"], input_support_status=context["input_support_status"],
                whole_evaluation_errors=context["whole_evaluation_errors"])
            document = result.as_dict()
            _check_document(document, pins, evaluation_id, context)
        except Exception:                                        # the kernel refused or produced an inconsistent result
            return _fail_running(connection, evaluation_id, case_id, token, "FAILED_INTEGRITY", "RESULT_ASSEMBLY_REJECTED", correlation)
        if before_completion:
            before_completion()
        try:
            _complete(connection, evaluation_id, case_id, token, timestamp, document, pins, digest, context, correlation)
        except _Stale:
            return
        except (psycopg.Error, AuditUnavailable, ValueError):
            _fail_running(connection, evaluation_id, case_id, token, "FAILED_INFRASTRUCTURE", "PERSISTENCE_FAILED", correlation)


def _check_document(document, pins, evaluation_id, context):
    provenance = document["provenance"]
    profile = provenance["evaluation_profile"]
    expected = {"bundle_content_digest": provenance["bundle_content_digest"], "bundle_version": provenance["bundle_version"],
                "commit_sha": provenance.get("commit_sha"), "engine_version": provenance["engine_version"],
                "result_contract_version": document["result_contract_version"], "evaluation_profile_id": profile["profile_id"],
                "extraction_confidence_gate": profile["extraction_confidence_gate"], "risk_matrix_id": profile["risk_matrix_id"],
                "confidence_policy_id": profile["confidence_policy_id"],
                "action_policy_version": provenance["component_versions"].get("action_policy"),
                "component_versions": provenance["component_versions"]}
    if any(pins[k] != v for k, v in expected.items()) or document["evaluation_id"] != evaluation_id \
            or document["input_id"] != context["input_id"] or document["input_support_status"] != context["input_support_status"]:
        raise ValueError("result provenance does not equal the evaluation pins")


def _replay_material_digest(evaluation_id, timestamp, pins, artifact_digest, result_digest, context) -> str:
    material = {"evaluation_id": evaluation_id, "evaluation_timestamp": _instant_text(timestamp), "input_id": context["input_id"],
                "pins": pins, "input_support_status": context["input_support_status"], "language": context["language"],
                "script": context["script"], "governed_artifact_digest": artifact_digest, "result_digest": result_digest}
    return _digest(canonical_json(material))


def _complete(connection, evaluation_id, case_id, token, timestamp, document, pins, artifact_digest, context, correlation):
    text = canonical_json(document)
    result_digest = _digest(text)
    result_id = str(uuid.uuid4())
    with connection.transaction(), connection.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {SCHEMA}.evaluation WHERE evaluation_id = %s AND status IN ('RUNNING', 'RESULT_COMPUTED_PERSISTENCE_PENDING')"
                    " AND execution_fence_token = %s FOR UPDATE", (evaluation_id, token))
        if cur.fetchone() is None:
            raise _Stale()
        profile = document["provenance"]["evaluation_profile"]
        cur.execute(f"INSERT INTO {SCHEMA}.detection_result (detection_result_id, evaluation_id, execution_fence_token,"
                    " result_contract_version, result_digest, canonical_json_version, storage_mode, result_canonical_json, ecs_locator,"
                    " input_support_status, classification, decision_severity, matched_evidence_strength, risk_level,"
                    " detection_confidence, degraded, engine_version, bundle_version, bundle_content_digest, commit_sha,"
                    " evaluation_profile_id, extraction_confidence_gate, risk_matrix_id, confidence_policy_id, action_policy_version,"
                    " component_versions, evaluation_timestamp, input_id, language, script, persisted_at, retention_policy_reference_id)"
                    " VALUES (%s, %s, %s, %s, %s, %s, 'INLINE', %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
                    " %s, %s, %s, %s, %s, now(), %s)",
                    (result_id, evaluation_id, token, document["result_contract_version"], result_digest, CANONICAL, text,
                     document["input_support_status"], document["classification"], document["decision_severity"],
                     document["matched_evidence_strength"], document["risk_level"], document["detection_confidence"],
                     bool(document.get("degraded", False)), document["provenance"]["engine_version"],
                     document["provenance"]["bundle_version"], document["provenance"]["bundle_content_digest"],
                     document["provenance"].get("commit_sha"), profile["profile_id"], profile["extraction_confidence_gate"],
                     profile["risk_matrix_id"], profile["confidence_policy_id"], pins["action_policy_version"],
                     json.dumps(document["provenance"]["component_versions"]), timestamp, document["input_id"],
                     document["language"], document["script"], _retention_reference(cur)))
        rows = [(str(uuid.uuid4()), result_id, n, r["rule_id"], r["rule_version"], r["kind"], r["evaluation_state"],
                 bool(r.get("governing", False)), r.get("effective_severity"), r.get("rule_evidence_strength"),
                 r.get("rule_detection_confidence")) for n, r in enumerate(document.get("rule_results", []))]
        if rows:
            cur.executemany(f"INSERT INTO {SCHEMA}.rule_result_projection (rule_result_projection_id, detection_result_id, ordinal,"
                            " rule_id, rule_version, kind, evaluation_state, is_governing, effective_severity, rule_evidence_strength,"
                            " rule_detection_confidence) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", rows)
        _audit(cur, "RESULT_PERSISTED", "SUCCEEDED", "DETECTION_RESULT", result_id, case_id, evaluation_id, correlation,
               metadata={"result_digest": result_digest}, bundle=pins["bundle_content_digest"])
        _audit(cur, "EVALUATION_COMPLETED", "SUCCEEDED", "EVALUATION", evaluation_id, case_id, evaluation_id, correlation,
               bundle=pins["bundle_content_digest"])
        cur.execute(f"UPDATE {SCHEMA}.evaluation SET status = 'COMPLETED', result_computed_at = now(), completed_at = now(),"
                    " replay_material_digest = %s WHERE evaluation_id = %s"
                    " AND status IN ('RUNNING', 'RESULT_COMPUTED_PERSISTENCE_PENDING') AND execution_fence_token = %s",
                    (_replay_material_digest(evaluation_id, timestamp, pins, artifact_digest, result_digest, context),
                     evaluation_id, token))
        if cur.rowcount != 1:
            raise _Stale()


def _fail_precondition(connection, evaluation_id, case_id, category, correlation):
    with connection.transaction(), connection.cursor() as cur:
        cur.execute(f"UPDATE {SCHEMA}.evaluation SET status = 'FAILED_PRECONDITION', failure_category = %s, failed_at = now()"
                    " WHERE evaluation_id = %s AND status = 'REQUESTED'", (category, evaluation_id))
        if cur.rowcount == 1:
            _audit(cur, "EVALUATION_FAILED", "FAILED", "EVALUATION", evaluation_id, case_id, evaluation_id, correlation,
                   metadata={"reason": category})


def _fail_running(connection, evaluation_id, case_id, token, status, category, correlation):
    """Fenced failure: compare-and-set on the live token, which is cleared so no result can ever reference it."""
    try:
        with connection.transaction(), connection.cursor() as cur:
            cur.execute(f"UPDATE {SCHEMA}.evaluation SET status = %s, failure_category = %s, failed_at = now(),"
                        " execution_fence_token = NULL WHERE evaluation_id = %s"
                        " AND status IN ('RUNNING', 'RESULT_COMPUTED_PERSISTENCE_PENDING') AND execution_fence_token = %s",
                        (status, category, evaluation_id, token))
            if cur.rowcount == 1:
                _audit(cur, "EVALUATION_FAILED", "FAILED", "EVALUATION", evaluation_id, case_id, evaluation_id, correlation,
                       metadata={"reason": category})
    except psycopg.Error:
        pass                          # the lease expires and recovery fences it


def recover(runtime, limit=50) -> dict:
    """Crash recovery: fence RUNNING work whose lease expired (FAILED_INFRASTRUCTURE, never resurrected), then run
    REQUESTED work that was never dispatched. Safe to run concurrently: every step is compare-and-set."""
    correlation = str(uuid.uuid4())
    connection = _connect(runtime)
    with connection:
        with connection.transaction(), connection.cursor() as cur:
            cur.execute(f"UPDATE {SCHEMA}.evaluation SET status = 'FAILED_INFRASTRUCTURE', failure_category = 'EXECUTION_LEASE_EXPIRED',"
                        " failed_at = now(), execution_fence_token = NULL"
                        " WHERE status IN ('RUNNING', 'RESULT_COMPUTED_PERSISTENCE_PENDING') AND execution_lease_expires_at < now()"
                        " RETURNING evaluation_id::text, case_record_id::text")
            fenced = cur.fetchall()
            for evaluation_id, case_id in fenced:
                _audit(cur, "EVALUATION_FAILED", "FAILED", "EVALUATION", evaluation_id, case_id, evaluation_id, correlation,
                       metadata={"reason": "EXECUTION_LEASE_EXPIRED"})
        with connection.cursor() as cur:
            cur.execute(f"SELECT evaluation_id::text FROM {SCHEMA}.evaluation WHERE status = 'REQUESTED' ORDER BY requested_at LIMIT %s",
                        (limit,))
            queued = [r[0] for r in cur.fetchall()]
    dispatch(runtime, queued)
    return {"fenced": [f[0] for f in fenced], "dispatched": queued}


def start_recovery(runtime, interval_seconds=30.0):
    """Background recovery loop for the served application (startup + every interval). Never started by tests."""
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            try:
                recover(runtime)
            except Exception:
                pass
            stop.wait(interval_seconds)

    threading.Thread(target=loop, name="trustlens-evaluation-recovery", daemon=True).start()
    return stop


# ---------------------------------------------------------------- reads
async def get_evaluation(request: Request):
    runtime, principal, error = current_principal(request, "GETEVALUATION")
    if error is not None:
        return error
    evaluation_id = _uuid(request.path_params["evaluation_id"])
    if evaluation_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "evaluation_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    return await run_in_threadpool(_get_evaluation, request, runtime, principal, evaluation_id)


def _get_evaluation(request, runtime, principal, evaluation_id):
    try:
        connection = _open(request, runtime)
    except _Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                row = _evaluation_row(cur, evaluation_id)
                _authorize(request, runtime, principal, cur, "getEvaluation", row[1] if row else None)
                return _json(200, _view(row))
        except _Refused as refused:
            return refused.response
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")


async def list_case_evaluations(request: Request):
    runtime, principal, error = current_principal(request, "LISTCASEEVALUATIONS")
    if error is not None:
        return error
    case_id = _uuid(request.path_params["case_id"])
    if case_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "case_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    params, problems = _page_params(request, LIST_FILTERS)
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_list_case_evaluations, request, runtime, principal, case_id, params)


def _list_case_evaluations(request, runtime, principal, case_id, params):
    try:
        connection = _open(request, runtime)
    except _Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                _authorize(request, runtime, principal, cur, "listCaseEvaluations", case_id)
                where, args = ["e.case_record_id = %s"], [case_id]
                if "state" in params:
                    where.append("e.status = ANY(%s)")
                    args.append([status for status, api in API_STATE.items() if api == params["state"]])
                if "submission_id" in params:
                    where.append("e.submission_id = %s")
                    args.append(params["submission_id"])
                if "requested_from" in params:
                    where.append("e.requested_at >= %s")
                    args.append(params["requested_from"])
                if "requested_to" in params:
                    where.append("e.requested_at <= %s")
                    args.append(params["requested_to"])
                if "result_availability" in params:
                    where.append(f"({_AVAILABILITY_SQL}) = %s")
                    args.append(params["result_availability"])
                if params["cursor"]:
                    where.append("(e.requested_at, e.evaluation_id) < (%s, %s::uuid)")
                    args += list(params["cursor"])
                cur.execute(f"SELECT {_EVAL_COLUMNS} FROM {SCHEMA}.evaluation e WHERE " + " AND ".join(where)
                            + " ORDER BY e.requested_at DESC, e.evaluation_id DESC LIMIT %s", args + [params["limit"] + 1])
                rows = cur.fetchall()
        except _Refused as refused:
            return refused.response
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
    page = {"limit": params["limit"]}
    if len(rows) > params["limit"]:
        rows = rows[:params["limit"]]
        page["next_cursor"] = _encode_cursor(rows[-1][7], rows[-1][0])
    return _json(200, {"items": [_view(r) for r in rows], "page": page})


async def get_detection_result(request: Request):
    runtime, principal, error = current_principal(request, "GETDETECTIONRESULT")
    if error is not None:
        return error
    evaluation_id = _uuid(request.path_params["evaluation_id"])
    if evaluation_id is None:
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "evaluation_id", "code": "INVALID_UUID", "message": "Not a UUID."}])
    params = dict(request.query_params)
    problems = [{"field": k, "code": "UNKNOWN_PARAMETER", "message": "Parameter is not accepted."} for k in params if k != "view"]
    if len(request.query_params.getlist("view")) > 1:
        problems.append({"field": "view", "code": "DUPLICATE", "message": "Parameter repeated."})
    view = params.get("view", "STANDARD")
    if view not in RESULT_VIEWS:
        problems.append({"field": "view", "code": "INVALID_VALUE", "message": "Value is not in the accepted vocabulary."})
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_get_detection_result, request, runtime, principal, evaluation_id, view)


def view_permitted(principal, case, view) -> bool:
    """UX-003 view_access / API-001 §14: STANDARD for the owner or an assigned analyst, each with evidence-content
    permission; DETAILED for an assigned analyst with that permission only. Break-glass and administrators: none."""
    grant_kind, content = case[6], bool(case[7])
    if not content:
        return False
    if "ANALYST" in principal.roles and grant_kind == "ASSIGNED_ANALYST":
        return True
    return view == "STANDARD" and "USER" in principal.roles and grant_kind == "OWNER"


def _get_detection_result(request, runtime, principal, evaluation_id, view):
    try:
        connection = _open(request, runtime)
    except _Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                row = _evaluation_row(cur, evaluation_id)
                case = _authorize(request, runtime, principal, cur, "getDetectionResult", row[1] if row else None)
                if not view_permitted(principal, case, view):
                    _audit_denial(runtime, request, principal, case[0], "ROLE_OWNERSHIP_OR_CONTENT_PERMISSION_REQUIRED",
                                  "getDetectionResult")
                    return api_error(request, "FORBIDDEN")
                if row[5] != "COMPLETED":
                    return api_error(request, "EVALUATION_NOT_COMPLETED")
                cur.execute(f"SELECT detection_result_id::text, result_digest, result_canonical_json FROM {SCHEMA}.detection_result"
                            " WHERE evaluation_id = %s", (evaluation_id,))
                stored = cur.fetchone()
            if stored is None:
                return api_error(request, "INTEGRITY_FAILURE")
            result_id, digest, text = stored
            if text is None or _digest(text) != digest:
                with connection.transaction(), connection.cursor() as cur:
                    _audit(cur, "INTEGRITY_FAILURE", "FAILED", "DETECTION_RESULT", result_id, case[0], evaluation_id,
                           request.state.request_id, actor=principal.principal_reference_id, metadata={"stage": "RESULT_READ"})
                return api_error(request, "INTEGRITY_FAILURE")
            body = result_response(json.loads(text), digest, view, content_permission=bool(case[7]))
            with connection.transaction(), connection.cursor() as cur:      # every read is audited, or nothing is shown
                _audit(cur, "EVIDENCE_ACCESSED", "SUCCEEDED", "DETECTION_RESULT", result_id, case[0], evaluation_id,
                       request.state.request_id, actor=principal.principal_reference_id,
                       metadata={"stage": f"RESULT_{view}_VIEW"})
        except _Refused as refused:
            return refused.response
        except (psycopg.Error, AuditUnavailable, ValueError):
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        except (KeyError, TypeError):
            return api_error(request, "INTEGRITY_FAILURE")
    return _json(200, body)


def _source_statement(entry) -> str:
    """Serialized form of one Phase-3 evidence_basis citation (UX-003 deferred decision: identifier + verbatim quote)."""
    if isinstance(entry, str):
        return entry
    head = f"{entry['issuing_body']} ({entry['source_id']})"
    return f"{head}: “{entry['quote']}”" if entry.get("quote") else head


def result_response(document, digest, view, *, content_permission) -> dict:
    """DetectionResultResponse from the exact stored Phase-3 document. Only accepted fields; nothing is derived."""
    rules = {r["rule_id"]: r for r in document.get("rule_results", [])}

    def reference(rule):
        return {"rule_id": rule["rule_id"], "rule_version": rule["rule_version"],
                "source_references": [s["source_id"] if isinstance(s, dict) else s for s in rule.get("source_references", [])]}

    governing = [r for r in document.get("rule_results", []) if r.get("governing")]
    explanation = {"summary": document["explanation"]["summary"]}
    if content_permission and document["explanation"].get("evidence_basis") is not None:
        explanation["evidence_basis"] = [_source_statement(e) for e in document["explanation"]["evidence_basis"]]
    provenance = document["provenance"]
    body = {
        "evaluation_id": document["evaluation_id"], "result_contract_version": document["result_contract_version"],
        "result_digest": digest, "view": view, "input_support_status": document["input_support_status"],
        "language": document["language"], "script": document["script"], "classification": document["classification"],
        "decision_severity": document["decision_severity"], "matched_evidence_strength": document["matched_evidence_strength"],
        "risk_level": document["risk_level"], "detection_confidence": document["detection_confidence"],
        "degraded": bool(document.get("degraded", False)),
        "governing_rule": reference(governing[0]) if governing else None,
        "matched_rules": [reference(rules[rule_id]) for rule_id in document.get("matched_rules", [])],
        "explanation": explanation,
        "recommended_actions": [{"action_code": a["action_code"]} for a in document["recommended_actions"]],
        "limitations": list(document.get("limitations", [])), "unknowns": list(document.get("unknowns", [])),
        "ambiguities": list(document.get("ambiguities", [])),
        "provenance": {"engine_version": provenance["engine_version"], "result_contract_version": document["result_contract_version"],
                       "bundle_content_digest": provenance["bundle_content_digest"], "bundle_version": provenance["bundle_version"],
                       "evaluation_profile_id": provenance["evaluation_profile"]["profile_id"],
                       "evaluation_timestamp": document["evaluation_timestamp"]},
        "not_an_official_determination": True,
        "absence_of_finding_notice": ABSENCE_OF_FINDING_NOTICE if document["classification"] == "NO_SCAM_PATTERN" else None,
    }
    if view == "DETAILED":
        body["rule_results"] = [{"rule_id": r["rule_id"], "rule_version": r["rule_version"], "kind": r["kind"],
                                 "evaluation_state": r["evaluation_state"], "governing": bool(r.get("governing", False)),
                                 "effective_severity": r.get("effective_severity"),
                                 "rule_evidence_strength": r.get("rule_evidence_strength"),
                                 "rule_detection_confidence": r.get("rule_detection_confidence")}
                                for r in document.get("rule_results", [])]
    return body


def install(app: FastAPI):
    app.add_api_route("/api/v1/submissions/{submission_id}/evaluations", create_evaluations, methods=["POST"])
    app.add_api_route("/api/v1/cases/{case_id}/evaluations", list_case_evaluations, methods=["GET"])
    app.add_api_route("/api/v1/evaluations/{evaluation_id}", get_evaluation, methods=["GET"])
    app.add_api_route("/api/v1/evaluations/{evaluation_id}/result", get_detection_result, methods=["GET"])
