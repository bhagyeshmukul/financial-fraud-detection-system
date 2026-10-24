"""
Train small explicit fixtures to verify artifacts, partitions and serving parity. Real benchmark
training is a separate recorded experiment.
"""

import json
import stat
import joblib
import pytest
from conftest import fixture_data
from src.train import train_and_select_best_model
from src.features import build_features
from src.evaluate import evaluate_probabilities


@pytest.mark.parametrize("profile", ["credit_card", "banksim"])
def test_all_cv_models_trained_and_report_matches_artifact(
    tmp_path, profile, monkeypatch
):
    """Verify all cv models trained and report matches artifact."""
    models, reports = tmp_path / "models", tmp_path / "reports"
    report = train_and_select_best_model(
        profile,
        frame=fixture_data(profile),
        manifest={
            "source": "test fixture, never a CV benchmark",
            "synthetic_fixture": True,
        },
        output_models=models,
        output_reports=reports,
        quick=True,
    )
    assert {"logistic_regression", "random_forest", "xgboost"}.issubset(
        report["models"]
    )
    pointer = json.loads((models / f"{profile}.current.json").read_text())
    assert stat.S_IMODE((models / f"{profile}.current.json").stat().st_mode) == 0o644
    artifact = joblib.load(models / pointer["model"])
    assert artifact["model_version"] == report["model_version"]
    assert artifact["decision_threshold"] == report["decision_threshold"]
    assert (
        report["partitions"]["validation"]["end"]
        < report["partitions"]["test"]["start"]
    )
    assert report["dataset"]["synthetic_fixture"] is True
    assert any(name.endswith("_without_resampling") for name in report["models"])
    assert "router_training" in report["partitions"]
    assert "router" in report["models"]
    router = joblib.load(models / pointer["router"])["model"]
    assert set(router.candidate_names) == set(pointer["candidates"])
    assert (
        "fraud" not in router.feature_columns and "Class" not in router.feature_columns
    )
    assert (
        report["partitions"]["calibration"]["end"]
        < report["partitions"]["router_training"]["start"]
    )
    assert (
        report["partitions"]["router_training"]["end"]
        < report["partitions"]["validation"]["start"]
    )
    assert artifact["model"].predict_proba(
        build_features(fixture_data(profile).iloc[:3], profile)
    ).shape == (3, 2)
    # Exercise saved-artifact loading and the live routing branch, not just fitting.
    from src.predict import ModelUnavailable, load_model_artifact, predict_rows

    monkeypatch.setattr("src.predict.MODELS_DIR", models)
    load_model_artifact.cache_clear()
    try:
        inputs = fixture_data(profile).iloc[:3]
        manual = predict_rows(inputs, profile, model_choice="random_forest")
        assert all(row["used_model"] == "random_forest" for row in manual)
        # Force promotion only inside this synthetic test run to cover routed serving.
        pointer["auto_policy"] = {
            "available": True,
            "policy": "router",
            "reason": "Explicit fixture branch coverage, not a quality claim.",
        }
        (models / f"{profile}.current.json").write_text(json.dumps(pointer))
        routed = predict_rows(inputs, profile, model_choice="auto")
        expected, _ = router.choose(build_features(inputs, profile))
        assert [row["used_model"] for row in routed] == expected.tolist()
        assert all(
            row["routing_status"] == "routed"
            and row["router_version"] == report["model_version"]
            for row in routed
        )
        # Losing a required controller must fail, not quietly change the decision.
        (models / pointer["router"]).unlink()
        load_model_artifact.cache_clear()
        with pytest.raises(ModelUnavailable, match="Cannot load"):
            predict_rows(inputs, profile, model_choice="auto")
    finally:
        load_model_artifact.cache_clear()


def test_metrics_use_exact_serving_threshold():
    """Verify metrics use exact serving threshold."""
    metrics = evaluate_probabilities([0, 1], [0.6, 0.8], 0.8)
    assert metrics["confusion_matrix"] == [[1, 0], [0, 1]]
    assert metrics["accuracy"] == 1


def test_inference_thread_budget_preserves_probabilities():
    """Verify inference thread budget preserves probabilities."""
    import numpy as np

    # This check is independent of benchmark quality; use a trained test fixture below.
    from sklearn.calibration import CalibratedClassifierCV
    from src.train import estimators
    from src.preprocessing import model_pipeline

    frame = fixture_data("credit_card")
    features = build_features(frame, "credit_card")
    pipeline = model_pipeline(
        "credit_card", features.columns, estimators(True)["xgboost"], resample=False
    )
    pipeline.fit(features.iloc[:300], frame.Class.iloc[:300])
    model = CalibratedClassifierCV(pipeline, cv="prefit").fit(
        features.iloc[300:400], frame.Class.iloc[300:400]
    )
    before = model.predict_proba(features.iloc[400:])
    model.calibrated_classifiers_[0].estimator.set_params(model__n_jobs=1)
    np.testing.assert_array_equal(before, model.predict_proba(features.iloc[400:]))
