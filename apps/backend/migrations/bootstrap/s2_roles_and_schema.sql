-- TrustLens S2 one-time database bootstrap (sponsor-executed, outside Alembic, as the database owner/superuser).
-- Creates the two least-privileged login roles named by DATA-001-WP2 and an empty schema owned by the migrator.
-- No password appears here: set each one afterwards with psql's \password (SCRAM-hashed client-side, not echoed).
\set ON_ERROR_STOP on

CREATE ROLE tl_schema_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
CREATE ROLE tl_app_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

GRANT CONNECT ON DATABASE trustlens_dev TO tl_schema_migrator, tl_app_runtime;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE SCHEMA trustlens AUTHORIZATION tl_schema_migrator;
REVOKE ALL ON SCHEMA trustlens FROM PUBLIC;
GRANT USAGE ON SCHEMA trustlens TO tl_app_runtime;

-- The request path never sees DDL: tl_app_runtime owns nothing and cannot create objects in either schema.
ALTER ROLE tl_app_runtime SET search_path = trustlens;
ALTER ROLE tl_schema_migrator SET search_path = trustlens;
