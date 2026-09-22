from datetime import date, datetime, time
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, model_validator

from app.schemas.department_roles.models import DepartmentRoleResponse
from app.schemas.departments.models import DepartmentResponse
from app.schemas.models import DayOfWeek
from app.schemas.subteams.models import SubteamResponse
from app.schemas.workers.models import WorkerResponse

# Matches schedules.chk_reminder_days. Five is a cap on someone's phone bill, not on the schema:
# a mistyped ladder against a forty-person department is forty texts per extra entry.
MAX_REMINDER_LEAD_TIMES = 5


def _normalize_lead_times(values: list[int]) -> list[int]:
    """Collapse duplicates and order a reminder ladder furthest-out first.

    Deduplication is done here rather than by a constraint because a repeated lead time is a
    slip, not an error worth a 422 — and `assignment_reminder_sends`' primary key would make the
    second send a no-op anyway. Sorting descending puts them in the order they fire, which is how
    both the form and the schedule header read them back.

    The cap is applied *after* deduplication, so `[1, 1, 1, 1, 1, 1]` is one reminder rather than
    six rejected ones.
    """
    unique = sorted(set(values), reverse=True)
    if len(unique) > MAX_REMINDER_LEAD_TIMES:
        raise ValueError(f"at most {MAX_REMINDER_LEAD_TIMES} reminders per schedule")
    return unique


# An empty ladder is allowed and means no reminders at all, only the "you have been scheduled"
# notice: a real choice for a team that works off the printed rota, and not one the app should
# spend their money overriding.
ReminderLeadTimes = Annotated[
    list[Annotated[int, Field(ge=0, le=365)]],
    AfterValidator(_normalize_lead_times),
]


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
    # A ladder, not a number: {7, 3, 1} is a week out, three days out and the night before. Read
    # straight from a smallint[] column, so no normalization here — the write paths validate.
    reminder_days_before: list[int]
    # The staffing band in force when this schedule was generated, summed across its groups.
    # Frozen at generation rather than re-resolved on read: the department's numbers may change
    # before the date comes round, and this rota was planned against these. Nullable because
    # rows created before the band existed have no honest answer — callers fall back to the
    # assignment count rather than rendering "0 needed".
    min_workers: int | None = None
    max_workers: int | None = None
    notes: str | None = None
    # Nullable because schedules_created_by_fkey is ON DELETE SET NULL: removing the worker who
    # created a schedule leaves the schedule standing without a creator. Typed non-optional, this
    # raised a ValidationError on every read of such a row — including inside the round-robin
    # sort, which took down schedule generation entirely.
    created_by: UUID | None = None
    created_at: datetime
    # Nested department object, present only on the queries that embed it — the public confirmation
    # page needs the name and cannot look one up, having no session. Optional like every other
    # embed, so the selects that don't ask for it still validate.
    departments: DepartmentResponse | None = None


class ScheduleCreate(BaseModel):
    department_id: UUID
    scope: ScopeType
    subteam_id: UUID | None = None
    title: str
    scheduled_date: date
    start_time: time
    end_time: time
    notes: str | None = None
    reminder_days_before: ReminderLeadTimes

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
    # The "you have been scheduled" message, sent once per assignment shortly after creation.
    # The pre-service reminder has no counterpart here: a schedule has several lead times and
    # "the 7-day one went out, the 3-day one has not" is set membership, which one timestamp
    # cannot hold. Those live in assignment_reminder_sends, a row per (assignment, lead time).
    notice_sent_at: datetime | None = None
    workers: WorkerResponse | None = None  # Nested worker object from joined query
    subteams: SubteamResponse | None = None  # Nested subteam object from joined query
    department_roles: DepartmentRoleResponse | None = None  # Nested role object from joined query
    schedules: "Schedule | None" = None  # Nested schedule object from joined query


class DueReminder(BaseModel):
    """One (assignment, lead time) pair whose reminder falls on the date being swept.

    Deliberately not an `AssignmentResponse`. The RPC returns a row per lead time now, so an
    assignment appears once per ladder entry; validating those as assignments would keep working
    and hand the caller duplicates that each mark the whole assignment reminded. The RPC's first
    column is named `assignment_id` for the same reason — the rename is what forces every caller
    to be rewritten rather than silently drifting.

    `days_before` has to survive the round trip: it is half the key the send is recorded under,
    and a fabricated one would mark a genuinely-due reminder as already sent.
    """

    assignment_id: UUID
    schedule_id: UUID
    worker_id: UUID
    days_before: int
    # row_to_json() embeds, optional like every other embed in this module.
    workers: WorkerResponse | None = None
    schedules: Schedule | None = None


class ScheduleResponse(Schedule):
    schedule_assignments: list[AssignmentResponse] = []


# ----------------------------------------------------------------
# Editing a rota after it has been generated
#
# A generated rota is almost right and then somebody pulls out. Until now the only
# repair was to delete the whole schedule and regenerate it, which loses every manual
# correction on it and re-texts everybody.
# ----------------------------------------------------------------


class AssignmentWorkerRequest(BaseModel):
    """Who to put on a rota — the body of both the add and the swap."""

    worker_id: UUID


class ScheduleEditResult(BaseModel):
    """The whole schedule after an edit, plus anything the head should know about it.

    Returns the re-read schedule rather than the one row that changed: the caller replaces
    `schedule` wholesale and every embed comes with it, which sidesteps the "a bare insert
    return has no `workers` embed" trap entirely.

    `warnings` are things that did not stop the edit. Removing somebody below the minimum is
    allowed, and so is booking a worker who is already out that day — a head recording what
    has actually happened must be able to, and refusing leaves the rota lying instead.
    """

    schedule: ScheduleResponse
    warnings: list[str] = []


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
    reminder_days_before: ReminderLeadTimes

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
    subteam, each carrying its own band. Subteam-scoped and department-only schedules
    have a single group.
    """

    # None for the department-only roster (workers in no subteam).
    subteam: SubteamResponse | None = None
    # `max_workers` is what the planner filled to; `min_workers` is what judges the result.
    # Renamed rather than redefined from `workers_needed` — a kept name meaning something new
    # is the kind of break nothing catches.
    min_workers: int
    max_workers: int
    status: DatePlanStatus
    assignments: list[PlannedAssignment] = []
    # Free but not picked for this group — powers the swap control in the preview UI.
    # Restricted to the group so a swap can never break another subteam's staffing.
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
    # Totals per date, summed across every group.
    min_workers: int
    max_workers: int
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
