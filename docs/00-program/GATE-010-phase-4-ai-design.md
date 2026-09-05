# GATE-010 — Phase 4 AI design gate: AI intelligence layer authority + contracts (DESIGN)

| Field | Value |
|---|---|
| Document ID | GATE-010 |
| Version | 1.0 |
| Status | **Gate — Phase 4 DESIGN checkpoint (P4-WP1)** |
| Phase assessed | Phase 4 — AI intelligence layer, authority + contracts, design only |
| Owner role | Chief Architect / Principal Security Engineer / Detection Architect |
| Dependencies | AI-001, ADR-0007, ADR-0002, DET-001 §17, PROGRAM-001 (CON-003, NG-07/08, FR-072…077), SRS-001 (REQ-61…66, NFR-16), RSK-008/RSK-012, G-09 (RSK-003) |
| Gate result | **DESIGN AUTHORED — bounded implementation authorised ONLY after WP1 documents pass review** |
| Phase 3 status | **`CLOSED`** at `phase3-wp8-v1.0` — unchanged; no Phase-3 semantics modified |
| Phase 2 status | **`PASS`** — unchanged |
| Phase 1 status | **`PARTIAL`** — unchanged and independent |
| Phase 5 status | **NOT started** |
| UI status | **NOT started** |
| Last updated | 2026-09-05 |

---

## 1. What this gate asserts (and what it does not)

This is a **design** gate for P4-WP1. It asserts that Phase 4 has produced an authoritative, internally
consistent design/governance set for the AI intelligence layer: the AI authority boundary, the
deterministic-engine authority boundary, the intermediate AI extraction contract, the model-output trust
boundary, grounding requirements, provenance/replay strategy, prompt-injection containment, feature-flag and
deterministic-fallback strategy, privacy/credential-masking requirements, the provider-neutral model strategy,
the Phase-4 WBS and the closure gate.

It does **not** assert that any AI runtime exists (none does), that AI is production-ready, or any AI efficacy.
It makes **no accuracy/precision/recall/fraud-detection-rate claim** — **G-09 remains OPEN** (RSK-003). No live
model was called; no API key is used; no vendor is selected; no promoted schema or Phase-3 semantics changed.

## 2. Deliverables

| Artefact | Path |
|---|---|
| AI intelligence layer design authority | `docs/04-ai/AI-001-ai-intelligence-layer.md` |
| AI authority + provider-neutral model strategy | `adr/ADR-0007-ai-authority-and-model-strategy.md` (Accepted) |
| This gate | `docs/00-program/GATE-010-phase-4-ai-design.md` |

Threat modelling is a section of AI-001 (§23, §33) for WP1; a standalone threat-model document is not created
at this stage and is deferred to ARCH-001 (Phase 5) STRIDE work.

## 3. Ratified programme decisions carried into this gate

- **PD-1** — Phase 4 = authoritative design **plus** a later bounded **offline** Fake/Fixture reference/scaffold; **not** a deployed AI service; live provider/runtime deferred (ADR-0002).
- **PD-2** — the reference scaffold may be Python (the Phase-3 engine is Python); the Java-core/Python-service vs. actual-Python-engine divergence is **recorded for Phase-5 ARCH-001**.
- **PD-3** — external-model credential policy: mask the value, preserve the type (`<OTP_VALUE>`, `<PIN_VALUE>`, `<CARD_PAN>`); Phase-4 requirement/fixture policy only; no external call now.
- **PD-4** — AI rule drafting and AI explanation paraphrasing are **DESIGN ONLY / implementation deferred**; WP6 deterministic explanation remains authoritative.
- **PD-5** — **no vendor selected**; ADR-0007 is provider-neutral and records selection *criteria* only; no API key in Phase-4 scope.

## 4. Gate criteria and status

| # | Criterion | Status |
|---|---|---|
| 1 | AI authority boundary stated precisely ("AI cannot directly set, override, or bypass decision semantics"; validated observations may indirectly affect the decision as governed input) | ✅ AI-001 §4, ADR-0007 §1 |
| 2 | Deterministic Phase-3 authority preserved; no Phase-3 semantic change | ✅ AI-001 §5, §34; ADR-0007 §1 |
| 3 | Intermediate AI extraction contract (JSON, `additionalProperties:false`, decision-fields structurally forbidden) | ✅ AI-001 §8, ADR-0007 alt-table |
| 4 | Atomic fail-closed acceptance (MVP) — whole-response rejection; no "decisive item" | ✅ AI-001 §9, ADR-0007 §4 |
| 5 | Indicator/taxonomy RuntimeKnowledge membership validation | ✅ AI-001 §11 |
| 6 | Grounding = "points to submitted input", not "interpretation is true"; offset/reference proof | ✅ AI-001 §12 |
| 7 | Confidence: model does not self-report (MVP); adapter assigns; LLM-only ≤ MEDIUM; LOW → Phase-3 UNKNOWN | ✅ AI-001 §14, ADR-0007 §10 |
| 8 | Provenance distinct (`extractor_type=LLM` + `config_ref`); no promoted-schema change | ✅ AI-001 §17, §18 |
| 9 | Replay never re-calls the model; re-extraction is a new evaluation | ✅ AI-001 §19, ADR-0007 §8 |
| 10 | Feature flags default OFF; deterministic-only mandatory | ✅ AI-001 §20, ADR-0007 §9 |
| 11 | Provider-failure → deterministic degradation; never `NO_SCAM_PATTERN` | ✅ AI-001 §21, §22 |
| 12 | Prompt-injection defence-in-depth (contained/bounded/fail-closed) + no tools | ✅ AI-001 §23, §24 |
| 13 | Language/script boundary preserved (AI ability ≠ governed support) | ✅ AI-001 §25 |
| 14 | Privacy / credential masking (PD-3) | ✅ AI-001 §26 |
| 15 | No self-learning (NG-08) | ✅ AI-001 §30 |
| 16 | Provider-neutral; no vendor selected; no API key | ✅ AI-001 §31, ADR-0007 §6/§7/§14 |
| 17 | Threat-intel kept separate from generative AI | ✅ AI-001 §32 |
| 18 | Phase-3 regression guarantee (identical governed observations ⇒ identical `DetectionResult`) | ✅ AI-001 §34 |
| 19 | G-09 open; no efficacy claim | ✅ AI-001 §37, this gate §1 |
| 20 | P4 WBS + Phase-4 closure criteria defined | ✅ AI-001 §35, §36 |

## 5. What this gate authorises

Upon review-approval of the WP1 documents, **bounded, offline** implementation of P4-WP2…WP7 (provider-neutral
reference adapter with a Fake/Fixture provider, strict validation, prompt-injection containment,
provenance/replay, Phase-3 integration with deterministic fallback, and offline CI closure) is authorised. It
does **not** authorise a live-provider call, an API key, a deployed AI service, a vendor selection, any
Phase-3 semantic change, any promoted-schema change, Phase 5, or UI.

## 6. Explicit non-claims

- Phase 4 is **not** complete; this is the WP1 design checkpoint only.
- AI is **not** production-ready and is **not** the decision authority.
- **No** AI efficacy / accuracy / precision / recall / fraud-detection-rate is claimed. **G-09 remains OPEN.**
- Phase 5 has **not** started. UI has **not** started.

## 7. Outcome

**Phase-4 WP1 design authored and internally consistent.** Bounded offline implementation is authorised only
after these documents pass review. No runtime, no live provider, no vendor, no API key, no Phase-3/schema
change.
