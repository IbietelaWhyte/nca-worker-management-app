from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.workers.models import Worker


# A subteam overrides its whole band or inherits its whole band. Half-set is unrepresentable in
# the schema (chk_subteam_inherit_both) because the pair generation actually uses would otherwise
# live half in this row and half in the department's, where no constraint can see it.
def _validate_band(minimum: int | None, maximum: int | None) -> None:
    """Raise if a band is half-set or inverted.

    Args:
        minimum: The subteam's own floor, or None to inherit.
        maximum: The subteam's own ceiling, or None to inherit.

    Raises:
        ValueError: If exactly one bound is set, or the maximum is below the minimum.
    """
    if (minimum is None) != (maximum is None):
        raise ValueError("Set both the fewest and the most workers, or neither to use the department's")
    if minimum is not None and maximum is not None and maximum < minimum:
        raise ValueError("The most workers must be the same as the fewest, or more")


class Subteam(BaseModel):
    id: UUID
    name: str
    department_id: UUID
    description: str | None = None
    min_workers_per_slot: int | None = None
    max_workers_per_slot: int | None = None
    created_at: datetime


class SubteamCreate(BaseModel):
    name: str
    department_id: UUID
    description: str | None = None
    min_workers_per_slot: int | None = Field(default=None, ge=1)
    max_workers_per_slot: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_worker_range(self) -> "SubteamCreate":
        """Both bounds or neither, and the right way round.

        Returns:
            SubteamCreate: The validated model.

        Raises:
            ValueError: If the band is half-set or inverted.
        """
        _validate_band(self.min_workers_per_slot, self.max_workers_per_slot)
        return self


class SubteamResponse(Subteam):
    pass


class SubteamWithWorkersResponse(SubteamResponse):
    worker: Worker | None = None


class SubteamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    min_workers_per_slot: int | None = Field(default=None, ge=1)
    max_workers_per_slot: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_worker_range(self) -> "SubteamUpdate":
        """Both bounds or neither, and the right way round.

        Unlike DepartmentUpdate this *can* be checked here: clearing the band means sending both
        as null, so a PATCH that names one bound and not the other is always the half-set case.

        Returns:
            SubteamUpdate: The validated model.

        Raises:
            ValueError: If the band is half-set or inverted.
        """
        _validate_band(self.min_workers_per_slot, self.max_workers_per_slot)
        return self
