# GATE-005 — Phase 2 checkpoint: indicator families + extraction contracts (WP2)

| Field | Value |
|---|---|
| Document ID | GATE-005 |
| Version | 1.0 |
| Status | **Checkpoint** — assesses WP2 (indicator families + extraction contracts) |
| Phase assessed | Phase 2 — Knowledge engineering (WP2) |
| Owner role | Technical Program Director |
| Dependencies | GATE-004, KB-001, KB-002, RESEARCH-003, RESEARCH-004, G-07 negative-indicator library, taxonomy v2.0 + dimensions-v1 |
| Gate result | **`PASS` — WP2 COMPLETE; Phase 2 still IN PROGRESS (WP7 CI + ADR-0004/0014 remain); Phase 3 NOT STARTED** |
| Phase 1 status | **`PARTIAL`** — unchanged (language scope + full source retrievability still fail; [GATE-001 §7](GATE-001-phase-1-assessment.md)) |
| Last updated | 2026-08-29 |

---

## 1. Scope
WP2 defines the **stable, versioned contract between raw TrustLens input and the deterministic
detection knowledge layer** — the typed boundary that stops the rule engine consuming arbitrary model
prose. It does **not** build the production extractor (NLP/LLM/OCR/URL reputation); that is later-phase
work. Full specification: [KB-002](../02-knowledge/KB-002-extraction-contracts.md).

## 2. What WP2 delivered

**Four contract schemas** (`knowledge/schemas/`, Draft 2020-12):
- `input-envelope.schema.json` — raw+normalized text, 9 modalities, channel, parties, extracted
  primitives (urls/phones/upi/amounts/codes), attachments, thread, user context, provenance, and a
  **data-minimisation `privacy.redaction`** block. Language/script carried as data — OI-04/ADR-0014
  **not resolved**.
- `observation.schema.json` — 13 typed observation types with **polarity**, **attribution**
  (first-party/reported/quoted/hypothetical), **mood**, an **actor/action/target/pretext/pressure
  frame**, **payment_direction**, spans, extraction confidence, provenance, and the
  OBSERVED/UNKNOWN/AMBIGUOUS/NOT_OBSERVED/NOT_APPLICABLE status.
- `url-observation.schema.json` — structural URL facts; reputation/allowlist/brand-match **reserved at
  UNKNOWN/NOT_EVALUATED** (no service invented).
- `indicator-observation.schema.json` — the rule-engine boundary object; **structurally forbids a
  verdict/risk/severity**.

**Indicator families** (`indicator-families-v1.json`) — **28 families** partitioning the **63 positive
indicators** exactly once (the file the registry named in `superseded_by`); each declares observation
inputs, indicator outputs, dimensions, negative/override interactions, ambiguities, examples.

**15 golden fixtures** (`extraction/extraction-fixtures-v1.json`) — the STEP-14 set incl. OTP
directionality, negation, reported/quoted speech, UPI-PIN pay vs receive, remote-access banking vs
benign IT support, wallet-connect, task-app, KYC chain, adversarial-benign advisory, ambiguous
direction, and the safety-wording decoy. Each fixture's projected signal set is **derived** from its
indicator observations, so it cannot drift, and cross-references the seed/suppression case it mirrors.

**Extraction-coverage matrix** (`extraction/rule-extraction-coverage-v1.json`) — derived from rules +
families + library. **Scope: 26 entries = the 25 encoded starter rules (`kind = COMPOSITE`) + TL-SUP-001,
the non-starter SUPPRESSION-infrastructure rule, covered separately.** Across all 26: 23
`CURRENTLY_EXTRACTABLE`, 2 `PARTIAL_REQUIRES_FUTURE_EXTRACTOR` (TL-JOB-003 → THREAD_CONTEXT;
TL-MAL-002 → DEVICE_STATE), 1 `UNOBSERVABLE` (TL-PAY-003 → PAYEE_IDENTITY). The 25 starters split
22/2/1; TL-SUP-001 is the +1 `CURRENTLY_EXTRACTABLE`.

**8th validator** (`validate_extraction.py`) — schema + cross-file lint for all of the above.

## 2a. WP2 completion — explicit record

| Fact | Status |
|---|---|
| **WP2** | **COMPLETE** |
| **25 encoded starter rules covered** | ✅ (all `kind = COMPOSITE`) |
| **TL-SUP-001 (non-starter suppression) covered separately** | ✅ (the 26th matrix entry) |
| **Total matrix entries** | **26** = 25 starters + TL-SUP-001 |
| **CURRENTLY_EXTRACTABLE** (across all 26) | **23** (25 starters: 22 · TL-SUP-001: 1) |
| **PARTIAL_REQUIRES_FUTURE_EXTRACTOR** (across all 26) | **2** — TL-JOB-003, TL-MAL-002 |
| **UNOBSERVABLE** (across all 26) | **1** — TL-PAY-003 |
| **Phase 2** | **IN PROGRESS** (WP7 CI + ADR-0004/0014 remain) |
| **Phase 3 (DET-001)** | **NOT STARTED** |
| **Production extractor (NLP/LLM/OCR/URL reputation)** | **NOT IMPLEMENTED** — contract only |
| **Validators** | **8 / 8 green** |

## 3. The boundary (why the rule engine is untouched)
The current `rule_runner` consumes a flat set of indicator IDs. WP2 makes that set the **projection**
`{ io.indicator_id : io.matched == OBSERVED }` of the indicator-observation layer — a strict,
backward-compatible superset of the hand-declared tags. **No rule, the taxonomy, the negative library
or the runner changed.** The 18 published rules and all 55 runner cases are unaffected.

## 4. Effect on the encoded rules
**None to logic or publication status.** The families reorganise positives without changing any
indicator ID, polarity, evidence class or strength; the negative library remains the home of negatives.
Publication status unchanged: **18 PUBLISHED**.

## 5. Machine-enforced vs human-review controls
- **Machine (8 validators):** the seven prior checks + `validate_extraction.py` (schema validity of
  four contracts and every fixture object; indicator resolution + polarity + no DEPRECATED emission;
  the 28↔63 partition; dimension/negative/override references; fixture cross-refs and projection
  equality; the verdict-key ban; the URL-assessment reservation; coverage-matrix agreement).
- **Human (KB-002 §13):** soundness of observation types/families; safeguarding scope (TAX-11 stays out
  of extraction); ADR-0014 language and ADR-0004 storage decisions.

## 6. Validator / test results (all green)
```
manual_evidence_check.py       PASS
phase1_consistency_check.py    35/35
validate_taxonomy.py           PASS  (11 categories, 42 subcategories, 50 dimension terms)
validate_kb.py                 PASS  (IDs unique across namespaces; versions valid)
validate_negative_library.py   PASS  (29 indicators, 6 overrides)
validate_rules.py              51/51 (26 rules, 18 PUBLISHED, 25 fixtures rejected)
rule_runner.py                 55/55 cases; 24 rules exercised; 6 overrides; 0 await encoding
validate_extraction.py         PASS  (4 schemas; 28 families ↔ 63 positives; 15 fixtures; 26 rules mapped)
```

## 7. Remaining Phase 2 work

**Phase 1 remains `PARTIAL`** (unchanged) and **Phase 2 remains IN PROGRESS**.

| WP | Status |
|---|---|
| WP2 indicator families + extraction contracts | ✅ **done** (this gate) |
| WP5 taxonomy | ✅ done |
| WP6 KB-001 | ✅ done |
| WP7 schema validation in CI | 🟡 **eight** validators exist; CI workflow wiring remains |
| WP8 ADR-0004 (storage), ADR-0014 (language) | open; ADR-0014 blocked on OI-04 |

## 8. Decision
**Stop here, as instructed.** WP2 passes its acceptance criteria: a typed, versioned, storage- and
language-agnostic boundary now separates raw input from the deterministic layer; the extractor cannot
emit a verdict; families formalise the positive vocabulary; the coverage matrix makes implementation
sequencing explicit; and the rule engine is untouched (all prior checks green). **Phase 2 remains IN
PROGRESS.** Phase 3 (DET-001) must not begin until explicitly approved.

## 9. Change history
| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-29 | WP2 assessed: four extraction contracts, 28 indicator families (63-positive partition), 15 golden fixtures, 26-entry coverage matrix (25 starters + TL-SUP-001), 8th validator. Increment PASSES; Phase 2 remains IN PROGRESS; rule set and prior gates unaffected. WP7 CI wiring + ADR-0004/0014 remain. | Technical Program Director |
