import os

from sqlalchemy import create_engine


def get_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://fraud_user:fraud_password@localhost:5432/fraud_db",
    )


DATABASE_URL = get_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
