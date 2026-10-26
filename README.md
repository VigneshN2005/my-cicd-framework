# DevSecOps CI/CD Framework

A config-driven CI/CD pipeline for full-stack projects (React + FastAPI), built on GitHub Actions.
One file, `pipeline-config.yml`, controls every stage: lint, test with coverage gates, security
scanning, containerisation, publishing, cloud deployment with automatic rollback, and an
LLM-based review of every pull request.

Nothing is published or deployed unless every earlier stage passes.

## Pipeline

```
push / pull request
        │
     config ──── validates pipeline-config.yml (fails fast on typos or bad values)
     │     │
   lint   security ── Gitleaks (secrets) · pip-audit · npm audit
     │     │
   test    │ ──────── pytest + Vitest with coverage gates
     └──┬──┘
      docker ──────── build · smoke test · Trivy image scan · push to GHCR
        │
      deploy ──────── Render · health check on the new version · rollback to :stable
        │
     summary

pull request ── ai-review ── Gemini reviews the diff and comments on the PR
```

| Stage | Tools | Blocks the release when |
| --- | --- | --- |
| Config | `scripts/read_config.py` (PyYAML) | the config is invalid or inconsistent |
| Lint | ruff (Python, incl. security rules), ESLint (React) | any lint error |
| Test | pytest + pytest-cov, Vitest + v8 coverage | a test fails or coverage drops below the threshold |
| Security | Gitleaks, pip-audit, npm audit | a secret is found or a vulnerable dependency at or above `fail_on` |
| Docker | multi-stage build, container smoke test, Trivy | the container does not start correctly or the image has fixable vulnerabilities at or above `fail_on` |
| Publish | GitHub Container Registry | (main branch only) |
| Deploy | Render API, `scripts/deploy_render.py` | the new version does not go live or fails its health check |
| AI review | Gemini (`scripts/ai_review.py`) | never: advisory comment only |

## The control panel: `pipeline-config.yml`

```yaml
stages:
  lint: true
  test: true
  security: true
  docker: true
  publish: true
  deploy: true
  ai_review: true

testing:
  backend_coverage_min: 80
  frontend_coverage_min: 70

security:
  fail_on: "critical"   # low | moderate | high | critical
```

The config is validated on every run. Wrong types (`lint: yes`), unknown stages, impossible
combinations (`deploy` without `publish`) and out-of-range values fail the pipeline in the first
job with a clear error message.

## How deployment and rollback work

1. Every image is tagged with its commit SHA, and the SHA is baked into the image as `APP_VERSION`.
2. The deploy job asks Render to run the new image and waits until Render reports it live.
3. It then calls `/api/health` until the app reports **the new commit SHA**. This proves the new
   version is the one actually serving traffic, not an old instance.
4. On success, the image is promoted to the `:stable` tag.
5. On failure, the pipeline redeploys `:stable` (the last version that passed its health check)
   and marks the run as failed.

## Setup

### Required for deployment (one time)

1. Let the pipeline run once on `main` so the image is published to
   `ghcr.io/vigneshn2005/my-cicd-app`. In the package settings on GitHub, set its visibility
   to **Public** (or give Render registry credentials).
2. On [Render](https://render.com), create a **Web Service** from an existing image:
   `ghcr.io/vigneshn2005/my-cicd-app:latest`. The container listens on Render's `PORT`
   automatically.
3. In this repository, add three secrets under **Settings > Secrets and variables > Actions**:
   - `RENDER_API_KEY`: from Render account settings
   - `RENDER_SERVICE_ID`: the `srv-...` ID in the service URL
   - `RENDER_APP_URL`: the public URL, e.g. `https://my-cicd-app.onrender.com`

Until these secrets exist, the deploy stage is skipped with a notice and everything else runs.

### Required for AI review

Add a `GEMINI_API_KEY` secret (free key from Google AI Studio). Without it, the review is
skipped.

## Run locally

```bash
# Whole app in Docker
docker compose up --build
# Frontend: http://localhost:3001   API docs: http://localhost:8000/docs

# Backend
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest tests --cov=app

# Frontend
cd frontend
npm ci
npm run dev
npm run lint
npm run test:coverage

# Check the pipeline config
python scripts/read_config.py
```

## Project structure

```
.github/workflows/
  core.yml            the CI/CD pipeline
  ai-review.yml       LLM review on pull requests
scripts/
  read_config.py      parses and validates pipeline-config.yml
  deploy_render.py    deploy, health check, rollback
  ai_review.py        builds the review prompt and calls Gemini
  tests/              unit tests for all three scripts
backend/              FastAPI app, pytest tests
frontend/             React (Vite) app, Vitest tests, ESLint config
Dockerfile            multi-stage build (Node build stage, Python + Nginx runtime)
pipeline-config.yml   the control panel
ruff.toml             Python lint rules
```

## Versions

- **v1**: React + FastAPI + Docker + GitHub Actions, config toggles for build and test
- **v2**: config validation, lint, coverage gates, DevSecOps scanning, GHCR publishing,
  cloud deployment with health-checked rollback, AI pull request review
