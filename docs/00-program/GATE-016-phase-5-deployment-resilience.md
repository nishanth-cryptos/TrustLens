# GATE-016 — Phase 5 deployment, resilience and recovery checkpoint

| Field | Value |
|---|---|
| Document ID | GATE-016 |
| Version | 1.0 |
| Status | **DECISION CANDIDATE** — independent review APPROVED; pending remote CI and merge; not Phase-5 closure |
| Phase assessed | Phase 5 — P5-WP5 deployment, resilience, recovery and runtime operations |
| Owner role | Chief Architect / Principal Security Engineer |
| Baseline | P5-WP4 merge `e83acea27293ca5037b17c20c699b0cfd099d5e5` |
| Primary deliverables | [ADR-0016](../../adr/ADR-0016-deployment-resilience-runtime-topology.md) (Accepted following independent review); [ARCH-005](../05-architecture/ARCH-005-deployment-resilience-recovery.md) (Decision Candidate) |
| Governing authority | ARCH-001 `INV-01`…`INV-15`, ARCH-002/003/004, ADR-0004/0007/0008/0009/0010, DET-001 and AI-001 |
| Closes | P5-WP4 LOW-WP4-2 (signer pending/signed), LOW-WP4-4 (restore authorisation + restored-evidence integrity) |
| Related risks | RSK-008, RSK-010, RSK-011, RSK-012, RSK-017, RSK-018 |
| Last updated | 2026-09-06 |

## 1. Checkpoint purpose

GATE-016 records the P5-WP5 deployment/resilience candidate: a replicated Python modular-monolith backend with
in-process Phase-3 reasoning, externalised durable state, an optional isolated least-privilege worker profile, a
protected security/key/signing control boundary, deny-by-default network zones and controlled egress, distinct
startup/liveness/readiness semantics, coordinated cross-store backup, and authorised, integrity-verified restore.
It closes the two P5-WP5-owned WP4 LOW findings. It does **not** close Phase 5, accept ADR-0016, authorise
implementation, choose a platform/product, or perform the independent review.

## 2. Decision criteria

| # | Criterion | Candidate evidence | State |
|---:|---|---|---|
| 1 | ADR-0016 is Accepted following independent review | ADR-0016 metadata; ADR index Accepted section | APPROVED — INDEPENDENT REVIEW |
| 2 | ARCH-005 exists as the detailed runtime/deployment view | ARCH-005 metadata | AUTHORED |
| 3 | Replicated modular-monolith decision; four deployment options compared | ADR-0016 §Decision, §Alternatives | AUTHORED |
| 4 | In-process Phase-3 reasoning preserved; no remote reasoning / microservice split | ADR-0016 §Decision(1,2); ARCH-005 §3 | AUTHORED |
| 5 | Durable state externalised; state-light replicas; no sticky-session requirement | ADR-0016 §State model; ARCH-005 §4 | AUTHORED |
| 6 | Optional worker profile bounded; not automatically a microservice; ADR-0008 not weakened | ADR-0016 §Worker model; ARCH-005 §6 | AUTHORED |
| 7 | Workload identities defined (short-lived preferred; no product) | ADR-0016 §Security control placement; ARCH-005 §6 | AUTHORED |
| 8 | Secret/key placement defined; no plaintext/default-key fallback; no vendor | ARCH-005 §7.1 | AUTHORED |
| 9 | Network zones defined; deny-by-default; ingress cannot reach DB/evidence/key/signer | ADR-0016 §Network zones; ARCH-005 §5 | AUTHORED |
| 10 | Startup/liveness/readiness defined; optional AI does not gate deterministic readiness | ARCH-005 §8.1, §8.2 | AUTHORED |
| 11 | Signer pending/signed lifecycle closes LOW-WP4-2 (no unsigned-as-signed) | ADR-0016 §Decision(8); ARCH-005 §7.2 | AUTHORED |
| 12 | Restore authorisation closes LOW-WP4-4 (privileged, audited; not an app user) | ADR-0016 §Decision(13); ARCH-005 §11.1 | AUTHORED |
| 13 | Restored-evidence integrity re-verification closes LOW-WP4-4; promotion blocked until verified | ARCH-005 §11.2, §11.3 | AUTHORED |
| 14 | Coordinated backup + cross-store consistency (manifest/cut/watermark) + encryption | ARCH-005 §10 | AUTHORED |
| 15 | Fail-closed on required-dependency loss; no infra failure becomes a safe result | ADR-0016 §Decision(11); ARCH-005 §9 | AUTHORED |
| 16 | Bounded work / timeout / retry / backoff / circuit / graceful shutdown as principles | ARCH-005 §8.3, §8.4 | AUTHORED |
| 17 | Failure/degradation and health/readiness matrices present | ARCH-005 §8.1, §9 | AUTHORED |
| 18 | No RPO/RTO invented; DR is principle only | ARCH-005 §10.4 | AUTHORED |
| 19 | No cloud/orchestrator/platform/queue/secret/KMS/DB-HA vendor selected | ADR-0016 §Decision; ARCH-005 §1 | AUTHORED |
| 20 | LOW-WP4-3 (DNS-rebinding/SSRF TOCTOU) left to Phase 6 / ADR-0012 | ARCH-005 §12 | AUTHORED |
| 21 | Phase-3/Phase-4 authority, semantics and `ENGINE_VERSION` frozen | Builder freeze verification | PASS — LOCAL BUILDER |
| 22 | No deployment/container/orchestrator/queue/worker/health/secret/backup implementation added | Builder change-surface verification | PASS — LOCAL BUILDER |
| 23 | Canonical gate and CI self-test remain green | Required local validation below | PASS — LOCAL BUILDER |
| 24 | No production-readiness / availability-SLO / DR-certification / compliance claim; G-09 OPEN | ADR-0016; ARCH-005 §1, §16; this gate §4 | AUTHORED |

`AUTHORED` means the builder supplied reviewable design evidence. It is not independent approval or acceptance.

## 3. Selected candidate and acknowledged limits

The candidate deploys one Python modular-monolith release as one or more identical, state-light replicas with the
Phase-3 kernel in-process and durable authoritative state externalised (ADR-0010). An optional least-privilege
worker profile isolates heavy/untrusted work without becoming a microservice. Secrets/keys sit in a protected
control boundary (`SecretProvider`, `DataKeyProvider`, `AuditCheckpointSigner`); the signer has an explicit
`CHECKPOINT_PENDING` → `CHECKPOINT_SIGNED` / `RETRYABLE_FAILURE` lifecycle (closing LOW-WP4-2). Network zones are
deny-by-default with private stores and controlled egress. Required-dependency loss fails closed; optional AI loss
degrades to the deterministic baseline. Backup is coordinated cross-store with a consistency manifest/cut/watermark;
restore is privileged, audited, isolated, and integrity re-verified before promotion (closing LOW-WP4-4).

Acknowledged limits: identical replicas share a release and failure domain; whole-backend releases apply.
Full-system HA additionally depends on stateful-store, key-control, IdP, and backup/recovery availability
mechanisms decided later. Replica count, RPO/RTO, timeouts, thresholds, and all platform/product choices are
deferred. LOW-WP4-3 (DNS-rebinding/SSRF TOCTOU) stays Phase 6 / ADR-0012. Retention/legal basis remain OI-05.

### 3.1 Independent review outcome (acceptance-time)

Independent P5-WP5 review returned **APPROVE** — BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 2. ADR-0016 is
**Accepted following independent review**; ARCH-005 and GATE-016 remain Decision Candidates pending remote CI and
merge. The two LOW findings are recorded non-blocking follow-ups and are **not** fixed under this acceptance step
(no architecture redesign, no deployment code):

| Finding | Summary | Disposition |
|---|---|---|
| LOW-1 | Signer state machine lacks a terminal non-retryable failure state (e.g. exhausted retries, permanently unavailable/revoked signing key) | **Carry to P5-WP6** — WP6 defines terminal signer failure / permanently-unsignable checkpoint, max pending age, alerting/escalation, and operator runbook; not implemented now |
| LOW-2 | Deployment diagram (ARCH-005 §3) draws edges from replica R1 only, though replicas are declared identical | **Presentational only** — the identical-replica semantics are unchanged; not reopened |

The 2 INFO items are non-blocking observations carried with the LOW follow-ups. Prior WP4 handoffs are preserved:
**LOW-WP4-2 remains architecturally CLOSED** (pending vs. signed checkpoint distinction), **LOW-WP4-4 remains
architecturally CLOSED** (restore authorisation + restored-data integrity verification), and **LOW-WP4-3 remains
deferred to Phase 6 / ADR-0012** (DNS-rebinding / resolve-time SSRF TOCTOU — not claimed closed). This is
acceptance-time governance bookkeeping only; deployment/resilience semantics are unchanged.

## 4. Programme and claim status

| Item | Status |
|---|---|
| Phase 1 | PARTIAL |
| Phase 2 | PASS |
| Phase 3 | CLOSED at `phase3-wp8-v1.0`; `ENGINE_VERSION = 1.0.0` |
| Phase 4 | FORMALLY CLOSED at merged GATE-011; bounded optional offline reference/scaffold |
| Phase 5 | P5-WP5 DECISION CANDIDATE; not complete |
| Phase 6 | NOT STARTED |
| Phase 7 / UI | NOT STARTED |
| G-09 | OPEN |

No production-readiness, measured/five-nines availability, zero-downtime, disaster-recovery certification, achieved
RPO/RTO, security certification, evidentiary admissibility, tamper-proof audit, or real-world detection-effectiveness
claim is made. Architecture capability is not operational proof.

## 5. Required local builder validation

| Check | Required result | Candidate state |
|---|---|---|
| `knowledge/validation/run_all.py` | PASS — 23/23 | PASS — LOCAL BUILDER |
| `knowledge/validation/run_all.py --json` | `gate=PASS`, `validators_run=23`, `validators_failed=0` | PASS — LOCAL BUILDER |
| `knowledge/validation/ci_selftest.py` | PASS — 7/7 defects caught | PASS — LOCAL BUILDER |
| Phase-3/Phase-4 freeze and `ENGINE_VERSION` | zero diff; `1.0.0` | PASS — LOCAL BUILDER |
| Markdown whitespace and `git diff --check` | clean | PASS — LOCAL BUILDER |

Local builder results are recorded here after execution. They do not replace independent review or remote CI.

## 6. Finalisation conditions

GATE-016 may be finalised only after:

1. a separate independent review returns **APPROVE**;
2. ADR-0016 is independently approved before any Accepted status;
3. canonical local validation and CI self-test pass;
4. remote CI passes where triggered; and
5. the approved changes merge to `main`.

Phase-5 closure remains later integrated gate work (P5-WP7). P5-WP6 must not start under this builder checkpoint.

## 7. Change boundary

The candidate change surface is limited to new ADR-0016, ARCH-005, GATE-016, and the ADR index update. ADR-0004/
0007/0008/0009/0010, ARCH-001/002/003/004, GATE-012/013/014/015, the risk register, runtime/AI code, promoted
schemas/rules/taxonomies, detection/AI design documents, canonical validators, workflow, deployment implementation,
and UI remain unchanged.

## 8. Candidate recommendation

Independent review APPROVED the P5-WP5 deployment/resilience candidate and ADR-0016; acceptance bookkeeping is
complete (ADR-0016 Accepted; ADR index updated; two LOW findings recorded — LOW-1 carried to P5-WP6, LOW-2
presentational only). The two WP5-owned WP4 LOW findings remain closed and LOW-WP4-3 remains deferred to Phase 6.
Continue with required remote CI and merge finalisation. Do not commit yet, and do not begin P5-WP6 in this step.
