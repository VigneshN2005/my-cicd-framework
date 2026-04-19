#!/bin/bash
# startup.sh
# This script runs inside Docker container
# It starts BOTH the backend and frontend server
# CI/CD Note: Docker runs this when container starts

echo "🚀 Starting CI/CD Framework App..."

# Start FastAPI backend in background
# --host 0.0.0.0 makes it accessible inside container
# & means run in background
echo "⚙️  Starting FastAPI backend on port 8000..."
cd /app/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Wait a moment for backend to start
sleep 2

# Start Nginx to serve frontend
echo "🌐 Starting Nginx for frontend on port 80..."
nginx -g 'daemon off;'