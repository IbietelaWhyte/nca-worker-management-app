import csv
import io
from uuid import UUID

from pydantic import ValidationError

from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.core.redaction import mask_email
from app.repository.departments.repository import DepartmentRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.departments.models import DepartmentResponse
from app.schemas.models import TokenPayload, UserRole
from app.schemas.workers.models import (
    WorkerCreate,
    WorkerImportResult,
    WorkerImportRowResult,
    WorkerResponse,
    WorkerUpdate,
)

logger = get_logger(__name__)

# Columns a CSV must provide for a bulk worker import. Email is required (it is the dedup key
# and the DB declares workers.email NOT NULL UNIQUE); phone is required for SMS reminders.
REQUIRED_IMPORT_COLUMNS = ("first_name", "last_name", "email", "phone")


class WorkerService:
    def __init__(
        self,
        worker_repo: WorkerRepository,
        department_repo: DepartmentRepository,
    ) -> None:
        """Initialize the WorkerService with required repositories.

        Args:
            worker_repo: Repository for worker database operations.
            department_repo: Repository for department database operations.
        """
        self.worker_repo = worker_repo
        self.department_repo = department_repo

        # bind the logger to the service name for structured logging
        self.logger = logger.bind(service="WorkerService")

    def get_worker(self, worker_id: UUID) -> WorkerResponse:
        """Retrieve a worker by ID.

        Args:
            worker_id: Unique identifier of the worker.

        Returns:
            WorkerResponse: The worker data with roles.

        Raises:
            ValueError: If worker not found.
        """
        # bind the method and worker_id for better traceability in logs
        log = self.logger.bind(method="get_worker", worker_id=str(worker_id))
        worker = self.worker_repo.get_by_id(worker_id)
        if not worker:
            log.warning("worker_not_found")
            raise NotFoundError(f"Worker {worker_id} not found")

        # Load roles for the worker
        worker.roles = self.worker_repo.get_worker_roles(worker_id)
        return worker

    def _attach_roles(self, workers: list[WorkerResponse]) -> list[WorkerResponse]:
        """Load roles for a list of workers in a single batched query and attach them.

        Args:
            workers: Workers to enrich with their roles.

        Returns:
            list[WorkerResponse]: The same workers with their ``roles`` populated.
        """
        if not workers:
            return workers
        roles_by_worker = self.worker_repo.get_roles_for_workers([worker.id for worker in workers])
        for worker in workers:
            worker.roles = roles_by_worker.get(worker.id, [])
        return workers

    def get_all_workers(self, limit: int = 100, offset: int = 0) -> list[WorkerResponse]:
        """Retrieve all workers (paginated), with their roles.

        Args:
            limit: Maximum number of workers to return.
            offset: Number of workers to skip before returning results.

        Returns:
            list[WorkerResponse]: List of workers in the system with their roles.
        """
        # bind the method for better traceability in logs
        log = self.logger.bind(method="get_all_workers", limit=limit, offset=offset)
        workers = self._attach_roles(self.worker_repo.get_all(limit=limit, offset=offset))
        log.info("fetched_all_workers", count=len(workers))
        return workers

    def get_active_workers(self) -> list[WorkerResponse]:
        """Retrieve all active workers.

        Returns:
            list[WorkerResponse]: List of workers with active status and their roles.
        """
        # bind the method for better traceability in logs
        log = self.logger.bind(method="get_active_workers")
        workers = self._attach_roles(self.worker_repo.get_active_workers())

        log.info("fetched_active_workers", count=len(workers))
        return workers

    def get_workers_by_department(self, department_id: UUID) -> list[WorkerResponse]:
        """Retrieve all workers assigned to a specific department.

        Args:
            department_id: Unique identifier of the department.

        Returns:
            list[WorkerResponse]: List of workers in the department.
        """
        # bind the method and department_id for better traceability in logs
        log = self.logger.bind(method="get_workers_by_department", department_id=str(department_id))
        workers = self.worker_repo.get_workers_by_department(department_id)
        log.info(
            "fetched_workers_by_department",
            count=len(workers),
        )
        return workers

    def create_worker(self, data: WorkerCreate) -> WorkerResponse:
        """Create a new worker.

        Validates that either email or phone is provided and checks for existing workers
        with the same contact information.

        Args:
            data: Worker creation data including name, contact info.

        Returns:
            WorkerResponse: The newly created worker.

        Raises:
            ValueError: If contact info is missing or worker already exists.
        """
        # bind the method and email for better traceability in logs
        log = self.logger.bind(method="create_worker", email=mask_email(data.email))
        if data.email:
            existing = self.worker_repo.get_by_email(data.email)
        elif data.phone:
            existing = self.worker_repo.get_by_phone(data.phone)
        else:
            log.error("missing_contact_info")
            raise BadRequestError("Either email or phone number must be provided")
        if existing:
            log.warning("worker_already_exists")
            raise ConflictError(f"Worker with email {data.email} already exists")
        worker = self.worker_repo.create(data.model_dump())
        log.info("worker_created", worker_id=str(worker.id))
        return worker

    def import_workers(self, file_bytes: bytes, department_id: UUID, *, dry_run: bool) -> WorkerImportResult:
        """Bulk-create workers from a CSV file and assign them to a department.

        Each row is processed independently: invalid or duplicate rows are skipped and reported,
        while valid rows are created (unless ``dry_run`` is set, in which case nothing is written
        and valid rows are flagged as ``valid``). Duplicates are detected both within the file
        (by email) and against existing workers in the database.

        Args:
            file_bytes: Raw bytes of the uploaded CSV file.
            department_id: Department to assign newly created workers to.
            dry_run: If True, validate and report only — perform no writes.

        Returns:
            WorkerImportResult: Per-row outcomes plus aggregate counts.

        Raises:
            NotFoundError: If the target department does not exist.
            BadRequestError: If the file is not decodable, empty, or missing required columns.
        """
        log = self.logger.bind(method="import_workers", department_id=str(department_id), dry_run=dry_run)

        # Fail fast on a bad target department before processing any rows.
        if not self.department_repo.get_by_id(department_id):
            log.warning("import_department_not_found")
            raise NotFoundError(f"Department {department_id} not found")

        try:
            text = file_bytes.decode("utf-8-sig")  # utf-8-sig tolerates the BOM Excel exports add
        except UnicodeDecodeError as exc:
            raise BadRequestError("CSV file must be UTF-8 encoded") from exc

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise BadRequestError("CSV file is empty")
        header = {(name or "").strip().lower() for name in reader.fieldnames}
        missing = [col for col in REQUIRED_IMPORT_COLUMNS if col not in header]
        if missing:
            raise BadRequestError(f"CSV is missing required column(s): {', '.join(missing)}")

        results: list[WorkerImportRowResult] = []
        seen_emails: set[str] = set()

        for index, raw in enumerate(reader, start=1):
            # Normalize keys and trim whitespace; unmatched/extra columns are ignored.
            row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()}
            email = row.get("email", "")
            name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or None

            blanks = [col for col in REQUIRED_IMPORT_COLUMNS if not row.get(col)]
            if blanks:
                results.append(
                    WorkerImportRowResult(
                        row_number=index,
                        status="error",
                        name=name,
                        email=email or None,
                        error=f"Missing value(s) for: {', '.join(blanks)}",
                    )
                )
                continue

            try:
                data = WorkerCreate(
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    email=email,
                    phone=row["phone"],
                )
            except ValidationError as exc:
                results.append(
                    WorkerImportRowResult(row_number=index, status="error", name=name, email=email, error=str(exc))
                )
                continue

            email_key = email.lower()
            if email_key in seen_emails:
                results.append(
                    WorkerImportRowResult(
                        row_number=index,
                        status="skipped_duplicate",
                        name=name,
                        email=email,
                        error="Duplicate email within file",
                    )
                )
                continue
            seen_emails.add(email_key)

            if self.worker_repo.get_by_email(email):
                results.append(
                    WorkerImportRowResult(
                        row_number=index,
                        status="skipped_duplicate",
                        name=name,
                        email=email,
                        error="Worker with this email already exists",
                    )
                )
                continue

            if dry_run:
                results.append(WorkerImportRowResult(row_number=index, status="valid", name=name, email=email))
                continue

            try:
                worker = self.worker_repo.create(data.model_dump())
                self.department_repo.assign_worker(department_id, worker.id)
                results.append(
                    WorkerImportRowResult(
                        row_number=index, status="created", name=name, email=email, worker_id=worker.id
                    )
                )
            except Exception as exc:  # one row's failure must not abort the rest of the batch
                log.warning("import_row_failed", row_number=index, error=str(exc))
                results.append(
                    WorkerImportRowResult(
                        row_number=index, status="error", name=name, email=email, error="Failed to create worker"
                    )
                )

        result = WorkerImportResult(
            dry_run=dry_run,
            total_rows=len(results),
            created=sum(1 for r in results if r.status == "created"),
            valid=sum(1 for r in results if r.status == "valid"),
            skipped_duplicate=sum(1 for r in results if r.status == "skipped_duplicate"),
            errors=sum(1 for r in results if r.status == "error"),
            results=results,
        )
        log.info(
            "import_workers_complete",
            total=result.total_rows,
            created=result.created,
            valid=result.valid,
            skipped=result.skipped_duplicate,
            errors=result.errors,
        )
        return result

    def update_worker(self, worker_id: UUID, data: WorkerUpdate) -> WorkerResponse:
        """Update a worker's information.

        Args:
            worker_id: Unique identifier of the worker to update.
            data: Partial worker data with fields to update (including optional roles).

        Returns:
            WorkerResponse: The updated worker data with roles.

        Raises:
            ValueError: If worker not found or update fails.
        """
        # bind the method and worker_id for better traceability in logs
        log = self.logger.bind(
            method="update_worker",
            worker_id=str(worker_id),
            fields=sorted(data.model_dump(exclude_none=True).keys()),
        )

        # Get existing worker
        worker = self.worker_repo.get_by_id(worker_id)
        if not worker:
            log.warning("worker_not_found")
            raise NotFoundError(f"Worker {worker_id} not found")

        # Extract roles and assistant_hod_departments from update data if present
        update_dict = data.model_dump(exclude_none=True)
        new_roles = update_dict.pop("roles", None)
        new_assistant_hod_departments = update_dict.pop("assistant_hod_departments", None)

        # Update worker profile fields if any were provided
        if update_dict:
            updated = self.worker_repo.update(worker_id, update_dict)
            if not updated:
                log.error("worker_update_failed")
                raise AppError(f"Failed to update worker {worker_id}")
            worker = updated

        # Update roles if provided (diff-based replace: batch-insert added, delete removed)
        if new_roles is not None:
            self.worker_repo.replace_worker_roles(worker_id, new_roles)
            log.info("roles_updated", new_roles=new_roles)

        # Update assistant_hod department assignments if provided
        if new_assistant_hod_departments is not None:
            # Get current assistant_hod departments
            current_dept_ids = set(self.department_repo.get_assistant_hod_department_ids(worker_id))
            new_dept_ids = set(new_assistant_hod_departments)

            # Remove old assignments
            for dept_id in current_dept_ids - new_dept_ids:
                self.department_repo.remove_assistant_hod(worker_id, dept_id)

            # Add new assignments
            for dept_id in new_dept_ids - current_dept_ids:
                self.department_repo.assign_assistant_hod(worker_id, dept_id)

            log.info("assistant_hod_departments_updated", departments=new_assistant_hod_departments)

        # Load current roles for response
        worker.roles = self.worker_repo.get_worker_roles(worker_id)

        log.info("worker_updated")
        return worker

    def deactivate_worker(self, worker_id: UUID) -> WorkerResponse:
        """Deactivate a worker (set is_active to False).

        Args:
            worker_id: Unique identifier of the worker to deactivate.

        Returns:
            WorkerResponse: The updated worker with is_active=False.

        Raises:
            ValueError: If worker not found or deactivation fails.
        """
        # bind the method and worker_id for better traceability in logs
        log = self.logger.bind(method="deactivate_worker", worker_id=str(worker_id))
        self.get_worker(worker_id)
        updated = self.worker_repo.update(worker_id, {"is_active": False})
        if not updated:
            log.error("worker_deactivation_failed")
            raise AppError(f"Failed to deactivate worker {worker_id}")
        log.info("worker_deactivated")
        return updated

    def search_workers(self, query: str) -> list[WorkerResponse]:
        """Search for workers by name.

        Performs case-insensitive partial matching on first and last names.

        Args:
            query: Search term to match against worker names.

        Returns:
            list[WorkerResponse]: List of workers matching the search query.
        """
        # bind the method and query for better traceability in logs
        log = self.logger.bind(method="search_workers", query=query)
        workers = self.worker_repo.search(query)
        log.info("worker_search", results=len(workers))
        return workers

    def get_worker_departments(self, worker_id: UUID) -> list[DepartmentResponse]:
        """Retrieve all departments a worker is assigned to.

        Args:
            worker_id: Unique identifier of the worker.

        Returns:
            list[DepartmentResponse]: List of departments the worker belongs to.
        """
        log = self.logger.bind(method="get_worker_departments", worker_id=str(worker_id))
        departments = self.department_repo.get_departments_for_worker(worker_id)
        log.info("fetched_worker_departments", count=len(departments))
        return [DepartmentResponse.model_validate(dept) for dept in departments]

    def can_manage_worker(self, manager_id: UUID, worker_id: UUID) -> bool:
        """Check if a manager (HOD or Assistant HOD) can manage a specific worker.

        A manager can manage a worker if the worker belongs to at least one department
        that the manager oversees (either as HOD or assistant_hod).

        Args:
            manager_id: Unique identifier of the manager (HOD or assistant_hod).
            worker_id: Unique identifier of the worker to check.

        Returns:
            bool: True if manager oversees at least one department containing the worker.
        """
        log = self.logger.bind(method="can_manage_worker", manager_id=str(manager_id), worker_id=str(worker_id))

        managed_dept_ids = self.get_managed_department_ids(manager_id)
        if not managed_dept_ids:
            log.info("manager_has_no_departments")
            return False

        # Get departments the worker belongs to
        worker_departments = self.department_repo.get_departments_for_worker(worker_id)
        if not worker_departments:
            log.info("worker_has_no_departments")
            return False

        # Check for overlap
        worker_dept_ids = {dept.id for dept in worker_departments}
        can_manage = bool(managed_dept_ids & worker_dept_ids)

        log.info("can_manage_check", can_manage=can_manage)
        return can_manage

    def get_managed_department_ids(self, worker_id: UUID) -> set[UUID]:
        """Return the IDs of all departments a worker oversees, as HOD or as assistant HOD.

        Args:
            worker_id: Unique identifier of the manager.

        Returns:
            set[UUID]: Union of department IDs the worker is HOD of and assistant HOD of.
        """
        managed_dept_ids = {dept.id for dept in self.department_repo.get_departments_by_hod(worker_id)}
        managed_dept_ids |= set(self.department_repo.get_assistant_hod_department_ids(worker_id))
        return managed_dept_ids

    def get_worker_for_token(self, token: TokenPayload) -> WorkerResponse:
        """Resolve the worker profile for the authenticated user described by a token.

        Args:
            token: The verified token payload of the requesting user.

        Returns:
            WorkerResponse: The worker record matching the token's email.

        Raises:
            BadRequestError: If the token carries no email.
            NotFoundError: If no worker profile exists for the token's email.
        """
        if not token.email:
            raise BadRequestError("Email not found in authentication token")
        worker = self.worker_repo.get_by_email(token.email)
        if not worker:
            raise NotFoundError("Worker profile not found for authenticated user")
        return worker

    def authorize_manage_worker(self, token: TokenPayload, worker_id: UUID) -> None:
        """Ensure the requesting user may manage the given worker.

        Admins are always allowed. Other users must manage a department the worker belongs to.

        Args:
            token: The verified token payload of the requesting user.
            worker_id: The worker being acted upon.

        Raises:
            PermissionDeniedError: If a non-admin does not manage the worker.
            BadRequestError/NotFoundError: If the actor's worker profile cannot be resolved.
        """
        if token.role == UserRole.ADMIN:
            return
        actor = self.get_worker_for_token(token)
        if not self.can_manage_worker(actor.id, worker_id):
            raise PermissionDeniedError("You can only manage workers in departments you manage")

    def authorize_update_worker(self, token: TokenPayload, worker_id: UUID, data: WorkerUpdate) -> None:
        """Authorize a worker update, including role and assistant-HOD-department restrictions.

        Admins are unrestricted. Non-admins must manage the worker, may not assign the ``admin`` or
        ``hod`` roles, and may only assign ``assistant_hod`` for departments they manage.

        Args:
            token: The verified token payload of the requesting user.
            worker_id: The worker being updated.
            data: The requested update payload.

        Raises:
            PermissionDeniedError: If any of the above rules are violated.
        """
        if token.role == UserRole.ADMIN:
            return
        actor = self.get_worker_for_token(token)
        if not self.can_manage_worker(actor.id, worker_id):
            raise PermissionDeniedError("You can only update workers in departments you manage")
        if data.roles is not None and any(role in {UserRole.ADMIN, UserRole.HOD} for role in data.roles):
            raise PermissionDeniedError("HODs can only assign worker and assistant_hod roles")
        if data.assistant_hod_departments is not None:
            managed = self.get_managed_department_ids(actor.id)
            if not set(data.assistant_hod_departments) <= managed:
                raise PermissionDeniedError("You can only assign assistant_hod for departments you manage")

    def authorize_view_worker(self, token: TokenPayload, worker_id: UUID) -> None:
        """Ensure the requesting user may read the given worker's record.

        Admins may read any worker. HODs and assistant HODs may read workers in departments they
        manage. A regular worker may read only their own record.

        Args:
            token: The verified token payload of the requesting user.
            worker_id: The worker being read.

        Raises:
            PermissionDeniedError: If the user is not allowed to view the worker.
            BadRequestError/NotFoundError: If the actor's worker profile cannot be resolved.
        """
        if token.role == UserRole.ADMIN:
            return
        actor = self.get_worker_for_token(token)
        if token.role in (UserRole.HOD, UserRole.ASSISTANT_HOD):
            if self.can_manage_worker(actor.id, worker_id):
                return
            raise PermissionDeniedError("You can only view workers in departments you manage")
        # Regular workers may only view their own record.
        if worker_id != actor.id:
            raise PermissionDeniedError("You can only view your own worker record")

    def authorize_create_assignment(self, token: TokenPayload, department_id: UUID) -> None:
        """Ensure the requesting user may assign a worker to the given department.

        Args:
            token: The verified token payload of the requesting user.
            department_id: The department a new worker would be assigned to.

        Raises:
            PermissionDeniedError: If a non-admin does not manage the department.
        """
        if token.role == UserRole.ADMIN:
            return
        actor = self.get_worker_for_token(token)
        if department_id not in self.get_managed_department_ids(actor.id):
            raise PermissionDeniedError("You can only assign workers to departments you manage")

    def list_visible_workers(
        self,
        token: TokenPayload,
        active_only: bool = False,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorkerResponse]:
        """List the workers visible to the requesting user, applying optional filters.

        Admins see all workers; HODs and assistant HODs see only workers in the departments they
        manage; a regular worker sees only their own record. The ``active_only`` and ``search``
        filters apply to every result. ``limit``/``offset`` page the unfiltered admin listing.

        Args:
            token: The verified token payload of the requesting user.
            active_only: If True, return only active workers.
            search: Optional case-insensitive name filter.
            limit: Max workers for the unfiltered listing.
            offset: Number of workers to skip for the unfiltered listing.

        Returns:
            list[WorkerResponse]: The filtered, deduplicated workers visible to the user.
        """
        if token.role == UserRole.ADMIN:
            # Admins see everyone.
            if search:
                return self.search_workers(search)
            if active_only:
                return self.get_active_workers()
            return self.get_all_workers(limit=limit, offset=offset)

        if token.role in (UserRole.HOD, UserRole.ASSISTANT_HOD):
            # HOD / assistant HOD: only workers in departments they manage.
            actor = self.get_worker_for_token(token)
            managed_dept_ids = self.get_managed_department_ids(actor.id)
            if not managed_dept_ids:
                return []

            workers_by_id: dict[UUID, WorkerResponse] = {}
            for dept_id in managed_dept_ids:
                for worker in self.get_workers_by_department(dept_id):
                    workers_by_id[worker.id] = worker
            workers = list(workers_by_id.values())
        else:
            # Regular workers see only their own record.
            workers = self._attach_roles([self.get_worker_for_token(token)])

        if search:
            needle = search.lower()
            workers = [w for w in workers if needle in w.first_name.lower() or needle in w.last_name.lower()]
        if active_only:
            workers = [w for w in workers if w.is_active]
        return workers
