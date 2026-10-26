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
      deploy ──────── Vercel blue-green: build hidden → health check → switch domain
        │             (or Render: run the GHCR image, roll back to :stable)
     summary

pull request ── ai-review ── Groq (or Gemini) reviews the diff and comments on the PR
```

| Stage | Tools | Blocks the release when |
| --- | --- | --- |
| Config | `scripts/read_config.py` (PyYAML) | the config is invalid or inconsistent |
| Lint | ruff (Python, incl. security rules), ESLint (React) | any lint error |
| Test | pytest + pytest-cov, Vitest + v8 coverage | a test fails or coverage drops below the threshold |
| Security | Gitleaks, pip-audit, npm audit | a secret is found or a vulnerable dependency at or above `fail_on` |
| Docker | multi-stage build, container smoke test, Trivy | the container does not start correctly or the image has fixable vulnerabilities at or above `fail_on` |
| Publish | GitHub Container Registry | (main branch only) |
| Deploy | Vercel CLI + API (`scripts/deploy_vercel.py`) or Render (`scripts/deploy_render.py`) | the new version fails its health check |
| AI review | Groq or Gemini (`scripts/ai_review.py`) | never: advisory comment only |

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

## How deployment and rollback work (Vercel)

On Vercel, the React app is served as static files and the FastAPI backend runs as a
serverless Python function (`api/index.py`). The release is blue-green:

1. The pipeline records which deployment currently serves the production domain.
2. It builds the new version as a production deployment **without** switching the domain
   (`vercel deploy --prod --skip-domain`). Users still see the old version.
3. It calls `/api/health` on the new deployment until it reports **the new commit SHA**.
   If it never does, the release stops here: the domain was never switched, so users are
   unaffected.
4. Only then does it point the production domain at the new deployment (`vercel promote`).
5. It checks the production domain itself. If that fails, it promotes the previous
   deployment back and fails the run.

The Docker image is still built, scanned and published to GHCR for container platforms.
Setting `deploy.provider: "render"` deploys that image to Render instead, with rollback to the
`:stable` image tag.

## Setup

### Deployment to Vercel (one time)

1. On [Vercel](https://vercel.com), import this GitHub repository as a project.
   `vercel.json` turns off Vercel's own automatic Git deployments, so only the pipeline
   deploys and nothing unchecked goes live.
2. Note the project's **Project ID** and your **Team/Org ID** (Project Settings > General), and
   create a token (Account Settings > Tokens).
3. Optional but recommended: under **Deployment Protection**, create a
   **Protection Bypass for Automation** secret, so the health check can reach the new
   deployment before it is public.
4. In this repository, add these secrets under **Settings > Secrets and variables > Actions**:
   - `VERCEL_TOKEN`
   - `VERCEL_ORG_ID`
   - `VERCEL_PROJECT_ID`
   - `VERCEL_APP_URL`: the production URL, e.g. `https://my-cicd-framework.vercel.app`
   - `VERCEL_AUTOMATION_BYPASS_SECRET` (from step 3)

Until the required secrets exist, the deploy stage is skipped with a notice and everything else
runs.

### Deployment to Render (alternative)

Set `deploy.provider: "render"`, make the GHCR package public, create a Render web service from
`ghcr.io/vigneshn2005/my-cicd-app:latest`, and add `RENDER_API_KEY`, `RENDER_SERVICE_ID` and
`RENDER_APP_URL` secrets.

### AI review

Add a `GROQ_API_KEY` secret (free key from console.groq.com). To use Gemini instead, set
`ai_review.provider: "gemini"` and add `GEMINI_API_KEY`. Without a key, the review is skipped.

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
  deploy_vercel.py    Vercel blue-green deploy, health checks, rollback
  deploy_render.py    Render deploy, health check, rollback
  ai_review.py        builds the review prompt and calls Groq or Gemini
  tests/              unit tests for all three scripts
api/index.py          Vercel entry point for the FastAPI backend
vercel.json           Vercel build and routing settings
backend/              FastAPI app, pytest tests
frontend/             React (Vite) app, Vitest tests, ESLint config
Dockerfile            multi-stage build (Node build stage, Python + Nginx runtime)
pipeline-config.yml   the control panel
ruff.toml             Python lint rules
```

## Versions

- **v1**: React + FastAPI + Docker + GitHub Actions, config toggles for build and test
- **v2**: config validation, lint, coverage gates, DevSecOps scanning, GHCR publishing,
  blue-green Vercel deployment (or Render) with health-checked rollback, AI pull request review
  (Groq or Gemini)
