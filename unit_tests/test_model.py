import numpy as np
import pytest
from src.model import train_model
from sklearn.ensemble import RandomForestClassifier

def test_train_model_returns_model():
    X = np.random.rand(10, 4)
    y = np.random.randint(0, 2, size=10)
    model = train_model(X, y)
    assert isinstance(model, RandomForestClassifier)
    assert hasattr(model, "predict")

def test_train_model_logs(caplog):
    X = np.random.rand(10, 4)
    y = np.random.randint(0, 2, size=10)

    with caplog.at_level("INFO"):
        model = train_model(X, y)

    assert "Training RandomForestClassifier..." in caplog.text
    assert "Model parameters" in caplog.text
