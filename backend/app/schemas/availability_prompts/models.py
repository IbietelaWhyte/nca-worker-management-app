from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PromptMode(StrEnum):
    ONCE = "once"
    MONTHLY = "monthly"


class AvailabilityPrompt(BaseModel):
    id: UUID
    department_id: UUID
    created_by: UUID | None = None
    mode: PromptMode
    send_on: date | None = None
    repeat_day: int | None = None
    is_active: bool
    last_sent_on: date | None = None
    created_at: datetime


class AvailabilityPromptCreate(BaseModel):
    mode: PromptMode
    send_on: date | None = None
    # Capped at 28 so the day exists in February — a monthly prompt that silently skipped a month
    # would be worse than one landing slightly early.
    repeat_day: int | None = Field(default=None, ge=1, le=28)

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "AvailabilityPromptCreate":
        """Reject the combinations the DB check constraints would reject anyway, with a message
        a person can act on.

        Returns:
            AvailabilityPromptCreate: The validated model.

        Raises:
            ValueError: If the date fields do not match the mode.
        """
        if self.mode == PromptMode.ONCE:
            if self.send_on is None:
                raise ValueError("send_on is required for a one-off prompt")
            if self.repeat_day is not None:
                raise ValueError("repeat_day only applies to a monthly prompt")
        if self.mode == PromptMode.MONTHLY:
            if self.repeat_day is None:
                raise ValueError("repeat_day is required for a monthly prompt")
            if self.send_on is not None:
                raise ValueError("send_on only applies to a one-off prompt")
        return self


class AvailabilityPromptResponse(AvailabilityPrompt):
    pass


class PromptSendResult(BaseModel):
    """Outcome of sending one prompt.

    Reported as counts rather than a formatted sentence: workers.phone is nullable and nothing in
    the UI warns about it, so unlike a schedule reminder — which is visible on the schedule page —
    an unreachable worker would otherwise go unnoticed entirely.
    """

    sent: int = 0
    skipped_no_phone: int = 0
    failed: int = 0
