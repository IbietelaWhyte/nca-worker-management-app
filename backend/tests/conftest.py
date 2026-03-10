import pytest
from fastapi.testclient import TestClient

from app.core.authentication import verify_token
from app.main import app
from app.schemas.models import TokenPayload, UserRole

# ----------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------


def make_token(role: UserRole = UserRole.WORKER, sub: str = "test-user-id") -> dict:
    """Returns Authorization header with a mock token string."""
    return {"Authorization": f"Bearer mock-token-{role}-{sub}"}


def mock_verify_token(role: UserRole = UserRole.WORKER) -> TokenPayload:
    return TokenPayload(sub="test-user-id", role=role, email="test@example.com")


# ----------------------------------------------------------------
# Test client fixture with auth override
# ----------------------------------------------------------------


@pytest.fixture
def auth_override():
    """
    Returns a factory that patches verify_token with a given role.
    Usage: auth_override(UserRole.ADMIN)
    """

    def _override(role: UserRole = UserRole.WORKER):
        app.dependency_overrides[verify_token] = lambda: mock_verify_token(role)
        return app.dependency_overrides

    yield _override
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_client(auth_override):
    auth_override(UserRole.ADMIN)
    return TestClient(app)


@pytest.fixture
def hod_client(auth_override):
    auth_override(UserRole.HOD)
    return TestClient(app)


@pytest.fixture
def worker_client(auth_override):
    auth_override(UserRole.WORKER)
    return TestClient(app)
