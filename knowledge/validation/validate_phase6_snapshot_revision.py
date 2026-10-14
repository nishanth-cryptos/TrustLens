"""TrustLens forward Phase-6 snapshot revision P6-SNAPSHOT-REV-001 (CANDIDATE) for persistence addendum P9-S2-ADD-001.

Validates contracts/phase6/phase6-snapshot-revision-p9-s2-add-001.json against its closed schema, composes the effective
persistence contract 0.3.0 from the frozen base 0.2.0 and the machine addendum, and checks:

  PSR-01 revision manifest is schema-valid (closed)
  PSR-02 lifecycle, fail closed: either CANDIDATE (not approved, not activated, review PENDING, not submitted) or
         ACCEPTED (independent review APPROVED and recorded in its gate record, approved, activated) with an integration
         state that never claims a merge without a PR number and merge commit; earlier REQUEST_CHANGES rounds stay recorded
  PSR-03 predecessor closure manifests (Phase-6, Phase-7) pinned and byte-for-byte unchanged
  PSR-04 all 19 historical Phase-6 pins carried exactly (same id, path, digest as the closure snapshot and the bytes)
  PSR-05 the four structural-schema pins carried from P6-WP7-LOW-1 are present and match their bytes
  PSR-06 every added artifact (machine addendum, its schema, human contract, migration 0004, revision schema, fixtures,
         this validator) is pinned and matches its bytes
  PSR-07 the machine addendum is valid against its closed schema, which references the ACTUAL structural definitions
  PSR-08 the addendum lifecycle matches the revision (CANDIDATE / ACTIVATED) and extends the exact pinned base
  PSR-09 deterministic composition succeeds: every amendment names the exact base text it replaces
  PSR-10 the effective contract 0.3.0 passes the full data-contract validation DC-01..DC-25 against the structural schema
  PSR-11 every historical data-contract negative mutation still bites on the effective contract
  PSR-12 the uq_api_idempotency_scope change is recorded as a GOVERNED CONSTRAINT RELAXATION (not additive) with
         preserved invariants and migration compatibility, in the machine addendum, this manifest and the human contract
  PSR-13 migration catalog: 0004 follows 0003 and creates exactly the declared tables with the effective columns, types,
         nullability, keys, unique/index names and partial predicates, plus the declared amendment DDL; the CHECK set of
         each table equals the governed set exactly (explicit rules, column patterns, vocabularies), predicate by
         predicate, so CHECK (true) or any weakened predicate fails even when the migration pin is updated to match
  PSR-14 transition guards: evidence_item transitions equal the DATA-001-WP2 §11 diagram; intent, fencing,
         supersession, write-once and governed-deletion guards present
  PSR-15 privileges: grants equal the addendum; UPDATE only on declared mutable/write-once columns; no DELETE/TRUNCATE/ALL,
         no DROP TABLE, no change to undeclared tables
  PSR-16 API/OpenAPI contracts unchanged (Phase-6 pinned bytes and versions); API impact NONE
  PSR-17 claim boundary for the lifecycle (no approval/activation claim while CANDIDATE; no merge, remote-CI, production,
         sponsor-migration or completeness claim); open items and post-decision steps carried

It then applies contracts/phase6/fixtures/snapshot-revision-negative-mutations.json and requires each named check to fail.
Offline and deterministic: reads repository files only; no network, no database, no execution of the migration.

Usage:  .venv/bin/python knowledge/validation/validate_phase6_snapshot_revision.py [--quiet]
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = "contracts/phase6/phase6-snapshot-revision-p9-s2-add-001.json"
MANIFEST_SCHEMA_PATH = "contracts/phase6/phase6-snapshot-revision-contract.schema.json"
NEGATIVE_PATH = "contracts/phase6/fixtures/snapshot-revision-negative-mutations.json"
PHASE6_PATH = "contracts/phase6/phase6-closure-v1.json"
PHASE7_PATH = "contracts/phase7/phase7-closure-v1.json"
BASE_PATH = "contracts/postgresql/schema-v1.json"
STRUCTURAL_PATH = "contracts/postgresql/schema-contract.schema.json"
ADDENDUM_PATH = "contracts/postgresql/schema-v1-addendum-p9-s2-add-001.json"
ADDENDUM_SCHEMA_PATH = "contracts/postgresql/schema-addendum.schema.json"
DATA_NEGATIVE_PATH = "contracts/postgresql/fixtures/negative-mutations.json"
WP2_DOC_PATH = "docs/06-contracts/DATA-001-WP2-postgresql-persistence-contract.md"
API_PATH = "contracts/api/api-v1.json"
OPENAPI_PATH = "contracts/api/openapi-v1.json"
MIGRATION_PATH = "apps/backend/migrations/versions/0004_evidence_intake.py"
SELF_PATH = "knowledge/validation/validate_phase6_snapshot_revision.py"
STRUCTURAL_SCHEMAS = {"contracts/postgresql/schema-contract.schema.json", "contracts/api/api-contract.schema.json",
                      "contracts/integrations/integration-contract.schema.json",
                      "contracts/operations/operational-contract.schema.json"}
GATE_PATH = "docs/00-program/GATE-033-p9-s2-add-001-persistence-revision.md"
REQUIRED_ADDED = {ADDENDUM_PATH, ADDENDUM_SCHEMA_PATH, "docs/06-contracts/DATA-001-WP2-ADD-P9-S2-001-evidence-upload-intent.md",
                  MIGRATION_PATH, MANIFEST_SCHEMA_PATH, NEGATIVE_PATH, SELF_PATH}
REQUIRED_ADDED_ACCEPTED = REQUIRED_ADDED | {GATE_PATH}          # an accepted revision also pins its gate record
EFFECTIVE_VERSION = "0.3.0"
HISTORICAL_PIN_COUNT = 19
MUST_NOT_SUPPORT = {"PRODUCTION_READY", "SPONSOR_DATABASE_MIGRATED", "COMPLETE_T09", "PRODUCTION_KMS", "FULL_S2_COMPLETE",
                    "ACCESSIBILITY_CONFORMANCE"}
MUST_NOT_SUPPORT_BY_LIFECYCLE = {"CANDIDATE": {"APPROVED", "ACTIVATED"}, "ACCEPTED": {"MERGED", "REMOTE_CI_PASSED"}}
LOW1_STATE = {"CANDIDATE": "CARRIED_PENDING_ACTIVATION", "ACCEPTED": "RESOLVED_BY_ACCEPTED_REVISION"}
STEPS_BY_LIFECYCLE = {"CANDIDATE": ("independent review", "gate record", "make migration-sql", "make migrate", "evidence key"),
                      "ACCEPTED": ("pull request", "merge", "make migration-sql", "make migrate", "evidence key")}
ADDENDUM_STATUS = {"CANDIDATE": "CANDIDATE", "ACCEPTED": "ACTIVATED"}
FORBIDDEN_PRIVILEGES = {"DELETE", "TRUNCATE", "ALL", "REFERENCES", "TRIGGER"}
FORBIDDEN_SQL = re.compile(r"\b(DROP\s+TABLE|DELETE\s+FROM|TRUNCATE|DROP\s+COLUMN|DROP\s+SCHEMA|ALTER\s+ROLE|CREATE\s+ROLE)\b", re.I)


# ---------------------------------------------------------------- helpers
def sha256_file(rel: str) -> str | None:
    try:
        return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    except OSError:
        return None


def load_module(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def norm(text: str) -> str:
    spaced = re.sub(r"\s+", " ", text.replace("(", " ( ").replace(")", " ) ")).strip().lower()
    return re.sub(r"\s*,\s*", ", ", spaced)


def strip_outer(text: str) -> str:
    """Remove parentheses that enclose the WHOLE expression only ("(a) = (b)" is left intact)."""
    text = text.strip()
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        for i, ch in enumerate(text):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and i < len(text) - 1:
                return text
        text = text[1:-1].strip()
    return text


def strip_parens(text: str) -> str:
    return norm(strip_outer(text))


def canon_sql(text: str) -> str:
    """Whitespace- and paren-spacing-insensitive, but case-sensitive (literals such as 'OPEN' must match exactly)."""
    spaced = re.sub(r"\s+", " ", strip_outer(text).replace("(", " ( ").replace(")", " ) ")).strip()
    return re.sub(r"\s*,\s*", ", ", spaced)


def governed_checks(table: dict, vocabularies: dict) -> dict:
    """Every CHECK the contract governs for a table, with its exact predicate: explicit checks, column patterns
    (ck_<table>_<column>_pattern) and controlled vocabularies (ck_<table>_<column>); nullable columns admit NULL."""
    out = {}

    def add(name, predicate):
        if name in out:
            raise CompositionError(f"{table['name']}: governed check name {name} is ambiguous")
        out[name] = predicate
    for c in table["columns"]:
        guard = f"{c['name']} IS NULL OR " if c["nullable"] else ""
        if "pattern" in c:
            add(f"ck_{table['name']}_{c['name']}_pattern", f"{guard}{c['name']} ~ '{c['pattern']}'")
        if "vocabulary" in c:
            if c["type"] != "text":
                raise CompositionError(f"{table['name']}.{c['name']}: vocabulary CHECK generation covers text columns only")
            values = ", ".join(f"'{v}'" for v in vocabularies[c["vocabulary"]]["values"])
            add(f"ck_{table['name']}_{c['name']}", f"{guard}{c['name']} IN ({values})")
    for ck in table["checks"]:
        add(ck["name"], ck["rule"])
    return out


def ddl_checks(constraints: dict) -> dict:
    out = {}
    for name, line in constraints.items():
        m = re.match(r"CONSTRAINT \w+ CHECK\s*(\(.*\))\s*$", line)
        if m:
            out[name] = m.group(1)
    return out


class CompositionError(ValueError):
    pass


def compose(base: dict, addendum: dict) -> dict:
    """Effective contract = base + addendum. Fails closed when an amendment does not match the base exactly."""
    eff = copy.deepcopy(base)
    eff["contract_version"] = addendum["resulting_contract"]["contract_version"]
    eff["status"] = addendum["resulting_contract"]["status"]
    for name, vocab in addendum["vocabularies_added"].items():
        if name in eff["vocabularies"]:
            raise CompositionError(f"vocabulary {name} already exists in the base")
        eff["vocabularies"][name] = copy.deepcopy(vocab)
    for obj, tables in addendum["logical_object_coverage_added"].items():
        current = eff["logical_object_coverage"].get(obj)
        if not isinstance(current, list):
            raise CompositionError(f"logical object {obj} is not a mapped base object")
        eff["logical_object_coverage"][obj] = current + [t for t in tables if t not in current]
    names = {t["name"] for t in eff["tables"]}
    for table in addendum["tables_added"]:
        if table["name"] in names:
            raise CompositionError(f"table {table['name']} already exists in the base")
        eff["tables"].append(copy.deepcopy(table))
        names.add(table["name"])
    by_name = {t["name"]: t for t in eff["tables"]}
    for amendment in addendum["tables_amended"]:
        table = by_name.get(amendment["name"])
        if table is None or amendment["name"] in {t["name"] for t in addendum["tables_added"]}:
            raise CompositionError(f"amended table {amendment['name']} is not a base table")
        existing = {c["name"] for c in table["columns"]}
        for column in amendment.get("columns_added", []):
            if column["name"] in existing:
                raise CompositionError(f"{table['name']}.{column['name']} already exists")
            table["columns"].append(copy.deepcopy(column))
        table["mutable_columns"] += amendment.get("mutable_columns_added", [])
        table["write_once_columns"] += amendment.get("write_once_columns_added", [])
        for change in amendment.get("unique_replaced", []):
            if change["from"] not in table["unique"]:
                raise CompositionError(f"{table['name']}: unique {change['from'].get('name')} does not match the base exactly")
            table["unique"][table["unique"].index(change["from"])] = copy.deepcopy(change["to"])
        for change in amendment.get("transition_guards_replaced", []):
            if change["from"] not in table["transition_guards"]:
                raise CompositionError(f"{table['name']}: replaced transition guard does not match the base exactly")
            table["transition_guards"][table["transition_guards"].index(change["from"])] = change["to"]
        table["transition_guards"] += amendment.get("transition_guards_added", [])
    return eff


def _select(node, seg):
    if isinstance(seg, dict):
        (k, v), = seg.items()
        for i, item in enumerate(node):
            if isinstance(item, dict) and item.get(k) == v:
                return i
        raise KeyError(f"no element with {k}={v!r}")
    return seg


def apply_mutation(docs: dict, mut: dict) -> dict:
    d = copy.deepcopy(docs)
    path = mut["path"]
    if mut["op"] == "replace_text":
        if mut["old"] not in d[path[0]]:
            raise ValueError(f"text to replace not found in {path[0]}")
        d[path[0]] = d[path[0]].replace(mut["old"], mut["new"], 1)
        if mut.get("rehash"):                      # an attacker who also updates the pin to the edited bytes
            pin = next(a for a in d["manifest"]["added_artifacts"] if a["id"] == mut["rehash"])
            pin["sha256"] = hashlib.sha256(d[path[0]].encode("utf-8")).hexdigest()
        return d
    node = d
    for seg in path[:-1]:
        node = node[_select(node, seg)]
    last = _select(node, path[-1])
    if mut["op"] == "set":
        node[last] = copy.deepcopy(mut["value"])
    elif mut["op"] == "append":
        node[last].append(copy.deepcopy(mut["value"]))
    elif mut["op"] == "remove":
        del node[last]
    else:
        raise ValueError(f"unknown op {mut['op']}")
    return d


# ---------------------------------------------------------------- migration parsing
def ddl_tables(sql: str) -> dict:
    out = {}
    for m in re.finditer(r"CREATE TABLE trustlens\.(\w+) \((.*?)\n\);", sql, re.S):
        cols, cons = [], {}
        for raw in m.group(2).split("\n"):
            line = raw.strip().rstrip(",")
            if not line:
                continue
            if line.startswith("CONSTRAINT "):
                cons[line.split()[1]] = line
            else:
                parts = line.split()
                cols.append((parts[0], parts[1], "NOT NULL" not in line))
        out[m.group(1)] = (cols, cons)
    return out


def ddl_indexes(sql: str) -> dict:
    out = {}
    for m in re.finditer(r"CREATE (UNIQUE )?INDEX (\w+) ON trustlens\.(\w+)\s*\(([^)]*)\)(?:\s*WHERE ([^;]*))?;", sql, re.S):
        out[m.group(2)] = {"unique": bool(m.group(1)), "table": m.group(3),
                           "columns": [c.strip() for c in m.group(4).split(",")], "where": m.group(5)}
    return out


def privileges(spec: str, tables: str) -> set:
    out = set()
    tables = [t.strip().replace("trustlens.", "") for t in tables.split(",")]
    for part in re.findall(r"[A-Z]+\s*(?:\([^)]*\))?", spec.upper()):
        name = part.split("(")[0].strip()
        cols = re.findall(r"\(([^)]*)\)", part)
        for table in tables:
            if cols:
                out |= {(name, c.strip().lower(), table) for c in cols[0].split(",")}
            else:
                out.add((name, None, table))
    return out


def migration_grants(sql: str) -> tuple[set, list]:
    found, roles = set(), []
    for spec, tables, role in re.findall(r"GRANT\s+(.*?)\s+ON\s+(?!FUNCTION\b)(.*?)\s+TO\s+(\w+)\s*;", sql, re.S):
        roles.append(role)
        found |= {(role,) + p for p in privileges(" ".join(spec.split()), " ".join(tables.split()))}
    return found, roles


def addendum_grants(addendum: dict) -> set:
    out = set()
    for role, lines in addendum["grants_added"].items():
        for line in lines:
            m = re.match(r"^(.*?)\s+on\s+(.*)$", line, re.I)
            if not m:
                raise ValueError(f"unparseable grant {line!r}")
            out |= {(role,) + p for p in privileges(m.group(1), m.group(2))}
    return out


def diagram_transitions(doc: str) -> set:
    block = doc[doc.index("stateDiagram-v2"):]
    block = block[:block.index("```")]
    return {(a, b) for a, b in re.findall(r"^\s*([A-Z_]+) --> ([A-Z_]+)", block, re.M)}


def function_body(sql: str, name: str) -> str:
    m = re.search(rf"CREATE (?:OR REPLACE )?FUNCTION trustlens\.{name}\(\).*?\$\$(.*?)\$\$", sql, re.S)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- checks
def check(docs: dict, ctx: dict) -> list[tuple[str, str]]:
    errs: list[tuple[str, str]] = []

    def e(code, msg):
        errs.append((code, msg))

    m, add = docs["manifest"], docs["addendum"]
    # PSR-01
    for err in sorted(ctx["manifest_validator"].iter_errors(m), key=lambda x: list(x.path)):
        e("PSR-01", f"manifest schema: {err.message[:160]} at /{'/'.join(map(str, err.path))}")
    if errs:
        return errs

    # PSR-02 lifecycle
    review, integ, life = m["independent_review"], m["integration"], m["status"]
    rounds = review["prior_rounds"]
    if life == "CANDIDATE":
        if m["approved"] or m["activated"] or review["state"] != "PENDING" or review["verdict_record"] \
                or integ["state"] != "NOT_SUBMITTED":
            e("PSR-02", "a CANDIDATE revision is not approved, not activated, review PENDING and not submitted")
    else:
        gate = docs.get("gate") or ""
        recorded = (review["verdict_record"] == GATE_PATH and m["revision_id"] in gate and "APPROVE" in gate
                    and all(r["id"] in gate for r in m["constraint_relaxations"]))
        if not (m["approved"] and m["activated"] and review["state"] == "APPROVED" and recorded
                and rounds and rounds[-1]["verdict"] == "APPROVE"):
            e("PSR-02", "an ACCEPTED revision needs a final APPROVE round recorded in its gate record, approved and activated")
    merged = integ["state"] == "MERGED"
    if merged != (integ["pr_number"] is not None and integ["merge_commit"] is not None) or \
            (merged and life != "ACCEPTED") or (not merged and (integ["pr_number"] or integ["merge_commit"])):
        e("PSR-02", "the integration state must not claim a merge without a PR number and merge commit (and vice versa)")
    gate_status = next((ln for ln in (docs.get("gate") or "").splitlines() if ln.startswith("| Status |")), "")
    if integ["state"] == "REMOTE_CI_AND_MERGE_PENDING" and ("REMOTE CI + MERGE PENDING" not in gate_status
                                                             or re.search(r"\bMERGED\b", gate_status)):
        e("PSR-02", "the gate record's status must state that remote CI and merge are pending (and claim no merge)")
    if not any(r["verdict"] == "REQUEST_CHANGES" for r in rounds):
        e("PSR-02", "the prior REQUEST_CHANGES review rounds must remain recorded")

    # PSR-03 predecessors
    for key, rel in (("predecessor", PHASE6_PATH), ("phase7_closure", PHASE7_PATH)):
        pin = m[key]
        if pin["path"] != rel or pin["sha256"] != ctx["sha"].get(rel) or pin["unchanged"] is not True:
            e("PSR-03", f"{rel}: predecessor manifest must be pinned to its exact current bytes and unchanged")
    if m["predecessor"]["snapshot_artifact_count"] != len(docs["phase6"]["snapshot"]["artifacts"]):
        e("PSR-03", "predecessor snapshot artifact count does not match the Phase-6 closure manifest")

    # PSR-04 the 19 historical pins
    historical = [{k: a[k] for k in ("id", "path", "work_package", "role", "sha256")} for a in docs["phase6"]["snapshot"]["artifacts"]]
    if len(historical) != HISTORICAL_PIN_COUNT:
        e("PSR-04", f"the Phase-6 closure snapshot must still hold {HISTORICAL_PIN_COUNT} pins, found {len(historical)}")
    if m["carried_artifacts"] != historical:
        e("PSR-04", "carried_artifacts must equal the Phase-6 closure snapshot exactly (ids, paths, roles, digests, order)")
    for a in m["carried_artifacts"]:
        if a["sha256"] != ctx["sha"].get(a["path"]):
            e("PSR-04", f"{a['path']}: historical pin {a['sha256'][:12]} != bytes {str(ctx['sha'].get(a['path']))[:12]}")

    # PSR-05 structural schema pins (P6-WP7-LOW-1)
    low1 = next((o for o in docs["phase6"]["open_items"] if o["id"] == "P6-WP7-LOW-1"), None)
    named = set(re.findall(r"contracts/[a-z]+/[a-z-]+\.schema\.json", low1["why_open"])) if low1 else set()
    sp = m["structural_schema_pins"]
    paths = [a["path"] for a in sp["artifacts"]]
    if sp["origin"] != "P6-WP7-LOW-1" or set(paths) != STRUCTURAL_SCHEMAS or named != STRUCTURAL_SCHEMAS or len(paths) != 4:
        e("PSR-05", "exactly the four structural schemas named by P6-WP7-LOW-1 must be pinned")
    for a in sp["artifacts"]:
        if a["sha256"] != ctx["sha"].get(a["path"]):
            e("PSR-05", f"{a['path']}: structural pin does not match its bytes")

    # PSR-06 added artifacts
    added = {a["path"]: a for a in m["added_artifacts"]}
    required = REQUIRED_ADDED_ACCEPTED if life == "ACCEPTED" else REQUIRED_ADDED
    if set(added) != required or len(added) != len(m["added_artifacts"]):
        e("PSR-06", f"added artifacts must be exactly {sorted(required)}")
    validated = dict(ctx["sha"])          # text inputs are pinned by the bytes this run validates, not only the file
    validated[MIGRATION_PATH] = hashlib.sha256(docs["migration"].encode("utf-8")).hexdigest()
    validated[docs["addendum"]["human_contract"]] = hashlib.sha256(docs["human_contract"].encode("utf-8")).hexdigest()
    for rel, a in added.items():
        if a["sha256"] != validated.get(rel):
            e("PSR-06", f"{rel}: pinned {a['sha256'][:12]} != bytes {str(validated.get(rel))[:12]} (drift without a revision update)")
    all_paths = [a["path"] for a in m["carried_artifacts"]] + paths + list(added)
    if len(all_paths) != len(set(all_paths)):
        e("PSR-06", "an artifact is pinned twice")

    # PSR-07 addendum structure
    for err in sorted(ctx["addendum_validator"].iter_errors(add), key=lambda x: list(x.path)):
        e("PSR-07", f"addendum: {err.message[:160]} at /{'/'.join(map(str, err.path))}")
    if any(c == "PSR-07" for c, _ in errs):
        return errs

    # PSR-08 lifecycle + base
    base = docs["base"]
    base_pin = next((a for a in docs["phase6"]["snapshot"]["artifacts"] if a["path"] == BASE_PATH), {})
    if add["status"] != ADDENDUM_STATUS.get(life) or add["addendum_id"] != m["authorizing_change"]["id"]:
        e("PSR-08", f"the addendum named by this revision must be {ADDENDUM_STATUS.get(life)} while the revision is {life}")
    human_status = next((ln for ln in docs["human_contract"].splitlines() if ln.startswith("| Status |")), "")
    if (life == "ACCEPTED") != ("APPROVED FOLLOWING INDEPENDENT REVIEW" in human_status and "GATE-033" in human_status) \
            or (life == "CANDIDATE") != ("CANDIDATE" in human_status):
        e("PSR-08", "the human contract's status row must state the same lifecycle as the revision")
    ext = add["extends"]
    if (ext["sha256"] != ctx["sha"].get(BASE_PATH) or ext["sha256"] != base_pin.get("sha256")
            or ext["contract_version"] != base["contract_version"] or ext["contract_id"] != base["contract_id"]):
        e("PSR-08", "the addendum must extend the exact frozen base (Phase-6 pin, bytes, id and version)")
    if m["effective_persistence_contract"]["base_sha256"] != ext["sha256"]:
        e("PSR-08", "the manifest and the addendum pin different bases")

    # PSR-09 composition
    try:
        effective = compose(base, add)
    except (CompositionError, KeyError, TypeError) as ex:
        e("PSR-09", f"composition failed: {ex}")
        return errs

    # PSR-10 full data-contract validation of the effective contract
    epc = m["effective_persistence_contract"]
    if effective["contract_version"] != EFFECTIVE_VERSION or epc["effective_version"] != EFFECTIVE_VERSION \
            or epc["base_version"] != base["contract_version"]:
        e("PSR-10", f"effective contract version must be {EFFECTIVE_VERSION} composed from {base['contract_version']}")
    for code, msg in ctx["vdc"].check(effective, ctx["structural_validator"]):
        e("PSR-10", f"effective contract {code}: {msg}")
    tables = {t["name"]: t for t in effective["tables"]}
    if (epc["table_count"] != len(tables) or epc["vocabulary_count"] != len(effective["vocabularies"])
            or epc["added_tables"] != [t["name"] for t in add["tables_added"]]
            or epc["amended_tables"] != [t["name"] for t in add["tables_amended"]]):
        e("PSR-10", "effective contract counts or table lists in the manifest do not match the composition")

    # PSR-11 historical negative mutations still bite (memoized per exact effective contract + mutation set: same result)
    memo_key = hashlib.sha256(json.dumps([effective, docs["data_negatives"]], sort_keys=True).encode()).hexdigest()
    memo = ctx.setdefault("psr11_memo", {})
    if memo_key not in memo:
        found = []
        for mut in docs["data_negatives"]:
            try:
                mutated = ctx["vdc"].apply_mutation(effective, mut)
            except (KeyError, IndexError, ValueError) as ex:
                found.append(f"historical mutation {mut['id']} no longer applies to the effective contract ({ex})")
                continue
            if mut["expect"] not in {c for c, _ in ctx["vdc"].check(mutated, ctx["structural_validator"])}:
                found.append(f"historical mutation {mut['id']} ({mut['expect']}) no longer bites on the effective contract")
        memo[memo_key] = found
    for msg in memo[memo_key]:
        e("PSR-11", msg)

    # PSR-12 governed constraint relaxation
    replaced = [(am["name"], r) for am in add["tables_amended"] for r in am.get("unique_replaced", [])]
    relax = {r["id"]: r for r in add["constraint_relaxations"]}
    mrelax = {r["id"]: r for r in m["constraint_relaxations"]}
    if replaced and add["change_class"] != "ADDITIVE_WITH_GOVERNED_CONSTRAINT_RELAXATION":
        e("PSR-12", "a replaced unique constraint makes the change class ADDITIVE_WITH_GOVERNED_CONSTRAINT_RELAXATION, not ADDITIVE")
    for table, r in replaced:
        rel = relax.get(r["relaxation_id"])
        relaxing = "where" not in r["from"] and "where" in r["to"] and r["from"]["columns"] == r["to"]["columns"] \
            and r["from"]["name"] == r["to"]["name"]
        if rel is None or rel["table"] != table or rel["constraint"] != r["from"]["name"] or not relaxing:
            e("PSR-12", f"{table}.{r['from']['name']}: the change must be a recorded governed relaxation (same name and columns, partial)")
        if rel and (len(rel["preserved_invariants"]) < 3 or len(rel["migration_compatibility"]) < 2):
            e("PSR-12", f"{r['relaxation_id']}: preserved invariants and migration compatibility must be explained")
        mr = mrelax.get(r["relaxation_id"])
        if not mr or mr["accepted"] is not m["approved"] or mr["table"] != table or mr["constraint"] != r["from"]["name"]:
            e("PSR-12", f"{r['relaxation_id']}: the relaxation is accepted exactly when the revision is approved")
    if set(relax) != {r["relaxation_id"] for _, r in replaced} or set(mrelax) != set(relax):
        e("PSR-12", "relaxation records must correspond one-to-one to replaced constraints")
    human = docs["human_contract"]
    for rid in relax:
        if rid not in human or "governed constraint relaxation" not in human.lower() or "not additive" not in human.lower():
            e("PSR-12", f"the human contract must document {rid} as a governed constraint relaxation that is not additive")

    # PSR-13 migration catalog
    sql = docs["migration"]
    mig = m["migration"]
    if (f'revision = "{mig["revision"]}"' not in sql or f'down_revision = "{mig["down_revision"]}"' not in sql
            or mig["revision"] != "0004_evidence_intake" or mig["down_revision"] != "0003_case_submission"):
        e("PSR-13", "migration 0004 must follow 0003 as declared")
    created = ddl_tables(sql)
    expected = [t["name"] for t in add["tables_added"]] + add["existing_contract_tables_created_by_migration"]
    if sorted(created) != sorted(expected):
        e("PSR-13", f"migration creates {sorted(created)}, contract declares {sorted(expected)}")
    indexes = ddl_indexes(sql)
    for name in expected:
        t, ddl = tables.get(name), created.get(name)
        if not t or not ddl:
            continue
        cols, cons = ddl
        want = [(c["name"], c["type"], c["nullable"]) for c in t["columns"]]
        if cols != want:
            e("PSR-13", f"{name}: DDL columns/types/nullability differ from the effective contract")
        for fk in t["foreign_keys"]:
            needle = norm(f"FOREIGN KEY ({', '.join(fk['columns'])}) REFERENCES trustlens.{fk['references']['table']} "
                          f"({', '.join(fk['references']['columns'])}) ON DELETE {fk['on_delete'].replace('_', ' ')}")
            if not any(needle in norm(line) for line in cons.values()):
                e("PSR-13", f"{name}: foreign key {fk['columns']} missing or different in DDL")
        for u in t["unique"]:
            if "where" in u:
                ix = indexes.get(u["name"])
                if not ix or not ix["unique"] or ix["columns"] != u["columns"] or strip_parens(ix["where"] or "") != strip_parens(u["where"]):
                    e("PSR-13", f"{name}: partial unique {u['name']} missing or different")
            elif u["name"] not in cons or norm(f"UNIQUE ({', '.join(u['columns'])})") not in norm(cons[u["name"]]):
                e("PSR-13", f"{name}: unique {u['name']} missing or different")
        try:
            governed = governed_checks(t, effective["vocabularies"])
        except (CompositionError, KeyError) as ex:
            e("PSR-13", str(ex))
            governed = {}
        actual = ddl_checks(cons)
        for ck in sorted(set(governed) - set(actual)):
            e("PSR-13", f"{name}: governed check {ck} missing from the migration")
        for ck in sorted(set(actual) - set(governed)):
            e("PSR-13", f"{name}: migration check {ck} is not governed by the effective contract")
        for ck in sorted(set(governed) & set(actual)):
            if canon_sql(actual[ck]) != canon_sql(governed[ck]):
                e("PSR-13", f"{name}: {ck} predicate differs from the governed rule ({canon_sql(actual[ck])[:60]!r})")
        for i in t["indexes"]:
            ix = indexes.get(i["name"])
            if not ix or ix["table"] != name or ix["columns"] != i["columns"] or \
                    strip_parens(ix["where"] or "") != strip_parens(i.get("where", "")):
                e("PSR-13", f"{name}: index {i['name']} missing or different")
    for am in add["tables_amended"]:
        for col in am.get("columns_added", []):
            null = "" if col["nullable"] else " NOT NULL"
            if norm(f"ALTER TABLE trustlens.{am['name']} ADD COLUMN {col['name']} {col['type']}{null};") not in norm(sql):
                e("PSR-13", f"{am['name']}.{col['name']}: ADD COLUMN missing or different")
        for r in am.get("unique_replaced", []):
            ix = indexes.get(r["to"]["name"])
            if norm(f"ALTER TABLE trustlens.{am['name']} DROP CONSTRAINT {r['from']['name']};") not in norm(sql) or not ix \
                    or not ix["unique"] or ix["columns"] != r["to"]["columns"] or strip_parens(ix["where"] or "") != strip_parens(r["to"].get("where", "")):
                e("PSR-13", f"{am['name']}: {r['from']['name']} replacement DDL missing or different")
    altered = set(re.findall(r"ALTER TABLE trustlens\.(\w+)", sql))
    if not altered <= {am["name"] for am in add["tables_amended"]}:
        e("PSR-15", f"migration alters undeclared tables {sorted(altered - {am['name'] for am in add['tables_amended']})}")

    # PSR-14 transition guards
    allowed = set(re.findall(r"\('([A-Z_]+)', '([A-Z_]+)'\)", function_body(sql, "tg_evidence_item_guard")))
    if allowed != diagram_transitions(docs["wp2_doc"]):
        e("PSR-14", "evidence_item transition guard differs from the DATA-001-WP2 §11 state diagram")
    intent_guard = function_body(sql, "tg_evidence_upload_intent_guard")
    if "'OPEN'" not in intent_guard or "'MATERIALIZED'" not in intent_guard or "evidence_item_id" not in intent_guard:
        e("PSR-14", "evidence_upload_intent guard must enforce OPEN -> MATERIALIZED and a write-once evidence_item_id")
    fence = function_body(sql, "tg_cross_store_operation_guard")
    if "NEW.attempt_count < OLD.attempt_count" not in fence or "OLD.attempt_count + 1" not in fence:
        e("PSR-14", "cross_store_operation guard must enforce the attempt_count fencing token (never back, +1 only)")
    supersede = function_body(sql, "tg_api_idempotency_record_write_once")
    if "superseded_at" not in supersede or "active_until" not in supersede or "now()" not in supersede:
        e("PSR-14", "api_idempotency_record guard must allow superseded_at only after active_until, write-once")
    for name in expected:
        t = tables.get(name, {})
        if t.get("delete_policy") == "GOVERNED_DELETION_ONLY" and not re.search(
                rf"BEFORE DELETE ON trustlens\.{name}\s+FOR EACH ROW EXECUTE FUNCTION trustlens\.tg_governed_deletion_only\(\)", sql):
            e("PSR-14", f"{name}: governed-deletion trigger missing")
        if t.get("mutability") in ("M-OPS", "M-APP", "M-IMM") and not re.search(rf"BEFORE UPDATE ON trustlens\.{name}\s", sql):
            e("PSR-14", f"{name}: update guard trigger missing")
        for trig in t.get("constraint_triggers", []):
            if not function_body(sql, trig["name"]):
                e("PSR-14", f"{name}: constraint trigger function {trig['name']} missing")

    # PSR-15 privileges
    if FORBIDDEN_SQL.search(sql):
        e("PSR-15", f"migration contains a forbidden statement: {FORBIDDEN_SQL.search(sql).group(0)}")
    granted, roles = migration_grants(sql)
    try:
        declared = addendum_grants(add)
    except ValueError as ex:
        e("PSR-15", str(ex))
        declared = set()
    if granted != declared:
        e("PSR-15", f"migration grants differ from the addendum: extra {sorted(map(str, granted - declared))[:3]}, "
                    f"missing {sorted(map(str, declared - granted))[:3]}")
    for role, priv, col, table in granted:
        if priv in FORBIDDEN_PRIVILEGES:
            e("PSR-15", f"{role} must not be granted {priv} on {table}")
        if priv == "UPDATE":
            t = tables.get(table, {})
            if col is None or col not in set(t.get("mutable_columns", [])) | set(t.get("write_once_columns", [])):
                e("PSR-15", f"UPDATE on {table}.{col} is not a declared mutable or write-once column")
    if set(roles) - {"tl_app_runtime"}:
        e("PSR-15", f"migration grants to unexpected roles {sorted(set(roles) - {'tl_app_runtime'})}")

    # PSR-16 API / OpenAPI unchanged
    ac = m["api_contract"]
    pins = {a["path"]: a["sha256"] for a in docs["phase6"]["snapshot"]["artifacts"]}
    if (ac["changed"] is not False or pins.get(API_PATH) is None or ac["api_catalog_sha256"] != pins.get(API_PATH)
            or ctx["sha"].get(API_PATH) != pins.get(API_PATH) or ctx["sha"].get(OPENAPI_PATH) != pins.get(OPENAPI_PATH)
            or ac["openapi_sha256"] != pins.get(OPENAPI_PATH) or ac["api_version"] != docs["api"]["api_version"]
            or ac["openapi_info_version"] != docs["openapi"]["info"]["version"]):
        e("PSR-16", "the API catalog and OpenAPI must stay byte-for-byte the Phase-6 pinned versions")
    if not add["api_impact"].startswith("NONE."):
        e("PSR-16", "the addendum must have no API impact")

    # PSR-17 claims and carried items
    cb = m["claim_boundary"]
    excluded = MUST_NOT_SUPPORT | MUST_NOT_SUPPORT_BY_LIFECYCLE.get(life, set())
    if not excluded <= set(cb["must_not_support"]) or set(cb["may_support"]) & set(cb["must_not_support"]):
        e("PSR-17", f"the claim boundary must exclude {sorted(excluded)}")
    if mig["applied_to_sponsor_database"] is not False or mig["apply_before_activation"] is not False:
        e("PSR-17", "migration 0004 must not be applied to the sponsor database before activation")
    items = {o["id"]: o for o in m["open_items"]}
    if "ADDITIVE-REVISION-ID-PATTERN" not in items or items.get("P6-WP7-LOW-1", {}).get("state") != LOW1_STATE.get(life):
        e("PSR-17", f"open items must carry P6-WP7-LOW-1 as {LOW1_STATE.get(life)} and the additive-revision id limitation")
    steps = " ".join(m["activation_steps"]).lower()
    for needed in STEPS_BY_LIFECYCLE.get(life, ()):
        if needed not in steps:
            e("PSR-17", f"activation steps must include {needed!r}")
    return errs


# ---------------------------------------------------------------- driver
def inputs() -> tuple[dict, dict]:
    def load(rel):
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    docs = {
        "manifest": load(MANIFEST_PATH), "addendum": load(ADDENDUM_PATH), "base": load(BASE_PATH),
        "phase6": load(PHASE6_PATH), "phase7": load(PHASE7_PATH), "api": load(API_PATH), "openapi": load(OPENAPI_PATH),
        "data_negatives": load(DATA_NEGATIVE_PATH)["mutations"],
        "migration": (ROOT / MIGRATION_PATH).read_text(encoding="utf-8"),
        "wp2_doc": (ROOT / WP2_DOC_PATH).read_text(encoding="utf-8"),
    }
    docs["human_contract"] = (ROOT / docs["addendum"]["human_contract"]).read_text(encoding="utf-8")
    gate = ROOT / GATE_PATH
    docs["gate"] = gate.read_text(encoding="utf-8") if gate.is_file() else ""
    structural = load(STRUCTURAL_PATH)
    manifest_schema, addendum_schema = load(MANIFEST_SCHEMA_PATH), load(ADDENDUM_SCHEMA_PATH)
    for s in (structural, manifest_schema, addendum_schema):
        Draft202012Validator.check_schema(s)
    registry = Registry().with_resource(structural["$id"], Resource.from_contents(structural))
    pinned = ({a["path"] for a in docs["phase6"]["snapshot"]["artifacts"]} | STRUCTURAL_SCHEMAS | REQUIRED_ADDED_ACCEPTED
              | {PHASE6_PATH, PHASE7_PATH, BASE_PATH, API_PATH, OPENAPI_PATH}
              | {a.get("path") for a in docs["manifest"].get("added_artifacts", []) if isinstance(a, dict)}
              | {a.get("path") for a in docs["manifest"].get("carried_artifacts", []) if isinstance(a, dict)})
    ctx = {
        "sha": {p: sha256_file(p) for p in pinned if isinstance(p, str)},
        "manifest_validator": Draft202012Validator(manifest_schema),
        "addendum_validator": Draft202012Validator(addendum_schema, registry=registry),
        "structural_validator": Draft202012Validator(structural),
        "vdc": load_module("validate_data_contract", "knowledge/validation/validate_data_contract.py"),
    }
    return docs, ctx


def main() -> int:
    quiet = "--quiet" in sys.argv
    try:
        docs, ctx = inputs()
    except (OSError, json.JSONDecodeError, KeyError) as ex:
        print(f"  FAIL  PSR-01  inputs unreadable: {ex!r}")
        print("PHASE-6 SNAPSHOT REVISION: FAIL")
        return 1
    errs = check(docs, ctx)
    if errs:
        for code, msg in errs:
            print(f"  FAIL  {code}  {msg}")
        print(f"PHASE-6 SNAPSHOT REVISION: FAIL — {len(errs)} violation(s)")
        return 1
    negatives = json.loads((ROOT / NEGATIVE_PATH).read_text(encoding="utf-8"))["mutations"]
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
        elif set(mut.get("must_not_report", [])) & found:
            failures.append(f"{mut['id']}: must be caught without {sorted(set(mut['must_not_report']) & found)}")
        elif not quiet:
            print(f"  ok    {mut['id']} rejected by {mut['expect']}: {mut['description']}")
    if failures:
        for f in failures:
            print(f"  FAIL  negative fixture {f}")
        print("PHASE-6 SNAPSHOT REVISION: FAIL — a guard did not bite")
        return 1
    m = docs["manifest"]
    effective = compose(docs["base"], docs["addendum"])
    n_checks = len(set(re.findall(r"^  (PSR-\d\d) ", __doc__, re.M)))
    state = ("not approved, not activated" if m["status"] == "CANDIDATE" else
             f"approved and activated by {m['independent_review']['verdict_record'].split('/')[-1][:8]}; integration {m['integration']['state']}")
    print(f"PHASE-6 SNAPSHOT REVISION: PASS — {m['revision_id']} {m['status']} ({state}); "
          f"{len(m['carried_artifacts'])} historical pins carried unchanged + {len(m['structural_schema_pins']['artifacts'])} "
          f"structural-schema pins + {len(m['added_artifacts'])} added pins; effective persistence contract "
          f"{effective['contract_version']} ({len(effective['tables'])} tables) passes DC-01..DC-25 and "
          f"{len(docs['data_negatives'])} historical negative mutations; {len(m['constraint_relaxations'])} governed constraint relaxation(s) recorded; "
          f"{n_checks} checks; {len(negatives)} negative mutations rejected (static; migration not executed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
