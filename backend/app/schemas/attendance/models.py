from datetime import date
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.departments.models import DepartmentResponse
from app.schemas.workers.models import WorkerResponse


class AttendanceState(str, Enum):
    """What a rota row says happened, derived from the pair of timestamps on it.

    A projection for reading, never a stored column - the schema holds two nullable timestamps
    and two booleans, and `rules.state_of` turns them into this. Deliberately not an enum in
    Postgres: `20260918090000` removed the last status enum from this table for good reasons,
    and reintroducing one would invite `pending` and `unknown` to creep in as values.

    NOT_RECORDED is the state that matters most. It is a duty nobody recorded attendance for, and
    it is emphatically not an absence - counting it as one is the failure the whole design is
    shaped to prevent.
    """

    NOT_RECORDED = "not_recorded"
    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    EXCUSED = "excused"


class AttendanceUpdate(BaseModel):
    """A head correcting an absence after the fact."""

    excused: bool


class AttendanceCount(BaseModel):
    """The tally on one rota, which is what an operator watches while taking attendance."""

    assigned: int
    present: int
    late: int
    absent: int
    excused: int
    not_recorded: int


class AbsenceRow(BaseModel):
    """One worker's attendance in one department over a window.

    `duties` counts only **recorded** duties, so `absences` is judged against what is actually
    known rather than against a rota nobody checked. Dividing by rostered duties instead would
    flatter a department that never takes attendance, which is the wrong incentive to build in.
    """

    worker_id: UUID
    department_id: UUID
    duties: int
    present: int
    late: int
    absences: int
    excused: int
    not_recorded: int
    last_absent_on: date | None = None
    absent_dates: list[date] = Field(default_factory=list)
    late_dates: list[date] = Field(default_factory=list)
    worker: WorkerResponse | None = None

    @property
    def absence_rate(self) -> float:
        """Share of recorded duties missed unexcused. Zero when nothing is recorded."""
        return self.absences / self.duties if self.duties else 0.0


class AbsenceReport(BaseModel):
    """A department's attendance over a window, plus how much of it is actually known.

    `services` against `services_with_attendance` is the honesty pair. Without it a month where
    attendance was taken twice out of twelve reads as near-perfect attendance, and the first
    report anybody opens quietly teaches them to distrust the feature.
    """

    department_id: UUID
    from_date: date
    to_date: date
    services: int
    services_with_attendance: int
    window_days: int
    repeat_threshold: int
    rows: list[AbsenceRow] = Field(default_factory=list)
    department: DepartmentResponse | None = None
