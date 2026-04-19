# routes.py
# This file contains all API endpoints
# Frontend (React) calls these endpoints to get data
# CI/CD Note: Add new endpoints here as your project grows

from fastapi import APIRouter
from pydantic import BaseModel

# APIRouter groups all your routes together
router = APIRouter(prefix="/api")


# ─────────────────────────────────────────
# BASIC ENDPOINTS
# ─────────────────────────────────────────

# GET /api/hello
# Frontend calls this to check backend connection
@router.get("/hello")
def hello():
    return {
        "message": "Hello from FastAPI Backend!",
        "status": "connected"
    }


# GET /api/pipeline-info
# Returns info about the CI/CD pipeline stages
@router.get("/pipeline-info")
def pipeline_info():
    return {
        "pipeline": "GitHub Actions",
        "stages": [
            "Code Push",
            "Checkout",
            "Build Frontend",
            "Build Backend",
            "Run Tests",
            "Docker Build",
            "Docker Deploy"
        ],
        "status": "All stages passed"
    }


# ─────────────────────────────────────────
# DATA ENDPOINT
# ─────────────────────────────────────────

# Data model for POST request
# Pydantic automatically validates the incoming data
class DataInput(BaseModel):
    name: str
    value: str

# POST /api/data
# Accepts data from frontend and returns processed result
@router.post("/data")
def process_data(input: DataInput):
    return {
        "received": {
            "name": input.name,
            "value": input.value
        },
        "processed": f"Backend processed: {input.name} = {input.value}",
        "status": "success"
    }


# ─────────────────────────────────────────
# AI READY ENDPOINT (placeholder for now)
# ─────────────────────────────────────────

# POST /api/predict
# This is ready for your AI model
# Right now it returns a placeholder response
# Later: load your ML model here and return predictions
@router.post("/predict")
def predict(input: DataInput):
    # TODO: Load your AI model here
    # Example:
    # model = load_model('model.pkl')
    # prediction = model.predict(input.value)

    return {
        "input": input.value,
        "prediction": "AI model not loaded yet",
        "note": "Replace this with your actual ML model",
        "status": "placeholder"
    }