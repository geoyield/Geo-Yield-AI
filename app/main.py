from fastapi import FastAPI

# Inicialización de la aplicación Geo-Yield AI
app = FastAPI(
    title="Geo-Yield AI API",
    description="Location Intelligence para Hostelería en Barcelona",
    version="1.0.0"
)

@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "online", 
        "message": "Geo-Yield AI Engine funcionando correctamente",
        "team": "Equipo GEOAI"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "db_status": "pending_connection",
        "api_status": "ok"
    }
