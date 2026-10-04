"""TrustLens Phase 6 P6-WP7 — static validator for the integrated Phase-6 closure (Phase 6 CLOSED; lifecycle-aware).

Validates contracts/phase6/phase6-closure-v1.json against contracts/phase6/phase6-closure-contract.schema.json, recomputes
the SHA-256 of every pinned canonical Phase-6 artifact from its exact file bytes, and cross-checks the FINAL integrated
state of the merged Phase-6 contracts (DATA-001, DATA-001-WP2 / schema-v1.json, API-001 / api-v1.json, OAS-001 /
openapi-v1.json, INT-001 / external-enrichment-v1.json, OPS-001 / operational-v1.json, ADR-0011, ADR-0012, GATE-019…024)
against PHASE-6-CLOSURE.md and GATE-025. It SUPPLEMENTS, and never replaces, validate_data_contract.py,
validate_api_contract.py, validate_openapi_contract.py, validate_integration_contract.py and
validate_operational_contract.py. No database, server, git process, network or API key is used: remote-CI evidence is
recorded data (checked for completeness and consistency), not re-fetched.

  P6C-01 PHASE-6-CLOSURE.md exists; Version 0.1; current status PHASE 6 CLOSED (no "pending" current state) and cites
         the recorded P6-WP7 closure evidence (PR, head, merge commit, CI runs); closure gate GATE-025; input baseline
  P6C-02 GATE-025 exists with current status PHASE 6 INTEGRATED CLOSURE PASSED — PHASE 6 CLOSED, cites the same P6-WP7
         evidence and references the closure record + manifest
  P6C-03 closure manifest is valid against its JSON Schema (Draft 2020-12)
  P6C-04 baseline commit exact (= merged P6-WP6 commit) in the manifest, closure document and GATE-025
  P6C-05 exactly six predecessor WPs (P6-WP1…WP6, in order), each merged and CLOSED; P6-WP7 CLOSED and merged with the
         exact PR #32, head and merge commit
  P6C-06 PR numbers 26…31 exact and recorded in the closure document
  P6C-07 merge SHAs exact; each successor gate's Baseline row cites its predecessor's merge SHA and PR
  P6C-08 GATE-019…024 referenced; gate files exist with matching Document IDs; recorded in the closure document
  P6C-09 canonical artifact inventory complete, unique, repository-relative, no excluded material
  P6C-10 every pinned artifact exists
  P6C-11 every pinned SHA-256 equals the SHA-256 of the artifact's actual bytes (drift detection)
  P6C-12 DATA-001 Matrix A <-> PostgreSQL logical-object coverage exact; table count recorded; evaluation 1:1 artifact
  P6C-13 api_idempotency_record -> ApiIdempotencyRecord exact; scoped digest key; CrossStoreOperation keeps its meaning
  P6C-14 governed_removal_tombstone -> GovernedRemovalTombstone exact; distinct from DeletionAction
  P6C-15 API catalog operation count exact (manifest = catalog = OPS-001)
  P6C-16 OpenAPI operation count exact (manifest = OpenAPI)
  P6C-17 API/OpenAPI parity exact (method, path, operationId, request/response schema, success status, auth, roles,
         resource authorization, idempotency, audit, sensitivity, sync/async, concurrency)
  P6C-18 listEvaluationEnrichments contract-active (not runtime-deployed), advisory, no raw provider body/credential
  P6C-19 DetectionResult immutable across persistence, API, OpenAPI and OPS-001
  P6C-20 no scam probability / arbitrary score / ranking / priority / verdict; classification = Phase-3 vocabulary
  P6C-21 external enrichment consumed_in_governed_artifact = false everywhere
  P6C-22 provider CLEAN is a provider assertion, never TrustLens safe
  P6C-23 historical replay never calls AI
  P6C-24 historical replay never calls an external enrichment provider
  P6C-25 historical replay never uses latest/current knowledge or current evidence
  P6C-26 RM-01…RM-14 replay material set unchanged across persistence, OPS-001 and the manifest
  P6C-27 missing replay material = REPLAY_UNAVAILABLE; no approximation; no silent new Evaluation
  P6C-28 report regeneration unavailable after required deletion; no hidden copy; no latest substitution
  P6C-29 tombstone content-free (persistence columns within OPS-001 allow-list; no content digest)
  P6C-30 deletion false-COMPLETE prohibited; explicit partial failure; no distributed transaction claimed
  P6C-31 restore anti-resurrection required before promotion; fails closed; no backup-purge claim
  P6C-32 idempotency carryover CONTRACT-LEVEL CLOSED; runtime pending Phase 9
  P6C-33 ETag carryover CONTRACT-LEVEL CLOSED; monotonic server revision on every If-Match aggregate; runtime Phase 9
  P6C-34 enrichment persistence carryover CONTRACT-LEVEL CLOSED; runtime Phase 9
  P6C-35 ADR-0012 (and ADR-0011) Accepted
  P6C-36 deny-by-default egress; governed destinations; no generic fetch; submitted URL is indicator data only
  P6C-37 governed proxy final-hop enforcement REQUIRED_AND_VERIFIED; unverified proxy blocked; no "SSRF solved" claim
  P6C-38 G-09 OPEN
  P6C-39 OI-05 OPEN; retention durations only when governed automatic expiry is enabled; no duration
  P6C-40 ASM-002 UNCONFIRMED / PROVISIONAL; no sponsor confirmation invented
  P6C-41 Phase-1 status PARTIAL (GATE-001)
  P6C-42 no tenant_id / tenant field anywhere in the Phase-6 contracts or the manifest
  P6C-43 ENGINE_VERSION = 1.0.0
  P6C-44 no numeric policy values invented (24 parameters NOT YET SPECIFIED; no duration/size literals in the manifest)
  P6C-45 premature closure: a CLOSED / MERGED / PASS claim (manifest or document status) requires complete P6-WP7 closure
         evidence (state CLOSED, merged, exact PR / head / merge commit, approving review, successful required CI jobs with
         run ids); manifest closure_status / phase_state / WP7 state consistently CLOSED
  P6C-46 lifecycle: Phase 7 and later phases were NOT STARTED at the moment Phase 6 closed (historical fact); a later-phase
         gate (GATE-026+) is rejected while Phase 6 is not CLOSED with complete evidence and is permitted afterwards
  P6C-47 implementation-deferred list present and owned; no runtime implementation introduced
  P6C-48 no production-readiness / deployment / certification claim
  P6C-49 no legal / compliance / admissibility claim
  P6C-50 no detection-effectiveness / accuracy / precision / recall / FPR claim
  P6C-51 Phase-7 handoff present and complete
  P6C-52 Phase-7 handoff does not redefine decision, authorization, data, replay, retention or network semantics
  P6C-53 open items complete with state, reason, impact, future owner and blocking scope
  P6C-54 this validator has no live network / subprocess dependency; CI needs no network/API key/database
  P6C-55 closure schema and manifest use no external references
  P6C-56 recorded independent reviews end in APPROVE with no unresolved BLOCKER/HIGH/MEDIUM (gate files are authority)
  P6C-57 remote CI evidence recorded for every predecessor WP (both checks, success, run ids, evidence source)
  P6C-58 authorization consistent with ADR-0009 (deny by default, no administrator raw evidence by role,
         administrator-only break-glass creation, no review self-assignment)
  P6C-59 knowledge activation by exact content_digest; no latest / bundle_version-only / rule-body mutation API
  P6C-60 unsupported / non-English input never treated as benign (ADR-0014); Phase-3 semantics unchanged
  P6C-61 AI influences deterministic output only through validated governed observations; never directly
  P6C-62 authority hierarchy restated exactly; no raw evidence bytes, secrets or knowledge authority in PostgreSQL
  P6C-63 re-analysis creates a new Evaluation; history never overwritten
  P6C-64 provider-policy lifecycle immutable, exact identity, no latest-by-name, governed mutators only, storage Phase 9

It then applies every mutation in contracts/phase6/fixtures/negative-mutations.json (to the manifest or, via "target",
to another Phase-6 contract or text input) and requires the named check to fail.

Usage:  .venv/bin/python knowledge/validation/validate_phase6_closure.py [--quiet]
Exit 0 = evidenced Phase-6 closure consistent and every negative mutation rejected by its expected check.
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
MANIFEST_PATH = ROOT / "contracts" / "phase6" / "phase6-closure-v1.json"
SCHEMA_PATH = ROOT / "contracts" / "phase6" / "phase6-closure-contract.schema.json"
NEGATIVE_PATH = ROOT / "contracts" / "phase6" / "fixtures" / "negative-mutations.json"
JSON_INPUTS = {
    "persistence": ROOT / "contracts" / "postgresql" / "schema-v1.json",
    "api": ROOT / "contracts" / "api" / "api-v1.json",
    "openapi": ROOT / "contracts" / "api" / "openapi-v1.json",
    "integration": ROOT / "contracts" / "integrations" / "external-enrichment-v1.json",
    "operations": ROOT / "contracts" / "operations" / "operational-v1.json",
    "phase3_result_schema": ROOT / "knowledge" / "schemas" / "detection" / "detection-result.schema.json",
}
PROGRAM = ROOT / "docs" / "00-program"
TEXT_INPUTS = {
    "closure_doc": PROGRAM / "PHASE-6-CLOSURE.md",
    "gate_doc": PROGRAM / "GATE-025-phase-6-closure.md",
    "data001_text": ROOT / "docs" / "06-contracts" / "DATA-001-data-domain-lifecycle-contract.md",
    "adr0011_text": ROOT / "adr" / "ADR-0011-database-migration-tooling.md",
    "adr0012_text": ROOT / "adr" / "ADR-0012-threat-intelligence-adapter-architecture-provider-selection.md",
    "gate001_text": PROGRAM / "GATE-001-phase-1-assessment.md",
    "gap_text": ROOT / "docs" / "01-research" / "RESEARCH-005-gap-register.md",
    "assumption_text": PROGRAM / "assumption-register.md",
    "engine_text": ROOT / "knowledge" / "runtime" / "engine.py",
    "requirements": ROOT / "requirements.txt",
    "self_source": Path(__file__),
}
GATE_FILES = {
    "GATE-019": "docs/00-program/GATE-019-phase-6-data-contract-foundation.md",
    "GATE-020": "docs/00-program/GATE-020-phase-6-postgresql-persistence.md",
    "GATE-021": "docs/00-program/GATE-021-phase-6-api-contract.md",
    "GATE-022": "docs/00-program/GATE-022-phase-6-openapi-contract.md",
    "GATE-023": "docs/00-program/GATE-023-phase-6-integration-contract.md",
    "GATE-024": "docs/00-program/GATE-024-phase-6-operational-contract.md",
}

BASELINE = "eba1882058e2638a7c4e11a610201d752b920654"
EXPECTED_WPS = [  # (wp, gate, PR, merge commit) — verified against local git history at P6-WP7 build time
    ("P6-WP1", "GATE-019", 26, "0ac84cd89be1f15895e7f8c3a8cd39126cfaa874"),
    ("P6-WP2", "GATE-020", 27, "58c8853dc6ee6ea7cf621ff88fe7c54bceae15a3"),
    ("P6-WP3", "GATE-021", 28, "4d08c5e570b9a08b87a56a51213f0423ea74166f"),
    ("P6-WP4", "GATE-022", 29, "9fa022f74e1a4c76ab5875f8fe6715057fd5654c"),
    ("P6-WP5", "GATE-023", 30, "8fb963e955c06ded736c81d8f8a076ee599b910d"),
    ("P6-WP6", "GATE-024", 31, "eba1882058e2638a7c4e11a610201d752b920654"),
]
REQUIRED_ARTIFACTS = {
    "docs/06-contracts/DATA-001-data-domain-lifecycle-contract.md",
    "docs/06-contracts/DATA-001-WP2-postgresql-persistence-contract.md",
    "contracts/postgresql/schema-v1.json",
    "docs/06-contracts/API-001-api-resource-protocol-contract.md",
    "contracts/api/api-v1.json",
    "docs/06-contracts/OAS-001-openapi-contract.md",
    "contracts/api/openapi-v1.json",
    "docs/06-contracts/INT-001-external-enrichment-integration-contract.md",
    "contracts/integrations/external-enrichment-v1.json",
    "docs/06-contracts/OPS-001-operational-replay-persistence-contract.md",
    "contracts/operations/operational-v1.json",
    "adr/ADR-0011-database-migration-tooling.md",
    "adr/ADR-0012-threat-intelligence-adapter-architecture-provider-selection.md",
} | set(GATE_FILES.values())
EXCLUDED_PATH = re.compile(r"(^|/)(\.git|\.venv|__pycache__|\.pytest_cache|tmp|node_modules)(/|$)|\.pyc$|\.DS_Store$")

CLOSED_STATUS = "PHASE 6 CLOSED"
GATE_CLOSED = "PHASE 6 INTEGRATED CLOSURE PASSED — PHASE 6 CLOSED"
WP7_PR = 32  # P6-WP7 closure evidence — verified against git history and GitHub check-runs at post-merge finalization
WP7_HEAD = "d7a6bba6688101f70243fc73f361b37fca38583a"
WP7_MERGE = "858784428c3caa00da958e170211f03b466941a9"
NYS = "NOT YET SPECIFIED"
CI_CHECKS = ["Knowledge validation suite", "Quality-gate self-test (gate must bite)"]
METHODS = ("get", "put", "post", "delete", "patch", "options", "head", "trace")
PREMATURE = re.compile(r"\b(CLOSED|COMPLETE|COMPLETED|PASS|PASSED|MERGED|REMOTE CI PASS)\b", re.I)
NEGATED = re.compile(r"\bnot (yet )?(formally )?(closed|merged|complete|started)\b", re.I)
NEG = re.compile(r"\b(not|no|never|cannot|without|nor|neither|none|forbidden|prohibited|excluded|unsupported claim)\b|"
                 r"must ?not|may ?not|does ?not|do ?not|isn't|aren't|MUST NOT", re.I)
PROD_CLAIM = re.compile(r"production[- ]read(y|iness)|enterprise[- ]deployed|security[- ]certified|"
                        r"implementation (is )?complete|API (is |was )?deployed|database (is |was )?migrated|"
                        r"penetration[- ]tested|provider integration (is )?live|product implemented", re.I)
LEGAL_CLAIM = re.compile(r"legal(ly)?[ -](complian|compliant|admissib)|legal admissibility|compliance certif|"
                         r"\b(GDPR|DPDP)[- ]compliant|regulatory complian", re.I)
EFFECT_CLAIM = re.compile(r"\b(accuracy|accurately|precision|recall|false[- ]positive rate|detection rate|"
                          r"production[- ]effective(ness)?|detection effectiveness|efficacy)\b", re.I)
AI_WRONG = re.compile(r"\bAI (cannot|can ?not|does not|never|may not|will not) influence\b", re.I)
SSRF_SOLVED = re.compile(r"SSRF (is |has been )?(universally |fully |completely )?(solved|eliminated|impossible)", re.I)
TENANT = re.compile(r"tenant[_-]?id|tenantid|x-tenant|tenant_ref|tenant_key", re.I)
DRIFT = re.compile(r"(probab|score|likelihood|ranking|priority|verdict)", re.I)
DURATION_LITERAL = re.compile(r"\b\d+(\.\d+)?\s*(ms|milliseconds?|s|secs?|seconds?|mins?|minutes?|h|hrs?|hours?|d|days?|"
                              r"weeks?|months?|years?|KB|KiB|MB|MiB|GB|GiB|bytes?)\b|\bP(\d+[YMWD])+(T\d+[HMS])?\b|\bPT\d+[HMS]\b")
NETWORK_IMPORT = re.compile(r"^\s*(import|from)\s+(socket|ssl|http|httplib|urllib|requests|httpx|aiohttp|ftplib|"
                            r"telnetlib|smtplib|poplib|imaplib|subprocess)\b", re.M)
RUNTIME_DEPS = re.compile(r"^\s*(fastapi|flask|django|starlette|uvicorn|gunicorn|sqlalchemy|alembic|psycopg|psycopg2|"
                          r"asyncpg|requests|httpx|aiohttp|urllib3|celery|rq)\b", re.I | re.M)
MIGRATION_PATHS = ("alembic.ini", "alembic", "migrations", "db/migrations")
NUMERIC_KEYS = {("contract_counts",), ("validation_counts",), ("operational_parameters", "count"),
                ("operational_parameters", "classes"), ("unresolved_phase6_review_findings",)}
NUMERIC_WP_KEYS = {"pr_number", "pr_head_run_id", "merge_commit_run_id"}
DIGEST_KEYS = {"sha256", "merge_commit", "pr_head_commit", "baseline_commit"}
HIERARCHY = {
    "knowledge_authority": "GIT_CI_IMMUTABLE_PUBLISHED_BUNDLE",
    "structured_operational_persistence": "POSTGRESQL",
    "raw_sensitive_content_bytes": "EVIDENCE_CONTENT_STORE",
    "security_governance_record": "GOVERNED_AUDIT",
    "operational_observability": "TELEMETRY_NOT_AUDIT",
    "secrets_and_keys": "OUTSIDE_NORMAL_DATABASE_CONTENT",
    "detection_result": "IMMUTABLE_AFTER_COMPLETION",
    "historical_replay": "EXACT_PINNED_HISTORICAL_MATERIAL",
}
FORBIDDEN_SUBSTITUTIONS = {"CURRENT_OR_LATEST_SUBSTITUTION", "AI_RERUN", "PROVIDER_RERUN"}
DECISION_FORBIDDEN = {"SCAM_PROBABILITY", "ARBITRARY_SCORE", "RANKING", "PRIORITY", "AI_VERDICT",
                      "PROVIDER_VERDICT_AS_TRUSTLENS_VERDICT", "NEW_CLASSIFICATION", "NEW_RISK", "NEW_SEVERITY",
                      "NEW_CONFIDENCE_SEMANTICS"}
AI_MAY_NOT = {"SET_DETECTION_RESULT", "SET_CLASSIFICATION", "OVERRIDE_DETERMINISTIC_RESULT", "BYPASS_RULE_SEMANTICS",
              "MUTATE_AUTHORITATIVE_RULE_SETS", "SELECT_ARBITRARY_NETWORK_DESTINATIONS"}
PROVIDER_NEVER = {"classification", "risk", "severity", "confidence", "detectionresult"}
ENRICHMENT_VIEW_FIELDS = {"enrichment_id", "provider_category", "status", "reputation_result", "observed_at", "advisory"}
FORBIDDEN_RESPONSE = re.compile(r"(raw|locator|credential|secret|authorization|network|target_host|policy_ref|evidence)", re.I)
RM_IDS = ["RM-%02d" % i for i in range(1, 15)]
REPLAY_FORBIDDEN = {"AI_CALL", "ENRICHMENT_PROVIDER_CALL", "LATEST_OR_CURRENT_KNOWLEDGE", "CURRENT_EVIDENCE",
                    "APPROXIMATION_OF_DELETED_MATERIAL", "NEW_EVALUATION"}
TOMB_FORBIDDEN = {"DETECTION_RESULT_BODY", "RAW_EVIDENCE", "REPORT_CONTENT", "PROVIDER_RAW_BODY", "C4_RATIONALE",
                  "SECRET_MATERIAL", "DELETED_CONTENT_DIGEST"}
POLICY_EXCLUDED = {"END_USER", "ANALYST", "AI", "PROVIDER_RESPONSE", "ADAPTER_RUNTIME"}
MAY_SUPPORT = {"CONTRACTS_DEFINED", "CROSS_CONTRACT_VALIDATION_EXISTS", "OFFLINE_DETERMINISTIC_VALIDATORS_PASS",
               "API_OPENAPI_PARITY_ESTABLISHED", "PERSISTENCE_DESIGN_SPECIFIED", "INTEGRATION_SECURITY_CONTRACT_SPECIFIED",
               "OPERATIONAL_REPLAY_SEMANTICS_SPECIFIED"}
PROD_TOKENS = {"PRODUCTION_READY", "API_DEPLOYED", "DATABASE_MIGRATED", "SECURITY_PENETRATION_TESTED",
               "PROVIDER_INTEGRATION_LIVE", "IMPLEMENTATION_COMPLETE", "SECURITY_CERTIFIED", "ENTERPRISE_DEPLOYED"}
LEGAL_TOKENS = {"LEGAL_COMPLIANCE", "LEGAL_ADMISSIBILITY"}
EFFECT_TOKENS = {"DETECTION_EFFECTIVENESS", "ACCURACY", "PRECISION", "RECALL", "FALSE_POSITIVE_RATE", "DETECTION_RATE"}
DEFERRED_REQUIRED = {"POSTGRESQL_DEPLOYMENT", "SQL_DDL_TRIGGERS_AND_ALEMBIC_MIGRATIONS", "FASTAPI_SERVICE_AND_RUNNING_ENDPOINTS",
                     "WORKERS", "EXTERNAL_PROVIDER_CONNECTOR", "PERSISTENCE_REPOSITORIES", "PROVIDER_POLICY_STORE",
                     "RESTORE_DELETION_AUTHORITY_IMPLEMENTATION", "OPERATIONAL_CONFIGURATION_VALUES_AS_APPROVED",
                     "FRONTEND", "PRODUCTION_READINESS"}
PHASE7_MAY = {"USER_FLOWS", "CASE_SUBMISSION_EVIDENCE_UX", "RESULT_EXPLANATION_PRESENTATION", "EVIDENCE_REVIEW_UX",
              "ADJUDICATION_UX", "REPORT_UX", "REPLAY_AND_REANALYSIS_UX", "DELETION_AND_UNAVAILABILITY_STATES",
              "PERMISSION_AWARE_VISIBILITY", "UNSUPPORTED_LANGUAGE_EXPERIENCE", "EXTERNAL_ENRICHMENT_PRESENTATION"}
PHASE7_MUST_NOT = {"CLASSIFICATION", "RISK", "SEVERITY", "CONFIDENCE", "DECISION_SEMANTICS", "AUTHORIZATION",
                   "DATA_AUTHORITY", "REPLAY_AUTHORITY", "PROVIDER_CLEAN_MEANING", "RETENTION_POLICY",
                   "NETWORK_SECURITY_SEMANTICS"}
DECISION_TOKEN = re.compile(r"(^|_)(CLASSIFICATION|RISK|SEVERITY|CONFIDENCE|DECISION|SCORE|VERDICT)(_|$)")
OPEN_ITEMS_REQUIRED = {"G-09": "OPEN", "OI-05": "OPEN", "ASM-002": "UNCONFIRMED / PROVISIONAL",
                       "OPERATIONAL-NUMERIC-VALUES": NYS}
CARRYOVERS = {"IDEMPOTENCY_PERSISTENCE": "P6C-32", "ETAG_REVISION_PERSISTENCE": "P6C-33", "ENRICHMENT_PERSISTENCE": "P6C-34"}
SECRET_COLUMN = re.compile(r"(secret|password|api_key|private_key|credential_value|access_token)", re.I)
RAW_CONTENT_COLUMN = re.compile(r"^(raw_|content_bytes|evidence_bytes|body$|raw$|payload$|file_bytes|blob)", re.I)
REFERENCE_SUFFIX = re.compile(r"_(ref|id|sha256|digest|locator|state|at|version|kind|category)$")
BYTEA_ALLOWED = {("audit_checkpoint_signing_attempt", "signature")}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def sha256_file(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def walk(node, fn, path=()):
    fn(node, path)
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, fn, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, fn, path + (i,))


def meta_row(text: str, field: str) -> str:
    m = re.search(r"^\|\s*" + re.escape(field) + r"\s*\|\s*(.+?)\s*\|\s*$", text, re.M)
    return m.group(1) if m else ""


def premature(status: str) -> bool:
    return bool(PREMATURE.search(NEGATED.sub("", status)))


def wp7_evidence_gaps(m: dict) -> list[str]:
    """What is missing for a CLOSED Phase 6 (empty list = fully evidenced P6-WP7 merge)."""
    cur = m.get("current_work_package") or {}
    rc = cur.get("remote_ci") or {}
    gaps = []
    if cur.get("id") != "P6-WP7" or cur.get("state") != "CLOSED":
        gaps.append("P6-WP7 state CLOSED")
    if cur.get("merged") is not True:
        gaps.append("P6-WP7 merged")
    if cur.get("pr_number") != WP7_PR:
        gaps.append(f"P6-WP7 PR #{WP7_PR}")
    if cur.get("merge_commit") != WP7_MERGE:
        gaps.append(f"P6-WP7 merge commit {WP7_MERGE}")
    if cur.get("pr_head_commit") != WP7_HEAD:
        gaps.append(f"P6-WP7 PR head {WP7_HEAD}")
    if "APPROVE" not in str(cur.get("independent_review")) or "REQUEST_CHANGES" in str(cur.get("independent_review")):
        gaps.append("P6-WP7 approving independent review")
    if rc.get("conclusion") != "success" or rc.get("checks") != CI_CHECKS or not isinstance(rc.get("pr_head_run_id"), int) \
            or isinstance(rc.get("pr_head_run_id"), bool) or not isinstance(rc.get("merge_commit_run_id"), int) \
            or "not re-verified by offline CI" not in str(rc.get("evidence_source")):
        gaps.append("P6-WP7 successful required remote-CI jobs with run ids")
    return gaps


def evidenced_closed(m: dict) -> bool:
    return m.get("closure_status") == CLOSED_STATUS and m.get("phase_state") == "CLOSED" and not wp7_evidence_gaps(m)


def unnegated_lines(text: str, pattern: re.Pattern) -> list[str]:
    """Lines that match `pattern` without any negation on the same line (an affirmative claim)."""
    return [ln.strip()[:120] for ln in text.splitlines() if pattern.search(ln) and not NEG.search(ln)]


def by_id(items, key="id"):
    return {i.get(key): i for i in items if isinstance(i, dict)} if isinstance(items, list) else {}


def iter_ops(doc):
    for path, item in (doc.get("paths") or {}).items():
        if isinstance(item, dict):
            for m in METHODS:
                if m in item and isinstance(item[m], dict):
                    yield path, m, item[m]


def schema_name(node):
    if isinstance(node, dict) and str(node.get("$ref", "")).startswith("#/components/schemas/"):
        return node["$ref"].rsplit("/", 1)[1]
    return None


def external_refs(node) -> list[str]:
    found = []

    def fn(n, path):
        if isinstance(n, dict):
            ref = n.get("$ref")
            if isinstance(ref, str) and not ref.startswith("#"):
                found.append(ref)
            dyn = n.get("$dynamicRef")
            if isinstance(dyn, str) and not dyn.startswith("#"):
                found.append(dyn)
    walk(node, fn)
    return found


def names_in(doc) -> list[str]:
    """Field/column/property names declared by a contract (dict keys + 'name' values)."""
    out = []

    def fn(n, path):
        if isinstance(n, dict):
            out.extend(k for k in n if isinstance(k, str))
            if isinstance(n.get("name"), str):
                out.append(n["name"])
    walk(doc, fn)
    return out


def check(d: dict, ctx: dict) -> list[tuple[str, str]]:
    errs: list[tuple[str, str]] = []

    def e(code, msg):
        errs.append((code, msg))

    m = d["closure"]
    if not isinstance(m, dict):
        return [("P6C-03", "closure manifest is not an object")]
    per, api, oas, integ, ops = d["persistence"], d["api"], d["openapi"], d["integration"], d["operations"]
    cdoc, gdoc = d["closure_doc"], d["gate_doc"]
    wps = m.get("work_packages") or []
    wpmap = by_id(wps)
    tables = per.get("tables", [])
    tmap = {t.get("name"): t for t in tables}
    cov = per.get("logical_object_coverage", {})
    catops = {o.get("operation_id"): o for o in api.get("operations", [])}
    oasops = {}
    for p, meth, op in iter_ops(oas):
        oasops.setdefault(op.get("operationId"), []).append((p, meth, op))
    counts = m.get("contract_counts") or {}
    oi = by_id(m.get("open_items"))

    cur7 = m.get("current_work_package") or {}
    rc7 = cur7.get("remote_ci") or {}
    wp7_cited = [f"#{WP7_PR}", WP7_MERGE, WP7_HEAD, str(rc7.get("pr_head_run_id")), str(rc7.get("merge_commit_run_id"))]

    # ---------------- P6C-01 closure document
    if not cdoc:
        e("P6C-01", "docs/00-program/PHASE-6-CLOSURE.md missing")
    else:
        st = meta_row(cdoc, "Status")
        if f"**{CLOSED_STATUS}**" not in st or re.search(r"PENDING|CANDIDATE", st):
            e("P6C-01", f"closure document current status must be {CLOSED_STATUS!r} (no pending/candidate state), found {st!r}")
        for ev in wp7_cited:
            if ev not in cdoc:
                e("P6C-01", f"closure document does not cite recorded P6-WP7 closure evidence {ev}")
        if meta_row(cdoc, "Version") != "0.1":
            e("P6C-01", "closure document Version must be 0.1")
        if "GATE-025" not in meta_row(cdoc, "Closure gate"):
            e("P6C-01", "closure document must name closure gate GATE-025")
        if "Data, API & Integration Contracts" not in meta_row(cdoc, "Phase"):
            e("P6C-01", "closure document Phase row must be 6 — Data, API & Integration Contracts")

    # ---------------- P6C-02 GATE-025
    if not gdoc:
        e("P6C-02", "docs/00-program/GATE-025-phase-6-closure.md missing")
    else:
        if meta_row(gdoc, "Document ID") != "GATE-025":
            e("P6C-02", "GATE-025 Document ID row missing")
        gst = meta_row(gdoc, "Status")
        if f"**{GATE_CLOSED}**" not in gst or re.search(r"PENDING|CANDIDATE", gst):
            e("P6C-02", f"GATE-025 current status must be {GATE_CLOSED!r} (no pending/candidate state)")
        for ev in wp7_cited:
            if ev not in gdoc:
                e("P6C-02", f"GATE-025 does not cite recorded P6-WP7 closure evidence {ev}")
        for ref in ("PHASE-6-CLOSURE.md", "phase6-closure-v1.json", "validate_phase6_closure.py"):
            if ref not in gdoc:
                e("P6C-02", f"GATE-025 must reference {ref}")
    cg = m.get("closure_gate") or {}
    if cg.get("id") != "GATE-025" or cg.get("status") != GATE_CLOSED or cg.get("path") != "docs/00-program/GATE-025-phase-6-closure.md":
        e("P6C-02", f"manifest closure_gate must be GATE-025 / {GATE_CLOSED}")

    # ---------------- P6C-03 schema / P6C-55 external refs
    sch = d["schema"]
    ext = external_refs(sch)
    if ext:
        e("P6C-55", f"closure schema has external references {ext}")
        e("P6C-03", "closure schema not evaluated: external references are not permitted (offline)")
    else:
        try:
            Draft202012Validator.check_schema(sch)
            for err in sorted(Draft202012Validator(sch).iter_errors(m), key=lambda x: list(x.path))[:10]:
                e("P6C-03", f"{'/'.join(map(str, err.path)) or '<root>'}: {err.message[:160]}")
        except SchemaError as ex:
            e("P6C-03", f"closure schema invalid: {ex.message[:160]}")
    urls = []
    walk(m, lambda n, p: urls.append("/".join(map(str, p))) if isinstance(n, str) and re.search(r"https?://", n) else None)
    if urls or external_refs(m):
        e("P6C-55", f"closure manifest must not carry external URLs/references: {urls[:3]}")

    # ---------------- P6C-04 baseline
    if m.get("baseline_commit") != BASELINE:
        e("P6C-04", f"baseline_commit must be {BASELINE}")
    if (wpmap.get("P6-WP6") or {}).get("merge_commit") != m.get("baseline_commit"):
        e("P6C-04", "baseline_commit must equal the merged P6-WP6 commit")
    for name, text in (("closure document", cdoc), ("GATE-025", gdoc)):
        if BASELINE not in meta_row(text, "Baseline"):
            e("P6C-04", f"{name} Baseline row must cite {BASELINE}")

    # ---------------- P6C-05 / 06 / 07 / 08 work packages
    if [w.get("id") for w in wps] != [x[0] for x in EXPECTED_WPS]:
        e("P6C-05", f"work_packages must be exactly P6-WP1..P6-WP6 in order, found {[w.get('id') for w in wps]}")
    for w in wps:
        if w.get("merged") is not True or w.get("closure_state") != "CLOSED":
            e("P6C-05", f"{w.get('id')}: predecessor must be merged and CLOSED")
    cur = m.get("current_work_package") or {}
    if cur.get("id") != "P6-WP7" or cur.get("state") != "CLOSED" or cur.get("merged") is not True \
            or cur.get("pr_number") != WP7_PR or cur.get("merge_commit") != WP7_MERGE or cur.get("pr_head_commit") != WP7_HEAD:
        e("P6C-05", f"P6-WP7 must be CLOSED and merged as PR #{WP7_PR} (head {WP7_HEAD[:12]}, merge {WP7_MERGE[:12]})")
    if cur.get("merge_commit") == m.get("baseline_commit"):
        e("P6C-05", "the closure merge commit must stay distinct from the closure input baseline")
    gate_ids = []
    for i, (wp, gate, pr, sha) in enumerate(EXPECTED_WPS):
        w = wpmap.get(wp) or {}
        if w.get("pr_number") != pr:
            e("P6C-06", f"{wp}: PR number {w.get('pr_number')} != #{pr}")
        if f"#{pr}" not in cdoc:
            e("P6C-06", f"closure document does not record PR #{pr}")
        if w.get("merge_commit") != sha:
            e("P6C-07", f"{wp}: merge commit {w.get('merge_commit')} != {sha}")
        if sha not in cdoc:
            e("P6C-07", f"closure document does not record merge {sha}")
        if i > 0:
            gtext = d["gates"].get(gate, "")
            pwp, _, ppr, psha = EXPECTED_WPS[i - 1]
            bl = meta_row(gtext, "Baseline")
            if psha not in bl or f"#{ppr}" not in bl:
                e("P6C-07", f"{gate} Baseline row does not cite {pwp} merge {psha} (PR #{ppr})")
        gate_ids.append(w.get("gate_id"))
        if w.get("gate_id") != gate or w.get("gate_path") != GATE_FILES[gate]:
            e("P6C-08", f"{wp}: gate must be {gate} at {GATE_FILES[gate]}")
        gtext = d["gates"].get(gate, "")
        if not gtext or meta_row(gtext, "Document ID") != gate:
            e("P6C-08", f"{gate} file missing or Document ID mismatch")
        if gate not in cdoc:
            e("P6C-08", f"closure document does not reference {gate}")
        if not set(w.get("primary_artifacts") or []) <= {a.get("path") for a in (m.get("snapshot") or {}).get("artifacts", [])}:
            e("P6C-09", f"{wp}: primary artifacts must all be pinned in the snapshot")
    if sorted(g for g in gate_ids if g) != sorted(GATE_FILES):
        e("P6C-08", f"GATE-019..GATE-024 must each be referenced exactly once, found {gate_ids}")

    # ---------------- P6C-09 / 10 / 11 snapshot
    snap = m.get("snapshot") or {}
    arts = snap.get("artifacts") or []
    paths = [a.get("path") for a in arts]
    if len(paths) != len(set(paths)) or len({a.get("id") for a in arts}) != len(arts):
        e("P6C-09", "snapshot artifacts must be unique by id and path")
    missing = REQUIRED_ARTIFACTS - set(paths)
    if missing:
        e("P6C-09", f"canonical artifact inventory incomplete: {sorted(missing)}")
    for p in paths:
        if not isinstance(p, str) or p.startswith("/") or ".." in p.split("/") or EXCLUDED_PATH.search(p):
            e("P6C-09", f"artifact path {p!r} is not a repository-relative canonical path")
    for a in arts:
        p = a.get("path")
        actual = ctx["actual_sha"].get(p) if p in ctx["actual_sha"] else sha256_file(ROOT / str(p))
        if actual is None:
            e("P6C-10", f"pinned artifact {p} does not exist")
        elif a.get("sha256") != actual:
            e("P6C-11", f"{a.get('id')} {p}: pinned {a.get('sha256')} != actual {actual} (drift without a governed snapshot revision)")

    # ---------------- P6C-12 logical-object coverage
    text = d["data001_text"]
    objs = []
    if "## 6. Matrix A" in text and "## 7." in text:
        s0 = text.index("## 6. Matrix A")
        objs = re.findall(r"^\| \d+ \| `([A-Za-z]+)` \|", text[s0:text.index("## 7.", s0)], re.M)
    if len(objs) < 20:
        e("P6C-12", f"could not parse DATA-001 Matrix A ({len(objs)} objects)")
    if set(objs) != set(cov):
        e("P6C-12", f"coverage keys != DATA-001 Matrix A: missing {sorted(set(objs) - set(cov))}, extra {sorted(set(cov) - set(objs))}")
    deferred = [k for k, v in cov.items() if not isinstance(v, list)]
    if deferred != ["Feedback"]:
        e("P6C-12", f"only Feedback may be deferred, found {deferred}")
    for t in tables:
        if t.get("name") not in (cov.get(t.get("logical_object")) or []):
            e("P6C-12", f"table {t.get('name')} not listed under its logical object {t.get('logical_object')}")
    for o, v in cov.items():
        for tn in v if isinstance(v, list) else []:
            if tn not in tmap:
                e("P6C-12", f"{o} mapped to unknown table {tn}")
    if counts.get("postgresql_tables") != len(tables):
        e("P6C-12", f"manifest postgresql_tables {counts.get('postgresql_tables')} != measured {len(tables)}")
    if counts.get("data001_logical_objects") != len(objs) or counts.get("data001_deferred_logical_objects") != len(deferred):
        e("P6C-12", "manifest logical-object counts != DATA-001 Matrix A")
    gia = tmap.get("governed_input_artifact") or {}
    if not any(u.get("columns") == ["evaluation_id"] for u in gia.get("unique", [])):
        e("P6C-12", "evaluation <-> governed_input_artifact must stay exactly 1:1 (UNIQUE(evaluation_id))")

    # ---------------- P6C-13 ApiIdempotencyRecord
    air = tmap.get("api_idempotency_record") or {}
    idem = ops.get("idempotency") or {}
    if air.get("logical_object") != "ApiIdempotencyRecord" or cov.get("ApiIdempotencyRecord") != ["api_idempotency_record"] \
            or idem.get("logical_object") != "ApiIdempotencyRecord":
        e("P6C-13", "api_idempotency_record must map exactly to ApiIdempotencyRecord (persistence, coverage, OPS-001)")
    if cov.get("CrossStoreOperation") != ["cross_store_operation"]:
        e("P6C-13", "CrossStoreOperation must keep its original meaning (cross_store_operation only)")
    scope = ["principal_reference_id", "operation_id", "target_resource_scope", "idempotency_key_digest"]
    if idem.get("scope") != scope or not any(u.get("columns") == scope for u in air.get("unique", [])):
        e("P6C-13", "idempotency scope must be principal + operation + target + key digest with a unique constraint")
    key = idem.get("key") or {}
    if key.get("stored_form") != "SHA256_DIGEST" or key.get("raw_key_stored") is not False:
        e("P6C-13", "idempotency key must be stored as a digest, never raw")
    claim = idem.get("claim") or {}
    if claim.get("check_then_insert") is not False or claim.get("fence_column") != "claim_token" \
            or (idem.get("outcome_storage") or {}).get("response_body_stored") is not False \
            or (idem.get("outcome_storage") or {}).get("c4_content_stored") is not False \
            or (idem.get("request_fingerprint") or {}).get("digest_column") != "request_semantic_digest" \
            or (idem.get("active_window") or {}).get("bound") != "FINITE":
        e("P6C-13", "idempotency must keep atomic claim, fencing, semantic digest, finite window and no C4 response cache")

    # ---------------- P6C-14 GovernedRemovalTombstone
    grt = tmap.get("governed_removal_tombstone") or {}
    dele = ops.get("deletion") or {}
    if grt.get("logical_object") != "GovernedRemovalTombstone" or cov.get("GovernedRemovalTombstone") != ["governed_removal_tombstone"] \
            or dele.get("tombstone_logical_object") != "GovernedRemovalTombstone":
        e("P6C-14", "governed_removal_tombstone must map exactly to GovernedRemovalTombstone")
    if "governed_removal_tombstone" in (cov.get("DeletionAction") or []) or (tmap.get("deletion_action") or {}).get("logical_object") != "DeletionAction":
        e("P6C-14", "DeletionAction must remain distinct from the tombstone")

    # ---------------- P6C-15 / 16 / 17 API / OpenAPI
    n_api, n_oas = len(api.get("operations", [])), sum(1 for _ in iter_ops(oas))
    act = ops.get("api_activation") or {}
    if not (n_api == counts.get("api_operations") == act.get("operation_count_after")):
        e("P6C-15", f"API operation count {n_api} != manifest {counts.get('api_operations')} / OPS-001 {act.get('operation_count_after')}")
    if n_oas != counts.get("openapi_operations"):
        e("P6C-16", f"OpenAPI operation count {n_oas} != manifest {counts.get('openapi_operations')}")
    if set(catops) != set(oasops) or any(len(v) != 1 for v in oasops.values()):
        e("P6C-17", f"operation sets differ: catalog-only {sorted(set(catops) - set(oasops))}, OpenAPI-only {sorted(set(oasops) - set(catops))}")
    for oid, c in catops.items():
        if oid not in oasops:
            continue
        p, meth, op = oasops[oid][0]
        resp = op.get("responses", {})
        rb = op.get("requestBody")
        req = (rb or {}).get("x-trustlens-binary-body") or schema_name(((rb or {}).get("content") or {}).get("application/json", {}).get("schema"))
        sr = resp.get(str(c.get("success_status")), {})
        res = sr.get("x-trustlens-binary-body") or schema_name((sr.get("content") or {}).get("application/json", {}).get("schema"))
        sec = op.get("security", oas.get("security"))
        diffs = []
        if (meth.upper(), p) != (c.get("method"), c.get("path")):
            diffs.append("method/path")
        if [k for k in resp if k.startswith("2")] != [str(c.get("success_status"))]:
            diffs.append("success status")
        if req != c.get("request_schema"):
            diffs.append("request schema")
        if res != c.get("response_schema"):
            diffs.append("response schema")
        if (sec == []) != bool(c.get("internal")) or (not c.get("internal") and sec != [{"bearerAuth": []}]):
            diffs.append("authentication")
        for k, ck in (("x-trustlens-roles", "roles"), ("x-trustlens-resource-authorization", "resource_authorization"),
                      ("x-trustlens-idempotency", "idempotency"), ("x-trustlens-sensitivity", "sensitivity"),
                      ("x-trustlens-mode", "mode"), ("x-trustlens-concurrency", "concurrency")):
            if op.get(k) != c.get(ck):
                diffs.append(ck)
        if op.get("x-trustlens-audit") != {"required": c.get("audit") == "REQUIRED", "event": c.get("audit_event")}:
            diffs.append("audit")
        if diffs:
            e("P6C-17", f"{oid}: API/OpenAPI parity broken on {diffs}")

    # ---------------- P6C-18 listEvaluationEnrichments
    leb = (m.get("enrichment_boundary") or {}).get("list_evaluation_enrichments") or {}
    le = catops.get("listEvaluationEnrichments") or {}
    loas = (oasops.get("listEvaluationEnrichments") or [(None, None, {})])[0]
    lpath = "/api/v1/evaluations/{evaluation_id}/enrichments"
    if (le.get("method"), le.get("path")) != ("GET", lpath) or (loas[1], loas[0]) != ("get", lpath):
        e("P6C-18", "listEvaluationEnrichments must be GET /api/v1/evaluations/{evaluation_id}/enrichments in catalog and OpenAPI")
    if "availability" in le or "x-trustlens-availability" in (loas[2] or {}) or \
            (integ.get("api_surface") or {}).get("availability") != "ACTIVE_CONTRACT" or act.get("availability_after") != "ACTIVE_CONTRACT":
        e("P6C-18", "listEvaluationEnrichments must be ACTIVE_CONTRACT (no FUTURE guard) in catalog, OpenAPI, INT-001 and OPS-001")
    if "Phase 9" not in str(act.get("runtime_serving")) or leb.get("state") != "ACTIVE_CONTRACT" or leb.get("runtime_deployed") is not False:
        e("P6C-18", "activation is contract-level only; runtime serving remains Phase 9 (not runtime-deployed)")
    view = {f.get("name") for f in ((api.get("schemas") or {}).get("EnrichmentView") or {}).get("fields", [])}
    if view != ENRICHMENT_VIEW_FIELDS or any(FORBIDDEN_RESPONSE.search(n or "") for n in view):
        e("P6C-18", f"EnrichmentView must expose only advisory metadata {sorted(ENRICHMENT_VIEW_FIELDS)}, found {sorted(view, key=str)}")
    if leb.get("raw_provider_response_exposed") is not False or leb.get("provider_credential_exposed") is not False \
            or leb.get("response") != "ADVISORY_METADATA" or leb.get("operation_id") != "listEvaluationEnrichments":
        e("P6C-18", "manifest must record advisory metadata with no raw provider response or credential")

    # ---------------- P6C-19 DetectionResult immutable
    dr = tmap.get("detection_result") or {}
    if dr.get("mutability") != "M-IMM" or dr.get("mutable_columns"):
        e("P6C-19", "detection_result must be M-IMM with no mutable columns")
    for oid, c in catops.items():
        if c.get("target_resource") == "DetectionResult" and c.get("method") != "GET":
            e("P6C-19", f"{oid}: DetectionResult is immutable; only GET is permitted")
    for p, meth, op in iter_ops(oas):
        if (op.get("x-trustlens-target-resource") == "DetectionResult" or p.endswith("/result")) and meth != "get":
            e("P6C-19", f"OpenAPI {meth.upper()} {p}: DetectionResult is immutable")
    if dele.get("detection_result_status_mutation") is not False or (m.get("deletion") or {}).get("detection_result_immutable") is not True \
            or (m.get("authority_hierarchy") or {}).get("detection_result") != "IMMUTABLE_AFTER_COMPLETION":
        e("P6C-19", "deletion must never mutate DetectionResult; manifest must record immutability")

    # ---------------- P6C-20 no invented decision semantics
    for label, doc in (("persistence", per), ("API catalog", api), ("OpenAPI", oas), ("manifest", m)):
        bad = sorted({n for n in names_in(doc) if DRIFT.search(n)})
        if bad:
            e("P6C-20", f"{label} declares decision-drift names {bad[:5]}")
    db = m.get("decision_boundary") or {}
    if db.get("phase6_new_decision_fields") != [] or not DECISION_FORBIDDEN <= set(db.get("forbidden_introductions") or []) \
            or db.get("authoritative_engine") != "PHASE_3_DETERMINISTIC_ENGINE":
        e("P6C-20", "decision boundary must keep Phase 3 authoritative with no new decision fields")
    if (ops.get("decision_semantics") or {}).get("new_decision_fields") != [] or \
            (ops.get("decision_semantics") or {}).get("provider_verdict_as_trustlens_verdict") is not False:
        e("P6C-20", "OPS-001 must introduce no decision fields / provider verdicts")
    p3 = (d["phase3_result_schema"].get("properties") or {}).get("classification") or {}
    if ((per.get("vocabularies") or {}).get("classification") or {}).get("values") != p3.get("enum"):
        e("P6C-20", "persistence classification vocabulary must equal the Phase-3 DetectionResult enum exactly")

    # ---------------- P6C-21 / 22 enrichment boundary
    eb = m.get("enrichment_boundary") or {}
    ep = ops.get("enrichment_persistence") or {}
    idb = integ.get("decision_boundary") or {}
    if idb.get("consumed_in_governed_artifact") is not False or ep.get("consumed_in_governed_artifact") is not False \
            or eb.get("consumed_in_governed_artifact") is not False or ep.get("phase3_mapping_introduced") is not False:
        e("P6C-21", "external enrichment must remain consumed_in_governed_artifact = false (advisory only)")
    never = {x.lower() for x in idb.get("provider_may_never_set", [])} | {x.lower().replace("_", "") for x in eb.get("provider_may_never_set", [])}
    if not PROVIDER_NEVER <= never or idb.get("provider_may_set") != [] or idb.get("phase3_sole_decision_authority") is not True:
        e("P6C-21", "provider output must never set classification / risk / severity / confidence / DetectionResult")
    if ep.get("provider_clean") != "PROVIDER_ASSERTION_ONLY" or act.get("clean_presentation") != "PROVIDER_ASSERTION" \
            or eb.get("provider_clean") != "PROVIDER_ASSERTION_ONLY" or ep.get("not_found_meaning") != "ABSENCE_OF_INFORMATION" \
            or not {"SAFE", "LEGITIMATE", "VERIFIED"} <= set(idb.get("forbidden_result_meanings", [])) \
            or set(eb.get("not_trustlens_safe") or []) != {"CLEAN", "NOT_FOUND", "UNAVAILABLE"}:
        e("P6C-22", "provider CLEAN / NOT_FOUND / UNAVAILABLE must never mean TrustLens safe")
    for label, t in (("closure document", cdoc), ("GATE-025", gdoc)):
        bad = [ln for ln in t.splitlines() if re.search(r"\bCLEAN\b", ln) and re.search(r"\bsafe\b", ln, re.I) and not NEG.search(ln)]
        if bad:
            e("P6C-22", f"{label} presents provider CLEAN as safe: {bad[0][:100]}")

    # ---------------- P6C-23..27 replay
    rp = ops.get("replay") or {}
    ih = (integ.get("replay") or {}).get("historical") or {}
    mr = m.get("replay") or {}
    forb = set(rp.get("forbidden") or [])
    if "AI_CALL" not in forb or ih.get("ai_substitute") is not False or mr.get("calls_ai") is not False \
            or (m.get("ai_boundary") or {}).get("historical_replay_calls_ai") is not False:
        e("P6C-23", "historical replay must never call AI")
    if "ENRICHMENT_PROVIDER_CALL" not in forb or ih.get("provider_call") is not False or ih.get("refetch") is not False \
            or mr.get("calls_external_provider") is not False:
        e("P6C-24", "historical replay must never call an external enrichment provider")
    if not {"LATEST_OR_CURRENT_KNOWLEDGE", "CURRENT_EVIDENCE"} <= forb or ih.get("use_latest_provider_policy") is not False \
            or mr.get("uses_latest_or_current_knowledge") is not False or mr.get("substitutes_current_evidence") is not False \
            or rp.get("replaces_authoritative_result") is not False:
        e("P6C-25", "historical replay must never use latest/current knowledge or current evidence")
    pids = [r.get("id") for r in per.get("replay_material_set", [])]
    if pids != RM_IDS or rp.get("material_ids") != RM_IDS or mr.get("material_ids") != RM_IDS or rp.get("material_kinds_added") != [] \
            or counts.get("replay_material_items") != len(RM_IDS):
        e("P6C-26", f"replay material set must remain exactly RM-01..RM-14 (persistence {pids})")
    if rp.get("missing_material") != "REPLAY_UNAVAILABLE" or ih.get("missing_material") != "REPLAY_UNAVAILABLE" \
            or mr.get("missing_material") != "REPLAY_UNAVAILABLE" or ih.get("approximation") is not False \
            or not {"APPROXIMATION_OF_DELETED_MATERIAL", "NEW_EVALUATION"} <= forb or mr.get("creates_new_evaluation") is not False \
            or "REPLAY_UNAVAILABLE" not in (catops.get("createReplay") or {}).get("errors", []):
        e("P6C-27", "missing replay material must be REPLAY_UNAVAILABLE with no approximation or silent new Evaluation")
    if rp.get("enrichment_required_for_detection_result_replay") is not False or mr.get("enrichment_required_for_current_replay") is not False:
        e("P6C-27", "external enrichment must not be required for current DetectionResult replay")

    # ---------------- P6C-28 report regeneration
    rep = ops.get("report") or {}
    mrep = m.get("report_regeneration") or {}
    if rep.get("missing_source") != "REPORT_REGENERATION_UNAVAILABLE" or rep.get("hidden_retained_copy") is not False \
            or rep.get("reconstruct_from_latest") is not False or rep.get("regeneration_requires") != "RETAINED_PINNED_SOURCE_MATERIAL" \
            or mrep.get("required_material_deleted") != "REPORT_REGENERATION_UNAVAILABLE" or mrep.get("hidden_retained_copy") is not False \
            or mrep.get("latest_substitution") is not False \
            or "REPORT_REGENERATION_UNAVAILABLE" not in (catops.get("getReportContent") or {}).get("errors", []):
        e("P6C-28", "report regeneration after required deletion must be REPORT_REGENERATION_UNAVAILABLE (no hidden copy, no latest)")

    # ---------------- P6C-29 tombstone
    tcols = {c.get("name") for c in grt.get("columns", [])}
    allowed = set(dele.get("tombstone_allowed_fields") or []) | {"governed_removal_tombstone_id"}
    if not tcols or not tcols <= allowed or not TOMB_FORBIDDEN <= set(dele.get("tombstone_forbidden_content") or []) \
            or dele.get("tombstone_digest_retained") is not False or (m.get("deletion") or {}).get("tombstone_content_free") is not True:
        e("P6C-29", f"tombstone must be content-free (unexpected columns {sorted(tcols - allowed)})")

    # ---------------- P6C-30 deletion
    md = m.get("deletion") or {}
    if dele.get("completion_requires") != "ALL_REQUIRED_ACTIONS_VERIFIED_ABSENT" or dele.get("completion_on_call_return") is not False \
            or not {"PARTIALLY_FAILED", "FAILED"} <= set(dele.get("partial_failure_states") or []) \
            or dele.get("distributed_transaction") is not False or dele.get("ecs_failure_hidden_by_ops_deletion") is not False \
            or dele.get("ops_failure_hidden_by_ecs_deletion") is not False or md.get("distributed_transaction_claimed") is not False \
            or md.get("complete_requires") != "ALL_REQUIRED_ACTIONS_VERIFIED" or md.get("mechanism") != ["DeletionAction", "GovernedRemovalTombstone"]:
        e("P6C-30", "deletion must not report COMPLETE before every required action is verified; failures explicit")

    # ---------------- P6C-31 restore
    rs = ops.get("restore") or {}
    mrs = m.get("restore") or {}
    if rs.get("anti_resurrection_required") is not True or rs.get("check_before_promotion") is not True \
            or rs.get("missing_deletion_record") != "PROMOTION_BLOCKED" or rs.get("backup_media_physical_purge_claimed") is not False \
            or "AUTHORITATIVE" not in str(rs.get("reconciliation_source")) or "not rolled back" not in str(rs.get("reconciliation_source_note")) \
            or mrs.get("anti_resurrection_required") is not True or mrs.get("authority_unavailable") != "PROMOTION_FAILS_CLOSED" \
            or mrs.get("backup_copies_immediately_purged_claimed") is not False:
        e("P6C-31", "restore must reconcile against non-rolled-back deletion authority and fail closed before promotion")

    # ---------------- P6C-32..34 carryover closures
    co = by_id(m.get("carryover_closures"))
    src = {"IDEMPOTENCY_PERSISTENCE": idem.get("carryover"), "ETAG_REVISION_PERSISTENCE": (ops.get("concurrency") or {}).get("carryover"),
           "ENRICHMENT_PERSISTENCE": ep.get("carryover")}
    for cid, code in CARRYOVERS.items():
        c = co.get(cid) or {}
        if c.get("contract_status") != "CONTRACT-LEVEL CLOSED" or c.get("runtime_implementation") != "Phase 9" \
                or c.get("runtime_implemented") is not False:
            e(code, f"{cid}: must be CONTRACT-LEVEL CLOSED with runtime implementation pending Phase 9 (not implemented)")
        if "CONTRACT-LEVEL CLOSED" not in str(src[cid]) or "Phase 9" not in str(src[cid]):
            e(code, f"{cid}: OPS-001 carryover must record CONTRACT-LEVEL CLOSED / runtime Phase 9")
    cc = ops.get("concurrency") or {}
    rev = cc.get("revision") or {}
    if rev.get("monotonic") is not True or rev.get("client_writable") is not False or rev.get("server_authoritative") is not True \
            or rev.get("reuse_permitted") is not False or (cc.get("etag") or {}).get("strength") != "STRONG" \
            or (cc.get("etag") or {}).get("derivation") != "MUTATION_REVISION" or (cc.get("etag") or {}).get("opaque") is not True:
        e("P6C-33", "ETag must be a strong opaque validator from a server-authoritative, monotonic, non-client-writable revision")
    guarded = {o for o, c in catops.items() if c.get("concurrency") not in (None, "NONE")}
    agg_ops = {o for a in cc.get("aggregates", []) for o in a.get("operations", [])}
    if guarded != agg_ops:
        e("P6C-33", f"If-Match operations {sorted(guarded)} != OPS-001 aggregates {sorted(agg_ops)}")
    for a in cc.get("aggregates", []):
        if "mutation_revision" not in {c.get("name") for c in (tmap.get(a.get("table")) or {}).get("columns", [])}:
            e("P6C-33", f"{a.get('table')}: If-Match guarded aggregate lacks mutation_revision")

    # ---------------- P6C-35 ADRs Accepted
    for label, t in (("ADR-0012", d["adr0012_text"]), ("ADR-0011", d["adr0011_text"])):
        if not meta_row(t, "Status").startswith("**Accepted**"):
            e("P6C-35", f"{label} must be Accepted")
    if (integ.get("adr") or {}).get("status") != "Accepted" or (m.get("security") or {}).get("adr_0012_status") != "Accepted":
        e("P6C-35", "INT-001 and the manifest must record ADR-0012 Accepted")

    # ---------------- P6C-36 egress / no generic fetch
    eg = integ.get("egress") or {}
    sc = integ.get("scope") or {}
    sec = m.get("security") or {}
    if eg.get("default") != "DENY" or eg.get("generic_fetch_primitive") is not False or eg.get("destination_authority") != "GOVERNED_PROVIDER_POLICY" \
            or "GENERIC_FETCH" not in sc.get("forbidden_capabilities", []) or (sc.get("submitted_url_semantics") or {}).get("treated_as") != "LOOKUP_DATA_ONLY" \
            or (sc.get("submitted_url_semantics") or {}).get("connect_to_submitted_destination") is not False \
            or (integ.get("request_construction") or {}).get("user_input_may_populate") != ["indicator_value"] \
            or sec.get("egress_default") != "DENY" or sec.get("generic_fetch") is not False:
        e("P6C-36", "egress must be deny-by-default to governed destinations with no generic fetch; submitted URL is data only")
    for p, meth, op in iter_ops(oas):
        if re.search(r"/(fetch|proxy|browse|crawl|url-fetch)(/|$)", p):
            e("P6C-36", f"OpenAPI exposes a fetch-like endpoint {meth.upper()} {p}")
    if not {"DNS_RESOLVE_VALIDATE_CONNECT_BINDING", "ACTUAL_PEER_VALIDATION", "MIXED_ANSWER_REJECTION",
            "REDIRECT_REVALIDATION", "NO_DOWNGRADE"} <= set(sec.get("controls") or []):
        e("P6C-36", "manifest must restate DNS/peer/mixed-answer/redirect/no-downgrade controls")

    # ---------------- P6C-37 governed proxy
    px = integ.get("proxy") or {}
    if px.get("final_hop_enforcement") != "REQUIRED_AND_VERIFIED" or px.get("environment_proxy_inheritance") is not False \
            or px.get("enforcement_evidence") != "GOVERNED_VERIFIABLE_EVIDENCE_REQUIRED" \
            or sec.get("governed_proxy_final_hop") != "REQUIRED_AND_VERIFIED" \
            or sec.get("unverified_proxy") != "DEPLOYMENT_BLOCKED / POLICY_REJECTED" or sec.get("ssrf_universally_solved_claimed") is not False:
        e("P6C-37", "governed proxy final-hop enforcement must be REQUIRED_AND_VERIFIED; unverified proxy blocked")
    for label, t in (("closure document", cdoc), ("GATE-025", gdoc)):
        if unnegated_lines(t, SSRF_SOLVED):
            e("P6C-37", f"{label} claims SSRF is solved")

    # ---------------- P6C-38..41 open items / Phase 1
    if (oi.get("G-09") or {}).get("state") != "OPEN" or (ops.get("open_items") or {}).get("G-09") != "OPEN" \
            or (integ.get("open_items") or {}).get("G-09") != "OPEN" or "**G-09**" not in d["gap_text"]:
        e("P6C-38", "G-09 must remain OPEN")
    ret = next((p for p in ops.get("runtime_parameters", []) if p.get("id") == "RETENTION_DURATIONS"), {})
    if (oi.get("OI-05") or {}).get("state") != "OPEN" or (ops.get("open_items") or {}).get("OI-05") != "OPEN" \
            or ret.get("applies_when") != "GOVERNED_AUTOMATIC_EXPIRY_ENABLED" or ret.get("value") != NYS \
            or (integ.get("retention") or {}).get("duration") != NYS:
        e("P6C-39", "OI-05 must remain OPEN; no retention duration; expiry only when governed automatic expiry is enabled")
    ten = m.get("tenancy") or {}
    asm_row = next((ln for ln in d["assumption_text"].splitlines() if ln.startswith("| ASM-002")), "")
    if (oi.get("ASM-002") or {}).get("state") != "UNCONFIRMED / PROVISIONAL" or ten.get("status") != "UNCONFIRMED / PROVISIONAL" \
            or ten.get("sponsor_confirmation_recorded") is not False or (ops.get("tenancy") or {}).get("status") != "UNCONFIRMED / PROVISIONAL" \
            or (per.get("tenancy") or {}).get("asm_002_status") != "UNCONFIRMED_PROVISIONAL" or not asm_row \
            or re.search(r"\bCONFIRMED\b", asm_row.replace("UNCONFIRMED", "")):
        e("P6C-40", "ASM-002 must remain UNCONFIRMED / PROVISIONAL with no invented sponsor confirmation")
    if m.get("phase1_status") != "PARTIAL" or "Phase 1 is `PARTIAL`" not in d["gate001_text"]:
        e("P6C-41", "Phase-1 status must remain PARTIAL (GATE-001)")

    # ---------------- P6C-42 tenancy
    for label, doc in (("persistence", per), ("API catalog", api), ("OpenAPI", oas), ("integration", integ),
                       ("operations", ops), ("manifest", m)):
        bad = sorted({n for n in names_in(doc) if TENANT.search(n)})
        if bad:
            e("P6C-42", f"{label} introduces tenant fields {bad[:3]} while ASM-002 is unconfirmed")
    if ten.get("tenant_fields_introduced") is not False or (per.get("tenancy") or {}).get("tenant_columns_permitted") is not False:
        e("P6C-42", "no tenant field may be introduced")

    # ---------------- P6C-43 ENGINE_VERSION
    ev = re.search(r'^ENGINE_VERSION\s*=\s*"([^"]+)"', d["engine_text"], re.M)
    if not ev or ev.group(1) != "1.0.0" or m.get("engine_version") != "1.0.0" \
            or (ops.get("decision_semantics") or {}).get("engine_version") != "1.0.0" or idb.get("engine_version") != "1.0.0":
        e("P6C-43", "ENGINE_VERSION must remain 1.0.0 (engine, manifest, OPS-001, INT-001)")

    # ---------------- P6C-44 numeric policy
    def numfn(n, path):
        if isinstance(n, bool) or n is None:
            return
        if isinstance(n, (int, float)):
            ok = any(path[:len(k)] == k for k in NUMERIC_KEYS) or \
                (len(path) >= 3 and path[0] == "work_packages" and path[-1] in NUMERIC_WP_KEYS) or \
                (path[:1] == ("current_work_package",) and path[-1] in NUMERIC_WP_KEYS)
            if not ok:
                e("P6C-44", f"manifest numeric value at {'/'.join(map(str, path))} is not a count or identifier")
        elif isinstance(n, str) and (not path or path[-1] not in DIGEST_KEYS) and DURATION_LITERAL.search(n):
            e("P6C-44", f"manifest string at {'/'.join(map(str, path))} carries an invented duration/size literal")
    walk(m, numfn)
    rps = ops.get("runtime_parameters", [])
    op_ = m.get("operational_parameters") or {}
    cls = {}
    for p in rps:
        cls[p.get("deployment_requirement")] = cls.get(p.get("deployment_requirement"), 0) + 1
        if p.get("value") != NYS or not p.get("owner"):
            e("P6C-44", f"runtime parameter {p.get('id')} must stay NOT YET SPECIFIED with an owner")
    if len(rps) != 24 or op_.get("count") != len(rps) or counts.get("operational_runtime_parameters") != len(rps) \
            or op_.get("classes") != cls or op_.get("value") != NYS or op_.get("numeric_values_invented") is not False \
            or cls.get("REQUIRED_BEFORE_DEPLOYMENT_SECURITY_OR_CORRECTNESS") != counts.get("parameters_security_or_correctness") \
            or cls.get("CONFIGURATION_REQUIRED_FOR_IMPLEMENTATION_PROFILE") != counts.get("parameters_implementation_profile"):
        e("P6C-44", f"operational parameters must remain 24 NOT YET SPECIFIED with their existing classes {cls}")

    # ---------------- P6C-45 premature closure (lifecycle-aware)
    gaps = wp7_evidence_gaps(m)
    claims = [("manifest closure_status", m.get("closure_status", "")), ("manifest phase_state", m.get("phase_state", "")),
              ("manifest P6-WP7 state", str(cur.get("state"))), ("closure document status", meta_row(cdoc, "Status")),
              ("GATE-025 status", meta_row(gdoc, "Status"))]
    for label, text_ in claims:
        if premature(text_) and gaps:
            e("P6C-45", f"{label} claims closure without complete P6-WP7 closure evidence (missing: {gaps})")
    if m.get("closure_status") != CLOSED_STATUS or m.get("phase_state") != "CLOSED" or cur.get("state") != "CLOSED":
        e("P6C-45", "manifest closure_status / phase_state / P6-WP7 state must be consistently CLOSED (no pending current state)")

    # ---------------- P6C-46 lifecycle: historical "not started at closure" vs current repository state
    h7 = m.get("phase7_handoff") or {}
    if h7.get("phase7_status_at_phase6_closure") != "NOT STARTED" or h7.get("phase7_started_at_phase6_closure") is not False \
            or any(x.get("status_at_phase6_closure") != "NOT STARTED" for x in m.get("later_phase_handoff") or []):
        e("P6C-46", "Phase 7 and later phases must be recorded as NOT STARTED at the moment Phase 6 closed")
    if d["later_gates"] and not evidenced_closed(m):
        e("P6C-46", f"later-phase gates {d['later_gates']} exist while Phase 6 is not CLOSED with complete P6-WP7 evidence")
    if not re.search(r"Phase 7[^\n]{0,40}NOT STARTED", cdoc):
        e("P6C-46", "closure document must record that Phase 7 had NOT STARTED when Phase 6 closed")

    # ---------------- P6C-47 implementation deferred
    dl = by_id(m.get("implementation_deferred"), "item")
    if not DEFERRED_REQUIRED <= set(dl) or any(not (v or {}).get("owner") for v in dl.values()):
        e("P6C-47", f"implementation-deferred list incomplete: {sorted(DEFERRED_REQUIRED - set(dl))}")
    if m.get("implementation_status") != "CONTRACT COMPLETE — NOT PRODUCT IMPLEMENTED":
        e("P6C-47", "implementation status must be CONTRACT COMPLETE — NOT PRODUCT IMPLEMENTED")
    impl = ops.get("implementation") or {}
    if not impl or any(v is not False for v in impl.values()) or RUNTIME_DEPS.search(d["requirements"]) or ctx["migration_paths"]:
        e("P6C-47", "no runtime implementation (framework, ORM, migrations, workers, connector) may exist in Phase 6")

    # ---------------- P6C-48..50 claim boundary
    cb = m.get("claim_boundary") or {}
    may, mustnot = set(cb.get("may_support") or []), set(cb.get("must_not_support") or [])
    for code, toks, pat in (("P6C-48", PROD_TOKENS, PROD_CLAIM), ("P6C-49", LEGAL_TOKENS, LEGAL_CLAIM),
                            ("P6C-50", EFFECT_TOKENS, EFFECT_CLAIM)):
        if may & toks or not toks <= mustnot:
            e(code, f"claim boundary must forbid {sorted(toks)} (found in may_support: {sorted(may & toks)})")
        for label, t in (("closure document", cdoc), ("GATE-025", gdoc)):
            bad = unnegated_lines(t, pat)
            if bad:
                e(code, f"{label} makes an affirmative claim: {bad[0]}")
    if may - MAY_SUPPORT:
        e("P6C-48", f"may_support contains unapproved claims {sorted(may - MAY_SUPPORT)}")
    if not MAY_SUPPORT <= may:
        e("P6C-48", "may_support must list the supportable contract claims")

    # ---------------- P6C-51 / 52 Phase-7 handoff
    if not PHASE7_MAY <= set(h7.get("may_design") or []) or not re.search(r"^#+ .*Phase-7 handoff", cdoc, re.M | re.I):
        e("P6C-51", "Phase-7 handoff must be present (manifest may_design + closure document section)")
    md7, mn7 = set(h7.get("may_design") or []), set(h7.get("must_not_redefine") or [])
    if not PHASE7_MUST_NOT <= mn7 or md7 & mn7 or any(DECISION_TOKEN.search(x) for x in md7):
        e("P6C-52", "Phase-7 handoff must not redefine classification/risk/severity/confidence/decision/authorization/"
                    "data/replay/provider-CLEAN/retention/network semantics")

    # ---------------- P6C-53 open-item owners
    for k, v in oi.items():
        if any(not str((v or {}).get(f, "")).strip() for f in ("state", "why_open", "phase6_impact", "future_owner", "blocking")):
            e("P6C-53", f"open item {k} must carry state, reason, impact, future owner and blocking scope")
        if re.search(r"\bCLOSED\b", str((v or {}).get("state"))):
            e("P6C-53", f"open item {k} may not be labelled CLOSED")
    for k, want in OPEN_ITEMS_REQUIRED.items():
        if k not in oi:
            e("P6C-53", f"open item {k} missing")
        elif (oi[k] or {}).get("state") != want:
            e("P6C-53", f"open item {k} state must remain {want!r}")

    # ---------------- P6C-54 offline
    if NETWORK_IMPORT.search(d["self_source"]):
        e("P6C-54", "closure validator imports a network-capable or subprocess module")
    ci = m.get("ci") or {}
    if ci.get("live_network") is not False or ci.get("api_keys_required") is not False or ci.get("database_required") is not False:
        e("P6C-54", "closure validation must need no network, API key or database")

    # ---------------- P6C-56 review history (gate files are authority)
    for wp, gate, _, _ in EXPECTED_WPS:
        row = meta_row(d["gates"].get(gate, ""), "Independent review")
        final = row.split("Targeted re-review")[-1]
        if "APPROVE" not in final or not all(f"{k} 0" in final for k in ("BLOCKER", "HIGH", "MEDIUM")):
            e("P6C-56", f"{gate}: final independent review must be APPROVE with BLOCKER/HIGH/MEDIUM 0")
        if "APPROVE" not in str((wpmap.get(wp) or {}).get("independent_review")):
            e("P6C-56", f"{wp}: manifest must record the approving independent review")
    if m.get("unresolved_phase6_review_findings") != {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 0}:
        e("P6C-56", "no unresolved Phase-6 BLOCKER/HIGH/MEDIUM may remain")

    # ---------------- P6C-57 remote CI evidence
    for w in wps:
        rc = w.get("remote_ci") or {}
        if rc.get("conclusion") != "success" or rc.get("checks") != CI_CHECKS or not isinstance(rc.get("pr_head_run_id"), int) \
                or not isinstance(rc.get("merge_commit_run_id"), int) or "not re-verified by offline CI" not in str(rc.get("evidence_source")):
            e("P6C-57", f"{w.get('id')}: remote CI evidence (both checks, success, run ids, evidence source) must be recorded")

    # ---------------- P6C-58 authorization (ADR-0009)
    fv = (api.get("field_visibility") or {}).get("raw_evidence_content") or {}
    bg = catops.get("createBreakGlassGrant") or {}
    au = m.get("authorization") or {}
    if fv.get("ADMINISTRATOR") != "BREAK_GLASS_ONLY" or bg.get("roles") != ["ADMINISTRATOR"] \
            or "ASSIGNEE_NOT_CALLER" not in json.dumps(api) \
            or any(c.get("authentication") != "REQUIRED" for c in catops.values() if not c.get("internal")) \
            or au.get("administrator_raw_evidence_by_role") is not False or au.get("break_glass_creation_roles") != ["ADMINISTRATOR"] \
            or au.get("review_self_assignment") is not False or au.get("default") != "DENY" or au.get("principal") != "OIDC":
        e("P6C-58", "authorization must stay ADR-0009: deny by default, no admin raw evidence by role, admin-only break-glass, no self-assignment")

    # ---------------- P6C-59 knowledge activation
    kar = {f.get("name"): f for f in ((api.get("schemas") or {}).get("KnowledgeActivationRequest") or {}).get("fields", [])}
    ka = m.get("knowledge_activation") or {}
    if (kar.get("content_digest") or {}).get("required") is not True or (kar.get("content_digest") or {}).get("pattern") != "^[0-9a-f]{64}$" \
            or "bundle_version" in kar or any(re.search(r"latest", c.get("path", ""), re.I) for c in catops.values()) \
            or any(re.search(r"/(rules|rule|indicators|taxonomy|rule-sets)(/|$)", c.get("path", "")) and c.get("method") != "GET" for c in catops.values()) \
            or ka.get("identity") != "EXACT_IMMUTABLE_CONTENT_DIGEST" or ka.get("activate_latest") is not False \
            or ka.get("bundle_version_only_activation") is not False or ka.get("rule_body_mutation_api") is not False:
        e("P6C-59", "knowledge activation must use an exact immutable content_digest (no latest / bundle_version / rule mutation)")

    # ---------------- P6C-60 unsupported language
    ul = m.get("unsupported_language_boundary") or {}
    if "UNSUPPORTED" not in ((per.get("vocabularies") or {}).get("classification") or {}).get("values", []) \
            or "never** represented as safe" not in text or ul.get("unsupported_is_benign") is not False \
            or ul.get("phase3_semantics_changed") is not False or ul.get("classification_on_unsupported") != "UNSUPPORTED":
        e("P6C-60", "unsupported / non-English input must never be treated as benign (ADR-0014)")
    for label, t in (("closure document", cdoc), ("GATE-025", gdoc)):
        bad = [ln for ln in t.splitlines() if re.search(r"unsupported|non-English", ln, re.I)
               and re.search(r"\b(benign|safe)\b", ln, re.I) and not NEG.search(ln)]
        if bad:
            e("P6C-60", f"{label} implies unsupported = benign: {bad[0][:100]}")

    # ---------------- P6C-61 AI boundary
    ab = m.get("ai_boundary") or {}
    iab = integ.get("ai_boundary") or {}
    if ab.get("may_influence_deterministic_output_via") != "VALIDATED_GOVERNED_OBSERVATIONS_ONLY" \
            or not AI_MAY_NOT <= set(ab.get("may_not_directly") or []) or iab.get("destination_control") is not False \
            or iab.get("ssrf_policy_bypass") is not False or iab.get("provider_policy_mutation") is not False \
            or iab.get("phase4_authority") != "NON_AUTHORITATIVE" or (ops.get("decision_semantics") or {}).get("phase4_changed") is not False:
        e("P6C-61", "AI may influence deterministic output only through validated governed observations, never directly")
    for label, t in (("closure document", cdoc), ("GATE-025", gdoc)):
        if AI_WRONG.search(t):
            e("P6C-61", f"{label} states AI cannot influence the decision (inaccurate: it can, via governed observations)")

    # ---------------- P6C-62 authority hierarchy / raw evidence / secrets
    ah = m.get("authority_hierarchy") or {}
    if any(ah.get(k) != v for k, v in HIERARCHY.items()) or set(ah.get("forbidden_substitutions") or []) != FORBIDDEN_SUBSTITUTIONS:
        e("P6C-62", "authority hierarchy must be restated exactly (knowledge=Git/CI/bundle, PostgreSQL=operational, ECS=content, ...)")
    for t in tables:
        if "KNOWLEDGE_AUTHORITY" in str(t.get("authority")) and t.get("authority") != "REFERENCE_TO_KNOWLEDGE_AUTHORITY":
            e("P6C-62", f"{t.get('name')}: PostgreSQL is never knowledge authority")
        for c in t.get("columns", []):
            if c.get("type") == "bytea" and (t.get("name"), c.get("name")) not in BYTEA_ALLOWED:
                e("P6C-62", f"{t.get('name')}.{c.get('name')}: raw content bytes are not stored in PostgreSQL")
            cn = c.get("name", "")
            if (RAW_CONTENT_COLUMN.search(cn) or SECRET_COLUMN.search(cn)) and not REFERENCE_SUFFIX.search(cn):
                e("P6C-62", f"{t.get('name')}.{c.get('name')}: raw evidence / secret material is not stored in PostgreSQL")
    if "ecs_locator" not in {c.get("name") for c in (tmap.get("evidence_item") or {}).get("columns", [])}:
        e("P6C-62", "evidence bytes must be referenced by ECS locator")

    # ---------------- P6C-63 re-analysis
    ra = ops.get("reanalysis") or {}
    mra = m.get("reanalysis") or {}
    if ra.get("creates") != "NEW_EVALUATION" or ra.get("overwrites_history") is not False or mra.get("creates") != "NEW_EVALUATION" \
            or mra.get("overwrites_historical_evaluation") is not False \
            or (integ.get("replay") or {}).get("reanalysis", {}).get("overwrite_historical") is not False:
        e("P6C-63", "re-analysis must create a new Evaluation and never overwrite history")

    # ---------------- P6C-64 provider policy
    pp = ops.get("provider_policy") or {}
    mpp = m.get("provider_policy") or {}
    if pp.get("lifecycle") != ["VALIDATED", "PUBLISHED", "ACTIVE", "WITHDRAWN"] or pp.get("immutable_after_publication") is not True \
            or pp.get("latest_by_name_authority") is not False or pp.get("activation_by") != "EXACT_IDENTITY" \
            or pp.get("history_retained") is not True or not POLICY_EXCLUDED <= set(pp.get("may_not_change") or []) \
            or pp.get("public_api") is not False or "Phase-9" not in str(pp.get("storage")) \
            or pp.get("identity") != ["provider_policy_ref", "provider_policy_version", "provider_policy_digest"] \
            or mpp.get("latest_by_name_authority") is not False or mpp.get("immutable_after_publication") is not True \
            or not POLICY_EXCLUDED <= set(mpp.get("may_not_mutate") or []) or mpp.get("physical_store") != "Phase 9":
        e("P6C-64", "provider policy must stay immutable, exact-identity, history-retaining, governed-only; storage Phase 9")
    return errs


def _select(node, seg):
    if isinstance(seg, dict):
        (k, v), = seg.items()
        for i, item in enumerate(node):
            if (k == "$value" and item == v) or (isinstance(item, dict) and item.get(k) == v):
                return i
        raise KeyError(f"no element with {k}={v!r}")
    return seg


def apply_mutation(docs: dict, mut: dict) -> dict:
    if "steps" in mut:  # composite mutation / lifecycle scenario: apply each step in order
        out = docs
        for step in mut["steps"]:
            out = apply_mutation(out, step)
        return out
    out = dict(docs)
    tgt = mut.get("target", "closure")
    if mut["op"] == "append" and not mut.get("path"):
        out[tgt] = list(docs[tgt]) + [copy.deepcopy(mut["value"])]
        return out
    if mut["op"] in ("replace_text", "append_text"):
        text = docs[tgt]
        if mut["op"] == "append_text":
            out[tgt] = text + mut["value"]
        else:
            if mut["old"] not in text:
                raise KeyError(f"text {mut['old']!r} not found in {tgt}")
            out[tgt] = text.replace(mut["old"], mut["new"], 1)
        return out
    if tgt == "gates":
        raise ValueError("gate texts are mutated via text targets only")
    doc = copy.deepcopy(docs[tgt])
    node = doc
    for seg in mut["path"][:-1]:
        node = node[_select(node, seg)]
    last = _select(node, mut["path"][-1])
    if mut["op"] == "set":
        node[last] = copy.deepcopy(mut["value"])
    elif mut["op"] == "append":
        node[last].append(copy.deepcopy(mut["value"]))
    elif mut["op"] == "remove":
        del node[last]
    else:
        raise ValueError(f"unknown op {mut['op']}")
    out[tgt] = doc
    return out


def inputs() -> tuple[dict, dict]:
    docs = {"closure": load(MANIFEST_PATH), "schema": load(SCHEMA_PATH)}
    docs.update({k: load(p) for k, p in JSON_INPUTS.items()})
    docs.update({k: read(p) for k, p in TEXT_INPUTS.items()})
    docs["gates"] = {g: read(ROOT / p) for g, p in GATE_FILES.items()}
    # current repository state: later-phase gates (GATE-026+) legitimately appear once Phase 6 is CLOSED
    docs["later_gates"] = sorted(p.name for p in PROGRAM.glob("GATE-*.md")
                                 if re.match(r"GATE-(\d+)", p.name) and int(re.match(r"GATE-(\d+)", p.name).group(1)) > 25)
    snap_paths = {a.get("path") for a in docs["closure"].get("snapshot", {}).get("artifacts", [])} | REQUIRED_ARTIFACTS
    ctx = {
        "actual_sha": {p: sha256_file(ROOT / p) for p in snap_paths if isinstance(p, str)},
        "migration_paths": [p for p in MIGRATION_PATHS if (ROOT / p).exists()],
    }
    return docs, ctx


def main() -> int:
    quiet = "--quiet" in sys.argv
    try:
        docs, ctx = inputs()
    except (OSError, json.JSONDecodeError) as ex:
        print(f"  FAIL  P6C-03  closure inputs unreadable: {ex!r}")
        print("PHASE-6 CLOSURE: FAIL")
        return 1
    errs = check(docs, ctx)
    if errs:
        for code, msg in errs:
            print(f"  FAIL  {code}  {msg}")
        print(f"PHASE-6 CLOSURE: FAIL — {len(errs)} violation(s)")
        return 1
    negatives = load(NEGATIVE_PATH)["mutations"]
    failures = []
    for mut in negatives:
        try:
            mutated = apply_mutation(docs, mut)
        except (KeyError, IndexError, ValueError, TypeError) as ex:
            failures.append(f"{mut['id']}: mutation could not be applied ({ex})")
            continue
        found = {code for code, _ in check(mutated, ctx)}
        if mut["expect"] not in found:
            failures.append(f"{mut['id']}: expected {mut['expect']}, got {sorted(found) or 'no violation'}")
        elif not quiet:
            print(f"  ok    {mut['id']} rejected by {mut['expect']}: {mut['description']}")
    positives = load(NEGATIVE_PATH).get("positive_scenarios", [])
    for sc in positives:
        try:
            found = sorted({code for code, _ in check(apply_mutation(docs, sc), ctx)})
        except (KeyError, IndexError, ValueError, TypeError) as ex:
            failures.append(f"{sc['id']}: positive scenario could not be applied ({ex})")
            continue
        if found:
            failures.append(f"{sc['id']}: positive lifecycle scenario must pass, got {found}")
        elif not quiet:
            print(f"  ok    {sc['id']} accepted: {sc['description']}")
    if failures:
        for f in failures:
            print(f"  FAIL  negative fixture {f}")
        print("PHASE-6 CLOSURE: FAIL — a guard did not bite")
        return 1
    n_checks = len(set(re.findall(r"^  (P6C-\d\d) ", __doc__, re.M)))
    m = docs["closure"]
    print(f"PHASE-6 CLOSURE: PASS — {m['closure_status']} at baseline {m['baseline_commit'][:12]}; {len(m['work_packages'])} "
          f"merged predecessor WPs; {len(m['snapshot']['artifacts'])} canonical artifacts SHA-256 pinned and verified; "
          f"{m['contract_counts']['postgresql_tables']} tables / {m['contract_counts']['api_operations']} API = "
          f"{m['contract_counts']['openapi_operations']} OpenAPI operations; {n_checks} checks; {len(positives)} positive lifecycle scenario(s) accepted; {len(negatives)} negative "
          f"mutations rejected (static closure validation; no runtime exists; contract phase closed, not product implemented)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
