# AI-001 WP3 — Strict AI-response validation, RuntimeKnowledge membership, grounding

| Field | Value |
|---|---|
| Work package | P4-WP3 |
| Status | **Implemented locally — strict, atomic, deterministic validation of untrusted AI responses** |
| Authority | [AI-001](AI-001-ai-intelligence-layer.md) §8–§17, [ADR-0007](../../adr/ADR-0007-ai-authority-and-model-strategy.md), [GATE-010](../00-program/GATE-010-phase-4-ai-design.md) |
| Baseline | Phase-3 frozen at `phase3-wp8-v1.0`; unchanged. Builds on the P4-WP2 provider seam. |
| Constraint | No live provider, no vendor SDK, no network, no API key, no Phase-3 change, no promoted-schema change; G-09 OPEN |

## Scope

WP3 implements the deterministic validation boundary between an **untrusted** `RawAIExtractionResponse` (WP2
transport output) and a `ValidatedAIExtraction` — a set of **validated AI extraction proposals**. It calls no
Phase-3 code and gives the AI no decision authority. WP4 owns provenance/replay/confidence-cap; WP5 maps
validated proposals to governed `Observation`/`IndicatorObservation` and runs the Phase-3 engine.

## Public API and authoritative binding

`validate_ai_extraction(raw, *, expected_request_id, expected_input_id, normalized_inputs, rk)`. The caller
supplies the **authoritative current request/input identity**; the AI payload can never select a different
submission by naming another key present in `normalized_inputs`. `normalized_inputs` maps `input_id` → the
authoritative normalized submitted text (single-current-input MVP; `expected_input_id` must be present). `rk`
is the same authoritative `RuntimeKnowledge` Phase 3 uses.

## Pipeline (deterministic precedence; all fail-closed, atomic)

Global stages run in a fixed, documented order so the failure code is invariant under array permutation; within
a per-item stage the winner is the lexically-first `proposal_id`:

1. **strict-UTF-8 validity + raw byte-size limit** (before parse) → a lone surrogate / non-UTF-8 payload is `AI_RESPONSE_MALFORMED`, oversize is `AI_RESPONSE_TOO_LARGE`
2. **current-request binding** (`raw.request_id == expected_request_id`) → `AI_REFERENCE_INVALID`
3. **strict `json.loads` + nesting-depth guard** (no `eval`/`exec`/`literal_eval`/YAML/repair/fence extraction; rejects invalid/empty/trailing-junk/concatenated JSON; `RecursionError` contained) → `AI_RESPONSE_MALFORMED`
4. **recursive forbidden-decision/confidence-field scan** → `AI_DECISION_FIELD_REJECTED`
5. **`ai-extraction.schema.json`** (`additionalProperties:false`, enums, bounds, version const) → `AI_SCHEMA_INVALID`
6. **current-input binding** (`payload.input_id == expected_input_id`; expected present in `normalized_inputs`) → `AI_REFERENCE_INVALID`
7. **duplicate `proposal_id`** (global) → `AI_REFERENCE_INVALID`
8. **per-item source/input correlation** (every `source_input_id`/`input_id` == `expected_input_id`) → `AI_REFERENCE_INVALID`
9. **indicator RuntimeKnowledge membership** (positive registry / negative library) + polarity + live status → `AI_UNKNOWN_INDICATOR`
10. **observation-reference integrity** (`observation_refs` resolve within THIS response; OBSERVED indicator cites ≥1) → `AI_REFERENCE_INVALID`
11. **grounding** (offsets in range; exact excerpt↔slice) → `AI_GROUNDING_FAILED`
12. construct the deeply-immutable validated output.

Containment limits (Python-enforced before expensive work; aligned with the schema): `MAX_RAW_RESPONSE_BYTES =
1 MiB` (UTF-8, checked before parse), `MAX_JSON_NESTING_DEPTH = 16` (iterative guard; a parser `RecursionError`
is caught and converted, never escapes). The scan and depth checks are **iterative** (no unbounded recursion on
hostile data). Schema bounds (≤128 observations/indicators, `canonical_value` ≤256, `evidence_excerpt` ≤2048,
`observation_refs` ≤64) keep a well-formed response far below the raw cap.

## Atomic policy

The response is **atomic**: any single invalid item rejects the **entire** response (`AIExtractionValidationError`
with a typed `.code`). No partial acceptance, no "good item" salvage, no decisive-item logic, no silent
dropping. A valid response **may** contain zero items.

## Intermediate contract

`knowledge/ai/schemas/ai-extraction.schema.json` — an **AI-layer** schema (not a promoted Phase-3 detection
contract, not placed among `knowledge/schemas/`). JSON object root, `additionalProperties:false` at every
object level, `ai_extraction_version` const `1.0.0`, bounded arrays/strings, explicit enums, explicit required
properties. An observation proposal **requires** the full structural frame — `observation_type`, `status`,
`polarity`, `attribution`, `mood`, `source_input_id`, `start`, `end` — that Phase-3 relies on for later mapping
(H1). Structural vocabularies (`observation_type`/`status`/`polarity`/`attribution`/`mood`, indicator
`polarity`/`matched`, id patterns) **mirror** `observation.schema.json` / `indicator-observation.schema.json`
exactly — they are not re-invented. It carries only extraction-owned proposal data (candidate observations +
indicator observations); the model authors no provenance, `config_ref`, governed confidence, or decision field.

## Forbidden decision / confidence fields

Structurally forbidden by `additionalProperties:false`; a **recursive name-scan** (defence in depth) rejects
`classification`, `decision_severity`, `matched_evidence_strength`, `risk_level`, `detection_confidence`,
`fraud_probability`, `scam_probability`, `score`, `safety_score`, `recommended_actions`, `rule_results`,
`governing_rule`, `official_evidence_basis`, `safe`, `legitimate`, `fraud_verdict`, and any model-confidence
field (`confidence`, `probability`, `certainty`, `token_probability`, `self_score`, …) **anywhere** in the
response, yielding `AI_DECISION_FIELD_REJECTED`. The model self-reports **no** extraction confidence (WP4's
deterministic adapter assigns/caps it).

## RuntimeKnowledge membership

Every `indicator_id` is resolved against the **same authoritative `RuntimeKnowledge` Phase 3 uses** (no
divergent copy): `POSITIVE` → positive registry, `NEGATIVE` → negative library. Unknown id, polarity mismatch,
invented/free-text id, or a non-live (non-`ACTIVE`) negative indicator → `AI_UNKNOWN_INDICATOR`. Taxonomy: the
MVP contract deliberately carries **no** AI-authored taxonomy/category/family references (`additionalProperties:
false` forbids them), so no free-text taxonomy can enter and indicator membership is the sole governed-ID hook;
a future WP adding taxonomy references must add the analogous membership check (a hook is noted in the design).

## Grounding (precise claim)

Grounding proves **only** source anchoring / reference + offset integrity / exact excerpt correspondence — it
does **not** prove semantic truth, factual correctness, correct model interpretation, or indicator truth. For
every observation: `source_input_id` resolves; offsets are integers with `0 ≤ start < end ≤ len(normalized)`;
and, if a transient `evidence_excerpt` is present, `normalized[start:end] == evidence_excerpt` **exactly** (no
fuzzy / case-insensitive / whitespace-normalised / approximate match). Failure → `AI_GROUNDING_FAILED`. Half-open
offsets `[start, end)`.

## Transient excerpt & privacy

The `evidence_excerpt` exists only to verify grounding. It is **dropped** from `ValidatedAIExtraction` after
verification — governed output keeps offsets/reference identity, not model-supplied text. No existing privacy
policy is weakened.

## Reference integrity & duplicates

Indicator `observation_refs` must resolve to `observationProposal.proposal_id` values in the **same** response;
`source_input_id`/`input_id` must equal the response `input_id` (cross-request rejected). Duplicate observation
`proposal_id` (and duplicate indicator `proposal_id` where present) → `AI_REFERENCE_INVALID`; nothing is
silently merged.

## Output & typed failures

`ValidatedAIExtraction` (frozen, **deeply read-only**) — clearly **validated proposals**, not a governed
`Observation`/`IndicatorObservation`, not a `DetectionResult`. `observations`/`indicators` are tuples of
`MappingProxyType`, and nested arrays (e.g. `observation_refs`) are tuples, so no nested collection is mutable
and the caller's payload never aliases validated state. `as_dict()` returns a fully **detached** mutable
JSON-like copy (mutating it never mutates the original or a later `as_dict()`).

Failures use a **closed, stable taxonomy** of concrete subclasses of `AIExtractionValidationError`; each owns a
fixed `.code` via a read-only property, and the constructor accepts a sanitized `detail` only (no `code=`
parameter) — the code is neither caller-selectable nor mutable. Codes: `AI_RESPONSE_TOO_LARGE`,
`AI_RESPONSE_MALFORMED`, `AI_SCHEMA_INVALID`, `AI_DECISION_FIELD_REJECTED`, `AI_UNKNOWN_INDICATOR`,
`AI_REFERENCE_INVALID`, `AI_GROUNDING_FAILED`.

**Sanitized diagnostics (all paths).** Every public error `detail` is a repository-controlled **structural**
description; it does **not** reproduce any model/provider-controlled value — no `proposal_id`, `indicator_id`,
`source_input_id`/`input_id`, `observation_refs`, `canonical_value`, `evidence_excerpt`, `request_id`,
unexpected enum value, or raw model text. Schema failures echo only the structural path + failing rule keyword.
A forbidden **canonical** field name may be referenced generically ("forbidden decision-owned field detected")
because the deny-list is a closed governed constant; arbitrary values are not echoed. Detail is bounded by a
single centralized helper so that **`AIExtractionValidationError.detail` is at most 256 characters** (the
sentinel/hostile value is removed at the call site first — truncation is only a secondary bound). Note
`str(exc)` additionally carries the fixed `[CODE]` prefix and may therefore exceed 256; the enforced invariant
governs `.detail`, not the full string. A validation failure is never a TrustLens decision (never
`NO_SCAM_PATTERN`/safe); WP5 degrades to deterministic-only / governed uncertainty.

**Raw payload must be strictly UTF-8 representable.** The pre-parse guard encodes `raw_text` with strict UTF-8;
a lone surrogate / non-UTF-8 payload fails as `AI_RESPONSE_MALFORMED` — no raw `UnicodeEncodeError` escapes the
boundary (no `errors="ignore"/"replace"/"surrogatepass"` is used, so the transport representation is never
altered to bypass validation).

## Independent-review remediation (applied)

- **H1** — observation proposals require the full structural frame (`polarity`/`attribution`/`mood` added to
  required), so a proposal always carries what Phase-3 mapping needs.
- **H2** — the caller supplies authoritative `expected_request_id` / `expected_input_id`; the response
  `request_id`, payload `input_id`, and every per-item `source_input_id`/`input_id` must match, and the AI
  cannot select another submission even if it is present in `normalized_inputs`.
- **H3** — a pre-parse `MAX_RAW_RESPONSE_BYTES` (1 MiB, UTF-8) cap and a `MAX_JSON_NESTING_DEPTH` (16) iterative
  guard; a parser `RecursionError` is caught and converted; no raw `RecursionError` escapes.
- **M1** — deep immutability (tuples + `MappingProxyType`, `observation_refs` as tuple) and a detached
  `as_dict()`.
- **M2** — a closed, non-overridable error taxonomy (fixed per-subclass codes; no `code=` override; `.code`
  read-only).
- **M3** — a documented deterministic failure precedence; a logically-equivalent response yields the same
  failure code under any array permutation.
- **M4** — sanitized schema diagnostics (structural path + rule only), length-bounded, never echoing a raw
  model value.

Final-remediation (second independent review):
- **UTF-8 (M1)** — strict-UTF-8 pre-parse guard; a lone surrogate / non-UTF-8 payload → `AI_RESPONSE_MALFORMED`;
  no raw `UnicodeEncodeError` escapes.
- **One sanitization policy (M2)** — the value-free diagnostic rule now applies to **every** WP3 failure path
  (not only schema), via a single centralized detail helper; the detail cap off-by-one is fixed so
  `.detail ≤ 256` exactly.
- **Coverage (M3)** — behavioral tests exercise lone surrogates, per-path sentinel non-leakage, and the exact
  `.detail` length boundary (255/256/257/very-long).

## Validation

`knowledge/validation/validate_ai_extraction.py` (offline, standalone; **not** wired into `run_all` — WP7 owns
canonical CI): 70 assertions over one real bundle covering the good path (incl. a live NEGATIVE indicator and a
zero-item response), required-structure rejections, request/input binding (incl. selecting a present-but-wrong
input), raw-size + nesting-depth containment (incl. very deep JSON never escaping as `RecursionError`),
strict-UTF-8 lone-surrogate rejection, multibyte byte-limit, strict-parse failures, forbidden-field rejection,
schema/enum/version/additionalProperties + taxonomy-closure failures, indicator membership + polarity + non-live
rejection (via a small stub RK for the DEPRECATED case), source/reference integrity, grounding (offset +
exact/case-sensitive excerpt), duplicates, deep-immutability + detached `as_dict` + no caller aliasing,
non-overridable error codes, permutation precedence, **per-path sentinel non-leakage**, the exact `.detail ≤ 256`
boundary, and the atomic whole-response rejection. Phase-3 regression (`run_all`) remains green.

## Next (P4-WP4)

Prompt-injection containment fixture matrix, provenance/replay (`AIExtractionResult`, `config_ref`) and the
deterministic extraction-confidence cap (LLM-only ≤ MEDIUM). WP3 hands WP4 only validated, grounded proposals.
