"""
Connect Alembic migrations to the configured database and ORM table metadata. Online mode
applies changes; offline mode produces SQL without connecting.
"""

from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.db.database import get_database_url
from app.db.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_database_url().replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline():
    """Generate migration SQL using configured metadata without opening a database connection."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Connect to an existing database and run pending schema revisions in a transaction."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
