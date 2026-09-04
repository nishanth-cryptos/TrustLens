# DET-001 P3-WP8 — Engine integration + CI closure

| Field | Value |
|---|---|
| Work package | P3-WP8 |
| Status | **Implementation-complete locally; local gate 18/18 + ci_selftest 6/6 GREEN; independent-review remediation applied** |
| Owner role | Detection Architect |
| Authority | DET-001 (§18 pipeline stage 19 "Result assembly with full version pinning") and the approved P3-WP8 implementation authorization |
| Consumes | One immutable current RuntimeKnowledge bundle, the WP3→WP6 public runtime, the promoted `detection-result.schema.json` (1.1.0) |
| Produces | The public `evaluate_detection_from_governed(...)` API returning one immutable, schema+semantically-valid `DetectionResult` |
| Gate | Canonical quality-gate check #18 (`validate_wp8_integration.py`); `ci_selftest` proves it bites |
| Next | Phase-3 formal closure **PENDING** commit / PR / remote GitHub Actions / merge / `phase3-wp8-v1.0` tag. Phase 4 (AI-assisted extraction) NOT started; G-09 remains OPEN |

## Scope and boundary

WP8 is the production-facing deterministic integration boundary that closes Phase 3. It turns governed
observation DATA + trusted envelope context (identity/time, language/script, support status) + an
already-loaded `RuntimeKnowledge` into ONE `DetectionResult` conforming to the promoted result contract. It
adds **zero** scam-detection semantics: every decision quantity comes from the authoritative WP5
`DecisionResult` and every explanation/action from the authoritative WP6 `ExplanationResult`. WP8 only
orchestrates, maps, pins, validates and reconciles. It performs no extraction/NLP/LLM, emits no probability or
score, implements no database/HTTP/UI, and makes no accuracy claim (G-09 open).

## Public API

`knowledge.runtime.evaluate_detection_from_governed(rk, indicator_observations, observations, *,
evaluation_id, evaluation_timestamp, input_id, language, script, input_support_status,
whole_evaluation_errors=()) -> DetectionResult`

The engine version and evaluation profile are runtime-pinned (`ENGINE_VERSION` / `DEFAULT_PROFILE`) and cannot
be supplied by the caller; nor can any decision, rollup, explanation, action or provenance field (the fixed
signature rejects them). `whole_evaluation_errors` are TRUSTED integration diagnostics, never end-user input.
`rk` MUST be an already-loaded bundle — a bundle that failed to load never reaches here, so provenance is never
fabricated.

## Support-first orchestration (DET-001 §3)

Only `SUPPORTED` / `PARTIALLY_SUPPORTED` execute rules (WP3→WP4→WP5 via `evaluate_decision_from_governed`,
which requires exactly one effective language/script scalar — a multi-valued evaluable context fails closed).
`UNSUPPORTED` / `INSUFFICIENT_INFORMATION` / `ERROR`, and any trusted whole-evaluation error, route through the
authoritative WP5 aggregation boundary over an EMPTY rule-result set — **no rule ever runs** — so a skipped
evaluation can never be reported as `NO_SCAM_PATTERN`. This is proven with a poison test: GDC-01's
live-matching observations under a forced `UNSUPPORTED` status still produce `UNSUPPORTED` with empty
`rule_results`.

## Result assembly and field sources

`result_contract_version` = `"1.1.0"` (const). `evaluation_id`/`evaluation_timestamp`/`input_id` are
envelope-only trusted identity/time (validated; never inputs to any decision). `language`/`script` are the
governed arrays, preserved verbatim. Decision axes, `rule_results` (serialized EXACTLY as
`DecisionResult.rule_results` — WP8 owns no filtering), and the WP5 rollups come from the `DecisionResult`;
`explanation`/`recommended_actions` and the top-level `limitations` come verbatim from the `ExplanationResult`.

Provenance is pinned from the loaded `RuntimeKnowledge` + `ENGINE_VERSION` + the `DecisionResult` profile:
`bundle_version`, `bundle_content_digest`, `commit_sha`, `engine_version`, `evaluation_profile`
(`mvp-default` / `MEDIUM` / `risk-matrix-v1` / `confidence-policy-v1`), and `component_versions`. The manifest
and result-contract component key sets differ, so WP8 applies one authoritative deterministic translation:
copy `rule_schema`/`indicator_registry`/`indicator_families`/`negative_library`/`taxonomy`/`dimensions`/
`action_policy`, rename `extraction_schemas`→`extraction_contracts`, and drop `evidence_manifest`/
`evidence_records` (the full bundle digest still pins them). The `action_policy` version must reconcile across
bundle, explanation and provenance or assembly fails closed.

## Validation, reconciliation and trust boundary

Before returning, every assembled result is (1) JSON-Schema validated against `detection-result.schema.json`
(with the `rule-evaluation-result` `$ref` resolved), (2) checked against the promoted cross-field semantic
invariants + a probability-key scan, and (3) reconciled field-by-field against the actual `RuntimeKnowledge`,
`DecisionResult` and `ExplanationResult`. Any schema failure, semantic contradiction, forged rollup/axis,
provenance/profile/action-policy mismatch, or smuggled probability raises a typed `DetectionResultError`
(`INVALID_INPUT_CONTEXT`, `INVALID_IDENTITY`, `PROFILE_MISMATCH`, `PROVENANCE_MISMATCH`,
`ACTION_POLICY_MISMATCH`, `RESULT_SCHEMA_INVALID`, `RESULT_SEMANTIC_INVALID`, `ASSEMBLY_INCONSISTENCY`) — never
an invalid or forged result. Established upstream typed failures (`BundleLoadError`, `AggregationError`,
`ExplanationError`, `EvaluatorError`) propagate; WP8 never catches-all into a generic result.

The promoted semantic invariants (`semantic_violations` + helpers) were moved into `knowledge/runtime/result.py`
so the engine assembler and `validate_runtime_contracts.py` share ONE definition (which reuses
`aggregation.RISK_MATRIX` and the promoted action vocabulary — no second policy matrix).

Independent-review remediation (applied):
- **H1 — whole-evaluation/support consistency.** A trusted `WHOLE_EVALUATION` diagnostic accompanies
  `input_support_status = ERROR` only. A non-empty `whole_evaluation_errors` with any non-ERROR support state is
  an inconsistent context and fails closed (`INVALID_INPUT_CONTEXT`) — the authoritative governed support state
  is never silently normalised to ERROR.
- **M1 — profile provenance truthfulness.** The emitted `evaluation_profile` ids are reconciled against the
  ACTUAL executed WP5 policy authority (`aggregation.RISK_MATRIX_ID` = `risk-matrix-v1`,
  `aggregation.CONFIDENCE_POLICY_ID` = `confidence-policy-v1`), not merely against each other — a mislabelled
  `DEFAULT_PROFILE` that agrees with the `DecisionResult` but disagrees with the real policy fails closed
  (`PROFILE_MISMATCH`).
- **M2 — real timestamp validation.** `evaluation_timestamp` is validated with the stdlib
  `datetime.fromisoformat` (a trailing `Z` normalised to `+00:00`) and must be a real, timezone-aware calendar
  instant; calendar-impossible values (`2026-99-99T…`, `2026-02-30T…`) and naive/offset-less timestamps are
  rejected (`INVALID_IDENTITY`). The caller's serialized value is validated only, never mutated.

## Engine version and evaluation profile

`ENGINE_VERSION = "1.0.0"` lives once in `knowledge/runtime/engine.py`. It identifies the deterministic engine
CODE (not the knowledge bundle), is caller-immutable, is pinned into `provenance.engine_version`, and is
authoritatively enforced by the result schema's SemVer pattern at assembly (it deliberately does not raise at
import, so a malformed value is a WP8-exclusive defect). A future change to deterministic runtime semantics
requires a governed bump. `EvaluationProfile` gained an explicit governed `profile_id = "mvp-default"` field,
replacing the implicit WP5 `getattr` fallback; the production API pins `DEFAULT_PROFILE` (a caller cannot label
a decision with a different risk-matrix/confidence-policy id while the runtime executes the fixed governed
implementation).

## Privacy, determinism and design-preview exclusion

The envelope is privacy-minimised: WP5 rollups are ids only; WP6 emits `observation_ref`(+optional `span`) and
never `raw_span`/`redacted_quote`; a full-envelope scan asserts no raw content, no redacted quote and no numeric
probability leaks. With fixed metadata the complete serialization is byte-identical; changing only
`evaluation_id`/`evaluation_timestamp` leaves every decision/explanation/action/provenance field unchanged.
The production final envelope is PUBLISHED-live-only — `DESIGN_PREVIEW` remains WP7 validation infrastructure;
an unpublished rule (e.g. `TL-MAL-003` in GDC-08) can never enter a production `DetectionResult`.

## Integration matrix (representative; not a re-run of WP7)

`validate_wp8_integration.py` runs 103 integration assertions over one real bundle: GDC-01 (detected + hard-risk
override + full provenance), GDC-02 (benign), GDC-06 (multi-rule), GDC-11 (insufficient + ambiguity), GDC-12
(unsupported + no rule execution + poison test), GDC-13 (insufficient), GDC-15 (occurrence separation),
GDC-08 (preview exclusion), a synthetic governed fixture that legitimately drives the PUBLISHED rule
`TL-JOB-001` to a live `SUPPRESSED` state (via `EXPLICIT_NO_FEE`, job family has no override), plus
whole-evaluation ERROR, single-rule degraded, bundle pre-load failure, malformed observations, invalid
identity/context, caller-cannot-inject, determinism, identity/time invariance, immutability, and an assembly
forgery/corruption matrix. WP7 remains authoritative for the 15 golden decisions (580 assertions); WP8 proves
the ENVELOPE. The golden corpus, rules, negative library, action policy and promoted schemas are unchanged.

## CI closure

`validate_wp8_integration.py` is canonical quality-gate check #18 (appended to `run_all.py`'s dependency
order); because the workflow already runs `run_all.py` and `ci_selftest.py` on PR/main, WP8 is automatically
part of the remote engine gate with no new CI job. `ci_selftest.py` gains one WP8-exclusive defect (a malformed
`ENGINE_VERSION`) that only `validate_wp8_integration.py` catches, proving the gate bites. All validation is
offline.

## Result

Canonical gate 18/18 GREEN; `ci_selftest` 6/6; WP8 103/103; WP1–WP7 regressions unchanged (WP3 457, WP4 220,
WP5 13009, WP6 2499, WP7 580 / 18 replay lanes). **WP8 is implementation-complete locally and Phase 3 is
technically ready for closure after independent approval.** Phase-3 formal closure is PENDING the repository
closure steps (commit / PR / remote GitHub Actions / merge / `phase3-wp8-v1.0` tag); it is not yet formally
closed. No accuracy/precision/recall claim; G-09 remains OPEN; Phase 4 not started.
