from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

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
    try:
        return service.set_availability(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{availability_id}", response_model=AvailabilityResponse)
def update_availability(
    availability_id: UUID,
    data: AvailabilityUpdate,
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> AvailabilityResponse:
    try:
        return service.update_availability(availability_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_availability(
    availability_id: UUID,
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> None:
    try:
        service.delete_availability(availability_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/workers/{worker_id}/bulk", response_model=list[AvailabilityResponse])
def bulk_set_availability(
    worker_id: UUID,
    records: list[AvailabilityCreate],
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> list[AvailabilityResponse]:
    try:
        return service.bulk_set_availability(worker_id, records)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/workers/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear_worker_availability(
    worker_id: UUID,
    _: TokenPayload = CurrentUser,
    service: AvailabilityService = Depends(get_availability_service),
) -> None:
    try:
        service.clear_worker_availability(worker_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
