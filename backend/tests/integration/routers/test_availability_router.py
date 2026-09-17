from datetime import date, timedelta
from uuid import uuid4

from app.core.exceptions import BadRequestError, NotFoundError
from app.schemas.availabilities.models import AvailabilityConfig, PublicAvailabilityResponse
from app.schemas.models import AvailabilityType, DayOfWeek
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_availability


class TestGetWorkerAvailability:
    def test_returns_200_with_records(self, mock_availability_service, mock_worker_service):
        worker_id = uuid4()
        records = [
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.SUNDAY),
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.WEDNESDAY),
        ]
        mock_availability_service.get_worker_availability.return_value = records
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        response = client.get(f"/api/v1/availability/workers/{worker_id}")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_returns_empty_list_when_none(self, mock_availability_service, mock_worker_service):
        mock_availability_service.get_worker_availability.return_value = []
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        response = client.get(f"/api/v1/availability/workers/{uuid4()}")
        assert response.status_code == 200
        assert response.json() == []


class TestSetAvailability:
    def test_returns_201_on_create(self, mock_availability_service, mock_worker_service):
        worker_id = uuid4()
        record = make_availability(worker_id=worker_id)
        mock_availability_service.set_availability.return_value = record
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        response = client.post(
            "/api/v1/availability",
            json={
                "worker_id": str(worker_id),
                "availability_type": "recurring",
                "day_of_week": "sunday",
                "is_available": True,
            },
        )
        assert response.status_code == 201

    def test_returns_400_on_invalid_data(self, mock_availability_service, mock_worker_service):
        mock_availability_service.set_availability.side_effect = BadRequestError("invalid")
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        # Missing day_of_week for recurring type
        response = client.post(
            "/api/v1/availability",
            json={
                "worker_id": str(uuid4()),
                "availability_type": "recurring",
                "is_available": True,
            },
        )
        assert response.status_code == 422  # Pydantic validation error


class TestUpdateAvailability:
    def test_returns_200_on_update(self, mock_availability_service, mock_worker_service):
        record = make_availability(is_available=False)
        mock_availability_service.update_availability.return_value = record
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        response = client.patch(
            f"/api/v1/availability/{record.id}",
            json={"is_available": False},
        )
        assert response.status_code == 200
        assert response.json()["is_available"] is False

    def test_returns_404_when_not_found(self, mock_availability_service, mock_worker_service):
        mock_availability_service.update_availability.side_effect = NotFoundError("not found")
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        response = client.patch(
            f"/api/v1/availability/{uuid4()}",
            json={"is_available": False},
        )
        assert response.status_code == 404


class TestBulkSetAvailability:
    def test_returns_200_with_all_records(self, mock_availability_service, mock_worker_service):
        worker_id = uuid4()
        records = [
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.SUNDAY),
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.WEDNESDAY),
        ]
        mock_availability_service.bulk_set_availability.return_value = records
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        response = client.post(
            f"/api/v1/availability/workers/{worker_id}/bulk",
            json=[
                {"worker_id": str(worker_id), "availability_type": "recurring", "day_of_week": "sunday"},
                {"worker_id": str(worker_id), "availability_type": "recurring", "day_of_week": "wednesday"},
            ],
        )
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestClearWorkerAvailability:
    def test_returns_204_on_clear(self, mock_availability_service, mock_worker_service):
        worker_id = uuid4()
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        response = client.delete(f"/api/v1/availability/workers/{worker_id}")
        assert response.status_code == 204
        mock_availability_service.clear_worker_availability.assert_called_once()


class TestAvailabilityConfig:
    def test_returns_the_cut_off(self, mock_availability_service, mock_worker_service):
        editable_from = date.today() + timedelta(days=7)
        mock_availability_service.get_config.return_value = AvailabilityConfig(
            editable_from=editable_from, notice_days=7
        )
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        response = client.get("/api/v1/availability/config")
        assert response.status_code == 200
        assert response.json() == {"editable_from": editable_from.isoformat(), "notice_days": 7}

    def test_config_is_not_swallowed_by_the_record_routes(self, mock_availability_service, mock_worker_service):
        # PATCH and DELETE /{availability_id} sit on the same prefix. "config" is not a UUID, so
        # it must resolve to its own route rather than 422 on the path parameter.
        mock_availability_service.get_config.return_value = AvailabilityConfig(
            editable_from=date.today(), notice_days=0
        )
        client = make_client(availability_service=mock_availability_service, worker_service=mock_worker_service)

        assert client.get("/api/v1/availability/config").status_code == 200


class TestPublicLinkEndpoints:
    """The token-authenticated page. No session — the link is the credential."""

    def test_marking_a_date_needs_no_is_available_flag(
        self, mock_availability_service, mock_worker_service, mock_confirmation_token_service
    ):
        # The page asks one question, so the body carries one field. Sending a flag would let it
        # write "available" rows, which mean nothing now that an unmarked date says the same.
        worker_id = uuid4()
        target = date.today() + timedelta(days=30)
        mock_confirmation_token_service.resolve_worker_id.return_value = worker_id
        mock_availability_service.mark_unavailable.return_value = make_availability(
            worker_id=worker_id,
            availability_type=AvailabilityType.SPECIFIC_DATE,
            specific_date=target,
            day_of_week=None,
            is_available=False,
        )
        client = make_client(
            availability_service=mock_availability_service,
            worker_service=mock_worker_service,
            confirmation_token_service=mock_confirmation_token_service,
        )

        response = client.put(
            f"/api/v1/availability/link/{uuid4()}",
            json={"specific_date": target.isoformat()},
        )
        assert response.status_code == 200
        mock_availability_service.mark_unavailable.assert_called_once_with(worker_id, target)

    def test_a_closed_date_comes_back_as_400_with_the_reason(
        self, mock_availability_service, mock_worker_service, mock_confirmation_token_service
    ):
        # The page renders this text verbatim; the server is the only side that knows the cut-off.
        mock_confirmation_token_service.resolve_worker_id.return_value = uuid4()
        mock_availability_service.mark_unavailable.side_effect = BadRequestError(
            "Availability for 01 Sep 2026 has closed. You can still change 17 Sep 2026 onwards."
        )
        client = make_client(
            availability_service=mock_availability_service,
            worker_service=mock_worker_service,
            confirmation_token_service=mock_confirmation_token_service,
        )

        response = client.put(
            f"/api/v1/availability/link/{uuid4()}",
            json={"specific_date": "2026-09-01"},
        )
        assert response.status_code == 400
        assert "has closed" in response.json()["detail"]

    def test_reading_the_page_returns_the_dates_and_the_cut_off(
        self, mock_availability_service, mock_worker_service, mock_confirmation_token_service
    ):
        mock_confirmation_token_service.resolve_worker_id.return_value = uuid4()
        mock_availability_service.get_public_availability.return_value = PublicAvailabilityResponse(
            worker_name="Ada Lovelace",
            dates=[],
            editable_from=date(2026, 9, 17),
        )
        client = make_client(
            availability_service=mock_availability_service,
            worker_service=mock_worker_service,
            confirmation_token_service=mock_confirmation_token_service,
        )

        response = client.get(f"/api/v1/availability/link/{uuid4()}")
        assert response.status_code == 200
        assert response.json()["editable_from"] == "2026-09-17"
