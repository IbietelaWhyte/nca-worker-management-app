from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.schemas.models import AvailabilityType, DayOfWeek


class Availability(BaseModel):
    id: UUID
    worker_id: UUID
    availability_type: AvailabilityType
    day_of_week: DayOfWeek | None = None
    specific_date: date | None = None
    is_available: bool
    notes: str | None = None
    created_at: datetime


class AvailabilityCreate(BaseModel):
    worker_id: UUID
    availability_type: AvailabilityType
    day_of_week: DayOfWeek | None = None
    specific_date: date | None = None
    is_available: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def validate_availability_fields(self) -> "AvailabilityCreate":
        if self.availability_type == AvailabilityType.RECURRING and self.day_of_week is None:
            raise ValueError("day_of_week is required when availability_type is 'recurring'")
        if self.availability_type == AvailabilityType.SPECIFIC_DATE and self.specific_date is None:
            raise ValueError("specific_date is required when availability_type is 'specific_date'")
        return self


class AvailabilityResponse(Availability):
    @field_validator("day_of_week", mode="before")
    @classmethod
    def convert_day_of_week(cls, v: int | None) -> DayOfWeek | None:
        """Convert integer day_of_week from database to DayOfWeek enum"""
        if isinstance(v, int):
            return DayOfWeek.from_number(v)
        return v


class AvailabilityUpdate(BaseModel):
    availability_type: AvailabilityType | None = None
    day_of_week: DayOfWeek | None = None
    specific_date: date | None = None
    is_available: bool | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_availability_fields(self) -> "AvailabilityUpdate":
        # Only validate if availability_type is being set
        if self.availability_type is not None:
            if self.availability_type == AvailabilityType.RECURRING and self.day_of_week is None:
                raise ValueError("day_of_week is required when availability_type is 'recurring'")
            if self.availability_type == AvailabilityType.SPECIFIC_DATE and self.specific_date is None:
                raise ValueError("specific_date is required when availability_type is 'specific_date'")
        return self
