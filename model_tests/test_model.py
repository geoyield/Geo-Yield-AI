import os
import pytest
import joblib  # or pickle, depending on your serialization method
import numpy as np
from sklearn.metrics import accuracy_score
import pandas as pd

def test_model_loading():
    model_path = 'models/model.pkl'
    assert os.path.exists(model_path), f"Model file not found at {model_path}"
    try:
        model = joblib.load(model_path)
    except Exception as e:
        pytest.fail(f"Failed to load model: {e}")


def test_prediction_shape():
    model = joblib.load('models/model.pkl')
    sample_input = np.random.rand(5, model.n_features_in_)
    predictions = model.predict(sample_input)
    assert predictions.shape == (5,), f"Expected predictions of shape (5,), got {predictions.shape}"

def test_prediction_values():
    model = joblib.load('models/model.pkl')
    sample_input = np.random.rand(5, model.n_features_in_)
    predictions = model.predict(sample_input)
    assert set(predictions).issubset({0, 1}), f"Predictions contain unexpected classes: {set(predictions)}"

def test_model_accuracy():
    model = joblib.load('models/model.pkl')
    test_data = pd.read_csv('data/raw/adult.test', header=None, skiprows=1)
    X_test = test_data.iloc[:, :-1]
    y_test = test_data.iloc[:, -1].str.strip().str.replace('.', '', regex=False)
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    assert accuracy >= 0.80, f"Model accuracy below expected threshold: {accuracy:.2f}"