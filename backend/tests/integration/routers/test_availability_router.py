from uuid import uuid4

from app.schemas.models import DayOfWeek
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_availability


class TestGetWorkerAvailability:
    def test_returns_200_with_records(self, mock_availability_service):
        worker_id = uuid4()
        records = [
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.SUNDAY),
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.WEDNESDAY),
        ]
        mock_availability_service.get_worker_availability.return_value = records
        client = make_client(availability_service=mock_availability_service)

        response = client.get(f"/api/v1/availability/workers/{worker_id}")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_returns_empty_list_when_none(self, mock_availability_service):
        mock_availability_service.get_worker_availability.return_value = []
        client = make_client(availability_service=mock_availability_service)

        response = client.get(f"/api/v1/availability/workers/{uuid4()}")
        assert response.status_code == 200
        assert response.json() == []


class TestSetAvailability:
    def test_returns_201_on_create(self, mock_availability_service):
        worker_id = uuid4()
        record = make_availability(worker_id=worker_id)
        mock_availability_service.set_availability.return_value = record
        client = make_client(availability_service=mock_availability_service)

        response = client.post("/api/v1/availability", json={
            "worker_id": str(worker_id),
            "availability_type": "recurring",
            "day_of_week": "sunday",
            "is_available": True,
        })
        assert response.status_code == 201

    def test_returns_400_on_invalid_data(self, mock_availability_service):
        mock_availability_service.set_availability.side_effect = ValueError("invalid")
        client = make_client(availability_service=mock_availability_service)

        # Missing day_of_week for recurring type
        response = client.post("/api/v1/availability", json={
            "worker_id": str(uuid4()),
            "availability_type": "recurring",
            "is_available": True,
        })
        assert response.status_code == 422  # Pydantic validation error


class TestUpdateAvailability:
    def test_returns_200_on_update(self, mock_availability_service):
        record = make_availability(is_available=False)
        mock_availability_service.update_availability.return_value = record
        client = make_client(availability_service=mock_availability_service)

        response = client.patch(
            f"/api/v1/availability/{record.id}",
            json={"is_available": False},
        )
        assert response.status_code == 200
        assert response.json()["is_available"] is False

    def test_returns_404_when_not_found(self, mock_availability_service):
        mock_availability_service.update_availability.side_effect = ValueError("not found")
        client = make_client(availability_service=mock_availability_service)

        response = client.patch(
            f"/api/v1/availability/{uuid4()}",
            json={"is_available": False},
        )
        assert response.status_code == 404


class TestBulkSetAvailability:
    def test_returns_200_with_all_records(self, mock_availability_service):
        worker_id = uuid4()
        records = [
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.SUNDAY),
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.WEDNESDAY),
        ]
        mock_availability_service.bulk_set_availability.return_value = records
        client = make_client(availability_service=mock_availability_service)

        response = client.post(f"/api/v1/availability/workers/{worker_id}/bulk", json=[
            {"worker_id": str(worker_id), "availability_type": "recurring", "day_of_week": "sunday"},
            {"worker_id": str(worker_id), "availability_type": "recurring", "day_of_week": "wednesday"},
        ])
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestClearWorkerAvailability:
    def test_returns_204_on_clear(self, mock_availability_service):
        worker_id = uuid4()
        client = make_client(availability_service=mock_availability_service)

        response = client.delete(f"/api/v1/availability/workers/{worker_id}")
        assert response.status_code == 204
        mock_availability_service.clear_worker_availability.assert_called_once()
