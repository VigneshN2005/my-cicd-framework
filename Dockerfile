# Dockerfile
# This builds your entire app into a Docker container
# CI/CD pipeline runs: docker build → docker run
#
# We use MULTI-STAGE BUILD:
# Stage 1 → Build React frontend (uses Node.js)
# Stage 2 → Build Python backend + copy frontend + run everything


# ─────────────────────────────────────────────────
# STAGE 1: BUILD FRONTEND
# Uses Node.js to build React app
# ─────────────────────────────────────────────────
FROM node:18-alpine AS frontend-build

# What this does:
# - Uses Node.js 18 (alpine = lightweight Linux)
# - We name this stage "frontend-build"

# Set working directory inside container
WORKDIR /app/frontend

# Copy package.json first (for better caching)
# Docker caches this layer so npm install
# only reruns if package.json changes
COPY frontend/package.json ./

# Install all React dependencies
RUN npm install

# Copy all frontend source code
COPY frontend/ ./

# Build React app for production
# Creates dist/ folder with HTML/CSS/JS files
RUN npm run build


# ─────────────────────────────────────────────────
# STAGE 2: BUILD BACKEND + COMBINE EVERYTHING
# Uses Python for FastAPI backend
# Copies frontend build from Stage 1
# ─────────────────────────────────────────────────
FROM python:3.11-slim

# What this does:
# - Uses Python 3.11 (slim = lightweight)
# - This is the FINAL container image

# Install Nginx (web server for frontend)
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# ── Backend Setup ──────────────────────────────
# Copy requirements and install Python libraries
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source code
COPY backend/ ./backend/

# ── Frontend Setup ─────────────────────────────
# Copy the built React files from Stage 1
# We only copy the dist/ folder (built files)
# not the node_modules (saves space)
COPY --from=frontend-build /app/frontend/dist ./dist

# ── Nginx Setup ────────────────────────────────
# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Remove default nginx config
RUN rm -f /etc/nginx/sites-enabled/default

# ── Startup Script ─────────────────────────────
COPY startup.sh ./
RUN chmod +x startup.sh     # make it executable

# ── Ports ──────────────────────────────────────
# Tell Docker which ports this container uses
# Nginx serves frontend here
EXPOSE 80
# FastAPI backend runs here
EXPOSE 8000

# ── Start Command ──────────────────────────────
# When container starts, run startup.sh
# This starts both backend and frontend
CMD ["./startup.sh"]