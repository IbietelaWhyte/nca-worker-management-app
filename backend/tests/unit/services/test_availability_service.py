from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.schemas.availabilities.models import AvailabilityCreate, AvailabilityUpdate
from app.schemas.models import AvailabilityType, DayOfWeek
from app.service.availabilities.service import AvailabilityService
from tests.unit.services.conftest import make_availability, make_worker

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
NEXT_MONTH = TODAY + timedelta(days=30)


@pytest.fixture
def notice_days(monkeypatch):
    """Set the notice period for one test."""

    def _set(days: int) -> None:
        monkeypatch.setattr("app.service.availabilities.service.settings.availability_notice_days", days)

    return _set


@pytest.fixture
def service(mock_availability_repo, mock_worker_repo):
    return AvailabilityService(availability_repo=mock_availability_repo, worker_repo=mock_worker_repo)


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
        with pytest.raises(NotFoundError, match="not found"):
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


class TestTheCutOff:
    """Availability is only worth collecting while there is still time to act on it."""

    def test_a_past_date_is_refused_by_default(self, service, mock_availability_repo):
        # The case the children's church hit: entering September's availability in October.
        with pytest.raises(BadRequestError, match="has closed"):
            service.mark_unavailable(uuid4(), YESTERDAY)
        mock_availability_repo.upsert_specific_date_availability.assert_not_called()

    def test_today_is_still_open_by_default(self, service, mock_availability_repo):
        # A zero notice period closes what has passed and nothing else — someone taken ill on a
        # Sunday morning can still say so.
        mock_availability_repo.upsert_specific_date_availability.return_value = make_availability(
            availability_type=AvailabilityType.SPECIFIC_DATE, specific_date=TODAY, day_of_week=None, is_available=False
        )
        service.mark_unavailable(uuid4(), TODAY)
        mock_availability_repo.upsert_specific_date_availability.assert_called_once()

    def test_a_notice_period_closes_dates_that_are_still_ahead(self, service, mock_availability_repo, notice_days):
        notice_days(7)
        with pytest.raises(BadRequestError, match="has closed"):
            service.mark_unavailable(uuid4(), TODAY + timedelta(days=6))
        mock_availability_repo.upsert_specific_date_availability.assert_not_called()

    def test_a_date_past_the_notice_period_is_open(self, service, mock_availability_repo, notice_days):
        notice_days(7)
        target = TODAY + timedelta(days=7)
        mock_availability_repo.upsert_specific_date_availability.return_value = make_availability(
            availability_type=AvailabilityType.SPECIFIC_DATE, specific_date=target, day_of_week=None, is_available=False
        )
        service.mark_unavailable(uuid4(), target)
        mock_availability_repo.upsert_specific_date_availability.assert_called_once()

    def test_the_message_names_the_deadline(self, service, notice_days):
        # The page shows this text verbatim — it is the only place that knows the cut-off.
        notice_days(7)
        with pytest.raises(BadRequestError) as exc:
            service.mark_unavailable(uuid4(), TODAY)
        assert f"{TODAY + timedelta(days=7):%d %b %Y}" in str(exc.value)

    def test_clearing_a_closed_date_is_refused_too(self, service, mock_availability_repo):
        # Otherwise the cut-off would only stop marks going on, not coming off — and taking one
        # off after the rota is built is the more disruptive of the two.
        with pytest.raises(BadRequestError, match="has closed"):
            service.clear_specific_date(uuid4(), YESTERDAY)
        mock_availability_repo.delete_specific_date.assert_not_called()

    def test_the_authenticated_write_path_is_held_to_it_as_well(self, service, mock_availability_repo):
        data = AvailabilityCreate(
            worker_id=uuid4(),
            availability_type=AvailabilityType.SPECIFIC_DATE,
            specific_date=YESTERDAY,
            is_available=False,
        )
        with pytest.raises(BadRequestError, match="has closed"):
            service.set_availability(data)
        mock_availability_repo.upsert_specific_date_availability.assert_not_called()

    def test_deleting_a_record_on_a_closed_date_is_refused(self, service, mock_availability_repo):
        # The signed-in page clears a date by deleting its record by id, so this is the same
        # action as clear_specific_date by another route.
        record = make_availability(
            availability_type=AvailabilityType.SPECIFIC_DATE, specific_date=YESTERDAY, day_of_week=None
        )
        mock_availability_repo.get_by_id.return_value = record
        with pytest.raises(BadRequestError, match="has closed"):
            service.delete_availability(record.id)
        mock_availability_repo.delete.assert_not_called()

    def test_a_recurring_record_is_untouched_by_the_cut_off(self, service, mock_availability_repo):
        # A weekly pattern names no date, so there is nothing for a cut-off to close.
        record = make_availability(day_of_week=DayOfWeek.SUNDAY)
        mock_availability_repo.get_by_id.return_value = record
        service.delete_availability(record.id)
        mock_availability_repo.delete.assert_called_once_with(record.id)

    def test_clearing_a_whole_worker_is_not_held_to_it(self, service, mock_availability_repo):
        # A manager resetting a roster, not a worker answering for a date. Refusing it part-way
        # would leave anyone whose history straddles the cut-off permanently un-resettable.
        worker_id = uuid4()
        service.clear_worker_availability(worker_id)
        mock_availability_repo.delete_worker_availability.assert_called_once_with(worker_id)


class TestMarkUnavailable:
    def test_it_always_writes_the_negative(self, service, mock_availability_repo):
        # There is no "mark available" counterpart: the rota treats an unrecorded date as
        # available already, so the only answer worth storing is the exception.
        worker_id = uuid4()
        mock_availability_repo.upsert_specific_date_availability.return_value = make_availability(
            worker_id=worker_id,
            availability_type=AvailabilityType.SPECIFIC_DATE,
            specific_date=NEXT_MONTH,
            day_of_week=None,
            is_available=False,
        )
        service.mark_unavailable(worker_id, NEXT_MONTH)
        mock_availability_repo.upsert_specific_date_availability.assert_called_once_with(
            worker_id, NEXT_MONTH, is_available=False
        )


class TestGetPublicAvailability:
    def test_it_returns_only_the_dates_they_cannot_serve(self, service, mock_availability_repo, mock_worker_repo):
        # Rows saying "I can serve" survive from when the page asked the opposite question. Under
        # the question it asks now an unmarked date already means that, so showing them would
        # read as a contradiction.
        worker_id = uuid4()
        mock_worker_repo.get_by_id.return_value = make_worker(id=worker_id, first_name="Ada", last_name="Lovelace")
        mock_availability_repo.get_by_worker.return_value = [
            make_availability(
                availability_type=AvailabilityType.SPECIFIC_DATE,
                specific_date=NEXT_MONTH,
                day_of_week=None,
                is_available=False,
            ),
            make_availability(
                availability_type=AvailabilityType.SPECIFIC_DATE,
                specific_date=NEXT_MONTH + timedelta(days=7),
                day_of_week=None,
                is_available=True,
            ),
            make_availability(day_of_week=DayOfWeek.SUNDAY),
        ]

        result = service.get_public_availability(worker_id)
        assert result.worker_name == "Ada Lovelace"
        assert [d.specific_date for d in result.dates] == [NEXT_MONTH]

    def test_it_carries_the_cut_off_for_the_calendar(
        self, service, mock_availability_repo, mock_worker_repo, notice_days
    ):
        # The public page has no session, so it cannot call the authenticated config endpoint —
        # the cut-off has to ride along with the page's only read.
        notice_days(7)
        mock_worker_repo.get_by_id.return_value = make_worker()
        mock_availability_repo.get_by_worker.return_value = []

        result = service.get_public_availability(uuid4())
        assert result.editable_from == TODAY + timedelta(days=7)

    def test_it_raises_when_the_worker_is_gone(self, service, mock_worker_repo):
        mock_worker_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.get_public_availability(uuid4())
