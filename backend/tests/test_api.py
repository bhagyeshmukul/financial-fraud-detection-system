"""
Exercise public HTTP behavior including validation, history isolation, retries and security.
Predictions use an explicit fake scorer so these are application tests, not accuracy
measurements.
"""

import io
import json
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.db.models import FraudPredictionLog
from app.services.fraud_service import score_and_log


def new_session(client, profile="banksim", seeded=False):
    """
    Create a test analysis session through the real API and return its response for later
    assertions.
    """
    response = client.post(
        "/api/v1/sessions", json={"profile": profile, "seeded": seeded}
    )
    assert response.status_code == 201
    return response.json()["id"]


def envelope(session, payload, identifier=None):
    """Build a valid test prediction request with a fresh or explicitly supplied retry identifier."""
    return {
        "session_id": session,
        "request_id": identifier or str(uuid4()),
        "transaction": payload,
    }


def test_prediction_retry_review_and_filters(client, fake_scoring, bank_payload):
    """Verify prediction retry review and filters."""
    session = new_session(client)
    body = envelope(session, bank_payload)
    first = client.post("/api/v1/profiles/banksim/predictions", json=body)
    assert first.status_code == 200, first.text
    assert first.json()["prediction_label"] == "Fraud"
    second = client.post("/api/v1/profiles/banksim/predictions", json=body)
    assert first.json() == second.json()
    body["transaction"]["amount"] = 1
    assert (
        client.post("/api/v1/profiles/banksim/predictions", json=body).status_code
        == 409
    )
    identifier = first.json()["id"]
    reviewed = client.patch(
        f"/api/v1/predictions/{identifier}/review",
        json={"state": "under_review", "notes": "Investigate source."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_state"] == "under_review"
    assert len(client.get(f"/api/v1/predictions/{identifier}/reviews").json()) == 1
    assert (
        len(
            client.get(
                "/api/v1/predictions",
                params={"session_id": session, "risk": "High", "state": "under_review"},
            ).json()
        )
        == 1
    )
    assert (
        client.get(
            "/api/v1/predictions", params={"session_id": session, "risk": "Low"}
        ).json()
        == []
    )
    exported = client.get("/api/v1/predictions/export", params={"session_id": session})
    assert "Investigate source." in exported.text


def test_legacy_route_preserved(client, fake_scoring, card_payload):
    """Verify legacy route preserved."""
    response = client.post("/predict-fraud", json=card_payload)
    assert response.status_code == 200
    assert response.json()["profile"] == "credit_card"
    assert isinstance(client.get("/prediction-logs").json(), list)


def test_sessions_do_not_share_behaviour(client, fake_scoring, bank_payload):
    """Verify sessions do not share behaviour."""
    first, second = new_session(client), new_session(client)
    client.post(
        "/api/v1/profiles/banksim/predictions", json=envelope(first, bank_payload)
    )
    bank_payload["step"] += 1
    a = client.post(
        "/api/v1/profiles/banksim/predictions", json=envelope(first, bank_payload)
    ).json()
    b = client.post(
        "/api/v1/profiles/banksim/predictions", json=envelope(second, bank_payload)
    ).json()
    assert "1 earlier payments" in a["context"][0]
    assert "0 earlier payments" in b["context"][0]


@pytest.mark.parametrize(
    "change",
    [
        {"amount": -1},
        {"step": -1},
        {"step": 1.5},
        {"amount": "nan"},
        {"customer": ""},
        {"fraud": 1},
    ],
)
def test_invalid_inputs_do_not_create_audit_records(
    client, fake_scoring, bank_payload, change
):
    """Verify invalid inputs do not create audit records."""
    session = new_session(client)
    bank_payload.update(change)
    result = client.post(
        "/api/v1/profiles/banksim/predictions", json=envelope(session, bank_payload)
    )
    assert result.status_code == 422
    assert (
        client.get("/api/v1/predictions", params={"session_id": session}).json() == []
    )


def test_profile_session_mismatch(client, fake_scoring, card_payload):
    """Verify profile session mismatch."""
    session = new_session(client)
    assert (
        client.post(
            "/api/v1/profiles/credit_card/predictions",
            json=envelope(session, card_payload),
        ).status_code
        == 409
    )


def test_labelled_csv_and_retry(client, fake_scoring):
    """Verify labelled csv and retry."""
    session = new_session(client)
    fields = {"session_id": session, "request_id": str(uuid4())}
    content = "step,customer,merchant,category,amount,fraud\n1,C,M,food,10,0\n2,C,M,travel,100,1\n"
    first = client.post(
        "/api/v1/profiles/banksim/batch-predictions",
        data=fields,
        files={"file": ("rows.csv", content, "text/csv")},
    )
    assert first.status_code == 200, first.text
    assert first.json()["evaluation"]["accuracy"] == 1.0
    second = client.post(
        "/api/v1/profiles/banksim/batch-predictions",
        data=fields,
        files={"file": ("rows.csv", content, "text/csv")},
    )
    assert second.json() == first.json()
    assert "2 rows" not in str(first.json()["results"])
    assert all(
        "fraud" not in entry["derived_features"] for entry in first.json()["results"]
    )


def test_original_banksim_columns_and_quotes_are_normalized(client, fake_scoring):
    """Verify original banksim columns and quotes are normalized."""
    session = new_session(client)
    content = "step,customer,merchant,category,amount,fraud,age,gender,zipcodeOri,zipMerchant\n1,'C1','M1','es_travel',100,1,3,M,28007,28007\n"
    result = client.post(
        "/api/v1/profiles/banksim/batch-predictions",
        data={"session_id": session, "request_id": str(uuid4())},
        files={"file": ("publisher.csv", content, "text/csv")},
    )
    assert result.status_code == 200
    assert result.json()["results"][0]["derived_features"]["category"] == "es_travel"
    assert "age" not in result.json()["results"][0]["derived_features"]


@pytest.mark.parametrize(
    "content",
    [
        "step,customer,merchant,category,amount\n",
        "step,customer,merchant,category,amount\n1,C,M,food,\n",
        "step,customer,merchant,category,amount,extra\n1,C,M,food,1,1\n",
        "step,step,customer,merchant,category,amount\n1,1,C,M,food,1\n",
    ],
)
def test_bad_csv_rejected_atomically(client, fake_scoring, content):
    """Verify bad csv rejected atomically."""
    session = new_session(client)
    result = client.post(
        "/api/v1/profiles/banksim/batch-predictions",
        data={"session_id": session, "request_id": str(uuid4())},
        files={"file": ("bad.csv", content, "text/csv")},
    )
    assert result.status_code == 422


def test_oversized_upload(client):
    """Verify oversized upload."""
    result = client.post(
        "/api/v1/profiles/banksim/batch-predictions",
        data={"session_id": str(uuid4()), "request_id": str(uuid4())},
        files={"file": ("big.csv", b"x" * (5 * 1024 * 1024 + 1), "text/csv")},
    )
    assert result.status_code == 413


def test_private_production_api(client, monkeypatch):
    """Verify private production api."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_ACCESS_TOKEN", "x" * 32)
    assert client.get("/api/v1/profiles").status_code == 401
    assert (
        client.get(
            "/api/v1/profiles", headers={"Authorization": "Bearer " + "x" * 32}
        ).status_code
        == 200
    )
    assert client.get("/health/live").status_code == 200


def test_missing_models_return_503(client, monkeypatch, card_payload):
    """Verify missing models return 503."""
    from src.predict import ModelUnavailable

    def unavailable(*args, **kwargs):
        """
        Raise a deliberate missing-model error to verify that the HTTP layer reports 503 without
        training.
        """
        raise ModelUnavailable("Import data and train the model.")

    monkeypatch.setattr("app.services.fraud_service.predict_rows", unavailable)
    assert client.post("/predict-fraud", json=card_payload).status_code == 503


def test_nonfinite_legacy_json_is_a_readable_validation_error(client, card_payload):
    """Verify nonfinite legacy json is a readable validation error."""
    card_payload["V1"] = float("nan")
    response = client.post(
        "/predict-fraud",
        content=json.dumps(card_payload),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "finite" in response.text


def test_export_escapes_spreadsheet_formula(client, fake_scoring, bank_payload):
    """Verify export escapes spreadsheet formula."""
    session = new_session(client)
    result = client.post(
        "/api/v1/profiles/banksim/predictions", json=envelope(session, bank_payload)
    ).json()
    client.patch(
        f"/api/v1/predictions/{result['id']}/review",
        json={"state": "closed", "notes": "=1+1"},
    )
    assert (
        "'=1+1"
        in client.get("/api/v1/predictions/export", params={"session_id": session}).text
    )


@pytest.mark.parametrize("profile", ["credit_card", "banksim"])
def test_concurrent_retries_write_one_prediction(
    postgres_committed_database, fake_scoring, card_payload, bank_payload, profile
):
    """Verify concurrent retries write one prediction."""
    from concurrent.futures import ThreadPoolExecutor
    from app.services.fraud_service import create_session
    from sqlalchemy import func

    factory = postgres_committed_database
    with factory() as db:
        session = create_session(db, profile)["id"]
    identifier = str(uuid4())
    payload = card_payload if profile == "credit_card" else bank_payload

    def score(_):
        """
        Return controlled fake predictions with real shared features; this rule is not the
        trained fraud model.
        """
        with factory() as db:
            return score_and_log(db, profile, session, identifier, [payload])

    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(score, range(8)))
    assert all(result == results[0] for result in results)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(FraudPredictionLog)) == 1
