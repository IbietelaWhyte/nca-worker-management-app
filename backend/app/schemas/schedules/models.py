from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Schedule(BaseModel):
    id: UUID
    department_id: UUID
    title: str
    scheduled_date: datetime
    start_time: datetime
    end_time: datetime
    notes: str | None
    created_by: UUID
    created_at: datetime


class CreateSchedule(BaseModel):
    title: str
    scheduled_date: datetime
    start_time: datetime
    end_time: datetime
    notes: str | None


class ScheduleResponse(Schedule):
    pass


class AssignmentResponse(BaseModel):
    id: UUID
    schedule_id: UUID
    worker_id: UUID
    schedule_date: datetime
    status: str
    worker_name: str | None


class ScheduleGenerateRequest(BaseModel):
    department_id: UUID
    subteam_id: UUID | None
    title: str
    scheduled_date: datetime
    start_time: datetime
    end_time: datetime
    notes: str | None
    reminder_days_before: int