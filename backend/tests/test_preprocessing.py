"""
Check temporal boundaries, history isolation and fitting-only transforms. These tests catch data
leakage even when an accidentally leaky pipeline appears accurate.
"""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from sklearn.linear_model import LogisticRegression
from src.features import build_features
from src.preprocessing import chronological_split, model_pipeline
from conftest import fixture_data


def test_earlier_days_only_and_labels_unused():
    """Verify earlier days only and labels unused."""
    rows = pd.DataFrame(
        [
            {
                "step": 1,
                "customer": "C",
                "merchant": "M",
                "category": "food",
                "amount": 10,
                "fraud": 0,
            },
            {
                "step": 2,
                "customer": "C",
                "merchant": "M",
                "category": "food",
                "amount": 20,
                "fraud": 1,
            },
            {
                "step": 2,
                "customer": "C",
                "merchant": "M",
                "category": "food",
                "amount": 9000,
                "fraud": 0,
            },
            {
                "step": 10,
                "customer": "C",
                "merchant": "M",
                "category": "food",
                "amount": 50,
                "fraud": 1,
            },
        ]
    )
    features = build_features(rows, "banksim")
    assert features.loc[1, "previous_mean_7d"] == 10
    assert features.loc[2, "previous_count_7d"] == 1
    assert features.loc[3, "previous_count_7d"] == 0
    changed = rows.copy()
    changed["fraud"] = 1 - changed["fraud"]
    assert_frame_equal(features, build_features(changed, "banksim"))
    assert_frame_equal(features.iloc[:2], build_features(rows.iloc[:2], "banksim"))
    assert features.loc[1, "new_merchant"] == 0


def test_batch_and_sequential_features_agree():
    """Verify batch and sequential features agree."""
    rows = fixture_data("banksim").drop(columns="fraud")
    full = build_features(rows, "banksim")
    earlier = rows[rows.step < 20]
    later = rows[rows.step >= 20]
    assert_frame_equal(
        full.loc[later.index].reset_index(drop=True),
        build_features(later, "banksim", earlier),
    )


@pytest.mark.parametrize("profile", ["credit_card", "banksim"])
def test_partitions_are_disjoint_and_chronological(profile):
    """Verify partitions are disjoint and chronological."""
    frame = fixture_data(profile)
    parts = chronological_split(frame, profile)
    column = "Time" if profile == "credit_card" else "step"
    groups = list(vars(parts).values())
    assert len(set(np.concatenate(groups))) == len(frame)
    # Check every adjacent pair of time windows rather than only their first and last rows.
    for before, after in zip(groups, groups[1:]):
        assert frame.iloc[before][column].max() < frame.iloc[after][column].min()


def test_smote_errors_are_not_silenced(monkeypatch):
    """Verify smote errors are not silenced."""
    frame = fixture_data("credit_card")
    features = build_features(frame, "credit_card")
    pipeline = model_pipeline(
        "credit_card", features.columns, LogisticRegression(), minority_count=60
    )

    def fail(*args, **kwargs):
        """Raise an intentional resampling error so the test can verify it is not silently ignored."""
        raise RuntimeError("intentional SMOTE failure")

    monkeypatch.setattr(pipeline.named_steps["balance"], "fit_resample", fail)
    with pytest.raises(RuntimeError, match="SMOTE failure"):
        pipeline.fit(features, frame.Class)


def test_imputation_does_not_learn_from_holdout():
    """Verify imputation does not learn from holdout."""
    frame = fixture_data("credit_card")
    features = build_features(frame, "credit_card")
    features.loc[0, "V2"] = np.nan
    pipeline = model_pipeline(
        "credit_card", features.columns, LogisticRegression(), resample=False
    )
    pipeline.fit(features.iloc[:300], frame.Class.iloc[:300])
    learned = (
        pipeline.named_steps["prepare"]
        .named_transformers_["numeric"]
        .named_steps["imputer"]
        .statistics_.copy()
    )
    features.loc[300:, "V2"] = 1e9
    pipeline.predict_proba(features.iloc[300:])
    np.testing.assert_array_equal(
        learned,
        pipeline.named_steps["prepare"]
        .named_transformers_["numeric"]
        .named_steps["imputer"]
        .statistics_,
    )
