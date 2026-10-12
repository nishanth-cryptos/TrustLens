# PLAN-001 — Implementation blueprint

| Field | Value |
| --- | --- |
| Document ID | PLAN-001 |
| Version | 0.1 |
| Status | APPROVED FOLLOWING INDEPENDENT REVIEW — Phase 8 itself NOT CLOSED; no Phase 9 implementation begun |
| Phase | Phase 8 — Implementation blueprint |
| Owner role | Programme / Backend / Product |
| Branch | phase8-delivery-blueprint |
| Base commit | 0a21d1f858eb7680e05ce703966201f06902e4c8 |
| Phase 7 entry | CLOSED through GATE-032 §8; PR #43 merged; CI #84 and #85 SUCCESS, both required jobs |
| Last updated | 2026-10-12 |

## 1. Outcome, scope and current evidence

The first priority is a runnable application: a user can sign in, preserve submitted text, request deterministic
analysis and read an explanation whose provenance survives a restart. Deliver the persistent walking skeleton at
S2, then the useful text-analysis journey at S5. Reports, optional providers and advanced workflows follow their
own readiness conditions. This document plans future implementation; no application service or infrastructure is
created by this kickoff.

The [roadmap](../00-program/roadmap.md) assigns PLAN-001 epics, slices, tasks, acceptance criteria, Definition of
Ready/Done, demonstrations and release criteria. The existing README reserves this directory for those artifacts;
no PLAN-001 file or Phase 8 work-package/gate record existed at the base. Task and slice IDs below are local to
PLAN-001. This single approved blueprint is the kickoff deliverable; it does not create a parallel contract or validation
framework for approved phases.

[PROGRAM-001](../00-program/PROGRAM-001-program-charter.md) governs programme scope and requirements.
[PHASE-7-CLOSURE](../00-program/PHASE-7-CLOSURE.md) and its
[machine record](../../contracts/phase7/phase7-closure-v1.json) remain authoritative for the handoff: 36 Phase 7
deliverables; 51 public API operations (42 detailed UX, 5 foundation-only, 4 undesigned); and 48 source decisions
(38 CARRIED, 9 SUPERSEDED_BY, 1 RESOLVED_BY). There are also two internal health probes; 53 catalog entries does
not mean 53 public operations. Source owners and exact decision text stay in the existing register.

Verified GitHub evidence confirms [PR #43](https://github.com/nishanth-cryptos/TrustLens/pull/43)
merged at the base commit, head `5af988d2740c4d826abc0f2e3074cd1fe3d28526`.
[CI #84](https://github.com/nishanth-cryptos/TrustLens/actions/runs/38266862243) is completed/SUCCESS.
[CI #85](https://github.com/nishanth-cryptos/TrustLens/actions/runs/38273120361), run `38273120361`, is
completed/SUCCESS; both required jobs completed SUCCESS, as rechecked read-only. GATE-032 §8 now records
governed final Phase 7 closure. PLAN-001 is APPROVED following independent review; this is blueprint approval,
not final Phase 8 closure. Phase 8 itself is NOT CLOSED and no Phase 9 implementation has begun.

The accepted Option A exceptions remain binding: REPORT-001 was **not delivered**, and WCAG 2.2 AA is **NOT
VERIFIED**. Phase 8 must define the report format before planning the report implementation portion of S6;
Phase 10 owns accessibility conformance testing and evidence. Neither future deliverable is waived.

## 2. Accepted implementation boundaries

The [ARCH-007 authority map](../05-architecture/ARCH-007-integrated-phase-5-architecture.md) identifies the owning
ADRs and architectures. Their acceptance is reused; this plan does not reopen their reviews.

| Concern | Binding choice and implementation consequence |
| --- | --- |
| Backend | [ADR-0008](../../adr/ADR-0008-python-runtime-service-topology.md): Python modular monolith, one initial backend deployable, kernel in-process. Thin HTTP adapters call application use cases; the kernel imports no web framework, database or provider adapter. |
| Frontend | React/TypeScript direction preserved by ADR-0008. Present accepted UX-001…006 and API DTOs; perform no rule matching, scoring, authorization or reconstruction of missing historical results. |
| Decision authority | Reuse `knowledge/runtime/result.py` → `evaluate_detection_from_governed(...)`; `ENGINE_VERSION = 1.0.0`. Host orchestration derives trusted context and persists the exact result. It never accepts client-supplied decision/provenance fields or builds a fallback verdict. |
| Optional AI | [ADR-0007](../../adr/ADR-0007-ai-authority-and-model-strategy.md) and `knowledge/ai/integration.py` → `evaluate_with_optional_ai(...)`: default OFF, validated observations only, exact deterministic fallback for the governed optional failures. An authoritative kernel ERROR is never optional-AI success. |
| Data and migrations | [DATA-001](../06-contracts/DATA-001-data-domain-lifecycle-contract.md), [DATA-001-WP2](../06-contracts/DATA-001-WP2-postgresql-persistence-contract.md), [ADR-0011](../../adr/ADR-0011-database-migration-tooling.md): PostgreSQL operational records and Alembic SQL-first, explicitly reviewed migrations. No ORM is selected, no auto-create/startup schema mutation, no database authority for knowledge. |
| Content, keys and audit | [ADR-0010](../../adr/ADR-0010-evidence-storage-tamper-evidence.md) / [ARCH-004](../05-architecture/ARCH-004-security-trust-threat-model.md): encrypted private `EvidenceContentStore`, digest-verified bytes, protected secret/key ports and append-only governed audit. Key/secret failure fails affected operations closed; no default key or plaintext fallback. |
| Identity and authorization | [ADR-0009](../../adr/ADR-0009-identity-authentication-authorization.md): external OIDC, interactive Authorization Code + PKCE, exactly five existing roles, TrustLens-owned role + resource authorization on every request. Minimum security is required from the first protected operation, before S9 expands administration. |
| HTTP contract | [API-001](../06-contracts/API-001-api-resource-protocol-contract.md) and [OAS-001](../06-contracts/OAS-001-openapi-contract.md), `contracts/api/api-v1.json` / `openapi-v1.json`: accepted paths, DTOs, errors, binary transfer, durable idempotency and If-Match rules. No invented login, export, analytics or operator API. |
| Operational invariants | [OPS-001](../06-contracts/OPS-001-operational-replay-persistence-contract.md): fenced completion, durable idempotency, monotonic ETags, removal tombstones, exact replay and restore anti-resurrection. Canonical artifact text/digests are immutable; projections cannot reinterpret them. |
| Deployment and enrichment | [ADR-0016](../../adr/ADR-0016-deployment-resilience-runtime-topology.md): externalized durable state and future identical replicas; a local development instance is not an HA claim. [ADR-0012](../../adr/ADR-0012-threat-intelligence-adapter-architecture-provider-selection.md) / [INT-001](../06-contracts/INT-001-external-enrichment-integration-contract.md): approved indicator lookup only, controlled egress, no fetch of submitted URLs, enrichment advisory only. |

The roadmap still controls the eleven-slice sequence below. Its historical Java core / separate Python-service
wording is superseded by ADR-0008; Python is the backend from the start, and S10 adds optional AI integration
rather than a required remote reasoning service. No engine rewrite or new deployable is justified here.

HTTP framework, PostgreSQL driver/adapter, frontend build tooling, runtime versions, IdP, content-store adapter,
secret/key mechanism and deployment target are not approved product selections in this record. T03 must record a
bounded implementation profile and pin application dependencies before S1/S2 are ready. Assess exact API/OpenAPI
parity, transaction/fencing support, binary transfer, authentication, supported versions and reproducible builds;
keep application locks separate from the existing knowledge-validation requirements. A topology or authority
change requires the existing ADR process; choosing an adapter within accepted ports does not reopen Phase 5.

## 3. Phase 8 decisions and prerequisites

T01 is MET through the verified closure record; T02–T10 remain OPEN. Names denote accountable existing roles, not additional API roles.

| Task | Decision or evidence required | Owner | Blocks |
| --- | --- | --- | --- |
| T01 | MET — CI #85 and both required jobs succeeded; governed Phase 7 closure recorded in GATE-032 §8. | Programme / builder bookkeeping | Phase 7 closure dependency satisfied; remaining Phase 8/implementation prerequisites are unchanged. |
| T02 | RSK-006 / OI-02: install Docker and PostgreSQL; verify daemon/Compose operation, database connectivity, a disposable migration exercise and persistence across restart. Command presence alone is insufficient. | Sponsor (admin install) with DevSecOps | Any Phase 9 implementation; Testcontainers integration checks. Installation is not established by this task. |
| T03 | Select and document the bounded local application profile described in §2, including runtime/dependency pins, identity provisioning, protected storage/key references and resource limits. Use synthetic development data; no credentials in Git. OI-06 remains a sponsor decision for hosting. | Backend / Data / Security / DevSecOps with Sponsor | S1 completion and runnable S2; external deployment remains separately gated. |
| T04 | Resolve ASM-002 before accepting or executing the first schema-creating migration, exactly as DATA-001-WP2 §3 requires. Single tenancy is still UNCONFIRMED / PROVISIONAL. Multi-tenancy requires the governed contract revision before schema implementation. | Sponsor / Programme | Schema creation and tenancy-sensitive implementation in S1/S2. No tenant field is invented. |
| T05 | UX-001#0: decide the unresolved browser session / CSRF profile in Phase 8 **before browser implementation**. Record token/session custody, credential transport, CSRF controls where applicable, origins, logout/revocation and secret handling while preserving external OIDC. | Security Architect | Any S2 browser authentication or protected browser flow. CLI API bearer authentication is not a browser-profile decision. |
| T06 | UX-005#0: define and approve REPORT-001, with format, reproducible pinned inputs, uncertainty/disclaimer, content access and export requirements. | Product / Reporting | Planning the report implementation portion of S6, then its implementation. §4 reserves that work without defining a formatter or report layout. |
| T07 | P7C-01: agree operator interaction scope for the four accepted but undesigned workflows (§6). The candidate proposal is an authenticated operator CLI first; detailed interaction design and failure/confirmation copy remain required. | Product with Knowledge governance and Operations | Operator interaction delivery in S3/S9/S11; none is claimed UX-designed by Phase 7. |
| T08 | Schedule the Phase 8 API/data/copy clarifications in §7; retain accepted contracts until a necessary governed revision is approved. Safe restricted scope may proceed where identified. | Existing carried owners in PHASE-7-CLOSURE | Each dependent operation or presentation; no speculative API expansion. |
| T09 | Define OPS-001 implementation parameters and deployment profile values: upload/media/size controls, polling/backoff, leases, idempotency windows, bounds and recovery controls. Record values and rationale before their dependent feature runs. | Backend / Operations / Security, with Product for UX limits | Unbounded retries, work, uploads or cleanup cannot be shipped. No numerical value is selected here. |
| T10 | Resolve OI-05 retention/legal basis and permitted tombstone/backup residual metadata before live retention, deletion or restored-content promotion. Preserve G-09, ASM-001 and the existing programme caveats. | Sponsor + legal/governance; QA for G-09 | Live-data policy and dependent S6/S11 release scope. ASM-014's historic 90-day assumption is not an accepted duration. |

No calendar commitment exists (OI-03 / ASM-009). Sizes below are relative planning estimates, not dates or capacity
promises. No infrastructure, credentials, provider or deployment is represented as already available.

## 4. Ordered vertical slices and implementation tasks

Epics group the roadmap sequence: **E1** runnable foundation (S1–S2), **E2** deterministic analysis (S3–S5),
**E3** evidence/history and extensions (S6–S8), **E4** governed workflows and optional AI (S9–S10), **E5** operability
and release evidence (S11). Dependencies are required capabilities, not permission to bypass prerequisite tasks.

| Slice / size | Dependencies | Concrete implementation tasks | Demonstration and acceptance criteria |
| --- | --- | --- | --- |
| S1 — Repository hygiene and CI / S | T01–T04 resolved; PLAN-001 independently approved for the selected scope | S1.1 create application package/build boundaries; S1.2 add pinned application dependencies and clean-clone commands; S1.3 retain the canonical offline suite and add feature build/test checks; S1.4 prepare reviewed migration and configuration entry points. | A clean checkout builds frontend/backend packages and runs the existing 36-validator gate plus the new build checks. No application imports leak into the kernel; no secrets or user evidence enter Git. A build is not a deployed service. |
| S2 — Persistent walking skeleton / M | S1; T05, T09; accepted minimum schema and protected local profile | S2.1 implement the principal/role/resource boundary and needed PostgreSQL constraints; S2.2 wire protected content and governed audit ports; S2.3 implement the accepted case/submission/evidence route subset; S2.4 connect a minimal React intake view and durable reads. | A signed-in USER creates a case, preserves synthetic text bytes and sees finalized evidence metadata after restart (§5). Identical retry does not duplicate the effect; changed retry conflicts; unauthorized access follows 401/403/masked 404 rules. FINALIZED does not imply evaluated. |
| S3 — Governed schema, loader and knowledge activation seam / S | S2; T07 for operator interaction; trusted publication/key profile | S3.1 reuse bundle schema/build/loader rather than replace them; S3.2 bind exact published-bundle references and validation into application startup/evaluation readiness; S3.3 implement the accepted activation/history capability needed by analysis, with exact digest and audit; S3.4 demonstrate invalid/withdrawn bundle rejection. | Application reasoning consumes an exact eligible, verified immutable bundle; bad digest/schema/version or effective active withdrawal prevents new governed evaluations. Existing evaluations retain their original pins. A development seed is explicitly provisioned through accepted governance, never an unchecked SQL pointer or "latest" substitution. |
| S4 — Deterministic raw-input extraction / L | S3; UX-002 upload clarifications/media limits; KB-002 extraction contracts | S4.1 derive immutable envelopes from finalized original bytes; S4.2 implement deterministic normalization/observation extraction and mappings; S4.3 preserve actor/action/target, negation/reported speech and payment direction; S4.4 validate governed inputs and support state before kernel invocation. | Synthetic English text yields traceable, valid observations from uploaded bytes; benign and adversarial examples obey extraction contracts. Unsupported/unknown language or unavailable extraction is explicit and never benign by default. Fixtures may test extraction but cannot replace it in the live path. |
| S5 — Scoring, explanation and persistent result / M | S4; exact active-bundle identity; fenced persistence protocol; UX-003 clarifications | S5.1 implement `createEvaluations` and status polling; S5.2 persist one immutable governed artifact per evaluation; S5.3 call the existing kernel in-process and atomically complete under its execution fence; S5.4 render authorized `getDetectionResult` views. | A browser-submitted synthetic text reaches the real kernel and produces a persisted result with exact engine/bundle/input pins, categorical risk separate from confidence, explanation and governed actions. Repeat/replay material is deterministic; stale workers cannot commit a result after failure. NO_SCAM_PATTERN never becomes "safe". This is the first runnable analysis journey. |
| S6 — Evidence, case history and report reservation / L | S5; T06 before report implementation planning; T10 for dependent live-data policy; UX-005/OPS-001 | S6.1 implement authorized evidence download and history; S6.2 implement accepted correction/re-analysis/replay and source-pinned material handling; S6.3 implement governed deletion states and tombstones only under an approved policy. Report tasks are HOLD until REPORT-001 exists; then propose an amendment to PLAN-001 with its implementation tasks and criteria. | History is retained; correction creates a new evaluation, replay never substitutes current material, and missing/deleted material yields explicit accepted unavailable/410 outcomes. A deletion request never claims completion before COMPLETE. No report format, generated report or report-slice readiness is claimed by this reservation. |
| S7 — URL intelligence adapters / M | S5/S6; T09; approved provider policy and protected credential references for live use | S7.1 implement the INT-001 adapter/egress boundary; S7.2 validate and persist normalized advisory outcomes; S7.3 expose only accepted analyst enrichment reads; S7.4 test policy rejection, provider outage and invalid response offline before any live adapter. | No connection to submitted URLs, DNS-rebinding bypass or user-supplied destination. Advisory lookup leaves DetectionResult unchanged; CLEAN/NOT_FOUND/UNAVAILABLE never assert safety. Provider selection/credentials remain OPEN until supplied; offline adapter evidence is not live-provider success. |
| S8 — Screenshot / OCR extension / L | S4–S7; accepted media profile; least-privilege worker and resource controls | S8.1 implement bounded malicious-upload isolation; S8.2 preserve original image and separately identified OCR derivative/envelope; S8.3 carry uncertain extraction and support state; S8.4 connect accepted intake/error behavior without adding unsupported capabilities. | Synthetic screenshot bytes remain digest-verifiable; OCR derivatives keep source lineage and a new input identity. Malformed/oversized content is safely refused; unavailable OCR is explicit. No QR execution, URL retrieval or unverified multilingual capability is introduced. |
| S9 — Full authz, analyst/admin and knowledge workflows / L | S2 security baseline; S5/S6; T07; UX-004 clarifications | S9.1 complete accepted review queue/assignment and grant lifecycle; S9.2 implement adjudication and C4 rationale policy; S9.3 implement administrator break-glass with expiry and independent review; S9.4 finish operator activation/rollback/withdrawal interaction and content-free audit reads. | Analyst assignment uses valid item/ETag/target references and forbids self-assignment. Administrator role alone cannot read evidence or reports. Adjudication never rewrites DetectionResult; revoked access takes effect per request. Knowledge editing/approval retains Git/CI authority and separation of duties. |
| S10 — Optional AI behind flags / M | S5; programme decision on analysis-mode UI; provider policy only for live use | S10.1 integrate the already-governed Phase-4 seam behind a default-OFF policy; S10.2 persist sealed provenance and exact replay material; S10.3 verify containment/strict validation; S10.4 exercise exact deterministic fallback with the fake provider. | OFF behavior equals S5. Governed optional provider failures retain the exact deterministic baseline; malformed output is rejected, and authoritative kernel failures remain failures. No AI rule publication or second decision path. A fake-provider test is not a deployed model or evidence of accuracy. |
| S11 — Analytics boundary, hardening and release evidence / L | S1–S10 scope accounted for; T09/T10 and deployment decisions for affected release | S11.1 implement accepted operational health, bounded resource controls and safe telemetry; S11.2 exercise idempotency/ETag races and required-dependency failure; S11.3 implement authorized cross-store backup/restore verification and tombstone anti-resurrection; S11.4 assemble the Phase 10 test handoff and release evidence. | Operators see content-free dependency state; optional AI loss does not disable deterministic readiness. Restore verifies integrity before promotion and cannot resurrect governed removal. No analytics API currently exists: any requested product analytics interface needs a governed capability decision before implementation. Operational counts are not accuracy metrics or production-readiness evidence. |

The nominal implementation order is S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 → S10 → S11, preserving
the roadmap. Earlier slices implement the security, audit, persistence and failure controls required for their own
exposed operations; S9/S11 complete those capabilities rather than retroactively secure an unsafe skeleton.
Optional features remain disabled until ready. A provider, OCR, report or other unresolved dependency is reported
BLOCKED for that scope; no slice is silently declared complete or reordered. Any proposed scope deferral/reordering
must be an explicit approved PLAN-001 change.

## 5. First runnable end-to-end walking skeleton

S2 proves the real browser → HTTP application → PostgreSQL + protected content store + governed audit path.
It is a persistent evidence journey; S5 subsequently adds raw-text-to-decision behavior. No direct browser database
access, fake result, client-supplied governed artifact or invented test-evaluation endpoint is permitted.

1. After T02–T05/T09 are resolved, provision the approved local profile with synthetic users and protected key/IdP
   references outside Git. Apply reviewed Alembic migrations explicitly; application startup does not migrate.
2. Start frontend and Python backend using the S1 documented commands. Internal `/health/live` and `/health/ready`
   follow accepted probe semantics and stay off public ingress. Required dependency failure refuses affected work.
3. Sign in through the approved external OIDC browser profile; `getMe` confirms trusted server-side access. Never
   accept a role, owner or identity from request data.
4. Call `createCase`, then `createSubmission` for supported synthetic text, using the exact accepted request schemas.
   The server owns case identity and owner assignment. Free-text evidence is not inserted into submission JSON.
5. Call `createEvidenceUpload`, `putEvidenceContent`, then `finalizeEvidence`. Send original UTF-8 bytes through the
   binary boundary using the governed media/size profile; compute the authoritative SHA-256 server-side, persist
   encrypted bytes and verify durable content before claiming FINALIZED. Preserve original bytes under normalization.
6. Reload via `getCase`, `listSubmissions`, `getSubmission`, `listEvidence` and `getEvidenceMetadata` as needed.
   Stop at preserved evidence in S2; an unavailable analysis action must not imply completion. In S5, call the existing
   `createEvaluations` operation, poll `getEvaluation` and read the authorized `getDetectionResult`.
7. Restart the application and database development profile, then demonstrate the same resource identities and
   digest-verified bytes. This requires real persistence; a mocked response or process-local dictionary cannot pass.
8. Exercise unauthorized/masked reads, same-key retry, changed-request conflict, changed-byte re-PUT rejection and
   a required dependency outage. Check audit requirements and verify that raw text, locators, secrets and bearer
   tokens do not appear in logs or error messages.

Do not expose a protected operation before its authorization, content permission, audit and idempotency requirements
are implemented. Use the complete accepted constraints for the table families needed by the slice, including their
dependencies; a partial schema is not permission to omit an invariant. The demo records synthetic data and its
limits and cannot establish accuracy, WCAG conformance, security certification or production readiness.

## 6. Four operator workflows with no detailed Phase 7 UX

P7C-01 remains OPEN. An authenticated operator CLI is a **candidate scope proposal**, not an accepted Phase 7 design
or an implemented console. Product / Knowledge governance / Operations must approve detailed interactions under T07.
It can use the existing API; it may not mint extra roles, credentials, command routes or access to case content.

| Accepted operation | Existing role | Proposed scheduling and necessary interaction evidence |
| --- | --- | --- |
| `activateKnowledgeBundle` | ADMINISTRATOR | Minimum capability in S3, complete operator interaction in S9. Select an exact eligible published digest, obtain required precondition, confirm scope, show accepted pending/result state and audit; reject invalid/withdrawn material. |
| `rollbackKnowledgeBundle` | ADMINISTRATOR | S9. Select an exact previously validated digest with required preconditions; communicate rollback without rewriting historical evaluation pins or claiming latest-material substitution. |
| `withdrawKnowledgeBundle` | KNOWLEDGE_APPROVER | S9. Bind exact digest, reason and governance authority; show effective active withdrawal and remediation consequences. Withdrawal never deletes audit/history or silently chooses a replacement. |
| `getOperationalHealth` | ADMINISTRATOR | S11. Show content-free accepted operational status and dependency failures; distinguish optional degradation from required failure. No raw provider body, evidence locator, secret or invented provider freshness field. |

The five foundation-only surfaces (`closeCase`, `reopenCase`, `getActiveKnowledge`, `getKnowledgeBundle`,
`listKnowledgeActivations`) likewise need slice-level interaction details where used; foundation placement is not a
detailed implemented workflow. P7C-02's historic WP1 status-row gap stays with programme governance; do not edit
hash-pinned UX-001 to make it appear closed retroactively.

## 7. Traceable decision scheduling

The source register is linked in §1; this table routes all 38 CARRIED decisions without duplicating their normative
text or changing their source owners. The three responsive decisions UX-003#6, UX-004#8 and UX-005#7 remain
SUPERSEDED_BY UX-006#1, owned by the Phase 9 design system with Product / Accessibility UX.

| Carried source IDs | Scheduled task / slice | Required treatment |
| --- | --- | --- |
| UX-001#0 | T05, before S2 browser work | Resolve session/CSRF first; accepted OIDC boundary remains. |
| UX-002#5, UX-002#8 | T08/T09, S2 | Clarify abandoned upload cleanup and interrupted PUT/finalize readiness; no invented status field, automatic cleanup period or finalization without observed successful PUT. |
| UX-002#7 | T08, S2/S4 | Keep user context under accepted OTHER + governed media type unless a data vocabulary revision is approved. |
| UX-003#0, UX-003#1, UX-003#2 | T08, S5 | API owner decides missing negative/mitigating identities, observations/spans and action reason IDs; do not reconstruct absent API fields in the UI. Accepted reduced presentation can proceed. |
| UX-003#3 | T08, S5 | Confirm serialized explanation evidence_basis rendering before presentation implementation. |
| UX-004#0, UX-004#1, UX-004#2 | T08, S9 | Respect absent admin queue/directory/evidence-list/grant-review listing capabilities; use only existing accepted channels and audit references until a governed revision. |
| UX-004#3, UX-005#4 | T08, S6/S9 | Define reason-code vocabularies through their API owner; no ad hoc command vocabulary becomes normative. |
| UX-004#4 | T08, S9 | Principals stay opaque identifiers; no guessed display names or invented directory API. |
| UX-004#5 | T08, S9 | Security/API owner confirms C4 rationale authoring versus content read permission before that path is enabled. |
| UX-005#0 | T06, report reservation in S6 | Produce REPORT-001 before report implementation planning; opaque bytes are not a format definition. |
| UX-005#1, UX-005#2 | T08, S6 | Historical records stay separate and user data export remains unavailable under current capabilities; any expansion needs an approved API revision. |
| UX-006#0, UX-006#2, UX-006#3 | T08, S7 | Keep provider attribution/outcome distinctions/freshness within EnrichmentView; no extra fields or inferred NOT_FOUND/UNAVAILABLE distinction. |
| UX-002#0, UX-002#2, UX-002#6 | T09, S2/S4 | Phase 9 configuration defines discoverability of media/size limits, email media support and polling/backoff; no invented discovery endpoint. |
| UX-002#4 | T05/T09, S2 | Security owns local draft persistence; default to no sensitive browser persistence until decided. |
| UX-003#5, UX-004#7, UX-005#6, UX-006#5 | S2/S5/S6/S9, Product / UX | Final copy, interface language and translation review remain Phase 9 work; detection scope is independently English-only. |
| UX-004#6 | T09, S9 | Break-glass duration remains server-set; use expires_at, with a bounded profile before implementation. |
| UX-006#1 | S2/S5/S6/S9, design system / Accessibility UX | Define breakpoint values and detailed layouts in Phase 9; retain permission, control and redaction parity across layouts. |
| UX-002#1 | T10, Sponsor + legal/governance with API owner | Consent/acknowledgment capture has no accepted API field; do not persist a fabricated field. |
| UX-003#4 | S10, Programme with AI governance | Decide whether analysis_mode is offered; default-OFF policy does not imply a user-facing AI choice is approved. |
| UX-003#7 | S5, Detection owner / Phase-3 governance | Clarify the historic MATCHED-helper issue; result presentation follows aggregation eligibility and never promotes a SUPPRESSION-kind rule into a finding. No engine semantic change is authorized by this plan. |
| UX-005#3 | S6, Programme UX governance | Correction placement is carried pending a governed UX-001 revision; current accepted API behavior is preserved. |
| UX-005#5 | T10, S6/S11 | OI-05 retention/tombstone metadata stays a programme/legal decision; no duration is invented. |
| UX-006#4 | S4/S8/S10, Sponsor with Knowledge governance | Non-English detection requires verified evidence and ADR-0014 governance; untranslated or unsupported input is not benign. |
| UX-006#6 | Phase 10 / QA Lead | Accessibility conformance testing with assistive technologies and evidence; no WCAG conformance claim before that work. |

G-09 remains OPEN with Phase 10 / QA and the Sponsor for corpus access. OI-05, ASM-002 and
P6-WP7-LOW-1 retain their existing owned statuses; the latter is a future governed Phase-6 snapshot revision, not an
excuse to modify the frozen 19-artifact snapshot during implementation planning.

## 8. Definition of Ready and Definition of Done

**Definition of Ready — per slice.**

- PLAN-001 scope has independent approval, formal Phase 7 entry is complete, and the slice's dependencies are
  demonstrably available. All blocking tasks in §3 and relevant source decisions in §7 have an owned disposition.
- Docker and PostgreSQL are installed and functionally verified before Phase 9; ASM-002 is resolved before any
  schema-creating migration; browser session/CSRF is decided before browser code; REPORT-001 is defined before
  report implementation planning. These prerequisites are not waived by a successful static validator.
- Enumerate exact API operations, request/response schemas, authorization/content checks, errors, state transitions,
  audit events, idempotency/preconditions and sensitive-data handling for the slice. Missing capability is recorded
  explicitly rather than guessed.
- The relevant runtime/profile values and dependencies are pinned, secret references can be provided outside Git,
  and migration compatibility/recovery is documented. No production resource or credential is assumed present.
- A concrete synthetic demonstration and meaningful acceptance tests are identified, including a denial and a
  dependency/failure path. No unresolved blocker is disguised as a Definition of Done exception.

**Definition of Done — per implemented slice in Phase 9.**

- The documented clean-clone startup/build and the slice demonstration actually execute on the selected profile.
  Frontend/backend/persistence use real implementations for the promised outcome; mocks are limited to explicitly
  simulated external dependencies.
- Approved API/data/UX contracts are implemented without added fields/roles or client-side authority. Real feature
  tests prove behavior, including authorization, restart/durability, idempotency/preconditions, races and safe
  failure where applicable; migration tests run against PostgreSQL rather than a substituted database.
- The canonical offline gate remains green, appropriate application checks and CI pass, required review findings
  are closed, and existing accepted artifacts remain intact unless a separate governed revision authorizes change.
- Provenance, immutable bytes/digests, fencing, governed audit, privacy and accessibility design behaviors hold for
  exposed paths. Secrets and synthetic sensitive content are absent from logs, error payloads and committed files.
- Installation, startup, recovery and evidence are reproducible; omitted optional capabilities and remaining owned
  gaps are visible. The slice leaves main usable for its accepted scope after the user completes Git operations.
- Phase 10 evidence requirements are handed off. A Phase 9 feature test is not a claim of full WCAG compliance,
  penetration testing, production readiness, legal admissibility or real-world detection effectiveness.

## 9. Milestones, phase responsibilities and release criteria

| Milestone | Observable outcome | Exit evidence |
| --- | --- | --- |
| M0 — Ready to implement | Approved PLAN-001, finalized Phase 7 entry, confirmed infrastructure/tenancy/profile decisions | T01–T05 resolved for the first browser slice; T09 bounded values; actual environment evidence. Currently NOT MET. |
| M1 — Runnable evidence app (S2) | Authenticated browser preserves synthetic text through real API, PostgreSQL, content store and audit | §5 demo, restart/digest verification, denial and retry tests; no detection-completion claim. |
| M2 — Runnable text analysis (S5) | Raw English synthetic submission → deterministic extraction → existing in-process kernel → authorized persisted explanation | Exact provenance, support-first refusal, benign/adversarial regression, durable result and fence-race checks. |
| M3 — Governed case workflows (S6/S9) | Source-pinned history/replay and authorized analyst/admin workflows; reports only after their definition | REPORT-001 planning prerequisite met for report scope; permission, break-glass, deletion-policy and unavailable-material evidence. Optional S7/S8 remain subject to the explicit sequencing/scope rule in §4. |
| M4 — Testing handoff (S11) | Accepted application scope is reproducible with an honest limitations register | Feature/contract/E2E results, migrations/recovery evidence, security/accessibility design checks, Phase 10 test inventory and deployment-specific decisions. No production-ready label. |

**Phase 8 owns planning and prerequisite decisions.** Approve the candidate scope, resolve/schedule its gates and
produce REPORT-001 before detailing the report build. It does not create runtime services or certify infrastructure.

**Phase 9 owns implementation and continuous feature verification.** Build each demonstrable increment, implement
the browser/security/data boundaries from the first protected operation, preserve the proven engine and add tests
with the features. Tests are not postponed until Phase 10.

**Phase 10 owns TEST-001 and integrated verification/evaluation evidence.** Exercise complete journeys, accessibility
with automated and manual assistive-technology testing, security, failure/recovery, deployment and evaluation
limitations. QA must record scope and actual results. Precision, recall, calibration and false-positive rates remain
unclaimed without an authorized real labelled corpus; synthetic regression proves consistency within its scope.

A release of an agreed application scope requires its slice DoD, successful relevant CI, reviewed migrations,
identity/key/provider/deployment configuration supplied through approved channels, and explicit treatment of
remaining blockers. A public/production release additionally requires the Phase 10 and operations/readiness
evidence applicable to that environment; M1/M2 are development milestones, not authorization to expose a service.
No rollout, installation, deployment or application test result is claimed complete by blueprint approval.

## 10. Independent approval and next work

The user reports an independent Codex review of PLAN-001 with decision APPROVE and
BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 0 / INFO 0. This approval is recorded from the user-supplied review decision;
no external review artifact or signature is invented. The reviewer confirmed 11 roadmap-ordered slices, valid
links (22/22), all carried decisions accounted for exactly once (38/38), authenticated persistent walking-skeleton
requirements, Docker/PostgreSQL and browser security prerequisites, REPORT-001 and operator UX scope decisions,
and passing existing checks and git diff check. Earlier approved phases are not re-reviewed.

PLAN-001 is APPROVED FOLLOWING INDEPENDENT REVIEW. Phase 8 itself remains NOT CLOSED; no Phase 9 implementation
has begun. No new gate, schema, fixture corpus or validator is introduced for this approval. T01 is MET; all other
owned prerequisites and scope reservations remain unchanged.

Next: obtain the T02/T04 sponsor evidence and T05 security decision; settle T03/T09 for the first runnable scope;
define REPORT-001 through T06 before report build planning; and resolve the candidate operator scope T07. Amend
unresolved reservations through the existing review process before their dependent implementation.
The builder performs no stage/commit/push/PR/merge operation; the user owns all Git transitions.
