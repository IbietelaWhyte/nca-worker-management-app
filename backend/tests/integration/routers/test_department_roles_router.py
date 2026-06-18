from uuid import uuid4

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.schemas.models import UserRole
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_department_role


class TestGetRole:
    def test_returns_200_when_found(self, mock_department_role_service):
        role = make_department_role()
        mock_department_role_service.get_role.return_value = role
        client = make_client(department_role_service=mock_department_role_service)

        response = client.get(f"/api/v1/roles/{role.id}")
        assert response.status_code == 200

    def test_returns_404_when_not_found(self, mock_department_role_service):
        mock_department_role_service.get_role.side_effect = NotFoundError("not found")
        client = make_client(department_role_service=mock_department_role_service)

        response = client.get(f"/api/v1/roles/{uuid4()}")
        assert response.status_code == 404


class TestCreateRole:
    def test_hod_can_create(self, mock_department_role_service):
        dept_id = uuid4()
        role = make_department_role(department_id=dept_id, name="Teacher")
        mock_department_role_service.create_role.return_value = role
        client = make_client(role=UserRole.HOD, department_role_service=mock_department_role_service)

        response = client.post(
            "/api/v1/roles",
            json={"department_id": str(dept_id), "name": "Teacher"},
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Teacher"

    def test_returns_409_on_duplicate_name(self, mock_department_role_service):
        mock_department_role_service.create_role.side_effect = ConflictError("already exists")
        client = make_client(role=UserRole.HOD, department_role_service=mock_department_role_service)

        response = client.post("/api/v1/roles", json={"department_id": str(uuid4()), "name": "Teacher"})
        assert response.status_code == 409

    def test_returns_403_for_worker_role(self, mock_department_role_service):
        client = make_client(role=UserRole.WORKER, department_role_service=mock_department_role_service)
        response = client.post("/api/v1/roles", json={"department_id": str(uuid4()), "name": "Teacher"})
        assert response.status_code == 403


class TestUpdateRole:
    def test_hod_can_update(self, mock_department_role_service):
        role = make_department_role(name="Helper")
        mock_department_role_service.update_role.return_value = role
        client = make_client(role=UserRole.HOD, department_role_service=mock_department_role_service)

        response = client.patch(f"/api/v1/roles/{role.id}", json={"name": "Helper"})
        assert response.status_code == 200
        assert response.json()["name"] == "Helper"


class TestDeleteRole:
    def test_hod_can_delete(self, mock_department_role_service):
        role = make_department_role()
        client = make_client(role=UserRole.HOD, department_role_service=mock_department_role_service)

        response = client.delete(f"/api/v1/roles/{role.id}")
        assert response.status_code == 204
        mock_department_role_service.delete_role.assert_called_once_with(role.id)

    def test_returns_403_for_worker_role(self, mock_department_role_service):
        client = make_client(role=UserRole.WORKER, department_role_service=mock_department_role_service)
        response = client.delete(f"/api/v1/roles/{uuid4()}")
        assert response.status_code == 403


class TestAssignWorkerRole:
    def test_returns_200_on_successful_assignment(self, mock_department_role_service):
        role_id = uuid4()
        worker_id = uuid4()
        client = make_client(role=UserRole.HOD, department_role_service=mock_department_role_service)

        response = client.post(f"/api/v1/roles/{role_id}/workers/{worker_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Role assigned to worker successfully"
        mock_department_role_service.assign_worker.assert_called_once_with(role_id, worker_id)

    def test_returns_400_when_worker_not_in_department(self, mock_department_role_service):
        mock_department_role_service.assign_worker.side_effect = BadRequestError("not assigned to department")
        client = make_client(role=UserRole.HOD, department_role_service=mock_department_role_service)

        response = client.post(f"/api/v1/roles/{uuid4()}/workers/{uuid4()}")
        assert response.status_code == 400

    def test_returns_403_for_worker_role(self, mock_department_role_service):
        client = make_client(role=UserRole.WORKER, department_role_service=mock_department_role_service)
        response = client.post(f"/api/v1/roles/{uuid4()}/workers/{uuid4()}")
        assert response.status_code == 403


class TestUnassignWorkerRole:
    def test_returns_204_on_successful_unassignment(self, mock_department_role_service):
        role_id = uuid4()
        worker_id = uuid4()
        client = make_client(role=UserRole.HOD, department_role_service=mock_department_role_service)

        response = client.delete(f"/api/v1/roles/{role_id}/workers/{worker_id}")
        assert response.status_code == 204
        mock_department_role_service.unassign_worker.assert_called_once_with(role_id, worker_id)

    def test_returns_403_for_worker_role(self, mock_department_role_service):
        client = make_client(role=UserRole.WORKER, department_role_service=mock_department_role_service)
        response = client.delete(f"/api/v1/roles/{uuid4()}/workers/{uuid4()}")
        assert response.status_code == 403
