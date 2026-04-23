from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.models import TokenPayload

bearer_scheme = HTTPBearer()
logger = get_logger(__name__)

# Cache it at module level
_jwks = None


async def get_jwks() -> Any:
    """Fetch and cache the JSON Web Key Set (JWKS) from Supabase.

    This function retrieves the public keys used to verify JWT tokens from
    Supabase's well-known JWKS endpoint. The keys are cached at module level
    to avoid repeated network requests.

    Returns:
        Any: The first JWK (JSON Web Key) from Supabase's JWKS endpoint.

    Raises:
        httpx.HTTPStatusError: If the request to fetch JWKS fails.
    """
    global _jwks
    if _jwks is None:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
            response.raise_for_status()
            _jwks = response.json()["keys"][0]  # grab the first key
    return _jwks


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
        jwk = await get_jwks()
        payload = jwt.decode(
            token,
            jwk,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )

        # Supabase stores custom roles in app_metadata
        app_metadata = payload.get("app_metadata", {})
        role = app_metadata.get("role", "worker")
        log.info("Token verified", role=role, sub=payload["sub"])

        return TokenPayload(
            sub=payload["sub"],
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
    if token.role != "admin":
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
    if token.role not in ("admin", "hod", "assistant_hod"):
        log = logger.bind(method="require_hod", sub=token.sub)
        log.warning("HOD access required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HOD access required",
        )
    return token
