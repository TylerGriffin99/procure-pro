from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_prefix_is_derived_from_version():
    assert settings.api_version == 1
    assert settings.api_prefix == "/api/v1"


def test_routes_are_mounted_under_prefix_and_health_is_not():
    paths = {r.path for r in app.routes}
    assert "/health" in paths
    assert f"{settings.api_prefix}/auth/login" in paths
    assert f"{settings.api_prefix}/projects" in paths
    assert not any(p.startswith("/api/") and not p.startswith(settings.api_prefix) for p in paths)


def test_unversioned_path_is_gone():
    with TestClient(app) as c:
        assert c.get("/api/projects").status_code == 404
        assert c.get("/health").status_code == 200
