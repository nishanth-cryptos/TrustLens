"""TrustLens Phase 6 P6-WP6 — static validator for the OPS-001 operational / replay / persistence-follow-up contract.

Validates contracts/operations/operational-v1.json against contracts/operations/operational-contract.schema.json and
against the artifacts it revises or binds: the P6-WP6 additive revision of contracts/postgresql/schema-v1.json, the
listEvaluationEnrichments activation in contracts/api/api-v1.json and contracts/api/openapi-v1.json, the INT-001
machine contract, OPS-001, GATE-024 and the revised documents. It also replays the contract's offline scenarios
(idempotency, ETag/If-Match, cross-store deletion, restore anti-resurrection, replay, report regeneration, historical
enrichment reads) through small REFERENCE MODELS driven by the contract's own policy values. No database, server,
network or API key is used; this proves contract coherence, not runtime behaviour (no runtime exists).

  OC-01 OPS-001 exists, Version 0.1, status APPROVED FOLLOWING INDEPENDENT REVIEW with remote CI + merge pending
        (contract status agrees); never claimed closed/merged before that
  OC-02 GATE-024 exists with status P6-WP6 OPERATIONAL CONTRACT APPROVED, remote CI + merge pending (not closed)
  OC-03 operational contract is valid against its JSON Schema (Draft 2020-12)
  OC-04 offline only: no external $ref or URL dependency; CI needs no network/database/API key; no network import
  OC-05 durable idempotency table exists in the persistence contract with the required columns
  OC-06 idempotency scope = principal + operation_id + target resource + key digest, enforced by a full unique constraint
  OC-07 semantic request digest required, versioned, excludes transport metadata, not the Phase-3 result digest
  OC-08 concurrent duplicate execution prevented structurally (atomic claim on the unique scope, fence, atomic completion)
  OC-09 same key + same request returns the original outcome without re-execution; key never authorizes
  OC-10 same key + different request maps to 409 IDEMPOTENCY_KEY_REUSED
  OC-11 same key while executing maps to 409 IDEMPOTENCY_IN_PROGRESS
  OC-12 no unrestricted response-body / C4 cache in idempotency records
  OC-13 finite, server-set active window and claim lease
  OC-14 no numeric idempotency retention / lease invented
  OC-15 If-Match aggregates derived exactly from the API catalog
  OC-16 every guarded aggregate table has a monotonic mutation_revision
  OC-17 mutation_revision is server-only (not client-writable, not an API field)
  OC-18 revision increments on every committed mutation and never decreases or repeats
  OC-19 ETag/CAS derive from the revision, never from representation or timestamp alone
  OC-20 immutable resources do not gain a mutation revision
  OC-21 enrichment additive persistence fields complete (INT-001 provenance/cache/freshness/artifact)
  OC-22 technical lookup-outcome vocabulary exact (INT-001 = OPS-001 = persistence) and status-consistent
  OC-23 safe_error_category constrained to the exact INT-001 failure vocabulary
  OC-24 provider CLEAN remains a provider assertion; NOT_FOUND remains absence of information
  OC-25 consumed_in_governed_artifact remains false; no Phase-3 mapping introduced
  OC-26 response-artifact digest, policy identity and retained-material locator represented; no raw body inline
  OC-27 historical enrichment records immutable; changes create new records
  OC-28 enrichment and provider-policy audit additions present; EGRESS_DENIED reused
  OC-29 audit-read accountability event present and wired to listAuditEvents (catalog + OpenAPI)
  OC-30 audit-read event copies no returned audit bodies, does not recurse per row, is appended after the result
        snapshot and before return (never in the same response), and an append failure withholds the read
  OC-31 governed removal tombstone exists (410 lookup key, deletion-request link)
  OC-32 DetectionResult remains immutable; deletion never mutates its status
  OC-33 tombstone excludes governed content and digests of deleted content
  OC-34 deletion COMPLETE requires verified absence of every required action
  OC-35 partial failure explicit at request and action level (persistence vocabularies agree)
  OC-36 no false completion across the OPS/ECS split; governed idempotent retry
  OC-37 restore anti-resurrection required before promotion; no backup-purge claim
  OC-38 report regeneration unavailable after required source deletion
  OC-39 replay unavailable after required material deletion (no approximation)
  OC-40 replay never calls AI
  OC-41 replay never calls an external enrichment provider
  OC-42 replay never uses latest/current knowledge or evidence and never replaces the authoritative result
  OC-43 RM-01..RM-14 binding unchanged; enrichment not added to DetectionResult replay (RM-09)
  OC-44 re-analysis remains a new Evaluation
  OC-45 provider policy versions immutable once published; history retained; no retroactive change
  OC-46 provider policy exact identity (ref + version + digest) pinned on every enrichment
  OC-47 no latest-by-name provider policy authority in replay
  OC-48 provider policy authority excludes user/analyst/AI/provider/adapter; no public API; no storage vendor
  OC-49 listEvaluationEnrichments activation consistent across API catalog, OpenAPI, INT-001 contract and OPS-001
  OC-50 its method/path/operationId/roles/authorization/status/pagination unchanged
  OC-51 enrichment response remains advisory and content-safe (exact EnrichmentView fields; CLEAN as provider assertion)
  OC-52 API/OpenAPI operation parity exact; operation count unchanged; base stays /api/v1
  OC-53 required runtime-parameter registry exists and covers the deferred parameters
  OC-54 parameters finite with owners; safety/correctness ones REQUIRED_BEFORE_DEPLOYMENT_SECURITY_OR_CORRECTNESS (fail
        closed), tuning ones CONFIGURATION_REQUIRED_FOR_IMPLEMENTATION_PROFILE (not a security gate)
  OC-55 no numeric policy value fabricated
  OC-56 no tenant field / routing (ASM-002 UNCONFIRMED / PROVISIONAL)
  OC-57 G-09 remains OPEN
  OC-58 OI-05 remains OPEN; retention durations apply only when governed automatic expiry is enabled
  OC-59 ENGINE_VERSION remains 1.0.0
  OC-60 no runtime implementation introduced (no web framework/ORM/migration/HTTP-client dependency or migration tree)
  OC-61 persistence additive revision recorded (contract 0.2.0, DATA-001-WP2 section, not covered by earlier gates)
  OC-62 API-001 / OAS-001 / catalog mark the P6-WP6 ADDITIVE ACTIVATION delta
  OC-63 OpenAPI ETag server-revision decision unchanged and its persistence dependency marked satisfied by P6-WP6
  OC-64 async work idempotent and fenced; evaluation fencing unchanged; no generic worker table
  OC-65 no decision-semantic drift (no score/probability/priority/verdict fields; Phase-3/4 unchanged)
  OC-66 offline scenarios evaluate to their expected outcome under the contract's own policy
  OC-67 api_idempotency_record and governed_removal_tombstone map to the DATA-001 objects ApiIdempotencyRecord and
        GovernedRemovalTombstone, which DATA-001 declares (Matrix A + object section); no unrelated-object mapping remains

It then applies every mutation in contracts/operations/fixtures/negative-mutations.json (to the operational contract
or, via "target", to the persistence / API / OpenAPI / integration contract) and requires the named check to fail.

Usage:  .venv/bin/python knowledge/validation/validate_operational_contract.py [--quiet]
Exit 0 = contract consistent and every negative mutation rejected by its expected check.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[2]
PATHS = {
    "operations": ROOT / "contracts" / "operations" / "operational-v1.json",
    "persistence": ROOT / "contracts" / "postgresql" / "schema-v1.json",
    "api": ROOT / "contracts" / "api" / "api-v1.json",
    "openapi": ROOT / "contracts" / "api" / "openapi-v1.json",
    "integration": ROOT / "contracts" / "integrations" / "external-enrichment-v1.json",
}
SCHEMA_PATH = ROOT / "contracts" / "operations" / "operational-contract.schema.json"
NEGATIVE_PATH = ROOT / "contracts" / "operations" / "fixtures" / "negative-mutations.json"
DOCS = {
    "ops": ROOT / "docs" / "06-contracts" / "OPS-001-operational-replay-persistence-contract.md",
    "gate": ROOT / "docs" / "00-program" / "GATE-024-phase-6-operational-contract.md",
    "wp2": ROOT / "docs" / "06-contracts" / "DATA-001-WP2-postgresql-persistence-contract.md",
    "data001": ROOT / "docs" / "06-contracts" / "DATA-001-data-domain-lifecycle-contract.md",
    "api": ROOT / "docs" / "06-contracts" / "API-001-api-resource-protocol-contract.md",
    "oas": ROOT / "docs" / "06-contracts" / "OAS-001-openapi-contract.md",
}
REQUIREMENTS_PATH = ROOT / "requirements.txt"
ENGINE_PATH = ROOT / "knowledge" / "runtime" / "engine.py"

NYS = "NOT YET SPECIFIED"
APPROVED = "P6-WP6 OPERATIONAL CONTRACT APPROVED FOLLOWING INDEPENDENT REVIEW — REMOTE CI + MERGE PENDING"
GATE_APPROVED = "P6-WP6 OPERATIONAL CONTRACT APPROVED"
PENDING = "REMOTE CI + MERGE PENDING"
PREMATURE = re.compile(r"\b(CLOSED|MERGED|REMOTE CI PASS)", re.I)
NEGATED = re.compile(r"\bnot (yet )?(formally )?(closed|merged)\b", re.I)
HEX64 = "^[0-9a-f]{64}$"
METHODS = ("get", "put", "post", "delete", "patch", "options", "head", "trace")
IDEM_SCOPE = ["principal_reference_id", "operation_id", "target_resource_scope", "idempotency_key_digest"]
IDEM_COLUMNS = {"principal_reference_id": "uuid", "operation_id": "text", "target_resource_scope": "text",
                "idempotency_key_digest": "text", "request_fingerprint_version": "text", "request_semantic_digest": "text",
                "execution_state": "text", "claim_token": "uuid", "in_progress_lease_until": "timestamptz",
                "outcome_http_status": "integer", "created_at": "timestamptz", "terminal_at": "timestamptz",
                "active_until": "timestamptz"}
TRANSPORT_HEADERS = {"X-Request-Id", "traceparent", "Idempotency-Key", "Connection"}
SAFE_AUDIT_READ_FIELDS = {"actor_principal_id", "occurred_at", "correlation_id", "scope_category"}
INT_AUDIT_EVENTS = {"ENRICHMENT_REQUESTED", "PROVIDER_POLICY_SELECTED", "ENRICHMENT_ACCEPTED", "CREDENTIAL_REFERENCE_FAILURE"}
POLICY_EVENTS = {"PROVIDER_POLICY_PUBLISHED", "PROVIDER_POLICY_ACTIVATED", "PROVIDER_POLICY_WITHDRAWN"}
TOMB_FORBIDDEN = {"DETECTION_RESULT_BODY", "RAW_EVIDENCE", "REPORT_CONTENT", "PROVIDER_RAW_BODY", "C4_RATIONALE",
                  "SECRET_MATERIAL", "DELETED_CONTENT_DIGEST"}
REPLAY_FORBIDDEN = {"AI_CALL", "ENRICHMENT_PROVIDER_CALL", "LATEST_OR_CURRENT_KNOWLEDGE", "CURRENT_EVIDENCE",
                    "APPROXIMATION_OF_DELETED_MATERIAL", "NEW_EVALUATION"}
POLICY_EXCLUDED = {"END_USER", "ANALYST", "AI", "PROVIDER_RESPONSE", "ADAPTER_RUNTIME"}
ENRICHMENT_VIEW_FIELDS = {"enrichment_id", "provider_category", "status", "reputation_result", "observed_at", "advisory"}
FORBIDDEN_RESPONSE = re.compile(r"(raw|locator|credential|secret|authorization|network|target_host|policy_ref|evidence)", re.I)
REQ_PARAMS = {"IDEMPOTENCY_ACTIVE_WINDOW", "INLINE_VS_ECS_THRESHOLD", "PAGINATION_DEFAULT_LIMIT", "PAGINATION_MAX_LIMIT",
              "RATE_LIMIT_THRESHOLDS", "BREAK_GLASS_MAX_DURATION", "PROVIDER_CONNECT_TIMEOUT", "PROVIDER_READ_TIMEOUT",
              "PROVIDER_OVERALL_DEADLINE", "PROVIDER_RETRY_MAX_ATTEMPTS", "PROVIDER_BACKOFF_BOUNDS",
              "PROVIDER_REDIRECT_MAX_HOPS", "PROVIDER_WIRE_RESPONSE_MAX_BYTES", "PROVIDER_DECODED_RESPONSE_MAX_BYTES",
              "PROVIDER_CACHE_TTL_AND_FRESHNESS_PERIODS", "PROVIDER_CIRCUIT_BREAKER_THRESHOLDS",
              "EVALUATION_EXECUTION_LEASE", "OPERATIONAL_WORKER_RETRY_MAX_ATTEMPTS", "OPERATIONAL_WORKER_BACKOFF_BOUNDS"}
NUMERIC_EXEMPT_PREFIXES = (("scenarios",), ("api_activation", "operation_count_before"), ("api_activation", "operation_count_after"))
TENANT = re.compile(r"tenant[_-]?id|tenantid|x-tenant|tenant_ref|tenant_key", re.I)
DRIFT = re.compile(r"(probab|score|likelihood|ranking|priority|verdict)", re.I)
RUNTIME_DEPS = re.compile(r"^\s*(fastapi|flask|django|starlette|uvicorn|gunicorn|sqlalchemy|alembic|psycopg|psycopg2|"
                          r"asyncpg|requests|httpx|aiohttp|urllib3|celery|rq)\b", re.I | re.M)
NETWORK_IMPORT = re.compile(r"^\s*(import|from)\s+(socket|requests|httpx|aiohttp|urllib|http|ssl)\b", re.M)
MIGRATION_PATHS = ("alembic.ini", "alembic", "migrations", "db/migrations")
DELETION_MARKER_COLUMNS = {"status", "deleted", "is_deleted", "deleted_at", "removed", "removed_at", "removal_state",
                           "lifecycle_state", "tombstoned", "content_state"}
REQ_SCENARIOS = {"SI-01", "SI-02", "SI-03", "SI-04", "SE-01", "SE-02", "SE-03", "SD-01", "SD-02", "SD-03", "SX-01",
                 "SR-01", "SR-02", "SR-03", "SR-04", "SR-06", "SN-01"}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def walk(node, fn, path=()):
    fn(node, path)
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, fn, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, fn, path + (i,))


def status_line(text: str) -> str:
    m = re.search(r"^\|\s*Status\s*\|\s*(.+?)\s*\|\s*$", text, re.M)
    return m.group(1) if m else ""


def premature(status: str) -> bool:
    """True if a status claims closure/merge/remote-CI success (explicit negations such as 'not yet closed' excepted)."""
    return bool(PREMATURE.search(NEGATED.sub("", status)))


def finite_nys(lim) -> bool:
    return isinstance(lim, dict) and lim.get("bound") == "FINITE" and lim.get("value") == NYS and bool(lim.get("owner"))


# ------------------------------------------------------------------ offline reference models (contract-driven)

IDEM_FIELD = {"principal_reference_id": "principal", "operation_id": "operation", "target_resource_scope": "target",
              "idempotency_key_digest": "key"}


def model_idempotency(s, c):
    idem = c["idempotency"]
    ex, req = s["existing"], s["request"]
    fields = [IDEM_FIELD[f] for f in idem["scope"] if f in IDEM_FIELD]
    if not fields or not all(ex[f] == req[f] for f in fields):
        return "EXECUTE"
    out = idem["outcomes"]
    if ex["digest"] != req["digest"]:
        return out.get("different_request", "EXECUTE")
    if ex["state"] == "IN_PROGRESS" and ex["lease_live"]:
        return out.get("same_request_in_progress", "EXECUTE")
    if ex["state"] in ("COMPLETED", "FAILED_TERMINAL"):
        return out.get("same_request_terminal", "EXECUTE")
    return out.get("released_after_transient_failure", "EXECUTE")


def model_etag(s, c):
    cc = c["concurrency"]
    rev = cc["revision"]
    if s["kind"] == "SEQUENCE":
        if cc["etag"]["derivation"] == "MUTATION_REVISION" and rev["increments_every_committed_mutation"] \
                and not rev["decrement_permitted"] and not rev["reuse_permitted"]:
            tags = list(range(1, len(s["states"]) + 1))
        elif cc["etag"]["derivation"] == "MUTATION_REVISION":
            tags = [1] * len(s["states"])
        else:
            tags = list(s["states"])  # representation/timestamp-derived validators can repeat
        return "DISTINCT" if len(set(tags)) == len(tags) else "COLLISION"
    w = cc["write"]
    if s["if_match_revision"] is None:
        return w["missing_if_match"]
    if s["if_match_revision"] != s["current_revision"]:
        return "MUTATED_WITH_STALE_ETAG" if w["mismatch_mutates"] else w["revision_mismatch"]
    return "COMMITTED_REVISION_ADVANCED" if rev["increments_every_committed_mutation"] else "COMMITTED_REVISION_UNCHANGED"


def model_deletion(s, c):
    d = c["deletion"]
    ok = []
    for a in s["actions"]:
        if d["completion_on_call_return"] or d["completion_requires"] != "ALL_REQUIRED_ACTIONS_VERIFIED_ABSENT":
            good = a["call_returned"]
        else:
            good = a["verification"] == "VERIFIED_ABSENT"
        if (a["store"] == "ECS" and d["ecs_failure_hidden_by_ops_deletion"]) or \
                (a["store"] == "OPS" and d["ops_failure_hidden_by_ecs_deletion"]):
            good = True
        ok.append(good)
    if all(ok):
        return "COMPLETE", "CREATE_TOMBSTONE" in d["workflow"]
    if any(ok):
        return ("PARTIALLY_FAILED" if "PARTIALLY_FAILED" in d["partial_failure_states"] else "COMPLETE"), False
    return ("FAILED" if "FAILED" in d["partial_failure_states"] else "COMPLETE"), False


def model_restore(s, c):
    r = c["restore"]
    if not s["snapshot_contains_deleted"]:
        return "PROMOTION_PERMITTED_AFTER_VERIFICATION"
    if not r["anti_resurrection_required"] or not r["check_before_promotion"]:
        return "PROMOTED_WITH_RESURRECTED_CONTENT"
    if s["deletion_record_available"]:
        return "REDELETE_AND_VERIFY_BEFORE_PROMOTION" if r["governed_deleted_content"].startswith("REMAIN_DELETED") \
            else "PROMOTED_WITH_RESURRECTED_CONTENT"
    return r["missing_deletion_record"]


def model_replay(s, c, rms):
    rp = c["replay"]
    forbidden = set(rp["forbidden"])
    required = {r["id"]: r for r in rms if r["required"] == "ALWAYS"
                or (r["required"] == "WHEN_AI_USED" and s["ai_used"])
                or (r["required"] == "WHEN_PRESENT_IN_LINEAGE" and s["lineage_derivatives"])}
    if rp["enrichment_required_for_detection_result_replay"] and not s["enrichment_provider_available"]:
        return "REPLAY_UNAVAILABLE_REQUIRED_ARTIFACT_MISSING"
    missing = [required[m] for m in s["missing"] if m in required]
    if not missing:
        return "REPLAY_CAPABLE"
    kinds = {m["kind"] for m in missing}
    if "AI_REPLAY_SNAPSHOT" in kinds and "AI_CALL" not in forbidden:
        return "AI_RERUN_SUBSTITUTED"
    if "KNOWLEDGE_BUNDLE" in kinds:
        return "LATEST_KNOWLEDGE_SUBSTITUTED" if "LATEST_OR_CURRENT_KNOWLEDGE" not in forbidden \
            else "REPLAY_UNAVAILABLE_BUNDLE_MISSING"
    if "APPROXIMATION_OF_DELETED_MATERIAL" not in forbidden or rp["missing_material"] != "REPLAY_UNAVAILABLE":
        return "APPROXIMATED"
    return "REPLAY_UNAVAILABLE_REQUIRED_ARTIFACT_MISSING"


def model_report(s, c):
    r = c["report"]
    if s["pinned_source_retained"]:
        return "REGENERATION_PERMITTED"
    if r["hidden_retained_copy"] or r["reconstruct_from_latest"]:
        return "RECONSTRUCTED_FROM_UNPINNED_MATERIAL"
    return r["missing_source"]


def model_enrichment(s, c):
    ep = c["enrichment_persistence"]
    if ep["historical_read"] == "FROM_IMMUTABLE_RECORD" and not ep["provider_call_on_historical_read"]:
        return "RETURNED_FROM_IMMUTABLE_RECORD_WITHOUT_PROVIDER_CALL"
    return "PROVIDER_CALLED"


# ------------------------------------------------------------------ checks

def check(docs: dict, ctx: dict) -> list[tuple[str, str]]:
    errs: list[tuple[str, str]] = []

    def e(code, msg):
        errs.append((code, msg))

    c, pz, api, oas, ic = docs["operations"], docs["persistence"], docs["api"], docs["openapi"], docs["integration"]

    def g(node, *keys, default=None):
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    tables = {t.get("name"): t for t in pz.get("tables", []) if isinstance(t, dict)}
    cols = {n: {col["name"]: col for col in t.get("columns", [])} for n, t in tables.items()}
    vocab = pz.get("vocabularies", {})
    vv = lambda n: list(g(vocab, n, "values", default=[]) or [])
    ops = {o.get("operation_id"): o for o in api.get("operations", [])}
    errors = {x.get("code"): x for x in api.get("error_codes", [])}
    oas_ops = {}
    for path, item in oas.get("paths", {}).items():
        for m, op in item.items():
            if m in METHODS and isinstance(op, dict):
                oas_ops[op.get("operationId")] = (m, path, op)

    # OC-01 / OC-02 documents
    if not ctx["ops_text"] or APPROVED not in status_line(ctx["ops_text"]) or premature(status_line(ctx["ops_text"])) or \
            not re.search(r"^\|\s*Version\s*\|\s*0\.1\s*\|", ctx["ops_text"], re.M):
        e("OC-01", f"OPS-001 must exist with Version 0.1 and status {APPROVED!r} (not closed/merged)")
    if c.get("status") != APPROVED:
        e("OC-01", f"operational contract status {c.get('status')!r} must be {APPROVED!r}")
    gst = status_line(ctx["gate_text"])
    if not ctx["gate_text"] or GATE_APPROVED not in gst or PENDING not in gst or premature(gst):
        e("OC-02", "GATE-024 must exist with status 'P6-WP6 OPERATIONAL CONTRACT APPROVED — REMOTE CI + MERGE PENDING' (not closed)")

    # OC-03 schema
    for err in sorted(ctx["validator"].iter_errors(c), key=lambda x: list(x.path)):
        e("OC-03", f"schema: {'/'.join(map(str, err.path)) or '<root>'}: {err.message[:160]}")

    # OC-04 offline
    def ext_ref(node, path):
        if isinstance(node, dict) and isinstance(node.get("$ref"), str) and not node["$ref"].startswith("#"):
            e("OC-04", f"external $ref at {'/'.join(map(str, path))}")
        if isinstance(node, str) and re.match(r"^https?://", node):
            e("OC-04", f"URL dependency at {'/'.join(map(str, path))}")
    walk(c, ext_ref)
    walk(ctx["schema"], lambda n, p: isinstance(n, dict) and isinstance(n.get("$ref"), str)
         and not n["$ref"].startswith("#") and e("OC-04", "operational schema has an external $ref"))
    if any(g(c, "ci", k) is not False for k in ("live_network", "database_required", "api_keys_required")):
        e("OC-04", "canonical CI must need no network, database or API key")
    if NETWORK_IMPORT.search(ctx["self_source"]):
        e("OC-04", "the operational validator imports a network module")

    # ---------------- idempotency
    idem = c.get("idempotency", {}) or {}
    it = tables.get(idem.get("persistence_table"))
    ic_cols = cols.get(idem.get("persistence_table"), {})
    if not it or it.get("name") != "api_idempotency_record":
        e("OC-05", "durable idempotency table api_idempotency_record missing from the persistence contract")
    else:
        for cn, ty in IDEM_COLUMNS.items():
            if cn not in ic_cols or ic_cols[cn]["type"] != ty:
                e("OC-05", f"api_idempotency_record.{cn} missing or not {ty}")
        if not any(fk["columns"] == ["principal_reference_id"] and fk["references"]["table"] == "principal_reference"
                   for fk in it.get("foreign_keys", [])):
            e("OC-05", "api_idempotency_record.principal_reference_id must reference principal_reference")
    uq = next((u for u in (it or {}).get("unique", []) if u.get("name") == idem.get("scope_unique_constraint")), None)
    if idem.get("scope") != IDEM_SCOPE:
        e("OC-06", f"idempotency scope must be exactly {IDEM_SCOPE}, got {idem.get('scope')}")
    if not uq or uq.get("columns") != IDEM_SCOPE or "where" in uq:
        e("OC-06", "a full (non-partial) unique constraint must enforce exactly the principal/operation/target/key scope")
    rf = idem.get("request_fingerprint", {}) or {}
    dcol = ic_cols.get(rf.get("digest_column"), {})
    if not rf.get("version") or dcol.get("content_kind") != "DIGEST" or dcol.get("pattern") != HEX64 or dcol.get("nullable"):
        e("OC-07", "a versioned, non-null SHA-256 semantic request digest column is required")
    if not TRANSPORT_HEADERS <= set(rf.get("excludes", [])):
        e("OC-07", f"semantic digest must exclude transport metadata {sorted(TRANSPORT_HEADERS - set(rf.get('excludes', [])))}")
    if rf.get("reuses_result_digest") is not False:
        e("OC-07", "semantic request digest must not reuse Phase-3 result digest semantics")
    cl = idem.get("claim", {}) or {}
    if cl.get("mechanism") != "INSERT_ON_CONFLICT_DO_NOTHING_ON_SCOPE_UNIQUE" or cl.get("check_then_insert") is not False \
            or cl.get("completion_atomic_with_effect") is not True or cl.get("fence_column") not in ic_cols:
        e("OC-08", "duplicate execution must be prevented by an atomic claim on the unique scope with a fence and atomic completion")
    out = idem.get("outcomes", {}) or {}
    key = idem.get("key", {}) or {}
    if out.get("same_request_terminal") != "RETURN_ORIGINAL_OUTCOME_WITHOUT_EXECUTION":
        e("OC-09", "same key + same request must return the original outcome without executing again")
    if key.get("authorization_credential") is not False or key.get("raw_key_stored") is not False \
            or key.get("stored_form") != "SHA256_DIGEST" or key.get("logged_as_authentication_material") is not False:
        e("OC-09", "the Idempotency-Key is stored only as a digest and never authorizes or is logged as authentication")
    if idem.get("authorization_order") != ["AUTHENTICATE", "AUTHORIZE", "CLAIM"]:
        e("OC-09", "normal authorization must run before the idempotency claim")
    if "idempotency_key" in ic_cols:
        e("OC-09", "raw idempotency_key column must not exist")
    if out.get("different_request") != "IDEMPOTENCY_KEY_REUSED" or g(errors, "IDEMPOTENCY_KEY_REUSED", "http_status") != 409:
        e("OC-10", "a conflicting request must map to 409 IDEMPOTENCY_KEY_REUSED")
    if out.get("same_request_in_progress") != "IDEMPOTENCY_IN_PROGRESS" or g(errors, "IDEMPOTENCY_IN_PROGRESS", "http_status") != 409:
        e("OC-11", "a duplicate during execution must map to 409 IDEMPOTENCY_IN_PROGRESS")
    os_ = idem.get("outcome_storage", {}) or {}
    if os_.get("response_body_stored") is not False or os_.get("c4_content_stored") is not False:
        e("OC-12", "idempotency must not cache response bodies or C4 content")
    for cn, col in ic_cols.items():
        if col["type"] == "jsonb" or col["classification"] in ("C3", "C4") or re.search(r"(body|payload|response_json)", cn):
            e("OC-12", f"api_idempotency_record.{cn} would cache response/C4 content")
    aw, lease = idem.get("active_window", {}) or {}, idem.get("claim_lease", {}) or {}
    if aw.get("bound") != "FINITE" or aw.get("server_set") is not True or aw.get("column") not in ic_cols \
            or lease.get("bound") != "FINITE" or lease.get("column") not in ic_cols \
            or not any(ck.get("name") == "ck_api_idempotency_window" for ck in (it or {}).get("checks", [])):
        e("OC-13", "a finite, server-set active window and finite claim lease are required")
    if not finite_nys(aw) or not finite_nys(lease):
        e("OC-14", "idempotency window/lease values must be NOT YET SPECIFIED with an owner (no invented duration)")

    # ---------------- ETag / mutation revision
    cc = c.get("concurrency", {}) or {}
    guarded = {}
    for o in api.get("operations", []):
        if o.get("concurrency") not in (None, "NONE"):
            guarded.setdefault(o.get("target_resource"), set()).add(o.get("operation_id"))
    declared = {a.get("resource"): set(a.get("operations", [])) for a in cc.get("aggregates", [])}
    if declared != guarded:
        e("OC-15", f"If-Match aggregates {declared} must equal those derived from the API catalog {guarded}")
    res_obj = {r.get("name"): r.get("data001_object") for r in api.get("resources", [])}
    rc = cc.get("revision_column")
    for a in cc.get("aggregates", []):
        tn = a.get("table")
        obj = res_obj.get(a.get("resource"))
        if tn not in (pz.get("logical_object_coverage", {}).get(obj) or []):
            e("OC-15", f"{a.get('resource')} table {tn!r} is not a persistence table of {obj}")
        col = cols.get(tn, {}).get(rc)
        t = tables.get(tn, {})
        if not col or col["type"] != "bigint" or col["nullable"] or rc not in t.get("mutable_columns", []) \
                or not any(ck.get("rule") == f"{rc} >= 1" for ck in t.get("checks", [])):
            e("OC-16", f"{tn} lacks a non-null bigint monotonic {rc} (mutable, positive-checked)")
        if not any(f"OLD.{rc} + 1" in gd for gd in t.get("transition_guards", [])):
            e("OC-18", f"{tn}: a database guard must increment {rc} by exactly one on every update")
    rev = cc.get("revision", {}) or {}
    if rev.get("client_writable") is not False or rev.get("api_field") is not False or rev.get("server_authoritative") is not True:
        e("OC-17", "mutation revision must be server-authoritative, not client-writable and not an API field")

    def rev_field(node, path):
        if isinstance(node, dict):
            for k in node:
                if re.search(r"(mutation_)?revision$", str(k)) and "properties" in path:
                    e("OC-17", f"API/OpenAPI exposes a revision field {k!r}")
    walk(oas.get("components", {}), rev_field)
    for name, sd in (api.get("schemas") or {}).items():
        if any(re.search(r"revision$", f.get("name", "")) for f in sd.get("fields", [])):
            e("OC-17", f"API catalog schema {name} exposes a revision field")
    if rev.get("monotonic") is not True or rev.get("increments_every_committed_mutation") is not True \
            or rev.get("increment") != "DATABASE_TRIGGER_PLUS_ONE" or rev.get("decrement_permitted") is not False \
            or rev.get("reuse_permitted") is not False:
        e("OC-18", "revision must be monotonic, +1 on every committed mutation, never decremented or reused")
    w = cc.get("write", {}) or {}
    if rev.get("derived_from") != "MUTATION_COUNTER" or rev.get("timestamp_only") is not False \
            or rev.get("representation_only") is not False or g(cc, "etag", "derivation") != "MUTATION_REVISION" \
            or g(cc, "etag", "opaque") is not True or g(cc, "etag", "strength") != "STRONG":
        e("OC-19", "the opaque strong ETag must derive from the mutation revision, never representation/timestamp alone")
    if w.get("mechanism") != "COMPARE_AND_SWAP" or "mutation_revision" not in str(w.get("predicate", "")) \
            or w.get("revision_mismatch") != "PRECONDITION_FAILED" or w.get("missing_if_match") != "PRECONDITION_REQUIRED" \
            or w.get("mismatch_mutates") is not False:
        e("OC-19", "If-Match writes must be compare-and-swap on mutation_revision (412 on mismatch, 428 when missing)")
    with_rev = {n for n, cs in cols.items() if rc and rc in cs}
    if with_rev != {a.get("table") for a in cc.get("aggregates", [])} or cc.get("immutable_resources_gain_revision") is not False \
            or any(tables[n].get("mutability") == "M-IMM" for n in with_rev):
        e("OC-20", f"only the guarded mutable aggregates may carry {rc}; found {sorted(with_rev)}")

    # ---------------- enrichment persistence
    ep = c.get("enrichment_persistence", {}) or {}
    et = tables.get("external_enrichment_result", {})
    ec = cols.get("external_enrichment_result", {})
    declared_cols = {r.get("column") for r in ep.get("required_columns", [])}
    int_required = {x.split(" ")[0] for x in ic.get("persistence_additive_requirements", [])
                    if " " not in x or x.startswith("safe_error_category")} - {"enrichment"}
    int_required |= {p.get("field") for p in g(ic, "provenance", "required_fields", default=[]) or []
                     if p.get("persistence") == "ADDITIVE_WP2_REVISION_REQUIRED"}
    int_required |= {"freshness_policy_ref"}
    missing = (int_required | declared_cols) - set(ec)
    if missing or not int_required <= declared_cols:
        e("OC-21", f"enrichment persistence incomplete: missing columns {sorted(missing)} / undeclared {sorted(int_required - declared_cols)}")
    lov = ep.get("lookup_outcome_vocabulary")
    if lov != g(ic, "outcomes", "vocabulary") or lov != vv("enrichment_lookup_outcome") \
            or g(ec, "lookup_outcome", "vocabulary") != "enrichment_lookup_outcome" \
            or not any(ck.get("name") == "ck_external_enrichment_outcome_status" for ck in et.get("checks", [])):
        e("OC-22", "lookup outcome vocabulary must equal INT-001 exactly, be bound in persistence and status-consistent")
    fail = [f.get("safe_error_category") for f in ic.get("failure_semantics", [])]
    if g(ec, "safe_error_category", "vocabulary") != ep.get("safe_error_category_vocabulary") \
            or vv(ep.get("safe_error_category_vocabulary", "")) != fail \
            or not any(ck.get("name") == "ck_external_enrichment_error_category" for ck in et.get("checks", [])):
        e("OC-23", "safe_error_category must be CHECK-bound to exactly the INT-001 failure vocabulary")
    view_desc = str(g(api, "schemas", "EnrichmentView", "description", default="")) + " " + \
        str(g(oas, "components", "schemas", "EnrichmentView", "description", default=""))
    if ep.get("provider_clean") != "PROVIDER_ASSERTION_ONLY" or ep.get("not_found_meaning") != "ABSENCE_OF_INFORMATION" \
            or not any(ck.get("name") == "ck_external_enrichment_not_found_unknown" for ck in et.get("checks", [])) \
            or view_desc.count("provider assertion") < 2 or view_desc.count("never TrustLens safe") < 2:
        e("OC-24", "provider CLEAN must stay a provider assertion (never TrustLens safe) and NOT_FOUND absence of information")
    if ep.get("consumed_in_governed_artifact") is not False or ep.get("phase3_mapping_introduced") is not False \
            or not any(ck.get("rule") == "NOT consumed_in_governed_artifact" for ck in et.get("checks", [])) \
            or g(ic, "decision_boundary", "consumed_in_governed_artifact") is not False:
        e("OC-25", "consumed_in_governed_artifact must remain false and no Phase-3 mapping may be introduced")
    for cn in ("response_artifact_digest", "provider_policy_digest"):
        if g(ec, cn, "content_kind") != "DIGEST" or g(ec, cn, "pattern") != HEX64:
            e("OC-26", f"external_enrichment_result.{cn} must be a SHA-256 digest column")
    if g(ec, "retained_provider_artifact_ecs_locator", "content_kind") != "OPAQUE_ECS_LOCATOR" \
            or ep.get("raw_provider_body_inline") is not False or ep.get("digest_proves") != "RECORDING_INTEGRITY_NOT_PROVIDER_TRUTH" \
            or any(col["type"] == "jsonb" for col in ec.values()):
        e("OC-26", "retained provider material must be an ECS locator only; no raw body inline; digest is not provider truth")
    if et.get("mutability") != "M-IMM" or et.get("mutable_columns") or ep.get("immutable") is not True or \
            not {"PROVIDER_REPUTATION_CHANGE", "CACHE_REFRESH", "PROVIDER_POLICY_CHANGE", "RE_ANALYSIS"} <= set(ep.get("new_record_on", [])):
        e("OC-27", "historical enrichment records must be immutable; every change creates a new record")

    # ---------------- audit
    aud = c.get("audit", {}) or {}
    at = set(vv("audit_event_type"))
    if not (INT_AUDIT_EVENTS | POLICY_EVENTS) <= at or not (INT_AUDIT_EVENTS | POLICY_EVENTS) <= {a.get("event") for a in aud.get("additions", [])}:
        e("OC-28", f"audit additions missing {sorted((INT_AUDIT_EVENTS | POLICY_EVENTS) - at)}")
    null_concepts = {ev.get("concept") for ev in g(ic, "audit", "events", default=[]) or [] if ev.get("audit_event_type") is None}
    if not null_concepts <= at or "EGRESS_DENIED" not in at or \
            set(aud.get("egress_denied_reused_for", [])) != {"POLICY_REJECTION", "SSRF_DESTINATION_REJECTION"}:
        e("OC-28", "every INT-001 audit concept must resolve to a persistence type; EGRESS_DENIED reused for rejections")
    ar = aud.get("audit_read", {}) or {}
    ev = ar.get("event")
    if not ev or ev not in at or g(ops, "listAuditEvents", "audit_event") != ev or \
            (oas_ops.get("listAuditEvents") or (None, None, {}))[2].get("x-trustlens-audit", {}).get("event") != ev:
        e("OC-29", "audit-read event must exist in persistence and be wired to listAuditEvents in catalog and OpenAPI")
    if ar.get("copies_returned_event_bodies") is not False or ar.get("per_row_events") is not False \
            or ar.get("granularity") != "ONE_EVENT_PER_AUTHORIZED_AUDIT_READ_OPERATION" \
            or not set(ar.get("records", [])) <= SAFE_AUDIT_READ_FIELDS or not ar.get("recursion_control"):
        e("OC-30", "audit-read accountability must record safe metadata only, once per read operation, without recursion")
    if ar.get("ordering") != ["AUTHORIZE_QUERY", "ESTABLISH_RESULT_SNAPSHOT", "APPEND_AUDIT_LOG_ACCESSED", "RETURN_ESTABLISHED_RESULT"] \
            or ar.get("access_event_in_same_response") is not False or ar.get("append_failure") != "READ_NOT_RETURNED":
        e("OC-30", "audit-read must authorize, snapshot, append one access event, then return the snapshot (no self-inclusion; "
                   "append failure withholds the read)")

    # ---------------- deletion / tombstone / restore
    dl = c.get("deletion", {}) or {}
    tt = tables.get(dl.get("tombstone_table"))
    tc = cols.get(dl.get("tombstone_table"), {})
    if not tt or not any(u.get("columns") == ["resource_kind", "prior_resource_id"] for u in tt.get("unique", [])) \
            or not any(fk["references"]["table"] == "deletion_request" for fk in tt.get("foreign_keys", [])):
        e("OC-31", "governed removal tombstone (unique resource_kind + prior_resource_id, linked to deletion_request) missing")
    dr = tables.get("detection_result", {})
    if dr.get("mutability") != "M-IMM" or dr.get("mutable_columns") or dl.get("detection_result_status_mutation") is not False \
            or DELETION_MARKER_COLUMNS & set(cols.get("detection_result", {})):
        e("OC-32", "DetectionResult must stay immutable; deletion never mutates it into a deleted result")
    allowed = set(dl.get("tombstone_allowed_fields", [])) | {f"{dl.get('tombstone_table')}_id"}
    for cn, col in tc.items():
        if cn not in allowed or col["classification"] in ("C3", "C4") or col["type"] in ("jsonb", "bytea") \
                or col.get("content_kind") in ("DIGEST", "OPAQUE_ECS_LOCATOR", "CANONICAL_ARTIFACT_JSON"):
            e("OC-33", f"tombstone column {cn} would retain governed content or a digest of deleted content")
    if dl.get("tombstone_digest_retained") is not False or not TOMB_FORBIDDEN <= set(dl.get("tombstone_forbidden_content", [])):
        e("OC-33", "tombstone must exclude governed content and digests of deleted content")
    wf = dl.get("workflow", [])
    if dl.get("completion_requires") != "ALL_REQUIRED_ACTIONS_VERIFIED_ABSENT" or dl.get("completion_on_call_return") is not False \
            or "VERIFY_ABSENCE_OR_MINIMIZATION" not in wf or "FINALIZE_REQUEST" not in wf \
            or wf.index("VERIFY_ABSENCE_OR_MINIMIZATION") > wf.index("FINALIZE_REQUEST") \
            or ("CREATE_TOMBSTONE" in wf and wf.index("CREATE_TOMBSTONE") > wf.index("FINALIZE_REQUEST")) \
            or not any("VERIFIED_ABSENT" in gd for gd in (tt or {}).get("transition_guards", [])):
        e("OC-34", "deletion COMPLETE requires verified absence of every required action before finalization")
    if not {"PARTIALLY_FAILED", "FAILED"} <= set(dl.get("partial_failure_states", [])) \
            or dl.get("request_states") != vv("deletion_request_state") or dl.get("action_states") != vv("deletion_action_state") \
            or "RESIDUAL_FOUND" not in dl.get("action_states", []):
        e("OC-35", "PARTIALLY_FAILED/FAILED and action-level residual/failure states must stay explicit")
    if dl.get("ecs_failure_hidden_by_ops_deletion") is not False or dl.get("ops_failure_hidden_by_ecs_deletion") is not False \
            or dl.get("distributed_transaction") is not False or dl.get("retry") != "GOVERNED_IDEMPOTENT":
        e("OC-36", "neither store's failure may be hidden by the other's success; retry is governed and idempotent")
    rs = c.get("restore", {}) or {}
    if rs.get("anti_resurrection_required") is not True or rs.get("check_before_promotion") is not True \
            or not str(rs.get("governed_deleted_content", "")).startswith("REMAIN_DELETED") \
            or rs.get("missing_deletion_record") != "PROMOTION_BLOCKED" or rs.get("backup_media_physical_purge_claimed") is not False:
        e("OC-37", "restore must reconcile governed deletions before promotion (fail closed) without claiming backup purge")

    # ---------------- replay / report / re-analysis
    rp, rpt = c.get("replay", {}) or {}, c.get("report", {}) or {}
    forbidden = set(rp.get("forbidden", []))
    if rpt.get("missing_source") != "REPORT_REGENERATION_UNAVAILABLE" or "REPORT_REGENERATION_UNAVAILABLE" not in errors \
            or rpt.get("hidden_retained_copy") is not False or rpt.get("reconstruct_from_latest") is not False:
        e("OC-38", "report regeneration must be unavailable after required source deletion (no hidden copy / latest)")
    if rp.get("missing_material") != "REPLAY_UNAVAILABLE" or "REPLAY_UNAVAILABLE" not in errors \
            or "APPROXIMATION_OF_DELETED_MATERIAL" not in forbidden:
        e("OC-39", "missing required replay material must make replay unavailable without approximation")
    if "AI_CALL" not in forbidden:
        e("OC-40", "historical replay must never call AI")
    if "ENRICHMENT_PROVIDER_CALL" not in forbidden:
        e("OC-41", "historical replay must never call an enrichment provider")
    if not {"LATEST_OR_CURRENT_KNOWLEDGE", "CURRENT_EVIDENCE", "NEW_EVALUATION"} <= forbidden \
            or rp.get("replaces_authoritative_result") is not False or rp.get("verification_outcomes") != vv("replay_outcome"):
        e("OC-42", "replay must not use latest/current knowledge or evidence and is verification only")
    rms = pz.get("replay_material_set", [])
    if rp.get("material_ids") != [r.get("id") for r in rms] or rp.get("material_ids") != [f"RM-{i:02d}" for i in range(1, 15)] \
            or rp.get("material_kinds_added") or rp.get("enrichment_required_for_detection_result_replay") is not False \
            or any(loc.startswith("external_enrichment_result.") and not loc.endswith("consumed_in_governed_artifact")
                   for r in rms for loc in r.get("locations", [])):
        e("OC-43", "replay must stay bound to RM-01..RM-14 without making enrichment DetectionResult replay material")
    ra = c.get("reanalysis", {}) or {}
    if ra.get("creates") != "NEW_EVALUATION" or ra.get("overwrites_history") is not False:
        e("OC-44", "re-analysis must remain a new Evaluation that never overwrites history")

    # ---------------- provider policy
    pp = c.get("provider_policy", {}) or {}
    if pp.get("immutable_after_publication") is not True or pp.get("retroactive_change") is not False \
            or pp.get("history_retained") is not True or not {"PUBLISHED", "ACTIVE", "WITHDRAWN"} <= set(pp.get("lifecycle", [])) \
            or pp.get("applies_to") != "NEW_ENRICHMENT_ONLY":
        e("OC-45", "provider policy versions must be immutable once published, history retained, never retroactive")
    ident = pp.get("identity", [])
    if ident != ["provider_policy_ref", "provider_policy_version", "provider_policy_digest"] \
            or any(i not in ec or ec[i]["nullable"] for i in ident) or pp.get("activation_by") != "EXACT_IDENTITY" \
            or pp.get("replay_authority") != "PINNED_EXACT_IDENTITY":
        e("OC-46", "every enrichment must pin the exact provider-policy identity (ref + version + digest)")
    if pp.get("latest_by_name_authority") is not False or g(ic, "policy_authority", "unpinned_latest_in_replay") is not False:
        e("OC-47", "no latest-by-name provider policy authority may be used")
    if pp.get("authority") != "GOVERNED_OPERATOR_CONFIGURATION" or not POLICY_EXCLUDED <= set(pp.get("may_not_change", [])) \
            or pp.get("public_api") is not False or pp.get("secrets") != "SEC_REFERENCES_ONLY" \
            or not str(pp.get("storage", "")).startswith("NOT FIXED"):
        e("OC-48", "provider policy authority must exclude user/analyst/AI/provider/adapter, with no public API or storage vendor")

    # ---------------- API activation
    aa = c.get("api_activation", {}) or {}
    op = ops.get("listEvaluationEnrichments", {})
    oop = oas_ops.get("listEvaluationEnrichments")
    if "availability" in op or (oop and "x-trustlens-availability" in oop[2]) or aa.get("availability_after") != "ACTIVE_CONTRACT" \
            or g(ic, "api_surface", "availability") != "ACTIVE_CONTRACT":
        e("OC-49", "listEvaluationEnrichments activation must be consistent (no FUTURE guard in catalog/OpenAPI; ACTIVE_CONTRACT recorded)")
    if op.get("method") != aa.get("method") or op.get("path") != aa.get("path") or aa.get("method") != "GET" \
            or aa.get("path") != "/api/v1/evaluations/{evaluation_id}/enrichments" or op.get("roles") != ["ANALYST"] \
            or op.get("resource_authorization") != "CASE_ACCESS" or op.get("success_status") != 200 \
            or g(op, "list", "pagination") != "CURSOR" or op.get("response_schema") != aa.get("response_schema") \
            or not oop or oop[0] != "get" or oop[1] != aa.get("path"):
        e("OC-50", "listEvaluationEnrichments method/path/operationId/roles/authorization/status/pagination must be unchanged")
    view_fields = {f.get("name") for f in g(api, "schemas", "EnrichmentView", "fields", default=[]) or []}
    oview = set(g(oas, "components", "schemas", "EnrichmentView", "properties", default={}) or {})
    lfields = {f.get("name") for f in g(api, "schemas", "EnrichmentListResponse", "fields", default=[]) or []}
    if view_fields != ENRICHMENT_VIEW_FIELDS or oview != ENRICHMENT_VIEW_FIELDS or lfields != {"items", "page"} \
            or any(FORBIDDEN_RESPONSE.search(f) for f in view_fields | oview) or aa.get("clean_presentation") != "PROVIDER_ASSERTION":
        e("OC-51", "enrichment response must stay advisory metadata (exact EnrichmentView fields, no raw/locator/credential/target)")
    n_api, n_oas = len(ops), len(oas_ops)
    if n_api != n_oas or set(ops) != set(oas_ops) or aa.get("operation_count_before") != aa.get("operation_count_after") \
            or n_api != aa.get("operation_count_after") or aa.get("new_endpoints") or aa.get("api_base") != "/api/v1" \
            or any(p.startswith("/api/v2") for p in oas.get("paths", {})) or api.get("base_path") != "/api/v1":
        e("OC-52", f"API/OpenAPI parity must stay exact with an unchanged operation count (catalog {n_api}, OpenAPI {n_oas})")

    # ---------------- runtime parameters
    params = c.get("runtime_parameters", []) or []
    ids = [p.get("id") for p in params]
    if not params or not REQ_PARAMS <= set(ids) or len(ids) != len(set(ids)):
        e("OC-53", f"runtime parameter registry incomplete: missing {sorted(REQ_PARAMS - set(ids))}")
    rule = c.get("runtime_parameters_rule", {}) or {}
    if rule.get("missing_security_or_correctness_parameter") != "STARTUP_FAILS_CLOSED" \
            or rule.get("missing_profile_parameter") != "IMPLEMENTATION_PROFILE_INCOMPLETE_NOT_A_SECURITY_GATE" or any(
            rule.get(k) is not False for k in ("infinite_permitted", "unbounded_permitted", "library_default_permitted",
                                               "security_control_disabled_permitted")):
        e("OC-54", "a missing required parameter must fail closed (never infinite/unbounded/library default/disabled)")
    for p in params:
        want = "REQUIRED_BEFORE_DEPLOYMENT_SECURITY_OR_CORRECTNESS" if p.get("safety_relevant") \
            else "CONFIGURATION_REQUIRED_FOR_IMPLEMENTATION_PROFILE"
        if p.get("bound") != "FINITE" or p.get("deployment_requirement") != want or not p.get("owner"):
            e("OC-54", f"parameter {p.get('id')} must be FINITE with an owner and deployment requirement {want}")
        lf = p.get("linked_contract_field")
        if lf:
            node = ic
            for part in lf.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            v = node.get("value") if isinstance(node, dict) else node
            if v != NYS:
                e("OC-54", f"parameter {p.get('id')}: linked INT-001 field {lf} must resolve to NOT YET SPECIFIED")

    def numeric(node, path):
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)) and not any(tuple(path[:len(px)]) == px for px in NUMERIC_EXEMPT_PREFIXES):
            e("OC-55", f"numeric value {node!r} at {'/'.join(map(str, path))} (no fabricated policy value)")
        if isinstance(node, dict) and "value" in node and node["value"] != NYS:
            e("OC-55", f"{'/'.join(map(str, path + ('value',)))} must be NOT YET SPECIFIED, got {node['value']!r}")
    walk(c, numeric)

    # ---------------- carryovers / freeze
    def tenant(node, path):
        if isinstance(node, dict):
            for k in node:
                if TENANT.search(str(k)):
                    e("OC-56", f"tenant key {k!r} at {'/'.join(map(str, path)) or '<root>'}")
        elif isinstance(node, str) and TENANT.search(node):
            e("OC-56", f"tenant reference at {'/'.join(map(str, path))}")
    walk(c, tenant)
    for n in ("api_idempotency_record", "governed_removal_tombstone", "external_enrichment_result"):
        for cn in cols.get(n, {}):
            if "tenant" in cn.lower():
                e("OC-56", f"{n}.{cn}: tenant column")
    if g(c, "tenancy", "tenant_fields_permitted") is not False or g(c, "tenancy", "tenant_specific_provider_routing") is not False \
            or g(c, "tenancy", "status") != "UNCONFIRMED / PROVISIONAL":
        e("OC-56", "no tenant fields or routing while ASM-002 is UNCONFIRMED / PROVISIONAL")
    for code, item in (("OC-57", "G-09"), ("OC-58", "OI-05")):
        if g(c, "open_items", item) != "OPEN" or not re.search(item + r"[^\n]{0,40}OPEN", ctx["ops_text"]) \
                or not re.search(item + r"[^\n]{0,40}OPEN", ctx["gate_text"]):
            e(code, f"{item} must remain OPEN (contract, OPS-001, GATE-024)")
    rd = next((p for p in params if p.get("id") == "RETENTION_DURATIONS"), {})
    if rd.get("value") != NYS or rd.get("applies_when") != "GOVERNED_AUTOMATIC_EXPIRY_ENABLED" or rd.get("open_item") != "OI-05":
        e("OC-58", "retention durations stay NOT YET SPECIFIED and apply only when OI-05 enables governed automatic expiry")
    if ctx["engine_version"] != "1.0.0" or g(c, "decision_semantics", "engine_version") != "1.0.0":
        e("OC-59", f"ENGINE_VERSION must remain 1.0.0 (engine {ctx['engine_version']!r})")
    impl = c.get("implementation", {}) or {}
    if any(v is not False for v in impl.values()) or not impl or RUNTIME_DEPS.search(ctx["requirements"]) \
            or ctx["migration_paths"]:
        e("OC-60", f"no runtime implementation may be introduced (deps/migrations: {ctx['migration_paths']})")
    revs = {r.get("id"): r for r in pz.get("additive_revisions", []) or []}
    ar_ = c.get("additive_revision", {}) or {}
    rv = revs.get(ar_.get("id"))
    if not rv or rv.get("contract_version") != pz.get("contract_version") or pz.get("contract_version") != ar_.get("persistence_contract_version") \
            or ar_.get("earlier_gates_cover_delta") is not False or ar_.get("redesigns_accepted_semantics") is not False \
            or "P6-WP6 ADDITIVE REVISION" not in ctx["wp2_text"]:
        e("OC-61", "the P6-WP6 additive persistence revision must be recorded (contract version, DATA-001-WP2 section, GATE-024 scope)")
    label = aa.get("delta_label")
    if label != "P6-WP6 ADDITIVE ACTIVATION" or label not in ctx["api_text"] or label not in ctx["oas_text"] \
            or label not in str(op.get("notes", "")):
        e("OC-62", "API-001, OAS-001 and the catalog must mark the P6-WP6 ADDITIVE ACTIVATION delta")
    es = oas.get("x-trustlens-etag-strategy", {}) or {}
    if es.get("decision") != "B_SERVER_REVISION_REQUIRED" or "P6-WP6" not in str(es.get("implementation_dependency", "")) \
            or "monotonic revision" not in str(es.get("rule", "")):
        e("OC-63", "OpenAPI ETag decision must be unchanged and its persistence dependency marked satisfied by P6-WP6")
    aw_ = c.get("async_work", {}) or {}
    cp = pz.get("completion_protocol", {}) or {}
    if aw_.get("terminal_effects") != "IDEMPOTENT_AND_FENCED" or aw_.get("new_generic_worker_table") is not False \
            or "execution_fence_token" not in json.dumps(cp) or any("worker" in n for n in tables):
        e("OC-64", "async work must stay idempotent and fenced, with evaluation fencing unchanged and no generic worker table")
    ds = c.get("decision_semantics", {}) or {}
    new_cols = [cn for n in ("api_idempotency_record", "governed_removal_tombstone", "external_enrichment_result")
                for cn in cols.get(n, {})]
    if ds.get("new_decision_fields") or ds.get("provider_verdict_as_trustlens_verdict") is not False \
            or ds.get("phase3_changed") is not False or ds.get("phase4_changed") is not False \
            or any(DRIFT.search(x) for x in new_cols):
        e("OC-65", "no decision-semantic drift (score/probability/priority/verdict) may be introduced")

    # ---------------- OC-67 logical-object mapping (P6-WP6 MEDIUM-1 correction)
    d1 = ctx["data001_text"]
    matrix = d1[d1.find("## 6. Matrix A"):d1.find("## 7.", d1.find("## 6. Matrix A"))] if "## 6. Matrix A" in d1 else ""
    declared_objects = set(re.findall(r"^\| \d+ \| `([A-Za-z]+)` \|", matrix, re.M))
    cov = pz.get("logical_object_coverage", {}) or {}
    for tn, obj in ((idem.get("persistence_table"), idem.get("logical_object")),
                    (dl.get("tombstone_table"), dl.get("tombstone_logical_object"))):
        want = {"api_idempotency_record": "ApiIdempotencyRecord", "governed_removal_tombstone": "GovernedRemovalTombstone"}.get(tn)
        if obj != want or tables.get(tn, {}).get("logical_object") != want:
            e("OC-67", f"{tn} must map to the DATA-001 object {want} (contract {obj!r}, persistence "
                       f"{tables.get(tn, {}).get('logical_object')!r})")
        if want not in declared_objects or not re.search(r"^### 5\.\d+ `" + str(want) + "`", d1, re.M):
            e("OC-67", f"DATA-001 must declare {want} in Matrix A and in its own object section")
        if cov.get(want) != [tn] or any(tn in (v or []) for k, v in cov.items() if k != want and isinstance(v, list)):
            e("OC-67", f"logical_object_coverage must list {tn} only under {want}")
    if "P6-WP6 ADDITIVE REVISION" not in d1:
        e("OC-67", "DATA-001 must mark the P6-WP6 ADDITIVE REVISION")

    # ---------------- OC-66 scenarios
    try:
        sc = c.get("scenarios", {}) or {}
        allids = {s.get("id") for v in sc.values() for s in v}
        if not REQ_SCENARIOS <= allids:
            e("OC-66", f"required scenarios missing: {sorted(REQ_SCENARIOS - allids)}")
        for s in sc.get("idempotency", []):
            if model_idempotency(s, c) != s["expected"]:
                e("OC-66", f"{s['id']} '{s['name']}': model {model_idempotency(s, c)} != {s['expected']}")
        for s in sc.get("etag", []):
            if model_etag(s, c) != s["expected"]:
                e("OC-66", f"{s['id']} '{s['name']}': model {model_etag(s, c)} != {s['expected']}")
        for s in sc.get("deletion", []):
            st, tomb = model_deletion(s, c)
            if (st, tomb) != (s["expected_state"], s["expected_tombstone"]):
                e("OC-66", f"{s['id']} '{s['name']}': model {st}/{tomb} != {s['expected_state']}/{s['expected_tombstone']}")
        for s in sc.get("restore", []):
            if model_restore(s, c) != s["expected"]:
                e("OC-66", f"{s['id']} '{s['name']}': model {model_restore(s, c)} != {s['expected']}")
        for s in sc.get("replay", []):
            if model_replay(s, c, rms) != s["expected"]:
                e("OC-66", f"{s['id']} '{s['name']}': model {model_replay(s, c, rms)} != {s['expected']}")
        for s in sc.get("report", []):
            if model_report(s, c) != s["expected"]:
                e("OC-66", f"{s['id']} '{s['name']}': model {model_report(s, c)} != {s['expected']}")
        for s in sc.get("enrichment", []):
            if model_enrichment(s, c) != s["expected"]:
                e("OC-66", f"{s['id']} '{s['name']}': model {model_enrichment(s, c)} != {s['expected']}")
    except (KeyError, TypeError, AttributeError, ValueError) as ex:
        e("OC-66", f"scenarios cannot be evaluated: {ex!r}")
    return errs


def _select(node, seg):
    if isinstance(seg, dict):
        (k, v), = seg.items()
        for i, item in enumerate(node):
            if isinstance(item, dict) and item.get(k) == v:
                return i
        raise KeyError(f"no element with {k}={v!r}")
    return seg


def apply_mutation(docs: dict, m: dict) -> dict:
    out = dict(docs)
    tgt = m.get("target", "operations")
    doc = copy.deepcopy(docs[tgt])
    node = doc
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
    out[tgt] = doc
    return out


def context() -> dict:
    schema = load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    eng = re.search(r'ENGINE_VERSION\s*=\s*"([^"]+)"', ENGINE_PATH.read_text(encoding="utf-8"))
    return {
        "schema": schema,
        "validator": Draft202012Validator(schema),
        "ops_text": read(DOCS["ops"]), "gate_text": read(DOCS["gate"]), "wp2_text": read(DOCS["wp2"]),
        "api_text": read(DOCS["api"]), "oas_text": read(DOCS["oas"]), "data001_text": read(DOCS["data001"]),
        "requirements": read(REQUIREMENTS_PATH),
        "self_source": Path(__file__).read_text(encoding="utf-8"),
        "engine_version": eng.group(1) if eng else None,
        "migration_paths": [p for p in MIGRATION_PATHS if (ROOT / p).exists()],
    }


def main() -> int:
    quiet = "--quiet" in sys.argv
    try:
        ctx = context()
        docs = {k: load(p) for k, p in PATHS.items()}
    except (SchemaError, OSError, json.JSONDecodeError) as ex:
        print(f"  FAIL  OC-03  operational contract inputs unreadable or schema invalid: {ex!r}")
        print("OPERATIONAL CONTRACT: FAIL")
        return 1
    errs = check(docs, ctx)
    if errs:
        for code, msg in errs:
            print(f"  FAIL  {code}  {msg}")
        print(f"OPERATIONAL CONTRACT: FAIL — {len(errs)} violation(s)")
        return 1
    negatives = load(NEGATIVE_PATH)["mutations"]
    failures = []
    for m in negatives:
        try:
            mutated = apply_mutation(docs, m)
        except (KeyError, IndexError, ValueError, TypeError) as ex:
            failures.append(f"{m['id']}: mutation could not be applied ({ex})")
            continue
        found = {code for code, _ in check(mutated, ctx)}
        if m["expect"] not in found:
            failures.append(f"{m['id']}: expected {m['expect']}, got {sorted(found) or 'no violation'}")
        elif not quiet:
            print(f"  ok    {m['id']} rejected by {m['expect']}: {m['description']}")
    if failures:
        for f in failures:
            print(f"  FAIL  negative fixture {f}")
        print("OPERATIONAL CONTRACT: FAIL — a guard did not bite")
        return 1
    n_sc = sum(len(v) for v in docs["operations"]["scenarios"].values())
    print(f"OPERATIONAL CONTRACT: PASS — OPS-001 {docs['operations']['contract_version']} (idempotency, mutation revisions, "
          f"enrichment persistence, audit, deletion/tombstone, restore anti-resurrection, replay, provider policy, "
          f"enrichment activation, {len(docs['operations']['runtime_parameters'])} runtime parameters); {n_sc} offline "
          f"scenarios; {len(negatives)} negative mutations rejected (static contract validation; no runtime exists)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
