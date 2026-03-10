from uuid import UUID

from app.core.logging import get_logger
from app.repository.availabilities.repository import AvailabilityRepository
from app.schemas.availabilities.models import (
    AvailabilityCreate,
    AvailabilityResponse,
    AvailabilityUpdate,
)
from app.schemas.models import AvailabilityType, DayOfWeek

logger = get_logger(__name__)


class AvailabilityService:
    def __init__(self, availability_repo: AvailabilityRepository) -> None:
        """Initialize the AvailabilityService with required repository.
        
        Args:
            availability_repo: Repository for availability database operations.
        """
        self.availability_repo = availability_repo

        # bind logger to service name for easier log filtering
        self.logger = logger.bind(service="AvailabilityService")

    def get_worker_availability(self, worker_id: UUID) -> list[AvailabilityResponse]:
        """Retrieve all availability records for a specific worker.
        
        Args:
            worker_id: Unique identifier of the worker.
            
        Returns:
            list[AvailabilityResponse]: All availability records for the worker.
        """
        # bind worker_id to logger for all calls in this method
        log = self.logger.bind(worker_id=str(worker_id))
        records = self.availability_repo.get_by_worker(worker_id)
        log.debug(
            "fetched_worker_availability",
            count=len(records),
        )
        return records

    def get_availability_by_day(
        self, worker_id: UUID, day_of_week: DayOfWeek
    ) -> AvailabilityResponse | None:
        """Retrieve a worker's availability for a specific day of the week.
        
        Args:
            worker_id: Unique identifier of the worker.
            day_of_week: Day of the week to query.
            
        Returns:
            AvailabilityResponse | None: Availability record if found, None otherwise.
        """
        record = self.availability_repo.get_by_worker_and_day(worker_id, day_of_week.to_number())
        log = self.logger.bind(worker_id=str(worker_id), day_of_week=day_of_week)
        log.debug(
            "fetched_availability_by_day",
            found=record is not None,
        )
        return record

    def get_available_workers_on_day(
        self, day_of_week: DayOfWeek
    ) -> list[AvailabilityResponse]:
        """Retrieve all workers available on a specific day of the week.
        
        Args:
            day_of_week: Day of the week to query.
            
        Returns:
            list[AvailabilityResponse]: List of availability records for available workers.
        """
        records = self.availability_repo.get_available_workers_on_day(day_of_week.to_number())
        log = self.logger.bind(day_of_week=day_of_week)
        log.debug(
            "fetched_available_workers_on_day",
            count=len(records),
        )
        return records

    def set_availability(self, data: AvailabilityCreate) -> AvailabilityResponse:
        """Create or update a worker's availability record.
        
        Uses upsert so callers don't need to know if a record already exists.
        Handles both recurring weekly availability and specific date availability.
        
        Args:
            data: Availability creation data with type, worker, and availability status.
            
        Returns:
            AvailabilityResponse: The created or updated availability record.
            
        Raises:
            ValueError: If specific_date is required but not provided.
        """
        log = self.logger.bind(worker_id=str(
            data.worker_id), data=data.model_dump(exclude={"worker_id"}))
        if data.availability_type == AvailabilityType.RECURRING and data.day_of_week is not None:
            record = self.availability_repo.upsert_availability(
                worker_id=data.worker_id,
                day_of_week=data.day_of_week.to_number(),
                is_available=data.is_available,
            )
            
            log.info(
                "recurring_availability_set",
            )
        else:
            if data.specific_date is None:
                raise ValueError("specific_date is required for specific date availability")
            record = self.availability_repo.upsert_specific_date_availability(
                worker_id=data.worker_id,
                specific_date=data.specific_date, 
                is_available=data.is_available,
            )
            log.info(
                "specific_date_availability_set",
            )
        return record

    def update_availability(
        self, availability_id: UUID, data: AvailabilityUpdate
    ) -> AvailabilityResponse:
        """Update an existing availability record.
        
        Args:
            availability_id: Unique identifier of the availability record.
            data: Partial availability data with fields to update.
            
        Returns:
            AvailabilityResponse: The updated availability record.
            
        Raises:
            ValueError: If availability record not found or update fails.
        """
        log = self.logger.bind(availability_id=str(availability_id), data=data.model_dump(exclude_none=True))
        existing = self.availability_repo.get_by_id(availability_id)
        if not existing:
            log.warning(
                "availability_not_found"
            )
            raise ValueError(
                f"Availability record {availability_id} not found")

        updated = self.availability_repo.update(
            availability_id, data.model_dump(exclude_none=True)
        )
        if not updated:
            log.error(
                "availability_update_failed"
            )
            raise ValueError(
                f"Failed to update availability {availability_id}")

        log.info(
            "availability_updated"
        )
        return updated

    def delete_availability(self, availability_id: UUID) -> None:
        log = self.logger.bind(availability_id=str(availability_id))
        existing = self.availability_repo.get_by_id(availability_id)
        if not existing:
            log.warning(
                "availability_not_found"
            )
            raise ValueError(
                f"Availability record {availability_id} not found")

        self.availability_repo.delete(availability_id)
        log.info("availability_deleted")

    def clear_worker_availability(self, worker_id: UUID) -> None:
        """Removes all availability records for a worker."""
        self.availability_repo.delete_worker_availability(worker_id)
        log = self.logger.bind(worker_id=str(worker_id))
        log.info("worker_availability_cleared")

    def bulk_set_availability(
        self, worker_id: UUID, records: list[AvailabilityCreate]
    ) -> list[AvailabilityResponse]:
        """
        Sets availability for multiple days/dates at once.
        Useful for onboarding a new worker or updating a full weekly schedule.
        """
        log = self.logger.bind(worker_id=str(worker_id), count=len(records))
        log.info("bulk_availability_set_started")
        results = [self.set_availability(record) for record in records]
        log.info(
            "bulk_availability_set_completed"
        )
        return results
