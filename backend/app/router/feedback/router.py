from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, get_feedback_service
from app.schemas.feedback.models import FeedbackConfig, FeedbackCreate, FeedbackResponse
from app.schemas.models import TokenPayload
from app.service.feedback.service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/config", response_model=FeedbackConfig)
def get_feedback_config(
    _: TokenPayload = CurrentUser,
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackConfig:
    """Report whether reporting is wired up, so the help page can hide the form when it is not."""
    return FeedbackConfig(enabled=service.is_enabled)


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    data: FeedbackCreate,
    current_user: TokenPayload = CurrentUser,
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    """File the authenticated user's bug report or idea as an issue."""
    return service.submit(current_user, data)
