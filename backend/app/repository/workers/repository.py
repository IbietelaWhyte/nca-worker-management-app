from datetime import date
from typing import Any
from uuid import UUID

from postgrest import CountMethod
from supabase import Client

from app.core.logging import get_logger
from app.core.phone import try_normalize_phone
from app.core.redaction import mask_email, mask_phone
from app.repository.filters import quote_postgrest_value
from app.repository.repository import BaseRepository
from app.repository.workers import queries as q
from app.schemas.models import UserRole, WorkerStatus
from app.schemas.workers.models import WorkerContactMatch, WorkerResponse

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

    def get_by_auth_user_id(self, auth_user_id: UUID) -> WorkerResponse | None:
        """Retrieve the worker linked to a Supabase login.

        `auth_user_id` is unique and only ever written when an admin grants a worker an account,
        so this is the link between a login and a profile that the login cannot influence.

        Args:
            auth_user_id: The login's id — the `sub` claim of its token.

        Returns:
            WorkerResponse | None: The linked worker, or None if the login has no profile.
        """
        response = (
            self.client.table(q.TABLE)
            .select(q.SELECT_ALL)
            .eq(q.Columns.AUTH_USER_ID, str(auth_user_id))
            .maybe_single()
            .execute()
        )
        return self._to_model(response.data) if response else None

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
        log = self.logger.bind(method="get_by_email", email=mask_email(email))
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
        log = self.logger.bind(method="get_by_phone", phone=mask_phone(phone))
        response = self.client.table(q.TABLE).select(q.SELECT_ALL).eq(q.Columns.PHONE, phone).maybe_single().execute()
        worker = self._to_model(response.data) if response else None
        if worker:
            log.debug("worker_found_by_phone", worker_id=str(worker.id))
        else:
            log.debug("worker_not_found_by_phone")
        return worker

    def get_active_workers(self) -> list[WorkerResponse]:
        """
        Retrieve all active workers.

        Returns:
            list[WorkerResponse]: A list of WorkerResponse model instances that are active. Returns an
                         empty list if no active workers are found or if the response contains no data.
        """
        log = self.logger.bind(method="get_active_workers")
        response = self.client.table(q.TABLE).select(q.SELECT_ALL).eq(q.Columns.IS_ACTIVE, True).execute()
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

    def get_workers_by_department_grouped_by_subteam(
        self, department_id: UUID
    ) -> dict[UUID | None, list[WorkerResponse]]:
        """
        Retrieve a department's workers bucketed by the subteam they belong to.

        One round-trip for the whole department, rather than a `get_with_workers` call
        per subteam. A worker holds at most one row per department (the junction is
        unique on worker_id + department_id), so the buckets are disjoint.

        Args:
            department_id (UUID): The unique identifier of the department.

        Returns:
            dict[UUID | None, list[WorkerResponse]]: Subteam ID -> its workers, with the
                                                    None key holding workers in no subteam.
                                                    Subteams with no members are absent.
        """
        log = self.logger.bind(method="get_workers_by_department_grouped_by_subteam", department_id=str(department_id))
        response = (
            self.client.table(q.JUNCTION_TABLE)
            .select(f"{q.JunctionColumns.SUBTEAM_ID}, workers(*)")
            .eq(q.JunctionColumns.DEPARTMENT_ID, str(department_id))
            .execute()
        )

        grouped: dict[UUID | None, list[WorkerResponse]] = {}
        for row in response.data or []:
            if not isinstance(row, dict) or not row.get("workers"):
                continue
            raw_subteam_id = row.get(q.JunctionColumns.SUBTEAM_ID)
            subteam_id = UUID(str(raw_subteam_id)) if raw_subteam_id else None
            grouped.setdefault(subteam_id, []).append(self._to_model(row["workers"]))

        log.debug(
            "fetched_workers_grouped_by_subteam",
            groups=len(grouped),
            total=sum(len(w) for w in grouped.values()),
        )
        return grouped

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

    def get_contact_index(self) -> dict[str, WorkerContactMatch]:
        """Build a lookup of every existing worker's contact details, for duplicate detection.

        Returns one map keyed by both lowercased email and E.164-normalized phone, so a caller can
        test either against it. Normalizing both sides here is what makes the check case-insensitive
        and format-insensitive — the ``workers.email`` unique index is case-sensitive and
        ``workers.phone`` has no constraint at all, so ``Jane@x.com`` would otherwise slip past both
        the app check and the database and create a second profile for the same person.

        Fetches the whole table in a single query rather than filtering by the values being imported:
        at this app's scale that is one cheap round trip instead of one per CSV row, and it avoids
        building a several-hundred-term PostgREST ``or()`` filter. Revisit if ``workers`` ever grows
        past a few thousand rows.

        Returns:
            dict[str, WorkerContactMatch]: Map of normalized email/phone to the owning worker.
        """
        log = self.logger.bind(method="get_contact_index")
        response = self.client.table(q.TABLE).select(q.SELECT_CONTACT_INDEX).execute()
        rows: list[dict[str, Any]] = response.data or []  # type: ignore[assignment]

        index: dict[str, WorkerContactMatch] = {}
        for row in rows:
            match = WorkerContactMatch(worker_id=UUID(row["id"]), is_active=bool(row["is_active"]))
            if email := row.get("email"):
                index[email.strip().lower()] = match
            if phone := try_normalize_phone(row.get("phone")):
                index[phone] = match

        log.debug("built_contact_index", workers=len(rows), keys=len(index))
        return index

    def create_many(self, rows: list[dict[str, Any]]) -> list[WorkerResponse]:
        """Create many workers in a single insert.

        One statement, so Postgres applies it atomically — either every row lands or none does.

        Args:
            rows: Field values for each worker to create.

        Returns:
            list[WorkerResponse]: The created workers, with database-generated fields populated.
        """
        if not rows:
            return []
        log = self.logger.bind(method="create_many", count=len(rows))
        response = self.client.table(q.TABLE).insert(rows).execute()
        workers = self._to_model_list(response.data or [])
        log.info("workers_created", created_count=len(workers))
        return workers

    def delete_many(self, ids: list[UUID]) -> None:
        """Delete many workers by id in a single statement.

        Used to compensate a partially-applied bulk import; see ``WorkerService.import_workers``.

        Args:
            ids: Unique identifiers of the workers to delete.
        """
        if not ids:
            return
        log = self.logger.bind(method="delete_many", count=len(ids))
        self.client.table(q.TABLE).delete().in_(q.Columns.ID, [str(i) for i in ids]).execute()
        log.info("workers_deleted")

    def search(
        self,
        query: str | None = None,
        *,
        department_ids: list[UUID] | None = None,
        role: UserRole | None = None,
        status: WorkerStatus | None = None,
        today: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[WorkerResponse], int]:
        """
        Search and filter workers, one page at a time, returning the page and the total match count.

        Every argument is optional and they combine with AND. ``query`` is split on whitespace and
        each word must match the first name, last name or email (case-insensitive), so "john smi"
        finds John Smith. The page and the total come back from a single PostgREST request.

        Args:
            query (str | None): Free-text search over first name, last name and email.
            department_ids (list[UUID] | None): Keep only workers in at least one of these
                departments. An empty list matches nobody.
            role (UserRole | None): Keep only workers holding this app role.
            status (WorkerStatus | None): ``active``/``inactive`` on ``is_active``; ``on_leave``
                for leave covering ``today``.
            today (date | None): The date ``on_leave`` is judged against. Defaults to today.
            limit (int): Maximum workers to return.
            offset (int): Workers to skip, in last name, first name order.

        Returns:
            tuple[list[WorkerResponse], int]: The page of workers and the number matching overall.
        """
        # The query may be an email address, so only whether one was given reaches the log.
        log = self.logger.bind(method="search", has_query=bool(query), role=role, status=status)
        if department_ids is not None and not department_ids:
            return [], 0

        embeds = []
        if department_ids is not None:
            embeds.append(q.EMBED_DEPARTMENTS)
        if role is not None:
            embeds.append(q.EMBED_APP_ROLES)
        if status == WorkerStatus.ON_LEAVE:
            embeds.append(q.EMBED_LEAVE)

        request = self.client.table(q.TABLE).select(", ".join([q.SELECT_ALL, *embeds]), count=CountMethod.exact)
        if department_ids is not None:
            request = request.in_(q.FILTER_DEPARTMENT_ID, [str(i) for i in department_ids])
        if role is not None:
            request = request.eq(q.FILTER_APP_ROLE, role.value)
        if status == WorkerStatus.ON_LEAVE:
            on = (today or date.today()).isoformat()
            request = request.lte(q.FILTER_LEAVE_START, on).gte(q.FILTER_LEAVE_END, on)
        elif status is not None:
            request = request.eq(q.Columns.IS_ACTIVE, status == WorkerStatus.ACTIVE)
        for term in (query or "").split()[: q.MAX_SEARCH_TERMS]:
            # Quote/escape the user value so PostgREST reserved characters in it (',', '.', '(', ')', '"')
            # are treated as literal data and cannot inject additional filter conditions.
            pattern = quote_postgrest_value(f"%{term}%")
            request = request.or_(
                f"{q.Columns.FIRST_NAME}.ilike.{pattern},"
                f"{q.Columns.LAST_NAME}.ilike.{pattern},"
                f"{q.Columns.EMAIL}.ilike.{pattern}"
            )

        response = (
            request.order(q.Columns.LAST_NAME)
            .order(q.Columns.FIRST_NAME)
            .order(q.Columns.ID)
            .range(offset, offset + limit - 1)
            .execute()
        )
        workers = self._to_model_list(response.data or [])
        total = response.count if response.count is not None else len(workers)
        log.debug("search_completed", count=len(workers), total=total)
        return workers, total

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
