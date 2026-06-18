from app.core.exceptions import BadRequestError
from app.schemas.models import UserRole
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_worker


class TestGetMyProfile:
    def test_returns_200_for_authenticated_worker(self, mock_account_service):
        worker = make_worker()
        mock_account_service.get_profile.return_value = worker
        client = make_client(role=UserRole.WORKER, account_service=mock_account_service)

        response = client.get("/api/v1/account/me")
        assert response.status_code == 200
        assert response.json()["email"] == worker.email


class TestUpdateMyProfile:
    def test_updates_own_profile(self, mock_account_service):
        worker = make_worker(first_name="Jane")
        mock_account_service.update_profile.return_value = worker
        client = make_client(role=UserRole.WORKER, account_service=mock_account_service)

        response = client.patch("/api/v1/account/me", json={"first_name": "Jane", "phone": "+14165550199"})
        assert response.status_code == 200
        assert response.json()["first_name"] == "Jane"
        mock_account_service.update_profile.assert_called_once()

    def test_ignores_email_and_role_fields(self, mock_account_service):
        worker = make_worker()
        mock_account_service.update_profile.return_value = worker
        client = make_client(role=UserRole.WORKER, account_service=mock_account_service)

        # Extra fields like email/roles are not part of AccountProfileUpdate and are dropped.
        response = client.patch(
            "/api/v1/account/me",
            json={"first_name": "Jane", "email": "hacker@example.com", "roles": ["admin"]},
        )
        assert response.status_code == 200
        _, update = mock_account_service.update_profile.call_args.args
        assert not hasattr(update, "email") or update.email is None
        assert not hasattr(update, "roles")


class TestChangeMyPassword:
    def test_returns_200_on_success(self, mock_account_service):
        client = make_client(role=UserRole.WORKER, account_service=mock_account_service)

        response = client.post(
            "/api/v1/account/change-password",
            json={"current_password": "old-password", "new_password": "new-password-123"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Password changed successfully"
        mock_account_service.change_password.assert_called_once()

    def test_returns_400_when_current_password_wrong(self, mock_account_service):
        mock_account_service.change_password.side_effect = BadRequestError("Current password is incorrect")
        client = make_client(role=UserRole.WORKER, account_service=mock_account_service)

        response = client.post(
            "/api/v1/account/change-password",
            json={"current_password": "wrong", "new_password": "new-password-123"},
        )
        assert response.status_code == 400

    def test_returns_422_when_new_password_too_short(self, mock_account_service):
        client = make_client(role=UserRole.WORKER, account_service=mock_account_service)

        response = client.post(
            "/api/v1/account/change-password",
            json={"current_password": "old-password", "new_password": "short"},
        )
        assert response.status_code == 422
        mock_account_service.change_password.assert_not_called()


class TestDeleteMyAccount:
    def test_returns_204_and_calls_service(self, mock_account_service):
        client = make_client(role=UserRole.WORKER, account_service=mock_account_service)

        response = client.delete("/api/v1/account/me")
        assert response.status_code == 204
        mock_account_service.delete_account.assert_called_once()
