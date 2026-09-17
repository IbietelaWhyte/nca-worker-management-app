from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    HODUser,
    get_worker_leave_service,
    get_worker_service,
)
from app.schemas.models import TokenPayload, UserRole
from app.schemas.worker_leave.models import (
    CurrentLeave,
    LeaveClashReport,
    WorkerLeaveCreate,
    WorkerLeaveResponse,
)
from app.service.worker_leave.service import WorkerLeaveService
from app.service.workers.service import WorkerService

router = APIRouter(prefix="/leave", tags=["leave"])


# Leave is set by a head, not self-declared: it is an absence the department agrees to, and it
# is what suppresses the availability prompt. A worker marking individual dates off themselves
# is what /availability is for. Hence HODUser on every route, narrowed further to the worker's
# own departments by authorize_manage_worker.


@router.get("/current", response_model=list[CurrentLeave])
def get_current_leave(
    _: TokenPayload = HODUser,
    service: WorkerLeaveService = Depends(get_worker_leave_service),
) -> list[CurrentLeave]:
    """Who is away right now. Declared before /{leave_id} so "current" is never parsed as one."""
    return service.get_current_leave()


@router.get("/workers/{worker_id}", response_model=list[WorkerLeaveResponse])
def get_worker_leave(
    worker_id: UUID,
    token: TokenPayload = HODUser,
    service: WorkerLeaveService = Depends(get_worker_leave_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> list[WorkerLeaveResponse]:
    worker_service.authorize_manage_worker(token, worker_id)
    return service.get_leave_for_worker(worker_id)


@router.get("/workers/{worker_id}/clashes", response_model=LeaveClashReport)
def get_leave_clashes(
    worker_id: UUID,
    start_date: date,
    end_date: date,
    token: TokenPayload = HODUser,
    service: WorkerLeaveService = Depends(get_worker_leave_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> LeaveClashReport:
    """Duties already on the rota inside a proposed leave period.

    Read-only and advisory: the dialog calls it before confirming so the head sees what they
    will need to reassign. Setting leave never edits the rota.
    """
    worker_service.authorize_manage_worker(token, worker_id)
    return service.get_clashes(worker_id, start_date, end_date)


@router.post("/workers/{worker_id}", response_model=WorkerLeaveResponse, status_code=status.HTTP_201_CREATED)
def create_worker_leave(
    worker_id: UUID,
    data: WorkerLeaveCreate,
    token: TokenPayload = HODUser,
    service: WorkerLeaveService = Depends(get_worker_leave_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> WorkerLeaveResponse:
    worker_service.authorize_manage_worker(token, worker_id)
    # Same idiom as the availability prompt router: an admin need not have a worker profile at
    # all, so resolving one is skipped for them rather than allowed to fail.
    actor = None if token.role == UserRole.ADMIN else worker_service.get_worker_for_token(token)
    return service.create_leave(worker_id, data, actor.id if actor else None)


@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_worker_leave(
    leave_id: UUID,
    token: TokenPayload = HODUser,
    service: WorkerLeaveService = Depends(get_worker_leave_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> None:
    # The URL names a leave, not a worker, so the owner has to be resolved before checking.
    worker_service.authorize_manage_worker(token, service.get_owner_id(leave_id))
    service.delete_leave(leave_id)
