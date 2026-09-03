import csv
import io
from datetime import date
from uuid import UUID

from pydantic import ValidationError
from supabase import Client
from supabase_auth.errors import AuthApiError

from app.core.config import settings
from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.core.redaction import mask_email
from app.repository.departments.repository import DepartmentRepository
from app.repository.schedules.repository import ScheduleRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.departments.models import DepartmentResponse
from app.schemas.models import TokenPayload, UserRole, highest_role
from app.schemas.workers.models import (
    WorkerCreate,
    WorkerImportResult,
    WorkerImportRow,
    WorkerImportRowResult,
    WorkerResponse,
    WorkerUpdate,
)

logger = get_logger(__name__)

# Columns a CSV must provide for a bulk worker import. Email is required (it is the dedup key
# and the DB declares workers.email NOT NULL UNIQUE); phone is required for SMS reminders.
REQUIRED_IMPORT_COLUMNS = ("first_name", "last_name", "email", "phone")

# Pydantic's own messages are written for developers. These are the ones a volunteer fixing a
# spreadsheet sees, keyed by the error "type" Pydantic reports.
_VALIDATION_MESSAGES = {
    "string_too_short": "Cannot be empty",
    "string_too_long": "Is too long (maximum 100 characters)",
    "value_error": "",  # Our own validators already raise a readable message; use it verbatim.
}


def _describe_validation_error(exc: ValidationError) -> tuple[str, str]:
    """Turn a Pydantic ValidationError into a (column, message) pair fit to show a user.

    Reports only the first failure for the row — a row with a bad email and a bad phone is fixed one
    cell at a time anyway, and listing every complaint at once makes the report harder to scan.

    Args:
        exc: The error raised while validating a WorkerImportRow.

    Returns:
        tuple[str, str]: The offending CSV column and a plain-English description of the problem.
    """
    error = exc.errors()[0]
    field = str(error["loc"][0]) if error["loc"] else "row"
    message = _VALIDATION_MESSAGES.get(str(error["type"]))
    if message:
        return field, message
    # Pydantic prefixes messages raised by a validator with "Value error, "; strip it.
    raw = str(error["msg"]).removeprefix("Value error, ")
    if field == "email" and str(error["type"]).startswith("value_error"):
        return field, f"'{error.get('input')}' is not a valid email address"
    return field, raw[:1].upper() + raw[1:]


class WorkerService:
    def __init__(
        self,
        worker_repo: WorkerRepository,
        department_repo: DepartmentRepository,
        schedule_repo: ScheduleRepository,
        client: Client,
    ) -> None:
        """Initialize the WorkerService with required repositories.

        Args:
            worker_repo: Repository for worker database operations.
            department_repo: Repository for department database operations.
            schedule_repo: Repository for schedule operations, used to check a worker's
                remaining commitments before deleting their profile.
            client: Supabase client (service-role) for syncing roles into auth app_metadata.
        """
        self.worker_repo = worker_repo
        self.department_repo = department_repo
        self.schedule_repo = schedule_repo
        self.client = client

        # bind the logger to the service name for structured logging
        self.logger = logger.bind(service="WorkerService")

    def _sync_role_to_auth(self, worker: WorkerResponse, roles: list[UserRole]) -> None:
        """Mirror the worker's most privileged role into their Supabase auth app_metadata.

        Roles are stored in the worker_app_roles table, but authorization reads the single role
        baked into the JWT (app_metadata.role). Without this sync, a role change would never take
        effect for a logged-in user. No-op for workers without a login account (auth_user_id None).

        Args:
            worker: The worker whose auth account should be synced.
            roles: The worker's complete current set of roles.

        Raises:
            AppError: If the Supabase admin update fails.
        """
        if not worker.auth_user_id:
            return
        role = highest_role(roles)
        log = self.logger.bind(method="_sync_role_to_auth", worker_id=str(worker.id), role=role)
        try:
            self.client.auth.admin.update_user_by_id(str(worker.auth_user_id), {"app_metadata": {"role": role}})
        except AuthApiError as exc:
            log.error("auth_role_sync_failed", error=str(exc))
            raise AppError(f"Failed to sync role to auth account: {exc}") from exc
        log.info("auth_role_synced")

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

        Checks both contact fields against existing workers before inserting. Email and phone are
        already normalized by WorkerCreate, so the comparison is case- and format-insensitive.

        Args:
            data: Worker creation data including name, contact info.

        Returns:
            WorkerResponse: The newly created worker.

        Raises:
            ConflictError: If a worker already exists with the same email or phone number.
        """
        # bind the method and email for better traceability in logs
        log = self.logger.bind(method="create_worker", email=mask_email(data.email))

        # Check both contact fields, not just whichever was supplied first: phone is the SMS
        # reminder key, so two workers sharing one number sends a person somebody else's reminders.
        if self.worker_repo.get_by_email(data.email):
            log.warning("worker_already_exists", conflict_field="email")
            raise ConflictError(f"A worker with email {data.email} already exists")
        if data.phone and self.worker_repo.get_by_phone(data.phone):
            log.warning("worker_already_exists", conflict_field="phone")
            raise ConflictError(f"A worker with phone number {data.phone} already exists")

        worker = self.worker_repo.create(data.model_dump())
        log.info("worker_created", worker_id=str(worker.id))
        return worker

    def import_workers(
        self,
        file_bytes: bytes,
        department_id: UUID,
        *,
        dry_run: bool,
        skip_duplicates: bool = False,
    ) -> WorkerImportResult:
        """Bulk-create workers from a CSV file and assign them to a department.

        All-or-nothing: the whole file is parsed and validated before anything is written, and a
        single invalid row rejects the entire import. This keeps a typo in one row from leaving a
        half-imported roster that nobody can tell apart from a complete one.

        Rows matching a worker who already exists are reported separately from validation errors,
        since re-uploading a roster is a normal thing to do and is not a mistake. They also block the
        import by default, but the caller can pass ``skip_duplicates`` to import the remainder — an
        explicit choice made after seeing the preview, not a silent skip.

        Args:
            file_bytes: Raw bytes of the uploaded CSV file.
            department_id: Department to assign newly created workers to.
            dry_run: If True, validate and report only — perform no writes.
            skip_duplicates: If True, already-existing workers no longer block the import; they are
                reported and passed over while the remaining rows are created.

        Returns:
            WorkerImportResult: Per-row outcomes plus aggregate counts. ``ok`` reports whether the
                import would proceed (dry run) or did proceed.

        Raises:
            NotFoundError: If the target department does not exist.
            BadRequestError: If the file is too large, not decodable, empty, missing required
                columns, or has more rows than ``settings.max_import_rows``.
            AppError: If the workers were created but assigning them to the department failed.
        """
        log = self.logger.bind(method="import_workers", department_id=str(department_id), dry_run=dry_run)

        # Fail fast on a bad target department before processing any rows.
        if not self.department_repo.get_by_id(department_id):
            log.warning("import_department_not_found")
            raise NotFoundError(f"Department {department_id} not found")

        rows = self._parse_import_rows(file_bytes)
        results, validated = self._validate_import_rows(rows)

        errors = sum(1 for r in results if r.status == "error")
        duplicates = sum(1 for r in results if r.status == "duplicate")
        duplicates_inactive = sum(1 for r in results if r.status == "duplicate_inactive")
        valid = [r for r in results if r.status == "valid"]

        # Validation errors always block. Duplicates block too, unless the caller has seen the
        # preview and explicitly opted to skip them.
        ok = errors == 0 and bool(valid) and (duplicates + duplicates_inactive == 0 or skip_duplicates)
        committed = ok and not dry_run

        if committed:
            self._commit_import(valid, validated, department_id)

        result = WorkerImportResult(
            dry_run=dry_run,
            ok=ok,
            total_rows=len(results),
            valid=0 if committed else len(valid),
            created=len(valid) if committed else 0,
            duplicates=duplicates,
            duplicates_inactive=duplicates_inactive,
            errors=errors,
            results=results,
        )
        log.info(
            "import_workers_complete",
            ok=result.ok,
            total=result.total_rows,
            created=result.created,
            valid=result.valid,
            duplicates=result.duplicates,
            duplicates_inactive=result.duplicates_inactive,
            errors=result.errors,
        )
        return result

    def _parse_import_rows(self, file_bytes: bytes) -> list[dict[str, str]]:
        """Decode and parse an import CSV into normalized, whitespace-trimmed row dicts.

        Failures here are whole-file problems, so they raise rather than producing row results.

        Args:
            file_bytes: Raw bytes of the uploaded CSV file.

        Returns:
            list[dict[str, str]]: One dict per data row, keys lowercased and values stripped.

        Raises:
            BadRequestError: If the file is too large, not UTF-8, empty, missing a required column,
                or exceeds the configured row limit.
        """
        if len(file_bytes) > settings.max_import_file_bytes:
            raise BadRequestError(
                f"CSV file is too large ({len(file_bytes) // 1024} KB); "
                f"the limit is {settings.max_import_file_bytes // 1024} KB"
            )

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

        # Normalize keys and trim whitespace; unmatched/extra columns are ignored.
        rows = [{(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()} for raw in reader]
        if not rows:
            raise BadRequestError("CSV file has a header row but no workers")
        if len(rows) > settings.max_import_rows:
            raise BadRequestError(f"CSV has {len(rows)} rows; the limit is {settings.max_import_rows} per import")
        return rows

    def _validate_import_rows(
        self, rows: list[dict[str, str]]
    ) -> tuple[list[WorkerImportRowResult], dict[int, WorkerImportRow]]:
        """Validate every parsed row against the schema, the rest of the file, and existing workers.

        Runs in full even once a row has failed, so the user sees every problem in one pass rather
        than fixing them one upload at a time.

        Args:
            rows: Parsed CSV rows from _parse_import_rows.

        Returns:
            tuple: The per-row results in file order, and the validated rows keyed by line number
                (only for rows that came out ``valid``).
        """
        # One query for the whole file instead of one per row.
        contact_index = self.worker_repo.get_contact_index()
        seen_emails: dict[str, int] = {}
        seen_phones: dict[str, int] = {}
        results: list[WorkerImportRowResult] = []
        validated: dict[int, WorkerImportRow] = {}

        for offset, row in enumerate(rows):
            # Line 1 of the spreadsheet is the header, so the first data row is line 2. Reporting the
            # row index instead would send the user to the wrong line in their file.
            line_number = offset + 2
            name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or None
            email = row.get("email") or None

            blanks = [col for col in REQUIRED_IMPORT_COLUMNS if not row.get(col)]
            if blanks:
                results.append(
                    WorkerImportRowResult(
                        line_number=line_number,
                        status="error",
                        name=name,
                        email=email,
                        field=blanks[0],
                        error=f"Missing value for: {', '.join(blanks)}",
                    )
                )
                continue

            try:
                data = WorkerImportRow(
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    email=row["email"],
                    phone=row["phone"],
                )
            except ValidationError as exc:
                field, message = _describe_validation_error(exc)
                results.append(
                    WorkerImportRowResult(
                        line_number=line_number,
                        status="error",
                        name=name,
                        email=email,
                        field=field,
                        value=row.get(field),
                        error=message,
                    )
                )
                continue

            # A repeat within the same file is a mistake in the file, not an already-imported worker.
            # It is an error the user must fix, and is never skippable — silently picking one of two
            # identical rows would be a coin flip over which one's details win.
            if (first_seen := seen_emails.get(data.email)) is not None:
                results.append(
                    WorkerImportRowResult(
                        line_number=line_number,
                        status="error",
                        name=name,
                        email=data.email,
                        field="email",
                        value=data.email,
                        error=f"Same email as line {first_seen} in this file",
                    )
                )
                continue
            if (first_seen := seen_phones.get(data.phone)) is not None:
                results.append(
                    WorkerImportRowResult(
                        line_number=line_number,
                        status="error",
                        name=name,
                        email=data.email,
                        field="phone",
                        value=data.phone,
                        error=f"Same phone number as line {first_seen} in this file",
                    )
                )
                continue
            seen_emails[data.email] = line_number
            seen_phones[data.phone] = line_number

            # Both keys are normalized on each side, so this catches "Jane@x.com" against an existing
            # "jane@x.com" and "(416) 555-0101" against an existing "+14165550101".
            existing = contact_index.get(data.email) or contact_index.get(data.phone)
            if existing:
                results.append(
                    WorkerImportRowResult(
                        line_number=line_number,
                        status="duplicate" if existing.is_active else "duplicate_inactive",
                        name=name,
                        email=data.email,
                        worker_id=existing.worker_id,
                        error=(
                            "Already in the system"
                            if existing.is_active
                            else "Already in the system but deactivated — reactivate them instead of re-importing"
                        ),
                    )
                )
                continue

            validated[line_number] = data
            results.append(WorkerImportRowResult(line_number=line_number, status="valid", name=name, email=data.email))

        return results, validated

    def _commit_import(
        self,
        valid: list[WorkerImportRowResult],
        validated: dict[int, WorkerImportRow],
        department_id: UUID,
    ) -> None:
        """Create the validated workers, assign them to the department, and mark the rows created.

        Two batched statements rather than two per row. Each is atomic on its own, so if the
        membership insert fails the just-created workers are deleted to undo the first half — the
        import must never leave workers who belong to no department, since no HOD can then see them.

        Args:
            valid: The rows that passed validation, mutated in place to ``created``.
            validated: The validated row data, keyed by line number.
            department_id: Department to assign the new workers to.

        Raises:
            AppError: If the department assignment failed. The worker creation is rolled back first.
        """
        log = self.logger.bind(method="_commit_import", department_id=str(department_id), count=len(valid))

        created = self.worker_repo.create_many([validated[r.line_number].model_dump() for r in valid])
        created_by_email = {worker.email.lower(): worker for worker in created}

        try:
            self.department_repo.assign_workers(department_id, [worker.id for worker in created])
        except Exception as exc:
            log.error("import_assign_failed_rolling_back", error=str(exc))
            try:
                self.worker_repo.delete_many([worker.id for worker in created])
            except Exception as cleanup_exc:
                # Both halves failed: the workers exist but belong to no department and could not be
                # removed. Log the ids so they can be cleaned up by hand.
                log.error(
                    "import_rollback_failed",
                    error=str(cleanup_exc),
                    orphaned_worker_ids=[str(worker.id) for worker in created],
                )
            raise AppError("Workers could not be assigned to the department, so no changes were saved") from exc

        for result in valid:
            worker = created_by_email.get((result.email or "").lower())
            result.status = "created"
            result.worker_id = worker.id if worker else None
        log.info("import_committed", created_count=len(created))

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
            # Re-read the persisted roles and mirror the highest into the auth JWT so the
            # change actually takes effect for a worker who has a login account.
            self._sync_role_to_auth(worker, self.worker_repo.get_worker_roles(worker_id))
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

    def delete_worker(self, worker_id: UUID) -> None:
        """Permanently delete a worker profile and revoke their login.

        This is irreversible. Deleting the row cascades away the worker's roles, department and
        subteam memberships, assistant-HOD assignments, availability, confirmation tokens and
        *past* schedule assignments, and nulls ``schedules.created_by`` on schedules they created.
        Three guards keep that from happening by accident:

        1. The worker must already be deactivated, so deletion is always a deliberate second step.
        2. They must have no assignments on or after today, since deleting those would silently
           leave holes in schedules that have already been published.
        3. They must not head a department, because the FK would null ``departments.hod_id`` and
           leave that department without a head.

        The login is revoked before the row is deleted. ``workers.auth_user_id`` references
        ``auth.users`` with ``on delete set null``, so if the row delete then fails the profile is
        left deactivated and login-less and the caller can simply retry. The reverse order would
        strand an auth user that can still sign in but has no profile and no way to be cleaned up.

        Args:
            worker_id: Unique identifier of the worker to delete.

        Raises:
            NotFoundError: If the worker does not exist.
            BadRequestError: If the worker is still active.
            ConflictError: If the worker has upcoming assignments or heads a department.
            AppError: If revoking the login or deleting the row fails.
        """
        log = self.logger.bind(method="delete_worker", worker_id=str(worker_id))
        worker = self.get_worker(worker_id)

        if worker.is_active:
            raise BadRequestError("Deactivate this worker before deleting their profile.")

        upcoming = self.schedule_repo.get_upcoming_assignments_for_worker(worker_id, date.today())
        if upcoming:
            log.info("worker_delete_blocked_by_assignments", count=len(upcoming))
            raise ConflictError(
                f"This worker has {len(upcoming)} upcoming schedule "
                f"{'assignment' if len(upcoming) == 1 else 'assignments'}. "
                "Remove or reassign them before deleting the profile."
            )

        headed = self.department_repo.get_departments_by_hod(worker_id)
        if headed:
            names = ", ".join(department.name for department in headed)
            log.info("worker_delete_blocked_by_hod_role", departments=names)
            raise ConflictError(
                f"This worker is the head of {names}. Assign a new department head before deleting the profile."
            )

        # Revoke the login first — see the ordering rationale in this method's docstring.
        if worker.auth_user_id:
            try:
                self.client.auth.admin.delete_user(str(worker.auth_user_id))
            except AuthApiError as exc:
                log.error("worker_login_revocation_failed", error=str(exc))
                raise AppError(f"Failed to revoke the worker's login: {exc}") from exc
            log.info("worker_login_revoked")

        if not self.worker_repo.delete(worker_id):
            log.error("worker_deletion_failed")
            raise AppError(f"Failed to delete worker {worker_id}")
        log.info("worker_deleted", email=mask_email(worker.email))

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

    def get_worker_assistant_hod_departments(self, worker_id: UUID) -> list[DepartmentResponse]:
        """Retrieve the departments a worker manages as assistant HOD.

        Distinct from get_worker_departments (membership): this returns the department_assistant_hods
        assignments, used to pre-populate the assistant-HOD department picker when editing roles.

        Args:
            worker_id: Unique identifier of the worker.

        Returns:
            list[DepartmentResponse]: Departments the worker is an assistant HOD of.
        """
        log = self.logger.bind(method="get_worker_assistant_hod_departments", worker_id=str(worker_id))
        departments = self.department_repo.get_assistant_hod_departments(worker_id)
        log.info("fetched_worker_assistant_hod_departments", count=len(departments))
        return departments

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

        The self-check comes first for the same reason as ``authorize_act_for_worker``: routed
        through the department branch, an HOD fails ``can_manage_worker(actor.id, actor.id)``
        unless they happen to also be a member of a department they lead, and is refused on their
        own record.

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
        if worker_id == actor.id:
            return
        if token.role in (UserRole.HOD, UserRole.ASSISTANT_HOD):
            if self.can_manage_worker(actor.id, worker_id):
                return
            raise PermissionDeniedError("You can only view workers in departments you manage")
        # Regular workers may only view their own record.
        if worker_id != actor.id:
            raise PermissionDeniedError("You can only view your own worker record")

    def authorize_act_for_worker(self, token: TokenPayload, worker_id: UUID, subject: str) -> None:
        """Ensure the requesting user may act on the given worker's behalf.

        Anyone may act on themselves; admins may act on anyone; HODs and assistant HODs may act on
        workers in the departments they manage. Used for the things a worker owns about themselves —
        their availability, and confirming or declining their own assignments.

        The self-check comes first on purpose. Routed through the department branch, an HOD failed
        ``can_manage_worker(actor.id, actor.id)`` unless they happened to also be a member of a
        department they lead, so they were refused on their own record.

        Args:
            token: The verified token payload of the requesting user.
            worker_id: The worker being acted on.
            subject: What is being acted on, for the error message, e.g. "availability".

        Raises:
            PermissionDeniedError: If the user is not allowed to act on this worker.
            BadRequestError/NotFoundError: If the actor's worker profile cannot be resolved.
        """
        if token.role == UserRole.ADMIN:
            return
        actor = self.get_worker_for_token(token)
        if worker_id == actor.id:
            return
        if token.role in (UserRole.HOD, UserRole.ASSISTANT_HOD):
            if self.can_manage_worker(actor.id, worker_id):
                return
            raise PermissionDeniedError(f"You can only manage {subject} for workers in departments you manage")
        raise PermissionDeniedError(f"You can only manage your own {subject}")

    def authorize_manage_availability(self, token: TokenPayload, worker_id: UUID) -> None:
        """Ensure the requesting user may read or change the given worker's availability.

        Args:
            token: The verified token payload of the requesting user.
            worker_id: The worker whose availability is being read or written.

        Raises:
            PermissionDeniedError: If the user is not allowed to act on this worker.
            BadRequestError/NotFoundError: If the actor's worker profile cannot be resolved.
        """
        self.authorize_act_for_worker(token, worker_id, subject="availability")

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
