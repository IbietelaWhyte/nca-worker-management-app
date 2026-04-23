from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

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
    search: str | None = Query(default=None),
    current_user: TokenPayload = CurrentUser,
    worker_service: WorkerService = Depends(get_worker_service),
    department_service: DepartmentService = Depends(get_department_service),
) -> list[WorkerResponse]:
    """List workers - filtered by HOD or Assistant HOD role if applicable.

    Args:
        active_only: If True, return only active workers.
        search: Optional search query to filter by worker name.
        current_user: Current authenticated user token.
        service: Worker service dependency.

    Returns:
        list[WorkerResponse]: List of workers (all for admin, department-filtered for HOD or Assistant HOD).

    Raises:
        HTTPException: 404 if HOD's or Assistant HOD's worker profile not found.
    """
    # Admin sees all workers (with filters)
    print(f"Current user role: {current_user.role}")
    if current_user.role == "admin":
        if search:
            return worker_service.search_workers(search)
        if active_only:
            return worker_service.get_active_workers()
        return worker_service.get_all_workers()

    # HOD or Assistant HOD sees only workers in their departments
    if current_user.role == "hod" or current_user.role == "assistant_hod":
        # Get worker record from email in JWT token
        if not current_user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not found in authentication token",
            )
        worker = worker_service.worker_repo.get_by_email(current_user.email)
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Worker profile not found for authenticated user",
            )

        # Get departments where this worker is HOD
        if current_user.role == "hod":
            hod_departments = department_service.get_departments_by_hod(worker.id)
        else:  # assistant_hod
            hod_departments = department_service.get_assistant_hod_departments(worker.id)
        if not hod_departments:
            return []

        # Collect all workers from HOD's departments (with deduplication)
        workers_dict = {}
        for dept in hod_departments:
            dept_workers = worker_service.get_workers_by_department(dept.id)
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
        return worker_service.search_workers(search)
    if active_only:
        return worker_service.get_active_workers()
    return worker_service.get_all_workers()


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
    department_id: UUID | None = Query(default=None, description="Optional department to assign worker to immediately"),
    current_user: TokenPayload = HODUser,
    service: WorkerService = Depends(get_worker_service),
) -> WorkerResponse:
    """Create a new worker (admin or HOD).

    Args:
        data: Worker creation data.
        department_id: Optional UUID of department to assign worker to immediately.
        current_user: Admin or HOD user token required.
        service: Worker service dependency.

    Returns:
        WorkerResponse: The newly created worker.

    Raises:
        HTTPException: 409 if worker with same contact info already exists.
        HTTPException: 403 if HOD tries to assign to department they don't manage.
    """
    try:
        # Create the worker
        worker = service.create_worker(data)

        # If department_id provided, assign worker to that department
        if department_id:
            # For non-admin users, verify they manage this department
            if current_user.role != "admin":
                if not current_user.email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email not found in authentication token",
                    )
                hod_worker = service.worker_repo.get_by_email(current_user.email)
                if not hod_worker:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Worker profile not found for authenticated user",
                    )

                # Check if HOD manages the specified department
                hod_departments = service.department_repo.get_departments_by_hod(hod_worker.id)
                if not any(dept.id == department_id for dept in hod_departments):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only assign workers to departments you manage",
                    )

            # Assign worker to department
            service.department_repo.assign_worker(department_id, worker.id)

        return worker
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/{worker_id}", response_model=WorkerResponse)
def update_worker(
    worker_id: UUID,
    data: WorkerUpdate,
    current_user: TokenPayload = HODUser,
    service: WorkerService = Depends(get_worker_service),
    department_service: DepartmentService = Depends(get_department_service),
) -> WorkerResponse:
    """Update a worker's information (admin or HOD managing worker's department).

    Args:
        worker_id: Unique identifier of the worker to update.
        data: Partial worker data with fields to update.
        current_user: Admin or HOD user token required.
        service: Worker service dependency.
        department_service: Department service dependency.

    Returns:
        WorkerResponse: The updated worker data.

    Raises:
        HTTPException: 404 if worker not found.
        HTTPException: 403 if HOD tries to update worker not in their departments.
        HTTPException: 403 if HOD tries to assign restricted roles.
        HTTPException: 403 if HOD tries to assign assistant_hod for departments they don't manage.
    """
    try:
        # Admins can update any worker
        if current_user.role != "admin":
            # HODs/Assistant HODs can only update workers in their departments
            if not current_user.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email not found in authentication token",
                )
            manager_worker = service.worker_repo.get_by_email(current_user.email)
            if not manager_worker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Worker profile not found for authenticated user",
                )

            # Check if manager can manage this worker
            if not service.can_manage_worker(manager_worker.id, worker_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only update workers in departments you manage",
                )

            # Restrict roles that HODs/Assistant HODs can assign
            if data.roles is not None:
                restricted_roles = {"admin", "hod"}
                if any(role in restricted_roles for role in data.roles):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="HODs can only assign worker and assistant_hod roles",
                    )

            # For assistant_hod departments, ensure they manage those departments
            if data.assistant_hod_departments is not None:
                # Get departments this manager oversees
                hod_departments = department_service.get_departments_by_hod(manager_worker.id)
                assistant_hod_dept_ids = department_service.department_repo.get_assistant_hod_departments(
                    manager_worker.id
                )
                managed_dept_ids = {dept.id for dept in hod_departments} | set(assistant_hod_dept_ids)

                for dept_id in data.assistant_hod_departments:
                    if dept_id not in managed_dept_ids:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="You can only assign assistant_hod for departments you manage",
                        )

        return service.update_worker(worker_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_worker(
    worker_id: UUID,
    current_user: TokenPayload = HODUser,
    service: WorkerService = Depends(get_worker_service),
) -> None:
    """Deactivate a worker (admin or HOD managing worker's department).

    Sets the worker's is_active flag to False rather than deleting the record.

    Args:
        worker_id: Unique identifier of the worker to deactivate.
        current_user: Admin or HOD user token required.
        service: Worker service dependency.

    Raises:
        HTTPException: 404 if worker not found.
        HTTPException: 403 if HOD tries to deactivate worker not in their departments.
    """
    try:
        # Admins can deactivate any worker
        if current_user.role != "admin":
            # HODs can only deactivate workers in their departments
            if not current_user.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email not found in authentication token",
                )
            hod_worker = service.worker_repo.get_by_email(current_user.email)
            if not hod_worker:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Worker profile not found for authenticated user",
                )

            # Check if HOD can manage this worker
            if not service.can_manage_worker(hod_worker.id, worker_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only deactivate workers in departments you manage",
                )

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
