"""P7-WP6 deterministic offline accessibility, responsive, unsupported-language and enrichment UX checks (UXA-01..UXA-34).

Builder verification, not independent review, assistive-technology testing or a conformance assessment. Reads the
accepted authorities (UX-001 foundation, the closed UX-002..UX-005 packages, INT-001, ADR-0014 and the closed Phase-6 API
catalog and OpenAPI) without editing them.

External enrichment is advisory supporting context: the enrichment interpretation table is re-derived independently from
INT-001's outcome mapping, so a (status, reputation_result) pair is presented as a specific integration outcome only when
exactly one outcome can produce it. In the accepted EnrichmentView, NOT_FOUND shares SUCCEEDED/UNKNOWN with a found entry of
unknown reputation, and UNAVAILABLE shares FAILED/NOT_EVALUATED with an invalid response, so those distinctions are never
claimed. Provider CLEAN is a provider assertion, never TrustLens safety. Detection scope is English only (ADR-0014): an
unsupported language is never benign and reaches no conclusion. Every UX-001 accessibility commitment is covered by a
pattern and no conformance is claimed; permissions, controls and redaction are identical in every layout.

Lifecycle is fail-closed without parsing Markdown review prose: review records, approval and merge evidence count only
when they equal the records pinned in this module (VERIFIED_*) by a governed bookkeeping step. Protected copy is bound to
a closed set of governed messages and to narrow semantic invariants. Governed projections must appear exactly once and
outside fences, and no visible GFM table outside them may act as a policy table.

Negative fixtures inject one change (or a synchronized sequence of steps) into an in-memory input copy and must fail
their named UXA check, not merely any check; positive controls must pass every check. No network, subprocess or frontend
is used.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "7f3c2899dae693d3b497faa3a68f691890488d2d"   # P7-WP5 delivery merge (PR #41); the P7-WP5 closure ships alongside
CONTRACT = "contracts/ux/ux-accessibility-v1.json"
SCHEMA = "contracts/ux/ux-accessibility-contract.schema.json"
FIXTURES = "contracts/ux/fixtures/accessibility-negative-mutations.json"
DOC = "docs/07-ux/UX-006-accessibility-responsive-enrichment.md"
GATE = "docs/00-program/GATE-031-phase-7-accessibility-enrichment.md"
CHECK_COUNT = 34
STATUS_BY_STATE = {
    "CANDIDATE": "P7-WP6 ACCESSIBILITY, RESPONSIVE AND ENRICHMENT UX CANDIDATE",
    "APPROVED": "P7-WP6 ACCESSIBILITY, RESPONSIVE AND ENRICHMENT UX APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING",
    "CLOSED": "P7-WP6 ACCESSIBILITY, RESPONSIVE AND ENRICHMENT UX CLOSED",
}
VERIFIED_REVIEW_HISTORY: list = [
    {"round": 1, "kind": "INITIAL_INDEPENDENT_REVIEW", "decision": "REQUEST_CHANGES",
     "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 2, "LOW": 0, "INFO": 0}, "reviewer_role": "Independent reviewer",
     "evidence_source": "Independent review result supplied to the builder by the programme", "record_reference": "GATE-031 §7"},
    {"round": 2, "kind": "TARGETED_INDEPENDENT_REREVIEW", "decision": "APPROVE",
     "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}, "reviewer_role": "Independent reviewer",
     "evidence_source": "Independent review result supplied to the builder by the programme", "record_reference": "GATE-031 §7"},
]
VERIFIED_APPROVAL = {"round": 2, "decision": "APPROVE", "record_reference": "GATE-031 §7", "reviewer_role": "Independent reviewer"}
VERIFIED_MERGE_EVIDENCE = {"repository": "nishanth-cryptos/TrustLens", "pr_number": 42,
                           "pr_head_commit": "b5dd2c776f17564d01f45ae6c65cef060d560761",
                           "merge_commit": "324fc320c47498a42f68c6bac941cc4a5dde9b39",
                           "base_commit": "7f3c2899dae693d3b497faa3a68f691890488d2d",
                           "remote_ci": {"workflow": "knowledge-validation",
                                         "checks": ["Knowledge validation suite", "Quality-gate self-test (gate must bite)"],
                                         "conclusion": "success", "pr_head_run_id": 38238792863, "merge_commit_run_id": 38244422412},
                           "verification": "INDEPENDENT_PROGRAMME_VERIFICATION", "verification_reference": "GATE-031 §8"}
INDEPENDENT_REVIEW_KINDS = {"INITIAL_INDEPENDENT_REVIEW", "TARGETED_INDEPENDENT_REREVIEW", "FINAL_INDEPENDENT_REVIEW"}
INDEPENDENT_REVIEWER_ROLES = {"Independent reviewer"}
PERMITTED_EVIDENCE_SOURCES = {"Independent review result supplied to the builder by the programme"}
REVIEW_RECORD = "GATE-031 §7"
REVIEW_HEADING = "## 7. Independent review record"
FINDING_DISPOSITIONS = {"CORRECTED_PENDING_TARGETED_REREVIEW", "OPEN_CARRIED", "OPEN_INFORMATIONAL", "CLOSED_BY_REREVIEW"}

# Predecessor freeze, including the P7-WP5 closure that ships with this package (closure bookkeeping, not a snapshot expansion).
PREDECESSOR_PINS = {
    'contracts/ux/ux-foundation-v1.json': '2a1a058028f4cf50597dc787aa4f18fa0f8364752818474ccb9cfa5a43aa7430',
    'contracts/ux/ux-intake-v1.json': 'be4a2933a1153549233813e4bf16a349aff578f66f29dd7db58425241706a83a',
    'contracts/ux/ux-result-v1.json': 'c8f63807165bbd1983f31d459d1281e46b77ff917ffd728c5cec034435951862',
    'contracts/ux/ux-review-v1.json': '86e029b42144191cfbaff536c74c4db5cc8ae173d38e2bd9eedf9692b3e8421a',
    'contracts/ux/ux-reporting-v1.json': '4034c252ef0e6143105c518fdd9bf724ef3cc93f022ea3335b87ab9338a75f5d',
    'docs/07-ux/UX-001-experience-foundation-information-architecture.md': '622f1a1a59dd5658e3f6555d164437d0b01c7c84bf3a5f8bbe0d2c5728b750aa',
    'docs/07-ux/UX-002-submission-evidence-intake.md': '6db2f57750593c9dd9e757fcf6e3c9a261d056bfdc3ff52a4fbdd14e74443453',
    'docs/07-ux/UX-003-result-presentation.md': 'c1fc84afbffae3e31e14b2f41b8373e62c5afa6e14eb2954313acfd86c39e9df',
    'docs/07-ux/UX-004-evidence-review-security.md': '04f4642a47abb6c82ae798159e74e34ea251f0bb571bb7968fc1a3aa3a0c3247',
    'docs/07-ux/UX-005-reporting-historical-workflows.md': 'ed5d30527753938e049778ad60c5c84f481758905f2ea9b914cb9a85654d24d0',
    'docs/00-program/GATE-029-phase-7-evidence-review-security.md': 'fb2d51498eafcd5cb2dbc4bf3071a50ce60720e575b4fd21b5175da5d32879f4',
    'docs/00-program/GATE-030-phase-7-reporting-historical-workflows.md': '6632e1fa77c0886e637420ad44d811413d95390dc5d9a7a4719bedb077c96628',
    'adr/ADR-0014-language-and-script-strategy.md': 'e0c5489c1342459e580346854503df1abf68d81a4b6813f1a310911ae3989a18',
}
OP_KEYS = ("method", "path", "roles", "resource_authorization", "sensitive_content_permission", "break_glass_roles",
           "request_schema", "response_schema", "success_status", "mode", "idempotency", "audit", "audit_event", "sensitivity",
           "concurrency")
ROLES = ["USER", "ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR"]
CASE_RELATIONSHIP = {"USER": "OWNER", "ANALYST": "ASSIGNED_ANALYST"}
CASE_SCOPED = {"CASE_ACCESS", "CASE_DERIVED_CONTENT"}
API_MASKING_TEXT = "If the caller has **no** access to a case's scope, every case-scoped"
DETECTION_SCOPE = {"languages": ["en"], "scripts": ["Latn"], "source": "ADR-0014 / DEC-008"}
ADR_SCOPE_TEXT = "English only (`en` / `Latn`)"
PROVIDER_ASSERTIONS = {"MALICIOUS", "SUSPICIOUS", "CLEAN"}
NOT_LOOKED_UP = ("NOT_EVALUATED", "NOT_EVALUATED")
# Independent presentation keys per accepted (status, reputation_result) pair; any other pair is an unrecognized record.
PRESENTATION_BY_PAIR = {
    ("SUCCEEDED", "MALICIOUS"): "PROVIDER_ADVERSE_ASSERTION", ("SUCCEEDED", "SUSPICIOUS"): "PROVIDER_CAUTION_ASSERTION",
    ("SUCCEEDED", "CLEAN"): "PROVIDER_CLEAN_ASSERTION", ("SUCCEEDED", "UNKNOWN"): "NO_PROVIDER_ASSERTION",
    ("TIMED_OUT", "NOT_EVALUATED"): "LOOKUP_UNAVAILABLE", ("FAILED", "NOT_EVALUATED"): "LOOKUP_DID_NOT_COMPLETE",
    ("REJECTED", "NOT_EVALUATED"): "LOOKUP_NOT_PERMITTED", NOT_LOOKED_UP: "NOT_LOOKED_UP",
}
SUPPORT_PRESENTATION = {"SUPPORTED": ("SUPPORTED_INPUT", True), "PARTIALLY_SUPPORTED": ("PARTIALLY_SUPPORTED_INPUT", True),
                        "UNSUPPORTED": ("UNSUPPORTED_INPUT", False), "INSUFFICIENT_INFORMATION": ("INSUFFICIENT_INFORMATION_INPUT", False),
                        "ERROR": ("ERROR_INPUT", False)}
ANNOUNCEMENT_POLICY = {"ENRICHMENT_PROVIDER_ASSERTION": {"provider_category", "reputation_result", "observed_at"},
                       "ENRICHMENT_NO_ASSERTION": {"provider_category"}, "UNSUPPORTED_LANGUAGE": set(), "CONTENT_WITHHELD": set()}
PROTECTED_FIELDS = {"rationale", "reason", "reason_note", "review_note", "evidence_content", "content", "raw_provider_body"}
RECOVERY_RETRYABILITY = {"RETRY_SAME_REQUEST": "RETRYABLE", "WAIT_THEN_RETRY_SAME_REQUEST": "RETRYABLE",
                         "CORRECT_REQUEST": "RETRY_WITH_CHANGES", "REAUTHENTICATE_THEN_RETRY": "RETRY_WITH_CHANGES",
                         "STOP_NO_RETRY": "NOT_RETRYABLE"}
DEFERRED_OWNERS = {"Phase 9", "Phase 10"}
REQUIRED_DECISIONS = ("Provider identity", "Breakpoint values", "lookup outcome", "freshness", "beyond English", "Interface language",
                      "conformance testing")
UX001_CARRIED = ("Provider identity and detailed outcome attribution beyond current EnrichmentView", "Breakpoints and responsive behavior")
GUARDRAILS = {"provider_clean_as_safe", "not_found_claimed_without_api_field", "unavailable_as_clean", "enrichment_changes_result",
              "invented_provider_identity", "invented_lookup_outcome_field", "invented_supported_language", "client_language_detection",
              "conformance_claim", "device_specific_permissions", "hidden_ui_security_control", "invented_breakpoints"}
GOVERNED_TEXT = {
    "enrichment.advisory_notice": "External lookups are advisory. They come from outside TrustLens and do not change the TrustLens result.",
    "enrichment.observed_at_absent_text": "Observation time not provided.",
    "enrichment.unrecognized_pair.label": "Unrecognized lookup record",
    "enrichment.unrecognized_pair.meaning": "This lookup record could not be interpreted and is not shown as a provider assertion.",
    "enrichment.interpretation.PROVIDER_ADVERSE_ASSERTION.label": "Provider reports malicious",
    "enrichment.interpretation.PROVIDER_ADVERSE_ASSERTION.meaning": "An external provider reported this indicator as malicious at the time shown. This is the provider's assertion, not a TrustLens finding.",
    "enrichment.interpretation.PROVIDER_CAUTION_ASSERTION.label": "Provider reports suspicious",
    "enrichment.interpretation.PROVIDER_CAUTION_ASSERTION.meaning": "An external provider reported this indicator as suspicious at the time shown. This is the provider's assertion, not a TrustLens finding.",
    "enrichment.interpretation.PROVIDER_CLEAN_ASSERTION.label": "Provider reports no adverse reputation",
    "enrichment.interpretation.PROVIDER_CLEAN_ASSERTION.meaning": "An external provider reported no adverse reputation for this indicator at the time shown. This is the provider's assertion only, not a TrustLens judgement.",
    "enrichment.interpretation.NO_PROVIDER_ASSERTION.label": "No provider assertion",
    "enrichment.interpretation.NO_PROVIDER_ASSERTION.meaning": "The lookup finished without a reputation from the provider. Whether the provider had an entry cannot be told from this record.",
    "enrichment.interpretation.LOOKUP_UNAVAILABLE.label": "Lookup timed out",
    "enrichment.interpretation.LOOKUP_UNAVAILABLE.meaning": "The provider did not answer in time, so there is no provider assertion.",
    "enrichment.interpretation.LOOKUP_DID_NOT_COMPLETE.label": "Lookup did not complete",
    "enrichment.interpretation.LOOKUP_DID_NOT_COMPLETE.meaning": "The lookup failed or its response could not be used, so there is no provider assertion.",
    "enrichment.interpretation.LOOKUP_NOT_PERMITTED.label": "Lookup not permitted",
    "enrichment.interpretation.LOOKUP_NOT_PERMITTED.meaning": "TrustLens policy did not allow this lookup, so there is no provider assertion.",
    "enrichment.interpretation.NOT_LOOKED_UP.label": "Not looked up",
    "enrichment.interpretation.NOT_LOOKED_UP.meaning": "No external lookup was made for this indicator.",
    "unsupported_language.explanation": "This content is in a language TrustLens does not evaluate yet, so no conclusion was reached and none is implied.",
    "accessibility.announcements.ENRICHMENT_PROVIDER_ASSERTION.text": "External lookup: provider assertion available.",
    "accessibility.announcements.ENRICHMENT_NO_ASSERTION.text": "External lookup: no provider assertion.",
    "accessibility.announcements.UNSUPPORTED_LANGUAGE.text": "Unsupported language. No conclusion was reached.",
    "accessibility.announcements.CONTENT_WITHHELD.text": "Some content is not shown.",
}
NOT_FOUND_CLAIM = re.compile(r"\b(not found|no entry|no record|not listed|unlisted|unknown to the provider)\b", re.I)
SPECIFIC_UNAVAILABLE = re.compile(r"\b(outage|provider (is|was) (down|unavailable|offline))\b", re.I)
CLEAN_CLAIM = re.compile(r"\b(clean|no threat|nothing (was )?found|no issues?|all clear)\b", re.I)
VERDICT_WORDS = re.compile(r"\b(scam pattern|no scam|scam detected|detected|trustlens (verdict|finding) is)\b", re.I)
CONFORMANCE_CLAIM = re.compile(r"\b(WCAG|conform\w*|compliant|compliance|certif\w*|AAA?|section 508|EN 301 549)\b")
FORBIDDEN_DISPLAY = re.compile(r"\b(safe|safely|safety|harmless|benign|legitimate|guarantee[sd]?|certified|verified|cleared|"
                               r"innocent|guilty|criminal|fraudster|probability|percent(age)?|score)\b", re.I)
PREMATURE = {
    re.compile(r"P7-WP6 (is |was |has been |has )?(approved|accepted)", re.I): {"APPROVED", "CLOSED"},
    re.compile(r"P7-WP6 (is |was |has been |has )?(closed|merged)", re.I): {"CLOSED"},
    re.compile(r"P7-WP6 (is |was |has been |has )?(implemented|complete)", re.I): set(),
    re.compile(r"P7-WP7 (is |was |has been |has )?(started|in progress|complete)", re.I): set(),
}
NEGATION = re.compile(r"\b(not|no|never|until|only after|cannot)\b", re.I)
EXPOSURES = {"raw_provider_bodies", "credentials_secrets", "connector_topology", "internal_hosts_ips",
             "evidence_store_locators", "raw_evidence_without_permission", "c4_without_permission",
             "execution_fence_tokens", "idempotency_key_material", "audit_equals_activity"}
DOC_PROJECTIONS = ["operations", "errors", "interpretation", "support", "patterns", "announcements", "protected_text", "scenarios", "decisions", "carryovers"]
GATE_PROJECTIONS = ["carryovers", "decisions", "review_history", "findings"]
GFM_DELIMITER_CELL = re.compile(r"^:?-+:?$")
POLICY_SUBJECT_HEADER = {"role", "roles", "principal", "principals", "who", "actor", "caller", "operation", "operations",
                         "scenario", "scenarios", "round", "status", "reputation", "layout"}
POLICY_ASSERTION_HEADER = {"permission", "permissions", "permitted", "access", "allowed", "presented", "presentation", "shown",
                           "distinguishes", "outcome", "outcomes", "assertion", "safe", "decision"}
POLICY_ASSERTION_WORDS = {"yes", "no", "y", "n", "true", "false", "allowed", "denied", "permitted", "forbidden", "shown",
                          "withheld", "safe", "clean"}


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


def closed_local_schema(schema):
    """Refuse remote resolution before invoking jsonschema; every object is closed."""
    for node in walk(schema):
        if not isinstance(node, dict):
            continue
        for key in ("$ref", "$dynamicRef", "$recursiveRef"):
            if key in node and not (isinstance(node[key], str) and node[key].startswith("#/")):
                return False
        if "patternProperties" in node or "unevaluatedProperties" in node:
            return False
        if (node.get("type") == "object" or "properties" in node) and node.get("additionalProperties") is not False:
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
        if isinstance(value, list):
            value = ", ".join(str(x) for x in value) or "—"
        if value is None or value == "":
            value = "—"
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(cell(x) for x in row) + " |" for row in rows])


def keyed(rows, *fields):
    """Rows keyed by their semantic key. A duplicate key raises (the calling check fails), so a later valid row can never
    conceal an earlier unsafe one (round-1 MEDIUM-1)."""
    out = {}
    for r in rows:
        k = tuple(r[f] for f in fields) if len(fields) > 1 else r[fields[0]]
        if k in out:
            raise ValueError(f"duplicate semantic key {k}")
        out[k] = r
    return out


def protected_items(d):
    """Every protected display field as (governed-text path, text), in contract order and including any duplicate."""
    e = d["enrichment"]
    out = [("enrichment.advisory_notice", e["advisory_notice"]), ("enrichment.observed_at_absent_text", e["observed_at_absent_text"]),
           ("enrichment.unrecognized_pair.label", e["unrecognized_pair"]["label"]), ("enrichment.unrecognized_pair.meaning", e["unrecognized_pair"]["meaning"])]
    for r in e["interpretation"]:
        out += [(f"enrichment.interpretation.{r['presentation']}.label", r["label"]), (f"enrichment.interpretation.{r['presentation']}.meaning", r["meaning"])]
    out.append(("unsupported_language.explanation", d["unsupported_language"]["explanation"]))
    out += [(f"accessibility.announcements.{a['state']}.text", a["text"]) for a in d["accessibility"]["announcements"]]
    return out


def protected_texts(d):
    """Protected display fields keyed by their governed-text path; a duplicated path raises."""
    out = {}
    for k, v in protected_items(d):
        if k in out:
            raise ValueError(f"duplicate protected field {k}")
        out[k] = v
    return out


def norm(text):
    return " ".join(str(text).split())


def int_pairs(integration):
    """(status, reputation_result) -> the integration outcomes INT-001 maps to that pair."""
    pairs = {}
    for m in integration["outcomes"]["mapping"]:
        for s, r in itertools.product(m["enrichment_status"], m["reputation_result"]):
            pairs.setdefault((s, r), set()).add(m["outcome"])
    return pairs


def projections(d):
    """Human-readable tables that UX-006 and GATE-031 must carry verbatim between <!-- UXA:name --> markers."""
    yes = {True: "yes", False: "no"}
    return {
        "operations": table(["Operation", "Surface", "Method", "Path", "Roles", "Resource authorization", "Audit", "Sensitivity"],
                            [[o["operation_id"], o["surface_id"], o["method"], o["path"], o["roles"], o["resource_authorization"],
                              o["audit"], o["sensitivity"]] for o in d["operations"]]),
        "errors": table(["API error", "HTTP", "Retryability", "Presentation state", "Recovery"],
                        [[e["error_code"], e["http_status"], e["retryability"], e["presentation_state"], e["recovery"]] for e in d["error_presentation"]]),
        "interpretation": table(["Status", "Reputation result", "Possible integration outcomes", "Distinguishes outcome", "Presented as", "Label", "Meaning"],
                                [[r["status"], r["reputation_result"], r["possible_outcomes"], yes[r["distinguishes_outcome"]], r["presentation"],
                                  r["label"], r["meaning"]] for r in d["enrichment"]["interpretation"]]),
        "support": table(["Input support status", "Presented as", "Conclusion reached"],
                         [[r["input_support_status"], r["presentation"], yes[r["conclusion_reached"]]] for r in d["unsupported_language"]["support_presentation"]]),
        "patterns": table(["Pattern", "Requirement", "UX-001 commitment"], [[p["id"], p["requirement"], p["ux001_flag"]] for p in d["accessibility"]["patterns"]]),
        "announcements": table(["Announcement state", "Announced fields"], [[a["state"], a["announced_fields"]] for a in d["accessibility"]["announcements"]]),
        "protected_text": table(["Protected display field", "Governed text"], [[k, v] for k, v in protected_items(d)]),
        "scenarios": table(["Scenario", "Situation", "Action", "Role / relationship / layout", "Presented", "Presented as", "Distinguishes outcome",
                            "Provider assertion", "Conclusion"],
                           [[s["id"], s["title"], s["action"], f"{s['context']['principal_role']} / {s['context']['relationship']} / {s['context']['layout']}",
                             yes[s["expected"]["presented"]], s["expected"]["presentation"], yes[s["expected"]["distinguishes_outcome"]],
                             yes[s["expected"]["provider_assertion"]], yes[s["expected"]["conclusion_reached"]]] for s in d["scenarios"]]),
        "decisions": table(["Unresolved decision", "Owner", "Status"], [[x["decision"], x["owner"], x["status"]] for x in d["open_decisions"]]),
        "carryovers": table(["Item", "Status", "Owner"], [[k, v["status"], v["owner"]] for k, v in d["carryovers"].items()]),
        "review_history": table(["Round", "Kind", "Decision", "BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO", "Reviewer role", "Evidence source", "Record"],
                                [[h["round"], h["kind"], h["decision"], *[h["counts"][k] for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")],
                                  h["reviewer_role"], h["evidence_source"], h["record_reference"]] for h in d["lifecycle"]["review_history"]]),
        "findings": table(["Finding", "Round", "Severity", "Summary", "Disposition", "Closed in round", "Owner"],
                          [[x["id"], x["round"], x["severity"], x["summary"], x["disposition"], x["closed_in_round"], x["owner"]] for x in d["review_findings"]]),
    }


def gfm_cells(line):
    """Cells of one GFM table line: optional leading/trailing pipe, unescaped '|' separators, surrounding whitespace."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def gfm_tables(lines, skip):
    """Bounded recognizer for visible GFM tables (outer pipes optional); fenced content and `skip` lines are not tables."""
    fence, visible = False, []
    for i, ln in enumerate(lines):
        if re.match(r"^ {0,3}(```|~~~)", ln):
            fence = not fence
            visible.append(False)
            continue
        visible.append(not fence and i not in skip)
    tables, i = [], 0
    indent = re.compile(r"^ {0,3}\S")
    while i + 1 < len(lines):
        head, delim = lines[i], lines[i + 1]
        if visible[i] and visible[i + 1] and "|" in head and indent.match(head) and indent.match(delim):
            hc, dc = gfm_cells(head), gfm_cells(delim)
            if len(hc) == len(dc) and all(GFM_DELIMITER_CELL.match(c) for c in dc):
                rows, j = [], i + 2
                while j < len(lines) and visible[j] and lines[j].strip() and not re.match(r"^ {0,3}(#|```|~~~|<!--)", lines[j]):
                    rows.append(gfm_cells(lines[j]))
                    j += 1
                tables.append((hc, rows))
                i = j
                continue
        i += 1
    return tables


def load_inputs():
    snapshot = read_json("contracts/phase6/phase6-closure-v1.json")
    hashed = [a["path"] for a in snapshot["snapshot"]["artifacts"]] + list(PREDECESSOR_PINS)
    return dict(contract=read_json(CONTRACT), schema=read_json(SCHEMA),
                doc=(ROOT / DOC).read_text(encoding="utf-8") if (ROOT / DOC).exists() else "",
                gate=(ROOT / GATE).read_text(encoding="utf-8") if (ROOT / GATE).exists() else "",
                api=read_json("contracts/api/api-v1.json"), openapi=read_json("contracts/api/openapi-v1.json"),
                persistence=read_json("contracts/postgresql/schema-v1.json"),
                foundation=read_json("contracts/ux/ux-foundation-v1.json"), intake=read_json("contracts/ux/ux-intake-v1.json"),
                result=read_json("contracts/ux/ux-result-v1.json"), review=read_json("contracts/ux/ux-review-v1.json"),
                reporting=read_json("contracts/ux/ux-reporting-v1.json"),
                integration=read_json("contracts/integrations/external-enrichment-v1.json"),
                adr=(ROOT / "adr/ADR-0014-language-and-script-strategy.md").read_text(encoding="utf-8"),
                api_doc=(ROOT / "docs/06-contracts/API-001-api-resource-protocol-contract.md").read_text(encoding="utf-8"),
                engine=(ROOT / "knowledge/runtime/engine.py").read_text(encoding="utf-8"), snapshot=snapshot,
                hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in hashed},
                pins=copy.deepcopy(dict(review_history=VERIFIED_REVIEW_HISTORY, approval=VERIFIED_APPROVAL,
                                        merge_evidence=VERIFIED_MERGE_EVIDENCE)),
                governed_text=dict(GOVERNED_TEXT))


def authorized(op, role, rel, permits):
    """API-001 §3 / §5 resource authorization (no break-glass applies). None when permitted, else the refusal state.
    Existence masking: a case-scoped resource without case visibility answers the masked 404 whatever the role; a visible
    case without the role, or derived content without permission, answers 403. A non-case resource answers 403 on a missing
    role (round-1 MEDIUM-2)."""
    ra = op["resource_authorization"]
    if ra in CASE_SCOPED:
        if CASE_RELATIONSHIP.get(role) != rel:
            return "NOT_FOUND_OR_NOT_VISIBLE"
        if role not in op["roles"]:
            return "ACCESS_DENIED"
        return "CONTENT_PERMISSION_REQUIRED" if ra == "CASE_DERIVED_CONTENT" and not permits else None
    return "ACCESS_DENIED"


def decide(api_ops, pairs, action, cx):
    """Independent decision procedure: API authorization, INT-001's outcome mapping, the input-support vocabulary and the
    ADR-0014 detection scope. The layout never changes the outcome (permission and redaction parity)."""
    out = dict(presented=False, presentation="ACCESS_DENIED", distinguishes_outcome=False, provider_assertion=False,
               implies_safe=False, on_result_surface=False, conclusion_reached=False, content_exposed_beyond_permission=False)
    if action == "VIEW_ENRICHMENT":
        refusal = authorized(api_ops["listEvaluationEnrichments"], cx["principal_role"], cx["relationship"], cx["permits_evidence_content"])
        if refusal:
            return dict(out, presentation=refusal)
        pair = (cx["enrichment_status"], cx["reputation_result"])
        if pair not in PRESENTATION_BY_PAIR or (pair not in pairs and pair != NOT_LOOKED_UP):
            return dict(out, presented=True, presentation="UNRECOGNIZED_RECORD")
        return dict(out, presented=True, presentation=PRESENTATION_BY_PAIR[pair], distinguishes_outcome=len(pairs.get(pair, set())) == 1,
                    provider_assertion=pair[0] == "SUCCEEDED" and pair[1] in PROVIDER_ASSERTIONS)
    if action == "VIEW_LANGUAGE_SUPPORT":
        refusal = authorized(api_ops["getDetectionResult"], cx["principal_role"], cx["relationship"], cx["permits_evidence_content"])
        if refusal:
            return dict(out, presentation=refusal)
        presentation, conclusion = SUPPORT_PRESENTATION[cx["input_support_status"]]
        if cx["input_support_status"] == "UNSUPPORTED" and [x for x in cx["language"] if x not in DETECTION_SCOPE["languages"]]:
            presentation = "UNSUPPORTED_LANGUAGE"
        return dict(out, presented=True, presentation=presentation, conclusion_reached=conclusion)
    raise ValueError("unknown action")


def validate(ctx):
    d, api, f = ctx["contract"], ctx["api"], ctx["foundation"]
    api_ops = {o["operation_id"]: o for o in api["operations"]}
    schemas = api["schemas"]
    pvoc = ctx["persistence"]["vocabularies"]
    pins = ctx["pins"]
    pairs = int_pairs(ctx["integration"])
    results = []

    def check(n, description, test):
        try:
            passed = bool(test())
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration):
            passed = False
        results.append({"check_id": f"UXA-{n:02d}", "description": description, "passed": passed})

    def vocab(name):
        v = api["vocabularies"][name]
        return v["values"] if v["source"] == "API" else pvoc[v["persistence_vocabulary"]]["values"]

    def fields(schema_name):
        return [x["name"] for x in schemas[schema_name]["fields"]]

    lc = d["lifecycle"]
    fsurf = {s["surface_id"]: s for s in f["surfaces"]}
    states = {s["state_id"]: s for s in f["presentation_states"]}
    openapi_ids = {op.get("operationId") for p in ctx["openapi"]["paths"].values() for op in p.values() if isinstance(op, dict)}
    handoff = next(h for h in f["handoffs"] if h["work_package"] == "P7-WP6")
    e = d["enrichment"]

    def review_entry_ok(h, i):
        return (h["round"] == i + 1 and h["kind"] in INDEPENDENT_REVIEW_KINDS and h["decision"] in ("APPROVE", "REQUEST_CHANGES")
                and h["reviewer_role"] in INDEPENDENT_REVIEWER_ROLES and h["evidence_source"] in PERMITTED_EVIDENCE_SOURCES
                and h["record_reference"] == REVIEW_RECORD
                and all(isinstance(h["counts"][k], int) and h["counts"][k] >= 0 for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"))
                and (h["decision"] != "APPROVE" or all(h["counts"][k] == 0 for k in ("BLOCKER", "HIGH", "MEDIUM"))))

    def lifecycle_ok():
        st, hist = lc["state"], lc["review_history"]
        if lc["status"] != STATUS_BY_STATE.get(st) or lc["decision_vocabulary"] != ["APPROVE", "REQUEST_CHANGES"]:
            return False
        if hist != pins["review_history"] or not all(review_entry_ok(h, i) for i, h in enumerate(hist)):
            return False
        approving = bool(hist) and hist[-1]["decision"] == "APPROVE"
        if st == "CANDIDATE":
            return (not approving and lc["approval"] is None and lc["merge_evidence"] is None
                    and d["claims"]["approved"] is False and d["claims"]["independently_reviewed"] is bool(hist))
        expected = ({"round": hist[-1]["round"], "decision": "APPROVE", "record_reference": hist[-1]["record_reference"],
                     "reviewer_role": hist[-1]["reviewer_role"]} if approving else None)
        if (not approving or pins["approval"] is None or lc["approval"] != pins["approval"] or lc["approval"] != expected
                or d["claims"]["approved"] is not True or d["claims"]["independently_reviewed"] is not True):
            return False
        if st == "APPROVED":
            return lc["merge_evidence"] is None
        me = lc["merge_evidence"]
        return (st == "CLOSED" and pins["merge_evidence"] is not None and me == pins["merge_evidence"] and me["base_commit"] == BASELINE
                and me["remote_ci"]["merge_commit_run_id"] > me["remote_ci"]["pr_head_run_id"]
                and re.fullmatch(r"GATE-031 §(\d+)", me["verification_reference"]) is not None
                and f"## {me['verification_reference'].split('§')[1]}. " in ctx["gate"])

    def freeze():
        snap = {a["path"]: a["sha256"] for a in ctx["snapshot"]["snapshot"]["artifacts"]}
        return (ctx["snapshot"]["closure_status"] == "PHASE 6 CLOSED" and len(snap) == 19
                and all(ctx["hashes"][p] == h for p, h in snap.items())
                and re.search(r'^ENGINE_VERSION = "1\.0\.0"$', ctx["engine"], re.M) is not None and d["engine_version"] == "1.0.0")

    def predecessors():
        r = ctx["result"]
        return (all(ctx["hashes"][p] == h for p, h in PREDECESSOR_PINS.items())
                and all(ctx[k]["lifecycle"]["state"] == "CLOSED" for k in ("intake", "result", "review", "reporting"))
                and d["foundation"] == dict(foundation_contract="UX-001", foundation_gate="GATE-026", foundation_handoff_scope=handoff["scope"],
                                            consumed_contracts=["UX-002", "UX-003", "UX-004", "UX-005"],
                                            consumed_gates=["GATE-027", "GATE-028", "GATE-029", "GATE-030"], integration_contract="INT-001",
                                            language_decision="ADR-0014 / DEC-008", predecessors_modified=False)
                and r["enrichment_presentation"]["owner"] == "P7-WP6" and r["language_presentation"]["unsupported_language_detail_owner"] == "P7-WP6"
                and f["unsupported_language"]["detail_owner"] == "P7-WP6" and r["accessibility"]["detail_owner"] == "P7-WP6")

    def scope_ok():
        sc = d["scope"]
        mapped = [m["handoff_item"] for m in sc["request_mapping"]]
        return (sc["owned"] == handoff["scope"] and set(mapped) == set(handoff["scope"]) and all(m["request_item"] for m in sc["request_mapping"])
                and sc["deferred"] and all(x["owner"] in DEFERRED_OWNERS and x["item"] for x in sc["deferred"]))

    def surfaces_ok():
        s = d["surfaces"]
        u = fsurf["UX-ENRICHMENT"]
        return (len(s) == 1 and s[0]["surface_id"] == "UX-ENRICHMENT" and s[0]["operations"] == u["api_operations"]
                and s[0]["allowed_roles"] == u["allowed_roles"] and s[0]["role_alone_sufficient"] is False is u["role_alone_sufficient"]
                and set(s[0]["handoff_items"]) <= set(handoff["scope"]) and d["cross_cutting_surfaces"] == [x["surface_id"] for x in f["surfaces"]])

    def api_parity():
        o = d["operations"]
        a = api_ops["listEvaluationEnrichments"]
        acc = fsurf["UX-ENRICHMENT"]["operation_access"][0]
        integ = ctx["integration"]["api_surface"]
        return (len(o) == 1 and o[0]["operation_id"] == "listEvaluationEnrichments" in openapi_ids and a["internal"] is False
                and all(o[0][k] == a[k] for k in OP_KEYS) and o[0]["errors"] == a["errors"] and o[0]["caller_constraints"] == a.get("caller_constraints", [])
                and acc["roles"] == a["roles"] and acc["resource_authorization"] == a["resource_authorization"]
                and integ["existing_operation"] == "listEvaluationEnrichments" and integ["path"] == a["path"] and integ["new_endpoints"] == []
                and o[0]["audit_notice_shown"] is (a["audit"] == "REQUIRED"))

    def errors_ok():
        api_err = {x["code"]: x for x in api["error_codes"]}
        voc = keyed(d["recovery_vocabulary"], "recovery")
        return ([x["error_code"] for x in d["error_presentation"]] == sorted(d["operations"][0]["errors"])
                and all(x["http_status"] == api_err[x["error_code"]]["http_status"] and x["retryability"] == api_err[x["error_code"]]["retryability"]
                        and x["error_code"] in states.get(x["presentation_state"], {}).get("api_error_codes", []) and x["implies_safe"] is False
                        and RECOVERY_RETRYABILITY.get(x["recovery"]) == x["retryability"] for x in d["error_presentation"])
                and set(voc) == set(RECOVERY_RETRYABILITY) and all(voc[r]["retryability"] == [t] and voc[r]["meaning"] for r, t in RECOVERY_RETRYABILITY.items()))

    def enrichment_rules():
        g = f["enrichment_guardrails"]
        view = fields("EnrichmentView")
        return (e["operation"] == "listEvaluationEnrichments" and e["roles"] == api_ops["listEvaluationEnrichments"]["roles"]
                and g["outcome_meanings"]["CLEAN"] == "PROVIDER_ASSERTION_NOT_TRUSTLENS_SAFETY" and g["primary_verdict"] is False
                and "Do not invent lookup_outcome" in g["unsupported_outcome_detail"]
                and e["authority"] == g["authority"] == "SUPPORTING_ADVISORY" and e["advisory_always_labelled"] is True
                and g["api_view_fields"] == view and set(e["displayed_fields"]) <= set(view)
                and e["attribution_fields"] == g["attribution_fields"] and g["provider_attribution_required"] is True
                and all(e[k] is False for k in ("presented_on_result_surface", "changes_classification", "changes_severity_risk_or_confidence",
                                                "consumed_in_governed_artifact", "provider_identity_displayed", "raw_provider_body", "freshness_claimed"))
                and ctx["result"]["enrichment_presentation"]["presented_on_result_surface"] is False
                and ctx["result"]["enrichment_presentation"]["provider_clean_as_safe"] is False
                and ctx["integration"]["decision_boundary"]["consumed_in_governed_artifact"] is False
                and next(x for x in schemas["EnrichmentView"]["fields"] if x["name"] == "observed_at").get("nullable") is True
                and e["list_contract"] == api_ops["listEvaluationEnrichments"]["list"])

    def interpretation_ok():
        rows = keyed(e["interpretation"], "status", "reputation_result")
        keyed(e["interpretation"], "presentation")
        expected_pairs = set(pairs) | {NOT_LOOKED_UP}
        if set(rows) != expected_pairs:
            return False
        statuses, reps = set(vocab("enrichment_status")), set(vocab("reputation_result"))
        for r in e["interpretation"]:
            pair = (r["status"], r["reputation_result"])
            possible = pairs.get(pair, set())
            if (pair[0] not in statuses or pair[1] not in reps or r["possible_outcomes"] != sorted(possible)
                    or r["distinguishes_outcome"] is not (len(possible) == 1) or r["presentation"] != PRESENTATION_BY_PAIR[pair]
                    or r["provider_assertion"] is not (pair[0] == "SUCCEEDED" and pair[1] in PROVIDER_ASSERTIONS) or r["implies_safe"] is not False):
                return False
        u = e["unrecognized_pair"]
        return u["presentation"] == "UNRECOGNIZED_RECORD" and u["interpreted"] is False

    def truthful_outcomes():
        """CLEAN is a provider assertion only; a pair that cannot establish NOT_FOUND or UNAVAILABLE never claims it."""
        keyed(e["interpretation"], "presentation")
        texts = {k: norm(v) for k, v in ctx["governed_text"].items()}
        for r in e["interpretation"]:
            pair = (r["status"], r["reputation_result"])
            possible = pairs.get(pair, set())
            for x in (norm(r["label"]), norm(r["meaning"]), texts[f"enrichment.interpretation.{r['presentation']}.label"],
                      texts[f"enrichment.interpretation.{r['presentation']}.meaning"]):
                if possible != {"NOT_FOUND"} and NOT_FOUND_CLAIM.search(x):
                    return False
                if possible != {"UNAVAILABLE"} and SPECIFIC_UNAVAILABLE.search(x):
                    return False
                if r["reputation_result"] != "CLEAN" and CLEAN_CLAIM.search(x):
                    return False
                if VERDICT_WORDS.search(x):
                    return False
            if r["provider_assertion"] and "provider" not in norm(r["meaning"]).lower():
                return False
            if r["reputation_result"] == "CLEAN" and not ("provider's assertion" in norm(r["meaning"]) and "TrustLens" in r["meaning"]):
                return False
        clean = texts["enrichment.interpretation.PROVIDER_CLEAN_ASSERTION.meaning"]
        return "provider's assertion" in clean and "TrustLens" in clean

    def governed_copy():
        got, gov = protected_texts(d), ctx["governed_text"]
        return (set(got) == set(gov) == set(GOVERNED_TEXT) and all(norm(got[k]) == norm(gov[k]) for k in gov)
                and all(norm(v) == norm(gov[k]) for k, v in protected_items(d)))

    def language_ok():
        ul = d["unsupported_language"]
        r = ctx["result"]["language_presentation"]
        return (ul["detection_scope"] == DETECTION_SCOPE and ADR_SCOPE_TEXT in ctx["adr"]
                and ul["classification"] == f["unsupported_language"]["classification"] == "UNSUPPORTED"
                and ul["benign_inference"] is False is f["unsupported_language"]["benign_inference"] and ul["conclusion_reached"] is False
                and ul["client_language_detection"] is False is r["client_language_detection"]
                and ul["language_fields_rendered_verbatim"] is True is r["rendered_verbatim"]
                and [x.rstrip("[]") for x in r["fields"]] == ul["language_fields"] and set(ul["language_fields"]) <= set(fields("DetectionResultResponse"))
                and ul["interface_language_is_detection_scope"] is False and ul["unsupported_input_owner"] == "UX-002"
                and set(ul["unsupported_input_states"]) <= set(states)
                and ul["input_support_statuses"] == vocab("input_support_status")
                and {k: (x["presentation"], x["conclusion_reached"]) for k, x in keyed(ul["support_presentation"], "input_support_status").items()} == SUPPORT_PRESENTATION
                and ul["language_explanation_presentation"] == "UNSUPPORTED_LANGUAGE")

    def accessibility_ok():
        a = d["accessibility"]
        ux1 = f["accessibility"]
        covered = {p["ux001_flag"] for p in a["patterns"]}
        expected = {k for k, v in ux1.items() if k not in ("certification_claim", "colour_only_meaning")}
        return (covered == expected and len({p["id"] for p in a["patterns"]}) == len(a["patterns"])
                and ux1["mandatory_animation"] is False and ux1["colour_only_meaning"] is False and a["colour_only_meaning"] is False
                and a["conformance_claim"] is False and ux1["certification_claim"] is False
                and ctx["intake"]["accessibility"]["certification_claim"] is False and ctx["result"]["accessibility"]["certification_claim"] is False
                and a["time_limit_imposed"] is False is ctx["intake"]["accessibility"]["time_limit_imposed"]
                and a["hover_only_interaction"] is False is ctx["intake"]["accessibility"]["hover_only_interaction"]
                and not [p for p in a["patterns"] if CONFORMANCE_CLAIM.search(p["requirement"])])

    def announcements_ok():
        rows = d["accessibility"]["announcements"]
        view = set(fields("EnrichmentView"))
        return (set(keyed(rows, "state")) == set(ANNOUNCEMENT_POLICY)
                and all(set(a["announced_fields"]) <= ANNOUNCEMENT_POLICY[a["state"]] and not set(a["announced_fields"]) & PROTECTED_FIELDS
                        and set(a["announced_fields"]) <= view for a in rows))

    def responsive_ok():
        r, ux1 = d["responsive"], f["responsive"]
        return (r["breakpoint_values"] == ux1["breakpoint_values"] == ctx["intake"]["mobile"]["breakpoint_values"] == "NOT YET SPECIFIED"
                and r["permission_parity"] is True is ux1["permission_parity"] and ctx["intake"]["mobile"]["permission_parity_across_form_factors"] is True
                and r["narrow_layout_exposes_hidden_content"] is False is ux1["narrow_layout_exposes_hidden_content"]
                and r["controls_parity"] is True and r["content_reflows"] is True and r["device_specific_permissions"] is False
                and r["orientation_locked"] is False and r["layouts"] == ["NARROW", "WIDE"]
                and r["wide_tables_on_narrow"] == "SCROLL_WITHIN_TABLE_REGION_WITH_HEADERS")

    def redaction_ok():
        rd = d["redaction"]
        return (rd == dict(withheld_content_rendered_then_hidden=False, placeholder_content_free=True, same_redaction_all_layouts=True,
                           tooltips_titles_alt_text_content_free=True, notifications_content_free=True, previews_content_free=True,
                           print_renders_only_permitted_view=True, copy_of_withheld_content_possible=False)
                and all(s["sensitivity_behavior"]["placeholder_content_free"] is True for s in f["surfaces"]))

    def display_texts():
        texts = [v for _, v in protected_items(d)] + [p["requirement"] for p in d["accessibility"]["patterns"]] + [x["meaning"] for x in d["recovery_vocabulary"]]
        return all(isinstance(x, str) and x and not FORBIDDEN_DISPLAY.search(x) and not CONFORMANCE_CLAIM.search(x) for x in texts)

    def decisions_ok():
        dec = d["open_decisions"]
        carried = [x["decision"] for x in f["open_design_decisions"] if "P7-WP6" in x["owner"]]
        return (all(x["status"] == "DEFERRED" and x["owner"] and x["decision"] for x in dec)
                and all(any(k.lower() in x["decision"].lower() for x in dec) for k in REQUIRED_DECISIONS)
                and all(any(x.startswith(c) for x in carried) for c in UX001_CARRIED)
                and sum("carried from UX-001" in x["owner"] for x in dec) >= len(UX001_CARRIED))

    def scenarios_ok():
        return (API_MASKING_TEXT in ctx["api_doc"] and bool(d["scenarios"])
                and all(s["expected"] == decide(api_ops, pairs, s["action"], s["context"]) for s in d["scenarios"]))

    def scenario_coverage():
        ids = [s["id"] for s in d["scenarios"]]
        shown = {s["expected"]["presentation"] for s in d["scenarios"]}
        return (len(set(ids)) == len(ids) and set(PRESENTATION_BY_PAIR.values()) | {"UNRECOGNIZED_RECORD", "UNSUPPORTED_LANGUAGE", "UNSUPPORTED_INPUT"} <= shown
                and {s["context"]["layout"] for s in d["scenarios"]} == {"NARROW", "WIDE"}
                and {s["action"] for s in d["scenarios"] if not s["expected"]["presented"]} == {"VIEW_ENRICHMENT", "VIEW_LANGUAGE_SUPPORT"})

    def layout_parity():
        """Scenarios that differ only by layout must present identically (permission, controls and redaction parity); every
        narrow-layout scenario has a wide-layout twin."""
        def key(s):
            return json.dumps({k: v for k, v in s["context"].items() if k != "layout"} | {"action": s["action"]}, sort_keys=True)
        groups = {}
        for s in d["scenarios"]:
            groups.setdefault(key(s), []).append(s)
        narrow = [s for s in d["scenarios"] if s["context"]["layout"] == "NARROW"]
        return (bool(narrow) and all(any(o["context"]["layout"] == "WIDE" for o in groups[key(s)]) for s in narrow)
                and all(len({json.dumps(s["expected"], sort_keys=True) for s in g}) == 1 for g in groups.values())
                and all(s["expected"]["content_exposed_beyond_permission"] is False and s["expected"]["on_result_surface"] is False
                        and s["expected"]["implies_safe"] is False for s in d["scenarios"]))

    def documentary_parity():
        proj = projections(d)
        return (all(f"<!-- UXA:{n}:BEGIN -->\n{proj[n]}\n<!-- UXA:{n}:END -->" in ctx["doc"] for n in DOC_PROJECTIONS)
                and all(f"<!-- UXA:{n}:BEGIN -->\n{proj[n]}\n<!-- UXA:{n}:END -->" in ctx["gate"] for n in GATE_PROJECTIONS))

    def projection_structure(text, names):
        subjects = set(ROLES) | {s["id"] for s in d["scenarios"]} | set(vocab("enrichment_status")) | {"listEvaluationEnrichments"} | set(d["carryovers"])
        assertions = ({"OWNER", "ASSIGNED_ANALYST", "NONE", "APPROVE", "REQUEST_CHANGES", "UNRECOGNIZED_RECORD"} | set(PRESENTATION_BY_PAIR.values())
                      | set(vocab("reputation_result")) | set(states) | FINDING_DISPOSITIONS)
        governed_headers = {tuple(" ".join(c.lower().split()) for c in gfm_cells(v.splitlines()[0])) for v in projections(d).values()}
        lines = text.splitlines()
        marker = re.compile(r"^<!-- UXA:(\w+):(BEGIN|END) -->$")
        spans, open_name, open_at, seen, in_fence = [], None, None, [], False
        for i, ln in enumerate(lines):
            if re.match(r"^ {0,3}(```|~~~)", ln):
                in_fence = not in_fence
            m = marker.match(ln)
            if m:
                if in_fence:
                    return False
                name, kind = m.groups()
                if kind == "BEGIN":
                    if open_name is not None:
                        return False
                    open_name, open_at = name, i
                    seen.append(name)
                elif open_name != name:
                    return False
                else:
                    spans.append((open_at, i))
                    open_name = None
                continue
            if "UXA:" in ln or ("<!--" in ln and "-->" not in ln) or ("-->" in ln and "<!--" not in ln):
                return False
        if open_name is not None or in_fence or sorted(seen) != sorted(names):
            return False
        inside = {k for a, b in spans for k in range(a, b + 1)}

        def policy_row(cells):
            return any(c in subjects and any((x in assertions or x.lower() in POLICY_ASSERTION_WORDS) for j, x in enumerate(cells) if j != i)
                       for i, c in enumerate(cells))

        fence = False
        for i, ln in enumerate(lines):
            if re.match(r"^ {0,3}(```|~~~)", ln):
                fence = not fence
                continue
            if not fence and i not in inside and ln.lstrip().startswith("|") and policy_row([c.strip("*`").strip() for c in gfm_cells(ln)]):
                return False
        for header, rows in gfm_tables(lines, inside):
            head = [c.strip("*`").strip() for c in header]
            words = {w for c in head for w in re.findall(r"[a-z]+", c.lower())}
            if (tuple(" ".join(c.lower().split()) for c in head) in governed_headers or (words & POLICY_SUBJECT_HEADER and words & POLICY_ASSERTION_HEADER)
                    or any(policy_row([c.strip("*`").strip() for c in r]) for r in rows)):
                return False
        return True

    def no_premature_claims():
        lines = ctx["doc"].splitlines() + ctx["gate"].splitlines()
        return not [ln for ln in lines for pat, allowed in PREMATURE.items() if pat.search(ln) and lc["state"] not in allowed and not NEGATION.search(ln)]

    def gate_decision():
        row = next(ln for ln in ctx["gate"].splitlines() if ln.startswith("| Deliverable |"))
        return (ctx["gate"].count(f"**{lc['status']}**") == 1
                and all(x in row for x in ("UX-006", "ux-accessibility-v1.json", "ux-accessibility-contract.schema.json",
                                           "accessibility-negative-mutations.json", "validate_ux_accessibility.py")))

    def findings_ok():
        fs, hist = d["review_findings"], lc["review_history"]
        if not hist:
            return fs == []
        rounds = {h["round"]: h for h in hist}
        if len({x["id"] for x in fs}) != len(fs) or ctx["gate"].splitlines().count(REVIEW_HEADING) != 1:
            return False
        for rnd, h in rounds.items():
            by = {k: sum(1 for x in fs if x["round"] == rnd and x["severity"] == k) for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")}
            if h["decision"] == "REQUEST_CHANGES" and by != h["counts"]:
                return False
        approved = lc["state"] in ("APPROVED", "CLOSED")
        for x in fs:
            closed = x["disposition"] == "CLOSED_BY_REREVIEW"
            if (x["round"] not in rounds or x["disposition"] not in FINDING_DISPOSITIONS or not x["owner"] or not x["summary"]
                    or closed != (x["closed_in_round"] is not None)):
                return False
            if closed and not (x["closed_in_round"] in rounds and x["closed_in_round"] > x["round"]):
                return False
            if x["severity"] in ("BLOCKER", "HIGH", "MEDIUM") and not closed and (approved or x["disposition"] != "CORRECTED_PENDING_TARGETED_REREVIEW"):
                return False
        return True

    check(1, "UX-006 identity and status row follow the recorded lifecycle", lambda: "| Document ID | UX-006 |" in ctx["doc"] and f"| Status | {lc['status']} |" in ctx["doc"])
    check(2, "GATE-031 identity and status row follow the recorded lifecycle", lambda: "| Document ID | GATE-031 |" in ctx["gate"] and f"| Status | {lc['status']} |" in ctx["gate"])
    check(3, "Machine contract valid against a closed, local-only schema", lambda: schema_valid(d, ctx["schema"]))
    check(4, "Exact baseline and work-package identity", lambda: d["baseline"] == BASELINE and BASELINE in ctx["doc"] and BASELINE in ctx["gate"] and d["work_package"] == "P7-WP6" and d["contract_id"] == "UX-006" and d["phase"] == f["phase"])
    check(5, "Lifecycle fail-closed: review records, approval and merge evidence only as pinned governed records", lifecycle_ok)
    check(6, "Phase-6 snapshot (19 artifacts, including INT-001) intact; ENGINE_VERSION 1.0.0", freeze)
    check(7, "UX-001..UX-005 and ADR-0014 unmodified; UX-002..UX-005 CLOSED; P7-WP6 hand-offs consumed", predecessors)
    check(8, "Scope equals the UX-001 P7-WP6 handoff; every request item mapped; deferred items owned", scope_ok)
    check(9, "Enrichment surface equals UX-001; cross-cutting rules cover every UX-001 surface", surfaces_ok)
    check(10, "listEvaluationEnrichments equals the accepted API, OpenAPI and INT-001 surface; no new endpoint", api_parity)
    check(11, "Errors map to UX-001 states with retryability-consistent recovery", errors_ok)
    check(12, "Enrichment advisory only: off the result surface, provider attribution only, no identity, body or freshness claim", enrichment_rules)
    check(13, "Interpretation table equals INT-001's outcome mapping; an outcome is distinguished only when one outcome fits", interpretation_ok)
    check(14, "CLEAN, NOT_FOUND and UNAVAILABLE claimed only where the record establishes them; CLEAN is a provider assertion", truthful_outcomes)
    check(15, "Protected copy bound to the closed set of governed messages", governed_copy)
    check(16, "Unsupported language: English-only detection scope (ADR-0014), never benign, no conclusion, no client detection", language_ok)
    check(17, "Every UX-001 accessibility commitment covered by a pattern; no conformance claim; no time limit or hover-only interaction", accessibility_ok)
    check(18, "Announcements carry only the fields their state may announce; no protected field", announcements_ok)
    check(19, "Responsive behaviour: breakpoints not invented; permission and control parity; narrow layouts expose nothing hidden", responsive_ok)
    check(20, "Redaction identical across layouts; withheld content never rendered, previewed, printed or copied", redaction_ok)
    check(21, "Access consequences equal API audit requirements", lambda: d["access_consequences"] == [{"operation_id": "listEvaluationEnrichments", "audit": api_ops["listEvaluationEnrichments"]["audit"], "audit_event": api_ops["listEvaluationEnrichments"]["audit_event"], "notice_shown": api_ops["listEvaluationEnrichments"]["audit"] == "REQUIRED"}])
    check(22, "Guardrails hold; no prohibited exposure", lambda: set(d["guardrails"]) == GUARDRAILS and all(v is False for v in d["guardrails"].values()) and set(d["exposure"]) == EXPOSURES and d["exposure"] == f["exposure"] and all(v is False for v in d["exposure"].values()))
    check(23, "Display texts make no safety, verification, scoring or conformance claim", display_texts)
    check(24, "Missing capabilities recorded as owned deferred decisions, including the UX-001 decisions owned by P7-WP6", decisions_ok)
    check(25, "Programme carryovers unchanged", lambda: d["carryovers"] == {k: {"status": v["status"], "owner": v["owner"]} for k, v in ctx["reporting"]["carryovers"].items()})
    check(26, "No tenancy, retention, implementation, readiness, testing or conformance claim", lambda: d["tenancy"] == dict(ux_enabled=False, organization_switcher_authority=False) and d["retention"] == dict(duration="NOT YET SPECIFIED", numeric_duration_invented=False) and all(d["claims"][k] is False for k in ("frontend_implemented", "api_implemented", "production_ready", "accessibility_compliant", "usability_tested", "security_tested", "later_wp_started")) and len(d["claims"]) == 9 and d["non_goals"])
    check(27, "Every pinned scenario equals the independent decision procedure", scenarios_ok)
    check(28, "Scenarios cover every presentation, both layouts and refused access; identifiers unique", scenario_coverage)
    check(29, "Scenarios differing only by layout present identically; nothing exposed beyond permission", layout_parity)
    check(30, "UX-006 and GATE-031 projections equal the machine contract", documentary_parity)
    check(31, "Exactly one governed projection per table, outside fences; no policy table outside projections", lambda: projection_structure(ctx["doc"], DOC_PROJECTIONS) and projection_structure(ctx["gate"], GATE_PROJECTIONS))
    check(32, "Approval and closure wording follows the recorded lifecycle; no implementation or later-WP claim", no_premature_claims)
    check(33, "GATE-031 deliverable row and single decision line follow the recorded lifecycle", gate_decision)
    check(34, "Review findings equal the recorded rounds; dispositions and the GATE-031 §7 record consistent", findings_ok)
    assert len(results) == CHECK_COUNT
    return results


TARGETS = {"contract", "schema", "doc", "gate", "api", "api_doc", "foundation", "intake", "result", "review", "reporting", "integration", "adr",
           "engine", "hashes", "snapshot", "pins", "governed_text"}


def mutate(ctx, fixture):
    """Small strict JSON-pointer / text mutation dialect; fixtures cannot run code or write files. A fixture with "steps"
    applies a synchronized sequence of such mutations."""
    if "steps" in fixture:
        result = ctx
        for step in fixture["steps"]:
            result = mutate(result, step)
        if result == ctx:
            raise ValueError("vacuous mutation")
        return result
    target = fixture["target"]
    if target not in TARGETS:
        raise ValueError("unknown mutation target")
    result = dict(ctx)
    result[target] = copy.deepcopy(ctx[target])
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


def step_keys(fixture):
    required = {"target", "op"}
    required |= {"old", "value"} if fixture["op"] == "replace_text" else {"path"}
    if fixture["op"] in {"add", "replace"}:
        required.add("value")
    return required


def fixture_keys(fixture):
    if "steps" in fixture:
        if not fixture["steps"] or not all(set(st) == step_keys(st) for st in fixture["steps"]):
            raise ValueError(f"invalid steps in {fixture.get('id')}")
        return {"id", "description", "steps"}
    return {"id", "description"} | step_keys(fixture)


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
            print(f"UX ACCESSIBILITY: FAIL — {len(failed)}/{CHECK_COUNT} checks failed")
            return 1
        fixtures = read_json(FIXTURES)
        if set(fixtures) != {"fixture_version", "mutations", "positive_controls"} or fixtures["fixture_version"] != "1.0":
            raise ValueError("invalid fixture document")
        ids, bad = set(), []
        for fixture in fixtures["mutations"]:
            if set(fixture) != fixture_keys(fixture) | {"expected_check"} or fixture["id"] in ids:
                raise ValueError(f"invalid/duplicate mutation {fixture.get('id')}")
            ids.add(fixture["id"])
            rejected = {r["check_id"] for r in validate(mutate(ctx, fixture)) if not r["passed"]}
            if fixture["expected_check"] not in rejected:
                bad.append(fixture["id"])
                print(f"FAIL {fixture['id']} expected {fixture['expected_check']}; got {sorted(rejected)}")
        pos_ids, pos_bad = set(), []
        for fixture in fixtures["positive_controls"]:
            if set(fixture) != fixture_keys(fixture) or fixture["id"] in pos_ids or fixture["id"] in ids:
                raise ValueError(f"invalid/duplicate positive control {fixture.get('id')}")
            pos_ids.add(fixture["id"])
            rejected = sorted(r["check_id"] for r in validate(mutate(ctx, fixture)) if not r["passed"])
            if rejected:
                pos_bad.append(fixture["id"])
                print(f"FAIL {fixture['id']} positive control rejected by {rejected}")
        if not ids or bad or not pos_ids or pos_bad:
            print(f"UX ACCESSIBILITY: FAIL — mutations {len(ids) - len(bad)}/{len(ids)}; positive controls {len(pos_ids) - len(pos_bad)}/{len(pos_ids)}")
            return 1
        print(f"UX ACCESSIBILITY: PASS — {CHECK_COUNT}/{CHECK_COUNT} checks; {len(ids)}/{len(ids)} negative mutations rejected by "
              f"intended checks; {len(pos_ids)}/{len(pos_ids)} positive controls accepted (static contract validation; no "
              f"frontend or runtime exists)")
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"UX ACCESSIBILITY: FAIL — invalid or missing input: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
