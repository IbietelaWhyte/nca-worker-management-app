from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.department_roles.models import DepartmentRoleResponse
from app.schemas.models import DayOfWeek
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
    department_roles: DepartmentRoleResponse | None = None  # Nested role object from joined query
    schedules: "Schedule | None" = None  # Nested schedule object from joined query


class ScheduleResponse(Schedule):
    schedule_assignments: list[AssignmentResponse] = []


# ----------------------------------------------------------------
# Monthly generation
#
# A "month" is not an entity — it is N ordinary schedules that happen to fall in the
# same month. Generation is two-phase: preview plans the month and writes nothing,
# commit persists the plan the HOD approved (including any manual swaps).
# ----------------------------------------------------------------


class MonthlyScheduleBase(BaseModel):
    """Fields shared by every schedule created in one monthly run."""

    department_id: UUID
    scope: ScopeType
    subteam_id: UUID | None = None
    title: str
    start_time: time
    end_time: time
    notes: str | None = None
    reminder_days_before: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_scope_and_times(self) -> "MonthlyScheduleBase":
        if self.scope == ScopeType.SUBTEAM and self.subteam_id is None:
            raise ValueError("subteam_id is required when scope is 'subteam'")
        if self.scope in [ScopeType.DEPARTMENT_ONLY, ScopeType.DEPARTMENT_ALL] and self.subteam_id is not None:
            raise ValueError("subteam_id must be None for department-level scopes")
        # schedules.chk_times enforces this too, but a bulk insert that trips a DB
        # constraint fails the whole month — catch it before any row is written.
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class MonthlySchedulePreviewRequest(MonthlyScheduleBase):
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    days_of_week: list[DayOfWeek] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def deduplicate_days(self) -> "MonthlySchedulePreviewRequest":
        seen: list[DayOfWeek] = []
        for day in self.days_of_week:
            if day not in seen:
                seen.append(day)
        self.days_of_week = seen
        return self


class DatePlanStatus(StrEnum):
    PLANNED = "planned"
    UNDERSTAFFED = "understaffed"
    SKIPPED_EXISTING = "skipped_existing"
    SKIPPED_NO_WORKERS = "skipped_no_workers"


class PlannedAssignment(BaseModel):
    worker: WorkerResponse
    department_role: DepartmentRoleResponse | None = None
    subteam_id: UUID | None = None


class PlannedGroup(BaseModel):
    """One roster's staffing on one date.

    A department-wide schedule has a group per subteam plus one for workers in no
    subteam, each carrying its own quota. Subteam-scoped and department-only schedules
    have a single group.
    """

    # None for the department-only roster (workers in no subteam).
    subteam: SubteamResponse | None = None
    workers_needed: int
    status: DatePlanStatus
    assignments: list[PlannedAssignment] = []
    # Free but not picked for this group — powers the swap control in the preview UI.
    # Restricted to the group so a swap can never break a subteam's quota.
    alternates: list[WorkerResponse] = []
    message: str | None = None


class DatePlan(BaseModel):
    scheduled_date: date
    status: DatePlanStatus
    groups: list[PlannedGroup] = []
    message: str | None = None


class MonthlySchedulePreview(BaseModel):
    year: int
    month: int
    # Total slots per date, summed across every group.
    workers_needed: int
    dates: list[DatePlan]


class DateSelection(BaseModel):
    scheduled_date: date
    worker_ids: list[UUID] = Field(min_length=1)


class MonthlyScheduleCommitRequest(MonthlyScheduleBase):
    dates: list[DateSelection] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dates_unique(self) -> "MonthlyScheduleCommitRequest":
        seen = {d.scheduled_date for d in self.dates}
        if len(seen) != len(self.dates):
            raise ValueError("dates must not contain duplicate scheduled_date values")
        return self


class SkippedDate(BaseModel):
    scheduled_date: date
    reason: str


class MonthlyScheduleResult(BaseModel):
    created: list[ScheduleResponse] = []
    skipped: list[SkippedDate] = []
