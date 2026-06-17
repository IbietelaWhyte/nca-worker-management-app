from typing import Any, cast

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.models import TokenPayload, UserRole

bearer_scheme = HTTPBearer()
logger = get_logger(__name__)

# The full JWKS document ({"keys": [...]}) cached at module level.
_jwks_cache: dict[str, Any] | None = None


async def _fetch_jwks() -> dict[str, Any]:
    """Fetch the full JWKS document from Supabase's well-known endpoint.

    Returns:
        dict[str, Any]: The JWKS document, i.e. ``{"keys": [...]}``.

    Raises:
        httpx.HTTPStatusError: If the request to fetch JWKS fails.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


async def get_jwks(force_refresh: bool = False) -> dict[str, Any]:
    """Fetch and cache the full JSON Web Key Set (JWKS) from Supabase.

    The entire key set is cached (not just the first key) so verification works regardless of which
    key signed a token and survives Supabase publishing multiple keys.

    Args:
        force_refresh: If True, re-fetch from Supabase even when a cached copy exists (used to pick up
            rotated signing keys).

    Returns:
        dict[str, Any]: The cached JWKS document (``{"keys": [...]}``).

    Raises:
        httpx.HTTPStatusError: If the request to fetch JWKS fails.
    """
    global _jwks_cache
    if _jwks_cache is None or force_refresh:
        _jwks_cache = await _fetch_jwks()
    return _jwks_cache


def _kid_in_jwks(jwks: dict[str, Any], kid: str) -> bool:
    """Return True if the given key id is present in the JWKS document."""
    return any(key.get("kid") == kid for key in jwks.get("keys", []))


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenPayload:
    """
    Verifies a Supabase JWT and returns the token payload.
    Supabase signs JWTs with the JWT secret found in:
    Supabase dashboard → Project Settings → API → JWT Secret
    """
    log = logger.bind(method="verify_token")
    token = credentials.credentials
    try:
        # Select the signing key by the token's kid; refresh the JWKS once if it's unknown, so
        # rotated/newly-published keys are picked up without a restart.
        kid = jwt.get_unverified_header(token).get("kid")
        jwks = await get_jwks()
        if kid and not _kid_in_jwks(jwks, kid):
            jwks = await get_jwks(force_refresh=True)

        payload = jwt.decode(
            token,
            jwks,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )

        sub = payload.get("sub")
        if not sub:
            raise JWTError("token missing 'sub' claim")

        # Supabase stores custom roles in app_metadata
        app_metadata = payload.get("app_metadata", {})
        role = app_metadata.get("role", "worker")
        log.info("token_verified", role=role, sub=sub)

        return TokenPayload(
            sub=sub,
            email=payload.get("email"),
            role=role,
        )
    except JWTError as e:
        log.error("Invalid or expired token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: TokenPayload = Depends(verify_token)) -> TokenPayload:
    """FastAPI dependency that requires a valid authentication token.

    This is the base authentication dependency that simply verifies the token
    is valid and returns the token payload without any role-based restrictions.

    Args:
        token: The verified token payload from verify_token dependency.

    Returns:
        TokenPayload: The decoded and validated token payload containing user info.
    """
    return token


def require_admin(token: TokenPayload = Depends(verify_token)) -> TokenPayload:
    """FastAPI dependency that requires the user to have admin role.

    This dependency validates that the authenticated user has 'admin' role
    in their token. If not, a 403 Forbidden error is raised.

    Args:
        token: The verified token payload from verify_token dependency.

    Returns:
        TokenPayload: The token payload if user has admin role.

    Raises:
        HTTPException: 403 Forbidden if user lacks admin role.
    """
    if token.role != UserRole.ADMIN:
        log = logger.bind(method="require_admin", sub=token.sub)
        log.warning("Admin access required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return token


def require_hod(
    token: TokenPayload = Depends(verify_token),
) -> TokenPayload:
    """FastAPI dependency that requires admin or department head role.

    This dependency validates that the authenticated user has either 'admin',
    'hod', or 'assistant_hod' role. If not, a 403 Forbidden error is raised.

    Args:
        token: The verified token payload from verify_token dependency.

    Returns:
        TokenPayload: The token payload if user has required role.

    Raises:
        HTTPException: 403 Forbidden if user lacks required role.
    """
    if token.role not in (UserRole.ADMIN, UserRole.HOD, UserRole.ASSISTANT_HOD):
        log = logger.bind(method="require_hod", sub=token.sub)
        log.warning("HOD access required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HOD access required",
        )
    return token
