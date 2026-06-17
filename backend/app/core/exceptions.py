"""Domain exception types and their HTTP semantics.

Services raise these instead of bare ``ValueError`` so that the FastAPI exception handlers registered
in ``app.main`` can map each to a consistent status code and response body, without routers having to
guess a status from the exception message.
"""


class AppError(Exception):
    """Base class for application errors with an associated HTTP status code.

    Attributes:
        status_code: The HTTP status code this error maps to. Defaults to 500.
        default_detail: Fallback message used when no explicit detail is provided.
    """

    status_code: int = 500
    default_detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        """Initialize the error with an optional human-readable detail message.

        Args:
            detail: Message describing the error. Falls back to ``default_detail`` when omitted.
        """
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    """A requested resource does not exist (HTTP 404)."""

    status_code = 404
    default_detail = "Resource not found"


class ConflictError(AppError):
    """The request conflicts with existing state, e.g. a uniqueness violation (HTTP 409)."""

    status_code = 409
    default_detail = "Resource already exists"


class BadRequestError(AppError):
    """The request is invalid, e.g. missing required input or an invalid value (HTTP 400)."""

    status_code = 400
    default_detail = "Invalid request"


class PermissionDeniedError(AppError):
    """The authenticated user is not allowed to perform this action (HTTP 403)."""

    status_code = 403
    default_detail = "Permission denied"


class GoneError(AppError):
    """The target resource is no longer available, e.g. a used or expired link (HTTP 410)."""

    status_code = 410
    default_detail = "No longer available"
