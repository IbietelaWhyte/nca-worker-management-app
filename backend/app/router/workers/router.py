from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    HODUser,
    get_authentication_service,
    get_department_service,
    get_worker_service,
)
from app.core.exceptions import BadRequestError
from app.schemas.authentication.models import GrantAccountRequest, RegisterResponse
from app.schemas.departments.models import DepartmentResponse
from app.schemas.models import TOTAL_COUNT_HEADER, TokenPayload, UserRole, WorkerStatus
from app.schemas.workers.models import WorkerCreate, WorkerResponse, WorkerUpdate
from app.service.authentication.service import AuthenticationService
from app.service.departments.service import DepartmentService
from app.service.workers.service import WorkerService

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("", response_model=list[WorkerResponse])
def list_workers(
    response: Response,
    active_only: bool = Query(default=False),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    department_id: UUID | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    status: WorkerStatus | None = Query(default=None),
    current_user: TokenPayload = CurrentUser,
    worker_service: WorkerService = Depends(get_worker_service),
) -> list[WorkerResponse]:
    """List workers visible to the requesting user, filtered by HOD/Assistant HOD scope.

    The body stays a plain array so existing callers are unaffected; the number of workers matching
    across all pages is returned in the ``X-Total-Count`` header for callers that page.

    Args:
        response: Outgoing response, used to set ``X-Total-Count``.
        active_only: If True, return only active workers (same as ``status=active``).
        search: Optional search over worker name and email.
        limit: Max workers to return (pagination).
        offset: Number of workers to skip (pagination).
        department_id: Optional department to filter by.
        role: Optional app role to filter by.
        status: Optional status to filter by: active, inactive or on_leave (today).
        current_user: Current authenticated user token.
        worker_service: Worker service dependency.

    Returns:
        list[WorkerResponse]: All workers for admins/workers, department-filtered for HOD/Assistant HOD.
    """
    workers, total = worker_service.list_visible_workers(
        current_user,
        active_only=active_only,
        search=search,
        limit=limit,
        offset=offset,
        department_id=department_id,
        role=role,
        status=status,
    )
    response.headers[TOTAL_COUNT_HEADER] = str(total)
    return workers


@router.get("/{worker_id}", response_model=WorkerResponse)
def get_worker(
    worker_id: UUID,
    current_user: TokenPayload = CurrentUser,
    service: WorkerService = Depends(get_worker_service),
) -> WorkerResponse:
    """Retrieve a specific worker by ID (admin, managing HOD/Assistant HOD, or the worker themselves).

    Args:
        worker_id: Unique identifier of the worker.
        current_user: Current authenticated user token.
        service: Worker service dependency.

    Returns:
        WorkerResponse: The worker data.
    """
    service.authorize_view_worker(current_user, worker_id)
    return service.get_worker(worker_id)


@router.post("", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
def create_worker(
    data: WorkerCreate,
    department_id: UUID | None = Query(default=None, description="Optional department to assign worker to immediately"),
    current_user: TokenPayload = HODUser,
    service: WorkerService = Depends(get_worker_service),
    department_service: DepartmentService = Depends(get_department_service),
) -> WorkerResponse:
    """Create a new worker (admin or HOD), assigning them to a department.

    The department is optional for an admin and required for a head of department.

    Args:
        data: Worker creation data.
        department_id: Department to assign the worker to; required unless the caller is an admin.
        current_user: Admin or HOD user token required.
        service: Worker service dependency.
        department_service: Department service dependency.

    Returns:
        WorkerResponse: The newly created worker.
    """
    # Authorize the department assignment before creating, so a forbidden request leaves no orphan worker.
    if department_id is not None:
        service.authorize_create_assignment(current_user, department_id)
    elif current_user.role != UserRole.ADMIN:
        # A head only sees workers in the departments they manage, so one created in none would
        # vanish from their view the moment it was saved — reachable only by an admin.
        raise BadRequestError("Choose one of your departments for the new worker")

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


@router.post("/{worker_id}/account", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def create_worker_account(
    worker_id: UUID,
    data: GrantAccountRequest,
    _: TokenPayload = AdminUser,
    auth_service: AuthenticationService = Depends(get_authentication_service),
) -> RegisterResponse:
    """Give an existing worker profile a Supabase login account (admin only).

    Creates a Supabase auth user with the provided password and role and links it to the worker
    record, so a profile created without a login can sign in.

    Args:
        worker_id: Unique identifier of the worker to grant an account to.
        data: The initial password and role for the new account.
        _: Admin user token required.
        auth_service: Authentication service dependency.

    Returns:
        RegisterResponse: Confirmation with the worker id and email.
    """
    return auth_service.create_account_for_worker(worker_id, data)


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
    service.authorize_manage_worker(current_user, worker_id, protect_heads=True)
    service.deactivate_worker(worker_id)


@router.delete("/{worker_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def delete_worker(
    worker_id: UUID,
    current_user: TokenPayload = HODUser,
    service: WorkerService = Depends(get_worker_service),
) -> None:
    """Permanently delete a worker (admin, or HOD/Assistant HOD managing the worker's department).

    Unlike the deactivate endpoint this removes the record outright, along with the worker's
    login, roles, memberships, availability and past assignments. The worker must already be
    deactivated, have no upcoming assignments, and not head a department.

    Args:
        worker_id: Unique identifier of the worker to delete.
        current_user: Admin or HOD user token required.
        service: Worker service dependency.
    """
    service.authorize_manage_worker(current_user, worker_id, protect_heads=True)
    service.delete_worker(worker_id)


@router.get("/{worker_id}/departments", response_model=list[DepartmentResponse])
def get_worker_departments(
    worker_id: UUID,
    current_user: TokenPayload = CurrentUser,
    service: WorkerService = Depends(get_worker_service),
) -> list[DepartmentResponse]:
    """Retrieve all departments a worker is assigned to (admin, managing HOD/Assistant HOD, or self).

    Args:
        worker_id: Unique identifier of the worker.
        current_user: Current authenticated user token.
        service: Worker service dependency.

    Returns:
        list[DepartmentResponse]: List of departments the worker belongs to.
    """
    service.authorize_view_worker(current_user, worker_id)
    return service.get_worker_departments(worker_id)


@router.get("/{worker_id}/assistant-hod-departments", response_model=list[DepartmentResponse])
def get_worker_assistant_hod_departments(
    worker_id: UUID,
    current_user: TokenPayload = CurrentUser,
    service: WorkerService = Depends(get_worker_service),
) -> list[DepartmentResponse]:
    """Retrieve the departments a worker manages as assistant HOD (admin, managing HOD, or self).

    Used to pre-populate the assistant-HOD department picker when editing a worker's roles.

    Args:
        worker_id: Unique identifier of the worker.
        current_user: Current authenticated user token.
        service: Worker service dependency.

    Returns:
        list[DepartmentResponse]: Departments the worker is an assistant HOD of.
    """
    service.authorize_view_worker(current_user, worker_id)
    return service.get_worker_assistant_hod_departments(worker_id)
