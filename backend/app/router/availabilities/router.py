from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, get_availability_service
from app.schemas.availabilities.models import (
    AvailabilityCreate,
    AvailabilityResponse,
    AvailabilityUpdate,
)
from app.schemas.models import DayOfWeek, TokenPayload
from app.service.availabilities.service import AvailabilityService

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("/workers/{worker_id}", response_model=list[AvailabilityResponse])
def get_worker_availability(
    worker_id: UUID,
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> list[AvailabilityResponse]:
    return service.get_worker_availability(worker_id)


@router.get("/workers/{worker_id}/day/{day_of_week}", response_model=AvailabilityResponse | None)
def get_availability_by_day(
    worker_id: UUID,
    day_of_week: DayOfWeek,
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityResponse | None:
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
) -> AvailabilityResponse:
    """
    Creates or updates a worker's availability.
    Workers can only set their own availability unless they are an admin or HOD.
    """
    return service.set_availability(data)


@router.patch("/{availability_id}", response_model=AvailabilityResponse)
def update_availability(
    availability_id: UUID,
    data: AvailabilityUpdate,
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityResponse:
    return service.update_availability(availability_id, data)


@router.delete("/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_availability(
    availability_id: UUID,
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> None:
    service.delete_availability(availability_id)


@router.post("/workers/{worker_id}/bulk", response_model=list[AvailabilityResponse])
def bulk_set_availability(
    worker_id: UUID,
    records: list[AvailabilityCreate],
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> list[AvailabilityResponse]:
    return service.bulk_set_availability(worker_id, records)


@router.delete("/workers/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear_worker_availability(
    worker_id: UUID,
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> None:
    service.clear_worker_availability(worker_id)
