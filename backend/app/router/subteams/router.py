from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    HODUser,
    get_subteam_service,
)
from app.schemas.models import MessageResponse, TokenPayload
from app.schemas.subteams.models import (
    SubteamCreate,
    SubteamResponse,
    SubteamUpdate,
    SubteamWithWorkersResponse,
    SubteamWorkersAssign,
)
from app.service.subteams.service import SubteamService

router = APIRouter(prefix="/subteams", tags=["subteams"])


@router.get("/{subteam_id}", response_model=SubteamResponse)
def get_subteam(
    subteam_id: UUID,
    _: TokenPayload = CurrentUser,
    service: SubteamService = Depends(get_subteam_service),
) -> SubteamResponse:
    return service.get_subteam(subteam_id)


@router.get("/{subteam_id}/workers", response_model=list[SubteamWithWorkersResponse])
def get_subteam_with_workers(
    subteam_id: UUID,
    _: TokenPayload = CurrentUser,
    service: SubteamService = Depends(get_subteam_service),
) -> list[SubteamWithWorkersResponse]:
    """Get subteam with all assigned workers."""
    return service.get_subteam_with_workers(subteam_id)


@router.post("", response_model=SubteamResponse, status_code=status.HTTP_201_CREATED)
def create_subteam(
    data: SubteamCreate,
    _: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
) -> SubteamResponse:
    return service.create_subteam(data)


@router.patch("/{subteam_id}", response_model=SubteamResponse)
def update_subteam(
    subteam_id: UUID,
    data: SubteamUpdate,
    _: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
) -> SubteamResponse:
    return service.update_subteam(subteam_id, data)


@router.delete("/{subteam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subteam(
    subteam_id: UUID,
    _: TokenPayload = AdminUser,
    service: SubteamService = Depends(get_subteam_service),
) -> None:
    service.delete_subteam(subteam_id)


@router.post("/{subteam_id}/workers", response_model=MessageResponse)
def assign_workers_to_subteam(
    subteam_id: UUID,
    data: SubteamWorkersAssign,
    _: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
) -> MessageResponse:
    """Assign several workers to a subteam in one call.

    Every worker must already be assigned to the subteam's parent department; if any is not,
    none are assigned.
    """
    service.assign_workers(subteam_id, data.worker_ids)
    count = len(set(data.worker_ids))
    return MessageResponse(message=f"{count} {'worker' if count == 1 else 'workers'} assigned to subteam")


@router.delete(
    "/{subteam_id}/workers/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unassign_worker_from_subteam(
    subteam_id: UUID,
    worker_id: UUID,
    _: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
) -> None:
    """Remove a worker's assignment from a subteam."""
    service.unassign_worker(subteam_id, worker_id)
