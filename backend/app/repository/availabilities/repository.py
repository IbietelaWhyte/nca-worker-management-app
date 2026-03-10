from datetime import date
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.availabilities import queries as q
from app.repository.repository import BaseRepository
from app.schemas.availabilities.models import AvailabilityResponse

logger = get_logger(__name__)


class AvailabilityRepository(BaseRepository[AvailabilityResponse]):
    def __init__(self, client: Client) -> None:
        """
        Initialize the AvailabilityRepository with a Supabase client.

        Args:
            client (Client): The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, AvailabilityResponse)
        self.logger = logger.bind(repository="AvailabilityRepository")

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
        log = self.logger.bind(method="get_by_worker", worker_id=str(worker_id))
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .execute()
        )
        availabilities = self._to_model_list(response.data or [])
        log.debug("fetched_availabilities_by_worker", count=len(availabilities))
        return availabilities

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
        log = self.logger.bind(method="get_by_worker_and_day", 
                               worker_id=str(worker_id), 
                               day_of_week=day_of_week)
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .eq(q.Columns.DAY_OF_WEEK, day_of_week)
            .single()
            .execute()
        )
        availability = self._to_model(response.data) if response.data else None
        if availability:
            log.debug("availability_found")
        else:
            log.debug("availability_not_found")
        return availability
    
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
        log = self.logger.bind(method="get_by_worker_and_type", 
                               worker_id=str(worker_id), 
                               availability_type=availability_type, 
                               specific_date=specific_date.isoformat() if specific_date else None)
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .eq(q.Columns.AVAILABILITY_TYPE, availability_type)
            .eq(q.Columns.SPECIFIC_DATE, specific_date.isoformat() if specific_date else None)
            .single()
            .execute()
        )
        availability = self._to_model(response.data) if response.data else None
        if availability:
            log.debug("availability_found_by_type")
        else:
            log.debug("availability_not_found_by_type")
        return availability

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
        log = self.logger.bind(method="get_available_workers_on_day", day_of_week=day_of_week)
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_WITH_WORKERS)
            .eq(q.Columns.DAY_OF_WEEK, day_of_week)
            .eq(q.Columns.IS_AVAILABLE, True)
            .execute()
        )
        availabilities = self._to_model_list(response.data or [])
        log.debug("fetched_available_workers_on_day", count=len(availabilities))
        return availabilities

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
        log = self.logger.bind(method="upsert_availability", 
                               worker_id=str(worker_id), 
                               day_of_week=day_of_week, 
                               is_available=is_available)
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
        availability = self._to_model(response.data[0])
        log.info("availability_upserted", availability_id=str(availability.id))
        return availability
    
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
        log = self.logger.bind(method="upsert_specific_date_availability", 
                               worker_id=str(worker_id), 
                               specific_date=specific_date.isoformat(), 
                               is_available=is_available)
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
        availability = self._to_model(response.data[0])
        log.info("specific_date_availability_upserted", availability_id=str(availability.id))
        return availability

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
        log = self.logger.bind(method="delete_worker_availability", worker_id=str(worker_id))
        response = (
            self.client.table(q.TABLE)
            .delete()
            .eq(q.Columns.WORKER_ID, str(worker_id))
            .execute()
        )
        deleted = len(response.data) > 0
        if deleted:
            log.info("worker_availability_deleted", count=len(response.data))
        else:
            log.debug("no_availability_to_delete")
        return deleted
