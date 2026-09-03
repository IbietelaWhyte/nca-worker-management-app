from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, GoneError, NotFoundError
from app.repository.confirmation_tokens.repository import ConfirmationTokenRepository
from app.repository.schedules.repository import ScheduleRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.confirmation_tokens.models import ConfirmationTokenResponse
from app.service.confirmation_tokens.service import ConfirmationTokenService
from tests.unit.services.conftest import make_worker
from tests.unit.services.test_reminder_service import make_due_assignment


def make_token(**kwargs) -> ConfirmationTokenResponse:
    return ConfirmationTokenResponse(
        id=kwargs.get("id", uuid4()),
        worker_id=kwargs.get("worker_id", uuid4()),
        assignment_id=kwargs.get("assignment_id"),
        expires_at=kwargs.get("expires_at", datetime.now(timezone.utc) + timedelta(days=30)),
        last_used_at=kwargs.get("last_used_at"),
        created_at=kwargs.get("created_at", datetime.now(timezone.utc)),
    )


@pytest.fixture
def mock_token_repo():
    return MagicMock(spec=ConfirmationTokenRepository)


@pytest.fixture
def mock_schedule_repo():
    return MagicMock(spec=ScheduleRepository)


@pytest.fixture
def mock_worker_repo():
    return MagicMock(spec=WorkerRepository)


@pytest.fixture
def service(mock_token_repo, mock_schedule_repo, mock_worker_repo):
    return ConfirmationTokenService(
        token_repo=mock_token_repo,
        schedule_repo=mock_schedule_repo,
        worker_repo=mock_worker_repo,
    )


class TestCreateToken:
    def test_reuses_a_live_token(self, service, mock_token_repo):
        # Load-bearing: the notice and the reminder are sent weeks apart and must lead to the
        # same page, so the link in the first message still works when the second arrives.
        worker_id = uuid4()
        existing = make_token(worker_id=worker_id)
        mock_token_repo.get_live_for_worker.return_value = existing

        url = service.create_token(worker_id=worker_id)
        assert url.endswith(f"/confirm/{existing.id}")
        mock_token_repo.create.assert_not_called()

    def test_mints_one_when_none_is_live(self, service, mock_token_repo):
        worker_id = uuid4()
        minted = make_token(worker_id=worker_id)
        mock_token_repo.get_live_for_worker.return_value = None
        mock_token_repo.create.return_value = minted

        url = service.create_token(worker_id=worker_id)
        assert url.endswith(f"/confirm/{minted.id}")
        mock_token_repo.create.assert_called_once()

    def test_mints_a_replacement_rather_than_failing(self, service, mock_token_repo):
        # The old per-assignment token had a unique constraint, so this path raised and the
        # caller silently sent a linkless SMS.
        mock_token_repo.get_live_for_worker.return_value = None
        mock_token_repo.create.return_value = make_token()

        assert service.create_token(worker_id=uuid4())


class TestGetConfirmationDetails:
    def test_lists_every_upcoming_duty(self, service, mock_token_repo, mock_schedule_repo, mock_worker_repo):
        worker_id = uuid4()
        mock_token_repo.get_by_token.return_value = make_token(worker_id=worker_id)
        mock_worker_repo.get_by_id.return_value = make_worker(id=worker_id, first_name="Ada", last_name="Lovelace")
        mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = [
            make_due_assignment(worker_id=worker_id, scheduled_date="2026-08-02"),
            make_due_assignment(worker_id=worker_id, scheduled_date="2026-08-09"),
        ]

        details = service.get_confirmation_details(uuid4())
        assert details.worker_name == "Ada Lovelace"
        assert details.expired is False
        assert len(details.assignments) == 2

    def test_names_the_department_that_scheduled_each_duty(
        self, service, mock_token_repo, mock_schedule_repo, mock_worker_repo
    ):
        # The page is reached from an SMS with no session, so it cannot resolve a department id
        # itself — the name has to arrive embedded on the assignment.
        worker_id = uuid4()
        mock_token_repo.get_by_token.return_value = make_token(worker_id=worker_id)
        mock_worker_repo.get_by_id.return_value = make_worker(id=worker_id)
        mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = [
            make_due_assignment(worker_id=worker_id, department_name="Ushering")
        ]

        assert service.get_confirmation_details(uuid4()).assignments[0].department_name == "Ushering"

    def test_department_name_is_blank_when_not_embedded(
        self, service, mock_token_repo, mock_schedule_repo, mock_worker_repo
    ):
        # Blank rather than absent: the page drops the label instead of rendering a stray separator.
        worker_id = uuid4()
        mock_token_repo.get_by_token.return_value = make_token(worker_id=worker_id)
        mock_worker_repo.get_by_id.return_value = make_worker(id=worker_id)
        mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = [make_due_assignment(worker_id=worker_id)]

        assert service.get_confirmation_details(uuid4()).assignments[0].department_name == ""

    def test_omits_duties_already_declined(self, service, mock_token_repo, mock_schedule_repo, mock_worker_repo):
        worker_id = uuid4()
        mock_token_repo.get_by_token.return_value = make_token(worker_id=worker_id)
        mock_worker_repo.get_by_id.return_value = make_worker(id=worker_id)
        mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = [
            make_due_assignment(worker_id=worker_id, status="declined"),
            make_due_assignment(worker_id=worker_id, status="pending"),
        ]

        assert len(service.get_confirmation_details(uuid4()).assignments) == 1

    def test_reports_expiry_rather_than_raising(self, service, mock_token_repo, mock_worker_repo):
        mock_token_repo.get_by_token.return_value = make_token(
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        mock_worker_repo.get_by_id.return_value = make_worker()

        details = service.get_confirmation_details(uuid4())
        assert details.expired is True
        assert details.assignments == []

    def test_raises_for_an_unknown_token(self, service, mock_token_repo):
        mock_token_repo.get_by_token.return_value = None
        with pytest.raises(NotFoundError, match="Token not found"):
            service.get_confirmation_details(uuid4())


class TestConfirm:
    def _wire(self, mock_token_repo, mock_schedule_repo, worker_id, assignment):
        mock_token_repo.get_by_token.return_value = make_token(worker_id=worker_id)
        mock_schedule_repo.get_assignment_by_id.return_value = assignment
        mock_schedule_repo.update_assignment_status.return_value = assignment

    def test_confirms_one_assignment(self, service, mock_token_repo, mock_schedule_repo):
        worker_id = uuid4()
        assignment = make_due_assignment(worker_id=worker_id)
        self._wire(mock_token_repo, mock_schedule_repo, worker_id, assignment)

        service.confirm(uuid4(), assignment.id, "confirmed")
        mock_schedule_repo.update_assignment_status.assert_called_once()

    def test_link_survives_being_used(self, service, mock_token_repo, mock_schedule_repo):
        # The old token was single-use, which would have made "confirm each date" impossible.
        worker_id = uuid4()
        first = make_due_assignment(worker_id=worker_id)
        second = make_due_assignment(worker_id=worker_id)
        token_id = uuid4()

        self._wire(mock_token_repo, mock_schedule_repo, worker_id, first)
        service.confirm(token_id, first.id, "confirmed")
        self._wire(mock_token_repo, mock_schedule_repo, worker_id, second)
        service.confirm(token_id, second.id, "declined")

        assert mock_schedule_repo.update_assignment_status.call_count == 2

    def test_rejects_an_assignment_belonging_to_someone_else(self, service, mock_token_repo, mock_schedule_repo):
        mock_token_repo.get_by_token.return_value = make_token(worker_id=uuid4())
        mock_schedule_repo.get_assignment_by_id.return_value = make_due_assignment(worker_id=uuid4())

        with pytest.raises(NotFoundError):
            service.confirm(uuid4(), uuid4(), "confirmed")
        mock_schedule_repo.update_assignment_status.assert_not_called()

    def test_rejects_an_expired_link(self, service, mock_token_repo, mock_schedule_repo):
        mock_token_repo.get_by_token.return_value = make_token(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )

        with pytest.raises(GoneError, match="expired"):
            service.confirm(uuid4(), uuid4(), "confirmed")
        mock_schedule_repo.update_assignment_status.assert_not_called()

    def test_rejects_an_unknown_action(self, service, mock_token_repo):
        with pytest.raises(BadRequestError, match="confirmed"):
            service.confirm(uuid4(), uuid4(), "maybe")
