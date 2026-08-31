import re
from uuid import UUID

from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.repository.department_roles.repository import DepartmentRoleRepository
from app.repository.departments.repository import DepartmentRepository
from app.schemas.department_roles.models import (
    DepartmentRoleCreate,
    DepartmentRoleResponse,
    DepartmentRoleUpdate,
)

logger = get_logger(__name__)

# A department_role is a job ("Head Usher"); a worker_app_role is a permission level (UserRole).
# A job named "HOD" reads as if it grants the HOD permission level, so those names are refused.
# Only canonical spellings are listed — _is_reserved_name normalizes before comparing, so
# "H.O.D.", "hod" and "Asst. HOD" are all caught without being spelled out here.
_RESERVED_ROLE_NAMES = frozenset(
    {
        "admin",
        "administrator",
        "worker",
        "hod",
        "head of department",
        "department head",
        "assistant hod",
        "asst hod",
        "assistant head of department",
    }
)

# Any run of characters that is neither a letter nor a digit, treated as a word separator.
_SEPARATORS = re.compile(r"[^a-z0-9]+")


def _is_reserved_name(name: str) -> bool:
    """Report whether a role name collides with a permission level.

    Matching is exact against `_RESERVED_ROLE_NAMES` after normalizing, deliberately not a
    substring test: seeded roles include "Assistant" and "Head Usher", which a substring rule
    on "assistant" or "head" would wrongly reject.

    Args:
        name: The role name as entered.

    Returns:
        bool: True if the name is a reserved permission-level name.
    """
    # Periods are dropped rather than split on, so the abbreviation "H.O.D." collapses to "hod"
    # instead of "h o d"; every other separator run becomes a space, so "head-of-department" and
    # "assistant_hod" split into words.
    cleaned = _SEPARATORS.sub(" ", name.casefold().replace(".", ""))
    return " ".join(cleaned.split()) in _RESERVED_ROLE_NAMES


class DepartmentRoleService:
    def __init__(self, department_role_repo: DepartmentRoleRepository, department_repo: DepartmentRepository) -> None:
        """Initialize the DepartmentRoleService with required repositories.

        Args:
            department_role_repo: Repository for department role database operations.
            department_repo: Repository for department database operations.
        """
        self.department_role_repo = department_role_repo
        self.department_repo = department_repo
        self.logger = logger.bind(service="DepartmentRoleService")

    def get_role(self, role_id: UUID) -> DepartmentRoleResponse:
        """Retrieve a department role by ID.

        Args:
            role_id: Unique identifier of the role.

        Returns:
            DepartmentRoleResponse: The role data.

        Raises:
            NotFoundError: If the role is not found.
        """
        log = self.logger.bind(method="get_role", role_id=str(role_id))
        role = self.department_role_repo.get_by_id(role_id)
        if not role:
            log.warning("role_not_found")
            raise NotFoundError(f"Department role {role_id} not found")
        return role

    def get_roles_by_department(self, department_id: UUID) -> list[DepartmentRoleResponse]:
        """Retrieve all roles belonging to a specific department.

        Args:
            department_id: Unique identifier of the department.

        Returns:
            list[DepartmentRoleResponse]: List of roles in the department.
        """
        log = self.logger.bind(method="get_roles_by_department", department_id=str(department_id))
        roles = self.department_role_repo.get_by_department(department_id)
        log.info("fetched_roles_by_department", count=len(roles))
        return roles

    def create_role(self, data: DepartmentRoleCreate) -> DepartmentRoleResponse:
        """Create a new department role.

        Validates that the name is not a permission level and that no role with the same name
        exists within the department.

        Args:
            data: Role creation data including name and department.

        Returns:
            DepartmentRoleResponse: The newly created role.

        Raises:
            BadRequestError: If the name collides with a permission level.
            ConflictError: If a role with the same name already exists in the department.
        """
        log = self.logger.bind(method="create_role", data=data.model_dump())
        if _is_reserved_name(data.name):
            log.warning("role_name_reserved")
            raise BadRequestError(f"'{data.name}' is a permission level, not a job. Pick a different role name.")
        existing = self.department_role_repo.get_by_name_in_department(data.department_id, data.name)
        if existing:
            log.warning("role_already_exists")
            raise ConflictError(f"Role '{data.name}' already exists in this department")
        role = self.department_role_repo.create(data.model_dump(mode="json"))
        log = self.logger.bind(method="create_role", role_id=str(role.id), name=data.name)
        log.info("role_created")
        return role

    def update_role(self, role_id: UUID, data: DepartmentRoleUpdate) -> DepartmentRoleResponse:
        """Update a department role's information.

        A rename is held to the same rules as a create: the name must not be a permission level,
        and it must not already be taken in the same department. `DepartmentRoleUpdate` carries no
        department_id, so the department is read off the existing role.

        Args:
            role_id: Unique identifier of the role to update.
            data: Partial role data with fields to update.

        Returns:
            DepartmentRoleResponse: The updated role data.

        Raises:
            NotFoundError: If the role is not found.
            BadRequestError: If the new name collides with a permission level.
            ConflictError: If another role in the department already has the new name.
            AppError: If the update fails.
        """
        log = self.logger.bind(method="update_role", role_id=str(role_id), data=data.model_dump(exclude_none=True))
        role = self.get_role(role_id)
        if data.name is not None:
            if _is_reserved_name(data.name):
                log.warning("role_name_reserved")
                raise BadRequestError(f"'{data.name}' is a permission level, not a job. Pick a different role name.")
            existing = self.department_role_repo.get_by_name_in_department(role.department_id, data.name)
            # Renaming a role to the name it already has is a no-op, not a collision.
            if existing and existing.id != role_id:
                log.warning("role_already_exists")
                raise ConflictError(f"Role '{data.name}' already exists in this department")
        updated = self.department_role_repo.update(role_id, data.model_dump(exclude_none=True))
        if not updated:
            log.error("role_update_failed")
            raise AppError(f"Failed to update department role {role_id}")
        log.info("role_updated")
        return updated

    def delete_role(self, role_id: UUID) -> None:
        """Delete a department role.

        Args:
            role_id: Unique identifier of the role to delete.

        Raises:
            NotFoundError: If the role is not found.
        """
        log = self.logger.bind(method="delete_role", role_id=str(role_id))
        self.get_role(role_id)
        self.department_role_repo.delete(role_id)
        log.info("role_deleted")

    def assign_worker(self, role_id: UUID, worker_id: UUID) -> None:
        """Assign a department role to a worker.

        Validates that the worker is already assigned to the role's parent department
        before allowing the assignment.

        Args:
            role_id: Unique identifier of the role.
            worker_id: Unique identifier of the worker to assign.

        Raises:
            NotFoundError: If the role is not found.
            BadRequestError: If the worker is not assigned to the parent department.
        """
        log = self.logger.bind(method="assign_worker", role_id=str(role_id), worker_id=str(worker_id))

        role = self.get_role(role_id)

        worker_departments = self.department_repo.get_departments_for_worker(worker_id)
        is_in_department = any(d.id == role.department_id for d in worker_departments)
        if not is_in_department:
            log.warning("worker_not_in_parent_department", department_id=str(role.department_id))
            raise BadRequestError(f"Worker {worker_id} is not assigned to department {role.department_id}")

        self.department_role_repo.assign_worker_role(role_id, worker_id)
        log.info("role_assigned_to_worker")

    def unassign_worker(self, role_id: UUID, worker_id: UUID) -> None:
        """Remove a department role from a worker.

        Args:
            role_id: Unique identifier of the role.
            worker_id: Unique identifier of the worker to unassign.

        Raises:
            NotFoundError: If the role is not found.
        """
        log = self.logger.bind(method="unassign_worker", role_id=str(role_id), worker_id=str(worker_id))
        self.get_role(role_id)
        self.department_role_repo.unassign_worker_role(role_id, worker_id)
        log.info("role_unassigned_from_worker")
