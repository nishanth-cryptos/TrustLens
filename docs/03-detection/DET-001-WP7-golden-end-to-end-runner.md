# DET-001 P3-WP7 — Golden end-to-end replay runner

| Field | Value |
|---|---|
| Work package | P3-WP7 |
| Status | **Ratified; gate GREEN — 580/580 assertions, 18/18 replay lanes** |
| Owner role | Detection Architect |
| Authority | DET-001 and the approved P3-WP7 implementation authorization |
| Consumes | Golden corpus v1.3.1, one immutable current RuntimeKnowledge bundle, WP3–WP6 public/private lifecycle APIs |
| Produces | Frozen internal `GoldenReplayResult` records and deterministic validation output |
| Gate | Canonical quality-gate check #17 (`validate_wp7_golden_runner.py`); canonical gate 17/17 GREEN, `ci_selftest` 5/5 |
| Next | WP8 (result envelope) has NOT started; G-09 remains OPEN |

## Scope and boundary

WP7 is validation infrastructure, not runtime product behavior. It proves composition from governed fixtures
through WP3 evaluation, WP4 suppression, WP5 aggregation and WP6 explanation/actions. It performs no
extraction, parses no `input_gloss`, invokes no network/subprocess/LLM/NLP facility, makes no probability or
accuracy claim, and leaves G-09 open.

The runner does **not** assemble `detection-result.schema.json`, an API/persistence envelope, an
`evaluation_id`, or a timestamp. Those remain WP8. Equality-sensitive replay data contains no duration.

## Corpus and fixture contract

The runner accepts `cases_version == 1.3.1` with exactly 15 unique case ids. Missing expectations,
unsupported versions, duplicate ids and version/count disagreement fail closed. Expected fields are projected
out before execution and are consulted only after runtime output exists.

Support is independently derived from fixture metadata: a non-empty all-`en` language array plus a non-empty
all-`Latn` script array is `SUPPORTED`; other well-formed values are `UNSUPPORTED`; missing/malformed metadata
is a case `ERROR`.

When `governed_input` exists, both governed arrays are defensively copied and otherwise passed unchanged.
Otherwise, `declared_indicators` is deterministically adapted to the same governed observation contracts using
the already-proven validation-fixture projection. This is test fixture infrastructure, never extraction.

## Replay lanes

`LIVE_REPLAY` calls `evaluate_decision_from_governed` and public `build_explanation`, so only PUBLISHED rules
execute. All 15 cases receive this lane. Twelve live-publishable cases compare directly with their goldens.

The three non-live preview cases (GDC-07, GDC-08 and GDC-10) first prove through `LIVE_REPLAY` that preview-only
rules cannot enter `matched_rules`, `rules_fired`, evidence or action reasons. They then receive `DESIGN_PREVIEW`,
which derives the complete sorted lifecycle set from RuntimeKnowledge where status is PUBLISHED, APPROVED or
PEER_REVIEW, uses the explicit on-promotion evaluator and private design-preview explanation path, and compares
the preview output to the golden. A preview PASS is never labelled as live detection.

Across all 15 cases this is 18 replay lanes (15 `LIVE_REPLAY` plus 3 `DESIGN_PREVIEW`), which currently run
18/18 PASS. The runner's full assertion count is 580/580 PASS.

## Comparison and safety assertions

The runner compares support, classification, exact fired-rule set, selected expected rule states, overrides,
blocked suppressors where specified, severity, evidence strength, risk, confidence, corroboration band,
unknowns, ambiguities and ordered recommended actions. It also verifies mandatory explanation fields,
decision-to-explanation rollups, governed verification steps, exact governed evidence-basis linkage, absence
of raw spans/redacted quotes/credential leakage/numeric probabilities/fabricated reporting details, and
non-reassuring unsupported/error/no-scam wording.

`GoldenReplayResult` is frozen and deeply read-only. It records case/lane/status, decision, explanation,
expected and actual projections, mismatches, and bundle/action-policy identity—never WP8 envelope state.

## Determinism and self-tests

The complete replay is repeated and its equality-sensitive projection compared. GDC-15 is additionally replayed
with reversed governed arrays and reversed dictionary-key order, preserving its separate disclaimer and live OTP
occurrences. In-memory expectation mutations for classification, risk, fired rules, overrides and actions must
be caught without changing actual execution. Further tests cover ERROR behavior, corpus corruption, immutable
results, stage-error isolation, all-case reporting, offline source invariants and golden-file immutability.

## Golden patch reconciliation (corpus 1.3.1)

The implementation does not weaken comparisons or read expectations to make the corpus pass. Its first exact run
reported four discrepancies between the golden ORACLE and the already-ratified runtime. All four were resolved by
the `1.3.1` PATCH, which aligned the ORACLE to the runtime and introduced **no runtime semantic change**:

- **GDC-08** lifecycle metadata corrected to non-live preview (`live_publishable` true→false). Its binding topology
  rests on the unpublished `TL-MAL-003`, so under the PUBLISHED-only live engine it routes to `DESIGN_PREVIEW`
  exactly like GDC-07/GDC-10; its designed `SUPPRESSED`/`NO_SCAM_PATTERN` preview decision is unchanged.
- **GDC-04** now records the pre-existing legitimate overlap where published `TL-CRED-002` also `MATCHED` alongside
  `TL-PAY-001`. The governing rule, severity, evidence strength, risk, confidence, corroboration, active override
  and recommended actions are all unchanged.
- **GDC-11** ambiguity text was replaced with the authoritative WP3 occurrence-association diagnostic the runtime
  actually emits.
- **GDC-13** removed a stale expected top-level unknown that the current sparse WP3/WP5 unknown rollup never
  produces.

The `1.3.1` golden patch introduced no runtime semantic change, no new fraud knowledge, no new rule, no rule
semantic change, no severity/risk/confidence/classification change, and no action-policy change. It added no new
case. G-09 remains OPEN and the runner makes no accuracy/precision/recall claim. No WP3–WP6 runtime file, promoted
schema, action policy or negative-indicator library was changed by WP7.

Current gate state: WP7 runs 580/580 assertions and 18/18 replay lanes PASS; the canonical quality gate is 17/17
and `ci_selftest` is 5/5. WP8 has NOT started.
