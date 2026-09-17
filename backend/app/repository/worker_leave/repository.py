from datetime import date
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.repository import BaseRepository
from app.repository.worker_leave import queries as q
from app.schemas.worker_leave.models import WorkerLeaveResponse

logger = get_logger(__name__)


class WorkerLeaveRepository(BaseRepository[WorkerLeaveResponse]):
    """Stretches of time a worker is away.

    Every query here is an overlap test rather than an equality test, which in PostgREST terms
    is `start_date <= range_end AND end_date >= range_start` — two half-open comparisons, not a
    range type. Both ends of a leave are inclusive.
    """

    def __init__(self, client: Client) -> None:
        """Initialize the WorkerLeaveRepository with a Supabase client.

        Args:
            client: The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, WorkerLeaveResponse)
        self.logger = logger.bind(repository="WorkerLeaveRepository")

    def get_by_worker(self, worker_id: UUID) -> list[WorkerLeaveResponse]:
        """Fetch every leave recorded for one worker, soonest first.

        Past leave is included: a head looking at somebody's record wants the history, and the
        list is a handful of rows per person.

        Args:
            worker_id: The worker whose leave to list.

        Returns:
            list[WorkerLeaveResponse]: The worker's leave, ascending by start date.
        """
        log = self.logger.bind(method="get_by_worker", worker_id=str(worker_id))
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .order(q.Columns.START_DATE)
            .execute()
        )
        leave = self._to_model_list(response.data or [])
        log.debug("fetched_leave_by_worker", count=len(leave))
        return leave

    def get_overlapping(self, worker_id: UUID, start_date: date, end_date: date) -> list[WorkerLeaveResponse]:
        """Fetch one worker's leave that overlaps a proposed range.

        Args:
            worker_id: The worker being checked.
            start_date: First day of the proposed range, inclusive.
            end_date: Last day of the proposed range, inclusive.

        Returns:
            list[WorkerLeaveResponse]: Any leave that would overlap.
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .lte(q.Columns.START_DATE, end_date.isoformat())
            .gte(q.Columns.END_DATE, start_date.isoformat())
            .execute()
        )
        return self._to_model_list(response.data or [])

    def get_for_workers(self, worker_ids: list[UUID], start_date: date, end_date: date) -> list[WorkerLeaveResponse]:
        """Fetch every leave overlapping a date range for a set of workers, in one round-trip.

        The batched form exists for monthly generation, which asks "who is away" for a month of
        dates at once. Fetching per worker per date would be a query per cell of the month grid.

        Args:
            worker_ids: The workers to check.
            start_date: First day of the range, inclusive.
            end_date: Last day of the range, inclusive.

        Returns:
            list[WorkerLeaveResponse]: Overlapping leave. Empty if `worker_ids` is empty.
        """
        if not worker_ids:
            return []
        log = self.logger.bind(method="get_for_workers", worker_count=len(worker_ids))
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .in_(q.Columns.WORKER_ID, [str(wid) for wid in worker_ids])
            .lte(q.Columns.START_DATE, end_date.isoformat())
            .gte(q.Columns.END_DATE, start_date.isoformat())
            .execute()
        )
        leave = self._to_model_list(response.data or [])
        log.debug("fetched_leave_for_workers", count=len(leave))
        return leave

    def get_active_on(self, day: date) -> list[WorkerLeaveResponse]:
        """Fetch every leave running on one date, across all workers.

        Backs both the availability prompt sweep ("skip whoever is away today") and the roster
        badge, neither of which knows its worker set in advance.

        Args:
            day: The date to test.

        Returns:
            list[WorkerLeaveResponse]: Leave covering that date.
        """
        log = self.logger.bind(method="get_active_on", day=day.isoformat())
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .lte(q.Columns.START_DATE, day.isoformat())
            .gte(q.Columns.END_DATE, day.isoformat())
            .execute()
        )
        leave = self._to_model_list(response.data or [])
        log.debug("fetched_active_leave", count=len(leave))
        return leave
