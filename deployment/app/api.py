from fastapi import FastAPI, Request
import os
from contextlib import asynccontextmanager
import time
import logging
from fastapi.responses import PlainTextResponse
import joblib
import requests
import tempfile
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import metrics
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# en la variable de entorno LOG_LEVEL se configura el nivel de logging, que se carga desde el archivo .env a través de load_dotenv() y se utiliza para configurar el logging.basicConfig() en main.py, lo que permite controlar la cantidad de información que se registra en los logs sin necesidad de modificar el código, simplemente cambiando el valor de LOG_LEVEL en el archivo .env
logger = logging.getLogger("geoyield_api")

scaler = None
model = None
encoders = None
db_engine = None

temp_files = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    global scaler, model, encoders, db_engine

    try:
        # Get GitHub repo info from environment or use defaults
        github_repo = os.getenv("GITHUB_REPO")
        
        # Get model version from MODEL_VERSION environment variable, which is set at deploy time, in the input section of deply.yml
        model_version = os.getenv("MODEL_VERSION", "latest")

        # Download release from GitHub. latest is the default, but you can specify a tag if needed
        logger.info(f"Fetching latest release from {github_repo}...")
        if model_version != "latest":
            response = requests.get(f"https://api.github.com/repos/{github_repo}/releases/tags/{model_version}")
        else:
            response = requests.get(f"https://api.github.com/repos/{github_repo}/releases/latest")
        response.raise_for_status()
        release = response.json()
        
        # Download model.pkl, scaler.pkl, and encoders.pkl
        assets_to_download = {'model.pkl': None, 'scaler.pkl': None, 'encoders.pkl': None}
        
        for asset in release.get('assets', []):
            if asset['name'] in assets_to_download:
                assets_to_download[asset['name']] = asset['browser_download_url']
        
        for asset_name in assets_to_download:
            if not assets_to_download[asset_name]:
                raise ValueError(f"{asset_name} not found in latest release")
        
        # Download and load model  
        logger.info(f"Downloading model, scaler, and encoders...")
        
        model_data = requests.get(assets_to_download['model.pkl']).content
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            f.write(model_data)
            model_path = f.name
            temp_files.append(model_path)
        model = joblib.load(model_path)
        logger.info("Model loaded successfully")
        
        scaler_data = requests.get(assets_to_download['scaler.pkl']).content
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            f.write(scaler_data)
            scaler_path = f.name
            temp_files.append(scaler_path)
        scaler = joblib.load(scaler_path)
        logger.info("Scaler loaded successfully")
        
        encoders_data = requests.get(assets_to_download['encoders.pkl']).content
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            f.write(encoders_data)
            encoders_path = f.name
            temp_files.append(encoders_path)
        encoders = joblib.load(encoders_path)
        logger.info("Encoders loaded successfully")

        # Open databaase connection
        db_engine = create_engine(os.getenv("DATABASE_URL"), connect_args={"check_same_thread": False})
        
    except Exception as e:
        logger.error(f"Failed to load artifacts: {e}")
        raise
    
    yield
    
    # Cleanup
    for temp_file in temp_files:
        try:
            if Path(temp_file).exists():
                Path(temp_file).unlink()
        except:
            pass

app = FastAPI(lifespan=lifespan)

SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/predict")
async def predict(request: Request):
    start = time.time()
    
    try:
        data = await request.json()
        df = pd.DataFrame([data])
        
        # Apply label encoders to categorical features
        for col, le in encoders.items():
            if col in df.columns:
                df[col] = le.transform(df[col])
        
        # Scale features
        df_scaled = scaler.transform(df)
        
        # Predict
        prediction = model.predict(df_scaled)
        duration = time.time() - start
        metrics["total_predictions"] += 1
        logger.info(f"Prediction: input={data}, output={prediction.tolist()}, time={duration:.3f}s")
        
        return {"prediction": prediction.tolist(), "duration": duration}
    
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        return {"error": str(e)}, 500

@app.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint():
    return f'total_predictions {metrics["total_predictions"]}\n'

