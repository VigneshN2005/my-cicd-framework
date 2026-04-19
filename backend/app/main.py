# main.py
# This is the ENTRY POINT of your FastAPI backend
# It creates the app and connects all routes
# CI/CD Note: Docker runs this file to start the backend server

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router

# Create the FastAPI app
app = FastAPI(
    title="My CI/CD Backend",
    description="FastAPI backend for CI/CD Learning Framework",
    version="1.0.0"
)

# CORS Middleware
# This allows the React frontend to talk to this backend
# Without this, browser will block frontend → backend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # allow all origins (fine for learning)
    allow_methods=["*"],      # allow all HTTP methods
    allow_headers=["*"],      # allow all headers
)

# Connect all routes from routes.py
app.include_router(router)

# Health check endpoint
# CI/CD pipeline uses this to verify backend is running
@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Backend is running!",
        "framework": "FastAPI"
    }