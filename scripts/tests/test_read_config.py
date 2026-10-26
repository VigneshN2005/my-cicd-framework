import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from read_config import ConfigError, load_config  # noqa: E402

REPO_CONFIG = Path(__file__).resolve().parents[2] / "pipeline-config.yml"


def write(tmp_path, data):
    path = tmp_path / "pipeline-config.yml"
    path.write_text(yaml.safe_dump(data))
    return path


def base():
    return yaml.safe_load(REPO_CONFIG.read_text())


def test_repo_config_is_valid():
    out = load_config(REPO_CONFIG)
    assert out["lint"] == "true"
    assert out["frontend"] == "true" and out["backend"] == "true"
    assert out["trivy_severity"] == "CRITICAL"


def test_backend_only_project_skips_frontend(tmp_path):
    data = base()
    data["project"]["type"] = "backend"
    out = load_config(write(tmp_path, data))
    assert out["frontend"] == "false"
    assert out["backend"] == "true"


def test_trivy_severity_includes_everything_above_threshold(tmp_path):
    data = base()
    data["security"]["fail_on"] = "moderate"
    out = load_config(write(tmp_path, data))
    assert out["trivy_severity"] == "MEDIUM,HIGH,CRITICAL"


def test_stage_flag_must_be_boolean(tmp_path):
    data = base()
    data["stages"]["lint"] = "yes"
    with pytest.raises(ConfigError, match="stages.lint"):
        load_config(write(tmp_path, data))


def test_unknown_stage_is_rejected(tmp_path):
    data = base()
    data["stages"]["lnt"] = True
    with pytest.raises(ConfigError, match="unknown stage"):
        load_config(write(tmp_path, data))


def test_deploy_requires_publish(tmp_path):
    data = base()
    data["stages"]["publish"] = False
    with pytest.raises(ConfigError, match="deploy needs"):
        load_config(write(tmp_path, data))


def test_coverage_must_be_a_percentage(tmp_path):
    data = base()
    data["testing"]["backend_coverage_min"] = 150
    with pytest.raises(ConfigError, match="backend_coverage_min"):
        load_config(write(tmp_path, data))


def test_invalid_severity_is_rejected(tmp_path):
    data = base()
    data["security"]["fail_on"] = "severe"
    with pytest.raises(ConfigError, match="fail_on"):
        load_config(write(tmp_path, data))


def test_health_path_must_start_with_slash(tmp_path):
    data = base()
    data["deploy"]["health_path"] = "api/health"
    with pytest.raises(ConfigError, match="health_path"):
        load_config(write(tmp_path, data))


def test_missing_file_gives_clear_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.yml")


def test_broken_yaml_gives_clear_error(tmp_path):
    path = tmp_path / "pipeline-config.yml"
    path.write_text("stages: [lint: true")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config(path)
