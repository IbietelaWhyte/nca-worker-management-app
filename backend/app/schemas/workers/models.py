from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Worker(BaseModel):
    id: UUID
    auth_user_id: UUID | None = Field(default=None, exclude=True)  # Exclude from serialization
    first_name: str
    last_name: str
    phone: str
    email: str | None = None
    is_active: bool
    created_at: datetime


class WorkerCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: str | None = None


class WorkerResponse(Worker):
    pass  # Now auth_user_id is already excluded in the parent class


class WorkerUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
