from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ConfirmationTokenResponse(BaseModel):
    id: UUID
    worker_id: UUID
    # Null for worker-scoped tokens. Only pre-2026-08-31 tokens, minted per assignment, set it.
    assignment_id: UUID | None = None
    expires_at: datetime
    last_used_at: datetime | None = None
    created_at: datetime


class ConfirmationTokenCreate(BaseModel):
    worker_id: UUID
    expires_at: datetime


class ConfirmableAssignment(BaseModel):
    """One duty shown on the public confirmation page."""

    assignment_id: UUID
    schedule_title: str
    # Which department expects them. A worker can serve in several, so the title alone ("Sunday
    # Service") does not say who is counting on them. Defaults to "" rather than being required:
    # the page drops the label instead of failing when a name cannot be resolved.
    department_name: str = ""
    scheduled_date: str
    start_time: str
    end_time: str
    status: str


class ConfirmationDetailsResponse(BaseModel):
    """Response model for the public GET /confirm/{token} endpoint.

    Lists every upcoming duty the worker holds, so one SMS can cover a whole month of dates and
    the worker can answer each independently. `expired` signals an invalid token to the frontend
    rather than raising here; there is no "already used" state any more, because the link stays
    usable until it expires.
    """

    worker_name: str
    expired: bool
    assignments: list[ConfirmableAssignment] = []
