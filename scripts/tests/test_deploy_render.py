import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deploy_render import Deployer, Http, run  # noqa: E402

NEW = "ghcr.io/owner/my-cicd-app:abc123"
STABLE = "ghcr.io/owner/my-cicd-app:stable"


class FakeRender:
    """Simulates the Render API and the deployed app."""

    def __init__(self, deploy_states, serving_version):
        self.deploy_states = deploy_states  # image -> final deploy status
        self.serving = serving_version      # image -> version the app reports
        self.current = None
        self.deploys = {}
        self.calls = []

    def __call__(self, method, url, body, auth):
        self.calls.append((method, url, body))
        if method == "POST" and url.endswith("/deploys"):
            deploy_id = f"dep-{len(self.deploys) + 1}"
            self.deploys[deploy_id] = body["imageUrl"]
            return 201, {"id": deploy_id, "status": "created"}
        if method == "GET" and "/deploys/" in url:
            image = self.deploys[url.rsplit("/", 1)[1]]
            state = self.deploy_states[image]
            if state == "live":
                self.current = image
            return 200, {"status": state}
        if method == "GET" and url.endswith("/api/health"):
            if self.current is None:
                return 503, {}
            return 200, {"status": "ok", "version": self.serving[self.current]}
        return 404, {}


def make(fake):
    clock = iter(range(0, 10_000, 5))
    return Deployer(
        http=Http(api_key="test", request=fake),
        service_id="srv-1",
        app_url="https://app.example.com",
        health_path="/api/health",
        timeout=60,
        sleep=lambda s: None,
        clock=lambda: next(clock),
    )


def test_healthy_deploy_succeeds():
    fake = FakeRender({NEW: "live"}, {NEW: "abc123"})
    assert run(make(fake), NEW, STABLE, "abc123", rollback=True) == "deployed"
    assert all(img == NEW for img in fake.deploys.values())


def test_failed_deploy_rolls_back_to_stable():
    fake = FakeRender({NEW: "update_failed", STABLE: "live"}, {STABLE: "old999"})
    assert run(make(fake), NEW, STABLE, "abc123", rollback=True) == "rolled_back"
    assert list(fake.deploys.values()) == [NEW, STABLE]


def test_wrong_version_serving_triggers_rollback():
    # Render says live, but the app still reports the old version.
    fake = FakeRender({NEW: "live", STABLE: "live"}, {NEW: "old999", STABLE: "old999"})
    assert run(make(fake), NEW, STABLE, "abc123", rollback=True) == "rolled_back"


def test_no_rollback_when_disabled():
    fake = FakeRender({NEW: "build_failed"}, {})
    assert run(make(fake), NEW, STABLE, "abc123", rollback=False) == "failed"
    assert list(fake.deploys.values()) == [NEW]


def test_rollback_failure_is_reported():
    fake = FakeRender({NEW: "update_failed", STABLE: "update_failed"}, {})
    assert run(make(fake), NEW, STABLE, "abc123", rollback=True) == "failed"
