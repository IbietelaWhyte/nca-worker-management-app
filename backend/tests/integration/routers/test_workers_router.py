from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.models import UserRole
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_worker


class TestListWorkers:
    def test_returns_200_with_workers(self, mock_worker_service):
        workers = [make_worker(), make_worker()]
        mock_worker_service.get_all_workers.return_value = workers
        client = make_client(worker_service=mock_worker_service)

        response = client.get("/api/v1/workers")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_returns_active_only_when_flag_set(self, mock_worker_service):
        active = [make_worker()]
        mock_worker_service.get_active_workers.return_value = active
        client = make_client(worker_service=mock_worker_service)

        response = client.get("/api/v1/workers?active_only=true")
        assert response.status_code == 200
        mock_worker_service.get_active_workers.assert_called_once()

    def test_returns_search_results_when_query_provided(self, mock_worker_service):
        mock_worker_service.search_workers.return_value = [make_worker()]
        client = make_client(worker_service=mock_worker_service)

        response = client.get("/api/v1/workers?search=john")
        assert response.status_code == 200
        mock_worker_service.search_workers.assert_called_once_with("john")

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
        mock_worker_service.get_worker.side_effect = ValueError("not found")
        client = make_client(worker_service=mock_worker_service)

        response = client.get(f"/api/v1/workers/{uuid4()}")
        assert response.status_code == 404


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
        mock_worker_service.create_worker.side_effect = ValueError("already exists")
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


class TestUpdateWorker:
    def test_returns_200_on_update(self, mock_worker_service):
        worker = make_worker(first_name="Jane")
        mock_worker_service.update_worker.return_value = worker
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.patch(f"/api/v1/workers/{worker.id}", json={"first_name": "Jane"})
        assert response.status_code == 200
        assert response.json()["first_name"] == "Jane"

    def test_returns_404_when_not_found(self, mock_worker_service):
        mock_worker_service.update_worker.side_effect = ValueError("not found")
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

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
