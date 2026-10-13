# TrustLens S1 local foundation

Run commands from the repository root. This is a local smoke scaffold, not the authenticated S2 journey.
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
make backend-run     # http://127.0.0.1:8000 — internal probes only
make frontend-run    # http://127.0.0.1:5173 — static development preview
```

```sh
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
```

The accepted probe response is HTTP 200 with categorical status: liveness reports `OK`, readiness reports
`NOT_READY`. Check the body, not HTTP success alone. No protected API, login, ingestion or content storage is
enabled; framework `/docs`, `/redoc` and `/openapi.json` are disabled. The frontend does not proxy internal
health endpoints, collect content or call a new API. Both development servers bind to loopback.

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

There are no application revisions in S1. `alembic.ini`, `migrations/env.py` and the SQL-first template are
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
