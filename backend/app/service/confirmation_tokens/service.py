from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import GoneError, NotFoundError
from app.core.logging import get_logger
from app.repository.confirmation_tokens.repository import ConfirmationTokenRepository
from app.schemas.confirmation_tokens.models import (
    ConfirmationTokenCreate,
    ConfirmationTokenResponse,
)

logger = get_logger(__name__)


class ConfirmationTokenService:
    """Issues and resolves the public link that identifies a worker with no login account.

    The name is historical. Nothing is confirmed any more — the token is the credential behind
    /availability/{token}, where a worker marks the dates they cannot serve. It identifies a
    *worker*, not a single duty, and it stays usable until it expires, so a link sent in one
    month still works when the next prompt goes out.
    """

    def __init__(self, token_repo: ConfirmationTokenRepository) -> None:
        """Initialize the ConfirmationTokenService with required dependencies.

        Args:
            token_repo: Repository for confirmation token database operations.
        """
        self.token_repo = token_repo
        self.logger = logger.bind(service="ConfirmationTokenService")

    def get_or_create_token_id(self, worker_id: UUID) -> UUID:
        """Return the worker's live token, minting one only if they have none.

        Reuse is deliberate rather than an optimisation: a worker may be prompted for their
        availability in one month and again in the next, and the older link has to keep working
        because most people never delete a text.

        Args:
            worker_id: The UUID of the worker the token identifies.

        Returns:
            UUID: The token that identifies this worker.
        """
        log = self.logger.bind(method="get_or_create_token_id", worker_id=str(worker_id))

        now = datetime.now(timezone.utc)
        existing = self.token_repo.get_live_for_worker(worker_id, now)
        if existing:
            log.info("confirmation_token_reused")
            return existing.id

        expires_at = now + timedelta(days=settings.confirmation_token_ttl_days)
        token_data = ConfirmationTokenCreate(worker_id=worker_id, expires_at=expires_at)
        # Log the worker linkage only — never the token id itself (it's the link credential).
        log.info("creating_confirmation_token")
        token = self.token_repo.create(token_data.model_dump(mode="json"))
        log.info("confirmation_token_created", expires_at=expires_at.isoformat())
        return token.id

    def resolve_worker_id(self, token_id: UUID) -> UUID:
        """Identify the worker a public link belongs to.

        The token is the only credential that page has, so this is what stands in for
        authentication on it.

        Args:
            token_id: The UUID from the link.

        Returns:
            UUID: The worker the token identifies.

        Raises:
            NotFoundError: If no such token exists.
            GoneError: If the link has expired.
        """
        token = self._require_token(token_id)
        if self._is_expired(token.expires_at):
            self.logger.warning("confirmation_token_expired", method="resolve_worker_id")
            raise GoneError("This link has expired")
        return token.worker_id

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
