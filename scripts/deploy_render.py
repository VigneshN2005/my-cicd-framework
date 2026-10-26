"""Deploy a container image to Render, verify it, and roll back on failure.

Flow:
  1. Ask Render to deploy the new image (tagged with the commit SHA).
  2. Wait until Render reports the deploy as live (or failed).
  3. Call the app's health endpoint until it answers with the new commit SHA,
     proving the NEW version is the one actually serving traffic.
  4. If any step fails and rollback is enabled, redeploy the :stable image
     (the last version that passed its health check) and fail the pipeline.

Settings come from environment variables set by the workflow:
  RENDER_API_KEY, RENDER_SERVICE_ID  - Render account access (GitHub secrets)
  APP_URL                            - public URL of the service
  NEW_IMAGE, STABLE_IMAGE            - image references (ghcr.io/owner/app:tag)
  EXPECTED_VERSION                   - commit SHA the health check must report
  HEALTH_PATH, HEALTH_TIMEOUT        - from pipeline-config.yml
  ROLLBACK                           - "true" or "false"

Exit code 0 = new version is live and healthy; 1 = failed (rolled back or not).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

API = "https://api.render.com/v1"
LIVE = "live"
FAILED = {"build_failed", "update_failed", "canceled", "deactivated", "pre_deploy_failed"}


class DeployError(RuntimeError):
    pass


@dataclass
class Http:
    """Thin wrapper around urllib so tests can swap in a fake."""

    api_key: str
    request: Callable[..., tuple[int, dict]] | None = None

    def call(self, method: str, url: str, body: dict | None = None, auth: bool = True) -> tuple[int, dict]:
        if self.request:
            return self.request(method, url, body, auth)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if auth:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode() or "{}"
                return resp.status, json.loads(text)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            return exc.code, {"error": detail}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return 0, {"error": str(exc)}


@dataclass
class Deployer:
    http: Http
    service_id: str
    app_url: str
    health_path: str
    timeout: int
    poll_seconds: float = 10.0
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    log: list[str] = field(default_factory=list)

    def say(self, message: str) -> None:
        self.log.append(message)
        print(message, flush=True)

    def trigger(self, image: str) -> str:
        url = f"{API}/services/{self.service_id}/deploys"
        status, body = self.http.call("POST", url, {"imageUrl": image})
        if status not in (200, 201, 202) or "id" not in body:
            raise DeployError(f"Render refused the deploy of {image} (HTTP {status}): {body}")
        self.say(f"Deploy {body['id']} started for {image}")
        return body["id"]

    def wait_until_live(self, deploy_id: str) -> None:
        url = f"{API}/services/{self.service_id}/deploys/{deploy_id}"
        deadline = self.clock() + self.timeout
        while self.clock() < deadline:
            status, body = self.http.call("GET", url)
            state = body.get("status", "unknown") if status == 200 else f"http-{status}"
            if state == LIVE:
                self.say(f"Deploy {deploy_id} is live")
                return
            if state in FAILED:
                raise DeployError(f"Deploy {deploy_id} ended with status '{state}'")
            self.say(f"Deploy {deploy_id}: {state}, waiting...")
            self.sleep(self.poll_seconds)
        raise DeployError(f"Deploy {deploy_id} did not go live within {self.timeout}s")

    def health_check(self, expected_version: str | None) -> None:
        url = self.app_url.rstrip("/") + self.health_path
        deadline = self.clock() + self.timeout
        last = "no response"
        while self.clock() < deadline:
            status, body = self.http.call("GET", url, auth=False)
            version = body.get("version")
            if status == 200 and body.get("status") == "ok":
                if expected_version is None or version == expected_version:
                    self.say(f"Health check passed: {url} reports version {version}")
                    return
                last = f"serving version {version}, expected {expected_version}"
            else:
                last = f"HTTP {status}"
            self.say(f"Health check not passing yet ({last}), retrying...")
            self.sleep(self.poll_seconds)
        raise DeployError(f"Health check failed after {self.timeout}s: {last}")

    def release(self, new_image: str, version: str) -> None:
        deploy_id = self.trigger(new_image)
        self.wait_until_live(deploy_id)
        self.health_check(version)


def run(deployer: Deployer, new_image: str, stable_image: str, version: str, rollback: bool) -> str:
    """Return 'deployed', 'rolled_back' or 'failed'."""
    try:
        deployer.release(new_image, version)
        return "deployed"
    except DeployError as exc:
        deployer.say(f"::error title=Deploy failed::{exc}")
        if not rollback:
            return "failed"
    deployer.say(f"Rolling back to {stable_image}")
    try:
        deploy_id = deployer.trigger(stable_image)
        deployer.wait_until_live(deploy_id)
        deployer.health_check(None)
        deployer.say("Rollback complete: the previous stable version is serving again")
        return "rolled_back"
    except DeployError as exc:
        deployer.say(f"::error title=Rollback failed::{exc}")
        return "failed"


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"::error::Missing required environment variable {name}")
    return value


def main() -> int:
    deployer = Deployer(
        http=Http(api_key=_require("RENDER_API_KEY")),
        service_id=_require("RENDER_SERVICE_ID"),
        app_url=_require("APP_URL"),
        health_path=os.environ.get("HEALTH_PATH", "/api/health"),
        timeout=int(os.environ.get("HEALTH_TIMEOUT", "300")),
    )
    result = run(
        deployer,
        new_image=_require("NEW_IMAGE"),
        stable_image=_require("STABLE_IMAGE"),
        version=_require("EXPECTED_VERSION"),
        rollback=os.environ.get("ROLLBACK", "true") == "true",
    )
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"result={result}\n")
    return 0 if result == "deployed" else 1


if __name__ == "__main__":
    sys.exit(main())
