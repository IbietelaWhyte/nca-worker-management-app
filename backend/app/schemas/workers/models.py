from datetime import datetime
from typing import Literal
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
    assistant_hod_departments: list[UUID] | None = Field(default=None, description="Departments for assistant_hod role")


# Status of a single CSV row during a bulk worker import.
# "valid" is only produced by a dry run (the row would be created); "created" by a real import.
WorkerImportRowStatus = Literal["valid", "created", "skipped_duplicate", "error"]


class WorkerImportRowResult(BaseModel):
    row_number: int  # 1-based data row, excluding the header
    status: WorkerImportRowStatus
    name: str | None = None
    email: str | None = None
    worker_id: UUID | None = None
    error: str | None = None


class WorkerImportResult(BaseModel):
    dry_run: bool
    total_rows: int
    created: int  # always 0 on a dry run
    valid: int  # rows that would be created; only populated on a dry run
    skipped_duplicate: int
    errors: int
    results: list[WorkerImportRowResult]
