from datetime import date
from uuid import UUID

from app.core.exceptions import AppError, BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.repository.availabilities.repository import AvailabilityRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.availabilities.models import (
    AvailabilityCreate,
    AvailabilityResponse,
    AvailabilityUpdate,
    PublicAvailabilityDate,
    PublicAvailabilityResponse,
)
from app.schemas.models import AvailabilityType, DayOfWeek

logger = get_logger(__name__)


class AvailabilityService:
    def __init__(self, availability_repo: AvailabilityRepository, worker_repo: WorkerRepository) -> None:
        """Initialize the AvailabilityService with required repositories.

        Args:
            availability_repo: Repository for availability database operations.
            worker_repo: Repository for workers, to greet the visitor on the public page.
        """
        self.availability_repo = availability_repo
        self.worker_repo = worker_repo

        # bind logger to service name for easier log filtering
        self.logger = logger.bind(service="AvailabilityService")

    def get_public_availability(self, worker_id: UUID) -> PublicAvailabilityResponse:
        """Build the view shown on the public, token-authenticated availability page.

        Args:
            worker_id: The worker the link identifies.

        Returns:
            PublicAvailabilityResponse: The worker's name and the dates they have set.

        Raises:
            NotFoundError: If the worker no longer exists.
        """
        worker = self.worker_repo.get_by_id(worker_id)
        if not worker:
            self.logger.warning("public_availability_worker_not_found", worker_id=str(worker_id))
            raise NotFoundError(f"Worker {worker_id} not found")

        records = self.availability_repo.get_by_worker(worker_id)
        dates = [
            PublicAvailabilityDate(id=r.id, specific_date=r.specific_date, is_available=r.is_available)
            for r in records
            if r.availability_type == AvailabilityType.SPECIFIC_DATE and r.specific_date is not None
        ]
        dates.sort(key=lambda d: d.specific_date)
        return PublicAvailabilityResponse(
            worker_name=f"{worker.first_name} {worker.last_name}".strip(),
            dates=dates,
        )

    def set_specific_date(self, worker_id: UUID, specific_date: date, is_available: bool) -> AvailabilityResponse:
        """Mark one date available or unavailable for a worker.

        Args:
            worker_id: The worker whose availability is being set.
            specific_date: The date being set.
            is_available: Whether they can serve that day.

        Returns:
            AvailabilityResponse: The stored record.
        """
        log = self.logger.bind(method="set_specific_date", worker_id=str(worker_id))
        record = self.availability_repo.upsert_specific_date_availability(worker_id, specific_date, is_available)
        log.info("specific_date_set", is_available=is_available)
        return record

    def clear_specific_date(self, worker_id: UUID, specific_date: date) -> None:
        """Remove a worker's override for one date, falling back to their recurring pattern.

        Args:
            worker_id: The worker whose override is being removed.
            specific_date: The date to clear.
        """
        log = self.logger.bind(method="clear_specific_date", worker_id=str(worker_id))
        deleted = self.availability_repo.delete_specific_date(worker_id, specific_date)
        log.info("specific_date_cleared", deleted=deleted)

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
        log.info(
            "fetched_worker_availability",
            count=len(records),
        )
        return records

    def get_availability_by_day(self, worker_id: UUID, day_of_week: DayOfWeek) -> AvailabilityResponse | None:
        """Retrieve a worker's availability for a specific day of the week.

        Args:
            worker_id: Unique identifier of the worker.
            day_of_week: Day of the week to query.

        Returns:
            AvailabilityResponse | None: Availability record if found, None otherwise.
        """
        record = self.availability_repo.get_by_worker_and_day(worker_id, day_of_week.to_number())
        log = self.logger.bind(worker_id=str(worker_id), day_of_week=day_of_week)
        log.info(
            "fetched_availability_by_day",
            found=record is not None,
        )
        return record

    def get_available_workers_on_day(self, day_of_week: DayOfWeek) -> list[AvailabilityResponse]:
        """Retrieve all workers available on a specific day of the week.

        Args:
            day_of_week: Day of the week to query.

        Returns:
            list[AvailabilityResponse]: List of availability records for available workers.
        """
        records = self.availability_repo.get_available_workers_on_day(day_of_week.to_number())
        log = self.logger.bind(day_of_week=day_of_week)
        log.info(
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
        log = self.logger.bind(worker_id=str(data.worker_id), data=data.model_dump(exclude={"worker_id"}))
        log.info("setting_worker_availability")  # Log the intent to set availability
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
                raise BadRequestError("specific_date is required for specific date availability")
            record = self.availability_repo.upsert_specific_date_availability(
                worker_id=data.worker_id,
                specific_date=data.specific_date,
                is_available=data.is_available,
            )
            log.info(
                "specific_date_availability_set",
            )
        return record

    def update_availability(self, availability_id: UUID, data: AvailabilityUpdate) -> AvailabilityResponse:
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
            log.warning("availability_not_found")
            raise NotFoundError(f"Availability record {availability_id} not found")

        updated = self.availability_repo.update(availability_id, data.model_dump(exclude_none=True))
        if not updated:
            log.error("availability_update_failed")
            raise AppError(f"Failed to update availability {availability_id}")

        log.info("availability_updated")
        return updated

    def delete_availability(self, availability_id: UUID) -> None:
        log = self.logger.bind(availability_id=str(availability_id))
        existing = self.availability_repo.get_by_id(availability_id)
        if not existing:
            log.warning("availability_not_found")
            raise NotFoundError(f"Availability record {availability_id} not found")

        self.availability_repo.delete(availability_id)
        log.info("availability_deleted")

    def get_owner_id(self, availability_id: UUID) -> UUID:
        """Return the worker an availability record belongs to, for authorization.

        Endpoints that address a record by its own id cannot tell whose it is from the URL, so
        the owner has to be looked up before the caller can be checked against it.

        Args:
            availability_id: The record being acted on.

        Returns:
            UUID: The owning worker.

        Raises:
            NotFoundError: If the record does not exist.
        """
        existing = self.availability_repo.get_by_id(availability_id)
        if not existing:
            self.logger.warning("availability_not_found", availability_id=str(availability_id))
            raise NotFoundError(f"Availability record {availability_id} not found")
        return existing.worker_id

    def clear_worker_availability(self, worker_id: UUID) -> None:
        """Removes all availability records for a worker."""
        self.availability_repo.delete_worker_availability(worker_id)
        log = self.logger.bind(worker_id=str(worker_id))
        log.info("worker_availability_cleared")

    def bulk_set_availability(self, worker_id: UUID, records: list[AvailabilityCreate]) -> list[AvailabilityResponse]:
        """
        Sets availability for multiple days/dates at once.
        Useful for onboarding a new worker or updating a full weekly schedule.
        """
        log = self.logger.bind(worker_id=str(worker_id), count=len(records))
        log.info("bulk_availability_set_started")
        results = [self.set_availability(record) for record in records]
        log.info("bulk_availability_set_completed")
        return results
