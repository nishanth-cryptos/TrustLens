# DET-001 P3-WP5 — Decision aggregation, risk, confidence & classification

| Field | Value |
|---|---|
| Work package | P3-WP5 |
| Status | **Implemented** — decision-level aggregation only (WP6 explanation/actions deferred) |
| Owner role | Detection Architect |
| Authority | [DET-001](DET-001-deterministic-detection-engine.md) §§4,5,9,10,11, [ADR-0006](../../adr/ADR-0006-risk-and-confidence-aggregation.md), [ADR-0005](../../adr/ADR-0005-rule-execution-model.md) |
| Consumes | The P3-WP4 `RuleEvaluationResult[]` + the immutable P3-WP2 `RuntimeKnowledge` |
| Produces | One decision-level `DecisionResult` (populates most of `detection-result.schema.json`; not a full document) |
| Runtime | `knowledge/runtime/aggregation.py` |
| Gate | Canonical quality-gate **check #15** (`knowledge/validation/validate_wp5_aggregation.py`) |
| Last updated | 2026-09-02 |

> **Scope.** WP5 folds the governed per-rule results into ONE decision across the DET-001 axes the earlier
> work packages deferred: decision severity, matched-evidence strength, risk, detection confidence,
> corroboration, the governing rule, and the final classification. It **does not** re-evaluate rule truth or
> re-run suppression (WP3/WP4), and it builds **no** explanation prose or recommended action (P3-WP6). It
> emits no numeric score and no fraud probability (CONF-001, ADR-0006).

---

## 1. Upstream boundary (WP4 → WP5)

WP5 consumes a tuple of per-rule result dicts conformant to
[`rule-evaluation-result.schema.json`](../../knowledge/schemas/detection/rule-evaluation-result.schema.json),
as produced by `RuleSuppressionExecutor.apply_all(...)`. It reads only already-computed fields:
`kind`, `evaluation_state`, `required_combination_result`, `effective_severity`, `rule_evidence_verdict`,
`matched_positive_indicators`, `evidence_classes_spanned`, `observation_refs`, `active_overrides`,
`extraction_confidence_inputs`, `ambiguities`/`unknowns`, `suppression`, `matched_negative_indicators`,
`neutralised_indicators`, and `evaluation_error`. Decisive-indicator **strength** is the only quantity not
already on the result; WP5 resolves it read-only through `RuntimeKnowledge.indicator(id)['strength']`.

`input_support_status` (DET-001 §3) is decided by the support-status/language gate **above** WP5 and passed
in — WP5 detects no language. The per-rule fields `rule_evidence_strength`, `rule_detection_confidence`,
`governing`, `governing_reason` are reserved by WP1 and **owned by WP5**: WP4 fails closed if any is
pre-populated, so WP5 is the stage that fills them.

## 2. Rule eligibility

A rule is **decision-eligible** (may set severity / strength / risk / govern) iff **all** hold:
`kind == COMPOSITE`, `evaluation_state == MATCHED`, `required_combination_result == TRUE`, and
`effective_severity ∈ {LOW,MEDIUM,HIGH,CRITICAL}`. Everything else is inert for the harmful axes:

- `SUPPRESSED` — auditable, retained in `rule_results`; never governs, never raises severity/risk.
- `INDETERMINATE` — feeds classification/uncertainty; never severity.
- `NOT_MATCHED` (`required=FALSE`) — an affirmative benign clear; never severity.
- `NOT_APPLICABLE` with `evaluation_error` — per-rule degraded: sets `degraded`, caps to review.

## 3. Governing-rule algorithm (deterministic, DET-001 §11)

Among decision-eligible MATCHED rules, the maximum under this **total order** governs:

1. **effective severity** (`LOW<MEDIUM<HIGH<CRITICAL`);
2. **evidence verdict** `SUPPORTED > PARTIAL > HEURISTIC > UNSUPPORTED`;
3. **more distinct `evidence_classes_spanned`**;
4. **lexical `rule_id`** — final deterministic tie-break.

`governing=true` + `governing_reason` are stamped on that one rule. A `SUPPRESSED`/ineligible rule can
never govern. Selection is independent of input/iteration order.

## 4. Decision severity

`decision_severity = max(effective_severity)` over eligible MATCHED rules (else `NONE`). Non-additive;
never inflated by rule count. Equal to `validate_det_design.py`'s severity check, so all 15 golden
severities reproduce by construction.

## 5. Matched-evidence strength (ADR-0006 composite)

Per matched rule: `rule_evidence_strength = min(max decisive-indicator strength, verdict cap)`, then an
active hard-risk override raises a **MODERATE floor**. `verdict cap`: `SUPPORTED→STRONG`, `PARTIAL→MODERATE`,
`HEURISTIC/UNSUPPORTED→WEAK`; decisive strength = max registry `strength` (`WEAK<MODERATE<STRONG`) over the
rule's `matched_positive_indicators`. **Decision `matched_evidence_strength` = the governing rule's**
`rule_evidence_strength` (`NONE` when nothing governs). This honours ADR-0006 §2 (“decisive indicator
strength + verdict + override”) and reproduces every golden value (SUPPORTED→STRONG, PARTIAL→MODERATE).

## 6. Corroboration — proven-independent (DET-001 §11–13)

**One quantity, `proven_independent_evidence_count`, drives BOTH the corroboration band AND the ≥3 path to
HIGH confidence (§7).** WP5 uses ONLY the authoritative WP3 `live_positive_provenance` (the P3-WP3
provenance-output amendment) — per matched-positive TRUE indicator, one grouped occurrence per structurally
LIVE contributing observation set. WP5 never inspects polarity/liveness itself. The count is computed by:

1. gather every live occurrence GROUP for the eligible-MATCHED positives, tagged with the indicator's
   governed `evidence_class`;
2. **union-find** — merge groups that share any `observation_ref` into one provenance **component** (so
   `[A,B]` and `[B,C]` are one component `{A,B,C}`);
3. build the bipartite graph *evidence class × provenance component* (edge iff a matched positive of that
   class has a live occurrence in that component);
4. `proven_independent_evidence_count = ` maximum deterministic bipartite matching size.

Band: `0→NONE, 1→LOW, 2→MEDIUM, ≥3→HIGH`, then **capped at MEDIUM when the governing verdict is
`PARTIAL`/`HEURISTIC`**. Thus three classes from one live occurrence → 1 (LOW), missing provenance → 0
(NONE), three distinct live components → 3 (HIGH). `evidence_class_count` reports the proven count;
`shared_observation_refs` records refs backing more than one occurrence. Missing `live_positive_provenance`
contributes zero independence, so the ≥3 path is then unavailable (HIGH only via an active override). A raw
class-name count never drives HIGH.

**No-fired corroboration** (metadata only — it can never manufacture a MATCHED decision): `LOW` only when
the classification is `INSUFFICIENT_EVIDENCE`, there is **no** unresolved harmful candidate, and a residual
OBSERVED positive exists (GDC-13); otherwise `NONE` (GDC-11 → NONE via unresolved harm; benign clears →
NONE).

## 7. Detection confidence — categorical (ratified WP5 policy)

`detection_confidence ∈ {LOW, MEDIUM, HIGH}` for the governing rule, or `NOT_APPLICABLE` when nothing
fires. **Never a probability.** This section **ratifies the DET-001 §9 clarification** that resolves the
§9-prose / GDC-10 tension:

> **HIGH requires ALL of:** governing evidence verdict `SUPPORTED`; **no** decisive `AMBIGUOUS` evidence;
> **minimum decisive extraction confidence ≥ MEDIUM**; **AND** either **`proven_independent_evidence_count
> ≥ 3`** (§6) OR an **active hard-risk-override** path.
>
> A `MEDIUM` extraction floor by itself never yields HIGH; a `LOW` decisive extraction never yields HIGH.
> Existing source/model verdict caps stay authoritative — `PARTIAL`/`HEURISTIC` never reach HIGH.

This replaces §9's literal “all decisive indicators OBSERVED at HIGH” with a **≥ MEDIUM** decisive floor,
and the ≥3 path uses the **same** `proven_independent_evidence_count` as the corroboration band (§6) — a
raw class-name count can never bypass the provenance/independence cap. It is the only reading consistent
with all 15 golden cases (GDC-10 is `HIGH` with a `MEDIUM` decisive indicator on three **proven-independent**
occurrences). Categorical, not a probability; changes no golden outcome. **degraded caps confidence at
MEDIUM** (Decision 2: HIGH→MEDIUM, MEDIUM→MEDIUM, LOW→LOW). **MEDIUM** is the default for a fired rule that
is not HIGH (e.g. `PARTIAL`); **LOW** (→ `SCAM_PATTERN_SUSPECTED`) arises for the weakest standing
(`HEURISTIC`/`UNSUPPORTED`) or when active benign `CONTEXT_ONLY` nudges a non-HIGH decision down. HIGH, once
met, is sufficient.

## 8. Risk (ADR-0006 matrix v1)

`risk_level = RISK_MATRIX[decision_severity][matched_evidence_strength]`; `severity=NONE ⇒ NONE`. The
matrix in `aggregation.py` is **byte-identical** to `validate_det_design.py`; the WP5 gate asserts the two
copies are equal (drift guard). An illegal `(severity, strength)` cell fails closed (never `NONE`). No
internal ordinal is ever exposed; risk is not a probability, not a percentage, and independent of
confidence.

## 9. Classification state machine

Given `input_support_status`:

- `ERROR → ERROR`; `UNSUPPORTED → UNSUPPORTED`; `INSUFFICIENT_INFORMATION → INSUFFICIENT_EVIDENCE`
  (never benign).
- **Whole-evaluation ERROR** (an explicit `whole_evaluation_errors` entry **or** `input_support_status ==
  ERROR`) → `classification = ERROR`, all axes NONE/NOT_APPLICABLE, a `WHOLE_EVALUATION` diagnostic — never
  a normal decision. `UNSUPPORTED → UNSUPPORTED`; `INSUFFICIENT_INFORMATION → INSUFFICIENT_EVIDENCE` (never
  benign).
- `SUPPORTED`/`PARTIALLY_SUPPORTED`, **ratified rule-local precedence**:
  1. **≥1 eligible harmful MATCHED** → `SCAM_PATTERN_SUSPECTED` if `detection_confidence == LOW`, else
     `SCAM_PATTERN_DETECTED`;
  2. **degraded** (any per-rule error) with no MATCHED → `INSUFFICIENT_EVIDENCE` (route to review);
  3. **unresolved harmful candidate** → `INSUFFICIENT_EVIDENCE`;
  4. **affirmative benign clear** with **no** unresolved harmful candidate → `NO_SCAM_PATTERN`;
  5. otherwise → `INSUFFICIENT_EVIDENCE`.

**Unresolved harmful candidate (rule-local, relevance-based)** = a COMPOSITE that is `INDETERMINATE` with
`required_combination_result == UNKNOWN` **and** carries a WP3-produced decisive `ambiguities` **or**
`unknowns` — i.e. at least one *required* operand was OBSERVED-but-unresolved (AMBIGUOUS / unresolved
structure / LOW-or-absent extraction). WP3 populates those lists **only** for decisive (required-operand)
uncertainties, never for merely-absent (sparse `UNKNOWN`) operands, so a sparse INDETERMINATE is **inert**.
`matched_positive_indicators` alone is **never** decisiveness. This keeps **GDC-05** (`NO_SCAM_PATTERN`:
sibling `TL-CRED-002` is a sparse INDETERMINATE, `amb=0/unk=0`) separate from **GDC-11**
(`INSUFFICIENT_EVIDENCE`: `TL-PAY-001` has an AMBIGUOUS direction) and **GDC-13** (`INSUFFICIENT_EVIDENCE`
via the default, sparse INDETERMINATE inert). Benign clear is **subordinate** to unresolved harm — an
unrelated benign/NOT_MATCHED signal can never clear unresolved harmful evidence.

**Affirmative benign clear (STRICT, rule-local, effect-aware)** = a COMPOSITE with `NOT_MATCHED` +
`required_combination_result == FALSE` (the candidate was affirmatively evaluated false — including an
explicit `NOT_OBSERVED` operand or a WP3 `SUPPRESS_INDICATOR`-neutralised positive that drove `require`
FALSE), **or** a COMPOSITE `SUPPRESSED` (an effective `SUPPRESS_RULE`). The **mere presence** of a
negative-indicator id never clears; **`CONTEXT_ONLY` and `CAP_SEVERITY` never** establish `NO_SCAM_PATTERN`.
It is only consulted when no rule is eligible-MATCHED and no unresolved harm exists, so it can never soften
a live or unresolved finding. (GDC-02/GDC-03 inputs were enriched at cases_version 1.2.0 so a governed rule
reaches `require = FALSE`; outcomes unchanged.)

## 10. Suppressed / indeterminate / error handling

`SUPPRESSED` rules stay in `rule_results` and roll up into `suppressed_indicators`/
`matched_negative_indicators` but never govern or raise risk. Decisive ambiguities/unknowns roll up to the
decision `ambiguities[]`/`unknowns[]`. A per-rule error sets `degraded=true`, **caps confidence at MEDIUM**,
and adds a `SINGLE_RULE` diagnostic to `errors[]`. A whole-evaluation error (§9) yields `classification =
ERROR` with a `WHOLE_EVALUATION` diagnostic. **No failure path ever serialises as `NO_SCAM_PATTERN`.**

## 11. Determinism, input validation & fail-closed

Pure over *(rule_results, RuntimeKnowledge, evaluation_profile, input_support_status)*; no clock, network,
randomness, or model call; inputs are deep-copied, never mutated. **Every incoming WP4 result is
JSON-Schema-validated against `rule-evaluation-result.schema.json`** and then checked for the full WP5
semantic-invariant matrix: the state↔`required_combination_result` pairing (`MATCHED`/`SUPPRESSED`⇒TRUE,
`INDETERMINATE`⇒UNKNOWN, **`NOT_MATCHED`⇒TRUE or FALSE** — TRUE is the legal evidence-class-diversity
fail, `NOT_APPLICABLE`⇒any + `evaluation_error`); `evaluation_error` present **iff** `NOT_APPLICABLE`
(so `MATCHED`+`evaluation_error` fails closed); a valid `rule_evidence_verdict` on every COMPOSITE result;
`live_positive_provenance` keys ⊆ `matched_positive_indicators`; and resolution of **every** governed
reference (matched positive/negative, neutralised, active override) against `RuntimeKnowledge`.
`whole_evaluation_errors` are validated against the promoted `evaluationError` contract. Any violation
raises a typed `AggregationError` — **no raw `KeyError`/`TypeError`/`AttributeError` escapes**, and a
malformed MATCHED never serialises as `NO_SCAM_PATTERN`. Every emitted array — flat, **nested `suppression`**,
and the grouped **`live_positive_provenance`** — is canonically sorted and duplicate-free, `rule_results` is
sorted by `rule_id`, and `errors[]` by a stable key, so a **permutation of valid inputs yields a
structurally identical result** (asserted). A **duplicate whole rule result / duplicate `rule_id`** is invalid upstream corruption and
**fails closed** — never silently de-duplicated. An unknown support status or an illegal matrix cell also
fail closed.

## 12. Result contract

No schema change was required: `detection-result.schema.json` already carries every WP5 field
(`classification`, `decision_severity`, `matched_evidence_strength`, `risk_level`, `detection_confidence`,
`corroboration_summary`, `matched_rules`, `rule_results`, roll-ups, `degraded`, `errors`), and
`rule-evaluation-result.schema.json` reserves the per-rule `governing`/`rule_evidence_strength`. WP5 emits a
`DecisionResult` populating that subset; `explanation`/`recommended_actions` (WP6) and `provenance` (result
assembly) are added downstream. `additionalProperties:false` plus the gate's name-scan structurally forbid
a smuggled probability/score, and the gate asserts **no WP6 field is emitted**.

## 13. Golden-case mapping

All 15 golden decision cases are replayed end-to-end (WP3 → WP4 → WP5) by the gate; the `expected` axes are
the binding oracle and are unchanged by this WP. `live_publishable:false` cases (GDC-07, GDC-10) are
asserted through the explicit **on-promotion** path (their governing rule is not yet PUBLISHED); the live
PUBLISHED-only engine routes them to review.

| Case | Classification | Severity | Strength | Risk | Confidence | Corrob. | Governing |
|---|---|---|---|---|---|---|---|
| GDC-01 | SCAM_PATTERN_DETECTED | CRITICAL | STRONG | CRITICAL | HIGH | HIGH | TL-CRED-001 |
| GDC-02 | NO_SCAM_PATTERN | NONE | NONE | NONE | n/a | NONE | — |
| GDC-03 | NO_SCAM_PATTERN | NONE | NONE | NONE | n/a | NONE | — |
| GDC-04 | SCAM_PATTERN_DETECTED | CRITICAL | STRONG | CRITICAL | HIGH | MEDIUM | TL-PAY-001 |
| GDC-05 | NO_SCAM_PATTERN | NONE | NONE | NONE | n/a | NONE | — |
| GDC-06 | SCAM_PATTERN_DETECTED | CRITICAL | STRONG | CRITICAL | HIGH | HIGH | TL-CRED-001 |
| GDC-07¹ | SCAM_PATTERN_DETECTED | HIGH | MODERATE | HIGH | MEDIUM | MEDIUM | TL-MAL-003 |
| GDC-08 | NO_SCAM_PATTERN | NONE | NONE | NONE | n/a | NONE | — |
| GDC-09 | SCAM_PATTERN_DETECTED | HIGH | MODERATE | HIGH | MEDIUM | MEDIUM | TL-CRYP-001 |
| GDC-10¹ | SCAM_PATTERN_DETECTED | HIGH | STRONG | HIGH | HIGH | HIGH | TL-JOB-003 |
| GDC-11 | INSUFFICIENT_EVIDENCE | NONE | NONE | NONE | n/a | NONE | — |
| GDC-12 | UNSUPPORTED | NONE | NONE | NONE | n/a | NONE | — |
| GDC-13 | INSUFFICIENT_EVIDENCE | NONE | NONE | NONE | n/a | LOW | — |
| GDC-14 | SCAM_PATTERN_DETECTED | CRITICAL | STRONG | CRITICAL | HIGH | HIGH | TL-AUTH-001 |
| GDC-15 | SCAM_PATTERN_DETECTED | CRITICAL | STRONG | CRITICAL | HIGH | MEDIUM | TL-CRED-001 |

¹ On-promotion (`live_publishable:false`): live PUBLISHED-only, these route to review.

## 14. Runtime API

- `aggregate_decision(rule_results, *, input_support_status, rk, profile=None, language, script, whole_evaluation_errors=()) -> DecisionResult` — proven-independence rides on each result's WP3 `live_positive_provenance`; WP5 builds no provenance of its own.
- `evaluate_decision_from_governed(rk, indicator_observations, observations, *, input_support_status, profile, language, script, whole_evaluation_errors=())` — composes WP3 → WP4 → WP5.
- `DecisionResult.as_decision_dict()` — the WP5-owned subset of the detection-result contract (no WP6 field, no numeric score).
- `RISK_MATRIX`, `AggregationError` are exported for tests/introspection.

## 15. Limitations & WP6 deferral

Decision-level only: **no** explanation prose, **no** recommended actions, **no** evidence-basis narrative
(all P3-WP6); **no** provenance assembly (result assembly). No accuracy claim (G-09) — the golden replay
proves determinism and internal consistency, never precision/recall. English/`Latn` MVP scope; support
status is decided upstream. `n_of`, `HEURISTIC`/`UNSUPPORTED` verdicts and the LOW confidence band are
implemented and unit-tested but not exercised by any current live golden case. The proven-independence proof
is conservative by governed design (Decision 3): a matched-positive indicator whose live decisive
occurrence cannot be proven single-ref contributes zero independence; it never recomputes WP3 liveness.

## 16. Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-09-02 | Initial WP5 aggregation implementation (gate check #15). |
| 1.1 (remediation) | 2026-09-02 | Adversarial-review remediation: single `proven_independent_evidence_count` (class→occurrence matching over unambiguous single-ref governed occurrences) drives both corroboration band and the ≥3 HIGH path; degraded caps confidence at MEDIUM; explicit whole-evaluation ERROR; rule-local unresolved-harm (ambiguities OR unknowns, never matched positives alone); STRICT effect-aware benign clear (NOT_MATCHED+FALSE or SUPPRESSED only); benign subordinate to unresolved harm; JSON-Schema + semantic input validation → typed `AggregationError`; nested-suppression/error canonicalisation. GDC-02/03 inputs enriched (golden cases_version 1.2.0), outcomes unchanged. |
| 1.2 (provenance contract) | 2026-09-02 | Consumes the authoritative WP3 `live_positive_provenance` (P3-WP3 provenance-output amendment); proven-independence is now a **union-find over shared observation_refs into components** then class×component matching (the single-ref guess is removed). Full WP5 semantic-validation matrix: state↔required pairing incl. the legal `NOT_MATCHED`+TRUE diversity-fail, `evaluation_error` placement, verdict presence, provenance-key membership, and resolution of every governed reference (positive/negative/neutralised/override); `whole_evaluation_errors` validated against the promoted `evaluationError` contract. Additive MINOR schema field + fixtures. `suppression.py`, ADR-0006, and golden outcomes unchanged. |

## 17. Next

**P3-WP6** — provenance-constrained explanation builder + recommended-action mapper, consuming this
`DecisionResult`. **Not started.**
