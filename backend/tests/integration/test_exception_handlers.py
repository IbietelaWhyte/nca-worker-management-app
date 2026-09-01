from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.authentication import verify_token
from app.core.dependencies import get_worker_service
from app.core.exceptions import GoneError, NotFoundError
from app.main import app
from app.schemas.models import UserRole
from app.service.workers.service import WorkerService
from tests.integration.routers.conftest import make_client, make_token_payload


class TestAppErrorHandler:
    def test_maps_status_code_and_detail(self):
        mock_service = MagicMock(spec=WorkerService)
        mock_service.get_worker.side_effect = NotFoundError("Worker abc not found")
        client = make_client(worker_service=mock_service)

        response = client.get(f"/api/v1/workers/{uuid4()}")
        assert response.status_code == 404
        assert response.json() == {"detail": "Worker abc not found"}

    def test_gone_error_maps_to_410(self):
        # Drive an AppError subclass with a non-default status through a public endpoint.
        from app.core.dependencies import get_confirmation_token_service
        from app.service.confirmation_tokens.service import ConfirmationTokenService

        mock_service = MagicMock(spec=ConfirmationTokenService)
        mock_service.confirm.side_effect = GoneError("This link has expired")
        app.dependency_overrides[get_confirmation_token_service] = lambda: mock_service
        try:
            client = TestClient(app)
            response = client.post(f"/api/v1/confirm/{uuid4()}?assignment_id={uuid4()}&action=confirmed")
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 410
        assert response.json() == {"detail": "This link has expired"}


class TestValidationErrorHandler:
    def test_detail_is_a_string_not_a_list(self):
        # FastAPI's default 422 makes detail a list of objects while every other error makes it a
        # string. The frontend renders err.response.data.detail directly, so the default shape
        # crashes the render ("Objects are not valid as a React child").
        mock_service = MagicMock(spec=WorkerService)
        client = make_client(role=UserRole.ADMIN, worker_service=mock_service)

        response = client.post("/api/v1/workers", json={"first_name": "Ann", "last_name": "Lee"})

        assert response.status_code == 422
        assert isinstance(response.json()["detail"], str)
        mock_service.create_worker.assert_not_called()

    def test_detail_names_the_offending_field(self):
        mock_service = MagicMock(spec=WorkerService)
        client = make_client(role=UserRole.ADMIN, worker_service=mock_service)

        response = client.post(
            "/api/v1/workers",
            json={"first_name": "Ann", "last_name": "Lee", "email": "banana", "phone": "+14165550111"},
        )

        assert response.status_code == 422
        assert response.json()["detail"].startswith("email:")


class TestUnhandledExceptionHandler:
    def test_unexpected_error_returns_generic_500_without_leaking(self):
        mock_service = MagicMock(spec=WorkerService)
        mock_service.get_worker.side_effect = RuntimeError("secret connection string leaked here")
        app.dependency_overrides[verify_token] = lambda: make_token_payload()
        app.dependency_overrides[get_worker_service] = lambda: mock_service
        try:
            # raise_server_exceptions=False so the catch-all 500 handler's response is returned.
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get(f"/api/v1/workers/{uuid4()}")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
        assert "secret" not in response.text
