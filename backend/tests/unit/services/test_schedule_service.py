from datetime import date, time
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.schemas.models import AvailabilityType, DayOfWeek
from app.schemas.schedules.models import (
    DatePlanStatus,
    DateSelection,
    MonthlyScheduleCommitRequest,
    MonthlySchedulePreviewRequest,
    ScheduleCreate,
)
from app.service.schedules.service import ScheduleService
from tests.unit.services.conftest import (
    make_assignment,
    make_availability,
    make_department,
    make_department_role,
    make_schedule,
    make_subteam,
    make_subteam_member,
    make_worker,
)


@pytest.fixture
def service(
    mock_schedule_repo,
    mock_worker_repo,
    mock_department_repo,
    mock_subteam_repo,
    mock_availability_repo,
    mock_department_role_repo,
    mock_leave_repo,
):
    # Default: workers have no standing role unless a test overrides this.
    mock_department_role_repo.get_role_for_worker_in_department.return_value = None
    return ScheduleService(
        schedule_repo=mock_schedule_repo,
        worker_repo=mock_worker_repo,
        department_repo=mock_department_repo,
        subteam_repo=mock_subteam_repo,
        availability_repo=mock_availability_repo,
        department_role_repo=mock_department_role_repo,
        leave_repo=mock_leave_repo,
    )


def make_generate_request(**kwargs) -> ScheduleCreate:
    dept_id = kwargs.get("department_id", uuid4())
    return ScheduleCreate(
        department_id=dept_id,
        scope=kwargs.get("scope", "department_only"),
        subteam_id=kwargs.get("subteam_id", None),
        title=kwargs.get("title", "Sunday Service"),
        scheduled_date=kwargs.get("scheduled_date", date(2026, 3, 15)),  # Sunday
        start_time=kwargs.get("start_time", time(9, 0)),
        end_time=kwargs.get("end_time", time(11, 0)),
        reminder_days_before=kwargs.get("reminder_days_before", 1),
    )


class TestGetSchedule:
    def test_returns_schedule_when_found(self, service, mock_schedule_repo):
        schedule = make_schedule()
        mock_schedule_repo.get_with_assignments.return_value = schedule
        result = service.get_schedule(schedule.id)
        assert result == schedule

    def test_raises_when_not_found(self, service, mock_schedule_repo):
        mock_schedule_repo.get_with_assignments.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.get_schedule(uuid4())


class TestGenerateSchedule:
    def test_generates_with_available_workers(
        self,
        service,
        mock_schedule_repo,
        mock_worker_repo,
        mock_department_repo,
        mock_availability_repo,
    ):
        dept = make_department(band=2)
        workers = [make_worker(), make_worker(), make_worker()]
        schedule = make_schedule(department_id=dept.id)

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = workers
        mock_availability_repo.get_by_worker_and_type.return_value = None
        mock_availability_repo.get_by_worker_and_day.return_value = None
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_schedule_repo.create.return_value = schedule
        mock_schedule_repo.bulk_create_assignments.return_value = []
        mock_schedule_repo.get_with_assignments.return_value = schedule
        mock_schedule_repo.get_assignments_for_worker.return_value = []

        data = make_generate_request(department_id=dept.id)
        result = service.generate_schedule(data, created_by=uuid4())

        assert result == schedule
        mock_schedule_repo.bulk_create_assignments.assert_called_once()
        # Verify only 2 workers were selected
        assignments_arg = mock_schedule_repo.bulk_create_assignments.call_args[0][0]
        assert len(assignments_arg) == 2

    def test_raises_when_no_workers_in_department(
        self,
        service,
        mock_schedule_repo,
        mock_department_repo,
        mock_worker_repo,
    ):
        dept = make_department()
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = []

        with pytest.raises(BadRequestError, match="No workers found"):
            service.generate_schedule(make_generate_request(), created_by=uuid4())

    def test_raises_when_no_available_workers(
        self,
        service,
        mock_schedule_repo,
        mock_department_repo,
        mock_worker_repo,
        mock_availability_repo,
    ):
        dept = make_department()
        workers = [make_worker(), make_worker()]
        the_date = date(2026, 3, 15)

        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = workers
        # One batched fetch for the whole roster now, not a pair of queries per worker.
        mock_availability_repo.get_for_workers.return_value = [
            make_availability(
                worker_id=w.id,
                availability_type=AvailabilityType.SPECIFIC_DATE,
                day_of_week=None,
                specific_date=the_date,
                is_available=False,
            )
            for w in workers
        ]

        # The planner's own message, which separates "unavailable" from "already scheduled" —
        # the hand-rolled one it replaced could only say that nobody was free.
        with pytest.raises(BadRequestError, match="No workers available for this date"):
            service.generate_schedule(make_generate_request(scheduled_date=the_date), created_by=uuid4())

    def test_specific_date_overrides_recurring(
        self,
        service,
        mock_schedule_repo,
        mock_department_repo,
        mock_worker_repo,
        mock_availability_repo,
    ):
        """A specific date beats the recurring weekly setting, in either direction."""
        dept = make_department(band=1)
        worker = make_worker()
        the_date = date(2026, 3, 15)  # a Sunday

        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [worker]
        mock_availability_repo.get_for_workers.return_value = [
            # Free every Sunday...
            make_availability(
                worker_id=worker.id,
                availability_type=AvailabilityType.RECURRING,
                day_of_week=DayOfWeek.SUNDAY,
                is_available=True,
            ),
            # ...except this one.
            make_availability(
                worker_id=worker.id,
                availability_type=AvailabilityType.SPECIFIC_DATE,
                day_of_week=None,
                specific_date=the_date,
                is_available=False,
            ),
        ]

        with pytest.raises(BadRequestError, match="No workers available for this date"):
            service.generate_schedule(make_generate_request(scheduled_date=the_date), created_by=uuid4())

    def test_raises_when_department_not_found(self, service, mock_schedule_repo, mock_department_repo):
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_department_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.generate_schedule(make_generate_request(), created_by=uuid4())


class TestRoundRobin:
    def test_prioritises_worker_never_assigned(
        self,
        service,
        mock_department_repo,
        mock_worker_repo,
        mock_availability_repo,
        mock_schedule_repo,
    ):
        """Worker with no prior assignments should be selected first."""
        dept = make_department(band=1)
        never_assigned = make_worker()
        recently_assigned = make_worker()
        schedule_id = uuid4()
        prior_assignment = make_assignment(
            worker_id=recently_assigned.id,
            schedule_id=schedule_id,
            schedules=make_schedule(
                schedule_id=schedule_id, department_id=dept.id, scheduled_date=date(2026, 3, 1)
            ),  # Recent past date
        )

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [recently_assigned, never_assigned]
        mock_schedule_repo.get_existing_schedule.return_value = None
        # One fetch for the whole roster. The old path issued this query per worker from
        # inside the sort key, which is N round-trips on a request thread.
        mock_schedule_repo.get_assignment_history_for_workers.return_value = [prior_assignment]
        schedule = make_schedule()
        mock_schedule_repo.create.return_value = schedule
        mock_schedule_repo.bulk_create_assignments.return_value = []
        mock_schedule_repo.get_with_assignments.return_value = schedule

        service.generate_schedule(make_generate_request(department_id=dept.id), created_by=uuid4())

        assignments_arg = mock_schedule_repo.bulk_create_assignments.call_args[0][0]
        assert assignments_arg[0]["worker_id"] == str(never_assigned.id)


class TestRoleAutoFill:
    def test_assignment_inherits_worker_standing_role(
        self,
        service,
        mock_schedule_repo,
        mock_worker_repo,
        mock_department_repo,
        mock_availability_repo,
        mock_department_role_repo,
    ):
        dept = make_department(band=1)
        worker = make_worker()
        role = make_department_role(department_id=dept.id)
        schedule = make_schedule(department_id=dept.id)

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [worker]
        mock_availability_repo.get_by_worker_and_type.return_value = None
        mock_availability_repo.get_by_worker_and_day.return_value = None
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_schedule_repo.create.return_value = schedule
        mock_schedule_repo.bulk_create_assignments.return_value = []
        mock_schedule_repo.get_with_assignments.return_value = schedule
        mock_schedule_repo.get_assignments_for_worker.return_value = []
        mock_department_role_repo.get_role_for_worker_in_department.return_value = role

        service.generate_schedule(make_generate_request(department_id=dept.id), created_by=uuid4())

        assignments_arg = mock_schedule_repo.bulk_create_assignments.call_args[0][0]
        assert assignments_arg[0]["department_role_id"] == str(role.id)

    def test_assignment_role_is_none_when_worker_has_no_role(
        self,
        service,
        mock_schedule_repo,
        mock_worker_repo,
        mock_department_repo,
        mock_availability_repo,
        mock_department_role_repo,
    ):
        dept = make_department(band=1)
        worker = make_worker()
        schedule = make_schedule(department_id=dept.id)

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [worker]
        mock_availability_repo.get_by_worker_and_type.return_value = None
        mock_availability_repo.get_by_worker_and_day.return_value = None
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_schedule_repo.create.return_value = schedule
        mock_schedule_repo.bulk_create_assignments.return_value = []
        mock_schedule_repo.get_with_assignments.return_value = schedule
        mock_schedule_repo.get_assignments_for_worker.return_value = []
        mock_department_role_repo.get_role_for_worker_in_department.return_value = None

        service.generate_schedule(make_generate_request(department_id=dept.id), created_by=uuid4())

        assignments_arg = mock_schedule_repo.bulk_create_assignments.call_args[0][0]
        assert assignments_arg[0]["department_role_id"] is None


class TestUpdateAssignmentRole:
    def test_sets_role_when_in_same_department(self, service, mock_schedule_repo, mock_department_role_repo):
        dept_id = uuid4()
        assignment = make_assignment()
        schedule = make_schedule(id=assignment.schedule_id, department_id=dept_id)
        role = make_department_role(department_id=dept_id)
        updated = make_assignment(id=assignment.id, department_role_id=role.id)

        mock_schedule_repo.get_assignment_by_id.return_value = assignment
        mock_schedule_repo.get_by_id.return_value = schedule
        mock_department_role_repo.get_by_id.return_value = role
        mock_schedule_repo.update_assignment_role.return_value = updated

        result = service.update_assignment_role(assignment.id, role.id)
        assert result.department_role_id == role.id
        mock_schedule_repo.update_assignment_role.assert_called_once_with(assignment.id, role.id)

    def test_clears_role_without_validation(self, service, mock_schedule_repo, mock_department_role_repo):
        assignment = make_assignment()
        cleared = make_assignment(id=assignment.id, department_role_id=None)
        mock_schedule_repo.get_assignment_by_id.return_value = assignment
        mock_schedule_repo.update_assignment_role.return_value = cleared

        result = service.update_assignment_role(assignment.id, None)
        assert result.department_role_id is None
        # No department/role lookups needed when clearing.
        mock_department_role_repo.get_by_id.assert_not_called()

    def test_raises_when_role_in_different_department(self, service, mock_schedule_repo, mock_department_role_repo):
        assignment = make_assignment()
        schedule = make_schedule(id=assignment.schedule_id, department_id=uuid4())
        role = make_department_role(department_id=uuid4())  # different department

        mock_schedule_repo.get_assignment_by_id.return_value = assignment
        mock_schedule_repo.get_by_id.return_value = schedule
        mock_department_role_repo.get_by_id.return_value = role

        with pytest.raises(BadRequestError, match="does not belong"):
            service.update_assignment_role(assignment.id, role.id)
        mock_schedule_repo.update_assignment_role.assert_not_called()

    def test_raises_when_assignment_not_found(self, service, mock_schedule_repo):
        mock_schedule_repo.get_assignment_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.update_assignment_role(uuid4(), uuid4())


# ----------------------------------------------------------------
# Monthly generation
# ----------------------------------------------------------------


def make_month_preview_request(**kwargs) -> MonthlySchedulePreviewRequest:
    return MonthlySchedulePreviewRequest(
        department_id=kwargs.get("department_id", uuid4()),
        scope=kwargs.get("scope", "department_only"),
        subteam_id=kwargs.get("subteam_id", None),
        title=kwargs.get("title", "Sunday Service"),
        year=kwargs.get("year", 2026),
        month=kwargs.get("month", 3),
        days_of_week=kwargs.get("days_of_week", [DayOfWeek.SUNDAY]),
        start_time=kwargs.get("start_time", time(9, 0)),
        end_time=kwargs.get("end_time", time(11, 0)),
        reminder_days_before=kwargs.get("reminder_days_before", 1),
    )


def make_month_commit_request(**kwargs) -> MonthlyScheduleCommitRequest:
    return MonthlyScheduleCommitRequest(
        department_id=kwargs.get("department_id", uuid4()),
        scope=kwargs.get("scope", "department_only"),
        subteam_id=kwargs.get("subteam_id", None),
        title=kwargs.get("title", "Sunday Service"),
        dates=kwargs.get("dates", []),
        start_time=kwargs.get("start_time", time(9, 0)),
        end_time=kwargs.get("end_time", time(11, 0)),
        reminder_days_before=kwargs.get("reminder_days_before", 1),
    )


def plan_assignments(date_plan):
    """Every assignment on a date, flattened across its groups."""
    return [a for g in date_plan.groups for a in g.assignments]


def plan_alternates(date_plan):
    return [w for g in date_plan.groups for w in g.alternates]


@pytest.fixture
def monthly_repos(mock_schedule_repo, mock_availability_repo):
    """Default the batched preloads to 'nothing on record'."""
    mock_availability_repo.get_for_workers.return_value = []
    mock_schedule_repo.get_workers_scheduled_in_range.return_value = {}
    mock_schedule_repo.get_assignment_history_for_workers.return_value = []
    mock_schedule_repo.get_by_department.return_value = []
    return mock_schedule_repo, mock_availability_repo


class TestPreviewMonthlySchedule:
    def test_plans_every_matching_weekday_in_the_month(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        dept = make_department(band=2)
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [make_worker() for _ in range(10)]

        result = service.preview_monthly_schedule(make_month_preview_request(department_id=dept.id))

        # March 2026 has five Sundays: 1, 8, 15, 22, 29.
        assert [p.scheduled_date.day for p in result.dates] == [1, 8, 15, 22, 29]
        assert (result.min_workers, result.max_workers) == (2, 2)
        assert all(p.status == DatePlanStatus.PLANNED for p in result.dates)
        assert all(len(plan_assignments(p)) == 2 for p in result.dates)

    def test_writes_nothing(self, service, monthly_repos, mock_worker_repo, mock_department_repo):
        schedule_repo, _ = monthly_repos
        dept = make_department(band=1)
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [make_worker() for _ in range(3)]

        service.preview_monthly_schedule(make_month_preview_request(department_id=dept.id))

        schedule_repo.create.assert_not_called()
        schedule_repo.bulk_create_schedules.assert_not_called()
        schedule_repo.bulk_create_assignments.assert_not_called()

    def test_preloads_in_batch_rather_than_per_date(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        schedule_repo, availability_repo = monthly_repos
        dept = make_department(band=1)
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [make_worker() for _ in range(6)]

        service.preview_monthly_schedule(make_month_preview_request(department_id=dept.id))

        # Five Sundays, six workers — the per-date/per-worker helpers must not be touched.
        availability_repo.get_for_workers.assert_called_once()
        schedule_repo.get_workers_scheduled_in_range.assert_called_once()
        schedule_repo.get_assignment_history_for_workers.assert_called_once()
        availability_repo.get_by_worker_and_day.assert_not_called()
        availability_repo.get_by_worker_and_type.assert_not_called()
        schedule_repo.get_assignments_for_worker.assert_not_called()
        schedule_repo.get_workers_scheduled_on_date.assert_not_called()

    def test_balances_workers_across_the_month(self, service, monthly_repos, mock_worker_repo, mock_department_repo):
        dept = make_department(band=1)
        mock_department_repo.get_by_id.return_value = dept
        # Five Sundays, five workers, one slot each -> everyone serves exactly once.
        mock_worker_repo.get_department_only_workers.return_value = [make_worker() for _ in range(5)]

        result = service.preview_monthly_schedule(make_month_preview_request(department_id=dept.id))

        served = [a.worker.id for p in result.dates for a in plan_assignments(p)]
        assert len(served) == 5
        assert len(set(served)) == 5

    def test_respects_specific_date_unavailability(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        _, availability_repo = monthly_repos
        dept = make_department(band=1)
        away, other = make_worker(), make_worker()
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [away, other]
        availability_repo.get_for_workers.return_value = [
            make_availability(
                worker_id=away.id,
                availability_type=AvailabilityType.SPECIFIC_DATE,
                day_of_week=None,
                specific_date=date(2026, 3, 1),
                is_available=False,
            )
        ]

        result = service.preview_monthly_schedule(make_month_preview_request(department_id=dept.id))

        first_sunday = result.dates[0]
        assert [a.worker.id for a in plan_assignments(first_sunday)] == [other.id]
        assert away.id not in [w.id for w in plan_alternates(first_sunday)]

    def test_specific_date_override_beats_recurring(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        _, availability_repo = monthly_repos
        dept = make_department(band=1)
        worker = make_worker()
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [worker]
        availability_repo.get_for_workers.return_value = [
            # Never available on Sundays...
            make_availability(
                worker_id=worker.id,
                availability_type=AvailabilityType.RECURRING,
                day_of_week=DayOfWeek.SUNDAY,
                is_available=False,
            ),
            # ...except this one.
            make_availability(
                worker_id=worker.id,
                availability_type=AvailabilityType.SPECIFIC_DATE,
                day_of_week=None,
                specific_date=date(2026, 3, 8),
                is_available=True,
            ),
        ]

        result = service.preview_monthly_schedule(make_month_preview_request(department_id=dept.id))

        by_date = {p.scheduled_date: p for p in result.dates}
        assert by_date[date(2026, 3, 1)].status == DatePlanStatus.SKIPPED_NO_WORKERS
        assert [a.worker.id for a in plan_assignments(by_date[date(2026, 3, 8)])] == [worker.id]

    def test_marks_dates_that_already_have_a_schedule(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        schedule_repo, _ = monthly_repos
        dept = make_department(band=1)
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [make_worker() for _ in range(3)]
        schedule_repo.get_by_department.return_value = [
            make_schedule(department_id=dept.id, scheduled_date=date(2026, 3, 8), subteam_id=None)
        ]

        result = service.preview_monthly_schedule(make_month_preview_request(department_id=dept.id))

        by_date = {p.scheduled_date: p.status for p in result.dates}
        assert by_date[date(2026, 3, 8)] == DatePlanStatus.SKIPPED_EXISTING
        assert by_date[date(2026, 3, 1)] == DatePlanStatus.PLANNED

    def test_flags_understaffed_dates(self, service, monthly_repos, mock_worker_repo, mock_department_repo):
        dept = make_department(band=4)
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [make_worker(), make_worker()]

        result = service.preview_monthly_schedule(make_month_preview_request(department_id=dept.id))

        assert all(p.status == DatePlanStatus.UNDERSTAFFED for p in result.dates)
        assert all(len(plan_assignments(p)) == 2 for p in result.dates)

    def test_supports_multiple_weekdays(self, service, monthly_repos, mock_worker_repo, mock_department_repo):
        dept = make_department(band=1)
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [make_worker() for _ in range(10)]

        result = service.preview_monthly_schedule(
            make_month_preview_request(department_id=dept.id, days_of_week=[DayOfWeek.SUNDAY, DayOfWeek.WEDNESDAY])
        )

        # Sundays 1/8/15/22/29 + Wednesdays 4/11/18/25, ascending.
        assert [p.scheduled_date.day for p in result.dates] == [1, 4, 8, 11, 15, 18, 22, 25, 29]

    def test_raises_when_department_has_no_workers(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        mock_department_repo.get_by_id.return_value = make_department()
        mock_worker_repo.get_department_only_workers.return_value = []

        with pytest.raises(BadRequestError, match="No workers found"):
            service.preview_monthly_schedule(make_month_preview_request())

    def test_raises_when_department_not_found(self, service, monthly_repos, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError, match="not found"):
            service.preview_monthly_schedule(make_month_preview_request())


class TestCommitMonthlySchedule:
    def test_creates_schedules_and_assignments_in_bulk(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        schedule_repo, _ = monthly_repos
        dept = make_department(band=1)
        w1, w2 = make_worker(), make_worker()
        creator = make_worker()

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [w1, w2]
        mock_worker_repo.get_by_email.return_value = creator
        created = [
            make_schedule(department_id=dept.id, scheduled_date=date(2026, 3, 1)),
            make_schedule(department_id=dept.id, scheduled_date=date(2026, 3, 8)),
        ]
        schedule_repo.bulk_create_schedules.return_value = created
        schedule_repo.get_with_assignments.side_effect = created

        data = make_month_commit_request(
            department_id=dept.id,
            dates=[
                DateSelection(scheduled_date=date(2026, 3, 1), worker_ids=[w1.id]),
                DateSelection(scheduled_date=date(2026, 3, 8), worker_ids=[w2.id]),
            ],
        )
        result = service.commit_monthly_schedule(data, created_by="hod@example.com")

        assert len(result.created) == 2
        assert result.skipped == []
        # One insert for all schedules, one for all assignments.
        schedule_repo.bulk_create_schedules.assert_called_once()
        schedule_repo.bulk_create_assignments.assert_called_once()
        assert len(schedule_repo.bulk_create_assignments.call_args[0][0]) == 2

    def test_honours_the_exact_workers_supplied(self, service, monthly_repos, mock_worker_repo, mock_department_repo):
        schedule_repo, _ = monthly_repos
        dept = make_department(band=1)
        workers = [make_worker() for _ in range(4)]
        swapped_in = workers[3]

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = workers
        mock_worker_repo.get_by_email.return_value = make_worker()
        schedule = make_schedule(department_id=dept.id, scheduled_date=date(2026, 3, 1))
        schedule_repo.bulk_create_schedules.return_value = [schedule]
        schedule_repo.get_with_assignments.return_value = schedule

        data = make_month_commit_request(
            department_id=dept.id,
            dates=[DateSelection(scheduled_date=date(2026, 3, 1), worker_ids=[swapped_in.id])],
        )
        service.commit_monthly_schedule(data, created_by="hod@example.com")

        assignments = schedule_repo.bulk_create_assignments.call_args[0][0]
        assert [a["worker_id"] for a in assignments] == [str(swapped_in.id)]

    def test_skips_dates_that_gained_a_schedule_since_preview(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        schedule_repo, _ = monthly_repos
        dept = make_department(band=1)
        w1, w2 = make_worker(), make_worker()

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [w1, w2]
        mock_worker_repo.get_by_email.return_value = make_worker()
        schedule_repo.get_by_department.return_value = [
            make_schedule(department_id=dept.id, scheduled_date=date(2026, 3, 1), subteam_id=None)
        ]
        survivor = make_schedule(department_id=dept.id, scheduled_date=date(2026, 3, 8))
        schedule_repo.bulk_create_schedules.return_value = [survivor]
        schedule_repo.get_with_assignments.return_value = survivor

        data = make_month_commit_request(
            department_id=dept.id,
            dates=[
                DateSelection(scheduled_date=date(2026, 3, 1), worker_ids=[w1.id]),
                DateSelection(scheduled_date=date(2026, 3, 8), worker_ids=[w2.id]),
            ],
        )
        result = service.commit_monthly_schedule(data, created_by="hod@example.com")

        assert len(result.created) == 1
        assert [s.scheduled_date for s in result.skipped] == [date(2026, 3, 1)]
        assert len(schedule_repo.bulk_create_schedules.call_args[0][0]) == 1

    def test_raises_when_every_date_already_exists(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        schedule_repo, _ = monthly_repos
        dept = make_department(band=1)
        worker = make_worker()

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [worker]
        mock_worker_repo.get_by_email.return_value = make_worker()
        schedule_repo.get_by_department.return_value = [
            make_schedule(department_id=dept.id, scheduled_date=date(2026, 3, 1), subteam_id=None)
        ]

        data = make_month_commit_request(
            department_id=dept.id,
            dates=[DateSelection(scheduled_date=date(2026, 3, 1), worker_ids=[worker.id])],
        )
        with pytest.raises(ConflictError, match="already has a schedule"):
            service.commit_monthly_schedule(data, created_by="hod@example.com")
        schedule_repo.bulk_create_schedules.assert_not_called()

    def test_rejects_a_worker_outside_the_scope(self, service, monthly_repos, mock_worker_repo, mock_department_repo):
        schedule_repo, _ = monthly_repos
        dept = make_department(band=1)
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [make_worker()]
        mock_worker_repo.get_by_email.return_value = make_worker()

        data = make_month_commit_request(
            department_id=dept.id,
            dates=[DateSelection(scheduled_date=date(2026, 3, 1), worker_ids=[uuid4()])],
        )
        with pytest.raises(BadRequestError, match="not eligible"):
            service.commit_monthly_schedule(data, created_by="hod@example.com")
        schedule_repo.bulk_create_schedules.assert_not_called()

    def test_rolls_back_schedules_when_assignments_fail(
        self, service, monthly_repos, mock_worker_repo, mock_department_repo
    ):
        schedule_repo, _ = monthly_repos
        dept = make_department(band=1)
        worker = make_worker()

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [worker]
        mock_worker_repo.get_by_email.return_value = make_worker()
        created = [make_schedule(department_id=dept.id, scheduled_date=date(2026, 3, 1))]
        schedule_repo.bulk_create_schedules.return_value = created
        schedule_repo.bulk_create_assignments.side_effect = RuntimeError("insert failed")

        data = make_month_commit_request(
            department_id=dept.id,
            dates=[DateSelection(scheduled_date=date(2026, 3, 1), worker_ids=[worker.id])],
        )
        with pytest.raises(RuntimeError):
            service.commit_monthly_schedule(data, created_by="hod@example.com")

        schedule_repo.delete_schedules.assert_called_once_with([created[0].id])

    def test_raises_when_creator_not_found(self, service, monthly_repos, mock_worker_repo, mock_department_repo):
        dept = make_department(band=1)
        worker = make_worker()
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [worker]
        mock_worker_repo.get_by_email.return_value = None

        data = make_month_commit_request(
            department_id=dept.id,
            dates=[DateSelection(scheduled_date=date(2026, 3, 1), worker_ids=[worker.id])],
        )
        with pytest.raises(NotFoundError, match="not found"):
            service.commit_monthly_schedule(data, created_by="ghost@example.com")


class TestDepartmentAllSubteamQuotas:
    """A department-wide schedule staffs each subteam to its own workers_per_slot.

    Regression cover for the flat-quota bug: `department.workers_per_slot` was used as a
    single number for the whole department, so subteams past the first few were left with
    nobody assigned.
    """

    @pytest.fixture
    def children_ministry(self, mock_department_repo, mock_subteam_repo, mock_worker_repo, monthly_repos):
        """Mirrors the real Children's Ministry: 3 subteams with different quotas."""
        dept = make_department(name="Children's Ministry", band=2)
        seekers = make_subteam(department_id=dept.id, name="Seekers", band=4)
        discovery = make_subteam(department_id=dept.id, name="Discovery", band=3)
        checkin = make_subteam(department_id=dept.id, name="Check In/Out", band=1)

        rosters = {
            seekers.id: [make_worker() for _ in range(5)],
            discovery.id: [make_worker() for _ in range(4)],
            checkin.id: [make_worker() for _ in range(2)],
            None: [make_worker(), make_worker()],  # in no subteam
        }

        mock_department_repo.get_by_id.return_value = dept
        mock_subteam_repo.get_by_department.return_value = [seekers, discovery, checkin]
        mock_worker_repo.get_workers_by_department_grouped_by_subteam.return_value = rosters
        return dept, {"Seekers": seekers, "Discovery": discovery, "Check In/Out": checkin}, rosters

    def test_each_subteam_gets_its_own_quota(self, service, children_ministry):
        dept, subteams, _ = children_ministry

        result = service.preview_monthly_schedule(
            make_month_preview_request(department_id=dept.id, scope="department_all")
        )

        first = result.dates[0]
        by_name = {(g.subteam.name if g.subteam else "Department"): g for g in first.groups}
        assert (by_name["Seekers"].min_workers, by_name["Seekers"].max_workers) == (4, 4)
        assert (by_name["Discovery"].min_workers, by_name["Discovery"].max_workers) == (3, 3)
        assert (by_name["Check In/Out"].min_workers, by_name["Check In/Out"].max_workers) == (1, 1)
        # No subteam quota set on the department-only group -> department default.
        assert (by_name["Department"].min_workers, by_name["Department"].max_workers) == (2, 2)

    def test_no_subteam_is_left_empty(self, service, children_ministry):
        dept, _, _ = children_ministry

        result = service.preview_monthly_schedule(
            make_month_preview_request(department_id=dept.id, scope="department_all")
        )

        for date_plan in result.dates:
            for group in date_plan.groups:
                label = group.subteam.name if group.subteam else "Department"
                assert len(group.assignments) == group.max_workers, f"{label} on {date_plan.scheduled_date}"

    def test_total_workers_needed_sums_every_group(self, service, children_ministry):
        dept, _, _ = children_ministry

        result = service.preview_monthly_schedule(
            make_month_preview_request(department_id=dept.id, scope="department_all")
        )

        # 4 Seekers + 3 Discovery + 1 Check In/Out + 2 department-only
        assert (result.min_workers, result.max_workers) == (10, 10)
        assert all(len(plan_assignments(p)) == 10 for p in result.dates)

    def test_workers_are_drawn_only_from_their_own_subteam(self, service, children_ministry):
        dept, subteams, rosters = children_ministry

        result = service.preview_monthly_schedule(
            make_month_preview_request(department_id=dept.id, scope="department_all")
        )

        for date_plan in result.dates:
            for group in date_plan.groups:
                roster = rosters[group.subteam.id if group.subteam else None]
                allowed = {w.id for w in roster}
                assert {a.worker.id for a in group.assignments} <= allowed
                assert {w.id for w in group.alternates} <= allowed

    def test_assignments_carry_their_subteam(self, service, children_ministry):
        dept, subteams, _ = children_ministry

        result = service.preview_monthly_schedule(
            make_month_preview_request(department_id=dept.id, scope="department_all")
        )

        for group in result.dates[0].groups:
            expected = group.subteam.id if group.subteam else None
            assert all(a.subteam_id == expected for a in group.assignments)

    def test_subteams_with_no_members_are_omitted(
        self, service, children_ministry, mock_subteam_repo, mock_worker_repo
    ):
        dept, subteams, rosters = children_ministry
        empty = make_subteam(department_id=dept.id, name="Pacesetters", band=3)
        mock_subteam_repo.get_by_department.return_value = [*subteams.values(), empty]

        result = service.preview_monthly_schedule(
            make_month_preview_request(department_id=dept.id, scope="department_all")
        )

        names = {g.subteam.name for g in result.dates[0].groups if g.subteam}
        assert "Pacesetters" not in names

    def test_commit_stamps_each_worker_with_their_subteam(
        self, service, children_ministry, mock_worker_repo, monthly_repos
    ):
        schedule_repo, _ = monthly_repos
        dept, subteams, rosters = children_ministry
        mock_worker_repo.get_by_email.return_value = make_worker()
        schedule = make_schedule(department_id=dept.id, scheduled_date=date(2026, 3, 1))
        schedule_repo.bulk_create_schedules.return_value = [schedule]
        schedule_repo.get_with_assignments.return_value = schedule

        seeker = rosters[subteams["Seekers"].id][0]
        loose = rosters[None][0]
        service.commit_monthly_schedule(
            make_month_commit_request(
                department_id=dept.id,
                scope="department_all",
                dates=[DateSelection(scheduled_date=date(2026, 3, 1), worker_ids=[seeker.id, loose.id])],
            ),
            created_by="hod@example.com",
        )

        assignments = {a["worker_id"]: a["subteam_id"] for a in schedule_repo.bulk_create_assignments.call_args[0][0]}
        assert assignments[str(seeker.id)] == str(subteams["Seekers"].id)
        assert assignments[str(loose.id)] is None


class TestGenerateScheduleDepartmentAll:
    """The single-date path uses the same per-subteam quotas as the monthly path."""

    def test_fills_each_subteam_to_its_own_quota(
        self,
        service,
        mock_schedule_repo,
        mock_department_repo,
        mock_subteam_repo,
        mock_worker_repo,
        mock_availability_repo,
    ):
        dept = make_department(band=2)
        seekers = make_subteam(department_id=dept.id, name="Seekers", band=4)
        checkin = make_subteam(department_id=dept.id, name="Check In/Out", band=1)
        seeker_workers = [make_worker() for _ in range(5)]
        checkin_workers = [make_worker(), make_worker()]

        mock_department_repo.get_by_id.return_value = dept
        mock_subteam_repo.get_by_department.return_value = [seekers, checkin]
        mock_worker_repo.get_workers_by_department_grouped_by_subteam.return_value = {
            seekers.id: seeker_workers,
            checkin.id: checkin_workers,
        }
        mock_worker_repo.get_by_email.return_value = make_worker()
        mock_availability_repo.get_by_worker_and_type.return_value = None
        mock_availability_repo.get_by_worker_and_day.return_value = None
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_schedule_repo.get_workers_scheduled_on_date.return_value = []
        mock_schedule_repo.get_assignments_for_worker.return_value = []
        schedule = make_schedule(department_id=dept.id)
        mock_schedule_repo.create.return_value = schedule
        mock_schedule_repo.get_with_assignments.return_value = schedule

        service.generate_schedule(
            make_generate_request(department_id=dept.id, scope="department_all"), created_by="hod@example.com"
        )

        assignments = mock_schedule_repo.bulk_create_assignments.call_args[0][0]
        by_subteam = {}
        for a in assignments:
            by_subteam[a["subteam_id"]] = by_subteam.get(a["subteam_id"], 0) + 1

        assert by_subteam[str(seekers.id)] == 4
        assert by_subteam[str(checkin.id)] == 1
        assert len(assignments) == 5


class TestLeaveExcludesWorkers:
    """A worker recorded as away must not be rostered, on either generation path."""

    def _leave(self, worker_id, start, end):
        from datetime import datetime

        from app.schemas.worker_leave.models import WorkerLeaveResponse

        return WorkerLeaveResponse(
            id=uuid4(),
            worker_id=worker_id,
            start_date=start,
            end_date=end,
            reason=None,
            created_by=None,
            created_at=datetime.now(),
        )

    def test_a_worker_on_leave_is_not_picked_for_a_single_date(
        self,
        service,
        mock_schedule_repo,
        mock_worker_repo,
        mock_department_repo,
        mock_availability_repo,
        mock_leave_repo,
    ):
        dept = make_department(band=1)
        away, free = make_worker(), make_worker()
        schedule = make_schedule(department_id=dept.id)
        scheduled_date = date(2026, 10, 11)

        mock_department_repo.get_by_id.return_value = dept
        # `away` is listed first, so fairness would otherwise take them.
        mock_worker_repo.get_department_only_workers.return_value = [away, free]
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_schedule_repo.create.return_value = schedule
        mock_schedule_repo.bulk_create_assignments.return_value = []
        mock_schedule_repo.get_with_assignments.return_value = schedule
        mock_leave_repo.get_for_workers.return_value = [self._leave(away.id, date(2026, 10, 5), date(2026, 10, 20))]

        service.generate_schedule(
            make_generate_request(department_id=dept.id, scheduled_date=scheduled_date), created_by=uuid4()
        )

        assignments = mock_schedule_repo.bulk_create_assignments.call_args[0][0]
        picked = {a["worker_id"] for a in assignments}
        assert str(away.id) not in picked
        assert str(free.id) in picked

    def test_leave_is_checked_for_the_date_being_scheduled(
        self,
        service,
        mock_schedule_repo,
        mock_worker_repo,
        mock_department_repo,
        mock_leave_repo,
    ):
        # Not for today. A rota built in September for October has to ask about October — a
        # worker away this week is fine for a date three weeks out.
        dept = make_department(band=1)
        # A roster of one, so "was this worker blocked?" has an unambiguous answer: blocked
        # means generation raises rather than picks somebody else.
        back_now = make_worker()
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [back_now]
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_schedule_repo.create.return_value = make_schedule(department_id=dept.id)
        mock_schedule_repo.bulk_create_assignments.return_value = []
        mock_schedule_repo.get_with_assignments.return_value = make_schedule(department_id=dept.id)
        # Away in September, back well before the October date being scheduled.
        mock_leave_repo.get_for_workers.return_value = [self._leave(back_now.id, date(2026, 9, 1), date(2026, 9, 20))]

        service.generate_schedule(
            make_generate_request(department_id=dept.id, scheduled_date=date(2026, 10, 11)), created_by=uuid4()
        )

        assignments = mock_schedule_repo.bulk_create_assignments.call_args[0][0]
        assert {a["worker_id"] for a in assignments} == {str(back_now.id)}, "leave that has ended must not block"

    def test_leave_blocks_only_the_dates_it_covers_in_a_month(self, service, mock_leave_repo):
        # The monthly path folds leave into the unavailability map, one batched fetch for the
        # whole month rather than a query per date.
        away = uuid4()
        dates = [date(2026, 10, 4), date(2026, 10, 11), date(2026, 10, 18), date(2026, 10, 25)]
        mock_leave_repo.get_for_workers.return_value = [self._leave(away, date(2026, 10, 8), date(2026, 10, 20))]

        unavailable = service._build_unavailability_map([away], dates, dates[0], dates[-1])

        assert away not in unavailable.get(date(2026, 10, 4), set())
        assert away in unavailable[date(2026, 10, 11)]
        assert away in unavailable[date(2026, 10, 18)]
        assert away not in unavailable.get(date(2026, 10, 25), set())


class TestStaffingBandResolution:
    """How a group's (minimum, maximum) is resolved, and what is recorded on the schedule."""

    def _generate(self, service, mock_schedule_repo, mock_department_repo, mock_worker_repo, dept, workers):
        schedule = make_schedule(department_id=dept.id)
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = workers
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_schedule_repo.create.return_value = schedule
        mock_schedule_repo.bulk_create_assignments.return_value = []
        mock_schedule_repo.get_with_assignments.return_value = schedule
        service.generate_schedule(make_generate_request(department_id=dept.id), created_by=uuid4())
        return mock_schedule_repo.create.call_args[0][0]

    def test_the_band_is_frozen_onto_the_schedule(
        self, service, mock_schedule_repo, mock_department_repo, mock_worker_repo
    ):
        # Recorded at generation rather than re-resolved on read: the department's numbers may
        # change before the date comes round, and this rota was planned against these ones.
        dept = make_department(band=(2, 4))

        row = self._generate(
            service, mock_schedule_repo, mock_department_repo, mock_worker_repo, dept, [make_worker() for _ in range(6)]
        )

        assert (row["min_workers"], row["max_workers"]) == (2, 4)

    def test_a_wide_band_takes_more_people_than_the_minimum(
        self, service, mock_schedule_repo, mock_department_repo, mock_worker_repo
    ):
        dept = make_department(band=(2, 4))
        mock_department_repo.get_by_id.return_value = dept
        self._generate(
            service, mock_schedule_repo, mock_department_repo, mock_worker_repo, dept, [make_worker() for _ in range(6)]
        )

        assignments = mock_schedule_repo.bulk_create_assignments.call_args[0][0]
        assert len(assignments) == 4

    def test_a_subteam_overrides_the_department_band(
        self, service, mock_department_repo, mock_subteam_repo, mock_worker_repo, monthly_repos
    ):
        dept = make_department(band=(2, 3))
        subteam = make_subteam(department_id=dept.id, name="Seekers", band=(4, 6))
        mock_department_repo.get_by_id.return_value = dept
        mock_subteam_repo.get_by_id.return_value = subteam
        mock_subteam_repo.get_with_workers.return_value = [make_subteam_member(worker=make_worker()) for _ in range(8)]

        result = service.preview_monthly_schedule(
            make_month_preview_request(department_id=dept.id, scope="subteam", subteam_id=subteam.id)
        )

        assert (result.min_workers, result.max_workers) == (4, 6)

    def test_a_subteam_that_inherits_uses_the_departments_band(
        self, service, mock_department_repo, mock_subteam_repo, mock_worker_repo, monthly_repos
    ):
        dept = make_department(band=(2, 3))
        subteam = make_subteam(department_id=dept.id, name="Seekers")  # band=None — inherit
        mock_department_repo.get_by_id.return_value = dept
        mock_subteam_repo.get_by_id.return_value = subteam
        mock_subteam_repo.get_with_workers.return_value = [make_subteam_member(worker=make_worker()) for _ in range(8)]

        result = service.preview_monthly_schedule(
            make_month_preview_request(department_id=dept.id, scope="subteam", subteam_id=subteam.id)
        )

        assert (result.min_workers, result.max_workers) == (2, 3)
