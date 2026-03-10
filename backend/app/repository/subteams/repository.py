from typing import Any, cast
from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.repository import BaseRepository
from app.repository.subteams import queries as q
from app.schemas.subteams.models import SubteamResponse, SubteamWithWorkersResponse

logger = get_logger(__name__)


class SubteamRepository(BaseRepository[SubteamResponse]):
    def __init__(self, client: Client) -> None:
        """
        Initialize the SubteamRepository with a Supabase client.

        Args:
            client (Client): The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, SubteamResponse)
        self.logger = logger.bind(repository="SubteamRepository")

    def get_by_name(self, name: str) -> SubteamResponse | None:
        """
        Retrieve a subteam by its name.

        This method performs a single-record query to find a subteam with an exact
        name match. The query is case-sensitive.

        Args:
            name (str): The exact name of the subteam to retrieve.

        Returns:
            SubteamResponse | None: The subteam if found, None if no subteam
                                      exists with the given name.
        """
        log = self.logger.bind(method="get_by_name", name=name)
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.NAME, name)
            .single()
            .execute()
        )
        subteam = self._to_model(response.data) if response.data else None
        if subteam:
            log.debug("subteam_found_by_name", subteam_id=str(subteam.id))
        else:
            log.debug("subteam_not_found_by_name")
        return subteam
    
    def get_by_department(self, department_id: UUID) -> list[SubteamResponse]:
        """
        Retrieve all subteams that belong to a specific department.

        This method queries the subteams table for records that have a matching
        department_id, returning a list of subteams associated with that department.

        Args:
            department_id (UUID): The unique identifier of the department.

        Returns:
            list[SubteamResponse]: A list of subteams that belong to the specified department.
                                    Returns an empty list if no subteams are found.
        """
        log = self.logger.bind(method="get_by_department", department_id=str(department_id))
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.DEPARTMENT_ID, str(department_id))
            .execute()
        )
        subteams = self._to_model_list(response.data) if response.data else []
        log.debug("fetched_subteams_by_department", count=len(subteams))
        return subteams

    def get_with_workers(self, subteam_id: UUID) -> list[SubteamWithWorkersResponse]:
        """
        Retrieve a subteam with all its assigned workers embedded.

        This method fetches subteam details along with complete information about
        all workers assigned to the subteam through a join operation.

        Args:
            subteam_id (UUID): The unique identifier of the subteam.

        Returns:
            list[SubteamWithWorkersResponse]: The subteam with embedded worker data if found,
        """
        log = self.logger.bind(method="get_with_workers", subteam_id=str(subteam_id))
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_WITH_WORKERS)
            .eq(q.Columns.ID, str(subteam_id))
            .single()
            .execute()
        )
        subteams = self._to_model_list([response.data], SubteamWithWorkersResponse) if response.data else []
        log.debug("fetched_subteam_with_workers", has_data=bool(subteams))
        return subteams

    def get_subteams_for_worker(self, worker_id: UUID) -> list[SubteamResponse]:
        """
        Retrieve all subteams that a specific worker is assigned to.

        This method queries the junction table to find all subteam associations for
        a worker, handling the many-to-many relationship between workers and subteams.

        Args:
            worker_id (UUID): The unique identifier of the worker.

        Returns:
            list[SubteamResponse]: A list of all subteams the worker is assigned to.
                                     Returns an empty list if the worker is not assigned
                                     to any subteams.
        """
        log = self.logger.bind(method="get_subteams_for_worker", worker_id=str(worker_id))
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .select("subteams(*)")
            .eq(q.JunctionColumns.WORKER_ID, str(worker_id))
            .execute()
        )
        rows = [
            row["subteams"]
            for row in response.data
            if isinstance(row, dict) and "subteams" in row
        ] if response.data else []
        subteams = self._to_model_list(rows)
        log.debug("fetched_subteams_for_worker", count=len(subteams))
        return subteams

    def assign_worker(self, subteam_id: UUID, worker_id: UUID) -> dict[str, Any]:
        """
        Assign a worker to a subteam.

        This method creates a new association in the junction table, linking a worker
        to a subteam. A worker can be assigned to multiple subteams.

        Args:
            subteam_id (UUID): The unique identifier of the subteam.
            worker_id (UUID): The unique identifier of the worker to assign.

        Returns:
            dict[str, Any]: The created junction record containing subteam_id and worker_id.
        """
        log = self.logger.bind(method="assign_worker", subteam_id=str(subteam_id), worker_id=str(worker_id))
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .insert({
                q.JunctionColumns.SUBTEAM_ID: str(subteam_id),
                q.JunctionColumns.WORKER_ID: str(worker_id),
            })
            .execute()
        )
        log.info("worker_assigned_to_subteam")
        return cast(dict[str, Any], response.data[0])

    def unassign_worker(self, subteam_id: UUID, worker_id: UUID) -> bool:
        """
        Remove a worker's assignment from a specific subteam.

        This method deletes the association record from the junction table, effectively
        unassigning the worker from the subteam. The worker and subteam records
        themselves remain unchanged.

        Args:
            subteam_id (UUID): The unique identifier of the subteam.
            worker_id (UUID): The unique identifier of the worker to unassign.

        Returns:
            bool: True if the assignment was successfully removed, False if no such
                 assignment existed.
        """
        log = self.logger.bind(method="unassign_worker", subteam_id=str(subteam_id), worker_id=str(worker_id))
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .delete()
            .eq(q.JunctionColumns.SUBTEAM_ID, str(subteam_id))
            .eq(q.JunctionColumns.WORKER_ID, str(worker_id))
            .execute()
        )
        success = len(response.data) > 0
        if success:
            log.info("worker_unassigned_from_subteam")
        else:
            log.debug("no_assignment_to_remove")
        return success
