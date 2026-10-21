import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

# The API returns JSON for a browser client on another origin. Nothing here is meant to be
# framed, sniffed into another type, or kept in a shared cache — most responses carry people's
# phone numbers and emails.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every incoming request and outgoing response with:
    - request_id (injected into structlog context for the duration of the request)
    - method, path, status code, duration
    Skips /health endpoints to avoid log noise.

    Also stamps the API's security headers on every response it logs, beside X-Request-ID, so
    there is one place that decorates outgoing responses rather than two middlewares in a row.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path.startswith("/health"):
            return await call_next(request)

        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Bind request_id to structlog context so all logs within
        # this request automatically include it
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger.info("request_started")

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(
                "request_failed",
                error=str(e),
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        response.headers.update(_SECURITY_HEADERS)
        return response
