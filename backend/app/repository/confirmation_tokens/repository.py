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

    def get_live_for_worker(self, worker_id: UUID, now: datetime) -> ConfirmationTokenResponse | None:
        """Fetch the worker's newest token that has not expired yet, if any.

        A worker may accumulate several token rows over time (an old per-assignment one, a
        superseded one), so this cannot use `maybe_single()` — it takes the newest live row.

        Args:
            worker_id: The worker the token identifies.
            now: Current time; rows expiring at or before this are ignored.

        Returns:
            ConfirmationTokenResponse if the worker has a live token, None otherwise.
        """
        response = (
            self.client.table(TABLE)
            .select("*")
            .eq("worker_id", str(worker_id))
            .gt("expires_at", now.isoformat())
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return self._to_model(rows[0]) if rows else None

    def mark_used(self, token_id: UUID) -> bool:
        """Record that the link was just acted on.

        This does not consume the token — a worker may come back to answer another date.

        Args:
            token_id: The UUID of the token that was used.

        Returns:
            True if the row was updated, False if not found.
        """
        response = (
            self.client.table(TABLE)
            .update({"last_used_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", str(token_id))
            .execute()
        )
        return len(response.data) > 0
