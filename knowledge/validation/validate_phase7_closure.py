"""P7-WP7 deterministic offline integrated Phase-7 closure checks (PC7-01..PC7-24).

Builder verification, not independent review. This gate checks only what no single Phase-7 validator can: the work
packages taken together. Each package's own rules stay with its canonical validator (validate_ux_foundation.py through
validate_ux_accessibility.py), which run_all executes before this gate; nothing here re-validates them.

Integrated checks: the Phase-7 artifact snapshot is intact; every work package's lifecycle and merge record equals its
contract (P7-WP1's merge and CI are pinned here because its contract keeps the pre-merge status row other contracts
hash-pin); every UX-001 handoff is consumed exactly once with an equal scope; every public API operation is accounted for
once (designed in detail, foundation surface only, or a carried integration gap); operation access, exposure, tenancy,
retention, claims and carryovers agree across contracts; every deferred decision of UX-001..UX-006 is carried verbatim to
a Phase-8, Phase-9, Phase-10 or programme owner, resolved by a later closed package, or superseded by a carried entry; and
the roadmap's Phase-7 commitments that were not met (REPORT-001, WCAG 2.2 AA) are recorded as deviations, not claimed.

Lifecycle is fail-closed: review records, approval and merge evidence count only when they equal records pinned in this
module (VERIFIED_*) by a governed bookkeeping step. Negative fixtures inject one change into an in-memory input copy and
must fail their named PC7 check; positive controls must pass every check. No network, subprocess or frontend is used.
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
BASELINE = "324fc320c47498a42f68c6bac941cc4a5dde9b39"   # P7-WP6 delivery merge (PR #42)
CONTRACT = "contracts/phase7/phase7-closure-v1.json"
SCHEMA = "contracts/phase7/phase7-closure-contract.schema.json"
FIXTURES = "contracts/phase7/fixtures/phase7-closure-negative-mutations.json"
DOC = "docs/00-program/PHASE-7-CLOSURE.md"
GATE = "docs/00-program/GATE-032-phase-7-closure.md"
CHECK_COUNT = 24
STATUS_BY_STATE = {
    "CANDIDATE": "PHASE 7 INTEGRATED CLOSURE CANDIDATE",
    "APPROVED": "PHASE 7 INTEGRATED CLOSURE APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING",
    "CLOSED": "PHASE 7 CLOSED",
}
VERIFIED_REVIEW_HISTORY = [{
    "round": 1, "kind": "INITIAL_INDEPENDENT_REVIEW", "decision": "REQUEST_CHANGES",
    "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 2, "LOW": 0, "INFO": 0},
    "reviewer_role": "Independent reviewer", "record_reference": "GATE-032 §7",
    "evidence_source": "User-supplied P7-WP7 Round 1 review and independently reproduced findings (2026-10-12)",
}, {
    "round": 2, "kind": "TARGETED_INDEPENDENT_REREVIEW", "decision": "APPROVE",
    "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0},
    "reviewer_role": "Independent reviewer", "record_reference": "GATE-032 §7",
    "evidence_source": "User-supplied P7-WP7 targeted Round 2 APPROVE; both findings independently closed (2026-10-12)",
}]
VERIFIED_APPROVAL = {"round": 2, "decision": "APPROVE", "record_reference": "GATE-032 §7", "reviewer_role": "Independent reviewer"}
VERIFIED_MERGE_EVIDENCE = {
    "repository": "nishanth-cryptos/TrustLens",
    "pr_number": 43,
    "pr_head_commit": "5af988d2740c4d826abc0f2e3074cd1fe3d28526",
    "merge_commit": "0a21d1f858eb7680e05ce703966201f06902e4c8",
    "base_commit": BASELINE,
    "remote_ci": {
        "workflow": "knowledge-validation",
        "checks": ["Knowledge validation suite", "Quality-gate self-test (gate must bite)"],
        "conclusion": "success",
        "pr_head_run_id": 38266862243,
        "merge_commit_run_id": 38273120361,
    },
    "verification": "READ_ONLY_GITHUB_VERIFICATION",
    "verification_reference": "GATE-032 §8",
}
VERIFIED_PROGRAMME_ACCEPTANCE = {
    "decision": "OPTION_A_ACCEPTED",
    "accepted_by": "User (programme sponsor)",
    "authority_reference": "PROGRAM-001 §4.1",
    "evidence_source": "User's explicit Option A decision in the P7-WP7 Final Acceptance Bookkeeping request (2026-10-12)",
    "record_reference": "GATE-032 §6",
    "deviation_ids": ["P7D-01", "P7D-02"],
    "scope": "DESIGN_CONTRACT_CLOSURE_ONLY",
    "future_deliverables_waived": False,
}
INDEPENDENT_REVIEW_KINDS = {"INITIAL_INDEPENDENT_REVIEW", "TARGETED_INDEPENDENT_REREVIEW", "FINAL_INDEPENDENT_REVIEW"}
REVIEW_RECORD = "GATE-032 §7"
REVIEW_HEADING = "## 7. Independent review record"
FINDING_DISPOSITIONS = {"CORRECTED_PENDING_TARGETED_REREVIEW", "OPEN_CARRIED", "OPEN_INFORMATIONAL", "CLOSED_BY_REREVIEW"}

UX = {"UX-001": "contracts/ux/ux-foundation-v1.json", "UX-002": "contracts/ux/ux-intake-v1.json", "UX-003": "contracts/ux/ux-result-v1.json",
      "UX-004": "contracts/ux/ux-review-v1.json", "UX-005": "contracts/ux/ux-reporting-v1.json", "UX-006": "contracts/ux/ux-accessibility-v1.json"}
GATES = {"UX-001": "GATE-026", "UX-002": "GATE-027", "UX-003": "GATE-028", "UX-004": "GATE-029", "UX-005": "GATE-030", "UX-006": "GATE-031"}
CANONICAL_VALIDATORS = {"UX-001": "validate_ux_foundation.py", "UX-002": "validate_ux_intake.py", "UX-003": "validate_ux_result.py",
                        "UX-004": "validate_ux_review.py", "UX-005": "validate_ux_reporting.py", "UX-006": "validate_ux_accessibility.py"}
ARTIFACT_KINDS = ("contracts/ux/", "contracts/ux/fixtures/", "docs/07-ux/", "docs/00-program/GATE-", "knowledge/validation/")
# P7-WP1 merge record, independently verified on GitHub by the builder for this closure; UX-001 itself stays frozen.
WP1_MERGE_EVIDENCE = {"pr_number": 34, "pr_head_commit": "1d99bcc88004d36115f2ea501cdde8755f2f87d5",
                      "merge_commit": "d16ee7a8fd65a0428a0cde7cc1dceb7bd166d528", "base_commit": "bbe741b8ebfb7adbc399c1231b74f67f73ba2cfc",
                      "pr_head_run_id": 37309265948, "merge_commit_run_id": 37309298428}
WP1_FROZEN_STATUS = "P7-WP1 UX FOUNDATION APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING"
TARGET_PHASES = {"PHASE_8", "PHASE_9", "PHASE_10", "PROGRAMME"}
DISPOSITIONS = {"CARRIED", "SUPERSEDED_BY", "RESOLVED_BY"}
COVERAGE = {"DETAILED", "FOUNDATION_SURFACE", "NOT_DESIGNED"}
ROADMAP_COMMITMENTS = {"REPORT-001": "OUTPUT_NOT_PRODUCED", "WCAG 2.2 AA": "GATE_CRITERION_NOT_VERIFIED"}
# Controlled wording for four security/closure claims, not a natural-language parser. These values restate
# roadmap Phase 7/8, RSK-006, UX-001#0, UX-005#0 and UX-006#6. All other prose keeps its existing flexibility.
GOVERNED_STATEMENTS = {
    "REPORT-001": {
        "Phase 7 did not produce REPORT-001; the report format remains deferred and report content is opaque bytes",
        "REPORT-001 is undelivered; Phase 8 must define the unresolved report format before planning the report implementation slice; report content remains opaque bytes",
    },
    "WCAG 2.2 AA": {
        "Accessibility is specified as design requirements only; conformance with WCAG 2.2 AA is not claimed or tested",
        "WCAG 2.2 AA is NOT VERIFIED; Phase 7 provides design requirements only; Phase 10 owns accessibility conformance testing and evidence",
    },
    "RSK-006": {
        "Docker and PostgreSQL must be installed before Phase 9 implementation can begin (roadmap: resolve in Phase 8)",
        "Phase 8 must resolve RSK-006: Docker and PostgreSQL installation is required before Phase 9 implementation begins",
    },
}
GOVERNED_OWNERS = {
    "UX-001#0": {
        "Security Architect (browser session / CSRF profile before any browser implementation; PLAN-001 prerequisite)",
        "Security Architect (Phase 8 / PLAN-001: decide the unresolved browser session / CSRF profile before browser implementation)",
    },
    "UX-005#0": {"Product / Reporting (REPORT-001 must be produced before the report slice is planned)"},
    "UX-006#6": {"Phase 10 / QA Lead (assistive-technology and conformance testing)"},
}
RESPONSIVE_DECISIONS = {"UX-001#6", "UX-003#6", "UX-004#8", "UX-005#7"}
RESPONSIVE_TARGET = "UX-006#1"
RESPONSIVE_OWNER = "Phase 9 design system with Product / Accessibility UX"
CLAIMS = {"phase7_closed", "frontend_implemented", "backend_implemented", "api_changed", "accessibility_conformance", "usability_tested",
          "production_ready", "detection_effectiveness", "independently_reviewed", "approved", "phase8_started"}
NOT_CLAIMED = ("frontend_implemented", "api_implemented", "production_ready", "accessibility_compliant", "usability_tested", "security_tested")
DOC_PROJECTIONS = ["work_packages", "handoffs", "coverage_gaps", "decisions", "disposition_counts", "phase8", "deviations", "programme_acceptance", "carryovers"]
GATE_PROJECTIONS = ["disposition_counts", "deviations", "programme_acceptance", "carryovers", "review_history", "findings"]
PREMATURE = {
    re.compile(r"Phase 7 (is |was |has been |has )?(closed|complete)", re.I): {"CLOSED"},
    re.compile(r"(P7-WP7|integrated closure) (is |was |has been |has )?(approved|accepted)", re.I): {"APPROVED", "CLOSED"},
    re.compile(r"Phase 8 (is |was |has been |has )?(started|in progress|complete)", re.I): set(),
    re.compile(r"(meets|conforms to|complies with|compliant with|achieves) WCAG", re.I): set(),
    re.compile(r"\b(production[- ]ready|detection effectiveness (is )?(proven|demonstrated))", re.I): set(),
}
NEGATION = re.compile(r"\b(not|no|none|nor|never|until|only after|cannot|before)\b", re.I)


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


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def closed_local_schema(schema):
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


def keyed(rows, field):
    out = {}
    for r in rows:
        if r[field] in out:
            raise ValueError(f"duplicate {field} {r[field]}")
        out[r[field]] = r
    return out


def table(headers, rows):
    def cell(value):
        if isinstance(value, list):
            value = ", ".join(str(x) for x in value) or "—"
        if value is None or value == "":
            value = "—"
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(cell(x) for x in row) + " |" for row in rows])


def projections(d):
    """Tables PHASE-7-CLOSURE and GATE-032 must carry verbatim between <!-- PC7:name --> markers."""
    carried = [x for x in d["decision_register"] if x["disposition"] == "CARRIED"]
    phase8 = ([[x["target_phase"], x["id"], x["decision"], x["carried_owner"]] for x in carried]
              + [[g["target_phase"], g["id"], g["gap"], g["carried_owner"]] for g in d["integration_gaps"]]
              + [["PHASE_8 prerequisite", p["id"], p["statement"], p["owner"]] for p in d["phase8_prerequisites"]])
    order = {"PHASE_8 prerequisite": 0, "PHASE_8": 1, "PHASE_9": 2, "PHASE_10": 3, "PROGRAMME": 4}
    return {
        "work_packages": table(["Work package", "Contract", "Gate", "Effective state", "Final review", "PR", "Merge commit", "PR-head run", "Merge run", "Record"],
                               [[w["work_package"], w["contract_id"], w["gate"], w["effective_state"], w["final_review"], w["pr_number"],
                                 (w["merge_commit"] or "")[:7], w["pr_head_run_id"], w["merge_commit_run_id"], w["record"]] for w in d["work_packages"]]),
        "handoffs": table(["Handoff", "Consumed by", "Scope"], [[h["work_package"], h["consumed_by"], h["scope"]] for h in d["handoffs"]]),
        "coverage_gaps": table(["Coverage", "Operations"], [[k, [x["operation_id"] for x in d["operation_coverage"] if x["coverage"] == k]]
                                                            for k in ("FOUNDATION_SURFACE", "NOT_DESIGNED")]),
        "decisions": table(["Decision", "Text", "Source owner", "Disposition", "Target", "Carried owner / reference"],
                           [[x["id"], x["decision"], x["source_owner"], x["disposition"], x["target_phase"],
                             x["carried_owner"] or x["superseded_by"] or x["resolved_by"]] for x in d["decision_register"]]),
        "disposition_counts": table(["Disposition", "Count"], [[k, v] for k, v in d["decision_disposition_counts"].items()]),
        "phase8": table(["Target", "Item", "Description", "Owner"], sorted(phase8, key=lambda r: (order.get(r[0], len(order)), str(r[0]), r[1]))),
        "deviations": table(["Deviation", "Roadmap item", "Kind", "Statement", "Linked decision", "Target", "Status", "Programme acceptance"],
                            [[x["id"], x["roadmap_item"], x["kind"], x["statement"], x["linked_decision"], x["target_phase"],
                              x["status"], x["programme_acceptance"]] for x in d["roadmap_deviations"]]),
        "programme_acceptance": table(["Acceptance field", "Value"],
                                      list((d["programme_acceptance_record"] or {"decision": "PENDING_PROGRAMME_ACCEPTANCE"}).items())),
        "carryovers": table(["Item", "Status", "Owner"], [[k, v["status"], v["owner"]] for k, v in d["carryovers"].items()]),
        "review_history": table(["Round", "Kind", "Decision", "BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO", "Reviewer role", "Evidence source", "Record"],
                                [[h["round"], h["kind"], h["decision"], *[h["counts"][k] for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")],
                                  h["reviewer_role"], h["evidence_source"], h["record_reference"]] for h in d["lifecycle"]["review_history"]]),
        "findings": table(["Finding", "Round", "Severity", "Summary", "Disposition", "Closed in round", "Owner"],
                          [[x["id"], x["round"], x["severity"], x["summary"], x["disposition"], x["closed_in_round"], x["owner"]] for x in d["review_findings"]]),
    }


def load_inputs():
    snapshot = read_json("contracts/phase6/phase6-closure-v1.json")
    closure = read_json(CONTRACT)
    hashed = [a["path"] for a in snapshot["snapshot"]["artifacts"]] + [a["path"] for a in closure["snapshot"]]
    hashed += [p for ps in ([v, v.replace("-v1.json", "-contract.schema.json")] for v in UX.values()) for p in ps]
    return dict(contract=closure, schema=read_json(SCHEMA),
                doc=(ROOT / DOC).read_text(encoding="utf-8") if (ROOT / DOC).exists() else "",
                gate=(ROOT / GATE).read_text(encoding="utf-8") if (ROOT / GATE).exists() else "",
                ux={k: read_json(v) for k, v in UX.items()}, api=read_json("contracts/api/api-v1.json"),
                roadmap=(ROOT / "docs/00-program/roadmap.md").read_text(encoding="utf-8"),
                risks=(ROOT / "docs/00-program/risk-register.md").read_text(encoding="utf-8"),
                run_all=(ROOT / "knowledge/validation/run_all.py").read_text(encoding="utf-8"),
                engine=(ROOT / "knowledge/runtime/engine.py").read_text(encoding="utf-8"), snapshot=snapshot,
                hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in dict.fromkeys(hashed) if (ROOT / p).exists()},
                pins=copy.deepcopy(dict(review_history=VERIFIED_REVIEW_HISTORY, approval=VERIFIED_APPROVAL,
                                        merge_evidence=VERIFIED_MERGE_EVIDENCE, programme_acceptance=VERIFIED_PROGRAMME_ACCEPTANCE)))


def validate(ctx):
    d, api, ux = ctx["contract"], ctx["api"], ctx["ux"]
    f = ux["UX-001"]
    lc = d["lifecycle"]
    pins = ctx["pins"]
    api_ops = {o["operation_id"]: o for o in api["operations"]}
    public = sorted(k for k, o in api_ops.items() if not o.get("internal"))
    results = []

    def check(n, description, test):
        try:
            passed = bool(test())
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration):
            passed = False
        results.append({"check_id": f"PC7-{n:02d}", "description": description, "passed": passed})

    def decisions_of(cid):
        return ux[cid]["open_design_decisions"] if cid == "UX-001" else ux[cid]["open_decisions"]

    def lifecycle_ok():
        st, hist = lc["state"], lc["review_history"]
        if lc["status"] != STATUS_BY_STATE.get(st) or lc["decision_vocabulary"] != ["APPROVE", "REQUEST_CHANGES"] or hist != pins["review_history"]:
            return False
        for i, h in enumerate(hist):
            if not (h["round"] == i + 1 and h["kind"] in INDEPENDENT_REVIEW_KINDS and h["decision"] in ("APPROVE", "REQUEST_CHANGES")
                    and h["record_reference"] == REVIEW_RECORD and h["reviewer_role"] == "Independent reviewer"):
                return False
        approving = bool(hist) and hist[-1]["decision"] == "APPROVE"
        cl = d["claims"]
        if st == "CANDIDATE":
            return (not approving and lc["approval"] is None and lc["merge_evidence"] is None and cl["approved"] is False
                    and cl["phase7_closed"] is False and cl["independently_reviewed"] is bool(hist))
        if not approving or pins["approval"] is None or lc["approval"] != pins["approval"] or cl["approved"] is not True:
            return False
        if st == "APPROVED":
            return lc["merge_evidence"] is None and cl["phase7_closed"] is False
        me = lc["merge_evidence"]
        return (st == "CLOSED" and pins["merge_evidence"] is not None and me == pins["merge_evidence"] and me["base_commit"] == BASELINE
                and d["programme_acceptance_record"] is not None and cl["phase7_closed"] is True
                and f"## {me['verification_reference'].split('§')[1]}. " in ctx["gate"])

    def freeze():
        snap = {a["path"]: a["sha256"] for a in ctx["snapshot"]["snapshot"]["artifacts"]}
        return (ctx["snapshot"]["closure_status"] == "PHASE 6 CLOSED" and len(snap) == 19 and all(ctx["hashes"].get(p) == h for p, h in snap.items())
                and re.search(r'^ENGINE_VERSION = "1\.0\.0"$', ctx["engine"], re.M) is not None and d["engine_version"] == "1.0.0"
                and all(u["engine_version"] == "1.0.0" for u in ux.values()))

    def snapshot_ok():
        snap = keyed(d["snapshot"], "path")
        expected = {p for v in UX.values() for p in (v, v.replace("-v1.json", "-contract.schema.json"))}
        by_contract = {}
        for a in d["snapshot"]:
            by_contract.setdefault(a["contract_id"], []).append(a["path"])
        return (expected <= set(snap) and set(by_contract) == set(UX)
                and all(len(ps) == 6 and any(GATES[cid] in p for p in ps) and any(CANONICAL_VALIDATORS[cid] in p for p in ps) for cid, ps in by_contract.items())
                and all(p.startswith(ARTIFACT_KINDS) for p in snap) and all(ctx["hashes"].get(p) == a["sha256"] for p, a in snap.items()))

    def register_ok():
        reg = keyed(d["work_packages"], "contract_id")
        if list(reg) != list(UX):
            return False
        w1 = reg["UX-001"]
        if not (w1["work_package"] == f["work_package"] == "P7-WP1" and w1["effective_state"] == "MERGED_CI_VERIFIED" and f["status"] == WP1_FROZEN_STATUS
                and w1["contract_status"] == f["status"] and w1["final_review"] == "APPROVE" and w1["record"] == "PHASE-7-CLOSURE §2"
                and all(w1[k] == v for k, v in WP1_MERGE_EVIDENCE.items())):
            return False
        prev = WP1_MERGE_EVIDENCE["merge_commit"]
        for cid in list(UX)[1:]:
            w, l = reg[cid], ux[cid]["lifecycle"]
            me = l["merge_evidence"] or {}
            rc = me.get("remote_ci") or {}
            if not (w["work_package"] == ux[cid]["work_package"] and w["gate"] == GATES[cid] and w["effective_state"] == l["state"]
                    and w["contract_status"] == l["status"] and w["final_review"] == (l["approval"] or {}).get("decision") == "APPROVE"
                    and w["pr_number"] == me.get("pr_number") and w["merge_commit"] == me.get("merge_commit") and w["pr_head_commit"] == me.get("pr_head_commit")
                    and w["base_commit"] == me.get("base_commit") and w["pr_head_run_id"] == rc.get("pr_head_run_id")
                    and w["merge_commit_run_id"] == rc.get("merge_commit_run_id") and w["record"] == me.get("verification_reference")):
                return False
            if l["state"] == "CLOSED" and not (rc.get("conclusion") == "success" and me.get("verification_reference", "").startswith(GATES[cid])):
                return False
        return True

    def all_closed():
        """Integrated closure requires P7-WP2..P7-WP6 CLOSED and P7-WP1 merged with verified CI."""
        reg = keyed(d["work_packages"], "contract_id")
        return reg["UX-001"]["effective_state"] == "MERGED_CI_VERIFIED" and all(reg[c]["effective_state"] == "CLOSED" for c in list(UX)[1:])

    def handoffs_ok():
        hs = keyed(d["handoffs"], "work_package")
        src = [h["work_package"] for h in f["handoffs"]]
        if list(hs) != src or d["scope"]["owned"] != next(h["scope"] for h in f["handoffs"] if h["work_package"] == "P7-WP7"):
            return False
        for h in f["handoffs"]:
            owner = [cid for cid, u in ux.items() if u["work_package"] == h["work_package"]]
            consumer = owner[0] if owner else "PHASE-7-CLOSURE"
            if hs[h["work_package"]]["consumed_by"] != consumer or hs[h["work_package"]]["scope"] != h["scope"] or len(owner) > 1:
                return False
            if owner and ux[consumer]["scope"]["owned"] != h["scope"]:
                return False
        return True

    def coverage_ok():
        cov = keyed(d["operation_coverage"], "operation_id")
        if sorted(cov) != public:
            return False
        refs = {cid: set(strings(u)) for cid, u in ux.items()}
        surf = {o for s in f["surfaces"] for o in s["api_operations"]}
        gaps = keyed(d["integration_gaps"], "id")
        for o in public:
            detailed = [cid for cid in UX if cid != "UX-001" and o in refs[cid]]
            kind = "DETAILED" if detailed else "FOUNDATION_SURFACE" if o in surf else "NOT_DESIGNED"
            x = cov[o]
            if x["coverage"] != kind or x["contracts"] != (detailed or (["UX-001"] if kind == "FOUNDATION_SURFACE" else [])):
                return False
            if (kind == "NOT_DESIGNED") != (x["gap"] is not None) or (x["gap"] and o not in gaps[x["gap"]]["operations"]):
                return False
        designed_gap_ops = {o for g in d["integration_gaps"] for o in g["operations"]}
        return designed_gap_ops == {o for o in public if cov[o]["coverage"] == "NOT_DESIGNED"} and not (surf - set(public))

    def access_consistent():
        """Every operation a Phase-7 contract restates carries the accepted API access; no operation has two owners."""
        owners = {}
        for cid, u in ux.items():
            for o in u.get("operations", []):
                owners.setdefault(o["operation_id"], []).append(cid)
                a = api_ops[o["operation_id"]]
                if any(o.get(k, a[k]) != a[k] for k in ("roles", "resource_authorization", "sensitive_content_permission", "audit", "method", "path")):
                    return False
        for s in f["surfaces"]:
            for acc in s["operation_access"]:
                a = api_ops[acc["operation_id"]]
                if acc["roles"] != a["roles"] or acc["resource_authorization"] != a["resource_authorization"]:
                    return False
        return all(len(v) == 1 for v in owners.values())

    def privacy_consistent():
        """UX-001's global exposure rules are all closed; a contract restating one of them uses the same value, and every
        surface-specific exposure flag is closed except an explicit *_preserved safeguard, which must hold. Tenancy is never
        enabled and retention never given a number, whatever shape each contract uses."""
        base = f["exposure"]
        if not base or any(v is not False for v in base.values()):
            return False
        for u in ux.values():
            for k, v in u.get("exposure", {}).items():
                if (k in base and v != base[k]) or (k not in base and v is not (k.endswith("_preserved"))):
                    return False
            if any(v is not False for v in u.get("tenancy", {}).values() if isinstance(v, bool)):
                return False
            r = u.get("retention", {})
            if r and (r.get("duration") != "NOT YET SPECIFIED" or r.get("numeric_duration_invented") is not False):
                return False
        return all("tenancy" in u and "retention" in u for u in ux.values())

    def claims_consistent():
        cl = d["claims"]
        return (set(cl) == CLAIMS and all(cl[k] is False for k in CLAIMS - {"phase7_closed", "approved", "independently_reviewed"})
                and all(u["claims"].get(k, False) is False for u in ux.values() for k in NOT_CLAIMED + ("detection_effectiveness",)))

    def carryovers_ok():
        """Same items, statuses and owners everywhere (owner compared case-insensitively: UX-001 writes "next governed",
        later contracts "Next governed"); the closure restates the latest contract exactly."""
        norm = lambda u: {k: (v["status"], v["owner"].lower()) for k, v in u["carryovers"].items()}
        return (all(norm(u) == norm(f) for u in ux.values())
                and d["carryovers"] == {k: {"status": v["status"], "owner": v["owner"]} for k, v in ux["UX-006"]["carryovers"].items()})

    def register_complete():
        reg = keyed(d["decision_register"], "id")
        expected = {f"{cid}#{i}": x for cid in UX for i, x in enumerate(decisions_of(cid))}
        return list(reg) == list(expected) and all(reg[k]["decision"] == x["decision"] and reg[k]["source_owner"] == x["owner"]
                                                   and x["status"] == "DEFERRED" for k, x in expected.items())

    def dispositions_ok():
        reg = keyed(d["decision_register"], "id")
        order = list(UX)
        counts = {k: sum(x["disposition"] == k for x in reg.values()) for k in ("CARRIED", "SUPERSEDED_BY", "RESOLVED_BY")}
        if d["decision_disposition_counts"] != counts or sum(counts.values()) != 48:
            return False
        # UX-006 closes behaviour design, while its explicit layout decision remains deferred to Phase 9.
        target = reg[RESPONSIVE_TARGET]
        if (target["disposition"] != "CARRIED" or target["target_phase"] != "PHASE_9"
                or target["carried_owner"] != RESPONSIVE_OWNER or ux["UX-006"]["responsive"]["breakpoint_values"] != "NOT YET SPECIFIED"):
            return False
        for k, x in reg.items():
            src = k.split("#")[0]
            if k in RESPONSIVE_DECISIONS and not (
                    (x["disposition"] == "SUPERSEDED_BY" and x["superseded_by"] == RESPONSIVE_TARGET)
                    or (x["disposition"] == "CARRIED" and x["target_phase"] == "PHASE_9" and x["carried_owner"] == RESPONSIVE_OWNER)):
                return False
            if k == "UX-001#0" and not (x["disposition"] == "CARRIED" and x["target_phase"] == "PHASE_8"
                                                    and x["carried_owner"] in GOVERNED_OWNERS[k]):
                return False
            if x["disposition"] not in DISPOSITIONS:
                return False
            if x["disposition"] == "CARRIED":
                if (x["target_phase"] not in TARGET_PHASES or not x["carried_owner"] or "P7-WP" in x["carried_owner"]
                        or x["superseded_by"] is not None or x["resolved_by"]):
                    return False
            elif x["disposition"] == "SUPERSEDED_BY":
                t = reg.get(x["superseded_by"])
                if (t is None or t["disposition"] != "CARRIED" or order.index(t["id"].split("#")[0]) <= order.index(src)
                        or x["target_phase"] is not None or x["carried_owner"] is not None or x["resolved_by"]):
                    return False
            else:
                wps = set(re.findall(r"P7-WP(\d)", x["source_owner"]))
                if "through" in x["source_owner"]:
                    lo, hi = sorted(int(n) for n in wps)
                    wps = {str(n) for n in range(lo, hi + 1)}
                if (not x["resolved_by"] or x["target_phase"] is not None or x["carried_owner"] is not None or x["superseded_by"] is not None
                        or {ux[c]["work_package"][-1] for c in x["resolved_by"]} != wps
                        or any(c not in ux or ux[c]["lifecycle"]["state"] != "CLOSED" or order.index(c) <= order.index(src) for c in x["resolved_by"])):
                    return False
        return True

    def gaps_ok():
        gaps = keyed(d["integration_gaps"], "id")
        return (set(gaps) == {"P7C-01", "P7C-02"} and all(g["target_phase"] in TARGET_PHASES and g["carried_owner"] and "P7-WP" not in g["carried_owner"]
                                                          for g in gaps.values())
                and gaps["P7C-01"]["operations"] and not gaps["P7C-02"]["operations"] and f["status"] == WP1_FROZEN_STATUS)

    def deviations_ok():
        devs = keyed(d["roadmap_deviations"], "roadmap_item")
        reg = keyed(d["decision_register"], "id")
        section = ctx["roadmap"].split("## Phase 7", 1)[1].split("\n## ", 1)[0]
        acceptance = d["programme_acceptance_record"]
        if acceptance != pins["programme_acceptance"]:
            return False
        status, accepted = ("PROPOSED", "PENDING_PROGRAMME_ACCEPTANCE") if acceptance is None else ("ACCEPTED", "ACCEPTED_OPTION_A")
        if acceptance is not None and not (acceptance["decision"] == "OPTION_A_ACCEPTED"
                                          and acceptance["deviation_ids"] == ["P7D-01", "P7D-02"]
                                          and acceptance["scope"] == "DESIGN_CONTRACT_CLOSURE_ONLY"
                                          and acceptance["future_deliverables_waived"] is False):
            return False
        return (set(devs) == set(ROADMAP_COMMITMENTS) and all(item in section for item in ROADMAP_COMMITMENTS)
                and all(devs[i]["kind"] == k and reg[devs[i]["linked_decision"]]["disposition"] == "CARRIED"
                        and reg[devs[i]["linked_decision"]]["target_phase"] == devs[i]["target_phase"] for i, k in ROADMAP_COMMITMENTS.items())
                and all(devs[i]["statement"] in GOVERNED_STATEMENTS[i] and devs[i]["status"] == status
                        and devs[i]["programme_acceptance"] == accepted for i in ROADMAP_COMMITMENTS)
                and all(devs[item]["linked_decision"] == sid and devs[item]["target_phase"] == phase
                        and reg[sid]["carried_owner"] in GOVERNED_OWNERS[sid]
                        for item, sid, phase in (("REPORT-001", "UX-005#0", "PHASE_8"), ("WCAG 2.2 AA", "UX-006#6", "PHASE_10")))
                and "REPORT-001" in reg[devs["REPORT-001"]["linked_decision"]]["decision"]
                and "conformance" in reg[devs["WCAG 2.2 AA"]["linked_decision"]]["decision"].lower()
                and d["claims"]["accessibility_conformance"] is False and not ux["UX-006"]["accessibility"]["conformance_claim"])

    def prerequisites_ok():
        pre = keyed(d["phase8_prerequisites"], "id")
        return (set(pre) == {"RSK-006"} and pre["RSK-006"]["statement"] in GOVERNED_STATEMENTS["RSK-006"]
                and pre["RSK-006"]["owner"] == "Sponsor (admin install)"
                and "RSK-006" in ctx["risks"] and "RSK-006" in ctx["roadmap"]
                and "Docker and PostgreSQL installation is required before Phase 9 can begin." in ctx["roadmap"]
                and "Docker and PostgreSQL absent." in ctx["risks"])

    def canonical_wired():
        order = re.findall(r'\("knowledge/validation/(\w+\.py)"', ctx["run_all"])
        own = "validate_phase7_closure.py"
        return (own in order and all(v in order and order.index(v) < order.index(own) for v in CANONICAL_VALIDATORS.values())
                and order.index("validate_phase6_closure.py") < order.index(CANONICAL_VALIDATORS["UX-001"]))

    def documentary_parity():
        proj = projections(d)
        return (all(f"<!-- PC7:{n}:BEGIN -->\n{proj[n]}\n<!-- PC7:{n}:END -->" in ctx["doc"] for n in DOC_PROJECTIONS)
                and all(f"<!-- PC7:{n}:BEGIN -->\n{proj[n]}\n<!-- PC7:{n}:END -->" in ctx["gate"] for n in GATE_PROJECTIONS))

    def projection_structure(text, names):
        seen, fence, open_name = [], False, None
        for ln in text.splitlines():
            if re.match(r"^ {0,3}(```|~~~)", ln):
                fence = not fence
            m = re.fullmatch(r"<!-- PC7:(\w+):(BEGIN|END) -->", ln)
            if m:
                if fence or (m.group(2) == "BEGIN") == (open_name is not None) or (m.group(2) == "END" and m.group(1) != open_name):
                    return False
                open_name = m.group(1) if m.group(2) == "BEGIN" else None
                if m.group(2) == "BEGIN":
                    seen.append(m.group(1))
            elif "PC7:" in ln:
                return False
        return open_name is None and not fence and sorted(seen) == sorted(names)

    def no_premature_claims():
        lines = ctx["doc"].splitlines() + ctx["gate"].splitlines()
        return not [ln for ln in lines for pat, allowed in PREMATURE.items() if pat.search(ln) and lc["state"] not in allowed and not NEGATION.search(ln)]

    def gate_decision():
        row = next(ln for ln in ctx["gate"].splitlines() if ln.startswith("| Deliverable |"))
        return (ctx["gate"].count(f"**{lc['status']}**") == 1
                and all(x in row for x in ("PHASE-7-CLOSURE", "phase7-closure-v1.json", "phase7-closure-contract.schema.json",
                                           "phase7-closure-negative-mutations.json", "validate_phase7_closure.py")))

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
            if x["round"] not in rounds or x["disposition"] not in FINDING_DISPOSITIONS or closed != (x["closed_in_round"] is not None):
                return False
            if closed and not (x["closed_in_round"] in rounds and x["closed_in_round"] > x["round"]
                               and rounds[x["closed_in_round"]]["decision"] == "APPROVE"):
                return False
            if x["severity"] in ("BLOCKER", "HIGH", "MEDIUM") and not closed and (approved or x["disposition"] != "CORRECTED_PENDING_TARGETED_REREVIEW"):
                return False
        return True

    check(1, "PHASE-7-CLOSURE identity and status row follow the recorded lifecycle",
          lambda: "| Document ID | PHASE-7-CLOSURE |" in ctx["doc"] and f"| Status | {lc['status']} |" in ctx["doc"])
    check(2, "GATE-032 identity and status row follow the recorded lifecycle",
          lambda: "| Document ID | GATE-032 |" in ctx["gate"] and f"| Status | {lc['status']} |" in ctx["gate"])
    check(3, "Closure record valid against a closed, local-only schema", lambda: schema_valid(d, ctx["schema"]))
    check(4, "Exact baseline and work-package identity",
          lambda: d["baseline"] == BASELINE and BASELINE in ctx["doc"] and BASELINE in ctx["gate"] and d["work_package"] == "P7-WP7"
          and d["closure_id"] == "PHASE-7-CLOSURE" and d["gate"] == "GATE-032" and d["phase"] == f["phase"])
    check(5, "Lifecycle fail-closed: review records, approval and merge evidence only as pinned governed records", lifecycle_ok)
    check(6, "Phase-6 snapshot (19 artifacts) intact; ENGINE_VERSION 1.0.0 in the engine and every Phase-7 contract", freeze)
    check(7, "Phase-7 artifact snapshot: six deliverables per work package (contract, schema, fixtures, document, gate, canonical validator), hashes current", snapshot_ok)
    check(8, "Work-package register equals each contract's lifecycle and merge record; P7-WP1 merge and CI pinned here", register_ok)
    check(9, "P7-WP2..P7-WP6 CLOSED and P7-WP1 merged with verified CI before integrated closure", all_closed)
    check(10, "Every UX-001 handoff consumed exactly once with an equal scope; P7-WP7 owns integrated closure", handoffs_ok)
    check(11, "Every public API operation accounted for exactly once; operations not designed carried as an integration gap", coverage_ok)
    check(12, "Operation access in every Phase-7 contract equals the accepted API; no operation has two owners", access_consistent)
    check(13, "Exposure, tenancy and retention agree across Phase-7 contracts; nothing exposed", privacy_consistent)
    check(14, "No implementation, conformance, testing, production or effectiveness claim in the closure or any Phase-7 contract", claims_consistent)
    check(15, "Programme carryovers identical across UX-001..UX-006 and the closure", carryovers_ok)
    check(16, "Every deferred decision of UX-001..UX-006 registered once, verbatim", register_complete)
    check(17, "Decision dispositions and counts consistent; responsive details remain with Phase 9 and session/CSRF is a Phase-8 prerequisite before browser implementation", dispositions_ok)
    check(18, "Closure-level integration gaps carried to non-Phase-7 owners", gaps_ok)
    check(19, "Unmet roadmap Phase-7 commitments (REPORT-001, WCAG 2.2 AA) recorded as deviations and carried, never claimed", deviations_ok)
    check(20, "Phase-8 prerequisite RSK-006 (Docker and PostgreSQL) carried", prerequisites_ok)
    check(21, "Every Phase-7 canonical validator runs in run_all before this gate", canonical_wired)
    check(22, "PHASE-7-CLOSURE and GATE-032 projections equal the closure record; each exactly once, outside fences",
          lambda: documentary_parity() and projection_structure(ctx["doc"], DOC_PROJECTIONS) and projection_structure(ctx["gate"], GATE_PROJECTIONS))
    check(23, "Closure wording follows the recorded lifecycle; GATE-032 deliverable row and single decision line",
          lambda: no_premature_claims() and gate_decision())
    check(24, "Review findings equal the recorded rounds; dispositions and the GATE-032 §7 record consistent", findings_ok)
    assert len(results) == CHECK_COUNT
    return results


TARGETS = {"contract", "schema", "doc", "gate", "api", "roadmap", "risks", "run_all", "engine", "hashes", "snapshot", "pins", "ux"}


def mutate(ctx, fixture):
    """Strict JSON-pointer / text mutation dialect (as the Phase-7 work-package validators); "steps" applies a sequence."""
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
            print(f"PHASE 7 CLOSURE: FAIL — {len(failed)}/{CHECK_COUNT} checks failed")
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
            # Semantic fixtures must stay schema-valid and synchronized, so neither validation layer can hide a bypass.
            incidental = (rejected & {"PC7-03", "PC7-22"}) - {fixture["expected_check"]}
            if fixture["expected_check"] not in rejected or incidental:
                bad.append(fixture["id"])
                print(f"FAIL {fixture['id']} expected {fixture['expected_check']}; got {sorted(rejected)}; "
                      f"incidental schema/parity failures {sorted(incidental)}")
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
            print(f"PHASE 7 CLOSURE: FAIL — mutations {len(ids) - len(bad)}/{len(ids)}; positive controls {len(pos_ids) - len(pos_bad)}/{len(pos_ids)}")
            return 1
        print(f"PHASE 7 CLOSURE: PASS — {CHECK_COUNT}/{CHECK_COUNT} checks; {len(ids)}/{len(ids)} negative mutations rejected by intended "
              f"checks; {len(pos_ids)}/{len(pos_ids)} positive controls accepted (integrated static closure validation; no frontend or "
              f"runtime exists)")
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"PHASE 7 CLOSURE: FAIL — invalid or missing input: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
