"""Blue-green deploy to Vercel with health checks and automatic rollback.

Flow:
  1. Note which deployment currently serves the production domain
     (the rollback target).
  2. Build a new production deployment WITHOUT pointing the domain at it
     (`vercel deploy --prod --skip-domain`). Users still see the old version.
  3. Health-check the new deployment directly: /api/health must answer with
     the new commit SHA.
     - Unhealthy: stop here. The domain was never switched, so production
       keeps serving the last healthy version. The pipeline fails.
  4. Healthy: point the production domain at it (`vercel promote`).
  5. Health-check the production domain itself.
     - Unhealthy and rollback enabled: promote the previous deployment
       back onto the domain, then fail the pipeline.

Settings come from environment variables set by the workflow:
  VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID  - Vercel access (GitHub secrets;
                                                   the CLI reads the IDs itself)
  APP_URL                     - production URL, e.g. https://my-app.vercel.app
  VERCEL_AUTOMATION_BYPASS_SECRET - optional; lets the health check reach the
                                    not-yet-public deployment when Vercel
                                    Deployment Protection is on
  EXPECTED_VERSION            - commit SHA the health check must report
  HEALTH_PATH, HEALTH_TIMEOUT - from pipeline-config.yml
  ROLLBACK                    - "true" or "false"

Exit code 0 = new version is live and healthy; 1 = it is not.
"""

from __future__ import annotations

import json
import os
import subprocess  # noqa: S404  (runs the fixed `vercel` CLI, no shell)
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

API = "https://api.vercel.com"


class DeployError(RuntimeError):
    pass


def default_runner(args: list[str]) -> str:
    """Run a CLI command and return its stdout; raise DeployError on failure."""
    result = subprocess.run(args, capture_output=True, text=True, timeout=900)  # noqa: S603
    if result.returncode != 0:
        raise DeployError(f"`{' '.join(args[:3])} ...` failed: {result.stderr.strip()[-500:]}")
    return result.stdout


def default_http(url: str, headers: dict[str, str]) -> tuple[int, dict]:
    req = urllib.request.Request(url, method="GET")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return 0, {"error": str(exc)}


@dataclass
class VercelDeployer:
    token: str
    org_id: str
    app_url: str
    health_path: str
    timeout: int
    bypass_secret: str = ""
    run: Callable[[list[str]], str] = default_runner
    http: Callable[[str, dict[str, str]], tuple[int, dict]] = default_http
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    poll_seconds: float = 10.0
    log: list[str] = field(default_factory=list)

    def say(self, message: str) -> None:
        self.log.append(message)
        print(message, flush=True)

    def cli(self, *args: str) -> str:
        return self.run(["vercel", *args, "--token", self.token])

    def current_production(self) -> str | None:
        """URL of the deployment the production domain points to right now."""
        host = urllib.parse.urlparse(self.app_url).netloc or self.app_url
        url = f"{API}/v13/deployments/{host}"
        if self.org_id.startswith("team_"):
            url += f"?teamId={self.org_id}"
        status, body = self.http(url, {"Authorization": f"Bearer {self.token}"})
        if status == 200 and body.get("url"):
            return "https://" + body["url"]
        self.say("No current production deployment found (first deploy?); rollback target unavailable")
        return None

    def deploy_candidate(self) -> str:
        output = self.cli("deploy", "--prod", "--skip-domain", "--yes")
        lines = [line.strip() for line in output.splitlines() if line.strip().startswith("https://")]
        if not lines:
            raise DeployError(f"could not find the deployment URL in Vercel's output: {output[-300:]}")
        self.say(f"New deployment built (not public yet): {lines[-1]}")
        return lines[-1]

    def promote(self, deployment_url: str) -> None:
        self.cli("promote", deployment_url)
        self.say(f"Production domain now points to {deployment_url}")

    def health_check(self, base_url: str, expected_version: str | None, use_bypass: bool) -> None:
        url = base_url.rstrip("/") + self.health_path
        headers = {}
        if use_bypass and self.bypass_secret:
            headers["x-vercel-protection-bypass"] = self.bypass_secret
        deadline = self.clock() + self.timeout
        last = "no response"
        while self.clock() < deadline:
            status, body = self.http(url, headers)
            version = body.get("version")
            if status == 200 and body.get("status") == "ok":
                if expected_version is None or version == expected_version:
                    self.say(f"Health check passed: {url} reports version {version}")
                    return
                last = f"serving version {version}, expected {expected_version}"
            elif status == 401:
                last = "HTTP 401 (Deployment Protection is on; add VERCEL_AUTOMATION_BYPASS_SECRET)"
            else:
                last = f"HTTP {status}"
            self.say(f"Health check not passing yet ({last}), retrying...")
            self.sleep(self.poll_seconds)
        raise DeployError(f"health check failed for {url} after {self.timeout}s: {last}")


def run(deployer: VercelDeployer, version: str, rollback: bool) -> str:
    """Return 'deployed', 'blocked', 'rolled_back' or 'failed'."""
    previous = deployer.current_production()

    try:
        candidate = deployer.deploy_candidate()
        deployer.health_check(candidate, version, use_bypass=True)
    except DeployError as exc:
        deployer.say(f"::error title=Release blocked::{exc}")
        deployer.say("Production domain was not switched; users keep the last healthy version.")
        return "blocked"

    try:
        deployer.promote(candidate)
        deployer.health_check(deployer.app_url, version, use_bypass=False)
        return "deployed"
    except DeployError as exc:
        deployer.say(f"::error title=Production check failed::{exc}")

    if not rollback or not previous:
        return "failed"
    deployer.say(f"Rolling back: pointing the production domain back to {previous}")
    try:
        deployer.promote(previous)
        deployer.health_check(deployer.app_url, None, use_bypass=False)
        deployer.say("Rollback complete: the previous version is serving again")
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
    deployer = VercelDeployer(
        token=_require("VERCEL_TOKEN"),
        org_id=_require("VERCEL_ORG_ID"),
        app_url=_require("APP_URL"),
        health_path=os.environ.get("HEALTH_PATH", "/api/health"),
        timeout=int(os.environ.get("HEALTH_TIMEOUT", "300")),
        bypass_secret=os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET", ""),
    )
    result = run(deployer, _require("EXPECTED_VERSION"), os.environ.get("ROLLBACK", "true") == "true")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"result={result}\n")
    return 0 if result == "deployed" else 1


if __name__ == "__main__":
    sys.exit(main())
