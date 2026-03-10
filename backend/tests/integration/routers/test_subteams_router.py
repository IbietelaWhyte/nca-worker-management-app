from uuid import uuid4

from app.schemas.models import UserRole
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_subteam


class TestGetSubteam:
    def test_returns_200_when_found(self, mock_subteam_service):
        subteam = make_subteam()
        mock_subteam_service.get_subteam.return_value = subteam
        client = make_client(subteam_service=mock_subteam_service)

        response = client.get(f"/api/v1/subteams/{subteam.id}")
        assert response.status_code == 200

    def test_returns_404_when_not_found(self, mock_subteam_service):
        mock_subteam_service.get_subteam.side_effect = ValueError("not found")
        client = make_client(subteam_service=mock_subteam_service)

        response = client.get(f"/api/v1/subteams/{uuid4()}")
        assert response.status_code == 404


class TestCreateSubteam:
    def test_returns_201_when_created(self, mock_subteam_service):
        dept_id = uuid4()
        subteam = make_subteam(department_id=dept_id, name="Toddlers", workers_per_slot=3)
        mock_subteam_service.create_subteam.return_value = subteam
        client = make_client(role=UserRole.HOD, subteam_service=mock_subteam_service)

        response = client.post(
            "/api/v1/subteams",
            json={
                "department_id": str(dept_id),
                "name": "Toddlers",
                "workers_per_slot": 3,
            },
        )
        assert response.status_code == 201
        assert response.json()["workers_per_slot"] == 3

    def test_returns_409_on_duplicate_name(self, mock_subteam_service):
        mock_subteam_service.create_subteam.side_effect = ValueError("already exists")
        client = make_client(role=UserRole.HOD, subteam_service=mock_subteam_service)

        response = client.post(
            "/api/v1/subteams",
            json={
                "department_id": str(uuid4()),
                "name": "Toddlers",
            },
        )
        assert response.status_code == 409

    def test_returns_403_for_worker_role(self, mock_subteam_service):
        client = make_client(role=UserRole.WORKER, subteam_service=mock_subteam_service)
        response = client.post(
            "/api/v1/subteams",
            json={
                "department_id": str(uuid4()),
                "name": "Toddlers",
            },
        )
        assert response.status_code == 403


class TestUpdateSubteam:
    def test_returns_200_on_update(self, mock_subteam_service):
        subteam = make_subteam(workers_per_slot=4)
        mock_subteam_service.update_subteam.return_value = subteam
        client = make_client(role=UserRole.HOD, subteam_service=mock_subteam_service)

        response = client.patch(f"/api/v1/subteams/{subteam.id}", json={"workers_per_slot": 4})
        assert response.status_code == 200
        assert response.json()["workers_per_slot"] == 4


class TestDeleteSubteam:
    def test_returns_204_on_delete(self, mock_subteam_service):
        subteam = make_subteam()
        client = make_client(role=UserRole.ADMIN, subteam_service=mock_subteam_service)

        response = client.delete(f"/api/v1/subteams/{subteam.id}")
        assert response.status_code == 204

    def test_returns_403_for_hod_role(self, mock_subteam_service):
        client = make_client(role=UserRole.HOD, subteam_service=mock_subteam_service)
        response = client.delete(f"/api/v1/subteams/{uuid4()}")
        assert response.status_code == 403
