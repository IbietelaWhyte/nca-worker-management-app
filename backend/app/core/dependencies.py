from fastapi import Depends
from supabase import Client

from app.core.authentication import (
    get_current_user,
    require_admin,
    require_hod,
)
from app.core.supabase import get_supabase
from app.repository.availabilities.repository import AvailabilityRepository
from app.repository.departments.repository import DepartmentRepository
from app.repository.schedules.repository import ScheduleRepository
from app.repository.subteams.repository import SubteamRepository
from app.repository.workers.repository import WorkerRepository
from app.service.authentication.service import AuthenticationService
from app.service.availabilities.service import AvailabilityService
from app.service.departments.service import DepartmentService
from app.service.reminders.service import ReminderService
from app.service.schedules.service import ScheduleService
from app.service.sms.service import SMSService
from app.service.subteams.service import SubteamService
from app.service.workers.service import WorkerService

# --- Database client ---


def get_db(client: Client = Depends(get_supabase)) -> Client:
    """FastAPI dependency that provides a Supabase database client.

    Args:
        client: Supabase client from get_supabase dependency.

    Returns:
        Client: The Supabase client for database operations.
    """
    return client


# --- Repositories ---


def get_worker_repository(client: Client = Depends(get_db)) -> WorkerRepository:
    """FastAPI dependency that provides a WorkerRepository instance.

    Args:
        client: Supabase client from get_db dependency.

    Returns:
        WorkerRepository: Repository for worker database operations.
    """
    return WorkerRepository(client)


def get_department_repository(client: Client = Depends(get_db)) -> DepartmentRepository:
    """FastAPI dependency that provides a DepartmentRepository instance.

    Args:
        client: Supabase client from get_db dependency.

    Returns:
        DepartmentRepository: Repository for department database operations.
    """
    return DepartmentRepository(client)


def get_schedule_repository(client: Client = Depends(get_db)) -> ScheduleRepository:
    """FastAPI dependency that provides a ScheduleRepository instance.

    Args:
        client: Supabase client from get_db dependency.

    Returns:
        ScheduleRepository: Repository for schedule database operations.
    """
    return ScheduleRepository(client)


def get_availability_repository(client: Client = Depends(get_db)) -> AvailabilityRepository:
    """FastAPI dependency that provides an AvailabilityRepository instance.

    Args:
        client: Supabase client from get_db dependency.

    Returns:
        AvailabilityRepository: Repository for availability database operations.
    """
    return AvailabilityRepository(client)


def get_subteam_repository(client: Client = Depends(get_db)) -> SubteamRepository:
    """FastAPI dependency that provides a SubteamRepository instance.

    Args:
        client: Supabase client from get_db dependency.

    Returns:
        SubteamRepository: Repository for subteam database operations.
    """
    return SubteamRepository(client)


# --- Services ---


def get_schedule_service(
    schedule_repo: ScheduleRepository = Depends(get_schedule_repository),
    worker_repo: WorkerRepository = Depends(get_worker_repository),
    department_repo: DepartmentRepository = Depends(get_department_repository),
    subteam_repo: SubteamRepository = Depends(get_subteam_repository),
    availability_repo: AvailabilityRepository = Depends(get_availability_repository),
) -> ScheduleService:
    """FastAPI dependency that provides a ScheduleService instance.

    Args:
        schedule_repo: ScheduleRepository dependency.
        worker_repo: WorkerRepository dependency.
        department_repo: DepartmentRepository dependency.
        subteam_repo: SubteamRepository dependency.
        availability_repo: AvailabilityRepository dependency.

    Returns:
        ScheduleService: Service for schedule business logic operations.
    """
    return ScheduleService(
        schedule_repo=schedule_repo,
        worker_repo=worker_repo,
        department_repo=department_repo,
        subteam_repo=subteam_repo,
        availability_repo=availability_repo,
    )


def get_sms_service() -> SMSService:
    """FastAPI dependency that provides an SMSService instance.

    Returns:
        SMSService: Service for sending SMS notifications via Twilio.
    """
    return SMSService()


def get_reminder_service(
    schedule_repo: ScheduleRepository = Depends(get_schedule_repository),
    sms_service: SMSService = Depends(get_sms_service),
    worker_repo: WorkerRepository = Depends(get_worker_repository),
) -> ReminderService:
    """FastAPI dependency that provides a ReminderService instance.

    Args:
        schedule_repo: ScheduleRepository dependency.
        sms_service: SMSService dependency.
        worker_repo: WorkerRepository dependency.

    Returns:
        ReminderService: Service for sending scheduled reminders to workers.
    """
    return ReminderService(
        schedule_repo=schedule_repo,
        sms_service=sms_service,
        worker_repo=worker_repo,
    )


def get_worker_service(
    worker_repo: WorkerRepository = Depends(get_worker_repository),
    department_repo: DepartmentRepository = Depends(get_department_repository),
) -> WorkerService:
    """FastAPI dependency that provides a WorkerService instance.

    Args:
        worker_repo: WorkerRepository dependency.
        department_repo: DepartmentRepository dependency.

    Returns:
        WorkerService: Service for worker business logic operations.
    """
    return WorkerService(
        worker_repo=worker_repo,
        department_repo=department_repo,
    )


def get_department_service(
    department_repo: DepartmentRepository = Depends(get_department_repository),
) -> DepartmentService:
    """FastAPI dependency that provides a DepartmentService instance.

    Args:
        department_repo: DepartmentRepository dependency.

    Returns:
        DepartmentService: Service for department business logic operations.
    """
    return DepartmentService(
        department_repo=department_repo,
    )


def get_availability_service(
    availability_repo: AvailabilityRepository = Depends(get_availability_repository),
) -> AvailabilityService:
    """FastAPI dependency that provides an AvailabilityService instance.

    Args:
        availability_repo: AvailabilityRepository dependency.

    Returns:
        AvailabilityService: Service for availability business logic operations.
    """
    return AvailabilityService(
        availability_repo=availability_repo,
    )


def get_subteam_service(
    subteam_repo: SubteamRepository = Depends(get_subteam_repository),
    department_repo: DepartmentRepository = Depends(get_department_repository),
) -> SubteamService:
    """FastAPI dependency that provides a SubteamService instance.

    Args:
        subteam_repo: SubteamRepository dependency.
        department_repo: DepartmentRepository dependency.

    Returns:
        SubteamService: Service for subteam business logic operations.
    """
    return SubteamService(
        subteam_repo=subteam_repo,
        department_repo=department_repo,
    )


def get_authentication_service(
    client: Client = Depends(get_db),
    worker_repo: WorkerRepository = Depends(get_worker_repository),
) -> AuthenticationService:
    """FastAPI dependency that provides an AuthenticationService instance.

    Args:
        client: Supabase client from get_db dependency.
        worker_repo: WorkerRepository dependency.

    Returns:
        AuthenticationService: Service for authentication business logic operations.
    """
    return AuthenticationService(
        client=client,
        worker_repo=worker_repo,
    )


# --- Auth (re-exported for a single import point in routers) ---

CurrentUser = Depends(get_current_user)
AdminUser = Depends(require_admin)
HODUser = Depends(require_hod)
