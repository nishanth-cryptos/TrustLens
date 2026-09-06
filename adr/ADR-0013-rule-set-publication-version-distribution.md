# ADR-0013 — Rule-set publication and version distribution mechanism

| Field | Value |
|---|---|
| Status | **Accepted** — following independent P5-WP7 closure review |
| Date | 2026-09-06 |
| Owner role | Chief Architect / Knowledge Approver / Principal Security Engineer |
| Phase | Phase 5 — P5-WP7 integrated architecture closure |
| Related | `MP §16, §20, §21`, [PROGRAM-001](../docs/00-program/PROGRAM-001-program-charter.md) (CON-003, NG-07, FR-075, NFR-006/010, RSK-012), [ARCH-001](../docs/05-architecture/ARCH-001-enterprise-architecture.md) (`INV-07`/`INV-08`/`INV-13`/`INV-14`), [ARCH-007](../docs/05-architecture/ARCH-007-integrated-phase-5-architecture.md), [ADR-0003](ADR-0003-rule-representation-format.md), [ADR-0004](ADR-0004-knowledge-storage-architecture.md), [ADR-0005](ADR-0005-rule-execution-model.md), [ADR-0009](ADR-0009-identity-authentication-authorization.md), [ADR-0010](ADR-0010-evidence-storage-tamper-evidence.md), [ADR-0016](ADR-0016-deployment-resilience-runtime-topology.md), [ADR-0017](ADR-0017-observability-operational-readiness.md), [KB-001](../docs/02-knowledge/KB-001-knowledge-governance.md), [risk-register](../docs/00-program/risk-register.md) RSK-012, G-09 (RSK-003) |

## Context and constraints

ADR-0004 established the governed knowledge pipeline: Git/JSON authoring → review → canonical CI → deterministic
bundle build → immutable hashed knowledge bundle → verified all-or-nothing load → immutable `RuntimeKnowledge`.
Git is the source of truth; the bundle is a projection; the runtime loads verified immutable knowledge; PostgreSQL
never becomes knowledge authority. ADR-0004 did **not** decide **how an approved published bundle is identified,
released, distributed, activated, rolled back, withdrawn and verified across deployments** — the question reserved
for ADR-0013. This ADR answers it as architecture, before any artifact repository, release service, signing code,
download/auto-update, activation/rollback API, or admin UI exists.

The current implementation (`knowledge/publish/build_bundle.py`) already produces a manifest with
`content_digest` (SHA-256 over the sorted `<path>=<sha256>` file set, excluding build time/commit), alongside a
static `bundle_version` (`1.0.0`), `manifest_schema_version`, `commit_sha`, and `component_versions`. Because
`bundle_version` is a static constant independent of content changes, **`bundle_version` alone cannot be the exact
immutable artifact identity** — `content_digest` is load-bearing. This ADR does not modify `build_bundle.py`.

Rule poisoning is a modelled risk (RSK-012); AI is never a publication authority (CON-003, NG-07, FR-075); and
`ENGINE_VERSION = 1.0.0` and Phase-3/Phase-4 authority are unchanged. **G-09 remains OPEN.**

## Decision

**An approved knowledge bundle is published only through the existing governed Git/CI process, built
deterministically, addressed by its exact `content_digest` (with associated version/provenance metadata),
published as an immutable artifact into a vendor-neutral distribution boundary, and activated **explicitly by
exact identity** after local pre-activation validation and — across untrusted/external distribution boundaries —
publisher-authenticity verification. Runtime never follows a mutable "latest" channel; no distribution store,
database, or service becomes knowledge authority; and no distribution/signing vendor is selected.**

1. **Governed publication only.** Only governed knowledge changes that have passed the existing review + canonical
   CI + deterministic build + bundle validation may be published (ADR-0004, KB-001). Publication/distribution
   infrastructure may **not** invent or modify knowledge; distribution, PostgreSQL, and runtime are **not**
   knowledge authority. No step bypasses review/CI. **AI cannot publish/activate; an admin UI cannot directly
   publish authoritative rules.**
2. **Publication flow.** AUTHOR → REVIEW → CANONICAL CI PASS → DETERMINISTIC BUNDLE BUILD → BUNDLE VALIDATION →
   RELEASE RECORD / EXACT DIGEST → IMMUTABLE PUBLICATION → DISTRIBUTION → PRE-ACTIVATION VALIDATION → EXPLICIT
   ACTIVATION.
3. **Exact artifact identity.** A published bundle is identified by its **`content_digest`** plus associated
   `bundle_version`, `manifest_schema_version`, `commit_sha`, and `component_versions`. `bundle_version` alone
   does **not** uniquely identify exact knowledge; mutable replacement of contents behind the same exact digest is
   forbidden.
4. **Immutability.** Published bundle artifacts are immutable; a knowledge change creates a **new** content digest,
   never an overwrite. Historical artifacts required for reproducibility remain addressable under the applicable
   retention policy (duration not invented; OI-05 where applicable).
5. **Vendor-neutral distribution boundary.** A conceptual `PublishedBundleRepository` (a.k.a.
   `KnowledgeBundleRepository`) abstracts distribution; possible future transports (artifact repository, object
   store, release asset, offline package) are examples only, **none selected**. Transport does not change
   authority.
6. **Offline / on-prem preserved.** Runtime must **not** require GitHub or Internet access to evaluate (ADR-0004);
   an on-prem/offline deployment receives a self-contained published bundle through a controlled
   distribution/import process and verifies it locally.
7. **No "latest" authority.** Governed evaluation must **never** download-latest / use-newest / auto-follow a
   mutable channel. Activation references an **exact validated bundle identity**. A human-readable channel
   (candidate/stable) may later exist only as a pointer to an exact immutable identity; the pointer alone is never
   sufficient provenance.
8. **Pre-activation validation.** Before activation: manifest validation; per-file SHA-256 verification;
   content-digest verification; schema/manifest compatibility; runtime compatibility; required-component presence;
   governed publication state; and authenticity verification where policy requires it. Failure → **candidate
   rejected**; never a silent fall-back to arbitrary latest content.
9. **Publisher authenticity (distinct from integrity).** `content_digest`/SHA-256 proves **content integrity
   relative to a trusted expected digest**, not **who published** the artifact. Across untrusted/external/on-prem
   distribution boundaries, a verifiable publisher-authenticity mechanism (a separately purposed
   `KnowledgeReleaseSigner` / release-signing boundary) is required before production activation. Its signing key
   is **key-purpose-separated** and **must not reuse the `AuditCheckpointSigner` key** (ARCH-004 §7). No signing/
   PKI/KMS/HSM product is selected, and no claim is made that current bundles are already publisher-signed.
   Required-but-failed authenticity verification → **do not activate**, do not mark trusted, do not reinterpret
   active knowledge; preserve the existing known-good active bundle where safe.
10. **Explicit activation model.** States: `PUBLISHED` → `DISTRIBUTED` → `VALIDATED` → `ACTIVE`, with failure
    path → `REJECTED`. Exactly one exact bundle identity is used for one evaluation. A durable **operational**
    activation record (content digest, bundle/manifest version, activation time, deployment/environment,
    actor/workload, previous bundle identity, outcome) may be kept — this does **not** make PostgreSQL
    authoritative for knowledge (schema is Phase 6).
11. **Runtime activation is immutable.** `RuntimeKnowledge` is not mutated in place (ARCH-001 `INV-07`); a
    knowledge update creates a **new** validated runtime-knowledge instance behind a controlled activation
    boundary, and an in-flight evaluation never switches bundles mid-evaluation.
12. **Replica rollout, rollback, withdrawal.** Temporary mixed bundle versions across replicas during controlled
    rollout may exist, but **each evaluation pins exactly the bundle it used** and no completed `DetectionResult`
    is reinterpreted (ARCH-005 §4.4). **Rollback** = explicit activation of a previous known-good exact immutable
    bundle — never editing/rewriting a bundle or a historical result/replay provenance, and never an automatic
    ungoverned load of an arbitrary prior/latest bundle. **Withdrawal/revocation** marks a bundle
    *not-approved-for-new-activation* **without** destroying historical artifacts needed to reproduce prior
    evaluations (retention policy-driven); its full historical-use / future-activation / **currently-active**
    semantics are specified in the "Withdrawal / revocation" section below.
13. **Fail-closed knowledge.** Missing/corrupt/digest-mismatched/incompatible candidate → reject activation. If no
    valid active bundle exists at startup, readiness/evaluation fails closed (ARCH-005 §9); it never returns
    `NO_SCAM_PATTERN`. A historically pinned bundle unavailable for replay → replay fails explicitly; never
    substitute current/latest (ARCH-001 `INV-08`, ARCH-003 §11). A bundle may be cryptographically digest-valid yet
    **governance-withdrawn**: digest validity alone is **not** sufficient for approved operational use, and a
    deployment must know the governed eligibility state of its exact active bundle (distribution infrastructure
    never becomes knowledge authority).
14. **Governed audit of publication-lifecycle actions.** Accountability-bearing lifecycle actions produce governed
    audit events (ADR-0010; not merely operational telemetry), covering at minimum: publication;
    distribution/import where governance/accountability applies; activation; rollback; withdrawal/revocation;
    rejected activation where relevant; and active-withdrawn remediation. Each event conceptually identifies the
    exact bundle `content_digest`, the lifecycle action, the actor/workload identity, the target
    environment/deployment where applicable, the outcome, the previous/next bundle identity where applicable, and
    a timestamp/reference per the existing audit architecture. Raw rule/evidence content is never placed in
    general operational logs, and a withdrawal **alert never replaces** its governed audit event (telemetry =
    operational visibility; governed audit = accountability/history).

## Withdrawal / revocation (historical use · future activation · currently-active bundle)

Withdrawal/revocation expresses **governed eligibility**, not artifact destruction, and is separated into three
cases.

**A. Historical use.** Prior evaluations that used the bundle are **not** rewritten, retain the exact withdrawn
bundle identity in provenance, remain reproducible using the historical artifact where retained, and are not
retrospectively changed merely because the bundle is later withdrawn.

**B. Future activation.** A withdrawn/revoked bundle **cannot** be selected for a new activation, **cannot** be
selected by rollback as a new target unless governance explicitly restores its eligibility through a new governed
decision, and **cannot** be silently selected through a channel/pointer.

**C. Currently-active bundle.** If a bundle becomes withdrawn/revoked while it is currently active on one or more
deployments, then once withdrawal is **effective** for a deployment:

1. the deployment MUST expose an explicit operational/governance state (e.g. `ACTIVE_BUNDLE_WITHDRAWN`);
2. it MUST generate an operational/security signal, an alert/incident condition, and a **governed audit event**
   (per Decision 14);
3. it MUST trigger a governed remediation workflow to activate a **replacement approved exact bundle** or
   explicitly roll back to a **previous known-good approved exact bundle** (each via normal pre-activation
   validation);
4. it MUST NOT silently remain in a normal/healthy knowledge state;
5. **no new** governed evaluation may begin using that withdrawn exact bundle once withdrawal is effective for that
   deployment; and
6. an in-flight evaluation MUST NOT switch bundles mid-execution — it remains pinned to the exact bundle with
   which it started (preserving one-bundle-per-evaluation) and follows the future governed withdrawal/effective-time
   operational policy; it may **never** silently switch to another bundle. Exact cancellation/drain mechanics are
   deferred to Phase 6.

Replacement or rollback is itself **explicit, governed, exact-identity based, validated and auditable**; withdrawal
never auto-loads an arbitrary prior/latest bundle, never rewrites prior `DetectionResult`s or replay provenance,
never deletes/mutates historical bundle identity or bytes, and never silently re-runs previous cases or invokes AI
re-analysis. A mixed-replica state (one replica on an approved bundle, another on a withdrawn bundle) is an
operational inconsistency requiring remediation — it must **not** look healthy merely because both bundles are
digest-valid (no atomic-rollout technology is required to surface it).

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A — Governed Git/CI → deterministic digest-addressed immutable bundle → vendor-neutral distribution → explicit activation by exact identity (this ADR)** | Deterministic, reproducible, offline/on-prem; explicit rollback/withdrawal; auditable; integrity + separable publisher authenticity; no vendor lock; preserves ADR-0004 and Phase-3 authority | Requires distribution + activation + authenticity machinery (Phase 6); operational activation record to maintain | ✅ **Selected** |
| B — Runtime reads repo/working tree or uses "latest" | Trivial | Non-reproducible; no integrity/authenticity boundary; violates `INV-07`/`INV-08`; semantic-drift and poisoning risk (RSK-012) | ❌ Rejected |
| C — Database becomes authoritative for published rules/distribution | Queryable; single store | Violates ADR-0004 (PostgreSQL not knowledge authority); weakens immutability/reproducibility; larger tamper surface | ❌ Rejected |
| D — Central always-online rule service dynamically distributes current rules | Central control | Breaks offline/on-prem; introduces availability dependency and a mutable-latest authority; semantic-drift and outage risk | ❌ Rejected |

Comparison spanned determinism, reproducibility, offline/on-prem operation, rollback, auditability, integrity,
publisher authenticity, failure isolation, operational complexity, distribution flexibility, vendor lock-in,
semantic-drift risk, and reversal cost.

## Justification

The strongest guarantee is that governed evaluation always consumes an **exact, immutable, digest-addressed**
bundle produced by the existing review/CI pipeline and **explicitly activated** — so no "latest" channel,
database, or distribution service can silently change what the engine reasons over (rejecting B/C/D). Making
`content_digest` load-bearing (not `bundle_version`) matches the implementation reality and prevents two different
knowledge sets sharing an identity. Separating **integrity** (digest) from **publisher authenticity** (a distinct
`KnowledgeReleaseSigner`, key-separated from the audit signer) closes the "who published this" gap on untrusted
distribution boundaries without overclaiming that a hash proves provenance. Explicit rollback and
withdrawal-without-history-destruction preserve reproducibility and replay. Deferring the distribution/signing
product keeps the architecture offline-capable and vendor-neutral. No efficacy is claimed (G-09 OPEN).

## Consequences

**Positive.**
- Deterministic, reproducible, offline/on-prem-capable publication with exact digest identity.
- Explicit activation/rollback/withdrawal; historical reproducibility and replay preserved.
- Integrity and separable publisher-authenticity boundaries; audit-signer key not reused (RSK-012).
- ADR-0004 authority, `INV-07`/`INV-08`/`INV-13`/`INV-14`, and Phase-3 authority preserved.

**Trade-offs.**
- Distribution, activation, authenticity/signing, and the operational activation record are Phase-6 implementation.
- A publisher-authenticity (signing/PKI) mechanism and its key custody must be selected later.
- Retention duration for historical artifacts remains policy-driven (OI-05).

## Risks

| Risk | Mitigation (this ADR / ARCH-007) |
|---|---|
| Rule poisoning / publication bypass (RSK-012) | Governed review+CI only; AI/admin-UI cannot publish; pre-activation validation; publisher authenticity on untrusted boundaries |
| Two knowledge sets sharing an identity | `content_digest` load-bearing; `bundle_version` alone insufficient; no mutable replacement behind a digest |
| "Latest"/mutable-channel drift | Activation by exact identity only; pointer never sufficient provenance |
| Digest match mistaken for provenance | Integrity ≠ authenticity; separate `KnowledgeReleaseSigner` required externally |
| Audit-signer key reuse | Key-purpose separation; release signing distinct from `AuditCheckpointSigner` (ARCH-004 §7) |
| Distribution/DB/runtime becoming authority | Explicitly forbidden; Git/ADR-0004 authoritative; operational records non-authoritative |
| Withdrawal destroying replay history | Withdrawal blocks new activation only; historical artifacts retained for reproducibility |
| Withdrawn bundle still actively serving | `ACTIVE_BUNDLE_WITHDRAWN` state + signal + alert + governed audit; governed replacement/rollback required; no new evaluations on it once effective; never silently healthy |
| Missing pinned bundle at replay | Replay fails explicitly; never substitute latest (`INV-08`) |
| Offline break | Runtime never requires Internet; local verification after controlled import |

## Reversal cost

**Low–Medium.** The distribution transport, signing product, activation-record schema and channel labels are cheap
to revise because they sit behind the vendor-neutral `PublishedBundleRepository`/`KnowledgeReleaseSigner`
boundaries. What is expensive to reverse are the **invariants**: exact digest-addressed immutable identity,
explicit activation, no-latest, integrity-vs-authenticity separation, and rollback/withdrawal without history
destruction. Reversing those (e.g. a mutable-latest channel or a DB/service knowledge authority) would reintroduce
semantic-drift, poisoning, and replay-integrity risks and require re-validating the whole knowledge path. The
invariants are deliberately durable.

## Validation plan

Architecture only; concrete mechanics are Phase-6 implementation.

- **ARCH-007** — integrated authority map placing publication/distribution under ADR-0013/ARCH-007; cross-WP
  knowledge contract matrix; invariant reconciliation (`INV-07`/`INV-08`/`INV-13`/`INV-14`).
- **Phase 6** — distribution transport, `KnowledgeReleaseSigner`/PKI and key custody, activation/rollback/
  withdrawal implementation and operational activation-record schema, and pre-activation-validation enforcement
  tests (digest/authenticity mismatch → reject; no-latest; replay fail-closed on missing pinned bundle).
- **Existing evidence** — `build_bundle.py`/`validate_bundle.py` deterministic digest build and all-or-nothing
  verified load remain the integrity oracle (unchanged by this WP).
- **Independent review** — approval of this Proposed ADR precedes any Accepted status; no artifact repository,
  release service, signing code, download/activation/rollback API, or admin UI is created by this WP.
