# DET-001 P3-WP3 — Deterministic three-valued rule evaluator

| Field | Value |
|---|---|
| Work package | P3-WP3 |
| Status | **Implemented** — per-rule evaluation only |
| Owner role | Detection Architect |
| Authority | [DET-001](DET-001-deterministic-detection-engine.md) §§6–10, [ADR-0005](../../adr/ADR-0005-rule-execution-model.md), [ADR-0006](../../adr/ADR-0006-risk-and-confidence-aggregation.md) |
| Consumes | `RuntimeKnowledge` (P3-WP2) + an `IndicatorObservationSet` |
| Produces | `RuleEvaluationResult[]` ([rule-evaluation-result.schema.json](../../knowledge/schemas/detection/rule-evaluation-result.schema.json)) — **per-rule only** |
| Gate | Canonical quality-gate **check #13** (`knowledge/validation/validate_rule_evaluator.py`) |
| Last updated | 2026-08-31 |

> **Scope.** WP3 implements the deterministic interpreter that evaluates **one governed PUBLISHED rule**
> against one submission's indicator observations and returns a schema-valid per-rule result. It does
> **not** aggregate rules, compute final risk/severity/classification/confidence, resolve final
> suppression, or build explanations/actions — those are P3-WP4/WP5/WP6. The only governed knowledge
> semantic change in this work package is the programme-approved negative-library `2.0.0`
> occurrence-association rule described in §8; it introduces no WP4 behaviour.

---

## 1. Files

| File | Role |
|---|---|
| `knowledge/runtime/kleene.py` | Kleene strong three-valued core: `TRUE/FALSE/UNKNOWN`, `all_of`/`any_of`/`n_of`, `k_and`/`k_or`. Pure. |
| `knowledge/runtime/observations.py` | The evaluator **input boundary**: `IndicatorObservation` + `Observation` + the internal `EvaluationObservationContext`, minted solely by the module function `build_validated_context(...)` over the `indicator-observation.schema.json` + `observation.schema.json` contracts. |
| `knowledge/runtime/evaluator.py` | `RuleEvaluator` + `evaluate_rule_from_governed` / `evaluate_rules_from_governed` / `evaluate_candidate_rule_from_governed` (+ `evaluate_on_promotion_from_governed`) + `EvaluationProfile`. The interpreter. |
| `knowledge/runtime/__init__.py` | Exports the WP3 public API alongside the WP2 loader. |
| `knowledge/validation/validate_rule_evaluator.py` | The WP3 validator/test-suite (gate check #13). |

## 2. Input boundary (STEP 2)

The evaluator consumes an **`EvaluationObservationContext`** — indicator observations **plus the
normalized observations they reference** — never raw text; there is no NLP or extraction inside WP3.
Occurrence structural semantics have **ONE authoritative source**, the governed `observation.schema.json`
instance, reached through `indicator-observation.schema.json` `observation_refs` (P3WP3-010 remediation):

```
indicator_observation.observation_refs → normalized observation(s) → polarity / attribution / mood
```

An `IndicatorObservation` mirrors `indicator-observation.schema.json` and carries only its governed fields
(`indicator_id`, five-valued `matched`, registry `polarity`, extraction `confidence` level, `observation_refs`,
`supporting_spans`, `input_id`) — **never** an occurrence structural attribute (the governed schema forbids
them via `additionalProperties:false`, so `structural_polarity`/`attribution`/`mood` on an indicator
observation are schema-rejected). An `Observation` is a typed projection of a normalized observation carrying
`status`, `polarity` (`AFFIRMED`/`NEGATED`, default `AFFIRMED`), `attribution` (`FIRST_PARTY`/`REPORTED`/
`QUOTED`/`HYPOTHETICAL`, default `FIRST_PARTY`) and `mood` (`DIRECTIVE`/`DESCRIPTIVE`/`INTERROGATIVE`,
default `DIRECTIVE`).

**Production OWNS validation (P3WP3-R3-016).** There is **no caller-built context**. A production caller
passes governed *data* — schema-valid indicator observations plus the normalized observations they
reference — to the evaluator's `*_from_governed` APIs; the evaluator validates it **once**, internally, via
the module function `build_validated_context(indicator_observations, observations)`. That function
JSON-Schema-validates every indicator observation against `indicator-observation.schema.json` and every
normalized observation against `observation.schema.json`, resolves every `observation_ref`, and rejects
duplicate observation ids, dangling refs, and any malformed/forbidden/missing value (`input_id=null`,
`provenance=null`, invalid enums, a forbidden direct structural field, a missing `matched`/`polarity`,
etc.), returning a **deep-frozen** internal `EvaluationObservationContext`. It **never manufactures decisive
evidence** — a missing `confidence` stays absent (the gate demotes a confidence-less `OBSERVED` to
`UNKNOWN`, never silently `HIGH`). The context type is **internal**: it is never a production caller
contract, so no external / test / forged object can masquerade as "validated", and there is **no
context-taking method to bypass validation**. Malformed governed data **fails closed** (`ValueError`).

Tests and design tooling exercise this same production path. Golden cases may store an exact `governed_input`
fixture; the generic corpus replay passes those indicator + normalized observation dicts unchanged to the
`*_from_governed` APIs. GDC-15 uses this representation for its disclaimer and live-request occurrences —
there is no case-specific semantic workaround or second production model.

The context is **SPARSE** (programme decision 1): an indicator with **no** observation is `UNKNOWN` at the
operand level (missing information is not negative evidence), **not** `FALSE`. Only an *explicit*
`NOT_OBSERVED` observation is `FALSE`. There is no complete-frame assumption. This separates GDC-05 (receive
frame *explicitly* `NOT_OBSERVED` → `NOT_MATCHED`; the case declares it) from GDC-11 (receive frame
`AMBIGUOUS` → `INDETERMINATE`).

## 3. Truth tables (STEP 4)

Frozen per ADR-0005 §2 / DET-001 §7 and asserted exhaustively:

```
AND   T F U        OR    T F U        n_of(n):  TRUE  if #TRUE ≥ n
T     T F U        T     T T T                  FALSE if #TRUE + #UNKNOWN < n
F     F F F        F     T F U                  UNKNOWN otherwise
U     U F U        U     T U U
```

`all_of`: `FALSE` if any `FALSE`, `TRUE` if all `TRUE`, else `UNKNOWN`. `any_of`: `TRUE` if any `TRUE`,
`FALSE` if all `FALSE`, else `UNKNOWN`. Python truthiness is never used as rule semantics.

## 4. Condition operators (STEP 3)

Supported: **`all_of`, `any_of`, `n_of`** — exactly the operators in `rule.schema.json`'s `condition`
`$def` and ADR-0005 §2. `all_of`/`any_of` are used by the live rules (25/34 nodes); `n_of` is governed
and specified but currently unused by any rule — it is implemented and tested, not invented. **No other
operator exists and none is invented** (there is no `not`/`none_of`/`xor`/threshold operator; negation is
carried at the observation layer via `polarity` and the negative-indicator library, never as a logic
operator). An unknown operator in a condition is a malformed rule → isolated error (§9).

## 5. Observation-state mapping + confidence gate (STEP 3/8)

| `matched` | Kleene |
|---|---|
| `OBSERVED` (confidence ≥ gate) | `TRUE` |
| `OBSERVED` (confidence `LOW`, below gate) | **`UNKNOWN`** (never `FALSE`) |
| `OBSERVED` (confidence **absent**) | **`UNKNOWN`** (never silently `HIGH` — remediation 3) |
| `NOT_OBSERVED` / `NOT_APPLICABLE` | `FALSE` |
| `UNKNOWN` / `AMBIGUOUS` | `UNKNOWN` |
| *absent (no observation)* | **`UNKNOWN`** (sparse set — missing info is not negative evidence) |
| structurally non-live occurrence (`NEGATED`/`REPORTED`/`QUOTED`/`HYPOTHETICAL`/`DESCRIPTIVE`) | not a live positive (→ `FALSE` if that is the only occurrence; see §8) |

The **extraction-confidence gate** (pinned `EvaluationProfile.extraction_confidence_gate`, MVP default
`MEDIUM`) decides *eligibility only* — confidence is **never multiplied** into anything. `HIGH`/`MEDIUM`
→ eligible `OBSERVED`; `LOW` → demoted to `UNKNOWN` (a `LOW`-confidence decisive read cannot alone
establish a match, so the rule becomes `INDETERMINATE`); missing/`UNKNOWN` extraction → `UNKNOWN`. The
per-indicator `HIGH/MEDIUM/LOW/UNKNOWN` inputs are echoed in `extraction_confidence_inputs`; the derived
per-rule/decision confidence is **not** computed here (WP4/WP5).

**Multiple occurrences for one positive id** (STEP 6, P3WP3-011) are combined with **deterministic
three-valued OR** over per-occurrence live truth: **any** structurally-eligible live `TRUE` → `TRUE`;
else **any** `UNKNOWN` → `UNKNOWN`; else `FALSE`. A structurally non-live `FALSE` therefore **never
dominates** an unresolved possibly-live occurrence (`FALSE` OR `UNKNOWN` → `UNKNOWN`), and a genuine live
occurrence survives a co-present negated one (`FALSE` OR `TRUE` → `TRUE`). The result is order-independent
(permutation-invariant). All contributing `observation_refs` are preserved. A declared registry polarity
that contradicts the registry does not contribute a live positive.

## 6. Rule states (STEP 5)

`require` evaluates to `required_combination_result ∈ {TRUE, FALSE, UNKNOWN}`, mapped to
`evaluation_state`:

- `TRUE` **and** evidence-class diversity met → `MATCHED`
- `TRUE` **and** diversity **not** met → `NOT_MATCHED` (the `min_evidence_classes` gate; CONF-002)
- `FALSE` → `NOT_MATCHED`
- `UNKNOWN` → **`INDETERMINATE`** (uncertainty preserved; never collapsed to `NOT_MATCHED`)

`SUPPRESSED` and final severity capping are **not** produced by WP3 (WP4). `NOT_APPLICABLE` is used only
for the non-executable / error paths (§8/§9).

## 7. Evidence-class diversity (STEP 8)

`min_evidence_classes` (a rule field, ≥ 2) is gated against the **distinct `evidence_class` of the `TRUE`
positive operands**, read from the indicator registry (`PRETEXT, PRESSURE, IDENTITY_CLAIM,
CREDENTIAL_ACTION, PAYMENT_ACTION, DEVICE_ACTION, FINANCIAL_CLAIM, CHANNEL_ARTIFACT`). Three indicators
of the *same* class do **not** satisfy a `min=3` rule; three *independent* classes do. Reported as
`evidence_classes_spanned` + `evidence_class_diversity_met`. Rule count is never treated as diversity.

## 8. Pre-match overrides + directional neutralisation (WP3/WP4 boundary)

DET-001 §18 orders **structural occurrence eligibility + directional neutralisation (step 6)** and
**hard-risk override computation (step 7)** *before* rule evaluation (step 8), so the match itself depends
on both. The authoritative order (programme decision 3, 2026-08-30) is:

> raw observations → **structural occurrence eligibility** (via `observation_refs`) → **raw LIVE-positive
> set** → **hard-risk override computation FROM that live set** → **execute governed `SUPPRESS_INDICATOR`
> through occurrence `observation_refs`** → required-combination evaluation → (WP4) `SUPPRESS_RULE`/
> `CAP_SEVERITY`/`CONTEXT_ONLY`.

WP3 performs exactly this pre-match behaviour — no more:

- **Structural occurrence eligibility (non-overridable), resolved via `observation_refs`.** For each
  positive occurrence the evaluator resolves its `observation_refs` to the backing normalized observation(s)
  (the ONE authoritative source) and reads `status`/`polarity`/`attribution`/`mood`, using **conservative
  agreement** across multiple refs (P3WP3-015):
  - a backing observation that is `NEGATED`/`REPORTED`/`QUOTED`/`HYPOTHETICAL`/purely-`DESCRIPTIVE`, or whose
    `status` is `NOT_OBSERVED`/`NOT_APPLICABLE`, → **NON_LIVE**; only `status == OBSERVED` + `AFFIRMED` +
    `FIRST_PARTY` + non-`DESCRIPTIVE` → **LIVE**; `UNKNOWN`/`AMBIGUOUS` status, an unresolvable ref, or a
    **mixture** of the above → **UNRESOLVED** (never `any(non_live)` masking uncertainty);
  - `NON_LIVE` → `FALSE`; `LIVE` → confidence-gated truth; `UNRESOLVED` → `FALSE` only for an explicit
    absence, else `UNKNOWN`.
  Separate occurrences combine by **three-valued OR** (§5). No override can turn a `NON_LIVE` occurrence
  live. Positives driven `FALSE` by a `NON_LIVE` backing are reported in `neutralised_indicators`.
- **Hard-risk overrides** are computed FROM the **raw structurally-eligible live-positive set** (DET-001 §10;
  "raw `OBSERVED` set" = raw structurally-eligible live positives, never ignoring negation/attribution),
  **before** governed suppression is executed. Because the truth it sees already reflects structural
  eligibility, an override can **never** activate on — nor resurrect — a structurally non-live occurrence.
- **Governed `SUPPRESS_INDICATOR` is EXECUTED at occurrence scope**: an active, applicable negative drives
  only target-positive occurrences sharing a governed `observation_ref` to `FALSE`. Non-empty disjoint ref
  sets identify different occurrences and do not interact. If either side lacks refs, association is unresolved
  and an otherwise-live/uncertain positive is `UNKNOWN`, never global `FALSE`. Per-indicator values then combine
  by three-valued OR. A suppressor is skipped only when explicitly override-blockable and blocked; every current
  directional suppressor is non-blockable. Structural `FALSE` remains authoritative. Active override ids populate
  `active_overrides`; the categories an override blocks populate `suppression.blocked_suppressors` (FR-042).
  GDC-15 remains `MATCHED`: stored `NEGATED_CREDENTIAL_REQUEST` and the positive projection on the disclaimer
  share its ref and are `FALSE`, while the separate live OTP request has a disjoint ref and remains `TRUE`
  (`FALSE OR TRUE = TRUE`). This is a programme-level deterministic safety decision, not new fraud evidence.

**Deferred to WP4** (left unset, never a placeholder): final `SUPPRESS_RULE`/`CAP_SEVERITY`/`CONTEXT_ONLY`
resolution and the `SUPPRESSED` state. WP3 *exposes* the picture (`matched_negative_indicators`,
`suppression.blocked_suppressors`, `suppression.context_only_present`, `active_overrides`) so WP4 can act
deterministically. **Deferred to WP5:** `rule_evidence_strength`, `rule_detection_confidence`,
`governing` — ADR-0006 aggregation quantities.

**Live-positive provenance (P3-WP3 provenance-output amendment, 2026-09-02, required by the WP5 safety
review).** For each MATCHED-positive TRUE indicator, WP3 also emits `live_positive_provenance` — one GROUP
per structurally-LIVE contributing occurrence, each group being that occurrence's governed `observation_refs`
(grouping preserved: one occurrence with two refs is ONE group). It is collected from the **same**
per-occurrence evaluation in `_combine_positive` that already produces the Kleene truth value: only
occurrences whose per-occurrence value is `TRUE` after structural eligibility + confidence gating +
occurrence-associated `SUPPRESS_INDICATOR` contribute; `NEGATED`/`REPORTED`/`QUOTED`/`HYPOTHETICAL`/non-live
`DESCRIPTIVE`/unresolved/neutralised occurrences do not. It **adds no new truth** (it changes no
`evaluation_state`, `required_combination_result`, `matched_positive_indicators`, `neutralised_indicators`,
severity, etc.) — it is provenance EXPOSURE only, so WP5 can prove evidence independence over authoritative
live occurrences (a class→occurrence matching) instead of guessing from flat refs. Canonically ordered
(keys lexical, refs sorted+unique within each group, groups sorted, duplicate-free) for determinism. The
field is an additive optional MINOR amendment to `rule-evaluation-result.schema.json`; GDC-15 exposes only
its live OTP occurrence (`g15-otp-live`), excluding the negated disclaimer (`g15-otp-neg`).

Rule kind (STEP 11): a `SUPPRESSION`-kind rule takes a **distinct pathway** — its `require` is evaluated
over negative operands and the outcome preserved for WP4; it never receives severity, evidence-class
diversity or overrides, so suppression infrastructure can never masquerade as a fraud conclusion. (No
`SUPPRESSION` rule is currently PUBLISHED, so none runs in the live set.)

## 9. Error behaviour + PUBLISHED-only (STEP 10 / STEP 16)

- **Runtime rule trust boundary (remediation 4):** the production API `evaluate_rule_from_governed(rule_id,
  indicator_observations, observations)` resolves the rule to execute **from the verified, immutable
  RuntimeKnowledge, by id, only**. A caller may **not** hand in an arbitrary rule mapping (a non-`str`
  `rule_id` raises `TypeError`). A synthetic mapping marked `PUBLISHED` but absent from RuntimeKnowledge
  cannot execute — an unknown id is `NOT_APPLICABLE{RULE_NOT_FOUND}`. **The production evaluator OWNS
  validation (P3WP3-R3-016):** the ONLY entry points are the governed-*data* `*_from_governed` APIs, which
  validate internally via `build_validated_context` and **fail closed** (`ValueError`) on any defect — there
  is no caller-built, test or forged context to inject and no context-taking method to bypass validation.
  `evaluate_rules_from_governed` iterates only PUBLISHED rules; a rule that exists but is not PUBLISHED is
  `NOT_APPLICABLE{RULE_NOT_PUBLISHED}` (status never silently promoted). Candidate / on-promotion evaluation
  is the **separate, explicitly non-production API** `evaluate_candidate_rule_from_governed(rule_mapping,
  indicator_observations, observations)` / `evaluate_on_promotion_from_governed(rule_id, …)` — never a
  governance bypass.
- **Language scope:** an out-of-scope input yields `NOT_APPLICABLE{LANGUAGE_OUT_OF_SCOPE}`, never benign.
- **Isolation (remediation 5 / candidate schema validation):** a **narrow** set of per-rule data faults
  (a malformed condition operator, or `KeyError`/`ValueError`/`TypeError`/`IndexError` from a rule's own
  data) is caught and returned as `NOT_APPLICABLE` + `evaluation_error{RULE_EVALUATION_ERROR}` — one bad rule
  degrades that rule only and never poisons the batch. The catch is deliberately **not** broad: a
  `RuntimeKnowledge` *integrity* error (a WP2 load-time fault that must refuse the whole bundle) is **never**
  in this set and propagates. A caller-supplied **plain-dict** candidate is validated **inside** the
  isolation boundary against the governed **`rule.schema.json`** before evaluation, so a schema-invalid
  candidate (absent/`null`/invalid `lifecycle.status`, non-object `language_scope`, scalar-where-object,
  malformed `logic`, invalid nested values) degrades to `NOT_APPLICABLE` rather than raising `AttributeError`
  or matching. A frozen RuntimeKnowledge rule (already governed-valid at WP2 load) is accepted without
  re-validation; a production rule's metadata comes from the verified RK record.

## 10. Determinism (STEP 15)

Every returned collection (`matched_positive_indicators`, `evidence_classes_spanned`, `active_overrides`,
`observation_refs`, …) is canonically sorted; the batch is ordered by lexical rule id; the interpreter is
pure over *(observations, RuntimeKnowledge, evaluation_profile)* with no clock/network/LLM. Identical
inputs produce byte-identical results (asserted).

## 11. Legacy runner differences (STEP 20)

The Phase-2 `rule_runner.py` remains valid as the **Phase-2 conformance harness over declared sets** and
is unchanged. WP3 intentionally differs where DET-001 upgrades semantics:

| Aspect | Phase-2 `rule_runner` | WP3 evaluator |
|---|---|---|
| Logic | Boolean closed-world (`indicator in signals`) | Kleene three-valued (`UNKNOWN ≠ NOT_OBSERVED`) |
| `UNKNOWN`/`AMBIGUOUS` | collapses to `FALSE` (benign) | preserved → `INDETERMINATE` |
| Confidence gate | none | `LOW` → `UNKNOWN` (DET-001 §8) |
| Directional suppression | flat-set/global Phase-2 harness semantics | occurrence-associated via governed `observation_refs`; unresolved → `UNKNOWN` |
| Live set | `{PUBLISHED, APPROVED, PEER_REVIEW}` | **PUBLISHED-only** |
| Override set | computed on the reduced set | computed on the **raw `OBSERVED`** set (DET-001 §10) |
| Output | fired / suppressed / effective severity | per-rule state only, no final decision |

Keystone (GDC-11): a PIN prompt with an `AMBIGUOUS` receive frame is `NOT_MATCHED` (benign) under the
boolean runner but **`INDETERMINATE`** under WP3 — asserted by the validator.

## 12. Golden-case rule-layer coverage (STEP 19)

All 15 DET-001 golden cases have their **rule-evaluation layer** reproduced (structural guidance only —
no final risk/classification is asserted): 12 reproduce their declared per-rule states (SUPPRESSED read
as MATCHED-at-rule-layer, since the MATCHED→SUPPRESSED transition is WP4); GDC-02/03/13 reproduce the
"no published rule fires" false-positive regression; GDC-12 is decided at the support gate before the
rule layer. GDC-07/GDC-10 are `live_publishable:false` (governing rule not yet PUBLISHED): live they
route to review; the matrix shows the designed on-promotion behaviour.

## 13. Limitations

- Per-rule only: no aggregation, risk, severity band, classification, confidence band, explanation prose
  or recommended action (WP4–WP6).
- English/`Latn` MVP scope; out-of-scope inputs are `NOT_APPLICABLE` at the rule layer (support-status
  `UNSUPPORTED` is a pipeline decision above this layer).
- No accuracy claim (G-09): the golden/legacy comparisons prove determinism and internal consistency,
  never precision/recall.
- `n_of` is implemented and tested but not exercised by any current live rule.

## 14. Next

**P3-WP4** — suppression + hard-risk override *executor* (final `SUPPRESS_RULE`/`CAP_SEVERITY`/
`CONTEXT_ONLY` resolution, the `SUPPRESSED` state), consuming the per-rule results and the exposed
override/suppression candidates produced here. **Not started.**
