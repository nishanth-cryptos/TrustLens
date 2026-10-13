"""Trusted principal and role state (DATA-001-WP2 principal_reference / role_assignment).

A validated external identity becomes a TrustLens principal only through explicit provisioning; signing in never
creates a principal or grants a role. Roles are read from PostgreSQL on every protected request, so a revocation or
deactivation takes effect immediately.
"""
from dataclasses import dataclass
from typing import Protocol

import psycopg

from .database import DatabaseSettings

ROLES = ("USER", "ANALYST", "KNOWLEDGE_EDITOR", "KNOWLEDGE_APPROVER", "ADMINISTRATOR")
APP_RUNTIME_ROLE = "tl_app_runtime"
SCHEMA = "trustlens"


class PrincipalStoreUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Principal:
    principal_reference_id: str
    principal_kind: str
    roles: tuple[str, ...]


class PrincipalStore(Protocol):
    def find_active(self, issuer: str, subject: str) -> Principal | None: ...

    def get_active(self, principal_reference_id: str) -> Principal | None: ...


def _select_roles(where: str) -> str:
    return ("SELECT p.principal_reference_id::text, p.principal_kind,"
            " coalesce(array_agg(r.role ORDER BY r.role) FILTER (WHERE r.role IS NOT NULL), ARRAY[]::text[])"
            f" FROM {SCHEMA}.principal_reference p"
            f" LEFT JOIN {SCHEMA}.role_assignment r"
            " ON r.principal_reference_id = p.principal_reference_id AND r.revoked_at IS NULL AND r.effective_from <= now()"
            f" WHERE p.status = 'ACTIVE' AND {where}"
            " GROUP BY p.principal_reference_id, p.principal_kind")


class PostgresPrincipalStore:
    """Request-path reads with the least-privileged tl_app_runtime role only; never DDL, never a migration role."""

    def __init__(self, settings: DatabaseSettings):
        if settings.user != APP_RUNTIME_ROLE:
            raise PrincipalStoreUnavailable("The application must connect as tl_app_runtime")
        self._settings = settings

    def _query(self, where: str, params: tuple) -> Principal | None:
        try:
            with psycopg.connect(**self._settings.connection_parameters(), autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET statement_timeout = '5s'")
                    cursor.execute(_select_roles(where), params)
                    row = cursor.fetchone()
        except psycopg.Error:
            raise PrincipalStoreUnavailable("principal store unavailable") from None
        if row is None:
            return None
        roles = tuple(r for r in ROLES if r in set(row[2]))
        if not roles or row[1] != "HUMAN":
            return None      # a principal with no active role, or a workload, has no browser session
        return Principal(row[0], row[1], roles)

    def find_active(self, issuer: str, subject: str) -> Principal | None:
        return self._query("p.external_issuer = %s AND p.external_subject = %s", (issuer, subject))

    def get_active(self, principal_reference_id: str) -> Principal | None:
        return self._query("p.principal_reference_id = %s::uuid", (principal_reference_id,))
