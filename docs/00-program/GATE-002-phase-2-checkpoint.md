# GATE-002 — Phase 2 Quality Gate (reconciliation increment checkpoint)

| Field | Value |
|---|---|
| Document ID | GATE-002 |
| Version | 1.0 |
| Status | **Checkpoint** — this gate assesses the RESEARCH-006 reconciliation + rule-encoding increment, not the whole of Phase 2 |
| Phase assessed | Phase 2 — Knowledge engineering (partial) |
| Owner role | Technical Program Director |
| Dependencies | GATE-001, RESEARCH-006, DEC-006, ADR-0003, ADR-0015 |
| Gate result | **`PARTIAL` — increment PASSES its acceptance criteria; Phase 2 as a whole is IN PROGRESS** |
| Last updated | 2026-08-28 |

---

## 1. Scope of this gate

This is the quality gate the Claude Code handoff instructed the programme to **stop at** after
executing the manual-retrieval reconciliation and the Phase-2 work it unblocked. It assesses one
increment of Phase 2 — the reconciliation and the rules it made publishable — against machine
checks. It does **not** claim Phase 2 is complete: several work packages remain open (§5).

## 2. What was delivered in this increment

| Work | Output |
|---|---|
| Manifest restoration + additive manual layer | `verification-manifest.json` v1.2 — automated `status` preserved, `manual_retrieval` overlay on 14 sources |
| Evidence-governance decision | **ADR-0015** (five-class hierarchy + seven official-alternate conditions) · **DEC-006** |
| Schema + linter extension | `sourceReference.manual_retrieval`; linter L10 (provenance integrity) + L11 (class caps); 2 new negative fixtures |
| Phase-1 reconciliation | RESEARCH-001 §6a, RESEARCH-004 v1.2 (+§9), RESEARCH-005 §2a, GATE-001 §7 — automated history preserved throughout |
| Indicator additions | 13 positive + 3 negative indicators (registry v0.2.0-interim) |
| Rule encoding | 5 new rules (TL-PAY-002, TL-AUTH-003, TL-CRYP-001, TL-JOB-003, TL-MAL-002) + 3 narrowed (TL-TEL-001, TL-MAL-001, TL-MAL-003) + 1 split/narrowed (TL-INV-003) |
| Seed cases | 6 new corpus cases (incl. an adversarial official-educational post) + 5 reconciliation cases |
| Rule-runner | `rule_runner.py` — deterministic evaluation, suppression, coverage, traceability |

## 3. Acceptance criteria for this increment

| Criterion | Status | Evidence |
|---|---|---|
| Original automated verification semantics preserved | ✅ | `manual_evidence_check.py` durable-truth guard: live statuses == frozen v1.1 |
| Manual evidence integrated additively, not overwriting | ✅ | `manual_retrieval` overlay; 26-source count and grade summary unchanged |
| Evidence hierarchy recorded before any upgrade | ✅ | ADR-0015 + DEC-006 precede rule publication |
| No rule overstates provenance | ✅ | Linter L6 unchanged; L10/L11 added; `official-alternate-claiming-supported` fixture rejected |
| Every published rule traces to evidence | ✅ | Rule-runner traceability: 7/7 PUBLISHED resolve to manifest + evidence records |
| Rules narrowed, not padded with unsupported clauses | ✅ | TL-TEL-001 (courier dropped), TL-MAL-001 (iOS profile dropped), TL-INV-003 (deepfake dropped) |
| Detection is combinational, not keyword | ✅ | `min_evidence_classes ≥ 2` on every satisfying path; 25/25 negative fixtures rejected |
| Negative indicators suppress official/benign language | ✅ | B-013 adversarial-benign suppressed; RB-002 IT-support distinguished |
| No malicious case expects an unsupported/deferred rule | ✅ | `phase1_consistency_check.py` |

## 4. Validator results (all green)

```
manual_evidence_check.py     PASS  (13 records, hashes OK, durable-truth guard OK)
phase1_consistency_check.py  35/35
validate_rules.py            40/40  (15 rules, 7 PUBLISHED, 25 fixtures rejected)
rule_runner.py               41/41  cases; 13 rules exercised; 7/7 traceable
```

## 5. Rule backlog — full reconciliation of the 30 starter rules

Corrected count. An earlier draft said "15/30 encoded" and "9 remaining"; both were wrong. The 15th
**rule file** is `TL-SUP-001`, a Phase-2 **suppression** rule authored in WP1 — it is **not** one of
the 30 starter rules. And "9" was only the subset of unencoded rules referenced by the current seed
corpus, not the whole backlog. The correct arithmetic:

| Category | Count | Rules |
|---|---|---|
| **Encoded** (a rule file exists, any status) | **14** | TL-CRED-001, TL-PAY-001, TL-PAY-002, TL-PAY-003, TL-KYC-001, TL-AUTH-001, TL-TEL-001, TL-AUTH-003, TL-INV-003, TL-JOB-003, TL-CRYP-001, TL-MAL-001, TL-MAL-002, TL-MAL-003 |
| **Not yet encoded — eligible** (SUPPORTED/PARTIAL, impl YES) | **11** | TL-CRED-002, TL-CRED-003, TL-AUTH-002, TL-UTIL-001, TL-ATO-001, TL-ATO-002, TL-INV-001, TL-INV-002, TL-JOB-001, TL-SOC-002, TL-SOC-003 |
| **Not yet encoded — UNSUPPORTED** (stay out of the published set) | **4** | TL-PAY-004, TL-JOB-002, TL-SOC-001, TL-IMP-001 |
| **Not yet encoded — DEFERRED / unobservable** (impl DEFERRED) | **1** | TL-CTX-001 |
| **Total starter rules** | **30** | — |

Reconciles exactly: **14 + 11 + 4 + 1 = 30.** Rule scope was **not** changed to fit — verdicts and
implementability are unchanged from RESEARCH-004 v1.2; only the count was corrected.

Notes:
- `TL-IMP-001` is both UNSUPPORTED **and** impl DEFERRED; it is counted once, under UNSUPPORTED.
- Of the 14 encoded: **7 PUBLISHED**, TL-JOB-003 + TL-MAL-002 APPROVED (impl PARTIAL), TL-TEL-001 +
  TL-MAL-001 + TL-MAL-003 + TL-INV-003 PEER_REVIEW (narrowed), TL-PAY-003 DRAFT (impl DEFERRED).
- **`TL-SUP-001`** is a 15th rule file but is **outside the 30** — it belongs to the WP3
  negative-indicator/suppression work package.
- The rule-runner's "9 corpus rules await encoding" is the subset of the 11+4+1=16 unencoded rules
  that the current seed corpus references (TL-ATO-001/002, TL-AUTH-002, TL-CRED-003, TL-INV-001/002,
  TL-JOB-001, TL-SOC-002/003) — not the whole backlog.

## 6. Phase 2 work still open (why this is not a full PASS)

| Work package | Status |
|---|---|
| WP2 indicator families with extraction contracts | interim registry only (v0.2.0-interim) |
| WP3 negative-indicator library (G-07) | **OPEN.** 23 interim suppressive indicators exist in the registry, are wired into 14 rules via `suppressed_by`, and are runner-validated — but the **formal authored library is not written** (registry note: "WP3 replaces the NEGATIVE half"). G-07 stays 🔴 open. |
| WP4 full rule encoding | **14 of 30** starter rules encoded (§5); 16 await encoding (11 eligible, 4 unsupported, 1 deferred) |
| WP5 taxonomy completion (sextortion TAX-11, loan/mule) | not started |
| WP6 KB-001 knowledge-governance document | not started |
| WP8 ADR-0004 (knowledge storage), ADR-0014 (language) | ADR-0014 blocked on OI-04 |

## 7. G-07 status (explicit)

G-07 is **OPEN**. To be precise about what exists versus what does not:

| Aspect | State |
|---|---|
| Interim negative indicators inside rules (`suppressed_by`) | ✅ present — 14 rules + the TL-SUP-001 suppression rule |
| Reusable negative indicators in the registry | ✅ 23 SUPPRESSIVE indicators (`indicator-registry-v0.json` v0.2.0-**interim**) |
| **Formal, authored negative-indicator library** | ❌ **not written** — this is the WP3 deliverable that closes G-07 |
| Schema support (SUPPRESSION kind, `suppressed_by`/`suppresses`/`effect`, polarity) | ✅ present |
| Validator support (linter L2 polarity; 2 polarity fixtures) | ✅ present |
| Runner / test coverage (suppression exercised; adversarial B-013; IT-support RB-002) | ✅ present |

**Formalising G-07 (the authored negative-indicator library) is the next major Phase-2 task and must
precede broad rule publication** — only 7 rules are PUBLISHED today precisely because the suppressive
layer is still interim.

## 8. Decision

**Stop here, as instructed.** The reconciliation increment passes every acceptance criterion under
machine check, and the evidence-first discipline held: no automated status was overwritten, every
upgraded rule carries retained/hashed/human-reviewed provenance, and every published rule is
traceable and explainable. **Phase 2 remains IN PROGRESS** (14/30 starter rules encoded; G-07 open).
The recommended next increment is: (1) formalise the G-07 negative-indicator library, then (2) encode
the 11 eligible starter rules. Phase 3 must not begin until explicitly approved.

## 9. Change history

| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-28 | Phase-2 reconciliation increment assessed. Increment PASSES; Phase 2 as a whole PARTIAL/in-progress. | Technical Program Director |
| 1.1 | 2026-08-28 | Pre-commit consistency review: corrected the rule backlog to a full 30-rule reconciliation (14 encoded / 11 eligible / 4 unsupported / 1 deferred; TL-SUP-001 is a non-starter suppression rule). Made G-07 status explicit and kept OPEN. Confirmed DEC-006 had no numbering conflict (language decision is ADR-0014/OI-04, never a DEC number). | Technical Program Director |
