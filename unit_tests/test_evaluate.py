import pytest
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from src.evaluate import evaluate

def test_evaluate_logs(caplog):
    # Create dummy data
    X = np.random.rand(10, 4)
    y = np.random.randint(0, 2, size=10)

    # Train simple model
    model = RandomForestClassifier(random_state=42)
    model.fit(X, y)

    # Run evaluation
    with caplog.at_level("INFO"):
        evaluate(model, X, y)

    # Assertions
    assert "Evaluating model..." in caplog.text
    assert "Test Accuracy" in caplog.text
    assert "Classification Report" in caplog.text
