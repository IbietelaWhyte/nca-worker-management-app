from datetime import date
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.repository.availability_prompts.repository import AvailabilityPromptRepository
from app.repository.departments.repository import DepartmentRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.availability_prompts.models import (
    AvailabilityPromptCreate,
    AvailabilityPromptResponse,
    PromptSendResult,
)
from app.service.confirmation_tokens.service import ConfirmationTokenService
from app.service.sms.service import SMSService

logger = get_logger(__name__)


class AvailabilityPromptService:
    """Asks a department's workers, by SMS, to enter the dates they can serve.

    A prompt is either sent on demand or queued for a date. Queued sends live in the database
    rather than in an in-process timer: the scheduler uses an in-memory jobstore, so a job queued
    for next month would not survive a restart and would fire once per replica.
    """

    def __init__(
        self,
        prompt_repo: AvailabilityPromptRepository,
        department_repo: DepartmentRepository,
        worker_repo: WorkerRepository,
        sms_service: SMSService,
        token_service: ConfirmationTokenService,
    ) -> None:
        """Initialize the AvailabilityPromptService with required dependencies.

        Args:
            prompt_repo: Repository for availability prompt rows.
            department_repo: Repository for departments, to validate the target.
            worker_repo: Repository for workers, to resolve recipients.
            sms_service: Service for sending SMS.
            token_service: Mints the per-worker link the SMS carries.
        """
        self.prompt_repo = prompt_repo
        self.department_repo = department_repo
        self.worker_repo = worker_repo
        self.sms_service = sms_service
        self.token_service = token_service
        self.logger = logger.bind(service="AvailabilityPromptService")

    # ------------------------------------------------------------------
    # Managing prompts
    # ------------------------------------------------------------------

    def get_prompts(self, department_id: UUID) -> list[AvailabilityPromptResponse]:
        """List a department's configured prompts.

        Args:
            department_id: The department whose prompts to list.

        Returns:
            list[AvailabilityPromptResponse]: Newest first.
        """
        return self.prompt_repo.get_by_department(department_id)

    def create_prompt(
        self, department_id: UUID, data: AvailabilityPromptCreate, created_by: UUID | None
    ) -> AvailabilityPromptResponse:
        """Queue a prompt to be sent on a date, or every month.

        Args:
            department_id: The department whose workers will be prompted.
            data: Mode and the matching date fields.
            created_by: The worker who set it up, if known.

        Returns:
            AvailabilityPromptResponse: The stored prompt.

        Raises:
            NotFoundError: If the department does not exist.
        """
        log = self.logger.bind(method="create_prompt", department_id=str(department_id), mode=data.mode)
        if not self.department_repo.get_by_id(department_id):
            log.warning("prompt_department_not_found")
            raise NotFoundError(f"Department {department_id} not found")

        payload = data.model_dump(mode="json")
        payload["department_id"] = str(department_id)
        payload["created_by"] = str(created_by) if created_by else None
        prompt = self.prompt_repo.create(payload)
        log.info("prompt_created", prompt_id=str(prompt.id))
        return prompt

    def delete_prompt(self, prompt_id: UUID) -> None:
        """Remove a prompt.

        Args:
            prompt_id: The prompt to delete.

        Raises:
            NotFoundError: If the prompt does not exist.
        """
        log = self.logger.bind(method="delete_prompt", prompt_id=str(prompt_id))
        if not self.prompt_repo.get_by_id(prompt_id):
            log.warning("prompt_not_found")
            raise NotFoundError(f"Availability prompt {prompt_id} not found")
        self.prompt_repo.delete(prompt_id)
        log.info("prompt_deleted")

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send_now(self, department_id: UUID) -> PromptSendResult:
        """Prompt a department's active workers immediately.

        Args:
            department_id: The department to prompt.

        Returns:
            PromptSendResult: How many were texted, skipped for want of a phone number, or failed.

        Raises:
            NotFoundError: If the department does not exist.
        """
        department = self.department_repo.get_by_id(department_id)
        if not department:
            raise NotFoundError(f"Department {department_id} not found")
        return self._prompt_department(department_id, department.name)

    def send_due_prompts(self, today: date | None = None) -> int:
        """Send every prompt scheduled for today. Called by the daily job.

        Args:
            today: Override for the sweep date; defaults to the current date.

        Returns:
            int: How many prompts were sent.
        """
        today = today or date.today()
        log = self.logger.bind(method="send_due_prompts", today=today.isoformat())
        due = self.prompt_repo.get_due(today)
        if not due:
            return 0
        log.info("availability_prompts_due", count=len(due))

        sent = 0
        for prompt in due:
            department = self.department_repo.get_by_id(prompt.department_id)
            if not department:
                log.warning("prompt_department_missing", prompt_id=str(prompt.id))
                continue
            result = self._prompt_department(prompt.department_id, department.name)
            # Marked regardless of how many messages landed: a partial failure should not make
            # the whole department's prompt fire again on the next sweep.
            self.prompt_repo.mark_sent(prompt.id, today)
            sent += 1
            log.info("prompt_sent", prompt_id=str(prompt.id), **result.model_dump())
        return sent

    def _prompt_department(self, department_id: UUID, department_name: str) -> PromptSendResult:
        """Text every active, contactable worker in a department.

        Args:
            department_id: The department to prompt.
            department_name: Its name, used in the message.

        Returns:
            PromptSendResult: Per-outcome counts.
        """
        log = self.logger.bind(method="_prompt_department", department_id=str(department_id))
        workers = [w for w in self.worker_repo.get_workers_by_department(department_id) if w.is_active]

        result = PromptSendResult()
        for worker in workers:
            if not worker.phone:
                # Counted rather than silently skipped: nothing in the UI flags a worker with no
                # phone, and unlike a schedule reminder there is no other screen where their
                # absence would be noticed.
                result.skipped_no_phone += 1
                continue
            token_id = self.token_service.get_or_create_token_id(worker.id)
            ok = self.sms_service.send_availability_prompt(
                to=worker.phone,
                worker_name=f"{worker.first_name} {worker.last_name}".strip(),
                department_name=department_name,
                availability_url=f"{settings.frontend_url}/availability/{token_id}",
            )
            if ok:
                result.sent += 1
            else:
                result.failed += 1

        log.info("department_prompted", **result.model_dump())
        return result
