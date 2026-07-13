from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.auth import install_auth_middleware
from app.config import Settings


pytestmark = pytest.mark.unit


def _protected_client() -> TestClient:
    app = FastAPI()
    install_auth_middleware(app, Settings(helixforge_api_token="test-admin-token"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/tools/health")
    def tools_health():
        return {"ok": True}

    @app.get("/api/private")
    def private():
        return {"ok": True}

    return TestClient(app)


def test_bearer_auth_protects_all_non_basic_health_apis():
    client = _protected_client()
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/tools/health").status_code == 401
    assert client.get("/api/private").status_code == 401
    assert client.get("/openapi.json").status_code == 401
    assert client.get("/").status_code == 401
    assert client.get(
        "/api/private", headers={"Authorization": "Bearer test-admin-token"}
    ).status_code == 200


def test_cors_preflight_is_not_rejected_by_bearer_middleware():
    client = _protected_client()
    response = client.options(
        "/api/private",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_headers_are_present_on_unauthorized_response():
    response = _protected_client().get(
        "/api/private", headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_production_refuses_to_start_without_token():
    with pytest.raises(RuntimeError, match="HELIXFORGE_API_TOKEN"):
        Settings(environment="production", helixforge_api_token="").validate_security_config()


def test_production_refuses_weak_or_malformed_token():
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        Settings(
            environment="production", helixforge_api_token="too-short"
        ).validate_security_config()
    with pytest.raises(RuntimeError, match="whitespace or control characters"):
        Settings(
            environment="production", helixforge_api_token=" x" * 32
        ).validate_security_config()
