"""Vercel entry point for the FastAPI backend.

Vercel runs this file as a serverless Python function. Every request to
/api/* is routed here (see vercel.json) and handled by the same FastAPI
app that runs in the Docker image.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "backend"))

# The pipeline writes api/_version.py (the git commit SHA) before deploying,
# so /api/health can prove which version is serving.
try:
    from _version import VERSION

    os.environ.setdefault("APP_VERSION", VERSION)
except ImportError:
    pass

from app.main import app  # noqa: E402,F401  (Vercel looks for "app")
