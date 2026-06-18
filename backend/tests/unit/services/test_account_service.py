from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from supabase_auth.errors import AuthApiError

from app.core.exceptions import BadRequestError
from app.schemas.account.models import AccountProfileUpdate
from app.schemas.models import TokenPayload, UserRole
from app.schemas.workers.models import WorkerUpdate
from app.service.account.service import AccountService
from app.service.workers.service import WorkerService
from tests.unit.services.conftest import make_worker

MODULE = "app.service.account.service"


def make_token(email: str | None = "john.doe@example.com") -> TokenPayload:
    return TokenPayload(sub=str(uuid4()), role=UserRole.WORKER, email=email)


@pytest.fixture
def mock_worker_service():
    return MagicMock(spec=WorkerService)


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def service(mock_worker_service, mock_client):
    return AccountService(worker_service=mock_worker_service, client=mock_client)


class TestGetProfile:
    def test_returns_own_profile_with_roles(self, service, mock_worker_service):
        worker = make_worker()
        mock_worker_service.get_worker_for_token.return_value = worker
        mock_worker_service.get_worker.return_value = worker
        token = make_token(worker.email)

        result = service.get_profile(token)

        assert result is worker
        mock_worker_service.get_worker_for_token.assert_called_once_with(token)
        mock_worker_service.get_worker.assert_called_once_with(worker.id)


class TestUpdateProfile:
    def test_only_forwards_name_and_phone(self, service, mock_worker_service):
        worker = make_worker()
        mock_worker_service.get_worker_for_token.return_value = worker
        mock_worker_service.update_worker.return_value = worker
        token = make_token(worker.email)

        service.update_profile(
            token,
            AccountProfileUpdate(first_name="Jane", last_name="Smith", phone="+14165550199"),
        )

        mock_worker_service.update_worker.assert_called_once()
        called_id, called_update = mock_worker_service.update_worker.call_args.args
        assert called_id == worker.id
        assert isinstance(called_update, WorkerUpdate)
        assert called_update.first_name == "Jane"
        assert called_update.phone == "+14165550199"
        # Self-service must never be able to change these.
        assert called_update.email is None
        assert called_update.roles is None
        assert called_update.assistant_hod_departments is None


class TestChangePassword:
    def test_updates_password_when_current_is_correct(self, service, mock_worker_service, mock_client):
        token = make_token()
        verifier = MagicMock()
        with patch(f"{MODULE}.create_client", return_value=verifier) as create_client:
            service.change_password(token, "old-password", "new-password-123")

        create_client.assert_called_once()
        verifier.auth.sign_in_with_password.assert_called_once_with({"email": token.email, "password": "old-password"})
        mock_client.auth.admin.update_user_by_id.assert_called_once_with(token.sub, {"password": "new-password-123"})

    def test_raises_and_skips_update_when_current_is_wrong(self, service, mock_client):
        token = make_token()
        verifier = MagicMock()
        verifier.auth.sign_in_with_password.side_effect = AuthApiError(
            "Invalid login credentials", 400, "invalid_credentials"
        )
        with patch(f"{MODULE}.create_client", return_value=verifier):
            with pytest.raises(BadRequestError):
                service.change_password(token, "wrong-password", "new-password-123")

        mock_client.auth.admin.update_user_by_id.assert_not_called()

    def test_raises_when_token_has_no_email(self, service):
        token = make_token(email=None)
        with pytest.raises(BadRequestError):
            service.change_password(token, "old", "new-password-123")


class TestDeleteAccount:
    def test_deactivates_worker_and_deletes_auth_user(self, service, mock_worker_service, mock_client):
        worker = make_worker()
        mock_worker_service.get_worker_for_token.return_value = worker
        token = make_token(worker.email)

        service.delete_account(token)

        mock_worker_service.deactivate_worker.assert_called_once_with(worker.id)
        mock_client.auth.admin.delete_user.assert_called_once_with(token.sub)
