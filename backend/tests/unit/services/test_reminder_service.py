from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.repository.schedules.repository import ScheduleRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.schedules.models import AssignmentResponse, ScheduleResponse
from app.schemas.workers.models import WorkerResponse
from app.service.reminders.service import ReminderService
from app.service.sms.service import SMSService


def make_due_assignment(**kwargs) -> AssignmentResponse:
    """Builds a raw assignment dict as returned by the RPC function."""
    worker_id = kwargs.get("worker_id", uuid4())
    schedule_id = kwargs.get("schedule_id", uuid4())
    return AssignmentResponse(
        id=kwargs.get("id", uuid4()),
        schedule_id=schedule_id,
        worker_id=worker_id,
        department_role_id=kwargs.get("department_role_id"),
        subteam_id=kwargs.get("subteam_id"),
        status="pending",
        reminder_sent_at=None,
        created_at=kwargs.get("created_at", "2026-03-10T12:00:00Z"),
        workers=WorkerResponse(
            id=worker_id,
            first_name=kwargs.get("first_name", "John"),
            last_name=kwargs.get("last_name", "Doe"),
            phone=kwargs.get("phone", "+14165550101"),
            is_active=True,
            created_at=kwargs.get("worker_created_at", "2026-01-01T08:00:00Z"),
        ),
        schedules=ScheduleResponse(
            id=schedule_id,
            department_id=kwargs.get("department_id", uuid4()),
            subteam_id=kwargs.get("subteam_id"),
            title=kwargs.get("title", "Sunday Service"),
            scheduled_date=kwargs.get("scheduled_date", "2026-03-15"),
            start_time=kwargs.get("start_time", "09:00:00"),
            end_time=kwargs.get("end_time", "11:00:00"),
            reminder_days_before=kwargs.get("reminder_days_before", 2),
            notes=kwargs.get("notes", "Be on time!"),
            created_by=kwargs.get("created_by", uuid4()),
            created_at=kwargs.get("schedule_created_at", "2026-02-01T10:00:00Z"),

        ),
    )
    


@pytest.fixture
def mock_schedule_repo():
    return MagicMock(spec=ScheduleRepository)


@pytest.fixture
def mock_sms_service():
    return MagicMock(spec=SMSService)


@pytest.fixture
def mock_worker_repo():
    return MagicMock(spec=WorkerRepository)


@pytest.fixture
def service(mock_schedule_repo, mock_sms_service, mock_worker_repo):
    svc = ReminderService(
        schedule_repo=mock_schedule_repo,
        sms_service=mock_sms_service,
        worker_repo=mock_worker_repo,
    )
    return svc


class TestSendDueReminders:
    def test_sends_reminders_and_marks_sent(
        self, service, mock_schedule_repo, mock_sms_service
    ):
        assignments = [make_due_assignment(), make_due_assignment()]
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = assignments
        mock_sms_service.send_reminder.return_value = True

        service._send_due_reminders()

        assert mock_sms_service.send_reminder.call_count == 2
        assert mock_schedule_repo.mark_reminder_sent.call_count == 2

    def test_does_not_mark_sent_when_sms_fails(
        self, service, mock_schedule_repo, mock_sms_service
    ):
        assignment = make_due_assignment()
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = [assignment]
        mock_sms_service.send_reminder.return_value = False

        service._send_due_reminders()

        mock_sms_service.send_reminder.assert_called_once()
        mock_schedule_repo.mark_reminder_sent.assert_not_called()

    def test_skips_assignment_with_missing_worker_data(
        self, service, mock_schedule_repo, mock_sms_service
    ):
        assignment = make_due_assignment()
        assignment.workers = None
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = [assignment]

        service._send_due_reminders()

        mock_sms_service.send_reminder.assert_not_called()

    def test_handles_empty_due_list(
        self, service, mock_schedule_repo, mock_sms_service
    ):
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = []
        service._send_due_reminders()
        mock_sms_service.send_reminder.assert_not_called()


class TestTriggerManually:
    def test_returns_sent_count(
        self, service, mock_schedule_repo, mock_sms_service
    ):
        assignments = [make_due_assignment(), make_due_assignment(), make_due_assignment()]
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = assignments
        mock_sms_service.send_reminder.return_value = True

        count = service.trigger_manually()
        assert count == 3

    def test_returns_zero_when_none_due(
        self, service, mock_schedule_repo, mock_sms_service
    ):
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = []
        count = service.trigger_manually()
        assert count == 0

    def test_partial_failures_reflected_in_count(
        self, service, mock_schedule_repo, mock_sms_service
    ):
        assignments = [make_due_assignment(), make_due_assignment()]
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = assignments
        # First succeeds, second fails
        mock_sms_service.send_reminder.side_effect = [True, False]

        count = service.trigger_manually()
        assert count == 1


class TestSchedulerLifecycle:
    def test_start_adds_job_and_starts_scheduler(self, service):
        with patch.object(service.scheduler, "add_job") as mock_add, \
             patch.object(service.scheduler, "start") as mock_start:
            service.start()
            mock_add.assert_called_once()
            mock_start.assert_called_once()

    def test_stop_shuts_down_scheduler(self, service):
        with patch.object(service.scheduler, "shutdown") as mock_shutdown:
            service.stop()
            mock_shutdown.assert_called_once()
