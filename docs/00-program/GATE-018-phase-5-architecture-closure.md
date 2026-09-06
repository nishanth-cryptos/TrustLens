# GATE-018 — Phase 5 integrated architecture closure checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-018 |
| Version | 1.0 |
| Status | **LOCAL / INDEPENDENT ARCHITECTURE CLOSURE APPROVED** — remote CI + merge pending; **Phase 5 not formally CLOSED** |
| Phase assessed | Phase 5 — P5-WP7 integrated enterprise architecture closure |
| Owner role | Chief Architect / Principal Security Engineer |
| Baseline | P5-WP6 merge `6145ce6448b9c64a089bbf89fece97abbca715d9` |
| Primary deliverables | [ADR-0013](../../adr/ADR-0013-rule-set-publication-version-distribution.md) (Accepted, following independent review); [ARCH-007](../05-architecture/ARCH-007-integrated-phase-5-architecture.md) (Architecture approved for closure) |
| Consolidates gates | GATE-012 (WP1), GATE-013 (WP2), GATE-014 (WP3), GATE-015 (WP4), GATE-016 (WP5), GATE-017 (WP6) |
| Governing authority | ARCH-001 `INV-01`…`INV-15`; ADR-0003…0010/0013/0014/0015/0016/0017; DET-001; AI-001 |
| Related risks | RSK-008, RSK-010, RSK-011, RSK-012, RSK-017, RSK-018; G-09 (RSK-003) |
| Last updated | 2026-09-06 |

## 1. Checkpoint purpose

GATE-018 records the P5-WP7 integrated architecture closure candidate: the final reserved decision (ADR-0013,
rule-set publication/version distribution) plus the consolidated Phase-5 authority map, integrated system view,
invariant reconciliation, cross-WP contract matrix, residual-findings register, and Phase-6 entry contract
(ARCH-007). It assesses whether the Phase-5 **architecture** is coherent and governed. Following the independent
P5-WP7 closure review, ADR-0013 is **Accepted** and the Phase-5 architecture is **approved for closure locally**;
this gate still does **not** formally close Phase 5, authorise implementation, choose a product, or claim
production readiness. Formal Phase-5 closure additionally requires remote CI PASS and merge to `main` (§6).

## 2. Decision criteria

| # | Criterion | Candidate evidence | State |
|---:|---|---|---|
| 1 | P5-WP1…WP6 merged and authoritative | ARCH-001…006, GATE-012…017 on `main` | PASS — MERGED |
| 2 | ADR-0013 issued and Accepted following independent review | ADR-0013 metadata; ADR index Accepted | APPROVED |
| 3 | ADR-0013 publication/distribution coherent with ADR-0004 | ADR-0013 §Context/§Decision; ARCH-007 §5 | AUTHORED |
| 4 | Exact bundle identity defined (`content_digest` load-bearing) | ADR-0013 §Decision(3); §9 | AUTHORED |
| 5 | `bundle_version` alone not exact identity | ADR-0013 §Context, §Decision(3) | AUTHORED |
| 6 | Immutable publication defined | ADR-0013 §Decision(4) | AUTHORED |
| 7 | No "latest"-rule runtime semantics | ADR-0013 §Decision(7) | AUTHORED |
| 8 | Explicit activation defined | ADR-0013 §Decision(10) | AUTHORED |
| 9 | Rollback defined (no bundle/history rewrite) | ADR-0013 §Decision(12) | AUTHORED |
| 10 | Withdrawal/revocation defined — future activation blocked; currently-active withdrawn bundle surfaced (`ACTIVE_BUNDLE_WITHDRAWN`); governed remediation/replacement/rollback required; no new evaluations continue indefinitely on the withdrawn bundle once effective; prior results/history unchanged; governed audit for lifecycle actions | ADR-0013 §Decision(12,14), "Withdrawal / revocation" (A/B/C); ARCH-007 §5.1 | AUTHORED |
| 11 | Historical bundle reproducibility preserved | ADR-0013 §Decision(4,12,13) | AUTHORED |
| 12 | External/untrusted distribution authenticity architecture defined | ADR-0013 §Decision(9) | AUTHORED |
| 13 | Release signing-key purpose separated from `AuditCheckpointSigner` | ADR-0013 §Decision(9); ARCH-004 §7 | AUTHORED |
| 14 | No distribution/signing vendor/product selected | ADR-0013 §Decision(5,9) | AUTHORED |
| 15 | Offline/on-prem preserved | ADR-0013 §Decision(6) | AUTHORED |
| 16 | Runtime still validates / fails closed | ADR-0013 §Decision(8,13) | AUTHORED |
| 17 | Integrated authority map complete | ARCH-007 §2 | AUTHORED |
| 18 | ARCH-001 invariants INV-01…INV-15 reconciled; no contradiction | ARCH-007 §4 | AUTHORED |
| 19 | Cross-WP contract matrix complete | ARCH-007 §5 | AUTHORED |
| 20 | Residual findings reconciled (no fabricated closure) | ARCH-007 §6 | AUTHORED |
| 21 | Phase-6 entry contract complete | ARCH-007 §9 | AUTHORED |
| 22 | ADR-0011/0012 remain Planned | ADR index Planned section | AUTHORED |
| 23 | G-09 remains OPEN; no production-readiness/efficacy claim | ARCH-007 §1, §11; this gate §4 | AUTHORED |
| 24 | Phase-3/Phase-4 frozen; `ENGINE_VERSION = 1.0.0`; publish/runtime code unchanged | Builder freeze verification | PASS — LOCAL BUILDER |
| 25 | Canonical gate and CI self-test remain green | Required local validation below | PASS — LOCAL BUILDER |
| 26 | Currently-active withdrawn bundle surfaced + governed remediation; not silently healthy; mixed-replica inconsistency observable | ADR-0013 "Withdrawal / revocation" (C); ARCH-007 §5.1 | AUTHORED |
| 27 | Publication-lifecycle actions produce governed audit events (publication/distribution/activation/rollback/withdrawal/rejected-activation/active-withdrawn); telemetry does not replace audit | ADR-0013 §Decision(14); ARCH-007 §5.1 | AUTHORED |

`AUTHORED` means the builder supplied reviewable design evidence. The independent P5-WP7 closure review has now
assessed that evidence and returned `APPROVE_PHASE5_CLOSURE_CANDIDATE` (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 /
INFO 1); the `AUTHORED` design-evidence criteria above are therefore independently **APPROVED** for architecture
closure. This remains a **local/independent** closure approval — it does not by itself constitute remote CI PASS
or merge.

### 2.1 Independent-review sequence and findings (P5-WP7)

**Initial full independent review** returned **REQUEST_CHANGES** (BLOCKER 0 / HIGH 0 / MEDIUM 1 / LOW 1 / INFO 3).
Both actionable findings were addressed by a narrow correction (no redesign; Phase 5 **not** claimed closed):

| Finding | Summary | Resolution |
|---|---|---|
| MEDIUM-1 | Withdrawal did not adequately define behaviour when the withdrawn bundle is already **active** | **CLOSED** — ADR-0013 "Withdrawal / revocation" case C + Decision 14; ARCH-007 §5.1 — `ACTIVE_BUNDLE_WITHDRAWN` state, `ACTIVE_KNOWLEDGE_BUNDLE_WITHDRAWN` alert, governed remediation runbook, mixed-replica inconsistency surfaced; never silently healthy; no new evaluations on it once effective; in-flight stays pinned; history unchanged; no auto-latest/ungoverned rollback |
| LOW-1 | ADR-0013 did not explicitly name governed-audit requirements for publication-lifecycle actions | **CLOSED** — ADR-0013 Decision 14 — governed audit for publication/distribution/activation/rollback/withdrawal/rejected-activation/active-withdrawn; telemetry never replaces audit |

**Targeted independent re-review** then returned **BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 1**, with final
recommendation **`APPROVE_PHASE5_CLOSURE_CANDIDATE`**. MEDIUM-1 and LOW-1 are confirmed **CLOSED**.

The single remaining **INFO-1** is an acceptance-time **wording alignment** only (the ARCH-007 §10 self-challenge
answer for a withdrawn bundle was broadened so it covers both historical-use provenance preservation and the
currently-active `ACTIVE_BUNDLE_WITHDRAWN` semantics). It changes **no** normative architecture. Following this
approval ADR-0013 is **Accepted** and the Phase-5 architecture is **approved for closure locally**; formal Phase-5
closure still requires remote CI PASS and merge to `main` (§6).

## 3. Selected candidate and acknowledged limits

The candidate issues ADR-0013 (governed Git/CI → deterministic digest-addressed immutable bundle → vendor-neutral
`PublishedBundleRepository` → pre-activation validation + external publisher-authenticity via a key-separated
`KnowledgeReleaseSigner` → explicit activation by exact identity, with rollback/withdrawal that never rewrite
history) and consolidates Phase-5 into ARCH-007 (authority map, integrated diagram, INV-01…INV-15 reconciliation
with no contradiction, cross-WP contract matrix, residual-findings register, Phase-6 entry contract and
non-negotiable constraints).

Acknowledged limits: the distribution transport, signing/PKI product and key custody, activation/rollback/
withdrawal and operational activation-record schema are Phase-6 implementation; the only still-open review finding
(WP4 LOW-3, DNS-rebinding/SSRF-TOCTOU) is deferred to Phase 6 / ADR-0012 with an owner. Numeric SLO/RPO/RTO,
alert thresholds, signer max pending age, restore-test frequency and telemetry retention remain NOT YET
SPECIFIED; OI-05 and G-09 remain OPEN. None of these blocks Phase-5 **architecture** closure.

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 1 | PARTIAL |
| Phase 2 | PASS |
| Phase 3 | CLOSED at `phase3-wp8-v1.0`; `ENGINE_VERSION = 1.0.0` |
| Phase 4 | FORMALLY CLOSED at merged GATE-011; bounded optional offline reference/scaffold |
| Phase 5 | **CLOSURE APPROVED / MERGE PENDING** — P5-WP1…WP7 authored; independent closure review APPROVED locally; **not formally CLOSED** (pending remote CI PASS + merge to `main`) |
| Phase 6 | NOT STARTED |
| Phase 7 / UI | NOT STARTED |
| G-09 | OPEN |

**Phase-5 architecture closure means the required architecture decisions are coherent and governed — it does NOT
mean production readiness.** No production-readiness, security/compliance certification, legal-admissibility,
measured/five-nines availability, zero-downtime, achieved RPO/RTO, or real-world detection-effectiveness (accuracy/
precision/recall/false-positive/negative) claim is made.

## 5. Required local builder validation

| Check | Required result | Candidate state |
|---|---|---|
| `knowledge/validation/run_all.py` | PASS — 23/23 | PASS — LOCAL BUILDER |
| `knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=23`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `knowledge/validation/ci_selftest.py` | PASS — 7/7 defects caught | PASS — LOCAL BUILDER |
| Phase-3/Phase-4/publish freeze and `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| Markdown whitespace and `git diff --check` | clean | PASS — LOCAL BUILDER |

Local builder results are recorded here after execution. They do not replace independent review or remote CI.

## 6. Finalisation conditions (Phase-5 closure)

Phase 5 is formally **CLOSED** only after **all** of:

1. a separate independent review returns **APPROVE** — **SATISFIED** (targeted re-review: `APPROVE_PHASE5_CLOSURE_CANDIDATE`);
2. ADR-0013 is independently approved before any Accepted status — **SATISFIED** (ADR-0013 now Accepted following that review);
3. canonical local validation and CI self-test pass — **SATISFIED locally** (§5);
4. remote CI passes where triggered — **PENDING**; and
5. the approved changes merge to `main` — **PENDING**.

Conditions 1–3 are satisfied locally, so the Phase-5 architecture is **approved for closure**; conditions 4–5
(remote CI PASS + merge) remain **PENDING**, so Phase 5 is **CLOSURE APPROVED / MERGE PENDING**, not yet formally
CLOSED. Upon satisfaction of 4–5, the merged GATE-018 constitutes **Phase-5 architecture closure** (not production
readiness). This gate does not modify GATE-012…017's historical checkpoint assertions.

## 7. Change boundary

The candidate change surface is limited to new ADR-0013, ARCH-007, GATE-018, and the ADR index update. ADR-0003…
0012 existing files, ADR-0014/0015/0016/0017, ARCH-001…006, GATE-012…017, the risk register, runtime/publish/AI
code, promoted schemas/rules/taxonomies, detection/AI design documents, canonical validators, workflow,
implementation, and UI remain unchanged.

## 8. Candidate recommendation

The P5-WP7 integrated architecture closure package is authored, internally consistent with ARCH-001…006 and
ADR-0003…0010/0014/0015/0016/0017, and has passed independent P5-WP7 closure review
(`APPROVE_PHASE5_CLOSURE_CANDIDATE`): ADR-0013 completes the reserved Phase-5 decision coherently with ADR-0004 and
is now **Accepted**; all ARCH-001 invariants are reconciled with no contradiction; and all Phase-5 findings are
reconciled (closed or deferred with an owner; WP7 MEDIUM-1/LOW-1 CLOSED). The Phase-5 architecture is therefore
**approved for closure locally**. Remaining steps to formal closure: remote GitHub Actions CI PASS and merge of the
closure PR into `main`. Do **not** claim Phase 5 formally CLOSED until merged, and do **not** begin Phase 6 in this
checkpoint.
