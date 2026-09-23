from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    get_special_service_service,
)
from app.core.exceptions import BadRequestError
from app.schemas.models import TokenPayload
from app.schemas.special_services.models import (
    SpecialDate,
    SpecialService,
    SpecialServiceCreate,
    SpecialServiceUpdate,
)
from app.service.special_services.service import SpecialServiceService

router = APIRouter(prefix="/special-services", tags=["special-services"])

# A year at a time is already far more than any screen asks for; the cap stops a typo turning
# a pure-arithmetic endpoint into a long walk over centuries of months.
MAX_WINDOW_DAYS = 366


# NOTE: declared before "/{special_service_id}" so "dates" is not parsed as a UUID.
@router.get("/dates", response_model=list[SpecialDate])
def list_special_dates(
    from_date: date = Query(..., alias="from", description="Inclusive start of the window"),
    to_date: date = Query(..., alias="to", description="Inclusive end of the window"),
    _: TokenPayload = CurrentUser,
    service: SpecialServiceService = Depends(get_special_service_service),
) -> list[SpecialDate]:
    """Resolve the configured rules and one-off dates into real dates in a window.

    Readable by anyone signed in: the month preview badges these, and that is where a head
    decides which dates to keep.
    """
    if to_date < from_date:
        raise BadRequestError("'to' must not be before 'from'")
    if (to_date - from_date).days > MAX_WINDOW_DAYS:
        raise BadRequestError(f"Ask for at most {MAX_WINDOW_DAYS} days at a time")
    return service.list_special_dates(from_date, to_date)


@router.get("", response_model=list[SpecialService])
def list_special_services(
    active_only: bool = Query(False, description="Exclude deactivated entries"),
    _: TokenPayload = CurrentUser,
    service: SpecialServiceService = Depends(get_special_service_service),
) -> list[SpecialService]:
    """Every configured rule and named date."""
    return service.list_special_services(active_only=active_only)


@router.post("", response_model=SpecialService, status_code=status.HTTP_201_CREATED)
def create_special_service(
    data: SpecialServiceCreate,
    token: TokenPayload = AdminUser,
    service: SpecialServiceService = Depends(get_special_service_service),
) -> SpecialService:
    """Add a recurring rule or a named one-off date (admin only).

    Admin rather than head of department because the planner's tally of special turns is
    church-wide: a head editing "first Sunday" would rewrite every other department's rotation.
    """
    if token.email is None:
        raise BadRequestError("User email is required to create a special service")
    return service.create_special_service(data, created_by=token.email)


@router.patch("/{special_service_id}", response_model=SpecialService)
def update_special_service(
    special_service_id: UUID,
    data: SpecialServiceUpdate,
    _: TokenPayload = AdminUser,
    service: SpecialServiceService = Depends(get_special_service_service),
) -> SpecialService:
    """Rename a special service or turn it on and off (admin only).

    A rule's day and week cannot be moved — see `SpecialServiceService.update_special_service`.
    """
    return service.update_special_service(special_service_id, data)


@router.delete("/{special_service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_special_service(
    special_service_id: UUID,
    _: TokenPayload = AdminUser,
    service: SpecialServiceService = Depends(get_special_service_service),
) -> None:
    """Remove a special service (admin only). Rotas keep their snapshot of the name."""
    service.delete_special_service(special_service_id)
