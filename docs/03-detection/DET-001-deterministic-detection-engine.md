# DET-001 — Deterministic Detection Engine Design

| Field | Value |
|---|---|
| Document ID | DET-001 |
| Version | 1.0 (design) |
| Status | **Draft — Phase 3 design gate** |
| Owner role | Detection Architect |
| Dependencies | KB-001, KB-002, RESEARCH-004 §7, [CONF-001](../00-program/conflict-register.md), [CONF-002](../00-program/conflict-register.md), [CONF-003](../00-program/conflict-register.md), [ADR-0003](../../adr/ADR-0003-rule-representation-format.md), [ADR-0004](../../adr/ADR-0004-knowledge-storage-architecture.md), [ADR-0014](../../adr/ADR-0014-language-and-script-strategy.md), [ADR-0015](../../adr/ADR-0015-evidence-hierarchy-and-official-alternate-provenance.md), [ADR-0005](../../adr/ADR-0005-rule-execution-model.md), [ADR-0006](../../adr/ADR-0006-risk-and-confidence-aggregation.md) |
| Feeds | AI-001 (Phase 4), ARCH-001 (Phase 5), UX-001/REPORT-001 (Phase 7), PLAN-001 (Phase 8) |
| Consumes | The immutable published knowledge bundle (ADR-0004) |
| Last updated | 2026-08-29 |

> **Scope of this document.** DET-001 is a **design specification**, not an implementation. It defines
> *what a TrustLens detection result means* and the deterministic rules by which one is produced, so
> that the production engine (Phase 9) can be built to a frozen contract. It writes no production engine
> and changes no Phase-2 knowledge semantics. Two ADRs freeze its decisions:
> [ADR-0005](../../adr/ADR-0005-rule-execution-model.md) (execution model) and
> [ADR-0006](../../adr/ADR-0006-risk-and-confidence-aggregation.md) (risk/confidence mathematics).
> Machine-checkable artefacts accompany it. The result contracts were **promoted at P3-WP1** to the
> runtime schema tree — [`knowledge/schemas/detection/detection-result.schema.json`](../../knowledge/schemas/detection/detection-result.schema.json)
> and [`knowledge/schemas/detection/rule-evaluation-result.schema.json`](../../knowledge/schemas/detection/rule-evaluation-result.schema.json)
> (see [`contracts/README.md`](contracts/README.md) and [`DET-001-WP1-runtime-contracts.md`](DET-001-WP1-runtime-contracts.md)) —
> alongside [`golden-decision-cases-v1.json`](golden-decision-cases-v1.json),
> [`validate_det_design.py`](validate_det_design.py) (design consistency) and
> [`../../knowledge/validation/validate_runtime_contracts.py`](../../knowledge/validation/validate_runtime_contracts.py) (contract validation).

---

## 1. Purpose and the four separated quantities

Phase 2 delivered a validated, source-traceable knowledge base but computed no decision: the Phase-2
`rule_runner` returns only *matched / suppressed / effective-severity* over a **declared** signal set,
using closed-world Boolean logic. DET-001 turns that knowledge base into a **deterministic decision
model**: RAW/NORMALISED INPUT → OBSERVATIONS → INDICATOR OBSERVATIONS → RULE EVALUATION →
SUPPRESSION/OVERRIDES → RULE RESULTS → AGGREGATION → RISK/CONFIDENCE/CLASSIFICATION → EXPLANATION →
RECOMMENDED ACTION.

The governing constraint is `MP §10` / [CONF-001](../00-program/conflict-register.md): **do not collapse
distinct concepts into one arbitrary percentage.** DET-001 keeps four quantities strictly separate and
never averages them (glossary §1):

| Quantity | Question it answers | Kind | User-visible |
|---|---|---|---|
| **Severity** | *If this pattern is genuine, how harmful/urgent is the requested action?* | ordinal `LOW..CRITICAL`, a property of the scam class | yes |
| **Matched-evidence strength** | *How strong is the evidence that actually matched?* | ordinal `WEAK..STRONG` | internal → feeds risk |
| **Risk level** | *What is the exposure for THIS submission?* | ordinal band = f(severity, evidence strength) | yes (as a band) |
| **Detection confidence** | *How much do we trust our own analysis of this submission?* | categorical `LOW/MEDIUM/HIGH` | yes |

The four terms **extraction confidence**, **rule evidence strength**, **detection confidence** and
**risk/severity** are different concepts and are never conflated (see §8–§9, §12). No quantity is ever
rendered as a fraud probability. TrustLens will not say *"93% chance this is fraud"* — no calibrated
statistical model supports such a claim, and G-09 (no labelled corpus) makes one unobtainable in the
MVP.

## 2. The canonical detection result (STEP 2)

One evaluation produces one **detection result**, whose shape is fixed by the runtime contract
[`knowledge/schemas/detection/detection-result.schema.json`](../../knowledge/schemas/detection/detection-result.schema.json). It is designed for
**full reproducibility and full explanation**. Fields (existing repository conventions preferred over
the placeholder names in the brief):

- **Identity / timing** — `result_schema_version`, `evaluation_id`, `timestamp`, `input_id`.
- **Support** — `language`, `script`, `input_support_status` (§3).
- **Decision** — `classification` (§4), `severity`, `matched_evidence_strength`, `risk_level`,
  `detection_confidence` (§5, §9).
- **Provenance (reproducibility, §17/STEP 23)** — `bundle_version`, `bundle_content_digest` (SHA-256,
  ADR-0004), `engine_version`, `evaluation_profile` (the pinned thresholds and matrix/policy ids),
  `component_versions` (rule schema, indicator registry, families, negative library, taxonomy,
  dimensions, extraction contracts). Every fired rule echoes its `rule_version`.
- **Findings** — `rule_results[]` (§6), `matched_positive_indicators`, `matched_negative_indicators`,
  `suppressed_indicators`, `active_overrides`, `corroboration` (§11).
- **Explanation & action** — `explanation` (§13), `recommended_actions[]` (§14).
- **Honesty** — `limitations`, `unknowns`, `ambiguities`, `degraded`, `errors[]`.

## 3. Input support outcomes — decided FIRST (STEP 3)

Before any fraud reasoning, the pipeline decides `input_support_status`. **UNKNOWN is not SAFE**: none
of these values may be mapped to a benign or low-risk outcome.

| Status | Meaning | Consequence |
|---|---|---|
| `SUPPORTED` | `en` / `Latn`, evaluable observation frame | proceed to full evaluation |
| `PARTIALLY_SUPPORTED` | supported language but a required channel is missing (e.g. an attached screenshot could not be OCR'd) | evaluate available evidence; cap confidence; list the gap |
| `UNSUPPORTED` | language/script outside MVP scope (G-08, [ADR-0014](../../adr/ADR-0014-language-and-script-strategy.md)) | **do not evaluate**; classification `UNSUPPORTED`; never benign |
| `INSUFFICIENT_INFORMATION` | supported input, too few observations for any rule combination | classification `INSUFFICIENT_EVIDENCE`; route to review |
| `ERROR` | fail-closed integrity/exception state (§16) | refuse to evaluate; surface the failure |

Language/script support is a property of the **rule** (`language_scope`) and the bundle, not a guess:
a non-English message is flagged `UNSUPPORTED` per NFR-009 rather than silently scored low. **AMBIGUOUS**
is deliberately *not* an input-support value — it is a per-observation/per-finding epistemic state (e.g.
unresolved payment direction) handled at the rule layer (§7) and surfaced in `ambiguities[]`.

## 4. Classification vocabulary (STEP 4)

`classification` answers *"what does TrustLens conclude from the observable evidence?"* — deliberately
**distinct from severity** (harm if genuine). A weakly observed credential-theft signal may be
`SCAM_PATTERN_SUSPECTED` (low confidence) yet carry `CRITICAL` severity; the two are not collapsed.

| Classification | Meaning |
|---|---|
| `NO_SCAM_PATTERN` | supported input; no composite rule fires (or all fired rules suppressed); benign evidence may be present |
| `INSUFFICIENT_EVIDENCE` | supported input; no rule combination satisfied and/or an unresolved decisive ambiguity. Explicitly **not** "safe" |
| `SCAM_PATTERN_SUSPECTED` | a rule fired but `detection_confidence = LOW` |
| `SCAM_PATTERN_DETECTED` | a rule fired at `detection_confidence` MEDIUM/HIGH |
| `UNSUPPORTED` | outside MVP language/script scope; not evaluated |
| `ERROR` | fail-closed state |

Classification is thus the pair *(is a recognised pattern present?) × (how well-evidenced is that
conclusion?)* — it never re-encodes severity. The Phase-2 seed corpus's coarse `phase2_expected_outcome`
labels (`NO_FINDING`, `HIGH`, `CRITICAL`, `INSUFFICIENT_EVIDENCE`) map onto this vocabulary as
`NO_SCAM_PATTERN` / `SCAM_PATTERN_*` / `INSUFFICIENT_EVIDENCE`; where a corpus label and a fired rule's
severity disagree (e.g. M-003 labelled `HIGH` but fires the `CRITICAL` rule TL-CRED-001), DET-001 derives
severity from the fired rule and treats the corpus band as the coarser Phase-2 shorthand it is. The field
was **renamed `expected_outcome → phase2_expected_outcome`** at the Phase-3 closure (GATE-009) precisely so
it can never be read as DET-001 runtime severity — the governed rule is authoritative for Phase-3 severity,
and the golden cases carry the governed-rule severity (enforced by `validate_det_design.py`).

## 5. Risk and severity (STEP 5) — categorical, decomposable, not a probability

**Decision: categorical output, with a *derived* ordinal risk band; no user-visible numeric score, no
0–100 scale.** Rationale in [ADR-0006](../../adr/ADR-0006-risk-and-confidence-aggregation.md).

- **Severity** preserves the existing repository ordinal `LOW | MEDIUM | HIGH | CRITICAL` (rule schema),
  plus `NONE` when nothing fires. It is a property of the scam *class*, fixed per rule. The **effective**
  severity of a fired rule is `min(declared severity, evidence.severity_cap, any CAP_SEVERITY suppressor)`
  — the mechanism that lets a `PARTIAL`-evidence rule be capped (RESEARCH-004 §7). Decision severity is
  the **maximum effective severity across fired rules** (§10); it is never inflated by rule count.
- **Matched-evidence strength** `WEAK | MODERATE | STRONG` is derived from the decisive indicators'
  `strength`, the governing rule's evidence `verdict` (`SUPPORTED > PARTIAL > HEURISTIC`), and whether a
  hard-risk override is active. It is the "strength of matched evidence" the glossary names as an input
  to risk.
- **Risk level** `NONE | LOW | MEDIUM | HIGH | CRITICAL` is a **fixed ordinal lookup** of
  `(severity × matched-evidence strength)` — the ADR-0006 risk matrix. It is bounded, decomposable (you
  can point at the cell and the governing rule), reproducible, and **user-visible as a band**. It is
  **not** a probability, **not** a percentage, and **not** an average of confidence.

If a numeric index is used internally to index the matrix, it is an implementation detail, never
exposed, and carries no probabilistic meaning. This directly implements CONF-001's resolution: map the
research package's 0–100 numbers to the severity ordinal (done in Phase 2), and **derive** risk at
evaluation time from severity × evidence strength (done here).

## 6. The rule result (STEP 6)

Each evaluated rule yields a structured result — shape fixed by the runtime contract
[`knowledge/schemas/detection/rule-evaluation-result.schema.json`](../../knowledge/schemas/detection/rule-evaluation-result.schema.json):
`rule_id`, `rule_version`, `kind`, `evaluation_state`, `required_combination_result`,
`matched_positive_indicators`, `matched_negative_indicators`, `neutralised_indicators`,
`evidence_classes_spanned` + `evidence_class_diversity_met`, `suppression` (effect, caps, blocked),
`active_overrides`, `extraction_confidence_inputs`, `rule_evidence_verdict`, `rule_severity_declared` +
`effective_severity`, `rule_confidence`, `explanation_fragment`, and echoed `source_references`.

`evaluation_state` ∈ `MATCHED | NOT_MATCHED | INDETERMINATE | SUPPRESSED | NOT_APPLICABLE`. The new
state relative to Phase 2 is **INDETERMINATE**: a required operand was `UNKNOWN`/`AMBIGUOUS`, so the rule
is neither matched nor cleared (§7). A rule is **never forced to MATCH/NO-MATCH when a required
observation is UNKNOWN.**

## 7. Three-valued logic — UNKNOWN ≠ NOT_OBSERVED (STEP 7)

Boolean logic is **not** sufficient. The Phase-2 contracts already model five epistemic states
(`OBSERVED`, `NOT_OBSERVED`, `UNKNOWN`, `AMBIGUOUS`, `NOT_APPLICABLE`); the Phase-2 `rule_runner`
collapses them to Boolean because its inputs are *declared* sets. The DET-001 engine evaluates rules in
**Kleene strong three-valued logic** to avoid accidental closed-world reasoning:

- Map each operand: `OBSERVED → TRUE`; `NOT_OBSERVED`/`NOT_APPLICABLE → FALSE`; `UNKNOWN`/`AMBIGUOUS →
  UNKNOWN`.
- Observation sets are **sparse** (programme decision, 2026-08-30): an operand with **no** observation is
  `UNKNOWN` (missing information is not negative evidence), **not** `FALSE`. Only an *explicit*
  `NOT_OBSERVED`/`NOT_APPLICABLE` is `FALSE`. There is no complete-frame assumption — an extractor is not
  required to emit an observation for every indicator.
- `all_of`: `FALSE` if any `FALSE`; `TRUE` if all `TRUE`; else `UNKNOWN`.
- `any_of`: `TRUE` if any `TRUE`; `FALSE` if all `FALSE`; else `UNKNOWN`.
- `n_of(n)`: `TRUE` if `#TRUE ≥ n`; `FALSE` if `#TRUE + #UNKNOWN < n`; else `UNKNOWN`.
- `require = TRUE` **and** evidence-class diversity met → `MATCHED`; `require = FALSE` → `NOT_MATCHED`;
  `require = UNKNOWN` → `INDETERMINATE`.

Worked contrast (STEP 7): with `UPI_PIN_PROMPT = OBSERVED`, a receive-money context that is `UNKNOWN`
yields TL-PAY-001 `require = UNKNOWN → INDETERMINATE` (route to review), whereas a receive context that
is `NOT_OBSERVED` yields `require = FALSE → NOT_MATCHED` (cleared). The two are not the same — see
golden cases GDC-04 / GDC-05 / GDC-11.

This is a **design upgrade over the Phase-2 runner, not a change to it**: the runner remains valid as the
Phase-2 conformance harness over declared indicator sets. No rule file changes.

## 8. Extraction confidence → evaluation (STEP 8)

Extraction confidence (`HIGH/MEDIUM/LOW` per indicator observation) is **not multiplied** into anything.
It **gates** whether an indicator counts as `OBSERVED`, via the pinned `extraction_confidence_gate`
(MVP default **MEDIUM**):

- `HIGH` / `MEDIUM` → the indicator is `OBSERVED` (truth `TRUE`) — eligible normally.
- `LOW` → the indicator is treated as **UNKNOWN**, not `FALSE`. It cannot alone establish a match; a rule
  that needs it becomes `INDETERMINATE` (preserving uncertainty) unless another `OBSERVED` operand
  satisfies the branch.
- `UNKNOWN` extraction → `UNKNOWN`.

Hard-risk patterns additionally require their **decisive** indicators to be `OBSERVED` at ≥ gate (§10):
a hard-risk override cannot be forced off a `LOW`-confidence read. Extraction confidence then also feeds
the detection-confidence band (§9). This keeps three distinct ideas apart: *did we read the text
correctly* (extraction confidence) vs *is the rule's source trustworthy* (evidence verdict) vs *how sure
are we of the overall finding* (detection confidence).

## 9. Detection confidence (STEP 9) — separate from severity

`detection_confidence ∈ LOW | MEDIUM | HIGH` (or `NOT_APPLICABLE` when nothing fires). It is a
deterministic categorical function — **not a calibrated probability** — of:

1. **completeness** of the required combination (any `INDETERMINATE` decisive branch lowers it);
2. **extraction confidence** of the decisive indicators (their minimum gates the band);
3. **corroboration breadth** — the count of *independent* evidence classes/families among decisive
   positives (§11);
4. **evidence verdict** of the governing rule (`PARTIAL`/`HEURISTIC` cap it at `MEDIUM`);
5. **ambiguity** — any `AMBIGUOUS` decisive observation caps it and is listed in `ambiguities[]`;
6. **suppressive context** — active `CONTEXT_ONLY` benign evidence nudges it down, but never below the
   floor implied by an active hard-risk override.

Banding (fixed policy, ADR-0006) — **one normative rule per band** (WP5 implements this exactly;
[DET-001-WP5](DET-001-WP5-decision-aggregation.md) §7):

- **HIGH** — **all** of: governing verdict `SUPPORTED`; **no** decisive `AMBIGUOUS` evidence; **minimum**
  decisive extraction confidence `≥ MEDIUM`; **and either** `proven_independent_evidence_count ≥ 3` (a
  class→occurrence bipartite matching over the authoritative WP3 `live_positive_provenance`, **never** a raw
  class-name count) **or** an active governed hard-risk override. `degraded = true` caps to `MEDIUM`;
  `PARTIAL`/`HEURISTIC` cannot reach HIGH; a `LOW` decisive extraction cannot reach HIGH.
- **MEDIUM** — a fired rule that does not meet the HIGH rule and is not LOW (e.g. `SUPPORTED` with < 3
  proven-independent supports and no override, or `PARTIAL`).
- **LOW** (→ `SCAM_PATTERN_SUSPECTED`) — governing verdict `HEURISTIC`/`UNSUPPORTED`, or active benign
  `CONTEXT_ONLY` on the governing rule.

The **same** `proven_independent_evidence_count` drives the corroboration band and the HIGH path, so a raw
class count can never bypass the provenance/independence cap. This supersedes any earlier phrasing that said
"all decisive indicators at HIGH" / "every indicator high confidence"; the `≥ MEDIUM` floor is the only
reading consistent with all 15 golden cases (GDC-10 is `HIGH` on three proven-independent occurrences with a
`MEDIUM` decisive indicator). It remains categorical (never a probability) and changes no golden outcome.

**What "HIGH confidence" means operationally:** every decisive indicator the conclusion rests on was
extracted at **at least `MEDIUM`** confidence (none at `LOW`); the governing rule is backed by a verified
official source (`SUPPORTED` verdict); and the conclusion is corroborated by **≥ 3 proven-independent
governed evidence supports** (the class→occurrence matching over `live_positive_provenance`) **or** by an
active, evidence-backed hard-risk override that reflects a categorical official boundary — with no
unresolved ambiguity and no degraded rule. It does **not** require every indicator at `HIGH`, and it does
**not** mean a statistical probability of fraud.

## 10. Hard-risk overrides (STEP 10)

Phase 2 defines six overrides in the negative-indicator library. DET-001 fixes their behaviour precisely
(they are not omnipotent — they do exactly what the evidence supports):

- **Computed on the raw `OBSERVED` signal set**, per applicable rule/family, and only when their decisive
  indicators are `OBSERVED` at ≥ the extraction-confidence gate (a `LOW`-confidence decisive read leaves
  the override **inactive**). "Raw `OBSERVED` set" here means the **raw structurally-eligible LIVE positives**
  (programme decision, 2026-08-30): it does **not** mean ignoring negation, reported speech or quotation. A
  structurally non-live occurrence (`NEGATED`/`REPORTED`/`QUOTED`/`HYPOTHETICAL`/`DESCRIPTIVE`, per
  `observation.schema.json`) is not part of the raw live set, so an override can never be activated by it and
  can never turn it into a live positive.
- **They gate suppression, nothing else.** When active they **block** the listed soft-suppression
  categories (`EDUCATIONAL_SAFETY`, `CUSTOMER_SUPPORT_SAFETY`, `LEGIT_SERVICE_COMMS`,
  `LEGIT_PAYMENT_DIRECTION`, `IT_SUPPORT`, `USER_INITIATED`, `ALLOWLIST_DOMAIN`, `REPORTED_SCAM`), and
  the block is **recorded** in the explanation (FR-042). They do **not** block `NEGATION_DIRECTIONAL`
  (`SUPPRESS_INDICATOR`) or `BENIGN_CONTEXT` (`CONTEXT_ONLY`).
- **They do not set severity.** An override does not manufacture `CRITICAL`; the rule fires at its own
  effective severity. TL-PAY-001 + `HR_UPI_PIN_TO_RECEIVE` is `CRITICAL` because *TL-PAY-001* is
  `CRITICAL`; TL-CRED-001 + `HR_OTP_DISCLOSURE_REQUEST` is `CRITICAL` because *that rule* is.
- **They do not bypass combination requirements.** The rule's `require` and `min_evidence_classes` must
  still be satisfied; an override over a single-class credential request still yields `NOT_MATCHED`
  (CONF-002 holds).
- **Conflicting context can still force UNKNOWN.** If a decisive required indicator is `AMBIGUOUS`/
  `UNKNOWN`, the rule is `INDETERMINATE` regardless of an override — an override cannot conjure a match
  from missing evidence.

Answers to the STEP 10 questions, in order: an override **can** block benign suppression (that is its
purpose); it **cannot** by itself produce `CRITICAL`; it **does not** change confidence directly (it sets
a floor by preventing wrongful suppression); it **does not** bypass combination requirements; it **only**
preserves a live positive against decoy suppression; a `LOW`-confidence underlying observation leaves it
**inactive**; and conflicting context **can** still force `UNKNOWN`.

## 11. Negative indicators & aggregation (STEP 11–13)

**Suppression semantics** are preserved exactly from negative-indicator-library `2.0.0` and its resolution
order (programme authority decision, 2026-08-31):

1. **Structural occurrence eligibility (non-overridable).** Resolved from the normalized
   `observation.schema.json` via `observation_refs`: a backing observation that is `NEGATED`/`REPORTED`/
   `QUOTED`/`HYPOTHETICAL`/purely-`DESCRIPTIVE`, or whose `status` is `NOT_OBSERVED`/`NOT_APPLICABLE`, is
   structurally non-live and never projects to a live positive; `UNKNOWN`/`AMBIGUOUS` status (or an
   unresolvable association) is `UNRESOLVED` (operand stays `UNKNOWN`). This is a semantic property of the
   occurrence, not a negative-library effect, and cannot be overridden.
2. **Overrides computed FROM the raw structurally-eligible live-positive set.** An override can never
   resurrect a structurally non-live occurrence.
3. **Governed `SUPPRESS_INDICATOR` is EXECUTED at the WP3 pre-match stage at occurrence scope:** an active,
   applicable negative neutralises only target-positive occurrences sharing a governed `observation_ref`.
   Explicitly disjoint occurrences do not interact; a missing ref on either side leaves association unresolved
   and makes an otherwise-live/uncertain target occurrence `UNKNOWN`, never global `FALSE`. Occurrences for the
   same indicator then combine by three-valued OR (`FALSE + TRUE → TRUE`; `FALSE + UNKNOWN → UNKNOWN`). A
   suppressor is skipped only when **explicitly** override-blockable and blocked by an active override. Every
   directional suppressor in the library is non-blockable; an override cannot rescue an associated occurrence.
   Structural non-live remains authoritative and can never be resurrected.
4. (WP4) `SUPPRESS_RULE` cancels a matched rule (→ `SUPPRESSED`) unless its category is blocked.
5. (WP4) `CAP_SEVERITY` caps effective severity ordinally unless blocked.
6. `CONTEXT_ONLY` records benign evidence, never changes the finding, feeds confidence down slightly.

The decoy *"We will never ask for your OTP. Now send me the OTP you just received"* keeps its live hard-risk
request detectable because GDC-15 explicitly stores two occurrences. `NEGATED_CREDENTIAL_REQUEST` references
the disclaimer occurrence and neutralises only its positive projection; the separate affirmed live request has
a disjoint ref and survives. Their positive values combine `FALSE OR TRUE = TRUE`; the override independently
blocks the educational/support soft suppressors. A negated-only request remains structurally non-live and no
override can resurrect it. This occurrence-association rule is a programme-level deterministic safety decision
addressing ambiguous/global suppression, not a newly sourced fraud fact.

**Multi-rule aggregation (STEP 12).** Not additive. Decision severity = max effective severity across
fired rules; the **governing rule** is the one setting it (ties broken by `SUPPORTED > PARTIAL`, then more
independent evidence classes, then lexical id, for determinism). Matched-evidence strength and confidence
draw on corroboration but **do not double-count** rules sharing the same underlying indicator.

**Cross-rule corroboration (STEP 13).** Measured over **independent evidence classes / indicator
families**, never rule count. Five rules all triggered by one URL keyword corroborate weakly (one class:
`CHANNEL_ARTIFACT`); five independent observations — authority claim, threat, external URL, credential
request, OTP-disclosure request — corroborate strongly (four+ classes). `corroboration.band` is derived
from the distinct-class count and feeds confidence. This is why GDC-06 (KYC chain, four independent
classes) reaches `HIGH` corroboration even though its capped `PARTIAL` KYC rule contributes only at
`MEDIUM` severity.

## 12. Payment-direction semantics (STEP 14)

`payment_direction ∈ USER_PAYS | USER_RECEIVES | UNKNOWN_DIRECTION` is protected end-to-end. `RECEIVE_FRAMING`
is emitted **only** when the text settles `USER_RECEIVES`; presence of currency or "UPI" never sets
direction. Therefore:

- *"Enter PIN to pay merchant"* → `USER_PAYS` → `RECEIVE_FRAMING = NOT_OBSERVED` → TL-PAY-001
  `NOT_MATCHED` (legitimate; GDC-05).
- *"Enter PIN to receive refund"* → `USER_RECEIVES` → `RECEIVE_FRAMING = OBSERVED` → TL-PAY-001 `MATCHED`,
  `HR_UPI_PIN_TO_RECEIVE` active (hard-risk; GDC-04).
- *"Enter PIN for ₹5,000"* → `UNKNOWN_DIRECTION` → `RECEIVE_FRAMING = AMBIGUOUS` → TL-PAY-001
  `INDETERMINATE` → `INSUFFICIENT_EVIDENCE`, with `payment_direction unresolved` in `ambiguities[]`
  (GDC-11). The third is **never** silently treated as the first or the second.

## 13. Explanation model (STEP 15)

The explanation is **structured data first**; prose is rendered from it (Phase 7 owns wording). Every
result answers: *what* was detected, *why*, which exact observations/spans supported it, which indicators
matched, which suppressors were considered (and whether applied or blocked), which overrides applied,
which rules fired, how strong detection confidence was and why it was limited, what remains unknown, which
official evidence supports the rules, and what to do next.

**Explanation-provenance constraint (hard rule).** The narrative may assert an official fact **only** if
that fact appears as a stored `quote` in a matched rule's `source_references`. TrustLens generates no
unsupported factual claims. It prefers concrete, sourced statements — e.g. *"TrustLens identified a request
to enter a UPI PIN in a receive-money context. CERT-In states you do not need a UPI PIN or OTP to receive
money."* — over opaque text such as *"this looks suspicious."* Citations carry issuing body,
`verification_status`, ADR-0015 evidence class and the quote, so a reader can verify independently.

## 14. Recommended-action model (STEP 16)

Classification and recommended action are separate. Actions come from a **controlled vocabulary**
(`DO_NOT_SHARE_CREDENTIALS`, `DO_NOT_ENTER_PIN`, `DO_NOT_TRANSFER_MONEY`, `DO_NOT_INSTALL_APP`,
`DO_NOT_CONNECT_WALLET`, `DO_NOT_DIAL_CODE`, `DISCONNECT_REMOTE_ACCESS`, `VERIFY_INDEPENDENTLY`,
`CONTACT_BANK`, `CONTACT_OFFICIAL_CHANNEL`, `REPORT_CYBERCRIME`, `PRESERVE_EVIDENCE`,
`PROCEED_WITH_CAUTION`, `SEEK_HUMAN_REVIEW`, `RESUBMIT_IN_SUPPORTED_LANGUAGE`). Each action **must trace**
to a fired rule, an active override, or a matched family — no high-stakes instruction is emitted beyond
the evidence. Mapping is deterministic (e.g. credential family / OTP override → `DO_NOT_SHARE_CREDENTIALS`;
receive+PIN override → `DO_NOT_ENTER_PIN`; remote-access override → `DISCONNECT_REMOTE_ACCESS`;
`UNSUPPORTED` → `RESUBMIT_IN_SUPPORTED_LANGUAGE` + `SEEK_HUMAN_REVIEW`). `VERIFY_INDEPENDENTLY` derives
from the rule's own `verification_steps`.

## 15. UNKNOWN / AMBIGUOUS output (STEP 17)

TrustLens must be comfortable saying *"insufficient information"* or *"suspicious indicators exist, but
payment direction could not be established."* No input is forced into benign-or-scam. `INSUFFICIENT_EVIDENCE`
carries an `unknowns[]`/`ambiguities[]` list naming exactly what is missing, plus `SEEK_HUMAN_REVIEW`.
This is a first-class outcome, not a failure.

## 16. Determinism, security & fail-closed (STEP 23, STEP 25)

**Determinism.** For identical *(input observations, published bundle, engine version, evaluation
profile)* the result is identical. Every input to the decision is pinned in `provenance`
(`bundle_content_digest`, `engine_version`, `evaluation_profile` with the confidence gate, risk-matrix id
and confidence-policy id, and per-component versions). No hidden configuration and **no LLM judgement**
participate in the deterministic scoring path (§17).

**Live rule set.** The engine evaluates **PUBLISHED rules only** (rule schema: only PUBLISHED rules run
against live submissions). `APPROVED`/`PEER_REVIEW` rules are knowledge, not live detection; golden cases
whose governing rule is not yet PUBLISHED (GDC-07 TL-MAL-003, GDC-10 TL-JOB-003) carry
`live_publishable: false` and document the designed on-promotion behaviour — live, they route to review.

**Fail-closed behaviour.** The engine must **never silently fall back to "safe."**

| Failure | Behaviour |
|---|---|
| bundle hash invalid / bundle version unknown / schema incompatible / required provenance missing | **Refuse to evaluate.** `input_support_status = ERROR`, `classification = ERROR`, the specific failure in `errors[]` |
| extractor result malformed | reject the malformed observation; if the decisive frame is lost → `ERROR`/`INSUFFICIENT_INFORMATION`, never benign |
| single-rule evaluation exception | that rule → `NOT_APPLICABLE` with an error note; evaluation continues; `degraded = true`; confidence capped; route to review |

The distinction is deliberate: integrity/bundle failures **refuse to run**; a single-rule error
**degrades and flags**. Neither yields `NO_SCAM_PATTERN`.

## 17. AI boundary (STEP 24)

Future AI (Phase 4, behind ADR-0002's deferral) **may**: propose candidate observations / indicator
observations (extraction), normalise entities, assist explanation *wording* (from the structured facts),
and summarise evidence. AI **may not, ever, silently**: invent indicators, invent official evidence,
override deterministic rule results, alter severity/risk/classification, convert `UNKNOWN` to benign, or
emit a fraud probability. AI-proposed observations enter the **same** typed contracts, are provenance-
tagged `extractor_type = LLM`, and are subject to the **same** extraction-confidence gate; by design an
LLM-only extraction is treated as ≤ `MEDIUM` confidence unless corroborated by a deterministic extractor,
so an LLM alone cannot establish a hard-risk `CRITICAL`. The deterministic result is authoritative; AI is
assistive and auditable.

## 18. Pipeline (STEP 18)

Stages, each deterministic and individually explainable:

1. **Ingest** envelope (`input-envelope.schema.json`).
2. **Support-status gate** (§3) — language/script; `UNSUPPORTED`/`ERROR` short-circuit here.
3. **Observations** (`observation.schema.json`) — typed, span-anchored, polarity/attribution/mood/
   payment-direction resolved.
4. **Indicator observations** (`indicator-observation.schema.json`) — five-valued `matched` + extraction
   confidence.
5. **Confidence gate** (§8) — `LOW` or absent extraction confidence → `UNKNOWN` (never `FALSE`, never
   silently `HIGH`).
6. **Structural occurrence eligibility** (§11) — resolved from the normalized observation via
   `observation_refs` (`status`/`polarity`/`attribution`/`mood`); fixes which positive occurrences are LIVE.
   Non-overridable; unresolved association / `UNKNOWN`-`AMBIGUOUS` status → `UNKNOWN`.
7. **Hard-risk override computation** (§10) — confidence-gated, computed FROM the raw **structurally-eligible
   live-positive** set.
8. **Execute governed `SUPPRESS_INDICATOR`** (§11) — apply it only to target occurrences associated by
   `observation_refs`; explicit disjoint occurrences survive and unresolved association is `UNKNOWN`; recombine
   occurrences with three-valued OR. Blocked only by an EXPLICITLY override-blockable flag (none currently).
9. **Rule evaluation** (§7) — Kleene three-valued `require`; `min_evidence_classes` diversity;
   `MATCHED`/`NOT_MATCHED`/`INDETERMINATE`/`NOT_APPLICABLE`. PUBLISHED-only, live.
11. **Suppression** (§11, WP4) — override-aware `SUPPRESS_RULE`/`CAP_SEVERITY`.
12. **Per-rule results** (§6).
13. **Aggregation** (§11) — governing rule + corroboration over independent classes.
14. **Severity + matched-evidence strength → risk** (§5, ADR-0006 matrix).
15. **Detection-confidence banding** (§9).
16. **Classification** (§4).
17. **Explanation build** (§13) — provenance-constrained.
18. **Recommended actions** (§14).
19. **Result assembly** with full version pinning (§16).

## 19. False positive / false negative — measurement hooks only (STEP 22)

**G-09 is open: no labelled real-world corpus exists or can be obtained (RSK-003).** DET-001 therefore
makes **no accuracy claim** — no precision, recall, calibration or false-positive-rate figure is produced
or implied. It defines only the future measurement machinery:

- **Definitions.** A *false positive* is a PUBLISHED rule firing on a benign gold case (`must_not_match`);
  a *false negative* is an expected rule failing to fire on a malicious gold case. On the **synthetic**
  corpus these are usable for **determinism and regression** only, never as an efficacy metric.
- **Hooks.** Per-decision logging of `(fired rules, suppressors, overrides, severity, confidence,
  corroboration, evaluation_profile)`; a versioned `evaluation_profile` so thresholds can later be tuned
  and replayed; `bundle_content_digest` pinning so a historical decision replays identically. When (if) a
  labelled corpus is obtained, these hooks feed calibration without any change to the deterministic core.

## 20. Deterministic guarantees & limitations (summary)

Guaranteed: identical inputs → identical result; every score decomposable to the rule/cell/indicator that
produced it; every finding traceable to an official source quote; uncertainty preserved, not hidden.
Limitations carried forward honestly: English/Latn MVP only (non-English `UNSUPPORTED`); no accuracy claim
(G-09); `PARTIAL`/`HEURISTIC` evidence capped; three governed rules `DEFERRED` (unobservable); reputation/
payee-identity `NOT_EVALUATED`, never invented.

## 21. Golden decision cases (STEP 21)

Fifteen design-level cases are specified and machine-checked in
[`golden-decision-cases-v1.json`](golden-decision-cases-v1.json) (validated by
[`validate_det_design.py`](validate_det_design.py) against the real KB and the ADR-0006 matrix). Summary:

| # | Case | Support | Governing rule(s) | Severity | Confidence | Risk | Classification |
|---|---|---|---|---|---|---|---|
| GDC-01 | "Share the OTP you received" (bank) | SUPPORTED | TL-CRED-001 | CRITICAL | HIGH | CRITICAL | SCAM_PATTERN_DETECTED |
| GDC-02 | "Never share your OTP" | SUPPORTED | — | NONE | n/a | NONE | NO_SCAM_PATTERN |
| GDC-03 | "The scammer asked me to…" (reported) | SUPPORTED | — | NONE | n/a | NONE | NO_SCAM_PATTERN |
| GDC-04 | UPI PIN to **receive** ₹5,000 | SUPPORTED | TL-PAY-001 | CRITICAL | HIGH | CRITICAL | SCAM_PATTERN_DETECTED |
| GDC-05 | UPI PIN to **pay** merchant | SUPPORTED | — | NONE | n/a | NONE | NO_SCAM_PATTERN |
| GDC-06 | KYC + link + OTP/card chain | SUPPORTED | TL-CRED-001 (+003,+KYC-001) | CRITICAL | HIGH | CRITICAL | SCAM_PATTERN_DETECTED |
| GDC-07 | AnyDesk in refund context | SUPPORTED | TL-MAL-003¹ | HIGH | MEDIUM | HIGH | SCAM_PATTERN_DETECTED |
| GDC-08 | Corporate IT TeamViewer | SUPPORTED | TL-MAL-003→SUPPRESSED | NONE | n/a | NONE | NO_SCAM_PATTERN |
| GDC-09 | Trust-Wallet verify + connect | SUPPORTED | TL-CRYP-001 | HIGH | MEDIUM | HIGH | SCAM_PATTERN_DETECTED |
| GDC-10 | Task deposit → blocked withdrawal | SUPPORTED | TL-JOB-003¹ | HIGH | HIGH | HIGH | SCAM_PATTERN_DETECTED |
| GDC-11 | PIN, **direction unknown** | SUPPORTED | TL-PAY-001→INDETERMINATE | NONE | n/a | NONE | INSUFFICIENT_EVIDENCE |
| GDC-12 | Hinglish scam | **UNSUPPORTED** | — | NONE | n/a | NONE | UNSUPPORTED |
| GDC-13 | Single weak cue | SUPPORTED | — | NONE | n/a | NONE | INSUFFICIENT_EVIDENCE |
| GDC-14 | Digital arrest (strong, corroborated) | SUPPORTED | TL-AUTH-001,-002 | CRITICAL | HIGH | CRITICAL | SCAM_PATTERN_DETECTED |
| GDC-15 | Live OTP wrapped in decoy safety | SUPPORTED | TL-CRED-001 | CRITICAL | HIGH | CRITICAL | SCAM_PATTERN_DETECTED |

¹ Governing rule not yet PUBLISHED (`live_publishable: false`): live, it routes to review pending
governance promotion; the row shows designed on-promotion behaviour.

## 22. Phase-3 implementation work packages (STEP 26 — NOT started here)

| WP | Deliverable | Depends on |
|---|---|---|
| **P3-WP1** | Decision/result schemas promoted to runtime contracts (detection-result, rule-evaluation-result) + fixtures | this design |
| **P3-WP2** | Bundle loader + runtime indexes (rules by status/family, indicator/override maps) over the ADR-0004 bundle | ADR-0004 |
| **P3-WP3** | Three-valued rule evaluator (Kleene) + `min_evidence_classes` diversity | ADR-0005 |
| **P3-WP4** | Suppression + hard-risk override executor (confidence-gated, resolution order) | WP3 |
| **P3-WP5** | Aggregation + risk/severity + confidence banding + classification | ADR-0006 |
| **P3-WP6** | Explanation builder (provenance-constrained) + recommended-action mapper | WP5 |
| **P3-WP7** | Golden decision-case runner (executes the engine over GDC + the Phase-2 corpus) | WP1–WP6 |
| **P3-WP8** | Integration tests + CI wiring of the *engine* gate | WP7 |

None of these is started; DET-001 stops at the design gate. (The *design* gate itself — the
`validate_det_design.py` contract/golden-case validator — was wired into `run_all.py` as the **10th
canonical check** at the Phase-3 closure, GATE-009. P3-WP8 concerns the future *engine* runner.)

## 23. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 (design) | 2026-08-29 | Initial DET-001 design: pipeline, three-valued execution, extraction-confidence gating, hard-risk override semantics, suppression, aggregation, corroboration, separated severity/risk/confidence model, classification vocabulary, explanation & action contracts, determinism & fail-closed behaviour, AI boundary, 15 machine-checked golden cases, and the Phase-3 WBS. Implements CONF-001; changes no Phase-2 semantics. Frozen by ADR-0005/ADR-0006. | Detection Architect |
| 1.0.1 (clarification) | 2026-09-02 | P3-WP5 implemented (`knowledge/runtime/aggregation.py`, gate check #15). Recorded the ratified §9 confidence clarification: the HIGH band's decisive-extraction floor is `≥ MEDIUM` (categorical policy, no golden outcome changed) — see [DET-001-WP5](DET-001-WP5-decision-aggregation.md). No ADR-0006 change; no golden-case change. | Detection Architect |
| 1.0.4 (WP6 + provenance amendment) | 2026-09-03 | P3-WP6 implemented (`knowledge/runtime/explanation.py`, gate check #16): deterministic templated explanation (official facts only via exact stored `evidence_basis` quotes; no LLM, no `redacted_quote`, no numeric) + governed recommended actions from a NEW bundled, versioned, schema-validated **action-policy artifact** (`knowledge/detection/action-policy-v1.json`) — actions only from the promoted vocabulary, no `priority`, system-state actions carry no fabricated reason ids. **Phase-2 bundle-provenance additive amendment:** action_policy is a hashed, digest-covered, version-pinned bundle member; `bundle-manifest` `manifest_schema_version` 1.0.0→1.1.0 (+`component_versions.action_policy`); detection-result `result_contract_version` 1.0.0→1.1.0 (+ `provenance.component_versions.action_policy`, structurally optional in the shared JSON schema only for historical/contract compatibility). The runtime semantic contract requires a valid action-policy semver pin on **every** `result_contract_version == 1.1.0` result, even when `recommended_actions` is empty, because WP6 consulted the policy to produce that empty set; a 1.1 result without it is invalid. Historical pre-WP6 results do not fabricate a pin. Golden `recommended_actions` normalized to the policy (cases_version 1.3.0); no decision-axis / no other-outcome change; no ADR-0006 change. | Detection Architect |
| 1.0.3 (contract amendment) | 2026-09-02 | P3-WP3 provenance-output amendment (WP5 safety review): the rule-evaluation-result contract gains an additive optional grouped `live_positive_provenance` (per matched-positive TRUE indicator, one group per structurally-LIVE contributing occurrence's observation_refs). §9 HIGH is now one normative rule — `proven_independent_evidence_count ≥ 3` is a class→occurrence matching over that authoritative provenance (union-find on shared refs), never a raw class count. Additive MINOR runtime-contract change; WP3 truth semantics unchanged; no golden-outcome change; no ADR-0006 change. | Detection Architect |
| 1.0.2 (clarification) | 2026-09-02 | P3-WP5 adversarial-review remediation. §9 HIGH ≥3 path now uses a single `proven_independent_evidence_count` (class→occurrence matching over unambiguous single-ref governed occurrences) shared with the corroboration band — a raw class count never bypasses provenance. Degraded caps confidence at MEDIUM; explicit whole-evaluation ERROR; rule-local unresolved-harm + strict effect-aware benign clear. GDC-02/03 governed inputs enriched (golden cases_version 1.2.0), outcomes unchanged. No ADR-0006 change; no golden-outcome change. | Detection Architect |
