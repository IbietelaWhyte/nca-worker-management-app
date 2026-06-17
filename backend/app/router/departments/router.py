from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    HODUser,
    get_department_service,
    get_subteam_service,
    get_worker_service,
)
from app.schemas.departments.models import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    DepartmentWithWorkersResponse,
)
from app.schemas.models import MessageResponse, TokenPayload
from app.schemas.subteams.models import SubteamResponse
from app.service.departments.service import DepartmentService
from app.service.subteams.service import SubteamService
from app.service.workers.service import WorkerService

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentResponse])
def list_departments(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: TokenPayload = CurrentUser,
    service: DepartmentService = Depends(get_department_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> list[DepartmentResponse]:
    """List departments - filtered by HOD or Assistant HOD role if applicable.

    Args:
        limit: Max departments to return for the admin/worker listing (pagination).
        offset: Number of departments to skip for the admin/worker listing (pagination).
        current_user: Current authenticated user token.
        service: Department service dependency.
        worker_service: Worker service dependency.

    Returns:
        list[DepartmentResponse]: All departments for admin/worker, managed-only for HOD/Assistant HOD.
    """
    # HOD or Assistant HOD sees only their departments; admins and regular workers see all.
    if current_user.role == "hod" or current_user.role == "assistant_hod":
        worker = worker_service.get_worker_for_token(current_user)
        if current_user.role == "hod":
            return service.get_departments_by_hod(worker.id)
        return service.get_assistant_hod_departments(worker.id)

    return service.get_all_departments(limit=limit, offset=offset)


@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department(
    department_id: UUID,
    _: TokenPayload = CurrentUser,
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    """Retrieve a specific department by ID.

    Args:
        department_id: Unique identifier of the department.
        _: Current authenticated user token.
        service: Department service dependency.

    Returns:
        DepartmentResponse: The department data.
    """
    return service.get_department(department_id)


@router.get("/{department_id}/workers", response_model=DepartmentWithWorkersResponse)
def get_department_with_workers(
    department_id: UUID,
    _: TokenPayload = CurrentUser,
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentWithWorkersResponse:
    """Retrieve a department with all assigned workers embedded.

    Args:
        department_id: Unique identifier of the department.
        _: Current authenticated user token.
        service: Department service dependency.

    Returns:
        DepartmentWithWorkersResponse: Department with worker details.
    """
    return service.get_department_with_workers(department_id)


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    data: DepartmentCreate,
    _: TokenPayload = AdminUser,
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    """Create a new department (admin only).

    Args:
        data: Department creation data.
        _: Admin user token required.
        service: Department service dependency.

    Returns:
        DepartmentResponse: The newly created department.
    """
    return service.create_department(data)


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: UUID,
    data: DepartmentUpdate,
    _: TokenPayload = AdminUser,
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    """Update a department's information (admin only).

    Args:
        department_id: Unique identifier of the department to update.
        data: Partial department data with fields to update.
        _: Admin user token required.
        service: Department service dependency.

    Returns:
        DepartmentResponse: The updated department data.
    """
    return service.update_department(department_id, data)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: UUID,
    _: TokenPayload = AdminUser,
    service: DepartmentService = Depends(get_department_service),
) -> None:
    """Delete a department (admin only).

    Args:
        department_id: Unique identifier of the department to delete.
        _: Admin user token required.
        service: Department service dependency.
    """
    service.delete_department(department_id)


@router.post("/{department_id}/workers/{worker_id}", response_model=MessageResponse)
def assign_worker(
    department_id: UUID,
    worker_id: UUID,
    _: TokenPayload = HODUser,
    service: DepartmentService = Depends(get_department_service),
) -> MessageResponse:
    service.assign_worker(department_id, worker_id)
    return MessageResponse(message="Worker assigned successfully")


@router.delete(
    "/{department_id}/workers/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unassign_worker(
    department_id: UUID,
    worker_id: UUID,
    _: TokenPayload = HODUser,
    service: DepartmentService = Depends(get_department_service),
) -> None:
    service.unassign_worker(department_id, worker_id)


@router.patch("/{department_id}/hod/{worker_id}", response_model=DepartmentResponse)
def set_hod(
    department_id: UUID,
    worker_id: UUID,
    _: TokenPayload = AdminUser,
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    return service.set_hod(department_id, worker_id)


@router.get("/{department_id}/subteams", response_model=list[SubteamResponse])
def list_subteams(
    department_id: UUID,
    _: TokenPayload = CurrentUser,
    service: SubteamService = Depends(get_subteam_service),
) -> list[SubteamResponse]:
    return service.get_subteams_by_department(department_id)
