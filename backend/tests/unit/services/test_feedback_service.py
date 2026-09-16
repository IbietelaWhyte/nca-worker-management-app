from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.config import settings
from app.core.exceptions import AppError, TooManyRequestsError
from app.schemas.feedback.models import FeedbackCreate, FeedbackKind
from app.schemas.models import TokenPayload, UserRole
from app.service.feedback import service as feedback_module
from app.service.feedback.service import FeedbackService

WORKER_ID = UUID("11111111-2222-3333-4444-555555555555")
TOKEN = TokenPayload(sub="auth-user", role=UserRole.WORKER, email="grace@example.com")


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    """Credentials present, and the module-level rate-limit store empty for every test."""
    monkeypatch.setattr(settings, "feedback_github_token", "ghp_test")
    monkeypatch.setattr(settings, "feedback_github_repo", "owner/repo")
    feedback_module._recent.clear()
    yield
    feedback_module._recent.clear()


@pytest.fixture
def worker_service():
    service = MagicMock()
    service.get_worker_for_token.return_value = MagicMock(id=WORKER_ID)
    return service


@pytest.fixture
def service(worker_service):
    return FeedbackService(worker_service)


def report(**overrides) -> FeedbackCreate:
    data = {
        "kind": FeedbackKind.BUG,
        "title": "Availability will not save",
        "details": "I tap the 12th and it goes red but when I come back it is gone again.",
    }
    return FeedbackCreate(**{**data, **overrides})


def submitted(service, data: FeedbackCreate) -> tuple[str, str, list[str]]:
    """Submit and return the (title, body, labels) that reached GitHub."""
    with patch.object(FeedbackService, "_create_issue", return_value=7) as create:
        service.submit(TOKEN, data)
    return create.call_args.args


class TestIssueBody:
    """The tracker is public, so what does and does not reach it is the point of these tests."""

    def test_identifies_the_reporter_only_by_worker_id(self, service):
        _, body, _ = submitted(service, report())
        assert str(WORKER_ID) in body

    def test_carries_no_name_email_or_phone(self, service, worker_service):
        worker_service.get_worker_for_token.return_value = MagicMock(
            id=WORKER_ID,
            first_name="Grace",
            last_name="Okoro",
            email="grace@example.com",
            phone="+14165550101",
        )
        _, body, _ = submitted(service, report())
        for leaked in ("Grace", "Okoro", "grace@example.com", "+14165550101"):
            assert leaked not in body

    def test_fences_what_the_reporter_typed(self, service):
        # Unfenced, "@someone" pings a real account and "#48" links a real pull request.
        _, body, _ = submitted(service, report(details="@maintainer this broke after #48 landed, please look"))
        mention_line = next(line for line in body.splitlines() if "@maintainer" in line)
        fence_lines = [i for i, line in enumerate(body.splitlines()) if line.startswith("```")]
        mention_index = body.splitlines().index(mention_line)
        assert fence_lines[0] < mention_index < fence_lines[1]

    def test_a_backticked_report_cannot_break_out_of_its_fence(self, service):
        _, body, _ = submitted(service, report(details="the error says ``` something ``` and then stops"))
        assert "````text" in body

    def test_context_omits_fields_the_browser_did_not_send(self, service):
        _, body, _ = submitted(service, report(page="/availability"))
        assert "| Page | /availability |" in body
        assert "Viewport" not in body


class TestTitleAndLabels:
    def test_a_bug_is_labelled_as_one(self, service):
        title, _, labels = submitted(service, report())
        assert title == "[Bug] Availability will not save"
        assert labels == ["bug", "from-app"]

    def test_an_idea_becomes_an_enhancement(self, service):
        title, _, labels = submitted(service, report(kind=FeedbackKind.IDEA))
        assert title.startswith("[Idea] ")
        assert labels == ["enhancement", "from-app"]


class TestRateLimit:
    def test_allows_the_hourly_quota(self, service, monkeypatch):
        monkeypatch.setattr(settings, "feedback_max_per_hour", 2)
        with patch.object(FeedbackService, "_create_issue", return_value=1):
            service.submit(TOKEN, report())
            service.submit(TOKEN, report())

    def test_refuses_the_one_after(self, service, monkeypatch):
        monkeypatch.setattr(settings, "feedback_max_per_hour", 1)
        with patch.object(FeedbackService, "_create_issue", return_value=1):
            service.submit(TOKEN, report())
            with pytest.raises(TooManyRequestsError):
                service.submit(TOKEN, report())

    def test_counts_per_worker(self, service, worker_service, monkeypatch):
        monkeypatch.setattr(settings, "feedback_max_per_hour", 1)
        with patch.object(FeedbackService, "_create_issue", return_value=1):
            service.submit(TOKEN, report())
            worker_service.get_worker_for_token.return_value = MagicMock(id=uuid4())
            service.submit(TOKEN, report())


class TestConfiguration:
    def test_disabled_without_credentials(self, service, monkeypatch):
        monkeypatch.setattr(settings, "feedback_github_token", None)
        assert service.is_enabled is False
        with pytest.raises(AppError):
            service.submit(TOKEN, report())

    def test_does_not_reach_github_when_disabled(self, service, monkeypatch):
        monkeypatch.setattr(settings, "feedback_github_repo", None)
        with patch.object(FeedbackService, "_create_issue") as create:
            with pytest.raises(AppError):
                service.submit(TOKEN, report())
        create.assert_not_called()


class TestGitHubFailure:
    def test_surfaces_a_message_the_reporter_can_act_on(self, service):
        import httpx

        with patch.object(feedback_module.httpx, "post", side_effect=httpx.ConnectTimeout("slow")):
            with pytest.raises(AppError) as exc:
                service.submit(TOKEN, report())
        assert "try again" in str(exc.value.detail).lower()

    def test_does_not_leak_the_token_in_the_message(self, service):
        import httpx

        with patch.object(feedback_module.httpx, "post", side_effect=httpx.ConnectTimeout("slow")):
            with pytest.raises(AppError) as exc:
                service.submit(TOKEN, report())
        assert "ghp_test" not in str(exc.value.detail)
