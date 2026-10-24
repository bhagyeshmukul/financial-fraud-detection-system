"""
Separate historical time windows and assemble training-only preprocessing. Imputation, scaling
and SMOTE learn from fitting rows rather than future evaluation data.
"""

from dataclasses import dataclass
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE, SMOTENC
from imblearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from src.features import BANK_NUMERIC
from src.profiles import get_profile


@dataclass
class Partitions:
    """
    Hold row indices for five ordered, non-overlapping time windows; no transactions are
    shuffled between them.
    """

    fit: np.ndarray
    calibration: np.ndarray
    router_training: np.ndarray
    validation: np.ndarray
    test: np.ndarray


def chronological_split(frame: pd.DataFrame, profile: str) -> Partitions:
    """
    Split distinct time groups at 40/50/60/80 percent and require both fraud classes in every
    window.
    """
    specification = get_profile(profile)
    timeline = np.sort(frame[specification.time].unique())
    # Split timestamps, not individual rows, so a single day cannot straddle two windows.
    if len(timeline) < 20:
        raise ValueError(
            "At least 20 distinct time steps are required for temporal evaluation."
        )
    fit_end, calibration_end, router_end, validation_end = [
        timeline[int(len(timeline) * fraction)] for fraction in (0.40, 0.50, 0.60, 0.80)
    ]
    time = frame[specification.time].to_numpy()
    partitions = Partitions(
        np.flatnonzero(time < fit_end),
        np.flatnonzero((time >= fit_end) & (time < calibration_end)),
        np.flatnonzero((time >= calibration_end) & (time < router_end)),
        np.flatnonzero((time >= router_end) & (time < validation_end)),
        np.flatnonzero(time >= validation_end),
    )
    # Reject an unusable time window instead of changing future labels or shuffling away the problem.
    for name, indices in vars(partitions).items():
        if frame.iloc[indices][specification.target].nunique() != 2:
            raise ValueError(
                f"{name} partition must contain both classes; do not alter test labels to fix this."
            )
    return partitions


def model_pipeline(
    profile: str, feature_columns, estimator, resample=True, minority_count=10
):
    """
    Assemble imputation, scaling, appropriate training-only SMOTE, category encoding and the
    chosen classifier.
    """
    numeric = list(feature_columns) if profile == "credit_card" else BANK_NUMERIC
    numeric_pipeline = Pipeline(
        [("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
    )
    transformers = [("numeric", numeric_pipeline, numeric)]
    if profile == "banksim":
        transformers.append(
            (
                "category",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                ["category"],
            )
        )
    steps = [("prepare", ColumnTransformer(transformers, sparse_threshold=0))]
    # imblearn Pipeline resamples on fit only; predict_proba never creates synthetic payments.
    if resample:
        if minority_count < 2:
            raise ValueError(
                "SMOTE requires at least two fraud examples in the fitting partition."
            )
        parameters = dict(
            random_state=42,
            sampling_strategy="auto",
            k_neighbors=min(5, minority_count - 1),
        )
        sampler = (
            SMOTE(**parameters)
            if profile == "credit_card"
            else SMOTENC(categorical_features=[len(numeric)], **parameters)
        )
        steps.append(("balance", sampler))
    if profile == "banksim":
        # SMOTENC sees categorical codes first; one-hot columns are created afterward.
        steps.append(
            (
                "encode",
                ColumnTransformer(
                    [
                        ("numeric", "passthrough", list(range(len(numeric)))),
                        (
                            "category",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                            [len(numeric)],
                        ),
                    ],
                    sparse_threshold=0,
                ),
            )
        )
    steps.append(("model", estimator))
    return Pipeline(steps)
