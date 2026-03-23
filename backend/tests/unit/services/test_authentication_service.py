from uuid import uuid4

import pytest
from supabase_auth.errors import AuthApiError

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
        with pytest.raises(ValueError, match="already registered"):
            service.register_worker(make_register_request())

    def test_cleans_up_auth_user_when_worker_creation_fails(self, service, mock_supabase_client, mock_worker_repo):
        """If the workers row insert fails, the auth user should be deleted."""
        auth_user_id = str(uuid4())
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user(auth_user_id)
        mock_worker_repo.create.side_effect = Exception("DB error")

        with pytest.raises(ValueError, match="Failed to create worker record"):
            service.register_worker(make_register_request())

        mock_supabase_client.auth.admin.delete_user.assert_called_once_with(auth_user_id)

    def test_continues_if_cleanup_also_fails(self, service, mock_supabase_client, mock_worker_repo):
        """Cleanup failure should not mask the original error."""
        auth_user_id = str(uuid4())
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user(auth_user_id)
        mock_worker_repo.create.side_effect = Exception("DB error")
        mock_supabase_client.auth.admin.delete_user.side_effect = Exception("Cleanup failed")

        # Should still raise the original error, not the cleanup error
        with pytest.raises(ValueError, match="Failed to create worker record"):
            service.register_worker(make_register_request())

    def test_email_confirm_is_true_for_admin_created_accounts(self, service, mock_supabase_client, mock_worker_repo):
        """Admin-created accounts should skip email confirmation."""
        worker = make_worker()
        mock_supabase_client.auth.admin.create_user.return_value = make_auth_user()
        mock_worker_repo.create.return_value = worker

        service.register_worker(make_register_request())

        create_user_args = mock_supabase_client.auth.admin.create_user.call_args[0][0]
        assert create_user_args["email_confirm"] is True
