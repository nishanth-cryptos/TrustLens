"""TrustLens Phase 6 P6-WP2 — static validator for the PostgreSQL persistence contract.

Validates contracts/postgresql/schema-v1.json (the machine-readable physical contract supplementing DATA-001)
against contracts/postgresql/schema-contract.schema.json (Draft 2020-12) and then enforces the cross-reference
and authority invariants JSON Schema cannot express:

  DC-01 contract is schema-valid
  DC-02 table/column names unique; primary key is the single non-null uuid <table>_id
  DC-03 foreign keys resolve to an existing primary key or full (non-partial) unique constraint
  DC-04 ON DELETE CASCADE forbidden; SET NULL only on nullable columns
  DC-05 every DATA-001 Matrix-A canonical object is mapped (parsed from DATA-001 itself)
  DC-06 no table is knowledge authority; no rule/indicator/taxonomy definition storage
  DC-07 raw evidence bytes / full submitted content never stored in PostgreSQL
  DC-08 detection_result is immutable and carries every provenance pin
  DC-09 evaluation <-> governed_input_artifact is exactly 1:1 (P6-WP1 LOW-1)
  DC-10 no secret/key material in OPS
  DC-11 content-bearing tables resolve a retention class
  DC-12 no probability / score columns
  DC-13 controlled vocabularies resolve; promoted Phase-2/3/4 vocabularies equal their source exactly
  DC-14 tenancy: no tenant columns while ASM-002 is unconfirmed; tenancy-sensitive items stay PROVISIONAL
  DC-15 audit tables are append-only history, never deleted, with no FK into OPS
  DC-16 no evaluation provenance through a mutable "current/latest" knowledge pointer
  DC-17 retention references carry no duration / expiry interval
  DC-18 replay material set is complete and every location resolves
  DC-19 no global evidence deduplication by digest
  DC-20 no administrator case-access grant kind
  DC-21 digest columns are lowercase-hex SHA-256 text
  DC-22 cross-store states and the lost-in-memory-result path are represented
  DC-23 mutable / write-once / soft-reference / index / unique columns exist; immutable tables stay immutable
  DC-24 every FK whose parent is governedly deletable has a supporting index (deletion dependency enumeration)
  DC-25 fenced, commit-coherent completion (P6-WP2 MEDIUM-1): a DetectionResult can be inserted only under the live
        execution fence token of a RUNNING/RESULT_COMPUTED_PERSISTENCE_PENDING evaluation; every terminal non-success
        state clears the token; the binding FK makes "failed evaluation + authoritative result" structurally
        impossible; deferred commit invariants make result existence <=> COMPLETED; consumers pin only such results

It then applies every mutation in contracts/postgresql/fixtures/negative-mutations.json to a copy of the
contract and requires the named check to fail — proving each guard bites. Offline and deterministic: reads
only repository files; no network; no database.

Usage:  .venv/bin/python knowledge/validation/validate_data_contract.py [--quiet]
Exit 0 = contract valid and every negative mutation rejected by its expected check.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "postgresql" / "schema-v1.json"
SCHEMA_PATH = ROOT / "contracts" / "postgresql" / "schema-contract.schema.json"
NEGATIVE_PATH = ROOT / "contracts" / "postgresql" / "fixtures" / "negative-mutations.json"
DATA001_PATH = ROOT / "docs" / "06-contracts" / "DATA-001-data-domain-lifecycle-contract.md"
AI_INTEGRATION_PATH = ROOT / "knowledge" / "ai" / "integration.py"

HEX64 = "^[0-9a-f]{64}$"
FORBIDDEN_KNOWLEDGE_TABLES = {"rule", "rule_set", "ruleset", "indicator", "indicator_definition", "taxonomy",
                              "taxonomy_node", "scam", "negative_indicator", "action_policy", "rule_definition",
                              "knowledge_rule", "published_rule"}
FORBIDDEN_KNOWLEDGE_COLUMNS = re.compile(r"^(rule_logic|rule_definition|rule_json|rule_body|logic|require|"
                                         r"indicator_definition|taxonomy_json|action_policy_json|bundle_bytes)$")
RAW_CONTENT_COLUMNS = re.compile(r"(raw_text|raw_bytes|raw_content|content_bytes|message_body|email_body|"
                                 r"screenshot|attachment_bytes|file_bytes|raw_url|normalized_text|submitted_text|"
                                 r"evidence_bytes|blob)")
SECRET_COLUMNS = re.compile(r"(password|passwd|access_token|refresh_token|id_token|bearer|secret|private_key|"
                            r"api_key|credential|mfa_seed|signing_key$|encryption_key$|data_key$)")
SCORE_COLUMNS = re.compile(r"(probab|likelihood|percent|score)", re.I)
TENANT_COLUMNS = re.compile(r"tenant", re.I)
DURATION_COLUMNS = re.compile(r"(duration|days|months|years|ttl|interval|period|delete_after|expire|retain_until)")
RESULT_PINS = ["evaluation_id", "result_contract_version", "result_digest", "engine_version", "bundle_version",
               "bundle_content_digest", "commit_sha", "evaluation_profile_id", "extraction_confidence_gate",
               "risk_matrix_id", "confidence_policy_id", "action_policy_version", "component_versions",
               "evaluation_timestamp", "input_id", "language", "script", "input_support_status", "classification",
               "decision_severity", "matched_evidence_strength", "risk_level", "detection_confidence", "degraded",
               "storage_mode", "result_canonical_json", "ecs_locator"]
AUDIT_EVENT_REQUIRED = ["chain_id", "chain_sequence", "event_type", "occurred_at", "actor_kind", "actor_principal_id",
                        "outcome", "target_kind", "target_id", "previous_event_hash", "event_hash", "correlation_id"]
CROSS_STORE_REQUIRED = {"RECEIVED", "CONTENT_PENDING", "CONTENT_STORED", "INTEGRITY_VERIFIED", "FINALIZED",
                        "FAILED_RETRYABLE", "FAILED_TERMINAL", "ORPHAN_DETECTED", "INTEGRITY_FAILED"}
CONTENT_TABLES = ("evidence_item", "evidence_derivative", "input_envelope_record")
REPLAY_REQUIRED_IDS = [f"RM-{i:02d}" for i in range(1, 15)]
IMM_ALLOWED_MUTABLE = {"content_state", "state_changed_at"}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def data001_objects() -> list[str]:
    """Canonical object names from DATA-001 §6 Matrix A (authoritative list, parsed, not duplicated)."""
    text = DATA001_PATH.read_text(encoding="utf-8")
    start = text.index("## 6. Matrix A")
    end = text.index("## 7.", start)
    return re.findall(r"^\| \d+ \| `([A-Za-z]+)` \|", text[start:end], re.MULTILINE)


def phase4_fallback_reasons() -> list[str]:
    src = AI_INTEGRATION_PATH.read_text(encoding="utf-8")
    block = src[src.index("class AIFallbackReason"):]
    block = block[:block.index("\n\n")]
    return re.findall(r'=\s*"([A-Z_]+)"', block)


def resolve_promoted(source: str) -> list[str]:
    path, pointer = source.split("#", 1)
    node = load(ROOT / path)
    for part in [p for p in pointer.split("/") if p]:
        node = node[part]
    if "enum" in node:
        return list(node["enum"])
    if "const" in node:
        return [node["const"]]
    raise KeyError(f"{source}: no enum/const")


def check(contract: dict, schema_validator: Draft202012Validator) -> list[tuple[str, str]]:
    errs: list[tuple[str, str]] = []

    def e(code, msg):
        errs.append((code, msg))

    for err in sorted(schema_validator.iter_errors(contract), key=lambda x: list(x.path)):
        e("DC-01", f"schema: {err.message} at /{'/'.join(map(str, err.path))}")
    if errs:
        return errs   # structural failure: later checks would only cascade

    tables = contract["tables"]
    by_name: dict[str, dict] = {}
    for t in tables:
        if t["name"] in by_name:
            e("DC-02", f"duplicate table {t['name']}")
        by_name[t["name"]] = t
    cols = {t["name"]: {c["name"]: c for c in t["columns"]} for t in tables}
    vocab = contract["vocabularies"]

    def uniques_of(t):
        out = [tuple(t["primary_key"])]
        out += [tuple(u["columns"]) for u in t["unique"] if "where" not in u]
        return out

    for t in tables:
        n = t["name"]
        names = [c["name"] for c in t["columns"]]
        if len(names) != len(set(names)):
            e("DC-02", f"{n}: duplicate column names")
        if t["primary_key"] != [f"{n}_id"]:
            e("DC-02", f"{n}: primary key must be [{n}_id], got {t['primary_key']}")
        pkc = cols[n].get(f"{n}_id")
        if not pkc or pkc["type"] != "uuid" or pkc["nullable"]:
            e("DC-02", f"{n}: primary key column must be a non-null uuid")

        # ---- DC-03 / DC-04 foreign keys
        fk_cols = set()
        for fk in t["foreign_keys"]:
            ref = fk["references"]["table"]
            fk_cols.update(fk["columns"])
            for c in fk["columns"]:
                if c not in cols[n]:
                    e("DC-03", f"{n}: FK column {c} missing")
            if ref not in by_name:
                e("DC-03", f"{n}: FK references unknown table {ref}")
                continue
            rcols = fk["references"]["columns"]
            if tuple(rcols) not in uniques_of(by_name[ref]):
                e("DC-03", f"{n}: FK {fk['columns']} -> {ref}{rcols} is not a primary key or full unique constraint")
            if len(rcols) != len(fk["columns"]):
                e("DC-03", f"{n}: FK arity mismatch to {ref}")
            else:
                for a, b in zip(fk["columns"], rcols):
                    ca, cb = cols[n].get(a), cols[ref].get(b)
                    if ca and cb and ca["type"] != cb["type"]:
                        e("DC-03", f"{n}.{a} type {ca['type']} != {ref}.{b} type {cb['type']}")
            if fk["on_delete"] == "CASCADE":
                e("DC-04", f"{n}: ON DELETE CASCADE forbidden ({fk['columns']} -> {ref})")
            if fk["on_delete"] == "SET_NULL" and any(not cols[n][c]["nullable"] for c in fk["columns"] if c in cols[n]):
                e("DC-04", f"{n}: SET NULL on a non-nullable FK column")

        # ---- DC-06 knowledge authority
        if n in FORBIDDEN_KNOWLEDGE_TABLES:
            e("DC-06", f"{n}: table name implies database-owned knowledge (ADR-0004/0013)")
        for c in t["columns"]:
            if FORBIDDEN_KNOWLEDGE_COLUMNS.match(c["name"]):
                e("DC-06", f"{n}.{c['name']}: knowledge definition column forbidden in PostgreSQL")
        if t["authority"] == "REFERENCE_TO_KNOWLEDGE_AUTHORITY" and any(c["classification"] in ("C3", "C4") for c in t["columns"]):
            e("DC-06", f"{n}: knowledge reference table must not hold evidence content")

        for c in t["columns"]:
            cn = c["name"]
            # ---- DC-07 raw evidence
            if c.get("content_kind") == "RAW_EVIDENCE_BYTES" or RAW_CONTENT_COLUMNS.search(cn):
                e("DC-07", f"{n}.{cn}: raw evidence / full submitted content must live in EvidenceContentStore")
            if c["classification"] == "C3":
                e("DC-07", f"{n}.{cn}: C3 sensitive submitted evidence is not stored in PostgreSQL")
            if c["type"] == "bytea" and c.get("content_kind") != "CRYPTOGRAPHIC_SIGNATURE":
                e("DC-07", f"{n}.{cn}: bytea permitted only for cryptographic signatures")
            # ---- DC-10 secrets
            if c["classification"] == "C7" or c.get("content_kind") == "SECRET_OR_KEY_MATERIAL" or SECRET_COLUMNS.search(cn):
                e("DC-10", f"{n}.{cn}: secret/key material must stay behind SecretProvider/key boundaries")
            # ---- DC-12 score
            if SCORE_COLUMNS.search(cn):
                e("DC-12", f"{n}.{cn}: probability/score-like column forbidden (INV-10)")
            # ---- DC-14 tenancy
            if TENANT_COLUMNS.search(cn) and not contract["tenancy"]["tenant_columns_permitted"]:
                e("DC-14", f"{n}.{cn}: tenant column added while ASM-002 tenancy is unconfirmed")
            # ---- DC-13 vocabulary binding
            if "vocabulary" in c:
                if c["vocabulary"] not in vocab:
                    e("DC-13", f"{n}.{cn}: unknown vocabulary {c['vocabulary']}")
                if c["type"] not in ("text", "text[]"):
                    e("DC-13", f"{n}.{cn}: controlled vocabulary must be CHECK-constrained text")
            # ---- DC-21 digests
            if (cn.endswith("_sha256") or cn.endswith("_digest")) and c.get("content_kind") != "DIGEST":
                e("DC-21", f"{n}.{cn}: digest-named column must be content_kind DIGEST")
            if c.get("content_kind") == "DIGEST" and (c["type"] != "text" or c.get("pattern") != HEX64):
                e("DC-21", f"{n}.{cn}: digest must be text with lowercase-hex SHA-256 pattern")

        if n in CONTENT_TABLES:
            if "ecs_locator" not in cols[n]:
                e("DC-07", f"{n}: content bytes must be referenced via ecs_locator")
            for c in t["columns"]:
                if c.get("content_kind") in ("CANONICAL_ARTIFACT_JSON", "DERIVED_SENSITIVE_TEXT"):
                    e("DC-07", f"{n}.{c['name']}: evidence/envelope content must not be inline")

        # ---- DC-11 retention
        if any(c["classification"] == "C4" for c in t["columns"]) and t["retention"]["mode"] == "NOT_APPLICABLE":
            e("DC-11", f"{n}: content-bearing table must resolve a retention class")
        r = t["retention"]
        if r["mode"] == "INHERITED" and r["via"] not in by_name:
            e("DC-11", f"{n}: retention inherited via unknown table {r['via']}")
        if r["mode"] == "EXPLICIT":
            if r["column"] not in cols[n]:
                e("DC-11", f"{n}: retention column {r['column']} missing")
            elif not any(fk["columns"] == [r["column"]] and fk["references"]["table"] == "retention_policy_reference"
                         for fk in t["foreign_keys"]):
                e("DC-11", f"{n}: retention column must reference retention_policy_reference")

        # ---- DC-14 tenancy statuses
        if contract["tenancy"]["asm_002_status"] == "UNCONFIRMED_PROVISIONAL":
            ts = [t.get("tenancy_sensitivity", {}).get("status")] + [u.get("tenancy_status") for u in t["unique"]] \
                + [i.get("tenancy_status") for i in t["indexes"]]
            if "CONFIRMED" in ts:
                e("DC-14", f"{n}: tenancy decision marked CONFIRMED although ASM-002 is unconfirmed")

        # ---- DC-23 column references
        for group in ("mutable_columns", "write_once_columns"):
            for c in t[group]:
                if c not in cols[n]:
                    e("DC-23", f"{n}: {group} names unknown column {c}")
        for s in t["soft_references"]:
            if s["column"] not in cols[n]:
                e("DC-23", f"{n}: soft reference names unknown column {s['column']}")
            if s["column"] in fk_cols:
                e("DC-23", f"{n}.{s['column']}: soft reference must not also be a foreign key")
        for u in t["unique"] + t["indexes"]:
            for c in u["columns"]:
                if c not in cols[n]:
                    e("DC-23", f"{n}: {u['name']} names unknown column {c}")
        if t["mutability"] == "M-IMM":
            bad = set(t["mutable_columns"]) - IMM_ALLOWED_MUTABLE
            if bad:
                e("DC-23", f"{n}: immutable table declares mutable columns {sorted(bad)}")

    # ---- DC-24 FK index coverage for governedly deletable parents
    for t in tables:
        usable = [i["columns"] for i in t["indexes"] + t["unique"]
                  if "where" not in i or i["where"].strip() == f"{i['columns'][0]} IS NOT NULL"]
        usable.append(t["primary_key"])
        for fk in t["foreign_keys"]:
            ref = by_name.get(fk["references"]["table"])
            if ref and ref["delete_policy"] == "GOVERNED_DELETION_ONLY" and \
                    not any(cols and cols[0] == fk["columns"][0] for cols in usable):
                e("DC-24", f"{t['name']}: FK {fk['columns']} -> {ref['name']} has no supporting index for deletion enumeration")

    # ---- DC-05 logical coverage
    expected = data001_objects()
    if len(expected) < 20:
        e("DC-05", f"could not parse DATA-001 Matrix A (found {len(expected)} objects)")
    cov = contract["logical_object_coverage"]
    for obj in expected:
        if obj not in cov:
            e("DC-05", f"DATA-001 object {obj} is not mapped")
    for obj, m in cov.items():
        if obj not in expected:
            e("DC-05", f"coverage names {obj}, which is not a DATA-001 Matrix-A object")
        if isinstance(m, list):
            for tn in m:
                if tn not in by_name:
                    e("DC-05", f"{obj} mapped to unknown table {tn}")
    for t in tables:
        mapped = cov.get(t["logical_object"])
        if not isinstance(mapped, list) or t["name"] not in mapped:
            e("DC-05", f"{t['name']}: not listed under its logical object {t['logical_object']}")

    # ---- DC-08 DetectionResult
    dr = by_name.get("detection_result")
    if not dr:
        e("DC-08", "detection_result table missing")
    else:
        if dr["mutability"] != "M-IMM" or dr["mutable_columns"] or dr["write_once_columns"]:
            e("DC-08", "detection_result must be fully immutable (no mutable or write-once columns)")
        for p in RESULT_PINS:
            if p not in cols["detection_result"]:
                e("DC-08", f"detection_result missing required pin/projection {p}")
        ev = cols["detection_result"].get("evaluation_id")
        if not ev or ev["nullable"] or ("evaluation_id",) not in uniques_of(dr):
            e("DC-08", "detection_result.evaluation_id must be non-null and unique (one result per evaluation)")

    # ---- DC-09 1:1
    ga = by_name.get("governed_input_artifact")
    if not ga:
        e("DC-09", "governed_input_artifact table missing")
    else:
        ev = cols["governed_input_artifact"].get("evaluation_id")
        if not ev or ev["nullable"]:
            e("DC-09", "governed_input_artifact.evaluation_id must be non-null")
        if ("evaluation_id",) not in uniques_of(ga):
            e("DC-09", "governed_input_artifact.evaluation_id must be UNIQUE (evaluation <-> artifact 1:1)")
        if not any(fk["columns"] == ["evaluation_id"] and fk["references"] == {"table": "evaluation", "columns": ["evaluation_id"]}
                   for fk in ga["foreign_keys"]):
            e("DC-09", "governed_input_artifact.evaluation_id must reference evaluation")
        if ga["mutability"] != "M-IMM" or ga["mutable_columns"]:
            e("DC-09", "governed_input_artifact must be immutable")

    # ---- DC-13 promoted vocabularies
    for name, v in vocab.items():
        if v["authority"] == "PROMOTED_CONTRACT":
            try:
                src = resolve_promoted(v["source"])
            except (KeyError, FileNotFoundError, ValueError) as ex:
                e("DC-13", f"vocabulary {name}: cannot resolve source {v['source']} ({ex})")
                continue
            if sorted(src) != sorted(v["values"]):
                e("DC-13", f"vocabulary {name} drifts from {v['source']}: {sorted(v['values'])} != {sorted(src)}")
        elif v["authority"] == "PHASE4_RUNTIME":
            if sorted(phase4_fallback_reasons()) != sorted(v["values"]):
                e("DC-13", f"vocabulary {name} drifts from AIFallbackReason")

    # ---- DC-14 tenancy contract
    if contract["tenancy"]["asm_002_status"] == "UNCONFIRMED_PROVISIONAL" and contract["tenancy"]["tenant_columns_permitted"]:
        e("DC-14", "tenant columns may not be permitted while ASM-002 is unconfirmed")

    # ---- DC-15 audit
    for t in tables:
        if t["store_class"] != "AUD":
            continue
        if t["delete_policy"] != "NEVER":
            e("DC-15", f"{t['name']}: audit history is never deleted by ordinary workflows")
        for fk in t["foreign_keys"]:
            ref = by_name.get(fk["references"]["table"])
            if ref and ref["store_class"] != "AUD":
                e("DC-15", f"{t['name']}: audit must not FK into OPS ({fk['references']['table']}); use soft references")
    ae = by_name.get("audit_event")
    if not ae:
        e("DC-15", "audit_event table missing")
    else:
        if ae["mutability"] != "M-APP" or ae["mutable_columns"] or ae["write_once_columns"]:
            e("DC-15", "audit_event must be append-only with no updatable columns")
        for c in AUDIT_EVENT_REQUIRED:
            if c not in cols["audit_event"]:
                e("DC-15", f"audit_event missing {c}")

    # ---- DC-16 no latest pointer provenance
    for t in tables:
        for fk in t["foreign_keys"]:
            if fk["references"]["table"] == "knowledge_deployment_state":
                e("DC-16", f"{t['name']}: nothing may reference the mutable current-bundle pointer")
            if t["name"] in ("evaluation", "detection_result", "report_evaluation_pin") and \
                    fk["references"]["table"] == "knowledge_activation_record":
                e("DC-16", f"{t['name']}: provenance must pin the exact content_digest, not an activation record")
    evt = by_name.get("evaluation")
    if not evt or not any(fk["columns"] == ["bundle_content_digest"] and fk["references"] == {"table": "knowledge_bundle_reference", "columns": ["content_digest"]}
                          for fk in evt["foreign_keys"]):
        e("DC-16", "evaluation must pin bundle_content_digest -> knowledge_bundle_reference.content_digest")

    # ---- DC-17 retention durations
    rp = by_name.get("retention_policy_reference")
    if not rp:
        e("DC-17", "retention_policy_reference table missing")
    else:
        for c in rp["columns"]:
            if DURATION_COLUMNS.search(c["name"]):
                e("DC-17", f"retention_policy_reference.{c['name']}: retention duration/expiry invented (OI-05 OPEN)")

    # ---- DC-18 replay material
    rms = {r["id"]: r for r in contract["replay_material_set"]}
    for rid in REPLAY_REQUIRED_IDS:
        if rid not in rms:
            e("DC-18", f"replay material {rid} missing")
    kinds = set(vocab.get("replay_material_kind", {}).get("values", []))
    for r in contract["replay_material_set"]:
        if r["kind"] not in kinds:
            e("DC-18", f"{r['id']}: unknown material kind {r['kind']}")
        for loc in r["locations"]:
            if loc.startswith(("KNOW:", "ECS:")):
                continue
            tn, _, cn = loc.partition(".")
            if tn not in cols or cn not in cols[tn]:
                e("DC-18", f"{r['id']}: location {loc} does not resolve")

    # ---- DC-19 no dedup
    for tn, dc in (("evidence_item", "content_sha256"), ("evidence_derivative", "derivative_sha256")):
        t = by_name.get(tn)
        if t and any(dc in u["columns"] for u in t["unique"]):
            e("DC-19", f"{tn}: unique constraint over {dc} would deduplicate user evidence by digest")

    # ---- DC-20 admin
    if any("ADMIN" in v for v in vocab.get("case_grant_kind", {}).get("values", [])):
        e("DC-20", "case_grant_kind must not contain an administrator grant (NFR-14)")

    # ---- DC-22 cross-store + lost result
    if not CROSS_STORE_REQUIRED <= set(vocab.get("cross_store_state", {}).get("values", [])):
        e("DC-22", "cross_store_state vocabulary is missing required states")
    for tn in CONTENT_TABLES:
        t = by_name.get(tn)
        if not t:
            e("DC-22", f"{tn} missing")
            continue
        cs = cols[tn].get("content_state")
        if not cs or cs.get("vocabulary") != "cross_store_state":
            e("DC-22", f"{tn}.content_state must use cross_store_state")
        if not any(c["name"] == f"ck_{tn}_finalized_requires_verified" for c in t["checks"]):
            e("DC-22", f"{tn}: finalized-requires-verified check missing")
    es = set(vocab.get("evaluation_status", {}).get("values", []))
    if not {"RESULT_COMPUTED_PERSISTENCE_PENDING", "FAILED_INFRASTRUCTURE", "COMPLETED"} <= es:
        e("DC-22", "evaluation_status must represent pending persistence and infrastructure failure")
    if "RETRY_AFTER_FAILURE" not in vocab.get("evaluation_origin", {}).get("values", []):
        e("DC-22", "evaluation_origin must represent retry-as-new-evaluation")
    if "RESULT_DURABILITY_UNCONFIRMED" not in vocab.get("evaluation_failure_category", {}).get("values", []):
        e("DC-22", "evaluation_failure_category must represent unconfirmed result durability")

    check_completion_protocol(contract, by_name, cols, vocab, e)
    return errs


def _quoted(states):
    return ",".join(f"'{x}'" for x in states)


def check_completion_protocol(contract, by_name, cols, vocab, e) -> None:
    """DC-25 — structural proof chain that a FAILED evaluation can never own an authoritative DetectionResult:
    (1) the result row carries a NOT NULL fence token bound by FK to the evaluation's (id, live token) pair, and the
        FK cannot cascade/null the token; (2) every terminal non-success state is CHECK-constrained to a NULL token,
        so a fenced evaluation has nothing a result could reference, and an existing result blocks clearing the token;
    (3) an executing evaluation always holds a token; (4) a BEFORE INSERT guard admits only pre-completion states;
    (5) deferred commit invariants tie result existence to COMPLETED; (6) every result consumer reaches results only
        through the result FK or a COMPLETED-only guard."""
    cp = contract.get("completion_protocol")
    if not cp:
        e("DC-25", "completion_protocol missing")
        return
    owner, result = by_name.get(cp["owner_table"]), by_name.get(cp["result_table"])
    if not owner or not result:
        e("DC-25", "completion_protocol owner/result table missing")
        return
    on, rn = owner["name"], result["name"]
    status = cols[on].get(cp["status_column"])
    if not status or status.get("vocabulary") not in vocab:
        e("DC-25", f"{on}.{cp['status_column']} must be a controlled-vocabulary status")
        return
    states = vocab[status["vocabulary"]]["values"]
    allowed = cp["result_insert_allowed_states"]
    success, initial = cp["success_state"], cp["initial_state"]
    for st in allowed + [success, initial] + cp["fence"]["cleared_states"]:
        if st not in states:
            e("DC-25", f"completion_protocol state {st} not in {status['vocabulary']}")
    if not allowed:
        e("DC-25", "result_insert_allowed_states must not be empty")
    forbidden_allowed = set(allowed) & ({success, initial} | set(cp["fence"]["cleared_states"]))
    if forbidden_allowed:
        e("DC-25", f"result insert allowed in terminal/initial states {sorted(forbidden_allowed)}")
    expected_cleared = [x for x in states if x not in set(allowed) | {success, initial}]
    if sorted(cp["fence"]["cleared_states"]) != sorted(expected_cleared):
        e("DC-25", f"every terminal non-success state must clear the fence: expected {expected_cleared}, "
                   f"got {cp['fence']['cleared_states']}")

    f = cp["fence"]
    oc, rc = cols[on].get(f["owner_column"]), cols[rn].get(f["result_column"])
    if not oc or oc["type"] != "uuid" or not oc["nullable"] or f["owner_column"] not in owner["mutable_columns"]:
        e("DC-25", f"{on}.{f['owner_column']} must be a nullable, mutable uuid fence token")
    if not rc or rc["type"] != "uuid" or rc["nullable"] or f["result_column"] in result["mutable_columns"] + result["write_once_columns"]:
        e("DC-25", f"{rn}.{f['result_column']} must be an immutable NOT NULL uuid fence token")
    bfk = f["binding_foreign_key"]
    match = [fk for fk in result["foreign_keys"]
             if fk["columns"] == bfk["columns"] and fk["references"] == bfk["references"]]
    if not match:
        e("DC-25", f"{rn}: binding fence FK {bfk['columns']} -> {bfk['references']} missing")
    else:
        if bfk["references"]["table"] != on or f["owner_column"] not in bfk["references"]["columns"]                 or f["result_column"] not in bfk["columns"]:
            e("DC-25", "binding fence FK must bind the result fence column to the owner fence column")
        if match[0].get("on_update", "NO_ACTION") not in ("NO_ACTION", "RESTRICT") or match[0]["on_delete"] not in ("NO_ACTION", "RESTRICT"):
            e("DC-25", "binding fence FK must not cascade or null the fence token")
        if tuple(bfk["references"]["columns"]) not in [tuple(u["columns"]) for u in owner["unique"] if "where" not in u]:
            e("DC-25", "binding fence FK target must be a full unique constraint on the owner")

    checks = {c["name"]: c["rule"] for c in owner["checks"]}
    sc, fc = cp["status_column"], f["owner_column"]
    want_cleared = f"{sc} NOT IN ({_quoted(f['cleared_states'])}) OR {fc} IS NULL"
    want_held = f"{sc} NOT IN ({_quoted(allowed)}) OR {fc} IS NOT NULL"
    if checks.get(f["cleared_check"]) != want_cleared:
        e("DC-25", f"{on}.{f['cleared_check']} must be exactly: {want_cleared}")
    if checks.get(f["held_check"]) != want_held:
        e("DC-25", f"{on}.{f['held_check']} must be exactly: {want_held}")

    def trig(table, name):
        return {t["name"]: t for t in table.get("constraint_triggers", [])}.get(name)

    g = trig(result, cp["result_insert_guard"])
    if not g or g["timing"] != "BEFORE_INSERT":
        e("DC-25", f"{rn}: BEFORE_INSERT result guard {cp['result_insert_guard']} missing")
    elif not all(f"'{st}'" in g["rule"] for st in allowed) or f["owner_column"] not in g["rule"]             or any(f"'{st}'" in g["rule"] for st in f["cleared_states"]):
        e("DC-25", f"{rn}: result guard must admit exactly the allowed states and check the fence token")
    inv_tables = set()
    for inv in cp["commit_invariants"]:
        t = by_name.get(inv["table"])
        tr = trig(t, inv["trigger"]) if t else None
        if not tr or tr["timing"] != "DEFERRED_AT_COMMIT":
            e("DC-25", f"deferred commit invariant {inv['trigger']} missing on {inv['table']}")
        else:
            inv_tables.add(inv["table"])
    if inv_tables != {on, rn}:
        e("DC-25", "commit invariants must cover both directions (result => COMPLETED and COMPLETED => result)")

    consumers = {c["table"]: c for c in cp["result_consumers"]}
    for tn in ("analyst_adjudication", "report_evaluation_pin", "replay_execution"):
        if tn not in consumers:
            e("DC-25", f"result consumer {tn} not covered by the completion protocol")
    for tn, c in consumers.items():
        t = by_name.get(tn)
        if not t:
            e("DC-25", f"result consumer {tn} missing")
        elif c["via"] == "FOREIGN_KEY":
            if not any(fk["references"]["table"] == rn for fk in t["foreign_keys"]):
                e("DC-25", f"{tn} must pin results through a FK to {rn}")
        else:
            tr = trig(t, c.get("trigger", ""))
            if not tr or tr["timing"] != "BEFORE_INSERT" or f"'{success}'" not in tr["rule"]:
                e("DC-25", f"{tn} must guard insertion on the evaluation being {success}")


# ================================================================ negative mutations


def _select(node, seg):
    if isinstance(seg, dict):
        (k, v), = seg.items()
        for i, item in enumerate(node):
            if isinstance(item, dict) and item.get(k) == v:
                return i
        raise KeyError(f"no element with {k}={v!r}")
    return seg


def apply_mutation(contract: dict, m: dict) -> dict:
    c = copy.deepcopy(contract)
    node = c
    path = m["path"]
    for seg in path[:-1]:
        node = node[_select(node, seg)]
    last = _select(node, path[-1])
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
    contract = load(CONTRACT_PATH)
    schema = load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    errs = check(contract, validator)
    if errs:
        for code, msg in errs:
            print(f"  FAIL  {code}  {msg}")
        print(f"DATA CONTRACT: FAIL — {len(errs)} violation(s) in {CONTRACT_PATH.relative_to(ROOT)}")
        return 1

    negatives = load(NEGATIVE_PATH)["mutations"]
    bite_failures = []
    for m in negatives:
        try:
            mutated = apply_mutation(contract, m)
        except (KeyError, IndexError, ValueError) as ex:
            bite_failures.append(f"{m['id']}: mutation could not be applied ({ex})")
            continue
        codes = {code for code, _ in check(mutated, validator)}
        if m["expect"] not in codes:
            bite_failures.append(f"{m['id']}: expected {m['expect']}, got {sorted(codes) or 'no violation'}")
        elif not quiet:
            print(f"  ok    {m['id']} rejected by {m['expect']}: {m['description']}")
    if bite_failures:
        for f in bite_failures:
            print(f"  FAIL  negative fixture {f}")
        print("DATA CONTRACT: FAIL — a guard did not bite")
        return 1

    n_tables = len(contract["tables"])
    print(f"DATA CONTRACT: PASS — {n_tables} tables, {len(contract['vocabularies'])} vocabularies, "
          f"{len(contract['replay_material_set'])} replay-material items; {len(negatives)} negative mutations rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
