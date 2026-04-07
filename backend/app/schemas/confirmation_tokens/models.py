from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ConfirmationTokenResponse(BaseModel):
    id: UUID
    worker_id: UUID
    assignment_id: UUID
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime


class ConfirmationTokenCreate(BaseModel):
    worker_id: UUID
    assignment_id: UUID
    expires_at: datetime


class ConfirmationDetailsResponse(BaseModel):
    """Response model for the public GET /confirm/{token} endpoint.

    Contains the assignment and schedule details a worker needs to see
    before confirming or declining, without exposing sensitive data.
    """

    worker_name: str
    schedule_title: str
    scheduled_date: str
    start_time: str
    end_time: str
    current_status: str
    already_used: bool
    expired: bool
