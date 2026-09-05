# AI-001 WP6 — Deferred AI capability specifications (rule-draft suggestion, explanation paraphrase)

| Field | Value |
|---|---|
| Work package | P4-WP6 |
| Status | **Specification only — DESIGN / DEFERRED / DEFAULT OFF / NON-AUTHORITATIVE; no runtime implementation**; builder authoring; awaiting independent review; uncommitted |
| Merged baseline | `main` @ P4-WP5 merge `98bdce154d4ffcdf1766c31d2800d5c618f6e25e` |
| Phase-3 baseline | `phase3-wp8-v1.0`; files, semantics, promoted schemas, rules and taxonomies unchanged |
| Authorities | [AI-001](AI-001-ai-intelligence-layer.md) §4–6, §18–20, §23–26, §29–33; [WP3](AI-001-WP3-response-validation.md); [WP4](AI-001-WP4-containment-provenance.md); [WP5](AI-001-WP5-phase3-integration.md); [ADR-0007](../../adr/ADR-0007-ai-authority-and-model-strategy.md); [GATE-010](../00-program/GATE-010-phase-4-ai-design.md) (PD-4) |
| Programme anchors | CON-003, NG-07/08, FR-072…077 (FR-075 human approval), RSK-008 (injection), RSK-012 (rule poisoning), G-09 (RSK-003) |
| Claim boundary | Governance/design specification only; no runtime, no provider, no efficacy; G-09 OPEN |

WP6 fixes the **future** governed boundaries for two capabilities the programme has ratified as **DESIGN
ONLY / implementation deferred** (PD-4): AI-assisted **rule-draft suggestion** and AI-assisted **explanation
paraphrasing**. Both remain deferred, default OFF and non-authoritative. This work package authors **no
executable implementation, no runtime Python, no feature-flag code, no provider, no schema and no rule**. It
does not modify Phase 3, promoted schemas, rules, taxonomies, the existing `knowledge/ai/*` runtime, `run_all.py`
or `ci_selftest.py`. If any of these capabilities appeared to require implementation now, the correct action is
to **STOP and report**, not to build.

The deterministic Phase-3 engine (`phase3-wp8-v1.0`; boundary `evaluate_detection_from_governed(...)`;
`engine_version = 1.0.0`; profile `mvp-default`) remains the sole decision authority (CON-003, NG-07,
ADR-0007 §1). WP5 already delivers the only governed Phase-4→Phase-3 bridge: validated AI *extraction*
observations become governed input, and the deterministic rules alone produce the `DetectionResult`. WP6
capabilities sit **outside** that decision path entirely.

## 1. Shared invariants (both capabilities)

1. **Non-authoritative.** Neither capability sets, overrides, or bypasses any decision quantity. Rule drafting
   produces an advisory *suggestion*; paraphrasing produces a *presentation-only* derivative. The precise
   AI-001 §4 wording holds: AI cannot directly set, override, or bypass decision semantics.
2. **Default OFF and deferred.** Conceptual flags `ai.rule_drafting.enabled` and
   `ai.explanation_paraphrase.enabled` are documented as default `false` (AI-001 §20). No executable flag,
   environment read, service wiring or auto-enable is created in WP6.
3. **Provider-neutral, offline.** No vendor is selected; no OpenAI/Anthropic/Gemini default; no API key, SDK,
   network, tools or agent loop (ADR-0007 §6/§7/§14; AI-001 §24, §31). Canonical Phase-4 CI stays offline.
4. **WP3/WP4 containment inherited.** Any analyst-authored intent, cited source text, or `DetectionResult`
   content handed to a future model is **untrusted DATA**, never instructions (FR-077, RSK-008). The optional
   derivative fails closed and is validated deterministically after generation. Prompt injection is
   **contained, not solved** (AI-001 §23).
5. **No self-learning (NG-08).** Neither capability adapts prompts, templates, rules, thresholds or scoring
   from acceptance, rejection, correction, later match, or reported outcome. Any future change to a prompt,
   template or rule is explicit, versioned, human-reviewed and governed (AI-001 §30).
6. **Replay ≠ regeneration.** Historical replay uses stored/pinned artifacts; it never re-calls a model. A
   fresh AI generation is a new revision/run with new run identity (AI-001 §19; WP4).
7. **G-09 OPEN.** No accuracy, precision, recall, false-positive/negative rate, rule-generation quality,
   paraphrase quality, improved detection or production-readiness claim is made.

---

## 2. Capability A — AI-assisted rule-draft suggestion (deferred)

### 2.1 Authority boundary

A future AI rule-drafting capability may produce **only** a *rule-draft suggestion*: a non-binding proposal for
a human knowledge editor. It **must never**: publish a rule; activate a rule; change any rule `lifecycle.status`;
assign or change `severity`; change the evidence hierarchy or evidence grades; change suppression policy; alter
`RuntimeKnowledge`; modify a published knowledge bundle; write directly to `knowledge/rules/*`; or trigger CI
publication. Rule-drafting output is advisory input to the **existing** governed authoring/publication
lifecycle; it grants no authority of its own (CON-003, NG-07, RSK-012, FR-075).

The governed rule contract is unchanged and remains authoritative: rules are **DATA, not code** (FR-020/021,
ADR-0003), validated by `knowledge/validation/validate_rules.py`, and only `lifecycle.status = PUBLISHED` rules
are evaluated against live submissions (`rule.schema.json`). A suggestion is not a rule and is never any of
these lifecycle states.

### 2.2 Minimum future governed inputs

A future draft request would accept only:

| Input | Constraint |
|---|---|
| Analyst-authored intent / rationale | Untrusted DATA; describes the pattern the analyst wants captured |
| Exact source / evidence references | Must resolve to existing governed source material; the model may cite, not invent |
| Existing governed indicator IDs | Must resolve against `RuntimeKnowledge` (POSITIVE registry / NEGATIVE library), non-DEPRECATED, governed polarity |
| Existing taxonomy / family IDs (where permitted) | Must resolve against the governed taxonomy; free-text labels rejected |
| Current rule schema version | The `schema_version` the draft is authored against |
| Current knowledge-bundle identity | Bundle version + `content_digest` the draft is proposed relative to |

The model **must not invent** official evidence, source quotes, indicator IDs, taxonomy IDs, severity authority,
or policy exceptions (AI-001 §11, §12, §33). Any governed ID appearing in a draft must resolve against
`RuntimeKnowledge` or another authoritative design-time knowledge view; an unresolved ID rejects the draft.

### 2.3 Conceptual output contract — `AIRuleDraftSuggestion`

Documented as a **conceptual, non-promoted** intermediate shape only. WP6 does **not** author a runtime schema;
no existing authority requires one now (AI-001 §17 — "STOP and report" before any additive schema). The future
shape would carry suggestion metadata only:

```text
AIRuleDraftSuggestion (conceptual; non-promoted; non-authoritative)
  draft_id
  proposed_rule_structure      # candidate title/description/logic/taxonomy_refs as a SUGGESTION, not a rule
  referenced_indicator_ids     # must resolve against RuntimeKnowledge
  referenced_evidence_source_ids  # must resolve against governed source material
  rationale                    # analyst-facing explanation of the suggestion
  uncertainties                # explicit gaps / assumptions the human must resolve
  requires_human_review = true # always; non-removable
  ai_provenance                # extractor_type = LLM, config_ref, prompt-template + response-schema versions
  schema_identity              # intermediate contract id + version (NOT a promoted rule schema)
```

**Forbidden fields / operations** (structurally excluded; a name-scan is defence in depth, not the primary
control, mirroring AI-001 §8): `published = true`, `active = true`, `approved = true`, any
`lifecycle.status`-setting authority, automatic deployment, automatic bundle publication, automatic severity
authority, or any field that would imply a rule is live, approved or authoritative. A suggestion cannot assert
its own acceptance.

### 2.4 Deterministic future validation sequence

```text
AI rule-draft suggestion
  → strict intermediate schema validation (bounded, additionalProperties:false, enums/ID patterns fixed)
  → decision/publication-field rejection (no published/active/approved/severity-authority/deploy field)
  → governed ID resolution (indicator + taxonomy IDs resolve in RuntimeKnowledge / design-time view)
  → source / evidence reference verification (cited references resolve; no invented evidence)
  → duplicate / conflict checks against existing PUBLISHED rules
  → HUMAN analyst review (mandatory)
  → normal existing rule validation (validate_rules.py: schema + linter + evidence-class diversity + grades)
  → normal governed promotion / publishing workflow (knowledge-editor + peer/security review + Git/PR)
```

AI **never bypasses** `validate_rules.py`, knowledge-bundle validation, human approval, or Git/PR governance.
The suggestion enters the *front* of the existing pipeline as unreviewed draft input; every existing gate still
applies unchanged.

### 2.5 Human approval (FR-075) and disposition

FR-075 authority remains explicit and mandatory: **no AI-suggested rule can become `PUBLISHED` without human
approval.** The lifecycle is:

```text
AI draft → DRAFT / SUGGESTED state
        → human analyst review
        → explicit disposition: accepted / rejected / revised
        → normal governed publication (only a human-approved rule advances toward PUBLISHED)
```

Acceptance, rejection or revision produces **no automatic learning** (NG-08, §1.5): the disposition is an
audited human decision, not a training signal. Rule poisoning (RSK-012) is mitigated precisely because
publication authority never leaves the human/peer/security governance path.

---

## 3. Capability B — AI-assisted explanation paraphrasing (deferred)

### 3.1 Authoritative explanation vs optional paraphrase

WP6 draws a hard line:

| Layer | Definition | Authority |
|---|---|---|
| **Authoritative explanation** | The Phase-3 / P4-not-applicable, WP6-deterministic explanation: `ExplanationResult` (`evidence_basis` = exact stored `source_references` quotes; `supporting_observations`; `verification_steps`; `limitations`; `confidence_reason`; `suppression_considered`) plus the governed `recommended_actions` from the RuntimeKnowledge action-policy artifact, all bound into the `DetectionResult`. | **Authoritative** (deterministic; Phase-3 owned) |
| **Optional AI paraphrase** | A presentation-only rewording derived *from* an already-finished authoritative result. | **Non-authoritative** (derivative) |

A future paraphrasing capability receives **only** an already-authoritative, finished `DetectionResult` /
governed explanation representation. It may rephrase wording. It may **never** change: `classification`,
`decision_severity`, `risk_level`, `detection_confidence`, governing rule, `matched_rules` / matched evidence,
official evidence basis, `recommended_actions`, source references, material uncertainty, or
`input_support_status`.

### 3.2 Source-faithful constraints

Any future paraphrase must remain traceable to the authoritative result and must **not**:

- invent a fact, official advice, or a source;
- drop or soften material uncertainty (`limitations` / `confidence_reason` must survive where governed);
- upgrade suspicion to detection (e.g. `SCAM_PATTERN_SUSPECTED` → `SCAM_PATTERN_DETECTED`) or downgrade
  detection to safe;
- say "safe" or "legitimate" when Phase 3 does not (RSK-009 — uncertainty is `INSUFFICIENT_EVIDENCE`, never
  "safe");
- change, add or reorder recommended actions, or introduce a new action code;
- add unsupported legal, police, payment or regulatory advice.

Official factual claims continue to come **only** from governed official evidence/reference material
(`evidence_basis` exact quotes); the paraphrase is a wording layer over those governed facts, never a new
source of fact.

### 3.3 Conceptual output artifact — `AIExplanationParaphrase`

Documented as a **conceptual, non-authoritative** artifact only (no runtime schema authored in WP6):

```text
AIExplanationParaphrase (conceptual; non-authoritative; presentation-only)
  paraphrase_id
  source_detection_result_digest   # pins the exact authoritative DetectionResult it rephrases
  source_explanation_digest        # pins the exact deterministic ExplanationResult
  text                             # bounded rewording
  ai_config_ref                    # WP4 config_ref
  adapter_model_provenance         # extractor_type = LLM, adapter/model + prompt-template/response-schema versions
  language                         # presentation language; does NOT expand governed support (AI-001 §25)
  requires_human_review            # marker where governed
  warnings / limitations           # carried, not dropped
```

It **must not** contain a second `classification`, `risk`, `severity`, `confidence`, verdict, or action set. The
authoritative `DetectionResult` remains the separate, sole decision object.

### 3.4 Deterministic future validation

A future paraphrase would be validated deterministically before any use:

- exact source `DetectionResult` pinned (digest match);
- exact deterministic `ExplanationResult` pinned (digest match);
- no decision-owned field present in the AI output;
- no new source/reference ID; no new recommended-action code;
- no unsupported certainty term; no "safe"/"legitimate" contradiction of the authoritative result;
- required uncertainty phrasing preserved where governed;
- source-digest linkage intact; output bounded; provenance sanitized.

**On validation failure: discard the paraphrase and use/show the original deterministic explanation unchanged.**

### 3.5 Failure behavior

Paraphrase failure (provider unavailable, malformed output, schema-invalid, decision-field contamination,
uncertainty dropped, digest mismatch) → **use the deterministic explanation unchanged**. A paraphrasing failure
**never** fails the authoritative `DetectionResult`, and never becomes `safe`, `NO_SCAM_PATTERN`, a new
classification, or a whole-evaluation `ERROR` — unless the underlying authoritative deterministic path
independently fails, in which case that authoritative failure propagates on its own terms (mirroring WP5 §12).

---

## 4. Feature flags (documented only)

Conceptual, default-OFF flags — **documented, not implemented**:

```text
ai.rule_drafting.enabled = false
ai.explanation_paraphrase.enabled = false
```

WP6 implements no executable feature flag, no environment handling and no service wiring. Deterministic-only
operation remains mandatory and is the production default (AI-001 §20, ADR-0007 §9).

## 5. Provider boundary

No provider is selected; the future design remains provider-neutral (ADR-0007 §6/§7/§14). No OpenAI/Anthropic/
Gemini default, API key, SDK, network, tools or agent loop is introduced. Canonical Phase-4 CI remains offline.
When a live provider is eventually evaluated, it is judged against ADR-0007's recorded selection *criteria* —
not chosen here.

## 6. Prompt-injection boundary

Rule-draft analyst/source content and `DetectionResult` content remain **DATA**. Both future capabilities
inherit WP4 containment: host-controlled prompt/template/config, no tools, a strict response contract,
deterministic post-generation validation, and fail-closed handling of the optional derivative. This is
**containment, not a claim that prompt injection is solved** (AI-001 §23; RSK-008).

## 7. Provenance and replay

Future draft/paraphrase artifacts require: run identity; `config_ref`; prompt-template version; response-schema
version; provider-adapter/model metadata *when one eventually exists*; and the source artifact digest (the
suggested-rule inputs digest, or the source `DetectionResult`/`ExplanationResult` digests). This reuses the WP4
`AIExtractionResult` / `config_ref` provenance model and the WP4/WP5 pinned-artifact replay discipline.

Historical replay uses stored/pinned artifacts and **never re-calls a model**. A fresh AI generation is a new
revision/run with a new run identity — never presented as replay (AI-001 §19; WP4; WP5 §16).

## 8. Privacy

Both capabilities reuse the Phase-4 minimum-necessary and credential-masking policy (AI-001 §26 / PD-3). WP6
implements **no masking code and no text substitution**. Because no provider is selected, WP6 makes **no
provider privacy/retention/logging guarantee**; such guarantees remain requirements for a later governed
decision.

## 9. Failure model (conceptual)

| Capability | Failure | Result |
|---|---|---|
| Rule drafting | Provider/validation/mapping failure | No draft; no publication; the existing deterministic system is unaffected |
| Explanation paraphrase | Provider/validation/digest failure | Use the deterministic explanation unchanged; authoritative `DetectionResult` untouched |

No optional-capability failure becomes `safe`, `NO_SCAM_PATTERN`, a new classification, or a whole-evaluation
`ERROR`, unless the underlying authoritative deterministic path independently fails.

## 10. Change surface and non-implementation statement

WP6 authors exactly one artifact: this specification, `docs/04-ai/AI-001-WP6-deferred-capabilities.md`. It adds
**no runtime Python** for these capabilities and does not modify `knowledge/ai/integration.py`,
`knowledge/ai/governance.py`, `knowledge/ai/replay.py`, `knowledge/runtime/*`, `knowledge/schemas/*`,
`knowledge/rules/*`, `knowledge/taxonomies/*`, `run_all.py` or `ci_selftest.py`. WP7 retains ownership of
canonical AI CI wiring and the adversarial fixture matrices.

Even though WP6 is specification-only, the existing offline regressions are run unchanged to prove no drift:
`validate_ai_integration.py`, `validate_ai_governance.py`, `validate_ai_extraction.py`,
`validate_ai_provider.py`, `run_all.py`, plus `git diff --check` and an explicit whitespace check on this new
document.

## 11. Limitations (G-09)

WP6 is governance/design specification only. **G-09 remains OPEN.** No accuracy, precision, recall,
false-positive/negative rate, rule-generation quality, paraphrase quality, improved-detection or
production-readiness claim is made or supported. Independent review belongs to a separate session. Stop without
commit. Do not start WP7, Phase 5 or UI.

## 12. Document review checklist (§22 mapping)

| Required statement | Where |
|---|---|
| Rule drafting is suggestion-only | §2.1, §2.3 |
| Human approval mandatory | §2.5 (FR-075) |
| No automatic publication | §2.1, §2.3 forbidden fields, §2.4 |
| No invented evidence / IDs | §2.2, §2.4 |
| No self-learning | §1.5, §2.5, §3 |
| Paraphrase is presentation-only | §3.1, §3.3 |
| `DetectionResult` remains authoritative | §3.1, §3.3 |
| Paraphrase cannot change actions/decision/uncertainty | §3.1, §3.2, §3.4 |
| Failure falls back to original deterministic behavior | §3.5, §9 |
| No provider selected | §1.3, §5 |
| No API key / network / tools | §1.3, §5, §6 |
| Replay ≠ regeneration | §1.6, §7 |
| G-09 OPEN | header, §1.7, §11 |
| WP6 contains no runtime implementation | header, §1 intro, §10 |
