from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.models import UserRole


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
    roles: list[UserRole] = Field(default_factory=list)


class WorkerUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    roles: list[UserRole] | None = Field(default=None, min_length=1, description="Must include at least one role")
