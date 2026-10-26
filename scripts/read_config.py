"""Read and validate pipeline-config.yml, then expose it to GitHub Actions.

Every job in the workflow decides whether to run, and with which settings,
from the outputs this script writes. Validation happens up front so a typo
in the config fails the pipeline in the first few seconds with a clear
message, instead of silently skipping a stage.

Usage:
    python scripts/read_config.py [path/to/pipeline-config.yml]

Writes key=value lines to $GITHUB_OUTPUT when it is set (inside Actions),
otherwise prints them, which is handy for checking the config locally.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

STAGES = ("lint", "test", "security", "docker", "publish", "deploy", "ai_review")
PROJECT_TYPES = ("fullstack", "frontend", "backend")
SEVERITIES = ("low", "moderate", "high", "critical")
PROVIDERS = ("render",)


class ConfigError(ValueError):
    """Raised when pipeline-config.yml is missing a value or has a wrong one."""


def _section(cfg: dict, name: str) -> dict:
    value = cfg.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"'{name}' section is missing or is not a mapping")
    return value


def _bool(section: dict, key: str, where: str) -> bool:
    value = section.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"{where}.{key} must be true or false, got {value!r}")
    return value


def _percent(section: dict, key: str, where: str) -> int:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise ConfigError(f"{where}.{key} must be a whole number from 0 to 100, got {value!r}")
    return value


def _positive_int(section: dict, key: str, where: str) -> int:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{where}.{key} must be a positive whole number, got {value!r}")
    return value


def _choice(section: dict, key: str, where: str, allowed: tuple[str, ...]) -> str:
    value = section.get(key)
    if value not in allowed:
        raise ConfigError(f"{where}.{key} must be one of {', '.join(allowed)}; got {value!r}")
    return value


def _text(section: dict, key: str, where: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}.{key} must be a non-empty string, got {value!r}")
    return value.strip()


def load_config(path: str | Path) -> dict[str, str]:
    """Parse and validate the config file; return flat outputs for Actions."""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"config file is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config file must contain a mapping at the top level")

    project = _section(raw, "project")
    stages = _section(raw, "stages")
    env = _section(raw, "environment")
    testing = _section(raw, "testing")
    security = _section(raw, "security")
    docker = _section(raw, "docker")
    deploy = _section(raw, "deploy")
    ai = _section(raw, "ai_review")

    unknown = set(stages) - set(STAGES)
    if unknown:
        raise ConfigError(f"unknown stage(s) in 'stages': {', '.join(sorted(unknown))}")

    out: dict[str, str] = {}
    project_type = _choice(project, "type", "project", PROJECT_TYPES)
    out["project_name"] = _text(project, "name", "project")
    out["project_type"] = project_type
    out["frontend"] = str(project_type in ("fullstack", "frontend")).lower()
    out["backend"] = str(project_type in ("fullstack", "backend")).lower()

    flags = {stage: _bool(stages, stage, "stages") for stage in STAGES}

    # Stages that need an earlier stage's output cannot run without it.
    if flags["publish"] and not flags["docker"]:
        raise ConfigError("stages.publish needs stages.docker to be true (nothing to publish)")
    if flags["deploy"] and not flags["publish"]:
        raise ConfigError("stages.deploy needs stages.publish to be true (nothing to deploy)")
    for stage, enabled in flags.items():
        out[stage] = str(enabled).lower()

    out["node_version"] = str(env.get("node_version", "")).strip() or "22"
    out["python_version"] = str(env.get("python_version", "")).strip() or "3.11"

    out["backend_coverage_min"] = str(_percent(testing, "backend_coverage_min", "testing"))
    out["frontend_coverage_min"] = str(_percent(testing, "frontend_coverage_min", "testing"))

    out["fail_on"] = _choice(security, "fail_on", "security", SEVERITIES)
    out["dependency_audit"] = str(_bool(security, "dependency_audit", "security")).lower()
    out["secret_scan"] = str(_bool(security, "secret_scan", "security")).lower()
    out["image_scan"] = str(_bool(security, "image_scan", "security")).lower()
    # Trivy wants every severity at or above the threshold, in upper case.
    # npm calls the second level "moderate"; Trivy calls it "MEDIUM".
    trivy_names = {"low": "LOW", "moderate": "MEDIUM", "high": "HIGH", "critical": "CRITICAL"}
    threshold = SEVERITIES.index(out["fail_on"])
    out["trivy_severity"] = ",".join(trivy_names[s] for s in SEVERITIES[threshold:])

    image = _text(docker, "image_name", "docker")
    if image != image.lower() or " " in image:
        raise ConfigError("docker.image_name must be lower case with no spaces")
    out["image_name"] = image

    out["deploy_provider"] = _choice(deploy, "provider", "deploy", PROVIDERS)
    health_path = _text(deploy, "health_path", "deploy")
    if not health_path.startswith("/"):
        raise ConfigError("deploy.health_path must start with '/'")
    out["health_path"] = health_path
    out["health_timeout_seconds"] = str(_positive_int(deploy, "health_timeout_seconds", "deploy"))
    out["rollback_on_failure"] = str(_bool(deploy, "rollback_on_failure", "deploy")).lower()

    out["ai_model"] = _text(ai, "model", "ai_review")
    out["ai_max_diff_chars"] = str(_positive_int(ai, "max_diff_chars", "ai_review"))
    return out


def write_outputs(outputs: dict[str, str]) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    lines = [f"{key}={value}" for key, value in outputs.items()]
    if target:
        with open(target, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    for line in lines:
        print(line)


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else "pipeline-config.yml"
    try:
        outputs = load_config(path)
    except ConfigError as exc:
        print(f"::error title=Invalid pipeline-config.yml::{exc}")
        return 1
    write_outputs(outputs)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
