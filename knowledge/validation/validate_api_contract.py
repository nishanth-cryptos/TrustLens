"""TrustLens Phase 6 P6-WP3 — static validator for the API v1 operation catalog.

Validates contracts/api/api-v1.json (machine-readable source for the P6-WP4 OpenAPI encoding of API-001) against
contracts/api/api-contract.schema.json (Draft 2020-12), then enforces the authorization, authority and protocol
invariants JSON Schema cannot express:

  AC-01 catalog is schema-valid
  AC-02 operation_id unique; METHOD + path template unique
  AC-03 every path is under /api/v1, except internal health probes under /health/
  AC-04 every non-internal operation requires authentication and names at least one role; probes expose nothing sensitive
  AC-05 evidence/derived-content operations require content-level resource authorization and audit; ADMINISTRATOR never
        holds content access by role (break-glass only)
  AC-06 immutable resources (DetectionResult, Evaluation, AuditEvent, Replay, ReportBundle, adjudications) accept no
        PUT/PATCH/DELETE
  AC-07 HTTP DELETE is not used for governed resources (no DELETE operation in v1)
  AC-08 governed actions (content access, adjudication, grants/assignment, break-glass, deletion, knowledge control,
        report export, corrections) are audit REQUIRED with a known audit event
  AC-09 every POST is idempotency REQUIRED; content PUT is naturally idempotent
  AC-10 knowledge control uses the exact content_digest (64-hex) and never bundle_version alone or latest/newest/current
  AC-11 no arbitrary server-side URL fetch (no fetch/proxy paths, no *_url request fields, no server_side_fetch)
  AC-12 no tenant field, parameter or filter anywhere while ASM-002 is unconfirmed
  AC-13 no probability / score field in any schema
  AC-14 replay is distinct from (re-)evaluation: pinned knowledge only, no AI recall, no substitution, no mode/knowledge input
  AC-15 request schemas never accept server-controlled fields (actor, owner, audit hash, fence token, decision axes,
        provenance, digests-as-authority, internal state, role grants)
  AC-16 every request schema rejects unknown fields
  AC-17 API state vocabularies map every persistence state (contracts/postgresql/schema-v1.json) losslessly enough
  AC-18 vocabulary references resolve (API or persistence vocabularies)
  AC-19 error codes unique; operation errors resolve; required codes present; INTERNAL_ERROR/INTEGRITY_FAILURE only 5xx
  AC-20 list operations use cursor pagination with an explicit allow-list of safe filters
  AC-21 commands on mutable shared resources carry If-Match concurrency; no PATCH on governed lifecycle
  AC-22 schema references resolve
  AC-23 field visibility never grants ADMINISTRATOR content and hides secrets from everyone
  AC-24 the DetectionResult response carries the exact Phase-3 axes and the not-an-official-determination marker, and
        EVERY field of the governed result response tree traces structurally either to an existing, runtime-emitted node of
        the promoted Phase-3 schemas or to an allow-listed API-only transport/provenance category; nothing invents
        decision semantics (priority, rank, score, probability, AI confidence, new decision category)
  AC-25 break-glass: in v1 only ADMINISTRATOR creates/activates break-glass and only ADMINISTRATOR may use it for content;
        the review must be by a different principal
  AC-26 operations that grant case access forbid self-assignment (assignee != authenticated caller)
  AC-27 C4 content fields (adjudication rationale, explanation evidence basis) need content permission, are hidden from
        ADMINISTRATOR / knowledge roles / owners where policy says so, and every operation that can return one is C4

It then applies every mutation in contracts/api/fixtures/negative-mutations.json to a copy and requires the named
check to fail. Offline and deterministic: reads repository files only; no network.

Usage:  .venv/bin/python knowledge/validation/validate_api_contract.py [--quiet]
Exit 0 = catalog valid and every negative mutation rejected by its expected check.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "contracts" / "api" / "api-v1.json"
SCHEMA_PATH = ROOT / "contracts" / "api" / "api-contract.schema.json"
NEGATIVE_PATH = ROOT / "contracts" / "api" / "fixtures" / "negative-mutations.json"
PERSISTENCE_PATH = ROOT / "contracts" / "postgresql" / "schema-v1.json"

HEX64 = "^[0-9a-f]{64}$"
IMMUTABLE_RESOURCES = {"DetectionResult", "Evaluation", "AuditEvent", "Replay", "ReportBundle", "AnalystAdjudication",
                       "UserCorrection", "EvidenceContent", "KnowledgeActivationRecord"}
AUDIT_REQUIRED_TARGETS = {"EvidenceContent", "AnalystAdjudication", "CaseAccessGrant", "ReviewItem", "BreakGlassGrant",
                          "DeletionRequest", "KnowledgeActivationRecord", "KnowledgeBundleReference", "UserCorrection"}
TENANT = re.compile(r"tenant", re.I)
SCORE = re.compile(r"(probab|likelihood|percent|score)", re.I)
FETCH_PATH = re.compile(r"(fetch|proxy|crawl|scrape|resolve-url|url-check|lookup-url)", re.I)
LATEST = re.compile(r"\b(latest|newest|current|previous)\b", re.I)
FORBIDDEN_REQUEST_FIELDS = {
    "actor_id", "actor_principal_id", "adjudicated_by", "adjudicating_principal_id", "created_by", "owner_principal_id",
    "owner_id", "principal_id_override", "event_hash", "previous_event_hash", "audit_hash", "execution_fence_token",
    "classification", "risk_level", "decision_severity", "detection_confidence", "matched_evidence_strength",
    "rule_results", "matched_rules", "governing_rule", "explanation", "recommended_actions", "ai_verdict",
    "ai_confidence", "engine_version", "result_contract_version", "result_digest", "bundle_version",
    "bundle_content_digest", "content_sha256", "replay_material_digest", "status", "state", "created_at",
    "completed_at", "adjudicated_at", "role", "roles", "grant_kind", "is_synthetic", "failure_category",
}
CONTENT_AUTHZ = {"CASE_EVIDENCE_CONTENT", "CASE_DERIVED_CONTENT", "CASE_OWNER", "CASE_ASSIGNED_ANALYST"}
REQUIRED_ERROR_CODES = {"INVALID_REQUEST", "UNAUTHENTICATED", "FORBIDDEN", "NOT_FOUND", "CONFLICT", "PRECONDITION_FAILED",
                        "RATE_LIMITED", "DEPENDENCY_UNAVAILABLE", "INTEGRITY_FAILURE", "REPLAY_UNAVAILABLE",
                        "REPORT_REGENERATION_UNAVAILABLE", "INTERNAL_ERROR", "IDEMPOTENCY_KEY_REUSED",
                        "REMOVED_UNDER_GOVERNANCE", "UNSUPPORTED_MEDIA_TYPE", "PAYLOAD_TOO_LARGE"}
SAFE_FILTERS = re.compile(r"^(state|created_from|created_to|relationship|received_from|received_to|upload_state|artifact_kind|"
                          r"submission_id|requested_from|requested_to|result_availability|status|outcome|assigned_to_me|"
                          r"queued_from|queued_to|grant_kind|active|action_kind|recorded_from|recorded_to|scope_kind|case_id|"
                          r"event_type|target_kind|target_id|occurred_from|occurred_to)$")
STATE_MAPPED = ["api_case_state", "api_submission_state", "api_upload_state", "api_evaluation_state",
                "api_evaluation_failure_reason", "api_review_state", "api_report_state", "api_deletion_state",
                "api_knowledge_deployment_state"]
GOVERNED_RESULT_ROOT = "DetectionResultResponse"
API_TRACE_CATEGORIES = {"VIEW_SELECTOR", "DISCLAIMER", "INTERPRETATION_NOTICE", "PERSISTENCE_PROVENANCE"}
# Promoted-schema nodes that are reserved but NOT emitted by the Phase-3 runtime (P3-WP6 asserts "no priority").
RESERVED_NOT_EMITTED = {("knowledge/schemas/detection/detection-result.schema.json", "/$defs/recommendedAction/properties/priority")}
INVENTED_SEMANTICS = re.compile(r"(priority|rank|score|probab|likelihood|percent|confidence|severity|risk|classification|"
                                r"verdict|category|urgency|weight)", re.I)
RESULT_AXES = {"classification": "classification", "decision_severity": "decision_severity",
               "matched_evidence_strength": "matched_evidence_strength", "risk_level": "risk_level",
               "detection_confidence": "detection_confidence", "input_support_status": "input_support_status"}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _template(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def _path_params(path: str) -> list[str]:
    return re.findall(r"\{([^}]+)\}", path)


def check(cat: dict, validator: Draft202012Validator, persistence: dict) -> list[tuple[str, str]]:
    errs: list[tuple[str, str]] = []

    def e(code, msg):
        errs.append((code, msg))

    for err in sorted(validator.iter_errors(cat), key=lambda x: list(x.path)):
        e("AC-01", f"schema: {err.message} at /{'/'.join(map(str, err.path))}")
    if errs:
        return errs

    ops, schemas, vocab = cat["operations"], cat["schemas"], cat["vocabularies"]
    pvocab = persistence["vocabularies"]
    codes = {c["code"]: c for c in cat["error_codes"]}

    # ---- AC-18 vocab resolution helper
    def vocab_values(name):
        v = vocab.get(name)
        if v is None:
            return None
        if v["source"] == "PERSISTENCE":
            pv = pvocab.get(v["persistence_vocabulary"])
            return None if pv is None else pv["values"]
        return v["values"]

    for name, v in vocab.items():
        if vocab_values(name) is None:
            e("AC-18", f"vocabulary {name} does not resolve")

    # ---- AC-22 / AC-12 / AC-13 / AC-15 / AC-16 schemas
    def all_fields():
        for sn, sd in schemas.items():
            for fd in sd["fields"]:
                yield sn, sd, fd

    for sn, sd, fd in all_fields():
        for ref in ("schema", "items"):
            r = fd.get(ref)
            if r and r not in schemas and r not in ("string", "uuid"):
                e("AC-22", f"{sn}.{fd['name']}: {ref} {r} does not resolve")
        for ref in ("vocabulary", "items_vocabulary"):
            r = fd.get(ref)
            if r and vocab_values(r) is None:
                e("AC-18", f"{sn}.{fd['name']}: vocabulary {r} does not resolve")
        if TENANT.search(fd["name"]) and not cat["tenancy"]["tenant_fields_permitted"]:
            e("AC-12", f"{sn}.{fd['name']}: tenant field while ASM-002 is unconfirmed")
        if SCORE.search(fd["name"]):
            e("AC-13", f"{sn}.{fd['name']}: probability/score field forbidden (INV-10)")
        if sd["kind"] == "REQUEST":
            if fd["name"] in FORBIDDEN_REQUEST_FIELDS:
                e("AC-15", f"{sn}.{fd['name']}: server-controlled field accepted from client (mass assignment)")
            if fd["name"].endswith("_url") or fd["name"] in ("url", "target", "fetch"):
                e("AC-11", f"{sn}.{fd['name']}: URL field in a request could become a server-side fetch target")
    for sn, sd in schemas.items():
        if sd["kind"] == "REQUEST" and sd["unknown_fields"] != "REJECT":
            e("AC-16", f"{sn}: request schemas must reject unknown fields")

    # ---- per-operation checks
    seen_id, seen_route = set(), set()
    role_universe = set(cat["roles"])
    audit_types = set(vocab_values("audit_event_type") or [])
    for o in ops:
        oid, m, p = o["operation_id"], o["method"], o["path"]
        if oid in seen_id:
            e("AC-02", f"duplicate operation_id {oid}")
        seen_id.add(oid)
        route = (m, _template(p))
        if route in seen_route:
            e("AC-02", f"duplicate route {m} {p}")
        seen_route.add(route)

        # AC-03 / AC-04
        if o["internal"]:
            if not p.startswith("/health/"):
                e("AC-03", f"{oid}: internal operations are limited to /health/ probes")
            if o["roles"] or o["sensitive_content_permission"] != "NONE" or o["sensitivity"] not in ("C2",):
                e("AC-04", f"{oid}: internal probe must expose nothing sensitive and grant no roles")
        else:
            if not p.startswith(cat["base_path"] + "/"):
                e("AC-03", f"{oid}: path {p} not under {cat['base_path']}")
            if o["authentication"] != "REQUIRED" or not o["roles"]:
                e("AC-04", f"{oid}: protected operation must require authentication and name roles")
        for r in o["roles"] + o["break_glass_roles"]:
            if r not in role_universe:
                e("AC-04", f"{oid}: unknown role {r}")

        # AC-12 path params / filters
        for prm in _path_params(p) + o.get("list", {}).get("filters", []):
            if TENANT.search(prm):
                e("AC-12", f"{oid}: tenant parameter {prm}")

        # AC-05 content access
        if o["sensitive_content_permission"] != "NONE":
            if o["resource_authorization"] not in CONTENT_AUTHZ:
                e("AC-05", f"{oid}: content access needs content-level resource authorization, got {o['resource_authorization']}")
            if "ADMINISTRATOR" in o["roles"]:
                e("AC-05", f"{oid}: ADMINISTRATOR must not hold content access by role (break-glass only)")
            if o["audit"] != "REQUIRED" and o["method"] == "GET":
                e("AC-05", f"{oid}: content read must be audited")
        if o["break_glass_roles"] and o["sensitive_content_permission"] == "NONE":
            e("AC-05", f"{oid}: break-glass applies only to content operations")

        # AC-06 / AC-07
        if m in ("PUT", "PATCH", "DELETE") and o["target_resource"] in IMMUTABLE_RESOURCES - {"EvidenceContent"}:
            e("AC-06", f"{oid}: {m} on immutable resource {o['target_resource']}")
        if m in ("PATCH", "DELETE") and o["target_resource"] == "EvidenceContent":
            e("AC-06", f"{oid}: evidence content is write-once")
        if m == "PUT" and o["target_resource"] == "EvidenceContent" and o["idempotency"] != "NATURALLY_IDEMPOTENT":
            e("AC-09", f"{oid}: content PUT must be naturally idempotent (write-once by digest)")
        if m == "DELETE":
            e("AC-07", f"{oid}: HTTP DELETE is not used for governed resources in v1 (use deletion requests)")
        if m == "PATCH" and o["target_resource"] in ("Case", "DeletionRequest", "ReviewItem", "KnowledgeDeploymentState",
                                                      "KnowledgeBundleReference", "BreakGlassGrant", "CaseAccessGrant"):
            e("AC-21", f"{oid}: governed lifecycle transitions use explicit commands, not PATCH")

        # AC-08 audit
        must_audit = (o["target_resource"] in AUDIT_REQUIRED_TARGETS and m != "GET") \
            or o["sensitive_content_permission"] != "NONE" or o.get("knowledge_control") or oid == "getReportContent"
        if must_audit and o["audit"] != "REQUIRED":
            e("AC-08", f"{oid}: governed action must be audit REQUIRED")
        if o["audit"] == "REQUIRED":
            ev = o["audit_event"]
            if ev is None or (ev not in audit_types and ev != "PENDING_TAXONOMY_P6_WP6"):
                e("AC-08", f"{oid}: audit event {ev!r} not in the governed audit taxonomy")

        # AC-09 idempotency
        if m == "POST" and o["idempotency"] != "REQUIRED":
            e("AC-09", f"{oid}: POST commands/creations require an Idempotency-Key")
        if m == "POST" and "IDEMPOTENCY_KEY_REUSED" not in o["errors"]:
            e("AC-09", f"{oid}: must declare IDEMPOTENCY_KEY_REUSED (conflicting key reuse)")

        # AC-10 knowledge control
        if o.get("knowledge_control"):
            req_schema = schemas.get(o["request_schema"] or "", {"fields": []})
            names = {f["name"]: f for f in req_schema["fields"]}
            in_path = "content_digest" in _path_params(p)
            cd = names.get("content_digest")
            if not in_path and not (cd and cd["required"] and cd.get("pattern") == HEX64):
                e("AC-10", f"{oid}: knowledge control must address the exact 64-hex content_digest")
            if "bundle_version" in names:
                e("AC-10", f"{oid}: bundle_version is not an activation identity")
            if LATEST.search(p) or any(LATEST.search(n) for n in names):
                e("AC-10", f"{oid}: latest/newest/current/previous semantics forbidden")
            for f in req_schema["fields"]:
                vv = vocab_values(f.get("vocabulary", "")) if f.get("vocabulary") else None
                if vv and any(LATEST.search(x.replace("_", " ")) for x in vv):
                    e("AC-10", f"{oid}: request enum offers latest/newest semantics")
        if re.search(r"/(rules|rule|indicators|taxonomy|rule-sets)(/|$)", p) and m != "GET":
            e("AC-10", f"{oid}: direct rule/knowledge body mutation bypasses Git/CI governance")

        # AC-11 fetch
        if FETCH_PATH.search(p) or o.get("server_side_fetch"):
            e("AC-11", f"{oid}: arbitrary server-side URL fetch is out of scope (P6-WP5 / ADR-0012)")

        # AC-14 replay
        rs = o.get("replay_semantics")
        if rs is not None:
            if rs["ai_recall"] or rs["knowledge_selection"] != "PINNED_ONLY" or rs["material_substitution"] != "FORBIDDEN" \
                    or rs["creates_new_evaluation"]:
                e("AC-14", f"{oid}: replay must use pinned material only, never AI recall, substitution or a new evaluation")
            names = {f["name"] for f in schemas.get(o["request_schema"] or "", {"fields": []})["fields"]}
            bad = names & {"analysis_mode", "content_digest", "bundle_version", "ai_extraction", "profile", "evaluation_profile_id",
                           "predecessor_evaluation_id", "use_latest_knowledge"}
            if bad:
                e("AC-14", f"{oid}: replay request accepts re-analysis inputs {sorted(bad)}")
            if o.get("creates_new_evaluation"):
                e("AC-14", f"{oid}: replay must not create a new evaluation")
        if "replay" in p and rs is None and m == "POST":
            e("AC-14", f"{oid}: replay operation must declare replay_semantics")

        # AC-19 errors
        for c in o["errors"]:
            if c not in codes:
                e("AC-19", f"{oid}: unknown error code {c}")

        # AC-20 lists
        if m == "GET" and (o["response_schema"].endswith("ListResponse") or o["response_schema"] == "ReviewQueueResponse"):
            lst = o.get("list")
            if not lst or lst["pagination"] != "CURSOR":
                e("AC-20", f"{oid}: list operations use cursor pagination")
            else:
                for flt in lst["filters"]:
                    if not SAFE_FILTERS.match(flt):
                        e("AC-20", f"{oid}: filter {flt} is not on the allow-list")

        # AC-21 concurrency for shared mutable commands
        if m == "POST" and o["target_resource"] in ("Case", "ReviewItem", "DeletionRequest") \
                and o["operation_id"] not in ("createCase", "createDeletionRequest") and o["concurrency"] != "IF_MATCH_REQUIRED":
            e("AC-21", f"{oid}: command on a shared mutable resource must require If-Match")

        # AC-22 schema refs
        for ref in (o["request_schema"], o["response_schema"]):
            if ref and ref not in schemas:
                e("AC-22", f"{oid}: schema {ref} does not resolve")

    # ---- AC-14 replay distinct from evaluation
    rep = [o for o in ops if o.get("replay_semantics") is not None]
    evs = [o for o in ops if o.get("creates_new_evaluation")]
    if not rep:
        e("AC-14", "no replay operation declared")
    if not evs:
        e("AC-14", "no (re-)evaluation operation declared")
    for r in rep:
        for ev in evs:
            if r["request_schema"] == ev["request_schema"] or _template(r["path"]) == _template(ev["path"]):
                e("AC-14", f"{r['operation_id']} is not distinct from {ev['operation_id']}")

    # ---- AC-17 state mapping coverage
    for name in STATE_MAPPED:
        v = vocab.get(name)
        if not v or v["source"] != "API" or "maps_from" not in v:
            e("AC-17", f"{name} must map from a persistence vocabulary")
            continue
        src = pvocab.get(v["maps_from"]["persistence_vocabulary"])
        if src is None:
            e("AC-17", f"{name}: unknown persistence vocabulary {v['maps_from']['persistence_vocabulary']}")
            continue
        mp = v["maps_from"]["mapping"]
        if sorted(mp) != sorted(src["values"]):
            e("AC-17", f"{name}: mapping keys {sorted(mp)} != persistence states {sorted(src['values'])}")
        for k, tgt in mp.items():
            if tgt is not None and tgt not in v["values"]:
                e("AC-17", f"{name}: {k} maps to unknown API value {tgt}")
    ev_map = vocab.get("api_evaluation_state", {}).get("maps_from", {}).get("mapping", {})
    if ev_map.get("RESULT_COMPUTED_PERSISTENCE_PENDING") == "COMPLETED" or any(
            ev_map.get(k) == "COMPLETED" for k in ev_map if k.startswith("FAILED")):
        e("AC-17", "only a durably COMPLETED evaluation may be exposed as COMPLETED")
    up_map = vocab.get("api_upload_state", {}).get("maps_from", {}).get("mapping", {})
    if any(up_map.get(k) == "FINALIZED" for k in up_map if k != "FINALIZED"):
        e("AC-17", "evidence may be exposed as FINALIZED only when durably verified")

    # ---- AC-19 codes
    seen = set()
    for c in cat["error_codes"]:
        if c["code"] in seen:
            e("AC-19", f"duplicate error code {c['code']}")
        seen.add(c["code"])
    missing = REQUIRED_ERROR_CODES - seen
    if missing:
        e("AC-19", f"missing required error codes {sorted(missing)}")
    for c in cat["error_codes"]:
        if c["code"] in ("INTERNAL_ERROR", "INTEGRITY_FAILURE", "DEPENDENCY_UNAVAILABLE") and c["http_status"] < 500:
            e("AC-19", f"{c['code']} must be a 5xx status")
        if c["code"] not in ("INTERNAL_ERROR", "INTEGRITY_FAILURE", "DEPENDENCY_UNAVAILABLE") and c["http_status"] >= 500:
            e("AC-19", f"{c['code']}: client-attributable errors must not be 5xx")
    api_codes = set(vocab_values("error_code") or [])
    if api_codes != seen:
        e("AC-19", "error_code vocabulary and error_codes table disagree")

    # ---- AC-12 tenancy contract
    if cat["tenancy"]["asm_002_status"] == "UNCONFIRMED_PROVISIONAL" and cat["tenancy"]["tenant_fields_permitted"]:
        e("AC-12", "tenant fields may not be permitted while ASM-002 is unconfirmed")

    # ---- AC-23 field visibility
    fv = cat["field_visibility"]
    for grp in ("raw_evidence_content", "normalized_sensitive_content", "governed_observations", "per_rule_results",
                "result_explanation_evidence_basis", "adjudication_rationale"):
        if fv.get(grp, {}).get("ADMINISTRATOR") not in ("HIDDEN", "BREAK_GLASS_ONLY"):
            e("AC-23", f"field visibility {grp}: ADMINISTRATOR must not see content by role")
    for role, vis in fv.get("secrets_and_keys", {"x": "missing"}).items():
        if vis != "HIDDEN":
            e("AC-23", f"secrets_and_keys must be HIDDEN for every role ({role}: {vis})")
    for grp in ("raw_evidence_content", "per_rule_results", "governed_observations"):
        for role in ("KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER"):
            if fv.get(grp, {}).get(role) != "HIDDEN":
                e("AC-23", f"{grp}: knowledge roles do not read case content")

    # ---- AC-24 result response
    dr = schemas.get("DetectionResultResponse")
    if not dr:
        e("AC-24", "DetectionResultResponse missing")
    else:
        fields = {f["name"]: f for f in dr["fields"]}
        for fname, voc in RESULT_AXES.items():
            if fields.get(fname, {}).get("vocabulary") != voc:
                e("AC-24", f"DetectionResultResponse.{fname} must use the {voc} vocabulary")
        if "not_an_official_determination" not in fields:
            e("AC-24", "DetectionResultResponse must carry the not-an-official-determination marker")
    check_result_traceability(cat, e)
    check_grant_and_content_rules(cat, e)
    return errs


def _resolve_pointer(path: str, pointer: str):
    node = load(ROOT / path)
    for part in [x for x in pointer.split("/") if x]:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def check_result_traceability(cat: dict, e) -> None:
    """AC-24 — structural traceability of the governed result response tree."""
    schemas = cat["schemas"]
    if GOVERNED_RESULT_ROOT not in schemas:
        e("AC-24", f"{GOVERNED_RESULT_ROOT} missing")
        return
    seen, stack = set(), [GOVERNED_RESULT_ROOT]
    while stack:
        sn = stack.pop()
        if sn in seen or sn not in schemas:
            continue
        seen.add(sn)
        for f in schemas[sn]["fields"]:
            where = f"{sn}.{f['name']}"
            for ref in (f.get("schema"), f.get("items")):
                if ref and ref in schemas:
                    stack.append(ref)
            tr = f.get("trace")
            if not tr:
                e("AC-24", f"{where}: governed result field has no trace to Phase-3 authority or an API-only category")
                continue
            if tr.startswith("api:"):
                cat_ = tr[4:]
                if cat_ not in API_TRACE_CATEGORIES:
                    e("AC-24", f"{where}: API-only category {cat_} is not allow-listed")
                voc = cat["vocabularies"].get(f.get("vocabulary") or f.get("items_vocabulary") or "")
                decision_vocab = voc is not None and (voc["source"] != "API"
                                                      or any(INVENTED_SEMANTICS.search(v) for v in voc["values"]))
                if INVENTED_SEMANTICS.search(f["name"]) or decision_vocab:
                    e("AC-24", f"{where}: an API-only field must not carry decision semantics")
                continue
            path, _, pointer = tr[len("phase3:"):].partition("#")
            if (path, pointer) in RESERVED_NOT_EMITTED:
                e("AC-24", f"{where}: traces to {pointer}, reserved in the schema but not emitted by the Phase-3 runtime")
            elif _resolve_pointer(path, pointer) is None:
                e("AC-24", f"{where}: trace {tr} does not resolve in the promoted Phase-3 schemas")


def _response_closure(schemas: dict, root: str) -> set:
    seen, stack = set(), [root]
    while stack:
        sn = stack.pop()
        if sn in seen or sn not in schemas:
            continue
        seen.add(sn)
        for f in schemas[sn]["fields"]:
            for ref in (f.get("schema"), f.get("items")):
                if ref and ref in schemas:
                    stack.append(ref)
    return seen


def check_grant_and_content_rules(cat: dict, e) -> None:
    ops, schemas, fv = cat["operations"], cat["schemas"], cat["field_visibility"]
    # AC-25 break-glass
    creators = [o for o in ops if o["target_resource"] == "BreakGlassGrant" and o["method"] == "POST"
                and o["resource_authorization"] == "BREAK_GLASS_SELF"]
    if not creators:
        e("AC-25", "break-glass creation operation missing")
    for o in creators:
        if o["roles"] != ["ADMINISTRATOR"]:
            e("AC-25", f"{o['operation_id']}: only ADMINISTRATOR may create/activate break-glass in v1 (got {o['roles']})")
    for o in ops:
        if set(o["break_glass_roles"]) - {"ADMINISTRATOR"}:
            e("AC-25", f"{o['operation_id']}: break-glass content access limited to ADMINISTRATOR in v1")
        if o["resource_authorization"] == "BREAK_GLASS_REVIEWER" and "REVIEWER_NOT_GRANTEE" not in o.get("caller_constraints", []):
            e("AC-25", f"{o['operation_id']}: break-glass review must be by a different principal")
    # AC-26 self-assignment
    for o in ops:
        if o.get("grants_case_access") and "ASSIGNEE_NOT_CALLER" not in o.get("caller_constraints", []):
            e("AC-26", f"{o['operation_id']}: granting case access must forbid assignee == caller")
    if not any(o.get("grants_case_access") for o in ops):
        e("AC-26", "no case-access-granting operation declares grants_case_access")
    # AC-27 C4 content fields
    content_fields = {(sn, f["name"]) for sn, sd in schemas.items() for f in sd["fields"] if f.get("visibility") == "CONTENT_PERMISSION"}
    for need in (("AdjudicationResponse", "rationale"), ("ExplanationView", "evidence_basis")):
        if need not in content_fields:
            e("AC-27", f"{need[0]}.{need[1]} must require content permission")
    rv = fv.get("adjudication_rationale", {})
    if rv.get("ANALYST") != "IF_GRANTED_CONTENT":
        e("AC-27", "adjudication rationale for ANALYST must be IF_GRANTED_CONTENT (assignment alone is insufficient)")
    for role in ("USER", "ADMINISTRATOR", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER"):
        if rv.get(role) != "HIDDEN":
            e("AC-27", f"adjudication rationale must be HIDDEN for {role}")
    for o in ops:
        closure = _response_closure(schemas, o["response_schema"])
        if any(sn in closure for sn, _ in content_fields) and o["sensitivity"] not in ("C3", "C4"):
            e("AC-27", f"{o['operation_id']}: can return C4 content but is classified {o['sensitivity']}")


# ================================================================ negative mutations (same harness as the data contract)


def _select(node, seg):
    if isinstance(seg, dict):
        (k, v), = seg.items()
        for i, item in enumerate(node):
            if isinstance(item, dict) and item.get(k) == v:
                return i
        raise KeyError(f"no element with {k}={v!r}")
    return seg


def apply_mutation(doc: dict, m: dict) -> dict:
    c = copy.deepcopy(doc)
    node = c
    for seg in m["path"][:-1]:
        node = node[_select(node, seg)]
    last = _select(node, m["path"][-1])
    if m["op"] == "set":
        node[last] = copy.deepcopy(m["value"])
    elif m["op"] == "append":
        node[last].append(copy.deepcopy(m["value"]))
    elif m["op"] == "remove":
        del node[last]
    else:
        raise ValueError(f"unknown op {m['op']}")
    return c


def main() -> int:
    quiet = "--quiet" in sys.argv
    cat, persistence = load(CATALOG_PATH), load(PERSISTENCE_PATH)
    schema = load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    errs = check(cat, validator, persistence)
    if errs:
        for code, msg in errs:
            print(f"  FAIL  {code}  {msg}")
        print(f"API CONTRACT: FAIL — {len(errs)} violation(s) in {CATALOG_PATH.relative_to(ROOT)}")
        return 1

    negatives = load(NEGATIVE_PATH)["mutations"]
    failures = []
    for m in negatives:
        try:
            mutated = apply_mutation(cat, m)
        except (KeyError, IndexError, ValueError) as ex:
            failures.append(f"{m['id']}: mutation could not be applied ({ex})")
            continue
        found = {code for code, _ in check(mutated, validator, persistence)}
        if m["expect"] not in found:
            failures.append(f"{m['id']}: expected {m['expect']}, got {sorted(found) or 'no violation'}")
        elif not quiet:
            print(f"  ok    {m['id']} rejected by {m['expect']}: {m['description']}")
    if failures:
        for f in failures:
            print(f"  FAIL  negative fixture {f}")
        print("API CONTRACT: FAIL — a guard did not bite")
        return 1

    print(f"API CONTRACT: PASS — {len(cat['operations'])} operations, {len(cat['schemas'])} schemas, "
          f"{len(cat['error_codes'])} error codes; {len(negatives)} negative mutations rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
