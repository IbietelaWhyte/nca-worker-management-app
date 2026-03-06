from typing import Any, cast
from uuid import UUID

from supabase import Client

from app.repository.departments import queries as q
from app.repository.repository import BaseRepository
from app.schemas.departments.models import DepartmentResponse, DepartmentWithWorkersResponse


class DepartmentRepository(BaseRepository[DepartmentResponse]):
    def __init__(self, client: Client) -> None:
        """
        Initialize the DepartmentRepository with a Supabase client.

        Args:
            client (Client): The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, DepartmentResponse)

    def get_by_name(self, name: str) -> DepartmentResponse | None:
        """
        Retrieve a department by its name.

        This method performs a single-record query to find a department with an exact
        name match. The query is case-sensitive.

        Args:
            name (str): The exact name of the department to retrieve.

        Returns:
            DepartmentResponse | None: The department if found, None if no department
                                      exists with the given name.
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.NAME, name)
            .single()
            .execute()
        )
        return self._to_model(response.data) if response.data else None

    def get_with_workers(self, department_id: UUID) -> list[DepartmentWithWorkersResponse]:
        """
        Retrieve a department with all its assigned workers embedded.

        This method fetches department details along with complete information about
        all workers assigned to the department through a join operation.

        Args:
            department_id (UUID): The unique identifier of the department.

        Returns:
            list[DepartmentWithWorkersResponse]: The department with embedded worker data if found,
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_WITH_WORKERS)
            .eq(q.Columns.ID, str(department_id))
            .single()
            .execute()
        )
        return self._to_model_list([response.data], DepartmentWithWorkersResponse) if response.data else []

    def get_departments_for_worker(self, worker_id: UUID) -> list[DepartmentResponse]:
        """
        Retrieve all departments that a specific worker is assigned to.

        This method queries the junction table to find all department associations for
        a worker, handling the many-to-many relationship between workers and departments.

        Args:
            worker_id (UUID): The unique identifier of the worker.

        Returns:
            list[DepartmentResponse]: A list of all departments the worker is assigned to.
                                     Returns an empty list if the worker is not assigned
                                     to any departments.
        """
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .select("departments(*)")
            .eq(q.JunctionColumns.WORKER_ID, str(worker_id))
            .execute()
        )
        rows = [
            row["departments"]
            for row in response.data
            if isinstance(row, dict) and "departments" in row
        ] if response.data else []
        return self._to_model_list(rows)

    def assign_worker(self, department_id: UUID, worker_id: UUID) -> dict[str, Any]:
        """
        Assign a worker to a department.

        This method creates a new association in the junction table, linking a worker
        to a department. A worker can be assigned to multiple departments.

        Args:
            department_id (UUID): The unique identifier of the department.
            worker_id (UUID): The unique identifier of the worker to assign.

        Returns:
            dict[str, Any]: The created junction record containing department_id and worker_id.
        """
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .insert({
                q.JunctionColumns.DEPARTMENT_ID: str(department_id),
                q.JunctionColumns.WORKER_ID: str(worker_id),
            })
            .execute()
        )
        return cast(dict[str, Any], response.data[0])

    def unassign_worker(self, department_id: UUID, worker_id: UUID) -> bool:
        """
        Remove a worker's assignment from a specific department.

        This method deletes the association record from the junction table, effectively
        unassigning the worker from the department. The worker and department records
        themselves remain unchanged.

        Args:
            department_id (UUID): The unique identifier of the department.
            worker_id (UUID): The unique identifier of the worker to unassign.

        Returns:
            bool: True if the assignment was successfully removed, False if no such
                 assignment existed.
        """
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .delete()
            .eq(q.JunctionColumns.DEPARTMENT_ID, str(department_id))
            .eq(q.JunctionColumns.WORKER_ID, str(worker_id))
            .execute()
        )
        return len(response.data) > 0
