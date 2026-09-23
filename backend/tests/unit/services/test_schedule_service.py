from datetime import date, time
from uuid import UUID, uuid4

import pytest
from postgrest.exceptions import APIError

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
    mock_sms_service,
    mock_special_service_service,
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
        sms_service=mock_sms_service,
        special_service_service=mock_special_service_service,
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
        reminder_days_before=kwargs.get("reminder_days_before", [1]),
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
        reminder_days_before=kwargs.get("reminder_days_before", [1]),
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
        reminder_days_before=kwargs.get("reminder_days_before", [1]),
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


# ----------------------------------------------------------------
# Editing a generated rota
# ----------------------------------------------------------------


class EditFixture:
    """Wires the repositories for one department-only rota that can be edited.

    Every edit path reads the same handful of things — the schedule, the department, the
    eligible roster, the worker — so setting them up once keeps each test to the one fact it
    is about.
    """

    def __init__(self, repos, *, band=(2, 4), on_rota=2, spare=1):
        schedule_repo, worker_repo, department_repo, role_repo = repos
        self.department = make_department(band=band)
        self.on_rota = [make_worker(first_name=f"On{i}", phone=f"+1416555010{i}") for i in range(on_rota)]
        self.spare = [make_worker(first_name=f"Spare{i}", phone=f"+1416555020{i}") for i in range(spare)]
        self.schedule = make_schedule(
            department_id=self.department.id,
            min_workers=band[0],
            max_workers=band[1],
            scheduled_date=date(2026, 8, 2),
        )
        self.schedule.schedule_assignments = [
            make_assignment(schedule_id=self.schedule.id, worker_id=w.id, workers=w) for w in self.on_rota
        ]

        schedule_repo.get_with_assignments.return_value = self.schedule
        schedule_repo.create_assignment.side_effect = lambda data: make_assignment(
            schedule_id=self.schedule.id, worker_id=UUID(data["worker_id"])
        )
        department_repo.get_by_id.return_value = self.department
        # The whole roster, on and off the rota — _eligible_worker resolves against this.
        worker_repo.get_department_only_workers.return_value = self.on_rota + self.spare
        worker_repo.get_by_id.side_effect = lambda wid: next(
            (w for w in self.on_rota + self.spare if w.id == wid), None
        )
        role_repo.get_role_for_worker_in_department.return_value = None

    def assignment_of(self, worker):
        """The assignment row holding a given worker, with the schedule embedded as the
        repository's edit-path read returns it."""
        row = next(a for a in self.schedule.schedule_assignments if a.worker_id == worker.id)
        return row.model_copy(update={"schedules": self.schedule})


@pytest.fixture
def edit(mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo):
    return EditFixture((mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo))


class TestGetAssignableWorkers:
    """Who the picker offers. Resolved server-side so eligibility keeps one definition."""

    def test_offers_the_roster_minus_whoever_is_already_on(self, service, edit):
        assignable = service.get_assignable_workers(edit.schedule.id)

        assert [a.worker.id for a in assignable] == [w.id for w in edit.spare]

    def test_a_department_only_rota_excludes_everybody_in_a_subteam(
        self, service, mock_schedule_repo, mock_worker_repo, mock_department_repo
    ):
        # The reason this is a server call at all. A DEPARTMENT_ONLY rota staffs from the
        # workers in no subteam, so listing the whole department would offer names that 400.
        department = make_department(band=(1, 4))
        spare = make_worker(first_name="Spare")
        schedule = make_schedule(department_id=department.id, subteam_id=None, min_workers=1, max_workers=4)
        schedule.schedule_assignments = [make_assignment(schedule_id=schedule.id, subteam_id=None)]
        mock_schedule_repo.get_with_assignments.return_value = schedule
        mock_department_repo.get_by_id.return_value = department
        mock_worker_repo.get_department_only_workers.return_value = [spare]

        assignable = service.get_assignable_workers(schedule.id)

        # get_department_only_workers, not the whole department.
        mock_worker_repo.get_department_only_workers.assert_called_once_with(department.id)
        assert [a.worker.id for a in assignable] == [spare.id]
        assert assignable[0].subteam is None

    def test_names_the_subteam_each_candidate_would_land_in(
        self, service, mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_subteam_repo
    ):
        # The subteam shown is the one that will actually be stamped, because both come from
        # the same _resolve_scope_groups call.
        department = make_department(band=(1, 4))
        seekers = make_subteam(department_id=department.id, name="Seekers")
        discovery = make_subteam(department_id=department.id, name="Discovery")
        ada, grace = make_worker(first_name="Ada"), make_worker(first_name="Grace")
        schedule = make_schedule(department_id=department.id, subteam_id=None, min_workers=1, max_workers=4)
        schedule.schedule_assignments = [make_assignment(schedule_id=schedule.id, subteam_id=seekers.id)]
        mock_schedule_repo.get_with_assignments.return_value = schedule
        mock_department_repo.get_by_id.return_value = department
        mock_subteam_repo.get_by_department.return_value = [seekers, discovery]
        mock_worker_repo.get_workers_by_department_grouped_by_subteam.return_value = {
            seekers.id: [ada],
            discovery.id: [grace],
        }

        assignable = service.get_assignable_workers(schedule.id)

        # Group order: subteams by name, so Discovery before Seekers.
        assert [(a.worker.first_name, a.subteam.name) for a in assignable] == [
            ("Grace", "Discovery"),
            ("Ada", "Seekers"),
        ]

    def test_raises_for_an_unknown_schedule(self, service, mock_schedule_repo):
        mock_schedule_repo.get_with_assignments.return_value = None
        with pytest.raises(NotFoundError, match="Schedule"):
            service.get_assignable_workers(uuid4())


class TestAddAssignment:
    def test_adds_a_worker_and_stamps_their_role(self, service, edit, mock_schedule_repo, mock_department_role_repo):
        role = make_department_role(department_id=edit.department.id)
        mock_department_role_repo.get_role_for_worker_in_department.return_value = role

        service.add_assignment(edit.schedule.id, edit.spare[0].id)

        written = mock_schedule_repo.create_assignment.call_args.args[0]
        assert written["worker_id"] == str(edit.spare[0].id)
        assert written["department_role_id"] == str(role.id)

    def test_texts_the_added_worker_immediately(self, service, edit, mock_sms_service, mock_schedule_repo):
        # The sweep would find the row on its own, but only within ten minutes, and the head is
        # standing in front of them.
        service.add_assignment(edit.schedule.id, edit.spare[0].id)

        mock_sms_service.send_assignment_notice.assert_called_once()
        assert mock_sms_service.send_assignment_notice.call_args.kwargs["duties"] == [
            (edit.department.name, "Sun 02 Aug at 09:00")
        ]
        mock_schedule_repo.mark_notice_sent.assert_called_once()

    def test_leaves_the_notice_unmarked_when_the_text_fails(self, service, edit, mock_sms_service, mock_schedule_repo):
        # Unmarked means notice_sent_at stays NULL and the ten-minute sweep retries, which is
        # the whole reason this path needs no warning of its own.
        mock_sms_service.send_assignment_notice.return_value = False

        result = service.add_assignment(edit.schedule.id, edit.spare[0].id)

        mock_schedule_repo.mark_notice_sent.assert_not_called()
        assert result.warnings == []

    def test_warns_when_the_added_worker_has_no_phone(self, service, edit, mock_worker_repo):
        edit.spare[0].phone = None

        result = service.add_assignment(edit.schedule.id, edit.spare[0].id)

        assert any("no phone number" in w for w in result.warnings)

    def test_refuses_a_worker_already_on_the_rota(self, service, edit, mock_schedule_repo):
        with pytest.raises(ConflictError, match="already on this rota"):
            service.add_assignment(edit.schedule.id, edit.on_rota[0].id)
        mock_schedule_repo.create_assignment.assert_not_called()

    def test_refuses_once_the_rota_is_at_its_maximum(
        self, mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo, service
    ):
        # Judged against the band frozen on the row, which is the number the screen shows.
        full = EditFixture(
            (mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo),
            band=(2, 2),
            on_rota=2,
        )
        with pytest.raises(ConflictError, match="maximum of 2"):
            service.add_assignment(full.schedule.id, full.spare[0].id)
        mock_schedule_repo.create_assignment.assert_not_called()

    def test_allows_an_add_to_a_rota_that_predates_the_band(
        self, mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo, service
    ):
        # min_workers/max_workers are nullable for rows generated before the band existed.
        # There is no honest ceiling to enforce, so the edit goes through rather than being
        # refused against a number nobody chose.
        old = EditFixture((mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo))
        old.schedule.min_workers = None
        old.schedule.max_workers = None

        service.add_assignment(old.schedule.id, old.spare[0].id)
        mock_schedule_repo.create_assignment.assert_called_once()

    def test_refuses_somebody_outside_the_scope(self, service, edit, mock_worker_repo, mock_schedule_repo):
        outsider = make_worker(first_name="Vera", last_name="Rubin")
        mock_worker_repo.get_by_id.side_effect = lambda wid: outsider if wid == outsider.id else None

        with pytest.raises(BadRequestError, match="Vera Rubin is not an active member"):
            service.add_assignment(edit.schedule.id, outsider.id)
        mock_schedule_repo.create_assignment.assert_not_called()

    def test_raises_for_an_unknown_worker(self, service, edit, mock_worker_repo):
        mock_worker_repo.get_by_id.side_effect = lambda wid: None
        with pytest.raises(NotFoundError, match="Worker"):
            service.add_assignment(edit.schedule.id, uuid4())

    def test_warns_rather_than_refusing_when_the_worker_is_unavailable(
        self, service, edit, mock_availability_repo, mock_schedule_repo
    ):
        # A head moving somebody onto a date they marked off has usually already spoken to
        # them. The app reports the clash; it does not overrule the conversation.
        mock_availability_repo.get_for_workers.return_value = [
            make_availability(
                worker_id=edit.spare[0].id,
                availability_type=AvailabilityType.SPECIFIC_DATE,
                specific_date=date(2026, 8, 2),
                day_of_week=None,
                is_available=False,
            )
        ]

        result = service.add_assignment(edit.schedule.id, edit.spare[0].id)

        assert any("marked unavailable or on leave" in w for w in result.warnings)
        mock_schedule_repo.create_assignment.assert_called_once()

    def test_warns_when_the_worker_is_already_on_another_rota(self, service, edit, mock_schedule_repo):
        mock_schedule_repo.get_workers_scheduled_on_date.return_value = [edit.spare[0].id]

        result = service.add_assignment(edit.schedule.id, edit.spare[0].id)

        assert any("already on another rota" in w for w in result.warnings)

    def test_maps_a_concurrent_duplicate_to_a_conflict(self, service, edit, mock_schedule_repo):
        # Two heads editing the same rota at once: unique (schedule_id, worker_id) is what
        # actually decides it, and 23505 has to read as a conflict rather than a 500.
        mock_schedule_repo.create_assignment.side_effect = APIError({"code": "23505", "message": "duplicate"})

        with pytest.raises(ConflictError, match="already on this rota"):
            service.add_assignment(edit.schedule.id, edit.spare[0].id)


class TestReplaceAssignmentWorker:
    def test_swaps_the_worker_on_the_row(self, service, edit, mock_schedule_repo):
        assignment = edit.assignment_of(edit.on_rota[0])
        mock_schedule_repo.get_assignment_with_schedule.return_value = assignment

        service.replace_assignment_worker(assignment.id, edit.spare[0].id)

        args = mock_schedule_repo.reassign_assignment.call_args.args
        assert args[0] == assignment.id
        assert args[1] == edit.spare[0].id

    def test_texts_both_people(self, service, edit, mock_schedule_repo, mock_sms_service):
        # A swap is the one edit where saying nothing leaves two people with the wrong idea.
        assignment = edit.assignment_of(edit.on_rota[0])
        mock_schedule_repo.get_assignment_with_schedule.return_value = assignment

        service.replace_assignment_worker(assignment.id, edit.spare[0].id)

        mock_sms_service.send_assignment_notice.assert_called_once()
        assert mock_sms_service.send_assignment_notice.call_args.kwargs["to"] == edit.spare[0].phone
        mock_sms_service.send_assignment_cancelled.assert_called_once()
        assert mock_sms_service.send_assignment_cancelled.call_args.kwargs["to"] == edit.on_rota[0].phone

    def test_warns_when_the_cancellation_text_fails(self, service, edit, mock_schedule_repo, mock_sms_service):
        # The only message in the system with no retry: the row it would be swept from is gone.
        assignment = edit.assignment_of(edit.on_rota[0])
        mock_schedule_repo.get_assignment_with_schedule.return_value = assignment
        mock_sms_service.send_assignment_cancelled.return_value = False

        result = service.replace_assignment_worker(assignment.id, edit.spare[0].id)

        assert any("Let them know another way" in w for w in result.warnings)

    def test_refuses_swapping_in_somebody_already_on_the_rota(self, service, edit, mock_schedule_repo):
        assignment = edit.assignment_of(edit.on_rota[0])
        mock_schedule_repo.get_assignment_with_schedule.return_value = assignment

        with pytest.raises(ConflictError, match="already on this rota"):
            service.replace_assignment_worker(assignment.id, edit.on_rota[1].id)
        mock_schedule_repo.reassign_assignment.assert_not_called()

    def test_refuses_swapping_a_worker_for_themselves(self, service, edit, mock_schedule_repo):
        assignment = edit.assignment_of(edit.on_rota[0])
        mock_schedule_repo.get_assignment_with_schedule.return_value = assignment

        with pytest.raises(ConflictError, match="already holds this duty"):
            service.replace_assignment_worker(assignment.id, edit.on_rota[0].id)

    def test_does_not_check_the_maximum(
        self, service, mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo
    ):
        # A swap is size-neutral. Refusing one on a full rota would make the commonest edit
        # impossible precisely when the rota is correctly staffed.
        full = EditFixture(
            (mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo),
            band=(2, 2),
            on_rota=2,
        )
        assignment = full.assignment_of(full.on_rota[0])
        mock_schedule_repo.get_assignment_with_schedule.return_value = assignment

        service.replace_assignment_worker(assignment.id, full.spare[0].id)
        mock_schedule_repo.reassign_assignment.assert_called_once()

    def test_raises_for_an_unknown_assignment(self, service, edit, mock_schedule_repo):
        mock_schedule_repo.get_assignment_with_schedule.return_value = None
        with pytest.raises(NotFoundError, match="Assignment"):
            service.replace_assignment_worker(uuid4(), edit.spare[0].id)


class TestRemoveAssignment:
    def test_removes_the_row_and_texts_the_worker(self, service, edit, mock_schedule_repo, mock_sms_service):
        assignment = edit.assignment_of(edit.on_rota[0])
        mock_schedule_repo.get_assignment_with_schedule.return_value = assignment

        service.remove_assignment(assignment.id)

        mock_schedule_repo.delete_assignment.assert_called_once_with(assignment.id)
        mock_sms_service.send_assignment_cancelled.assert_called_once()
        assert mock_sms_service.send_assignment_cancelled.call_args.kwargs["when"] == "Sun 02 Aug at 09:00"

    def test_warns_but_still_removes_when_it_drops_below_the_minimum(self, service, edit, mock_schedule_repo):
        # Never refuses. A head recording that somebody pulled out must be able to, and a rota
        # that still lists them is worse than a short one that is true.
        result = service.remove_assignment(self._prime(edit, mock_schedule_repo, edit.on_rota[0]))

        mock_schedule_repo.delete_assignment.assert_called_once()
        assert any("1 short of the 2" in w for w in result.warnings)

    def test_is_silent_when_the_rota_stays_above_its_minimum(
        self, service, mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo
    ):
        roomy = EditFixture(
            (mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_department_role_repo),
            band=(1, 4),
            on_rota=2,
        )
        assignment = roomy.assignment_of(roomy.on_rota[0])
        mock_schedule_repo.get_assignment_with_schedule.return_value = assignment

        assert service.remove_assignment(assignment.id).warnings == []

    def test_warns_when_the_cancellation_text_fails(self, service, edit, mock_schedule_repo, mock_sms_service):
        mock_sms_service.send_assignment_cancelled.return_value = False

        result = service.remove_assignment(self._prime(edit, mock_schedule_repo, edit.on_rota[0]))

        assert any("Let them know another way" in w for w in result.warnings)

    def test_raises_for_an_unknown_assignment(self, service, mock_schedule_repo):
        mock_schedule_repo.get_assignment_with_schedule.return_value = None
        with pytest.raises(NotFoundError, match="Assignment"):
            service.remove_assignment(uuid4())

    @staticmethod
    def _prime(edit, schedule_repo, worker):
        assignment = edit.assignment_of(worker)
        schedule_repo.get_assignment_with_schedule.return_value = assignment
        return assignment.id


class TestScopeOfAGeneratedSchedule:
    """Which scope produced a rota, reconstructed from the row — it does not record one."""

    def test_a_subteam_id_pins_it_to_the_subteam_scope(
        self,
        service,
        mock_schedule_repo,
        mock_worker_repo,
        mock_department_repo,
        mock_subteam_repo,
        mock_department_role_repo,
    ):
        department = make_department(band=(1, 4))
        subteam = make_subteam(department_id=department.id)
        worker, spare = make_worker(), make_worker(first_name="Spare")
        schedule = make_schedule(department_id=department.id, subteam_id=subteam.id, min_workers=1, max_workers=4)
        schedule.schedule_assignments = [
            make_assignment(schedule_id=schedule.id, worker_id=worker.id, subteam_id=subteam.id)
        ]
        mock_schedule_repo.get_with_assignments.return_value = schedule
        mock_schedule_repo.create_assignment.return_value = make_assignment(worker_id=spare.id)
        mock_department_repo.get_by_id.return_value = department
        mock_subteam_repo.get_by_id.return_value = subteam
        mock_subteam_repo.get_with_workers.return_value = [
            make_subteam_member(subteam=subteam, worker=w) for w in (worker, spare)
        ]
        mock_worker_repo.get_by_id.return_value = spare
        mock_department_role_repo.get_role_for_worker_in_department.return_value = None

        service.add_assignment(schedule.id, spare.id)

        # Resolved through the subteam's own roster, not the department's.
        mock_subteam_repo.get_with_workers.assert_called_once_with(subteam.id)
        assert mock_schedule_repo.create_assignment.call_args.args[0]["subteam_id"] == str(subteam.id)

    def test_subteam_stamps_on_a_department_wide_rota_mean_department_all(
        self,
        service,
        mock_schedule_repo,
        mock_worker_repo,
        mock_department_repo,
        mock_subteam_repo,
        mock_department_role_repo,
    ):
        # A DEPARTMENT_ALL rota has no subteam of its own but stamps one on each row, which is
        # the only thing separating it from a DEPARTMENT_ONLY rota on the row itself.
        department = make_department(band=(1, 4))
        subteam = make_subteam(department_id=department.id)
        member, spare = make_worker(), make_worker(first_name="Spare")
        schedule = make_schedule(department_id=department.id, subteam_id=None, min_workers=1, max_workers=4)
        schedule.schedule_assignments = [
            make_assignment(schedule_id=schedule.id, worker_id=member.id, subteam_id=subteam.id)
        ]
        mock_schedule_repo.get_with_assignments.return_value = schedule
        mock_schedule_repo.create_assignment.return_value = make_assignment(worker_id=spare.id)
        mock_department_repo.get_by_id.return_value = department
        mock_subteam_repo.get_by_department.return_value = [subteam]
        mock_worker_repo.get_workers_by_department_grouped_by_subteam.return_value = {subteam.id: [member, spare]}
        mock_worker_repo.get_by_id.return_value = spare
        mock_department_role_repo.get_role_for_worker_in_department.return_value = None

        service.add_assignment(schedule.id, spare.id)

        mock_worker_repo.get_workers_by_department_grouped_by_subteam.assert_called_once()
        assert mock_schedule_repo.create_assignment.call_args.args[0]["subteam_id"] == str(subteam.id)


class TestSpecialServiceStamping:
    """A rota records what it served, and records it from the rules rather than the client."""

    def test_a_single_date_is_stamped_with_the_special_name(
        self, service, mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_special_service_service
    ):
        mock_special_service_service.get_special_dates.return_value = {date(2026, 3, 15): "Jesus is Lord Service"}
        mock_department_repo.get_by_id.return_value = make_department(band=1)
        mock_worker_repo.get_department_only_workers.return_value = [make_worker()]
        mock_worker_repo.get_by_email.return_value = make_worker()
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_schedule_repo.create.return_value = make_schedule()

        service.generate_schedule(make_generate_request(scheduled_date=date(2026, 3, 15)), created_by="a@b.com")

        assert mock_schedule_repo.create.call_args.args[0]["special_service_name"] == "Jesus is Lord Service"

    def test_an_ordinary_date_is_stamped_with_nothing(
        self, service, mock_schedule_repo, mock_worker_repo, mock_department_repo
    ):
        mock_department_repo.get_by_id.return_value = make_department(band=1)
        mock_worker_repo.get_department_only_workers.return_value = [make_worker()]
        mock_worker_repo.get_by_email.return_value = make_worker()
        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_schedule_repo.create.return_value = make_schedule()

        service.generate_schedule(make_generate_request(), created_by="a@b.com")

        assert mock_schedule_repo.create.call_args.args[0]["special_service_name"] is None

    def test_the_preview_badges_the_special_dates(
        self, service, mock_worker_repo, mock_department_repo, mock_special_service_service
    ):
        mock_special_service_service.get_special_dates.return_value = {date(2026, 3, 1): "Communion"}
        mock_department_repo.get_by_id.return_value = make_department(band=1)
        mock_worker_repo.get_department_only_workers.return_value = [make_worker()]

        preview = service.preview_monthly_schedule(make_month_preview_request())

        first = next(d for d in preview.dates if d.scheduled_date == date(2026, 3, 1))
        assert first.is_special is True
        assert first.special_service_name == "Communion"
        assert all(not d.is_special for d in preview.dates if d.scheduled_date != date(2026, 3, 1))

    def test_the_commit_re_resolves_rather_than_trusting_the_client(
        self, service, mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_special_service_service
    ):
        # DateSelection carries no special field on purpose. Nothing the browser sends can
        # mislabel a date, or hide that it was special and so quietly skip the tally.
        mock_special_service_service.get_special_dates.return_value = {date(2026, 3, 1): "Communion"}
        worker = make_worker()
        mock_department_repo.get_by_id.return_value = make_department(band=1)
        mock_worker_repo.get_department_only_workers.return_value = [worker]
        mock_worker_repo.get_by_email.return_value = make_worker()
        mock_schedule_repo.get_by_department.return_value = []
        mock_schedule_repo.bulk_create_schedules.return_value = [
            make_schedule(scheduled_date=date(2026, 3, 1)),
            make_schedule(scheduled_date=date(2026, 3, 8)),
        ]
        # The commit re-reads each created schedule to return it with its assignments.
        mock_schedule_repo.get_with_assignments.side_effect = lambda sid: make_schedule(id=sid)

        service.commit_monthly_schedule(
            make_month_commit_request(
                dates=[
                    DateSelection(scheduled_date=date(2026, 3, 1), worker_ids=[worker.id]),
                    DateSelection(scheduled_date=date(2026, 3, 8), worker_ids=[worker.id]),
                ]
            ),
            created_by="a@b.com",
        )

        rows = mock_schedule_repo.bulk_create_schedules.call_args.args[0]
        stamped = {row["scheduled_date"]: row["special_service_name"] for row in rows}
        assert stamped == {"2026-03-01": "Communion", "2026-03-08": None}

    def test_the_tally_is_read_off_the_snapshot_not_a_join(
        self, service, mock_schedule_repo, mock_worker_repo, mock_department_repo, mock_special_service_service
    ):
        # `special_service_name is not None` is the whole test, and it costs no extra query:
        # the history fetch already embeds the schedule.
        ada, grace = make_worker(first_name="Ada"), make_worker(first_name="Grace")
        special_date = date(2026, 3, 1)
        mock_special_service_service.get_special_dates.return_value = {special_date: "Communion"}
        mock_department_repo.get_by_id.return_value = make_department(band=1)
        mock_worker_repo.get_department_only_workers.return_value = [ada, grace]
        # Grace has already served two special dates; Ada none. Ada should lead.
        mock_schedule_repo.get_assignment_history_for_workers.return_value = [
            make_assignment(
                worker_id=grace.id,
                schedules=make_schedule(scheduled_date=date(2026, 1, 4), special_service_name="Communion"),
            ),
            make_assignment(
                worker_id=grace.id,
                schedules=make_schedule(scheduled_date=date(2026, 2, 1), special_service_name="Communion"),
            ),
        ]

        preview = service.preview_monthly_schedule(
            make_month_preview_request(year=2026, month=3, days_of_week=[DayOfWeek.SUNDAY])
        )

        first = next(d for d in preview.dates if d.scheduled_date == special_date)
        assert [a.worker.id for a in plan_assignments(first)] == [ada.id]
