import re
import threading
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx

from app.core.config import settings
from app.core.exceptions import AppError, TooManyRequestsError
from app.core.logging import get_logger
from app.schemas.feedback.models import FeedbackCreate, FeedbackKind, FeedbackResponse
from app.schemas.models import TokenPayload
from app.service.workers.service import WorkerService

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"
# Marks what arrived through this form, so volunteer reports can be filtered from the maintainer's
# own issues. GitHub creates a label it does not recognise when the issue is created.
SOURCE_LABEL = "from-app"
KIND_LABELS = {FeedbackKind.BUG: "bug", FeedbackKind.IDEA: "enhancement"}
KIND_TITLES = {FeedbackKind.BUG: "Bug", FeedbackKind.IDEA: "Idea"}

# Submission times per worker, newest last. Module-level because the service is constructed per
# request, so an instance attribute would reset on every call. This is per-process and does not
# survive a restart — enough to stop a stuck Send button, not a determined abuser. A worker who
# needs a real audit trail wants a table instead.
_recent: dict[UUID, list[datetime]] = {}
_recent_lock = threading.Lock()

_BACKTICK_RUN = re.compile(r"`+")


class FeedbackService:
    """Turns an in-app bug report or idea into a GitHub issue.

    The tracker it posts to is **public**, so the issue body identifies the reporter only by their
    worker id — never a name, an email or a phone number. Resolving an id to a person is a lookup
    in the app, which is the point: the correlation stays inside the church's own systems.

    The form is hidden rather than broken when no credentials are configured, so a checkout with
    no GitHub token still runs the app.
    """

    def __init__(self, worker_service: WorkerService) -> None:
        """Initialize the FeedbackService.

        Args:
            worker_service: Resolves the caller's own worker record from their token.
        """
        self.worker_service = worker_service
        self.logger = logger.bind(service="FeedbackService")

    @property
    def is_enabled(self) -> bool:
        """Whether reporting is configured. Both credentials are needed, neither has a default."""
        return bool(settings.feedback_github_token and settings.feedback_github_repo)

    def submit(self, token: TokenPayload, data: FeedbackCreate) -> FeedbackResponse:
        """File a report as a GitHub issue and return the number the reporter can quote.

        Args:
            token: The verified token payload of the reporting user.
            data: The submitted report, already length-validated by its schema.

        Returns:
            FeedbackResponse: The created issue's number.

        Raises:
            AppError: If reporting is not configured, or GitHub rejected or did not answer the
                call. The caller's text is never discarded on this path — the dialog keeps it.
            TooManyRequestsError: If this worker has filed too many reports this hour.
        """
        if not self.is_enabled:
            raise AppError("Reporting is not available.")

        worker = self.worker_service.get_worker_for_token(token)
        self._check_rate_limit(worker.id)

        title = f"[{KIND_TITLES[data.kind]}] {data.title}"
        body = self._build_body(data, worker.id, token.role)
        labels = [KIND_LABELS[data.kind], SOURCE_LABEL]

        number = self._create_issue(title, body, labels)
        self.logger.info("feedback_submitted", worker_id=str(worker.id), kind=data.kind, issue=number)
        return FeedbackResponse(reference=number)

    def _check_rate_limit(self, worker_id: UUID) -> None:
        """Reject a worker who has already filed the hour's allowance.

        Args:
            worker_id: The reporting worker.

        Raises:
            TooManyRequestsError: If the allowance is spent.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        with _recent_lock:
            times = [t for t in _recent.get(worker_id, []) if t > cutoff]
            if len(times) >= settings.feedback_max_per_hour:
                self.logger.warning("feedback_rate_limited", worker_id=str(worker_id))
                raise TooManyRequestsError("You have sent several reports already. Please try again later.")
            times.append(datetime.now(UTC))
            _recent[worker_id] = times

    @staticmethod
    def _build_body(data: FeedbackCreate, worker_id: UUID, role: str) -> str:
        """Render the issue body.

        What the reporter typed goes in a fenced block, which is not cosmetic: pasted straight into
        markdown, "@someone" pings a real GitHub account and "#48" cross-links a real pull request,
        so a volunteer describing a problem could notify strangers by accident.

        Args:
            data: The submitted report.
            worker_id: The reporter, as an id — deliberately not a name, see the class docstring.
            role: The reporter's app role, which usually explains what they were able to see.

        Returns:
            str: Markdown for the issue body.
        """
        fence = FeedbackService._fence_for(data.details)
        context = [
            ("Worker", f"`{worker_id}`"),
            ("Role", role),
            ("Page", data.page),
            ("Browser", data.user_agent),
            ("Viewport", data.viewport),
            ("App version", data.app_version),
            ("Submitted", datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")),
        ]
        rows = "\n".join(f"| {label} | {value} |" for label, value in context if value)

        return (
            "Reported from the app.\n\n"
            f"{fence}text\n{data.details}\n{fence}\n\n"
            "<details><summary>Context</summary>\n\n"
            "| | |\n| --- | --- |\n"
            f"{rows}\n\n"
            "</details>\n"
        )

    @staticmethod
    def _fence_for(text: str) -> str:
        """Return a code fence longer than any backtick run in the text it has to contain.

        Args:
            text: The text to be fenced.

        Returns:
            str: A run of at least three backticks that the text cannot break out of.
        """
        longest = max((len(m.group()) for m in _BACKTICK_RUN.finditer(text)), default=0)
        return "`" * max(3, longest + 1)

    def _create_issue(self, title: str, body: str, labels: list[str]) -> int:
        """POST the issue to GitHub and return its number.

        Args:
            title: The issue title.
            body: The rendered markdown body.
            labels: Labels to apply.

        Returns:
            int: The created issue's number.

        Raises:
            AppError: If GitHub rejected the call or did not answer in time.
        """
        url = f"{GITHUB_API}/repos/{settings.feedback_github_repo}/issues"
        try:
            response = httpx.post(
                url,
                json={"title": title, "body": body, "labels": labels},
                headers={
                    "Authorization": f"Bearer {settings.feedback_github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=settings.feedback_timeout_seconds,
            )
            response.raise_for_status()
            number = response.json()["number"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            # The status is worth logging; the response body is not, in case it echoes the payload.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            self.logger.error("feedback_submit_failed", error=type(exc).__name__, status=status)
            raise AppError("Your report could not be sent. Please try again.") from exc
        return int(number)
