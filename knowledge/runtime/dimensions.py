"""Canonical dimension-map KEY -> governed dimension AXIS mapping (single source of truth).

Shared by the authoring taxonomy validator (`knowledge/validation/validate_taxonomy.py`) and the P3-WP2
runtime loader so axis-integrity validation cannot silently diverge again. Pure: stdlib only, no I/O,
no intra-package imports, so either side can import it cheaply.

A dimension MAP — as it appears in a taxonomy subcategory's `dimensions` — uses keys that DIFFER from the
dimension-registry AXIS/group names in dimensions-v1.json (e.g. the map key `typical_channels` refers to
the axis `channel`; `social_engineering_tactics` -> `social_engineering_tactic`;
`requested_user_actions` -> `requested_user_action`). A dimension term is legal ONLY under its own axis:
`technical_mechanism: ["FO-01"]` must be rejected even though `FO-01` exists in the `fraud_objective`
axis, and an unknown axis key must be rejected even if its term exists elsewhere. Validating against a
flattened global term set would wrongly accept both, so membership is axis-scoped.

Authority: the `KEY_TO_AXIS` mapping in validate_taxonomy.py (WP5). This module is that mapping, promoted
to a shared location; validate_taxonomy.py now imports it rather than keeping a private copy.
"""

from __future__ import annotations

# taxonomy dimension-map key -> dimensions-v1.json axis (group) name.
DIMENSION_KEY_TO_AXIS: dict[str, str] = {
    "fraud_objective": "fraud_objective",
    "technical_mechanism": "technical_mechanism",
    "typical_channels": "channel",
    "social_engineering_tactics": "social_engineering_tactic",
    "requested_user_actions": "requested_user_action",
    "potential_harm": "potential_harm",
}


def terms_by_axis(dimensions_component: dict) -> dict[str, set[str]]:
    """{axis_name: {term_id, ...}} from a parsed dimensions-v1.json component."""
    return {
        axis: {t["id"] for t in block.get("terms", []) if isinstance(t, dict) and "id" in t}
        for axis, block in dimensions_component.get("dimensions", {}).items()
        if isinstance(block, dict)
    }


def dimension_map_problems(where: str, dim_map: dict, axis_terms: dict[str, set[str]]) -> list[str]:
    """Axis-integrity problems for ONE dimension map (empty == clean). Rejects, per the governed
    contract: (A) an unknown dimension key/axis; (B) a valid term placed under the wrong axis;
    (C) a nonexistent term under an otherwise valid axis."""
    problems: list[str] = []
    for key, terms in dim_map.items():
        axis = DIMENSION_KEY_TO_AXIS.get(key)
        if axis is None:
            problems.append(f"{where}: unknown dimension axis/key {key!r}")
            continue
        valid = axis_terms.get(axis, set())
        for term in terms:
            if term not in valid:
                problems.append(f"{where}: dimension term {term!r} not valid in axis {key!r}")
    return problems
