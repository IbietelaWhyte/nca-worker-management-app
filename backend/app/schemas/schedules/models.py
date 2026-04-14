from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel

from app.schemas.subteams.models import SubteamResponse
from app.schemas.workers.models import WorkerResponse


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
    subteam_id: UUID | None = None
    title: str
    scheduled_date: date
    start_time: time
    end_time: time
    notes: str | None = None
    reminder_days_before: int


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
