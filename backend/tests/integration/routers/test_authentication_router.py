from app.schemas.authentication.models import RegisterResponse
from app.schemas.models import UserRole
from tests.integration.routers.conftest import make_client

VALID_PAYLOAD = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone": "+14165550101",
    "password": "securepassword123",
}


class TestRegisterWorker:
    def test_returns_201_on_success(self, mock_authentication_service):
        mock_authentication_service.register_worker.return_value = RegisterResponse(
            message="Worker registered successfully",
            worker_id="some-uuid",
            email="john.doe@example.com",
        )
        client = make_client(UserRole.ADMIN, authentication_service=mock_authentication_service)

        response = client.post("/api/v1/authentication/register", json=VALID_PAYLOAD)
        assert response.status_code == 201
        assert response.json()["email"] == "john.doe@example.com"

    def test_returns_409_on_duplicate_email(self, mock_authentication_service):
        mock_authentication_service.register_worker.side_effect = ValueError(
            "Email john.doe@example.com is already registered"
        )
        client = make_client(UserRole.ADMIN, authentication_service=mock_authentication_service)

        response = client.post("/api/v1/authentication/register", json=VALID_PAYLOAD)
        assert response.status_code == 409

    def test_returns_400_on_other_failure(self, mock_authentication_service):
        mock_authentication_service.register_worker.side_effect = ValueError("Failed to create worker record")
        client = make_client(UserRole.ADMIN, authentication_service=mock_authentication_service)

        response = client.post("/api/v1/authentication/register", json=VALID_PAYLOAD)
        assert response.status_code == 400

    def test_returns_403_for_non_admin(self, mock_authentication_service):
        client = make_client(UserRole.WORKER, authentication_service=mock_authentication_service)
        response = client.post("/api/v1/authentication/register", json=VALID_PAYLOAD)
        assert response.status_code == 403

    def test_returns_403_for_hod_role(self, mock_authentication_service):
        client = make_client(UserRole.HOD, authentication_service=mock_authentication_service)
        response = client.post("/api/v1/authentication/register", json=VALID_PAYLOAD)
        assert response.status_code == 403

    def test_returns_422_on_invalid_email(self, mock_authentication_service):
        client = make_client(UserRole.ADMIN, mock_authentication_service)
        response = client.post(
            "/api/v1/authentication/register",
            json={
                **VALID_PAYLOAD,
                "email": "not-an-email",
            },
        )
        assert response.status_code == 422

    def test_returns_422_when_password_missing(self, mock_authentication_service):
        client = make_client(UserRole.ADMIN, mock_authentication_service)
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "password"}
        response = client.post("/api/v1/authentication/register", json=payload)
        assert response.status_code == 422
