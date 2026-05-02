from sklearn.ensemble import RandomForestClassifier
import logging

logger=logging.getLogger("adult-income")

def train_model(X_train, y_train):
    logger.info("Training RandomForestClassifier...")
    model = RandomForestClassifier(random_state=42)
    logger.info(f"Model parameters: {model.get_params()}")
    model.fit(X_train, y_train)
    return model
