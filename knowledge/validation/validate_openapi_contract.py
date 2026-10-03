"""TrustLens Phase 6 P6-WP4 — static validator for the OpenAPI 3.1 encoding of API-001.

Validates contracts/api/openapi-v1.json against the accepted machine catalog contracts/api/api-v1.json (which
validate_api_contract.py already checks against API-001's invariants) and the promoted Phase-3 schemas. This is
DETERMINISTIC STRUCTURAL validation plus catalog parity — no official OpenAPI conformance validator is pinned in
requirements.txt, so no claim of full OpenAPI specification compliance is made. Component schemas are checked against
the JSON Schema Draft 2020-12 metaschema (the OpenAPI 3.1 schema dialect, extensions permitted).

  OA-01 document is OpenAPI 3.1.x with info/paths/components; no OpenAPI-3.0-only `nullable`; JSON Schema 2020-12 dialect
  OA-02 servers are relative placeholders (no hostname, no localhost, no gateway)
  OA-03 operation set parity: every catalog operationId exactly once; no extra operation
  OA-04 method + path parity
  OA-05 success status parity (exactly one 2xx response, equal to the catalog)
  OA-06 request body parity (JSON $ref or binary body name equals the catalog request schema; none when the catalog has none)
  OA-07 success response parity (JSON $ref or binary body name equals the catalog response schema)
  OA-08 authentication parity (bearer on every protected operation, none on internal probes) and role parity
  OA-09 resource-authorization, content-permission and break-glass-role parity
  OA-10 idempotency parity (Idempotency-Key header present and required exactly where the catalog requires it)
  OA-11 audit parity (required flag + event)
  OA-12 sensitivity parity
  OA-13 sync/async parity (async operations answer 202)
  OA-14 concurrency parity (If-Match required + 412 and 428 responses exactly where the catalog requires it)
  OA-15 error parity (per-operation error codes and their HTTP statuses equal the catalog error table)
  OA-16 component schema parity (properties, required, additionalProperties:false on requests, enum values) with the catalog
  OA-17 every local $ref resolves; no external $ref
  OA-18 no tenant concept anywhere (property, parameter or header names)
  OA-19 no API-invented decision field (priority, probability, score, likelihood, ranking, urgency) anywhere
  OA-20 DetectionResult immutable: no PUT/PATCH/DELETE on the result path; no DELETE operation at all
  OA-21 governed result tree keeps AC-24 traces exactly as the catalog; no trace to the reserved, non-emitted priority
  OA-22 knowledge control addresses the exact 64-hex content_digest; no bundle_version, no oneOf/anyOf escape branch
  OA-23 no latest/newest/current/previous activation semantics in knowledge paths, properties or enums
  OA-24 no arbitrary server-side URL fetch (paths, *_url properties)
  OA-25 break-glass creation is ADMINISTRATOR-only; break-glass content roles limited to ADMINISTRATOR
  OA-26 caller constraints: ASSIGNEE_NOT_CALLER on access-granting operations; REVIEWER_NOT_GRANTEE on break-glass review
  OA-27 C4 content fields keep x-trustlens-visibility CONTENT_PERMISSION and every operation returning them is C3/C4
  OA-28 replay request accepts only a reason code and keeps pinned/no-AI/no-substitution semantics
  OA-29 mass assignment: request schemas reject unknown properties and carry no server-controlled field
  OA-30 pagination: cursor + limit on list operations, no invented default/maximum, filters exactly the catalog allow-list
  OA-31 timestamps are date-time strings; no server timestamp is client-settable
  OA-32 health probes expose only a status; operator health exposes no topology fields
  OA-33 evidence/report bytes are binary bodies, never base64 JSON
  OA-34 ETag strategy resolved: server-revision decision recorded and ETag headers on mutable shared resources
  OA-35 info.version is a contract version, not ENGINE_VERSION; no FastAPI/web-framework dependency in requirements.txt
  OA-36 component schemas are valid JSON Schema 2020-12

It then applies every mutation in contracts/api/fixtures/openapi-negative-mutations.json and requires the named
check to fail. Offline and deterministic: reads repository files only.

Usage:  .venv/bin/python knowledge/validation/validate_openapi_contract.py [--quiet]
Exit 0 = OpenAPI consistent with the catalog and every negative mutation rejected by its expected check.
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
OPENAPI_PATH = ROOT / "contracts" / "api" / "openapi-v1.json"
CATALOG_PATH = ROOT / "contracts" / "api" / "api-v1.json"
PERSISTENCE_PATH = ROOT / "contracts" / "postgresql" / "schema-v1.json"
NEGATIVE_PATH = ROOT / "contracts" / "api" / "fixtures" / "openapi-negative-mutations.json"
REQUIREMENTS_PATH = ROOT / "requirements.txt"
ENGINE_PATH = ROOT / "knowledge" / "runtime" / "engine.py"

METHODS = ("get", "put", "post", "delete", "patch", "options", "head", "trace")
HEX64 = "^[0-9a-f]{64}$"
TENANT = re.compile(r"tenant", re.I)
INVENTED = re.compile(r"(priority|probab|likelihood|percent|score|rank|urgency)", re.I)
LATEST = re.compile(r"\b(latest|newest|current|previous)\b", re.I)
FETCH = re.compile(r"(fetch|proxy|crawl|scrape|resolve-url|url-check|lookup-url)", re.I)
RESERVED_TRACE = "knowledge/schemas/detection/detection-result.schema.json#/$defs/recommendedAction/properties/priority"
SERVER_CONTROLLED = {
    "actor_id", "actor_principal_id", "adjudicated_by", "adjudicating_principal_id", "created_by", "owner_principal_id",
    "owner_id", "event_hash", "previous_event_hash", "audit_hash", "execution_fence_token", "classification", "risk_level",
    "decision_severity", "detection_confidence", "matched_evidence_strength", "rule_results", "matched_rules",
    "governing_rule", "explanation", "recommended_actions", "ai_verdict", "ai_confidence", "engine_version",
    "result_contract_version", "result_digest", "bundle_version", "bundle_content_digest", "content_sha256",
    "replay_material_digest", "status", "state", "created_at", "completed_at", "adjudicated_at", "role", "roles",
    "grant_kind", "is_synthetic", "failure_category", "use_latest", "ai_reextract", "principal_id",
}
FRAMEWORKS = re.compile(r"^(fastapi|starlette|flask|django|uvicorn|gunicorn|sanic|aiohttp|connexion)\b", re.I | re.M)
GOVERNED_RESULT_ROOT = "DetectionResultResponse"


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def iter_ops(doc):
    for path, item in doc.get("paths", {}).items():
        if not isinstance(item, dict):
            continue
        for m in METHODS:
            if m in item:
                yield path, m, item[m]


def walk(node, fn, where=""):
    fn(node, where)
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, fn, f"{where}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, fn, f"{where}/{i}")


def resolve(doc, ref):
    if not ref.startswith("#/"):
        return None
    node = doc
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def deref(doc, node):
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 20:
        node = resolve(doc, node["$ref"]) or {}
        seen += 1
    return node


def schema_name(node):
    if isinstance(node, dict) and "$ref" in node and node["$ref"].startswith("#/components/schemas/"):
        return node["$ref"].rsplit("/", 1)[1]
    return None


def check(doc: dict, cat: dict, persistence: dict) -> list[tuple[str, str]]:
    errs: list[tuple[str, str]] = []

    def e(code, msg):
        errs.append((code, msg))

    # ---- OA-01 / OA-02 / OA-35
    if not isinstance(doc.get("openapi"), str) or not re.match(r"^3\.1\.\d+$", doc["openapi"]):
        e("OA-01", f"openapi must be 3.1.x, got {doc.get('openapi')!r}")
    for k in ("info", "paths", "components"):
        if k not in doc:
            e("OA-01", f"missing top-level {k}")
    if doc.get("jsonSchemaDialect") not in (None, "https://json-schema.org/draft/2020-12/schema"):
        e("OA-01", "jsonSchemaDialect must be JSON Schema 2020-12")
    walk(doc, lambda n, w: e("OA-01", f"OpenAPI-3.0-only 'nullable' at {w}") if isinstance(n, dict) and "nullable" in n else None)
    if errs:
        return errs
    for s in doc.get("servers", []):
        url = s.get("url", "")
        if re.match(r"^[a-z]+://", url) or "localhost" in url or "127.0.0.1" in url:
            e("OA-02", f"server url {url!r} implies a host/topology")
    eng = re.search(r'ENGINE_VERSION\s*=\s*"([^"]+)"', ENGINE_PATH.read_text(encoding="utf-8")).group(1)
    iv = str(doc["info"].get("version", ""))
    if iv in (eng, cat["api_version"]) or "v1" not in iv:
        e("OA-35", f"info.version {iv!r} must be a contract version distinct from ENGINE_VERSION and naming v1")
    if FRAMEWORKS.search(REQUIREMENTS_PATH.read_text(encoding="utf-8")):
        e("OA-35", "a web framework/server dependency was added to requirements.txt (no implementation in P6-WP4)")

    # ---- OA-17 refs
    def refcheck(n, w):
        if isinstance(n, dict) and "$ref" in n:
            r = n["$ref"]
            if not isinstance(r, str) or not r.startswith("#/"):
                e("OA-17", f"external or non-local $ref {r!r} at {w}")
            elif resolve(doc, r) is None:
                e("OA-17", f"dangling $ref {r} at {w}")
    walk(doc, refcheck)

    comps = doc["components"].get("schemas", {})
    # ---- OA-36 metaschema
    for n, s in comps.items():
        try:
            Draft202012Validator.check_schema(s)
        except SchemaError as ex:
            e("OA-36", f"components.schemas.{n} is not valid JSON Schema 2020-12: {ex.message}")

    # ---- parity
    catops = {o["operation_id"]: o for o in cat["operations"]}
    errtab = {x["code"]: x["http_status"] for x in cat["error_codes"]}
    seen = {}
    for path, m, op in iter_ops(doc):
        oid = op.get("operationId")
        if oid in seen:
            e("OA-03", f"duplicate operationId {oid}")
        seen[oid] = (path, m, op)
    for oid in catops:
        if oid not in seen:
            e("OA-03", f"catalog operation {oid} missing from OpenAPI")
    for oid in seen:
        if oid not in catops:
            e("OA-03", f"OpenAPI operation {oid} is not in the accepted catalog")

    def params_of(op):
        out = []
        for p in op.get("parameters", []):
            out.append(deref(doc, p))
        return out

    content_fields = set()
    for sn, s in comps.items():
        for pn, ps in (s.get("properties") or {}).items():
            if isinstance(ps, dict) and ps.get("x-trustlens-visibility") == "CONTENT_PERMISSION":
                content_fields.add(sn)

    def closure(name):
        out, stack = set(), [name]
        while stack:
            n = stack.pop()
            if n in out or n not in comps:
                continue
            out.add(n)
            walk(comps[n], lambda x, w: stack.append(schema_name(x)) if schema_name(x) else None)
        return out

    for oid, (path, m, op) in seen.items():
        # ---- invariants that hold for EVERY operation present, catalogued or not
        # immutability
        if m in ("put", "patch", "delete") and (path.endswith("/result") or op.get("x-trustlens-target-resource") == "DetectionResult"):
            e("OA-20", f"{oid}: mutation of the immutable DetectionResult")
        if m == "delete":
            e("OA-20", f"{oid}: HTTP DELETE is not used for governed resources")
        # knowledge
        if op.get("x-trustlens-knowledge-control"):
            body = deref(doc, (op.get("requestBody") or {}).get("content", {}).get("application/json", {}).get("schema", {}))
            props = body.get("properties", {})
            in_path = "{content_digest}" in path
            cd = deref(doc, props.get("content_digest", {}))
            if not in_path and not ("content_digest" in body.get("required", []) and cd.get("pattern") == HEX64):
                e("OA-22", f"{oid}: content_digest must be required with the 64-hex pattern")
            if "bundle_version" in props:
                e("OA-22", f"{oid}: bundle_version is not an activation identity")
            if any(k in body for k in ("oneOf", "anyOf")):
                e("OA-22", f"{oid}: knowledge request must not offer alternative identity branches")
            if LATEST.search(path) or any(LATEST.search(k) for k in props):
                e("OA-23", f"{oid}: latest/newest/current/previous semantics")
            walk(body, lambda n, w: e("OA-23", f"{oid}: latest-like enum value") if isinstance(n, dict) and any(
                isinstance(v, str) and LATEST.search(v.replace("_", " ")) for v in n.get("enum", [])) else None)
        if re.search(r"/(rules|rule|indicators|taxonomy|rule-sets)(/|$)", path) and m != "get":
            e("OA-22", f"{oid}: rule/knowledge body mutation bypasses Git/CI governance")
        if FETCH.search(path):
            e("OA-24", f"{oid}: arbitrary server-side URL fetch")
        # break-glass / constraints
        if op.get("x-trustlens-target-resource") == "BreakGlassGrant" and m == "post" \
                and op.get("x-trustlens-resource-authorization") == "BREAK_GLASS_SELF" and op.get("x-trustlens-roles") != ["ADMINISTRATOR"]:
            e("OA-25", f"{oid}: break-glass creation must be ADMINISTRATOR-only")
        if set(op.get("x-trustlens-break-glass-roles", [])) - {"ADMINISTRATOR"}:
            e("OA-25", f"{oid}: break-glass content roles limited to ADMINISTRATOR")
        c = catops.get(oid)
        if not c:
            continue
        if (m.upper(), path) != (c["method"], c["path"]):
            e("OA-04", f"{oid}: {m.upper()} {path} != catalog {c['method']} {c['path']}")
        resp = op.get("responses", {})
        two = [k for k in resp if k.startswith("2")]
        if two != [str(c["success_status"])]:
            e("OA-05", f"{oid}: success responses {two} != catalog {c['success_status']}")
        # request
        rb = op.get("requestBody")
        rs = c["request_schema"]
        if rs is None:
            if rb:
                e("OA-06", f"{oid}: request body declared but catalog has none")
        else:
            if not rb or not rb.get("required"):
                e("OA-06", f"{oid}: required request body {rs} missing")
            else:
                got = rb.get("x-trustlens-binary-body") or schema_name(rb.get("content", {}).get("application/json", {}).get("schema"))
                if got != rs:
                    e("OA-06", f"{oid}: request schema {got} != catalog {rs}")
        # response
        sr = resp.get(str(c["success_status"]), {})
        got = sr.get("x-trustlens-binary-body") or schema_name(sr.get("content", {}).get("application/json", {}).get("schema"))
        if got != c["response_schema"]:
            e("OA-07", f"{oid}: response schema {got} != catalog {c['response_schema']}")
        # auth
        sec = op.get("security", doc.get("security"))
        if c["internal"]:
            if sec != []:
                e("OA-08", f"{oid}: internal probe must declare security: []")
        elif sec != [{"bearerAuth": []}]:
            e("OA-08", f"{oid}: protected operation must require bearerAuth")
        if op.get("x-trustlens-roles") != c["roles"]:
            e("OA-08", f"{oid}: roles {op.get('x-trustlens-roles')} != catalog {c['roles']}")
        for k, ck in (("x-trustlens-resource-authorization", "resource_authorization"),
                      ("x-trustlens-sensitive-content-permission", "sensitive_content_permission"),
                      ("x-trustlens-break-glass-roles", "break_glass_roles")):
            if op.get(k) != c[ck]:
                e("OA-09", f"{oid}: {k} {op.get(k)!r} != catalog {c[ck]!r}")
        # idempotency
        prms = params_of(op)
        idem = [p for p in prms if p.get("name") == "Idempotency-Key" and p.get("in") == "header"]
        if op.get("x-trustlens-idempotency") != c["idempotency"]:
            e("OA-10", f"{oid}: x-trustlens-idempotency != catalog")
        if c["idempotency"] == "REQUIRED" and not (idem and idem[0].get("required") is True):
            e("OA-10", f"{oid}: Idempotency-Key header must be present and required")
        if c["idempotency"] != "REQUIRED" and idem:
            e("OA-10", f"{oid}: Idempotency-Key declared on a non-idempotency operation")
        if c["idempotency"] == "REQUIRED" and "IDEMPOTENCY_KEY_REUSED" not in resp.get("409", {}).get("x-trustlens-error-codes", []):
            e("OA-10", f"{oid}: 409 IDEMPOTENCY_KEY_REUSED must be documented")
        # audit / sensitivity / mode
        if op.get("x-trustlens-audit") != {"required": c["audit"] == "REQUIRED", "event": c["audit_event"]}:
            e("OA-11", f"{oid}: audit metadata != catalog")
        if op.get("x-trustlens-sensitivity") != c["sensitivity"]:
            e("OA-12", f"{oid}: sensitivity {op.get('x-trustlens-sensitivity')} != catalog {c['sensitivity']}")
        if op.get("x-trustlens-mode") != c["mode"] or (c["mode"] == "ASYNC") != (c["success_status"] == 202 and "202" in resp):
            e("OA-13", f"{oid}: sync/async representation != catalog")
        # concurrency
        im = [p for p in prms if p.get("name") == "If-Match" and p.get("in") == "header"]
        if c["concurrency"] == "IF_MATCH_REQUIRED":
            if not (im and im[0].get("required") is True and "412" in resp and "428" in resp):
                e("OA-14", f"{oid}: If-Match must be required with 412 and 428 responses")
        elif im:
            e("OA-14", f"{oid}: If-Match declared on an operation without catalog concurrency")
        # errors
        doc_codes = {}
        for st, r in resp.items():
            for code in r.get("x-trustlens-error-codes", []):
                doc_codes[code] = int(st)
        if set(doc_codes) != set(c["errors"]):
            e("OA-15", f"{oid}: error codes {sorted(doc_codes)} != catalog {sorted(c['errors'])}")
        for code, st in doc_codes.items():
            if errtab.get(code) != st:
                e("OA-15", f"{oid}: {code} documented under {st} but the catalog maps it to {errtab.get(code)}")
        cc = op.get("x-trustlens-caller-constraints", [])
        if cc != c.get("caller_constraints", []):
            e("OA-26", f"{oid}: caller constraints {cc} != catalog {c.get('caller_constraints', [])}")
        if op.get("x-trustlens-grants-case-access") and "ASSIGNEE_NOT_CALLER" not in cc:
            e("OA-26", f"{oid}: access-granting operation must forbid self-assignment")
        if op.get("x-trustlens-resource-authorization") == "BREAK_GLASS_REVIEWER" and "REVIEWER_NOT_GRANTEE" not in cc:
            e("OA-26", f"{oid}: break-glass review must be by a different principal")
        # C4 sensitivity
        if c["response_schema"] in comps and closure(c["response_schema"]) & content_fields \
                and op.get("x-trustlens-sensitivity") not in ("C3", "C4"):
            e("OA-27", f"{oid}: returns C4 content but is classified {op.get('x-trustlens-sensitivity')}")
        # replay
        rsem = op.get("x-trustlens-replay-semantics")
        if c.get("replay_semantics") is not None:
            if rsem != c["replay_semantics"] or rsem.get("ai_recall") or rsem.get("knowledge_selection") != "PINNED_ONLY" \
                    or rsem.get("material_substitution") != "FORBIDDEN" or rsem.get("creates_new_evaluation"):
                e("OA-28", f"{oid}: replay must be pinned-only, no AI recall, no substitution, no new evaluation")
            body = deref(doc, (op.get("requestBody") or {}).get("content", {}).get("application/json", {}).get("schema", {}))
            if set(body.get("properties", {})) - {"reason_code"} or body.get("additionalProperties") is not False:
                e("OA-28", f"{oid}: replay request may carry only reason_code and must reject unknown fields")
        # pagination
        if c.get("list"):
            names = [p.get("name") for p in prms if p.get("in") == "query"]
            if "cursor" not in names or "limit" not in names:
                e("OA-30", f"{oid}: list operations need cursor + limit")
            for p in prms:
                if p.get("name") == "limit":
                    sch = p.get("schema", {})
                    if "maximum" in sch or "default" in sch:
                        e("OA-30", f"{oid}: limit default/maximum must not be invented")
            extra = set(names) - {"cursor", "limit"} - set(c["list"]["filters"])
            missing = set(c["list"]["filters"]) - set(names)
            if extra or missing:
                e("OA-30", f"{oid}: filters differ from the catalog allow-list (extra {sorted(extra)}, missing {sorted(missing)})")
        # binary
        for loc in (op.get("requestBody") or {}, sr):
            for mt, media in (loc.get("content") or {}).items():
                walk(media, lambda n, w: e("OA-33", f"{oid}: base64 content encoding") if isinstance(n, dict) and n.get("contentEncoding") == "base64" else None)
        if c["response_schema"] in ("EvidenceContentDownload", "ReportContentDownload") and "application/json" in sr.get("content", {}):
            e("OA-33", f"{oid}: binary content must not be wrapped in JSON")
        # ETag
        if c["target_resource"] in ("Case", "ReviewItem", "DeletionRequest") and "ETag" not in sr.get("headers", {}):
            e("OA-34", f"{oid}: mutable shared resource response must carry ETag")
        # health
        if c["internal"]:
            hs = comps.get(c["response_schema"], {})
            if set(hs.get("properties", {})) - {"status"}:
                e("OA-32", f"{oid}: internal probe may expose only status")

    # ---- component schema parity (OA-16) + mass assignment (OA-29) + timestamps (OA-31)
    cschemas = cat["schemas"]
    vocab, pv = cat["vocabularies"], persistence["vocabularies"]

    def vvals(n):
        v = vocab[n]
        return pv[v["persistence_vocabulary"]]["values"] if v["source"] == "PERSISTENCE" else v["values"]

    for name, sd in cschemas.items():
        if sd["body"] != "JSON":
            continue
        s = comps.get(name)
        if s is None:
            e("OA-16", f"catalog schema {name} missing from components")
            continue
        props = s.get("properties", {})
        if set(props) != {f["name"] for f in sd["fields"]}:
            e("OA-16", f"{name}: properties {sorted(props)} != catalog {sorted(f['name'] for f in sd['fields'])}")
        if sorted(s.get("required", [])) != sorted(f["name"] for f in sd["fields"] if f["required"]):
            e("OA-16", f"{name}: required list differs from the catalog")
        if sd["kind"] == "REQUEST":
            if s.get("additionalProperties") is not False:
                e("OA-29", f"{name}: request schema must reject unknown properties")
            for pn in props:
                if pn in SERVER_CONTROLLED:
                    e("OA-29", f"{name}.{pn}: server-controlled field accepted from client")
        for f in sd["fields"]:
            ps = props.get(f["name"])
            if ps is None:
                continue
            flat = json.dumps(ps)
            if f["type"] == "enum":
                target = deref(doc, {"$ref": f"#/components/schemas/Enum_{f['vocabulary']}"})
                if sorted(target.get("enum", [])) != sorted(vvals(f["vocabulary"])) or f"Enum_{f['vocabulary']}" not in flat:
                    e("OA-16", f"{name}.{f['name']}: enum does not equal vocabulary {f['vocabulary']}")
            if f["type"] == "timestamp" and '"date-time"' not in flat:
                e("OA-31", f"{name}.{f['name']}: timestamps must be date-time strings")
            if f.get("trace") != (ps.get("x-trustlens-trace") if isinstance(ps, dict) else None):
                e("OA-21", f"{name}.{f['name']}: trace differs from the catalog (AC-24)")
            if f.get("visibility") != (ps.get("x-trustlens-visibility") if isinstance(ps, dict) else None):
                e("OA-27", f"{name}.{f['name']}: visibility differs from the catalog")
    for n, s in comps.items():
        if n not in cschemas and not n.startswith("Enum_"):
            e("OA-16", f"component schema {n} is not in the catalog")

    # ---- result tree traces (OA-21) and invented fields (OA-19) and tenancy (OA-18)
    for n in closure(GOVERNED_RESULT_ROOT):
        for pn, ps in (comps[n].get("properties") or {}).items():
            tr = ps.get("x-trustlens-trace") if isinstance(ps, dict) else None
            if not tr:
                e("OA-21", f"{n}.{pn}: governed result field without trace")
            elif tr.endswith(RESERVED_TRACE):
                e("OA-21", f"{n}.{pn}: traces to the reserved, never-emitted Phase-3 priority")

    def names_check(n, w):
        if isinstance(n, dict):
            for key in list(n.get("properties", {}).keys()):
                if TENANT.search(key):
                    e("OA-18", f"tenant property {key} at {w}")
                if INVENTED.search(key):
                    e("OA-19", f"API-invented decision field {key} at {w}")
                if key.endswith("_url"):
                    e("OA-24", f"URL property {key} at {w} could become a fetch target")
            if n.get("in") in ("query", "header", "path", "cookie") and TENANT.search(str(n.get("name", ""))):
                e("OA-18", f"tenant parameter {n.get('name')} at {w}")
    walk(doc, names_check)
    for hn in doc["components"].get("headers", {}):
        if TENANT.search(hn):
            e("OA-18", f"tenant header {hn}")
    for sn, s in comps.items():
        if s.get("x-trustlens-schema-kind") == "REQUEST":
            for pn in s.get("properties", {}):
                if pn in ("created_at", "completed_at", "adjudicated_at", "occurred_at", "recorded_at"):
                    e("OA-31", f"{sn}.{pn}: server timestamp is client-settable")

    # ---- C4 visibility (OA-27)
    for need in (("AdjudicationResponse", "rationale"), ("ExplanationView", "evidence_basis")):
        ps = comps.get(need[0], {}).get("properties", {}).get(need[1], {})
        if ps.get("x-trustlens-visibility") != "CONTENT_PERMISSION":
            e("OA-27", f"{need[0]}.{need[1]} must keep CONTENT_PERMISSION visibility")

    # ---- health topology (OA-32)
    oh = comps.get("OperationalHealthResponse", {})
    for pn in json.dumps(oh).lower().split('"'):
        if pn in ("hostname", "host", "address", "endpoint", "credential", "key_id", "region", "ip"):
            e("OA-32", f"OperationalHealthResponse exposes topology field {pn}")

    # ---- ETag strategy (OA-34)
    es = doc.get("x-trustlens-etag-strategy", {})
    if es.get("decision") != "B_SERVER_REVISION_REQUIRED" or "monotonic revision" not in es.get("rule", "") \
            or "DATA-001-WP2" not in es.get("implementation_dependency", ""):
        e("OA-34", "ETag strategy must record the server-revision decision and the WP2 implementation dependency")

    # ---- tenancy contract
    if doc.get("x-trustlens-tenancy", {}).get("tenant_fields_permitted") is not False:
        e("OA-18", "tenant fields must not be permitted while ASM-002 is unconfirmed")
    return errs


# ================================================================ negative mutations


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
    doc, cat, persistence = load(OPENAPI_PATH), load(CATALOG_PATH), load(PERSISTENCE_PATH)
    errs = check(doc, cat, persistence)
    if errs:
        for code, msg in errs:
            print(f"  FAIL  {code}  {msg}")
        print(f"OPENAPI CONTRACT: FAIL — {len(errs)} violation(s) in {OPENAPI_PATH.relative_to(ROOT)}")
        return 1
    negatives = load(NEGATIVE_PATH)["mutations"]
    failures = []
    for m in negatives:
        try:
            mutated = apply_mutation(doc, m)
        except (KeyError, IndexError, ValueError, TypeError) as ex:
            failures.append(f"{m['id']}: mutation could not be applied ({ex})")
            continue
        found = {code for code, _ in check(mutated, cat, persistence)}
        if m["expect"] not in found:
            failures.append(f"{m['id']}: expected {m['expect']}, got {sorted(found) or 'no violation'}")
        elif not quiet:
            print(f"  ok    {m['id']} rejected by {m['expect']}: {m['description']}")
    if failures:
        for f in failures:
            print(f"  FAIL  negative fixture {f}")
        print("OPENAPI CONTRACT: FAIL — a guard did not bite")
        return 1
    n_ops = sum(1 for _ in iter_ops(doc))
    print(f"OPENAPI CONTRACT: PASS — OpenAPI {doc['openapi']}, {n_ops} operations in parity with the catalog, "
          f"{len(doc['components']['schemas'])} component schemas; {len(negatives)} negative mutations rejected "
          f"(deterministic structural validation; no official OpenAPI conformance validator is pinned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
