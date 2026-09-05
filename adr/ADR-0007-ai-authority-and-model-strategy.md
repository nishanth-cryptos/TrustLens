# ADR-0007 — AI authority boundary and provider-neutral model strategy

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date | 2026-09-05 |
| Owner role | Chief Architect / Principal Security Engineer |
| Related | `MP §3, §11, §15`, [PROGRAM-001](../docs/00-program/PROGRAM-001-program-charter.md) (CON-003, NG-07/08, FR-072…077), [SRS-001](../docs/00-program/SRS-001-software-requirements-specification.md) (REQ-61…66, NFR-16), [DET-001 §17](../docs/03-detection/DET-001-deterministic-detection-engine.md), [ADR-0002](ADR-0002-defer-python-intelligence-service.md), [AI-001](../docs/04-ai/AI-001-ai-intelligence-layer.md), [risk-register](../docs/00-program/risk-register.md) RSK-008/RSK-012, G-09 (RSK-003) |

## Context and constraints

Phase 3 delivered a closed, deterministic detection engine (`phase3-wp8-v1.0`; final boundary
`evaluate_detection_from_governed(...)`, engine_version `1.0.0`, profile `mvp-default`, canonical gate 18/18).
Phase 4 introduces AI, which the master prompt sequences last and behind a hard gate: `MP §11` requires the
deterministic system to remain usable when AI is degraded/unavailable, and CON-003/NG-07 make the rule engine
the authority. Submitted content is attacker-authored (RSK-008, score 16): any content reaching a model is a
direct prompt-injection vector. G-09 (RSK-003) means no efficacy is measurable. This ADR fixes **what authority
AI has** and **how the model layer is structured** — deliberately *before* any model is called or selected.

`ADR-0002` already defers the standing AI service runtime; this ADR governs the AI *contract and authority*,
whose realisation in Phase 4 is a **bounded, offline, Fake/Fixture-provider reference only** (ratified PD-1).

## Decision

**AI is an extraction/advisory layer whose untrusted output is deterministically validated into governed
observations; the deterministic Phase-3 engine remains the sole decision authority. The model layer is
provider-neutral, and no vendor is selected in Phase 4.**

1. **Deterministic Phase 3 is the final decision authority.** AI cannot directly set, override, or bypass
   decision semantics. Validated AI-derived observations MAY *indirectly* affect the decision because, once
   validated, they are legitimate governed Phase-3 input — but only the deterministic rules decide.
2. **AI is extraction/advisory only.** It proposes candidate `Observation` / `IndicatorObservation` data,
   normalises entities, and (deferred) may assist explanation wording; it never authors a decision field.
3. **Model output is untrusted.** Strict schema + semantic + RuntimeKnowledge ID/taxonomy membership +
   grounding + reference-integrity validation is **mandatory** before any governed observation is produced.
4. **Atomic fail-closed response policy (MVP).** If any item in a model response is invalid (schema, forbidden
   field, unknown indicator/taxonomy id, invalid enum/polarity, dangling/invalid reference, invalid
   span/offset, grounding failure, or decision/risk/score/action injection), the **entire response is
   rejected**. No partial acceptance; no "decisive item" concept. A valid response may contain zero
   observations.
5. **The extraction model receives no tools** — no browser, shell, filesystem, network, reputation lookup, or
   rule-publication authority.
6. **Provider-neutral core; no vendor selected in Phase 4.** The domain depends on a conceptual
   `AIExtractorProvider` interface, never a vendor SDK.
7. **No live provider is required for Phase-4 canonical closure**, and **no API key** is used. Canonical CI is
   offline (fixtures + fake provider).
8. **Replay uses persisted validated observation artifacts** — a historical replay never re-calls a model; an
   AI re-extraction is a new evaluation.
9. **AI feature flags default OFF; deterministic-only mode is mandatory** and is the production default.
10. **LLM-only extraction confidence ≤ `MEDIUM`** (DET-001 §17); the **model does not self-report confidence**
    in the MVP; the deterministic adapter assigns it and may only downgrade (to `LOW` → Phase-3 `UNKNOWN`).
11. **No AI fraud probability/score** ever enters governed data.
12. **No uncontrolled learning** (NG-08): prompts/templates/rules never silently adapt from feedback.
13. **Human governance for future AI rule suggestions** (FR-075): AI may only produce a draft; publication
    requires the existing knowledge-editor + peer/security review lifecycle. *(Design only in Phase 4.)*
14. **Actual external provider selection is deferred** to later architecture/integration/privacy work.

### Provider-selection criteria (for the deferred decision — not a selection)

When a live provider is later evaluated, it is judged against: structured-output reliability;
latency; cost; privacy / data-handling and retention posture; model pinning/versioning; enterprise deployment
options; regional / data-residency requirements; local / on-prem capability; provider availability/reliability;
testability (record/replay, deterministic fixtures); and SDK isolation (swappable behind `AIExtractorProvider`
with no domain dependency on the vendor). This ADR records the **criteria**, not a choice.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **AI as validated extraction feeding the deterministic engine (this ADR)** | Preserves CON-003/NG-07; AI never authoritative; fail-closed; provider-neutral; replayable | Requires a strict validation gauntlet and an intermediate contract | ✅ **Selected** |
| AI produces the final classification/risk directly | "Simpler" single call | Violates CON-003/NG-07/DET-001 §17; unauditable; injection sets the verdict; no replay determinism | ❌ Rejected |
| Model authors the governed observation schema directly | One fewer schema | Model would author provenance/confidence it must not own; weaker injection containment; couples model quirks to governed contracts | ❌ Rejected (use an intermediate AI-extraction contract) |
| Select a vendor now and integrate the SDK | Faster path to a live demo | Premature per ADR-0002; no privacy/residency decision yet; vendor lock; needs an API key in scope | ❌ Rejected |
| Give the extraction model tools (browsing/reputation) | Richer single-shot extraction | Turns prompt injection into action/tool escalation; violates FR-077 containment | ❌ Rejected |
| Partial-item acceptance from a mixed-validity response | Salvages "good" items | A single crafted item can steer which items survive; MVP cannot bound that safely | ❌ Rejected for MVP (deferred, separately governed) |
| Let AI extraction expand language support because a model understands the language | Broader coverage | AI ability ≠ governed product support; would silently expand scope past ADR-0014 governance | ❌ Rejected |

## Justification

The strongest guarantee is structural: because AI output is untrusted and only becomes governed input through a
deterministic validation gauntlet, and because the deterministic engine is independently complete and
replayable, **there is no path by which a model — however manipulated — can set, override, or bypass a
TrustLens decision**. Atomic fail-closed acceptance, no model tools, and RuntimeKnowledge membership validation
convert the prompt-injection surface (RSK-008) from an authority risk into, at worst, a *rejected extraction*
that degrades gracefully to deterministic-only operation (FR-076). Deferring vendor selection keeps the core
provider-neutral and testable offline, and keeps the privacy/residency decision where it belongs — with later
architecture work — rather than being forced by an early SDK choice. No efficacy is claimed (G-09 open).

## Consequences

**Positive.**
- Phase 3 (`phase3-wp8-v1.0`) remains the **sole final decision authority**; the AI layer cannot set, override, or bypass a decision.
- The AI provider remains **replaceable/provider-neutral** — no vendor lock, swappable behind `AIExtractorProvider`.
- Phase 4 can be **validated without a live provider or API key** (offline fixtures + fake provider).
- **Deterministic-only operation** remains always available and is the production default.
- Model **non-determinism is quarantined** before the governed observation boundary; the engine stays deterministic.
- **Historical replay does not require model re-execution** — it consumes the persisted validated observation artifact.

**Trade-offs.**
- AI **cannot directly optimise or override** final verdicts (by design), so any extraction improvement must flow through governed observations and the deterministic rules.
- Model output requires **additional validation / grounding / provenance** work (an intermediate contract, a validation gauntlet, an audit artifact).
- **Live-provider value is deferred** until later architecture/integration/privacy decisions.
- Extraction **coverage may be bounded** by the strict atomic fail-closed policy (a single invalid item rejects the whole response in the MVP).
- **Provider-neutrality adds adapter/configuration complexity** (an interface + config pinning + fixtures) versus a single hard-wired SDK.

## Risks

| Risk | Mitigation (this ADR / AI-001) |
|---|---|
| Prompt injection via hostile submitted content (RSK-008) | content-as-data only, extraction-only role, **no tools**, strict schema + bounds, decision-field rejection, grounding, **atomic rejection**, post-model validation |
| Hallucinated observations | schema + semantic validation, **grounding**, atomic rejection; unproven extraction is capped and gated, never authoritative |
| Unknown indicator / taxonomy IDs | **RuntimeKnowledge membership** validation; unknown id → whole-response rejection |
| Forged grounding / span references | offset/reference-integrity proof; transient excerpt must match the source slice exactly |
| Privacy / credential leakage to a future provider | **credential masking** (`<OTP_VALUE>`/`<PIN_VALUE>`/`<CARD_PAN>`), minimum-necessary content; no provider-retention claim made |
| Provider / model drift | pinned model id + prompt-template + response-schema versions in the AI audit artifact (`config_ref`); replay uses persisted observations, not re-calls |
| Provider outage / throttling | **feature flags default OFF**, provider-neutral, **deterministic fallback** (FR-071/076); typed failure never maps to `NO_SCAM_PATTERN` |
| Accidental expansion of AI authority | AI authors no decision field; decision fields structurally forbidden in the intermediate contract; this ADR + CON-003/NG-07 |
| Accidental language-support expansion | governed en/Latn support (ADR-0014) is Phase-3-owned; AI ability ≠ product support |
| Future rule-drafting poisoning (RSK-012) | AI rule drafting is **draft-only, deferred**; publication requires human/peer/security governance (FR-075) |
| Efficacy overclaim while G-09 is open | no accuracy/precision/recall claim; Phase 4 measures contract/grounding/injection-resistance/regression only |

## Reversal cost

**High.** The reversible surface is not the provider (swapping or specialising a provider later is Low, precisely because the core is provider-neutral). The decision actually being recorded is a **safety/authority boundary** — AI is non-authoritative, model output is untrusted, validation is mandatory and fail-closed, and the deterministic engine is the sole decision authority. Reversing *that* (letting AI set or influence a decision field directly) would invalidate the prompt-injection containment (RSK-008), the replay-determinism guarantee, and the CON-003/NG-07 governance anchor, and would require re-architecting the trust boundary and re-validating the whole detection path. The provider-neutrality and deferral choices are cheap to revisit; the **authority boundary is deliberately expensive to reverse**, and that is the point. The value is not lowered to make reversal cheap.

## Validation plan

Concrete proof points land in later Phase-4 WPs; canonical validation is offline and requires no live provider or API key.

- **WP2** — a provider-neutral Fake/Fixture `AIExtractorProvider`; **no vendor SDK** imported.
- **WP3** — schema validation, semantic validation, RuntimeKnowledge indicator/taxonomy **membership**, grounding/reference integrity, and **atomic fail-closed rejection** proven over fixtures.
- **WP4** — a prompt-injection fixture matrix; a **no-tools** proof; the AI provenance/replay artifact (`AIExtractionResult` + `config_ref`); **LLM-only confidence ≤ MEDIUM** (adapter-assigned, model self-report absent).
- **WP5** — feature flag **default OFF**; **deterministic-only fallback**; the regression invariant **same governed observations ⇒ same Phase-3 `DetectionResult`**.
- **WP7** — offline canonical CI; malformed/adversarial fixtures; a **`ci_selftest` defect proving the AI gate bites**; **no live provider / API key required**; **G-09 remains open** (no efficacy claim).
