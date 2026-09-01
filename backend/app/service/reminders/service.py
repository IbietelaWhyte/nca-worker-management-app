from collections import defaultdict
from datetime import date
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore

from app.core.config import settings
from app.core.logging import get_logger
from app.repository.schedules.repository import ScheduleRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.models import AssignmentStatus
from app.schemas.schedules.models import AssignmentResponse, Schedule
from app.service.availability_prompts.service import AvailabilityPromptService
from app.service.confirmation_tokens.service import ConfirmationTokenService
from app.service.sms.service import SMSService

logger = get_logger(__name__)


class ReminderService:
    """Sends workers the two SMS messages that bracket an assignment.

    A worker hears about a duty twice: a notice shortly after the schedule is created, in time to
    arrange cover if they cannot make it, and a reminder `reminder_days_before` the service. Both
    are driven by background jobs rather than the request that creates the schedule — a monthly
    commit can create thirty assignments at once, and sending those inline would occupy a request
    thread through thirty serial Twilio calls, with no retry for whichever ones failed.
    """

    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        sms_service: SMSService,
        worker_repo: WorkerRepository,
        token_service: ConfirmationTokenService | None = None,
        prompt_service: AvailabilityPromptService | None = None,
    ) -> None:
        """Initialize the ReminderService with required dependencies.

        Args:
            schedule_repo: Repository for schedule database operations.
            sms_service: Service for sending SMS notifications.
            worker_repo: Repository for worker database operations.
            token_service: Optional service for creating confirmation tokens.
                           When provided, messages include a confirmation link.
            prompt_service: Optional service for availability prompts. This service owns the only
                           scheduler in the process, so the daily prompt sweep is registered here
                           rather than starting a second one.
        """
        self.schedule_repo = schedule_repo
        self.sms_service = sms_service
        self.worker_repo = worker_repo
        self.token_service = token_service
        self.prompt_service = prompt_service
        # Created lazily in start(): this service is also constructed per-request to back the
        # manual trigger endpoints, and those instances must not each spin up a scheduler.
        self.scheduler: BackgroundScheduler | None = None

        # bind the logger to the service name for structured logging
        self.logger = logger.bind(service="ReminderService")

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler for automated messages.

        Two jobs: the pre-service reminder sweep once a day, and the initial notice often enough
        that being scheduled feels immediate.
        """
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self._send_due_reminders,
            trigger="cron",
            hour=settings.reminder_hour,
            minute=0,
            id="daily_reminders",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._send_pending_notices,
            trigger="interval",
            minutes=settings.notice_interval_minutes,
            id="assignment_notices",
            replace_existing=True,
        )
        if self.prompt_service:
            # Same hour as the reminder sweep: both are "morning admin", and a worker who is
            # both rostered and being asked for availability gets their texts together.
            self.scheduler.add_job(
                self.prompt_service.send_due_prompts,
                trigger="cron",
                hour=settings.reminder_hour,
                minute=0,
                id="availability_prompts",
                replace_existing=True,
            )
        self.scheduler.start()
        self.logger.info(
            "reminder_scheduler_started",
            reminder_hour=settings.reminder_hour,
            notice_interval_minutes=settings.notice_interval_minutes,
        )

    def stop(self) -> None:
        """Stop the background scheduler and all scheduled jobs."""
        if self.scheduler is None:
            return
        self.scheduler.shutdown()
        self.scheduler = None
        self.logger.info("reminder_scheduler_stopped")

    # ------------------------------------------------------------------
    # Initial notice — "you have been scheduled"
    # ------------------------------------------------------------------

    def _send_pending_notices(self) -> int:
        """Announce newly created assignments, one message per worker.

        Assignments are grouped by worker so somebody rostered onto every Sunday in a month gets
        a single text listing all of them rather than five in a row. Every date in a batch is
        marked in one statement, so a crash cannot leave half of them looking un-notified and
        announce them again on the next run.

        Returns:
            int: How many workers were notified.
        """
        log = self.logger.bind(method="_send_pending_notices")
        due = self.schedule_repo.get_assignments_due_for_notice()
        if not due:
            return 0

        by_worker: dict[UUID, list[AssignmentResponse]] = defaultdict(list)
        for assignment in due:
            by_worker[assignment.worker_id].append(assignment)
        log.info("notices_due", workers=len(by_worker), assignments=len(due))

        notified = 0
        for worker_id, assignments in by_worker.items():
            if self._send_notice(worker_id, assignments):
                notified += 1
        log.info("notice_job_finished", notified=notified, workers=len(by_worker))
        return notified

    def _send_notice(self, worker_id: UUID, assignments: list[AssignmentResponse]) -> bool:
        """Send one worker their notice and mark every date it covered.

        Args:
            worker_id: The worker to notify.
            assignments: That worker's un-notified assignments, soonest first.

        Returns:
            bool: True if the SMS was sent and the assignments marked.
        """
        log = self.logger.bind(method="_send_notice", worker_id=str(worker_id), dates=len(assignments))

        worker = assignments[0].workers
        if not worker or not worker.phone:
            log.warning("notice_skipped_no_phone")
            return False

        confirmation_url = self._confirmation_url(worker_id)
        if not confirmation_url:
            # Without a link the message has no action to offer, and the assignments stay
            # un-notified so the next run can try again.
            log.warning("notice_skipped_no_confirmation_link")
            return False

        schedules = [a.schedules for a in assignments if a.schedules]
        if not schedules:
            log.warning("notice_skipped_missing_schedule")
            return False
        dates = [self._describe(s) for s in schedules]

        sent = self.sms_service.send_assignment_notice(
            to=worker.phone,
            worker_name=f"{worker.first_name} {worker.last_name}".strip(),
            dates=dates,
            confirmation_url=confirmation_url,
        )
        if not sent:
            log.warning("notice_send_failed")
            return False

        self.schedule_repo.mark_notice_sent([a.id for a in assignments])
        log.info("notice_sent")
        return True

    # ------------------------------------------------------------------
    # Pre-service reminder
    # ------------------------------------------------------------------

    def _send_due_reminders(self) -> int:
        """Send reminders for every assignment whose lead time falls today.

        Returns:
            int: How many reminders were sent.
        """
        today = date.today()
        log = self.logger.bind(method="_send_due_reminders", date=today.isoformat())
        due = self.schedule_repo.get_assignments_due_for_reminder(today)
        log.info("reminders_due", count=len(due))
        sent = self._send_reminders(due)
        log.info("reminder_job_finished", sent=sent, due=len(due))
        return sent

    def _send_reminders(self, assignments: list[AssignmentResponse]) -> int:
        """Send one reminder per assignment, marking each that succeeds.

        Args:
            assignments: Assignments to remind about.

        Returns:
            int: How many reminders were sent.
        """
        sent = 0
        for assignment in assignments:
            if self._send_reminder(assignment):
                sent += 1
        return sent

    def _send_reminder(self, assignment: AssignmentResponse) -> bool:
        """Send a single pre-service reminder.

        Args:
            assignment: The assignment to remind about, with worker and schedule embedded.

        Returns:
            bool: True if the SMS was sent and the assignment marked.
        """
        log = self.logger.bind(method="_send_reminder", assignment_id=str(assignment.id))

        worker, schedule = assignment.workers, assignment.schedules
        if not worker or not schedule:
            log.warning("reminder_skipped_missing_data")
            return False
        if not worker.phone:
            log.warning("reminder_skipped_no_phone")
            return False

        sent = self.sms_service.send_reminder(
            to=worker.phone,
            worker_name=f"{worker.first_name} {worker.last_name}".strip(),
            schedule_title=schedule.title,
            scheduled_date=schedule.scheduled_date.strftime("%Y-%m-%d"),
            start_time=schedule.start_time.strftime("%H:%M"),
            confirmation_url=self._confirmation_url(assignment.worker_id),
        )
        if not sent:
            log.warning("reminder_send_failed")
            return False

        self.schedule_repo.mark_reminder_sent(assignment.id)
        log.info("reminder_sent")
        return True

    # ------------------------------------------------------------------
    # Manual triggers
    # ------------------------------------------------------------------

    def trigger_manually(self) -> int:
        """Run the reminder sweep now rather than waiting for the daily job.

        Returns:
            int: How many reminders were sent.
        """
        self.logger.info("reminders_triggered_manually")
        return self._send_due_reminders()

    def trigger_notices(self) -> int:
        """Run the notice job now rather than waiting for the interval.

        Returns:
            int: How many workers were notified.
        """
        self.logger.info("notices_triggered_manually")
        return self._send_pending_notices()

    def trigger_for_schedule(self, schedule_id: UUID) -> int:
        """Send reminders to everyone on one schedule, on demand.

        Unlike the daily sweep this ignores `reminder_sent_at`, so an HOD can re-send after
        changing a rota — but it still skips workers who have declined, who should not be chased
        about a duty they have already turned down.

        Args:
            schedule_id: The schedule whose workers to remind.

        Returns:
            int: How many reminders were sent.
        """
        log = self.logger.bind(method="trigger_for_schedule", schedule_id=str(schedule_id))
        schedule = self.schedule_repo.get_with_assignments(schedule_id)
        if not schedule:
            log.warning("schedule_not_found")
            return 0

        # get_with_assignments embeds the worker but not the schedule, which _send_reminder needs.
        assignments = [
            a.model_copy(update={"schedules": schedule})
            for a in schedule.schedule_assignments
            if a.status != AssignmentStatus.DECLINED
        ]
        sent = self._send_reminders(assignments)
        log.info("schedule_reminders_finished", sent=sent, candidates=len(assignments))
        return sent

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _confirmation_url(self, worker_id: UUID) -> str | None:
        """Mint or reuse the worker's confirmation link.

        Args:
            worker_id: The worker the link identifies.

        Returns:
            str | None: The URL, or None if tokens are unavailable or minting failed.
        """
        if not self.token_service:
            return None
        try:
            return self.token_service.create_token(worker_id=worker_id)
        except Exception as exc:  # noqa: BLE001 — a token failure must not abort the whole run
            self.logger.warning("confirmation_token_creation_failed", worker_id=str(worker_id), error=str(exc))
            return None

    @staticmethod
    def _describe(schedule: Schedule) -> str:
        """Render one date for the notice SMS, e.g. "Sun 02 Aug at 09:00".

        Args:
            schedule: The schedule a worker has been assigned to.

        Returns:
            str: A short human-readable date and time.
        """
        return f"{schedule.scheduled_date.strftime('%a %d %b')} at {schedule.start_time.strftime('%H:%M')}"
