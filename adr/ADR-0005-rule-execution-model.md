# ADR-0005 — Rule execution model: three-valued interpreter over an immutable bundle

| Status | Accepted |
| Date | 2026-08-29 |
| Owner role | Detection Architect |
| Related | [DET-001](../docs/03-detection/DET-001-deterministic-detection-engine.md), [ADR-0003](ADR-0003-rule-representation-format.md), [ADR-0004](ADR-0004-knowledge-storage-architecture.md), [CONF-002](../docs/00-program/conflict-register.md), [CONF-003](../docs/00-program/conflict-register.md), KB-002 |

## Context and constraints

Phase 2 rules are declarative data (ADR-0003): a `require` tree of `all_of` / `any_of` / `n_of` over
indicator ids, with `min_evidence_classes`, plus an override-aware suppression layer. The Phase-2
`rule_runner` interprets them with **closed-world Boolean** logic (`indicator in signals`) over a
*declared* set — correct for a conformance harness, wrong for a live engine, because the extraction
contracts carry five epistemic states (`OBSERVED`, `NOT_OBSERVED`, `UNKNOWN`, `AMBIGUOUS`,
`NOT_APPLICABLE`) and collapsing `UNKNOWN`→`FALSE` is accidental closed-world reasoning. DET-001 needs a
production execution model that (a) preserves uncertainty, (b) is deterministic and reproducible against
a pinned bundle (ADR-0004), (c) evaluates only PUBLISHED rules live, and (d) contains no rule *code* —
rules stay data (FR-020).

## Decision

Adopt a **deterministic three-valued (Kleene strong) interpreter** over the immutable published bundle:

1. **Signal states.** Each indicator observation maps `OBSERVED→TRUE`, `NOT_OBSERVED`/`NOT_APPLICABLE→
   FALSE`, `UNKNOWN`/`AMBIGUOUS→UNKNOWN`. Extraction confidence below the pinned gate (default `MEDIUM`),
   or absent, demotes an indicator to `UNKNOWN`, never `FALSE` (DET-001 §8). Observation sets are **sparse**:
   an operand with no observation is `UNKNOWN`, not `FALSE` (clarified 2026-08-30 — no complete-frame
   assumption).
2. **Operators (Kleene).** `all_of`: FALSE if any FALSE, TRUE if all TRUE, else UNKNOWN. `any_of`: TRUE
   if any TRUE, FALSE if all FALSE, else UNKNOWN. `n_of(n)`: TRUE if `#TRUE≥n`, FALSE if `#TRUE+#UNKNOWN<n`,
   else UNKNOWN.
3. **Rule states.** `require=TRUE` and evidence-class diversity (`min_evidence_classes`) met → `MATCHED`;
   `require=FALSE` → `NOT_MATCHED`; `require=UNKNOWN` → `INDETERMINATE`; matched-then-cancelled →
   `SUPPRESSED`; out-of-scope/error → `NOT_APPLICABLE`.
4. **Resolution order** (negative-indicator-library-v1.json §resolution_order, updated by programme
   authority 2026-08-31): **structural occurrence eligibility** (status/polarity/attribution/mood — non-overridable,
   sourced from the normalized `observation.schema.json` via `observation_refs`) → raw **structurally-eligible
   live-positive** set (confidence-gated) → **hard-risk override computation FROM that live set** →
   **execute governed `SUPPRESS_INDICATOR` at occurrence scope** (a shared `observation_ref` drives only the
   associated target-positive occurrence `FALSE`; explicitly disjoint occurrences are unaffected; unresolved
   association is `UNKNOWN`; occurrences then combine by three-valued OR; blocked only if the suppressor is
   EXPLICITLY override-blockable) → `require` → (WP4) override-blockable
   `SUPPRESS_RULE`/`CAP_SEVERITY` → `CONTEXT_ONLY` recorded. "Raw `OBSERVED` set" means the raw
   structurally-eligible live positives; it does **not** mean ignoring negation/reported/quoted attribution.
   Overrides never set severity, never bypass `require`, can **never** turn a structurally non-live
   occurrence into a live positive. A non-blockable suppressor defeats an associated occurrence, but never a
   separate live occurrence (DET-001 §10/§11).
5. **Live set.** Only `PUBLISHED` rules are evaluated against live submissions; lifecycle is read from the
   bundle, not hard-coded.
6. **Determinism.** Evaluation order is fixed (lexical rule id); the interpreter is pure over
   *(observations, bundle, engine_version, evaluation_profile)*; no network, no clock, no LLM in the
   deterministic path. The bundle `content_digest` and profile are pinned into every result.

The interpreter remains a **data interpreter** — no rule-specific code, matching ADR-0003.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Keep Boolean closed-world (reuse rule_runner) | simplest; already passing | collapses UNKNOWN→benign; violates DET-001 §7; unsafe (a shaky read reads as "cleared") | **Rejected** |
| Full probabilistic/Bayesian inference | models uncertainty richly | manufactures probabilities with no calibration data (G-09); violates CONF-001; not explainable as an ordinal | **Rejected** |
| Compile rules to code for speed | fast | rules become code (breaks FR-020); every rule change is a deploy | **Rejected** |
| **Kleene three-valued interpreter over the bundle** | preserves uncertainty; deterministic; rules stay data; explainable | one new state (`INDETERMINATE`) for downstream to handle | **Selected** |

## Justification

Three-valued logic is the minimal, well-defined extension that keeps `UNKNOWN ≠ NOT_OBSERVED` (DET-001
§7) without inventing probabilities. It matches the five-valued vocabulary the Phase-2 contracts already
committed to, so no rule or schema changes. Determinism + bundle pinning gives replay (glossary), and
keeping rules as data preserves the ADR-0003 guarantee.

## Consequences

- Downstream must handle `INDETERMINATE` (→ `INSUFFICIENT_EVIDENCE`, route to review) — designed in
  DET-001 §4/§15.
- The Phase-2 `rule_runner` is unchanged and remains the Phase-2 conformance harness; the two coexist
  (harness over declared sets vs live engine over extracted observations).
- Golden cases GDC-04/05/11 exercise the TRUE/FALSE/UNKNOWN branches of the same rule. GDC-15 stores and
  replays separate disclaimer and live-request occurrences, proving occurrence-associated suppression.

## Risks

- Extractors that emit `LOW`-confidence noise could push rules to `INDETERMINATE` and over-route to
  review. Mitigation: the confidence gate is a pinned, tunable `evaluation_profile` value; regression is
  measured on the synthetic corpus (determinism only, not accuracy).

## Reversal cost

**Low.** The interpreter is a pure function selected by `engine_version`; reverting to Boolean is a code
change with no data migration. Results are versioned, so historical decisions replay under their own
engine version.

## Validation plan

`docs/03-detection/validate_det_design.py` checks the rule-evaluation-result contract and that every
golden case's rule states/severities/statuses are consistent with the real KB. It is wired into
`run_all.py` as the **10th canonical check** (Phase-3 closure, GATE-009), so the gate now proves the
detection design alongside the knowledge base. Phase-3 implementation (P3-WP3) adds a golden-case *runner*
that executes the interpreter over the golden cases and the Phase-2 corpus.
