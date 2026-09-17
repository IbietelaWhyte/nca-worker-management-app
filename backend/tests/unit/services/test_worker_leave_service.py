from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.worker_leave.models import WorkerLeaveCreate, WorkerLeaveResponse
from app.service.worker_leave.service import WorkerLeaveService
from tests.unit.services.conftest import make_assignment, make_schedule, make_worker

TODAY = date.today()


def make_leave(**kwargs) -> WorkerLeaveResponse:
    return WorkerLeaveResponse(
        id=kwargs.get("id", uuid4()),
        worker_id=kwargs.get("worker_id", uuid4()),
        start_date=kwargs.get("start_date", TODAY),
        end_date=kwargs.get("end_date", TODAY + timedelta(days=7)),
        reason=kwargs.get("reason", None),
        created_by=kwargs.get("created_by", None),
        created_at=kwargs.get("created_at", datetime.now()),
    )


@pytest.fixture
def service(mock_leave_repo, mock_worker_repo, mock_schedule_repo):
    mock_worker_repo.get_by_id.return_value = make_worker()
    mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = []
    return WorkerLeaveService(
        leave_repo=mock_leave_repo,
        worker_repo=mock_worker_repo,
        schedule_repo=mock_schedule_repo,
    )


class TestCreateLeave:
    def test_stores_the_range_and_the_head_who_set_it(self, service, mock_leave_repo):
        worker_id, actor_id = uuid4(), uuid4()
        mock_leave_repo.create.return_value = make_leave(worker_id=worker_id, created_by=actor_id)

        service.create_leave(
            worker_id,
            WorkerLeaveCreate(start_date=TODAY, end_date=TODAY + timedelta(days=7), reason="Travelling"),
            created_by=actor_id,
        )
        payload = mock_leave_repo.create.call_args.args[0]
        assert payload["worker_id"] == str(worker_id)
        assert payload["created_by"] == str(actor_id)
        assert payload["reason"] == "Travelling"

    def test_an_admin_with_no_worker_profile_can_still_set_it(self, service, mock_leave_repo):
        # created_by is ON DELETE SET NULL and admins need not be workers at all, so None is a
        # designed state rather than a missing value.
        mock_leave_repo.create.return_value = make_leave()
        service.create_leave(uuid4(), WorkerLeaveCreate(start_date=TODAY, end_date=TODAY), created_by=None)
        assert mock_leave_repo.create.call_args.args[0]["created_by"] is None

    def test_a_single_day_is_allowed(self, service, mock_leave_repo):
        mock_leave_repo.create.return_value = make_leave(start_date=TODAY, end_date=TODAY)
        service.create_leave(uuid4(), WorkerLeaveCreate(start_date=TODAY, end_date=TODAY), created_by=None)
        mock_leave_repo.create.assert_called_once()

    def test_a_backwards_range_is_rejected_by_the_schema(self):
        # Caught before the service, and mirrored by chk_worker_leave_dates in Postgres.
        with pytest.raises(ValueError, match="end date cannot be before"):
            WorkerLeaveCreate(start_date=TODAY + timedelta(days=7), end_date=TODAY)

    def test_overlapping_leave_is_refused_and_names_the_clash(self, service, mock_leave_repo):
        existing = make_leave(start_date=date(2026, 10, 1), end_date=date(2026, 10, 20))
        mock_leave_repo.get_overlapping.return_value = [existing]

        with pytest.raises(ConflictError, match="01 Oct 2026"):
            service.create_leave(
                uuid4(),
                WorkerLeaveCreate(start_date=date(2026, 10, 10), end_date=date(2026, 10, 25)),
                created_by=None,
            )
        mock_leave_repo.create.assert_not_called()

    def test_raises_when_the_worker_does_not_exist(self, service, mock_worker_repo, mock_leave_repo):
        mock_worker_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.create_leave(uuid4(), WorkerLeaveCreate(start_date=TODAY, end_date=TODAY), created_by=None)
        mock_leave_repo.create.assert_not_called()


class TestClashes:
    def test_it_reports_duties_inside_the_window_without_touching_them(
        self, service, mock_schedule_repo, mock_leave_repo
    ):
        # The head is told so they can reassign. Silently dropping somebody off a rota they were
        # counted on for would be a worse surprise than the clash.
        inside = make_schedule(scheduled_date=TODAY + timedelta(days=3))
        mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = [make_assignment(schedules=inside)]

        report = service.get_clashes(uuid4(), TODAY, TODAY + timedelta(days=7))
        assert [c.scheduled_date for c in report.clashes] == [inside.scheduled_date]
        mock_schedule_repo.update_assignment_role.assert_not_called()
        mock_schedule_repo.delete_assignments_for_schedule.assert_not_called()
        mock_leave_repo.create.assert_not_called()

    def test_duties_after_the_window_are_not_clashes(self, service, mock_schedule_repo):
        # get_upcoming_assignments_for_worker has no upper bound, so the window's end is applied
        # here — without it every future duty would be reported.
        outside = make_schedule(scheduled_date=TODAY + timedelta(days=30))
        mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = [make_assignment(schedules=outside)]

        report = service.get_clashes(uuid4(), TODAY, TODAY + timedelta(days=7))
        assert report.clashes == []

    def test_the_window_start_is_the_lower_bound_asked_for(self, service, mock_schedule_repo):
        start = TODAY + timedelta(days=10)
        service.get_clashes(uuid4(), start, start + timedelta(days=5))
        assert mock_schedule_repo.get_upcoming_assignments_for_worker.call_args.args[1] == start

    def test_an_assignment_with_no_schedule_is_skipped(self, service, mock_schedule_repo):
        mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = [make_assignment(schedules=None)]
        assert service.get_clashes(uuid4(), TODAY, TODAY + timedelta(days=7)).clashes == []


class TestCurrentLeave:
    def test_it_lists_who_is_away_today(self, service, mock_leave_repo):
        worker_id = uuid4()
        mock_leave_repo.get_active_on.return_value = [make_leave(worker_id=worker_id)]

        current = service.get_current_leave(today=TODAY)
        assert [c.worker_id for c in current] == [worker_id]
        mock_leave_repo.get_active_on.assert_called_once_with(TODAY)


class TestLeaveCoverage:
    @pytest.mark.parametrize(
        ("day", "covered"),
        [
            (date(2026, 10, 9), False),
            (date(2026, 10, 10), True),  # both ends inclusive
            (date(2026, 10, 15), True),
            (date(2026, 10, 20), True),  # the last day away is still a day away
            (date(2026, 10, 21), False),
        ],
    )
    def test_both_ends_are_inclusive(self, day, covered):
        # "Away 10-20 Oct" is how a person says it, so the 20th has to count.
        leave = make_leave(start_date=date(2026, 10, 10), end_date=date(2026, 10, 20))
        assert leave.covers(day) is covered
