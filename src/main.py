import logging
import os
import time
import platform
import joblib
from pathlib import Path
from datetime import datetime
from data_loader import load_data, preprocess_data
from evaluate import evaluate
from model import train_model

# Configurar logging (consola + archivo)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("training.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("adult-income")

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)

def main():
    """
    Train model and save artifacts locally.
    No external MLflow server required.
    """
    script_start = time.time()
    logger.info(f"System info: {platform.platform()}")
    logger.info(f"Training started at {datetime.now().isoformat()}")

    # Load and preprocess data
    train_df, test_df = load_data(DATA_DIR / "adult.data", DATA_DIR / "adult.test")
    X_train, X_test, y_train, y_test, scaler, encoders = preprocess_data(train_df, test_df)
    
    # Train model
    start_time = time.time()
    model = train_model(X_train, y_train)
    elapsed = time.time() - start_time
    logger.info(f"Model training complete. Time taken: {elapsed:.2f} seconds")
    
    # Evaluate model
    evaluate(model, X_test, y_test)

    # Save model and preprocessing artifacts
    logger.info(f"Saving artifacts to {MODEL_DIR}...")
    model_path = MODEL_DIR / "model.pkl"
    joblib.dump(model, model_path)
    logger.info(f"✓ Model saved to {model_path}")

    joblib.dump(scaler, MODEL_DIR / "scaler.pkl")
    logger.info(f"✓ Scaler saved to {MODEL_DIR / 'scaler.pkl'}")
    
    joblib.dump(encoders, MODEL_DIR / "encoders.pkl")
    logger.info(f"✓ Encoders saved to {MODEL_DIR / 'encoders.pkl'}")

    total_time = time.time() - script_start
    logger.info(f"✅ Training pipeline completed in {total_time:.2f} seconds")
    logger.info(f"Model ready for deployment!")

if __name__ == "__main__":
    main()
