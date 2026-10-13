# T05 — Browser session and CSRF profile (S2 local implementation)

| Field | Value |
| --- | --- |
| Resolves | PLAN-001 T05 / UX-001#0 for the S2 local, single-tenant (DEC-009) profile |
| Status | Implemented in `apps/backend` and `apps/frontend`; awaiting independent security review |
| Preserves | ADR-0009 (external OIDC, TrustLens-owned roles), API-001 `getMe`, DATA-001-WP2 principal/role tables |

**Pattern.** Backend-for-frontend. The browser holds only an opaque, server-side session cookie. ID, access and refresh
tokens and the client secret never leave the backend process and are never placed in a URL, log, API response or
browser storage.

| Choice | Value |
| --- | --- |
| Origins | Application `http://127.0.0.1:5173` (Vite dev server; proxies `/api` and `/auth` to the backend). Backend `http://127.0.0.1:8000`. Keycloak `http://127.0.0.1:8081/realms/trustlens-local`. `localhost` is rejected by configuration. |
| Flow | Authorization Code + PKCE S256 (64-character verifier); `state` and `nonce` are 256-bit CSPRNG values; confidential client with `client_secret_basic`; `scope=openid`. |
| Callback | `http://127.0.0.1:8000/auth/callback` (registered). State is single-use, expires after 5 minutes and is bound to the starting browser by an HttpOnly `tl_oidc_tx` cookie (path `/auth`). RFC 9207 `iss` is required and must match. Parameters are bounded, and duplicates are rejected. |
| ID token | PyJWT verifies the signature against the provider JWKS with an asymmetric-algorithm allowlist (no `none` or HMAC), plus issuer, audience, `exp`/`nbf`/`iat` (30 s leeway), `azp` when present and a constant-time nonce comparison. Discovery endpoints must stay on the issuer's origin. |
| Authorization | A TrustLens principal and an active role must already exist (explicit provisioning). Sign-in never creates either. Roles are re-read from PostgreSQL on every protected request. An unprovisioned identity is redirected with `?signin=denied` and gets no session. |
| Session | Opaque 256-bit identifier; only its SHA-256 is kept server-side. Rotated on every successful sign-in, and any presented earlier session is invalidated, including after a failed or denied sign-in. Idle limit 30 minutes; absolute limit 8 hours; capacity bounded. Held in memory because DATA-001-WP2 defines no session table, so a restart ends all sessions (fail closed). Run a single backend process. |
| Cookie | `tl_session`: HttpOnly, SameSite=Lax, Path=/, host-only (no Domain), session-lifetime. Under HTTPS it becomes `__Host-tl_session` with Secure. Plain HTTP is accepted only when every URL is `127.0.0.1`. |
| CSRF | Every POST/PUT/PATCH/DELETE needs `Origin` exactly equal to the application origin (and `Sec-Fetch-Site` same-origin when sent). Anything on `/api/*`, and `/auth/logout`, also needs `X-CSRF-Token` to match the session's synchronizer token (from `GET /auth/csrf`). No CORS is configured. |
| Logout | `POST /auth/logout` invalidates the local session and clears the cookie. It then ends the Keycloak session back-channel (refresh token, server-side, 5 s bound). If the provider call fails, the local session is still ended and the response says `provider_session: NOT_CONFIRMED`. |
| Fail closed | Missing or unsafe OIDC or database configuration disables sign-in: `/auth/login` returns 503 and `getMe` returns 503 `DEPENDENCY_UNAVAILABLE`. There is no development bypass. |

`/auth/login`, `/auth/callback`, `/auth/csrf` and `/auth/logout` are authentication-boundary integration routes, not
API v1 operations. API v1 bearer-token access for non-browser clients (API-001 §3) is not implemented in S2.

**Audit.** Migration `0002_audit_chain` implements the contract's `audit_chain_head` / `audit_event`:
- **Hashing:** hash-chained per DATA-001-WP2 §15, with event schema version `1`; `event_without_hash` is every column except `event_hash`, UUIDs as text and instants as RFC 3339 UTC in microseconds.
- **Chain:** a single deployment chain with a genesis head.
- **Database guards:** triggers keep events append-only, and the head can only advance to the event just appended.
- **Events recorded:**
  - `AUTHENTICATION_SUCCEEDED`: the session is issued only after the event commits, so sign-in fails closed.
  - `AUTHENTICATION_FAILED`, with a categorical reason.
  - `AUTHORIZATION_DENIED`: for an unprovisioned identity (no identity data), a revoked principal, and untrusted-Origin or CSRF rejections.
  - `ROLE_ASSIGNED` / `ROLE_REVOKED`: in the same transaction as the role change.
- **Metadata:** only opaque IDs and allowlisted categorical values; never subjects, issuers, tokens, codes or browser details.
- **Verification:** `make audit-verify` recomputes the whole chain.
- **Not audited:** sign-out, because there is no governed event type for it.

**Not covered here:**
- a durable or shared session store (needs a governed DATA-001-WP2 revision);
- rate limiting (NFR-016). Without it, unauthenticated callers can append unlimited `AUTHENTICATION_FAILED` and
  `AUTHORIZATION_DENIED` events (audit flooding);
- signed audit checkpoints (`audit_checkpoint` tables; ARCH-005 §7.2). The chain is tamper-evident only against
  row-level edits, not against wholesale replacement;
- production TLS and deployment;
- the remaining T09 parameters (upload, media, case persistence, idempotency, workers).
