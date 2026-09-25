from datetime import date
from uuid import UUID

from postgrest.exceptions import APIError

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.repository.special_services import queries as q
from app.repository.special_services.repository import SpecialServiceRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.special_services.models import (
    SpecialDate,
    SpecialService,
    SpecialServiceCreate,
    SpecialServiceUpdate,
)
from app.service.special_services.rules import resolve_special_dates

logger = get_logger(__name__)

# Postgres unique_violation — raised by the partial unique indexes when the same rule or the
# same one-off date is added twice.
UNIQUE_VIOLATION = "23505"


class SpecialServiceService:
    """Church-wide configuration for the dates that are bigger than an ordinary service.

    Writes are admin-only, enforced by `AdminUser` on the router and by RLS in Postgres. That is
    not tidiness: these rules are not scoped to a department, so every rota on a matching date is
    planned as special in every team. A head moving "first Sunday" to "second Sunday" would
    change which dates every other department rotates specially.
    """

    def __init__(self, special_service_repo: SpecialServiceRepository, worker_repo: WorkerRepository) -> None:
        """Initialize the service.

        Args:
            special_service_repo: Repository for special service rows.
            worker_repo: Repository for workers, to resolve the creating admin's worker record.
        """
        self.special_service_repo = special_service_repo
        self.worker_repo = worker_repo
        self.logger = logger.bind(service="SpecialServiceService")

    def list_special_services(self, active_only: bool = False) -> list[SpecialService]:
        """Every configured rule and named date.

        Args:
            active_only: Exclude deactivated entries.

        Returns:
            list[SpecialService]: The configured entries.
        """
        return self.special_service_repo.list_all(active_only=active_only)

    def get_special_dates(self, start: date, end: date) -> dict[date, str]:
        """Resolve every special date in a window to its name.

        Two queries' worth of rows against a table measured in tens, then pure arithmetic. The
        planner takes this **as an argument** rather than calling it itself, so a month preview
        resolves the window once and reuses it for both the plan and the badges on screen.

        Args:
            start: First date of the window, inclusive.
            end: Last date of the window, inclusive.

        Returns:
            dict[date, str]: Special dates mapped to what to call them.
        """
        rules, one_offs = self.special_service_repo.get_active_by_kind()
        return resolve_special_dates(
            rules=[
                (rule.day_of_week.to_number(), rule.week_of_month, rule.name)
                for rule in rules
                if rule.day_of_week is not None and rule.week_of_month is not None
            ],
            one_offs=[(one_off.service_date, one_off.name) for one_off in one_offs if one_off.service_date],
            start=start,
            end=end,
        )

    def list_special_dates(self, start: date, end: date) -> list[SpecialDate]:
        """The same resolution as a sorted list, for the API.

        Args:
            start: First date of the window, inclusive.
            end: Last date of the window, inclusive.

        Returns:
            list[SpecialDate]: Occurrences in date order.
        """
        resolved = self.get_special_dates(start, end)
        return [SpecialDate(service_date=d, name=resolved[d]) for d in sorted(resolved)]

    def create_special_service(self, data: SpecialServiceCreate, created_by: str) -> SpecialService:
        """Add a recurring rule or a named one-off date.

        Args:
            data: The rule or date to add.
            created_by: Email of the signed-in admin, recorded as the author.

        Returns:
            SpecialService: The newly created entry.

        Raises:
            NotFoundError: If the author's worker record cannot be found.
            ConflictError: If the same rule or the same date already exists.
        """
        log = self.logger.bind(method="create_special_service", kind=data.kind.value)

        author = self.worker_repo.get_by_email(created_by)
        if not author:
            raise NotFoundError(f"User with email {created_by} not found")

        try:
            service = self.special_service_repo.create(
                {
                    q.Columns.NAME: data.name.strip(),
                    q.Columns.KIND: data.kind.value,
                    # The API speaks day names; the column holds 0-6 with Sunday as 0.
                    q.Columns.DAY_OF_WEEK: data.day_of_week.to_number() if data.day_of_week else None,
                    q.Columns.WEEK_OF_MONTH: data.week_of_month,
                    q.Columns.SERVICE_DATE: data.service_date.isoformat() if data.service_date else None,
                    q.Columns.CREATED_BY: str(author.id),
                }
            )
        except APIError as error:
            # The partial unique indexes: one rule per (weekday, week), one entry per date.
            if error.code == UNIQUE_VIOLATION:
                raise ConflictError("That special service is already set up.") from error
            raise

        log.info("special_service_created", special_service_id=str(service.id))
        return service

    def update_special_service(self, special_service_id: UUID, data: SpecialServiceUpdate) -> SpecialService:
        """Rename a special service or turn it on and off.

        Deliberately cannot move a rule's day or week. A rota generated last month was planned
        against the date that rule resolved to then, and the schedule's own
        `special_service_name` snapshot is what the fairness tally counts — editing the rule in
        place would leave the two disagreeing. Deactivate and add the replacement instead.

        Args:
            special_service_id: The entry to update.
            data: The fields to change.

        Returns:
            SpecialService: The updated entry.

        Raises:
            NotFoundError: If no entry has that id.
        """
        log = self.logger.bind(method="update_special_service", special_service_id=str(special_service_id))

        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] is not None:
            changes[q.Columns.NAME] = changes["name"].strip()
        if not changes:
            existing = self.special_service_repo.get_by_id(special_service_id)
            if not existing:
                raise NotFoundError(f"Special service {special_service_id} not found")
            return existing

        updated = self.special_service_repo.update(special_service_id, changes)
        if not updated:
            log.warning("special_service_not_found")
            raise NotFoundError(f"Special service {special_service_id} not found")
        log.info("special_service_updated")
        return updated

    def delete_special_service(self, special_service_id: UUID) -> None:
        """Remove a special service.

        Rotas already generated keep their `special_service_name` snapshot: the foreign key is
        ON DELETE SET NULL, so deleting a rule does not retroactively make past dates ordinary
        or zero anybody's tally.

        Args:
            special_service_id: The entry to delete.

        Raises:
            NotFoundError: If no entry has that id.
        """
        log = self.logger.bind(method="delete_special_service", special_service_id=str(special_service_id))
        if not self.special_service_repo.delete(special_service_id):
            log.warning("special_service_not_found")
            raise NotFoundError(f"Special service {special_service_id} not found")
        log.info("special_service_deleted")
