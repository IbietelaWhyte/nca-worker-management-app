from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.department_roles.models import DepartmentRoleResponse
from app.schemas.workers.models import Worker


class WorkerWithDepartmentRole(Worker):
    """A department member with their standing role in that department (if any)."""

    department_role: DepartmentRoleResponse | None = None


class Department(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    hod_id: UUID | None = None
    workers_per_slot: int
    created_at: datetime


class DepartmentCreate(BaseModel):
    name: str
    description: str | None = None
    hod_id: UUID | None = None
    workers_per_slot: int = 1


class DepartmentResponse(Department):
    pass


class DepartmentWithWorkersResponse(DepartmentResponse):
    workers: list[WorkerWithDepartmentRole] = []


class DepartmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    hod_id: UUID | None = None
    workers_per_slot: int | None = None
