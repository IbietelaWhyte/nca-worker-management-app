from collections import defaultdict
from datetime import date
from uuid import UUID

import structlog
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore

from app.core.config import settings
from app.core.logging import get_logger
from app.repository.departments.repository import DepartmentRepository
from app.repository.schedules.repository import ScheduleRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.schedules.models import AssignmentResponse, DueReminder, Schedule
from app.schemas.workers.models import WorkerResponse
from app.service.availability_prompts.service import AvailabilityPromptService
from app.service.sms.service import SMSService

logger = get_logger(__name__)


class ReminderService:
    """Sends workers the SMS messages that bracket an assignment.

    A worker hears about a duty at least twice: a notice shortly after the schedule is created, in
    time to arrange cover if they cannot make it, then once for each lead time in the schedule's
    `reminder_days_before` ladder. Both kinds group a person's dates into a single message, and
    are driven by background jobs rather than the request that creates the schedule — a monthly
    commit can create thirty assignments at once, and sending those inline would occupy a request
    thread through thirty serial Twilio calls, with no retry for whichever ones failed.
    """

    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        sms_service: SMSService,
        worker_repo: WorkerRepository,
        department_repo: DepartmentRepository,
        prompt_service: AvailabilityPromptService | None = None,
    ) -> None:
        """Initialize the ReminderService with required dependencies.

        Args:
            schedule_repo: Repository for schedule database operations.
            sms_service: Service for sending SMS notifications.
            worker_repo: Repository for worker database operations.
            department_repo: Repository for departments, to name the team in a message.
            prompt_service: Optional service for availability prompts. This service owns the only
                           scheduler in the process, so the daily prompt sweep is registered here
                           rather than starting a second one.
        """
        self.schedule_repo = schedule_repo
        self.sms_service = sms_service
        self.worker_repo = worker_repo
        self.department_repo = department_repo
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

        # Shared across the whole run so a department is fetched once rather than once per
        # assignment — a month of Sundays for forty people is otherwise the same row over and over.
        # Deliberately not held on self: this service is long-lived under the BackgroundScheduler,
        # and a cache outliving the run would keep serving a department's old name after a rename.
        department_names: dict[UUID, str] = {}

        notified = 0
        for worker_id, assignments in by_worker.items():
            if self._send_notice(worker_id, assignments, department_names):
                notified += 1
        log.info("notice_job_finished", notified=notified, workers=len(by_worker))
        return notified

    def _send_notice(
        self,
        worker_id: UUID,
        assignments: list[AssignmentResponse],
        department_names: dict[UUID, str],
    ) -> bool:
        """Send one worker their notice and mark every date it covered.

        Args:
            worker_id: The worker to notify.
            assignments: That worker's un-notified assignments, soonest first.
            department_names: Run-scoped cache of department id to name, shared across workers.

        Returns:
            bool: True if the SMS was sent and the assignments marked.
        """
        log = self.logger.bind(method="_send_notice", worker_id=str(worker_id), dates=len(assignments))

        worker = assignments[0].workers
        if not worker or not worker.phone:
            log.warning("notice_skipped_no_phone")
            return False

        schedules = [a.schedules for a in assignments if a.schedules]
        if not schedules:
            log.warning("notice_skipped_missing_schedule")
            return False
        # Naming the department matters most when a worker serves in more than one: "you have been
        # scheduled for 3 dates" alone leaves them guessing which team expects them.
        duties = [(self._department_name(s.department_id, department_names, log), self._describe(s)) for s in schedules]

        sent = self.sms_service.send_assignment_notice(
            to=worker.phone,
            worker_name=f"{worker.first_name} {worker.last_name}".strip(),
            duties=duties,
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
        """Remind everyone whose lead time falls today, one message per worker.

        A schedule reminds at several lead times now, so the sweep is grouped exactly as the
        notice job is: three lead times across four Sundays is twelve rows for one person, and
        twelve texts would be the feature working as designed and still being wrong.

        Returns:
            int: How many workers were reminded.
        """
        today = date.today()
        log = self.logger.bind(method="_send_due_reminders", date=today.isoformat())
        due = self.schedule_repo.get_assignments_due_for_reminder(today)
        if not due:
            return 0

        by_worker: dict[UUID, list[DueReminder]] = defaultdict(list)
        for reminder in due:
            by_worker[reminder.worker_id].append(reminder)
        log.info("reminders_due", workers=len(by_worker), reminders=len(due))

        # Run-scoped for the same reason as the notice sweep's: a department is fetched once, and
        # a cache held on self would keep serving its old name after a rename.
        department_names: dict[UUID, str] = {}

        reminded = 0
        for worker_id, reminders in by_worker.items():
            marks = [(r.assignment_id, r.days_before) for r in reminders]
            schedules = [r.schedules for r in reminders if r.schedules]
            if self._send_reminder(worker_id, reminders[0].workers, schedules, marks, department_names):
                reminded += 1
        log.info("reminder_job_finished", reminded=reminded, workers=len(by_worker))
        return reminded

    def _send_reminder(
        self,
        worker_id: UUID,
        worker: WorkerResponse | None,
        schedules: list[Schedule],
        marks: list[tuple[UUID, int]],
        department_names: dict[UUID, str],
    ) -> bool:
        """Send one worker their reminder and record the lead times it covered.

        `marks` is passed in rather than derived from `schedules` because the manual trigger has
        no lead time to record — see `trigger_for_schedule`. An empty list means "send, record
        nothing", which is a legitimate outcome and not a bug to be tidied away.

        Args:
            worker_id: The worker being reminded, for the log even when their record is missing.
            worker: That worker, as embedded on the due rows.
            schedules: The duties whose reminders fall today, soonest first.
            marks: (assignment id, lead time) pairs to record once the message is away.
            department_names: Run-scoped cache of department id to name, shared across workers.

        Returns:
            bool: True if the SMS was sent.
        """
        log = self.logger.bind(method="_send_reminder", worker_id=str(worker_id), dates=len(schedules))

        if not worker or not worker.phone:
            log.warning("reminder_skipped_no_phone")
            return False
        if not schedules:
            log.warning("reminder_skipped_missing_schedule")
            return False

        duties = [(self._department_name(s.department_id, department_names, log), self._describe(s)) for s in schedules]
        sent = self.sms_service.send_reminder(
            to=worker.phone,
            worker_name=f"{worker.first_name} {worker.last_name}".strip(),
            duties=duties,
        )
        if not sent:
            log.warning("reminder_send_failed")
            return False

        self.schedule_repo.mark_reminders_sent(marks)
        log.info("reminder_sent", marked=len(marks))
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

        Unlike the daily sweep this ignores what has already gone out, so a head can re-send
        after changing a rota. It texts every worker on the schedule without exception — the
        declined filter it used to apply was its only one, and there is no longer such a state.

        **It records nothing** (`marks=[]`). This send answers no particular lead time, so any
        `days_before` it wrote would be invented, and an invented one lands on a rung of the
        ladder that has not fired yet and cancels it — silently, days later. Before the ladder
        existed this method burned the automatic reminder outright; now it costs nothing.

        Args:
            schedule_id: The schedule whose workers to remind.

        Returns:
            int: How many workers were reminded.
        """
        log = self.logger.bind(method="trigger_for_schedule", schedule_id=str(schedule_id))
        schedule = self.schedule_repo.get_with_assignments(schedule_id)
        if not schedule:
            log.warning("schedule_not_found")
            return 0

        department_names: dict[UUID, str] = {}
        sent = 0
        for assignment in schedule.schedule_assignments:
            # One schedule, so one duty each: unique (schedule_id, worker_id) rules out a repeat.
            if self._send_reminder(assignment.worker_id, assignment.workers, [schedule], [], department_names):
                sent += 1
        log.info("schedule_reminders_finished", sent=sent, candidates=len(schedule.schedule_assignments))
        return sent

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _department_name(self, department_id: UUID, cache: dict[UUID, str], log: structlog.stdlib.BoundLogger) -> str:
        """Look up a department's name, remembering it for the rest of the run.

        Returns "" rather than raising or aborting when the name cannot be found: the department is
        context on the message, not the message itself, and withholding a whole notice over it would
        leave the worker never told they are scheduled. `SMSService` drops the department framing
        when it sees a blank.

        Args:
            department_id: The department that owns the schedule.
            cache: Run-scoped id-to-name map, mutated in place.
            log: The caller's bound logger, so a miss is attributed to the right worker.

        Returns:
            str: The department's name, or "" if it could not be resolved.
        """
        if department_id not in cache:
            department = self.department_repo.get_by_id(department_id)
            if not department:
                log.warning("notice_department_not_found", department_id=str(department_id))
            cache[department_id] = department.name if department else ""
        return cache[department_id]

    @staticmethod
    def _describe(schedule: Schedule) -> str:
        """Render one date for the notice SMS, e.g. "Sun 02 Aug at 09:00".

        Args:
            schedule: The schedule a worker has been assigned to.

        Returns:
            str: A short human-readable date and time.
        """
        return f"{schedule.scheduled_date.strftime('%a %d %b')} at {schedule.start_time.strftime('%H:%M')}"
