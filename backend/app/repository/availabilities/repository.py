from datetime import date
from uuid import UUID

from supabase import Client

from app.repository.availabilities import queries as q
from app.repository.repository import BaseRepository
from app.schemas.availabilities.models import AvailabilityResponse


class AvailabilityRepository(BaseRepository[AvailabilityResponse]):
    def __init__(self, client: Client) -> None:
        """
        Initialize the AvailabilityRepository with a Supabase client.

        Args:
            client (Client): The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, AvailabilityResponse)

    def get_by_worker(self, worker_id: UUID) -> list[AvailabilityResponse]:
        """
        Retrieve all availability records for a specific worker.

        Args:
            worker_id (UUID): The unique identifier of the worker.

        Returns:
            list[AvailabilityResponse]: A list of all availability records for the worker,
                                       one for each day they have availability set.
                                       Returns an empty list if no records are found.
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .execute()
        )
        return self._to_model_list(response.data or [])

    def get_by_worker_and_day(
        self, worker_id: UUID, day_of_week: int
    ) -> AvailabilityResponse | None:
        """
        Retrieve a worker's availability for a specific day of the week.

        Args:
            worker_id (UUID): The unique identifier of the worker.
            day_of_week (int): The day of the week to query (0=Monday, 6=Sunday).

        Returns:
            AvailabilityResponse | None: The availability record if found, None if the worker
                                        has no availability set for the specified day.
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .eq(q.Columns.DAY_OF_WEEK, day_of_week)
            .single()
            .execute()
        )
        return self._to_model(response.data) if response.data else None
    
    def get_by_worker_and_type(
        self, worker_id: UUID, availability_type: str, specific_date: date | None = None
    ) -> AvailabilityResponse | None:
        """
        Retrieve a worker's availability for a specific type.
        Args:
            worker_id (UUID): The unique identifier of the worker.
            availability_type (str): The type of availability to query.

        Returns:
            AvailabilityResponse | None: The availability record if found, None if the worker
                                        has no availability set for the specified type.
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .eq(q.Columns.AVAILABILITY_TYPE, availability_type)
            .eq(q.Columns.SPECIFIC_DATE, specific_date.isoformat() if specific_date else None)
            .single()
            .execute()
        )
        return self._to_model(response.data) if response.data else None

    def get_available_workers_on_day(
        self, day_of_week: int
    ) -> list[AvailabilityResponse]:
        """
        Retrieve all workers who are available on a specific day of the week.

        This method returns availability records with worker information embedded,
        filtered to only include workers who have marked themselves as available.

        Args:
            day_of_week (int): The day of the week to query (0=Monday, 6=Sunday).
        Returns:
            list[AvailabilityResponse]: A list of availability records with embedded worker
                                       data for all workers available on the specified day.
                                       Returns an empty list if no workers are available.
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_WITH_WORKERS)
            .eq(q.Columns.DAY_OF_WEEK, day_of_week)
            .eq(q.Columns.IS_AVAILABLE, True)
            .execute()
        )
        return self._to_model_list(response.data or [])

    def upsert_availability(
        self, worker_id: UUID, day_of_week: int, is_available: bool
    ) -> AvailabilityResponse:
        """
        Create or update a worker's availability for a specific day.

        This method uses an upsert operation: if an availability record already exists
        for the given worker and day combination, it updates the availability status;
        otherwise, it creates a new record.

        Args:
            worker_id (UUID): The unique identifier of the worker.
            day_of_week (int): The day of the week to set availability for (0=Monday, 6=Sunday).
            is_available (bool): Whether the worker is available on this day.

        Returns:
            AvailabilityResponse: The created or updated availability record.
        """
        response = (
            self.client.table(q.TABLE)
            .upsert(
                {
                    q.Columns.WORKER_ID: str(worker_id),
                    q.Columns.DAY_OF_WEEK: day_of_week,
                    q.Columns.IS_AVAILABLE: is_available,
                },
                on_conflict=q.UPSERT_CONFLICT_TARGET,
            )
            .execute()
        )
        return self._to_model(response.data[0])
    
    def upsert_specific_date_availability(
        self, worker_id: UUID, specific_date: date, is_available: bool
    ) -> AvailabilityResponse:
        """
        Create or update a worker's availability for a specific date.

        This method uses an upsert operation: if an availability record already exists
        for the given worker and specific date combination, it updates the availability status;
        otherwise, it creates a new record.

        Args:
            worker_id (UUID): The unique identifier of the worker.
            specific_date (date): The specific date to set availability for.
            is_available (bool): Whether the worker is available on this date.

        Returns:
            AvailabilityResponse: The created or updated availability record.
        """
        response = (
            self.client.table(q.TABLE)
            .upsert(
                {
                    q.Columns.WORKER_ID: str(worker_id),
                    q.Columns.SPECIFIC_DATE: specific_date.isoformat(),
                    q.Columns.IS_AVAILABLE: is_available,
                },
                on_conflict=q.UPSERT_CONFLICT_TARGET,
            )
            .execute()
        )
        return self._to_model(response.data[0])

    def delete_worker_availability(self, worker_id: UUID) -> bool:
        """
        Delete all availability records for a specific worker.

        This method removes all availability entries across all days of the week
        for the specified worker. Useful when removing a worker from the system
        or resetting their availability.

        Args:
            worker_id (UUID): The unique identifier of the worker whose availability
                             records should be deleted.

        Returns:
            bool: True if one or more records were deleted, False if no records were found.
        """
        response = (
            self.client.table(q.TABLE)
            .delete()
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .execute()
        )
        return len(response.data) > 0
