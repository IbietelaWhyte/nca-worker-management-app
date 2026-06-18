from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    CurrentUser,
    HODUser,
    get_department_role_service,
)
from app.schemas.department_roles.models import (
    DepartmentRoleCreate,
    DepartmentRoleResponse,
    DepartmentRoleUpdate,
)
from app.schemas.models import MessageResponse, TokenPayload
from app.service.department_roles.service import DepartmentRoleService

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/{role_id}", response_model=DepartmentRoleResponse)
def get_role(
    role_id: UUID,
    _: TokenPayload = CurrentUser,
    service: DepartmentRoleService = Depends(get_department_role_service),
) -> DepartmentRoleResponse:
    return service.get_role(role_id)


@router.post("", response_model=DepartmentRoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    data: DepartmentRoleCreate,
    _: TokenPayload = HODUser,
    service: DepartmentRoleService = Depends(get_department_role_service),
) -> DepartmentRoleResponse:
    return service.create_role(data)


@router.patch("/{role_id}", response_model=DepartmentRoleResponse)
def update_role(
    role_id: UUID,
    data: DepartmentRoleUpdate,
    _: TokenPayload = HODUser,
    service: DepartmentRoleService = Depends(get_department_role_service),
) -> DepartmentRoleResponse:
    return service.update_role(role_id, data)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: UUID,
    _: TokenPayload = HODUser,
    service: DepartmentRoleService = Depends(get_department_role_service),
) -> None:
    service.delete_role(role_id)


@router.post("/{role_id}/workers/{worker_id}", response_model=MessageResponse)
def assign_worker_role(
    role_id: UUID,
    worker_id: UUID,
    _: TokenPayload = HODUser,
    service: DepartmentRoleService = Depends(get_department_role_service),
) -> MessageResponse:
    """Assign a department role to a worker.

    Requires the worker to already be assigned to the role's parent department.
    """
    service.assign_worker(role_id, worker_id)
    return MessageResponse(message="Role assigned to worker successfully")


@router.delete(
    "/{role_id}/workers/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unassign_worker_role(
    role_id: UUID,
    worker_id: UUID,
    _: TokenPayload = HODUser,
    service: DepartmentRoleService = Depends(get_department_role_service),
) -> None:
    """Clear a worker's department role."""
    service.unassign_worker(role_id, worker_id)
