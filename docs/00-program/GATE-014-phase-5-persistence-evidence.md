# GATE-014 — Phase 5 persistence, evidence and tamper-evidence checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-014 |
| Version | 1.0 |
| Status | **DECISION CANDIDATE** — independent review approved; pending remote CI and merge; not Phase-5 closure |
| Phase assessed | Phase 5 — P5-WP3 persistence, evidence storage and tamper evidence |
| Owner role | Chief Architect |
| Baseline | P5-WP2 merge `7238695e752038cf643851d03184b5e1d0cf49ec` |
| Primary deliverables | [ADR-0010](../../adr/ADR-0010-evidence-storage-tamper-evidence.md) (Accepted following independent review); [ARCH-003](../05-architecture/ARCH-003-persistence-evidence-tamper-architecture.md) (Decision Candidate) |
| Governing authority | ARCH-001, ARCH-002, ADR-0004/0007/0008/0015, DET-001 and AI-001 |
| Last updated | 2026-09-06 |

## 1. Checkpoint purpose

GATE-014 records the P5-WP3 architecture candidate for structured operational persistence, protected
user-evidence content, custody and tamper evidence, replay/report inputs, audit, and retention/deletion. It does
not close Phase 5, accept ADR-0010, authorize implementation, choose an infrastructure product, or perform the
independent review.

## 2. Decision criteria

| # | Criterion | Candidate evidence | State |
|---:|---|---|---|
| 1 | ADR-0010 is Accepted following independent review | ADR-0010 metadata; ADR index Accepted section | APPROVED — INDEPENDENT REVIEW |
| 2 | ARCH-003 remains a Decision Candidate pending remote CI and merge | ARCH-003 metadata | AUTHORED |
| 3 | Four credible persistence options are compared across integrity, transaction, binary/privacy, query, replay, operations, scale and reversal concerns | ADR-0010 §4 | AUTHORED |
| 4 | PostgreSQL is justified as structured operational store without becoming knowledge authority | ADR-0010 §§2–4; ARCH-003 §§3–5, 16 | AUTHORED |
| 5 | Raw/binary user evidence is separated behind a private encrypted vendor-neutral `EvidenceContentStore` | ADR-0010 §2; ARCH-003 §§4, 8 | AUTHORED |
| 6 | Official knowledge evidence and user-submitted case evidence are explicitly distinguished; user evidence is never Git content | ADR-0010 §1.1; ARCH-003 §3 | AUTHORED |
| 7 | Evidence identity, SHA-256 over exact ingest bytes and custody sequence are defined | ADR-0010 §5; ARCH-003 §7 | AUTHORED |
| 8 | Original/derivative separation and digest-pinned lineage are defined | ADR-0010 §5; ARCH-003 §§5, 7 | AUTHORED |
| 9 | Immutable, revisioned and mutable operational classes prevent silent historical overwrite | ADR-0010 §6; ARCH-003 §§5, 9 | AUTHORED |
| 10 | Completed `DetectionResult` is preserved exactly without redefining Phase-3 fields or authority | ADR-0010 §7; ARCH-003 §10 | AUTHORED |
| 11 | Phase-4 provenance/fallback and exact governed-artifact pins are persisted without model decision fields or numeric confidence | ADR-0010 §7; ARCH-003 §10 | AUTHORED |
| 12 | Replay and report inputs are digest/version pinned; integrity failures fail closed without AI recall or latest-knowledge fallback | ADR-0010 §§7–8; ARCH-003 §11 | AUTHORED |
| 13 | Append-only audit hashing is accurately bounded as tamper-evident and a signed/external checkpoint path is reserved | ADR-0010 §9; ARCH-003 §12 | AUTHORED |
| 14 | Retention/deletion supports configurable future policy, dependency deletion and proof while OI-05 remains open | ADR-0010 §10; ARCH-003 §13 | AUTHORED |
| 15 | Cross-store state, idempotency, digest verification and orphan reconciliation avoid an assumed distributed transaction | ADR-0010 §§5, 11; ARCH-003 §§7, 14 | AUTHORED |
| 16 | Backup/restore preserves joint references, digests, audit, replay/report and key references and verifies recovery | ADR-0010 §11; ARCH-003 §15 | AUTHORED |
| 17 | Security preserves TLS 1.3/AES-256, least privilege, private access and content-free logs/audit | ADR-0010 §12; ARCH-003 §§8, 16 | AUTHORED |
| 18 | No SQL, migration, ORM, storage code, infrastructure, queue, API or UI implementation is added | Builder change-surface verification | PASS — LOCAL BUILDER |
| 19 | Phase-3/Phase-4 implementation and semantics remain frozen and engine stays 1.0.0 | Builder freeze verification | PASS — LOCAL BUILDER |
| 20 | Canonical gate and CI self-test remain green | Required local validation below | PASS — LOCAL BUILDER |
| 21 | G-09 remains OPEN and no efficacy, admissibility, certified-custody or production-readiness claim is made | ADR-0010 §16; ARCH-003 §§1, 19; this gate §4 | AUTHORED |

`AUTHORED` means the builder supplied reviewable design evidence. It is not independent approval or acceptance.

## 3. Selected candidate and acknowledged limits

The candidate uses PostgreSQL for structured operational records, a vendor-neutral encrypted
`EvidenceContentStore` for protected bytes, SHA-256 manifests/artifact pins, and append-only hash-chained audit.
It preserves deterministic replay and report inputs while keeping official knowledge authority under ADR-0004.

This split requires idempotent cross-store states, reconciliation, coordinated backup/restore, and later
security/deployment decisions. A hash chain can reveal changes relative to a trusted root but cannot prevent a
privileged whole-history rewrite. Signed or independently anchored checkpoints remain a P5-WP4/P5-WP5 path.
Retention duration, legal basis, and permitted residual metadata remain OI-05.

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 1 | PARTIAL |
| Phase 2 | PASS |
| Phase 3 | CLOSED at `phase3-wp8-v1.0`; `ENGINE_VERSION = 1.0.0` |
| Phase 4 | FORMALLY CLOSED at merged GATE-011; bounded optional offline reference/scaffold |
| Phase 5 | P5-WP3 DECISION CANDIDATE; not complete |
| Phase 6 | NOT STARTED |
| Phase 7/UI | NOT STARTED |
| G-09 | OPEN |

No accuracy, precision, recall, false-positive/negative rate, real-world detection effectiveness, evidentiary
admissibility, legal chain-of-custody certification, tamper-proofing, or production-readiness claim is made.

## 5. Required local builder validation

| Check | Required result | Candidate state |
|---|---|---|
| `knowledge/validation/run_all.py` | PASS — 23/23 | PASS — LOCAL BUILDER |
| `knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=23`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `knowledge/validation/ci_selftest.py` | PASS — 7/7 defects caught | PASS — LOCAL BUILDER |
| Phase-3/Phase-4 freeze and `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| Markdown whitespace and `git diff --check` | clean | PASS — LOCAL BUILDER |

Local builder results may be recorded here after execution. They do not replace independent review or remote CI.

## 6. Finalisation conditions

GATE-014 may be finalized only after:

1. a separate independent review returns **APPROVE**;
2. ADR-0010 is independently approved for acceptance;
3. canonical local validation and CI self-test pass;
4. remote CI passes where triggered; and
5. the approved changes merge to `main`.

Phase-5 closure remains later integrated gate work. P5-WP4 must not start under this builder checkpoint.

## 7. Change boundary

The candidate change surface is limited to new ADR-0010, ARCH-003, GATE-014, and the ADR index update.
ADR-0004/0008, ARCH-001/002, GATE-012/013, runtime/AI code, promoted schemas/rules/taxonomies, detection/AI design
documents, canonical validators, workflow, storage implementation, and UI remain unchanged.

## 8. Candidate recommendation

Independent review approved ADR-0010 and acceptance bookkeeping is complete. Continue with required remote CI
and merge finalisation. Do not commit yet or begin P5-WP4 in this acceptance step.
