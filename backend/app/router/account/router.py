from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, get_account_service
from app.schemas.account.models import AccountProfileUpdate, ChangePasswordRequest
from app.schemas.models import MessageResponse, TokenPayload
from app.schemas.workers.models import WorkerResponse
from app.service.account.service import AccountService

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/me", response_model=WorkerResponse)
def get_my_profile(
    current_user: TokenPayload = CurrentUser,
    service: AccountService = Depends(get_account_service),
) -> WorkerResponse:
    """Return the authenticated user's own profile."""
    return service.get_profile(current_user)


@router.patch("/me", response_model=WorkerResponse)
def update_my_profile(
    data: AccountProfileUpdate,
    current_user: TokenPayload = CurrentUser,
    service: AccountService = Depends(get_account_service),
) -> WorkerResponse:
    """Update the authenticated user's own profile (name, phone)."""
    return service.update_profile(current_user, data)


@router.post("/change-password", response_model=MessageResponse)
def change_my_password(
    data: ChangePasswordRequest,
    current_user: TokenPayload = CurrentUser,
    service: AccountService = Depends(get_account_service),
) -> MessageResponse:
    """Change the authenticated user's password after verifying the current one."""
    service.change_password(current_user, data.current_password, data.new_password)
    return MessageResponse(message="Password changed successfully")


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    current_user: TokenPayload = CurrentUser,
    service: AccountService = Depends(get_account_service),
) -> None:
    """Soft-delete the authenticated user's account and revoke their login."""
    service.delete_account(current_user)
