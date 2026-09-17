from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ConfirmationTokenResponse(BaseModel):
    id: UUID
    worker_id: UUID
    expires_at: datetime
    created_at: datetime


class ConfirmationTokenCreate(BaseModel):
    worker_id: UUID
    expires_at: datetime
