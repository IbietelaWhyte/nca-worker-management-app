from datetime import date
from uuid import UUID

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.repository.departments.repository import DepartmentRepository
from app.repository.monthly_leads.repository import MonthlyLeadRepository
from app.schemas.monthly_leads.models import MonthlyLeadsResponse, first_of_month

logger = get_logger(__name__)


class MonthlyLeadService:
    """The workers a head names to be in charge of a department for a month.

    Children's Church calls them "Teachers of the Month"; what any department calls them is
    `departments.monthly_lead_title`, and a department with no title does not use the feature.
    A lead serves every service that month in that capacity, so they are shown at the top of the
    month's schedules and **left out of that department's rota generation** for the month — see
    `lead_ids_by_month`. It grants no permission. See the migration header for why this is not a
    department role.
    """

    def __init__(self, lead_repo: MonthlyLeadRepository, department_repo: DepartmentRepository) -> None:
        """Initialize the MonthlyLeadService with required repositories.

        Args:
            lead_repo: Repository for monthly leads.
            department_repo: Repository for departments, for the title and the member list.
        """
        self.lead_repo = lead_repo
        self.department_repo = department_repo
        self.logger = logger.bind(service="MonthlyLeadService")

    def get_leads(self, department_id: UUID, month: date) -> MonthlyLeadsResponse:
        """A department's leads for the month a date falls in, with what the department calls them.

        Args:
            department_id: The department.
            month: Any date in the month.

        Returns:
            MonthlyLeadsResponse: The title and leads. Leads are empty when the title is unset,
            so turning the feature off hides any names already recorded.

        Raises:
            NotFoundError: If the department does not exist.
        """
        department = self.department_repo.get_by_id(department_id)
        if not department:
            raise NotFoundError(f"Department {department_id} not found")
        month = first_of_month(month)
        title = department.monthly_lead_title
        leads = self.lead_repo.get_for_month(department_id, month) if title else []
        return MonthlyLeadsResponse(title=title, month=month, leads=leads)

    def lead_ids_by_month(self, department_id: UUID, range_start: date, range_end: date) -> dict[date, set[UUID]]:
        """Who leads the department in each month a date range touches, keyed by the month's 1st.

        What schedule generation reads to leave leads out of their own department's rota. A
        department with no title has no leads here, matching `get_leads`, so turning the
        feature off also stops it removing anybody from the rota.

        Args:
            department_id: The department being scheduled.
            range_start: First date being planned.
            range_end: Last date being planned.

        Returns:
            dict[date, set[UUID]]: Month (its 1st) -> lead worker ids. Months with none are absent.
        """
        department = self.department_repo.get_by_id(department_id)
        if not department or not department.monthly_lead_title:
            return {}
        leads = self.lead_repo.get_in_range(department_id, first_of_month(range_start), first_of_month(range_end))
        by_month: dict[date, set[UUID]] = {}
        for lead in leads:
            by_month.setdefault(lead.month, set()).add(lead.worker_id)
        return by_month

    def set_leads(
        self, department_id: UUID, month: date, worker_ids: list[UUID], actor_id: UUID | None
    ) -> MonthlyLeadsResponse:
        """Replace a department's leads for one month. An empty list clears the month.

        All-or-nothing on membership: every worker must be an active member of the department,
        checked with one read of the member list, and if any is not, nothing is written.

        The new names are inserted **before** the old ones are deleted, so a failure between the
        two statements leaves an extra name on the month rather than an empty one.

        Args:
            department_id: The department.
            month: Any date in the month.
            worker_ids: The complete set of leads for the month. Duplicates are ignored.
            actor_id: The worker making the change, recorded as created_by on new rows.

        Returns:
            MonthlyLeadsResponse: The month as it now stands.

        Raises:
            NotFoundError: If the department does not exist.
            BadRequestError: If the department has no title, too many workers are named, or any
                worker is not an active member of the department.
        """
        month = first_of_month(month)
        log = self.logger.bind(method="set_leads", department_id=str(department_id), month=month.isoformat())

        department = self.department_repo.get_with_workers(department_id)
        if not department:
            raise NotFoundError(f"Department {department_id} not found")
        if not department.monthly_lead_title:
            raise BadRequestError("This department does not have monthly leads turned on")

        wanted = list(dict.fromkeys(worker_ids))
        if len(wanted) > settings.max_monthly_leads:
            raise BadRequestError(f"You can name at most {settings.max_monthly_leads} people for a month")

        active_member_ids = {w.id for w in department.workers if w.is_active}
        outsiders = [w for w in wanted if w not in active_member_ids]
        if outsiders:
            log.warning("monthly_leads_not_active_members", count=len(outsiders))
            raise BadRequestError(
                f"Workers {', '.join(str(w) for w in outsiders)} are not active members of this department"
            )

        current = {lead.worker_id for lead in self.lead_repo.get_for_month(department_id, month)}
        to_add = [w for w in wanted if w not in current]
        to_remove = [w for w in current if w not in set(wanted)]
        self.lead_repo.add(department_id, month, to_add, actor_id)
        self.lead_repo.remove(department_id, month, to_remove)
        log.info("monthly_leads_set", added=len(to_add), removed=len(to_remove))

        return self.get_leads(department_id, month)
