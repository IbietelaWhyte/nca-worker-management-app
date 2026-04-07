from datetime import datetime, timezone
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.repository import BaseRepository
from app.schemas.confirmation_tokens.models import ConfirmationTokenResponse

logger = get_logger(__name__)

TABLE = "confirmation_tokens"


class ConfirmationTokenRepository(BaseRepository[ConfirmationTokenResponse]):
    def __init__(self, client: Client) -> None:
        super().__init__(client, TABLE, ConfirmationTokenResponse)
        self.logger = logger.bind(repository="ConfirmationTokenRepository")

    def get_by_token(self, token_id: UUID) -> ConfirmationTokenResponse | None:
        """Fetch a token row by its UUID (the token embedded in the SMS link).

        Args:
            token_id: The UUID from the confirmation link path parameter.

        Returns:
            ConfirmationTokenResponse if found, None otherwise.
        """
        response = self.client.table(TABLE).select("*").eq("id", str(token_id)).maybe_single().execute()
        return self._to_model(response.data) if response else None

    def get_by_assignment(self, assignment_id: UUID) -> ConfirmationTokenResponse | None:
        """Fetch the token row for a given assignment, if one exists.

        Args:
            assignment_id: The schedule assignment UUID.

        Returns:
            ConfirmationTokenResponse if a token exists for this assignment, None otherwise.
        """
        response = self.client.table(TABLE).select("*").eq("assignment_id", str(assignment_id)).maybe_single().execute()
        return self._to_model(response.data) if response else None

    def mark_used(self, token_id: UUID) -> bool:
        """Set used_at to now, marking the token as consumed.

        Args:
            token_id: The UUID of the token to mark as used.

        Returns:
            True if the row was updated, False if not found.
        """
        response = (
            self.client.table(TABLE)
            .update({"used_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", str(token_id))
            .execute()
        )
        return len(response.data) > 0
