import base64

import pytest
from fastapi import FastAPI


@pytest.fixture(autouse=True)
def clear_docs_env(monkeypatch: pytest.MonkeyPatch):
    for key in (
        "ENVIRONMENT",
        "APP_ENV",
        "DISABLE_API_DOCS",
        "DOCS_BASIC_USER",
        "DOCS_BASIC_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)


def test_defaults_keep_docs_urls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    from app.docs_access import docs_fastapi_kwargs

    assert docs_fastapi_kwargs() == {}


@pytest.mark.parametrize("env_key", ["ENVIRONMENT", "APP_ENV"])
def test_production_without_basic_disables_urls(env_key: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(env_key, "production")
    from app.docs_access import docs_fastapi_kwargs

    assert docs_fastapi_kwargs() == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }


def test_prod_with_basic_keeps_urls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DOCS_BASIC_USER", "adm")
    monkeypatch.setenv("DOCS_BASIC_PASSWORD", "sekret")
    from app.docs_access import docs_fastapi_kwargs

    assert docs_fastapi_kwargs() == {}


def test_disable_flag_overrides_basic(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DOCS_BASIC_USER", "adm")
    monkeypatch.setenv("DOCS_BASIC_PASSWORD", "sekret")
    monkeypatch.setenv("DISABLE_API_DOCS", "1")
    from app.docs_access import docs_fastapi_kwargs, should_use_docs_basic_middleware

    assert docs_fastapi_kwargs() == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    assert should_use_docs_basic_middleware() is False


def test_basic_middleware_allows_with_valid_header(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DOCS_BASIC_USER", "owner")
    monkeypatch.setenv("DOCS_BASIC_PASSWORD", "correct horse battery staple")
    from fastapi.testclient import TestClient

    from app.docs_access import add_docs_basic_auth_middleware, docs_fastapi_kwargs

    app = FastAPI(**docs_fastapi_kwargs())

    @app.get("/health")
    def _health():
        return {"ok": True}

    @app.get("/services")
    def _services():
        return []

    add_docs_basic_auth_middleware(app)
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/services").status_code == 200
    assert client.get("/openapi.json").status_code == 401
    token = base64.b64encode(b"owner:correct horse battery staple").decode("ascii")
    r = client.get("/openapi.json", headers={"Authorization": f"Basic {token}"})
    assert r.status_code == 200


def test_basic_middleware_rejects_bad_password(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DOCS_BASIC_USER", "u")
    monkeypatch.setenv("DOCS_BASIC_PASSWORD", "good")
    from fastapi.testclient import TestClient

    from app.docs_access import add_docs_basic_auth_middleware, docs_fastapi_kwargs

    app = FastAPI(**docs_fastapi_kwargs())
    add_docs_basic_auth_middleware(app)
    client = TestClient(app)
    bad = base64.b64encode(b"u:wrong").decode("ascii")
    assert client.get("/openapi.json", headers={"Authorization": f"Basic {bad}"}).status_code == 401
