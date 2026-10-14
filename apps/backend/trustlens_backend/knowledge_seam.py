"""S3 governed knowledge seam: exact-bundle verification, evaluation readiness and the accepted knowledge READ operations.

- Bundles are verified by the existing Phase-3 loader (knowledge.runtime.loader.load_bundle): manifest schema, member
  path safety and SHA-256, content-digest recomputation, exact-token version compatibility, member schemas and
  cross-references. No second loader or rule engine exists here.
- Identity is the exact content digest. A bundle lives at <TRUSTLENS_KNOWLEDGE_ROOT>/<content_digest>/; the digest
  selects the directory and must equal the verified manifest digest. There is no "latest" lookup and no fallback.
- Evaluation readiness (ADR-0013 Decision 13, ARCH-005 §8) is READY only when the deployment state is ACTIVE, its
  current activation record is a successful ACTIVE activation of the same digest, the bundle reference is ELIGIBLE and
  matches the verified bundle's versions, and the bundle verifies locally. Every other case is NOT_READY with a
  categorical reason; it never degrades to a guess.
- Verified RuntimeKnowledge is immutable and cached per exact digest, so an evaluation always uses the bundle that was
  verified; later disk changes cannot alter it.
- activateKnowledgeBundle (DEC-011, CLI-first) is the only write. It activates an exact digest that the deployment's
  committed release record approves, after full pre-activation validation (ADR-0013 Decision 8) and, for the
  single-machine synthetic development profile only, authenticity NOT_REQUIRED_BY_POLICY (DEC-012). An unsigned bundle
  is never described as publisher-authenticated. Rollback and withdrawal stay outside S3 (PLAN-001 §6, S9).
"""
import json
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg
from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool

from knowledge.runtime import errors as kerr
from knowledge.runtime.loader import load_bundle

from . import idempotency
from .audit import AuditEvent, append as audit_append
from .auth import api_error, current_principal
from .capabilities import evidence_schema_active
from .cases import (SYNTHETIC_ONLY_PROFILE, _Unavailable, _connect, _encode_cursor, _idempotent_error, _instant, _json,
                    _page_params, read_json_object)
from .principals import SCHEMA

OPERATIONS = {
    "getActiveKnowledge": {"method": "GET", "path": "/api/v1/knowledge/active",
                           "roles": ("ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR"),
                           "resource_authorization": "KNOWLEDGE_READ"},
    "getKnowledgeBundle": {"method": "GET", "path": "/api/v1/knowledge/bundles/{content_digest}",
                           "roles": ("ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR"),
                           "resource_authorization": "KNOWLEDGE_READ"},
    "listKnowledgeActivations": {"method": "GET", "path": "/api/v1/knowledge/activations",
                                 "roles": ("KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR"),
                                 "resource_authorization": "KNOWLEDGE_READ"},
    "activateKnowledgeBundle": {"method": "POST", "path": "/api/v1/knowledge/deployment/activate", "roles": ("ADMINISTRATOR",),
                                "resource_authorization": "KNOWLEDGE_OPERATION"},
}
RELEASE_DIR = Path(__file__).resolve().parents[1] / "knowledge_releases"     # governed in Git; one file per deployment
LOCAL_PROFILE = "SINGLE_MACHINE_SYNTHETIC_DEVELOPMENT"
_REFERENCE = re.compile(r"^[A-Z0-9][A-Z0-9:_-]{0,79}$")
ACTIVATION_SCOPE = "/api/v1/knowledge/deployment/activate"
DEFAULT_DEPLOYMENT_REF = "local-development"
DEFAULT_KNOWLEDGE_ROOT = "~/.local/share/trustlens/knowledge"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
ACTIVATION_FILTERS = {"action_kind": ("ACTIVATION", "ROLLBACK", "WITHDRAWAL_REMEDIATION", "REJECTED_ACTIVATION"),
                      "outcome": ("SUCCEEDED", "FAILED"), "recorded_from": "timestamp", "recorded_to": "timestamp"}

# Loader failure -> categorical rejection reason (no paths, member names or content in the category).
REJECTION = [(kerr.BundleNotFoundError, "BUNDLE_MISSING"), (kerr.UnsafePathError, "BUNDLE_TAMPERED"),
             (kerr.IntegrityError, "BUNDLE_TAMPERED"), (kerr.ManifestError, "BUNDLE_INVALID"),
             (kerr.MemberSchemaError, "BUNDLE_INVALID"), (kerr.DuplicateIdError, "BUNDLE_INVALID"),
             (kerr.ReferenceIntegrityError, "BUNDLE_INVALID"), (kerr.CompatibilityError, "BUNDLE_INCOMPATIBLE")]


class BundleRejected(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Readiness:
    ready: bool
    reason: str                        # READY or a categorical NOT_READY reason
    deployment_state: str | None = None
    content_digest: str | None = None
    knowledge: object | None = None    # the verified, immutable RuntimeKnowledge when ready


class KnowledgeVerifier:
    """Verifies bundles by exact digest and caches the immutable result per digest (positive results only)."""

    def __init__(self, root):
        self.root = Path(root).expanduser()
        self._verified: dict[str, object] = {}
        self._lock = threading.Lock()

    def verify(self, content_digest: str):
        if not isinstance(content_digest, str) or not _DIGEST.match(content_digest):
            raise BundleRejected("DIGEST_INVALID")
        with self._lock:
            cached = self._verified.get(content_digest)
        if cached is not None:
            return cached
        try:
            knowledge = load_bundle(self.root / content_digest)
        except kerr.BundleLoadError as error:
            raise BundleRejected(next((r for cls, r in REJECTION if isinstance(error, cls)), "BUNDLE_INVALID")) from None
        except OSError:
            raise BundleRejected("BUNDLE_MISSING") from None
        if knowledge.content_digest != content_digest:      # the directory name is the identity; never trust a rename
            raise BundleRejected("BUNDLE_TAMPERED")
        with self._lock:
            self._verified[content_digest] = knowledge
        return knowledge


def verifier_from_environment(env) -> KnowledgeVerifier:
    return KnowledgeVerifier(env.get("TRUSTLENS_KNOWLEDGE_ROOT", DEFAULT_KNOWLEDGE_ROOT))


def schema_active(cur) -> bool:
    cur.execute("SELECT to_regclass('trustlens.knowledge_deployment_state') IS NOT NULL")
    return bool(cur.fetchone()[0])


def evaluation_readiness(cur, verifier: KnowledgeVerifier | None, deployment_ref: str) -> Readiness:
    """Fail-closed readiness of governed evaluation for one deployment (never NO_SCAM_PATTERN, never a guess)."""
    if not schema_active(cur):
        return Readiness(False, "KNOWLEDGE_SCHEMA_MISSING")
    cur.execute(f"SELECT operational_state, active_bundle_content_digest, current_activation_record_id::text"
                f" FROM {SCHEMA}.knowledge_deployment_state WHERE deployment_ref = %s", (deployment_ref,))
    row = cur.fetchone()
    if row is None:
        return Readiness(False, "NO_DEPLOYMENT_STATE")
    state, digest, activation_id = row
    if state != "ACTIVE":
        return Readiness(False, state, state, digest)         # NO_ACTIVE_BUNDLE or ACTIVE_BUNDLE_WITHDRAWN
    cur.execute(f"SELECT bundle_version, manifest_schema_version, governance_eligibility FROM {SCHEMA}.knowledge_bundle_reference"
                " WHERE content_digest = %s", (digest,))
    reference = cur.fetchone()
    if reference is None:
        return Readiness(False, "BUNDLE_REFERENCE_MISSING", state, digest)
    if reference[2] != "ELIGIBLE":
        return Readiness(False, "BUNDLE_WITHDRAWN" if reference[2] == "WITHDRAWN" else "ELIGIBILITY_UNKNOWN", state, digest)
    cur.execute(f"SELECT bundle_content_digest, lifecycle_state, outcome, validation_outcome, authenticity_outcome"
                f" FROM {SCHEMA}.knowledge_activation_record WHERE knowledge_activation_record_id = %s", (activation_id,))
    activation = cur.fetchone()
    if activation is None or activation[0] != digest or activation[1] != "ACTIVE" or activation[2] != "SUCCEEDED":
        return Readiness(False, "ACTIVATION_RECORD_INCONSISTENT", state, digest)
    if verifier is None:
        return Readiness(False, "KNOWLEDGE_STORE_UNCONFIGURED", state, digest)
    try:
        knowledge = verifier.verify(digest)
    except BundleRejected as rejected:
        return Readiness(False, rejected.reason, state, digest)
    if (knowledge.bundle_version, knowledge.manifest_schema_version) != (reference[0], reference[1]):
        return Readiness(False, "BUNDLE_REFERENCE_MISMATCH", state, digest)
    return Readiness(True, "READY", state, digest, knowledge)


# ---------------------------------------------------------------- accepted READ operations
def _bundle_view(row) -> dict:
    digest, version, manifest_version, commit_sha, eligibility = row
    return {"content_digest": digest, "bundle_version": version, "manifest_schema_version": manifest_version,
            "commit_sha": commit_sha, "governance_eligibility": eligibility}


def _authorized(request: Request, operation_id: str):
    runtime, principal, error = current_principal(request, operation_id.upper())
    if error is not None:
        return runtime, None, error
    if not set(principal.roles) & set(OPERATIONS[operation_id]["roles"]):
        return runtime, None, api_error(request, "FORBIDDEN")
    return runtime, principal, None


def _with_schema(request, runtime, work):
    try:
        connection = _connect(runtime)
    except _Unavailable:
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    with connection:
        try:
            with connection.cursor() as cur:
                if not schema_active(cur):
                    return api_error(request, "DEPENDENCY_UNAVAILABLE")     # 0005 not applied: fail closed
                return work(cur)
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")


async def get_active_knowledge(request: Request):
    runtime, principal, error = _authorized(request, "getActiveKnowledge")
    if error is not None:
        return error
    deployment_ref = getattr(runtime, "deployment_ref", None) or DEFAULT_DEPLOYMENT_REF

    def work(cur):
        cur.execute(f"SELECT d.operational_state, d.state_changed_at, b.content_digest, b.bundle_version, b.manifest_schema_version,"
                    f" b.commit_sha, b.governance_eligibility FROM {SCHEMA}.knowledge_deployment_state d"
                    f" LEFT JOIN {SCHEMA}.knowledge_bundle_reference b ON b.content_digest = d.active_bundle_content_digest"
                    " WHERE d.deployment_ref = %s", (deployment_ref,))
        row = cur.fetchone()
        if row is None:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")             # no deployment state: not a "no bundle" claim
        return _json(200, {"deployment_state": row[0], "state_changed_at": _instant(row[1]),
                           "active_bundle": _bundle_view(row[2:]) if row[2] else None})
    return await run_in_threadpool(_with_schema, request, runtime, work)


async def get_knowledge_bundle(request: Request):
    runtime, principal, error = _authorized(request, "getKnowledgeBundle")
    if error is not None:
        return error
    digest = request.path_params["content_digest"]
    if not _DIGEST.match(digest):
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "content_digest", "code": "INVALID_DIGEST",
                                                                    "message": "Use the exact lowercase SHA-256 digest."}])

    def work(cur):
        cur.execute(f"SELECT content_digest, bundle_version, manifest_schema_version, commit_sha, governance_eligibility"
                    f" FROM {SCHEMA}.knowledge_bundle_reference WHERE content_digest = %s", (digest,))
        row = cur.fetchone()
        return api_error(request, "NOT_FOUND") if row is None else _json(200, _bundle_view(row))
    return await run_in_threadpool(_with_schema, request, runtime, work)


async def list_knowledge_activations(request: Request):
    runtime, principal, error = _authorized(request, "listKnowledgeActivations")
    if error is not None:
        return error
    params, problems = _page_params(request, ACTIVATION_FILTERS)
    if problems:
        return api_error(request, "INVALID_REQUEST", field_errors=problems)

    def work(cur):
        where, args = [], []
        for key, column in (("action_kind", "action_kind"), ("outcome", "outcome")):
            if key in params:
                where.append(f"{column} = %s")
                args.append(params[key])
        if "recorded_from" in params:
            where.append("recorded_at >= %s")
            args.append(params["recorded_from"])
        if "recorded_to" in params:
            where.append("recorded_at <= %s")
            args.append(params["recorded_to"])
        if params["cursor"]:
            where.append("(recorded_at, knowledge_activation_record_id) < (%s, %s::uuid)")
            args += list(params["cursor"])
        cur.execute(f"SELECT knowledge_activation_record_id::text, action_kind, bundle_content_digest, previous_bundle_content_digest,"
                    f" lifecycle_state, outcome, recorded_at FROM {SCHEMA}.knowledge_activation_record"
                    + (" WHERE " + " AND ".join(where) if where else "")
                    + " ORDER BY recorded_at DESC, knowledge_activation_record_id DESC LIMIT %s", args + [params["limit"] + 1])
        rows = cur.fetchall()
        page = {"limit": params["limit"]}
        if len(rows) > params["limit"]:
            rows = rows[:params["limit"]]
            page["next_cursor"] = _encode_cursor(rows[-1][6], rows[-1][0])
        items = [{"activation_id": r[0], "action_kind": r[1], "content_digest": r[2], "previous_content_digest": r[3],
                  "lifecycle_state": r[4], "outcome": r[5], "recorded_at": _instant(r[6])} for r in rows]
        return _json(200, {"items": items, "page": page})
    return await run_in_threadpool(_with_schema, request, runtime, work)


# ---------------------------------------------------------------- activateKnowledgeBundle (DEC-011 / DEC-012)
class NotEligible(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def release_entry(runtime, content_digest: str) -> dict:
    """The committed release-record entry approving this exact digest for this deployment, or NotEligible."""
    deployment = getattr(runtime, "deployment_ref", None) or DEFAULT_DEPLOYMENT_REF
    release_dir = Path(getattr(runtime, "knowledge_release_dir", None) or RELEASE_DIR)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", deployment):
        raise NotEligible("RELEASE_RECORD_INVALID")
    try:
        record = json.loads((release_dir / f"{deployment}.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise NotEligible("NO_RELEASE_RECORD") from None
    except (OSError, ValueError):
        raise NotEligible("RELEASE_RECORD_INVALID") from None
    policy = record.get("authenticity_policy") or {}
    if (record.get("release_record_schema_version") != "1.0" or record.get("deployment_ref") != deployment
            or record.get("profile") != LOCAL_PROFILE or policy.get("decision") != "DEC-012"
            or policy.get("outcome") != "NOT_REQUIRED_BY_POLICY" or not isinstance(record.get("approved_bundles"), list)):
        raise NotEligible("RELEASE_RECORD_INVALID")
    matches = [b for b in record["approved_bundles"] if isinstance(b, dict) and b.get("content_digest") == content_digest]
    if len(matches) != 1:
        raise NotEligible("NOT_APPROVED_FOR_DEPLOYMENT")
    entry = matches[0]
    if not (isinstance(entry.get("release_record_ref"), str) and _REFERENCE.match(entry["release_record_ref"])
            and re.fullmatch(r"\d+\.\d+\.\d+", str(entry.get("bundle_version"))) and entry.get("manifest_schema_version") in ("1.0.0", "1.1.0")):
        raise NotEligible("RELEASE_RECORD_INVALID")
    return entry


def prevalidate(runtime, content_digest: str):
    """ADR-0013 Decision 8 before any write: approved exact digest, governed publication (gate PASS), local verification
    (manifest, per-file hashes, content digest, compatibility, schemas), versions equal the release record, and the
    DEC-012 authenticity exception applies (single-machine synthetic profile only)."""
    if not SYNTHETIC_ONLY_PROFILE:
        raise NotEligible("AUTHENTICITY_REQUIRED")              # DEC-012 never covers a non-synthetic profile
    entry = release_entry(runtime, content_digest)
    verifier = getattr(runtime, "knowledge_verifier", None)
    if verifier is None:
        raise NotEligible("KNOWLEDGE_STORE_UNCONFIGURED")
    try:
        knowledge = verifier.verify(content_digest)
    except BundleRejected as rejected:
        raise NotEligible(rejected.reason) from None
    if knowledge.meta.get("gate") != "PASS":
        raise NotEligible("NOT_GOVERNED_PUBLICATION")           # built without the passed publication gate
    if (knowledge.bundle_version, knowledge.manifest_schema_version) != (entry["bundle_version"], entry["manifest_schema_version"]):
        raise NotEligible("RELEASE_RECORD_MISMATCH")
    return entry, knowledge


def _activation_view(row) -> dict:
    record_id, kind, digest, previous, lifecycle, outcome, recorded = row
    return {"activation_id": record_id, "action_kind": kind, "content_digest": digest, "previous_content_digest": previous,
            "lifecycle_state": lifecycle, "outcome": outcome, "recorded_at": _instant(recorded)}


_ACTIVATION_COLUMNS = ("knowledge_activation_record_id::text, action_kind, bundle_content_digest, previous_bundle_content_digest,"
                       " lifecycle_state, outcome, recorded_at")


def _validate_activation(body) -> list:
    allowed = {"content_digest", "expected_active_content_digest", "governance_change_ref"}
    errors = [{"field": k, "code": "UNKNOWN_FIELD", "message": "Field is not accepted."} for k in body if k not in allowed]
    if not isinstance(body.get("content_digest"), str) or not _DIGEST.match(body["content_digest"]):
        errors.append({"field": "content_digest", "code": "INVALID_DIGEST", "message": "Use the exact lowercase SHA-256 digest."})
    expected = body.get("expected_active_content_digest")
    if expected is not None and (not isinstance(expected, str) or not _DIGEST.match(expected)):
        errors.append({"field": "expected_active_content_digest", "code": "INVALID_DIGEST", "message": "Use a digest or null."})
    ref = body.get("governance_change_ref")
    if not isinstance(ref, str) or not _REFERENCE.match(ref):
        errors.append({"field": "governance_change_ref", "code": "INVALID_VALUE", "message": "Use an uppercase governance reference."})
    return errors


def _audit_knowledge(cur, request, principal, event_type, outcome, metadata, reference_id=None):
    audit_append(cur, AuditEvent(event_type=event_type, outcome=outcome, actor_kind="HUMAN",
                                 actor_principal_id=principal.principal_reference_id, target_kind="KNOWLEDGE_BUNDLE",
                                 target_id=reference_id, correlation_id=request.state.request_id,
                                 safe_metadata={k: v for k, v in metadata.items() if v is not None}))


async def activate_knowledge_bundle(request: Request):
    runtime, principal, error = current_principal(request, "ACTIVATEKNOWLEDGEBUNDLE")
    if error is not None:
        return error
    if "ADMINISTRATOR" not in principal.roles:
        try:                                                       # best effort, as for other S2 denials
            runtime.audit.record(AuditEvent(event_type="AUTHORIZATION_DENIED", outcome="DENIED", actor_kind="HUMAN",
                                            actor_principal_id=principal.principal_reference_id, target_kind="KNOWLEDGE_BUNDLE",
                                            correlation_id=request.state.request_id,
                                            safe_metadata={"reason": "ROLE_NOT_PERMITTED", "operation": "ACTIVATEKNOWLEDGEBUNDLE"}))
        except Exception:
            pass
        return api_error(request, "FORBIDDEN")
    key = request.headers.get("idempotency-key")
    if not idempotency.valid_key(key):
        return api_error(request, "INVALID_REQUEST", field_errors=[{"field": "Idempotency-Key", "code": "REQUIRED",
                                                                    "message": "Send a high-entropy key (16-255 URL-safe characters)."}])
    body, problems = await read_json_object(request)
    if problems or (problems := _validate_activation(body)):
        return api_error(request, "INVALID_REQUEST", field_errors=problems)
    return await run_in_threadpool(_activate, request, runtime, principal, key, body)


def _activate(request, runtime, principal, key, body):
    digest, ref = body["content_digest"], body["governance_change_ref"]
    deployment = getattr(runtime, "deployment_ref", None) or DEFAULT_DEPLOYMENT_REF
    try:
        connection = _connect(runtime)
    except _Unavailable:
        return api_error(request, "DEPENDENCY_UNAVAILABLE")
    with connection:
        try:
            with connection.cursor() as cur:
                if not schema_active(cur):
                    return api_error(request, "DEPENDENCY_UNAVAILABLE")
            claim = idempotency.claim(connection, principal.principal_reference_id, "activateKnowledgeBundle", ACTIVATION_SCOPE, key,
                                      idempotency.semantic_digest("activateKnowledgeBundle", ACTIVATION_SCOPE, body),
                                      supersession=evidence_schema_active(connection))
        except (idempotency.KeyReused, idempotency.InProgress) as e:
            return _idempotent_error(request, e)
        except psycopg.Error:
            return api_error(request, "DEPENDENCY_UNAVAILABLE")
        if isinstance(claim, idempotency.Replay):
            if claim.error_code:
                return api_error(request, claim.error_code)
            with connection.cursor() as cur:
                cur.execute(f"SELECT {_ACTIVATION_COLUMNS} FROM {SCHEMA}.knowledge_activation_record"
                            " WHERE knowledge_activation_record_id = %s", (claim.resource_id,))
                return _json(202, _activation_view(cur.fetchone()))

        def reject(cur, reason, status, code, reference_id=None):
            _audit_knowledge(cur, request, principal, "KNOWLEDGE_ACTIVATION_REJECTED", "DENIED",
                             {"content_digest": digest, "deployment": deployment, "reason": reason, "governance_change_ref": ref},
                             reference_id)
            idempotency.fail_terminal(cur, claim, status, code)
            return api_error(request, code)
        try:
            try:
                entry, knowledge = prevalidate(runtime, digest)       # no transaction is held across verification
            except NotEligible as refused:
                with connection.transaction(), connection.cursor() as cur:
                    return reject(cur, refused.reason, 409, "KNOWLEDGE_NOT_ELIGIBLE")
            with connection.transaction(), connection.cursor() as cur:
                cur.execute(f"SELECT knowledge_deployment_state_id::text, operational_state, active_bundle_content_digest"
                            f" FROM {SCHEMA}.knowledge_deployment_state WHERE deployment_ref = %s FOR UPDATE", (deployment,))
                state = cur.fetchone()
                if state is None:
                    return reject(cur, "NO_DEPLOYMENT_STATE", 409, "KNOWLEDGE_NOT_ELIGIBLE")
                if "expected_active_content_digest" in body and body["expected_active_content_digest"] != state[2]:
                    return reject(cur, "PRECONDITION_FAILED", 412, "PRECONDITION_FAILED")
                # Register the exact reference if new (never altered once recorded); the deployment-state lock above
                # serializes activations, and ON CONFLICT covers a concurrent registration from another deployment.
                cur.execute(f"INSERT INTO {SCHEMA}.knowledge_bundle_reference (knowledge_bundle_reference_id, content_digest,"
                            " bundle_version, manifest_schema_version, commit_sha, component_versions, release_record_ref,"
                            " governance_eligibility, eligibility_observed_at, eligibility_source_ref, first_seen_at)"
                            " VALUES (%s, %s, %s, %s, %s, %s, %s, 'ELIGIBLE', now(), %s, now()) ON CONFLICT (content_digest) DO NOTHING",
                            (str(uuid.uuid4()), digest, knowledge.bundle_version, knowledge.manifest_schema_version,
                             knowledge.commit_sha, json.dumps(dict(knowledge.component_versions)), entry["release_record_ref"],
                             f"release-record:{deployment}:{entry['release_record_ref']}"))
                cur.execute(f"SELECT knowledge_bundle_reference_id::text, governance_eligibility, bundle_version, manifest_schema_version,"
                            f" release_record_ref FROM {SCHEMA}.knowledge_bundle_reference WHERE content_digest = %s", (digest,))
                reference_id, eligibility, *identity = cur.fetchone()
                if eligibility != "ELIGIBLE":                            # withdrawn is never silently re-qualified
                    return reject(cur, "BUNDLE_WITHDRAWN" if eligibility == "WITHDRAWN" else "ELIGIBILITY_UNKNOWN",
                                  409, "KNOWLEDGE_NOT_ELIGIBLE", reference_id)
                if tuple(identity) != (entry["bundle_version"], entry["manifest_schema_version"], entry["release_record_ref"]):
                    return reject(cur, "REFERENCE_MISMATCH", 409, "KNOWLEDGE_NOT_ELIGIBLE", reference_id)
                record_id = str(uuid.uuid4())
                cur.execute(f"INSERT INTO {SCHEMA}.knowledge_activation_record (knowledge_activation_record_id, deployment_ref,"
                            " bundle_content_digest, previous_bundle_content_digest, action_kind, lifecycle_state, validation_outcome,"
                            " authenticity_outcome, actor_principal_id, reason_ref, outcome, recorded_at)"
                            " VALUES (%s, %s, %s, %s, 'ACTIVATION', 'ACTIVE', 'PASSED', 'NOT_REQUIRED_BY_POLICY', %s, %s, 'SUCCEEDED', now())"
                            f" RETURNING {_ACTIVATION_COLUMNS}",
                            (record_id, deployment, digest, state[2], principal.principal_reference_id, ref))
                view = _activation_view(cur.fetchone())
                cur.execute(f"UPDATE {SCHEMA}.knowledge_deployment_state SET operational_state = 'ACTIVE', active_bundle_content_digest = %s,"
                            " current_activation_record_id = %s, state_changed_at = now() WHERE knowledge_deployment_state_id = %s",
                            (digest, record_id, state[0]))
                _audit_knowledge(cur, request, principal, "KNOWLEDGE_ACTIVATED", "SUCCEEDED",
                                 {"content_digest": digest, "previous_content_digest": state[2], "activation_id": record_id,
                                  "deployment": deployment, "governance_change_ref": ref, "authenticity": "NOT_REQUIRED_BY_POLICY"},
                                 reference_id)
                idempotency.complete(cur, claim, 202, "knowledge_activation_record", record_id)
                return _json(202, view)
        except idempotency.StaleClaim:
            return api_error(request, "IDEMPOTENCY_IN_PROGRESS")
        except psycopg.Error:
            idempotency.release(connection, claim, 503, "DEPENDENCY_UNAVAILABLE")
            return api_error(request, "DEPENDENCY_UNAVAILABLE")


def install(app: FastAPI):
    app.add_api_route("/api/v1/knowledge/deployment/activate", activate_knowledge_bundle, methods=["POST"])
    app.add_api_route("/api/v1/knowledge/active", get_active_knowledge, methods=["GET"])
    app.add_api_route("/api/v1/knowledge/bundles/{content_digest}", get_knowledge_bundle, methods=["GET"])
    app.add_api_route("/api/v1/knowledge/activations", list_knowledge_activations, methods=["GET"])
