from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.main import app
from app.schemas.authentication.models import RegisterResponse
from app.schemas.models import UserRole
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_worker


class TestListWorkers:
    def test_returns_200_with_workers(self, mock_worker_service):
        workers = [make_worker(), make_worker()]
        mock_worker_service.list_visible_workers.return_value = workers
        client = make_client(worker_service=mock_worker_service)

        response = client.get("/api/v1/workers")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_passes_active_only_flag(self, mock_worker_service):
        mock_worker_service.list_visible_workers.return_value = [make_worker()]
        client = make_client(worker_service=mock_worker_service)

        response = client.get("/api/v1/workers?active_only=true")
        assert response.status_code == 200
        assert mock_worker_service.list_visible_workers.call_args.kwargs["active_only"] is True

    def test_passes_search_query(self, mock_worker_service):
        mock_worker_service.list_visible_workers.return_value = [make_worker()]
        client = make_client(worker_service=mock_worker_service)

        response = client.get("/api/v1/workers?search=john")
        assert response.status_code == 200
        assert mock_worker_service.list_visible_workers.call_args.kwargs["search"] == "john"

    def test_passes_limit_and_offset(self, mock_worker_service):
        mock_worker_service.list_visible_workers.return_value = []
        client = make_client(worker_service=mock_worker_service)

        response = client.get("/api/v1/workers?limit=5&offset=10")
        assert response.status_code == 200
        kwargs = mock_worker_service.list_visible_workers.call_args.kwargs
        assert kwargs["limit"] == 5
        assert kwargs["offset"] == 10

    def test_rejects_out_of_range_limit(self, mock_worker_service):
        mock_worker_service.list_visible_workers.return_value = []
        client = make_client(worker_service=mock_worker_service)

        response = client.get("/api/v1/workers?limit=999")
        assert response.status_code == 422  # exceeds le=500

    def test_requires_authentication(self):
        client = TestClient(app)
        response = client.get("/api/v1/workers")
        assert response.status_code == 401


class TestGetWorker:
    def test_returns_200_when_found(self, mock_worker_service):
        worker = make_worker()
        mock_worker_service.get_worker.return_value = worker
        client = make_client(worker_service=mock_worker_service)

        response = client.get(f"/api/v1/workers/{worker.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(worker.id)

    def test_returns_404_when_not_found(self, mock_worker_service):
        mock_worker_service.get_worker.side_effect = NotFoundError("not found")
        client = make_client(worker_service=mock_worker_service)

        response = client.get(f"/api/v1/workers/{uuid4()}")
        assert response.status_code == 404

    def test_returns_403_when_not_authorized_to_view(self, mock_worker_service):
        mock_worker_service.authorize_view_worker.side_effect = PermissionDeniedError("nope")
        client = make_client(role=UserRole.WORKER, worker_service=mock_worker_service)

        response = client.get(f"/api/v1/workers/{uuid4()}")
        assert response.status_code == 403
        mock_worker_service.get_worker.assert_not_called()


class TestCreateWorker:
    def test_returns_201_when_created(self, mock_worker_service):
        worker = make_worker()
        mock_worker_service.create_worker.return_value = worker
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.post(
            "/api/v1/workers",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+14165550101",
            },
        )
        assert response.status_code == 201

    def test_returns_409_on_duplicate_email(self, mock_worker_service):
        mock_worker_service.create_worker.side_effect = ConflictError("already exists")
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.post(
            "/api/v1/workers",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+14165550101",
            },
        )
        assert response.status_code == 409

    def test_returns_403_for_non_admin(self, mock_worker_service):
        client = make_client(role=UserRole.WORKER, worker_service=mock_worker_service)

        response = client.post(
            "/api/v1/workers",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+14165550101",
            },
        )
        assert response.status_code == 403


class TestCreateWorkerAccount:
    def test_returns_201_on_success(self, mock_authentication_service):
        worker_id = uuid4()
        mock_authentication_service.create_account_for_worker.return_value = RegisterResponse(
            message="Account created successfully",
            worker_id=str(worker_id),
            email="john.doe@example.com",
        )
        client = make_client(role=UserRole.ADMIN, authentication_service=mock_authentication_service)

        response = client.post(
            f"/api/v1/workers/{worker_id}/account",
            json={"password": "securepass1", "role": "admin"},
        )
        assert response.status_code == 201
        assert response.json()["worker_id"] == str(worker_id)

    def test_returns_403_for_non_admin(self, mock_authentication_service):
        client = make_client(role=UserRole.HOD, authentication_service=mock_authentication_service)

        response = client.post(
            f"/api/v1/workers/{uuid4()}/account",
            json={"password": "securepass1", "role": "worker"},
        )
        assert response.status_code == 403
        mock_authentication_service.create_account_for_worker.assert_not_called()

    def test_returns_409_when_already_has_account(self, mock_authentication_service):
        mock_authentication_service.create_account_for_worker.side_effect = ConflictError(
            "Worker already has a login account"
        )
        client = make_client(role=UserRole.ADMIN, authentication_service=mock_authentication_service)

        response = client.post(
            f"/api/v1/workers/{uuid4()}/account",
            json={"password": "securepass1", "role": "worker"},
        )
        assert response.status_code == 409


class TestUpdateWorker:
    def test_returns_200_on_update(self, mock_worker_service):
        worker = make_worker(first_name="Jane")
        mock_worker_service.update_worker.return_value = worker
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.patch(f"/api/v1/workers/{worker.id}", json={"first_name": "Jane"})
        assert response.status_code == 200
        assert response.json()["first_name"] == "Jane"

    def test_returns_404_when_not_found(self, mock_worker_service):
        mock_worker_service.update_worker.side_effect = NotFoundError("not found")
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.patch(f"/api/v1/workers/{uuid4()}", json={"first_name": "Jane"})
        assert response.status_code == 404

    def test_returns_403_when_not_manager(self, mock_worker_service):
        # A HOD updating a worker they don't manage: the service authorization raises.
        mock_worker_service.authorize_update_worker.side_effect = PermissionDeniedError("nope")
        client = make_client(role=UserRole.HOD, worker_service=mock_worker_service)

        response = client.patch(f"/api/v1/workers/{uuid4()}", json={"first_name": "Jane"})
        assert response.status_code == 403
        mock_worker_service.update_worker.assert_not_called()

    def test_returns_404_when_actor_has_no_profile(self, mock_worker_service):
        mock_worker_service.authorize_update_worker.side_effect = NotFoundError(
            "Worker profile not found for authenticated user"
        )
        client = make_client(role=UserRole.HOD, worker_service=mock_worker_service)

        response = client.patch(f"/api/v1/workers/{uuid4()}", json={"first_name": "Jane"})
        assert response.status_code == 404


class TestDeactivateWorker:
    def test_returns_204_on_deactivate(self, mock_worker_service):
        worker = make_worker()
        mock_worker_service.deactivate_worker.return_value = worker
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.delete(f"/api/v1/workers/{worker.id}")
        assert response.status_code == 204

    def test_returns_403_for_non_admin(self, mock_worker_service):
        client = make_client(role=UserRole.WORKER, worker_service=mock_worker_service)
        response = client.delete(f"/api/v1/workers/{uuid4()}")
        assert response.status_code == 403

    def test_returns_403_when_not_manager(self, mock_worker_service):
        mock_worker_service.authorize_manage_worker.side_effect = PermissionDeniedError("nope")
        client = make_client(role=UserRole.HOD, worker_service=mock_worker_service)

        response = client.delete(f"/api/v1/workers/{uuid4()}")
        assert response.status_code == 403
        mock_worker_service.deactivate_worker.assert_not_called()
