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
    _: TokenPayload = CurrentUser,
    service: WorkerService = Depends(get_worker_service),
) -> list[WorkerResponse]:
    """List all workers with optional filtering.
    
    Args:
        active_only: If True, return only active workers.
        search: Optional search query to filter by worker name.
        _: Current authenticated user token.
        service: Worker service dependency.
        
    Returns:
        list[WorkerResponse]: List of workers matching the criteria.
    """
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e))


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
