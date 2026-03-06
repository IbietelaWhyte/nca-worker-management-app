from app.router.availabilities import router as availabilities
from app.router.departments import router as departments
from app.router.schedules import router as schedules
from app.router.subteams import router as subteams
from app.router.workers import router as workers

__all__ = ["workers", "departments", "schedules", "availabilities", "subteams"]
