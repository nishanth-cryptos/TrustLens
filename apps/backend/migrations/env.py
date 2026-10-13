"""Explicit SQL-first migration environment (ADR-0011).

Online execution requires the separate tl_schema_migrator role and serializes executors with an advisory lock; the
version table lives in the governed trustlens schema that the sponsor bootstrap creates. Offline mode only renders SQL.
"""
from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from trustlens_backend.database import DatabaseSettings

SCHEMA = "trustlens"
config = context.config
if not ScriptDirectory.from_config(config).get_heads():
    raise RuntimeError("No application revisions exist; add and review explicit SQL before migration execution")

settings = DatabaseSettings.from_environment()
if context.is_offline_mode():
    context.configure(url=settings.sqlalchemy_url(), target_metadata=None, literal_binds=True, version_table_schema=SCHEMA)
    with context.begin_transaction():
        context.run_migrations()
else:
    if settings.user != "tl_schema_migrator":
        raise RuntimeError("Application migrations require the separate tl_schema_migrator role")
    engine = create_engine(settings.sqlalchemy_url(), poolclass=NullPool, echo=False,
                           hide_parameters=True, connect_args={"connect_timeout": settings.connect_timeout})
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(8439271001)"))
        connection.commit()
        try:
            context.configure(connection=connection, target_metadata=None, version_table_schema=SCHEMA,
                              transaction_per_migration=True)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(8439271001)"))
            connection.commit()
    engine.dispose()
