"""
Resolve the database address and configure SQLAlchemy connections. A connection reaches an
existing database; Alembic separately manages the tables inside it.
"""

import os
from sqlalchemy import create_engine


def get_database_url():
    """Read DATABASE_URL or use the documented loopback development default; never print credentials."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://fraud_user:fraud_password@localhost:5432/fraud_db",
    )


def create_db_engine(url=None):
    """
    Configure a reusable SQLAlchemy connection pool, with SQLite-specific options only for local
    unit tests.
    """
    url = url or get_database_url()
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    else:
        options.update(pool_size=5, max_overflow=5, connect_args={"connect_timeout": 5})
    return create_engine(url, **options)


engine = create_db_engine()
