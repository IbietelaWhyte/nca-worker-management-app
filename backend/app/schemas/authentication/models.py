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
