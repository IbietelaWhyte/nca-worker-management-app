from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import get_confirmation_token_service
from app.schemas.confirmation_tokens.models import ConfirmationDetailsResponse
from app.schemas.schedules.models import AssignmentResponse
from app.service.confirmation_tokens.service import ConfirmationTokenService

router = APIRouter(prefix="/confirm", tags=["confirmation"])


@router.get(
    "/{token}",
    response_model=ConfirmationDetailsResponse,
    summary="List the worker's upcoming duties for a confirmation token",
    description=(
        "Public endpoint — no authentication required. "
        "Returns the worker's name and every upcoming duty they hold, so one SMS can cover a "
        "whole month of dates and each can be answered separately."
    ),
)
def get_confirmation_details(
    token: UUID,
    service: ConfirmationTokenService = Depends(get_confirmation_token_service),
) -> ConfirmationDetailsResponse:
    return service.get_confirmation_details(token)


@router.post(
    "/{token}",
    response_model=AssignmentResponse,
    summary="Confirm or decline one assignment via token",
    description=(
        "Public endpoint — no authentication required. "
        "Validates the token and sets one of the worker's assignments to 'confirmed' or "
        "'declined'. The link stays usable afterwards so the worker can answer their other "
        "dates, or change an answer."
    ),
)
def submit_confirmation(
    token: UUID,
    assignment_id: UUID,
    action: str,
    service: ConfirmationTokenService = Depends(get_confirmation_token_service),
) -> AssignmentResponse:
    return service.confirm(token, assignment_id, action)
