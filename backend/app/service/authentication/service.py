from uuid import UUID

from supabase import Client
from supabase_auth.errors import AuthApiError

from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.redaction import mask_email
from app.repository.departments.repository import DepartmentRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.authentication.models import GrantAccountRequest, RegisterRequest, RegisterResponse
from app.schemas.models import UserRole
from app.schemas.workers.models import WorkerResponse

logger = get_logger(__name__)


class AuthenticationService:
    def __init__(self, client: Client, worker_repo: WorkerRepository, department_repo: DepartmentRepository) -> None:
        self.client = client
        self.worker_repo = worker_repo
        self.department_repo = department_repo

    def register_worker(self, data: RegisterRequest) -> RegisterResponse:
        """
        Registers a new worker. Admin only.

        Steps:
        1. Create auth.users entry via Supabase Admin API
        2. Create workers row linked via auth_user_id
        3. Assign specified role (from data.role) in worker_app_roles
        4. Assign to departments if provided
        5. On any failure, attempt to clean up the auth user to avoid orphans
        """
        logger.info("worker_registration_started", email=mask_email(data.email), role=data.role)

        # 1. Create Supabase auth user
        auth_user_id = self._create_auth_user(data.email, data.password, data.role)

        # 2, 3 & 4. Create worker row + assign role + assign departments
        # If this fails we clean up the auth user
        try:
            worker = self._create_worker_record(auth_user_id, data)
            self._assign_role(worker.id, data.role)

            # Assign to departments if provided
            if data.department_ids:
                for department_id in data.department_ids:
                    self.department_repo.assign_worker(UUID(department_id), worker.id)
                    if data.role == UserRole.ASSISTANT_HOD:
                        self.department_repo.assign_assistant_hod(worker.id, UUID(department_id))
                logger.info("departments_assigned", worker_id=str(worker.id), department_ids=data.department_ids)
        except Exception as e:
            logger.error(
                "worker_record_creation_failed",
                email=mask_email(data.email),
                auth_user_id=str(auth_user_id),
                error=str(e),
            )
            self._cleanup_auth_user(auth_user_id)
            raise AppError(f"Failed to create worker record: {e}") from e

        logger.info(
            "worker_registration_completed",
            worker_id=str(worker.id),
            email=mask_email(data.email),
            role=data.role,
        )

        return RegisterResponse(
            message="Worker registered successfully",
            worker_id=str(worker.id),
            email=data.email,
        )

    def _create_auth_user(self, email: str, password: str, role: UserRole) -> UUID:
        """Creates the Supabase auth user and returns the auth_user_id."""
        try:
            response = self.client.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,  # skip confirmation email for admin-created accounts
                    "app_metadata": {"role": role},
                }
            )
            auth_user_id = response.user.id
            logger.info("auth_user_created", auth_user_id=auth_user_id, email=mask_email(email), role=role)
            return UUID(auth_user_id)
        except AuthApiError as e:
            logger.warning("auth_user_creation_failed", email=mask_email(email), error=str(e))
            if "already registered" in str(e).lower():
                raise ConflictError(f"Email {email} is already registered") from e
            raise AppError(f"Failed to create auth user: {e}") from e

    def create_account_for_worker(self, worker_id: UUID, data: GrantAccountRequest) -> RegisterResponse:
        """Give an existing worker profile a Supabase login account. Admin only.

        Workers created as bare profiles (via "Add Worker Profile") have no auth_user_id and cannot
        sign in. This creates a Supabase auth user, links it to the existing worker row, and ensures
        the chosen role is recorded in both worker_app_roles and the JWT app_metadata.

        Args:
            worker_id: The existing worker to grant an account to.
            data: The initial password and role for the new account.

        Returns:
            RegisterResponse: Confirmation with the worker id and email.

        Raises:
            NotFoundError: If the worker does not exist.
            ConflictError: If the worker already has a login account.
            BadRequestError: If the worker has no email (the login identity).
            AppError: If linking the account fails after the auth user was created.
        """
        worker = self.worker_repo.get_by_id(worker_id)
        if not worker:
            raise NotFoundError(f"Worker {worker_id} not found")
        log = logger.bind(method="create_account_for_worker", worker_id=str(worker_id))
        if worker.auth_user_id:
            log.warning("worker_already_has_account")
            raise ConflictError("Worker already has a login account")
        if not worker.email:
            log.warning("worker_missing_email")
            raise BadRequestError("Worker must have an email before an account can be created")

        # 1. Create the Supabase auth user (sets app_metadata.role for the JWT).
        auth_user_id = self._create_auth_user(worker.email, data.password, data.role)

        # 2. Link the auth user to the worker row and record the role. Clean up on any failure.
        try:
            self.worker_repo.update(worker_id, {"auth_user_id": str(auth_user_id)})
            if data.role not in self.worker_repo.get_worker_roles(worker_id):
                self._assign_role(worker_id, data.role)
            # An assistant_hod only manages departments via department_assistant_hods rows; the role
            # alone grants nothing. Assign the chosen departments so the access actually applies.
            if data.role == UserRole.ASSISTANT_HOD and data.assistant_hod_departments:
                existing = set(self.department_repo.get_assistant_hod_department_ids(worker_id))
                for department_id in data.assistant_hod_departments:
                    if department_id not in existing:
                        self.department_repo.assign_assistant_hod(worker_id, department_id)
                log.info("assistant_hod_departments_assigned", departments=data.assistant_hod_departments)
        except Exception as e:
            log.error("account_link_failed", auth_user_id=str(auth_user_id), error=str(e))
            self._cleanup_auth_user(auth_user_id)
            raise AppError(f"Failed to link account to worker: {e}") from e

        log.info("account_created_for_worker", auth_user_id=str(auth_user_id), role=data.role)
        return RegisterResponse(
            message="Account created successfully",
            worker_id=str(worker_id),
            email=worker.email,
        )

    def _create_worker_record(self, auth_user_id: UUID, data: RegisterRequest) -> WorkerResponse:
        """Inserts a row into the workers table linked to the auth user."""
        return self.worker_repo.create(
            {
                "auth_user_id": str(auth_user_id),
                "first_name": data.first_name,
                "last_name": data.last_name,
                "email": data.email,
                "phone": data.phone,
                "is_active": True,
            }
        )

    def _assign_role(self, worker_id: UUID, role: UserRole) -> None:
        """Inserts the specified role into worker_app_roles."""
        self.client.table("worker_app_roles").insert(
            {
                "worker_id": str(worker_id),
                "role": role,
            }
        ).execute()
        logger.info("role_assigned", worker_id=str(worker_id), role=role)

    def _cleanup_auth_user(self, auth_user_id: UUID) -> None:
        """
        Deletes the auth user if worker record creation fails.
        Prevents orphaned auth users with no corresponding worker row.
        """
        try:
            self.client.auth.admin.delete_user(str(auth_user_id))
            logger.info("auth_user_cleanup_successful", auth_user_id=str(auth_user_id))
        except Exception as e:
            # Log but don't raise — the original error is more important
            logger.error(
                "auth_user_cleanup_failed",
                auth_user_id=str(auth_user_id),
                error=str(e),
            )
