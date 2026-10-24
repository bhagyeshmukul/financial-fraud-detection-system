"""
Test routing, quality constraints, grouped scoring and model-choice audit behavior. Artificial
specialists provide known correct outcomes without making claims about bank traffic.
"""

import json
from uuid import uuid4
import numpy as np
import pandas as pd
import pytest
from src.evaluate import constrained_threshold, evaluate_probabilities
from src.routing import ModelRouter, choose_auto_policy, routed_probabilities


def result(recall, precision=0.85, eligible=True):
    """Build compact validation summaries to test policy selection directly."""
    return {
        "recall": recall,
        "precision": precision,
        "eligible": eligible,
        "average_precision": 0.7,
    }


@pytest.mark.parametrize(
    "router,expected",
    [
        (result(0.9), "router"),
        (result(0.8), "random_forest"),
        (result(0.95, eligible=False), "random_forest"),
    ],
)
def test_auto_requires_strict_eligible_recall_improvement(router, expected):
    """A tie or a precision failure must keep the stronger individual policy."""
    policy = choose_auto_policy(
        {"random_forest": result(0.8), "xgboost": result(0.7), "router": router}
    )
    assert policy["policy"] == expected


def test_auto_unavailable_without_an_eligible_individual():
    """An unsupported baseline must not become a misleading Auto fallback."""
    policy = choose_auto_policy(
        {"xgboost": result(0.9, eligible=False), "router": result(0.95)}
    )
    assert policy["available"] is False


def test_threshold_matches_brute_force_and_includes_equal_scores():
    """Compare efficient threshold selection against every possible operating point."""
    labels = np.r_[np.ones(10), np.zeros(190)]
    probabilities = np.r_[np.linspace(0.4, 0.95, 10), [0.7, 0.7], np.full(188, 0.05)]
    threshold, eligible = constrained_threshold(labels, probabilities)
    possibilities = [
        evaluate_probabilities(labels, probabilities, value)
        for value in np.unique(probabilities)
    ]
    valid = [
        item
        for item in possibilities
        if item["precision"] >= 0.8 and item["accuracy"] >= 0.94
    ]
    best = max(
        valid, key=lambda item: (item["recall"], item["precision"], item["threshold"])
    )
    assert eligible
    assert threshold == best["threshold"]
    assert evaluate_probabilities(labels, probabilities, threshold)["precision"] >= 0.8


def test_impossible_quality_goal_is_explicitly_ineligible():
    """Identical uninformative scores cannot satisfy a rare-fraud precision floor."""
    _, eligible = constrained_threshold([0] * 99 + [1], [0.5] * 100)
    assert eligible is False


def test_router_learns_context_and_scores_only_selected_groups():
    """Known artificial specialists make routing, determinism and ordering observable."""
    features = pd.DataFrame(
        {"amount": np.repeat([10.0, 100.0], 1000), "category": ["food"] * 2000}
    )
    labels = (np.arange(2000) % 20 == 0).astype(int)
    ideal = np.where(labels == 1, 0.9, 0.1)
    first = np.where(features.amount < 50, ideal, 1 - ideal)
    second = 1 - first
    router = ModelRouter().fit(features, labels, {"first": first, "second": second})
    query = pd.DataFrame(
        {"amount": [100.0, 10.0, 100.0], "category": ["unseen", "food", "food"]}
    )
    selected, _ = router.choose(query)
    assert selected.tolist() == ["second", "first", "second"]
    np.testing.assert_array_equal(selected, router.choose(query)[0])
    calls = []

    class Expert:
        """Record queried positions while returning a recognizable probability."""

        def __init__(self, name, score):
            """Save the controlled values needed by this small test helper."""
            self.name, self.score = name, score

        def predict_proba(self, rows):
            """Return a two-column legitimate/fraud probability array for controlled test assertions."""
            calls.append((self.name, rows.index.tolist()))
            return np.tile([1 - self.score, self.score], (len(rows), 1))

    probabilities, _, _ = routed_probabilities(
        router, {"first": Expert("first", 0.2), "second": Expert("second", 0.8)}, query
    )
    np.testing.assert_allclose(probabilities, [0.8, 0.2, 0.8])
    assert calls == [("first", [1]), ("second", [0, 2])]
    assert router.pipeline.named_steps["tree"].get_depth() <= 3
    assert router.pipeline.named_steps["tree"].min_samples_leaf == 200


def test_router_rejects_one_class_training():
    """Fail clearly instead of dividing by a missing class count."""
    with pytest.raises(ValueError, match="both"):
        ModelRouter().fit(
            pd.DataFrame({"amount": [1, 2]}), [0, 0], {"expert": [0.1, 0.2]}
        )


def test_manual_and_auto_choices_are_audited_and_retry_safe(
    client, fake_scoring, bank_payload
):
    """The requested policy survives storage, retries, review output and CSV export."""
    session = client.post("/api/v1/sessions", json={"profile": "banksim"}).json()["id"]
    payload = {
        "session_id": session,
        "request_id": str(uuid4()),
        "transaction": bank_payload,
        "model_choice": "auto",
    }
    route = "/api/v1/profiles/banksim/predictions"
    original = client.post(route, json=payload)
    assert original.status_code == 200
    assert original.json()["requested_model"] == "auto"
    assert original.json()["used_model"] == "random_forest"
    assert client.post(route, json=payload).json() == original.json()
    assert (
        client.post(route, json={**payload, "model_choice": "xgboost"}).status_code
        == 409
    )
    logs = client.get("/api/v1/predictions", params={"session_id": session}).json()
    assert logs[0]["used_model"] == "random_forest"
    exported = client.get(
        "/api/v1/predictions/export", params={"session_id": session}
    ).text
    assert (
        "requested_model,used_model,router_version,routing_status,decision_threshold"
        in exported
    )
    assert "random_forest" in exported
    assert (
        client.post(route, json={**payload, "model_choice": "../../bad"}).status_code
        == 422
    )


def test_csv_choice_is_preserved_and_changed_choice_conflicts(client, fake_scoring):
    """Multipart requests obey the same model-choice idempotency contract."""
    session = client.post("/api/v1/sessions", json={"profile": "banksim"}).json()["id"]
    data = {
        "session_id": session,
        "request_id": str(uuid4()),
        "model_choice": "random_forest",
    }
    files = {
        "file": (
            "sample.csv",
            b"step,customer,merchant,category,amount,fraud\n1,C,M,food,100,1\n",
            "text/csv",
        )
    }
    route = "/api/v1/profiles/banksim/batch-predictions"
    response = client.post(route, data=data, files=files)
    assert response.status_code == 200
    assert response.json()["used_models"] == {"random_forest": 1}
    assert client.post(route, data=data, files=files).json() == response.json()
    assert (
        client.post(
            route, data={**data, "model_choice": "auto"}, files=files
        ).status_code
        == 409
    )
