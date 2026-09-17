from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class WorkerLeave(BaseModel):
    id: UUID
    worker_id: UUID
    start_date: date
    end_date: date
    reason: str | None = None
    # ON DELETE SET NULL on the FK, so a leave outlives the head who set it. Typed optional for
    # that reason, not as a convenience — a non-optional field here raises ValidationError deep
    # inside a repository read the first time a head is deleted.
    created_by: UUID | None = None
    created_at: datetime

    @property
    def covers_today(self) -> bool:
        """Whether this leave is running right now."""
        return self.covers(date.today())

    def covers(self, day: date) -> bool:
        """Whether this leave covers a given date.

        Args:
            day: The date to test.

        Returns:
            bool: True if the date falls inside the leave, both ends inclusive.
        """
        return self.start_date <= day <= self.end_date


class WorkerLeaveCreate(BaseModel):
    """A stretch of time a worker is away.

    Both ends are inclusive, because that is how the person setting it reads the dates: "away
    10-20 Oct" means the 20th is still a day off.
    """

    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check_order(self) -> "WorkerLeaveCreate":
        """Reject a range that ends before it starts.

        Returns:
            WorkerLeaveCreate: The validated model.

        Raises:
            ValueError: If end_date precedes start_date.
        """
        if self.end_date < self.start_date:
            raise ValueError("The end date cannot be before the start date")
        return self


class WorkerLeaveResponse(WorkerLeave):
    pass


class LeaveClash(BaseModel):
    """A duty already on the rota inside a proposed leave period.

    Setting leave never edits the rota — a head is recording an absence, not reassigning work —
    so these are reported and left alone. Without the warning the duty would sit there until its
    reminder went out to somebody who is abroad.
    """

    schedule_id: UUID
    scheduled_date: date
    department_name: str | None = None


class LeaveClashReport(BaseModel):
    clashes: list[LeaveClash] = []


class CurrentLeave(BaseModel):
    """Who is away right now, for badging a roster without fetching each worker's history."""

    worker_id: UUID
    start_date: date
    end_date: date
