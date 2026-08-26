from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.phone import normalize_phone
from app.schemas.models import UserRole


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = None
    password: str
    role: UserRole = UserRole.WORKER
    department_ids: list[str] | None = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="after")
    @classmethod
    def _lowercase_email(cls, value: str) -> str:
        # The workers.email unique index is case-sensitive, so store one canonical form.
        return value.strip().lower()

    @field_validator("phone", mode="after")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        # Every entry path must store a dialable number, or the SMS reminder fails silently later.
        return normalize_phone(value) if value else None


class RegisterResponse(BaseModel):
    message: str
    worker_id: str
    email: str


class GrantAccountRequest(BaseModel):
    password: str
    role: UserRole = UserRole.WORKER
    # Departments this worker should manage as assistant HOD. Only used when role is assistant_hod;
    # creates department_assistant_hods rows so the assignment actually grants management access.
    assistant_hod_departments: list[UUID] | None = None
