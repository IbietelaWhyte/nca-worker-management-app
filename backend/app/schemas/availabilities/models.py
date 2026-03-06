from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.models import AvailabilityType, DayOfWeek


class Availability(BaseModel):
    id: UUID
    worker_id: UUID
    availability_type: AvailabilityType
    day_of_week: DayOfWeek
    specific_date: datetime | None = None
    is_available: bool
    notes: str | None = None
    created_at: datetime


class AvailabilityCreate(BaseModel):
    worker_id: UUID
    availability_type: AvailabilityType
    day_of_week: DayOfWeek
    specific_date: datetime | None = None
    is_available: bool
    notes: str | None = None


class AvailabilityResponse(Availability):
    pass


class AvailabilityUpdate(BaseModel):
    availability_type: AvailabilityType | None = None
    day_of_week: DayOfWeek | None = None
    specific_date: datetime | None = None
    is_available: bool | None = None
    notes: str | None = None
