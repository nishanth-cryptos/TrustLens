# DET-001 / P3-WP1 — Runtime Detection Result Contracts

| Field | Value |
|---|---|
| Document ID | DET-001-WP1 |
| Version | 1.0 |
| Status | **P3-WP1 complete — runtime contracts frozen** |
| Owner role | Detection Architect |
| Dependencies | [DET-001](DET-001-deterministic-detection-engine.md), [ADR-0005](../../adr/ADR-0005-rule-execution-model.md), [ADR-0006](../../adr/ADR-0006-risk-and-confidence-aggregation.md), [ADR-0004](../../adr/ADR-0004-knowledge-storage-architecture.md), KB-001 §8, KB-002 |
| Feeds | P3-WP2 (bundle loader), P3-WP3–WP6 (evaluator → aggregation → explanation) |
| Last updated | 2026-08-29 |

> **Scope.** P3-WP1 converts the approved Phase-3 **design** contracts into stable **runtime-facing**
> contracts and freezes the boundary that later components produce and consume. It implements **no**
> detection logic (no loader, evaluator, scorer, aggregator or extractor). DET-001 / ADR-0005 / ADR-0006
> remain authoritative for meaning; this document specifies the frozen shapes.

## 1. Purpose and authoritative location

The runtime contracts are the stable structures every later work package targets:

```
P3-WP2 bundle loader → P3-WP3 evaluator → P3-WP4 suppression/overrides →
P3-WP5 aggregation → P3-WP6 explanation/actions → RUNTIME RESULT CONTRACTS (frozen here)
```

**Promotion (STEP 2).** The Phase-3 design copies under `docs/03-detection/contracts/` were **promoted,
enriched and frozen** into the repository's runtime schema tree. There is now **one** authoritative
definition of each contract; the doc-only path holds a [pointer README](contracts/README.md), and the
originals are preserved in git history and the `phase3-design-v1.0` tag.

| Contract | Authoritative runtime location | `$id` (unchanged) |
|---|---|---|
| Detection result | [`knowledge/schemas/detection/detection-result.schema.json`](../../knowledge/schemas/detection/detection-result.schema.json) | `https://trustlens/schemas/detection/detection-result.schema.json` |
| Rule evaluation result | [`knowledge/schemas/detection/rule-evaluation-result.schema.json`](../../knowledge/schemas/detection/rule-evaluation-result.schema.json) | `https://trustlens/schemas/detection/rule-evaluation-result.schema.json` |

**Not bundled.** Result contracts are consumer-side *output* shapes, not evaluation *knowledge*, so they
are deliberately **kept out of** the ADR-0004 published bundle (the bundle carries what is needed to
evaluate an input; a result schema is not). This leaves the bundle `content_digest` untouched. If the
programme later wants them distributed with the bundle, that is a governed ADR-0004 change.

## 2. Field semantics — the five separated quantities

The contract keeps the DET-001 decision quantities **separate** (CONF-001; never one number, never a
probability):

| Field | Meaning | Vocabulary |
|---|---|---|
| `input_support_status` | Was the input evaluable? (decided FIRST) | SUPPORTED · PARTIALLY_SUPPORTED · UNSUPPORTED · INSUFFICIENT_INFORMATION · ERROR |
| `classification` | What TrustLens concludes | NO_SCAM_PATTERN · INSUFFICIENT_EVIDENCE · SCAM_PATTERN_SUSPECTED · SCAM_PATTERN_DETECTED · UNSUPPORTED · ERROR |
| `decision_severity` | Harm **if** genuine (max effective severity of fired rules) | NONE · LOW · MEDIUM · HIGH · CRITICAL |
| `matched_evidence_strength` | Strength of the matched evidence (governing rule) | NONE · WEAK · MODERATE · STRONG |
| `risk_level` | Exposure = fixed matrix (severity × strength) | NONE · LOW · MEDIUM · HIGH · CRITICAL |
| `detection_confidence` | Trust in our own analysis (separate axis) | NOT_APPLICABLE · LOW · MEDIUM · HIGH |

Per-rule (`rule-evaluation-result`): `evaluation_state` (MATCHED · NOT_MATCHED · **INDETERMINATE** ·
SUPPRESSED · NOT_APPLICABLE), `required_combination_result` (TRUE · FALSE · UNKNOWN — Kleene, ADR-0005),
`rule_evidence_verdict`, `rule_evidence_strength`, `rule_severity_declared` / `effective_severity`,
`rule_detection_confidence`, `observation_refs` / `indicator_observation_refs`, `evidence_classes_spanned`,
`suppression`, `active_overrides`, `ambiguities` / `unknowns`, `explanation_fragment`, `source_references`,
`evidence_ids`, optional `governing`, and `evaluation_error` (for degraded single-rule failures).

**Enums are reused, not duplicated.** Severity, evidence verdict, extraction-confidence levels, the
five-valued epistemic states, suppression effects, the eight evidence classes, and id patterns are the
Phase-2 vocabularies. The new DET-001/ADR-0006 vocabularies (support status, classification, detection
confidence, risk, evaluation state, matched-evidence strength, the 15 action codes) are frozen here and
checked for drift by `validate_runtime_contracts.py`.

## 3. Explanation & recommended-action contracts (STEP 6/7)

`explanation` is **structured first** (`summary`, `what_was_detected`, `why`, `supporting_observations`,
`matched_indicators`, `suppression_considered`, `overrides_applied`, `rules_fired`, `evidence_basis`,
`remaining_unknowns`, `limitations`, `detection_confidence_reason`, `verification_steps`); optional
human-readable text is *derived* from it. **Explanation-provenance constraint:** an official fact may be
asserted only if it appears as a `quote` in `evidence_basis` (echoed from a fired rule's stored
`source_references`). `recommended_actions` use the governed 15-code vocabulary and each carries
`reason_rule_ids` / `reason_indicator_ids` / `reason_override_ids` / `evidence_refs` — no free-form advice
may enter the deterministic contract. UNSUPPORTED ⇒ `RESUBMIT_IN_SUPPORTED_LANGUAGE` + `SEEK_HUMAN_REVIEW`;
ERROR ⇒ `SEEK_HUMAN_REVIEW` — never a "safe" action.

## 4. Corroboration (STEP 8)

`corroboration_summary` records `independent_evidence_classes`, `evidence_class_count`,
`supporting_indicator_families`, `family_count`, `shared_observation_refs`, and a `band`. It represents
corroboration over **independent evidence classes/families, not rule count**; `shared_observation_refs`
keeps shared evidence from being mistaken for independent corroboration. WP1 fixes the shape; **P3-WP5**
computes it.

## 5. Provenance & reproducibility (STEP 9)

`provenance` is **required** and pins everything that affects the output: `bundle_version`,
`bundle_content_digest` (SHA-256, ADR-0004), `engine_version`, `evaluation_profile` (`profile_id`,
`extraction_confidence_gate`, `risk_matrix_id`, `confidence_policy_id`), and `component_versions`
(`rule_schema`, `indicator_registry`, `indicator_families`, `negative_library`, `taxonomy`, `dimensions`,
`extraction_contracts`) — names mirroring `bundle-manifest.schema.json`. Each fired rule echoes its
`rule_version`. `commit_sha` is optional provenance and is **not sufficient alone** (STEP 9): the content
digest + component versions are what make a decision replayable.

## 6. Failure / degraded model (STEP 10)

Fail-closed. `errors[]` entries carry `scope`:
- `WHOLE_EVALUATION` accompanies `input_support_status = ERROR` — the engine **refused to evaluate**
  (bundle integrity, unknown bundle version, schema incompatibility, missing provenance, malformed
  extraction). `classification = ERROR`.
- `SINGLE_RULE` accompanies `degraded = true` — evaluation continued with one rule unavailable
  (`evaluation_state = NOT_APPLICABLE` + per-rule `evaluation_error`), confidence is capped, and the
  decision is routed to review.

The cross-field rule **ERROR/UNSUPPORTED can never serialize as NO_SCAM_PATTERN** is enforced by the
runtime validator's semantic checks (JSON Schema alone cannot express it). No engine exception handling is
implemented here — only the representable shapes.

## 7. UNKNOWN / AMBIGUOUS representation (STEP 11)

The Phase-2 five-valued epistemic states are preserved end to end: at the rule level via
`required_combination_result = UNKNOWN → evaluation_state = INDETERMINATE` (distinct from `NOT_MATCHED`),
and at the decision level via `ambiguities[]` / `unknowns[]`. Unresolved information is never forced into a
`null` without semantics; `INDETERMINATE` + `INSUFFICIENT_EVIDENCE` is the canonical "we don't know, and
that is not safe" outcome.

## 8. Versioning (STEP 12)

`result_contract_version` is a **const** (`1.0.0`), bumped per KB-001 §8:

| Bump | Trigger |
|---|---|
| **PATCH** | Clarified description/example; no change to interpretation or shape. |
| **MINOR** | Backwards-compatible **additive** optional field. |
| **MAJOR** | Any backwards-**incompatible** interpretation change — a removed/renamed field, a **tightened enum**, a changed field meaning, or a new required field. |

A backwards-incompatible interpretation change **must** be MAJOR. The `$id`s are stable across PATCH/MINOR;
a MAJOR revision issues new schema files and records the migration.

## 9. Privacy (STEP 18)

The contract is privacy-minimised: it carries **references** (`observation_refs`,
`indicator_observation_refs`, `supporting_observations[].observation_ref` + `span`) and, at most, an
optional **redacted** excerpt (`redacted_quote`) — never raw OTP / card / UPI / phone / account content.
Official quotes come only from governed rule evidence, not from the user's input.

## 10. API-neutrality (STEP 17)

The contracts are serialization/API-neutral **JSON Schema**. They are not bound to REST/GraphQL, Python/
Java DTOs, or a database schema; later application layers (Phase 5/6) map them.

## 11. Validation & compatibility (STEP 13–16, 20)

`knowledge/validation/validate_runtime_contracts.py` (the **11th canonical gate check**) proves: both
schemas valid Draft 2020-12; **enum synchronisation** with DET-001/ADR-0006; **10 valid fixtures** pass
schema + probability name-scan + semantic invariants; **10 invalid fixtures** each rejected
(non-vacuous); and all **15 DET-001 golden decision cases are representable** in the runtime contract
(structural compatibility — no engine decision generated). Fixtures live under
`knowledge/schemas/detection/fixtures/` and are explicitly marked SYNTHETIC. `validate_det_design.py`
(10th check) retains the golden-case ↔ KB consistency check. CI path triggers already cover
`knowledge/**` and `docs/03-detection/**`; local `run_all.py` and CI run the identical suite.

## 12. What is NOT done (deferred to later WPs)

No bundle loader (P3-WP2), no evaluator (P3-WP3), no suppression/override executor (P3-WP4), no
aggregation/scoring (P3-WP5), no explanation/action builder (P3-WP6). The `corroboration_summary`,
`governing`, `rule_evidence_strength`, and confidence bands are **shapes reserved** here and **computed**
later. Fixtures are contract examples, never engine-generated decisions, and never an accuracy claim (G-09).

## 13. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-29 | P3-WP1: promoted + enriched the two runtime contracts to `knowledge/schemas/detection/`; froze enums; added structured explanation/action/corroboration/provenance/failure shapes; 10 valid + 10 invalid fixtures; `validate_runtime_contracts.py` wired as the 11th canonical gate check; retired the doc-only schema copies to a pointer README; golden-case representability proven. No detection logic implemented. | Detection Architect |
| 1.1 (additive MINOR) | 2026-09-02 | P3-WP3 provenance-output amendment (required by the WP5 safety review): `rule-evaluation-result.schema.json` gains an **additive optional** grouped `live_positive_provenance` (object keyed by `indicatorId`; each value an array of non-empty, unique occurrence groups of `instanceRef`). Backwards-compatible — no `required` change, no enum change. Populated by WP3 for MATCHED-positive TRUE indicators; consumed by WP5 to prove evidence independence. Fixtures extended (1 valid enrichment + 4 invalid: empty group, duplicate ref, duplicate group, invalid key). The JSON Schema carries no explicit version field, so none is invented; this is recorded as a MINOR contract evolution. | Detection Architect |
