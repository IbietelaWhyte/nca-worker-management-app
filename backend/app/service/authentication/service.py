from uuid import UUID

from supabase import Client
from supabase_auth.errors import AuthApiError

from app.core.logging import get_logger
from app.repository.workers.repository import WorkerRepository
from app.schemas.authentication.models import RegisterRequest, RegisterResponse
from app.schemas.models import UserRole
from app.schemas.workers.models import WorkerResponse

logger = get_logger(__name__)


class AuthenticationService:
    def __init__(self, client: Client, worker_repo: WorkerRepository) -> None:
        self.client = client
        self.worker_repo = worker_repo

    def register_worker(self, data: RegisterRequest) -> RegisterResponse:
        """
        Registers a new worker. Admin only.

        Steps:
        1. Create auth.users entry via Supabase Admin API
        2. Create workers row linked via auth_user_id
        3. Assign default 'worker' role in worker_app_roles
        4. On any failure, attempt to clean up the auth user to avoid orphans
        """
        logger.info("worker_registration_started", email=data.email)

        # 1. Create Supabase auth user
        auth_user_id = self._create_auth_user(data)

        # 2 & 3. Create worker row + assign role
        # If this fails we clean up the auth user
        try:
            worker = self._create_worker_record(auth_user_id, data)
            self._assign_default_role(worker.id)
        except Exception as e:
            logger.error(
                "worker_record_creation_failed",
                email=data.email,
                auth_user_id=str(auth_user_id),
                error=str(e),
            )
            self._cleanup_auth_user(auth_user_id)
            raise ValueError(f"Failed to create worker record: {e}") from e

        logger.info(
            "worker_registration_completed",
            worker_id=str(worker.id),
            email=data.email,
        )

        return RegisterResponse(
            message="Worker registered successfully",
            worker_id=str(worker.id),
            email=data.email,
        )

    def _create_auth_user(self, data: RegisterRequest) -> UUID:
        """Creates the Supabase auth user and returns the auth_user_id."""
        try:
            response = self.client.auth.admin.create_user(
                {
                    "email": data.email,
                    "password": data.password,
                    "email_confirm": True,  # skip confirmation email for admin-created accounts
                    "app_metadata": {"role": UserRole.WORKER},
                }
            )
            auth_user_id = response.user.id
            logger.info("auth_user_created", auth_user_id=auth_user_id, email=data.email)
            return UUID(auth_user_id)
        except AuthApiError as e:
            logger.warning("auth_user_creation_failed", email=data.email, error=str(e))
            if "already registered" in str(e).lower():
                raise ValueError(f"Email {data.email} is already registered") from e
            raise ValueError(f"Failed to create auth user: {e}") from e

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

    def _assign_default_role(self, worker_id: UUID) -> None:
        """Inserts the default worker role into worker_app_roles."""
        self.client.table("worker_app_roles").insert(
            {
                "worker_id": str(worker_id),
                "role": UserRole.WORKER,
            }
        ).execute()
        logger.info("default_role_assigned", worker_id=str(worker_id))

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
