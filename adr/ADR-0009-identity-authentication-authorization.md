# ADR-0009 — Identity, authentication and authorisation

| Field | Value |
|---|---|
| Status | **Accepted** — following independent P5-WP4 review (BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 4 / INFO 2; APPROVE) |
| Date | 2026-09-06 |
| Owner role | Chief Architect / Principal Security Engineer |
| Phase | Phase 5 — P5-WP4 security architecture |
| Related | `MP §3, §16, §20, §21`, [PROGRAM-001](../docs/00-program/PROGRAM-001-program-charter.md) (CON-003, NG-07/08, FR-054/060/061/062/063/065/070…077, NFR-006/007/010/016), [SRS-001](../docs/00-program/SRS-001-software-requirements-specification.md) (REQ-43/54/55/56/57/38/59…66, NFR-10/11/13/14/16), [ARCH-001](../docs/05-architecture/ARCH-001-enterprise-architecture.md) (`INV-01`…`INV-15`, ZONE 0–5), [ARCH-002](../docs/05-architecture/ARCH-002-python-runtime-service-topology.md), [ARCH-003](../docs/05-architecture/ARCH-003-persistence-evidence-tamper-architecture.md), [ARCH-004](../docs/05-architecture/ARCH-004-security-trust-threat-model.md), [ADR-0004](ADR-0004-knowledge-storage-architecture.md), [ADR-0007](ADR-0007-ai-authority-and-model-strategy.md), [ADR-0008](ADR-0008-python-runtime-service-topology.md), [ADR-0010](ADR-0010-evidence-storage-tamper-evidence.md), [risk-register](../docs/00-program/risk-register.md) RSK-008/010/011/012/017/018, G-09 (RSK-003) |

## Context and constraints

TrustLens receives attacker-controlled scam evidence, produces an authoritative deterministic `DetectionResult`,
and preserves sensitive evidence, audit and replay provenance. Phase 5 selected a Python modular-monolith backend
(ADR-0008) with an in-process Phase-3 kernel and a persistence/evidence architecture (ADR-0010) whose
protected content and append-only audit require an actor model. ARCH-001 §12 defers the identity mechanism to
this ADR (ZONE 1) and requires authenticate-before-protected-operation with per-operation and per-resource
authorisation. No identity, authentication, or authorisation mechanism has been chosen yet.

The requirements are explicit: authenticate users (FR-060/REQ-54); enforce RBAC across the reporting user,
analyst, knowledge editor, knowledge approver and administrator roles (FR-061/REQ-55); the administrator role must
operate the platform **without** access to submitted content (NFR-14, DERIVED from FR-061); write immutable audit
of security- and knowledge-relevant actions (FR-062/REQ-56; NFR-010/NFR-13); support analyst adjudication
with recorded rationale and override audit (FR-063/REQ-38); export reports through an authenticated,
access-controlled channel that never auto-transmits to an authority (FR-054/REQ-43, NG-01); support data
export/deletion with audit evidence (FR-065/REQ-57); rate-limit and protect public endpoints (NFR-016/REQ-70);
and encrypt in transit with TLS 1.3 (NFR-006). Submitted content is attacker-authored (RSK-008/010/017) and the
rule engine is the sole decision authority (CON-003, NG-07). G-09 (RSK-003) remains OPEN.

This ADR fixes **who the actor is, how they are authenticated, and how each TrustLens operation and resource is
authorised** — deliberately as architecture, before any authentication code, IdP, login page, middleware, token
library, or secret/key material exists. The full trust-zone/STRIDE model, secrets, encryption-key and
audit-signing trust, and controlled egress are elaborated in the companion **ARCH-004**.

## Security requirements traced

| Requirement | This ADR's response |
|---|---|
| FR-060 authenticate users | Standards-based external/pluggable OIDC/OAuth 2.0 authentication boundary; TrustLens never stores passwords. |
| FR-061 RBAC (5 roles) | TrustLens-owned role model: `USER`, `ANALYST`, `KNOWLEDGE_EDITOR`, `KNOWLEDGE_APPROVER`, `ADMINISTRATOR`. |
| NFR-14 admin without content | Platform administration is separated from case/evidence content access; admin role grants no implicit evidence read. |
| FR-062 / NFR-010 immutable audit | Every authentication, authorisation-denial, privilege, governance and evidence-access decision is an auditable security event (ADR-0010 append-only chain). |
| FR-063 analyst adjudication + override audit | Analyst adjudication and override are authorised operations with mandatory recorded rationale and actor provenance. |
| FR-054 secure report export | Export is an application-authorised, access-controlled operation over the case authorisation graph; a storage locator/URL is never export authority. |
| FR-065 export/deletion with audit | Data export/deletion are privileged, resource-scoped, audited operations subject to owner/authorisation checks. |
| FR-072…077 bounded AI | AI remains non-authoritative (CON-003); no identity/authorisation token is ever exposed to an AI provider; the provider receives no application authority (ADR-0007). |
| NFR-016 rate limiting / abuse | Authentication and public operations are subject to abuse protection; exact thresholds deferred. |
| NFR-006 TLS 1.3 | All identity/token exchange occurs over TLS 1.3; no bearer material in logs (NFR-007). |
| CON-003 / NG-07 | No identity, role, or provider claim can set, override, or bypass a Phase-3 decision field. |

## Decision

**TrustLens adopts standards-based external/pluggable identity (OIDC / OAuth 2.0) for human authentication and
retains TrustLens-owned application authorisation (role- and resource-level) as a distinct, server-side,
deny-by-default responsibility. TrustLens does not implement its own password credential store, and no IdP
vendor is selected.**

1. **Pluggable OIDC/OAuth 2.0 identity boundary.** Human authentication is delegated to a standards-based,
   configurable external identity provider. Interactive user clients use the **Authorization Code flow with
   PKCE**. TrustLens **must not** implement its own username/password credential store, password hashing, or
   account-recovery flow. No specific IdP product is chosen; Keycloak, Auth0, Okta, Entra ID and Cognito are
   **non-selected examples** only.
2. **Authentication ≠ authorisation.** The IdP authenticates the human and issues identity/session/token claims
   (and MFA where policy requires). **TrustLens** decides which TrustLens role(s) apply, which operation is
   permitted, and which case/evidence/result/report the actor may access. **IdP claims alone never directly grant
   TrustLens resource access.**
3. **TrustLens-owned role model.** Exactly five first-class roles — `USER`, `ANALYST`, `KNOWLEDGE_EDITOR`,
   `KNOWLEDGE_APPROVER`, `ADMINISTRATOR` — are defined and not silently merged. Role assignment is trusted
   server-side application state, provisioned through governed administration, not read from a client request.
4. **Deny by default + resource-level authorisation.** RBAC alone is insufficient. Every protected action
   requires an explicit allow, evaluated server-side over **both** the actor's role **and** the specific resource
   (case, evidence, result, report, governed-knowledge resource). Absence of an explicit grant is denial.
5. **Separation of duties.** A single actor must not satisfy both the authoring and the required-approval step of
   the same governed knowledge change merely because multiple roles are assigned. `KNOWLEDGE_EDITOR` drafts;
   `KNOWLEDGE_APPROVER` approves; the same human cannot self-approve their own change. The existing ADR-0004
   Git/CI knowledge governance remains authoritative and is not redesigned.
6. **Administrator ≠ evidence reader (NFR-14).** Platform administration (identity, roles, configuration,
   operations) is separated from case/evidence content access. The administrator role confers **no** implicit
   raw-evidence read. Emergency content access uses a **break-glass** concept — explicit reason, short-lived
   elevation, strong audit, attributable actor, mandatory post-event review — which is **defined but not
   implemented** here.
7. **Service / workload identities.** Non-human components (backend, future evidence/OCR/AI-egress workers,
   knowledge-publication process, audit-checkpoint signer) receive distinct workload identities under least
   privilege. Service identities **must not** reuse human credentials; short-lived workload credentials are
   preferred where the deployment environment supports them. Exact workload-identity technology is P5-WP5.
8. **No client-authorised security.** Client-supplied role, `owner_id`, analyst-assignment, or admin flag is
   never trusted. Authorisation context derives from a validated server-side identity and trusted application
   state only.
9. **Session/token principles.** Tokens are accepted only after issuer, audience, signature and expiry/not-before
   validation; unsigned/invalid tokens are rejected; access tokens are short-lived; authorisation is always
   re-evaluated server-side so role/resource changes take effect without depending on indefinitely valid tokens.
   No bearer token appears in logs. Token/identity **signing** is owned by the identity system, not the TrustLens
   application (distinct from the data-encryption and audit-signing key purposes in ARCH-004 §7).
10. **MFA-capable, not MFA-mandating.** The architecture supports MFA (delegated to the IdP) and **recommends**
    stronger authentication policy for privileged roles (`KNOWLEDGE_APPROVER`, `ADMINISTRATOR`, break-glass). It
    invents no universal MFA mandate beyond existing requirements; exact assurance level is configurable/deferred.
11. **AI carries no identity authority.** No user token, session, role, or authorisation context is ever passed to
    an AI provider or used to expand AI scope; the AI boundary (ADR-0007, ARCH-004 §8) stays outside the decision
    and identity trust zones.

## Authentication architecture

```text
human user
  -> interactive client (future UI / API client)     [ZONE 0 untrusted]
  -> Authorization Code + PKCE redirect                [ZONE 1 auth boundary]
  -> external OIDC/OAuth 2.0 identity provider (pluggable; not selected)
  -> ID/access token with validated issuer/audience/signature/expiry
  -> TrustLens token validation + session establishment
  -> authenticated principal (subject claim) mapped to TrustLens actor
```

- TrustLens validates every token (issuer, audience, signature via IdP-published keys, expiry/not-before) before
  establishing a session; it does not accept a self-asserted identity.
- The IdP owns credential lifecycle, MFA, and account recovery. TrustLens owns the mapping from an authenticated
  subject to a TrustLens actor and that actor's role/resource authorisation.
- Service/workload authentication is separate (workload identity, §"Service identities"), never a human login.
- All exchanges occur over TLS 1.3 (NFR-006); tokens are treated as secrets and never logged (NFR-007).

## Authorization architecture

Authorisation is a distinct, server-side, deny-by-default decision with two composed layers:

```text
protected request
  -> authenticated principal (from validated token/session)
  -> ROLE check      : does the actor hold a role permitting this operation type?
  -> RESOURCE check  : is the actor authorised for THIS case/evidence/result/report/knowledge resource?
  -> SoD / privilege / break-glass constraints
  -> explicit ALLOW  (otherwise DENY)  -> audited decision
```

- **Role authorisation** gates operation *types* (e.g. adjudicate, draft-knowledge, approve-knowledge,
  administer). **Resource authorisation** gates the *specific* object (ownership/assignment/scope).
- Both must pass. Neither a valid role without resource authorisation, nor resource ownership without a permitting
  role, is sufficient.
- Every allow/deny is an auditable event (FR-062, NFR-010); denials are logged with actor, operation, resource
  reference and reason category, never with raw evidence.
- Authorisation is re-evaluated per request from trusted state; a stale token does not extend revoked access.

## Human roles

| Role | May (conceptually) | Must not |
|---|---|---|
| `USER` | Create own cases/submissions; view own accessible results; view/download own reports; request correction; request data export/deletion | Read other users' cases; access unrelated raw evidence; adjudicate; edit/publish knowledge; administer security |
| `ANALYST` | Access cases assigned/authorised for review; inspect evidence required for that adjudication; inspect the deterministic decomposition; record adjudication/rationale (FR-063) | Publish rules; change security configuration; administer identities; browse all evidence without a legitimate case authorisation |
| `KNOWLEDGE_EDITOR` | Propose/draft governed knowledge changes under ADR-0004 | Approve their own change; publish without the required approval; administer security; read unrelated case evidence |
| `KNOWLEDGE_APPROVER` | Approve governed changes subject to existing governance | Author + approve the same change (SoD); bypass Git/CI governance; gain implicit evidence access |
| `ADMINISTRATOR` | Operate platform security/configuration, identity and role administration | Automatically read raw case/evidence content (NFR-14); adjudicate cases; self-grant evidence access without audited break-glass |

Multiple roles may be assigned only where the architecture can still enforce SoD and least privilege; assignment
never lets one actor satisfy mutually-exclusive duties on the same object. Exact per-endpoint permissions are
deferred to Phase 6.

## Service identities

| Workload identity | Least-privilege intent |
|---|---|
| TrustLens backend | Application/orchestration and authorised data access only |
| Background evidence worker | Scoped evidence-processing operations |
| Future OCR worker | Isolated, least-privilege media processing |
| Future AI-egress worker | Send only approved, sanitised, minimum-necessary extraction payloads to approved destinations; no case DB, rule, DetectionResult, user-admin, or arbitrary-query access |
| Knowledge publication process | Governed bundle publication only (ADR-0004) |
| Audit checkpoint signer | Protected signing operation only; cannot export raw signing private-key material (ARCH-004 §7) |

Service identities are non-human, never reuse human credentials, and use short-lived workload credentials where
supported. Persistence credentials are scoped to required operations. Exact workload-identity and SQL-role
technology is P5-WP5 / Phase 6.

## Resource authorization

- `USER` may read Case X only if the actor owns / is authorised for X.
- `ANALYST` may read Case X only if assigned / authorised for X.
- Report access follows the owning case/resource authorisation; a locator or presigned URL is never authority
  (FR-054, ADR-0010).
- Evidence access requires **case authorisation + evidence authorisation** and is application-mediated
  (ADR-0010 §16); direct client-to-store access is not authoritative.
- Knowledge roles operate on governed knowledge resources, not on case evidence.
- Deny by default: every protected action requires an explicit grant.

## Separation of duties

- Author vs. approver of a governed knowledge change are distinct required steps; the same actor cannot fulfil
  both for the same change, regardless of assigned roles (RSK-012).
- Analyst adjudication cannot silently become knowledge approval; role escalation is an explicit, audited,
  governed action.
- Administrator platform authority is separated from evidence content authority (NFR-14).
- The existing ADR-0004 Git/CI knowledge governance (peer/security review, PUBLISHED-only) remains the binding
  publication control; this ADR adds application-layer SoD, it does not replace ADR-0004.

## Privileged access

- Privileged operations (identity/role administration, security configuration, break-glass, key/secret
  administration, deletion/export approval) require the appropriate privileged role and are all audited.
- **Break-glass (defined, not implemented):** emergency evidence/content access requires an explicit reason,
  short-lived elevation, strong immutable audit, an attributable individual actor, and mandatory post-event
  review; elevation must expire automatically and never become standing privilege.
- Stronger authentication (MFA) is recommended for privileged roles.

## Session/token principles

Validate issuer, audience, signature and expiry/not-before; reject invalid/unsigned tokens; keep access tokens
short-lived; handle refresh/session safely; evaluate authorisation server-side per request; ensure role/resource
changes become effective without relying on indefinitely valid tokens; never place a bearer token in logs. No
exact token lifetime is invented; the requirement set does not mandate one.

## Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A — Standards-based external/pluggable OIDC identity + TrustLens-owned RBAC/resource authorisation (this ADR)** | No local credential store to breach; standards-based MFA/account-lifecycle at the IdP; enterprise-compatible; on-prem/offline-viable via pluggable IdP; full authorisation flexibility and resource-level control retained in TrustLens; no vendor lock (provider-neutral); strong security isolation of credentials from the application | Requires an external IdP to be configured and trusted; adds token-validation and role/resource-mapping work; IdP compromise is a modelled dependency (ARCH-004) | ✅ **Selected** |
| B — TrustLens-native username/password authentication | No external dependency; fully self-contained | TrustLens owns credential-breach, hashing, reset, MFA and lockout risk; higher implementation complexity and account-lifecycle burden; weaker enterprise SSO fit; larger attack surface | ❌ Rejected |
| C — IdP groups/roles directly determine all application authorisation | Less application authorisation code | Couples resource authorisation to IdP group hygiene; loses resource-level and SoD control; an IdP misconfiguration becomes a TrustLens authorisation breach; violates NFR-14 admin/evidence separation and deny-by-default | ❌ Rejected |
| D — No authenticated user model / possession-link access | Trivial to start | No accountable actor; breaks FR-060/061/062/063/065 and auditability; possession-link is guessable/shareable and cannot enforce ownership or SoD | ❌ Rejected |

Comparison spanned credential risk, implementation complexity, account lifecycle, MFA readiness, enterprise
compatibility, offline/on-prem viability, authorisation flexibility, vendor lock-in, operational burden, security
isolation and reversal cost. No IdP vendor is claimed to be mandatory.

## Justification

Delegating authentication to a standards-based, pluggable OIDC provider removes the highest-density credential
risk (a local password store) from TrustLens while keeping the security-critical authorisation decision —
role **and** resource, deny-by-default, with SoD and admin/evidence separation — inside the application where it
can be governed, audited and reasoned about. Keeping authorisation TrustLens-owned (rejecting Option C) is what
preserves NFR-14, resource-level control and SoD when an external IdP is imperfect. Provider-neutrality mirrors
ADR-0007's stance for AI: the security-relevant boundary (authenticate externally, authorise internally, deny by
default) is fixed now; the specific IdP, secret store and key system are deferred to deployment work without
weakening the boundary. No efficacy is claimed (G-09 OPEN).

## Consequences

**Positive.**
- No TrustLens-owned password store; credential breach surface minimised (RSK-010).
- Standards-based MFA and account lifecycle available at the IdP; privileged roles can require stronger auth.
- Resource-level, deny-by-default authorisation with enforced SoD and admin/evidence separation (NFR-14, RSK-012).
- Provider-neutral: the IdP is swappable; no vendor lock-in.
- Every security/knowledge/evidence-access decision is auditable (FR-062, NFR-010).

**Trade-offs.**
- TrustLens depends on a correctly configured, trusted external IdP; IdP compromise is a modelled residual risk
  (ARCH-004 §11).
- Token validation, session handling and role/resource mapping are additional application responsibilities.
- Break-glass, service-identity technology, secret/key mechanisms and exact RBAC permissions are deferred to
  ARCH-004 / P5-WP5 / Phase 6 rather than resolved here.

## Risks

| Risk | Mitigation (this ADR / ARCH-004) |
|---|---|
| Stolen/forged token grants access (RSK-010) | issuer/audience/signature/expiry validation; short-lived tokens; server-side per-request authorisation; no token in logs |
| IdP-claims-as-authorisation overreach | authorisation is TrustLens-owned; IdP claims never directly grant resource access (rejecting Option C) |
| Administrator reads all evidence (NFR-14) | admin ≠ evidence reader; content access needs case+evidence authorisation or audited break-glass |
| Editor self-approves a rule (RSK-012) | enforced author≠approver SoD; ADR-0004 Git/CI governance remains authoritative |
| Cross-user case/evidence access (RSK-010) | resource-level authorisation over ownership/assignment; deny by default |
| Client-supplied privilege (role/owner/admin flag) | never trusted; authorisation derives from validated server-side identity/state only |
| Service identity over-privilege | least-privilege workload identities; no human-credential reuse; scoped persistence credentials |
| Break-glass becomes standing privilege | short-lived auto-expiring elevation, explicit reason, strong audit, mandatory post-event review |
| IdP compromise | modelled residual risk; least privilege, audit, and later monitoring/anomaly controls reduce blast radius (ARCH-004 §11) |
| AI provider receives identity/token | no identity/token/authorisation context is ever exposed to an AI provider (ADR-0007) |
| Efficacy overclaim while G-09 open | no accuracy/precision/recall or production-readiness claim made here |

## Reversal cost

**Medium.** The *authentication delegation* is cheap to revisit — swapping or adding an OIDC provider is a
configuration change precisely because the core is provider-neutral. What is expensive to reverse is the
**boundary**: authenticate externally, authorise internally, deny by default, role **and** resource, SoD, and
admin/evidence separation. Reversing that (e.g. letting IdP groups directly authorise resources, or letting the
administrator implicitly read evidence) would invalidate NFR-14, the SoD control (RSK-012), and resource-level
containment (RSK-010), and would force re-architecture of the authorisation layer, audit semantics and threat
model. The value is not lowered to make reversal cheap; the boundary is deliberately durable.

## Validation plan

This ADR is architecture; concrete enforcement is later implementation work. Design-level proof points:

- **ARCH-004** — trust zones, STRIDE across identity/session/authorisation/evidence/admin boundaries, secrets,
  encryption-key purposes, audit-signing trust, controlled egress and SSRF, residual risk and control matrix.
- **P5-WP5** — service/workload identity technology, secret/key placement, deployment isolation and resilience.
- **Phase 6** — exact API authorisation contracts, per-endpoint RBAC/resource policy, token lifetimes, refresh
  and rate-limit thresholds (NFR-016), and enforcement tests (authenticate-before-access, deny-by-default,
  cross-user denial, editor-cannot-self-approve, admin-cannot-read-evidence, break-glass expiry).
- **Independent review** — this ADR was **Accepted following independent P5-WP4 review** (APPROVE; BLOCKER 0 /
  HIGH 0 / MEDIUM 0 / LOW 4 / INFO 2, the LOW/INFO items recorded as follow-ups for P5-WP5 / Phase 6); no
  authentication code, IdP integration, middleware, token library, or secret/key material is created by this WP.
