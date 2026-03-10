from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import (
    AdminUser,
    CurrentUser,
    HODUser,
    get_subteam_service,
)
from app.schemas.models import TokenPayload
from app.schemas.subteams.models import SubteamCreate, SubteamResponse, SubteamUpdate
from app.service.subteams.service import SubteamService

router = APIRouter(prefix="/subteams", tags=["subteams"])


@router.get("/{subteam_id}", response_model=SubteamResponse)
def get_subteam(
    subteam_id: UUID,
    _: TokenPayload = CurrentUser,
    service: SubteamService = Depends(get_subteam_service),
) -> SubteamResponse:
    try:
        return service.get_subteam(subteam_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=SubteamResponse, status_code=status.HTTP_201_CREATED)
def create_subteam(
    data: SubteamCreate,
    _: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
) -> SubteamResponse:
    try:
        return service.create_subteam(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/{subteam_id}", response_model=SubteamResponse)
def update_subteam(
    subteam_id: UUID,
    data: SubteamUpdate,
    _: TokenPayload = HODUser,
    service: SubteamService = Depends(get_subteam_service),
) -> SubteamResponse:
    try:
        return service.update_subteam(subteam_id, data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{subteam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subteam(
    subteam_id: UUID,
    _: TokenPayload = AdminUser,
    service: SubteamService = Depends(get_subteam_service),
) -> None:
    try:
        service.delete_subteam(subteam_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
