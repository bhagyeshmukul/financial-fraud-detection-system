import pandas as pd

from src.data_loader import load_transaction_data
from src.preprocessing import preprocess_data


def test_preprocessing_outputs_have_expected_shapes():
    df = load_transaction_data().head(3000)
    artifacts = preprocess_data(df)

    assert len(artifacts.X_train_resampled) == len(artifacts.y_train_resampled)
    assert artifacts.X_test_scaled.shape[1] == 30
    assert artifacts.y_test.nunique() == 2
