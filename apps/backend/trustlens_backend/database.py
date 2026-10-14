"""Database settings, the disposable-test isolation guard and an explicit read-only diagnostic.

Configuration values are never logged.

Disposable mode (TRUSTLENS_TEST_DISPOSABLE_DB=1) fails closed before any network connection:
- TRUSTLENS_DB_HOST and TRUSTLENS_DB_PORT must be given explicitly and be well formed. There is no default host or port;
  the normal default is the persistent development endpoint.
- The host must be a loopback literal (disposable containers are published on loopback only).
- The persistent development endpoint (port 55432) is refused on any host.
- Environment files under ~/.config/trustlens (the sponsor's permanent credentials) are refused.
- Settings not built by from_environment cannot produce connection parameters.
- install_connect_guard() wraps psycopg's connect entry points (SQLAlchemy uses them too), so a connection with a
  missing host or port, or one aimed at the persistent endpoint, is refused even if it was built some other way.
Outside disposable mode nothing changes: sponsor-executed commands keep their explicit configuration.
"""
import argparse
import inspect
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import psycopg
from dotenv import dotenv_values, load_dotenv
from sqlalchemy.engine import URL

from .disposable import DISPOSABLE_FLAG, PERMANENT_CONFIG_DIR, PermanentConfigurationRefused, disposable_mode, guard_env_file

PERSISTENT_DEV_PORTS = frozenset({55432})        # the sponsor's persistent development PostgreSQL
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
_PORT = re.compile(r"^[0-9]{1,5}$")


class DatabaseConfigurationError(ValueError):
    pass


class DisposableEndpointRefused(DatabaseConfigurationError):
    """Disposable mode refused a database endpoint before any connection was attempted."""


def check_disposable_endpoint(host, port) -> None:
    """Raise DisposableEndpointRefused unless (host, port) is an explicit loopback endpoint other than the persistent one."""
    if not isinstance(host, str) or not host.strip():
        raise DisposableEndpointRefused("disposable mode needs an explicit TRUSTLENS_DB_HOST")
    if isinstance(port, int) and not isinstance(port, bool):
        port_text = str(port)
    elif isinstance(port, str):
        port_text = port.strip()
    else:
        raise DisposableEndpointRefused("disposable mode needs an explicit TRUSTLENS_DB_PORT")
    if not _PORT.match(port_text) or not 1 <= int(port_text) <= 65535:
        raise DisposableEndpointRefused("disposable TRUSTLENS_DB_PORT is malformed")
    if host.strip().lower() not in LOOPBACK_HOSTS:
        raise DisposableEndpointRefused("disposable TRUSTLENS_DB_HOST must be a loopback address")
    if int(port_text) in PERSISTENT_DEV_PORTS:
        raise DisposableEndpointRefused("refusing the persistent development database endpoint in disposable mode")


def disposable_settings_from_file(path) -> "DatabaseSettings":
    """Disposable-test settings from one explicit env file only (never merged with the process environment)."""
    if not disposable_mode():
        raise DisposableEndpointRefused(f"{DISPOSABLE_FLAG}=1 is required for disposable database settings")
    if not path:
        raise DisposableEndpointRefused("no disposable database environment file was given")
    try:
        resolved = guard_env_file(path)                 # shared guard: the checked destination is the one read
    except PermanentConfigurationRefused as refused:
        raise DisposableEndpointRefused(str(refused)) from None
    if not resolved.is_file():
        raise DisposableEndpointRefused("disposable database environment file is missing")
    values = {k: v for k, v in dotenv_values(resolved).items() if v is not None}
    return DatabaseSettings.from_environment({**values, DISPOSABLE_FLAG: "1"})


def install_connect_guard() -> None:
    """In disposable mode, refuse any psycopg connection whose host/port is missing or is the persistent endpoint.

    Wraps psycopg.connect and psycopg.Connection.connect (idempotent). The check runs before libpq is called, so a
    refused connection never opens a socket."""
    if not disposable_mode() or getattr(psycopg.Connection.connect, "_trustlens_guard", False):
        return
    original = psycopg.Connection.connect.__func__
    python_options = {name for name, p in inspect.signature(original).parameters.items() if p.kind is p.KEYWORD_ONLY}

    def guarded(cls, conninfo="", **kwargs):
        libpq = {k: v for k, v in kwargs.items() if k not in python_options}   # autocommit, context, ... are not libpq
        params = psycopg.conninfo.conninfo_to_dict(psycopg.conninfo.make_conninfo(conninfo, **libpq))
        if params.get("service") or params.get("hostaddr"):
            raise DisposableEndpointRefused("disposable mode refuses service files and hostaddr overrides")
        check_disposable_endpoint(params.get("host"), params.get("port"))
        return original(cls, conninfo, **kwargs)
    guarded._trustlens_guard = True
    guarded._trustlens_original = original          # for tests that must prove a real socket would have been opened
    psycopg.Connection.connect = classmethod(guarded)
    psycopg.connect = psycopg.Connection.connect


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    connect_timeout: int = 5
    explicit_endpoint: bool = field(default=False, repr=False, compare=False)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None):
        env = os.environ if environment is None else environment
        if disposable_mode(env):
            # No defaults in disposable mode: a missing or misnamed variable must never become 127.0.0.1:55432.
            check_disposable_endpoint(env.get("TRUSTLENS_DB_HOST"), env.get("TRUSTLENS_DB_PORT"))
        try:
            port = int(env.get("TRUSTLENS_DB_PORT", "55432"))
        except ValueError:
            raise DatabaseConfigurationError("TRUSTLENS_DB_PORT must be an integer") from None
        if not 1 <= port <= 65535:
            raise DatabaseConfigurationError("TRUSTLENS_DB_PORT is out of range")
        values = [env.get(key, "") for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")]
        if not all(values):
            raise DatabaseConfigurationError("Set POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD outside Git")
        return cls(env.get("TRUSTLENS_DB_HOST", "127.0.0.1"), port, *values,
                   explicit_endpoint="TRUSTLENS_DB_HOST" in env and "TRUSTLENS_DB_PORT" in env)

    def _checked(self):
        if disposable_mode():
            if not self.explicit_endpoint:
                raise DisposableEndpointRefused("disposable mode accepts only settings built from explicit configuration")
            check_disposable_endpoint(self.host, self.port)

    def sqlalchemy_url(self):
        self._checked()
        return URL.create("postgresql+psycopg", username=self.user, password=self.password,
                          host=self.host, port=self.port, database=self.database)

    def connection_parameters(self):
        self._checked()
        return dict(host=self.host, port=self.port, dbname=self.database, user=self.user,
                    password=self.password, connect_timeout=self.connect_timeout)


def main():
    parser = argparse.ArgumentParser(description="Read-only local database SELECT 1 diagnostic")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    try:
        if args.env_file:
            path = guard_env_file(args.env_file)        # disposable mode: permanent files refused before any access
            if not path.is_file():
                raise DatabaseConfigurationError("External environment file is missing")
            load_dotenv(path, override=False)
        settings = DatabaseSettings.from_environment()
        with psycopg.connect(**settings.connection_parameters(), autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = '5s'")
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    return 1
    except PermanentConfigurationRefused:
        print("Database diagnostic refused: permanent configuration is not used in disposable test mode.")
        return 1
    except (DatabaseConfigurationError, psycopg.Error, OSError):
        print("Database diagnostic failed; verify the external environment and local PostgreSQL. Details suppressed.")
        return 1
    print("Database SELECT 1: PASS (read-only; credentials omitted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
