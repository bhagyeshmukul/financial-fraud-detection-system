"""
Verify serving refuses missing or mismatched saved artifacts. The API must report unavailable
models instead of training silently during a request.
"""

import json
import pytest
from src.predict import ModelUnavailable, load_model_artifact, model_report


def test_missing_artifact_never_trains(tmp_path, monkeypatch):
    """Verify missing artifact never trains."""
    monkeypatch.setattr("src.predict.MODELS_DIR", tmp_path)
    load_model_artifact.cache_clear()
    with pytest.raises(ModelUnavailable, match="No verified"):
        load_model_artifact("credit_card")
    assert not list(tmp_path.iterdir())
    load_model_artifact.cache_clear()


def test_mismatched_report_rejected(tmp_path, monkeypatch):
    """Verify mismatched report rejected."""
    monkeypatch.setattr("src.predict.MODELS_DIR", tmp_path)
    monkeypatch.setattr("src.predict.REPORTS_DIR", tmp_path)
    monkeypatch.setattr(
        "src.predict.load_model_artifact", lambda profile: {"model_version": "served"}
    )
    (tmp_path / "credit_card.current.json").write_text(
        json.dumps({"report": "report.json"})
    )
    (tmp_path / "report.json").write_text(json.dumps({"model_version": "different"}))
    with pytest.raises(ModelUnavailable, match="does not match"):
        model_report("credit_card")


def test_auto_missing_manifest_is_unavailable_not_an_internal_error(
    tmp_path, monkeypatch, card_payload
):
    """An Auto request must report an absent serving manifest as a dependency outage."""
    import pandas as pd
    from src.predict import predict_rows

    monkeypatch.setattr("src.predict.MODELS_DIR", tmp_path)
    with pytest.raises(ModelUnavailable, match="serving manifest"):
        predict_rows(pd.DataFrame([card_payload]), "credit_card", model_choice="auto")
