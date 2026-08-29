# GATE-004 — Phase 2 checkpoint: taxonomy completion (WP5) + KB-001 (WP6)

| Field | Value |
|---|---|
| Document ID | GATE-004 |
| Version | 1.0 |
| Status | **Checkpoint** — assesses WP5 (taxonomy completion) and WP6 (KB-001) |
| Phase assessed | Phase 2 — Knowledge engineering (WP5 + WP6) |
| Owner role | Technical Program Director |
| Dependencies | GATE-003, RESEARCH-002 v2.0, RESEARCH-005 v1.3, KB-001, DEC-006, DEC-007, ADR-0015 |
| Gate result | **`PARTIAL` — increment PASSES; Phase 2 still IN PROGRESS (WP2 + CI + ADR-0004/0014 remain)** |
| Phase 1 status | **`PARTIAL`** — unchanged (language scope + full source retrievability still fail; see [GATE-001 §7](GATE-001-phase-1-assessment.md)) |
| Last updated | 2026-08-28 |

---

## 1. Scope
WP5 taxonomy completion and WP6 KB-001 knowledge governance. This is the checkpoint to stop at before
WP2 extraction contracts.

## 2. WP5 — taxonomy completion
- **Multidimensional model:** six new dimension registries (`dimensions-v1.json`, 50 terms across
  channel/fraud_objective/technical_mechanism/social_engineering_tactic/requested_user_action/potential_harm);
  every scam subcategory tagged. Dimensions kept **separate**, not collapsed into one enum.
- **`evidence_maturity`** added per subcategory (current, post-RESEARCH-006) alongside `evidence`
  (automated historical, preserved). Resolved the reconciliation inconsistency where six subcategories
  carried published rules while graded 🔴.
- **TAX-11 sextortion — ADDED, detection DEFERRED** ([DEC-007](decision-log.md)).
- **Loan-app / mule (G-12)** preserved at `NO_PRIMARY_SOURCE`; no fabricated rule.
- Rich per-term metadata (definition, scope_notes, examples, status, version, change_history).
- Taxonomy → **v2.0**; RESEARCH-002 → v2.0.

## 3. WP6 — KB-001
Knowledge governance covering: the SOURCE→…→PUBLISH→MONITOR→REVISE pipeline; seven artifact lifecycles;
the rule state machine (reconciled with ADR-0003 statuses — not renamed); the PUBLISHED checklist with an
explicit **machine-enforced vs human-review** split; a change-response playbook (source disappears,
advisory superseded, FP/FN reported, over-suppression, emergency disablement); the **provenance model**
(preserving the ADR-0015 hierarchy); a **versioning policy** (PATCH/MINOR/MAJOR); and a **storage
boundary** that defers physical persistence to the unresolved ADR-0004.

## 4. Effect on the 25 encoded rules
**None to logic or publication status.** Every rule's `taxonomy_refs` still resolves; `validate_taxonomy.py`
confirms no published rule sits on a non-publishable-maturity subcategory and none references the
detection-deferred TAX-11. The six reconciliation subcategories now carry a maturity consistent with the
rules that sit on them. **Publication status unchanged: 18 PUBLISHED.**

## 5. Machine-enforced vs human-review controls
- **Machine (7 validators):** schema; ID/version syntax + global uniqueness (`validate_kb.py`); taxonomy
  + dimension integrity and rule reconciliation (`validate_taxonomy.py`); negative-library integrity;
  evidence/traceability/caps; combination discipline; test coverage; manifest durable-truth guard.
- **Human (KB-001 §9):** concept soundness; review diligence; official-channel identity; safeguarding
  (TAX-11); weakening a hard-risk override; emergency disablement authorisation.

## 6. Validator / test results (all green)
```
manual_evidence_check.py       PASS
phase1_consistency_check.py    35/35
validate_taxonomy.py           PASS  (11 categories, 42 subcategories, 50 dimension terms)
validate_kb.py                 PASS  (IDs unique across namespaces; versions valid; PUBLISHED review OK)
validate_negative_library.py   PASS  (29 indicators, 6 overrides)
validate_rules.py              51/51 (26 rules, 18 PUBLISHED, 25 fixtures rejected)
rule_runner.py                 55/55 cases; 24 rules exercised; 6 overrides; 0 await encoding
```

## 7. Remaining Phase 2 work

**Phase 1 remains `PARTIAL`** (unchanged by this increment) and **Phase 2 remains IN PROGRESS**.

| WP | Status |
|---|---|
| WP2 indicator families + extraction contracts | **next** — not started |
| WP5 taxonomy | ✅ done |
| WP6 KB-001 | ✅ done |
| WP7 schema validation in CI | 🟡 seven validators exist; CI workflow wiring remains |
| WP8 ADR-0004 (storage), ADR-0014 (language) | open; ADR-0014 blocked on OI-04 |

## 8. Decision
**Stop here, as instructed.** WP5 and WP6 pass their acceptance criteria; the taxonomy is complete and
multidimensional, KB-001 governs the knowledge lifecycle, and the 18 published rules are unaffected.
**WP2 extraction contracts are now ready to start** (taxonomy dimensions + KB lifecycle give the
extraction contract its target vocabulary and governance). Phase 2 remains IN PROGRESS. Phase 3 must not
begin until explicitly approved.

## 9. Change history
| Version | Date | Change | Author role |
|---|---|---|---|
| 1.0 | 2026-08-28 | WP5 (taxonomy v2.0, TAX-11 deferred, multidimensional model, evidence maturity) and WP6 (KB-001) assessed. Increment PASSES; Phase 2 remains PARTIAL/in-progress. WP2 ready to start. | Technical Program Director |
