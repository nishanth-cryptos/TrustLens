# ADR-0006 — Risk and confidence aggregation: categorical, decomposable, non-probabilistic

| Status | Accepted |
| Date | 2026-08-29 |
| Owner role | Detection Architect |
| Related | [DET-001](../docs/03-detection/DET-001-deterministic-detection-engine.md), [CONF-001](../docs/00-program/conflict-register.md), [ADR-0005](ADR-0005-rule-execution-model.md), RESEARCH-004 §7, [glossary §1](../docs/00-program/glossary.md), RSK-003 (G-09) |

## Context and constraints

CONF-001 forbids collapsing risk, confidence, severity and evidence quality into "one arbitrary
percentage," and forbids the research package's 0–100 numbers as operational risk (they are provenance
only, `operational_use: false`). The glossary §1 defines the axes as *independent*: **risk** = f(severity,
matched-evidence strength) for this submission; **confidence** = trust in our own analysis (extraction
quality, corroboration, completeness). RESEARCH-004 §7 further requires that evidence quality *change
behaviour*: `PARTIAL` rules must need stronger combinations than `SUPPORTED` rules to reach the same band.
G-09 means **no calibrated probability is obtainable** — so none may be produced. This ADR fixes the
aggregation mathematics DET-001 uses.

## Decision

**Categorical outputs with a derived ordinal risk band; no user-visible numeric score; no probability.**

1. **Severity (ordinal, `NONE|LOW|MEDIUM|HIGH|CRITICAL`).** Per-rule, a property of the scam class.
   *Effective* severity = `min(declared, evidence.severity_cap, CAP_SEVERITY suppressor)`. **Decision
   severity = max effective severity across fired rules** — never inflated by rule count.
2. **Matched-evidence strength (`NONE|WEAK|MODERATE|STRONG`).** Derived from the governing rule's decisive
   indicator `strength`, its evidence `verdict` (`SUPPORTED>PARTIAL>HEURISTIC`), and whether a hard-risk
   override is active. This is the glossary's "strength of matched evidence."
3. **Risk level (`NONE..CRITICAL`) — fixed matrix `risk = M[severity][strength]`** (risk-matrix v1):

   | severity ↓ / strength → | WEAK | MODERATE | STRONG |
   |---|---|---|---|
   | LOW | LOW | LOW | MEDIUM |
   | MEDIUM | LOW | MEDIUM | MEDIUM |
   | HIGH | MEDIUM | HIGH | HIGH |
   | CRITICAL | HIGH | HIGH | CRITICAL |

   `severity=NONE ⇒ risk=NONE`. Risk is **bounded, decomposable** (the cell + governing rule are
   auditable), **reproducible**, and user-visible as a band. It is **not** a probability, **not** a
   percentage, **not** an average of confidence. Note the matrix encodes RESEARCH-004 §7: a `CRITICAL`
   class reaches `CRITICAL` risk only with `STRONG` matched evidence (`SUPPORTED` + strong indicators /
   active override); a capped `PARTIAL` rule with weak evidence lands at `MEDIUM`.
4. **Detection confidence (categorical `LOW/MEDIUM/HIGH`, or `NOT_APPLICABLE`)** — a **separate** axis,
   never folded into risk. Fixed banding policy (confidence-policy v1), inputs and thresholds per DET-001
   §9: completeness of `require`, extraction confidence of decisive indicators, corroboration across
   *independent* evidence classes, evidence verdict (`PARTIAL/HEURISTIC` cap at `MEDIUM`), ambiguity,
   suppressive context.
5. **Corroboration** is counted over **distinct independent evidence classes/families**, never rule count
   (DET-001 §11–13), and feeds confidence — not risk.
6. **No numeric probability anywhere.** Any internal integer used to index the matrix is not exposed and
   carries no probabilistic meaning. TrustLens never emits "N% chance of fraud."

`risk_matrix_id` and `confidence_policy_id` are pinned in every result's `evaluation_profile` for replay.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Single 0–100 risk score | familiar; one number | exactly what CONF-001 forbids; false precision; no calibration (G-09) | **Rejected** |
| Additive weighted sum of rule/indicator weights | tunable | invents magnitudes with no basis; double-counts correlated rules; not decomposable to a boundary | **Rejected** |
| Fold confidence into risk (one band) | fewer fields | conflates two independent axes (glossary §1); "unsure but severe" becomes invisible | **Rejected** |
| **Categorical + fixed severity×strength matrix, confidence separate** | honours CONF-001 & glossary; decomposable; evidence quality changes behaviour; no fake probability | two axes to present in the UI | **Selected** |

## Justification

The matrix is the smallest deterministic construction that satisfies every constraint at once: it keeps
risk and confidence independent (glossary), derives risk from severity × evidence strength (glossary),
makes `PARTIAL` evidence reach lower bands than `SUPPORTED` (RESEARCH-004 §7), and refuses to manufacture
a probability (CONF-001, G-09). It is auditable to a single cell plus the governing rule, satisfying the
explainability and determinism gates.

## Consequences

- Phase 7 (UX) must present **risk and confidence side by side**, never averaged (e.g. "CRITICAL risk,
  LOW confidence" is a valid, meaningful state). REPORT-001 renders the decomposition.
- The matrix and banding policy are versioned config; changing them is a governed `evaluation_profile`
  bump, replayable against history.
- Golden cases encode the matrix; `validate_det_design.py` checks `risk_level == M[severity][strength]`
  for all 15, so a future edit that breaks the mapping fails the design gate.

## Risks

- Ordinal bands are coarser than a score and can feel blunt at boundaries. Accepted: coarse-but-honest
  beats precise-but-fabricated (`MP §21`). Calibration awaits a labelled corpus (G-09) and would arrive as
  a *future* profile, never as an MVP claim.

## Reversal cost

**Low–Medium.** Matrix/policy are data selected by `evaluation_profile`; a different scheme is a config
(and possibly schema) change. Because risk was never presented as a probability, no user-facing
probabilistic promise has to be walked back.

## Validation plan

`docs/03-detection/validate_det_design.py` validates the matrix against every golden case and checks the
severity-derivation and classification-consistency rules. Phase-3 P3-WP5 implements the aggregation and is
covered by the golden-case runner. No accuracy/precision/recall figure is produced (G-09); only
determinism and internal consistency are asserted.
