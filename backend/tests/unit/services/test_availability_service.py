from datetime import date
from uuid import uuid4

import pytest

from app.schemas.availabilities.models import AvailabilityCreate, AvailabilityUpdate
from app.schemas.models import AvailabilityType, DayOfWeek
from app.service.availabilities.service import AvailabilityService
from tests.unit.services.conftest import make_availability


@pytest.fixture
def service(mock_availability_repo):
    return AvailabilityService(availability_repo=mock_availability_repo)


class TestGetWorkerAvailability:
    def test_returns_all_records(self, service, mock_availability_repo):
        records = [
            make_availability(day_of_week=DayOfWeek.SUNDAY),
            make_availability(day_of_week=DayOfWeek.WEDNESDAY),
        ]
        mock_availability_repo.get_by_worker.return_value = records
        worker_id = uuid4()

        result = service.get_worker_availability(worker_id)
        assert len(result) == 2
        mock_availability_repo.get_by_worker.assert_called_once_with(worker_id)

    def test_returns_empty_list_when_none(self, service, mock_availability_repo):
        mock_availability_repo.get_by_worker.return_value = []
        result = service.get_worker_availability(uuid4())
        assert result == []


class TestSetAvailability:
    def test_sets_recurring_availability(self, service, mock_availability_repo):
        worker_id = uuid4()
        record = make_availability(worker_id=worker_id, day_of_week=DayOfWeek.SUNDAY)
        mock_availability_repo.upsert_availability.return_value = record

        data = AvailabilityCreate(
            worker_id=worker_id,
            availability_type=AvailabilityType.RECURRING,
            day_of_week=DayOfWeek.SUNDAY,
            is_available=True,
        )
        result = service.set_availability(data)
        assert result.day_of_week == DayOfWeek.SUNDAY
        mock_availability_repo.upsert_availability.assert_called_once()

    def test_sets_specific_date_availability(self, service, mock_availability_repo):
        worker_id = uuid4()
        specific = date(2026, 12, 25)
        record = make_availability(
            worker_id=worker_id,
            availability_type=AvailabilityType.SPECIFIC_DATE,
            specific_date=specific,
            day_of_week=None,
            is_available=False,
        )
        mock_availability_repo.upsert_specific_date_availability.return_value = record

        data = AvailabilityCreate(
            worker_id=worker_id,
            availability_type=AvailabilityType.SPECIFIC_DATE,
            specific_date=specific,
            is_available=False,
        )
        result = service.set_availability(data)
        assert result.is_available is False
        mock_availability_repo.upsert_specific_date_availability.assert_called_once()


class TestUpdateAvailability:
    def test_updates_successfully(self, service, mock_availability_repo):
        record = make_availability()
        updated = make_availability(is_available=False)
        mock_availability_repo.get_by_id.return_value = record
        mock_availability_repo.update.return_value = updated

        result = service.update_availability(record.id, AvailabilityUpdate(is_available=False))
        assert result.is_available is False

    def test_raises_when_not_found(self, service, mock_availability_repo):
        mock_availability_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.update_availability(uuid4(), AvailabilityUpdate(is_available=False))


class TestBulkSetAvailability:
    def test_sets_multiple_days(self, service, mock_availability_repo):
        worker_id = uuid4()
        records = [
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.SUNDAY),
            make_availability(worker_id=worker_id, day_of_week=DayOfWeek.WEDNESDAY),
        ]
        mock_availability_repo.upsert_availability.side_effect = records

        data = [
            AvailabilityCreate(
                worker_id=worker_id,
                availability_type=AvailabilityType.RECURRING,
                day_of_week=DayOfWeek.SUNDAY,
                is_available=True,
            ),
            AvailabilityCreate(
                worker_id=worker_id,
                availability_type=AvailabilityType.RECURRING,
                day_of_week=DayOfWeek.WEDNESDAY,
                is_available=True,
            ),
        ]
        result = service.bulk_set_availability(worker_id, data)
        assert len(result) == 2
        assert mock_availability_repo.upsert_availability.call_count == 2


class TestClearWorkerAvailability:
    def test_clears_all_records(self, service, mock_availability_repo):
        worker_id = uuid4()
        service.clear_worker_availability(worker_id)
        mock_availability_repo.delete_worker_availability.assert_called_once_with(worker_id)
