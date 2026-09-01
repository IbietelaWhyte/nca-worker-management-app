from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.repository.schedules.repository import ScheduleRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.schedules.models import AssignmentResponse, ScheduleResponse
from app.schemas.workers.models import WorkerResponse
from app.service.confirmation_tokens.service import ConfirmationTokenService
from app.service.reminders.service import ReminderService
from app.service.sms.service import SMSService


def make_due_assignment(**kwargs) -> AssignmentResponse:
    """Builds an assignment with worker and schedule embedded, as the RPCs return it."""
    worker_id = kwargs.get("worker_id", uuid4())
    schedule_id = kwargs.get("schedule_id", uuid4())
    return AssignmentResponse(
        id=kwargs.get("id", uuid4()),
        schedule_id=schedule_id,
        worker_id=worker_id,
        department_role_id=kwargs.get("department_role_id"),
        subteam_id=kwargs.get("subteam_id"),
        status=kwargs.get("status", "pending"),
        reminder_sent_at=None,
        notice_sent_at=kwargs.get("notice_sent_at"),
        workers=WorkerResponse(
            id=worker_id,
            first_name=kwargs.get("first_name", "John"),
            last_name=kwargs.get("last_name", "Doe"),
            email=kwargs.get("email", "john.doe@example.com"),
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
def mock_token_service():
    token_service = MagicMock(spec=ConfirmationTokenService)
    token_service.create_token.return_value = "https://app.example.com/confirm/tok"
    return token_service


@pytest.fixture
def service(mock_schedule_repo, mock_sms_service, mock_worker_repo, mock_token_service):
    return ReminderService(
        schedule_repo=mock_schedule_repo,
        sms_service=mock_sms_service,
        worker_repo=mock_worker_repo,
        token_service=mock_token_service,
    )


class TestSendPendingNotices:
    def test_groups_a_workers_dates_into_one_message(
        self, service, mock_schedule_repo, mock_sms_service, mock_token_service
    ):
        # The whole point of the notice job: monthly generation rosters one person onto four
        # Sundays, and they should get one text, not four.
        worker_id = uuid4()
        assignments = [
            make_due_assignment(worker_id=worker_id, scheduled_date=day)
            for day in ("2026-08-02", "2026-08-09", "2026-08-16", "2026-08-23")
        ]
        mock_schedule_repo.get_assignments_due_for_notice.return_value = assignments
        mock_sms_service.send_assignment_notice.return_value = True

        assert service.trigger_notices() == 1
        mock_sms_service.send_assignment_notice.assert_called_once()
        assert len(mock_sms_service.send_assignment_notice.call_args.kwargs["dates"]) == 4
        # One token for the worker, not one per date.
        mock_token_service.create_token.assert_called_once_with(worker_id=worker_id)

    def test_marks_every_date_the_notice_covered(self, service, mock_schedule_repo, mock_sms_service):
        worker_id = uuid4()
        assignments = [make_due_assignment(worker_id=worker_id) for _ in range(3)]
        mock_schedule_repo.get_assignments_due_for_notice.return_value = assignments
        mock_sms_service.send_assignment_notice.return_value = True

        service.trigger_notices()
        marked = mock_schedule_repo.mark_notice_sent.call_args.args[0]
        assert sorted(marked) == sorted(a.id for a in assignments)

    def test_one_message_per_worker(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_assignments_due_for_notice.return_value = [
            make_due_assignment(),
            make_due_assignment(),
            make_due_assignment(),
        ]
        mock_sms_service.send_assignment_notice.return_value = True

        assert service.trigger_notices() == 3
        assert mock_sms_service.send_assignment_notice.call_count == 3

    def test_leaves_assignments_unmarked_when_sending_fails(self, service, mock_schedule_repo, mock_sms_service):
        # Unmarked means the next run retries — the reminder job's exact-date RPC cannot do this.
        mock_schedule_repo.get_assignments_due_for_notice.return_value = [make_due_assignment()]
        mock_sms_service.send_assignment_notice.return_value = False

        assert service.trigger_notices() == 0
        mock_schedule_repo.mark_notice_sent.assert_not_called()

    def test_skips_a_worker_with_no_phone(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_assignments_due_for_notice.return_value = [make_due_assignment(phone=None)]

        assert service.trigger_notices() == 0
        mock_sms_service.send_assignment_notice.assert_not_called()
        mock_schedule_repo.mark_notice_sent.assert_not_called()

    def test_does_not_send_a_linkless_notice(self, service, mock_schedule_repo, mock_sms_service, mock_token_service):
        # A notice with no link has nothing to act on, so it is deferred rather than wasted.
        mock_token_service.create_token.side_effect = RuntimeError("token store down")
        mock_schedule_repo.get_assignments_due_for_notice.return_value = [make_due_assignment()]

        assert service.trigger_notices() == 0
        mock_sms_service.send_assignment_notice.assert_not_called()
        mock_schedule_repo.mark_notice_sent.assert_not_called()

    def test_no_work_is_not_an_error(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_assignments_due_for_notice.return_value = []

        assert service.trigger_notices() == 0
        mock_sms_service.send_assignment_notice.assert_not_called()


class TestSendDueReminders:
    def test_sends_reminders_and_marks_sent(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = [
            make_due_assignment(),
            make_due_assignment(),
        ]
        mock_sms_service.send_reminder.return_value = True

        assert service.trigger_manually() == 2
        assert mock_schedule_repo.mark_reminder_sent.call_count == 2

    def test_includes_the_confirmation_link(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = [make_due_assignment()]
        mock_sms_service.send_reminder.return_value = True

        service.trigger_manually()
        assert mock_sms_service.send_reminder.call_args.kwargs["confirmation_url"] == (
            "https://app.example.com/confirm/tok"
        )

    def test_still_reminds_a_worker_who_already_confirmed(self, service, mock_schedule_repo, mock_sms_service):
        # The RPC no longer filters to 'pending'. Confirming from the initial notice must not
        # cancel the pre-service reminder.
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = [make_due_assignment(status="confirmed")]
        mock_sms_service.send_reminder.return_value = True

        assert service.trigger_manually() == 1

    def test_does_not_mark_sent_when_sms_fails(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = [make_due_assignment()]
        mock_sms_service.send_reminder.return_value = False

        assert service.trigger_manually() == 0
        mock_schedule_repo.mark_reminder_sent.assert_not_called()

    def test_skips_assignments_missing_worker_data(self, service, mock_schedule_repo, mock_sms_service):
        assignment = make_due_assignment()
        assignment.workers = None
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = [assignment]

        assert service.trigger_manually() == 0
        mock_sms_service.send_reminder.assert_not_called()

    def test_skips_a_worker_with_no_phone(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = [make_due_assignment(phone=None)]

        assert service.trigger_manually() == 0
        mock_sms_service.send_reminder.assert_not_called()

    def test_no_due_reminders(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_assignments_due_for_reminder.return_value = []

        assert service.trigger_manually() == 0
        mock_sms_service.send_reminder.assert_not_called()


class TestTriggerForSchedule:
    def _schedule_with(self, assignments):
        schedule = make_due_assignment().schedules
        schedule.schedule_assignments = assignments
        return schedule

    def test_reminds_everyone_on_the_schedule(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_with_assignments.return_value = self._schedule_with(
            [make_due_assignment(), make_due_assignment()]
        )
        mock_sms_service.send_reminder.return_value = True

        assert service.trigger_for_schedule(uuid4()) == 2

    def test_skips_workers_who_declined(self, service, mock_schedule_repo, mock_sms_service):
        # Re-sending is deliberate here (an HOD may have changed the rota), but chasing somebody
        # about a duty they already turned down is not.
        mock_schedule_repo.get_with_assignments.return_value = self._schedule_with(
            [make_due_assignment(status="declined"), make_due_assignment(status="confirmed")]
        )
        mock_sms_service.send_reminder.return_value = True

        assert service.trigger_for_schedule(uuid4()) == 1

    def test_returns_zero_for_an_unknown_schedule(self, service, mock_schedule_repo, mock_sms_service):
        mock_schedule_repo.get_with_assignments.return_value = None

        assert service.trigger_for_schedule(uuid4()) == 0
        mock_sms_service.send_reminder.assert_not_called()


class TestSchedulerLifecycle:
    def test_constructing_the_service_creates_no_scheduler(self, service):
        # The DI factory builds one of these per request to back the trigger endpoints. Creating
        # a BackgroundScheduler in __init__ leaked an idle one on every call.
        assert service.scheduler is None

    def test_start_registers_both_jobs(self, service):
        with patch("app.service.reminders.service.BackgroundScheduler") as mock_cls:
            service.start()
            scheduler = mock_cls.return_value
            job_ids = {call.kwargs["id"] for call in scheduler.add_job.call_args_list}
            assert job_ids == {"daily_reminders", "assignment_notices"}
            scheduler.start.assert_called_once()

    def test_stop_shuts_down_scheduler(self, service):
        with patch("app.service.reminders.service.BackgroundScheduler") as mock_cls:
            service.start()
            service.stop()
            mock_cls.return_value.shutdown.assert_called_once()

    def test_stop_is_a_noop_when_never_started(self, service):
        service.stop()  # must not raise — request-scoped instances never start a scheduler
        assert service.scheduler is None
