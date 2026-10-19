from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.department_roles.models import DepartmentRoleResponse
from app.schemas.subteams.models import SubteamResponse
from app.schemas.workers.models import Worker


class WorkerWithDepartmentRole(Worker):
    """A department member with their standing role and subteam in that department (if any).

    Both come from the `worker_departments` junction rather than the worker, because both are
    facts about this membership: the same person can hold a different role in another
    department. `subteam` is None for a member who is in the department but in no subteam.
    """

    department_role: DepartmentRoleResponse | None = None
    subteam: SubteamResponse | None = None


class Department(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    hod_id: UUID | None = None
    min_workers_per_slot: int
    max_workers_per_slot: int
    # What this department calls its monthly leads ("Teacher of the Month"); None turns them off.
    monthly_lead_title: str | None = None
    created_at: datetime


def _blank_title_to_none(value: str | None) -> str | None:
    """Treat a blank monthly-lead title as no title, so clearing the field turns the feature off.

    Args:
        value: The submitted title.

    Returns:
        str | None: The trimmed title, or None if it was blank.
    """
    if value is None:
        return None
    return value.strip() or None


class DepartmentCreate(BaseModel):
    name: str
    description: str | None = None
    hod_id: UUID | None = None
    min_workers_per_slot: int = Field(default=1, ge=1)
    max_workers_per_slot: int = Field(default=1, ge=1)
    monthly_lead_title: str | None = Field(default=None, max_length=60)

    @field_validator("monthly_lead_title")
    @classmethod
    def _normalise_title(cls, value: str | None) -> str | None:
        """See _blank_title_to_none."""
        return _blank_title_to_none(value)

    @model_validator(mode="after")
    def validate_worker_range(self) -> "DepartmentCreate":
        """Reject the band the DB would reject anyway, with a message a person can act on.

        Same reasoning as AvailabilityPromptCreate: chk_dept_worker_range catches this, but a
        constraint violation surfaces as a 500 with a constraint name in it.

        Returns:
            DepartmentCreate: The validated model.

        Raises:
            ValueError: If the maximum is below the minimum.
        """
        if self.max_workers_per_slot < self.min_workers_per_slot:
            raise ValueError("The most workers must be the same as the fewest, or more")
        return self


class DepartmentResponse(Department):
    pass


class DepartmentWithWorkersResponse(DepartmentResponse):
    workers: list[WorkerWithDepartmentRole] = []


class DepartmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    hod_id: UUID | None = None
    # No cross-field validator here: a PATCH may carry one bound and not the other, so the pair
    # can only be judged against the merged row — DepartmentService.update does that.
    min_workers_per_slot: int | None = Field(default=None, ge=1)
    max_workers_per_slot: int | None = Field(default=None, ge=1)
    # Unlike the fields above, an explicit null here is meaningful — it turns monthly leads off —
    # so DepartmentService.update_department writes it whenever it was sent, null included.
    monthly_lead_title: str | None = Field(default=None, max_length=60)

    @field_validator("monthly_lead_title")
    @classmethod
    def _normalise_title(cls, value: str | None) -> str | None:
        """See _blank_title_to_none."""
        return _blank_title_to_none(value)
