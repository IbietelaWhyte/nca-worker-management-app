from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DayOfWeek(StrEnum):
    SUNDAY = "sunday"
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"

    def to_number(self) -> int:
        """Convert to 0-6 where Sunday=0"""
        return list(DayOfWeek).index(self)


class WorkerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AssignmentStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DECLINED = "declined"


class UserRole(StrEnum):
    ADMIN = "admin"
    HOD = "hod"
    WORKER = "worker"


class TokenPayload(BaseModel):
    sub: str  # Supabase user UUID
    role: str = UserRole.WORKER
    email: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    message: str


class AvailabilityType(StrEnum):
    SPECIFIC_DATE = "specific_date"
    RECURRING = "recurring"
