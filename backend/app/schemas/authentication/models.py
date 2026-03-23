from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    password: str


class RegisterResponse(BaseModel):
    message: str
    worker_id: str
    email: str
