# Phase-3 detection contracts — PROMOTED to the runtime schema tree

The Phase-3 **design** copies of the detection contracts previously lived here
(`detection-result.schema.json`, `rule-evaluation-result.schema.json`). At **P3-WP1** they were
**promoted, enriched and frozen** as the authoritative **runtime** contracts, and moved into the
repository's runtime schema tree so production-facing schemas are not stranded under a
documentation-only path:

| Contract | Authoritative location (runtime) |
|---|---|
| Detection result | [`knowledge/schemas/detection/detection-result.schema.json`](../../../knowledge/schemas/detection/detection-result.schema.json) |
| Rule evaluation result | [`knowledge/schemas/detection/rule-evaluation-result.schema.json`](../../../knowledge/schemas/detection/rule-evaluation-result.schema.json) |

There is now **one** authoritative definition of each contract (no second, independently-maintained
copy). The `$id`s are unchanged (`https://trustlens/schemas/detection/...`), so any reference by `$id`
still resolves.

- **Design authority:** [`DET-001`](../DET-001-deterministic-detection-engine.md),
  [`ADR-0005`](../../../adr/ADR-0005-rule-execution-model.md),
  [`ADR-0006`](../../../adr/ADR-0006-risk-and-confidence-aggregation.md).
- **Contract spec (field semantics, versioning, privacy, provenance, failure, compatibility):**
  [`DET-001-WP1-runtime-contracts.md`](../DET-001-WP1-runtime-contracts.md).
- **Validation:** `knowledge/validation/validate_runtime_contracts.py` (the 11th canonical gate check)
  validates the schemas, the valid/invalid fixtures, enum synchronisation, and golden-case
  representability.
- **History:** the original design copies are preserved in git history and in the tag
  `phase3-design-v1.0`.
