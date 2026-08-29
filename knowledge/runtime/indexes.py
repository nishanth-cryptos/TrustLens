"""TrustLens Phase 3 P3-WP2 — deterministic runtime index construction + structural validation.

Pure functions over already-parsed, already-integrity-verified bundle components. Builds ONLY the
indexes justified by a demonstrated runtime-evaluation need (STEP 1 assessment); it invents no
speculative index (`rules_by_channel` is intentionally absent — rules carry no channel attribute).
It contains NO detection logic: it does not evaluate a rule, compute a severity, or make any decision.
Every reverse-index value is a SORTED tuple so iteration order can never leak into a downstream
decision (STEP 11).

Governed contracts enforced here (WP2 remediation):
  * `rules_by_indicator` maps a POSITIVE trigger indicator → the COMPOSITE rules it can activate. A
    negative operand of a SUPPRESSION rule's `require` is NOT admitted to this positive index
    (validate_rules L2 polarity discipline).
  * `negative_indicators_by_rule` admits only ACTIVE negatives (a DEPRECATED negative is not live
    knowledge — the analogue of the PUBLISHED-only rule boundary).
  * Structural shape + duplicate-id checks run BEFORE indexing so a malformed/ambiguous component
    fails closed with a typed error rather than silently overwriting a record or leaking a KeyError.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Iterator

from .dimensions import dimension_map_problems, terms_by_axis
from .errors import DuplicateIdError, MemberSchemaError

PUBLISHED = "PUBLISHED"
ACTIVE = "ACTIVE"

# Canonical index names (also the keys RuntimeKnowledge exposes via `.index(name)`).
INDEX_NAMES = (
    "rules_by_id",
    "published_rules_by_id",
    "indicators_by_id",
    "negative_indicators_by_id",
    "indicator_families_by_id",
    "positive_indicators_by_family",
    "taxonomy_by_id",
    "dimensions_by_id",
    "sources_by_id",
    "evidence_by_id",
    "overrides_by_id",
    "rules_by_indicator",
    "rules_by_category",
    "negative_indicators_by_rule",
    "overrides_by_indicator",
    "overrides_by_target",
)

_CATEGORY_RE = re.compile(r"^(TAX-\d{2})")


def operands(condition: Any) -> Iterator[str]:
    """Yield every indicator id referenced anywhere in a require/condition tree.

    Mirrors the walk in validate_rules.py so runtime and authoring agree on what a rule references.
    Handles the governed shapes: a bare string, {all_of:[...]}, {any_of:[...]}, {n_of:{n,of:[...]}}.
    """
    if isinstance(condition, str):
        yield condition
        return
    if not isinstance(condition, dict):
        return
    for op, val in condition.items():
        if op == "n_of":
            of = val.get("of", []) if isinstance(val, dict) else []
            for item in of:
                yield from operands(item)
        elif isinstance(val, list):
            for item in val:
                yield from operands(item)


def category_of(taxonomy_ref: str) -> str | None:
    """Governed category (TAX-NN) that a taxonomy_ref belongs to. 'TAX-01-03' -> 'TAX-01'."""
    m = _CATEGORY_RE.match(taxonomy_ref)
    return m.group(1) if m else None


def rule_categories(rule: dict) -> set[str]:
    """Distinct taxonomy categories a rule sits under, derived from its taxonomy_refs."""
    out = set()
    for t in rule.get("taxonomy_refs", []):
        cat = category_of(t)
        if cat:
            out.add(cat)
    return out


def _sorted_tuple(ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(ids)))


# --------------------------------------------------------------- shape + duplicate id checks

def _need_list(container: Any, key: str, kind: str, *, required: bool = False, of_str: bool = False) -> list:
    """A present `key` must be a list (never null / wrong type); absent → [] unless required."""
    if not isinstance(container, dict) or key not in container:
        if required:
            raise MemberSchemaError(f"{kind}: missing {key!r}", code="MEMBER_SHAPE_INVALID")
        return []
    v = container[key]
    if not isinstance(v, list):
        raise MemberSchemaError(f"{kind}: {key!r} must be a list (got {type(v).__name__})", code="MEMBER_SHAPE_INVALID")
    if of_str and not all(isinstance(x, str) for x in v):
        raise MemberSchemaError(f"{kind}: {key!r} must be a list of strings", code="MEMBER_SHAPE_INVALID")
    return v


def _need_dict(container: Any, key: str, kind: str, *, required: bool = False) -> dict:
    """A present `key` must be an object (never null / wrong type); absent → {} unless required."""
    if not isinstance(container, dict) or key not in container:
        if required:
            raise MemberSchemaError(f"{kind}: missing {key!r}", code="MEMBER_SHAPE_INVALID")
        return {}
    v = container[key]
    if not isinstance(v, dict):
        raise MemberSchemaError(f"{kind}: {key!r} must be an object (got {type(v).__name__})", code="MEMBER_SHAPE_INVALID")
    return v


def _need_dim_map(container: Any, key: str, kind: str) -> dict:
    """A dimensions-reference map: {group: [term_id, ...]} — each value a list of strings."""
    m = _need_dict(container, key, kind)
    for group, terms in m.items():
        if not isinstance(terms, list) or not all(isinstance(t, str) for t in terms):
            raise MemberSchemaError(f"{kind}: dimensions group {group!r} must map to a list of term ids",
                                    code="MEMBER_SHAPE_INVALID")
    return m


def _keyed_map(items: list, id_key: str, kind: str) -> dict:
    """Return {id: record} from a list, raising MemberSchemaError on a malformed item and
    DuplicateIdError on a repeated id (never silently overwrites)."""
    if not isinstance(items, list):
        raise MemberSchemaError(f"{kind}: expected a list", code="MEMBER_SHAPE_INVALID")
    out: dict[str, Any] = {}
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get(id_key), str) or not it.get(id_key):
            raise MemberSchemaError(f"{kind}: item missing string {id_key!r}", code="MEMBER_SHAPE_INVALID")
        iid = it[id_key]
        if iid in out:
            raise DuplicateIdError(f"{kind}: duplicate id {iid!r}", code="DUPLICATE_ID")
        out[iid] = it
    return out


def check_shapes_and_duplicates(components: dict) -> None:
    """Validate the structural shape of EVERY runtime-consumed nested structure BEFORE any traversal,
    and enforce id uniqueness, so a malformed/ambiguous bundle fails closed with a typed error rather
    than leaking a raw KeyError/TypeError/AttributeError (WP2 remediation finding 1) and never silently
    overwrites a record (finding 4). Raises MemberSchemaError (`MEMBER_SHAPE_INVALID`) or DuplicateIdError.

    Global stable-id uniqueness matches validate_kb.py / KB-001: taxonomy nodes, dimension terms,
    positive indicators, negative indicators and rules occupy ONE namespace and may not collide
    (a positive id equal to a negative id is rejected — rules reference both through a shared string).
    Sources (`SRC-*`), evidence (`MR-EVID-*`), families (`FAM-*`) and overrides (`HR_*`) are governed as
    separate prefixed namespaces (KB-001) and get per-collection duplicate checks."""
    rules = components["rules"]
    _keyed_map(rules, "id", "rules")
    for r in rules:  # defensive nested shape for the rule fields the loader traverses post-schema
        rid = r.get("id", "<rule>")
        logic = _need_dict(r, "logic", f"rule {rid}", required=True)
        _need_list(logic, "suppressed_by", f"rule {rid}.logic", of_str=True)
        _need_list(r, "taxonomy_refs", f"rule {rid}", of_str=True)
        ev = _need_dict(r, "evidence", f"rule {rid}", required=True)
        for ref in _need_list(ev, "source_references", f"rule {rid}.evidence"):
            if not isinstance(ref, dict):
                raise MemberSchemaError(f"rule {rid}: source_reference must be an object", code="MEMBER_SHAPE_INVALID")
            _need_list(_need_dict(ref, "manual_retrieval", f"rule {rid} source_reference"),
                       "evidence_ids", f"rule {rid} manual_retrieval", of_str=True)

    registry = _keyed_map(_need_list(components["registry"], "indicators", "indicator-registry", required=True),
                          "id", "indicators")

    fam_list = _need_list(components["families"], "families", "indicator-families", required=True)
    _keyed_map(fam_list, "family_id", "families")
    for f in fam_list:
        fid = f.get("family_id", "<family>")
        _need_list(f, "indicator_outputs", f"family {fid}", of_str=True)
        _need_list(f, "negative_interactions", f"family {fid}", of_str=True)
        _need_list(f, "hard_risk_overrides", f"family {fid}", of_str=True)
        _need_dim_map(f, "applicable_dimensions", f"family {fid}")

    neg_list = _need_list(components["negatives"], "negative_indicators", "negative-library", required=True)
    _keyed_map(neg_list, "negative_indicator_id", "negative_indicators")
    for n in neg_list:
        nid = n.get("negative_indicator_id", "<negative>")
        _need_list(n, "applicable_rule_families", f"negative {nid}", of_str=True)
        _need_list(n, "source_basis", f"negative {nid}", of_str=True)
        _need_list(n, "suppresses_indicators", f"negative {nid}", of_str=True)
    _need_dict(components["negatives"], "categories", "negative-library", required=True)  # suppression vocab
    ov_list = _need_list(components["negatives"], "overrides", "negative-library")
    _keyed_map(ov_list, "override_id", "overrides")
    for o in ov_list:
        oid = o.get("override_id", "<override>")
        if "condition" not in o:
            raise MemberSchemaError(f"override {oid}: missing 'condition'", code="MEMBER_SHAPE_INVALID")
        _need_list(o, "applies_to_families", f"override {oid}", of_str=True)
        _need_list(o, "applies_to_rules", f"override {oid}", of_str=True)
        _need_list(o, "blocks_suppression_categories", f"override {oid}", of_str=True)

    cats = _need_list(components["taxonomy"], "categories", "taxonomy", required=True)
    for c in cats:
        if not isinstance(c, dict) or not isinstance(c.get("id"), str):
            raise MemberSchemaError("taxonomy: category missing string 'id'", code="MEMBER_SHAPE_INVALID")
        for s in _need_list(c, "subcategories", f"taxonomy {c['id']}"):
            if not isinstance(s, dict) or not isinstance(s.get("id"), str):
                raise MemberSchemaError(f"taxonomy {c['id']}: subcategory missing string 'id'", code="MEMBER_SHAPE_INVALID")
            _need_dim_map(s, "dimensions", f"taxonomy {s['id']}")

    groups = _need_dict(components["dimensions"], "dimensions", "dimensions", required=True)
    for gname, body in groups.items():
        for term in _need_list(body if isinstance(body, dict) else {}, "terms", f"dimensions {gname}", required=True):
            if not isinstance(term, dict) or not isinstance(term.get("id"), str):
                raise MemberSchemaError(f"dimensions {gname}: term missing string 'id'", code="MEMBER_SHAPE_INVALID")

    _keyed_map(_need_list(components["sources"], "sources", "verification-manifest", required=True), "id", "sources")
    for s in components["sources"]["sources"]:
        _need_list(_need_dict(s, "manual_retrieval", f"source {s['id']}"),
                   "evidence_ids", f"source {s['id']} manual_retrieval", of_str=True)
    _keyed_map(_need_list(components["evidence"], "records", "evidence-records", required=True), "evidence_id", "evidence")

    # ---- global stable-id uniqueness across the KB-001 shared namespace ----
    seen: dict[str, str] = {}

    def claim(idv: str, ns: str) -> None:
        if idv in seen:
            raise DuplicateIdError(f"stable-id collision: {idv!r} used as {seen[idv]} and {ns}", code="DUPLICATE_ID")
        seen[idv] = ns

    for c in cats:
        claim(c["id"], "taxonomy")
        for s in c.get("subcategories", []):
            claim(s["id"], "taxonomy")
    for body in groups.values():
        for term in body.get("terms", []):
            claim(term["id"], "dimension")
    for i in registry.values():
        claim(i["id"], "indicator")
    for n in neg_list:
        claim(n["negative_indicator_id"], "negative-indicator")
    for r in rules:
        claim(r["id"], "rule")


# --------------------------------------------------------------- index construction

def build_indexes(components: dict) -> dict:
    """Construct every runtime index from parsed components. Assumes check_shapes_and_duplicates has
    passed. Returns raw (unfrozen) structures; RuntimeKnowledge deep-freezes them."""
    rules_all = components["rules"]
    registry = components["registry"]
    families = components["families"]
    negatives = components["negatives"]
    taxonomy = components["taxonomy"]
    dimensions = components["dimensions"]
    sources = components["sources"]
    evidence = components["evidence"]

    published = [r for r in rules_all if r.get("lifecycle", {}).get("status") == PUBLISHED]
    positive_ids = {i["id"] for i in registry["indicators"]}

    rules_by_id = {r["id"]: r for r in rules_all}
    published_rules_by_id = {r["id"]: r for r in published}

    indicators_by_id = {i["id"]: i for i in registry["indicators"]}
    negative_indicators_by_id = {n["negative_indicator_id"]: n for n in negatives["negative_indicators"]}
    indicator_families_by_id = {f["family_id"]: f for f in families["families"]}
    positive_indicators_by_family = {
        f["family_id"]: _sorted_tuple(f.get("indicator_outputs", [])) for f in families["families"]
    }

    taxonomy_by_id: dict[str, dict] = {}
    for cat in taxonomy["categories"]:
        taxonomy_by_id[cat["id"]] = cat
        for sub in cat.get("subcategories", []):
            taxonomy_by_id[sub["id"]] = sub

    dimensions_by_id: dict[str, dict] = {}
    for group in dimensions["dimensions"].values():
        for term in group.get("terms", []):
            dimensions_by_id[term["id"]] = term

    sources_by_id = {s["id"]: s for s in sources["sources"]}
    evidence_by_id = {r["evidence_id"]: r for r in evidence["records"]}
    overrides = negatives.get("overrides", [])
    overrides_by_id = {o["override_id"]: o for o in overrides}

    active_negatives = [n for n in negatives["negative_indicators"] if n.get("status") == ACTIVE]

    # ---- execution-oriented reverse indexes (PUBLISHED rules only) ----
    rules_by_indicator: dict[str, list[str]] = {}
    rules_by_category: dict[str, list[str]] = {}
    negative_indicators_by_rule: dict[str, tuple[str, ...]] = {}
    for r in published:
        rid = r["id"]
        # POSITIVE trigger operands only — a SUPPRESSION rule's negative operands never pollute this
        # positive-indicator index (validate_rules L2 polarity discipline).
        for ind in set(operands(r.get("logic", {}).get("require"))):
            if ind in positive_ids:
                rules_by_indicator.setdefault(ind, []).append(rid)
        for cat in rule_categories(r):
            rules_by_category.setdefault(cat, []).append(rid)
        cats = rule_categories(r)
        applicable = [
            n["negative_indicator_id"]
            for n in active_negatives
            if "*" in n.get("applicable_rule_families", [])
            or (set(n.get("applicable_rule_families", [])) & cats)
        ]
        negative_indicators_by_rule[rid] = _sorted_tuple(applicable)

    rules_by_indicator = {k: _sorted_tuple(v) for k, v in rules_by_indicator.items()}
    rules_by_category = {k: _sorted_tuple(v) for k, v in rules_by_category.items()}

    # ---- override reverse indexes (governed knowledge, status-independent) ----
    overrides_by_indicator: dict[str, list[str]] = {}
    overrides_by_target: dict[str, list[str]] = {}
    for o in overrides:
        oid = o["override_id"]
        for ind in set(operands(o.get("condition"))):
            overrides_by_indicator.setdefault(ind, []).append(oid)
        for target in list(o.get("applies_to_families", [])) + list(o.get("applies_to_rules", [])):
            overrides_by_target.setdefault(target, []).append(oid)
    overrides_by_indicator = {k: _sorted_tuple(v) for k, v in overrides_by_indicator.items()}
    overrides_by_target = {k: _sorted_tuple(v) for k, v in overrides_by_target.items()}

    return {
        "rules_by_id": rules_by_id,
        "published_rules_by_id": published_rules_by_id,
        "indicators_by_id": indicators_by_id,
        "negative_indicators_by_id": negative_indicators_by_id,
        "indicator_families_by_id": indicator_families_by_id,
        "positive_indicators_by_family": positive_indicators_by_family,
        "taxonomy_by_id": taxonomy_by_id,
        "dimensions_by_id": dimensions_by_id,
        "sources_by_id": sources_by_id,
        "evidence_by_id": evidence_by_id,
        "overrides_by_id": overrides_by_id,
        "rules_by_indicator": rules_by_indicator,
        "rules_by_category": rules_by_category,
        "negative_indicators_by_rule": negative_indicators_by_rule,
        "overrides_by_indicator": overrides_by_indicator,
        "overrides_by_target": overrides_by_target,
    }


def validate_references(components: dict) -> list[str]:
    """Return a sorted list of unresolved-reference problems (empty == clean).

    Trust boundary (WP2 remediation / requirement E): rule-originated references are checked on ALL
    shipped rules — not only PUBLISHED ones — because authoring (`validate_rules.py`) validates every
    rule regardless of lifecycle status, so a bundle may never legitimately ship a rule with a dangling
    reference; the loader mirrors that boundary as fail-closed defence-in-depth (PUBLISHED remains a
    separate executability filter). Component-internal references (family/negative/override/evidence)
    are checked globally.
    """
    rules_all = components["rules"]
    registry = components["registry"]
    families = components["families"]
    negatives = components["negatives"]
    taxonomy = components["taxonomy"]
    dimensions = components["dimensions"]
    sources = components["sources"]
    evidence = components["evidence"]

    positive_ids = {i["id"] for i in registry["indicators"]}
    negative_ids = {n["negative_indicator_id"] for n in negatives["negative_indicators"]}
    active_negative_ids = {n["negative_indicator_id"] for n in negatives["negative_indicators"] if n.get("status") == ACTIVE}
    indicator_ns = positive_ids | negative_ids  # rules may reference either polarity
    tax_categories = {c["id"] for c in taxonomy["categories"]}
    tax_all = set(tax_categories)
    for c in taxonomy["categories"]:
        for s in c.get("subcategories", []):
            tax_all.add(s["id"])
    dimension_terms = {t["id"] for g in dimensions["dimensions"].values() for t in g.get("terms", [])}
    axis_terms = terms_by_axis(dimensions)  # {axis: {term_id}} for axis-scoped taxonomy dimension checks
    source_ids = {s["id"] for s in sources["sources"]}
    evidence_by = {r["evidence_id"]: r for r in evidence["records"]}
    evidence_ids = set(evidence_by)
    override_ids = {o["override_id"] for o in negatives.get("overrides", [])}
    suppression_categories = set(negatives.get("categories", {}))
    all_rule_ids = {r["id"] for r in rules_all}

    problems: list[str] = []

    # rule -> indicator / taxonomy / source / manual-retrieval evidence (ALL shipped rules), plus the
    # governed POLARITY, DEPRECATED-suppressor and evidence-OWNERSHIP contracts (validate_rules L1b/L2/L10).
    for r in rules_all:
        rid = r.get("id", "<no id>")
        kind = r.get("kind")
        status = r.get("lifecycle", {}).get("status")
        logic = r.get("logic", {})
        trigger = set(operands(logic.get("require")))
        suppressors = set(logic.get("suppressed_by", []))
        for ind in sorted(trigger | suppressors):
            if ind not in indicator_ns:
                problems.append(f"rule {rid}: unresolved indicator {ind!r}")
        for op in sorted(trigger):
            if kind == "COMPOSITE" and op in negative_ids and op not in positive_ids:
                problems.append(f"rule {rid}: COMPOSITE trigger {op!r} is a NEGATIVE indicator (polarity)")
            if kind == "SUPPRESSION" and op in positive_ids and op not in negative_ids:
                problems.append(f"rule {rid}: SUPPRESSION trigger {op!r} is a POSITIVE indicator (polarity)")
        for sup in sorted(suppressors):
            if status == "PUBLISHED" and sup in negative_ids and sup not in active_negative_ids:
                problems.append(f"rule {rid}: PUBLISHED rule suppressed_by DEPRECATED negative {sup!r}")
        for t in r.get("taxonomy_refs", []):
            if t not in tax_all:
                problems.append(f"rule {rid}: unresolved taxonomy_ref {t!r}")
        for ref in r.get("evidence", {}).get("source_references", []):
            sid = ref.get("source_id")
            if sid not in source_ids:
                problems.append(f"rule {rid}: unresolved source_id {sid!r}")
            for eid in (ref.get("manual_retrieval") or {}).get("evidence_ids", []):
                if eid not in evidence_ids:
                    problems.append(f"rule {rid}: unresolved manual_retrieval evidence id {eid!r}")
                elif evidence_by[eid].get("manifest_source_id") != sid:
                    problems.append(f"rule {rid}: manual evidence {eid!r} is owned by "
                                    f"{evidence_by[eid].get('manifest_source_id')!r}, not cited source {sid!r}")

    # family -> indicator outputs / negative_interactions / hard_risk_overrides / dimension terms.
    # NOTE: family applicable_dimensions is validated against the GLOBAL term set, mirroring the
    # governing authoring validator validate_extraction.py (which checks family dims against a flattened
    # dim_ids). Only the taxonomy subcategory dimension map is axis-scoped (validate_taxonomy.py); we do
    # not tighten family dims beyond the governed contract (WP2 remediation round-3, finding step 6).
    for f in families["families"]:
        fid = f["family_id"]
        for out in f.get("indicator_outputs", []):
            if out not in positive_ids:
                problems.append(f"family {fid}: unresolved indicator_output {out!r}")
        for neg in f.get("negative_interactions", []):
            if neg not in negative_ids:
                problems.append(f"family {fid}: unresolved negative_interaction {neg!r}")
        for ovr in f.get("hard_risk_overrides", []):
            if ovr not in override_ids:
                problems.append(f"family {fid}: unresolved hard_risk_override {ovr!r}")
        for _grp, terms in (f.get("applicable_dimensions") or {}).items():
            for term in terms:
                if term not in dimension_terms:
                    problems.append(f"family {fid}: unresolved dimension term {term!r}")

    # taxonomy subcategory -> dimension terms, AXIS-SCOPED (finding: axis integrity). A term is legal
    # only under its own axis; an unknown axis key or a valid term under the wrong axis is rejected.
    # Uses the shared knowledge.runtime.dimensions helper — the same mapping validate_taxonomy.py uses.
    for c in taxonomy["categories"]:
        for s in c.get("subcategories", []):
            dim_map = s.get("dimensions") or {}
            problems.extend(dimension_map_problems(f"taxonomy {s['id']}", dim_map, axis_terms))

    # negative -> applicable_rule_families (CATEGORY scope) / source_basis / suppresses_indicators
    for n in negatives["negative_indicators"]:
        nid = n["negative_indicator_id"]
        for fam in n.get("applicable_rule_families", []):
            if fam != "*" and fam not in tax_categories:
                problems.append(f"negative {nid}: applicable_rule_family {fam!r} is not a TAX category")
        for sid in n.get("source_basis", []):
            if sid not in source_ids:
                problems.append(f"negative {nid}: unresolved source_basis {sid!r}")
        for tgt in n.get("suppresses_indicators", []):
            if tgt not in positive_ids:
                problems.append(f"negative {nid}: suppresses unknown positive indicator {tgt!r}")

    # override -> condition indicators / family (CATEGORY) / rule targets / blocked suppression categories
    for o in negatives.get("overrides", []):
        oid = o["override_id"]
        for ind in sorted(set(operands(o.get("condition")))):
            if ind not in positive_ids:
                problems.append(f"override {oid}: unresolved condition indicator {ind!r}")
        for fam in o.get("applies_to_families", []):
            if fam not in tax_categories:
                problems.append(f"override {oid}: applies_to_family {fam!r} is not a TAX category")
        for tgt in o.get("applies_to_rules", []):
            if tgt not in all_rule_ids:
                problems.append(f"override {oid}: unresolved applies_to_rule {tgt!r}")
        for cat in o.get("blocks_suppression_categories", []):
            if cat not in suppression_categories:
                problems.append(f"override {oid}: blocks unknown suppression category {cat!r}")

    # evidence <-> source
    for rec in evidence["records"]:
        msid = rec.get("manifest_source_id")
        if msid not in source_ids:
            problems.append(f"evidence {rec['evidence_id']}: unresolved manifest_source_id {msid!r}")
    for s in sources["sources"]:
        mr = s.get("manual_retrieval") or {}
        for eid in mr.get("evidence_ids", []):
            if eid not in evidence_ids:
                problems.append(f"source {s['id']}: unresolved manual_retrieval evidence id {eid!r}")

    return sorted(problems)
