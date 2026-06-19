from uuid import uuid4

import pytest
from supabase_auth.errors import AuthApiError

from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError
from app.schemas.authentication.models import GrantAccountRequest
from app.schemas.models import UserRole
from tests.unit.services.conftest import make_auth_user, make_register_request, make_worker


class TestRegisterWorker:
    def test_registers_successfully(self, service, mock_supabase_client, mock_worker_repo):
        auth_user_id = str(uuid4())
        worker = make_worker()
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user(auth_user_id)
        mock_worker_repo.create.return_value = worker

        result = service.register_worker(make_register_request())

        assert result.worker_id == str(worker.id)
        assert result.email == "john.doe@example.com"
        mock_supabase_client.auth.admin.create_user.assert_called_once()
        mock_worker_repo.create.assert_called_once()

    def test_assigns_default_worker_role(self, service, mock_supabase_client, mock_worker_repo):
        auth_user_id = str(uuid4())
        worker = make_worker()
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user(auth_user_id)
        mock_worker_repo.create.return_value = worker

        service.register_worker(make_register_request())

        mock_supabase_client.table.assert_called_with("worker_app_roles")
        insert_call = mock_supabase_client.table.return_value.insert.call_args[0][0]
        assert insert_call["role"] == "worker"
        assert insert_call["worker_id"] == str(worker.id)

    def test_raises_on_duplicate_email(self, service, mock_supabase_client):
        mock_supabase_client.auth.admin.create_user.side_effect = AuthApiError(
            message="User already registered", status=422, code="identity_already_exists"
        )
        with pytest.raises(ConflictError, match="already registered"):
            service.register_worker(make_register_request())

    def test_cleans_up_auth_user_when_worker_creation_fails(self, service, mock_supabase_client, mock_worker_repo):
        """If the workers row insert fails, the auth user should be deleted."""
        auth_user_id = str(uuid4())
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user(auth_user_id)
        mock_worker_repo.create.side_effect = Exception("DB error")

        with pytest.raises(AppError, match="Failed to create worker record"):
            service.register_worker(make_register_request())

        mock_supabase_client.auth.admin.delete_user.assert_called_once_with(auth_user_id)

    def test_continues_if_cleanup_also_fails(self, service, mock_supabase_client, mock_worker_repo):
        """Cleanup failure should not mask the original error."""
        auth_user_id = str(uuid4())
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user(auth_user_id)
        mock_worker_repo.create.side_effect = Exception("DB error")
        mock_supabase_client.auth.admin.delete_user.side_effect = Exception("Cleanup failed")

        # Should still raise the original error, not the cleanup error
        with pytest.raises(AppError, match="Failed to create worker record"):
            service.register_worker(make_register_request())

    def test_email_confirm_is_true_for_admin_created_accounts(self, service, mock_supabase_client, mock_worker_repo):
        """Admin-created accounts should skip email confirmation."""
        worker = make_worker()
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user()
        mock_worker_repo.create.return_value = worker

        service.register_worker(make_register_request())

        create_user_args = mock_supabase_client.auth.admin.create_user.call_args[0][0]
        assert create_user_args["email_confirm"] is True


class TestCreateAccountForWorker:
    def test_creates_account_and_links_worker(self, service, mock_supabase_client, mock_worker_repo):
        auth_user_id = str(uuid4())
        worker = make_worker(auth_user_id=None)
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = []
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user(auth_user_id)

        result = service.create_account_for_worker(
            worker.id, GrantAccountRequest(password="securepass1", role=UserRole.ADMIN)
        )

        assert result.worker_id == str(worker.id)
        # Auth user gets the chosen role in app_metadata.
        create_user_args = mock_supabase_client.auth.admin.create_user.call_args[0][0]
        assert create_user_args["app_metadata"] == {"role": UserRole.ADMIN}
        assert create_user_args["email"] == worker.email
        # Worker row is linked to the new auth user.
        mock_worker_repo.update.assert_called_once_with(worker.id, {"auth_user_id": auth_user_id})
        # Role is recorded in worker_app_roles.
        insert_call = mock_supabase_client.table.return_value.insert.call_args[0][0]
        assert insert_call["role"] == UserRole.ADMIN

    def test_assigns_assistant_hod_departments(
        self, service, mock_supabase_client, mock_worker_repo, mock_department_repo
    ):
        worker = make_worker(auth_user_id=None)
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = []
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user()
        mock_department_repo.get_assistant_hod_department_ids.return_value = []
        dept1, dept2 = uuid4(), uuid4()

        service.create_account_for_worker(
            worker.id,
            GrantAccountRequest(
                password="securepass1", role=UserRole.ASSISTANT_HOD, assistant_hod_departments=[dept1, dept2]
            ),
        )

        assert mock_department_repo.assign_assistant_hod.call_count == 2
        mock_department_repo.assign_assistant_hod.assert_any_call(worker.id, dept1)
        mock_department_repo.assign_assistant_hod.assert_any_call(worker.id, dept2)

    def test_skips_already_assigned_assistant_hod_departments(
        self, service, mock_supabase_client, mock_worker_repo, mock_department_repo
    ):
        worker = make_worker(auth_user_id=None)
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = [UserRole.ASSISTANT_HOD]
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user()
        dept1, dept2 = uuid4(), uuid4()
        mock_department_repo.get_assistant_hod_department_ids.return_value = [dept1]

        service.create_account_for_worker(
            worker.id,
            GrantAccountRequest(
                password="securepass1", role=UserRole.ASSISTANT_HOD, assistant_hod_departments=[dept1, dept2]
            ),
        )

        mock_department_repo.assign_assistant_hod.assert_called_once_with(worker.id, dept2)

    def test_ignores_departments_for_non_assistant_hod_role(
        self, service, mock_supabase_client, mock_worker_repo, mock_department_repo
    ):
        worker = make_worker(auth_user_id=None)
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = []
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user()

        service.create_account_for_worker(
            worker.id,
            GrantAccountRequest(password="securepass1", role=UserRole.WORKER, assistant_hod_departments=[uuid4()]),
        )

        mock_department_repo.assign_assistant_hod.assert_not_called()

    def test_does_not_duplicate_existing_role(self, service, mock_supabase_client, mock_worker_repo):
        worker = make_worker(auth_user_id=None)
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = [UserRole.WORKER]
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user()

        service.create_account_for_worker(worker.id, GrantAccountRequest(password="securepass1"))

        mock_supabase_client.table.return_value.insert.assert_not_called()

    def test_raises_when_worker_not_found(self, service, mock_worker_repo):
        mock_worker_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.create_account_for_worker(uuid4(), GrantAccountRequest(password="securepass1"))

    def test_raises_when_already_has_account(self, service, mock_worker_repo):
        worker = make_worker(auth_user_id=uuid4())
        mock_worker_repo.get_by_id.return_value = worker
        with pytest.raises(ConflictError, match="already has a login account"):
            service.create_account_for_worker(worker.id, GrantAccountRequest(password="securepass1"))

    def test_raises_when_no_email(self, service, mock_worker_repo):
        worker = make_worker(auth_user_id=None, email=None)
        mock_worker_repo.get_by_id.return_value = worker
        with pytest.raises(BadRequestError, match="must have an email"):
            service.create_account_for_worker(worker.id, GrantAccountRequest(password="securepass1"))

    def test_cleans_up_auth_user_when_linking_fails(self, service, mock_supabase_client, mock_worker_repo):
        auth_user_id = str(uuid4())
        worker = make_worker(auth_user_id=None)
        mock_worker_repo.get_by_id.return_value = worker
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user(auth_user_id)
        mock_worker_repo.update.side_effect = Exception("DB error")

        with pytest.raises(AppError, match="Failed to link account"):
            service.create_account_for_worker(worker.id, GrantAccountRequest(password="securepass1"))

        mock_supabase_client.auth.admin.delete_user.assert_called_once_with(auth_user_id)
