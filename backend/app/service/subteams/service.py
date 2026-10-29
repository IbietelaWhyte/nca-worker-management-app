from uuid import UUID

from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.repository.department_roles.repository import DepartmentRoleRepository
from app.repository.departments.repository import DepartmentRepository
from app.repository.subteams.repository import SubteamRepository
from app.schemas.departments.models import DepartmentResponse
from app.schemas.subteams.models import (
    RoleRequirement,
    RoleRequirementsSet,
    SubteamCreate,
    SubteamResponse,
    SubteamUpdate,
    SubteamWithWorkersResponse,
)

logger = get_logger(__name__)


def staffing_band(subteam: SubteamResponse | None, department: DepartmentResponse) -> tuple[int, int]:
    """The (minimum, maximum) a group has to staff to.

    A subteam overrides the whole band or inherits the whole band — `chk_subteam_inherit_both`
    makes a half-set override unrepresentable — so one `is None` test settles both bounds.

    Tested with `is None` rather than the old `subteam.workers_per_slot or ...`: a minimum of 0
    ("use whoever is free, never flag it short") is now a legitimate setting, and `or` would
    silently discard it in favour of the department's. The old expression was only ever safe
    because a CHECK forbade 0, and that guard does not survive the split.

    Args:
        subteam: The group's subteam, or None for the department-only roster.
        department: The department, which supplies the band when the subteam inherits.

    Returns:
        tuple[int, int]: Minimum and maximum workers for this group on one date.
    """
    if subteam is not None and subteam.min_workers_per_slot is not None:
        # max is guaranteed non-None alongside min by chk_subteam_inherit_both; the `or` is a
        # belt-and-braces default for a row that predates the constraint.
        return subteam.min_workers_per_slot, subteam.max_workers_per_slot or subteam.min_workers_per_slot
    return department.min_workers_per_slot, department.max_workers_per_slot


class SubteamService:
    def __init__(
        self,
        subteam_repo: SubteamRepository,
        department_repo: DepartmentRepository,
        department_role_repo: DepartmentRoleRepository,
    ) -> None:
        """Initialize the SubteamService with required repositories.

        Args:
            subteam_repo: Repository for subteam database operations.
            department_repo: Repository for department database operations.
            department_role_repo: Repository for department roles, to check role requirements.
        """
        self.subteam_repo = subteam_repo
        self.department_repo = department_repo
        self.department_role_repo = department_role_repo
        self.logger = logger.bind(service="SubteamService")

    def get_subteam(self, subteam_id: UUID) -> SubteamResponse:
        """Retrieve a subteam by ID.

        Args:
            subteam_id: Unique identifier of the subteam.

        Returns:
            SubteamResponse: The subteam data.

        Raises:
            ValueError: If subteam not found.
        """
        log = self.logger.bind(method="get_subteam", subteam_id=str(subteam_id))
        subteam = self.subteam_repo.get_by_id(subteam_id)
        if not subteam:
            log.warning("subteam_not_found")
            raise NotFoundError(f"subteam {subteam_id} not found")
        return subteam

    def get_all_subteams(self) -> list[SubteamResponse]:
        """Retrieve all subteams.

        Returns:
            list[SubteamResponse]: List of all subteams in the system.
        """
        log = self.logger.bind(method="get_all_subteams")
        subteams = self.subteam_repo.get_all()
        log.info("fetched_all_subteams", count=len(subteams))
        return subteams

    def get_subteam_with_workers(self, subteam_id: UUID) -> list[SubteamWithWorkersResponse]:
        """Retrieve a subteam with all assigned workers embedded.

        Args:
            subteam_id: Unique identifier of the subteam.

        Returns:
            list[SubteamWithWorkersResponse]: Subteam with worker details (can be empty list).

        Raises:
            ValueError: If subteam not found.
        """
        log = self.logger.bind(method="get_subteam_with_workers", subteam_id=str(subteam_id))

        # First validate that the subteam exists
        subteam_exists = self.subteam_repo.get_by_id(subteam_id)
        if not subteam_exists:
            log.warning("subteam_not_found")
            raise NotFoundError(f"subteam {subteam_id} not found")

        # Then get workers (can be empty list if no workers assigned)
        workers = self.subteam_repo.get_with_workers(subteam_id)
        return workers

    def create_subteam(self, data: SubteamCreate) -> SubteamResponse:
        """Create a new subteam.

        Validates that no subteam with the same name exists.

        Args:
            data: Subteam creation data including name and department.

        Returns:
            SubteamResponse: The newly created subteam.

        Raises:
            ValueError: If subteam with the same name already exists.
        """
        log = self.logger.bind(method="create_subteam", data=data.model_dump())
        existing = self.subteam_repo.get_by_name(data.name)
        if existing:
            log.warning("subteam_already_exists")
            raise ConflictError(f"subteam '{data.name}' already exists")
        subteam = self.subteam_repo.create(data.model_dump(mode="json"))
        log = self.logger.bind(method="create_subteam", subteam_id=str(subteam.id), name=data.name)
        log.info("subteam_created")
        return subteam

    def update_subteam(self, subteam_id: UUID, data: SubteamUpdate) -> SubteamResponse:
        """Update a subteam's information.

        Args:
            subteam_id: Unique identifier of the subteam to update.
            data: Partial subteam data with fields to update.

        Returns:
            SubteamResponse: The updated subteam data.

        Raises:
            ValueError: If subteam not found or update fails.
        """
        log = self.logger.bind(
            method="update_subteam", subteam_id=str(subteam_id), data=data.model_dump(exclude_none=True)
        )
        self.get_subteam(subteam_id)
        updated = self.subteam_repo.update(subteam_id, data.model_dump(exclude_none=True))
        if not updated:
            log.error("subteam_update_failed")
            raise AppError(f"Failed to update subteam {subteam_id}")
        log.info("subteam_updated")
        return updated

    def delete_subteam(self, subteam_id: UUID) -> None:
        """Delete a subteam.

        Args:
            subteam_id: Unique identifier of the subteam to delete.

        Raises:
            ValueError: If subteam not found.
        """
        log = self.logger.bind(method="delete_subteam", subteam_id=str(subteam_id))
        self.get_subteam(subteam_id)
        self.subteam_repo.delete(subteam_id)
        log.info("subteam_deleted")

    def assign_workers(self, subteam_id: UUID, worker_ids: list[UUID]) -> None:
        """Assign several workers to a subteam at once.

        All-or-nothing: every worker must already be a member of the subteam's parent department,
        and if any is not, nothing is written. Somebody already in another subteam of the same
        department moves across, since a worker belongs to one subteam per department.

        Args:
            subteam_id: Unique identifier of the subteam.
            worker_ids: Unique identifiers of the workers to assign. Duplicates are ignored.

        Raises:
            NotFoundError: If the subteam does not exist.
            BadRequestError: If any worker is not assigned to the parent department.
        """
        log = self.logger.bind(method="assign_workers", subteam_id=str(subteam_id), count=len(worker_ids))

        subteam = self.get_subteam(subteam_id)
        unique_ids = list(dict.fromkeys(worker_ids))

        # One read of the department's members rather than one membership lookup per worker.
        department = self.department_repo.get_with_workers(subteam.department_id)
        member_ids = {w.id for w in department.workers} if department else set()
        outsiders = [worker_id for worker_id in unique_ids if worker_id not in member_ids]
        if outsiders:
            log.warning("workers_not_in_parent_department", department_id=str(subteam.department_id))
            raise BadRequestError(
                f"Workers {', '.join(str(w) for w in outsiders)} are not assigned to department {subteam.department_id}"
            )

        self.subteam_repo.assign_workers(subteam.department_id, subteam_id, unique_ids)
        log.info("workers_assigned_to_subteam", assigned=len(unique_ids))

    def unassign_worker(self, subteam_id: UUID, worker_id: UUID) -> None:
        """Remove a worker's assignment from a subteam.

        Args:
            subteam_id: Unique identifier of the subteam.
            worker_id: Unique identifier of the worker to unassign.

        Raises:
            ValueError: If subteam not found.
        """
        log = self.logger.bind(method="unassign_worker", subteam_id=str(subteam_id), worker_id=str(worker_id))
        self.get_subteam(subteam_id)
        self.subteam_repo.unassign_worker(subteam_id, worker_id)
        log.info(
            "worker_unassigned_from_subteam",
        )

    def set_hod(self, subteam_id: UUID, worker_id: UUID) -> SubteamResponse:
        """Set the Head of Department (HOD) for a subteam.

        Args:
            subteam_id: Unique identifier of the subteam.
            worker_id: Unique identifier of the worker to set as HOD.

        Returns:
            SubteamResponse: The updated subteam with new HOD.

        Raises:
            ValueError: If subteam not found or HOD assignment fails.
        """
        log = self.logger.bind(method="set_hod", subteam_id=str(subteam_id), worker_id=str(worker_id))
        self.get_subteam(subteam_id)
        updated = self.subteam_repo.update(subteam_id, {"hod_id": str(worker_id)})
        if not updated:
            log.error("set_hod_failed")
            raise AppError(f"Failed to set HOD for subteam {subteam_id}")
        log.info("hod_assigned")
        return updated

    def get_subteams_by_department(self, department_id: UUID) -> list[SubteamResponse]:
        """Retrieve all subteams belonging to a specific department.

        Args:
            department_id: Unique identifier of the department.

        Returns:
            list[SubteamResponse]: List of subteams in the department.
        """
        log = self.logger.bind(method="get_subteams_by_department", department_id=str(department_id))
        subteams = self.subteam_repo.get_by_department(department_id)
        log.info("fetched_subteams_by_department", count=len(subteams))
        return subteams

    def set_role_requirements(self, subteam_id: UUID, data: RoleRequirementsSet) -> list[RoleRequirement]:
        """Replace the minimum count of each department role on this subteam's rotas.

        Two rules no constraint can hold, because each spans tables: every role must belong to the
        subteam's own department, and the minimums together may not exceed the subteam's maximum —
        the planner never passes the maximum, so a larger total could never be met and would mark
        every date short.

        Args:
            subteam_id: The subteam whose requirements to set.
            data: The complete new set. An empty list clears them.

        Returns:
            list[RoleRequirement]: The requirements now stored.

        Raises:
            NotFoundError: If the subteam or its department does not exist.
            BadRequestError: If a role is not the department's, or the total exceeds the maximum.
        """
        log = self.logger.bind(method="set_role_requirements", subteam_id=str(subteam_id))
        subteam = self.get_subteam(subteam_id)
        department = self.department_repo.get_by_id(subteam.department_id)
        if not department:
            raise NotFoundError(f"Department {subteam.department_id} not found")

        roles = {role.id: role.name for role in self.department_role_repo.get_by_department(department.id)}
        strangers = [r.department_role_id for r in data.requirements if r.department_role_id not in roles]
        if strangers:
            log.warning("role_requirement_outside_department", roles=[str(r) for r in strangers])
            raise BadRequestError(f"{len(strangers)} of these roles do not belong to {department.name}")

        _, maximum = staffing_band(subteam, department)
        total = sum(r.min_count for r in data.requirements)
        if total > maximum:
            parts = " + ".join(f"{r.min_count} {roles[r.department_role_id]}" for r in data.requirements)
            raise BadRequestError(
                f"{parts} is {total}, but {subteam.name} takes at most {maximum} on a rota. "
                "Lower a count, or raise the most workers."
            )

        self.subteam_repo.replace_role_requirements(subteam_id, data.requirements)
        log.info("role_requirements_set", count=len(data.requirements), total=total)
        return data.requirements
