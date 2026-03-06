from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import (
    CurrentUser,
    DepartmentHeadUser,
    get_reminder_service,
    get_schedule_service,
)
from app.schemas.models import AssignmentStatus, MessageResponse, TokenPayload
from app.schemas.schedules.models import (
    AssignmentResponse,
    ScheduleGenerateRequest,
    ScheduleResponse,
)
from app.service.reminders.service import ReminderService
from app.service.schedules.service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("/departments/{department_id}", response_model=list[ScheduleResponse])
def list_schedules_by_department(
    department_id: UUID,
    _: TokenPayload = CurrentUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> list[ScheduleResponse]:
    return service.get_schedules_by_department(department_id)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: UUID,
    _: TokenPayload = CurrentUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    try:
        return service.get_schedule(schedule_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/generate",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_schedule(
    data: ScheduleGenerateRequest,
    token: TokenPayload = DepartmentHeadUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    """
    Generates a schedule for a single event using round-robin assignment.
    Requires HOD or admin role.
    """
    try:
        schedule = service.generate_schedule(data, created_by=UUID(token.sub))
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to generate schedule"
            )
        return schedule
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: UUID,
    _: TokenPayload = DepartmentHeadUser,
    service: ScheduleService = Depends(get_schedule_service),
) -> None:
    try:
        service.delete_schedule(schedule_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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
    try:
        return service.update_assignment_status(assignment_id, status_update)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/reminders/trigger", response_model=MessageResponse)
def trigger_reminders(
    _: TokenPayload = DepartmentHeadUser,
    reminder_service: ReminderService = Depends(get_reminder_service),
) -> MessageResponse:
    """Manually trigger the reminder job — useful for testing."""
    sent = reminder_service.trigger_manually()
    return MessageResponse(message=f"Sent {sent} reminder(s)")
