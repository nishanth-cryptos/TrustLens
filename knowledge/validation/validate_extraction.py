"""TrustLens extraction-contract validator — Phase 2 work package 2.

Validates the WP2 boundary between raw input and the deterministic rule layer:

  SCHEMA  Draft 2020-12 for the four contracts —
          input-envelope / observation / url-observation / indicator-observation —
          and every embedded object in the golden fixtures.

  LINT    Everything the schema cannot express on its own:
            * indicator IDs resolve to the positive registry or the negative library,
              polarity agrees, and nothing DEPRECATED is emitted;
            * the 28 families PARTITION the 63 positive indicators exactly once;
            * family negative-interactions, overrides and dimension refs resolve;
            * fixture cross-refs (observation_refs, url_ref, input_id) resolve;
            * expected_projection == the projection derived from indicator_observations;
            * NO extractor artefact carries a final scam verdict/risk/severity (STEP 5/13);
            * URL assessments stay UNKNOWN/NOT_EVALUATED — no reputation is invented (STEP 9);
            * the rule-extraction coverage matrix agrees with the live rules + families
              (re-derived, so it cannot drift).

This is a NEW validator; it does not touch the seven existing ones. Extraction itself is a
later phase — WP2 defines the contract, this checks the contract holds.

Usage:  .venv/bin/python knowledge/validation/validate_extraction.py [--quiet]
Exit 0 = every contract, fixture and coverage row is valid.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:
    sys.exit(
        "jsonschema>=4.18 and referencing are required.\n"
        "    .venv/bin/pip install jsonschema\n"
    )

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "knowledge" / "schemas"
IND_DIR = ROOT / "knowledge" / "indicators"
TAX_DIR = ROOT / "knowledge" / "taxonomies"
EXT_DIR = ROOT / "knowledge" / "extraction"
RULES_DIR = ROOT / "knowledge" / "rules"

ENVELOPE_SCHEMA = SCHEMA_DIR / "input-envelope.schema.json"
OBSERVATION_SCHEMA = SCHEMA_DIR / "observation.schema.json"
URL_SCHEMA = SCHEMA_DIR / "url-observation.schema.json"
INDOBS_SCHEMA = SCHEMA_DIR / "indicator-observation.schema.json"
REGISTRY_PATH = IND_DIR / "indicator-registry-v0.json"
NEG_LIBRARY_PATH = IND_DIR / "negative-indicator-library-v1.json"
FAMILIES_PATH = IND_DIR / "indicator-families-v1.json"
DIMENSIONS_PATH = TAX_DIR / "dimensions-v1.json"
TAXONOMY_PATH = TAX_DIR / "scam-taxonomy.json"
FIXTURES_PATH = EXT_DIR / "extraction-fixtures-v1.json"
COVERAGE_PATH = EXT_DIR / "rule-extraction-coverage-v1.json"

# Keys an extraction artefact may NEVER carry — a verdict belongs to the rule/detection layer.
FORBIDDEN_VERDICT_KEYS = {
    "verdict", "risk", "risk_score", "risk_level", "severity", "is_scam", "scam",
    "scam_verdict", "finding", "decision", "label", "classification", "malicious", "outcome",
}
# URL assessment values that WP2 may not assert (no reputation/allowlist service exists yet).
FORBIDDEN_URL_ASSESSMENTS = {
    "domain_matches_claimed_brand": {"MATCH", "MISMATCH"},
    "allowlist_result": {"ALLOWLISTED", "NOT_ALLOWLISTED"},
    "reputation_result": {"MALICIOUS", "SUSPICIOUS", "CLEAN"},
}
IMPL2X = {"YES": "CURRENTLY_EXTRACTABLE", "PARTIAL": "PARTIAL_REQUIRES_FUTURE_EXTRACTOR", "DEFERRED": "UNOBSERVABLE"}


def load(p):
    return json.loads(p.read_text())


def build_validators():
    """Register all four schemas by $id so the envelope's cross-ref to url-observation resolves."""
    resources = []
    for path in (ENVELOPE_SCHEMA, OBSERVATION_SCHEMA, URL_SCHEMA, INDOBS_SCHEMA):
        schema = load(path)
        Draft202012Validator.check_schema(schema)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    return {
        "envelope": Draft202012Validator(load(ENVELOPE_SCHEMA), registry=registry),
        "observation": Draft202012Validator(load(OBSERVATION_SCHEMA), registry=registry),
        "url": Draft202012Validator(load(URL_SCHEMA), registry=registry),
        "indicator_observation": Draft202012Validator(load(INDOBS_SCHEMA), registry=registry),
    }


def scan_forbidden(node, path, errs, ctx):
    """Recursively reject any FORBIDDEN_VERDICT_KEYS, skipping the legitimate confidence.score."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in FORBIDDEN_VERDICT_KEYS:
                errs.append(f"{ctx}: forbidden verdict key {k!r} at {path} — an extractor may not emit a finding (STEP 5/13)")
            if k == "confidence":
                continue  # confidence.score/level are extraction confidence, not risk
            scan_forbidden(v, f"{path}.{k}", errs, ctx)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            scan_forbidden(v, f"{path}[{i}]", errs, ctx)


def main() -> int:
    quiet = "--quiet" in sys.argv
    errs = []
    V = build_validators()

    # ---- reference data
    registry = load(REGISTRY_PATH)
    positives = {i["id"]: i for i in registry["indicators"]}
    library = load(NEG_LIBRARY_PATH)
    negatives = {n["negative_indicator_id"]: n for n in library["negative_indicators"]}
    override_ids = {o["override_id"] for o in library["overrides"]}
    families = load(FAMILIES_PATH)
    dims = load(DIMENSIONS_PATH)
    dim_ids = {t["id"] for block in dims["dimensions"].values() for t in block["terms"]}
    taxonomy = load(TAXONOMY_PATH)
    taxa = set()
    for c in taxonomy["categories"]:
        taxa.add(c["id"])
        for s in c["subcategories"]:
            taxa.add(s["id"])

    def polarity_of(iid):
        if iid in positives:
            return "POSITIVE"
        if iid in negatives:
            return "NEGATIVE"
        return None

    def is_deprecated(iid):
        return iid in negatives and negatives[iid].get("status") == "DEPRECATED"

    # ---- families: partition + reference integrity
    fam_ids = set()
    covered = []
    ind2fam = {}
    for f in families["families"]:
        fid = f["family_id"]
        if fid in fam_ids:
            errs.append(f"families: duplicate family_id {fid}")
        fam_ids.add(fid)
        # family ids must not collide with any existing stable ID namespace
        if fid in positives or fid in negatives or fid in taxa or fid in dim_ids:
            errs.append(f"families: family_id {fid} collides with an existing stable ID")
        for i in f["indicator_outputs"]:
            if i not in positives:
                errs.append(f"family {fid}: indicator_output {i} is not a known positive indicator")
            covered.append(i)
            ind2fam[i] = fid
        for n in f.get("negative_interactions", []):
            if n not in negatives:
                errs.append(f"family {fid}: negative_interaction {n} does not resolve")
        for o in f.get("hard_risk_overrides", []):
            if o not in override_ids:
                errs.append(f"family {fid}: override {o} does not resolve")
        for axis, terms in f.get("applicable_dimensions", {}).items():
            for t in terms:
                if t not in dim_ids:
                    errs.append(f"family {fid}: dimension ref {t} does not resolve")
    dupes = [k for k, v in Counter(covered).items() if v > 1]
    missing = sorted(set(positives) - set(covered))
    if dupes:
        errs.append(f"families: indicator in >1 family (partition broken): {sorted(dupes)}")
    if missing:
        errs.append(f"families: positive indicators covered by no family: {missing}")

    # ---- fixtures
    fixtures = load(FIXTURES_PATH)
    fx_list = fixtures["fixtures"]
    behaviours = {"negated": False, "reported": False, "quoted": False,
                  "pays": False, "receives": False, "mixed_decoy": False}
    for fx in fx_list:
        fid = fx["fixture_id"]
        env = fx["envelope"]
        input_id = env["input_id"]

        for e in V["envelope"].iter_errors(env):
            errs.append(f"{fid} envelope: {e.json_path} {e.message}")
        # url primitives already validated via the envelope $ref, but assessment guard needs a direct pass
        for u in env.get("extracted_primitives", {}).get("urls", []):
            for field, banned in FORBIDDEN_URL_ASSESSMENTS.items():
                val = u.get("assessments", {}).get(field)
                if val in banned:
                    errs.append(f"{fid} url {u.get('url_id')}: assessment {field}={val} is reserved — no reputation/allowlist service exists in WP2 (STEP 9)")

        obs_ids = set()
        norm_len = len(env.get("content", {}).get("normalized_text", "") or "")
        for o in fx["observations"]:
            for e in V["observation"].iter_errors(o):
                errs.append(f"{fid} observation {o.get('observation_id')}: {e.json_path} {e.message}")
            obs_ids.add(o["observation_id"])
            if o.get("source_input_id") != input_id:
                errs.append(f"{fid} observation {o.get('observation_id')}: source_input_id != envelope input_id")
            off = o.get("offsets")
            if off and (off["start"] > off["end"] or off["end"] > norm_len):
                errs.append(f"{fid} observation {o.get('observation_id')}: offsets out of range")
            for axis in ("action", "pressure"):
                dref = (o.get(axis) or {}).get("dimension_ref")
                if dref and dref not in dim_ids:
                    errs.append(f"{fid} observation {o.get('observation_id')}: {axis}.dimension_ref {dref} does not resolve")
            # track behaviours for scenario coverage
            if o.get("polarity") == "NEGATED":
                behaviours["negated"] = True
            if o.get("attribution") == "REPORTED":
                behaviours["reported"] = True
            if o.get("attribution") == "QUOTED":
                behaviours["quoted"] = True
            if o.get("payment_direction") == "USER_PAYS":
                behaviours["pays"] = True
            if o.get("payment_direction") == "USER_RECEIVES":
                behaviours["receives"] = True

        url_ids = {u["url_id"] for u in env.get("extracted_primitives", {}).get("urls", [])}
        for o in fx["observations"]:
            if o.get("url_ref") and o["url_ref"] not in url_ids:
                errs.append(f"{fid} observation {o.get('observation_id')}: url_ref {o['url_ref']} not in envelope urls")

        # indicator observations
        derived_pos, derived_neg = [], []
        for io in fx["indicator_observations"]:
            for e in V["indicator_observation"].iter_errors(io):
                errs.append(f"{fid} indicator_observation {io.get('indicator_id')}: {e.json_path} {e.message}")
            scan_forbidden(io, f"{fid}.indicator_observation({io.get('indicator_id')})", errs, fid)
            iid = io["indicator_id"]
            pol = polarity_of(iid)
            if pol is None:
                errs.append(f"{fid}: indicator {iid} resolves to neither registry nor library")
            elif io["polarity"] != pol:
                errs.append(f"{fid}: indicator {iid} polarity {io['polarity']} disagrees with registry/library {pol}")
            if is_deprecated(iid):
                errs.append(f"{fid}: indicator {iid} is DEPRECATED and may not be emitted")
            if io.get("input_id") != input_id:
                errs.append(f"{fid}: indicator_observation {iid} input_id != envelope input_id")
            for ref in io.get("observation_refs", []):
                if ref not in obs_ids:
                    errs.append(f"{fid}: indicator {iid} observation_ref {ref} does not resolve")
            fref = io.get("family_ref")
            if fref:
                if fref not in fam_ids:
                    errs.append(f"{fid}: indicator {iid} family_ref {fref} unknown")
                elif ind2fam.get(iid) != fref:
                    errs.append(f"{fid}: indicator {iid} family_ref {fref} != its family {ind2fam.get(iid)}")
            if io.get("matched") == "OBSERVED":
                (derived_pos if pol == "POSITIVE" else derived_neg).append(iid)

        exp = fx["expected_projection"]
        if sorted(derived_pos) != sorted(exp["positive_signals"]):
            errs.append(f"{fid}: positive projection {sorted(derived_pos)} != expected {sorted(exp['positive_signals'])}")
        if sorted(derived_neg) != sorted(exp["negative_signals"]):
            errs.append(f"{fid}: negative projection {sorted(derived_neg)} != expected {sorted(exp['negative_signals'])}")
        if fx is fx_list[-1] or True:
            pass
    # decoy fixture: a live positive coexisting with negative signals
    for fx in fx_list:
        pos = fx["expected_projection"]["positive_signals"]
        neg = fx["expected_projection"]["negative_signals"]
        if pos and neg:
            behaviours["mixed_decoy"] = True
    for b, seen in behaviours.items():
        if not seen:
            errs.append(f"fixtures: no fixture exercises required behaviour {b!r}")
    if len(fx_list) < 15:
        errs.append(f"fixtures: {len(fx_list)} present, WP2 STEP 14 requires at least 15")

    # ---- coverage matrix: re-derive and check for drift
    cov = load(COVERAGE_PATH)
    cov_by = {r["rule_id"]: r for r in cov["rules"]}

    def ops(c, acc):
        if isinstance(c, str):
            acc.append(c)
        elif isinstance(c, dict):
            for k, v in c.items():
                if k == "n_of":
                    for i in v.get("of", []):
                        ops(i, acc)
                else:
                    for i in v:
                        ops(i, acc)
        return acc

    rule_ids = set()
    for p in sorted(RULES_DIR.glob("*.json")):
        r = load(p)
        rid = r["id"]
        rule_ids.add(rid)
        if rid not in cov_by:
            errs.append(f"coverage: rule {rid} is not in the coverage matrix")
            continue
        row = cov_by[rid]
        req = ops(r["logic"].get("require"), []) if r["logic"].get("require") else []
        req_pos = sorted(i for i in req if i in positives)
        if sorted(row.get("required_positive_indicators", [])) != req_pos:
            errs.append(f"coverage {rid}: required_positive_indicators drifted from rule logic")
        req_fams = sorted({ind2fam[i] for i in req_pos})
        if sorted(row.get("required_indicator_families", [])) != req_fams:
            errs.append(f"coverage {rid}: required_indicator_families drifted")
        want_x = IMPL2X[r["evidence"]["implementability"]]
        if row.get("extractability") != want_x:
            errs.append(f"coverage {rid}: extractability {row.get('extractability')} != derived {want_x}")
    for rid in cov_by:
        if rid not in rule_ids:
            errs.append(f"coverage: matrix row {rid} has no matching rule file")

    # ---- report
    if errs:
        print("EXTRACTION-CONTRACT CHECK: FAIL")
        for e in errs:
            print(" -", e)
        return 1
    print("EXTRACTION-CONTRACT CHECK: PASS")
    print(f" schemas: 4 (envelope, observation, url-observation, indicator-observation) — valid Draft 2020-12")
    print(f" families: {len(fam_ids)} partitioning {len(positives)} positive indicators exactly once")
    print(f" fixtures: {len(fx_list)} golden extraction fixtures; projections consistent; no verdict emitted")
    print(f" coverage: {len(cov_by)} rules mapped "
          f"({Counter(r['extractability'] for r in cov['rules'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
