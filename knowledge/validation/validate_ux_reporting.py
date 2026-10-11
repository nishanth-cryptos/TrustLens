"""P7-WP5 deterministic offline reporting and historical-workflow UX checks (UXP-01..UXP-41).

Builder verification, not independent review or runtime testing. Reads the accepted authorities (UX-001 foundation, the
closed UX-002..UX-004 packages, the closed Phase-6 API catalog and OpenAPI) without editing them.

Every owned operation must equal the accepted API exactly. Reports are case-scoped, source-pinned, never regenerated from
latest material and never transmitted automatically; replay is exact historical verification whose unavailable material
is an explicit outcome, never a fallback to re-analysis; re-analysis and user correction create NEW evaluations and never
modify history; governed deletion keeps request, administrator decision, execution and completion distinct, and only
completed removal claims completion; 410 governed removal stays distinct from 404 not found or not visible; historical
comparison has no API capability and is never computed. The report-content matrix and the pinned scenarios are re-derived
by an independent decision procedure built from the API's own resource authorization, modes and audit requirements.

Lifecycle is fail-closed without parsing Markdown review prose: review records, approval and merge evidence count only
when they equal the records pinned in this module (VERIFIED_*) by a governed bookkeeping step. Protected copy is bound to
a closed set of governed messages and to narrow semantic invariants. Governed projections must appear exactly once and
outside fences, and no visible GFM table outside them may act as a reporting-policy table.

Negative fixtures inject one change (or a synchronized sequence of steps) into an in-memory input copy and must fail
their named UXP check, not merely any check; positive controls must pass every check. No network, subprocess or frontend
is used.
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
BASELINE = "b5a663a6dd6343b17b7cf8dfa927c0aae4f8ebd9"   # P7-WP4 closure merge (PR #40)
CONTRACT = "contracts/ux/ux-reporting-v1.json"
SCHEMA = "contracts/ux/ux-reporting-contract.schema.json"
FIXTURES = "contracts/ux/fixtures/reporting-negative-mutations.json"
DOC = "docs/07-ux/UX-005-reporting-historical-workflows.md"
GATE = "docs/00-program/GATE-030-phase-7-reporting-historical-workflows.md"
CHECK_COUNT = 41
STATUS_BY_STATE = {
    "CANDIDATE": "P7-WP5 REPORTING AND HISTORICAL WORKFLOWS UX CANDIDATE",
    "APPROVED": "P7-WP5 REPORTING AND HISTORICAL WORKFLOWS UX APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING",
    "CLOSED": "P7-WP5 REPORTING AND HISTORICAL WORKFLOWS UX CLOSED",
}
# Governed lifecycle pins: a review round, the approval and the merge evidence count only when a governed bookkeeping
# step has pinned the exact record here from programme-supplied evidence; until then the lifecycle fails closed.
# Round 1 (GATE-030 §7): the independent review result supplied to the builder by the programme.
VERIFIED_REVIEW_HISTORY: list = [
    {"round": 1, "kind": "INITIAL_INDEPENDENT_REVIEW", "decision": "REQUEST_CHANGES",
     "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 2, "LOW": 0, "INFO": 0},
     "reviewer_role": "Independent reviewer", "record_reference": "GATE-030 §7",
     "evidence_source": "Independent review result supplied to the builder by the programme"},
    {"round": 2, "kind": "TARGETED_INDEPENDENT_REREVIEW", "decision": "REQUEST_CHANGES",
     "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 1, "LOW": 0, "INFO": 0},
     "reviewer_role": "Independent reviewer", "record_reference": "GATE-030 §7",
     "evidence_source": "Independent review result supplied to the builder by the programme"},
    {"round": 3, "kind": "TARGETED_INDEPENDENT_REREVIEW", "decision": "APPROVE",
     "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0},
     "reviewer_role": "Independent reviewer", "record_reference": "GATE-030 §7",
     "evidence_source": "Independent review result supplied to the builder by the programme"},
]
# The independent approval of round 3 (GATE-030 §7). CLOSED additionally needs merge evidence pinned post-merge.
VERIFIED_APPROVAL = {"round": 3, "decision": "APPROVE", "record_reference": "GATE-030 §7", "reviewer_role": "Independent reviewer"}
VERIFIED_MERGE_EVIDENCE = None
INDEPENDENT_REVIEW_KINDS = {"INITIAL_INDEPENDENT_REVIEW", "TARGETED_INDEPENDENT_REREVIEW", "FINAL_INDEPENDENT_REVIEW"}
INDEPENDENT_REVIEWER_ROLES = {"Independent reviewer"}
PERMITTED_EVIDENCE_SOURCES = {"Independent review result supplied to the builder by the programme"}
REVIEW_RECORD = "GATE-030 §7"
REVIEW_HEADING = "## 7. Independent review record"
FINDING_DISPOSITIONS = {"CORRECTED_PENDING_TARGETED_REREVIEW", "OPEN_CARRIED", "OPEN_INFORMATIONAL", "CLOSED_BY_REREVIEW"}

# Predecessor freeze: the P7-WP1..WP4 deliverables at the baseline (closure bookkeeping, not a snapshot expansion).
PREDECESSOR_PINS = {
    'contracts/ux/ux-foundation-v1.json': '2a1a058028f4cf50597dc787aa4f18fa0f8364752818474ccb9cfa5a43aa7430',
    'contracts/ux/ux-intake-v1.json': 'be4a2933a1153549233813e4bf16a349aff578f66f29dd7db58425241706a83a',
    'contracts/ux/ux-result-v1.json': 'c8f63807165bbd1983f31d459d1281e46b77ff917ffd728c5cec034435951862',
    'contracts/ux/ux-review-v1.json': '86e029b42144191cfbaff536c74c4db5cc8ae173d38e2bd9eedf9692b3e8421a',
    'docs/07-ux/UX-001-experience-foundation-information-architecture.md': '622f1a1a59dd5658e3f6555d164437d0b01c7c84bf3a5f8bbe0d2c5728b750aa',
    'docs/07-ux/UX-002-submission-evidence-intake.md': '6db2f57750593c9dd9e757fcf6e3c9a261d056bfdc3ff52a4fbdd14e74443453',
    'docs/07-ux/UX-003-result-presentation.md': 'c1fc84afbffae3e31e14b2f41b8373e62c5afa6e14eb2954313acfd86c39e9df',
    'docs/07-ux/UX-004-evidence-review-security.md': '04f4642a47abb6c82ae798159e74e34ea251f0bb571bb7968fc1a3aa3a0c3247',
    'docs/00-program/GATE-029-phase-7-evidence-review-security.md': 'fb2d51498eafcd5cb2dbc4bf3071a50ce60720e575b4fd21b5175da5d32879f4',
}
SURFACES = ["UX-REPORTS", "UX-REPORT-CONTENT", "UX-REPLAY", "UX-EVALUATION", "UX-DELETION"]
OWNED = ["createReport", "listReports", "getReport", "getReportContent", "createReplay", "getReplay", "createEvaluations",
         "createCorrection", "createDeletionRequest", "listDeletionRequests", "getDeletionRequest", "authorizeDeletionRequest",
         "rejectDeletionRequest"]
OP_KEYS = ("method", "path", "roles", "resource_authorization", "sensitive_content_permission", "break_glass_roles",
           "request_schema", "response_schema", "success_status", "mode", "idempotency", "audit", "audit_event", "sensitivity",
           "concurrency")
ROLES = ["USER", "ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR"]
CASE_RELATIONSHIP = {"USER": "OWNER", "ANALYST": "ASSIGNED_ANALYST"}
ACTION_OPS = {"CREATE_REPORT": "createReport", "LIST_REPORTS": "listReports", "DOWNLOAD_REPORT": "getReportContent",
              "CREATE_REPLAY": "createReplay", "VIEW_REPLAY": "getReplay", "REANALYZE": "createEvaluations",
              "CORRECT": "createCorrection", "REQUEST_DELETION": "createDeletionRequest", "VIEW_DELETION": "getDeletionRequest",
              "AUTHORIZE_DELETION": "authorizeDeletionRequest", "REJECT_DELETION": "rejectDeletionRequest"}
# API-001 §17-§20: conditions known from authorized metadata before any request (no control, no request) ...
PRE_REQUEST_CONDITIONS = {
    ("DOWNLOAD_REPORT", "REGENERATION_UNAVAILABLE"): "REPORT_REGENERATION_UNAVAILABLE",
    ("DOWNLOAD_REPORT", "REMOVED_UNDER_GOVERNANCE"): "REMOVED_UNDER_GOVERNANCE",
    ("CREATE_REPORT", "REMOVED_UNDER_GOVERNANCE"): "REMOVED_UNDER_GOVERNANCE",
    ("CREATE_REPLAY", "REMOVED_UNDER_GOVERNANCE"): "REPLAY_UNAVAILABLE",
    ("CREATE_REPLAY", "EVALUATION_NOT_COMPLETED"): "CONDITIONAL_ON_EVALUATION_STATE",
    ("CREATE_REPORT", "EVALUATION_NOT_COMPLETED"): "CONDITIONAL_ON_EVALUATION_STATE",
    ("CORRECT", "EVALUATION_NOT_COMPLETED"): "CONDITIONAL_ON_EVALUATION_STATE",
}
# ... and outcomes known only from the response.
POST_REQUEST_CONDITIONS = {
    ("VIEW_REPLAY", "REPLAY_MATERIAL_MISSING"): "REPLAY_UNAVAILABLE",
    ("AUTHORIZE_DELETION", "STALE_ETAG"): "STALE_STATE", ("REJECT_DELETION", "STALE_ETAG"): "STALE_STATE",
}
DELETION_VIEW_STATES = {"DELETION_REQUESTED": "REQUESTED", "DELETION_AUTHORIZED": "AUTHORIZED", "DELETION_IN_PROGRESS": "IN_PROGRESS",
                        "DELETION_COMPLETE": "COMPLETE", "DELETION_PARTIALLY_FAILED": "PARTIALLY_FAILED", "DELETION_FAILED": "FAILED",
                        "DELETION_REJECTED": "REJECTED"}
# Round-1 MEDIUM-2: API-001 §26 Matrix H — a deletion request moves REQUESTED -> AUTHORIZED / REJECTED only. Decisions are
# offered only for a request known to be REQUESTED; any other known state stays read-only (no control, no request).
DECISION_ACTIONS = {"AUTHORIZE_DELETION", "REJECT_DELETION"}
DECISION_ELIGIBLE_STATES = {"REQUESTED"}
API_TRANSITION_ROW = "| Deletion request | `.../authorize`, `.../reject` | `REQUESTED` → `AUTHORIZED` / `REJECTED` |"
NEW_EVALUATION_RESPONSES = {"EvaluationBatchAcceptedResponse", "CorrectionAcceptedResponse"}
TOMBSTONE = {"result_availability": "REMOVED_UNDER_GOVERNANCE", "result_request": "410 REMOVED_UNDER_GOVERNANCE",
             "evidence_content_request": "410 REMOVED_UNDER_GOVERNANCE", "report_content_request": "410 REMOVED_UNDER_GOVERNANCE",
             "replay_request": "409 REPLAY_UNAVAILABLE", "report_regeneration": "REGENERATION_UNAVAILABLE"}
PINNED_SOURCES = ["CASE", "EVALUATIONS", "RESULT_DIGESTS", "EVIDENCE_DIGESTS", "BUNDLE_DIGEST", "ENGINE_VERSION", "REPORT_CONTRACT_VERSION"]
RECOVERY_RETRYABILITY = {"RETRY_SAME_REQUEST": "RETRYABLE", "WAIT_THEN_RETRY_SAME_REQUEST": "RETRYABLE",
                         "WAIT_FOR_PENDING_COMMAND": "RETRYABLE", "REFRESH_EVALUATION_STATUS": "RETRYABLE",
                         "CORRECT_REQUEST": "RETRY_WITH_CHANGES", "REAUTHENTICATE_THEN_RETRY": "RETRY_WITH_CHANGES",
                         "REFRESH_THEN_DECIDE": "RETRY_WITH_CHANGES", "REVIEW_THEN_NEW_COMMAND": "RETRY_WITH_CHANGES",
                         "STOP_NO_RETRY": "NOT_RETRYABLE"}
EXTRA_STATES = {"CONDITIONAL_ON_EVALUATION_STATE"}   # resolved from the Evaluation state, never from the code alone
DEFERRED_OWNERS = {"P7-WP6", "Phase 9"}
REQUIRED_DECISIONS = ("Report format", "historical comparison", "data export", "createCorrection", "reason_code", "Retention period")
UX001_CARRIED = ("Report format and source-pinned comparison", "User data export lacks an accepted API operation")
# Round-0 governed protected copy (closed set). A wording change is a governed revision of this table, never a contract edit.
# Round-1 MEDIUM-1: every label AND meaning of the report states, replay outcomes and deletion states is governed.
GOVERNED_TEXT = {
    "reports.state_labels.GENERATING.label": "Generating",
    "reports.state_labels.GENERATING.meaning": "The report is being generated from its pinned sources; nothing is ready yet.",
    "reports.state_labels.GENERATED.label": "Ready",
    "reports.state_labels.GENERATED.meaning": "The report was generated from its pinned sources.",
    "reports.state_labels.FAILED.label": "Generation failed",
    "reports.state_labels.FAILED.meaning": "The report could not be generated.",
    "reports.state_labels.INTEGRITY_FAILED.label": "Integrity check failed",
    "reports.state_labels.INTEGRITY_FAILED.meaning": "The report content did not pass its integrity check and is withheld.",
    "reports.state_labels.REGENERATION_UNAVAILABLE.label": "Cannot be regenerated",
    "reports.state_labels.REGENERATION_UNAVAILABLE.meaning": "A pinned source is no longer available, so the report cannot be reproduced; nothing is approximated.",
    "reports.state_labels.REMOVED_UNDER_GOVERNANCE.label": "Removed under governance",
    "reports.state_labels.REMOVED_UNDER_GOVERNANCE.meaning": "The report was removed through governed deletion; it is not recreated.",
    "reports.content.pre_access_notice": "Downloading this report is recorded in the audit log.",
    "replay.state_labels.PENDING.label": "Replay pending",
    "replay.state_labels.PENDING.meaning": "The replay was accepted and has not finished; no outcome is implied.",
    "replay.state_labels.COMPLETED.label": "Replay finished",
    "replay.state_labels.COMPLETED.meaning": "The replay finished with the outcome shown.",
    "replay.outcome_labels.MATCH.label": "Reproduced exactly",
    "replay.outcome_labels.MATCH.meaning": "Replaying the pinned material produced the recorded result digest.",
    "replay.outcome_labels.MISMATCH.label": "Did not reproduce",
    "replay.outcome_labels.MISMATCH.meaning": "Replaying the pinned material produced a different digest; the recorded result is unchanged.",
    "replay.outcome_labels.FAILED_MISSING_MATERIAL.label": "Replay unavailable: material missing",
    "replay.outcome_labels.FAILED_MISSING_MATERIAL.meaning": "Required pinned material is missing, so the evaluation cannot be replayed.",
    "replay.outcome_labels.FAILED_INTEGRITY.label": "Replay unavailable: integrity failure",
    "replay.outcome_labels.FAILED_INTEGRITY.meaning": "Pinned material failed its integrity check, so the evaluation cannot be replayed.",
    "replay.outcome_labels.FAILED_ENGINE_UNAVAILABLE.label": "Replay unavailable: engine unavailable",
    "replay.outcome_labels.FAILED_ENGINE_UNAVAILABLE.meaning": "The pinned engine version is not available for replay.",
    "replay.outcome_labels.FAILED_BUNDLE_UNAVAILABLE.label": "Replay unavailable: knowledge bundle unavailable",
    "replay.outcome_labels.FAILED_BUNDLE_UNAVAILABLE.meaning": "The pinned knowledge bundle is not available for replay.",
    "reanalysis.notice": "A new analysis creates a new evaluation. Earlier evaluations and results are kept unchanged.",
    "correction.notice": "Your correction creates a new evaluation. The earlier evaluation and its result are kept unchanged.",
    "historical_comparison.notice": "Each evaluation is shown as its own record. No comparison between them is computed.",
    "deletion.state_labels.REQUESTED.label": "Requested",
    "deletion.state_labels.REQUESTED.meaning": "The request was recorded and awaits an administrator decision; nothing has been removed.",
    "deletion.state_labels.AUTHORIZED.label": "Authorized",
    "deletion.state_labels.AUTHORIZED.meaning": "An administrator authorized the request; removal has not started.",
    "deletion.state_labels.IN_PROGRESS.label": "In progress",
    "deletion.state_labels.IN_PROGRESS.meaning": "Governed removal is running; it is not finished.",
    "deletion.state_labels.COMPLETE.label": "Removal complete",
    "deletion.state_labels.COMPLETE.meaning": "Governed removal finished for the requested scope.",
    "deletion.state_labels.PARTIALLY_FAILED.label": "Partly failed",
    "deletion.state_labels.PARTIALLY_FAILED.meaning": "Governed removal covered only part of the scope; it is not complete.",
    "deletion.state_labels.FAILED.label": "Failed",
    "deletion.state_labels.FAILED.meaning": "Governed removal did not complete.",
    "deletion.state_labels.REJECTED.label": "Rejected",
    "deletion.state_labels.REJECTED.meaning": "An administrator rejected the request; nothing was removed.",
}
COMPLETION_WORDS = re.compile(r"\b(deleted|removed|erased|purged|complete|completed|finished|done)\b", re.I)
NEGATED = re.compile(r"\b(not|nothing|no|never|only part|did not|has not|have not)\b", re.I)
NOT_FOUND_WORDING = re.compile(r"\b(not found|does not exist|never existed|cannot be found|unknown)\b", re.I)
APPROXIMATION = re.compile(r"\b(approximat\w*|latest|current version|reconstruct\w*|substitut\w*|regenerated from)\b", re.I)
HISTORY_KEPT = re.compile(r"\bunchanged\b", re.I)
ENGINE_SUBSTITUTION = re.compile(r"\b(current|latest|newest|replac\w*|substitut\w*|instead|fall(s|ing)? back|re-?analy\w*|new evaluation)\b", re.I)
# Round-2 MEDIUM-1: a substitution term is acceptable only inside a clause that explicitly negates it ("The current engine is
# not used for replay."); clauses split at sentence punctuation and at contrastive joins, so "not X but the current engine"
# is still an affirmative substitution.
CLAUSE_BREAK = re.compile(r"[.;:,!?]|\b(but|however|whereas|so|then)\b", re.I)
CLAUSE_NEGATION = re.compile(r"\b(not|never|no|cannot|can't|isn't|aren't|won't|nor)\b", re.I)
PENDING_COMPLETION = re.compile(r"\b(complete|completed|finished|done|succeeded|successful\w*|success)\b", re.I)


def affirmed_substitution(text):
    """True when some clause names a substitution (current/latest engine, replacement, fallback, re-analysis) without
    negating it in the same clause."""
    return any(ENGINE_SUBSTITUTION.search(c) and not CLAUSE_NEGATION.search(c) for c in CLAUSE_BREAK.split(text) if c)
COMPARISON_CLAIM = re.compile(r"\b(improv\w*|better|worse|regress\w*|more accurate|changed from)\b", re.I)
FORBIDDEN_DISPLAY = re.compile(r"\b(safe|safely|safety|harmless|benign|legitimate|guarantee[sd]?|certified|verified|cleared|"
                               r"innocent|guilty|criminal|fraudster|probability|percent(age)?|score)\b", re.I)
PREMATURE = {   # claim wording -> lifecycle states in which it is permitted (implementation and later WPs never are)
    re.compile(r"P7-WP5 (is |was |has been |has )?(approved|accepted)", re.I): {"APPROVED", "CLOSED"},
    re.compile(r"P7-WP5 (is |was |has been |has )?(closed|merged)", re.I): {"CLOSED"},
    re.compile(r"P7-WP5 (is |was |has been |has )?(implemented|complete)", re.I): set(),
    re.compile(r"P7-WP[67] (is |was |has been |has )?(started|in progress|complete)", re.I): set(),
}
NEGATION = re.compile(r"\b(not|no|never|until|only after|cannot)\b", re.I)
EXPOSURES = {"raw_provider_bodies", "credentials_secrets", "connector_topology", "internal_hosts_ips",
             "evidence_store_locators", "raw_evidence_without_permission", "c4_without_permission",
             "execution_fence_tokens", "idempotency_key_material", "audit_equals_activity"}
DOC_PROJECTIONS = ["operations", "errors", "report_content", "labels", "protected_text", "consequences", "scenarios", "decisions", "carryovers"]
GATE_PROJECTIONS = ["carryovers", "decisions", "review_history", "findings"]
GFM_DELIMITER_CELL = re.compile(r"^:?-+:?$")
# A reporting-policy table is recognized by structure and assertions, never by vocabulary alone (P7-WP4 lesson).
POLICY_SUBJECT_HEADER = {"role", "roles", "principal", "principals", "who", "actor", "caller", "operation", "operations",
                         "scenario", "scenarios", "round", "state", "outcome"}
POLICY_ASSERTION_HEADER = {"permission", "permissions", "permitted", "access", "content", "allowed", "download", "offered",
                           "decision", "completion", "claimed", "presented", "regenerated", "replayable", "removed"}
POLICY_ASSERTION_WORDS = {"yes", "no", "y", "n", "true", "false", "allowed", "denied", "permitted", "forbidden", "offered",
                          "shown", "withheld", "complete", "removed"}


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


def protected_texts(d):
    """Protected display fields (each label and each meaning separately) keyed by their governed-text path."""
    out = {}
    for x in d["reports"]["state_labels"]:
        out[f"reports.state_labels.{x['state']}.label"] = x["label"]
        out[f"reports.state_labels.{x['state']}.meaning"] = x["meaning"]
    out["reports.content.pre_access_notice"] = d["reports"]["content"]["pre_access_notice"]
    for x in d["replay"]["state_labels"]:
        out[f"replay.state_labels.{x['state']}.label"] = x["label"]
        out[f"replay.state_labels.{x['state']}.meaning"] = x["meaning"]
    for x in d["replay"]["outcome_labels"]:
        out[f"replay.outcome_labels.{x['outcome']}.label"] = x["label"]
        out[f"replay.outcome_labels.{x['outcome']}.meaning"] = x["meaning"]
    out["reanalysis.notice"] = d["reanalysis"]["notice"]
    out["correction.notice"] = d["correction"]["notice"]
    out["historical_comparison.notice"] = d["historical_comparison"]["notice"]
    for x in d["deletion"]["state_labels"]:
        out[f"deletion.state_labels.{x['state']}.label"] = x["label"]
        out[f"deletion.state_labels.{x['state']}.meaning"] = x["meaning"]
    return out


def norm(text):
    return " ".join(str(text).split())


def projections(d):
    """Human-readable tables that UX-005 and GATE-030 must carry verbatim between <!-- UXP:name --> markers."""
    yes = {True: "yes", False: "no"}
    return {
        "operations": table(["Operation", "Surface", "On UX-001 surface", "Method", "Path", "Roles", "Resource authorization",
                             "Content permission", "Mode", "Audit event", "Concurrency"],
                            [[o["operation_id"], o["surface_id"], yes[o["listed_on_ux001_surface"]], o["method"], o["path"], o["roles"],
                              o["resource_authorization"], o["sensitive_content_permission"], o["mode"], o["audit_event"],
                              o["concurrency"]] for o in d["operations"]]),
        "errors": table(["API error", "HTTP", "Retryability", "Presentation state", "Recovery", "Alternate state"],
                        [[e["error_code"], e["http_status"], e["retryability"], e["presentation_state"], e["recovery"],
                          e["alternate_presentation_state"]] for e in d["error_presentation"]]),
        "report_content": table(["Role", "Case relationship", "Content permission", "Report content"],
                                [[r["principal_role"], r["relationship"], yes[r["permits_evidence_content"]], r["content_action"]]
                                 for r in d["reports"]["content_rows"]]),
        "labels": table(["Vocabulary", "Value", "Label", "Meaning"],
                        [["api_report_state", x["state"], x["label"], x["meaning"]] for x in d["reports"]["state_labels"]] +
                        [["api_replay_state", x["state"], x["label"], x["meaning"]] for x in d["replay"]["state_labels"]] +
                        [["replay_outcome", x["outcome"], x["label"], x["meaning"]] for x in d["replay"]["outcome_labels"]] +
                        [["api_deletion_state", x["state"], x["label"], x["meaning"]] for x in d["deletion"]["state_labels"]]),
        "protected_text": table(["Protected display field", "Governed text"], [[k, v] for k, v in protected_texts(d).items()]),
        "consequences": table(["Operation", "Audit", "Audit event", "Audit notice shown"],
                              [[a["operation_id"], a["audit"], a["audit_event"], yes[a["notice_shown"]]] for a in d["access_consequences"]]),
        "scenarios": table(["Scenario", "Situation", "Action", "Role / relationship / content / condition", "Control", "Request",
                            "Presented as", "Content", "New evaluation", "Completion claimed", "Audit notice"],
                           [[s["id"], s["title"], s["action"],
                             f"{s['context']['principal_role']} / {s['context']['relationship']} / "
                             f"{yes[s['context']['permits_evidence_content']]} / {s['context']['condition']}",
                             yes[s["expected"]["control_offered"]], yes[s["expected"]["request_issued"]], s["expected"]["presentation_state"],
                             s["expected"]["content_delivery"], yes[s["expected"]["new_evaluation"]], yes[s["expected"]["completion_claimed"]],
                             yes[s["expected"]["audit_notice"]]] for s in d["scenarios"]]),
        "decisions": table(["Unresolved decision", "Owner", "Status"], [[x["decision"], x["owner"], x["status"]] for x in d["open_decisions"]]),
        "carryovers": table(["Item", "Status", "Owner"], [[k, v["status"], v["owner"]] for k, v in d["carryovers"].items()]),
        "review_history": table(["Round", "Kind", "Decision", "BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO", "Reviewer role",
                                 "Evidence source", "Record"],
                                [[h["round"], h["kind"], h["decision"], *[h["counts"][k] for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")],
                                  h["reviewer_role"], h["evidence_source"], h["record_reference"]] for h in d["lifecycle"]["review_history"]]),
        "findings": table(["Finding", "Round", "Severity", "Summary", "Disposition", "Closed in round", "Owner"],
                          [[x["id"], x["round"], x["severity"], x["summary"], x["disposition"], x["closed_in_round"], x["owner"]]
                           for x in d["review_findings"]]),
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
    """Bounded recognizer for visible GFM tables: a header line containing '|', then a delimiter row with the same number of
    ':?-+:?' cells (outer pipes optional, indentation at most 3), then rows until a blank line, fence, heading or marker.
    Fenced content and lines in `skip` are not visible tables. Returns [(header_cells, [row_cells, ...])]."""
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
                api_doc=(ROOT / "docs/06-contracts/API-001-api-resource-protocol-contract.md").read_text(encoding="utf-8"),
                engine=(ROOT / "knowledge/runtime/engine.py").read_text(encoding="utf-8"), snapshot=snapshot,
                hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in hashed},
                pins=copy.deepcopy(dict(review_history=VERIFIED_REVIEW_HISTORY, approval=VERIFIED_APPROVAL,
                                        merge_evidence=VERIFIED_MERGE_EVIDENCE)),
                governed_text=dict(GOVERNED_TEXT))


def authorized(op, role, rel, permits):
    """API-001 §3 resource authorization for one principal (no break-glass applies to any P7-WP5 operation).
    Returns None when permitted, otherwise the presentation state of the refusal."""
    if role not in op["roles"]:
        return "ACCESS_DENIED"
    ra = op["resource_authorization"]
    visible = CASE_RELATIONSHIP.get(role) == rel
    if ra == "CASE_ACCESS":
        return None if visible else "NOT_FOUND_OR_NOT_VISIBLE"
    if ra == "CASE_DERIVED_CONTENT":
        return "NOT_FOUND_OR_NOT_VISIBLE" if not visible else (None if permits else "CONTENT_PERMISSION_REQUIRED")
    if ra in ("CASE_OWNER", "DELETION_SCOPE_OWNER"):
        return None if role == "USER" and rel == "OWNER" else "NOT_FOUND_OR_NOT_VISIBLE"
    if ra == "CASE_ASSIGNED_ANALYST_OR_PLATFORM_ADMIN":
        return None if role == "ADMINISTRATOR" or (role == "ANALYST" and rel == "ASSIGNED_ANALYST") else "NOT_FOUND_OR_NOT_VISIBLE"
    if ra == "DELETION_SCOPE_OWNER_OR_PLATFORM_ADMIN":
        return None if role == "ADMINISTRATOR" or (role == "USER" and rel == "OWNER") else "NOT_FOUND_OR_NOT_VISIBLE"
    if ra == "PLATFORM_ADMIN":
        return None if role == "ADMINISTRATOR" else "ACCESS_DENIED"
    return "ACCESS_DENIED"


def decide(api_ops, action, cx):
    """Independent decision procedure from the accepted API: roles, resource authorization, mode, response schema, audit and
    the API-001 §17-§20 conditions. Returns what the UX offers and presents for one action in one context."""
    op = api_ops[ACTION_OPS[action]]
    out = dict(control_offered=False, request_issued=False, presentation_state="ACCESS_DENIED", content_delivery="NONE",
               new_evaluation=False, history_modified=False, completion_claimed=False, audit_notice=False)
    refusal = authorized(op, cx["principal_role"], cx["relationship"], cx["permits_evidence_content"])
    if refusal:
        return dict(out, presentation_state=refusal)
    cond = cx["condition"]
    if action in DECISION_ACTIONS and cond != "STALE_ETAG" and DELETION_VIEW_STATES.get(cond) not in DECISION_ELIGIBLE_STATES:
        return dict(out, presentation_state="READY")      # the request stays viewable; no decision is offered or issued
    if (action, cond) in PRE_REQUEST_CONDITIONS:
        return dict(out, presentation_state=PRE_REQUEST_CONDITIONS[(action, cond)])
    out.update(control_offered=True, request_issued=True, audit_notice=op["audit"] == "REQUIRED")
    if (action, cond) in POST_REQUEST_CONDITIONS:
        return dict(out, presentation_state=POST_REQUEST_CONDITIONS[(action, cond)])
    out["presentation_state"] = "ACTION_PENDING" if op["mode"] == "ASYNC" else "READY"
    out["content_delivery"] = "ATTACHMENT" if op["response_schema"] == "ReportContentDownload" else "NONE"
    out["new_evaluation"] = op["response_schema"] in NEW_EVALUATION_RESPONSES
    out["completion_claimed"] = action == "VIEW_DELETION" and DELETION_VIEW_STATES.get(cond) == "COMPLETE"
    return out


def validate(ctx):
    d, api, f = ctx["contract"], ctx["api"], ctx["foundation"]
    api_ops = {o["operation_id"]: o for o in api["operations"]}
    schemas = api["schemas"]
    pvoc = ctx["persistence"]["vocabularies"]
    pins = ctx["pins"]
    results = []

    def check(n, description, test):
        try:
            passed = bool(test())
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration):
            passed = False
        results.append({"check_id": f"UXP-{n:02d}", "description": description, "passed": passed})

    def vocab(name):
        v = api["vocabularies"][name]
        return v["values"] if v["source"] == "API" else pvoc[v["persistence_vocabulary"]]["values"]

    def fields(schema_name):
        return [x["name"] for x in schemas[schema_name]["fields"]]

    lc = d["lifecycle"]
    ops = {o["operation_id"]: o for o in d["operations"]}
    fsurf = {s["surface_id"]: s for s in f["surfaces"]}
    states = {s["state_id"]: s for s in f["presentation_states"]}
    openapi_ids = {op.get("operationId") for p in ctx["openapi"]["paths"].values() for op in p.values() if isinstance(op, dict)}
    handoff = next(h for h in f["handoffs"] if h["work_package"] == "P7-WP5")

    # ---------------- lifecycle (fail-closed; pinned records only)
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
                and re.fullmatch(r"GATE-030 §(\d+)", me["verification_reference"]) is not None
                and f"## {me['verification_reference'].split('§')[1]}. " in ctx["gate"])

    def freeze():
        snap = {a["path"]: a["sha256"] for a in ctx["snapshot"]["snapshot"]["artifacts"]}
        return (ctx["snapshot"]["closure_status"] == "PHASE 6 CLOSED" and len(snap) == 19
                and all(ctx["hashes"][p] == h for p, h in snap.items())
                and re.search(r'^ENGINE_VERSION = "1\.0\.0"$', ctx["engine"], re.M) is not None and d["engine_version"] == "1.0.0")

    def predecessors():
        return (all(ctx["hashes"][p] == h for p, h in PREDECESSOR_PINS.items())
                and all(ctx[k]["lifecycle"]["state"] == "CLOSED" for k in ("intake", "result", "review"))
                and d["foundation"] == dict(foundation_contract="UX-001", foundation_gate="GATE-026", foundation_handoff_scope=handoff["scope"],
                                            consumed_contracts=["UX-002", "UX-003", "UX-004"],
                                            consumed_gates=["GATE-027", "GATE-028", "GATE-029"], predecessors_modified=False)
                and ctx["result"]["immutability"]["correction_reanalysis_owner"] == "P7-WP5")

    def scope_ok():
        sc = d["scope"]
        mapped = [m["handoff_item"] for m in sc["request_mapping"]]
        return (sc["owned"] == handoff["scope"] and sorted(mapped) == sorted(handoff["scope"]) and len(set(mapped)) == len(mapped)
                and all(m["request_item"] for m in sc["request_mapping"]) and sc["deferred"]
                and all(x["owner"] in DEFERRED_OWNERS and x["item"] for x in sc["deferred"]))

    def surfaces_ok():
        covered = {i for s in d["surfaces"] for i in s["handoff_items"]}
        return ([s["surface_id"] for s in d["surfaces"]] == SURFACES and covered == set(handoff["scope"])
                and all(s["operations"] == fsurf[s["surface_id"]]["api_operations"] and s["allowed_roles"] == fsurf[s["surface_id"]]["allowed_roles"]
                        and s["role_alone_sufficient"] is False is fsurf[s["surface_id"]]["role_alone_sufficient"]
                        and set(s["handoff_items"]) <= set(handoff["scope"]) for s in d["surfaces"]))

    def api_parity():
        on_any_surface = {op for s in f["surfaces"] for op in s["api_operations"]}
        return ([o["operation_id"] for o in d["operations"]] == OWNED
                and all(o["operation_id"] in api_ops and o["operation_id"] in openapi_ids and api_ops[o["operation_id"]]["internal"] is False
                        and all(o[k] == api_ops[o["operation_id"]][k] for k in OP_KEYS)
                        and o["caller_constraints"] == api_ops[o["operation_id"]].get("caller_constraints", [])
                        and o["errors"] == api_ops[o["operation_id"]]["errors"] and o["surface_id"] in SURFACES
                        and o["listed_on_ux001_surface"] is (o["operation_id"] in fsurf[o["surface_id"]]["api_operations"])
                        and (o["listed_on_ux001_surface"] or o["operation_id"] not in on_any_surface)
                        for o in d["operations"]))

    def ux001_access():
        for s in d["surfaces"]:
            for acc in fsurf[s["surface_id"]]["operation_access"]:
                o = ops.get(acc["operation_id"])
                if o is not None and (acc["roles"] != o["roles"] or acc["resource_authorization"] != o["resource_authorization"]
                                      or acc["sensitive_content_permission"] != o["sensitive_content_permission"]
                                      or acc["break_glass_roles"] != o["break_glass_roles"] or acc["sensitivity"] != o["sensitivity"]):
                    return False
        return all(not o["break_glass_roles"] for o in d["operations"])

    def supporting():
        sup = {x["operation_id"] for x in d["supporting_operations"]}
        ev = fields("EvaluationResponse")
        return (sup == {"getCase", "getEvaluation", "listCaseEvaluations"} and sup <= set(api_ops) and sup.isdisjoint(ops)
                and {"origin", "predecessor_evaluation_id", "result_availability", "state", "ai_usage"} <= set(ev)
                and {"relationship", "can_view_evidence_content"} <= set(fields("CaseViewerAccess")))

    def errors_ok():
        codes = sorted({e for o in d["operations"] for e in o["errors"]})
        api_err = {e["code"]: e for e in api["error_codes"]}
        if [e["error_code"] for e in d["error_presentation"]] != codes:
            return False
        for e in d["error_presentation"]:
            k = e["error_code"]
            if e["http_status"] != api_err[k]["http_status"] or e["retryability"] != api_err[k]["retryability"]:
                return False
            if e["implies_safe"] is not False or e["content_shown"] is not False:
                return False
            if e["presentation_state"] in EXTRA_STATES:
                if k != "EVALUATION_NOT_COMPLETED":
                    return False
            elif k not in states.get(e["presentation_state"], {}).get("api_error_codes", []):
                return False
            if k == "FORBIDDEN":
                if (e["presentation_state"] != "ACCESS_DENIED" or e["alternate_presentation_state"] != "CONTENT_PERMISSION_REQUIRED"
                        or "getReportContent" not in (e["alternate_condition"] or "")):
                    return False
            elif e["alternate_presentation_state"] is not None or e["alternate_condition"] is not None:
                return False
        return True

    def recovery_ok():
        voc = {x["recovery"]: x for x in d["recovery_vocabulary"]}
        return (set(voc) == set(RECOVERY_RETRYABILITY) and all(voc[r]["retryability"] == [t] and voc[r]["meaning"] for r, t in RECOVERY_RETRYABILITY.items())
                and all(RECOVERY_RETRYABILITY.get(e["recovery"]) == e["retryability"] for e in d["error_presentation"]))

    def removal_ok():
        g = d["governed_removal"]
        errs = {e["error_code"]: e for e in d["error_presentation"]}
        return (g["removed_status"] == 410 and g["not_found_status"] == 404 and g["removed_state"] == "REMOVED_UNDER_GOVERNANCE"
                and g["not_found_state"] == "NOT_FOUND_OR_NOT_VISIBLE" and g["distinct"] is True
                and all(g[k] is False for k in ("removed_presented_as_not_found", "not_found_discloses_existence", "recreate_removed_content"))
                and g["tombstone"] == TOMBSTONE and g["tombstone_content_rules"] == "NOT YET SPECIFIED (OI-05)"
                and errs["REMOVED_UNDER_GOVERNANCE"]["http_status"] == 410 and errs["REMOVED_UNDER_GOVERNANCE"]["presentation_state"] == "REMOVED_UNDER_GOVERNANCE"
                and errs["NOT_FOUND"]["http_status"] == 404 and errs["NOT_FOUND"]["presentation_state"] == "NOT_FOUND_OR_NOT_VISIBLE"
                and "REMOVED_UNDER_GOVERNANCE" in vocab("api_result_availability")
                and "REMOVED_UNDER_GOVERNANCE" in api_ops["getReportContent"]["errors"]
                and "REPLAY_UNAVAILABLE" in api_ops["createReplay"]["errors"])

    def reports_ok():
        r = d["reports"]
        report_paths = [o["path"] for o in api_ops.values() if "report" in o["path"]]
        return (r["case_scoped"] is True and r["global_reports_endpoint"] is False and "/api/v1/reports" not in report_paths
                and r["list_contract"] == api_ops["listReports"]["list"] and set(r["displayed_metadata"]) <= set(fields("ReportResponse"))
                and r["content_link_displayed"] is False and r["create_fields"] == fields("ReportCreateRequest")
                and r["pinned_sources"] == PINNED_SOURCES and r["reproduction"] == "EXACT_FROM_PINS"
                and r["uses_latest"] is False is f["semantics"]["report"]["uses_latest"]
                and r["new_revision_on_create"] is True and r["overwrites_revision"] is False
                and f["semantics"]["report"]["pinned_sources"] is True
                and [x["state"] for x in r["state_labels"]] == vocab("api_report_state")
                and all(x["label"] and x["meaning"] for x in r["state_labels"]))

    def regeneration_ok():
        rg = d["reports"]["regeneration_unavailable"]
        return (rg["report_state"] == "REGENERATION_UNAVAILABLE" in vocab("api_report_state")
                and rg["content_error"] == "REPORT_REGENERATION_UNAVAILABLE" == f["semantics"]["report"]["missing_material"]
                and "REPORT_REGENERATION_UNAVAILABLE" in api_ops["getReportContent"]["errors"]
                and all(rg[k] is False for k in ("approximate_regeneration", "latest_substitution", "ai_call", "reconstruct_removed_content"))
                and f["semantics"]["report"]["reconstructs_deleted_content"] is False and rg["unavailable_reason_display"] == "CATEGORY_ONLY")

    def report_content_ok():
        ct = d["reports"]["content"]
        return (ct["delivery"] == "ATTACHMENT_DOWNLOAD" and ct["inline_rendering"] is False and ct["client_cache"] is False
                and ct["format"] == "NOT YET SPECIFIED (REPORT-001)" and "no-store" in schemas["ReportContentDownload"]["description"]
                and ct["automatic_transmission"] is False is f["semantics"]["report"]["automatic_transmission"]
                and ct["audit_event"] == api_ops["getReportContent"]["audit_event"] == "REPORT_EXPORTED")

    def report_matrix():
        rows = d["reports"]["content_rows"]
        if {r["principal_role"] for r in rows} != set(ROLES):
            return False
        op = api_ops["getReportContent"]
        for r in rows:
            refusal = authorized(op, r["principal_role"], r["relationship"], r["permits_evidence_content"])
            want = {None: "OFFERED", "ACCESS_DENIED": "NOT_OFFERED", "NOT_FOUND_OR_NOT_VISIBLE": "NOT_VISIBLE",
                    "CONTENT_PERMISSION_REQUIRED": "CONTENT_PERMISSION_REQUIRED"}[refusal]
            if r["content_action"] != want:
                return False
        return True

    def replay_ok():
        rp = d["replay"]
        return (rp["semantics"] == f["semantics"]["replay"] and rp["request_fields"] == fields("ReplayCreateRequest") == ["reason_code"]
                and rp["create_operation"] == "createReplay" and rp["read_operation"] == "getReplay"
                and set(rp["displayed_fields"]) <= set(fields("ReplayResponse")) and rp["content_free"] is True
                and rp["administrator_entry_by_reference"] is True
                and all(rp[k] is False for k in ("generic_error", "new_result", "fallback_to_reanalysis")) and rp["unavailable_is_outcome"] is True
                and rp["reanalysis_offered_as"] == "SEPARATE_ACTION_NEW_EVALUATION"
                and [x["state"] for x in rp["state_labels"]] == vocab("api_replay_state")
                and [x["outcome"] for x in rp["outcome_labels"]] == vocab("replay_outcome")
                and rp["capabilities"] == vocab("replay_capability_state") and rp["material_kinds"] == vocab("replay_material_kind"))

    def reanalysis_ok():
        ra = d["reanalysis"]
        return (ra["operation"] == "createEvaluations" and ra["request_fields"] == fields("EvaluationCreateRequest")
                and "predecessor_evaluation_id" in ra["request_fields"] and ra["predecessor_required"] is True and ra["reason_required"] is True
                and ra["semantics"] == f["semantics"]["reanalysis"] and ra["origin_server_derived"] is True
                and ra["origins"] == vocab("evaluation_origin") and ra["analysis_modes"] == vocab("analysis_mode")
                and ra["ai_honoured_only_if_enabled"] is True and ra["ai_fallback_shown_from"] == "EvaluationResponse.ai_usage"
                and ra["history"] == dict(predecessor_link_displayed=True, earlier_results_retained=True, newer_supersedes_earlier=False,
                                          aggregate_verdict=False)
                and f["semantics"]["case_aggregate_verdict"] is False)

    def correction_ok():
        co = d["correction"]
        on_any_surface = {op for s in f["surfaces"] for op in s["api_operations"]}
        return (co["operation"] == "createCorrection" and co["roles"] == api_ops["createCorrection"]["roles"]
                and co["resource_authorization"] == api_ops["createCorrection"]["resource_authorization"]
                and co["request_fields"] == fields("UserCorrectionCreateRequest") and co["creates_new_evaluation"] is True
                and co["origin"] == "USER_CORRECTION" in vocab("evaluation_origin")
                and all(co[k] is False for k in ("edits_original", "structured_field_editing", "description_in_notifications", "description_in_audit"))
                and co["description_sensitivity"] == api_ops["createCorrection"]["sensitivity"] == "C4"
                and co["ux001_surface_listed"] is ("createCorrection" in on_any_surface) is False and co["placement"] in SURFACES)

    def deletion_ok():
        dl = d["deletion"]
        rq, dc = dl["request"], dl["decision"]
        transitions = [o for o in api_ops.values() if "deletion" in o["path"] and o["method"] == "POST" and o["path"].endswith(("/complete", "/progress", "/execute"))]
        return (not [o for o in api_ops.values() if o["method"] == "DELETE"] and dl["delete_verb_exists"] is False
                and dl["request_is_deletion"] is False and dl["optimistic_completion"] is False
                and rq["operation"] == "createDeletionRequest" and rq["roles"] == api_ops["createDeletionRequest"]["roles"]
                and rq["resource_authorization"] == api_ops["createDeletionRequest"]["resource_authorization"]
                and rq["fields"] == fields("DeletionRequestCreateRequest") and rq["scope_kinds"] == vocab("deletion_scope_kind")
                and dc["operations"] == ["authorizeDeletionRequest", "rejectDeletionRequest"]
                and all(api_ops[o]["roles"] == dc["roles"] == ["ADMINISTRATOR"] and api_ops[o]["concurrency"] == "IF_MATCH_REQUIRED"
                        and api_ops[o]["request_schema"] == "ReasonCommandRequest" for o in dc["operations"])
                and dc["precondition"] == "If-Match" and dc["reason_required"] is True and dc["administrator_sees_content"] is False
                and dc["eligible_from"] == sorted(DECISION_ELIGIBLE_STATES) and dc["terminal_requests_read_only"] is True
                and API_TRANSITION_ROW in ctx["api_doc"]
                and dl["execution"] == dict(api_operation=None, executor="GOVERNED_EXECUTOR", progress_from="getDeletionRequest") and not transitions
                and dl["list_contract"] == api_ops["listDeletionRequests"]["list"]
                and set(dl["displayed_fields"]) <= set(fields("DeletionRequestResponse")) and "etag" not in dl["displayed_fields"]
                and dl["failure_display"] == "CATEGORY_ONLY" and dl["retention"] == "NOT YET SPECIFIED"
                and [x["state"] for x in dl["state_labels"]] == vocab("api_deletion_state")
                and [x["state"] for x in dl["state_labels"] if x["completion_claimed"]] == ["COMPLETE"])

    def comparison_ok():
        hc = d["historical_comparison"]
        return (hc["api_capability"] is False and not [o for o in api_ops if "ompar" in o]
                and hc["computed_comparison"] is False and hc["improvement_or_change_claims"] is False
                and hc["presentation"] == "SEPARATE_RECORDS_WITH_PROVENANCE" and set(hc["shown_per_record"]) <= set(fields("EvaluationResponse"))
                and hc["ordering"] in fields("EvaluationResponse"))

    def consequences_ok():
        rows = d["access_consequences"]
        return ([r["operation_id"] for r in rows] == OWNED
                and all(r["audit"] == api_ops[r["operation_id"]]["audit"] and r["audit_event"] == api_ops[r["operation_id"]]["audit_event"]
                        and r["notice_shown"] is (r["audit"] == "REQUIRED") and ops[r["operation_id"]]["audit_notice_shown"] is r["notice_shown"]
                        for r in rows))

    def governed_copy():
        got, gov = protected_texts(d), ctx["governed_text"]
        return set(got) == set(gov) == set(GOVERNED_TEXT) and all(norm(got[k]) == norm(gov[k]) for k in gov)

    def semantic_copy():
        """Each label and each meaning is judged on its own (round-1 MEDIUM-1): a safe meaning never excuses a label."""
        governed = {k: norm(v) for k, v in ctx["governed_text"].items()}
        shown = {k: norm(v) for k, v in protected_texts(d).items()}
        for t in (governed, shown):
            for k, x in t.items():
                if (k.startswith("deletion.state_labels.") and ".COMPLETE." not in k
                        and COMPLETION_WORDS.search(x) and not NEGATED.search(x)):
                    return False
                if k.startswith("reports.state_labels.REMOVED_UNDER_GOVERNANCE.") and NOT_FOUND_WORDING.search(x):
                    return False
                if k.startswith("reports.state_labels.REGENERATION_UNAVAILABLE.") and APPROXIMATION.search(x) and not NEGATED.search(x):
                    return False
                if k.startswith(("replay.outcome_labels.", "replay.state_labels.")) and affirmed_substitution(x):
                    return False
                if k.startswith("replay.state_labels.PENDING.") and PENDING_COMPLETION.search(x) and not NEGATED.search(x):
                    return False
        t = dict(governed, **shown)
        return (True
                and HISTORY_KEPT.search(t["reanalysis.notice"]) and HISTORY_KEPT.search(t["correction.notice"])
                and HISTORY_KEPT.search(t["replay.outcome_labels.MISMATCH.meaning"])
                and not COMPARISON_CLAIM.search(t["historical_comparison.notice"]))

    def display_texts():
        texts = ([x[k] for x in d["reports"]["state_labels"] + d["replay"]["state_labels"] + d["replay"]["outcome_labels"]
                  + d["deletion"]["state_labels"] for k in ("label", "meaning")]
                 + list(protected_texts(d).values()) + [x["meaning"] for x in d["recovery_vocabulary"]])
        return all(isinstance(x, str) and x and not FORBIDDEN_DISPLAY.search(x) for x in texts)

    def decisions_ok():
        dec = d["open_decisions"]
        carried = [x["decision"] for x in f["open_design_decisions"] if "P7-WP5" in x["owner"]]
        return (all(x["status"] == "DEFERRED" and x["owner"] and x["decision"] for x in dec)
                and all(any(k.lower() in x["decision"].lower() for x in dec) for k in REQUIRED_DECISIONS)
                and all(any(x.startswith(c) for x in carried) for c in UX001_CARRIED) and len(carried) == len(UX001_CARRIED)
                and sum("carried from UX-001" in x["owner"] for x in dec) >= len(UX001_CARRIED))

    def scenarios_ok():
        return bool(d["scenarios"]) and all(s["expected"] == decide(api_ops, s["action"], s["context"]) for s in d["scenarios"])

    def scenario_coverage():
        by, conds = {}, set()
        for s in d["scenarios"]:
            by.setdefault(s["action"], set()).add(s["expected"]["request_issued"])
            conds.add(s["context"]["condition"])
        ids = [s["id"] for s in d["scenarios"]]
        needed = {c for _, c in PRE_REQUEST_CONDITIONS} | {c for _, c in POST_REQUEST_CONDITIONS} | {"DELETION_COMPLETE", "DELETION_PARTIALLY_FAILED"}
        ineligible = {s["action"] for s in d["scenarios"] if s["action"] in DECISION_ACTIONS
                      and DELETION_VIEW_STATES.get(s["context"]["condition"]) not in (None, *DECISION_ELIGIBLE_STATES)}
        return (set(by) == set(ACTION_OPS) and all(True in v for v in by.values()) and len(set(ids)) == len(ids)
                and ineligible == DECISION_ACTIONS
                and needed <= conds and all(s["context"]["condition"] in {"AVAILABLE"} | needed | set(DELETION_VIEW_STATES) for s in d["scenarios"]))

    def scenario_agreement():
        content = {(r["principal_role"], r["relationship"], r["permits_evidence_content"]): r["content_action"] for r in d["reports"]["content_rows"]}
        labels = {x["state"]: x["completion_claimed"] for x in d["deletion"]["state_labels"]}
        for s in d["scenarios"]:
            cx, ex = s["context"], s["expected"]
            key = (cx["principal_role"], cx["relationship"], cx["permits_evidence_content"])
            if s["action"] == "DOWNLOAD_REPORT" and key in content and cx["condition"] == "AVAILABLE":
                if (content[key] == "OFFERED") is not ex["control_offered"]:
                    return False
            if s["action"] == "VIEW_DELETION" and ex["request_issued"] and ex["completion_claimed"] is not labels[DELETION_VIEW_STATES[cx["condition"]]]:
                return False
            if ex["history_modified"] is not False:
                return False
            if (s["action"] in DECISION_ACTIONS and cx["condition"] != "STALE_ETAG"
                    and DELETION_VIEW_STATES.get(cx["condition"]) not in DECISION_ELIGIBLE_STATES
                    and (ex["control_offered"] or ex["request_issued"])):
                return False
        return True

    def documentary_parity():
        proj = projections(d)
        return (all(f"<!-- UXP:{n}:BEGIN -->\n{proj[n]}\n<!-- UXP:{n}:END -->" in ctx["doc"] for n in DOC_PROJECTIONS)
                and all(f"<!-- UXP:{n}:BEGIN -->\n{proj[n]}\n<!-- UXP:{n}:END -->" in ctx["gate"] for n in GATE_PROJECTIONS))

    def policy_vocabulary():
        subjects = set(ROLES) | set(OWNED) | {s["id"] for s in d["scenarios"]} | set(SURFACES) | set(d["carryovers"])
        subjects |= {x["state"] for x in d["deletion"]["state_labels"] + d["reports"]["state_labels"]} | {x["id"] for x in d["review_findings"]}
        assertions = {"OWNER", "ASSIGNED_ANALYST", "BREAK_GLASS", "NONE", "APPROVE", "REQUEST_CHANGES", "OFFERED", "NOT_OFFERED",
                      "NOT_VISIBLE", "CONTENT_PERMISSION_REQUIRED", "ATTACHMENT"} | set(states) | EXTRA_STATES | FINDING_DISPOSITIONS
        return subjects, assertions

    def projection_structure(text, names):
        subjects, assertions = policy_vocabulary()
        governed_headers = {tuple(" ".join(c.lower().split()) for c in gfm_cells(v.splitlines()[0])) for v in projections(d).values()}
        lines = text.splitlines()
        marker = re.compile(r"^<!-- UXP:(\w+):(BEGIN|END) -->$")
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
            if "UXP:" in ln or ("<!--" in ln and "-->" not in ln) or ("-->" in ln and "<!--" not in ln):
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
            if (tuple(" ".join(c.lower().split()) for c in head) in governed_headers
                    or (words & POLICY_SUBJECT_HEADER and words & POLICY_ASSERTION_HEADER)
                    or any(policy_row([c.strip("*`").strip() for c in r]) for r in rows)):
                return False
        return True

    def no_premature_claims():
        lines = ctx["doc"].splitlines() + ctx["gate"].splitlines()
        return not [ln for ln in lines for pat, allowed in PREMATURE.items()
                    if pat.search(ln) and lc["state"] not in allowed and not NEGATION.search(ln)]

    def gate_decision():
        row = next(ln for ln in ctx["gate"].splitlines() if ln.startswith("| Deliverable |"))
        return (f"**{lc['status']}**" in ctx["gate"] and ctx["gate"].count(f"**{lc['status']}**") == 1
                and all(x in row for x in ("UX-005", "ux-reporting-v1.json", "ux-reporting-contract.schema.json",
                                           "reporting-negative-mutations.json", "validate_ux_reporting.py")))

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

    check(1, "UX-005 identity and status row follow the recorded lifecycle", lambda: "| Document ID | UX-005 |" in ctx["doc"] and f"| Status | {lc['status']} |" in ctx["doc"])
    check(2, "GATE-030 identity and status row follow the recorded lifecycle", lambda: "| Document ID | GATE-030 |" in ctx["gate"] and f"| Status | {lc['status']} |" in ctx["gate"])
    check(3, "Machine contract valid against a closed, local-only schema", lambda: schema_valid(d, ctx["schema"]))
    check(4, "Exact baseline and work-package identity", lambda: d["baseline"] == BASELINE and BASELINE in ctx["doc"] and BASELINE in ctx["gate"] and d["work_package"] == "P7-WP5" and d["contract_id"] == "UX-005" and d["phase"] == f["phase"])
    check(5, "Lifecycle fail-closed: review records, approval and merge evidence only as pinned governed records", lifecycle_ok)
    check(6, "Phase-6 snapshot (19 artifacts) intact; ENGINE_VERSION 1.0.0", freeze)
    check(7, "UX-001..UX-004 unmodified and consumed; UX-002..UX-004 CLOSED", predecessors)
    check(8, "Scope equals the UX-001 P7-WP5 handoff; every request item mapped; deferred items owned", scope_ok)
    check(9, "Surfaces equal UX-001 surfaces (operations, roles); no role-alone access", surfaces_ok)
    check(10, "Owned operations equal the accepted API and OpenAPI; surface placement truthful", api_parity)
    check(11, "UX-001 operation access equals the owned operations; no break-glass on any P7-WP5 operation", ux001_access)
    check(12, "Supporting reads exist and carry the fields history and tombstones need", supporting)
    check(13, "Every operation error maps to a UX-001 state that lists it; FORBIDDEN alternate only for report content", errors_ok)
    check(14, "Recovery vocabulary consistent with API retryability", recovery_ok)
    check(15, "EVALUATION_NOT_COMPLETED resolved from the Evaluation state as in UX-001", lambda: d["evaluation_not_completed"] == dict(state_source_operation="getEvaluation", error_code_alone_sufficient=False, rules=f["evaluation_error_presentation"]["rules"], unresolved_context="DO_NOT_INFER_PENDING_OR_FAILURE"))
    check(16, "410 governed removal distinct from 404 not found or not visible; tombstone behaviour exact", removal_ok)
    check(17, "Reports case-scoped, source-pinned, revisioned, never from latest material; states exact", reports_ok)
    check(18, "Report regeneration unavailable: no approximation, substitution, AI or reconstruction", regeneration_ok)
    check(19, "Report content attachment-only, uncached, format unspecified, audited, never transmitted automatically", report_content_ok)
    check(20, "Report-content matrix equals API resource authorization (derived content; no administrator, no break-glass)", report_matrix)
    check(21, "Replay exact historical verification; unavailable material an explicit outcome; never re-analysis or a new result", replay_ok)
    check(22, "Re-analysis creates a new Evaluation with predecessor and reason; history retained; origins server-derived", reanalysis_ok)
    check(23, "User correction limited to the accepted API: owner only, new evaluation, no editing; placement recorded", correction_ok)
    check(24, "Deletion request, decision (only from REQUESTED), execution and completion distinct; only COMPLETE claims completion", deletion_ok)
    check(25, "Historical comparison has no API capability and is never computed", comparison_ok)
    check(26, "Access consequences and audit notices equal API audit requirements", consequences_ok)
    check(27, "Guardrails hold; no prohibited exposure", lambda: all(v is False for v in d["guardrails"].values()) and len(d["guardrails"]) == 16 and set(d["exposure"]) == EXPOSURES and d["exposure"] == f["exposure"] and all(v is False for v in d["exposure"].values()))
    check(28, "Protected copy bound to the closed set of governed messages", governed_copy)
    check(29, "Each protected label and meaning: no completion before COMPLETE or for a pending replay, 410 never not found, no approximation, no affirmed engine substitution, history kept", semantic_copy)
    check(30, "Display texts make no safety, verification, guilt or scoring claim", display_texts)
    check(31, "Missing capabilities recorded as owned deferred decisions, including the UX-001 decisions owned by P7-WP5", decisions_ok)
    check(32, "Programme carryovers unchanged", lambda: d["carryovers"] == {k: {"status": v["status"], "owner": v["owner"]} for k, v in ctx["review"]["carryovers"].items()})
    check(33, "No tenancy, retention, implementation, readiness, testing or approval claim", lambda: d["tenancy"] == dict(ux_enabled=False, organization_switcher_authority=False) and d["retention"] == dict(duration="NOT YET SPECIFIED", numeric_duration_invented=False) and all(d["claims"][k] is False for k in ("frontend_implemented", "api_implemented", "production_ready", "accessibility_compliant", "usability_tested", "security_tested", "later_wp_started")) and len(d["claims"]) == 9 and d["non_goals"])
    check(34, "Every pinned scenario equals the independent decision procedure", scenarios_ok)
    check(35, "Scenarios cover every action and every governed condition; identifiers unique", scenario_coverage)
    check(36, "Scenarios agree with the report-content matrix and deletion completion labels; history never modified", scenario_agreement)
    check(37, "UX-005 and GATE-030 projections equal the machine contract", documentary_parity)
    check(38, "Exactly one governed projection per table, outside fences; no reporting-policy table outside projections", lambda: projection_structure(ctx["doc"], DOC_PROJECTIONS) and projection_structure(ctx["gate"], GATE_PROJECTIONS))
    check(39, "Approval and closure wording follows the recorded lifecycle; no implementation or later-WP claim", no_premature_claims)
    check(40, "GATE-030 deliverable row and single decision line follow the recorded lifecycle", gate_decision)
    check(41, "Review findings equal the recorded rounds; dispositions and the GATE-030 §7 record consistent", findings_ok)
    assert len(results) == CHECK_COUNT
    return results


TARGETS = {"contract", "schema", "doc", "gate", "api", "api_doc", "foundation", "intake", "result", "review", "engine", "hashes", "snapshot",
           "pins", "governed_text"}


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
            print(f"UX REPORTING: FAIL — {len(failed)}/{CHECK_COUNT} checks failed")
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
            print(f"UX REPORTING: FAIL — mutations {len(ids) - len(bad)}/{len(ids)}; positive controls {len(pos_ids) - len(pos_bad)}/{len(pos_ids)}")
            return 1
        print(f"UX REPORTING: PASS — {CHECK_COUNT}/{CHECK_COUNT} checks; {len(ids)}/{len(ids)} negative mutations rejected by "
              f"intended checks; {len(pos_ids)}/{len(pos_ids)} positive controls accepted (static contract validation; no "
              f"frontend or runtime exists)")
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"UX REPORTING: FAIL — invalid or missing input: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
