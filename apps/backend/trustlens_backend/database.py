"""Explicit, read-only database diagnostic; configuration is never logged."""
import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import psycopg
from dotenv import load_dotenv
from sqlalchemy.engine import URL


class DatabaseConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)
    connect_timeout: int = 5

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None):
        env = os.environ if environment is None else environment
        try:
            port = int(env.get("TRUSTLENS_DB_PORT", "55432"))
        except ValueError:
            raise DatabaseConfigurationError("TRUSTLENS_DB_PORT must be an integer") from None
        if not 1 <= port <= 65535:
            raise DatabaseConfigurationError("TRUSTLENS_DB_PORT is out of range")
        values = [env.get(key, "") for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")]
        if not all(values):
            raise DatabaseConfigurationError("Set POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD outside Git")
        return cls(env.get("TRUSTLENS_DB_HOST", "127.0.0.1"), port, *values)

    def sqlalchemy_url(self):
        return URL.create("postgresql+psycopg", username=self.user, password=self.password,
                          host=self.host, port=self.port, database=self.database)

    def connection_parameters(self):
        return dict(host=self.host, port=self.port, dbname=self.database, user=self.user,
                    password=self.password, connect_timeout=self.connect_timeout)


def main():
    parser = argparse.ArgumentParser(description="Read-only local database SELECT 1 diagnostic")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    try:
        if args.env_file:
            path = args.env_file.expanduser()
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
    except (DatabaseConfigurationError, psycopg.Error, OSError):
        print("Database diagnostic failed; verify the external environment and local PostgreSQL. Details suppressed.")
        return 1
    print("Database SELECT 1: PASS (read-only; credentials omitted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
