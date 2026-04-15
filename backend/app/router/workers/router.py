from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    get_worker_service,
)
from app.schemas.departments.models import DepartmentResponse
from app.schemas.models import TokenPayload
from app.schemas.workers.models import WorkerCreate, WorkerResponse, WorkerUpdate
from app.service.workers.service import WorkerService

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("", response_model=list[WorkerResponse])
def list_workers(
    active_only: bool = Query(default=False),
    search: str | None = Query(default=None),
    current_user: TokenPayload = CurrentUser,
    service: WorkerService = Depends(get_worker_service),
) -> list[WorkerResponse]:
    """List workers - filtered by HOD role if applicable.

    Args:
        active_only: If True, return only active workers.
        search: Optional search query to filter by worker name.
        current_user: Current authenticated user token.
        service: Worker service dependency.

    Returns:
        list[WorkerResponse]: List of workers (all for admin, department-filtered for HOD).

    Raises:
        HTTPException: 404 if HOD's worker profile not found.
    """
    # Admin sees all workers (with filters)
    if current_user.role == "admin":
        if search:
            return service.search_workers(search)
        if active_only:
            return service.get_active_workers()
        return service.get_all_workers()

    # HOD sees only workers in their departments
    if current_user.role == "hod":
        # Get worker record from email in JWT token
        if not current_user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not found in authentication token",
            )
        worker = service.worker_repo.get_by_email(current_user.email)
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Worker profile not found for authenticated user",
            )

        # Get departments where this worker is HOD
        hod_departments = service.department_repo.get_departments_by_hod(worker.id)

        if not hod_departments:
            return []

        # Collect all workers from HOD's departments (with deduplication)
        workers_dict = {}
        for dept in hod_departments:
            dept_workers = service.get_workers_by_department(dept.id)
            for w in dept_workers:
                workers_dict[w.id] = w

        workers = list(workers_dict.values())

        # Apply filters
        if search:
            search_lower = search.lower()
            workers = [
                w for w in workers if search_lower in w.first_name.lower() or search_lower in w.last_name.lower()
            ]
        if active_only:
            workers = [w for w in workers if w.is_active]

        return workers

    # Regular workers see all workers (for collaboration purposes)
    if search:
        return service.search_workers(search)
    if active_only:
        return service.get_active_workers()
    return service.get_all_workers()


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

    Raises:
        HTTPException: 404 if worker not found.
    """
    try:
        return service.get_worker(worker_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
def create_worker(
    data: WorkerCreate,
    _: TokenPayload = AdminUser,
    service: WorkerService = Depends(get_worker_service),
) -> WorkerResponse:
    """Create a new worker (admin only).

    Args:
        data: Worker creation data.
        _: Admin user token required.
        service: Worker service dependency.

    Returns:
        WorkerResponse: The newly created worker.

    Raises:
        HTTPException: 409 if worker with same contact info already exists.
    """
    try:
        return service.create_worker(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/{worker_id}", response_model=WorkerResponse)
def update_worker(
    worker_id: UUID,
    data: WorkerUpdate,
    _: TokenPayload = AdminUser,
    service: WorkerService = Depends(get_worker_service),
) -> WorkerResponse:
    """Update a worker's information (admin only).

    Args:
        worker_id: Unique identifier of the worker to update.
        data: Partial worker data with fields to update.
        _: Admin user token required.
        service: Worker service dependency.

    Returns:
        WorkerResponse: The updated worker data.

    Raises:
        HTTPException: 404 if worker not found.
    """
    try:
        return service.update_worker(worker_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_worker(
    worker_id: UUID,
    _: TokenPayload = AdminUser,
    service: WorkerService = Depends(get_worker_service),
) -> None:
    """Deactivate a worker (admin only).

    Sets the worker's is_active flag to False rather than deleting the record.

    Args:
        worker_id: Unique identifier of the worker to deactivate.
        _: Admin user token required.
        service: Worker service dependency.

    Raises:
        HTTPException: 404 if worker not found.
    """
    try:
        service.deactivate_worker(worker_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{worker_id}/departments", response_model=list)
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

    Raises:
        HTTPException: 404 if worker not found.
    """
    try:
        return service.get_worker_departments(worker_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
