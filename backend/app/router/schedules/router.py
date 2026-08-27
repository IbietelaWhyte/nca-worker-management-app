from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    CurrentUser,
    HODUser,
    get_reminder_service,
    get_schedule_service,
)
from app.core.exceptions import AppError, BadRequestError
from app.schemas.models import AssignmentStatus, MessageResponse, TokenPayload
from app.schemas.schedules.models import (
    AssignmentResponse,
    MonthlyScheduleCommitRequest,
    MonthlySchedulePreview,
    MonthlySchedulePreviewRequest,
    MonthlyScheduleResult,
    ScheduleCreate,
    ScheduleResponse,
)
from app.service.reminders.service import ReminderService
from app.service.schedules.service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("/departments/{department_id}", response_model=list[ScheduleResponse])
def list_schedules_by_department(
    department_id: UUID,
    from_date: date | None = Query(None, alias="from", description="Inclusive lower bound on scheduled_date"),
    to_date: date | None = Query(None, alias="to", description="Inclusive upper bound on scheduled_date"),
    _: TokenPayload = CurrentUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> list[ScheduleResponse]:
    """List a department's schedules, optionally bounded to a date range (e.g. one month)."""
    return service.get_schedules_by_department(department_id, from_date, to_date)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: UUID,
    _: TokenPayload = CurrentUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    return service.get_schedule(schedule_id)


@router.post(
    "/generate",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_schedule(
    data: ScheduleCreate,
    token: TokenPayload = HODUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    """
    Generates a schedule for a single event using round-robin assignment.
    Requires HOD or admin role.
    """
    if token.email is None:
        raise BadRequestError("User email is required to create schedule")
    schedule = service.generate_schedule(data, created_by=token.email)
    if schedule is None:
        raise AppError("Failed to generate schedule")
    return schedule


@router.post("/generate-month/preview", response_model=MonthlySchedulePreview)
def preview_monthly_schedule(
    data: MonthlySchedulePreviewRequest,
    _: TokenPayload = HODUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> MonthlySchedulePreview:
    """
    Plan a whole month's rota without saving anything.

    Expands the chosen weekdays across the month and balances assignments over every
    date, so nobody serves twice before everyone has served once. Requires HOD or admin.
    """
    return service.preview_monthly_schedule(data)


@router.post(
    "/generate-month",
    response_model=MonthlyScheduleResult,
    status_code=status.HTTP_201_CREATED,
)
def generate_monthly_schedule(
    data: MonthlyScheduleCommitRequest,
    token: TokenPayload = HODUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> MonthlyScheduleResult:
    """
    Save the month reviewed via the preview endpoint.

    Takes the approved per-date worker selection verbatim, so manual swaps are kept.
    Dates that gained a schedule since the preview come back as skipped rather than
    failing the run. Requires HOD or admin role.
    """
    if token.email is None:
        raise BadRequestError("User email is required to create schedule")
    return service.commit_monthly_schedule(data, created_by=token.email)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: UUID,
    _: TokenPayload = HODUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> None:
    service.delete_schedule(schedule_id)


@router.get("/workers/{worker_id}/assignments", response_model=list[AssignmentResponse])
def get_worker_assignments(
    worker_id: UUID,
    _: TokenPayload = CurrentUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> list[AssignmentResponse]:
    return service.get_worker_assignments(worker_id)


@router.patch(
    "/assignments/{assignment_id}/status",
    response_model=AssignmentResponse,
)
def update_assignment_status(
    assignment_id: UUID,
    status_update: AssignmentStatus,
    token: TokenPayload = CurrentUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> AssignmentResponse:
    """Workers can confirm or decline their own assignments."""
    return service.update_assignment_status(assignment_id, status_update)


@router.patch(
    "/assignments/{assignment_id}/role",
    response_model=AssignmentResponse,
)
def update_assignment_role(
    assignment_id: UUID,
    department_role_id: UUID | None = None,
    _: TokenPayload = HODUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> AssignmentResponse:
    """Override the department role on an assignment (omit department_role_id to clear)."""
    return service.update_assignment_role(assignment_id, department_role_id)


@router.post("/reminders/trigger", response_model=MessageResponse)
def trigger_reminders(
    _: TokenPayload = HODUser,
    reminder_service: ReminderService = Depends(get_reminder_service),
) -> MessageResponse:
    """Manually trigger the reminder job — useful for testing."""
    sent = reminder_service.trigger_manually()
    return MessageResponse(message=f"Sent {sent} reminder(s)")


@router.post("/{schedule_id}/reminders/trigger", response_model=MessageResponse)
def send_reminders_for_schedule(
    schedule_id: UUID,
    _: TokenPayload = HODUser,
    reminder_service: ReminderService = Depends(get_reminder_service),
) -> MessageResponse:
    """Manually trigger reminders for a specific schedule."""
    sent = reminder_service.trigger_for_schedule(schedule_id)
    return MessageResponse(message=f"Sent {sent} reminder(s) for schedule {schedule_id}")
