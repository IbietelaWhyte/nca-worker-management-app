from datetime import date
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.availability_prompts import queries as q
from app.repository.repository import BaseRepository
from app.schemas.availability_prompts.models import AvailabilityPromptResponse

logger = get_logger(__name__)


class AvailabilityPromptRepository(BaseRepository[AvailabilityPromptResponse]):
    def __init__(self, client: Client) -> None:
        super().__init__(client, q.TABLE, AvailabilityPromptResponse)
        self.logger = logger.bind(repository="AvailabilityPromptRepository")

    def get_by_department(self, department_id: UUID) -> list[AvailabilityPromptResponse]:
        """Fetch every prompt configured for a department, newest first.

        Args:
            department_id: The department whose prompts to list.

        Returns:
            list[AvailabilityPromptResponse]: The department's prompts, active or not.
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .order(q.Columns.CREATED_AT, desc=True)
            .execute()
        )
        return [self._to_model(row) for row in response.data or []]

    def get_due(self, today: date) -> list[AvailabilityPromptResponse]:
        """Fetch active prompts that should go out today and have not already.

        One-offs are picked up on or *after* their date, so a prompt whose day passed while the
        app was down still goes out rather than being missed silently. Monthly prompts match on
        day-of-month. Both are guarded by last_sent_on, which is what stops a second run on the
        same day re-sending.

        Args:
            today: The date being swept.

        Returns:
            list[AvailabilityPromptResponse]: Prompts to send now.
        """
        log = self.logger.bind(method="get_due", today=today.isoformat())
        response = self.client.table(q.TABLE).select(q.SELECT_ALL).eq(q.Columns.IS_ACTIVE, True).execute()
        prompts = [self._to_model(row) for row in response.data or []]
        due = [p for p in prompts if self._is_due(p, today)]
        log.debug("fetched_due_prompts", active=len(prompts), due=len(due))
        return due

    @staticmethod
    def _is_due(prompt: AvailabilityPromptResponse, today: date) -> bool:
        """Whether a prompt should be sent today.

        Kept in Python rather than SQL because the monthly rule compares a day-of-month against
        the current date, which is awkward to express as a PostgREST filter and trivial here —
        a church has a handful of prompts, not thousands.

        Args:
            prompt: The prompt to test.
            today: The date being swept.

        Returns:
            bool: True if it is due and has not gone out today.
        """
        if prompt.last_sent_on == today:
            return False
        if prompt.mode == "once":
            return prompt.send_on is not None and prompt.send_on <= today and prompt.last_sent_on is None
        return prompt.repeat_day == today.day

    def mark_sent(self, prompt_id: UUID, sent_on: date) -> bool:
        """Record that a prompt went out, so it is not repeated today.

        A one-off is also deactivated: its work is done, and leaving it active would make it
        due again on every later sweep.

        Args:
            prompt_id: The prompt that was sent.
            sent_on: The date it was sent.

        Returns:
            bool: True if the row was updated.
        """
        log = self.logger.bind(method="mark_sent", prompt_id=str(prompt_id))
        prompt = self.get_by_id(prompt_id)
        payload: dict[str, Any] = {q.Columns.LAST_SENT_ON: sent_on.isoformat()}
        if prompt and prompt.mode == "once":
            payload[q.Columns.IS_ACTIVE] = False
        response = self.client.table(q.TABLE).update(payload).eq(q.Columns.ID, str(prompt_id)).execute()
        updated = len(response.data or []) > 0
        log.info("prompt_marked_sent", updated=updated)
        return updated
