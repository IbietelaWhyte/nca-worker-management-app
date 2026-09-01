from datetime import date, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.repository.availability_prompts.repository import AvailabilityPromptRepository
from app.repository.departments.repository import DepartmentRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.availability_prompts.models import (
    AvailabilityPromptCreate,
    AvailabilityPromptResponse,
    PromptMode,
)
from app.service.availability_prompts.service import AvailabilityPromptService
from app.service.confirmation_tokens.service import ConfirmationTokenService
from app.service.sms.service import SMSService
from tests.unit.services.conftest import make_department, make_worker


def make_prompt(**kwargs) -> AvailabilityPromptResponse:
    mode = kwargs.get("mode", PromptMode.ONCE)
    return AvailabilityPromptResponse(
        id=kwargs.get("id", uuid4()),
        department_id=kwargs.get("department_id", uuid4()),
        created_by=kwargs.get("created_by"),
        mode=mode,
        send_on=kwargs.get("send_on", date.today() if mode == PromptMode.ONCE else None),
        repeat_day=kwargs.get("repeat_day", None if mode == PromptMode.ONCE else date.today().day),
        is_active=kwargs.get("is_active", True),
        last_sent_on=kwargs.get("last_sent_on"),
        created_at=kwargs.get("created_at", "2026-09-01T08:00:00Z"),
    )


@pytest.fixture
def mock_prompt_repo():
    return MagicMock(spec=AvailabilityPromptRepository)


@pytest.fixture
def mock_department_repo():
    return MagicMock(spec=DepartmentRepository)


@pytest.fixture
def mock_worker_repo():
    return MagicMock(spec=WorkerRepository)


@pytest.fixture
def mock_sms_service():
    sms = MagicMock(spec=SMSService)
    sms.send_availability_prompt.return_value = True
    return sms


@pytest.fixture
def mock_token_service():
    token_service = MagicMock(spec=ConfirmationTokenService)
    token_service.get_or_create_token_id.return_value = uuid4()
    return token_service


@pytest.fixture
def service(mock_prompt_repo, mock_department_repo, mock_worker_repo, mock_sms_service, mock_token_service):
    return AvailabilityPromptService(
        prompt_repo=mock_prompt_repo,
        department_repo=mock_department_repo,
        worker_repo=mock_worker_repo,
        sms_service=mock_sms_service,
        token_service=mock_token_service,
    )


class TestSendNow:
    def test_texts_every_active_worker(self, service, mock_department_repo, mock_worker_repo, mock_sms_service):
        mock_department_repo.get_by_id.return_value = make_department(name="Ushers")
        mock_worker_repo.get_workers_by_department.return_value = [make_worker(), make_worker()]

        result = service.send_now(uuid4())
        assert result.sent == 2
        assert mock_sms_service.send_availability_prompt.call_count == 2

    def test_counts_workers_with_no_phone_instead_of_dropping_them(
        self, service, mock_department_repo, mock_worker_repo, mock_sms_service
    ):
        # Nothing in the UI flags a phoneless worker, and unlike a schedule reminder there is no
        # other screen where their absence would show up.
        mock_department_repo.get_by_id.return_value = make_department()
        mock_worker_repo.get_workers_by_department.return_value = [make_worker(), make_worker(phone=None)]

        result = service.send_now(uuid4())
        assert (result.sent, result.skipped_no_phone) == (1, 1)
        assert mock_sms_service.send_availability_prompt.call_count == 1

    def test_skips_inactive_workers(self, service, mock_department_repo, mock_worker_repo, mock_sms_service):
        mock_department_repo.get_by_id.return_value = make_department()
        mock_worker_repo.get_workers_by_department.return_value = [make_worker(), make_worker(is_active=False)]

        assert service.send_now(uuid4()).sent == 1

    def test_counts_failures(self, service, mock_department_repo, mock_worker_repo, mock_sms_service):
        mock_department_repo.get_by_id.return_value = make_department()
        mock_worker_repo.get_workers_by_department.return_value = [make_worker()]
        mock_sms_service.send_availability_prompt.return_value = False

        result = service.send_now(uuid4())
        assert (result.sent, result.failed) == (0, 1)

    def test_raises_for_an_unknown_department(self, service, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.send_now(uuid4())


class TestSendDuePrompts:
    def test_sends_and_marks(self, service, mock_prompt_repo, mock_department_repo, mock_worker_repo):
        prompt = make_prompt()
        mock_prompt_repo.get_due.return_value = [prompt]
        mock_department_repo.get_by_id.return_value = make_department()
        mock_worker_repo.get_workers_by_department.return_value = [make_worker()]

        assert service.send_due_prompts(date.today()) == 1
        mock_prompt_repo.mark_sent.assert_called_once_with(prompt.id, date.today())

    def test_marks_even_when_some_messages_fail(
        self, service, mock_prompt_repo, mock_department_repo, mock_worker_repo, mock_sms_service
    ):
        # A partial failure must not make the whole department's prompt fire again tomorrow.
        mock_prompt_repo.get_due.return_value = [make_prompt()]
        mock_department_repo.get_by_id.return_value = make_department()
        mock_worker_repo.get_workers_by_department.return_value = [make_worker()]
        mock_sms_service.send_availability_prompt.return_value = False

        service.send_due_prompts(date.today())
        mock_prompt_repo.mark_sent.assert_called_once()

    def test_nothing_due_is_not_an_error(self, service, mock_prompt_repo, mock_sms_service):
        mock_prompt_repo.get_due.return_value = []

        assert service.send_due_prompts(date.today()) == 0
        mock_sms_service.send_availability_prompt.assert_not_called()


class TestDueRules:
    """The scheduling rules live in the repository, and are the part most likely to double-send."""

    def _due(self, prompt, today=None):
        return AvailabilityPromptRepository._is_due(prompt, today or date.today())

    def test_one_off_due_today(self):
        assert self._due(make_prompt(mode=PromptMode.ONCE, send_on=date.today()))

    def test_one_off_still_due_after_its_date_passed(self):
        # A prompt whose day went by while the app was down should still go out.
        assert self._due(make_prompt(mode=PromptMode.ONCE, send_on=date.today() - timedelta(days=3)))

    def test_one_off_not_due_before_its_date(self):
        assert not self._due(make_prompt(mode=PromptMode.ONCE, send_on=date.today() + timedelta(days=1)))

    def test_one_off_never_repeats(self):
        prompt = make_prompt(mode=PromptMode.ONCE, send_on=date.today() - timedelta(days=1))
        prompt.last_sent_on = date.today() - timedelta(days=1)
        assert not self._due(prompt)

    def test_monthly_due_on_its_day(self):
        assert self._due(make_prompt(mode=PromptMode.MONTHLY, repeat_day=date.today().day))

    def test_monthly_not_due_on_other_days(self):
        other = 1 if date.today().day != 1 else 2
        assert not self._due(make_prompt(mode=PromptMode.MONTHLY, repeat_day=other))

    def test_monthly_does_not_send_twice_in_one_day(self):
        prompt = make_prompt(mode=PromptMode.MONTHLY, repeat_day=date.today().day)
        prompt.last_sent_on = date.today()
        assert not self._due(prompt)

    def test_monthly_sends_again_next_month(self):
        prompt = make_prompt(mode=PromptMode.MONTHLY, repeat_day=date.today().day)
        prompt.last_sent_on = date.today() - timedelta(days=28)
        assert self._due(prompt)


class TestCreatePrompt:
    def test_rejects_an_unknown_department(self, service, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.create_prompt(
                uuid4(),
                AvailabilityPromptCreate(mode=PromptMode.ONCE, send_on=date.today()),
                created_by=None,
            )

    def test_one_off_requires_a_date(self):
        with pytest.raises(ValueError, match="send_on is required"):
            AvailabilityPromptCreate(mode=PromptMode.ONCE)

    def test_monthly_requires_a_repeat_day(self):
        with pytest.raises(ValueError, match="repeat_day is required"):
            AvailabilityPromptCreate(mode=PromptMode.MONTHLY)

    def test_monthly_day_is_capped_so_it_exists_in_february(self):
        with pytest.raises(ValueError):
            AvailabilityPromptCreate(mode=PromptMode.MONTHLY, repeat_day=30)
