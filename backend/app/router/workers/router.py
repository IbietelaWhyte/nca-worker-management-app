from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    CurrentUser,
    HODUser,
    get_department_service,
    get_worker_service,
)
from app.schemas.departments.models import DepartmentResponse
from app.schemas.models import TokenPayload
from app.schemas.workers.models import WorkerCreate, WorkerResponse, WorkerUpdate
from app.service.departments.service import DepartmentService
from app.service.workers.service import WorkerService

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("", response_model=list[WorkerResponse])
def list_workers(
    active_only: bool = Query(default=False),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: TokenPayload = CurrentUser,
    worker_service: WorkerService = Depends(get_worker_service),
) -> list[WorkerResponse]:
    """List workers visible to the requesting user, filtered by HOD/Assistant HOD scope.

    Args:
        active_only: If True, return only active workers.
        search: Optional search query to filter by worker name.
        limit: Max workers to return for the unfiltered listing (pagination).
        offset: Number of workers to skip for the unfiltered listing (pagination).
        current_user: Current authenticated user token.
        worker_service: Worker service dependency.

    Returns:
        list[WorkerResponse]: All workers for admins/workers, department-filtered for HOD/Assistant HOD.
    """
    return worker_service.list_visible_workers(
        current_user, active_only=active_only, search=search, limit=limit, offset=offset
    )


@router.get("/{worker_id}", response_model=WorkerResponse)
def get_worker(
    worker_id: UUID,
    _: TokenPayload = CurrentUser,
    service: WorkerService = Depends(get_worker_service),
) -> WorkerResponse:
    """Retrieve a specific worker by ID.

    Args:
        worker_id: Unique identifier of the worker.
        _: Current authenticated user token.
        service: Worker service dependency.

    Returns:
        WorkerResponse: The worker data.
    """
    return service.get_worker(worker_id)


@router.post("", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
def create_worker(
    data: WorkerCreate,
    department_id: UUID | None = Query(default=None, description="Optional department to assign worker to immediately"),
    current_user: TokenPayload = HODUser,
    service: WorkerService = Depends(get_worker_service),
    department_service: DepartmentService = Depends(get_department_service),
) -> WorkerResponse:
    """Create a new worker (admin or HOD), optionally assigning them to a department.

    Args:
        data: Worker creation data.
        department_id: Optional UUID of department to assign worker to immediately.
        current_user: Admin or HOD user token required.
        service: Worker service dependency.
        department_service: Department service dependency.

    Returns:
        WorkerResponse: The newly created worker.
    """
    # Authorize the department assignment before creating, so a forbidden request leaves no orphan worker.
    if department_id is not None:
        service.authorize_create_assignment(current_user, department_id)

    worker = service.create_worker(data)

    if department_id is not None:
        department_service.assign_worker(department_id, worker.id)

    return worker


@router.patch("/{worker_id}", response_model=WorkerResponse)
def update_worker(
    worker_id: UUID,
    data: WorkerUpdate,
    current_user: TokenPayload = HODUser,
    service: WorkerService = Depends(get_worker_service),
) -> WorkerResponse:
    """Update a worker's information (admin, or HOD/Assistant HOD managing the worker's department).

    Args:
        worker_id: Unique identifier of the worker to update.
        data: Partial worker data with fields to update.
        current_user: Admin or HOD user token required.
        service: Worker service dependency.

    Returns:
        WorkerResponse: The updated worker data.
    """
    service.authorize_update_worker(current_user, worker_id, data)
    return service.update_worker(worker_id, data)


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_worker(
    worker_id: UUID,
    current_user: TokenPayload = HODUser,
    service: WorkerService = Depends(get_worker_service),
) -> None:
    """Deactivate a worker (admin, or HOD/Assistant HOD managing the worker's department).

    Sets the worker's is_active flag to False rather than deleting the record.

    Args:
        worker_id: Unique identifier of the worker to deactivate.
        current_user: Admin or HOD user token required.
        service: Worker service dependency.
    """
    service.authorize_manage_worker(current_user, worker_id)
    service.deactivate_worker(worker_id)


@router.get("/{worker_id}/departments", response_model=list[DepartmentResponse])
def get_worker_departments(
    worker_id: UUID,
    _: TokenPayload = CurrentUser,
    service: WorkerService = Depends(get_worker_service),
) -> list[DepartmentResponse]:
    """Retrieve all departments a worker is assigned to.

    Args:
        worker_id: Unique identifier of the worker.
        _: Current authenticated user token.
        service: Worker service dependency.

    Returns:
        list[DepartmentResponse]: List of departments the worker belongs to.
    """
    return service.get_worker_departments(worker_id)
