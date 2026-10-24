"""
Verify migrations preserve legacy data on SQLite and PostgreSQL. Temporary databases or schemas
keep migration experiments away from the application’s saved records.
"""

import os
import uuid
import pytest
from sqlalchemy.engine import make_url
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_migrations_preserve_legacy_rows(tmp_path, monkeypatch):
    """Verify migrations preserve legacy rows."""
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    configuration = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(Path(__file__).parents[1] / "alembic")
    )
    command.upgrade(configuration, "001")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO fraud_prediction_logs (transaction_amount, fraud_probability, prediction_label, risk_level, model_version, request_payload) VALUES (12,0.2,'Not Fraud','Low','legacy','{}')"
            )
        )
    command.upgrade(configuration, "head")
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT profile, model_version, review_state FROM fraud_prediction_logs"
            )
        ).one()
        assert tuple(row) == ("credit_card", "legacy", "open")
    assert "review_events" in inspect(engine).get_table_names()
    command.downgrade(configuration, "001")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT COUNT(*) FROM fraud_prediction_logs")
            ).scalar()
            == 1
        )
    engine.dispose()


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL for PostgreSQL migration verification",
)
def test_postgresql_migration_preserves_legacy_records(monkeypatch):
    """Verify postgresql migration preserves legacy records."""
    database_url = os.environ["TEST_DATABASE_URL"]
    base = create_engine(database_url)
    schema = "migration_" + uuid.uuid4().hex
    with base.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped_url = (
        make_url(database_url)
        .update_query_dict({"options": "-csearch_path=" + schema})
        .render_as_string(hide_password=False)
    )
    monkeypatch.setenv("DATABASE_URL", scoped_url)
    configuration = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    configuration.set_main_option(
        "script_location", str(Path(__file__).parents[1] / "alembic")
    )
    scoped = create_engine(scoped_url)
    try:
        command.upgrade(configuration, "001")
        with scoped.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO fraud_prediction_logs (transaction_amount, fraud_probability, prediction_label, risk_level, model_version, request_payload) VALUES (12,0.2,'Not Fraud','Low','legacy','{}')"
                )
            )
        command.upgrade(configuration, "head")
        with scoped.connect() as connection:
            assert tuple(
                connection.execute(
                    text(
                        "SELECT profile, model_version, review_state FROM fraud_prediction_logs"
                    )
                ).one()
            ) == ("credit_card", "legacy", "open")
    finally:
        scoped.dispose()
        with base.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        base.dispose()
