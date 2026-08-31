from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.core.config import Settings
from app.core import config as config_module
from app.api.exception_handlers import service_error_detail
from app.core.middleware import RateLimitMiddleware, RequestContextMiddleware


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "debug": False,
        "enable_docs": False,
        "expose_error_details": False,
        "rate_limit_enabled": True,
        "database_url": (
            "postgresql+psycopg2://app:strong-password@db:5432/knowledge"
        ),
        "deepseek_api_key": "deepseek-secret",
        "siliconflow_api_key": "siliconflow-secret",
        "cors_origins": ["https://knowledge.example.com"],
        "trusted_hosts": ["api.knowledge.example.com"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_production_settings_hide_secrets() -> None:
    configured = production_settings()

    assert configured.is_production is True
    assert "deepseek-secret" not in repr(configured)
    assert configured.secret_value(configured.deepseek_api_key) == (
        "deepseek-secret"
    )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"debug": True}, "DEBUG must be false"),
        ({"enable_docs": True}, "ENABLE_DOCS must be false"),
        ({"rate_limit_enabled": False}, "RATE_LIMIT_ENABLED must be true"),
        ({"cors_origins": ["*"]}, "CORS_ORIGINS cannot contain"),
        ({"deepseek_api_key": ""}, "DEEPSEEK_API_KEY is required"),
    ],
)
def test_invalid_production_settings_are_rejected(
    override: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        production_settings(**override)


def test_request_context_adds_tracking_and_security_headers() -> None:
    application = FastAPI()
    application.add_middleware(RequestContextMiddleware)

    @application.get("/ok")
    def ok() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(application).get(
        "/ok",
        headers={"X-Request-ID": "safe-request-123"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "safe-request-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_rate_limit_returns_retry_after() -> None:
    application = FastAPI()
    application.add_middleware(
        RateLimitMiddleware,
        requests=2,
        window_seconds=60,
    )

    @application.get("/limited")
    def limited() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(application)
    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200
    response = client.get("/limited")

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limit_exceeded"
    assert int(response.headers["retry-after"]) >= 1


def test_service_error_details_can_be_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config_module.settings, "expose_error_details", False)

    detail = service_error_detail(
        RuntimeError("provider secret diagnostics"),
        "Service unavailable.",
    )

    assert detail == "Service unavailable."
