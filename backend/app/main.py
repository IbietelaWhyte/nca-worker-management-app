from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from supabase import Client

from app.core.authentication import get_jwks
from app.core.concurrency import configure_thread_pool
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.core.supabase import get_supabase
from app.repository.schedules.repository import ScheduleRepository
from app.router import (
    account,
    authentication,
    availabilities,
    confirmation_tokens,
    department_roles,
    departments,
    schedules,
    subteams,
    workers,
)
from app.service.reminders.service import ReminderService
from app.service.sms.service import SMSService

setup_logging()
logger = get_logger(__name__)


def create_reminder_service() -> ReminderService:
    """Create and initialize the reminder service with required dependencies.

    This function instantiates a ReminderService with all necessary repository
    and service dependencies for sending automated schedule reminders to workers.

    Returns:
        ReminderService: Configured reminder service instance ready to send notifications.
    """
    from app.repository.confirmation_tokens.repository import ConfirmationTokenRepository
    from app.repository.workers.repository import WorkerRepository
    from app.service.confirmation_tokens.service import ConfirmationTokenService

    client = get_supabase()
    token_repo = ConfirmationTokenRepository(client)
    token_service = ConfirmationTokenService(
        token_repo=token_repo,
        schedule_repo=ScheduleRepository(client),
        worker_repo=WorkerRepository(client),
    )
    return ReminderService(
        schedule_repo=ScheduleRepository(client),
        sms_service=SMSService(),
        worker_repo=WorkerRepository(client),
        token_service=token_service,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage the application lifecycle for FastAPI startup and shutdown.

    This async context manager handles initialization tasks when the app starts
    (like starting the reminder service and caching JWKS) and cleanup tasks
    when the app shuts down (like stopping the reminder service).

    Args:
        app: The FastAPI application instance.

    Yields:
        None: Control is yielded back to the application to handle requests.
    """
    logger.info("app_starting", env=settings.app_env)
    configure_thread_pool()
    reminder_service = create_reminder_service()
    reminder_service.start()
    await get_jwks()
    yield
    logger.info("app_shutting_down")
    reminder_service.stop()


app = FastAPI(
    title="Church Worker Scheduler API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workers.router, prefix="/api/v1")
app.include_router(departments.router, prefix="/api/v1")
app.include_router(schedules.router, prefix="/api/v1")
app.include_router(availabilities.router, prefix="/api/v1")
app.include_router(subteams.router, prefix="/api/v1")
app.include_router(department_roles.router, prefix="/api/v1")
app.include_router(account.router, prefix="/api/v1")
app.include_router(authentication.router, prefix="/api/v1")
app.include_router(confirmation_tokens.router, prefix="/api/v1")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Map a domain AppError to its associated HTTP status code and a JSON detail body.

    Args:
        request: The incoming request (unused, required by the handler signature).
        exc: The raised domain error carrying its status_code and detail.

    Returns:
        JSONResponse: A response with the error's status code and ``{"detail": ...}`` body.
    """
    logger.info("app_error", status_code=exc.status_code, detail=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler so unexpected errors return a generic 500 without leaking internals.

    Args:
        request: The incoming request (unused, required by the handler signature).
        exc: The unhandled exception.

    Returns:
        JSONResponse: A generic 500 response. The exception detail is logged, not returned.
    """
    logger.error("unhandled_exception", error=str(exc), error_type=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Basic health check endpoint to verify the API is running.

    Returns:
        dict[str, str]: A dictionary with status 'ok' if the service is healthy.
    """
    return {"status": "ok"}


@app.get("/health/db", tags=["health"])
async def db_health_check(response: Response, client: Client = Depends(get_supabase)) -> dict[str, str]:
    """Database health check endpoint to verify database connectivity.

    Performs a simple query to the workers table to ensure the database
    connection is working properly.

    Args:
        response: The outgoing response, used to set a 503 status when the DB is unreachable.
        client: Supabase client injected via dependency injection.

    Returns:
        dict[str, str]: Status dictionary with 'ok'/'connected' if healthy, or 'error'/'unavailable'
                       with a 503 status if the database is unreachable. The underlying error is
                       logged, never returned to the caller.
    """
    try:
        client.table("workers").select("id").limit(1).execute()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error("db_health_check_failed", error=str(e))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": "unavailable"}
