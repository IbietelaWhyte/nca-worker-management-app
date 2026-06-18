from uuid import UUID

from pydantic import BaseModel


class DepartmentRole(BaseModel):
    id: UUID
    name: str
    department_id: UUID
    description: str | None = None


class DepartmentRoleCreate(BaseModel):
    name: str
    department_id: UUID
    description: str | None = None


class DepartmentRoleResponse(DepartmentRole):
    pass


class DepartmentRoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
