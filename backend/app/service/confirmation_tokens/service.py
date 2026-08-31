from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import BadRequestError, GoneError, NotFoundError
from app.core.logging import get_logger
from app.repository.confirmation_tokens.repository import ConfirmationTokenRepository
from app.repository.schedules.repository import ScheduleRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.confirmation_tokens.models import (
    ConfirmableAssignment,
    ConfirmationDetailsResponse,
    ConfirmationTokenCreate,
    ConfirmationTokenResponse,
)
from app.schemas.models import AssignmentStatus
from app.schemas.schedules.models import AssignmentResponse

logger = get_logger(__name__)


class ConfirmationTokenService:
    """Issues and resolves the public links workers use to confirm or decline duties.

    A token identifies a *worker*, not a single assignment. One link therefore covers every
    upcoming duty that worker holds, which is what lets a month of dates be announced in a single
    SMS, and it stays usable until it expires so they can answer one date now and another later.
    """

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

    def create_token(self, worker_id: UUID) -> str:
        """Return the worker's confirmation URL, minting a token only if they have no live one.

        Reuse is deliberate rather than an optimisation: the initial notice and the pre-service
        reminder are sent weeks apart and must lead to the same page, so the link in the first
        message keeps working when the second arrives.

        Args:
            worker_id: The UUID of the worker the link identifies.

        Returns:
            str: The full public URL the worker can visit, e.g.
                 "https://app.example.com/confirm/{token_uuid}".
        """
        log = self.logger.bind(method="create_token", worker_id=str(worker_id))

        now = datetime.now(timezone.utc)
        existing = self.token_repo.get_live_for_worker(worker_id, now)
        if existing:
            log.info("confirmation_token_reused")
            return f"{settings.frontend_url}/confirm/{existing.id}"

        expires_at = now + timedelta(days=settings.confirmation_token_ttl_days)
        token_data = ConfirmationTokenCreate(worker_id=worker_id, expires_at=expires_at)
        # Log the worker linkage only — never the token id itself (it's the link credential).
        log.info("creating_confirmation_token")
        token = self.token_repo.create(token_data.model_dump(mode="json"))
        log.info("confirmation_token_created", expires_at=expires_at.isoformat())
        return f"{settings.frontend_url}/confirm/{token.id}"

    def get_confirmation_details(self, token_id: UUID) -> ConfirmationDetailsResponse:
        """List the worker's upcoming duties for the public confirmation page.

        Always returns a response for a token that exists — `expired` signals the invalid state to
        the frontend rather than raising here, so the page can explain itself.

        Args:
            token_id: The UUID from the SMS link path parameter.

        Returns:
            ConfirmationDetailsResponse with the worker's name, their upcoming duties, and
            whether the link has expired.

        Raises:
            NotFoundError: If the token or its worker does not exist.
        """
        log = self.logger.bind(method="get_confirmation_details")

        token = self._require_token(token_id)
        worker = self.worker_repo.get_by_id(token.worker_id)
        if not worker:
            log.warning("confirmation_token_worker_not_found")
            raise NotFoundError("Worker not found")

        worker_name = f"{worker.first_name} {worker.last_name}".strip()
        if self._is_expired(token.expires_at):
            log.info("confirmation_token_expired")
            return ConfirmationDetailsResponse(worker_name=worker_name, expired=True)

        assignments = self._upcoming_for(token.worker_id)
        log.info("confirmation_details_served", count=len(assignments))
        return ConfirmationDetailsResponse(
            worker_name=worker_name,
            expired=False,
            assignments=[self._to_confirmable(a) for a in assignments],
        )

    def confirm(self, token_id: UUID, assignment_id: UUID, action: str) -> AssignmentResponse:
        """Validate a token and set one assignment's status.

        Args:
            token_id: The UUID from the SMS link.
            assignment_id: Which of the worker's duties is being answered.
            action: Either "confirmed" or "declined".

        Returns:
            Updated AssignmentResponse.

        Raises:
            BadRequestError: If the action is not a valid status.
            NotFoundError: If the token or assignment does not exist, or the assignment belongs
                to a different worker (reported as not-found so a link cannot be used to probe
                for other people's assignment ids).
            GoneError: If the link has expired.
        """
        log = self.logger.bind(method="confirm", assignment_id=str(assignment_id), action=action)

        if action not in (AssignmentStatus.CONFIRMED, AssignmentStatus.DECLINED):
            raise BadRequestError("Action must be 'confirmed' or 'declined'")

        token = self._require_token(token_id)
        if self._is_expired(token.expires_at):
            log.warning("confirmation_token_expired")
            raise GoneError("This link has expired")

        assignment = self.schedule_repo.get_assignment_by_id(assignment_id)
        if not assignment:
            log.warning("confirmation_assignment_not_found")
            raise NotFoundError(f"Assignment {assignment_id} not found")
        # A token speaks for one worker only. Without this, anyone holding a link could answer
        # for somebody else by editing the assignment id.
        if assignment.worker_id != token.worker_id:
            log.warning("confirmation_assignment_worker_mismatch")
            raise NotFoundError(f"Assignment {assignment_id} not found")

        updated = self.schedule_repo.update_assignment_status(assignment_id, AssignmentStatus(action))
        if not updated:
            raise NotFoundError(f"Assignment {assignment_id} not found")

        self.token_repo.mark_used(token_id)
        log.info("assignment_status_updated")
        return updated

    def _require_token(self, token_id: UUID) -> ConfirmationTokenResponse:
        """Fetch a token or raise NotFoundError.

        Args:
            token_id: The UUID from the SMS link.

        Returns:
            The token row.

        Raises:
            NotFoundError: If no such token exists.
        """
        token = self.token_repo.get_by_token(token_id)
        if not token:
            self.logger.warning("confirmation_token_not_found", method="_require_token")
            raise NotFoundError("Token not found")
        return token

    @staticmethod
    def _is_expired(expires_at: datetime) -> bool:
        """Whether a token's expiry has passed, tolerating a naive timestamp from the DB.

        Args:
            expires_at: The token's expiry.

        Returns:
            bool: True if the token is no longer usable.
        """
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)

    def _upcoming_for(self, worker_id: UUID) -> list[AssignmentResponse]:
        """The worker's duties from today onwards, excluding ones they already declined.

        Args:
            worker_id: The worker whose duties to list.

        Returns:
            list[AssignmentResponse]: Soonest first.
        """
        assignments = self.schedule_repo.get_upcoming_assignments_for_worker(worker_id, date.today())
        return [a for a in assignments if a.status != AssignmentStatus.DECLINED]

    @staticmethod
    def _to_confirmable(assignment: AssignmentResponse) -> ConfirmableAssignment:
        """Flatten an assignment and its embedded schedule into a row for the public page.

        Args:
            assignment: An assignment with its schedule embedded.

        Returns:
            ConfirmableAssignment: Display-ready values.
        """
        schedule = assignment.schedules
        return ConfirmableAssignment(
            assignment_id=assignment.id,
            schedule_title=schedule.title if schedule else "Service",
            scheduled_date=schedule.scheduled_date.strftime("%A, %d %B %Y") if schedule else "",
            start_time=schedule.start_time.strftime("%H:%M") if schedule else "",
            end_time=schedule.end_time.strftime("%H:%M") if schedule else "",
            status=assignment.status,
        )
