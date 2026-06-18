from typing import Any, cast
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.department_roles import queries as q
from app.repository.repository import BaseRepository
from app.schemas.department_roles.models import DepartmentRoleResponse

logger = get_logger(__name__)


class DepartmentRoleRepository(BaseRepository[DepartmentRoleResponse]):
    def __init__(self, client: Client) -> None:
        """
        Initialize the DepartmentRoleRepository with a Supabase client.

        Args:
            client (Client): The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, DepartmentRoleResponse)
        self.logger = logger.bind(repository="DepartmentRoleRepository")

    def get_by_name_in_department(self, department_id: UUID, name: str) -> DepartmentRoleResponse | None:
        """
        Retrieve a role by name within a specific department.

        Role names are unique per department (not globally), so the lookup is scoped to
        the department to support the same name existing in different departments.

        Args:
            department_id (UUID): The department the role belongs to.
            name (str): The exact role name to retrieve (case-sensitive).

        Returns:
            DepartmentRoleResponse | None: The role if found, None otherwise.
        """
        log = self.logger.bind(method="get_by_name_in_department", department_id=str(department_id), name=name)
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .eq(q.Columns.NAME, name)
            .maybe_single()
            .execute()
        )
        role = self._to_model(response.data) if response else None
        if role:
            log.debug("role_found_by_name", role_id=str(role.id))
        else:
            log.debug("role_not_found_by_name")
        return role

    def get_by_department(self, department_id: UUID) -> list[DepartmentRoleResponse]:
        """
        Retrieve all roles that belong to a specific department.

        Args:
            department_id (UUID): The unique identifier of the department.

        Returns:
            list[DepartmentRoleResponse]: A list of roles for the department. Empty if none.
        """
        log = self.logger.bind(method="get_by_department", department_id=str(department_id))
        response = (
            self.client.table(q.TABLE).select(q.SELECT_ALL).eq(q.Columns.DEPARTMENT_ID, str(department_id)).execute()
        )
        roles = self._to_model_list(response.data) if response.data else []
        log.debug("fetched_roles_by_department", count=len(roles))
        return roles

    def assign_worker_role(self, role_id: UUID, worker_id: UUID) -> dict[str, Any]:
        """
        Assign a department role to a worker.

        This updates the existing worker_departments association to set the
        department_role_id. The worker must already be assigned to the role's
        parent department.

        Args:
            role_id (UUID): The unique identifier of the role.
            worker_id (UUID): The unique identifier of the worker.

        Returns:
            dict[str, Any]: The updated junction record.
        """
        log = self.logger.bind(method="assign_worker_role", role_id=str(role_id), worker_id=str(worker_id))

        # Get the role to find its department_id
        role_response = (
            self.client.table(q.TABLE).select(q.SELECT_ALL).eq(q.Columns.ID, str(role_id)).single().execute()
        )
        role_data = cast(dict[str, Any], role_response.data)
        department_id = role_data["department_id"]

        # Update the existing worker_departments row to set the department_role_id
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .update({q.JunctionColumns.DEPARTMENT_ROLE_ID: str(role_id)})
            .eq(q.JunctionColumns.WORKER_ID, str(worker_id))
            .eq(q.JunctionColumns.DEPARTMENT_ID, str(department_id))
            .execute()
        )
        log.info("role_assigned_to_worker")
        return cast(dict[str, Any], response.data[0])

    def unassign_worker_role(self, role_id: UUID, worker_id: UUID) -> bool:
        """
        Remove a department role from a worker.

        This updates the worker_departments row to set department_role_id to NULL,
        keeping the worker assigned to the parent department but clearing their role.

        Args:
            role_id (UUID): The unique identifier of the role to clear.
            worker_id (UUID): The unique identifier of the worker.

        Returns:
            bool: True if the role was cleared, False if no matching assignment existed.
        """
        log = self.logger.bind(method="unassign_worker_role", role_id=str(role_id), worker_id=str(worker_id))

        # Get the role to find its department_id
        role_response = (
            self.client.table(q.TABLE).select(q.SELECT_ALL).eq(q.Columns.ID, str(role_id)).single().execute()
        )
        role_data = cast(dict[str, Any], role_response.data)
        department_id = role_data["department_id"]

        # Only clear the role if this worker currently holds this specific role
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .update({q.JunctionColumns.DEPARTMENT_ROLE_ID: None})
            .eq(q.JunctionColumns.WORKER_ID, str(worker_id))
            .eq(q.JunctionColumns.DEPARTMENT_ID, str(department_id))
            .eq(q.JunctionColumns.DEPARTMENT_ROLE_ID, str(role_id))
            .execute()
        )
        success = len(response.data) > 0
        if success:
            log.info("role_unassigned_from_worker")
        else:
            log.debug("no_role_assignment_to_remove")
        return success

    def get_role_for_worker_in_department(self, worker_id: UUID, department_id: UUID) -> DepartmentRoleResponse | None:
        """
        Retrieve the worker's standing role within a given department.

        Reads the department_role_id on the worker_departments association and returns the
        embedded role. Used to auto-fill an assignment's role at schedule generation.

        Args:
            worker_id (UUID): The unique identifier of the worker.
            department_id (UUID): The unique identifier of the department.

        Returns:
            DepartmentRoleResponse | None: The worker's role in the department, or None if unset.
        """
        log = self.logger.bind(
            method="get_role_for_worker_in_department", worker_id=str(worker_id), department_id=str(department_id)
        )
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .select(f"{q.TABLE}(*)")
            .eq(q.JunctionColumns.WORKER_ID, str(worker_id))
            .eq(q.JunctionColumns.DEPARTMENT_ID, str(department_id))
            .maybe_single()
            .execute()
        )
        if not response or not response.data:
            log.debug("no_role_for_worker_in_department")
            return None
        data = cast(dict[str, Any], response.data)
        role_data = data.get(q.TABLE)
        role = self._to_model(role_data) if role_data else None
        log.debug("fetched_role_for_worker_in_department", role_id=str(role.id) if role else None)
        return role
