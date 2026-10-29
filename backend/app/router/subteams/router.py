from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    HODUser,
    get_subteam_service,
    get_worker_service,
)
from app.schemas.models import MessageResponse, TokenPayload
from app.schemas.subteams.models import (
    RoleRequirement,
    RoleRequirementsSet,
    SubteamCreate,
    SubteamResponse,
    SubteamUpdate,
    SubteamWithWorkersResponse,
    SubteamWorkersAssign,
)
from app.service.subteams.service import SubteamService
from app.service.workers.service import WorkerService

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
    token: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> list[SubteamWithWorkersResponse]:
    """Get subteam with all assigned workers (their contact details included), for its department's heads."""
    worker_service.authorize_create_assignment(token, service.get_subteam(subteam_id).department_id)
    return service.get_subteam_with_workers(subteam_id)


@router.post("", response_model=SubteamResponse, status_code=status.HTTP_201_CREATED)
def create_subteam(
    data: SubteamCreate,
    token: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> SubteamResponse:
    worker_service.authorize_create_assignment(token, data.department_id)
    return service.create_subteam(data)


@router.patch("/{subteam_id}", response_model=SubteamResponse)
def update_subteam(
    subteam_id: UUID,
    data: SubteamUpdate,
    token: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> SubteamResponse:
    worker_service.authorize_create_assignment(token, service.get_subteam(subteam_id).department_id)
    return service.update_subteam(subteam_id, data)


@router.put("/{subteam_id}/role-requirements", response_model=list[RoleRequirement])
def set_subteam_role_requirements(
    subteam_id: UUID,
    data: RoleRequirementsSet,
    token: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> list[RoleRequirement]:
    """Replace the minimum count of each role on this subteam's generated rotas."""
    worker_service.authorize_create_assignment(token, service.get_subteam(subteam_id).department_id)
    return service.set_role_requirements(subteam_id, data)


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
    token: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> MessageResponse:
    """Assign several workers to a subteam in one call.

    Every worker must already be assigned to the subteam's parent department; if any is not,
    none are assigned.
    """
    worker_service.authorize_create_assignment(token, service.get_subteam(subteam_id).department_id)
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
    token: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> None:
    """Remove a worker's assignment from a subteam."""
    worker_service.authorize_create_assignment(token, service.get_subteam(subteam_id).department_id)
    service.unassign_worker(subteam_id, worker_id)
