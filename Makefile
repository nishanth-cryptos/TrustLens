BACKEND_PY := apps/backend/.venv/bin/python
ENV_FILE ?= $(HOME)/.config/trustlens/postgres-dev.env
OIDC_ENV_FILE ?= $(HOME)/.config/trustlens/oidc-dev.env
APP_DB_ENV_FILE ?= $(HOME)/.config/trustlens/app-db.env
MIGRATOR_ENV_FILE ?= $(HOME)/.config/trustlens/migrator-db.env

.PHONY: backend-install backend-build backend-test backend-run database-check migration-history migration-sql migrate provision-user audit-verify frontend-install frontend-build frontend-test frontend-run smoke

backend-install:
	python3.12 -c 'import sys; assert sys.version_info[:3] == (3, 12, 12), "Use Python 3.12.12 for the local application profile"'
	python3.12 -m venv apps/backend/.venv
	$(BACKEND_PY) -m pip install --disable-pip-version-check -r apps/backend/requirements.lock

backend-build:
	$(BACKEND_PY) -m compileall -q apps/backend/trustlens_backend

backend-test:
	PYTHONPATH=apps/backend $(BACKEND_PY) -m unittest discover -s apps/backend/tests -v

# Single process only: S2 sessions are held in memory (no --workers / --reload).
backend-run:
	TRUSTLENS_OIDC_ENV_FILE="$(OIDC_ENV_FILE)" TRUSTLENS_APP_DB_ENV_FILE="$(APP_DB_ENV_FILE)" \
	PYTHONPATH=apps/backend $(BACKEND_PY) -m uvicorn trustlens_backend.main:app --host 127.0.0.1 --port 8000 --no-access-log

database-check:
	PYTHONPATH=apps/backend $(BACKEND_PY) -m trustlens_backend.database --env-file "$(ENV_FILE)"

migration-history:
	PYTHONPATH=apps/backend $(BACKEND_PY) -m alembic -c apps/backend/alembic.ini history

# Review step: renders the exact SQL offline (placeholder connection values; nothing connects or executes).
migration-sql:
	POSTGRES_DB=offline-render POSTGRES_USER=tl_schema_migrator POSTGRES_PASSWORD=render-only \
	PYTHONPATH=apps/backend $(BACKEND_PY) -m alembic -c apps/backend/alembic.ini upgrade head --sql

# Sponsor-executed release step only, as tl_schema_migrator (refused for any other role).
migrate:
	@test -f "$(MIGRATOR_ENV_FILE)" || { echo "Missing $(MIGRATOR_ENV_FILE)"; exit 1; }
	set -a; . "$(MIGRATOR_ENV_FILE)"; set +a; \
	PYTHONPATH=apps/backend $(BACKEND_PY) -m alembic -c apps/backend/alembic.ini upgrade head

# Read-only recomputation of every audit hash and link, as tl_app_runtime.
audit-verify:
	TRUSTLENS_APP_DB_ENV_FILE="$(APP_DB_ENV_FILE)" PYTHONPATH=apps/backend $(BACKEND_PY) -m trustlens_backend.audit

# Explicit local USER-role grant for one validated identity: make provision-user SUBJECT=<keycloak user id>
provision-user:
	@test -n "$(SUBJECT)" || { echo "Set SUBJECT=<keycloak user id>"; exit 1; }
	TRUSTLENS_OIDC_ENV_FILE="$(OIDC_ENV_FILE)" TRUSTLENS_APP_DB_ENV_FILE="$(APP_DB_ENV_FILE)" \
	PYTHONPATH=apps/backend $(BACKEND_PY) -m trustlens_backend.provisioning grant-user --subject "$(SUBJECT)" --confirm

frontend-install:
	npm ci --prefix apps/frontend

frontend-build:
	npm run build --prefix apps/frontend

frontend-test:
	npm test --prefix apps/frontend

frontend-run:
	npm run dev --prefix apps/frontend

smoke: backend-build backend-test migration-history frontend-test frontend-build
