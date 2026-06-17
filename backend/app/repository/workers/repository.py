from uuid import UUID

from supabase import Client

from app.core.logging import get_logger
from app.repository.filters import quote_postgrest_value
from app.repository.repository import BaseRepository
from app.repository.workers import queries as q
from app.schemas.models import UserRole, WorkerStatus
from app.schemas.workers.models import WorkerResponse

logger = get_logger(__name__)


class WorkerRepository(BaseRepository[WorkerResponse]):
    def __init__(self, client: Client) -> None:
        """
        Initialize the WorkerRepository with a Supabase client.

        Args:
            client (Client): The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, WorkerResponse)
        self.logger = logger.bind(repository="WorkerRepository")

    def get_by_email(self, email: str) -> WorkerResponse | None:
        """
        Retrieve a worker by their email address.

        This method performs a single-record query on the workers table to find a worker
        with the specified email address. The query expects at most one matching record.

        Args:
            email (str): The email address of the worker to retrieve.

        Returns:
            WorkerResponse | None: A WorkerResponse model instance if found, None if no worker exists with
                          the given email address or if the response contains no data.
        """
        log = self.logger.bind(method="get_by_email", email=email)
        response = self.client.table(q.TABLE).select(q.SELECT_ALL).eq(q.Columns.EMAIL, email).maybe_single().execute()
        worker = self._to_model(response.data) if response else None
        if worker:
            log.debug("worker_found_by_email", worker_id=str(worker.id))
        else:
            log.debug("worker_not_found_by_email")
        return worker

    def get_by_phone(self, phone: str) -> WorkerResponse | None:
        """
        Retrieve a worker by their phone number.

        This method performs a single-record query on the workers table to find a worker
        with the specified phone number. The query expects at most one matching record.

        Args:
            phone (str): The phone number of the worker to retrieve.

        Returns:
            WorkerResponse | None: A WorkerResponse model instance if found, None if no worker exists with
                          the given phone number or if the response contains no data.
        """
        log = self.logger.bind(method="get_by_phone", phone=phone)
        response = self.client.table(q.TABLE).select(q.SELECT_ALL).eq(q.Columns.PHONE, phone).maybe_single().execute()
        worker = self._to_model(response.data) if response else None
        if worker:
            log.debug("worker_found_by_phone", worker_id=str(worker.id))
        else:
            log.debug("worker_not_found_by_phone")
        return worker

    def get_active_workers(self) -> list[WorkerResponse]:
        """
        Retrieve all workers with an active status.

        This method queries the workers table and filters for workers whose status is set
        to ACTIVE. It returns all matching worker records as a list of Worker instances.

        Returns:
            list[WorkerResponse]: A list of WorkerResponse model instances with active status. Returns an
                         empty list if no active workers are found or if the response contains no data.
        """
        log = self.logger.bind(method="get_active_workers")
        response = self.client.table(q.TABLE).select(q.SELECT_ALL).eq(q.Columns.STATUS, WorkerStatus.ACTIVE).execute()
        workers = self._to_model_list(response.data or [])
        log.debug("fetched_active_workers", count=len(workers))
        return workers

    def get_workers_by_department(self, department_id: UUID) -> list[WorkerResponse]:
        """
        Retrieve all workers associated with a specific department.

        This method queries the junction table to find all worker records linked to the given
        department ID. It performs a join operation through the junction table to fetch the
        complete worker information.

        Args:
            department_id (UUID): The unique identifier of the department whose workers are to be retrieved.

        Returns:
            list[Worker]: A list of Worker model instances belonging to the specified department.
                          Returns an empty list if no workers are found or if the response contains no data.

        Note:
            The method uses a junction table to handle the many-to-many relationship between
            workers and departments, selecting worker data through the 'workers(*)' relation.
        """
        log = self.logger.bind(method="get_workers_by_department", department_id=str(department_id))
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .select("workers(*)")
            .eq(q.JunctionColumns.DEPARTMENT_ID, str(department_id))
            .execute()
        )

        # More explicit type handling
        if not response.data:
            return []

        rows = [row["workers"] for row in response.data if isinstance(row, dict) and "workers" in row]
        workers = self._to_model_list(rows)
        log.debug("fetched_workers_by_department", count=len(workers))
        return workers

    def get_department_only_workers(self, department_id: UUID) -> list[WorkerResponse]:
        """
        Get workers assigned to a department but NOT assigned to any subteam.

        This method retrieves workers from the worker_departments junction table where
        the department_id matches and subteam_id is NULL, indicating department-level
        workers who are not part of any specific subteam.

        Args:
            department_id (UUID): The unique identifier of the department.

        Returns:
            list[WorkerResponse]: A list of Worker model instances assigned to the department
                                  but not to any subteam. Returns an empty list if no such workers exist.
        """
        log = self.logger.bind(method="get_department_only_workers", department_id=str(department_id))
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .select("workers(*)")
            .eq(q.JunctionColumns.DEPARTMENT_ID, str(department_id))
            .is_("subteam_id", "null")
            .execute()
        )

        if not response.data:
            return []

        rows = [row["workers"] for row in response.data if isinstance(row, dict) and "workers" in row]
        workers = self._to_model_list(rows)
        log.debug("fetched_department_only_workers", count=len(workers))
        return workers

    def update_status(self, id: UUID, status: WorkerStatus) -> WorkerResponse | None:
        """
        Update the status of a worker.

        This method updates only the status field of a worker record identified by the given UUID.
        It delegates to the base repository's update method to perform the actual database operation.

        Args:
            id (UUID): The unique identifier of the worker whose status is to be updated.
            status (WorkerStatus): The new status to assign to the worker (e.g., ACTIVE, INACTIVE).

        Returns:
            WorkerResponse | None: The updated WorkerResponse model instance if the update was successful,
                          None if the worker was not found or the update failed.
        """
        log = self.logger.bind(method="update_status", worker_id=str(id), status=status)
        worker = self.update(id, {q.Columns.STATUS: status})
        if worker:
            log.info("worker_status_updated")
        else:
            log.warning("worker_not_found")
        return worker

    def search(self, query: str) -> list[WorkerResponse]:
        """
        Search for workers by first name or last name.

        This method performs a case-insensitive partial match search across both the first_name
        and last_name columns. It uses the SQL ILIKE operator to find workers whose first or
        last name contains the search query string.

        Args:
            query (str): The search term to match against worker names. The search is case-insensitive
                        and matches partial strings (e.g., "john" will match "John", "Johnny", "Johnson").

        Returns:
            list[WorkerResponse]: A list of WorkerResponse model instances whose first or last name matches the query.
                         Returns an empty list if no matches are found or if the response contains no data.

        Example:
            >>> repository.search("smith")
            [WorkerResponse(first_name="John", last_name="Smith"),
            WorkerResponse(first_name="Jane", last_name="Smithson")]
        """
        log = self.logger.bind(method="search", query=query)
        # Quote/escape the user value so PostgREST reserved characters in it (',', '.', '(', ')', '"')
        # are treated as literal data and cannot inject additional filter conditions.
        pattern = quote_postgrest_value(f"%{query}%")
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .or_(f"{q.Columns.FIRST_NAME}.ilike.{pattern},{q.Columns.LAST_NAME}.ilike.{pattern}")
            .execute()
        )
        workers = self._to_model_list(response.data or [])
        log.debug("search_completed", count=len(workers))
        return workers

    def get_worker_roles(self, worker_id: UUID) -> list[UserRole]:
        """Retrieve all roles assigned to a worker from worker_app_roles table.

        Args:
            worker_id: Unique identifier of the worker.

        Returns:
            list[UserRole]: List of roles assigned to the worker.
        """
        log = self.logger.bind(method="get_worker_roles", worker_id=str(worker_id))
        response = self.client.table("worker_app_roles").select("role").eq("worker_id", str(worker_id)).execute()

        # Type assertion for mypy - response.data is a list of dicts
        role_data: list[dict[str, str]] = response.data  # type: ignore[assignment]
        roles = [UserRole(row["role"]) for row in role_data]
        log.debug("fetched_worker_roles", roles=roles)
        return roles

    def get_roles_for_workers(self, worker_ids: list[UUID]) -> dict[UUID, list[UserRole]]:
        """Retrieve roles for many workers in a single query, keyed by worker id.

        Batched counterpart to get_worker_roles, used to avoid N+1 queries when loading roles for a
        list of workers.

        Args:
            worker_ids: The workers whose roles to fetch.

        Returns:
            dict[UUID, list[UserRole]]: Map of worker id to its roles. Workers with no roles are
                omitted; the caller should default missing entries to an empty list. Returns an empty
                dict when given no worker ids.
        """
        if not worker_ids:
            return {}
        log = self.logger.bind(method="get_roles_for_workers", count=len(worker_ids))
        response = (
            self.client.table("worker_app_roles")
            .select("worker_id, role")
            .in_("worker_id", [str(wid) for wid in worker_ids])
            .execute()
        )
        rows: list[dict[str, str]] = response.data or []  # type: ignore[assignment]
        roles_by_worker: dict[UUID, list[UserRole]] = {}
        for row in rows:
            roles_by_worker.setdefault(UUID(row["worker_id"]), []).append(UserRole(row["role"]))
        log.debug("fetched_roles_for_workers", workers_with_roles=len(roles_by_worker))
        return roles_by_worker

    def replace_worker_roles(self, worker_id: UUID, roles: list[UserRole]) -> None:
        """Replace a worker's roles with the given set, applying only the difference.

        Computes the difference against the worker's current roles, batch-inserts the newly added
        roles in a single call, then deletes the removed ones. The added roles are inserted before
        any deletion so the worker is never left without roles mid-update (avoids the zero-roles
        window of a delete-all-then-reinsert approach).

        Args:
            worker_id: Unique identifier of the worker.
            roles: The complete set of roles the worker should end up with.
        """
        log = self.logger.bind(method="replace_worker_roles", worker_id=str(worker_id))
        current = set(self.get_worker_roles(worker_id))
        desired = set(roles)

        to_add = desired - current
        to_remove = current - desired

        if to_add:
            self.client.table("worker_app_roles").insert(
                [{"worker_id": str(worker_id), "role": role} for role in to_add]
            ).execute()
        for role in to_remove:
            self.client.table("worker_app_roles").delete().eq("worker_id", str(worker_id)).eq("role", role).execute()
        log.debug("replaced_worker_roles", added=sorted(to_add), removed=sorted(to_remove))
