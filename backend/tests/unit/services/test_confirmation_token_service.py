from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import GoneError, NotFoundError
from app.repository.confirmation_tokens.repository import ConfirmationTokenRepository
from app.schemas.confirmation_tokens.models import ConfirmationTokenResponse
from app.service.confirmation_tokens.service import ConfirmationTokenService


def make_token(**kwargs) -> ConfirmationTokenResponse:
    return ConfirmationTokenResponse(
        id=kwargs.get("id", uuid4()),
        worker_id=kwargs.get("worker_id", uuid4()),
        expires_at=kwargs.get("expires_at", datetime.now(timezone.utc) + timedelta(days=30)),
        created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
    )


@pytest.fixture
def mock_token_repo():
    return MagicMock(spec=ConfirmationTokenRepository)


@pytest.fixture
def service(mock_token_repo):
    return ConfirmationTokenService(token_repo=mock_token_repo)


class TestGetOrCreateTokenId:
    def test_reuses_a_live_token(self, service, mock_token_repo):
        # Load-bearing: a worker may be prompted for their availability this month and again
        # next month, and the older text still has to open the same page.
        worker_id = uuid4()
        existing = make_token(worker_id=worker_id)
        mock_token_repo.get_live_for_worker.return_value = existing

        assert service.get_or_create_token_id(worker_id) == existing.id
        mock_token_repo.create.assert_not_called()

    def test_mints_one_when_none_is_live(self, service, mock_token_repo):
        worker_id = uuid4()
        minted = make_token(worker_id=worker_id)
        mock_token_repo.get_live_for_worker.return_value = None
        mock_token_repo.create.return_value = minted

        assert service.get_or_create_token_id(worker_id) == minted.id
        mock_token_repo.create.assert_called_once()

    def test_mints_a_replacement_rather_than_failing(self, service, mock_token_repo):
        # The old per-assignment token had a unique constraint, so this path raised and the
        # caller silently sent a linkless SMS.
        mock_token_repo.get_live_for_worker.return_value = None
        mock_token_repo.create.return_value = make_token()

        assert service.get_or_create_token_id(uuid4())


class TestResolveWorkerId:
    def test_returns_the_workers_id(self, service, mock_token_repo):
        worker_id = uuid4()
        mock_token_repo.get_by_token.return_value = make_token(worker_id=worker_id)

        assert service.resolve_worker_id(uuid4()) == worker_id

    def test_raises_for_an_unknown_token(self, service, mock_token_repo):
        mock_token_repo.get_by_token.return_value = None

        with pytest.raises(NotFoundError, match="Token not found"):
            service.resolve_worker_id(uuid4())

    def test_raises_for_an_expired_link(self, service, mock_token_repo):
        mock_token_repo.get_by_token.return_value = make_token(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )

        with pytest.raises(GoneError, match="expired"):
            service.resolve_worker_id(uuid4())

    def test_tolerates_a_naive_expiry_from_the_database(self, service, mock_token_repo):
        # Postgres can hand back a naive timestamp; comparing it against an aware `now` would
        # raise TypeError deep inside the availability page rather than saying "expired".
        naive_future = (datetime.now(timezone.utc) + timedelta(days=1)).replace(tzinfo=None)
        worker_id = uuid4()
        mock_token_repo.get_by_token.return_value = make_token(worker_id=worker_id, expires_at=naive_future)

        assert service.resolve_worker_id(uuid4()) == worker_id
