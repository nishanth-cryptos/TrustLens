# DET-001 P3-WP4 — Rule-level suppression and severity orchestration

| Field | Value |
|---|---|
| Work package | P3-WP4 |
| Status | **Implemented** — post-WP3 per-rule orchestration only |
| Authority | [DET-001](DET-001-deterministic-detection-engine.md), [ADR-0005](../../adr/ADR-0005-rule-execution-model.md), [ADR-0006](../../adr/ADR-0006-risk-and-confidence-aggregation.md) |
| Consumes | A P3-WP3 `RuleEvaluationResult` plus the same immutable P3-WP2 `RuntimeKnowledge` |
| Produces | A schema-valid per-rule result; only `MATCHED` may become `SUPPRESSED` |
| Runtime | `knowledge/runtime/suppression.py` |
| Gate | Canonical quality-gate **check #14** (`knowledge/validation/validate_wp4_suppression.py`) |
| Last updated | 2026-08-31 |

> **Scope.** WP4 resolves governed `SUPPRESS_RULE`, `CAP_SEVERITY`, and `CONTEXT_ONLY` effects after WP3.
> It does not reevaluate rule truth or implement decision aggregation, governing-rule selection, decision
> severity, risk, confidence, corroboration, classification, explanations, or actions. Those decision-level
> concerns remain deferred to P3-WP5 and later work packages.

## 1. WP3 → WP4 boundary

WP3 remains authoritative for governed input validation, structural occurrence eligibility, sparse
`UNKNOWN`, extraction-confidence gating, hard-risk override computation, occurrence-associated
`SUPPRESS_INDICATOR`, Kleene `require` evaluation, evidence-class diversity, and its four output states:
`MATCHED`, `NOT_MATCHED`, `INDETERMINATE`, and `NOT_APPLICABLE`.

WP4 consumes the WP3 result rather than recomputing it. Its authoritative inputs are:

- `evaluation_state` and `required_combination_result`;
- WP3's base `effective_severity`;
- `matched_negative_indicators`;
- `active_overrides`.

Negative-indicator and override IDs are resolved again through immutable `RuntimeKnowledge`. WP3's
informational `suppression.blocked_suppressors`, when present, is cross-checked but is not the authority.
The production convenience APIs run the normal governed-data WP3 entry point first and then WP4; they do
not expose a caller-built observation context. Every public WP4 entry point rejects pre-populated WP5-owned
fields with a typed fail-closed error; no stage can use WP4 as a pass-through for decision-level data.

## 2. Exact runtime order

For each per-rule result, WP4 performs this deterministic sequence:

1. Deep-copy the input and canonicalise every contract-defined set-like result array (sorted and
   duplicate-free), including the matched/neutralised indicator, override, evidence-class, and reference
   arrays. The caller's mapping is never mutated.
2. Reject any pre-populated WP5-owned field with `SUPPRESSION_EXECUTION_ERROR`.
3. Pass through every non-`MATCHED` state and every `SUPPRESSION`-kind result semantically unchanged after
   canonicalisation.
4. Validate the `MATCHED` WP3 boundary (`COMPOSITE`, combination truth `TRUE`, canonical base severity,
   typed matched-negative and active-override arrays, and no pre-applied WP4 metadata).
5. Resolve active override IDs and union their governed `blocks_suppression_categories`.
6. Resolve each matched negative indicator and classify its governed effect.
7. Mark a rule suppressor or cap blocked only when the negative is `blockable_by_overrides: true` **and**
   an active override explicitly blocks its category.
8. Cross-check any WP3 informational blocked-soft-suppressor set against the governed WP4 resolution.
9. Apply all surviving severity ceilings to the WP3 base with the canonical ordinal minimum.
10. If at least one `SUPPRESS_RULE` survives, perform the sole WP4 state transition:
   `MATCHED → SUPPRESSED`.
11. Emit canonically sorted, duplicate-free suppression metadata.

WP4 has no clock, network, random source, model call, or mutation of its inputs.

## 3. Governed effects

### `SUPPRESS_RULE`

All surviving suppressor IDs are emitted in lexical order as `applied_suppressors`. Their lexical first is
also emitted as `suppressed_by`, and the primary `effect` is `SUPPRESS_RULE`. Blocked suppressors leave the
rule `MATCHED` and are retained in `blocked_suppressors` for auditability. The presence of an override alone
does not block anything.

No state other than `MATCHED` may transition to `SUPPRESSED`. WP4 cannot manufacture or resurrect a match;
structural `NOT_MATCHED`, uncertainty-bearing `INDETERMINATE`, and degraded/out-of-scope `NOT_APPLICABLE`
remain authoritative.

### `CAP_SEVERITY`

WP4 imports the one canonical severity ordering from the WP3 evaluator:

```text
LOW < MEDIUM < HIGH < CRITICAL
```

For the WP3 base `B` and surviving governed ceilings `C₁ … Cₙ`:

```text
final effective_severity = min(B, C₁, …, Cₙ)
```

This operation is monotone: a cap never increases an already-lower WP3 severity. Surviving cap indicator
IDs are recorded in `applied_severity_caps`; their deterministic unique ordinal values are recorded in
`severity_caps_applied`. Blocked cap IDs are recorded separately in `blocked_severity_caps`. If every cap
is blocked, WP3's base is retained. Governed `CAP_SEVERITY` ceilings are exactly `LOW`, `MEDIUM`, and
`HIGH`. `CRITICAL` is deliberately not a cap value; encountering it is malformed governed metadata and
fails closed with `SUPPRESSION_EXECUTION_ERROR`.

### `CONTEXT_ONLY`

`CONTEXT_ONLY` never changes state, severity, rule activation, or suppression. Its indicator IDs are only
recorded in `context_only_present`. When combined with another effect, primary-effect precedence is
`SUPPRESS_RULE > CAP_SEVERITY > CONTEXT_ONLY > NONE`.

### `SUPPRESS_INDICATOR`

WP4 recognizes `SUPPRESS_INDICATOR` as already resolved and does not execute it again. Occurrence-associated
neutralisation through governed `observation_refs` belongs exclusively to WP3. The WP4 regression replays
stored GDC-15 through WP3 and proves that WP4 preserves its `MATCHED` state and WP3 neutralisation metadata.
Structural negation likewise stays non-live and cannot be resurrected by WP4 or an override.

## 4. Fail-closed isolation

An unresolved negative or override ID, unknown effect, invalid cap (including `CRITICAL`), malformed governed
effect metadata, pre-populated WP5-owned field, or WP3/WP4 blocked-set disagreement degrades only that rule to:

```json
{
  "evaluation_state": "NOT_APPLICABLE",
  "evaluation_error": {"code": "SUPPRESSION_EXECUTION_ERROR", "message": "..."}
}
```

Useful rule identity and valid combination truth are preserved. Batch execution retains input order and
continues after a malformed member. A malformed effect can never silently produce a normal `MATCHED` or
`SUPPRESSED` result.

## 5. Runtime API

- `RuleSuppressionExecutor(rk).apply(wp3_result)`
- `RuleSuppressionExecutor(rk).apply_all(wp3_results)`
- `apply_rule_suppression(rk, wp3_result)`
- `evaluate_rule_with_suppression_from_governed(rk, rule_id, indicator_observations, observations, ...)`
- `evaluate_rules_with_suppression_from_governed(rk, indicator_observations, observations, ...)`

All return new per-rule mappings; they do not mutate the WP3 result or `RuntimeKnowledge`.
All enforce the same WP5-field rejection and whole-result canonicalisation boundary before orchestration.

## 6. Validation evidence and limitations

The WP4 validator visibly separates real governed-bundle tests from synthetic engine-capability tests.
Real tests cover live `SUPPRESS_RULE`, override blocking, `CONTEXT_ONLY`, structural pass-through,
GDC-15 non-reexecution, structural negation, multiple suppressors, and combined context/suppression.

The current governed negative library contains no live `CAP_SEVERITY` entry, and every current
`SUPPRESS_RULE` is override-blockable. Therefore cap combinations and non-blockable suppression are tested
against explicit test-only synthetic `RuntimeKnowledge`. Synthetic records establish executor semantics
only; they make no claim that those facts exist in the production knowledge base. The real immutable bundle
is never mutated.

No production negative indicator, fraud fact, source, citation, or other evidence was introduced for WP4.
No WP5 behavior is implemented, emitted, accepted, or passed through by any public WP4 entry point.
