"""P7-WP1 deterministic offline UX foundation checks (UXF-01..UXF-65).

Builder verification, not independent review or runtime authorization testing. Reads
accepted authorities without editing them. The existing 19-artifact Phase-6 snapshot
remains unchanged, including its OPEN four-schema omission. Repository-wide freeze
verification is additionally a builder git-diff obligation, not a repaired snapshot.

Negative fixtures inject one change into an in-memory input copy and must fail their
named UXF check, not merely any check. No network, subprocess or frontend is used.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "bbe741b8ebfb7adbc399c1231b74f67f73ba2cfc"
STATUS = "P7-WP1 UX FOUNDATION APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING"
CONTRACT = "contracts/ux/ux-foundation-v1.json"
SCHEMA = "contracts/ux/ux-foundation-contract.schema.json"
FIXTURES = "contracts/ux/fixtures/negative-mutations.json"
DOC = "docs/07-ux/UX-001-experience-foundation-information-architecture.md"
GATE = "docs/00-program/GATE-026-phase-7-ux-foundation.md"
CHECK_COUNT = 65
REQUIRED_SURFACES = {
    "UX-SESSION", "UX-HOME", "UX-CASES", "UX-CASE", "UX-SUBMISSION",
    "UX-EVIDENCE-METADATA", "UX-EVIDENCE-CONTENT", "UX-EVALUATION", "UX-RESULT",
    "UX-ADJUDICATION", "UX-REPORTS", "UX-REPORT-CONTENT", "UX-REPLAY",
    "UX-REVIEW-QUEUE", "UX-ASSIGNMENT", "UX-AUDIT", "UX-ENRICHMENT",
    "UX-BREAK-GLASS", "UX-DELETION", "UX-ACCESS-GRANTS", "UX-ACCOUNT", "UX-KNOWLEDGE",
}
PRESENTATION_CONCEPTS = {"Home", "Overview", "Activity", "History", "SupportingContext", "ReAnalysis", "SessionEntry"}
REQUIRED_OBJECTS = {
    "Case": "Case", "Submission": "Submission", "EvidenceItem": "EvidenceItem",
    "EvidenceDerivative": "EvidenceDerivative", "Evaluation": "Evaluation",
    "GovernedInputArtifact": "GovernedInputArtifact", "DetectionResult": "DetectionResultRecord",
    "Adjudication": "AnalystAdjudication", "Report": "ReportBundleRecord", "Replay": "ReplayExecution",
    "ExternalEnrichment": "ExternalEnrichmentResult", "GovernedRemoval": "GovernedRemovalTombstone",
}
CLASSIFICATION_MEANINGS = {
    "NO_SCAM_PATTERN": "NO_GOVERNED_PATTERN_MATCHED_NOT_SAFETY",
    "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_BASIS_NOT_SAFETY",
    "UNSUPPORTED": "CANNOT_EVALUATE_NOT_SAFETY", "ERROR": "ERROR_NOT_SAFETY",
    "SCAM_PATTERN_SUSPECTED": "UNCERTAINTY_VISIBLE", "SCAM_PATTERN_DETECTED": "NOT_LEGAL_GUILT",
}
STATE_CODES = {
    "LOADING": [], "EMPTY": [], "READY": [],
    "ACTION_PENDING": ["IDEMPOTENCY_IN_PROGRESS"],
    "ACTION_FAILED": ["INVALID_REQUEST"], "AUTHENTICATION_REQUIRED": ["UNAUTHENTICATED"],
    "ACCESS_DENIED": ["FORBIDDEN"], "CONTENT_PERMISSION_REQUIRED": ["FORBIDDEN"],
    "NOT_FOUND_OR_NOT_VISIBLE": ["NOT_FOUND"], "PRECONDITION_REQUIRED": ["PRECONDITION_REQUIRED"],
    "STALE_STATE": ["PRECONDITION_FAILED"], "CONFLICT": ["CONFLICT", "STATE_CONFLICT", "IDEMPOTENCY_KEY_REUSED"],
    "REMOVED_UNDER_GOVERNANCE": ["REMOVED_UNDER_GOVERNANCE"],
    "TEMPORARILY_UNAVAILABLE": ["DEPENDENCY_UNAVAILABLE"], "UNSUPPORTED_INPUT": ["UNSUPPORTED_MEDIA_TYPE"],
    "REPLAY_UNAVAILABLE": ["REPLAY_UNAVAILABLE"],
    "REPORT_REGENERATION_UNAVAILABLE": ["REPORT_REGENERATION_UNAVAILABLE"],
    "INTEGRITY_ERROR": ["INTEGRITY_FAILURE"], "SERVER_ERROR": ["INTERNAL_ERROR"],
    "RATE_LIMITED": ["RATE_LIMITED"], "INPUT_LIMIT_EXCEEDED": ["PAYLOAD_TOO_LARGE"],
}
ACCESS_KEYS = ("operation_id", "roles", "resource_authorization", "sensitive_content_permission",
               "break_glass_roles", "sensitivity")
EXPOSURES = {"raw_provider_bodies", "credentials_secrets", "connector_topology", "internal_hosts_ips",
             "evidence_store_locators", "raw_evidence_without_permission", "c4_without_permission",
             "execution_fence_tokens", "idempotency_key_material", "audit_equals_activity"}
# Hashes pin closure bookkeeping, not an expansion of the accepted 19-artifact snapshot.
CLOSURE_PINS = {
    'docs/00-program/PHASE-6-CLOSURE.md': '5de55c72a39faf28254552e11a1c243ed9d549d7b45a07d36df3de57ab72f50d',
    'docs/00-program/GATE-025-phase-6-closure.md': '3938fb1662f3540a313896cae36a11ad8abf0f227e437969b306d846c203d7b8',
    'contracts/phase6/phase6-closure-v1.json': '506b9afdffc7bedc5d04ed49f9b605ea1518a7d7a95bd96e9b695d9aae597d3d',
    'knowledge/validation/validate_phase6_closure.py': '3689e4bd321d6040bf386810c929299544d92be4e75ec2dd08fe6a9fcb44a5ea',
}


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def all_false(mapping):
    return bool(mapping) and all(v is False for v in mapping.values())


def closed_local_schema(schema):
    """Refuse remote resolution before invoking jsonschema; every object is closed."""
    for node in walk(schema):
        if not isinstance(node, dict):
            continue
        for key in ("$ref", "$dynamicRef", "$recursiveRef"):
            if key in node:
                ref = node[key]
                if not isinstance(ref, str) or not ref.startswith("#/"):
                    return False
                try:
                    value = schema
                    for part in ref[2:].split("/"):
                        value = value[part.replace("~1", "/").replace("~0", "~")]
                except (KeyError, TypeError):
                    return False
        if "patternProperties" in node or "unevaluatedProperties" in node:
            return False
        if node.get("type") == "object" or "properties" in node:
            if node.get("additionalProperties") is not False:
                return False
    return True


def schema_valid(contract, schema):
    if not closed_local_schema(schema):
        return False
    try:
        Draft202012Validator.check_schema(schema)
        return not list(Draft202012Validator(schema).iter_errors(contract))
    except (SchemaError, ValueError, TypeError):
        return False


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(cell(x) for x in row) + " |" for row in rows])


def projections(d):
    """Exact documentation projections prevent inventory/permission/claim text drift."""
    return {
        "principles": "\n".join(f"{i}. {p['requirement']}" for i, p in enumerate(d["principles"], 1)),
        "model": table(["UX concept", "Trace", "Meaning"], [
            (x["concept_id"], x["data_object"] if x["kind"] == "DATA_001" else "PRESENTATION_ONLY", x["meaning"])
            for x in d["mental_model"]]),
        "surfaces": table(["Stable surface ID", "Task / category", "Parent", "Ordinary eligible roles", "API operationIds", "Content permission", "Boundary"], [
            (s["surface_id"], s["title"] + " / " + s["category"], s["parent_surface_id"] or "—",
             ", ".join(s["allowed_roles"]), ", ".join(s["api_operations"]) or "NON_RESOURCE_SURFACE",
             s["content_permission_required"], s["scope_note"]) for s in d["surfaces"]]),
        "access": table(["Surface", "Operation", "Ordinary roles", "Resource authorization", "Content gate", "Break-glass roles", "Sensitivity", "Caller constraints"], [
            (s["surface_id"], o["operation_id"], ", ".join(o["roles"]), o["resource_authorization"],
             o["sensitive_content_permission"], ", ".join(o["break_glass_roles"]) or "—", o["sensitivity"],
             ", ".join(o["caller_constraints"]) or "—") for s in d["surfaces"] for o in s["operation_access"]]),
        "states": table(["Presentation state", "Accepted API error code(s)", "Meaning"], [
            (s["state_id"], ", ".join(s["api_error_codes"]) or "Presentation only", s["meaning"])
            for s in d["presentation_states"]]),
        "evaluation_error": table(["API error", "Authoritative Evaluation state", "Result availability", "Presentation state"], [
            (d["evaluation_error_presentation"]["error_code"], r["evaluation_state"],
             r["result_availability"], r["presentation_state"])
            for r in d["evaluation_error_presentation"]["rules"]]),
        "handoffs": table(["Work package", "Status", "Owner", "Detailed scope deferred"], [
            (h["work_package"], h["status"], h["owner"], "; ".join(h["scope"])) for h in d["handoffs"]]),
        "carryovers": table(["Item", "Status", "Owner", "Boundary"], [
            (k, v["status"], v["owner"], v["reason"]) for k, v in d["carryovers"].items()]),
        "decisions": table(["Unresolved decision", "Owner", "Status"], [
            (v["decision"], v["owner"], v["status"]) for v in d["open_design_decisions"]]),
    }


def load_inputs():
    snapshot = read_json("contracts/phase6/phase6-closure-v1.json")
    asset_paths = [x["path"] for x in snapshot["snapshot"]["artifacts"]] + list(CLOSURE_PINS)
    excluded = {".git", ".venv", "__pycache__", "node_modules"}
    runtime_files = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
                           if p.is_file() and not excluded.intersection(p.relative_to(ROOT).parts)
                           and (p.suffix.lower() in {".js", ".ts", ".tsx", ".jsx", ".css", ".scss", ".html", ".vue", ".svelte"}
                                or p.relative_to(ROOT).parts[0] == "apps"))
    return dict(contract=read_json(CONTRACT), schema=read_json(SCHEMA),
                doc=(ROOT / DOC).read_text() if (ROOT / DOC).exists() else "",
                gate=(ROOT / GATE).read_text() if (ROOT / GATE).exists() else "",
                api=read_json("contracts/api/api-v1.json"), openapi=read_json("contracts/api/openapi-v1.json"),
                integration=read_json("contracts/integrations/external-enrichment-v1.json"),
                operations=read_json("contracts/operations/operational-v1.json"),
                phase3=read_json("knowledge/schemas/detection/detection-result.schema.json"),
                data_doc=(ROOT / "docs/06-contracts/DATA-001-data-domain-lifecycle-contract.md").read_text(),
                engine=(ROOT / "knowledge/runtime/engine.py").read_text(), snapshot=snapshot,
                asset_hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in asset_paths},
                runtime_files=runtime_files)


def evaluation_error_rules_from_authority(ctx):
    """Derive lifecycle groups from API-001's accepted persistence-to-API mappings.

    API-001 §13.1 defines NOT_YET_AVAILABLE for queued/running and NOT_PRODUCED
    for failed executions. Cross-check those identifiers against the response
    fields and vocabularies; never derive lifecycle authority from UX constants.
    """
    api = ctx["api"]
    response = next(o for o in api["operations"] if o["operation_id"] == "getEvaluation")["response_schema"]
    fields = {f["name"]: f for f in api["schemas"][response]["fields"]}
    states = api["vocabularies"][fields["state"]["vocabulary"]]
    availability = api["vocabularies"][fields["result_availability"]["vocabulary"]]
    failures = api["vocabularies"]["api_evaluation_failure_class"]["maps_from"]
    mapping = states["maps_from"]
    if (response != "EvaluationResponse" or not fields["state"]["required"] or
            not fields["result_availability"]["required"] or
            mapping["persistence_vocabulary"] != failures["persistence_vocabulary"] or
            set(mapping["mapping"]) != set(failures["mapping"]) or
            not {"NOT_YET_AVAILABLE", "NOT_PRODUCED"} <= set(availability["values"])):
        raise ValueError("Evaluation response/lifecycle authority does not reconcile")
    state_map = mapping["mapping"]
    failed = {state_map[p] for p, failure_class in failures["mapping"].items() if failure_class is not None}
    # COMPLETED is the accepted durable-completion status (DATA-001 §5.9.1),
    # distinct from all three nonterminal persistence statuses and execution failure.
    completed = state_map["COMPLETED"]
    pending = {state_map[p] for p, failure_class in failures["mapping"].items()
               if failure_class is None and p != "COMPLETED"}
    if (not pending or not failed or pending & failed or completed in pending | failed or
            pending | failed | {completed} != set(states["values"])):
        raise ValueError("Evaluation lifecycle groups do not partition accepted states")
    oas = ctx["openapi"]["components"]["schemas"]
    for field, vocabulary in [("state", states), ("result_availability", availability)]:
        ref = oas[response]["properties"][field]["$ref"]
        if oas[ref.rsplit("/", 1)[1]]["enum"] != vocabulary["values"]:
            raise ValueError("Evaluation API/OpenAPI state vocabulary drift")
    return [dict(evaluation_state=s,
                 result_availability="NOT_YET_AVAILABLE" if s in pending else "NOT_PRODUCED",
                 presentation_state="ACTION_PENDING" if s in pending else "ACTION_FAILED")
            for s in states["values"] if s in pending | failed]


def evaluation_error_mapping_valid(ctx):
    """UXF-64: the error code alone never proves that execution is pending."""
    rule = ctx["contract"]["evaluation_error_presentation"]
    return (rule["error_code"] == "EVALUATION_NOT_COMPLETED" and
            rule["state_source_operation"] == "getEvaluation" and
            rule["state_source_schema"] == "EvaluationResponse" and
            rule["error_code_alone_sufficient"] is False and
            rule["unresolved_context"] == "DO_NOT_INFER_PENDING_OR_FAILURE" and
            rule["rules"] == evaluation_error_rules_from_authority(ctx))


def validate(ctx):
    d = ctx["contract"]
    results = []

    def check(n, description, test):
        try:
            ok = test() is True
        except (KeyError, TypeError, ValueError, IndexError, AttributeError):
            ok = False
        results.append(dict(check_id=f"UXF-{n:02d}", description=description, passed=ok))

    def surface(sid):
        return next((s for s in d["surfaces"] if s["surface_id"] == sid), {})

    def state(sid):
        return next((s for s in d["presentation_states"] if s["state_id"] == sid), {})

    def data_surfaces():
        return [s for s in d["surfaces"] if s["category"] != "NON_RESOURCE_SURFACE"]

    api = {o["operation_id"]: o for o in ctx["api"]["operations"]}
    openapi_ids = {o["operationId"] for p in ctx["openapi"]["paths"].values() for o in p.values()
                   if isinstance(o, dict) and "operationId" in o}
    roles = set(ctx["api"]["roles"])

    def freeze():
        pins = {a["path"]: a["sha256"] for a in ctx["snapshot"]["snapshot"]["artifacts"]}
        return len(pins) == 19 and all(ctx["asset_hashes"].get(p) == h for p, h in {**pins, **CLOSURE_PINS}.items())

    def carryover(item):
        accepted = next((x for x in ctx["snapshot"]["open_items"] if x["id"] == item), {})
        return (d["carryovers"][item]["status"] == accepted["state"] == "OPEN" and
                d["carryovers"][item]["owner"] == accepted["future_owner"] and
                ctx["operations"]["open_items"][item] == "OPEN")

    def no_new_roles():
        return set(d["accepted_roles"]) == roles and all(set(s["allowed_roles"]) <= roles and
            all(set(o["roles"]) <= roles and set(o["break_glass_roles"]) <= roles for o in s["operation_access"])
            for s in d["surfaces"])

    def domain_trace():
        matrix = ctx["data_doc"].split("## 6. Matrix A", 1)[1].split("## 7.", 1)[0]
        objects = set(re.findall(r"^\|\s*\d+\s*\|\s*`([^`]+)`", matrix, re.M))
        model = {x["concept_id"]: x for x in d["mental_model"]}
        return (len(model) == len(d["mental_model"]) and
                all(model.get(k, {}).get("data_object") == v for k, v in REQUIRED_OBJECTS.items()) and
                all(x["persisted_ux_entity"] is False and
                    ((x["kind"] == "DATA_001" and x["data_object"] in objects) or
                     (x["kind"] == "PRESENTATION_ONLY" and x["data_object"] is None)) for x in model.values()) and
                all(set(s["objects"]) <= set(model) for s in d["surfaces"]))

    def op_parity():
        for s in data_surfaces():
            expected = []
            for opid in s["api_operations"]:
                o = api[opid]
                expected.append({**{k: o[k] for k in ACCESS_KEYS}, "caller_constraints": o.get("caller_constraints", [])})
            expected_roles = [r for r in ctx["api"]["roles"] if any(r in api[x]["roles"] for x in s["api_operations"])]
            if s["operation_access"] != expected or s["allowed_roles"] != expected_roles:
                return False
            if s["sensitivity_behavior"]["classes"] != sorted({api[x]["sensitivity"] for x in s["api_operations"]}):
                return False
        return d["authorization"]["field_visibility"] == ctx["api"]["field_visibility"]

    def content_permissions():
        for s in data_surfaces():
            required = "FIELD_PERMISSION_REQUIRED" if any(api[x]["target_resource"] == "AnalystAdjudication" for x in s["api_operations"]) else (
                "CONTENT_PERMISSION_REQUIRED" if any(api[x]["sensitive_content_permission"] != "NONE" for x in s["api_operations"]) else "NONE")
            if s["content_permission_required"] != required or s["sensitivity_behavior"]["metadata_implies_content"] is not False:
                return False
        return d["authorization"]["content_separate"] is True

    def no_invented_keys(pattern):
        return not any(re.search(pattern, key, re.I) for node in walk(d) if isinstance(node, dict) for key in node)

    def graph():
        ss = {s["surface_id"]: s for s in d["surfaces"]}
        if set(ss) != REQUIRED_SURFACES or len(ss) != len(d["surfaces"]):
            return False
        if set(d["surface_categories"]) != {s["category"] for s in ss.values()}:
            return False
        for s in ss.values():
            seen = {s["surface_id"]}
            parent = s["parent_surface_id"]
            while parent is not None:
                if parent not in ss or parent in seen:
                    return False
                seen.add(parent)
                parent = ss[parent]["parent_surface_id"]
        n = d["navigation"]
        return (n["basis"] == "USER_TASK" and n["authorization_inherited_from_parent"] is False and
                n["ordinary_users_see_admin_navigation"] is False and
                all(e["surface_id"] in ss for e in n["entries"]) and
                all(s["api_operations"] == [] and s["operation_access"] == [] and s["data_source"] == "NONE"
                    for s in ss.values() if s["category"] == "NON_RESOURCE_SURFACE"))

    def documentary_parity():
        for name, value in projections(d).items():
            block = f"<!-- UXF:{name}:BEGIN -->\n{value}\n<!-- UXF:{name}:END -->"
            if ctx["doc"].count(block) != 1:
                return False
        return len(d["principles"]) == 12 and len({p["principle_id"] for p in d["principles"]}) == 12

    check(1, "UX-001 approved after review; remote CI and merge pending", lambda: f"| Document ID | UX-001 |" in ctx["doc"] and f"| Status | {STATUS} |" in ctx["doc"])
    check(2, "GATE-026 approved after review; remote CI and merge pending", lambda: "| Document ID | GATE-026 |" in ctx["gate"] and f"| Status | {STATUS} |" in ctx["gate"])
    check(3, "Machine contract schema-valid", lambda: schema_valid(d, ctx["schema"]))
    check(4, "Closed schema with resolvable local references only", lambda: closed_local_schema(ctx["schema"]))
    check(5, "Exact requested baseline and work-package identity", lambda: d["baseline"] == BASELINE and BASELINE in ctx["doc"] and BASELINE in ctx["gate"] and d["status"] == STATUS and d["work_package"] == "P7-WP1" and d["contract_id"] == "UX-001" and d["phase"] == "Phase 7 — UX, Evidence & Reporting Design")
    check(6, "Accepted Phase-6 snapshot and closure bookkeeping unchanged", freeze)
    check(7, "Role vocabulary matches API authority", lambda: d["accepted_roles"] == ctx["api"]["roles"])
    check(8, "No new RBAC role", no_new_roles)
    check(9, "Persona cannot grant authorization", lambda: all(p["classification"] == "UX PERSONA ONLY" and p["authorization_role"] is False and p["name"] not in roles for p in d["personas"]) and not {p["name"].upper() for p in d["personas"]}.intersection(r for s in d["surfaces"] for r in s["allowed_roles"]))
    check(10, "Domain objects trace to DATA-001 or PRESENTATION_ONLY", domain_trace)
    check(11, "DetectionResult immutable", lambda: d["semantics"]["result_immutable"] is True)
    check(12, "Adjudication separate from system result", lambda: d["semantics"]["adjudication_separate"] is True and d["semantics"]["adjudication_overwrites_result"] is False)
    check(13, "Replay means exact historical verification", lambda: d["semantics"]["replay"]["meaning"] == "EXACT_HISTORICAL_VERIFICATION" and all(d["semantics"]["replay"][k] is False for k in ["calls_ai", "calls_provider", "uses_latest", "creates_evaluation", "replaces_result"]))
    check(14, "Re-analysis creates new evaluation and input, preserves history", lambda: d["semantics"]["reanalysis"] == dict(meaning="NEW_EVALUATION_CURRENT_GOVERNED_CONDITIONS", creates_new_evaluation=True, creates_new_governed_artifact=True, overwrites_history=False))
    check(15, "Operations exist in API and OpenAPI, public only", lambda: all(op in api and op in openapi_ids and api[op]["internal"] is False for s in data_surfaces() for op in s["api_operations"]))
    check(16, "Every data surface has API traceability", lambda: bool(data_surfaces()) and all(bool(s["api_operations"]) for s in data_surfaces()))
    check(17, "No direct database-table UI source", lambda: all(s["data_source"] == "API_ONLY" for s in data_surfaces()) and no_invented_keys(r"^(?:db_table|sql_query|database_table)$"))
    check(18, "Presentation concepts explicitly declared", lambda: {x["concept_id"] for x in d["mental_model"] if x["kind"] == "PRESENTATION_ONLY"} == PRESENTATION_CONCEPTS and all(s["kind"] == "PRESENTATION_ONLY" for s in d["presentation_states"]))
    check(19, "Resource authorization; backend authority, never role alone", lambda: all(s["resource_authorization_required"] is True and s["role_alone_sufficient"] is False for s in data_surfaces()) and all(d["authorization"][k] is True for k in ["backend_authoritative", "deny_by_default", "role_and_resource"]) and d["authorization"]["hidden_ui_security_control"] is False)
    check(20, "Separate content permission per operation and field", content_permissions)
    check(21, "Administrator has no role-only evidence access", lambda: d["authorization"]["administrator_content_by_role"] is False and "ADMINISTRATOR" not in surface("UX-EVIDENCE-CONTENT")["allowed_roles"] and d["authorization"]["field_visibility"]["raw_evidence_content"]["ADMINISTRATOR"] == "BREAK_GLASS_ONLY")
    check(22, "Analyst cannot create break-glass", lambda: d["authorization"]["analyst_creates_break_glass"] is False and surface("UX-BREAK-GLASS")["allowed_roles"] == ["ADMINISTRATOR"] and all(o["roles"] == ["ADMINISTRATOR"] for o in surface("UX-BREAK-GLASS")["operation_access"]))
    check(23, "No self-assignment including dual-role caller", lambda: d["authorization"]["self_assignment"] == "ASSIGNEE_NOT_CALLER" and d["authorization"]["dual_role_exemption"] is False and surface("UX-ASSIGNMENT")["operation_access"][0]["caller_constraints"] == ["ASSIGNEE_NOT_CALLER"])
    check(24, "C4 rationale permission and content-free placeholders", lambda: d["authorization"]["c4_rationale_permission"] == "ASSIGNED_ANALYST_WITH_CONTENT_PERMISSION" and surface("UX-ADJUDICATION")["content_permission_required"] == "FIELD_PERMISSION_REQUIRED" and all(s["sensitivity_behavior"]["c4_default_visible"] is False and s["sensitivity_behavior"]["placeholder_content_free"] is True for s in d["surfaces"]))
    check(25, "No DetectionResult edit or override action", lambda: d["semantics"]["result_actions"] == ["READ"] and surface("UX-RESULT")["api_operations"] == ["getDetectionResult"])
    check(26, "No invented scam probability", lambda: d["result_guardrails"]["probability_allowed"] is False and no_invented_keys(r"(?:scam_probability|fraud_probability|confidence_percentage|probability_gauge)"))
    check(27, "No arbitrary trust/scam/safety score", lambda: d["result_guardrails"]["arbitrary_score_allowed"] is False and no_invented_keys(r"^(?:trust_score|scam_score|safety_score|reputation_score|risk_score)$"))
    for number, classification in enumerate(["NO_SCAM_PATTERN", "INSUFFICIENT_EVIDENCE", "UNSUPPORTED", "ERROR"], 28):
        check(number, f"{classification} never means SAFE", lambda c=classification: d["result_guardrails"]["classification_meanings"][c] == CLASSIFICATION_MEANINGS[c])
    for number, outcome, meaning in [(32, "CLEAN", "PROVIDER_ASSERTION_NOT_TRUSTLENS_SAFETY"), (33, "NOT_FOUND", "NO_PROVIDER_ENTRY_NOT_SAFETY"), (34, "UNAVAILABLE", "PROVIDER_UNAVAILABLE_NOT_SAFETY")]:
        check(number, f"Provider {outcome} never means TrustLens safe", lambda o=outcome, m=meaning: d["enrichment_guardrails"]["outcome_meanings"][o] == m)
    check(35, "Enrichment remains supporting/advisory", lambda: d["enrichment_guardrails"]["authority"] == "SUPPORTING_ADVISORY" and d["enrichment_guardrails"]["primary_verdict"] is False and d["enrichment_guardrails"]["consumed_in_governed_artifact"] is False and ctx["integration"]["decision_boundary"]["consumed_in_governed_artifact"] is False and d["enrichment_guardrails"]["provider_attribution_required"] is True)
    check(36, "AI cannot directly set, override or bypass verdict", lambda: all(d["ai_guardrails"][k] is False for k in ["direct_verdict", "direct_override", "bypass_rules"]))
    check(37, "Indirect governed AI influence represented accurately", lambda: d["ai_guardrails"]["indirect_influence"] == "VALIDATED_GOVERNED_OBSERVATIONS_MAY_AFFECT_DETERMINISTIC_OUTPUT" and d["ai_guardrails"]["never_influences_result"] is False and d["ai_guardrails"]["default_enabled"] is False)
    check(38, "Empty cannot imply safety", lambda: state("EMPTY")["implies_safe"] is False and state("EMPTY")["meaning"] == "Nothing is available for this surface/query; no safety inference.")
    check(39, "Loading and pending cannot imply safety/completion", lambda: all(state(k)["implies_safe"] is False for k in ["LOADING", "ACTION_PENDING"]) and state("LOADING")["meaning"] == "Waiting for an authorized response; no provisional verdict." and state("ACTION_PENDING")["meaning"] == "Accepted or executing work; no completion claim." and d["interaction"]["asynchronous"]["pending_implies_safe"] is False and d["interaction"]["asynchronous"]["accepted_is_complete"] is False)
    check(40, "Governed removal distinct from empty/not-found", lambda: state("REMOVED_UNDER_GOVERNANCE")["api_error_codes"] == ["REMOVED_UNDER_GOVERNANCE"] and state("NOT_FOUND_OR_NOT_VISIBLE")["api_error_codes"] == ["NOT_FOUND"])
    check(41, "Replay unavailable never silently uses latest", lambda: state("REPLAY_UNAVAILABLE")["api_error_codes"] == ["REPLAY_UNAVAILABLE"] and d["semantics"]["replay"]["missing_material"] == "REPLAY_UNAVAILABLE" and d["semantics"]["replay"]["uses_latest"] is False)
    check(42, "Report regeneration unavailable, no reconstruction/latest", lambda: state("REPORT_REGENERATION_UNAVAILABLE")["api_error_codes"] == ["REPORT_REGENERATION_UNAVAILABLE"] and d["semantics"]["report"]["missing_material"] == "REPORT_REGENERATION_UNAVAILABLE" and d["semantics"]["report"]["uses_latest"] is False and d["semantics"]["report"]["reconstructs_deleted_content"] is False)
    check(43, "Meaning not conveyed by colour alone", lambda: d["accessibility"]["colour_only_meaning"] is False)
    check(44, "Text status equivalent required", lambda: d["accessibility"]["textual_status_equivalents"] is True)
    check(45, "Keyboard, focus and semantic accessibility baseline", lambda: all(d["accessibility"][k] is True for k in ["keyboard_operable", "logical_focus_order", "visible_focus", "semantic_headings_regions", "error_summary_field_association", "screen_reader_control_labels", "dynamic_announcements"]) and d["accessibility"]["mandatory_animation"] is False)
    check(46, "No accessibility certification/compliance claim", lambda: d["accessibility"]["certification_claim"] is False and d["claims"]["accessibility_compliant"] is False)
    check(47, "No tenancy UX or tenancy authority", lambda: all_false(d["tenancy"]) and no_invented_keys(r"^(tenant_id|tenant_selector|workspace_tenancy|multi_tenant_navigation)$"))
    check(48, "G-09 remains OPEN with accepted owner", lambda: carryover("G-09"))
    check(49, "OI-05 remains OPEN with accepted owner", lambda: carryover("OI-05"))
    check(50, "ASM-002 remains unconfirmed/provisional", lambda: d["carryovers"]["ASM-002"]["status"] == "UNCONFIRMED / PROVISIONAL")
    check(51, "No numeric retention invented", lambda: d["retention"] == dict(duration="NOT YET SPECIFIED", numeric_duration_invented=False) and no_invented_keys(r"retention_(days|hours|months|years|seconds)$"))
    check(52, "Owned handoffs for all later Phase-7 WPs", lambda: [h["work_package"] for h in d["handoffs"]] == [f"P7-WP{i}" for i in range(2, 8)] and all(h["owner"] and h["scope"] for h in d["handoffs"]))
    check(53, "No later WP started or falsely complete", lambda: all(h["status"] == "NOT STARTED" for h in d["handoffs"]) and d["claims"]["later_wp_complete"] is False)
    check(54, "No runtime frontend implementation or claim", lambda: ctx["runtime_files"] == [] and d["claims"]["frontend_implemented"] is False and d["claims"]["api_implemented"] is False)
    check(55, "No production-readiness claim", lambda: d["claims"]["production_ready"] is False)
    check(56, "ENGINE_VERSION remains 1.0.0", lambda: d["engine_version"] == "1.0.0" and re.search(r'^ENGINE_VERSION = "1\.0\.0"$', ctx["engine"], re.M) is not None)
    check(57, "Stable surface graph and task navigation, no inherited authority", graph)
    check(58, "Per-operation roles/resource/content/sensitivity match API", op_parity)
    check(59, "Privileged/destructive, concurrency, retry and async foundations", lambda: all(v is True for k, v in d["authorization"]["break_glass"].items() if k not in ["review_constraint", "silent_elevation"]) and d["authorization"]["break_glass"]["review_constraint"] == "REVIEWER_NOT_GRANTEE" and d["authorization"]["break_glass"]["silent_elevation"] is False and d["interaction"] == dict(destructive=dict(explicit_action=True, affected_resource_visible=True, consequence_visible=True, confirmation_where_appropriate=True, server_confirmed_outcome=True, optimistic_completion=False), concurrency=dict(stale_visible=True, silent_overwrite=False, missing_precondition_distinct=True), idempotency=dict(user_concept="SAFE_RETRY", key_exposed=False, key_is_authorization=False), asynchronous=dict(accepted_is_complete=False, pending_implies_safe=False, poll_accepted_resources=True, invented_progress_percentage=False)))
    check(60, "No prohibited information exposure or invented enrichment fields", lambda: set(d["exposure"]) == EXPOSURES and all_false(d["exposure"]) and d["enrichment_guardrails"]["api_view_fields"] == [f["name"] for f in ctx["api"]["schemas"]["EnrichmentView"]["fields"]] and d["enrichment_guardrails"]["attribution_fields"] == ["provider_category", "observed_at"])
    check(61, "Human inventory/access/state/handoff projections match machine", documentary_parity)
    check(62, "No detection-effectiveness claim", lambda: d["claims"]["detection_effectiveness"] is False)
    check(63, "Phase-6 four-schema snapshot LOW carried unchanged", lambda: d["carryovers"]["P6-WP7-LOW-1"]["status"] == "OPEN / NON-BLOCKING" and d["carryovers"]["P6-WP7-LOW-1"]["owner"] == "next governed Phase-6 snapshot revision / Programme governance" and len(ctx["snapshot"]["snapshot"]["artifacts"]) == 19)
    check(64, "Distinct API errors and authoritative Evaluation pending/failure mapping", lambda: {s["state_id"]: s["api_error_codes"] for s in d["presentation_states"]} == STATE_CODES and all(s["implies_safe"] is False for s in d["presentation_states"]) and evaluation_error_mapping_valid(ctx))
    check(65, "Accepted result axes, provenance, responsive and scope boundaries", lambda: d["result_guardrails"]["authority"] == "PHASE_3" and d["result_guardrails"]["categorical_axes"] == {k: ctx["phase3"]["properties"][k]["enum"] for k in ["classification", "decision_severity", "matched_evidence_strength", "risk_level", "detection_confidence"]} and d["result_guardrails"]["classification_meanings"] == CLASSIFICATION_MEANINGS and set(d["result_guardrails"]["explanation_requirements"]) == {"OBSERVATIONS", "GOVERNED_RULE_CONTRIBUTIONS", "NEGATIVE_MITIGATING_INDICATORS", "UNCERTAINTY", "PROVENANCE", "NEXT_ACTIONS"} and set(d["result_guardrails"]["provenance_distinctions"]) == {"USER_PROVIDED_MATERIAL", "RETAINED_EVIDENCE", "SYSTEM_DERIVED_OBSERVATIONS", "AI_DERIVED_GOVERNED_OBSERVATIONS", "EXTERNAL_PROVIDER_ASSERTIONS", "DETERMINISTIC_RESULT", "HUMAN_ADJUDICATION"} and d["responsive"] == dict(capable=True, breakpoint_values="NOT YET SPECIFIED", permission_parity=True, narrow_layout_exposes_hidden_content=False) and d["unsupported_language"]["benign_inference"] is False and d["unsupported_language"]["classification"] == "UNSUPPORTED" and all(d["semantics"][k] is False for k in ["governed_input_editable", "governed_input_equals_raw_evidence", "case_aggregate_verdict"]) and d["semantics"]["report"]["pinned_sources"] is True and d["semantics"]["report"]["automatic_transmission"] is False and d["claims"]["independently_reviewed"] is True and d["claims"]["approved"] is True)
    assert len(results) == CHECK_COUNT
    return results


def mutate(ctx, fixture):
    """Small strict JSON-pointer mutation dialect; fixtures cannot run code or write files."""
    result = copy.deepcopy(ctx)
    target = fixture["target"]
    if target not in {"contract", "schema", "engine", "doc", "gate", "asset_hashes", "runtime_files"}:
        raise ValueError("unknown mutation target")
    if fixture["op"] == "replace_text":
        original = result[target]
        if not isinstance(original, str) or fixture["old"] not in original:
            raise ValueError("text mutation does not apply")
        result[target] = original.replace(fixture["old"], fixture["value"], 1)
    else:
        parts = fixture["path"].split("/")[1:]
        if not parts:
            raise ValueError("root replacement not permitted")
        parent = result[target]
        for part in parts[:-1]:
            part = part.replace("~1", "/").replace("~0", "~")
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        key = parts[-1].replace("~1", "/").replace("~0", "~")
        if isinstance(parent, list):
            key = int(key)
        if fixture["op"] == "remove":
            del parent[key]
        elif fixture["op"] == "replace":
            if isinstance(parent, dict) and key not in parent:
                raise ValueError("replace key missing")
            parent[key] = fixture["value"]
        elif fixture["op"] == "add":
            if not isinstance(parent, dict) or key in parent:
                raise ValueError("add requires new object key")
            parent[key] = fixture["value"]
        else:
            raise ValueError("unknown mutation operation")
    if result == ctx:
        raise ValueError("vacuous mutation")
    return result


def main():
    quiet = "--quiet" in sys.argv
    try:
        ctx = load_inputs()
        results = validate(ctx)
        failed = [r for r in results if not r["passed"]]
        if not quiet:
            for r in results:
                print(f"{'PASS' if r['passed'] else 'FAIL'} {r['check_id']} {r['description']}")
        if failed:
            print(f"UX FOUNDATION: FAIL — {len(failed)}/{CHECK_COUNT} checks failed")
            return 1
        fixtures = read_json(FIXTURES)
        if set(fixtures) != {"fixture_version", "mutations"} or fixtures["fixture_version"] != "1.0":
            raise ValueError("invalid fixture document")
        ids = set()
        mutation_failures = []
        for fixture in fixtures["mutations"]:
            required = {"id", "description", "expected_check", "target", "op"}
            required |= {"old", "value"} if fixture["op"] == "replace_text" else {"path"}
            if fixture["op"] in {"add", "replace"}:
                required.add("value")
            if set(fixture) != required or fixture["id"] in ids:
                raise ValueError("invalid/duplicate mutation")
            ids.add(fixture["id"])
            outcomes = validate(mutate(ctx, fixture))
            rejected = {r["check_id"] for r in outcomes if not r["passed"]}
            if fixture["expected_check"] not in rejected:
                mutation_failures.append(fixture["id"])
                print(f"FAIL {fixture['id']} expected {fixture['expected_check']}; got {sorted(rejected)}")
        if not ids or mutation_failures:
            print(f"UX FOUNDATION: FAIL — mutation coverage {len(ids) - len(mutation_failures)}/{len(ids)}")
            return 1
        print(f"UX FOUNDATION: PASS — {CHECK_COUNT}/{CHECK_COUNT} checks; {len(ids)}/{len(ids)} negative mutations rejected by intended checks")
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"UX FOUNDATION: FAIL — invalid or missing input: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
