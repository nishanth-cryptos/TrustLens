# TrustLens local application (S1 foundation + S2 authentication)

Run commands from the repository root. S2 adds real browser sign-in through the local Keycloak; see
[§ S2 authentication](#s2-authentication) and the [T05 profile](../docs/07-implementation/T05-browser-session-profile.md).
Python **3.12.12**, Node **26.0.0** and npm **11.12.1** are the selected profile. Runtime/test dependencies
are pinned in `backend/requirements.lock` and `frontend/package-lock.json`; the knowledge `.venv` and root
`requirements.txt` remain independent.

```sh
make backend-install frontend-install
make smoke
make database-check
```

Start these in separate terminals:

```sh
make backend-run     # http://127.0.0.1:8000 — single process, loopback only, proxy headers off (trustlens_backend.serve)
make frontend-run    # http://127.0.0.1:5173 — sign-in UI; proxies /api and /auth to the backend
```

```sh
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
```

The accepted probe response is HTTP 200 with categorical status: liveness reports `OK`, readiness reports
`NOT_READY` (sign-in alone does not make the service ready). Check the body, not HTTP success alone. No ingestion
or content storage is enabled; framework `/docs`, `/redoc` and `/openapi.json` are disabled. The frontend does
not proxy internal health endpoints or collect content. Both development servers bind to loopback.

## Database configuration and migrations

`make database-check` reads `~/.config/trustlens/postgres-dev.env` explicitly (or `make database-check
ENV_FILE=/absolute/path/outside/git.env`). Existing process variables take precedence. The file supplies
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`; the local defaults are `127.0.0.1:55432`, overridden by
`TRUSTLENS_DB_HOST` / `TRUSTLENS_DB_PORT`. No URL, password or server error detail is printed.
`backend/.env.example` is a credential-free template; never copy real credentials into tracked files.

The diagnostic executes only `SELECT 1`, with five-second connection/query limits. PostgreSQL 17.11 is
running in `trustlens-postgres-dev` on persistent volume `trustlens-pg-dev`. A disposable, randomly named SQL
schema/table and committed record survived a real container restart on 2026-10-13; that namespace was cleaned
and the existing object snapshot was unchanged. No TrustLens application schema migration was applied.
For psql diagnostics, use `docker exec trustlens-postgres-dev psql -U trustlens_dev -d trustlens_dev`;
native macOS psql is unnecessary.

```sh
make migration-history   # Valid empty Alembic history; no database connection or DDL
```

S1 had no application revisions; S2 adds `0001_principal_role` (below). `alembic.ini`, `migrations/env.py` and the SQL-first template are
explicit entry points for later reviewed revisions. Execution refuses an empty revision chain; online migration
also requires the distinct `tl_schema_migrator` role and serializes executors with a PostgreSQL advisory lock.
Application startup never invokes Alembic or creates a schema. Before a future upgrade, review its contract
reference, change class, SQL, compatibility and recovery under ADR-0011; render the specific revision offline
before executing it. The current development connection role is not authorization to apply an application migration.

## Checks and remaining scope

`make smoke` compiles the backend, exercises its route/startup/credential/kernel boundaries, reads migration
history, renders React through Vite for two Node smoke tests, type-checks TypeScript and builds the frontend.
`.github/workflows/application-smoke.yml` adds separate backend/frontend build jobs; no database credentials
or protected-flow prerequisites are fabricated in CI. Remote application CI has not run for these uncommitted changes.

```sh
.venv/bin/python knowledge/validation/run_all.py --json
```

Three frozen UX validators historically required no application files anywhere. After verified Phase 7 closure,
the canonical runner runs these unchanged validators against current governed sources in a temporary design
view excluding later `apps/` implementation. Their fixture audits and artifact hashes remain intact. Runtime
files outside `apps/` still fail the original design guard; the backend smoke test proves that refusal.
The other canonical validators run against the working tree. This is design-scope validation, not a substitute
for application behavior tests.

Before S2: external OIDC and trusted role provisioning, browser session/CSRF decision (T05), encrypted content
storage plus secret/key mechanisms, reviewed application migrations/roles and the remaining T09 limits must be
resolved. Single-tenancy is sponsor-confirmed by DEC-009; it preserves multiple users and all five roles.
No production deployment, accuracy, WCAG conformance or complete user journey is claimed.

Framework references: [FastAPI](https://fastapi.tiangolo.com/deployment/),
[Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [Vite](https://vite.dev/guide/).

## S2 authentication

Keycloak authenticates the person; TrustLens decides access. Signing in never creates a TrustLens principal or role:
an identity must be provisioned first, and roles are re-read from PostgreSQL on every request. Tokens and the client
secret stay in the backend; the browser holds only an HttpOnly session cookie (details: T05 profile).

One-time, sponsor-executed setup (privileged; never run by the application):

1. Bootstrap roles and schema as the database owner, then set both passwords interactively (SCRAM, not echoed):
   `docker exec -i trustlens-postgres-dev psql -U <owner> -d trustlens_dev < apps/backend/migrations/bootstrap/s2_roles_and_schema.sql`, then
   `docker exec -it trustlens-postgres-dev psql -U <owner> -d trustlens_dev -c '\password tl_schema_migrator'` (and `tl_app_runtime`).
2. Create `~/.config/trustlens/migrator-db.env` and `~/.config/trustlens/app-db.env` (`chmod 600`), each with
   `POSTGRES_DB=trustlens_dev`, `POSTGRES_USER=` the role and `POSTGRES_PASSWORD=` its password.
3. Review `make migration-sql`, then `make migrate` (refused for any role except `tl_schema_migrator`). This applies
   `0001_principal_role` and `0002_audit_chain`; an environment already at 0001 only needs `make migrate` again.
4. Grant USER to the Keycloak account by its user ID (Keycloak admin console → realm `trustlens-local` → Users →
   `tl-demo-user` → ID): `make provision-user SUBJECT=<id>`. Only USER can be granted this way.

Run `make backend-run` and `make frontend-run`, open http://127.0.0.1:5173 (not localhost) and choose
**Sign in with Keycloak**. `/auth/*` are authentication-boundary routes, not API v1 operations. Sessions live in the
backend process: restarting it signs everyone out, so run exactly one backend process. Sign-in outcomes,
authorization denials and role grants/revocations are written to the hash-chained audit log (`make audit-verify`
recomputes it); if the audit append fails, sign-in fails closed. Sign-in and state-changing requests are bounded by
local, in-memory admission control; a durable session store is not implemented yet.

## S2 cases and submissions

Signed-in users can create cases and record submissions through the accepted API operations `createCase`, `getCase`,
`listCases`, `createSubmission`, `getSubmission` and `listSubmissions`:
- owners and grants are set by the server;
- access is masked as 404 or refused as 403;
- creates require an `Idempotency-Key`;
- `CASE_CREATED` is audited atomically.

Migration `0003_case_submission` adds the contract tables; apply it with `make migrate`, as before.

## S2 evidence intake (contract approved and merged)

Owners can paste synthetic message text into a submission. The upload uses the accepted three-step flow:
`createEvidenceUpload`, then `putEvidenceContent` (exact bytes as `text/plain; charset=utf-8`), then `finalizeEvidence`
(`202`). `getEvidenceMetadata` and `listEvidence` read it back.
- The server computes the SHA-256; a client digest is optional and advisory.
- Content is encrypted at rest with the approved local key profile.
- Custody steps are audited in the hash chain.
- Nothing is analysed or scored.

Evidence routes answer `503` until **both** of these are true:
1. Migration `0004_evidence_intake` is applied. It implements persistence addendum
   [DATA-001-WP2-ADD-P9-S2-001](../docs/06-contracts/DATA-001-WP2-ADD-P9-S2-001-evidence-upload-intent.md), approved
   following independent review and merged in PR #47
   ([GATE-033](../docs/00-program/GATE-033-p9-s2-add-001-persistence-revision.md)). Review `make migration-sql`
   before `make migrate`.
2. The sponsor has created the evidence key; see
   [S2-local-development-profile.md](../docs/07-implementation/S2-local-development-profile.md).

That file also lists the approved limits and the bounded local admission control (`429 RATE_LIMITED`).

## S3 governed knowledge seam (exact-digest activation, DEC-011 / DEC-012)

Migration `0005_knowledge_seam` creates the accepted contract tables `knowledge_bundle_reference`,
`knowledge_activation_record` and `knowledge_deployment_state`. It records one `NO_ACTIVE_BUNDLE` state for deployment
`local-development`. Apply it like the earlier migrations: `make migration-sql` to review, then `make migrate`.

1. `make knowledge-bundle` runs the canonical gate, publishes with the existing tool and installs the bundle at
   `~/.local/share/trustlens/knowledge/<digest>/`. It installs only if the exact digest is approved in
   [`backend/knowledge_releases/local-development.json`](backend/knowledge_releases/local-development.json).
2. `make knowledge-activate DIGEST=<sha256> CHANGE_REF=<REF>` signs you in through Keycloak (an ADMINISTRATOR account
   is required; see DEC-013 and `make provision-administrator SUBJECT=<id> CONFIRM_SUBJECT=<id>` for a separate local
   account). It shows the current and requested digests, asks you to type the digest prefix, and calls the
   accepted `activateKnowledgeBundle` operation. The CLI never touches the database.

- **Server checks:** the release approval, the publication gate, local verification (manifest, per-file hashes, digest,
  compatibility), eligibility and the stale-state precondition. Every outcome is audited as `KNOWLEDGE_ACTIVATED` or
  `KNOWLEDGE_ACTIVATION_REJECTED`.
- **Authenticity:** recorded as `NOT_REQUIRED_BY_POLICY` under DEC-012, for this single-machine synthetic profile only.
  It is not publisher authentication.
- **Readiness:** evaluation readiness and `/health/ready` are `OK` only for an active, eligible, verified bundle with the
  S2 dependencies present.
- **Not implemented:** rollback, withdrawal and the operator UI (S9), and scoring and results (S5).

## S4 deterministic extraction (no endpoint, no result)

`trustlens_backend/extraction.py` turns one FINALIZED synthetic text evidence item into governed engine inputs.
`extract_finalized_evidence` authorizes the caller as `createEvaluations` does (USER/ANALYST with case access), reads
the original bytes through the encrypted store, re-verifies digest and length, audits the read (`EVIDENCE_ACCESSED`)
and extracts against the ACTIVE verified bundle. `extract_text` is the same extractor over bytes.

- **Output:** an immutable `GovernedInput`: input envelope, observations, indicator observations and the input
  support state. All are checked against the KB-002 schemas, the active registry and negative library, and the
  engine's own `build_validated_context`. `engine_inputs()` is what S5 will pass to `evaluate_detection_from_governed`.
- **Grounding:** offsets index `normalized_text`; every `raw_span` is the exact submitted text. Provenance pins the
  extractor version and the pattern-pack digest (`config_ref`).
- **Structure:** negated, reported, quoted and hypothetical occurrences never project a positive indicator. An
  unstated payment direction is `AMBIGUOUS` and marked for review.
- **Support states:** `UNSUPPORTED` (non-English or other scripts), `INSUFFICIENT_INFORMATION`, `PARTIALLY_SUPPORTED`
  (a referenced attachment that is not evaluated) and `ERROR` (malformed bytes) are explicit. None is benign.
- **Not implemented:** an API endpoint, scoring, `DetectionResult` persistence and the result UI (S5). The golden
  fixtures test the extractor; they never stand in for it.
