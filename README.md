# 🚀 My CI/CD Framework

A config-driven CI/CD framework for college projects.
Built with React + FastAPI + Docker + GitHub Actions.

---

## 📁 Project Structure
my-cicd-framework/
├── frontend/          → React app (UI)
├── backend/           → FastAPI app (API + AI ready)
├── .github/workflows/ → GitHub Actions pipeline
├── Dockerfile         → Container setup
├── docker-compose.yml → Easy run command
├── pipeline-config.yml→ YOUR CONTROL PANEL
└── nginx.conf         → Web server config
---

## ⚙️ Pipeline Control Panel

Edit `pipeline-config.yml` to control the pipeline:

```yaml
features:
  frontend: true   # build React?
  backend: true    # build FastAPI?
  test: true       # run tests?
  docker: true     # build Docker image?
  deploy: true     # deploy container?
```

---

## 🚀 How to Run Locally

### Run Frontend
```powershell
cd frontend
npm install
npm run dev
# Opens at http://localhost:3001
```

### Run Backend
```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Opens at http://localhost:8000
```

### Run with Docker
```powershell
docker build -t my-cicd-app .
docker run -d -p 80:80 -p 8000:8000 --name my-app my-cicd-app
# Frontend → http://localhost
# Backend  → http://localhost:8000
# API Docs → http://localhost:8000/docs
```

### Run Tests
```powershell
cd backend
pytest tests/ -v
```

---

## 🔄 CI/CD Pipeline Flow
Push to GitHub
↓
GitHub Actions triggers
↓
Read pipeline-config.yml
↓
Build Frontend (React)
↓
Build Backend (FastAPI)
↓
Run Tests (pytest)
↓
Docker Build
↓
Docker Deploy
↓
App is LIVE 🚀
---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite |
| Backend | FastAPI + Python |
| Testing | pytest + vitest |
| Container | Docker |
| Pipeline | GitHub Actions |
| Web Server | Nginx |

---

## 📌 Version

- V1 → React + FastAPI + Docker + GitHub Actions ✅
- V2 → Electron + AI Models + Docker Hub (coming)
- V3 → Kubernetes (future)
