BACKEND_PY := apps/backend/.venv/bin/python
ENV_FILE ?= $(HOME)/.config/trustlens/postgres-dev.env

.PHONY: backend-install backend-build backend-test backend-run database-check migration-history frontend-install frontend-build frontend-test frontend-run smoke

backend-install:
	python3.12 -c 'import sys; assert sys.version_info[:3] == (3, 12, 12), "Use Python 3.12.12 for the local application profile"'
	python3.12 -m venv apps/backend/.venv
	$(BACKEND_PY) -m pip install --disable-pip-version-check -r apps/backend/requirements.lock

backend-build:
	$(BACKEND_PY) -m compileall -q apps/backend/trustlens_backend

backend-test:
	PYTHONPATH=apps/backend $(BACKEND_PY) -m unittest discover -s apps/backend/tests -v

backend-run:
	PYTHONPATH=apps/backend $(BACKEND_PY) -m uvicorn trustlens_backend.main:app --host 127.0.0.1 --port 8000 --no-access-log

database-check:
	PYTHONPATH=apps/backend $(BACKEND_PY) -m trustlens_backend.database --env-file "$(ENV_FILE)"

migration-history:
	PYTHONPATH=apps/backend $(BACKEND_PY) -m alembic -c apps/backend/alembic.ini history

frontend-install:
	npm ci --prefix apps/frontend

frontend-build:
	npm run build --prefix apps/frontend

frontend-test:
	npm test --prefix apps/frontend

frontend-run:
	npm run dev --prefix apps/frontend

smoke: backend-build backend-test migration-history frontend-test frontend-build
