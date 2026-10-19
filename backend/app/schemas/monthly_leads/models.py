from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.schemas.workers.models import Worker


def first_of_month(day: date) -> date:
    """The first day of the month a date falls in — the one spelling of a month in this table.

    Args:
        day: Any date in the month.

    Returns:
        date: The first of that month.
    """
    return day.replace(day=1)


class MonthlyLead(BaseModel):
    id: UUID
    department_id: UUID
    worker_id: UUID
    month: date
    # ON DELETE SET NULL on the FK, so a lead outlives the head who named them.
    created_by: UUID | None = None
    created_at: datetime


class MonthlyLeadResponse(MonthlyLead):
    worker: Worker | None = None


class MonthlyLeadsSet(BaseModel):
    """The whole set of leads for one month. An empty list clears the month.

    Any date in the month is accepted and normalised to the 1st, so a client can send the date
    of the schedule it is looking at.
    """

    month: date
    worker_ids: list[UUID]

    @field_validator("month")
    @classmethod
    def _normalise_month(cls, value: date) -> date:
        """Store every month as its first day.

        Args:
            value: Any date in the month.

        Returns:
            date: The first of that month.
        """
        return first_of_month(value)


class MonthlyLeadsResponse(BaseModel):
    """A department's leads for one month, with what the department calls them.

    `title` is None when the department does not use the feature, in which case `leads` is
    always empty and the frontend renders nothing.
    """

    title: str | None = None
    month: date
    leads: list[MonthlyLeadResponse] = []
