#!/bin/bash
# startup.sh
# Runs inside the container: starts the FastAPI backend, then Nginx.
#
# Cloud hosts such as Render tell the container which port to listen on
# through the PORT variable. Nginx listens on $PORT if set, otherwise 80.
set -e

PORT="${PORT:-80}"
sed -i "s/listen 80;/listen ${PORT};/" /etc/nginx/conf.d/default.conf

echo "Starting FastAPI backend on port 8000 (version: ${APP_VERSION:-dev})..."
cd /app/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Wait until the backend answers before accepting traffic
for _ in $(seq 1 30); do
  if python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=2)" 2>/dev/null; then
    break
  fi
  sleep 1
done

echo "Starting Nginx for the frontend on port ${PORT}..."
exec nginx -g 'daemon off;'
