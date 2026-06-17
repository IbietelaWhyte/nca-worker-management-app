from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.supabase import get_supabase
from app.main import app


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


class TestHealthCheck:
    def test_basic_health_returns_ok(self):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestDbHealthCheck:
    def test_returns_connected_when_db_reachable(self):
        client_mock = MagicMock()
        app.dependency_overrides[get_supabase] = lambda: client_mock

        response = TestClient(app).get("/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "connected"}

    def test_returns_503_and_hides_error_when_db_unreachable(self):
        client_mock = MagicMock()
        client_mock.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception(
            "FATAL: password authentication failed for user 'postgres'"
        )
        app.dependency_overrides[get_supabase] = lambda: client_mock

        response = TestClient(app).get("/health/db")
        assert response.status_code == 503
        body = response.json()
        assert body == {"status": "error", "database": "unavailable"}
        # The raw driver error must never leak to the caller.
        assert "password" not in response.text
