"""Data cleaning, splitting, scaling, and class-balancing utilities."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.utils import FEATURE_COLUMNS


@dataclass
class PreprocessArtifacts:
    X_train_resampled: pd.DataFrame
    y_train_resampled: pd.Series
    X_test_scaled: pd.DataFrame
    y_test: pd.Series
    scaler: StandardScaler


def preprocess_data(df: pd.DataFrame, random_state: int = 42) -> PreprocessArtifacts:
    """Prepare train/test artifacts used by training and evaluation routines."""
    cleaned = df.copy()
    cleaned = cleaned.drop_duplicates()
    numeric_medians = cleaned.median(numeric_only=True)
    cleaned = cleaned.where(~cleaned.isna(), numeric_medians, axis=1)

    X = cleaned[FEATURE_COLUMNS]
    y = cleaned["Class"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=random_state,
    )

    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train), columns=FEATURE_COLUMNS, index=X_train.index
    )
    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test), columns=FEATURE_COLUMNS, index=X_test.index
    )

    try:
        from imblearn.over_sampling import SMOTE

        smote = SMOTE(random_state=random_state)
        X_train_resampled, y_train_resampled = smote.fit_resample(X_train_scaled, y_train)
    except Exception:
        X_train_resampled, y_train_resampled = X_train_scaled, y_train

    return PreprocessArtifacts(
        X_train_resampled=X_train_resampled,
        y_train_resampled=y_train_resampled,
        X_test_scaled=X_test_scaled,
        y_test=y_test,
        scaler=scaler,
    )
