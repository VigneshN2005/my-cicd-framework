# Dockerfile
# Builds the whole app (React frontend + FastAPI backend + Nginx) into one image.
#
# MULTI-STAGE BUILD:
#   Stage 1 builds the React frontend with Node.js.
#   Stage 2 is the final image: Python + Nginx, plus only the built frontend
#   files from stage 1. Node.js and node_modules never reach production,
#   which keeps the image small and reduces what security scanners must check.

# ─────────────────────────────────────────────────
# STAGE 1: BUILD FRONTEND
# ─────────────────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend

# Copy dependency files first so Docker can cache the npm install layer;
# it only reruns when package.json or package-lock.json change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ─────────────────────────────────────────────────
# STAGE 2: FINAL IMAGE
# ─────────────────────────────────────────────────
FROM python:3.11-slim

# The pipeline passes the git commit SHA here. /api/health reports it, so the
# post-deploy health check can prove the NEW version is the one serving.
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Links the published image to its source repository on GitHub
LABEL org.opencontainers.image.source="https://github.com/VigneshN2005/my-cicd-framework" \
      org.opencontainers.image.description="Config-driven DevSecOps CI/CD framework demo app" \
      org.opencontainers.image.revision="${APP_VERSION}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Runtime dependencies only (test tools live in requirements-dev.txt)
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./dist

COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

COPY startup.sh ./
RUN chmod +x startup.sh

# Nginx serves the frontend on 80 (or $PORT on cloud hosts); FastAPI on 8000
EXPOSE 80 8000

# Docker marks the container unhealthy if the backend stops answering
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=4)" || exit 1

CMD ["./startup.sh"]
