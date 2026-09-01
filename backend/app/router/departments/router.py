from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    HODUser,
    get_availability_prompt_service,
    get_department_role_service,
    get_department_service,
    get_subteam_service,
    get_worker_service,
)
from app.schemas.availability_prompts.models import (
    AvailabilityPromptCreate,
    AvailabilityPromptResponse,
    PromptSendResult,
)
from app.schemas.department_roles.models import DepartmentRoleResponse
from app.schemas.departments.models import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    DepartmentWithWorkersResponse,
)
from app.schemas.models import MessageResponse, TokenPayload, UserRole
from app.schemas.subteams.models import SubteamResponse
from app.schemas.workers.models import WorkerImportResult
from app.service.availability_prompts.service import AvailabilityPromptService
from app.service.department_roles.service import DepartmentRoleService
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
    if current_user.role == UserRole.HOD or current_user.role == UserRole.ASSISTANT_HOD:
        worker = worker_service.get_worker_for_token(current_user)
        if current_user.role == UserRole.HOD:
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


# NOTE: declared before "/{department_id}/workers/{worker_id}" so "import" is not parsed as a worker_id.
@router.post("/{department_id}/workers/import", response_model=WorkerImportResult)
async def import_workers(
    department_id: UUID,
    file: UploadFile = File(..., description="CSV file with columns: first_name, last_name, email, phone"),
    dry_run: bool = Query(default=False, description="Validate and preview the import without writing any rows"),
    skip_duplicates: bool = Query(
        default=False,
        description="Import the remaining rows even though some workers already exist, instead of rejecting the file",
    ),
    current_user: TokenPayload = HODUser,
    worker_service: WorkerService = Depends(get_worker_service),
) -> WorkerImportResult:
    """Bulk-import workers from a CSV file and assign them to a department (admin/HOD).

    The import is all-or-nothing: any row that fails validation rejects the whole file. Rows for
    workers who already exist also block it unless ``skip_duplicates`` is set, which callers should
    only do once the user has seen the dry-run preview and chosen to proceed.

    Args:
        department_id: Department to assign the imported workers to.
        file: Uploaded CSV file with a header row and the required columns.
        dry_run: If True, validate and return a per-row preview without creating anything.
        skip_duplicates: If True, already-existing workers are passed over rather than blocking.
        current_user: Admin or HOD/Assistant HOD token; non-admins must manage the department.
        worker_service: Worker service dependency.

    Returns:
        WorkerImportResult: Per-row outcomes and aggregate counts.
    """
    worker_service.authorize_create_assignment(current_user, department_id)
    file_bytes = await file.read()
    return worker_service.import_workers(file_bytes, department_id, dry_run=dry_run, skip_duplicates=skip_duplicates)


@router.get("/{department_id}/availability-prompts", response_model=list[AvailabilityPromptResponse])
def list_availability_prompts(
    department_id: UUID,
    current_user: TokenPayload = HODUser,
    worker_service: WorkerService = Depends(get_worker_service),
    prompt_service: AvailabilityPromptService = Depends(get_availability_prompt_service),
) -> list[AvailabilityPromptResponse]:
    """List the availability prompts configured for a department (admin/HOD).

    Args:
        department_id: The department whose prompts to list.
        current_user: Admin or HOD/Assistant HOD token; non-admins must manage the department.
        worker_service: Worker service dependency, for the department scope check.
        prompt_service: Availability prompt service dependency.

    Returns:
        list[AvailabilityPromptResponse]: The department's prompts, newest first.
    """
    worker_service.authorize_create_assignment(current_user, department_id)
    return prompt_service.get_prompts(department_id)


@router.post(
    "/{department_id}/availability-prompts",
    response_model=AvailabilityPromptResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_availability_prompt(
    department_id: UUID,
    data: AvailabilityPromptCreate,
    current_user: TokenPayload = HODUser,
    worker_service: WorkerService = Depends(get_worker_service),
    prompt_service: AvailabilityPromptService = Depends(get_availability_prompt_service),
) -> AvailabilityPromptResponse:
    """Schedule an availability prompt for a department, once or monthly (admin/HOD).

    Args:
        department_id: The department whose workers will be prompted.
        data: Mode plus the matching date fields.
        current_user: Admin or HOD/Assistant HOD token; non-admins must manage the department.
        worker_service: Worker service dependency, for the department scope check.
        prompt_service: Availability prompt service dependency.

    Returns:
        AvailabilityPromptResponse: The stored prompt.
    """
    worker_service.authorize_create_assignment(current_user, department_id)
    actor = None if current_user.role == UserRole.ADMIN else worker_service.get_worker_for_token(current_user)
    return prompt_service.create_prompt(department_id, data, created_by=actor.id if actor else None)


@router.post("/{department_id}/availability-prompts/send", response_model=PromptSendResult)
def send_availability_prompt_now(
    department_id: UUID,
    current_user: TokenPayload = HODUser,
    worker_service: WorkerService = Depends(get_worker_service),
    prompt_service: AvailabilityPromptService = Depends(get_availability_prompt_service),
) -> PromptSendResult:
    """Text a department's active workers now, asking them to enter their availability (admin/HOD).

    Args:
        department_id: The department to prompt.
        current_user: Admin or HOD/Assistant HOD token; non-admins must manage the department.
        worker_service: Worker service dependency, for the department scope check.
        prompt_service: Availability prompt service dependency.

    Returns:
        PromptSendResult: How many were texted, skipped for want of a phone number, or failed.
    """
    worker_service.authorize_create_assignment(current_user, department_id)
    return prompt_service.send_now(department_id)


@router.delete(
    "/{department_id}/availability-prompts/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_availability_prompt(
    department_id: UUID,
    prompt_id: UUID,
    current_user: TokenPayload = HODUser,
    worker_service: WorkerService = Depends(get_worker_service),
    prompt_service: AvailabilityPromptService = Depends(get_availability_prompt_service),
) -> None:
    """Remove a scheduled availability prompt (admin/HOD).

    Args:
        department_id: The department the prompt belongs to.
        prompt_id: The prompt to delete.
        current_user: Admin or HOD/Assistant HOD token; non-admins must manage the department.
        worker_service: Worker service dependency, for the department scope check.
        prompt_service: Availability prompt service dependency.
    """
    worker_service.authorize_create_assignment(current_user, department_id)
    prompt_service.delete_prompt(prompt_id)


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


@router.get("/{department_id}/roles", response_model=list[DepartmentRoleResponse])
def list_roles(
    department_id: UUID,
    _: TokenPayload = CurrentUser,
    service: DepartmentRoleService = Depends(get_department_role_service),
) -> list[DepartmentRoleResponse]:
    return service.get_roles_by_department(department_id)
