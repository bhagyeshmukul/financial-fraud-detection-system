from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, engine_from_config, exc, pool, text
from sqlalchemy.engine.url import make_url

from app.db.database import get_database_url
from app.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_database_url())
target_metadata = Base.metadata


def ensure_database_exists() -> None:
    database_url = config.get_main_option("sqlalchemy.url")
    url = make_url(database_url)

    database_name = url.database
    if not database_name:
        return

    backend_name = url.get_backend_name()
    if backend_name == "sqlite":
        return

    if backend_name == "postgresql":
        admin_url = url.set(database="postgres")
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with admin_engine.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        except exc.ProgrammingError as error:
            pg_error_code = getattr(getattr(error, "orig", None), "pgcode", None)
            if pg_error_code != "42P04":
                raise
        finally:
            admin_engine.dispose()
        return

    if backend_name == "mysql":
        admin_url = url.set(database=None)
        admin_engine = create_engine(admin_url)
        try:
            with admin_engine.connect() as connection:
                connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{database_name}`"))
                connection.commit()
        finally:
            admin_engine.dispose()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    ensure_database_exists()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
