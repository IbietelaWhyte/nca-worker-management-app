from supabase import Client, create_client
from supabase_auth.errors import AuthApiError

from app.core.config import settings
from app.core.exceptions import AppError, BadRequestError
from app.core.logging import get_logger
from app.core.redaction import mask_email
from app.schemas.account.models import AccountProfileUpdate
from app.schemas.models import TokenPayload
from app.schemas.workers.models import WorkerResponse, WorkerUpdate
from app.service.workers.service import WorkerService

logger = get_logger(__name__)


class AccountService:
    """Self-service account operations scoped to the authenticated user.

    A thin wrapper over ``WorkerService`` (which resolves and mutates the caller's own worker
    record) plus the privileged Supabase client for auth-user operations (password, deletion).
    """

    def __init__(self, worker_service: WorkerService, client: Client) -> None:
        """Initialize the AccountService.

        Args:
            worker_service: Service used to resolve and update the caller's own worker record.
            client: Supabase client (service-role) for privileged auth admin operations.
        """
        self.worker_service = worker_service
        self.client = client
        self.logger = logger.bind(service="AccountService")

    def get_profile(self, token: TokenPayload) -> WorkerResponse:
        """Return the authenticated user's own worker profile, with roles attached.

        Args:
            token: The verified token payload of the requesting user.

        Returns:
            WorkerResponse: The caller's worker record including roles.
        """
        worker = self.worker_service.get_worker_for_token(token)
        # get_worker re-fetches by id and attaches the worker's roles for display.
        return self.worker_service.get_worker(worker.id)

    def update_profile(self, token: TokenPayload, data: AccountProfileUpdate) -> WorkerResponse:
        """Update the authenticated user's own profile fields (name, phone).

        Args:
            token: The verified token payload of the requesting user.
            data: The profile fields to change.

        Returns:
            WorkerResponse: The updated worker record.
        """
        worker = self.worker_service.get_worker_for_token(token)
        log = self.logger.bind(method="update_profile", worker_id=str(worker.id))
        # Restrict the update to the three self-editable fields; never forward roles/email/etc.
        update = WorkerUpdate(
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
        )
        updated = self.worker_service.update_worker(worker.id, update)
        log.info("profile_updated")
        return updated

    def change_password(self, token: TokenPayload, current_password: str, new_password: str) -> None:
        """Change the authenticated user's password after verifying the current one.

        The current password is verified by attempting a sign-in with a short-lived anon-key
        client (the service-role client is for admin operations, not credential checks). On
        success the password is updated via the Supabase admin API.

        Args:
            token: The verified token payload of the requesting user.
            current_password: The user's existing password, for verification.
            new_password: The new password to set.

        Raises:
            BadRequestError: If the token carries no email or the current password is incorrect.
            AppError: If the password update fails.
        """
        if not token.email:
            raise BadRequestError("Email not found in authentication token")
        log = self.logger.bind(method="change_password", email=mask_email(token.email))

        # Verify the current password without mutating the live (service-role) client's session.
        verifier = create_client(settings.supabase_url, settings.supabase_anon_key)
        try:
            verifier.auth.sign_in_with_password({"email": token.email, "password": current_password})
        except AuthApiError as exc:
            log.warning("current_password_incorrect")
            raise BadRequestError("Current password is incorrect") from exc
        finally:
            try:
                verifier.auth.sign_out()
            except Exception:  # best-effort cleanup of the throwaway session
                pass

        try:
            self.client.auth.admin.update_user_by_id(token.sub, {"password": new_password})
        except AuthApiError as exc:
            log.error("password_update_failed", error=str(exc))
            raise AppError(f"Failed to update password: {exc}") from exc
        log.info("password_changed")

    def delete_account(self, token: TokenPayload) -> None:
        """Soft-delete the authenticated user's account and revoke their login.

        Deactivates the worker record (preserving schedule/availability history) and deletes the
        Supabase auth user so they can no longer sign in. The ``auth_user_id`` FK is nulled
        automatically via ``on delete set null``.

        Args:
            token: The verified token payload of the requesting user.

        Raises:
            AppError: If revoking the auth login fails.
        """
        worker = self.worker_service.get_worker_for_token(token)
        log = self.logger.bind(method="delete_account", worker_id=str(worker.id))

        # 1. Preserve history: deactivate rather than cascade-delete the worker row.
        self.worker_service.deactivate_worker(worker.id)

        # 2. Revoke login by deleting the auth user (also nulls workers.auth_user_id via FK).
        try:
            self.client.auth.admin.delete_user(token.sub)
        except AuthApiError as exc:
            log.error("auth_user_deletion_failed", error=str(exc))
            raise AppError(f"Failed to delete account login: {exc}") from exc
        log.info("account_deleted")
