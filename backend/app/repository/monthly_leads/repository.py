from datetime import date
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.monthly_leads import queries as q
from app.repository.repository import BaseRepository
from app.schemas.monthly_leads.models import MonthlyLeadResponse

logger = get_logger(__name__)


class MonthlyLeadRepository(BaseRepository[MonthlyLeadResponse]):
    """The workers a head names to be in charge of a department for a month.

    `month` is always the first of the month; callers normalise before they get here.
    """

    def __init__(self, client: Client) -> None:
        """Initialize the MonthlyLeadRepository with a Supabase client.

        Args:
            client: The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, MonthlyLeadResponse)
        self.logger = logger.bind(repository="MonthlyLeadRepository")

    def get_for_month(self, department_id: UUID, month: date) -> list[MonthlyLeadResponse]:
        """Fetch a department's leads for one month, with each worker embedded.

        Args:
            department_id: The department.
            month: The first of the month.

        Returns:
            list[MonthlyLeadResponse]: The leads, in the order they were named.
        """
        log = self.logger.bind(method="get_for_month", department_id=str(department_id), month=month.isoformat())
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_WITH_WORKER)
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .eq(q.Columns.MONTH, month.isoformat())
            .order(q.Columns.CREATED_AT)
            .execute()
        )
        rows: list[dict[str, Any]] = [
            {**row, "worker": row.get("workers")} for row in (response.data or []) if isinstance(row, dict)
        ]
        leads = self._to_model_list(rows)
        log.debug("fetched_monthly_leads", count=len(leads))
        return leads

    def get_in_range(self, department_id: UUID, first_month: date, last_month: date) -> list[MonthlyLeadResponse]:
        """Fetch a department's leads for every month in a span, without the worker embed.

        For schedule generation, which needs only who to leave out of which month.

        Args:
            department_id: The department.
            first_month: The first of the earliest month, inclusive.
            last_month: The first of the latest month, inclusive.

        Returns:
            list[MonthlyLeadResponse]: The leads across the span.
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .gte(q.Columns.MONTH, first_month.isoformat())
            .lte(q.Columns.MONTH, last_month.isoformat())
            .execute()
        )
        return self._to_model_list(response.data or [])

    def add(self, department_id: UUID, month: date, worker_ids: list[UUID], created_by: UUID | None) -> None:
        """Name several workers as leads for a month in one insert.

        Args:
            department_id: The department.
            month: The first of the month.
            worker_ids: The workers to add.
            created_by: The worker naming them, or None for an admin with no worker record.
        """
        if not worker_ids:
            return
        log = self.logger.bind(method="add", department_id=str(department_id), count=len(worker_ids))
        self.client.table(q.TABLE).insert(
            [
                {
                    q.Columns.DEPARTMENT_ID: str(department_id),
                    q.Columns.WORKER_ID: str(worker_id),
                    q.Columns.MONTH: month.isoformat(),
                    q.Columns.CREATED_BY: str(created_by) if created_by else None,
                }
                for worker_id in worker_ids
            ]
        ).execute()
        log.info("monthly_leads_added")

    def remove(self, department_id: UUID, month: date, worker_ids: list[UUID]) -> None:
        """Stop several workers being leads for a month in one delete.

        Args:
            department_id: The department.
            month: The first of the month.
            worker_ids: The workers to remove.
        """
        if not worker_ids:
            return
        log = self.logger.bind(method="remove", department_id=str(department_id), count=len(worker_ids))
        (
            self.client.table(q.TABLE)
            .delete()
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .eq(q.Columns.MONTH, month.isoformat())
            .in_(q.Columns.WORKER_ID, [str(worker_id) for worker_id in worker_ids])
            .execute()
        )
        log.info("monthly_leads_removed")
