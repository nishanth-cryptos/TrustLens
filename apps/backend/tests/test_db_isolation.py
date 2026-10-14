"""Disposable-test database isolation (review finding 6): refusal happens before any connection is attempted.

These tests never connect to the persistent development endpoint. Socket-level proofs use a local listener that the
test temporarily treats as "the persistent endpoint"; the alembic test replaces create_engine with a sentinel so that
even a broken guard could not reach a real database.
"""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from trustlens_backend import config, database, disposable
from trustlens_backend.config import AuthConfigurationError, load_environment_files
from trustlens_backend.disposable import PermanentConfigurationRefused, guard_env_file
from trustlens_backend.main import create_app
from trustlens_backend.database import (DatabaseSettings, DisposableEndpointRefused, check_disposable_endpoint,
                                        disposable_settings_from_file, install_connect_guard)

ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC = {"POSTGRES_DB": "trustlens_dev", "POSTGRES_USER": "tl_app_runtime", "POSTGRES_PASSWORD": "synthetic-not-a-secret"}
# The exact shape of the 2026-10-14 incident: correct names for Docker, wrong names for TrustLens.
WRONG_NAMES = {"POSTGRES_HOST": "127.0.0.1", "POSTGRES_PORT": "55491", **SYNTHETIC}


class Listener:
    """A loopback TCP listener that counts accepted connections (it never speaks PostgreSQL)."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.port, self.accepted, self._stop = self.sock.getsockname()[1], 0, threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except (socket.timeout, OSError):
                continue
            self.accepted += 1
            conn.close()

    def close(self):
        self._stop.set()
        self._thread.join(2)
        self.sock.close()


def write_env(directory, values):
    path = Path(directory) / "db.env"
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    return path


class _Isolated(unittest.TestCase):
    def setUp(self):
        saved = (psycopg.connect, psycopg.Connection.__dict__["connect"])

        def restore():                                   # undo any connect guard a test installed
            psycopg.connect = saved[0]
            psycopg.Connection.connect = saved[1]
        self.addCleanup(restore)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        environment = patch.dict(os.environ, {database.DISPOSABLE_FLAG: "1"})   # restores the whole environment on stop
        environment.start()
        self.addCleanup(environment.stop)
        for name in ("TRUSTLENS_DB_HOST", "TRUSTLENS_DB_PORT", "PGHOST", "PGPORT", "PGSERVICE"):
            os.environ.pop(name, None)


class EndpointValidationTests(_Isolated):
    def test_the_incident_reproduction_is_refused_before_any_connection(self):
        path = write_env(self.tmp.name, WRONG_NAMES)
        with patch.object(database.psycopg, "connect", side_effect=AssertionError("connection attempted")) as connect:
            with self.assertRaisesRegex(DisposableEndpointRefused, "explicit TRUSTLENS_DB_HOST"):
                disposable_settings_from_file(path)
        connect.assert_not_called()
        with patch.dict(os.environ, {database.DISPOSABLE_FLAG: "0"}):
            # Outside disposable mode the same file silently means the persistent endpoint: the original hazard.
            self.assertEqual(DatabaseSettings.from_environment(WRONG_NAMES).port, 55432)

    def test_missing_empty_and_malformed_endpoints_are_refused(self):
        cases = [{}, {"TRUSTLENS_DB_HOST": "127.0.0.1"}, {"TRUSTLENS_DB_PORT": "55491"},
                 {"TRUSTLENS_DB_HOST": "", "TRUSTLENS_DB_PORT": "55491"}, {"TRUSTLENS_DB_HOST": "127.0.0.1", "TRUSTLENS_DB_PORT": ""}]
        cases += [{"TRUSTLENS_DB_HOST": "127.0.0.1", "TRUSTLENS_DB_PORT": port}
                  for port in ("abc", "0", "70000", "-1", "5432,55432", "55491x", "5.5")]
        cases += [{"TRUSTLENS_DB_HOST": host, "TRUSTLENS_DB_PORT": "55491"}
                  for host in ("db.example.invalid", "10.0.0.5", "127.0.0.1,db.example.invalid", "/tmp")]
        for endpoint in cases:
            with self.subTest(endpoint=endpoint), self.assertRaises(DisposableEndpointRefused):
                disposable_settings_from_file(write_env(self.tmp.name, {**SYNTHETIC, **endpoint}))

    def test_the_persistent_endpoint_is_refused_on_every_loopback_spelling(self):
        for host in ("127.0.0.1", "localhost", "LOCALHOST", "::1"):
            with self.subTest(host=host), self.assertRaisesRegex(DisposableEndpointRefused, "persistent"):
                disposable_settings_from_file(write_env(self.tmp.name, {**SYNTHETIC, "TRUSTLENS_DB_HOST": host,
                                                                        "TRUSTLENS_DB_PORT": "55432"}))

    def test_permanent_credentials_are_refused_without_being_read(self):
        permanent = Path("~/.config/trustlens/app-db.env")
        with patch.object(Path, "is_file", side_effect=AssertionError("permanent file inspected")), \
                patch.object(database, "dotenv_values", side_effect=AssertionError("permanent file read")):
            with self.assertRaisesRegex(DisposableEndpointRefused, "permanent"):
                disposable_settings_from_file(permanent)
        with self.assertRaises(DisposableEndpointRefused):
            disposable_settings_from_file("")

    def test_settings_built_another_way_cannot_produce_connection_parameters(self):
        direct = DatabaseSettings("127.0.0.1", 55491, "trustlens_dev", "tl_app_runtime", "synthetic")
        with self.assertRaisesRegex(DisposableEndpointRefused, "explicit configuration"):
            direct.connection_parameters()
        with self.assertRaises(DisposableEndpointRefused):
            direct.sqlalchemy_url()
        persistent = DatabaseSettings("127.0.0.1", 55432, "x", "y", "z", explicit_endpoint=True)
        with self.assertRaises(DisposableEndpointRefused):
            persistent.connection_parameters()
        good = disposable_settings_from_file(write_env(self.tmp.name, {**SYNTHETIC, "TRUSTLENS_DB_HOST": "127.0.0.1",
                                                                       "TRUSTLENS_DB_PORT": "55491"}))
        self.assertEqual((good.host, good.port), ("127.0.0.1", 55491))
        self.assertEqual(good.connection_parameters()["port"], 55491)

    def test_disposable_mode_must_be_selected_explicitly(self):
        with patch.dict(os.environ, {database.DISPOSABLE_FLAG: "0"}), self.assertRaises(DisposableEndpointRefused):
            disposable_settings_from_file(write_env(self.tmp.name, {**SYNTHETIC, "TRUSTLENS_DB_HOST": "127.0.0.1",
                                                                    "TRUSTLENS_DB_PORT": "55491"}))

    def test_sponsor_commands_are_unchanged_outside_disposable_mode(self):
        with patch.dict(os.environ, {database.DISPOSABLE_FLAG: ""}):
            settings = DatabaseSettings.from_environment({**SYNTHETIC})
            self.assertEqual((settings.host, settings.port), ("127.0.0.1", 55432))
            self.assertEqual(settings.connection_parameters()["port"], 55432)       # built, never connected here


class PermanentPathLoaderTests(_Isolated):
    """Review finding (round 2): both runtime loaders refuse permanent configuration before any access to it."""

    REAL_PERMANENT = ("~/.config/trustlens/app-db.env", "~/.config/trustlens/oidc-dev.env",
                      "~/.config/trustlens/evidence-kek-v1.key", "~/.config/trustlens", "~/.config/./trustlens/x.env",
                      "~/.config/other/../trustlens/migrator-db.env")

    def no_access(self):
        """Any read of a configuration file (existence check, open or dotenv) fails the test."""
        boom = AssertionError("a permanent configuration file was accessed")
        return [patch.object(Path, "is_file", side_effect=boom), patch.object(Path, "read_bytes", side_effect=boom),
                patch("builtins.open", side_effect=boom), patch.object(config, "dotenv_values", side_effect=boom),
                patch.object(database, "load_dotenv", side_effect=boom), patch.object(database, "dotenv_values", side_effect=boom),
                patch.object(database.psycopg, "connect", side_effect=AssertionError("connection attempted"))]

    def guarded(self):
        for p in self.no_access():
            p.start()
            self.addCleanup(p.stop)

    def fake_permanent(self):
        """A temporary stand-in for ~/.config/trustlens, so symlink cases never touch the real directory."""
        root = Path(self.tmp.name) / "home-config" / "trustlens"
        root.mkdir(parents=True)
        secret = root / "app-db.env"
        secret.write_text("POSTGRES_PASSWORD=synthetic-permanent-secret\n")
        stand_in = patch.object(disposable, "PERMANENT_CONFIG_DIR", root)
        stand_in.start()
        self.addCleanup(stand_in.stop)
        return root, secret

    def test_config_loader_refuses_the_real_permanent_paths_without_reading(self):
        home = str(Path("~").expanduser())
        self.guarded()
        for name in self.REAL_PERMANENT + (home + "/.config/trustlens/app-db.env",):
            for variable in ("TRUSTLENS_APP_DB_ENV_FILE", "TRUSTLENS_OIDC_ENV_FILE"):
                with self.subTest(path=name, variable=variable), self.assertRaisesRegex(AuthConfigurationError, "permanent"):
                    load_environment_files({variable: name, database.DISPOSABLE_FLAG: "1"})

    def test_database_env_file_option_refuses_permanent_paths_before_any_connection(self):
        self.guarded()
        for name in self.REAL_PERMANENT[:3]:
            with self.subTest(path=name), patch("sys.argv", ["database", "--env-file", name]), \
                    patch("builtins.print") as printed:
                self.assertEqual(database.main(), 1)
                self.assertIn("refused", printed.call_args[0][0])

    def test_symlinks_and_traversal_into_permanent_configuration_are_refused(self):
        root, secret = self.fake_permanent()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "link.env").symlink_to(secret)                       # symlinked file
        (outside / "linked-dir").symlink_to(root, target_is_directory=True)   # symlinked directory
        alias = Path(self.tmp.name) / "alias-config"
        alias.symlink_to(root.parent, target_is_directory=True)
        cases = [outside / "link.env", outside / "linked-dir" / "app-db.env", alias / "trustlens" / "app-db.env",
                 outside / ".." / "home-config" / "trustlens" / "app-db.env", secret]
        with patch.object(config, "dotenv_values", side_effect=AssertionError("read")), \
                patch.object(database, "load_dotenv", side_effect=AssertionError("read")), \
                patch.object(database.psycopg, "connect", side_effect=AssertionError("connection attempted")):
            for path in cases:
                with self.subTest(path=str(path)):
                    with self.assertRaises(PermanentConfigurationRefused):
                        guard_env_file(path)
                    with self.assertRaisesRegex(AuthConfigurationError, "permanent"):
                        load_environment_files({"TRUSTLENS_APP_DB_ENV_FILE": str(path)})
                    with patch("sys.argv", ["database", "--env-file", str(path)]), patch("builtins.print"):
                        self.assertEqual(database.main(), 1)
                    with self.assertRaises(DisposableEndpointRefused):
                        disposable_settings_from_file(path)
        # The permanent directory itself reached through a symlink (its resolved form is compared too).
        linked_root = patch.object(disposable, "PERMANENT_CONFIG_DIR", alias / "trustlens")
        with linked_root, self.assertRaises(PermanentConfigurationRefused):
            guard_env_file(secret)

    def symlink_dotdot_case(self):
        """Independent-review reproduction: O/link -> P/child, input O/link/../app-db.env really means P/app-db.env."""
        root, secret = self.fake_permanent()                                   # P (stand-in) holding P/app-db.env
        (root / "child").mkdir()
        outside = Path(self.tmp.name) / "O"
        outside.mkdir()
        (outside / "app-db.env").write_text("POSTGRES_PASSWORD=decoy\n")         # the file a lexical guard would inspect
        (outside / "link").symlink_to(root / "child", target_is_directory=True)
        return outside / "link" / ".." / "app-db.env", secret

    def test_symlink_then_dotdot_is_resolved_like_the_loader_and_refused(self):
        tricky, secret = self.symlink_dotdot_case()
        self.assertEqual(tricky.resolve(), secret.resolve())                     # the OS really reaches P/app-db.env
        with patch.object(config, "dotenv_values", side_effect=AssertionError("read")), \
                patch.object(database, "dotenv_values", side_effect=AssertionError("read")), \
                patch.object(database, "load_dotenv", side_effect=AssertionError("read")), \
                patch.object(database.psycopg, "connect", side_effect=AssertionError("connection attempted")):
            with self.assertRaises(PermanentConfigurationRefused):
                guard_env_file(tricky)
            for variable in ("TRUSTLENS_APP_DB_ENV_FILE", "TRUSTLENS_OIDC_ENV_FILE"):           # entry point 1: config
                with self.subTest(entry="config", variable=variable), self.assertRaisesRegex(AuthConfigurationError, "permanent"):
                    load_environment_files({variable: str(tricky)})
            with patch("sys.argv", ["database", "--env-file", str(tricky)]), patch("builtins.print") as printed:
                self.assertEqual(database.main(), 1)                                            # entry point 2: --env-file
                self.assertIn("refused", printed.call_args[0][0])
            with self.assertRaisesRegex(DisposableEndpointRefused, "permanent"):              # entry point 3: test settings
                disposable_settings_from_file(tricky)

    def test_the_guarded_destination_is_exactly_what_gets_loaded(self):
        root, _ = self.fake_permanent()
        target = Path(self.tmp.name) / "real-target"
        target.mkdir()
        (target / "app-db.env").write_text("POSTGRES_USER=from-the-resolved-destination\n")
        hop = Path(self.tmp.name) / "hop"
        hop.mkdir()
        (hop / "link").symlink_to(target / "sub", target_is_directory=True)
        (target / "sub").mkdir()
        (hop / "app-db.env").write_text("POSTGRES_USER=lexical-decoy\n")
        path = hop / "link" / ".." / "app-db.env"                                 # really target/app-db.env (not protected)
        self.assertEqual(guard_env_file(path), (target / "app-db.env").resolve())
        self.assertEqual(load_environment_files({"TRUSTLENS_APP_DB_ENV_FILE": str(path)})["POSTGRES_USER"],
                         "from-the-resolved-destination")

    def test_a_disposable_file_outside_permanent_configuration_still_loads(self):
        self.fake_permanent()
        safe = write_env(self.tmp.name, {**SYNTHETIC, "TRUSTLENS_DB_HOST": "127.0.0.1", "TRUSTLENS_DB_PORT": "55491"})
        env = load_environment_files({"TRUSTLENS_APP_DB_ENV_FILE": str(safe)})
        self.assertEqual(env["POSTGRES_USER"], "tl_app_runtime")

    def test_normal_development_behaviour_is_unchanged_outside_disposable_mode(self):
        root, secret = self.fake_permanent()
        with patch.dict(os.environ, {database.DISPOSABLE_FLAG: ""}):
            self.assertEqual(guard_env_file(secret), secret)
            env = load_environment_files({"TRUSTLENS_APP_DB_ENV_FILE": str(secret)})
            self.assertEqual(env["POSTGRES_PASSWORD"], "synthetic-permanent-secret")   # the stand-in, never the real one
            real = Path("~/.config/trustlens/app-db.env")
            self.assertEqual(guard_env_file(real), real.expanduser())                # returned unread, as before

    def test_the_runtime_stays_fail_closed_when_refused(self):
        self.guarded()
        with patch.dict(os.environ, {"TRUSTLENS_APP_DB_ENV_FILE": "~/.config/trustlens/app-db.env",
                                     "TRUSTLENS_OIDC_ENV_FILE": "~/.config/trustlens/oidc-dev.env"}), \
                patch("builtins.print"):
            app = create_app()
        self.assertIsNone(app.state.auth)                                 # authentication disabled, nothing loaded


class ConnectGuardTests(_Isolated):
    """Socket-level proof: a local listener stands in for the persistent endpoint, so nothing real is ever contacted."""

    def setUp(self):
        super().setUp()
        self.listener = Listener()
        self.addCleanup(self.listener.close)
        guarded_ports = patch.object(database, "PERSISTENT_DEV_PORTS", frozenset({55432, self.listener.port}))
        guarded_ports.start()
        self.addCleanup(guarded_ports.stop)

    def settle(self):
        threading.Event().wait(0.5)        # give the accept loop time to observe any connection
        return self.listener.accepted

    def test_the_positive_control_really_reaches_the_listener(self):
        current = psycopg.Connection.connect.__func__
        unguarded = getattr(current, "_trustlens_original", current)          # bypass a guard the harness installed
        with self.assertRaises(psycopg.OperationalError):
            unguarded(psycopg.Connection, host="127.0.0.1", port=self.listener.port, dbname="x", user="y", password="z",
                      connect_timeout=2)
        self.assertGreaterEqual(self.settle(), 1)                                 # unguarded: a socket was opened

    def test_guarded_psycopg_and_sqlalchemy_never_open_a_socket(self):
        install_connect_guard()
        install_connect_guard()                                                   # idempotent
        attempts = [
            lambda: psycopg.connect(host="127.0.0.1", port=self.listener.port, dbname="x", user="y", password="z"),
            lambda: psycopg.Connection.connect(f"host=localhost port={self.listener.port} dbname=x user=y password=z"),
            lambda: psycopg.connect("dbname=x user=y password=z"),                # no host/port: libpq defaults refused
            lambda: psycopg.connect(host="127.0.0.1", hostaddr="127.0.0.1", port=55491, dbname="x", user="y", password="z"),
            lambda: psycopg.connect(service="trustlens", dbname="x"),
            lambda: create_engine(f"postgresql+psycopg://y:z@127.0.0.1:{self.listener.port}/x", poolclass=NullPool).connect(),
        ]
        for attempt in attempts:
            with self.assertRaises(Exception) as caught:
                attempt()
            chain, error = [], caught.exception
            while error is not None:
                chain.append(error)
                error = error.__cause__ or error.__context__
            self.assertTrue(any(isinstance(x, DisposableEndpointRefused) for x in chain), repr(caught.exception))
        self.assertEqual(self.settle(), 0)

    def test_check_disposable_endpoint_accepts_only_explicit_loopback_non_persistent(self):
        check_disposable_endpoint("127.0.0.1", "55491")
        check_disposable_endpoint("::1", 55491)
        for host, port in (("127.0.0.1", self.listener.port), ("127.0.0.1", 55432), (None, 55491), ("127.0.0.1", None),
                           ("127.0.0.1", True)):
            with self.subTest(host=host, port=port), self.assertRaises(DisposableEndpointRefused):
                check_disposable_endpoint(host, port)


class MigrationEnvironmentTests(_Isolated):
    """The alembic env.py path uses the same guard; create_engine is a sentinel, so no database is reachable at all."""

    WRAPPER = (
        "import sys, sqlalchemy\n"
        "def sentinel(*a, **k):\n"
        "    print('SENTINEL-CREATE-ENGINE-REACHED'); sys.exit(99)\n"
        "sqlalchemy.create_engine = sentinel\n"
        "import trustlens_backend.database as d\n"
        "d.PERSISTENT_DEV_PORTS = frozenset({55432, int(sys.argv[1])})\n"
        "from alembic.config import main\n"
        "main(argv=['-c', 'apps/backend/alembic.ini', 'upgrade', 'head'])\n")

    def run_alembic(self, values, guarded_port):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("TRUSTLENS_", "POSTGRES_", "PG"))}
        env.update({**values, database.DISPOSABLE_FLAG: "1", "PYTHONPATH": "apps/backend"})
        return subprocess.run([sys.executable, "-c", self.WRAPPER, str(guarded_port)], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=120)

    def test_misnamed_or_persistent_endpoints_stop_alembic_before_any_engine(self):
        listener = Listener()
        self.addCleanup(listener.close)
        migrator = {**SYNTHETIC, "POSTGRES_USER": "tl_schema_migrator"}
        for values in ({**WRONG_NAMES, "POSTGRES_USER": "tl_schema_migrator"},
                       {**migrator, "TRUSTLENS_DB_HOST": "127.0.0.1", "TRUSTLENS_DB_PORT": "55432"},
                       {**migrator, "TRUSTLENS_DB_HOST": "127.0.0.1", "TRUSTLENS_DB_PORT": str(listener.port)}):
            with self.subTest(endpoint=(values.get("TRUSTLENS_DB_HOST"), values.get("TRUSTLENS_DB_PORT"))):
                result = self.run_alembic(values, listener.port)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotEqual(result.returncode, 99, "the guard let alembic reach create_engine")
                self.assertNotIn("SENTINEL-CREATE-ENGINE-REACHED", result.stdout)
                self.assertIn("DisposableEndpointRefused", result.stderr)
                self.assertNotIn("synthetic-not-a-secret", result.stdout + result.stderr)
        threading.Event().wait(0.5)
        self.assertEqual(listener.accepted, 0)

    def test_an_acceptable_disposable_endpoint_reaches_the_engine_step(self):
        listener = Listener()
        self.addCleanup(listener.close)
        values = {**SYNTHETIC, "POSTGRES_USER": "tl_schema_migrator", "TRUSTLENS_DB_HOST": "127.0.0.1", "TRUSTLENS_DB_PORT": "55491"}
        result = self.run_alembic(values, listener.port)
        self.assertEqual(result.returncode, 99, result.stderr[-2000:])             # positive control: guard passed it on
        self.assertIn("SENTINEL-CREATE-ENGINE-REACHED", result.stdout)


if __name__ == "__main__":
    unittest.main()
