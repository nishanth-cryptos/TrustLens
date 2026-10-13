"""Explicit SQL-first migration environment. S1 contains no application revisions."""
from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from trustlens_backend.database import DatabaseSettings

config = context.config
if not ScriptDirectory.from_config(config).get_heads():
    raise RuntimeError("No application revisions exist; add and review explicit SQL before migration execution")

settings = DatabaseSettings.from_environment()
if context.is_offline_mode():
    context.configure(url=settings.sqlalchemy_url(), target_metadata=None, literal_binds=True)
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
            context.configure(connection=connection, target_metadata=None)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(8439271001)"))
            connection.commit()
    engine.dispose()
