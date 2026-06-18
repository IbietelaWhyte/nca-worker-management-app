from datetime import date, time
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.schemas.models import AssignmentStatus
from app.schemas.schedules.models import ScheduleCreate
from app.service.schedules.service import ScheduleService
from tests.unit.services.conftest import (
    make_assignment,
    make_availability,
    make_department,
    make_department_role,
    make_schedule,
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
        dept = make_department(workers_per_slot=2)
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
        # All workers marked unavailable via specific date override
        unavailable = make_availability(is_available=False)

        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = workers
        mock_availability_repo.get_by_worker_and_type.return_value = unavailable

        with pytest.raises(BadRequestError, match="No available workers"):
            service.generate_schedule(make_generate_request(), created_by=uuid4())

    def test_specific_date_overrides_recurring(
        self,
        service,
        mock_schedule_repo,
        mock_department_repo,
        mock_worker_repo,
        mock_availability_repo,
    ):
        """A specific date unavailability should override recurring availability."""
        dept = make_department(workers_per_slot=1)
        worker = make_worker()
        # Recurring says available, specific date says unavailable
        specific_unavailable = make_availability(is_available=False)

        mock_schedule_repo.get_existing_schedule.return_value = None
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_department_only_workers.return_value = [worker]
        # Specific date override returns unavailable — recurring should be ignored
        mock_availability_repo.get_by_worker_and_type.return_value = specific_unavailable

        with pytest.raises(BadRequestError, match="No available workers"):
            service.generate_schedule(make_generate_request(), created_by=uuid4())
        # Verify recurring availability was never checked
        mock_availability_repo.get_by_worker_and_day.assert_not_called()

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
        dept = make_department(workers_per_slot=1)
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
        mock_availability_repo.get_by_worker_and_type.return_value = None
        mock_availability_repo.get_by_worker_and_day.return_value = None
        mock_schedule_repo.get_existing_schedule.return_value = None

        def get_assignments(worker_id):
            if worker_id == recently_assigned.id:
                return [prior_assignment]
            return []

        mock_schedule_repo.get_assignments_for_worker.side_effect = get_assignments
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
        dept = make_department(workers_per_slot=1)
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
        dept = make_department(workers_per_slot=1)
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


class TestUpdateAssignmentStatus:
    def test_updates_successfully(self, service, mock_schedule_repo):
        assignment = make_assignment()
        confirmed = make_assignment(status=AssignmentStatus.CONFIRMED)
        mock_schedule_repo.update_assignment_status.return_value = confirmed

        result = service.update_assignment_status(assignment.id, AssignmentStatus.CONFIRMED)
        assert result.status == AssignmentStatus.CONFIRMED

    def test_raises_when_not_found(self, service, mock_schedule_repo):
        mock_schedule_repo.update_assignment_status.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.update_assignment_status(uuid4(), AssignmentStatus.CONFIRMED)


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
