from sklearn.metrics import accuracy_score, classification_report
import logging

logger=logging.getLogger("adult-income")

def evaluate(model, X_test, y_test):
    logger.info("Evaluating model...")
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    report = classification_report(y_test, preds)
    logger.info(f"Test Accuracy: {acc:.4f}")
    logger.info(f"Classification Report:\n{report}")
    return