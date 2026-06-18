from app.router.account import router as account
from app.router.authentication import router as authentication
from app.router.availabilities import router as availabilities
from app.router.confirmation_tokens import router as confirmation_tokens
from app.router.department_roles import router as department_roles
from app.router.departments import router as departments
from app.router.schedules import router as schedules
from app.router.subteams import router as subteams
from app.router.workers import router as workers

__all__ = [
    "account",
    "workers",
    "departments",
    "department_roles",
    "schedules",
    "availabilities",
    "subteams",
    "authentication",
    "confirmation_tokens",
]
