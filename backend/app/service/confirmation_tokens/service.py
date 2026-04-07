from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.repository.confirmation_tokens.repository import ConfirmationTokenRepository
from app.repository.schedules.repository import ScheduleRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.confirmation_tokens.models import (
    ConfirmationDetailsResponse,
    ConfirmationTokenCreate,
)
from app.schemas.models import AssignmentStatus
from app.schemas.schedules.models import AssignmentResponse

logger = get_logger(__name__)

TOKEN_TTL_HOURS = 48


class ConfirmationTokenService:
    def __init__(
        self,
        token_repo: ConfirmationTokenRepository,
        schedule_repo: ScheduleRepository,
        worker_repo: WorkerRepository,
    ) -> None:
        """Initialize the ConfirmationTokenService with required dependencies.

        Args:
            token_repo: Repository for confirmation token database operations.
            schedule_repo: Repository for schedule/assignment database operations.
            worker_repo: Repository for worker database operations.
        """
        self.token_repo = token_repo
        self.schedule_repo = schedule_repo
        self.worker_repo = worker_repo
        self.logger = logger.bind(service="ConfirmationTokenService")

    def create_token(self, assignment_id: UUID, worker_id: UUID) -> str:
        """Create a confirmation token for an assignment and return the full confirmation URL.

        If a token already exists for this assignment and it is still valid (not expired,
        not used), return the existing URL rather than creating a duplicate.

        Args:
            assignment_id: The UUID of the schedule assignment.
            worker_id: The UUID of the worker being reminded.

        Returns:
            str: The full public URL the worker can visit to confirm/decline,
                 e.g. "https://app.example.com/confirm/{token_uuid}".
        """
        log = self.logger.bind(method="create_token", assignment_id=str(assignment_id))

        # Return the existing token if one is still valid to avoid hitting the unique constraint
        existing = self.token_repo.get_by_assignment(assignment_id)
        if existing and existing.used_at is None:
            now = datetime.now(timezone.utc)
            # Make existing.expires_at offset-aware for comparison if needed
            expires_at = existing.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at > now:
                log.info("confirmation_token_reused", token_id=str(existing.id))
                return f"{settings.frontend_url}/confirm/{existing.id}"

        expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
        token_data = ConfirmationTokenCreate(
            worker_id=worker_id,
            assignment_id=assignment_id,
            expires_at=expires_at,
        )
        log.debug("creating_confirmation_token", token_data=token_data.model_dump())
        token = self.token_repo.create(token_data.model_dump(mode="json"))
        log.info("confirmation_token_created", token_id=str(token.id), expires_at=expires_at.isoformat())
        return f"{settings.frontend_url}/confirm/{token.id}"

    def get_confirmation_details(self, token_id: UUID) -> ConfirmationDetailsResponse:
        """Fetch the assignment details associated with a token for the public confirmation page.

        Always returns a response — the `expired` and `already_used` flags signal
        invalid states to the frontend rather than raising HTTP errors here.

        Args:
            token_id: The UUID from the SMS link path parameter.

        Returns:
            ConfirmationDetailsResponse with assignment details and token state flags.

        Raises:
            ValueError: If the token does not exist.
        """
        log = self.logger.bind(method="get_confirmation_details", token_id=str(token_id))

        token = self.token_repo.get_by_token(token_id)
        if not token:
            log.warning("confirmation_token_not_found")
            raise ValueError("Token not found")

        now = datetime.now(timezone.utc)
        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        already_used = token.used_at is not None
        expired = expires_at <= now

        assignment = self.schedule_repo.get_assignment_by_id(token.assignment_id)
        if not assignment:
            log.warning("confirmation_token_assignment_not_found", assignment_id=str(token.assignment_id))
            raise ValueError("Assignment not found")

        schedule = self.schedule_repo.get_by_id(assignment.schedule_id)
        worker = self.worker_repo.get_by_id(token.worker_id)

        if not schedule or not worker:
            log.warning("confirmation_token_missing_schedule_or_worker")
            raise ValueError("Schedule or worker data not found")

        return ConfirmationDetailsResponse(
            worker_name=f"{worker.first_name} {worker.last_name}".strip(),
            schedule_title=schedule.title,
            scheduled_date=schedule.scheduled_date.strftime("%A, %d %B %Y"),
            start_time=schedule.start_time.strftime("%H:%M"),
            end_time=schedule.end_time.strftime("%H:%M"),
            current_status=assignment.status,
            already_used=already_used,
            expired=expired,
        )

    def confirm(self, token_id: UUID, action: str) -> AssignmentResponse:
        """Validate a token and update the assignment status.

        Args:
            token_id: The UUID from the SMS link.
            action: Either "confirmed" or "declined".

        Returns:
            Updated AssignmentResponse.

        Raises:
            ValueError: If the token is invalid, expired, or already used.
        """
        log = self.logger.bind(method="confirm", token_id=str(token_id), action=action)

        if action not in ("confirmed", "declined"):
            raise ValueError("Action must be 'confirmed' or 'declined'")

        token = self.token_repo.get_by_token(token_id)
        if not token:
            log.warning("confirmation_token_not_found")
            raise ValueError("Token not found")

        if token.used_at is not None:
            log.warning("confirmation_token_already_used")
            raise ValueError("This link has already been used")

        now = datetime.now(timezone.utc)
        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            log.warning("confirmation_token_expired")
            raise ValueError("This link has expired")

        updated = self.schedule_repo.update_assignment_status(token.assignment_id, AssignmentStatus(action))
        if not updated:
            raise ValueError(f"Assignment {token.assignment_id} not found")

        self.token_repo.mark_used(token_id)
        log.info("assignment_status_updated", assignment_id=str(token.assignment_id), action=action)
        return updated
