from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.workers.models import Worker


class Subteam(BaseModel):
    id: UUID
    name: str
    department_id: UUID
    description: str | None = None
    workers_per_slot: int | None = None
    created_at: datetime


class SubteamCreate(BaseModel):
    name: str
    description: str | None = None
    workers_per_slot: int | None = None


class SubteamResponse(Subteam):
    pass


class SubteamWithWorkersResponse(SubteamResponse):
    worker: Worker | None = None
    

class SubteamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workers_per_slot: int | None = None
