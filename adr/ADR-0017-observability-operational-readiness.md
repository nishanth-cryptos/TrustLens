# ADR-0017 — Observability and operational readiness

| Field | Value |
|---|---|
| Status | **Accepted** — following independent P5-WP6 review (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 1 / INFO 3; APPROVE) |
| Date | 2026-09-06 |
| Owner role | Chief Architect / Principal Security Engineer |
| Phase | Phase 5 — P5-WP6 observability, operability and operational readiness |
| Related | `MP §16, §20, §21`, [PROGRAM-001](../docs/00-program/PROGRAM-001-program-charter.md) (NFR-006/007/010/016, FR-062, CON-003, NG-07), [ARCH-001](../docs/05-architecture/ARCH-001-enterprise-architecture.md) (`INV-01`…`INV-15`, §15), [ARCH-002](../docs/05-architecture/ARCH-002-python-runtime-service-topology.md), [ARCH-003](../docs/05-architecture/ARCH-003-persistence-evidence-tamper-architecture.md), [ARCH-004](../docs/05-architecture/ARCH-004-security-trust-threat-model.md), [ARCH-005](../docs/05-architecture/ARCH-005-deployment-resilience-recovery.md), [ARCH-006](../docs/05-architecture/ARCH-006-observability-operational-readiness.md), [ADR-0004](ADR-0004-knowledge-storage-architecture.md), [ADR-0007](ADR-0007-ai-authority-and-model-strategy.md), [ADR-0008](ADR-0008-python-runtime-service-topology.md), [ADR-0009](ADR-0009-identity-authentication-authorization.md), [ADR-0010](ADR-0010-evidence-storage-tamper-evidence.md), [ADR-0016](ADR-0016-deployment-resilience-runtime-topology.md), [risk-register](../docs/00-program/risk-register.md) RSK-008/010/011/012/017/018, G-09 (RSK-003) |

## Context and constraints

ARCH-001 §15 requires structured logs, correlation IDs, metrics and health, while deferring the telemetry schema,
alert thresholds and service-scoped SLOs. ARCH-005 defined the deployment/resilience model and handed WP6 the
list of *what* must be observable (replica readiness, dependency state, worker backlog, signer pending state,
backup/restore, key/secret errors, reconciliation) plus the RPO/RTO objectives, alert thresholds and runbooks.
ADR-0010 established a governed, append-only, tamper-evident **audit** mechanism that is distinct from operational
telemetry. No observability architecture, vendor, or operational model has been chosen yet.

This ADR fixes **how TrustLens becomes observable and operable** — as architecture, before any telemetry SDK,
logging library, trace exporter, metrics/health endpoint, dashboard, alert rule, collector, or pager integration
exists. It also closes the P5-WP5 independent-review finding **LOW-WP5-1** by adding a terminal operational
signer-failure state (retries exhausted / key permanently unavailable / key revoked / policy-blocked /
unrecoverable) to the operational signer model, without ever converting a failure into a signed success.

Observability must remain **outside decision authority**: telemetry may not set, override, or reinterpret a
`DetectionResult` (CON-003, `INV-01`/`INV-11`). `ENGINE_VERSION = 1.0.0` is unchanged. **G-09 remains OPEN**;
aggregate classification counts are descriptive operational distributions only, never accuracy/precision/recall/
false-positive/negative or efficacy claims.

## Decision

**TrustLens adopts a vendor-neutral three-signal observability architecture — metrics + structured logs +
traces/correlation — combined with explicit health/dependency states, governed operational alerts, and
runbook-driven response. Operational telemetry is strictly separated from the governed audit mechanism, remains
outside decision authority, excludes raw evidence/secrets/PII, and never blocks or alters Phase-3 evaluation. No
observability vendor is selected.**

1. **Three signals, vendor-neutral.** Metrics (bounded-cardinality), structured categorical logs, and
   trace/correlation are defined as portable concepts behind neutral contracts; no Prometheus/Grafana/
   OpenTelemetry/Datadog/Elastic/Splunk/CloudWatch/PagerDuty/etc. product is chosen (examples only, non-selected).
2. **Telemetry ≠ audit.** Operational telemetry (health/diagnostics; may be aggregated, sampled, or expired under
   policy) is a different system from the governed ADR-0010 audit (append-only, tamper-evident, security/custody
   authority). Telemetry loss must never silently delete or replace required audit history, and general
   application logs are **not** called "audit logs" unless within the governed audit mechanism.
3. **Telemetry outside decision authority.** Metrics/logs/traces never set, override, or reinterpret
   classification, severity, risk, confidence, governing rule, or actions, and are never the authoritative
   reconstruction of `DetectionResult`, evidence, audit history, or knowledge state (those remain with their
   accepted stores/artifacts).
4. **Telemetry failure is contained.** General metrics/log/trace backend outage yields an operational
   `OBSERVABILITY_DEGRADED` state — never `NO_SCAM_PATTERN`, safe, clean, or successful-integrity. Telemetry
   emission is bounded and failure-contained (bounded buffering / sampling / dropping lower-priority signals after
   bounds / explicit telemetry-loss signal) and **never** a synchronous network dependency of Phase 3. Required
   governed **audit** failure keeps existing WP3/WP4 fail-closed semantics and is never treated as droppable
   telemetry.
5. **Privacy and cardinality by construction.** General telemetry excludes raw evidence, full user messages,
   screenshots, uploaded files, AI request/response bodies containing user content, passwords/tokens/API
   keys/private keys, OTP/PIN/PAN/account data, unnecessary PII, and secret values (ARCH-003/004 preserved). Full
   attacker-controlled submitted URLs are not logged by default (categorical source/type/opaque reference
   instead). Metrics use bounded labels only (component, operation, status, error category, dependency,
   environment, release version, capability mode) — never `case_id`/`evidence_id`/`user_id`/`trace_id`/full
   URL/message content.
6. **Correlation model.** A vendor-neutral correlation set (e.g. `correlation_id`, `trace_id`, `span_id`,
   `operation_name`, `component`, `environment`, `release_version`, and `ENGINE_VERSION` / `knowledge_bundle_version`
   where relevant, `outcome`, `categorical_error_code`, `duration`) links a request across replica, persistence,
   worker dispatch/execution, controlled egress and provider call. Tracing may be sampled but never changes
   application decisions, removes governed audit, or is presented as custody/history evidence. **Phase-3 reasoning
   stays in-process; tracing does not create or imply a remote Phase-3 service.**
7. **Operational severity is separate.** An operational-severity namespace (`OPS_CRITICAL`/`OPS_HIGH`/`OPS_MEDIUM`/
   `OPS_LOW`/`OPS_INFO`) describes system/operator urgency and is independent of TrustLens `DetectionResult`
   severity (governed scam-risk reasoning). A system incident (e.g. PostgreSQL unavailable) is an OPS incident,
   not a `CRITICAL` scam result.
8. **Health/dependency observability.** WP5's startup / liveness / readiness / optional-dependency-health /
   degraded-capability model is preserved (not redesigned); WP6 defines observable signals and dependency-health
   categories (`HEALTHY`/`DEGRADED`/`UNAVAILABLE`/`UNKNOWN`, where `UNKNOWN` is never silently treated as
   `HEALTHY`). **Optional AI outage is never treated as core outage** and does not gate deterministic readiness or
   the core availability objective.
9. **Governed alerts + runbooks.** Alerts are actionable, deduplicated/state-based where appropriate, owner- and
   runbook-mapped, and bounded against alert storms; candidate alert classes are named without invented numeric
   thresholds. A runbook catalog (trigger/scope/owner/verification/containment/safe-recovery/integrity/escalation/
   closure/prohibited-actions) covers the WP5/WP6 failure domains. Runbooks must **never** instruct changing a
   `DetectionResult`, overriding classification, editing an evidence digest, marking an unsigned checkpoint signed,
   disabling encryption, bypassing authorisation, using arbitrary latest knowledge, deleting audit history, or
   promoting an unverified restore.
10. **Signer terminal-failure state (closes LOW-WP5-1).** The operational signer model adds
    `CHECKPOINT_TERMINAL_FAILURE` alongside `CHECKPOINT_PENDING` / `CHECKPOINT_SIGNED` / `RETRYABLE_FAILURE`.
    Terminal failure means the current automatic signing lifecycle cannot safely succeed without explicit
    remediation. Invariants: terminal failure **never** becomes signed success automatically; no fabricated
    signature; the original failure remains auditable; authorised remediation creates a new/linked signing attempt
    that preserves history (key recovery/replacement does not rewrite old failure events); previously signed
    checkpoints stay signed and unchanged; terminal state emits an operational/security signal. Pending age is
    measurable, but the maximum acceptable pending age is **NOT YET SPECIFIED**.
11. **SLI/SLO and RPO/RTO frameworks, not numbers.** SLI classes and an SLO framework with ownership are defined;
    the core deterministic-evaluation objective is kept separate from optional AI-assisted-extraction availability;
    an error-budget concept is optional. No numeric SLO/RPO/RTO is invented absent sponsor evidence — targets are
    **NOT YET SPECIFIED** with named owners. RPO observability uses last-verified-recoverable-backup/watermark age;
    RTO observability uses restore-initiation → integrity-verification → safe-promotion.
12. **ADR-0013 untouched.** Rule-set publication/distribution (reserved ADR-0013) is **not** issued or resolved
    here; P5-WP7 reconciles it before Phase-5 closure. Git/CI/immutable-bundle governance (ADR-0004) remains
    authoritative; monitoring never becomes rule-approval/publication authority.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A — Vendor-neutral metrics + structured logs + traces/correlation + health/dependency + alert/runbook (this ADR)** | Strong diagnosability and failure localisation; correlation across replica/worker/egress; portable, no vendor lock; separates telemetry from audit and from decision authority; supports privacy/cardinality controls | Requires disciplined signal/cardinality/privacy design; three signal types to model | ✅ **Selected** |
| B — Logs-only operational model | Simple; low moving parts | Poor aggregate/latency visibility; weak correlation and failure localisation; easy to leak sensitive free-text; hard to build SLIs | ❌ Rejected |
| C — Metrics-only operational model | Cheap aggregate health | No per-incident context; poor root-cause; no correlation/trace for cross-component failures; weak security-operational forensics | ❌ Rejected |
| D — Vendor-specific integrated platform as architectural authority | Fast to wire; batteries included | Vendor lock-in; portability/cost risk; couples architecture to a product; risks treating vendor store as audit/decision authority | ❌ Rejected (a vendor may later *implement* Option A, but not *be* the architecture) |

Comparison spanned diagnosability, failure localisation, correlation, operational complexity, privacy risk,
cardinality risk, vendor lock-in, cost portability, security observability, incident response, and reversal cost.
No benchmark numbers are invented.

## Justification

Three complementary signals are needed because each answers a different question: metrics show *that* something is
wrong and trends, logs show *what* happened for a specific operation, and traces/correlation show *where* across
replica/worker/egress a failure occurs. Logs-only (B) and metrics-only (C) each lose one of those axes and, for a
one-engineer team, that gap turns an incident into a guessing exercise. Keeping the architecture vendor-neutral
(rejecting D as *authority*) preserves portability and, critically, prevents a monitoring product from being
mistaken for the governed audit or decision authority. The hard separations — telemetry vs audit, telemetry vs
decision authority, operational vs detection severity, optional-AI vs core health — are what keep observability
from silently corrupting integrity or safety semantics. The terminal signer-failure state closes LOW-WP5-1 while
preserving the no-unsigned-as-signed and history-immutability invariants. No efficacy or availability is claimed
(G-09 OPEN).

## Consequences

**Positive.**
- Diagnosable, correlatable operations across replicas, workers, egress and providers without a remote Phase-3.
- Telemetry cannot alter, block, or reconstruct decisions; audit integrity and fail-closed semantics preserved.
- Privacy/cardinality controls keep raw evidence/secrets/PII out of telemetry (RSK-010).
- Terminal signer-failure state closes LOW-WP5-1 with history-preserving invariants.
- Portable, vendor-neutral; a product can later implement it without becoming the authority.

**Trade-offs.**
- Disciplined signal/cardinality/privacy modelling is required; three signal types add design surface.
- Numeric SLO/RPO/RTO/threshold values, dashboards, alert rules and the telemetry product remain deferred to
  sponsor evidence / Phase 6, so this ADR establishes framework and ownership, not tuned targets.
- Operational severity vs detection severity duality must be taught to operators to avoid confusion.

## Risks

| Risk | Mitigation (this ADR / ARCH-006) |
|---|---|
| Telemetry mistaken for audit / custody | Explicit telemetry≠audit separation; audit stays ADR-0010 append-only/tamper-evident |
| Telemetry outage changing/blocking decisions | `OBSERVABILITY_DEGRADED`; non-blocking bounded emission; never a Phase-3 sync dependency; never `NO_SCAM_PATTERN` |
| Raw evidence/secrets/PII in telemetry (RSK-010) | Privacy-by-construction exclusions; URL/content logging limits; automated leak scanning (Phase 6) |
| Metric cardinality explosion | Bounded labels only; no case/evidence/user/trace IDs or full URLs as labels |
| Optional AI outage read as core outage | Optional-vs-core separation in health, alerts and SLOs |
| Unsigned/terminal checkpoint appearing signed (LOW-WP5-1) | Terminal state never auto-signs; no fabricated signature; history preserved; operational/security signal |
| Efficacy overclaim from classification counts | Descriptive distributions only; no accuracy/precision/recall/FP/FN; G-09 OPEN |
| Invented SLO/RPO/RTO without evidence | Frameworks + ownership only; numeric targets NOT YET SPECIFIED |
| Monitoring becoming rule-publication authority | Git/CI/bundle governance (ADR-0004) authoritative; monitoring is read-only status |
| Runbook overriding the engine | Prohibited-actions list; runbooks never change decisions/audit/integrity |

## Reversal cost

**Low–Medium.** The observability product, exact signal names, dashboards, alert rules and thresholds are cheap to
revise because the architecture is vendor-neutral and behind portable contracts. What is more expensive to reverse
are the **separations**: telemetry vs governed audit, telemetry vs decision authority, operational vs detection
severity, and optional-AI vs core health, plus the terminal signer-failure invariants. Reversing those (e.g.
letting a monitoring store act as audit/decision authority, or letting a terminal failure silently become signed)
would reintroduce integrity, repudiation and safety risks and require re-validating the audit and detection
boundaries. The separations are deliberately durable; their value is not lowered to make reversal cheap.

## Validation plan

Architecture only; concrete telemetry is later work.

- **ARCH-006** — signal catalog; correlation model; telemetry-vs-audit and telemetry-failure behaviour; signer
  terminal-failure state diagram; health/dependency, SLI/SLO, RPO/RTO frameworks; backup/restore/reconciliation/
  security/AI observability; alert classes; dashboards; runbook catalog RB-01…RB-15; operations, incident-flow and
  backup/restore diagrams; observability-failure matrix.
- **P5-WP7** — reconcile reserved ADR-0013 (rule-set publication/distribution) before Phase-5 closure.
- **P5-WP6 sponsor input / Phase 6** — numeric SLO/RPO/RTO targets, alert thresholds, max pending-checkpoint age,
  telemetry retention durations, and the observability product/exporters/dashboards/alert-rule implementation.
- **Independent review** — this ADR was **Accepted following independent P5-WP6 review** (APPROVE; BLOCKER 0 /
  HIGH 0 / MEDIUM 0 / LOW 1 / INFO 3, the LOW/INFO items recorded as follow-ups in GATE-017 §3.1); no telemetry SDK, logging
  library, exporter, metrics/health endpoint, dashboard, alert rule, collector, or pager integration is created
  by this WP.
