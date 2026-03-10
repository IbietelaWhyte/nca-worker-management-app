from datetime import date, time
from uuid import uuid4

import pytest

from app.schemas.models import AssignmentStatus
from app.schemas.schedules.models import ScheduleCreate
from app.service.schedules.service import ScheduleService
from tests.unit.services.conftest import (
    make_assignment,
    make_availability,
    make_department,
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
):
    return ScheduleService(
        schedule_repo=mock_schedule_repo,
        worker_repo=mock_worker_repo,
        department_repo=mock_department_repo,
        subteam_repo=mock_subteam_repo,
        availability_repo=mock_availability_repo,
    )


def make_generate_request(**kwargs) -> ScheduleCreate:
    dept_id = kwargs.get("department_id", uuid4())
    return ScheduleCreate(
        department_id=dept_id,
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
        with pytest.raises(ValueError, match="not found"):
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
        mock_worker_repo.get_workers_by_department.return_value = workers
        mock_availability_repo.get_by_worker_and_type.return_value = None
        mock_availability_repo.get_by_worker_and_day.return_value = None
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
        mock_department_repo,
        mock_worker_repo,
    ):
        dept = make_department()
        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_workers_by_department.return_value = []

        with pytest.raises(ValueError, match="No workers found"):
            service.generate_schedule(make_generate_request(), created_by=uuid4())

    def test_raises_when_no_available_workers(
        self,
        service,
        mock_department_repo,
        mock_worker_repo,
        mock_availability_repo,
    ):
        dept = make_department()
        workers = [make_worker(), make_worker()]
        # All workers marked unavailable via specific date override
        unavailable = make_availability(is_available=False)

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_workers_by_department.return_value = workers
        mock_availability_repo.get_by_worker_and_type.return_value = unavailable

        with pytest.raises(ValueError, match="No available workers"):
            service.generate_schedule(make_generate_request(), created_by=uuid4())

    def test_specific_date_overrides_recurring(
        self,
        service,
        mock_department_repo,
        mock_worker_repo,
        mock_availability_repo,
    ):
        """A specific date unavailability should override recurring availability."""
        dept = make_department(workers_per_slot=1)
        worker = make_worker()
        # Recurring says available, specific date says unavailable
        specific_unavailable = make_availability(is_available=False)

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_workers_by_department.return_value = [worker]
        # Specific date override returns unavailable — recurring should be ignored
        mock_availability_repo.get_by_worker_and_type.return_value = specific_unavailable

        with pytest.raises(ValueError, match="No available workers"):
            service.generate_schedule(make_generate_request(), created_by=uuid4())
        # Verify recurring availability was never checked
        mock_availability_repo.get_by_worker_and_day.assert_not_called()

    def test_raises_when_department_not_found(self, service, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
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
            schedules=make_schedule(schedule_id=schedule_id, scheduled_date=date(2026, 3, 1)),  # Recent past date
        )

        mock_department_repo.get_by_id.return_value = dept
        mock_worker_repo.get_workers_by_department.return_value = [recently_assigned, never_assigned]
        mock_availability_repo.get_by_worker_and_type.return_value = None
        mock_availability_repo.get_by_worker_and_day.return_value = None

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


class TestUpdateAssignmentStatus:
    def test_updates_successfully(self, service, mock_schedule_repo):
        assignment = make_assignment()
        confirmed = make_assignment(status=AssignmentStatus.CONFIRMED)
        mock_schedule_repo.update_assignment_status.return_value = confirmed

        result = service.update_assignment_status(assignment.id, AssignmentStatus.CONFIRMED)
        assert result.status == AssignmentStatus.CONFIRMED

    def test_raises_when_not_found(self, service, mock_schedule_repo):
        mock_schedule_repo.update_assignment_status.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.update_assignment_status(uuid4(), AssignmentStatus.CONFIRMED)
