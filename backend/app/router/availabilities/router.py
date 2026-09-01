from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    CurrentUser,
    get_availability_service,
    get_confirmation_token_service,
    get_worker_service,
)
from app.schemas.availabilities.models import (
    AvailabilityCreate,
    AvailabilityResponse,
    AvailabilityUpdate,
    PublicAvailabilityResponse,
    PublicAvailabilityUpdate,
)
from app.schemas.models import DayOfWeek, TokenPayload
from app.service.availabilities.service import AvailabilityService
from app.service.confirmation_tokens.service import ConfirmationTokenService
from app.service.workers.service import WorkerService

router = APIRouter(prefix="/availability", tags=["availability"])


# ----------------------------------------------------------------------
# Public, token-authenticated endpoints
#
# Declared before the authenticated routes so "link" is never parsed as a worker id or an
# availability id. Most workers have no login account — accounts are granted one at a time by an
# admin — so an SMS asking them to set their availability has to reach them without one. The
# token is the credential, exactly as it is for /confirm.
# ----------------------------------------------------------------------


@router.get("/link/{token}", response_model=PublicAvailabilityResponse)
def get_availability_by_link(
    token: UUID,
    service: AvailabilityService = Depends(get_availability_service),
    token_service: ConfirmationTokenService = Depends(get_confirmation_token_service),
) -> PublicAvailabilityResponse:
    """Public endpoint — no authentication required. Lists the dates a worker has already set."""
    worker_id = token_service.resolve_worker_id(token)
    return service.get_public_availability(worker_id)


@router.put("/link/{token}", response_model=AvailabilityResponse)
def set_availability_by_link(
    token: UUID,
    data: PublicAvailabilityUpdate,
    service: AvailabilityService = Depends(get_availability_service),
    token_service: ConfirmationTokenService = Depends(get_confirmation_token_service),
) -> AvailabilityResponse:
    """Public endpoint — no authentication required. Marks one date available or unavailable."""
    worker_id = token_service.resolve_worker_id(token)
    return service.set_specific_date(worker_id, data.specific_date, data.is_available)


@router.delete("/link/{token}", status_code=status.HTTP_204_NO_CONTENT)
def clear_availability_by_link(
    token: UUID,
    specific_date: date,
    service: AvailabilityService = Depends(get_availability_service),
    token_service: ConfirmationTokenService = Depends(get_confirmation_token_service),
) -> None:
    """Public endpoint — no authentication required. Removes a worker's override for one date."""
    worker_id = token_service.resolve_worker_id(token)
    service.clear_specific_date(worker_id, specific_date)


# ----------------------------------------------------------------------
# Authenticated endpoints
# ----------------------------------------------------------------------


@router.get("/workers/{worker_id}", response_model=list[AvailabilityResponse])
def get_worker_availability(
    worker_id: UUID,
    token: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> list[AvailabilityResponse]:
    worker_service.authorize_manage_availability(token, worker_id)
    return service.get_worker_availability(worker_id)


@router.get("/workers/{worker_id}/day/{day_of_week}", response_model=AvailabilityResponse | None)
def get_availability_by_day(
    worker_id: UUID,
    day_of_week: DayOfWeek,
    token: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> AvailabilityResponse | None:
    worker_service.authorize_manage_availability(token, worker_id)
    return service.get_availability_by_day(worker_id, day_of_week)


@router.get("/day/{day_of_week}", response_model=list[AvailabilityResponse])
def get_available_workers_on_day(
    day_of_week: DayOfWeek,
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> list[AvailabilityResponse]:
    return service.get_available_workers_on_day(day_of_week)


@router.post("", response_model=AvailabilityResponse, status_code=status.HTTP_201_CREATED)
def set_availability(
    data: AvailabilityCreate,
    token: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> AvailabilityResponse:
    """
    Creates or updates a worker's availability.
    Workers can only set their own availability unless they are an admin or HOD.
    """
    worker_service.authorize_manage_availability(token, data.worker_id)
    return service.set_availability(data)


@router.patch("/{availability_id}", response_model=AvailabilityResponse)
def update_availability(
    availability_id: UUID,
    data: AvailabilityUpdate,
    token: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> AvailabilityResponse:
    # The URL names a record, not a worker, so the owner has to be resolved before checking.
    worker_service.authorize_manage_availability(token, service.get_owner_id(availability_id))
    return service.update_availability(availability_id, data)


@router.delete("/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_availability(
    availability_id: UUID,
    token: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> None:
    worker_service.authorize_manage_availability(token, service.get_owner_id(availability_id))
    service.delete_availability(availability_id)


@router.post("/workers/{worker_id}/bulk", response_model=list[AvailabilityResponse])
def bulk_set_availability(
    worker_id: UUID,
    records: list[AvailabilityCreate],
    token: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> list[AvailabilityResponse]:
    worker_service.authorize_manage_availability(token, worker_id)
    return service.bulk_set_availability(worker_id, records)


@router.delete("/workers/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear_worker_availability(
    worker_id: UUID,
    token: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
    worker_service: WorkerService = Depends(get_worker_service),
) -> None:
    worker_service.authorize_manage_availability(token, worker_id)
    service.clear_worker_availability(worker_id)
