import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deploy_vercel import DeployError, VercelDeployer, run  # noqa: E402

PROD = "https://my-app.vercel.app"
OLD = "https://my-app-old111.vercel.app"
NEW = "https://my-app-new222.vercel.app"


class FakeVercel:
    """Simulates the Vercel CLI, the Vercel API and the deployed app."""

    def __init__(self, versions, deploy_fails=False, protected=False, has_previous=True):
        self.versions = versions          # deployment URL -> version it reports (None = broken)
        self.deploy_fails = deploy_fails
        self.protected = protected        # Deployment Protection on non-production URLs
        self.domain_target = OLD if has_previous else None
        self.has_previous = has_previous
        self.commands = []

    def run(self, args):
        self.commands.append(args[1:-2])  # drop "vercel" and the token flag
        if args[1] == "deploy":
            if self.deploy_fails:
                raise DeployError("build failed")
            return f"Vercel CLI\nInspect: https://vercel.com/x\n{NEW}\n"
        if args[1] == "promote":
            self.domain_target = args[2]
            return ""
        raise AssertionError(args)

    def http(self, url, headers):
        if url.startswith("https://api.vercel.com/v13/deployments/"):
            if not self.has_previous:
                return 404, {}
            return 200, {"url": OLD.removeprefix("https://")}
        base = url.rsplit("/api/health", 1)[0]
        target = self.domain_target if base == PROD else base
        if base != PROD and self.protected and "x-vercel-protection-bypass" not in headers:
            return 401, {}
        version = self.versions.get(target)
        if version is None:
            return 500, {}
        return 200, {"status": "ok", "version": version}


def make(fake, bypass=""):
    clock = iter(range(0, 10_000, 5))
    return VercelDeployer(
        token="t", org_id="team_abc", app_url=PROD, health_path="/api/health", timeout=30,
        bypass_secret=bypass, run=fake.run, http=fake.http,
        sleep=lambda s: None, clock=lambda: next(clock),
    )


def test_healthy_release_is_promoted():
    fake = FakeVercel({OLD: "v1", NEW: "v2"})
    assert run(make(fake), "v2", rollback=True) == "deployed"
    assert fake.domain_target == NEW
    assert fake.commands[0] == ["deploy", "--prod", "--skip-domain", "--yes"]


def test_unhealthy_candidate_is_never_promoted():
    fake = FakeVercel({OLD: "v1", NEW: None})
    assert run(make(fake), "v2", rollback=True) == "blocked"
    assert fake.domain_target == OLD          # users never saw the broken build
    assert not any(c[0] == "promote" for c in fake.commands)


def test_wrong_version_on_candidate_blocks_release():
    fake = FakeVercel({OLD: "v1", NEW: "v1"})
    assert run(make(fake), "v2", rollback=True) == "blocked"


def test_failed_build_blocks_release():
    fake = FakeVercel({OLD: "v1"}, deploy_fails=True)
    assert run(make(fake), "v2", rollback=True) == "blocked"
    assert fake.domain_target == OLD


def test_protection_needs_bypass_secret():
    fake = FakeVercel({OLD: "v1", NEW: "v2"}, protected=True)
    assert run(make(fake), "v2", rollback=True) == "blocked"
    fake = FakeVercel({OLD: "v1", NEW: "v2"}, protected=True)
    assert run(make(fake, bypass="secret"), "v2", rollback=True) == "deployed"


def test_production_failure_rolls_back_to_previous():
    fake = FakeVercel({OLD: "v1", NEW: "v2"})
    deployer = make(fake)
    real_promote = deployer.promote

    def promote_then_break(url):
        real_promote(url)
        if url == NEW:
            fake.versions[NEW] = None   # breaks only once it receives real traffic

    deployer.promote = promote_then_break
    assert run(deployer, "v2", rollback=True) == "rolled_back"
    assert fake.domain_target == OLD


def test_no_rollback_on_first_deploy_without_previous():
    fake = FakeVercel({NEW: "v2"}, has_previous=False)
    deployer = make(fake)
    real_promote = deployer.promote

    def promote_then_break(url):
        real_promote(url)
        fake.versions[NEW] = None

    deployer.promote = promote_then_break
    assert run(deployer, "v2", rollback=True) == "failed"
