"""S6 case history: getEvidenceContent, createCorrection, createReplay and getReplay (API-001 §12-§15, UX-004/UX-005).

- getEvidenceContent returns the exact original bytes of a FINALIZED item to a caller whose case grant permits evidence
  content (the owner by policy; an assigned analyst only if granted). The store is re-read and length and SHA-256
  re-verified before any byte is sent; every read and every integrity failure is audited. No role grants content by
  itself; break-glass access needs the break-glass grant store, which is not built yet (S9).
- createCorrection records the owner's free-text correction (C4, never audited or logged) and a reason, and creates a
  NEW USER_CORRECTION evaluation of the same original bytes through the unchanged S5 pipeline. The accepted API has no
  field-level editing, so the correction cannot alter the governed extraction; it is lineage, not a mutation. The corrected
  evaluation, its artifact and its result are never touched.
- createReplay re-runs ONLY the pinned material of a COMPLETED evaluation (its governed input artifact, the exact bundle by
  digest, the pinned engine and profile) and compares the replayed result digest with the stored one. It never selects the
  active bundle, never creates an evaluation or result, and records missing or failed material as an explicit outcome.
  Replay records are content-free.
"""
import hashlib
import json
import re
import uuid
from datetime import timezone

import psycopg
from fastapi import FastAPI, Request
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from knowledge.ai.governance import canonical_json
from knowledge.runtime.engine import ENGINE_VERSION
from knowledge.runtime.result import evaluate_detection_from_governed

from . import evaluation as ev, idempotency
from .audit import AuditUnavailable
from .auth import api_error, current_principal
from .cases import _Unavailable, _audit_denial, _idempotent_error, _instant, _json, _uuid, _visible_case, is_too_large, read_json_object
from .content_store import ContentStoreUnavailable, IntegrityFailure
from .evidence import get_store
from .knowledge_seam import BundleRejected
from .principals import SCHEMA

OPERATIONS = {
    "getEvidenceContent": {"method": "GET", "path": "/api/v1/evidence/{evidence_id}/content", "roles": ("USER", "ANALYST"),
                           "resource_authorization": "CASE_EVIDENCE_CONTENT"},
    "createCorrection": {"method": "POST", "path": "/api/v1/evaluations/{evaluation_id}/corrections", "roles": ("USER",),
                         "resource_authorization": "CASE_OWNER"},
    "createReplay": {"method": "POST", "path": "/api/v1/evaluations/{evaluation_id}/replays", "roles": ("ANALYST", "ADMINISTRATOR"),
                     "resource_authorization": "CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN"},
    "getReplay": {"method": "GET", "path": "/api/v1/replays/{replay_id}", "roles": ("ANALYST", "ADMINISTRATOR"),
                  "resource_authorization": "CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN"},
}
MAX_CORRECTION_CHARS = 2000            # implementation profile bound for correction_description ("BOUNDED" in the API)
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
REMOVED_STATES = ("DELETION_PENDING", "DELETED")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bad(request, field, code, message):
    return api_error(request, "INVALID_REQUEST", field_errors=[{"field": field, "code": code, "message": message}])


def _evaluation_case(cur, evaluation_id):
    cur.execute(f"SELECT case_record_id::text, submission_id::text, status FROM {SCHEMA}.evaluation WHERE evaluation_id = %s",
                (evaluation_id,))
    return cur.fetchone()


async def _strict_body(request, allowed: set, required: set):
    body, problems = await read_json_object(request)
    if problems:
        return None, [] if is_too_large(problems) else problems
    errors = [{"field": k, "code": "UNKNOWN_FIELD", "message": "Field is not accepted."} for k in body if k not in allowed]
    errors += [{"field": k, "code": "REQUIRED", "message": "Field is required."} for k in sorted(required) if k not in body]
    if "reason_code" in body and (not isinstance(body["reason_code"], str) or not _REASON.match(body["reason_code"])):
        errors.append({"field": "reason_code", "code": "INVALID_VALUE", "message": "Use an upper-case reason code."})
    return (None, errors) if errors else (body, None)


# ---------------------------------------------------------------- getEvidenceContent
async def get_evidence_content(request: Request):
    runtime, principal, error = current_principal(request, "GETEVIDENCECONTENT")
    if error is not None:
        return error
    evidence_id = _uuid(request.path_params["evidence_id"])
    if evidence_id is None:
        return _bad(request, "evidence_id", "INVALID_UUID", "Not a UUID.")
    if request.query_params:
        return _bad(request, next(iter(request.query_params)), "UNKNOWN_PARAMETER", "Parameter is not accepted.")
    return await run_in_threadpool(_get_evidence_content, request, runtime, principal, evidence_id)


def _get_evidence_content(request, runtime, principal, evidence_id):
    from .evidence import _Refused as EvidenceRefused, _case_of_evidence, _open as open_evidence
    try:
        connection = open_evidence(request, runtime)
    except EvidenceRefused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                case_id = _case_of_evidence(cur, evidence_id)
                case = _visible_case(cur, case_id, principal.principal_reference_id) if case_id else None
                if case is None:
                    return api_error(request, "NOT_FOUND")                      # masked, whatever the role
                if not set(principal.roles) & {"USER", "ANALYST"} or not case[7]:
                    _audit_denial(runtime, request, principal, case_id, "ROLE_OWNERSHIP_OR_CONTENT_PERMISSION_REQUIRED",
                                  "getEvidenceContent")
                    return api_error(request, "FORBIDDEN")
                cur.execute(f"SELECT content_state, ecs_locator, content_sha256, byte_length, verified_media_type"
                            f" FROM {SCHEMA}.evidence_item WHERE evidence_item_id = %s", (evidence_id,))
                item = cur.fetchone()
            if item is None:
                return api_error(request, "STATE_CONFLICT")                    # no content stored yet
            state, locator, sha, length, media = item
            if state in REMOVED_STATES:
                return api_error(request, "REMOVED_UNDER_GOVERNANCE")
            if state != "FINALIZED" or not locator or not media:
                return api_error(request, "STATE_CONFLICT")
            store = get_store(runtime)
            if store is None:
                return api_error(request, "DEPENDENCY_UNAVAILABLE")
            try:
                data = store.get(locator)
                if len(data) != length or _digest(data) != sha:
                    raise IntegrityFailure("digest or length mismatch")
            except (IntegrityFailure, ContentStoreUnavailable):                 # a FINALIZED item must be readable and exact
                with connection.transaction(), connection.cursor() as cur:
                    ev._audit(cur, "INTEGRITY_FAILURE", "FAILED", "EVIDENCE_ITEM", evidence_id, case_id, None,
                              request.state.request_id, actor=principal.principal_reference_id,
                              metadata={"stage": "CONTENT_DOWNLOAD"}, evidence_id=evidence_id)
                return api_error(request, "INTEGRITY_FAILURE")
            with connection.transaction(), connection.cursor() as cur:          # audited, or nothing is sent
                ev._audit(cur, "EVIDENCE_ACCESSED", "SUCCEEDED", "EVIDENCE_ITEM", evidence_id, case_id, None,
                          request.state.request_id, actor=principal.principal_reference_id,
                          metadata={"stage": "CONTENT_DOWNLOAD"}, evidence_id=evidence_id)
        except (psycopg.Error, AuditUnavailable, ValueError):
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
    return Response(content=data, status_code=200, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="trustlens-evidence-{evidence_id}.txt"',
                             "Cache-Control": "no-store"})


# ---------------------------------------------------------------- createCorrection
async def create_correction(request: Request):
    runtime, principal, error = current_principal(request, "CREATECORRECTION")
    if error is not None:
        return error
    evaluation_id = _uuid(request.path_params["evaluation_id"])
    if evaluation_id is None:
        return _bad(request, "evaluation_id", "INVALID_UUID", "Not a UUID.")
    key = request.headers.get("idempotency-key")
    if not idempotency.valid_key(key):
        return _bad(request, "Idempotency-Key", "REQUIRED", "Send a high-entropy key (16-255 URL-safe characters).")
    body, problems = await _strict_body(request, {"correction_description", "reason_code"}, {"correction_description", "reason_code"})
    if problems is not None:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    text = body["correction_description"]
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_CORRECTION_CHARS:
        return _bad(request, "correction_description", "INVALID_LENGTH", f"Describe the correction in 1..{MAX_CORRECTION_CHARS} characters.")
    return await run_in_threadpool(_create_correction, request, runtime, principal, evaluation_id, key, body)


def _create_correction(request, runtime, principal, evaluation_id, key, body):
    scope = f"/api/v1/evaluations/{evaluation_id}/corrections"
    try:
        connection = ev._open(request, runtime)
    except ev._Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                if not _corrections_active(cur):
                    return api_error(request, "DEPENDENCY_UNAVAILABLE")
                row = _evaluation_case(cur, evaluation_id)
                case = _visible_case(cur, row[0], principal.principal_reference_id) if row else None
                if case is None:
                    return api_error(request, "NOT_FOUND")
                if "USER" not in principal.roles or case[6] != "OWNER":
                    _audit_denial(runtime, request, principal, case[0], "ROLE_OWNERSHIP_OR_CONTENT_PERMISSION_REQUIRED",
                                  "createCorrection")
                    return api_error(request, "FORBIDDEN")
            outcome = idempotency.claim(connection, principal.principal_reference_id, "createCorrection", scope, key,
                                        idempotency.semantic_digest("createCorrection", scope, body), supersession=True)
        except (idempotency.KeyReused, idempotency.InProgress) as e:
            return _idempotent_error(request, e)
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if isinstance(outcome, idempotency.Replay):
            return _correction_replay(request, runtime, connection, outcome)
        if row[2] != "COMPLETED":
            return ev._conflict(request, connection, outcome, "EVALUATION_NOT_COMPLETED", 409)
        correction_id = str(uuid.uuid4())

        def record(cur, new_evaluation_id):
            cur.execute(f"INSERT INTO {SCHEMA}.user_correction (user_correction_id, case_record_id, corrected_evaluation_id,"
                        " resulting_evaluation_id, correcting_principal_id, correction_description, created_at)"
                        " VALUES (%s, %s, %s, %s, %s, %s, now())",
                        (correction_id, case[0], evaluation_id, new_evaluation_id, principal.principal_reference_id,
                         body["correction_description"]))
            ev._audit(cur, "USER_CORRECTION", "SUCCEEDED", "EVALUATION", evaluation_id, case[0], evaluation_id,
                      request.state.request_id, actor=principal.principal_reference_id,
                      metadata={"reason": body["reason_code"]})                      # the description is C4: never audited
            return "user_correction", correction_id

        started = ev._start_evaluation(request, runtime, principal, connection, outcome, case, row[1], "USER_CORRECTION",
                                       evaluation_id, {}, in_transaction=record)
        if not isinstance(started, str):
            return started
        with connection.cursor() as cur:
            view = ev._view(ev._evaluation_row(cur, started))
    return _correction_accepted(runtime, correction_id, evaluation_id, view)


def _corrections_active(cur) -> bool:
    cur.execute("SELECT to_regclass('trustlens.user_correction') IS NOT NULL AND to_regclass('trustlens.replay_execution') IS NOT NULL")
    return bool(cur.fetchone()[0])


def _correction_accepted(runtime, correction_id, corrected_id, view):
    response = _json(202, {"correction_id": correction_id, "corrected_evaluation_id": corrected_id, "new_evaluation": view})
    if view["state"] == "QUEUED":
        response.background = BackgroundTask(ev.dispatch, runtime, [view["evaluation_id"]])
    return response


def _correction_replay(request, runtime, connection, replay):
    if replay.error_code:
        return api_error(request, replay.error_code)
    with connection.cursor() as cur:
        cur.execute(f"SELECT corrected_evaluation_id::text, resulting_evaluation_id::text FROM {SCHEMA}.user_correction"
                    " WHERE user_correction_id = %s", (replay.resource_id,))
        row = cur.fetchone()
        view = ev._view(ev._evaluation_row(cur, row[1])) if row else None
    if view is None:
        return api_error(request, "NOT_FOUND")
    return _correction_accepted(runtime, replay.resource_id, row[0], view)


# ---------------------------------------------------------------- createReplay / getReplay
def _replay_authorize(request, runtime, principal, cur, case_id, operation_id):
    """CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN: an analyst assigned to the case, or a platform administrator (no case
    access needed; the replay record is content-free). Everyone else: masked 404 without visibility, 403 with it."""
    if "ADMINISTRATOR" in principal.roles:
        return True
    case = _visible_case(cur, case_id, principal.principal_reference_id) if case_id else None
    if case is None:
        raise ev._Refused(api_error(request, "NOT_FOUND"))
    if "ANALYST" not in principal.roles or case[6] != "ASSIGNED_ANALYST":
        _audit_denial(runtime, request, principal, case_id, "ROLE_OWNERSHIP_OR_CONTENT_PERMISSION_REQUIRED", operation_id)
        raise ev._Refused(api_error(request, "FORBIDDEN"))
    return True


_REPLAY_COLUMNS = ("replay_execution_id::text, evaluation_id::text, replay_capability_state, missing_material_kinds, outcome,"
                   " replayed_result_digest, requested_at, completed_at")


def _replay_view(row) -> dict:
    replay_id, evaluation_id, capability, missing, outcome, digest, requested, completed = row
    view = {"replay_id": replay_id, "evaluation_id": evaluation_id, "state": "COMPLETED" if completed else "PENDING",
            "capability": capability, "outcome": outcome, "replayed_result_digest": digest,
            "requested_at": _instant(requested), "completed_at": _instant(completed)}
    if missing is not None:
        view["missing_material_kinds"] = list(missing)
    return view


def _replay_row(cur, replay_id):
    cur.execute(f"SELECT {_REPLAY_COLUMNS} FROM {SCHEMA}.replay_execution WHERE replay_execution_id = %s", (replay_id,))
    return cur.fetchone()


async def create_replay(request: Request):
    runtime, principal, error = current_principal(request, "CREATEREPLAY")
    if error is not None:
        return error
    evaluation_id = _uuid(request.path_params["evaluation_id"])
    if evaluation_id is None:
        return _bad(request, "evaluation_id", "INVALID_UUID", "Not a UUID.")
    key = request.headers.get("idempotency-key")
    if not idempotency.valid_key(key):
        return _bad(request, "Idempotency-Key", "REQUIRED", "Send a high-entropy key (16-255 URL-safe characters).")
    body, problems = await _strict_body(request, {"reason_code"}, {"reason_code"})
    if problems is not None:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_create_replay, request, runtime, principal, evaluation_id, key, body)


def _create_replay(request, runtime, principal, evaluation_id, key, body):
    scope = f"/api/v1/evaluations/{evaluation_id}/replays"
    try:
        connection = ev._open(request, runtime)
    except ev._Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                if not _corrections_active(cur):
                    return api_error(request, "DEPENDENCY_UNAVAILABLE")
                row = _evaluation_case(cur, evaluation_id)
                if row is None:
                    return api_error(request, "NOT_FOUND")
                _replay_authorize(request, runtime, principal, cur, row[0], "createReplay")
            outcome = idempotency.claim(connection, principal.principal_reference_id, "createReplay", scope, key,
                                        idempotency.semantic_digest("createReplay", scope, body), supersession=True)
        except ev._Refused as refused:
            return refused.response
        except (idempotency.KeyReused, idempotency.InProgress) as e:
            return _idempotent_error(request, e)
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if isinstance(outcome, idempotency.Replay):
            if outcome.error_code:
                return api_error(request, outcome.error_code)
            with connection.cursor() as cur:
                view = _replay_view(_replay_row(cur, outcome.resource_id))
            return _replay_accepted(runtime, view)
        if row[2] != "COMPLETED":
            return ev._conflict(request, connection, outcome, "EVALUATION_NOT_COMPLETED", 409)
        replay_id = str(uuid.uuid4())
        try:
            with connection.transaction(), connection.cursor() as cur:
                if _known_removed(cur, evaluation_id):
                    idempotency.fail_terminal(cur, outcome, 409, "REPLAY_UNAVAILABLE")
                    removed = True
                else:
                    removed = False
                    cur.execute(f"INSERT INTO {SCHEMA}.replay_execution (replay_execution_id, evaluation_id, requested_by_principal_id,"
                                " reason_ref, requested_at) VALUES (%s, %s, %s, %s, now())",
                                (replay_id, evaluation_id, principal.principal_reference_id, body["reason_code"]))
                    ev._audit(cur, "REPLAY_EXECUTED", "SUCCEEDED", "REPLAY", replay_id, row[0], evaluation_id,
                              request.state.request_id, actor=principal.principal_reference_id, metadata={"stage": "REQUESTED"})
                    idempotency.complete(cur, outcome, 202, "replay_execution", replay_id)
        except idempotency.StaleClaim:
            return api_error(request, "IDEMPOTENCY_IN_PROGRESS")
        except (psycopg.Error, AuditUnavailable, ValueError):
            idempotency.release(connection, outcome, 503, "DEPENDENCY_UNAVAILABLE")
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if removed:
            return api_error(request, "REPLAY_UNAVAILABLE")
        with connection.cursor() as cur:
            view = _replay_view(_replay_row(cur, replay_id))
    return _replay_accepted(runtime, view)


def _known_removed(cur, evaluation_id) -> bool:
    """Pinned material already known to be removed under governance (409 REPLAY_UNAVAILABLE at request time)."""
    cur.execute(f"SELECT EXISTS (SELECT 1 FROM {SCHEMA}.evaluation e JOIN {SCHEMA}.input_envelope_record r"
                " ON r.input_envelope_record_id = e.input_envelope_record_id"
                f" LEFT JOIN {SCHEMA}.input_envelope_source s ON s.input_envelope_record_id = r.input_envelope_record_id"
                f" LEFT JOIN {SCHEMA}.evidence_item i ON i.evidence_item_id = s.evidence_item_id"
                " WHERE e.evaluation_id = %s AND (r.content_state = ANY(%s) OR i.content_state = ANY(%s)))",
                (evaluation_id, list(REMOVED_STATES), list(REMOVED_STATES)))
    return bool(cur.fetchone()[0])


def _replay_accepted(runtime, view):
    response = _json(202, view)
    if view["state"] == "PENDING":
        response.background = BackgroundTask(run_replay, runtime, view["replay_id"])
    return response


async def get_replay(request: Request):
    runtime, principal, error = current_principal(request, "GETREPLAY")
    if error is not None:
        return error
    replay_id = _uuid(request.path_params["replay_id"])
    if replay_id is None:
        return _bad(request, "replay_id", "INVALID_UUID", "Not a UUID.")
    return await run_in_threadpool(_get_replay, request, runtime, principal, replay_id)


def _get_replay(request, runtime, principal, replay_id):
    try:
        connection = ev._open(request, runtime)
    except ev._Refused as refused:
        return refused.response
    with connection:
        try:
            with connection.cursor() as cur:
                if not _corrections_active(cur):
                    return api_error(request, "DEPENDENCY_UNAVAILABLE")
                row = _replay_row(cur, replay_id)
                if row is None:
                    return api_error(request, "NOT_FOUND")
                case = _evaluation_case(cur, row[1])
                _replay_authorize(request, runtime, principal, cur, case[0], "getReplay")
                return _json(200, _replay_view(row))
        except ev._Refused as refused:
            return refused.response
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")


# ---------------------------------------------------------------- exact replay
_OUTCOMES = {"REPLAY_UNAVAILABLE_INTEGRITY_FAILED": "FAILED_INTEGRITY", "REPLAY_UNAVAILABLE_BUNDLE_MISSING": "FAILED_BUNDLE_UNAVAILABLE",
             "REPLAY_UNAVAILABLE_ENGINE_UNAVAILABLE": "FAILED_ENGINE_UNAVAILABLE",
             "REPLAY_UNAVAILABLE_REQUIRED_ARTIFACT_MISSING": "FAILED_MISSING_MATERIAL"}


class _Material:
    def __init__(self):
        self.missing, self.integrity, self.bundle, self.engine = [], [], False, False

    def lost(self, kind):
        self.missing.append(kind)

    def broken(self, kind):
        self.integrity.append(kind)

    def capability(self):
        if self.integrity:
            return "REPLAY_UNAVAILABLE_INTEGRITY_FAILED"
        if self.bundle:
            return "REPLAY_UNAVAILABLE_BUNDLE_MISSING"
        if self.engine:
            return "REPLAY_UNAVAILABLE_ENGINE_UNAVAILABLE"
        if self.missing:
            return "REPLAY_UNAVAILABLE_REQUIRED_ARTIFACT_MISSING"
        return "REPLAY_CAPABLE"

    def kinds(self):
        return sorted(set(self.missing + self.integrity))


def _check_stored(store, locator, sha, length, kind, material):
    if store is None or not locator:
        return material.lost(kind)
    try:
        data = store.get(locator)
    except ContentStoreUnavailable:
        return material.lost(kind)
    except IntegrityFailure:
        return material.broken(kind)
    if _digest(data) != sha or (length is not None and len(data) != length):
        material.broken(kind)


def run_replay(runtime, replay_id):
    """Check every pinned material kind (DATA-001-WP2 replay_material_set), re-run the pinned kernel on the exact governed
    artifact, compare digests and record the write-once outcome. Never touches the evaluation or its result."""
    try:
        _run_replay(runtime, replay_id)
    except Exception:                 # recovery re-runs a PENDING replay; a background failure never escapes
        pass


def _run_replay(runtime, replay_id):
    """DATA-001-WP2 §9.3, in order: every manifest row present and FINALIZED; exact bytes re-hashed; governed artifact,
    stored result and the whole-material commitment re-verified; the exact bundle by digest; the pinned engine and
    profile. Only then the pinned kernel runs. An integrity failure or MISMATCH is audited as INTEGRITY_FAILURE in the
    same transaction as the write-once outcome; if that audit cannot be written nothing is finalized (still PENDING)."""
    connection = ev._connect(runtime)
    with connection:
        with connection.cursor() as cur:
            replay = _replay_row(cur, replay_id)
            if replay is None or replay[7] is not None:
                return
            evaluation_id = replay[1]
            cur.execute(f"SELECT e.case_record_id::text, e.bundle_content_digest, e.engine_version, e.evaluation_timestamp,"
                        " e.input_id, e.input_support_status, e.language, e.script, e.input_envelope_record_id::text, e.ai_used,"
                        " e.bundle_version, e.manifest_schema_version, e.commit_sha, e.result_contract_version,"
                        " e.evaluation_profile_id, e.extraction_confidence_gate, e.risk_matrix_id, e.confidence_policy_id,"
                        " e.action_policy_version, e.component_versions, e.replay_material_digest"
                        f" FROM {SCHEMA}.evaluation e WHERE e.evaluation_id = %s", (evaluation_id,))
            e = cur.fetchone()
            cur.execute(f"SELECT artifact_canonical_json, governed_artifact_digest FROM {SCHEMA}.governed_input_artifact"
                        " WHERE evaluation_id = %s", (evaluation_id,))
            artifact_row = cur.fetchone()
            cur.execute(f"SELECT result_canonical_json, result_digest, engine_version, result_contract_version, bundle_content_digest"
                        f" FROM {SCHEMA}.detection_result WHERE evaluation_id = %s", (evaluation_id,))
            result_row = cur.fetchone()
            cur.execute(f"SELECT ecs_locator, envelope_sha256, content_state FROM {SCHEMA}.input_envelope_record"
                        " WHERE input_envelope_record_id = %s", (e[8],))
            envelope_row = cur.fetchone()
            cur.execute(f"SELECT s.evidence_item_id, s.evidence_derivative_id, i.ecs_locator, i.content_sha256, i.byte_length,"
                        f" i.content_state FROM {SCHEMA}.input_envelope_source s"
                        f" LEFT JOIN {SCHEMA}.evidence_item i ON i.evidence_item_id = s.evidence_item_id"
                        " WHERE s.input_envelope_record_id = %s", (e[8],))
            sources = cur.fetchall()
            committed = ev.material_record(cur, evaluation_id, result_row[1] if result_row else None)
        case_id = e[0]
        material, store = _Material(), get_store(runtime)
        pins = {"bundle_content_digest": e[1], "bundle_version": e[10], "manifest_schema_version": e[11], "commit_sha": e[12],
                "engine_version": e[2], "result_contract_version": e[13], "evaluation_profile_id": e[14],
                "extraction_confidence_gate": e[15], "risk_matrix_id": e[16], "confidence_policy_id": e[17],
                "action_policy_version": e[18], "component_versions": e[19]}
        # RM-01, RM-03..RM-07: every pin present
        if any(v is None for k, v in pins.items() if k != "commit_sha") or e[3] is None or e[20] is None:
            material.lost("EVALUATION_PINS")
        if e[9]:
            material.lost("AI_REPLAY_SNAPSHOT")                  # RM-08: no AI snapshot store exists; AI is never re-called
        # §9.3 C: every manifest row present and FINALIZED (RM-11, RM-13, RM-14)
        if not sources:
            material.lost("EVIDENCE_MANIFEST")
        for item_id, derivative_id, locator, sha, length, state in sources:
            if derivative_id is not None:
                material.lost("EVIDENCE_DERIVATIVE")             # no derivative lineage is produced in MVP text evaluation
            elif state != "FINALIZED":
                material.lost("EVIDENCE_MANIFEST")
        if envelope_row is None or envelope_row[2] != "FINALIZED":
            material.lost("INPUT_ENVELOPE")
        # §9.3 D/E: exact bytes re-hashed against the recorded digests (RM-12, RM-14)
        if not material.missing:
            for item_id, derivative_id, locator, sha, length, state in sources:
                _check_stored(store, locator, sha, length, "EVIDENCE_BYTES", material)
            _check_stored(store, envelope_row[0], envelope_row[1], None, "INPUT_ENVELOPE", material)
        # §9.3 F: governed artifact, stored result and the whole-material commitment (RM-02, RM-10, RM-01)
        artifact = None
        if artifact_row is None or artifact_row[0] is None:
            material.lost("GOVERNED_INPUT_ARTIFACT")
        else:
            try:
                artifact = json.loads(artifact_row[0])
                if _digest(artifact_row[0].encode()) != artifact_row[1] or canonical_json(artifact) != artifact_row[0]:
                    raise ValueError
            except ValueError:
                artifact = None
                material.broken("GOVERNED_INPUT_ARTIFACT")
        if result_row is None or result_row[0] is None:
            material.lost("DETECTION_RESULT")
        elif _digest(result_row[0].encode()) != result_row[1] or (result_row[2], result_row[3], result_row[4]) != (e[2], e[13], e[1]):
            material.broken("DETECTION_RESULT")                  # RM-03/RM-04/RM-05 recorded twice; both must agree
        if e[20] is not None and (committed is None or ev.material_digest(committed) != e[20]):
            material.broken("EVALUATION_PINS")                   # the whole-material commitment does not verify
        # §9.3 G/H: the exact bundle by digest (never the active one), then the pinned engine and profile
        rk = None
        if e[1] and not material.integrity:
            try:
                rk = runtime.knowledge_verifier.verify(e[1]) if runtime.knowledge_verifier else None
            except BundleRejected as rejected:
                if rejected.reason == "BUNDLE_TAMPERED":
                    material.broken("KNOWLEDGE_BUNDLE")
                else:
                    material.bundle = True
                    material.lost("KNOWLEDGE_BUNDLE")
            if rk is None and "KNOWLEDGE_BUNDLE" not in material.kinds():
                material.bundle = True
                material.lost("KNOWLEDGE_BUNDLE")
        if e[2] != ENGINE_VERSION or (rk is not None and ev._pins(rk) != pins):
            material.engine = True
            material.lost("ENGINE_VERSION")
        capability = material.capability()
        replayed = None
        if capability == "REPLAY_CAPABLE":
            context = artifact["evaluation_context"]
            if (context["input_id"], context["input_support_status"], context["language"], context["script"]) != \
                    (e[4], e[5], list(e[6]), list(e[7])):
                material.broken("GOVERNED_INPUT_ARTIFACT")
                capability = material.capability()
            else:
                result = evaluate_detection_from_governed(
                    rk, artifact["indicator_observations"], artifact["observations"], evaluation_id=evaluation_id,
                    evaluation_timestamp=ev._instant_text(e[3].astimezone(timezone.utc)), input_id=e[4], language=list(e[6]),
                    script=list(e[7]), input_support_status=e[5], whole_evaluation_errors=context["whole_evaluation_errors"])
                replayed = _digest(canonical_json(result.as_dict()).encode())
        outcome = ("MATCH" if replayed == result_row[1] else "MISMATCH") if capability == "REPLAY_CAPABLE" else _OUTCOMES[capability]
        missing = None if capability == "REPLAY_CAPABLE" else material.kinds()
        integrity_event = outcome in ("FAILED_INTEGRITY", "MISMATCH")
        correlation = str(uuid.uuid4())
        with connection.transaction(), connection.cursor() as cur:
            cur.execute(f"UPDATE {SCHEMA}.replay_execution SET replay_capability_state = %s, missing_material_kinds = %s, outcome = %s,"
                        " replayed_result_digest = %s, completed_at = now() WHERE replay_execution_id = %s AND completed_at IS NULL",
                        (capability, missing, outcome, replayed, replay_id))
            if cur.rowcount == 1:                                # the one run that records the outcome also audits it
                if integrity_event:                              # §9.3: U2 and MISMATCH carry INTEGRITY_FAILURE
                    ev._audit(cur, "INTEGRITY_FAILURE", "FAILED", "REPLAY", replay_id, case_id, evaluation_id, correlation,
                              metadata={"stage": "REPLAY_VERIFICATION"})
                ev._audit(cur, "REPLAY_EXECUTED", "SUCCEEDED" if outcome == "MATCH" else "FAILED", "REPLAY", replay_id, case_id,
                          evaluation_id, correlation, metadata={"outcome": outcome})


def recover_replays(runtime, limit=50) -> list:
    """Run replays left PENDING by a crash. Completion is write-once (completed_at IS NULL), so this is always safe."""
    connection = ev._connect(runtime)
    with connection:
        with connection.cursor() as cur:
            if not _corrections_active(cur):
                return []
            cur.execute(f"SELECT replay_execution_id::text FROM {SCHEMA}.replay_execution WHERE completed_at IS NULL"
                        " ORDER BY requested_at LIMIT %s", (limit,))
            pending = [r[0] for r in cur.fetchall()]
    for replay_id in pending:
        run_replay(runtime, replay_id)
    return pending


def install(app: FastAPI):
    app.add_api_route("/api/v1/evidence/{evidence_id}/content", get_evidence_content, methods=["GET"])
    app.add_api_route("/api/v1/evaluations/{evaluation_id}/corrections", create_correction, methods=["POST"])
    app.add_api_route("/api/v1/evaluations/{evaluation_id}/replays", create_replay, methods=["POST"])
    app.add_api_route("/api/v1/replays/{replay_id}", get_replay, methods=["GET"])
