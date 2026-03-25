from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    HODUser,
    get_department_service,
    get_subteam_service,
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

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentResponse])
def list_departments(
    _: TokenPayload = CurrentUser,
    service: DepartmentService = Depends(get_department_service),
) -> list[DepartmentResponse]:
    """List all departments.

    Args:
        _: Current authenticated user token.
        service: Department service dependency.

    Returns:
        list[DepartmentResponse]: List of all departments.
    """
    return service.get_all_departments()


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

    Raises:
        HTTPException: 404 if department not found.
    """
    try:
        return service.get_department(department_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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

    Raises:
        HTTPException: 404 if department not found.
    """
    try:
        return service.get_department_with_workers(department_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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

    Raises:
        HTTPException: 409 if department with same name already exists.
    """
    try:
        return service.create_department(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


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

    Raises:
        HTTPException: 404 if department not found.
    """
    try:
        return service.update_department(department_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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

    Raises:
        HTTPException: 404 if department not found.
    """
    try:
        service.delete_department(department_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{department_id}/workers/{worker_id}", response_model=MessageResponse)
def assign_worker(
    department_id: UUID,
    worker_id: UUID,
    _: TokenPayload = HODUser,
    service: DepartmentService = Depends(get_department_service),
) -> MessageResponse:
    try:
        service.assign_worker(department_id, worker_id)
        return MessageResponse(message="Worker assigned successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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
    try:
        service.unassign_worker(department_id, worker_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{department_id}/hod/{worker_id}", response_model=DepartmentResponse)
def set_hod(
    department_id: UUID,
    worker_id: UUID,
    _: TokenPayload = AdminUser,
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    try:
        return service.set_hod(department_id, worker_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{department_id}/subteams", response_model=list[SubteamResponse])
def list_subteams(
    department_id: UUID,
    _: TokenPayload = CurrentUser,
    service: SubteamService = Depends(get_subteam_service),
) -> list[SubteamResponse]:
    return service.get_subteams_by_department(department_id)
