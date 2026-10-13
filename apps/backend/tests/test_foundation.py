import json
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from trustlens_backend.database import DatabaseConfigurationError, DatabaseSettings
from trustlens_backend.main import app, create_app

ROOT = Path(__file__).resolve().parents[3]


class FoundationTests(unittest.TestCase):
    def test_probe_surface_matches_accepted_contract(self):
        catalog = json.loads((ROOT / "contracts/api/api-v1.json").read_text())
        expected = {o["path"] for o in catalog["operations"] if o.get("internal")}
        unconfigured = create_app(None, configure_from_environment=False)
        self.assertTrue(expected <= {route.path for route in unconfigured.routes})   # full surface: test_auth
        with TestClient(unconfigured) as client:
            for path, status in (("/health/live", "OK"), ("/health/ready", "NOT_READY")):
                response = client.get(path, headers={"X-Request-Id": "untrusted-client-id"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"status": status})
                self.assertIn(status, catalog["vocabularies"]["probe_status"]["values"])
                self.assertEqual(UUID(response.headers["X-Request-Id"]).version, 4)

    def test_unimplemented_routes_and_framework_docs_are_not_enabled(self):
        with TestClient(create_app(None, configure_from_environment=False)) as client:
            for path in ("/api/v1/cases", "/api/v1/evaluations", "/docs", "/redoc", "/openapi.json"):
                self.assertEqual(client.get(path).status_code, 404)
            # getMe exists from S2 but fails closed without authentication configuration; it never answers 200.
            self.assertEqual(client.get("/api/v1/me").status_code, 503)

    def test_startup_does_not_connect_or_create_schema(self):
        with patch("psycopg.connect", side_effect=AssertionError("unexpected database call")), \
                patch("sqlalchemy.create_engine", side_effect=AssertionError("unexpected schema startup")):
            with TestClient(app) as client:
                self.assertEqual(client.get("/health/live").json(), {"status": "OK"})

    def test_kernel_is_the_existing_in_process_function(self):
        from knowledge.runtime.result import evaluate_detection_from_governed
        from trustlens_backend import kernel
        self.assertIs(kernel.evaluate_detection_from_governed, evaluate_detection_from_governed)
        self.assertEqual(kernel.ENGINE_VERSION, "1.0.0")

    def test_credentials_are_required_and_redacted(self):
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseSettings.from_environment({})
        sample = "synthetic-test-value"
        settings = DatabaseSettings.from_environment(
            {"POSTGRES_DB": "synthetic", "POSTGRES_USER": "synthetic", "POSTGRES_PASSWORD": sample})
        self.assertNotIn(sample, repr(settings))
        self.assertNotIn(sample, str(settings.sqlalchemy_url()))

    def test_invalid_port_has_safe_error(self):
        with self.assertRaisesRegex(DatabaseConfigurationError, "must be an integer"):
            DatabaseSettings.from_environment({"TRUSTLENS_DB_PORT": "invalid"})

    def test_application_role_cannot_run_migrations(self):
        from alembic import command
        from alembic.config import Config
        ordinary = {"POSTGRES_DB": "synthetic", "POSTGRES_USER": "tl_app_runtime", "POSTGRES_PASSWORD": "synthetic"}
        with patch.dict("os.environ", ordinary), \
                patch("sqlalchemy.create_engine", side_effect=AssertionError("unexpected database mutation")):
            with self.assertRaisesRegex(RuntimeError, "tl_schema_migrator"):
                command.upgrade(Config(str(ROOT / "apps/backend/alembic.ini")), "head")

    def test_historical_design_scope_still_rejects_runtime_outside_apps(self):
        spec = importlib.util.spec_from_file_location("s1_runner", ROOT / "knowledge/validation/run_all.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        view = runner.phase7_design_root()
        self.assertNotEqual(view, ROOT)
        self.assertFalse((view / "apps").exists())
        injected = view / "unexpected-frontend.js"
        try:
            injected.write_text("// Synthetic scope violation for this test only.\n")
            spec = importlib.util.spec_from_file_location("s1_ux_scope", view / "knowledge/validation/validate_ux_foundation.py")
            validator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(validator)
            failed = {r["check_id"] for r in validator.validate(validator.load_inputs()) if not r["passed"]}
            self.assertEqual(failed, {"UXF-54"})
        finally:
            injected.unlink()
            runner._design_view.cleanup()


if __name__ == "__main__":
    unittest.main()
