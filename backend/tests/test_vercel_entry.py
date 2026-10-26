# test_vercel_entry.py
# Checks the Vercel entry point (api/index.py): it must expose the same
# FastAPI app and report the version the pipeline writes before deploying.

import importlib.util
import os
from pathlib import Path

from fastapi.testclient import TestClient

ENTRY = Path(__file__).resolve().parents[2] / "api" / "index.py"


def load_entry(monkeypatch, tmp_path, version=None):
    # setenv first so pytest restores the original (unset) value afterwards
    monkeypatch.setenv("APP_VERSION", "placeholder")
    monkeypatch.delenv("APP_VERSION")
    if version:
        (tmp_path / "_version.py").write_text(f'VERSION = "{version}"\n')
        monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(__import__("sys").modules, "_version", raising=False)
    spec = importlib.util.spec_from_file_location("vercel_entry", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_entry_exposes_the_fastapi_app(monkeypatch, tmp_path):
    module = load_entry(monkeypatch, tmp_path)
    client = TestClient(module.app)
    assert client.get("/api/hello").status_code == 200


def test_entry_reports_pipeline_version(monkeypatch, tmp_path):
    module = load_entry(monkeypatch, tmp_path, version="sha123")
    assert os.environ["APP_VERSION"] == "sha123"
    client = TestClient(module.app)
    assert client.get("/api/health").json() == {"status": "ok", "version": "sha123"}
