import pytest
import pandas as pd
import numpy as np
from io import StringIO
from sklearn.preprocessing import LabelEncoder, StandardScaler

from src.data_loader import load_data, preprocess_data  # Update this import path as needed

@pytest.fixture
def sample_csv_data():
    train_csv = StringIO("""39, State-gov, 77516, HS-grad, 13, Divorced, Handlers-cleaners, Not-in-family, White, Male, 0, 0, 40, United-States, <=50K.
50, Private, 83311, Bachelors, 13, Married, Exec-managerial, Husband, White, Female, 0, 0, 13, United-States, >50K
""")
    test_csv = StringIO("""
    |1x3 Cross validator
38, Private, 215646, HS-grad, 9, Divorced, Handlers-cleaners, Not-in-family, White, Male, 0, 0, 40, United-States, <=50K.
28, Private, 338409, Bachelors, 13, Married, Exec-managerial, Husband, White, Female, 0, 0, 40, United-States, >50K.
""")
    return train_csv, test_csv

def test_load_data(sample_csv_data):
    train_csv, test_csv = sample_csv_data
    train_df, test_df = load_data(train_csv, test_csv)

    assert isinstance(train_df, pd.DataFrame)
    assert isinstance(test_df, pd.DataFrame)

    assert train_df.shape[0] == 2
    assert test_df.shape[0] == 2
    assert "income" in test_df.columns
    assert not test_df["income"].str.contains("\.").any(), "Periods were not removed from test income column"

def test_preprocess_data(sample_csv_data):
    train_csv, test_csv = sample_csv_data
    train_df, test_df = load_data(train_csv, test_csv)
    X_train, X_test, y_train, y_test, scaler, encoders = preprocess_data(train_df, test_df)

    assert isinstance(X_train, np.ndarray)
    assert isinstance(y_train, np.ndarray)
    assert X_train.shape == (2, X_train.shape[1])
    assert X_test.shape == (2, X_train.shape[1])
    assert isinstance(scaler, StandardScaler)
    assert isinstance(encoders, dict)
    assert all(isinstance(le, LabelEncoder) for le in encoders.values())
