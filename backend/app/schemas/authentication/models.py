from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.schemas.models import UserRole


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    password: str
    role: UserRole = UserRole.WORKER
    department_ids: list[str] | None = None


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
