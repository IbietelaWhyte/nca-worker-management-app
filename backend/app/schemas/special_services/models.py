from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, model_validator

from app.schemas.models import DayOfWeek

# Matches special_services.week_of_month: 1-4 are the first four occurrences, 5 is a fifth that
# most months do not have, and -1 is the last whichever that turns out to be.
LAST_WEEK_OF_MONTH = -1


class SpecialServiceKind(StrEnum):
    RECURRING = "recurring"
    ONE_OFF = "one_off"


def _day_of_week_from_db(value: object) -> object:
    """Accept the smallint the column holds as well as the name the API speaks.

    The column stores 0-6 with Sunday as 0; every other API surface in this app names the
    day. Converting here rather than in the router means a read straight off the repository
    and a request body both land on the same enum.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return DayOfWeek.from_number(value)
    return value


ApiDayOfWeek = Annotated[DayOfWeek | None, BeforeValidator(_day_of_week_from_db)]


class SpecialService(BaseModel):
    """A date the church treats as bigger than an ordinary service.

    Either a recurring rule ("the first Sunday of every month") or a named one-off. One model
    for both, matching the single table and the way `availability` already handles two modes:
    the kind says which of the nullable fields are populated.
    """

    id: UUID
    name: str
    kind: SpecialServiceKind
    day_of_week: ApiDayOfWeek = None
    week_of_month: int | None = None
    service_date: date | None = None
    is_active: bool = True
    # ON DELETE SET NULL on the FK: removing the admin who added a rule leaves the rule
    # standing. Typed non-optional, this raises a ValidationError on the first such read.
    created_by: UUID | None = None
    created_at: datetime


class SpecialServiceCreate(BaseModel):
    """A new rule or named date.

    The kind/field pairing is enforced twice — here and in Postgres check constraints. The
    Pydantic copy exists to give a person a message they can act on rather than a 500 carrying
    a constraint name.
    """

    name: str = Field(min_length=1, max_length=100)
    kind: SpecialServiceKind
    day_of_week: DayOfWeek | None = None
    week_of_month: int | None = Field(default=None, ge=LAST_WEEK_OF_MONTH, le=5)
    service_date: date | None = None

    @model_validator(mode="after")
    def validate_kind_fields(self) -> "SpecialServiceCreate":
        if self.kind == SpecialServiceKind.RECURRING:
            if self.day_of_week is None or self.week_of_month is None:
                raise ValueError("a recurring rule needs both a day_of_week and a week_of_month")
            if self.week_of_month == 0:
                raise ValueError("week_of_month must be 1-5, or -1 for the last of the month")
            if self.service_date is not None:
                raise ValueError("a recurring rule cannot have a service_date")
        else:
            if self.service_date is None:
                raise ValueError("a one-off needs a service_date")
            if self.day_of_week is not None or self.week_of_month is not None:
                raise ValueError("a one-off cannot have a day_of_week or week_of_month")
        return self


class SpecialServiceUpdate(BaseModel):
    """What may be changed after the fact.

    Deliberately narrow. Editing a rule's day or week would move a date that rotas have
    already been generated against; deactivate it and add the replacement instead, which
    leaves the history of what was special intact.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class SpecialDate(BaseModel):
    """One resolved occurrence: a real date and what to call it."""

    service_date: date
    name: str
