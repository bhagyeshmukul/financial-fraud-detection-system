"""
Provide reusable test transactions, isolated databases and explicit synthetic fixtures. These
fixtures verify program behavior and must never be reported as benchmark accuracy.
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.models import Base
from app.db.session import get_db
from app.main import app
from src.utils import FEATURE_COLUMNS


@pytest.fixture
def card_payload():
    """Provide one valid anonymized-card input covering all original 30 feature fields."""
    return {key: (20.0 if key == "Amount" else 1.0) for key in FEATURE_COLUMNS}


@pytest.fixture
def bank_payload():
    """Provide one valid readable BankSim payment shared by application tests."""
    return {
        "step": 5,
        "customer": "C1",
        "merchant": "M1",
        "category": "es_travel",
        "amount": 100.0,
    }


@pytest.fixture
def database(tmp_path):
    """Give a test an isolated SQLAlchemy transaction and undo its records afterward."""
    url = os.getenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    options = (
        {"connect_args": {"check_same_thread": False}}
        if url.startswith("sqlite")
        else {}
    )
    engine = create_engine(url, **options)
    Base.metadata.create_all(engine)
    connection = engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    yield factory
    transaction.rollback()
    connection.close()
    engine.dispose()


@pytest.fixture
def client(database, monkeypatch):
    """
    Create a FastAPI test client with its database dependency overridden and production secrets
    removed.
    """
    monkeypatch.delenv("API_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    def dependency():
        """Yield the test database session in place of the production HTTP dependency."""
        with database() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def fake_scoring(monkeypatch):
    """
    Replace real inference with a named test-only scoring rule so API behavior can be asserted
    exactly.
    """

    def score(frame, profile, history=None, seed_before=None, model_choice="champion"):
        """
        Return controlled fake predictions with real shared features; this rule is not the
        trained fraud model.
        """
        from src.features import build_features, describe_context
        from src.utils import risk_from_probability

        features = build_features(frame, profile, history)
        result = []
        # Return one controlled fake score for each input, keeping the real shared feature-building path.
        for raw, derived in zip(frame.to_dict("records"), features.to_dict("records")):
            score = 0.9 if raw.get("amount", raw.get("Amount", 0)) > 80 else 0.1
            result.append(
                {
                    "prediction_label": "Fraud" if score >= 0.7 else "Not Fraud",
                    "fraud_probability": score,
                    "risk_level": risk_from_probability(score, 0.7),
                    "profile": profile,
                    "model_version": "explicit_test_fixture",
                    "decision_threshold": 0.7,
                    "review_threshold": 0.35,
                    "context": describe_context(derived, profile),
                    "derived_features": derived,
                    "requested_model": model_choice,
                    "used_model": "random_forest"
                    if model_choice == "auto"
                    else model_choice,
                    "router_version": "test_router" if model_choice == "auto" else None,
                    "routing_status": "routed" if model_choice == "auto" else "manual",
                    "routing_reason": "Explicit test fixture, not benchmark evidence.",
                }
            )
        return result

    monkeypatch.setattr("app.services.fraud_service.predict_rows", score)


def fixture_data(profile):
    """
    Create deterministic synthetic fixture rows containing both classes in every chronological
    test window.
    """
    random = np.random.default_rng(7)
    if profile == "credit_card":
        frame = pd.DataFrame(random.normal(size=(600, 30)), columns=FEATURE_COLUMNS)
        frame["Time"] = np.arange(600)
        frame["Amount"] = random.uniform(1, 100, 600)
        frame["Class"] = (np.arange(600) % 10 == 0).astype(int)
        frame["V1"] -= 6 * frame["Class"]
        return frame
    return pd.DataFrame(
        [
            {
                "step": day,
                "customer": f"C{index % 4}",
                "merchant": f"M{index % 3}",
                "category": "es_travel" if index % 10 == 0 else "es_food",
                "amount": float(200 if index % 10 == 0 else 10 + index),
                "fraud": int(index % 10 == 0),
            }
            for day in range(40)
            for index in range(20)
        ]
    )


@pytest.fixture
def postgres_committed_database():
    """Create a temporary PostgreSQL schema with committed records for real concurrent retry tests."""
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("Set TEST_DATABASE_URL for concurrent PostgreSQL verification")
    from sqlalchemy.engine import make_url
    from uuid import uuid4

    url = os.environ["TEST_DATABASE_URL"]
    admin = create_engine(url)
    schema = "concurrency_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": "-csearch_path=" + schema})
    engine = create_engine(scoped)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()
    with admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()
