from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator

from app.core.phone import normalize_phone
from app.schemas.models import UserRole


class Worker(BaseModel):
    id: UUID
    auth_user_id: UUID | None = Field(default=None, exclude=True)  # Exclude from serialization
    first_name: str
    last_name: str
    # Mirrors the database: workers.email is NOT NULL UNIQUE, workers.phone is nullable.
    phone: str | None = None
    email: str
    is_active: bool
    created_at: datetime


class WorkerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = None

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
        # Reminders are sent over SMS, so a stored number must always be dialable.
        return normalize_phone(value) if value else None


class WorkerResponse(Worker):
    roles: list[UserRole] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_account(self) -> bool:
        """Whether this worker has a Supabase login account (without leaking the auth_user_id)."""
        return self.auth_user_id is not None


class WorkerUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = None
    email: EmailStr | None = None
    roles: list[UserRole] | None = Field(default=None, min_length=1, description="Must include at least one role")
    assistant_hod_departments: list[UUID] | None = Field(default=None, description="Departments for assistant_hod role")

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="after")
    @classmethod
    def _lowercase_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else value

    @field_validator("phone", mode="after")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None


class WorkerContactMatch(BaseModel):
    """An existing worker that a CSV row's email or phone collides with."""

    worker_id: UUID
    is_active: bool


class WorkerImportRow(BaseModel):
    """One validated row of a bulk worker import CSV.

    Kept separate from WorkerCreate so import failures can be reported per column with a message a
    non-technical user can act on, rather than leaking raw Pydantic error text into the UI. Phone is
    required here (unlike WorkerCreate) because an imported worker who cannot receive SMS reminders
    is not much use, and the CSV template asks for it.
    """

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="after")
    @classmethod
    def _lowercase_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("phone", mode="after")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return normalize_phone(value)


# Outcome of a single CSV row.
#   "valid"             - would be created (dry run only)
#   "created"           - was created
#   "duplicate"         - matches an existing active worker
#   "duplicate_inactive"- matches an existing deactivated worker; the fix is reactivation, not import
#   "error"             - failed validation; blocks the whole file
WorkerImportRowStatus = Literal["valid", "created", "duplicate", "duplicate_inactive", "error"]


class WorkerImportRowResult(BaseModel):
    # Line number as the user's spreadsheet shows it — the header counts as line 1.
    line_number: int
    status: WorkerImportRowStatus
    name: str | None = None
    email: str | None = None
    field: str | None = None  # Which column is at fault, for error rows.
    value: str | None = None  # The offending value, echoed back so the user can find it.
    error: str | None = None
    worker_id: UUID | None = None


class WorkerImportResult(BaseModel):
    dry_run: bool
    # Whether the import would proceed (dry run) or did proceed. False when any row failed
    # validation, or when duplicates were found and the caller did not opt into skipping them.
    ok: bool
    total_rows: int
    valid: int
    created: int  # Always 0 on a dry run.
    duplicates: int
    duplicates_inactive: int
    errors: int
    results: list[WorkerImportRowResult]
