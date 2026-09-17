from datetime import date, timedelta
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import AppError, BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.repository.availabilities.repository import AvailabilityRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.availabilities.models import (
    AvailabilityConfig,
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

    # ------------------------------------------------------------------
    # The cut-off
    #
    # Availability is only worth collecting while there is still time to act on it. Every write
    # that names a date goes through _ensure_editable, so a worker cannot answer for a date that
    # has already been rostered — or, at the default notice period of zero, for one already past.
    # ------------------------------------------------------------------

    def editable_from(self, today: date | None = None) -> date:
        """Return the earliest date still open for changes.

        Args:
            today: Override for the current date; defaults to the current date.

        Returns:
            date: The first date a worker may still mark off or clear.
        """
        return (today or date.today()) + timedelta(days=settings.availability_notice_days)

    def get_config(self) -> AvailabilityConfig:
        """Return the cut-off for the signed-in availability editor.

        Returns:
            AvailabilityConfig: The first editable date and the notice period behind it.
        """
        return AvailabilityConfig(
            editable_from=self.editable_from(),
            notice_days=settings.availability_notice_days,
        )

    def _ensure_editable(self, specific_date: date) -> None:
        """Reject a change to a date whose cut-off has passed.

        Args:
            specific_date: The date being marked off or cleared.

        Raises:
            BadRequestError: If that date has closed.
        """
        cutoff = self.editable_from()
        if specific_date >= cutoff:
            return
        self.logger.info(
            "availability_date_closed",
            specific_date=specific_date.isoformat(),
            editable_from=cutoff.isoformat(),
        )
        raise BadRequestError(
            f"Availability for {specific_date:%d %b %Y} has closed. You can still change {cutoff:%d %b %Y} onwards."
        )

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
        # is_available rows are dropped rather than rendered. The page used to ask the opposite
        # question, so old rows saying "I can serve" still exist; under the question it asks now
        # an unmarked date already means that, and showing them would read as a contradiction.
        dates = [
            PublicAvailabilityDate(id=r.id, specific_date=r.specific_date)
            for r in records
            if r.availability_type == AvailabilityType.SPECIFIC_DATE
            and r.specific_date is not None
            and not r.is_available
        ]
        dates.sort(key=lambda d: d.specific_date)
        return PublicAvailabilityResponse(
            worker_name=f"{worker.first_name} {worker.last_name}".strip(),
            dates=dates,
            editable_from=self.editable_from(),
        )

    def mark_unavailable(self, worker_id: UUID, specific_date: date) -> AvailabilityResponse:
        """Record that a worker cannot serve on one date.

        The only write the public page makes. There is no matching "mark available" because the
        rota treats an unrecorded date as available already, so the answer worth collecting is
        the exception.

        Args:
            worker_id: The worker marking themselves off.
            specific_date: The date they cannot serve.

        Returns:
            AvailabilityResponse: The stored record.

        Raises:
            BadRequestError: If that date has passed its cut-off.
        """
        log = self.logger.bind(method="mark_unavailable", worker_id=str(worker_id))
        self._ensure_editable(specific_date)
        record = self.availability_repo.upsert_specific_date_availability(worker_id, specific_date, is_available=False)
        log.info("marked_unavailable", specific_date=specific_date.isoformat())
        return record

    def clear_specific_date(self, worker_id: UUID, specific_date: date) -> None:
        """Remove a worker's mark on one date, putting them back to available.

        Args:
            worker_id: The worker whose mark is being removed.
            specific_date: The date to clear.

        Raises:
            BadRequestError: If that date has passed its cut-off.
        """
        log = self.logger.bind(method="clear_specific_date", worker_id=str(worker_id))
        self._ensure_editable(specific_date)
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
            BadRequestError: If specific_date is required but not provided, or names a date
                whose cut-off has passed.
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
            self._ensure_editable(data.specific_date)
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
            NotFoundError: If the availability record does not exist.
            BadRequestError: If the date it names, before or after the change, has closed.
            AppError: If the update fails.
        """
        log = self.logger.bind(availability_id=str(availability_id), data=data.model_dump(exclude_none=True))
        existing = self.availability_repo.get_by_id(availability_id)
        if not existing:
            log.warning("availability_not_found")
            raise NotFoundError(f"Availability record {availability_id} not found")

        # Both ends of the change are checked: moving a mark off a closed date reopens that date
        # just as surely as editing it in place, and landing on one answers for it after the fact.
        if existing.specific_date is not None:
            self._ensure_editable(existing.specific_date)
        if data.specific_date is not None:
            self._ensure_editable(data.specific_date)

        updated = self.availability_repo.update(availability_id, data.model_dump(exclude_none=True))
        if not updated:
            log.error("availability_update_failed")
            raise AppError(f"Failed to update availability {availability_id}")

        log.info("availability_updated")
        return updated

    def delete_availability(self, availability_id: UUID) -> None:
        """Remove one availability record.

        Args:
            availability_id: The record to remove.

        Raises:
            NotFoundError: If the record does not exist.
            BadRequestError: If it names a date whose cut-off has passed.
        """
        log = self.logger.bind(availability_id=str(availability_id))
        existing = self.availability_repo.get_by_id(availability_id)
        if not existing:
            log.warning("availability_not_found")
            raise NotFoundError(f"Availability record {availability_id} not found")

        if existing.specific_date is not None:
            self._ensure_editable(existing.specific_date)

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
        """Remove every availability record for a worker.

        Deliberately not held to the cut-off. This is a manager resetting a roster, not a worker
        answering for a date, and refusing it part-way would leave a worker whose history spans
        the cut-off permanently un-resettable.

        Args:
            worker_id: The worker whose records are removed.
        """
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
