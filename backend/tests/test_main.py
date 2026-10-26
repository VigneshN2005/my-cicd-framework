# test_main.py
# These are automated tests for your FastAPI backend
# CI/CD Note: GitHub Actions runs these automatically
# If any test fails → pipeline STOPS → app is NOT deployed

import os
import sys

from fastapi.testclient import TestClient

# This adds backend folder to Python path
# So Python can find your app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

# TestClient simulates HTTP requests to your API
client = TestClient(app)


# ─────────────────────────────────────────
# TEST 1: Health Check
# ─────────────────────────────────────────
def test_health_check():
    # Call GET /
    response = client.get("/")

    # Check status code is 200 (success)
    assert response.status_code == 200

    # Check response has status: ok
    assert response.json()["status"] == "ok"

    print("✅ Health check passed")


# ─────────────────────────────────────────
# TEST 2: Hello Endpoint
# ─────────────────────────────────────────
def test_hello():
    # Call GET /api/hello
    response = client.get("/api/hello")

    # Check status code
    assert response.status_code == 200

    # Check message exists in response
    assert "message" in response.json()

    print("✅ Hello endpoint passed")


# ─────────────────────────────────────────
# TEST 3: Pipeline Info Endpoint
# ─────────────────────────────────────────
def test_pipeline_info():
    # Call GET /api/pipeline-info
    response = client.get("/api/pipeline-info")

    # Check status code
    assert response.status_code == 200

    # Check stages list exists
    assert "stages" in response.json()

    print("✅ Pipeline info endpoint passed")


# ─────────────────────────────────────────
# TEST 4: Data Processing Endpoint
# ─────────────────────────────────────────
def test_process_data():
    # Call POST /api/data with test data
    response = client.post("/api/data", json={
        "name": "test",
        "value": "hello"
    })

    # Check status code
    assert response.status_code == 200

    # Check processed field exists
    assert "processed" in response.json()

    print("✅ Data processing endpoint passed")

# ─────────────────────────────────────────
# TEST 5: AI Predict Placeholder
# ─────────────────────────────────────────
def test_predict_placeholder():
    response = client.post("/api/predict", json={"name": "model", "value": "input"})
    assert response.status_code == 200
    assert response.json()["status"] == "placeholder"


# ─────────────────────────────────────────
# TEST 6: Deploy Health Check
# The pipeline calls this after every deploy and compares "version"
# with the commit it just deployed.
# ─────────────────────────────────────────
def test_deploy_health_reports_version(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "abc123")
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "abc123"}


# ─────────────────────────────────────────
# TEST 7: Invalid Input Is Rejected
# Pydantic validation must return 422 when a required field is missing.
# ─────────────────────────────────────────
def test_invalid_data_is_rejected():
    response = client.post("/api/data", json={"name": "only-name"})
    assert response.status_code == 422
