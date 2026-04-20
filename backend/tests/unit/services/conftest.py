from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.repository.availabilities.repository import AvailabilityRepository
from app.repository.departments.repository import DepartmentRepository
from app.repository.schedules.repository import ScheduleRepository
from app.repository.subteams.repository import SubteamRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.authentication.models import RegisterRequest
from app.schemas.availabilities.models import AvailabilityResponse
from app.schemas.departments.models import DepartmentResponse
from app.schemas.models import AssignmentStatus, AvailabilityType, DayOfWeek
from app.schemas.schedules.models import AssignmentResponse, ScheduleResponse
from app.schemas.subteams.models import SubteamResponse
from app.schemas.workers.models import WorkerResponse
from app.service.authentication.service import AuthenticationService

# ----------------------------------------------------------------
# Mock repositories
# ----------------------------------------------------------------


@pytest.fixture
def mock_worker_repo():
    return MagicMock(spec=WorkerRepository)


@pytest.fixture
def mock_department_repo():
    return MagicMock(spec=DepartmentRepository)


@pytest.fixture
def mock_schedule_repo():
    return MagicMock(spec=ScheduleRepository)


@pytest.fixture
def mock_availability_repo():
    return MagicMock(spec=AvailabilityRepository)


@pytest.fixture
def mock_subteam_repo():
    return MagicMock(spec=SubteamRepository)


@pytest.fixture
def mock_supabase_client():
    client = MagicMock()
    # Mock the table insert chain for worker_app_roles
    client.table.return_value.insert.return_value.execute.return_value = MagicMock()
    return client


@pytest.fixture
def service(mock_supabase_client, mock_worker_repo, mock_department_repo):
    return AuthenticationService(
        client=mock_supabase_client,
        worker_repo=mock_worker_repo,
        department_repo=mock_department_repo,
    )


# ----------------------------------------------------------------
# Model factories
# ----------------------------------------------------------------


def make_worker(**kwargs) -> WorkerResponse:
    return WorkerResponse(
        id=kwargs.get("id", uuid4()),
        first_name=kwargs.get("first_name", "John"),
        last_name=kwargs.get("last_name", "Doe"),
        email=kwargs.get("email", "john.doe@example.com"),
        phone=kwargs.get("phone", "+14165550101"),
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", date.today()),
    )


def make_department(**kwargs) -> DepartmentResponse:
    return DepartmentResponse(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "Ushers"),
        description=kwargs.get("description", "Door and seating team"),
        hod_id=kwargs.get("hod_id", None),
        workers_per_slot=kwargs.get("workers_per_slot", 2),
        created_at=kwargs.get("created_at", date.today()),
    )


def make_subteam(**kwargs) -> SubteamResponse:
    return SubteamResponse(
        id=kwargs.get("id", uuid4()),
        department_id=kwargs.get("department_id", uuid4()),
        name=kwargs.get("name", "Toddlers"),
        description=kwargs.get("description", None),
        workers_per_slot=kwargs.get("workers_per_slot", None),
        created_at=kwargs.get("created_at", date.today()),
    )


def make_schedule(**kwargs) -> ScheduleResponse:
    return ScheduleResponse(
        id=kwargs.get("id", uuid4()),
        department_id=kwargs.get("department_id", uuid4()),
        subteam_id=kwargs.get("subteam_id", None),
        title=kwargs.get("title", "Sunday Service"),
        scheduled_date=kwargs.get("scheduled_date", date(2026, 3, 15)),
        start_time=kwargs.get("start_time", "09:00:00"),
        end_time=kwargs.get("end_time", "11:00:00"),
        notes=kwargs.get("notes", None),
        reminder_days_before=kwargs.get("reminder_days_before", 1),
        created_by=kwargs.get("created_by", uuid4()),
        created_at=kwargs.get("created_at", date.today()),
    )


def make_availability(**kwargs) -> AvailabilityResponse:
    return AvailabilityResponse(
        id=kwargs.get("id", uuid4()),
        worker_id=kwargs.get("worker_id", uuid4()),
        availability_type=kwargs.get("availability_type", AvailabilityType.RECURRING),
        day_of_week=kwargs.get("day_of_week", DayOfWeek.SUNDAY),
        specific_date=kwargs.get("specific_date", None),
        is_available=kwargs.get("is_available", True),
        notes=kwargs.get("notes", None),
        created_at=kwargs.get("created_at", date.today()),
    )


def make_assignment(**kwargs) -> AssignmentResponse:
    return AssignmentResponse(
        id=kwargs.get("id", uuid4()),
        schedule_id=kwargs.get("schedule_id", uuid4()),
        worker_id=kwargs.get("worker_id", uuid4()),
        department_role_id=kwargs.get("department_role_id", None),
        subteam_id=kwargs.get("subteam_id", None),
        status=kwargs.get("status", AssignmentStatus.PENDING),
        reminder_sent_at=kwargs.get("reminder_sent_at", None),
        workers=kwargs.get("workers", None),
        schedules=kwargs.get("schedules", None),
    )


def make_register_request(**kwargs) -> RegisterRequest:
    return RegisterRequest(
        first_name=kwargs.get("first_name", "John"),
        last_name=kwargs.get("last_name", "Doe"),
        email=kwargs.get("email", "john.doe@example.com"),
        phone=kwargs.get("phone", "+14165550101"),
        password=kwargs.get("password", "securepassword123"),
    )


def make_auth_user(auth_user_id: str | None = None):
    mock = MagicMock()
    mock.user.id = auth_user_id or str(uuid4())
    return mock
