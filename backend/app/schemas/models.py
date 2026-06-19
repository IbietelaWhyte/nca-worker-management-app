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

    @classmethod
    def from_number(cls, day: int) -> "DayOfWeek":
        """Convert from 0-6 (Sunday=0) to DayOfWeek enum"""
        return list(cls)[day]


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
    ASSISTANT_HOD = "assistant_hod"
    WORKER = "worker"


def highest_role(roles: list[UserRole]) -> UserRole:
    """Return the most privileged role (admin > hod > assistant_hod > worker).

    The single role carried in a JWT's app_metadata must reflect a worker's most privileged
    role, since authorization reads only that one value. UserRole is declared in
    descending-privilege order, so the most privileged role is the earliest in the enum.
    Defaults to WORKER for an empty list.
    """
    order = list(UserRole)
    return min(roles, key=order.index, default=UserRole.WORKER)


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
