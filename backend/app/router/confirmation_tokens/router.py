from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_confirmation_token_service
from app.schemas.confirmation_tokens.models import ConfirmationDetailsResponse
from app.schemas.schedules.models import AssignmentResponse
from app.service.confirmation_tokens.service import ConfirmationTokenService

router = APIRouter(prefix="/confirm", tags=["confirmation"])


@router.get(
    "/{token}",
    response_model=ConfirmationDetailsResponse,
    summary="Get assignment details for a confirmation token",
    description=(
        "Public endpoint — no authentication required. "
        "Returns the schedule and worker details associated with the token "
        "so the confirmation page can render before the worker takes action."
    ),
)
def get_confirmation_details(
    token: UUID,
    service: ConfirmationTokenService = Depends(get_confirmation_token_service),
) -> ConfirmationDetailsResponse:
    try:
        return service.get_confirmation_details(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{token}",
    response_model=AssignmentResponse,
    summary="Confirm or decline an assignment via token",
    description=(
        "Public endpoint — no authentication required. "
        "Validates the token (not expired, not already used) and updates "
        "the assignment status to 'confirmed' or 'declined'."
    ),
)
def submit_confirmation(
    token: UUID,
    action: str,
    service: ConfirmationTokenService = Depends(get_confirmation_token_service),
) -> AssignmentResponse:
    try:
        return service.confirm(token, action)
    except ValueError as e:
        error = str(e)
        if "already been used" in error or "expired" in error or "not found" in error.lower():
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=error,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
