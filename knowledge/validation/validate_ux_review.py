"""P7-WP4 deterministic offline evidence-review and security UX checks (UXV-01..UXV-47).

Builder verification, not independent review, penetration testing or runtime authorization testing. Reads the accepted
authorities (UX-001 foundation, closed UX-002 / UX-003, the closed Phase-6 API catalog and OpenAPI) without editing them.

Every operation binding must equal the accepted API exactly; the content-permission and C4-rationale matrices and the
pinned security scenarios are re-derived by an independent decision procedure built from the API's own resource
authorization rules and field visibility, so the contract cannot grant what the API does not.

Lifecycle is fail-closed without parsing Markdown review prose: review records, approval and merge evidence count only
when they equal the records pinned in this module (VERIFIED_*) by a governed bookkeeping step. While those pins are empty,
only CANDIDATE with no review history can pass.

Protected display copy is bound to a closed set of governed messages (whitespace-normalised) and, independently, to
narrow semantic invariants that also bind any governed revision: no existence disclosure, no identifiers or content in
locked or restricted text, no adjudication wording that rewrites the deterministic result. Accessible announcements
may carry only the fields their presentation state is authorized to show. Governed projections must appear exactly once
and outside fences, and no visible GFM table outside them (with or without outer pipes) may act as a security-policy
table: repeat a governed header, pair a subject column with a policy column, or pair a governed subject with a governed
assertion in a row. Explanatory tables that merely mention a role or term remain valid. Visible prose or table text
may not affirm that an administrator can obtain evidence content without break-glass (bounded claim recognizer).

Negative fixtures inject one change (or a synchronized sequence of steps) into an in-memory input copy and must fail
their named UXV check, not merely any check; positive controls must pass every check. Hypothetical future lifecycle
states are exercised through the in-memory "pins" input only. No network, subprocess or frontend is used.
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
BASELINE = "e58dac6bff63a8cb79512338919af6d15db958c1"   # P7-WP3 closure merge (PR #38)
CONTRACT = "contracts/ux/ux-review-v1.json"
SCHEMA = "contracts/ux/ux-review-contract.schema.json"
FIXTURES = "contracts/ux/fixtures/review-negative-mutations.json"
DOC = "docs/07-ux/UX-004-evidence-review-security.md"
GATE = "docs/00-program/GATE-029-phase-7-evidence-review-security.md"
CHECK_COUNT = 47
STATUS_BY_STATE = {
    "CANDIDATE": "P7-WP4 EVIDENCE REVIEW AND SECURITY UX CANDIDATE",
    "APPROVED": "P7-WP4 EVIDENCE REVIEW AND SECURITY UX APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING",
    "CLOSED": "P7-WP4 EVIDENCE REVIEW AND SECURITY UX CLOSED",
}
# Governed lifecycle pins. A review round, the approval and the merge evidence count only when a governed bookkeeping step
# has pinned the exact record here from programme-supplied evidence; until then the lifecycle fails closed to CANDIDATE.
# Round 1 (GATE-029 §7): the independent review result supplied to the builder by the programme.
VERIFIED_REVIEW_HISTORY: list = [
    {"round": 1, "kind": "INITIAL_INDEPENDENT_REVIEW", "decision": "REQUEST_CHANGES",
     "counts": {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 3, "LOW": 0, "INFO": 0},
     "reviewer_role": "Independent reviewer", "record_reference": "GATE-029 §7",
     "evidence_source": "Independent review result supplied to the builder by the programme"},
    {"round": 2, "kind": "TARGETED_INDEPENDENT_REREVIEW", "decision": "REQUEST_CHANGES",
     "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 2, "LOW": 0, "INFO": 0},
     "reviewer_role": "Independent reviewer", "record_reference": "GATE-029 §7",
     "evidence_source": "Independent review result supplied to the builder by the programme"},    {"round": 3, "kind": "TARGETED_INDEPENDENT_REREVIEW", "decision": "REQUEST_CHANGES",
     "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 1, "LOW": 0, "INFO": 0},
     "reviewer_role": "Independent reviewer", "record_reference": "GATE-029 §7",
     "evidence_source": "Independent review result supplied to the builder by the programme"},
    {"round": 4, "kind": "TARGETED_INDEPENDENT_REREVIEW", "decision": "APPROVE",
     "counts": {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0},
     "reviewer_role": "Independent reviewer", "record_reference": "GATE-029 §7",
     "evidence_source": "Independent review result supplied to the builder by the programme"},
]
# The independent approval of round 4 (GATE-029 §7). CLOSED additionally needs merge evidence pinned post-merge.
VERIFIED_APPROVAL = {"round": 4, "decision": "APPROVE", "record_reference": "GATE-029 §7", "reviewer_role": "Independent reviewer"}
VERIFIED_MERGE_EVIDENCE = None
INDEPENDENT_REVIEW_KINDS = {"INITIAL_INDEPENDENT_REVIEW", "TARGETED_INDEPENDENT_REREVIEW", "FINAL_INDEPENDENT_REVIEW"}
INDEPENDENT_REVIEWER_ROLES = {"Independent reviewer"}
PERMITTED_EVIDENCE_SOURCES = {"Independent review result supplied to the builder by the programme"}
REVIEW_RECORD = "GATE-029 §7"
REVIEW_HEADING = "## 7. Independent review record"
FINDING_DISPOSITIONS = {"CORRECTED_PENDING_TARGETED_REREVIEW", "OPEN_CARRIED", "OPEN_INFORMATIONAL", "CLOSED_BY_REREVIEW"}

# Round-1 MEDIUM-1: the closed set of governed, disclosure-safe messages for protected display fields. A wording change is
# a governed revision of this table (and still has to satisfy the semantic invariants below), never a contract-only edit.
GOVERNED_TEXT = {
    "content_permission.content_actions.DOWNLOAD_OFFERED": "An explicit download control is offered after the audit notice; the backend still decides.",
    "content_permission.content_actions.CONTENT_PERMISSION_REQUIRED": "The case is visible but content permission was not granted; no download control and no request.",
    "content_permission.content_actions.NOT_VISIBLE": "The case is not visible to this person; existence is not disclosed.",
    "content_permission.content_actions.NOT_OFFERED": "This role has no evidence surface.",
    "content_permission.content_actions.BREAK_GLASS_ONLY": "No content by role; content is reachable only through the caller's own active, scoped break-glass grant covering the item.",
    "content_permission.pre_access_notice.text": "Downloading the original evidence is recorded in the audit log.",
    "c4_rationale.restricted_text": "The rationale is restricted to an assigned analyst with content permission.",
    "c4_rationale.author_notice": "This rationale may quote evidence. Only an assigned analyst with content permission can read it.",
    "audit.pre_read_notice": "Reading the audit log is itself recorded in the audit log.",
    "adjudication.outcome_labels.AGREES_WITH_RESULT.label": "Analyst agrees with the system result",
    "adjudication.outcome_labels.AGREES_WITH_RESULT.meaning": "A human reviewer agreed with this exact result. The result itself is unchanged.",
    "adjudication.outcome_labels.DISAGREES_WITH_RESULT.label": "Analyst disagrees with the system result",
    "adjudication.outcome_labels.DISAGREES_WITH_RESULT.meaning": "A human reviewer disagreed with this exact result. The result itself is unchanged.",
    "adjudication.outcome_labels.UNABLE_TO_ADJUDICATE.label": "Analyst could not adjudicate",
    "adjudication.outcome_labels.UNABLE_TO_ADJUDICATE.meaning": "A human reviewer could not reach a view on this exact result.",
    "announcements.CONTENT_PERMISSION_REQUIRED.text": "You do not have permission to view this evidence content.",
    "announcements.NOT_FOUND_OR_NOT_VISIBLE.text": "Nothing is available here.",
    "announcements.ACCESS_DENIED.text": "This action is not available to you.",
    "announcements.RATIONALE_RESTRICTED.text": "The rationale is restricted.",
    "announcements.BREAK_GLASS_ACTIVE.text": "Break-glass access is active and recorded until the time shown.",
}
# Semantic invariants (bind contract text and any governed revision alike).
MASKED_TEXTS = ("content_permission.content_actions.NOT_VISIBLE", "announcements.NOT_FOUND_OR_NOT_VISIBLE.text",
                "announcements.ACCESS_DENIED.text")
LOCKED_TEXTS = ("content_permission.content_actions.CONTENT_PERMISSION_REQUIRED", "content_permission.content_actions.NOT_VISIBLE",
                "content_permission.content_actions.NOT_OFFERED", "content_permission.content_actions.BREAK_GLASS_ONLY",
                "c4_rationale.restricted_text", "announcements.CONTENT_PERMISSION_REQUIRED.text",
                "announcements.NOT_FOUND_OR_NOT_VISIBLE.text", "announcements.ACCESS_DENIED.text",
                "announcements.RATIONALE_RESTRICTED.text", "announcements.BREAK_GLASS_ACTIVE.text")
EXISTENCE_DISCLOSURE = re.compile(r"\b(exists?|existing|was found|is there|there is|belongs to|but you (cannot|can't|do not|don't)|"
                                  r"you (cannot|can't) (access|open|see|view) (it|this case|this item))\b", re.I)
CONTENT_LEAK = re.compile(r"\d|\b[A-Z]{2,}\b|[A-Z]+_[A-Z0-9_]+|[\"“”@:]|https?://", re.U)   # quotes, colons, digits, codes
REWRITE_VERB = re.compile(r"\b(replac|overrid|overwrit|rewrit|revis|correct|updat|supersed|amend|alter|downgrad|upgrad)\w*|"
                          r"\bchang(e|es|ed|ing)\b", re.I)
REWRITE_OBJECT = re.compile(r"\b(results?|classifications?|severity|risk|confidence|matched rules?|rules?|findings?)\b", re.I)
ANNOUNCEMENT_STATES = ["CONTENT_PERMISSION_REQUIRED", "NOT_FOUND_OR_NOT_VISIBLE", "ACCESS_DENIED", "RATIONALE_RESTRICTED",
                       "BREAK_GLASS_ACTIVE"]
# Round-2 MEDIUM-1: governed presentation-state -> (authorized source read, fields that state may show and announce).
# Masked, denied and content-restricted states show and announce no resource metadata; a restricted rationale keeps only
# what case access already shows (outcome and time); an active grant shows only its own grant fields to the grantee.
ANNOUNCEMENT_POLICY = {
    "CONTENT_PERMISSION_REQUIRED": (None, set()),
    "NOT_FOUND_OR_NOT_VISIBLE": (None, set()),
    "ACCESS_DENIED": (None, set()),
    "RATIONALE_RESTRICTED": ("getAdjudication", {"outcome", "adjudicated_at"}),
    "BREAK_GLASS_ACTIVE": ("getBreakGlassGrant", {"scope_kind", "case_id", "evidence_id", "started_at", "expires_at"}),
}
ANNOUNCEMENT_SOURCE_AUTHORIZATION = {"getAdjudication": "CASE_ACCESS", "getBreakGlassGrant": "BREAK_GLASS_GRANTEE_OR_PLATFORM_ADMIN"}
PROTECTED_FIELDS = {"rationale", "reason", "reason_note", "review_note", "evidence_content", "content"}
DOC_PROJECTIONS = ["operations", "content_matrix", "rationale_matrix", "errors", "consequences", "labels", "protected_text",
                   "announcements", "scenarios", "decisions", "carryovers"]
GFM_DELIMITER_CELL = re.compile(r"^:?-+:?$")
# Round-3 MEDIUM-2: a security-policy table is recognized by structure and assertions, never by vocabulary alone.
POLICY_SUBJECT_HEADER = {"role", "roles", "principal", "principals", "who", "actor", "actors", "caller", "viewer", "grantee",
                         "round", "operation", "operations", "scenario", "scenarios"}
POLICY_ASSERTION_HEADER = {"permission", "permissions", "permitted", "access", "content", "relationship", "rationale", "visible",
                           "visibility", "sees", "see", "allowed", "decision", "outcome", "grant", "grants", "download",
                           "offered", "authorization", "authorized", "disposition", "announced", "glass"}
# Round-4 MEDIUM-2: bounded recognizer of explicit affirmative administrator evidence-access claims (not general NLP).
ADMIN_SUBJECT = re.compile(r"\b(administrators?|admins?)\b", re.I)
ACCESS_VERB = re.compile(r"\b(download|downloads|downloading|view|views|read|reads|open|opens|access|accesses|see|sees|"
                         r"retrieve|retrieves|obtain|obtains|get|gets)\b", re.I)
EVIDENCE_OBJECT = re.compile(r"\b(original evidence|raw evidence|evidence content|evidence bytes|evidence|submitted content)\b", re.I)
CLAIM_NEGATION = re.compile(r"\b(cannot|can't|can not|may not|might not|must not|mustn't|shall not|will not|won't|never|not|"
                            r"no|nor|unable)\b", re.I)
BREAK_GLASS_CONDITION = re.compile(r"\b(through|with|via|under|using)\b[^.;:]*\bbreak-glass\b", re.I)
BREAK_GLASS_BYPASS = re.compile(r"\b(without|regardless of|bypassing|instead of|no)\b[^.;:]*\bbreak-glass\b|\bby role\b|"
                                r"\brole alone\b", re.I)
POLICY_ASSERTION_WORDS = {"yes", "no", "y", "n", "true", "false", "allowed", "denied", "permitted", "forbidden", "visible",
                          "hidden", "granted", "offered", "shown", "withheld"}
GATE_PROJECTIONS = ["carryovers", "decisions", "review_history", "findings"]
COVERAGE_REQUIREMENTS = ["CALLER_IS_GRANTEE", "GRANT_ACTIVE", "CASE_IN_SCOPE", "ITEM_IN_SCOPE_FOR_EVIDENCE_ITEM"]

# Predecessor freeze: the closed P7-WP1..WP3 deliverables at the baseline (closure bookkeeping, not a snapshot expansion).
PREDECESSOR_PINS = {
    'contracts/ux/ux-foundation-v1.json': '2a1a058028f4cf50597dc787aa4f18fa0f8364752818474ccb9cfa5a43aa7430',
    'contracts/ux/ux-intake-v1.json': 'be4a2933a1153549233813e4bf16a349aff578f66f29dd7db58425241706a83a',
    'contracts/ux/ux-result-v1.json': 'c8f63807165bbd1983f31d459d1281e46b77ff917ffd728c5cec034435951862',
    'docs/07-ux/UX-001-experience-foundation-information-architecture.md': '622f1a1a59dd5658e3f6555d164437d0b01c7c84bf3a5f8bbe0d2c5728b750aa',
    'docs/07-ux/UX-002-submission-evidence-intake.md': '6db2f57750593c9dd9e757fcf6e3c9a261d056bfdc3ff52a4fbdd14e74443453',
    'docs/07-ux/UX-003-result-presentation.md': 'c1fc84afbffae3e31e14b2f41b8373e62c5afa6e14eb2954313acfd86c39e9df',
}
SURFACES = ["UX-EVIDENCE-CONTENT", "UX-ACCESS-GRANTS", "UX-REVIEW-QUEUE", "UX-ASSIGNMENT", "UX-BREAK-GLASS",
            "UX-ADJUDICATION", "UX-AUDIT"]
OP_KEYS = ("method", "path", "roles", "resource_authorization", "sensitive_content_permission", "break_glass_roles",
           "request_schema", "response_schema", "success_status", "idempotency", "audit", "audit_event", "sensitivity",
           "concurrency")
ROLES = ["USER", "ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR"]
ACTION_OPS = {"DOWNLOAD_EVIDENCE": "getEvidenceContent", "READ_ADJUDICATION": "listAdjudications",
              "CREATE_ADJUDICATION": "createAdjudication", "VIEW_QUEUE": "listReviewQueue", "ASSIGN_REVIEW": "assignReview",
              "CREATE_BREAK_GLASS": "createBreakGlassGrant", "END_BREAK_GLASS": "endBreakGlassGrant",
              "REVIEW_BREAK_GLASS": "reviewBreakGlassGrant", "VIEW_AUDIT": "listAuditEvents",
              "LIST_GRANTS": "listCaseAccessGrants", "REVOKE_GRANT": "revokeCaseAccessGrant"}
CASE_RELATIONSHIP = {"USER": "OWNER", "ANALYST": "ASSIGNED_ANALYST"}   # the relationship that makes a case visible per role
RECOVERY_RETRYABILITY = {"RETRY_SAME_REQUEST": "RETRYABLE", "WAIT_THEN_RETRY_SAME_REQUEST": "RETRYABLE",
                         "WAIT_FOR_PENDING_COMMAND": "RETRYABLE", "REFRESH_EVALUATION_STATUS": "RETRYABLE",
                         "CORRECT_REQUEST": "RETRY_WITH_CHANGES", "REAUTHENTICATE_THEN_RETRY": "RETRY_WITH_CHANGES",
                         "REFRESH_THEN_DECIDE": "RETRY_WITH_CHANGES", "REVIEW_THEN_NEW_COMMAND": "RETRY_WITH_CHANGES",
                         "STOP_NO_RETRY": "NOT_RETRYABLE"}
DEFERRED_OWNERS = {"P7-WP5", "P7-WP6", "Phase 9"}
REQUIRED_DECISIONS = ("assignment target", "CASE_EVIDENCE break-glass", "awaiting review", "reason_code", "display-name",
                      "C4 rationale", "Break-glass duration")
# Display text must make no safety, legitimacy, verification, guilt or scoring claim (no negation allowance: the governed
# texts simply avoid these words).
FORBIDDEN_DISPLAY = re.compile(r"\b(safe|safely|safety|harmless|benign|legitimate|guarantee[sd]?|certified|verified|cleared|"
                               r"innocent|guilty|criminal|fraudster|probability|percent(age)?|score)\b", re.I)
PREMATURE = {   # claim wording -> lifecycle states in which it is permitted (implementation and later WPs never are)
    re.compile(r"P7-WP4 (is |was |has been |has )?(approved|accepted)", re.I): {"APPROVED", "CLOSED"},
    re.compile(r"P7-WP4 (is |was |has been |has )?(closed|merged)", re.I): {"CLOSED"},
    re.compile(r"P7-WP4 (is |was |has been |has )?(implemented|complete)", re.I): set(),
    re.compile(r"P7-WP[5-7] (is |was |has been |has )?(started|in progress|complete)", re.I): set(),
}
NEGATION = re.compile(r"\b(not|no|never|until|only after|cannot)\b", re.I)
EXPOSURES = {"raw_provider_bodies", "credentials_secrets", "connector_topology", "internal_hosts_ips",
             "evidence_store_locators", "raw_evidence_without_permission", "c4_without_permission",
             "execution_fence_tokens", "idempotency_key_material", "audit_equals_activity"}


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
    """Protected display fields keyed by their governed-text path."""
    out = {f"content_permission.content_actions.{k}": v for k, v in d["content_permission"]["content_actions"].items()}
    out["content_permission.pre_access_notice.text"] = d["content_permission"]["pre_access_notice"]["text"]
    out["c4_rationale.restricted_text"] = d["c4_rationale"]["restricted_text"]
    out["c4_rationale.author_notice"] = d["c4_rationale"]["author_notice"]
    out["audit.pre_read_notice"] = d["audit"]["pre_read_notice"]
    for x in d["adjudication"]["outcome_labels"]:
        out[f"adjudication.outcome_labels.{x['outcome']}.label"] = x["label"]
        out[f"adjudication.outcome_labels.{x['outcome']}.meaning"] = x["meaning"]
    for x in d["announcements"]:
        out[f"announcements.{x['state']}.text"] = x["text"]
    return out


def gfm_cells(line):
    """Cells of one GFM table line: optional leading/trailing pipe, unescaped '|' separators, surrounding whitespace."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def gfm_tables(lines, skip):
    """Bounded recognizer for visible GFM tables (round-2 MEDIUM-2): a header line containing '|', followed by a delimiter
    row with the same number of ':?-+:?' cells (outer pipes optional, indentation at most 3), then rows until a blank line,
    fence, heading or projection marker. Fenced content and lines in `skip` are not visible tables.
    Returns [(header_cells, [row_cells, ...])]."""
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
        if (visible[i] and visible[i + 1] and "|" in head and indent.match(head) and indent.match(delim)
                and "|" in delim + head):
            hc, dc = gfm_cells(head), gfm_cells(delim)
            if len(hc) == len(dc) and all(GFM_DELIMITER_CELL.match(c) for c in dc):
                rows, j = [], i + 2
                while (j < len(lines) and visible[j] and lines[j].strip() and not re.match(r"^ {0,3}(#|```|~~~|<!--)", lines[j])):
                    rows.append(gfm_cells(lines[j]))
                    j += 1
                tables.append((hc, rows))
                i = j
                continue
        i += 1
    return tables


def admin_content_claim(sentence):
    """True for an explicit affirmative claim that an administrator may obtain evidence content without break-glass:
    administrator subject, then an access verb, then an evidence object, no negation before the verb, and either a
    break-glass bypass (without / regardless of / by role ...) or no break-glass condition at all."""
    subject = ADMIN_SUBJECT.search(sentence)
    verb = ACCESS_VERB.search(sentence, subject.end()) if subject else None
    if verb is None or not EVIDENCE_OBJECT.search(sentence, verb.end()) or CLAIM_NEGATION.search(sentence[:verb.start()]):
        return False
    return bool(BREAK_GLASS_BYPASS.search(sentence)) or not BREAK_GLASS_CONDITION.search(sentence)


def visible_sentences(lines, skip):
    """Sentences of visible text outside `skip` and fences: prose paragraphs (joined across wrapped lines) and each
    table-like line with its pipes read as spaces."""
    units, para, fence = [], [], False
    for i, ln in enumerate(lines + [""]):
        if re.match(r"^ {0,3}(```|~~~)", ln):
            fence = not fence
            continue
        prose = not fence and i not in skip and ln.strip() and not ln.lstrip().startswith(("#", "<!--"))
        if prose and "|" in ln:
            units.append(ln.replace("|", " "))
            prose = False
        if prose:
            para.append(ln.strip())
        elif para:
            units.append(" ".join(para))
            para = []
    return [x for u in units for x in re.split(r"(?<=[.!?;])\s+", u) if x.strip()]


def norm(text):
    return " ".join(str(text).split())


def projections(d):
    """Human-readable tables that UX-004 and GATE-029 must carry verbatim between <!-- UXV:name --> markers."""
    yes = {True: "yes", False: "no"}
    return {
        "operations": table(["Operation", "Surface", "Method", "Path", "Roles", "Resource authorization", "Content permission",
                             "Break-glass roles", "Sensitivity", "Audit event", "Concurrency", "Caller constraints"],
                            [[o["operation_id"], o["surface_id"], o["method"], o["path"], o["roles"], o["resource_authorization"],
                              o["sensitive_content_permission"], o["break_glass_roles"], o["sensitivity"], o["audit_event"],
                              o["concurrency"], o["caller_constraints"]] for o in d["operations"]]),
        "content_matrix": table(["Role", "Case relationship", "Content permission", "Evidence content"],
                                [[r["principal_role"], r["relationship"], yes[r["permits_evidence_content"]], r["content_action"]]
                                 for r in d["content_permission"]["rows"]]),
        "rationale_matrix": table(["Role", "Case relationship", "Content permission", "Outcome visible", "C4 rationale visible"],
                                  [[r["principal_role"], r["relationship"], yes[r["permits_evidence_content"]],
                                    yes[r["outcome_visible"]], yes[r["rationale_visible"]]] for r in d["c4_rationale"]["rows"]]),
        "errors": table(["API error", "HTTP", "Retryability", "Presentation state", "Recovery", "Alternate state"],
                        [[e["error_code"], e["http_status"], e["retryability"], e["presentation_state"], e["recovery"],
                          e["alternate_presentation_state"]] for e in d["error_presentation"]]),
        "consequences": table(["Operation", "Audit", "Audit event", "Audit notice shown"],
                              [[a["operation_id"], a["audit"], a["audit_event"], yes[a["notice_shown"]]] for a in d["access_consequences"]]),
        "labels": table(["Vocabulary", "Value", "Label", "Meaning"],
                        [["api_review_state", x["state"], x["label"], x["meaning"]] for x in d["review_queue"]["state_labels"]] +
                        [["review_routing_basis", x["basis"], x["label"], x["meaning"]] for x in d["review_queue"]["routing_basis_labels"]] +
                        [["adjudication_outcome", x["outcome"], x["label"], x["meaning"]] for x in d["adjudication"]["outcome_labels"]]),
        "scenarios": table(["Scenario", "Situation", "Action", "Role / relationship / content", "Control offered", "Request",
                            "Presented as", "Content", "Rationale", "Audit notice"],
                           [[s["id"], s["title"], s["action"],
                             f"{s['context']['principal_role']} / {s['context']['relationship']} / "
                             f"{yes[s['context']['permits_evidence_content']]}",
                             yes[s["expected"]["control_offered"]], yes[s["expected"]["request_issued"]],
                             s["expected"]["presentation_state"], s["expected"]["content_delivery"],
                             yes[s["expected"]["rationale_shown"]], yes[s["expected"]["audit_notice"]]] for s in d["scenarios"]]),
        "protected_text": table(["Protected display field", "Governed text"], [[k, v] for k, v in protected_texts(d).items()]),
        "announcements": table(["Presentation state", "Source read", "Visible fields", "Announced fields"],
                               [[a["state"], a["field_source_operation"], a["visible_fields"], a["announced_fields"]] for a in d["announcements"]]),
        "findings": table(["Finding", "Round", "Severity", "Summary", "Disposition", "Closed in round", "Owner"],
                          [[x["id"], x["round"], x["severity"], x["summary"], x["disposition"], x["closed_in_round"], x["owner"]]
                           for x in d["review_findings"]]),
        "decisions": table(["Unresolved decision", "Owner", "Status"],
                           [[x["decision"], x["owner"], x["status"]] for x in d["open_decisions"]]),
        "carryovers": table(["Item", "Status", "Owner"], [[k, v["status"], v["owner"]] for k, v in d["carryovers"].items()]),
        "review_history": table(["Round", "Kind", "Decision", "BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO", "Reviewer role",
                                 "Evidence source", "Record"],
                                [[h["round"], h["kind"], h["decision"], *[h["counts"][k] for k in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")],
                                  h["reviewer_role"], h["evidence_source"], h["record_reference"]] for h in d["lifecycle"]["review_history"]]),
    }


def load_inputs():
    snapshot = read_json("contracts/phase6/phase6-closure-v1.json")
    hashed = [a["path"] for a in snapshot["snapshot"]["artifacts"]] + list(PREDECESSOR_PINS)
    return dict(contract=read_json(CONTRACT), schema=read_json(SCHEMA),
                doc=(ROOT / DOC).read_text(encoding="utf-8") if (ROOT / DOC).exists() else "",
                gate=(ROOT / GATE).read_text(encoding="utf-8") if (ROOT / GATE).exists() else "",
                api=read_json("contracts/api/api-v1.json"), openapi=read_json("contracts/api/openapi-v1.json"),
                persistence=read_json("contracts/postgresql/schema-v1.json"),
                foundation=read_json("contracts/ux/ux-foundation-v1.json"), intake=read_json("contracts/ux/ux-intake-v1.json"),
                result=read_json("contracts/ux/ux-result-v1.json"),
                engine=(ROOT / "knowledge/runtime/engine.py").read_text(encoding="utf-8"), snapshot=snapshot,
                hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in hashed},
                pins=copy.deepcopy(dict(review_history=VERIFIED_REVIEW_HISTORY, approval=VERIFIED_APPROVAL,
                                        merge_evidence=VERIFIED_MERGE_EVIDENCE)),
                governed_text=dict(GOVERNED_TEXT))


def break_glass_covers(cx):
    """API-001 §3/§23: CASE_EVIDENCE_CONTENT via break-glass needs the caller's OWN active, unexpired grant whose scope covers
    the item (the case for CASE_EVIDENCE, the exact item for EVIDENCE_ITEM). Another administrator never inherits it."""
    return (cx["is_break_glass_grantee"] is True and cx["break_glass_active"] is True and cx["break_glass_case_in_scope"] is True
            and (cx["break_glass_scope_kind"] == "CASE_EVIDENCE"
                 or (cx["break_glass_scope_kind"] == "EVIDENCE_ITEM" and cx["break_glass_item_in_scope"] is True)))


def context_consistent(cx):
    """Reject contradictory scenario context: the claimed coverage must equal the caller-bound coverage, and the backend
    reports the BREAK_GLASS relationship only to the caller's own active grant over the case."""
    if cx["break_glass_covers_item"] is not break_glass_covers(cx):
        return False
    if cx["relationship"] == "BREAK_GLASS" and not (cx["principal_role"] == "ADMINISTRATOR" and cx["is_break_glass_grantee"]
                                                    and cx["break_glass_active"] and cx["break_glass_case_in_scope"]):
        return False
    if cx["break_glass_scope_kind"] not in (None, "CASE_EVIDENCE", "EVIDENCE_ITEM"):
        return False
    roles = [cx["principal_role"]] + cx["additional_roles"]
    return len(set(roles)) == len(roles) and all(r in ROLES for r in roles)


def decide(api_ops, field_visibility, action, cx):
    """Independent decision procedure from the accepted API: roles, break-glass roles, resource authorization, caller
    constraints, audit and field visibility. A principal holding several roles is permitted when any held role is, and is
    otherwise presented with its primary role's refusal. Returns what the UX offers and presents for one action."""
    outcomes = [decide_role(api_ops, field_visibility, action, cx, role) for role in [cx["principal_role"]] + cx["additional_roles"]]
    return next((o for o in outcomes if o["request_issued"]), outcomes[0])


def decide_role(api_ops, field_visibility, action, cx, role):
    op = api_ops[ACTION_OPS[action]]
    rel, permits = cx["relationship"], cx["permits_evidence_content"]
    denied = dict(control_offered=False, request_issued=False, presentation_state="ACCESS_DENIED", content_delivery="NONE",
                  rationale_shown=False, audit_notice=False)
    case_visible = CASE_RELATIONSHIP.get(role) == rel
    via_break_glass = role in op["break_glass_roles"] and break_glass_covers(cx)
    if role not in op["roles"] and not via_break_glass:
        return denied
    ra = op["resource_authorization"]
    if ra in ("CASE_ACCESS", "CASE_EVIDENCE_CONTENT", "CASE_ASSIGNED_ANALYST", "CASE_OWNER_OR_PLATFORM_ADMIN") and not via_break_glass:
        if ra == "CASE_OWNER_OR_PLATFORM_ADMIN" and role == "ADMINISTRATOR":
            pass
        elif not case_visible or (ra == "CASE_ASSIGNED_ANALYST" and rel != "ASSIGNED_ANALYST") or \
                (ra == "CASE_OWNER_OR_PLATFORM_ADMIN" and rel != "OWNER"):
            return dict(denied, presentation_state="NOT_FOUND_OR_NOT_VISIBLE")
        if ra == "CASE_EVIDENCE_CONTENT" and not permits:
            return dict(denied, presentation_state="CONTENT_PERMISSION_REQUIRED")
    if ra == "BREAK_GLASS_GRANTEE" and not cx["is_break_glass_grantee"]:
        return denied
    constraints = op.get("caller_constraints", [])
    if "REVIEWER_NOT_GRANTEE" in constraints and cx["is_break_glass_grantee"]:
        return denied
    if "ASSIGNEE_NOT_CALLER" in constraints and cx["assignee_is_caller"]:
        return denied
    rationale = (action == "READ_ADJUDICATION" and field_visibility["adjudication_rationale"][role] == "IF_GRANTED_CONTENT"
                 and case_visible and permits)
    return dict(control_offered=True, request_issued=True, presentation_state="READY",
                content_delivery="ATTACHMENT" if op["response_schema"] == "EvidenceContentDownload" else "NONE",
                rationale_shown=rationale, audit_notice=op["audit"] == "REQUIRED")


def validate(ctx):
    d, api, f = ctx["contract"], ctx["api"], ctx["foundation"]
    api_ops = {o["operation_id"]: o for o in api["operations"]}
    schemas = api["schemas"]
    fv = api["field_visibility"]
    pvoc = ctx["persistence"]["vocabularies"]
    results = []

    def check(n, description, test):
        try:
            passed = bool(test())
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration):
            passed = False
        results.append({"check_id": f"UXV-{n:02d}", "description": description, "passed": passed})

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
    handoff = next(h for h in f["handoffs"] if h["work_package"] == "P7-WP4")

    pins = ctx["pins"]

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
        # APPROVED / CLOSED (round-1 MEDIUM-3): both claims must be true and the approval must be the pinned approval of
        # the latest, approving round; a true approval flag never compensates for a false review claim.
        expected = ({"round": hist[-1]["round"], "decision": "APPROVE", "record_reference": hist[-1]["record_reference"],
                     "reviewer_role": hist[-1]["reviewer_role"]} if approving else None)
        if (not approving or pins["approval"] is None or lc["approval"] != pins["approval"] or lc["approval"] != expected
                or d["claims"]["approved"] is not True or d["claims"]["independently_reviewed"] is not True):
            return False
        if st == "APPROVED":
            return lc["merge_evidence"] is None
        return st == "CLOSED" and pins["merge_evidence"] is not None and lc["merge_evidence"] == pins["merge_evidence"]

    def freeze():
        pins = {a["path"]: a["sha256"] for a in ctx["snapshot"]["snapshot"]["artifacts"]}
        return (ctx["snapshot"]["closure_status"] == "PHASE 6 CLOSED" and len(pins) == 19
                and all(ctx["hashes"][p] == h for p, h in pins.items())
                and re.search(r'^ENGINE_VERSION = "1\.0\.0"$', ctx["engine"], re.M) is not None and d["engine_version"] == "1.0.0")

    def predecessors():
        fo = d["foundation"]
        return (all(ctx["hashes"][p] == h for p, h in PREDECESSOR_PINS.items())
                and ctx["intake"]["lifecycle"]["state"] == "CLOSED" and ctx["result"]["lifecycle"]["state"] == "CLOSED"
                and fo == dict(foundation_contract="UX-001", foundation_gate="GATE-026", foundation_handoff_scope=handoff["scope"],
                               intake_contract="UX-002", intake_gate="GATE-027", result_contract="UX-003", result_gate="GATE-028",
                               predecessors_modified=False)
                and f["contract_id"] == "UX-001" and ctx["intake"]["contract_id"] == "UX-002" and ctx["result"]["contract_id"] == "UX-003")

    def scope_ok():
        sc = d["scope"]
        mapped = [m["handoff_item"] for m in sc["request_mapping"]]
        return (sc["owned"] == handoff["scope"] and sorted(mapped) == sorted(handoff["scope"]) and len(set(mapped)) == len(mapped)
                and all(m["request_item"] for m in sc["request_mapping"])
                and sc["deferred"] and all(x["owner"] in DEFERRED_OWNERS and x["item"] for x in sc["deferred"]))

    def surfaces_ok():
        got = [s["surface_id"] for s in d["surfaces"]]
        covered = {i for s in d["surfaces"] for i in s["handoff_items"]}
        return (got == SURFACES and covered == set(handoff["scope"])
                and all(s["operations"] == fsurf[s["surface_id"]]["api_operations"]
                        and s["allowed_roles"] == fsurf[s["surface_id"]]["allowed_roles"]
                        and s["role_alone_sufficient"] is False is fsurf[s["surface_id"]]["role_alone_sufficient"]
                        and set(s["handoff_items"]) <= set(handoff["scope"]) for s in d["surfaces"]))

    def api_parity():
        listed = [op for s in d["surfaces"] for op in s["operations"]]
        return ([o["operation_id"] for o in d["operations"]] == listed and len(set(listed)) == len(listed)
                and all(o["operation_id"] in api_ops and o["operation_id"] in openapi_ids and api_ops[o["operation_id"]]["internal"] is False
                        and all(o[k] == api_ops[o["operation_id"]][k] for k in OP_KEYS)
                        and o["caller_constraints"] == api_ops[o["operation_id"]].get("caller_constraints", [])
                        and o["errors"] == api_ops[o["operation_id"]]["errors"]
                        and o["surface_id"] == next(s["surface_id"] for s in d["surfaces"] if o["operation_id"] in s["operations"])
                        for o in d["operations"]))

    def ui_access_parity():
        for s in d["surfaces"]:
            for acc in fsurf[s["surface_id"]]["operation_access"]:
                o = ops[acc["operation_id"]]
                if (acc["roles"] != o["roles"] or acc["resource_authorization"] != o["resource_authorization"]
                        or acc["sensitive_content_permission"] != o["sensitive_content_permission"]
                        or acc["break_glass_roles"] != o["break_glass_roles"] or acc["sensitivity"] != o["sensitivity"]
                        or acc["caller_constraints"] != o["caller_constraints"]):
                    return False
        return True

    def supporting():
        sup = {x["operation_id"]: x for x in d["supporting_operations"]}
        va = {x["name"]: x for x in schemas["CaseViewerAccess"]["fields"]}
        return (set(sup) == {"getCase", "getDetectionResult", "getMe"} and all(o in api_ops for o in sup)
                and set(sup) .isdisjoint(ops)
                and "viewer_access" in fields("CaseResponse") and {"relationship", "can_view_evidence_content"} <= set(va)
                and "result_digest" in fields("DetectionResultResponse"))

    def errors_ok():
        codes = sorted({e for o in d["operations"] for e in o["errors"]})
        rows = {e["error_code"]: e for e in d["error_presentation"]}
        api_err = {e["code"]: e for e in api["error_codes"]}
        if [e["error_code"] for e in d["error_presentation"]] != codes:
            return False
        for k, e in rows.items():
            if e["http_status"] != api_err[k]["http_status"] or e["retryability"] != api_err[k]["retryability"]:
                return False
            if e["implies_safe"] is not False or e["content_shown"] is not False:
                return False
            if k == "EVALUATION_NOT_COMPLETED":
                if e["presentation_state"] != "CONDITIONAL_ON_EVALUATION_STATE":
                    return False
            elif k not in states.get(e["presentation_state"], {}).get("api_error_codes", []):
                return False
            if k == "FORBIDDEN":
                if (e["presentation_state"] != "ACCESS_DENIED" or e["alternate_presentation_state"] != "CONTENT_PERMISSION_REQUIRED"
                        or "getEvidenceContent" not in (e["alternate_condition"] or "")):
                    return False
            elif e["alternate_presentation_state"] is not None or e["alternate_condition"] is not None:
                return False
        return True

    def recovery_ok():
        voc = {x["recovery"]: x for x in d["recovery_vocabulary"]}
        return (set(voc) == set(RECOVERY_RETRYABILITY)
                and all(voc[r]["retryability"] == [t] and voc[r]["meaning"] for r, t in RECOVERY_RETRYABILITY.items())
                and all(RECOVERY_RETRYABILITY.get(e["recovery"]) == e["retryability"] for e in d["error_presentation"]))

    def content_matrix():
        cp = d["content_permission"]
        rows = cp["rows"]
        if {r["principal_role"] for r in rows} != set(ROLES) or set(cp["content_actions"]) != {r["content_action"] for r in rows}:
            return False
        op = api_ops["getEvidenceContent"]
        for r in rows:
            role, rel, permits = r["principal_role"], r["relationship"], r["permits_evidence_content"]
            vis = fv["raw_evidence_content"][role]
            if role in op["break_glass_roles"]:
                want = "DOWNLOAD_OFFERED" if rel == "BREAK_GLASS" and permits and vis == "BREAK_GLASS_ONLY" else "BREAK_GLASS_ONLY"
            elif role not in op["roles"] or vis == "HIDDEN":
                want = "NOT_OFFERED"
            elif CASE_RELATIONSHIP.get(role) != rel:
                want = "NOT_VISIBLE"
            else:
                want = "DOWNLOAD_OFFERED" if permits and vis in ("OWN_CASE", "IF_GRANTED_CONTENT") else "CONTENT_PERMISSION_REQUIRED"
            if r["content_action"] != want:
                return False
        return True

    def content_rules():
        cp = d["content_permission"]
        dl = cp["delivery"]
        desc = schemas["EvidenceContentDownload"]["description"]
        return (cp["authority"] == "BACKEND" and cp["content_operation"] == "getEvidenceContent"
                and cp["permission_signal"] == dict(operation="getCase", relationship_field="viewer_access.relationship",
                                                    permission_field="viewer_access.can_view_evidence_content")
                and cp["metadata_implies_content"] is False and cp["hidden_ui_is_security_control"] is False
                and cp["client_authorization_decision"] is False
                and dl == dict(mode="ATTACHMENT_DOWNLOAD", inline_rendering=False, preview_or_thumbnail=False, client_cache=False,
                               filename="SERVER_GENERATED", media_type="SERVER_VERIFIED", content_in_notifications=False)
                and "attachment" in desc and "no-store" in desc
                and cp["pre_access_notice"]["shown"] is True
                and cp["pre_access_notice"]["audit_event"] == api_ops["getEvidenceContent"]["audit_event"])

    def queue_ok():
        q = d["review_queue"]
        lst = api_ops["listReviewQueue"]["list"]
        item_fields = fields("ReviewItemResponse")
        return (q["operation"] == "listReviewQueue" and q["roles"] == api_ops["listReviewQueue"]["roles"] and q["content_free"] is True
                and set(q["displayed_fields"]) <= set(item_fields) and "etag" not in q["displayed_fields"]
                and q["concurrency_field_displayed"] is False
                and q["filters"] == lst["filters"] and q["sort"] == lst["sort"] and q["pagination"] == lst["pagination"]
                and q["tenancy_status"] == api_ops["listReviewQueue"]["tenancy_status"] == "PROVISIONAL_BLOCKED_ON_ASM_002"
                and q["entry_grants_access"] is False and q["opens_case_via"] == "getCase"
                and all(q[k] is False for k in ("evidence_content_in_queue", "rationale_in_queue", "result_axes_in_queue", "aggregate_counters"))
                and [x["state"] for x in q["state_labels"]] == vocab("api_review_state")
                and [x["basis"] for x in q["routing_basis_labels"]] == vocab("review_routing_basis"))

    def assignment_ok():
        a = d["assignment"]
        op = api_ops["assignReview"]
        return (a["operation"] == "assignReview" and a["roles"] == op["roles"] == ["ADMINISTRATOR"]
                and [a["caller_constraint"]] == op["caller_constraints"] == ["ASSIGNEE_NOT_CALLER"]
                and f["authorization"]["self_assignment"] == "ASSIGNEE_NOT_CALLER"
                and a["dual_role_exemption"] is False is f["authorization"]["dual_role_exemption"]
                and a["analyst_self_assignment"] is False and a["administrator_gains_content"] is False
                and a["request_fields"] == fields("ReviewAssignmentRequest")
                and a["content_permission_choice"] == dict(explicit=True, default_selected=None, consequence_visible=True)
                and op["concurrency"] == "IF_MATCH_REQUIRED" and a["precondition"]["header"] == "If-Match"
                and a["precondition"]["source_field"] == "ReviewItemResponse.etag" and "etag" in fields("ReviewItemResponse")
                and a["precondition"]["stale_presentation"] == "STALE_STATE"
                and a["idempotency"] == dict(user_concept="SAFE_RETRY", key_exposed=False) and op["idempotency"] == "REQUIRED"
                and a["target_discovery"] == "BLOCKED_NO_ACCEPTED_API_CAPABILITY" and a["principal_directory"] is False
                and a["outcome_from_server"] is True)

    def break_glass_ok():
        b = d["break_glass"]
        auth = f["authorization"]["break_glass"]
        grant_fields = fields("BreakGlassGrantResponse")
        return (b["creator_roles"] == api_ops["createBreakGlassGrant"]["roles"] == ["ADMINISTRATOR"]
                and b["analyst_can_create"] is False is f["authorization"]["analyst_creates_break_glass"]
                and b["separate_entry"] is True and b["request_flag_elevation"] is False
                and b["scope_kinds"] == vocab("break_glass_scope") and b["evidence_id_required_for"] == ["EVIDENCE_ITEM"]
                and fields("BreakGlassCreateRequest") == ["scope_kind", "case_id", "evidence_id", "reason"]
                and b["reason_required"] is True and b["reason_must_not_contain_evidence"] is True
                and b["duration"] == dict(set_by="SERVER", value="NOT YET SPECIFIED", client_selectable=False,
                                          display="SERVER_EXPIRES_AT_ONLY", invented_countdown=False)
                and b["pre_activation_notice"]["shown"] is True
                and set(b["pre_activation_notice"]["items"]) == {"SCOPE", "REASON_RECORDED", "TEMPORARY", "AUDITED", "SIGNALLED",
                                                                 "MANDATORY_REVIEW_BY_DIFFERENT_ADMINISTRATOR"}
                and b["active_indicator"]["persistent"] is True and set(b["active_indicator"]["fields"]) <= set(grant_fields)
                and b["active_indicator"]["end_early_action"] == "endBreakGlassGrant"
                and b["coverage_decided_by"] == "BACKEND" and b["caller_bound"] is True
                and b["coverage_requires"] == COVERAGE_REQUIREMENTS and b["inherited_by_other_administrators"] is False
                and all(b[k] is False for k in ("standing_privilege", "silent_elevation", "rationale_access", "result_detail_access"))
                and auth["silent_elevation"] is False and auth["review_constraint"] == "REVIEWER_NOT_GRANTEE"
                and b["review"]["operation"] == "reviewBreakGlassGrant"
                and [b["review"]["constraint"]] == api_ops["reviewBreakGlassGrant"]["caller_constraints"]
                and b["review"]["outcomes"] == vocab("break_glass_review_outcome")
                and b["review"]["review_states"] == vocab("break_glass_review_state")
                and b["review"]["note_must_not_contain_evidence"] is True
                and b["review"]["discovery"] == "AUDIT_EVENTS_THEN_GET_GRANT"
                and "BREAK_GLASS_ACTIVATED" in vocab("audit_event_type") and "BREAK_GLASS_GRANT" in vocab("audit_target_kind")
                and b["operations"] == fsurf["UX-BREAK-GLASS"]["api_operations"])

    def break_glass_path():
        granting = [o for o in api_ops.values() if o["break_glass_roles"]]
        return ([o["operation_id"] for o in granting] == ["getEvidenceContent"]
                and api_ops["getEvidenceContent"]["break_glass_roles"] == ["ADMINISTRATOR"]
                and fv["raw_evidence_content"]["ADMINISTRATOR"] == "BREAK_GLASS_ONLY"
                and f["authorization"]["administrator_content_by_role"] is False
                and "ADMINISTRATOR" not in api_ops["listAdjudications"]["roles"] + api_ops["getAdjudication"]["roles"])

    def adjudication_separate():
        a = d["adjudication"]
        sem, im = f["semantics"], ctx["result"]["immutability"]
        prov = {p["type"]: p for p in ctx["result"]["provenance_types"]}
        return (a["separate_record"] is True and a["overwrites_result"] is False and a["replaces_classification"] is False
                and a["merged_with_result"] is False and a["append_only"] is True and a["supersession"] == "RELATIONSHIP_NOT_EDIT"
                and a["provenance_type"] == "HUMAN_ADJUDICATION" and prov["HUMAN_ADJUDICATION"]["owner"] == "P7-WP4"
                and prov["HUMAN_ADJUDICATION"]["merged_with_other_types"] is False
                and sem["adjudication_separate"] is True and sem["adjudication_overwrites_result"] is False
                and im["adjudication_presentation_owner"] == "P7-WP4" and im["adjudication_outcome_replaces_classification"] is False
                and not [o for o in api_ops.values() if o["target_resource"] == "DetectionResult" and o["method"] != "GET"])

    def adjudication_create():
        cr = d["adjudication"]["create"]
        req = fields("AdjudicationCreateRequest")
        return (cr["operation"] == "createAdjudication" and cr["roles"] == api_ops["createAdjudication"]["roles"]
                and cr["resource_authorization"] == api_ops["createAdjudication"]["resource_authorization"]
                and cr["fields"] == req and not {"adjudicated_by", "adjudicated_at"} & set(req) and cr["actor_and_time"] == "SERVER"
                and cr["digest_source"] == "DetectionResultResponse.result_digest" and "result_digest" in fields("DetectionResultResponse")
                and cr["digest_mismatch_state"] == "CONFLICT" and "CONFLICT" in api_ops["createAdjudication"]["errors"]
                and d["adjudication"]["read_operations"] == ["listAdjudications", "getAdjudication"]
                and [x["outcome"] for x in d["adjudication"]["outcome_labels"]] == vocab("adjudication_outcome"))

    def rationale_matrix():
        rows = d["c4_rationale"]["rows"]
        if {r["principal_role"] for r in rows} != set(ROLES):
            return False
        read = api_ops["listAdjudications"]
        for r in rows:
            role, rel, permits = r["principal_role"], r["relationship"], r["permits_evidence_content"]
            visible = role in read["roles"] and CASE_RELATIONSHIP.get(role) == rel
            rationale = visible and permits and fv["adjudication_rationale"][role] == "IF_GRANTED_CONTENT"
            if r["outcome_visible"] is not visible or r["rationale_visible"] is not rationale:
                return False
        return True

    def rationale_rules():
        c4 = d["c4_rationale"]
        return (c4["sensitivity"] == "C4" == api_ops["listAdjudications"]["sensitivity"] == api_ops["getAdjudication"]["sensitivity"]
                and c4["visible_rule"] == f["authorization"]["c4_rationale_permission"] == "ASSIGNED_ANALYST_WITH_CONTENT_PERMISSION"
                and c4["may_quote_evidence"] is True
                and all(c4[k] is False for k in ("assignment_alone_sufficient", "administrator_by_role", "knowledge_roles",
                                                 "break_glass_reveals", "in_notifications", "in_queue", "in_audit"))
                and c4["owner_sees"] == ["outcome", "adjudicated_at"]
                and set(c4["owner_sees"]) <= set(fields("AdjudicationResponse")) and "rationale" in fields("AdjudicationResponse")
                and c4["absence_is_not_emptiness"] is True and c4["read_audited"] is True
                and c4["read_audit_event"] == api_ops["listAdjudications"]["audit_event"] == api_ops["getAdjudication"]["audit_event"]
                and c4["restricted_text"] and c4["author_notice"])

    def audit_ok():
        a = d["audit"]
        lst = api_ops["listAuditEvents"]["list"]
        return (a["operation"] == "listAuditEvents" and a["roles"] == api_ops["listAuditEvents"]["roles"] == ["ADMINISTRATOR"]
                and a["content_free"] is True and a["displayed_fields"] == fields("AuditEventView")
                and a["filters"] == lst["filters"] and a["sort"] == lst["sort"] and a["pagination"] == lst["pagination"]
                and a["read_is_audited"] is True and a["read_audit_event"] == api_ops["listAuditEvents"]["audit_event"] == "AUDIT_LOG_ACCESSED"
                and a["pre_read_notice"] and all(a[k] is False for k in ("equals_activity_feed", "user_or_analyst_audit_view",
                                                                       "integrity_fields_are_verdict"))
                and fv["audit_metadata"] == {r: ("VISIBLE" if r == "ADMINISTRATOR" else "HIDDEN") for r in ROLES})

    def consequences_ok():
        rows = d["access_consequences"]
        return ([r["operation_id"] for r in rows] == [o["operation_id"] for o in d["operations"]]
                and all(r["audit"] == api_ops[r["operation_id"]]["audit"] and r["audit_event"] == api_ops[r["operation_id"]]["audit_event"]
                        and r["notice_shown"] is (r["audit"] == "REQUIRED") and ops[r["operation_id"]]["audit_notice_shown"] is r["notice_shown"]
                        for r in rows))

    def grants_ok():
        g = d["access_grants"]
        reason = {x["name"]: x for x in schemas["ReasonCommandRequest"]["fields"]}
        return (g["list_operation"] == "listCaseAccessGrants" and g["revoke_operation"] == "revokeCaseAccessGrant"
                and g["displayed_fields"] == fields("CaseAccessGrantResponse") and g["principal_display"] == "OPAQUE_PRINCIPAL_ID"
                and g["revoke_reason_required"] is True is reason["reason_code"]["required"]
                and api_ops["revokeCaseAccessGrant"]["request_schema"] == "ReasonCommandRequest"
                and g["parent_case_access_from_entry"] is False)

    def visibility_basis():
        keys = ("raw_evidence_content", "evidence_metadata", "adjudication_rationale", "audit_metadata", "principal_information")
        return all(f["authorization"]["field_visibility"][k] == fv[k] for k in keys) and list(fv["raw_evidence_content"]) == ROLES

    def display_texts():
        texts = ([x[k] for x in d["review_queue"]["state_labels"] + d["review_queue"]["routing_basis_labels"]
                  + d["adjudication"]["outcome_labels"] for k in ("label", "meaning")]
                 + list(d["content_permission"]["content_actions"].values())
                 + [d["content_permission"]["pre_access_notice"]["text"], d["c4_rationale"]["restricted_text"],
                    d["c4_rationale"]["author_notice"], d["audit"]["pre_read_notice"]]
                 + [x["meaning"] for x in d["recovery_vocabulary"]])
        return all(t and isinstance(t, str) and not FORBIDDEN_DISPLAY.search(t) for t in texts)

    def decisions_ok():
        dec = d["open_decisions"]
        return (all(x["status"] == "DEFERRED" and x["owner"] and x["decision"] for x in dec)
                and all(any(k in x["decision"] for x in dec) for k in REQUIRED_DECISIONS)
                and any("carried from UX-001" in x["owner"] for x in dec if "assignment target" in x["decision"])
                and any("Administrator assignment target" in x["decision"] and x["status"] == "DEFERRED" for x in f["open_design_decisions"]))

    def carryovers_ok():
        want = {k: {"status": v["status"], "owner": v["owner"]} for k, v in ctx["result"]["carryovers"].items()}
        return (d["carryovers"] == want and want["G-09"]["status"] == "OPEN" and want["OI-05"]["status"] == "OPEN"
                and want["ASM-002"]["status"] == "UNCONFIRMED / PROVISIONAL" and want["P6-WP7-LOW-1"]["status"] == "OPEN / NON-BLOCKING")

    def scenarios_ok():
        return bool(d["scenarios"]) and all(context_consistent(s["context"]) and s["expected"] == decide(api_ops, fv, s["action"], s["context"])
                                            for s in d["scenarios"])

    def scenario_coverage():
        by = {}
        for s in d["scenarios"]:
            by.setdefault(s["action"], set()).add(s["expected"]["request_issued"])
        ids = [s["id"] for s in d["scenarios"]]
        return set(by) == set(ACTION_OPS) and all(v == {True, False} for v in by.values()) and len(set(ids)) == len(ids)

    def scenario_matrix_agreement():
        content = {(r["principal_role"], r["relationship"], r["permits_evidence_content"]): r["content_action"]
                   for r in d["content_permission"]["rows"]}
        rationale = {(r["principal_role"], r["relationship"], r["permits_evidence_content"]): r["rationale_visible"]
                     for r in d["c4_rationale"]["rows"]}
        for s in d["scenarios"]:
            cx, ex = s["context"], s["expected"]
            key = (cx["principal_role"], cx["relationship"], cx["permits_evidence_content"])
            if s["action"] == "DOWNLOAD_EVIDENCE" and key in content and not cx["additional_roles"] and \
                    cx["break_glass_covers_item"] == (cx["relationship"] == "BREAK_GLASS"):
                if (content[key] == "DOWNLOAD_OFFERED") is not ex["control_offered"]:
                    return False
            if s["action"] == "READ_ADJUDICATION" and key in rationale and rationale[key] is not ex["rationale_shown"]:
                return False
        return True

    def documentary_parity():
        proj = projections(d)
        return (all(f"<!-- UXV:{n}:BEGIN -->\n{proj[n]}\n<!-- UXV:{n}:END -->" in ctx["doc"] for n in DOC_PROJECTIONS)
                and all(f"<!-- UXV:{n}:BEGIN -->\n{proj[n]}\n<!-- UXV:{n}:END -->" in ctx["gate"] for n in GATE_PROJECTIONS))

    # ---------------- round-1 MEDIUM-1: governed protected copy
    def governed_copy():
        got = protected_texts(d)
        gov = ctx["governed_text"]
        return (set(got) == set(gov) == set(GOVERNED_TEXT)
                and all(norm(got[k]) == norm(gov[k]) for k in gov)
                and [x["state"] for x in d["announcements"]] == ANNOUNCEMENT_STATES)

    def semantic_copy():
        texts = {k: norm(v) for k, v in ctx["governed_text"].items()}
        texts.update({k: norm(v) for k, v in protected_texts(d).items()})
        adjudication = [v for k, v in texts.items() if k.startswith("adjudication.outcome_labels.")]
        return (not [k for k in MASKED_TEXTS if EXISTENCE_DISCLOSURE.search(texts[k])]
                and not [k for k in LOCKED_TEXTS if CONTENT_LEAK.search(texts[k])]
                and not [t for t in adjudication if REWRITE_VERB.search(t) and REWRITE_OBJECT.search(t)]
                and not [a for a in d["announcements"] if set(a["announced_fields"] + a["visible_fields"]) & PROTECTED_FIELDS]
                and d["notifications"] == dict(evidence_content=False, rationale=False, break_glass_reason=False, review_note=False)
                and d["content_permission"]["delivery"]["content_in_notifications"] is False
                and d["c4_rationale"]["in_notifications"] is False)

    # ---------------- round-1 MEDIUM-2: one authoritative projection per governed table
    def policy_vocabulary():
        subjects = set(ROLES) | {o["operation_id"] for o in d["operations"]} | {s["id"] for s in d["scenarios"]}
        subjects |= {x["id"] for x in d["review_findings"]} | set(d["carryovers"]) | set(SURFACES)
        assertions = {"OWNER", "ASSIGNED_ANALYST", "BREAK_GLASS", "NONE", "APPROVE", "REQUEST_CHANGES"} | INDEPENDENT_REVIEW_KINDS
        assertions |= set(d["content_permission"]["content_actions"]) | set(states) | FINDING_DISPOSITIONS
        assertions |= {e["presentation_state"] for e in d["error_presentation"]} | {e["recovery"] for e in d["error_presentation"]}
        assertions |= {x["outcome"] for x in d["adjudication"]["outcome_labels"]}
        return subjects, assertions

    def policy_row(cells, subjects, assertions):
        """A row asserts security policy when a governed subject sits beside a governed assertion in another cell."""
        for i, cell in enumerate(cells):
            if cell in subjects and any((c in assertions or c.lower() in POLICY_ASSERTION_WORDS) for j, c in enumerate(cells) if j != i):
                return True
        return False

    def policy_header(header, governed_headers):
        words = {w for c in header for w in re.findall(r"[a-z]+", c.lower())}
        norm_header = tuple(" ".join(c.lower().split()) for c in header)
        return norm_header in governed_headers or bool(words & POLICY_SUBJECT_HEADER and words & POLICY_ASSERTION_HEADER)

    def projection_structure(text, names):
        subjects, assertions = policy_vocabulary()
        governed_headers = {tuple(" ".join(c.lower().split()) for c in gfm_cells(v.splitlines()[0])) for v in projections(d).values()}
        lines = text.splitlines()
        marker = re.compile(r"^<!-- UXV:(\w+):(BEGIN|END) -->$")
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
            if "UXV:" in ln or ("<!--" in ln and "-->" not in ln) or ("-->" in ln and "<!--" not in ln):
                return False
        if open_name is not None or in_fence or sorted(seen) != sorted(names):
            return False
        inside = {k for a, b in spans for k in range(a, b + 1)}
        fence = False
        for i, ln in enumerate(lines):
            if re.match(r"^ {0,3}(```|~~~)", ln):
                fence = not fence
                continue
            if fence or i in inside or not ln.lstrip().startswith("|"):
                continue
            if policy_row([c.strip("*`").strip() for c in gfm_cells(ln)], subjects, assertions):
                return False
        for header, rows in gfm_tables(lines, inside):
            head = [c.strip("*`").strip() for c in header]
            body = [[c.strip("*`").strip() for c in r] for r in rows]
            if policy_header(head, governed_headers) or any(policy_row(r, subjects, assertions) for r in body):
                return False
        return not [x for x in visible_sentences(lines, inside) if admin_content_claim(x)]

    # ---------------- round-2 MEDIUM-1: state-specific announcement permissions
    def announcement_fields():
        anns = {a["state"]: a for a in d["announcements"]}
        if set(anns) != set(ANNOUNCEMENT_POLICY):
            return False
        if (ANNOUNCEMENT_POLICY["RATIONALE_RESTRICTED"][1] != set(d["c4_rationale"]["owner_sees"])
                or ANNOUNCEMENT_POLICY["BREAK_GLASS_ACTIVE"][1] != set(d["break_glass"]["active_indicator"]["fields"])):
            return False
        for state, (source, allowed) in ANNOUNCEMENT_POLICY.items():
            a = anns[state]
            announced, shown = a["announced_fields"], a["visible_fields"]
            if a["field_source_operation"] != source or len(set(announced)) != len(announced):
                return False
            if not set(announced) <= set(shown) <= allowed:
                return False
            if source is None:
                if shown or announced:
                    return False
            elif (api_ops[source]["resource_authorization"] != ANNOUNCEMENT_SOURCE_AUTHORIZATION[source]
                  or not set(shown) <= set(fields(api_ops[source]["response_schema"]))):
                return False
            if set(shown) & PROTECTED_FIELDS:
                return False
        return True

    # ---------------- round-1: review findings and record
    def findings_ok():
        fs, hist = d["review_findings"], lc["review_history"]
        rounds = {h["round"]: h for h in hist}
        if not hist:
            return fs == []
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
            if x["severity"] == "INFO" and x["disposition"] not in ("OPEN_CARRIED", "OPEN_INFORMATIONAL"):
                return False
        return True

    def no_premature_claims():
        lines = ctx["doc"].splitlines() + ctx["gate"].splitlines()
        return not [ln for ln in lines for pat, allowed in PREMATURE.items()
                    if pat.search(ln) and lc["state"] not in allowed and not NEGATION.search(ln)]

    def gate_decision():
        row = next(ln for ln in ctx["gate"].splitlines() if ln.startswith("| Deliverable |"))
        return (f"**{lc['status']}**" in ctx["gate"] and "| Document ID | GATE-029 |" in ctx["gate"]
                and all(x in row for x in ("UX-004", "ux-review-v1.json", "ux-review-contract.schema.json",
                                           "review-negative-mutations.json", "validate_ux_review.py")))

    check(1, "UX-004 identity and status row follow the recorded lifecycle", lambda: "| Document ID | UX-004 |" in ctx["doc"] and f"| Status | {lc['status']} |" in ctx["doc"])
    check(2, "GATE-029 identity and status row follow the recorded lifecycle", lambda: "| Document ID | GATE-029 |" in ctx["gate"] and f"| Status | {lc['status']} |" in ctx["gate"])
    check(3, "Machine contract valid against a closed, local-only schema", lambda: schema_valid(d, ctx["schema"]))
    check(4, "Exact baseline and work-package identity", lambda: d["baseline"] == BASELINE and BASELINE in ctx["doc"] and BASELINE in ctx["gate"] and d["work_package"] == "P7-WP4" and d["contract_id"] == "UX-004" and d["phase"] == f["phase"])
    check(5, "Lifecycle fail-closed: review records, approval and merge evidence only as pinned governed records", lifecycle_ok)
    check(6, "Phase-6 snapshot (19 artifacts) intact; ENGINE_VERSION 1.0.0", freeze)
    check(7, "UX-001..UX-003 unmodified and consumed; UX-002 and UX-003 CLOSED", predecessors)
    check(8, "Scope equals the UX-001 P7-WP4 handoff; every request item mapped; deferred items owned", scope_ok)
    check(9, "Surfaces equal UX-001 surfaces (operations, roles); no role-alone access", surfaces_ok)
    check(10, "Every operation equals the accepted API exactly and exists in OpenAPI; no invented operation", api_parity)
    check(11, "Per-surface operation access equals UX-001 operation access", ui_access_parity)
    check(12, "Supporting reads exist and carry viewer_access and result_digest", supporting)
    check(13, "Every operation error maps to a UX-001 state that lists it; FORBIDDEN alternate only for content permission", errors_ok)
    check(14, "Recovery vocabulary consistent with API retryability", recovery_ok)
    check(15, "EVALUATION_NOT_COMPLETED resolved from the Evaluation state as in UX-001", lambda: d["evaluation_not_completed"] == dict(state_source_operation="getEvaluation", error_code_alone_sufficient=False, rules=f["evaluation_error_presentation"]["rules"], unresolved_context="DO_NOT_INFER_PENDING_OR_FAILURE"))
    check(16, "Content permission backend-authoritative; attachment-only delivery; audited download notice", content_rules)
    check(17, "Content-permission matrix equals API field visibility and resource authorization", content_matrix)
    check(18, "Administrator content only through break-glass; break-glass grants no rationale or result access", break_glass_path)
    check(19, "Review queue content-free and exact to the API list contract and vocabularies", queue_ok)
    check(20, "Assignment administrator-only, assignee not caller, explicit content choice, If-Match, discovery deferred", assignment_ok)
    check(21, "Break-glass explicit, scoped, reasoned, server-timed, signalled, audited and reviewed by another principal", break_glass_ok)
    check(22, "Adjudication separate, append-only and never replaces the immutable DetectionResult", adjudication_separate)
    check(23, "Adjudication creation exact to the API; digest of the exact result; actor and time server-side", adjudication_create)
    check(24, "C4 rationale matrix equals API field visibility (assigned analyst with content permission only)", rationale_matrix)
    check(25, "C4 rationale protection: restricted text, audited reads, never in queue, audit or notifications", rationale_rules)
    check(26, "Audit content-free, administrator-only, exact filters; reading audit is itself audited", audit_ok)
    check(27, "Access consequences and audit notices equal API audit requirements", consequences_ok)
    check(28, "Access grants content-free with opaque principals and reasoned revocation", grants_ok)
    check(29, "UX-001 field visibility basis equals the API for evidence, rationale, audit and principals", visibility_basis)
    check(30, "Guardrails hold: no admin content by role, no self-elevation, no self-assignment, no invention", lambda: set(d["guardrails"]) == {"administrator_content_by_role", "analyst_creates_break_glass", "self_assignment", "dual_role_exemption", "hidden_ui_security_control", "client_authorization_decision", "silent_break_glass", "standing_break_glass", "adjudication_edits_result", "adjudication_replaces_classification", "rationale_without_permission", "evidence_inline_render", "content_in_queue", "invented_api_operation", "invented_persisted_field", "invented_permission_grant", "invented_retention_rule"} and all(v is False for v in d["guardrails"].values()))
    check(31, "No prohibited information exposure", lambda: set(d["exposure"]) == EXPOSURES and d["exposure"] == f["exposure"] and all(v is False for v in d["exposure"].values()))
    check(32, "Display texts make no safety, verification, guilt or scoring claim", display_texts)
    check(33, "Unresolved API capabilities and interactions recorded as owned deferred decisions", decisions_ok)
    check(34, "Programme carryovers unchanged", carryovers_ok)
    check(35, "Tenancy and retention not invented; review queue provisional under ASM-002", lambda: d["tenancy"] == dict(ux_enabled=False, organization_switcher_authority=False, review_queue_scope="PROVISIONAL_BLOCKED_ON_ASM_002") and d["retention"] == dict(duration="NOT YET SPECIFIED", numeric_duration_invented=False, break_glass_duration="NOT YET SPECIFIED") and f["retention"]["duration"] == "NOT YET SPECIFIED")
    check(36, "No implementation, readiness, testing or approval claim", lambda: set(d["claims"]) == {"frontend_implemented", "api_implemented", "production_ready", "accessibility_compliant", "usability_tested", "security_tested", "independently_reviewed", "approved", "later_wp_started"} and all(d["claims"][k] is False for k in ("frontend_implemented", "api_implemented", "production_ready", "accessibility_compliant", "usability_tested", "security_tested", "later_wp_started")) and d["non_goals"])
    check(37, "Every pinned scenario equals the independent decision procedure", scenarios_ok)
    check(38, "Scenarios cover every action with permitted and refused contexts; identifiers unique", scenario_coverage)
    check(39, "Scenarios agree with the content and rationale matrices", scenario_matrix_agreement)
    check(40, "UX-004 and GATE-029 projections equal the machine contract", documentary_parity)
    check(41, "Approval and closure wording follows the recorded lifecycle; no implementation or later-WP claim in prose", no_premature_claims)
    check(42, "GATE-029 deliverable row and decision follow the recorded lifecycle", gate_decision)
    check(43, "Protected display copy bound to the closed set of governed messages", governed_copy)
    check(44, "Protected copy discloses no existence, identifiers or content and never rewrites the deterministic result", semantic_copy)
    check(45, "Exactly one governed projection per table, outside fences; no governed rows outside projections", lambda: projection_structure(ctx["doc"], DOC_PROJECTIONS) and projection_structure(ctx["gate"], GATE_PROJECTIONS))
    check(46, "Review findings equal the recorded rounds; dispositions and the GATE-029 §7 record consistent", findings_ok)
    check(47, "Announcements carry only the fields their presentation state may show, from the authorized source read", announcement_fields)
    assert len(results) == CHECK_COUNT
    return results


TARGETS = {"contract", "schema", "doc", "gate", "api", "foundation", "intake", "result", "engine", "hashes", "snapshot", "pins",
           "governed_text"}


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


def fixture_keys(fixture):
    if "steps" in fixture:
        if not fixture["steps"] or not all(set(st) == step_keys(st) for st in fixture["steps"]):
            raise ValueError(f"invalid steps in {fixture.get('id')}")
        return {"id", "description", "steps"}
    return {"id", "description"} | step_keys(fixture)


def step_keys(fixture):
    required = {"target", "op"}
    required |= {"old", "value"} if fixture["op"] == "replace_text" else {"path"}
    if fixture["op"] in {"add", "replace"}:
        required.add("value")
    return required


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
            print(f"UX REVIEW: FAIL — {len(failed)}/{CHECK_COUNT} checks failed")
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
            print(f"UX REVIEW: FAIL — mutations {len(ids) - len(bad)}/{len(ids)}; positive controls {len(pos_ids) - len(pos_bad)}/{len(pos_ids)}")
            return 1
        print(f"UX REVIEW: PASS — {CHECK_COUNT}/{CHECK_COUNT} checks; {len(ids)}/{len(ids)} negative mutations rejected by "
              f"intended checks; {len(pos_ids)}/{len(pos_ids)} positive controls accepted (static contract validation; no "
              f"frontend or runtime exists)")
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"UX REVIEW: FAIL — invalid or missing input: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
