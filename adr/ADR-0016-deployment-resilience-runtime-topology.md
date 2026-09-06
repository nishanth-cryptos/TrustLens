# ADR-0016 — Deployment, resilience and runtime topology

| Field | Value |
|---|---|
| Status | **Accepted** — following independent P5-WP5 review (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2 / INFO 2; APPROVE) |
| Date | 2026-09-06 |
| Owner role | Chief Architect / Principal Security Engineer |
| Phase | Phase 5 — P5-WP5 deployment, resilience, recovery and runtime operations |
| Related | `MP §16, §20, §21`, [PROGRAM-001](../docs/00-program/PROGRAM-001-program-charter.md) (NFR-006/007/010/016, FR-071/076), [ARCH-001](../docs/05-architecture/ARCH-001-enterprise-architecture.md) (`INV-01`…`INV-15`), [ARCH-002](../docs/05-architecture/ARCH-002-python-runtime-service-topology.md), [ARCH-003](../docs/05-architecture/ARCH-003-persistence-evidence-tamper-architecture.md), [ARCH-004](../docs/05-architecture/ARCH-004-security-trust-threat-model.md), [ARCH-005](../docs/05-architecture/ARCH-005-deployment-resilience-recovery.md), [ADR-0004](ADR-0004-knowledge-storage-architecture.md), [ADR-0007](ADR-0007-ai-authority-and-model-strategy.md), [ADR-0008](ADR-0008-python-runtime-service-topology.md), [ADR-0009](ADR-0009-identity-authentication-authorization.md), [ADR-0010](ADR-0010-evidence-storage-tamper-evidence.md), [risk-register](../docs/00-program/risk-register.md) RSK-008/010/011/012/017/018, G-09 (RSK-003) |

## Context and constraints

ADR-0008 selected a Python **modular monolith** with the proven Phase-3/Phase-4 reasoning kernel in-process, and
reserved the physical deployment, replica/worker model, scaling, and resilience mechanics for P5-WP5. ADR-0010
externalised durable evidence/operational state behind PostgreSQL and a private `EvidenceContentStore`. ADR-0009
and ARCH-004 defined identity, workload identities, secrets, encryption-key purposes, the `AuditCheckpointSigner`
trust boundary, controlled deny-by-default egress, and the trust zones. This ADR fixes **how TrustLens is
deployed and how it behaves under failure** — as architecture, before any container, orchestrator, cloud
resource, queue, health endpoint, secret integration, or deployment script exists.

Two P5-WP4 independent-review LOW findings are explicitly owned here and must be closed architecturally:

- **LOW-WP4-2** — the audit signer must distinguish an **unsigned/pending** checkpoint from a **successfully
  signed** checkpoint; a failed signing must never appear signed.
- **LOW-WP4-4** — backup/restore must require **restore authorisation** and **restored-evidence integrity
  re-verification** before restored state is trusted.

A third finding, **LOW-WP4-3** (DNS-rebinding / resolve-time SSRF TOCTOU), is **not** closed here; it remains
Phase 6 / ADR-0012. This WP only preserves the controlled-egress and network-zone boundary.

`ENGINE_VERSION = 1.0.0` and Phase-3 sole-decision authority (CON-003, `INV-01`/`INV-02`) are unchanged. **G-09
remains OPEN**; deployment capability is not operational proof and no availability/efficacy is claimed.

## Decision

**TrustLens deploys as one Python modular-monolith backend release running as one or more identical,
state-light/stateless replicas with the Phase-3 reasoning kernel in-process, all durable authoritative state
externalised to the accepted stores, an optional isolated least-privilege worker execution profile for
heavy/untrusted work, a protected security/key/signing control boundary, and deny-by-default controlled external
egress. No microservice split, remote reasoning service, cloud platform, orchestrator, queue, secret/KMS/HSM, or
DB-HA product is selected.**

1. **One deployable, many identical replicas.** The backend is one versioned release (ADR-0008) that may run as a
   single instance (low-demand/dev) or multiple identical replicas behind a generic ingress/load-balancing
   boundary. Replicas are **not** separate microservices.
2. **In-process Phase-3.** Reasoning stays in-process in each replica; there is **no** HTTP/RPC/network call to
   Phase 3, **no** remote reasoning service, and **no** duplicate/fallback classifier. Semantic authority is
   unchanged.
3. **Externalised durable state; state-light replicas.** No replica depends on process-local durable case/user
   state. Process memory holds only the immutable loaded knowledge bundle, bounded caches, in-flight
   request/work state, safe configuration, and ephemeral computation — never the sole authority for case
   ownership, evidence, `DetectionResult`, audit history, role-authorisation state, or retention state.
4. **No sticky-session requirement.** Requests may reach any replica; authentication/authorisation follows
   ADR-0009 and is re-evaluated server-side. Any future ephemeral session/cache state is never decision authority.
5. **Knowledge-load gating.** A replica verifies a compatible immutable knowledge bundle (digest + schema/runtime
   compatibility) before it is **ready** to serve governed evaluations; missing/invalid/incompatible knowledge
   fails closed (never guessed/latest content). Each evaluation pins the exact bundle/version/digest (ADR-0004).
6. **Optional isolated worker profile.** Heavy/untrusted work (OCR, document/image extraction, large report
   generation, controlled enrichment) may run as an **execution/isolation profile** from the same release family,
   with a distinct least-privilege workload identity and resource limits. This is **not** automatically a
   separately owned service; independent service extraction still requires ADR-0008's evidence criteria + a new
   ADR.
7. **Protected security-control placement.** Data-encryption and audit-signing key operations live in the
   protected security/control boundary behind conceptual `DataKeyProvider` and `AuditCheckpointSigner` ports; the
   backend cannot possess or export raw master/signing private-key material (ARCH-004 §7). Secrets arrive from a
   protected `SecretProvider`/deployment-secret boundary, never baked into artifacts/images/Git/DB rows/logs.
8. **Signer pending/signed lifecycle (closes LOW-WP4-2).** A checkpoint is `CHECKPOINT_PENDING` until a signing
   attempt succeeds → `CHECKPOINT_SIGNED` (recording key id/version + signature provenance), or fails → remains
   pending / `RETRYABLE_FAILURE` visible as operational/security state. An unsigned checkpoint is **never**
   labelled signed; there is **no** fake signature and **no** unsigned-as-signed fallback. Append-only application
   audit may continue while signing is temporarily unavailable, subject to future operational policy (WP6 owns
   alert thresholds / max pending age / runbook).
9. **Deny-by-default network zones.** Public ingress cannot directly reach PostgreSQL, `EvidenceContentStore`,
   secret/key controls, the `AuditCheckpointSigner`, or internal worker control paths. Data stores are private to
   authorised workloads; external providers are reachable only through controlled egress (ARCH-004 §8, TLS 1.3).
10. **Distinct startup / liveness / readiness.** Startup validates config, knowledge bundle, and required
    crypto/config references; liveness reflects internal function and does not depend on every external provider;
    readiness reflects the ability to serve the relevant workload given required dependencies. **Optional AI
    provider outage does not make the deterministic baseline unready** (preserves Phase-4 fallback, FR-076).
11. **Fail-closed on required-dependency loss.** If a required dependency (PostgreSQL, `EvidenceContentStore`,
    key operation, identity validation) is unavailable, the operation fails safely as infrastructure/application
    failure. It never returns `NO_SCAM_PATTERN`, a safe classification, or claimed durable completion because
    infrastructure failed. Phase-3 computation semantics remain separate from persistence success.
12. **Bounded work and controlled lifecycle.** Bounded request size, concurrency, timeouts, admission control and
    backpressure; bounded, operation- and idempotency-aware retries with bounded backoff/jitter; a generic
    dependency-isolation/circuit pattern that never alters decision authority; and graceful shutdown (stop intake
    → drain bounded in-flight → reconcile → terminate) that relies on idempotency/reconciliation rather than
    fabricated completion. No numeric thresholds/schedules are invented (WP6/Phase 6).
13. **Coordinated backup + authorised, verified restore (closes LOW-WP4-4).** Backups coordinate PostgreSQL,
    `EvidenceContentStore`, audit/checkpoint state, replay/report artifacts, knowledge/version references, and
    key-version references via a conceptual consistency manifest/cut/watermark, encrypted to source sensitivity.
    Restore is a privileged, audited, least-privilege security operation requiring an authorised actor/workload;
    restored state is **quarantined and integrity re-verified** (relational consistency, evidence coverage,
    SHA-256 digests, manifest/derivative lineage, `DetectionResult`/replay/report pins, audit chain/checkpoints,
    knowledge digest, key-version references) **before promotion**. Verification failure keeps the restore
    failed/quarantined; restored data is never trusted merely because rows/files exist.
14. **RPO/RTO unspecified; no availability claim.** RPO and RTO are **NOT YET SPECIFIED** (P5-WP6 / sponsor). The
    application tier *supports* multiple healthy replicas, but no measured availability, zero-downtime, or DR
    certification is claimed; complete system HA additionally depends on stateful-store, key-control, IdP, and
    backup/recovery availability mechanisms decided later.

## Deployment unit

One versioned, immutable Python backend artifact (package format deferred; **not** Docker). Runtime code does not
mutate the deployed artifact. Non-secret configuration is separated from secret/key references and is
version-identifiable where it materially affects runtime behaviour; decision semantics continue to use governed
profile/config provenance (DET-001, ADR-0006).

## Replica model

A generic ingress/load-balancing boundary distributes independent requests across one to N identical replicas.
Exact replica count is **NOT YET SPECIFIED**; the architecture supports one replica for low-demand/dev and
multiple replicas where availability/throughput requires it. Temporary mixed versions during controlled rollout
are acknowledged: each completed evaluation already pins `ENGINE_VERSION`, bundle and profile/config provenance,
so completed results are **not** reinterpreted across versions, and rollout must avoid incompatible
request/artifact formats between replicas. The rollout platform is deferred.

## State model

Authoritative durable state (case ownership, evidence, `DetectionResult`, audit history, role-authorisation
state, retention state) lives only in the accepted external stores (ADR-0010). Process-local memory is limited to
the immutable knowledge bundle, bounded caches, in-flight state, safe config, and ephemeral computation. A crashed
replica loses none of these authorities; another healthy replica serves subsequent independent requests, and no
completed `DetectionResult` is reconstructed from process memory.

## Worker model

An optional worker execution profile runs heavy/untrusted tasks from the same release family under a distinct
least-privilege workload identity, resource limits, and the ARCH-004 malicious-upload isolation (no unrestricted
filesystem/network/database/secrets/host privileges). A conceptual bounded work-dispatch mechanism is permitted
**without** selecting a queue product. A worker profile is justified by resource isolation, malicious-content
isolation, long-running work, availability protection, or bounded concurrency — it is not, by itself, a separately
owned service.

## Security control placement

Identity validation follows ADR-0009; workload identities are non-human, least-privilege, and preferably
deployment-provided short-lived credentials (static long-lived shared credentials are **not** preferred, and if
unavoidable must be protected/rotated/least-privileged). Secret and key operations sit in the protected security
zone; the `AuditCheckpointSigner` custody is separated from ordinary backend DB-write and application credentials
and requires no raw-evidence browsing, rule publication, or identity administration. Secret/key mechanism
unavailability fails affected protected operations closed — **no** plaintext fallback, default hard-coded key, or
disabled-encryption fallback.

## Network zones

Public ingress · application · data · security/key control · worker/untrusted processing · controlled egress ·
external provider — deny by default, detailed in ARCH-005 §5. Public ingress reaches only the application tier;
data/security/signer/worker-control paths are private; external providers are reached only through controlled
egress. TLS 1.3 where boundaries apply (NFR-006); encryption never removes an authorisation requirement.

## Health/readiness

Startup (safe initialisation: config parse, knowledge validation, required crypto/config references), liveness
(internal function; not gated on every external provider), and readiness (can serve the relevant workload given
required dependencies) are distinct. Optional AI health never gates deterministic readiness.

## Failure semantics

Summarised in ARCH-005 §9 failure/degradation matrix. Required-dependency loss fails closed; optional AI loss
degrades to the deterministic baseline (ADR-0007, FR-076); signer loss yields pending/uncheckpointed state, never
signed success; no infrastructure failure becomes a safe classification or claimed durable completion.

## Scaling

Horizontal replica scaling for the application tier when state is externalised; heavy/long-running work may move to
the worker profile. PostgreSQL and `EvidenceContentStore` require an eventual resilience/failover mechanism
appropriate to the chosen environment — no clustering/replication/managed-service/synchronous-replication choice
is made without requirement/evidence. No benchmark numbers are invented.

## Backup/recovery

Coordinated cross-store backup with a consistency manifest/cut/watermark, sensitivity-equivalent encryption, and
non-universal backup credentials; authorised, isolated, integrity-verified restore before promotion; restore audit
of request/authorise/start/verify/promote-or-reject without logging restored raw evidence. DR principles only;
RPO/RTO NOT YET SPECIFIED.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A — Replicated Python modular monolith; in-process Phase-3; externalised durable state; optional worker profile (this ADR)** | Horizontal availability/throughput with no semantic split; preserves ADR-0008 and the proven kernel; simplest operations for a one-engineer team; isolates heavy/untrusted work only when justified; clear fail-closed and security boundaries | Shared release/failure domain per replica set; stateful stores and control plane still need their own resilience; whole-backend releases | ✅ **Selected** |
| B — Single instance / single host, no replica model | Simplest possible operation | No application-tier availability; single point of failure; no rolling change headroom; poor throughput scaling | ❌ Rejected (architecture must at least *support* replicas) |
| C — Microservice physical deployment from inception | Independent scaling/ownership in theory | Distributed transactions, more security surfaces, CI/release/observability burden unjustified by current evidence; contradicts ADR-0008; semantic-drift risk around the kernel | ❌ Rejected (see ARCH-002 §11 extraction criteria) |
| D — Separate remote reasoning service | Deployment isolation of the kernel | Wraps the sole decision authority in a network boundary (serialization, version, latency, retry, availability risk) with no measured need; contradicts ADR-0008; strict kernel-extraction safeguards unmet | ❌ Rejected |

Comparison spanned availability, failure isolation, operational/deployment complexity, semantic-drift risk,
network failure modes, scalability, cost/operational burden, small-team maintainability, security isolation,
recovery complexity, and reversal cost. C and D are evaluated for their deployment/resilience consequences, not
pretended away; ADR-0008 already rejected them as the current architecture.

## Justification

Identical state-light replicas give application-tier availability and throughput headroom while keeping the proven
Phase-3/Phase-4 semantics in-process and unchanged — the strongest guarantee is that no deployment shape
introduces a second decision path or a network boundary around the sole authority. Externalised durable state is
what makes replicas interchangeable and crash-tolerant; deny-by-default zoning, protected key/secret/signer
placement, and fail-closed required-dependency semantics keep the security and integrity boundaries intact under
failure. The signer pending/signed lifecycle and authorised, integrity-verified restore close the two WP5-owned
LOW findings without inventing operational thresholds that belong to WP6. Deferring platform/queue/secret/KMS/DB-HA
selection keeps the architecture neutral and small-team-maintainable. No efficacy or availability is claimed
(G-09 OPEN).

## Consequences

**Positive.**
- Application-tier availability/throughput via identical replicas with no semantic split (preserves ADR-0008).
- Crash-tolerant, interchangeable replicas because durable state is externalised.
- Heavy/untrusted work isolatable under a least-privilege worker profile without becoming a microservice.
- Fail-closed integrity: no infrastructure failure yields a safe result or fake completion.
- LOW-WP4-2 and LOW-WP4-4 closed architecturally (signer lifecycle; authorised, verified restore).

**Trade-offs.**
- Replicas share a release and failure domain; whole-backend releases rather than per-module deploys.
- Stateful stores, the control plane, the IdP, and backup/recovery each need their own availability mechanism
  before any full-system HA statement is possible.
- Numeric objectives (replica count, RPO/RTO, timeouts, thresholds) and platform/product choices are deferred.

## Risks

| Risk | Mitigation (this ADR / ARCH-005) |
|---|---|
| Process-local state treated as authority | State-light replicas; durable authority externalised (ADR-0010); §State model |
| Optional AI outage disabling deterministic core | Readiness excludes optional AI; exact deterministic fallback (ADR-0007, FR-076) |
| Required-dependency failure faked as safe/complete | Fail-closed semantics; never `NO_SCAM_PATTERN`/durable-completion on infra failure |
| Unsigned checkpoint mistaken for signed (LOW-WP4-2) | Explicit pending/signed lifecycle; no fake signature; signed records key/version/signature provenance |
| Untrusted restore promoted (LOW-WP4-4) | Restore authorisation + quarantine + integrity re-verification before promotion; audited |
| Malicious upload escaping isolation (RSK-017) | Least-privilege bounded worker profile; no unrestricted fs/net/db/secrets/host (ARCH-004) |
| Secret/key mechanism failure → plaintext fallback | Fail closed; no plaintext/default-key/disabled-encryption fallback |
| Public ingress reaching data/key/signer | Deny-by-default zones; stores private to authorised workloads |
| Overload/retry storm | Bounded concurrency/timeouts/admission control; bounded idempotent retries + backoff/jitter |
| Mixed-version rollout corrupting results | Completed results pin engine/bundle/profile; no cross-version reinterpretation; compatible formats |
| Cross-store backup inconsistency | Consistency manifest/cut/watermark; verify-before-promote restore |
| Efficacy/availability overclaim while G-09 open | No accuracy/availability/DR/production-readiness claim; capability ≠ operational proof |

## Reversal cost

**Medium.** Replica count, worker enablement, backup/restore mechanics, and platform/product choices are cheap to
revise because they sit behind stable ports and externalised state. What is expensive to reverse is the
**boundary**: in-process reasoning, externalised durable authority, fail-closed required-dependency semantics, the
signer pending/signed distinction, and authorised verified restore. Reversing those (e.g. a remote reasoning
service, process-local authority, or unsigned-as-signed checkpoints) would reintroduce semantic-drift, integrity,
and repudiation risks and require re-validating the whole detection and audit path. The boundary is deliberately
durable; its value is not lowered to make reversal cheap.

## Validation plan

Architecture only; concrete mechanics are later work.

- **ARCH-005** — deployment/network-zone/backup-restore diagrams; failure-degradation and health-readiness
  matrices; signer lifecycle and restore verification detail.
- **P5-WP6** — observability, alert thresholds, max pending-checkpoint age, RPO/RTO objectives, runbooks.
- **Phase 6** — ADR-0011 database migration tooling compatible with safe rollout/rollback; ADR-0012
  threat-intelligence/SSRF-controlled fetch (LOW-WP4-3); exact deployment/queue/secret/KMS/DB-HA products and
  health/backup/restore implementation.
- **Independent review** — this ADR was **Accepted following independent P5-WP5 review** (APPROVE; BLOCKER 0 /
  HIGH 0 / MEDIUM 0 / LOW 2 / INFO 2, the LOW/INFO items recorded as follow-ups in GATE-016 §3.1); no container,
  orchestrator, cloud resource, queue, health endpoint, secret integration, deployment script, or worker code is created by
  this WP.
