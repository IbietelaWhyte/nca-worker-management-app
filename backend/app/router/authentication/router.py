from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import AdminUser, get_authentication_service
from app.schemas.authentication.models import RegisterRequest, RegisterResponse
from app.schemas.models import TokenPayload
from app.service.authentication.service import AuthenticationService

router = APIRouter(prefix="/authentication", tags=["authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_worker(
    data: RegisterRequest,
    _: TokenPayload = AdminUser,
    service: AuthenticationService = Depends(get_authentication_service),
) -> RegisterResponse:
    """
    Creates a new worker account. Admin only.
    Creates both a Supabase auth user and a workers table row in one call.
    """
    try:
        return service.register_worker(data)
    except ValueError as e:
        error = str(e)
        if "already registered" in error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
