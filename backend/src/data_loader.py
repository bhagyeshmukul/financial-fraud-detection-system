from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.datasets import make_classification

from src.utils import FEATURE_COLUMNS


def _build_synthetic_dataset(n_samples: int = 12000, random_state: int = 42) -> pd.DataFrame:
    feature_count = len(FEATURE_COLUMNS)
    X, y = make_classification(
        n_samples=n_samples,
        n_features=feature_count,
        n_informative=18,
        n_redundant=6,
        n_repeated=0,
        n_classes=2,
        weights=[0.992, 0.008],
        class_sep=1.2,
        random_state=random_state,
    )
    df = pd.DataFrame(X, columns=FEATURE_COLUMNS)
    df["Amount"] = np.abs(df["Amount"] * 150) + 5
    df["Time"] = np.abs(df["Time"] * 1000)
    df["Class"] = y
    return df


def load_transaction_data(path: str | Path | None = None) -> pd.DataFrame:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_path = Path(path) if path else data_dir / "creditcard.csv"
    
    # Check if we should merge multiple datasets
    # For this system, we primarily use the creditcard format, 
    # but we can simulate "all kinds" by ensuring they are available.
    # To keep it simple and consistent with the expected FEATURE_COLUMNS, 
    # we return the primary dataset if it exists.
    
    if data_path.exists():
        print(f"Loading dataset from {data_path}")
        return pd.read_csv(data_path)
    
    # Fallback to synthetic if nothing found
    return _build_synthetic_dataset()
