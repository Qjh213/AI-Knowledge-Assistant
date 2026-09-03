import pytest


@pytest.fixture
def api_service_session():
    """Mock-service contract tests only. Real auth/isolation has separate tests.

    These tests override provider services and do not exercise database access.
    Opt in explicitly; never bypass authentication globally for the test suite.
    """
    from app.api.dependencies import get_db
    from app.main import app
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = lambda: None
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
