from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import (
    HODUser,
    get_attendance_service,
    get_worker_service,
)
from app.schemas.attendance.models import AbsenceReport, AttendanceUpdate
from app.schemas.models import TokenPayload
from app.schemas.schedules.models import AttendanceResult
from app.service.attendance.service import AttendanceService
from app.service.workers.service import WorkerService

router = APIRouter(prefix="/attendance", tags=["attendance"])


# Attendance is recorded by whoever ran the service, never by the worker it is about. That is the
# whole point of the feature: the register that was removed in 20260918090000 was a worker's claim
# about the future that nothing acted on, and this is an operator's observation of the past that a
# head acts on. So HODUser on every route, narrowed to the operator's own departments by
# authorize_record_attendance — a head of Ushering must not close the Choir's attendance.
#
# ROUTE ORDER: everything here leads with a literal segment ("assignments", "schedules",
# "departments"), and this router has no bare /{uuid} route, so nothing can be swallowed the way
# "assignments" would be by GET /schedules/{schedule_id}. Keep it that way: a /{id} route added
# later must be declared last.


@router.post("/assignments/{assignment_id}/check-in", response_model=AttendanceResult)
def check_in(
    assignment_id: UUID,
    token: TokenPayload = HODUser,
    service: AttendanceService = Depends(get_attendance_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> AttendanceResult:
    """Mark a scheduled worker present, judging lateness against the service's start time."""
    worker_service.authorize_record_attendance(token, service.department_for_assignment(assignment_id))
    return service.check_in(assignment_id, token.email)


@router.delete("/assignments/{assignment_id}/check-in", response_model=AttendanceResult)
def undo_check_in(
    assignment_id: UUID,
    token: TokenPayload = HODUser,
    service: AttendanceService = Depends(get_attendance_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> AttendanceResult:
    """Take a check-in back: to absent if attendance is closed, to nothing if it is open."""
    worker_service.authorize_record_attendance(token, service.department_for_assignment(assignment_id))
    return service.undo_check_in(assignment_id)


@router.patch("/assignments/{assignment_id}/excused", response_model=AttendanceResult)
def set_excused(
    assignment_id: UUID,
    data: AttendanceUpdate,
    token: TokenPayload = HODUser,
    service: AttendanceService = Depends(get_attendance_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> AttendanceResult:
    """Mark an absence as not counting against the worker, or put it back."""
    worker_service.authorize_record_attendance(token, service.department_for_assignment(assignment_id))
    return service.set_excused(assignment_id, data.excused)


@router.post("/schedules/{schedule_id}/close", response_model=AttendanceResult)
def close_attendance(
    schedule_id: UUID,
    token: TokenPayload = HODUser,
    service: AttendanceService = Depends(get_attendance_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> AttendanceResult:
    """Finish the register. Everyone untapped is recorded absent, or excused if they are on leave."""
    worker_service.authorize_record_attendance(token, service.department_for_schedule(schedule_id))
    return service.close_attendance(schedule_id, token.email)


@router.post("/schedules/{schedule_id}/reopen", response_model=AttendanceResult)
def reopen_attendance(
    schedule_id: UUID,
    token: TokenPayload = HODUser,
    service: AttendanceService = Depends(get_attendance_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> AttendanceResult:
    """Reopen the register, erasing the absences closing it stamped. Check-ins survive."""
    worker_service.authorize_record_attendance(token, service.department_for_schedule(schedule_id))
    return service.reopen_attendance(schedule_id)


@router.get("/departments/{department_id}/report", response_model=AbsenceReport)
def get_report(
    department_id: UUID,
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    token: TokenPayload = HODUser,
    service: AttendanceService = Depends(get_attendance_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> AbsenceReport:
    """A department's attendance over a window, worst first, with how much of it was recorded."""
    worker_service.authorize_record_attendance(token, department_id)
    return service.get_report(department_id, from_date, to_date)
