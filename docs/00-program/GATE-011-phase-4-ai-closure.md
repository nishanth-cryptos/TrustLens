# GATE-011 — Phase 4 AI closure: bounded offline AI reference/scaffold (CLOSURE CANDIDATE)

| Field | Value |
|---|---|
| Document ID | GATE-011 |
| Version | 1.0 |
| Status | **CLOSURE CANDIDATE** — bounded offline AI reference/scaffold; **not** AI production readiness |
| Phase assessed | Phase 4 — AI intelligence layer, bounded offline reference + canonical CI closure (P4-WP7) |
| Owner role | Chief Architect / Principal Security Engineer / Detection Architect |
| Dependencies | AI-001, ADR-0007, ADR-0002, DET-001 §17, PROGRAM-001 (CON-003, NG-07/08, FR-072…077), SRS-001 (REQ-61…66, NFR-16), RSK-008/RSK-012, G-09 (RSK-003), GATE-010 |
| Merged baseline | `main` @ P4-WP6 merge `936f8c3cd917ac5742a463bbd0df2ba4d4f664bc` |
| Deliverables | [AI-001-WP7-phase4-closure.md](../04-ai/AI-001-WP7-phase4-closure.md); `knowledge/ai/fixtures/phase4-adversarial-fixtures-v1.json`; `knowledge/validation/validate_ai_phase4_closure.py`; `run_all.py` / `ci_selftest.py` / `knowledge-validation.yml` updates |
| Last updated | 2026-09-05 |

---

## 1. What this gate asserts (and what it does not)

This gate assesses **Phase-4 engineering/governance closure of the bounded, offline, Fake/Fixture-provider AI
reference/scaffold** (PD-1, ADR-0002/0007). It asserts that the AI extraction layer is fully specified, built as
a bounded offline reference, strictly validated, contained, integrated behind a default-OFF flag with exact
deterministic fallback, and now covered by a durable adversarial fixture matrix folded into the single canonical
`run_all.py` gate whose self-test proves it bites a representative Phase-4 defect.

It does **not** assert AI production readiness, that AI may decide fraud, or any AI efficacy. It makes **no
accuracy / precision / recall / false-positive/negative-rate / detection-effectiveness claim**. Prompt injection
is **contained / bounded / fail-closed**, never solved. No live model was called; no API key, vendor SDK,
network or tool was added; no Phase-3 semantics or promoted schema changed. **G-09 remains OPEN (RSK-003).**

## 2. Programme / phase status

| Item | Status |
|---|---|
| Phase 1 | **PARTIAL** — unchanged and independent |
| Phase 2 | **PASS** — unchanged |
| Phase 3 | **CLOSED** at `phase3-wp8-v1.0` — unchanged; `ENGINE_VERSION = 1.0.0`; no semantics modified |
| Phase 4 | **bounded offline reference/scaffold — CLOSURE CANDIDATE** (this gate) |
| Phase 5 | **NOT started** |
| UI | **NOT started** |

## 3. Phase-4 closure criteria

| # | Criterion | Status |
|---|---|---|
| 1 | P4-WP1 AI authority + intermediate contract + design gate | ✅ AI-001, ADR-0007, GATE-010 |
| 2 | P4-WP2 provider-neutral **offline** adapter + `FakeProvider` (no vendor SDK) | ✅ `validate_ai_provider.py` 65/65 |
| 3 | P4-WP3 strict untrusted-response validation (schema/size/nesting, RuntimeKnowledge membership, grounding, references, atomic fail-closed) | ✅ `validate_ai_extraction.py` 70/70 |
| 4 | P4-WP4 containment + `config_ref` provenance + capped categorical confidence + sealed audit/replay | ✅ `validate_ai_governance.py` 300/300 |
| 5 | P4-WP5 governed mapping + Phase-3 integration + default-OFF flag + exact deterministic fallback + exact consumed-artifact pinning | ✅ `validate_ai_integration.py` 282/282 |
| 6 | P4-WP6 deferred rule-drafting / explanation-paraphrasing **specification** (design only) | ✅ AI-001-WP6 |
| 7 | P4-WP7 durable offline adversarial fixture matrix + cross-WP closure validator | ✅ fixtures v1 (18 cases) + `validate_ai_phase4_closure.py` 189/189 |
| 8 | All executable Phase-4 validators in the single canonical `run_all.py` gate, dependency-ordered | ✅ 23/23 checks; `--json` lists all five |
| 9 | Quality-gate self-test proves the gate bites a representative Phase-4 defect | ✅ `ci_selftest.py` 7/7 (AI default-ON caught by `validate_ai_integration.py`) |
| 10 | Offline preflight covers Phase-4 validators (no network/subprocess import) | ✅ `run_all.py` preflight over full `ORDER` |
| 11 | CI path coverage includes `docs/04-ai/**` for both push and pull_request | ✅ shared anchor in `knowledge-validation.yml` |
| 12 | No live model / vendor SDK / API key / network / tools | ✅ security-name search clean |
| 13 | No self-learning (NG-08) | ✅ AI-001 §30; WP6 §1.5 |
| 14 | No Phase-3 semantic change; `ENGINE_VERSION = 1.0.0`; no promoted-schema change | ✅ Phase-3 tree untouched |
| 15 | G-09 OPEN; no efficacy claim | ✅ this gate §1; AI-001-WP7 §12 |

## 4. Adversarial matrix coverage

18 literal-expectation cases across feature-flag, valid-integration, prompt-injection-content, decision-field
injection (incl. self-reported confidence), malformed, unknown-indicator, wrong-input-binding, grounding,
empty-extraction, confidence-cap (UNKNOWN/AMBIGUOUS→LOW, determinate→≤MEDIUM), support-first, provider-failure,
and structural-semantics families; plus programmatic probes for lone surrogate / non-finite / bytes / set /
opaque / cycle / deep-nesting host material, caller-mutation TOCTOU, exact-artifact replay, and replay
tampering. The synthetic accepted-AI fixture changes `INSUFFICIENT_EVIDENCE` → `SCAM_PATTERN_DETECTED` solely by
supplying governed data to the unchanged engine — **wiring proof only, not efficacy**.

## 5. Residual findings (recorded, non-blocking)

- **WP5 (runtime, deferred):** broader-than-ideal optional-path mapping exception normalization; an effectively
  unreachable dangling-host-ref / generated-AI-ID collision edge case. Recorded as residual LOW technical debt
  for Phase-5 / later hardening; not reopened in WP7.
- **WP6 (documentation):** two prior LOW doc nits corrected in WP7 (`detection_confidence_reason` naming;
  cross-reference precision).

## 6. Finalisation condition

This gate is a **closure candidate**. Phase 4 becomes **PASS** only upon **all** of:

1. Independent review **APPROVE**;
2. canonical local gate **PASS** (`run_all.py`);
3. quality-gate self-test **PASS** (`ci_selftest.py`);
4. remote **GitHub Actions PASS**;
5. **merge to main**.

Once those occur, the merged gate constitutes **Phase-4 PASS** (bounded offline reference/scaffold). This gate
does **not** modify GATE-010's historical P4-WP1 design-checkpoint assertions.

## 7. Explicit non-claims

- Phase 4 is **not** production-ready and AI is **not** the decision authority (CON-003, NG-07).
- **No** AI efficacy / accuracy / precision / recall / false-positive/negative-rate / detection-effectiveness is
  claimed. **G-09 remains OPEN.**
- Prompt injection is contained/bounded/fail-closed, **not** solved.
- Live provider, vendor selection, API keys, network egress and deployment topology remain **deferred** to
  Phase-5 / later architecture work (ADR-0002/0007).
- Phase 5 has **not** started. UI has **not** started.

## 8. What this gate authorises

Upon satisfaction of the §6 finalisation condition, Phase-4 closes as a bounded offline reference/scaffold. It
does **not** authorise a live-provider call, an API key, a deployed AI service, a vendor selection, any Phase-3
semantic change, any promoted-schema change, Phase 5, or UI. Those require fresh governance decisions.
