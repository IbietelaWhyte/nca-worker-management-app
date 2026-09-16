from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, StringConstraints

# Trimmed at the edge rather than in the service: a title of spaces would otherwise pass
# min_length and reach the issue tracker blank.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=80)]
# The floor rejects "it's broken" — a report nobody can act on costs more to triage than it is
# worth. The ceiling is well above anything a phone keyboard produces in one sitting.
Details = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=2000)]
# Browser-supplied context. Bounded because it is attacker-controlled in principle and lands in a
# public issue body; none of it is trusted or parsed.
ContextValue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class FeedbackKind(StrEnum):
    BUG = "bug"
    IDEA = "idea"


class FeedbackCreate(BaseModel):
    """A report as the form submits it.

    The context fields are the ones a volunteer could never supply accurately and an engineer
    always wants, so the page fills them in rather than asking.
    """

    kind: FeedbackKind
    title: Title
    details: Details
    page: ContextValue | None = None
    user_agent: ContextValue | None = None
    viewport: ContextValue | None = None
    app_version: ContextValue | None = None


class FeedbackResponse(BaseModel):
    """What the reporter gets back: a number to quote, not a link to a tracker."""

    reference: int


class FeedbackConfig(BaseModel):
    """Whether reporting is wired up at all, so the page can hide the form when it is not."""

    enabled: bool
