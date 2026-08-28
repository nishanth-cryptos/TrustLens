# GATE-003 — Phase 2 checkpoint: G-07 closure + eligible-rule encoding

| Field | Value |
|---|---|
| Document ID | GATE-003 |
| Version | 1.0 |
| Status | **Checkpoint** — assesses the G-07 negative-indicator library and the 11 eligible-rule encoding increment |
| Phase assessed | Phase 2 — Knowledge engineering (WP3 + WP4 advance) |
| Owner role | Technical Program Director |
| Dependencies | GATE-002, RESEARCH-004 v1.2, RESEARCH-005 v1.3, DEC-006, ADR-0003, ADR-0015 |
| Gate result | **`PARTIAL` — increment PASSES its acceptance criteria; Phase 2 still IN PROGRESS** |
| Last updated | 2026-08-28 |

---

## 1. Scope

Two increments since GATE-002: (a) the **G-07 formal negative-indicator & suppression library** (WP3);
(b) encoding the **11 eligible starter rules** (WP4 advance). This is the checkpoint the handoff
instructed the programme to stop at. Phase 2 is not complete (§6).

## 2. G-07 — CLOSED (all eight criteria)

See [RESEARCH-005 §6a](../01-research/RESEARCH-005-gap-register.md) for the evidence table. Summary:
a reusable library of **29 negative indicators + 6 hard-risk overrides** with graded, explainable
effects (`SUPPRESS_RULE` / `SUPPRESS_INDICATOR` / `CAP_SEVERITY` / `CONTEXT_ONLY`; numeric reduction
deferred to DET-001), a dedicated `validate_negative_library.py`, runner execution, and 53→ tests
including adversarial decoys. Negatives remain `HEURISTIC`; extraction is Phase 9. **The register
moves G-07 OPEN → CLOSED honestly, not because a JSON file exists.**

Key over-suppression fixes proven by test:
- `IT_SUPPORT_CONTEXT` no longer cancels a banking screen-share (HR_BANKING_REMOTE_ACCESS blocks it) — S-H, S-L.
- Safety-wording decoys ("we never ask your OTP" + a live OTP request) no longer suppress — S-I, S-J.
- Educational/reported scam content is represented as negation/reporting (no live positive) — B-013, S-D, S-E.

## 3. Rule backlog — reconciles to 30

| Category | Count | Change since GATE-002 |
|---|---|---|
| Encoded | **25** | +11 (was 14) |
| Not encoded — UNSUPPORTED | 4 | unchanged (TL-PAY-004, TL-JOB-002, TL-SOC-001, TL-IMP-001) |
| Not encoded — DEFERRED / unobservable | 1 | unchanged (TL-CTX-001) |
| **Total starter rules** | **30** | 25 + 4 + 1 = 30 ✅ |

Plus `TL-SUP-001` (non-starter suppression rule). **18 rules PUBLISHED** (was 7): the 11 newly
encoded are all evidenced (9 SUPPORTED on PRIMARY_VERIFIED sources, 2 PARTIAL capped) and
fully implementable. The 4 held at PEER_REVIEW (TL-TEL-001, TL-MAL-001, TL-MAL-003, TL-INV-003) and
the impl-PARTIAL APPROVED rules (TL-JOB-003, TL-MAL-002) are deliberately not published.

## 4. Acceptance criteria (this increment)

| Criterion | Status | Evidence |
|---|---|---|
| Suppression is reusable, not copy-pasted | ✅ | `EDUCATIONAL_CONTENT` removed from 14 rules; auto-applied from the library |
| Suppression is graded and explainable | ✅ | 4 effects + overrides; `rule_runner --explain` |
| Over-suppression prevented for hard-risk patterns | ✅ | 6 overrides; S-H/S-I/S-J/S-L |
| New rules preserve source traceability | ✅ | every rule cites manifest sources at the correct grade; linter L6/L11 |
| New rules use the formal library | ✅ | family suppressors referenced; globals auto-applied |
| Each new rule has positive + benign tests | ✅ | corpus M-004…M-016 fire; B-002/005/006/007/008/009 near-misses hold |
| No rule published merely for being encoded | ✅ | 4 PEER_REVIEW + 2 APPROSVED held back; publication gated by verdict/impl/tests |
| CONF-002 combination discipline holds | ✅ | linter found 6 single-class paths during authoring; all fixed |

## 5. Validator / test results (all green)

```
manual_evidence_check.py       PASS
phase1_consistency_check.py    35/35
validate_negative_library.py   PASS  (29 indicators, 6 overrides)
validate_rules.py              51/51 (26 rules, 18 PUBLISHED, 25 fixtures rejected)
rule_runner.py                 55/55 cases; 24 rules exercised; 6 overrides exercised; 0 await encoding
```

## 6. Phase 2 work still open

| Work package | Status |
|---|---|
| WP2 indicator families with extraction contracts | interim registry (positives) only |
| WP3 negative-indicator library (G-07) | ✅ **closed** |
| WP4 rule encoding | **25/30 encoded, 18 published**; 5 intentionally unencoded (4 unsupported, 1 deferred) |
| WP5 taxonomy completion (sextortion TAX-11, loan/mule) | not started |
| WP6 KB-001 knowledge-governance document | not started |
| WP8 ADR-0004 (knowledge storage), ADR-0014 (language) | ADR-0014 blocked on OI-04 |

## 7. Decision

**Stop here, as instructed.** G-07 is closed against all eight criteria; 11 eligible rules are
encoded and 18 rules published, all evidence-traceable and explainable, with the suppression layer
now reusable and override-protected. **Phase 2 remains IN PROGRESS** (WP2/WP5/WP6/WP8 open). The
recommended next increment is WP5 (taxonomy completion) and WP6 (KB-001), then WP2 extraction
contracts. Phase 3 must not begin until explicitly approved.

## 8. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-28 | G-07 closed; 11 eligible rules encoded (18 published); suppression library reusable + override-protected. Increment PASSES; Phase 2 remains PARTIAL/in-progress. | Technical Program Director |
