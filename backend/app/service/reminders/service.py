from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore

from app.core.logging import get_logger
from app.repository.schedules.repository import ScheduleRepository
from app.repository.workers.repository import WorkerRepository
from app.service.sms.service import SMSService

logger = get_logger(__name__)


class ReminderService:
    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        sms_service: SMSService,
        worker_repo: WorkerRepository,
    ) -> None:
        """Initialize the ReminderService with required dependencies.
        
        Args:
            schedule_repo: Repository for schedule database operations.
            sms_service: Service for sending SMS notifications.
            worker_repo: Repository for worker database operations.
        """
        self.schedule_repo = schedule_repo
        self.sms_service = sms_service
        self.worker_repo = worker_repo
        self.scheduler = BackgroundScheduler()

        # bind the logger to the service name for structured logging
        self.logger = logger.bind(service="ReminderService")

    def start(self) -> None:
        """Start the background scheduler for automated reminders.
        
        Schedules a daily job at 08:00 to send reminders for upcoming assignments.
        """
        self.scheduler.add_job(
            self._send_due_reminders,
            trigger="cron",
            hour=8,
            minute=0,
            id="daily_reminders",
            replace_existing=True,
        )
        self.scheduler.start()
        self.logger.info("reminder_scheduler_started", trigger="daily_at_08:00")

    def stop(self) -> None:
        """Stop the background scheduler and all scheduled jobs."""
        self.scheduler.shutdown()
        self.logger.info("reminder_scheduler_stopped")

    def _send_due_reminders(self) -> None:
        """Internal method to send reminders for all due assignments.
        
        This is called automatically by the scheduler. It fetches all assignments
        due for reminders today, sends SMS reminders to workers, and marks them as sent.
        """
        # bind the method for better traceability in logs
        log = self.logger.bind(method="_send_due_reminders")
        today = date.today()
        log.info("reminder_job_started", date=today.isoformat())

        due_assignments = self.schedule_repo.get_assignments_due_for_reminder(
            today)
        log.info("reminders_due", count=len(due_assignments))

        sent = 0
        failed = 0

        for assignment in due_assignments:
            worker = self.worker_repo.get_by_id(assignment.worker_id)
            schedule = self.schedule_repo.get_by_id(assignment.schedule_id)

            if not worker or not schedule:
                log.warning(
                    "reminder_skipped_missing_data",
                    assignment_id=assignment.id,
                )
                continue

            phone = worker.phone
            if not phone:
                log.warning(
                    "reminder_skipped_no_phone",
                    worker_id=worker.id,
                )
                continue

            success = self.sms_service.send_reminder(
                to=phone,
                worker_name=f"{worker.first_name} {worker.last_name}".strip(),
                schedule_title=schedule.title,
                scheduled_date=schedule.scheduled_date.strftime("%Y-%m-%d"),
                start_time=schedule.start_time.strftime("%H:%M"),
            )

            if success:
                self.schedule_repo.mark_reminder_sent(assignment.id)
                sent += 1
            else:
                failed += 1

        log.info(
            "reminder_job_completed",
            sent=sent,
            failed=failed,
            date=today.isoformat(),
        )

    def trigger_manually(self) -> int:
        """Manually trigger reminder sending for testing or emergency use.
        
        Returns:
            int: Number of reminders successfully sent.
        """
        log = self.logger.bind(method="trigger_manually")
        log.info("reminder_manual_trigger")
        today = date.today()
        due_assignments = self.schedule_repo.get_assignments_due_for_reminder(
            today)
        sent_count = 0

        for assignment in due_assignments:
            worker = self.worker_repo.get_by_id(assignment.worker_id)
            schedule = self.schedule_repo.get_by_id(assignment.schedule_id)
            if not worker or not schedule:
                continue
            phone = worker.phone
            if not phone:
                continue

            sent = self.sms_service.send_reminder(
                to=phone,
                worker_name=f"{worker.first_name} {worker.last_name}".strip(),
                schedule_title=schedule.title,
                scheduled_date=schedule.scheduled_date.strftime("%Y-%m-%d"),
                start_time=schedule.start_time.strftime("%H:%M"),
            )
            if sent:
                self.schedule_repo.mark_reminder_sent(assignment.id)
                sent_count += 1

        log.info("reminder_manual_trigger_completed", sent=sent_count)
        return sent_count
