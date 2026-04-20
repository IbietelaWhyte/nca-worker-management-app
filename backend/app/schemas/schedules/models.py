from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.schemas.subteams.models import SubteamResponse
from app.schemas.workers.models import WorkerResponse


class ScopeType(StrEnum):
    SUBTEAM = "subteam"
    DEPARTMENT_ONLY = "department_only"
    DEPARTMENT_ALL = "department_all"


class Schedule(BaseModel):
    id: UUID
    department_id: UUID
    subteam_id: UUID | None
    title: str
    scheduled_date: date
    start_time: time
    end_time: time
    reminder_days_before: int
    notes: str | None = None
    created_by: UUID
    created_at: datetime


class ScheduleCreate(BaseModel):
    department_id: UUID
    scope: ScopeType
    subteam_id: UUID | None = None
    title: str
    scheduled_date: date
    start_time: time
    end_time: time
    notes: str | None = None
    reminder_days_before: int

    @model_validator(mode="after")
    def validate_scope_fields(self) -> "ScheduleCreate":
        if self.scope == ScopeType.SUBTEAM and self.subteam_id is None:
            raise ValueError("subteam_id is required when scope is 'subteam'")
        if self.scope in [ScopeType.DEPARTMENT_ONLY, ScopeType.DEPARTMENT_ALL] and self.subteam_id is not None:
            raise ValueError("subteam_id must be None for department-level scopes")
        return self


class AssignmentResponse(BaseModel):
    id: UUID
    schedule_id: UUID
    worker_id: UUID
    department_role_id: UUID | None = None
    subteam_id: UUID | None = None
    status: str
    reminder_sent_at: datetime | None = None
    workers: WorkerResponse | None = None  # Nested worker object from joined query
    subteams: SubteamResponse | None = None  # Nested subteam object from joined query
    schedules: "Schedule | None" = None  # Nested schedule object from joined query


class ScheduleResponse(Schedule):
    schedule_assignments: list[AssignmentResponse] = []
