from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.repository.availabilities.repository import AvailabilityRepository
from app.repository.department_roles.repository import DepartmentRoleRepository
from app.repository.departments.repository import DepartmentRepository
from app.repository.schedules.repository import ScheduleRepository
from app.repository.subteams.repository import SubteamRepository
from app.repository.worker_leave.repository import WorkerLeaveRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.authentication.models import RegisterRequest
from app.schemas.availabilities.models import AvailabilityResponse
from app.schemas.department_roles.models import DepartmentRoleResponse
from app.schemas.departments.models import DepartmentResponse
from app.schemas.models import AvailabilityType, DayOfWeek
from app.schemas.schedules.models import AssignmentResponse, ScheduleResponse
from app.schemas.subteams.models import SubteamResponse, SubteamWithWorkersResponse
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
    """Nobody has recorded anything by default, which the rota reads as available.

    `get_for_workers` is the batched fetch the planner drives off — the per-worker
    `get_by_worker_and_*` calls are AvailabilityService's now, not the scheduler's.
    """
    repo = MagicMock(spec=AvailabilityRepository)
    repo.get_for_workers.return_value = []
    return repo


@pytest.fixture
def mock_leave_repo():
    """No leave by default, so an existing test never has a worker quietly removed."""
    repo = MagicMock(spec=WorkerLeaveRepository)
    repo.get_active_on.return_value = []
    repo.get_for_workers.return_value = []
    repo.get_by_worker.return_value = []
    repo.get_overlapping.return_value = []
    return repo


@pytest.fixture
def mock_subteam_repo():
    return MagicMock(spec=SubteamRepository)


@pytest.fixture
def mock_department_role_repo():
    return MagicMock(spec=DepartmentRoleRepository)


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
        auth_user_id=kwargs.get("auth_user_id", None),
        first_name=kwargs.get("first_name", "John"),
        last_name=kwargs.get("last_name", "Doe"),
        email=kwargs.get("email", "john.doe@example.com"),
        phone=kwargs.get("phone", "+14165550101"),
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", date.today()),
    )


def make_department(**kwargs) -> DepartmentResponse:
    """A department as the repository returns it.

    `band=(min, max)` is shorthand for the pair; a bare `band=N` means a band of exactly N,
    which is how every department behaved before the minimum and maximum were split apart.
    """
    minimum, maximum = _band(kwargs.get("band", 2))
    return DepartmentResponse(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "Ushers"),
        description=kwargs.get("description", "Door and seating team"),
        hod_id=kwargs.get("hod_id", None),
        min_workers_per_slot=kwargs.get("min_workers_per_slot", minimum),
        max_workers_per_slot=kwargs.get("max_workers_per_slot", maximum),
        created_at=kwargs.get("created_at", date.today()),
    )


def make_subteam(**kwargs) -> SubteamResponse:
    """A subteam as the repository returns it. `band` defaults to None — inherit the department."""
    minimum, maximum = _band(kwargs.get("band"))
    return SubteamResponse(
        id=kwargs.get("id", uuid4()),
        department_id=kwargs.get("department_id", uuid4()),
        name=kwargs.get("name", "Toddlers"),
        description=kwargs.get("description", None),
        min_workers_per_slot=kwargs.get("min_workers_per_slot", minimum),
        max_workers_per_slot=kwargs.get("max_workers_per_slot", maximum),
        created_at=kwargs.get("created_at", date.today()),
    )


def _band(value: int | tuple[int, int] | None) -> tuple[int | None, int | None]:
    """Normalise a `band=` shorthand into (minimum, maximum).

    A bare int is the pre-split behaviour — fill to N, flag below N — which keeps every test
    written before the band existed asserting exactly what it used to.
    """
    if value is None:
        return None, None
    if isinstance(value, tuple):
        return value
    return value, value


def make_subteam_member(**kwargs) -> SubteamWithWorkersResponse:
    """One row as `get_with_workers` returns it: the subteam, with a member embedded."""
    subteam = kwargs.get("subteam") or make_subteam()
    return SubteamWithWorkersResponse(**subteam.model_dump(), worker=kwargs.get("worker"))


def make_department_role(**kwargs) -> DepartmentRoleResponse:
    return DepartmentRoleResponse(
        id=kwargs.get("id", uuid4()),
        department_id=kwargs.get("department_id", uuid4()),
        name=kwargs.get("name", "Teacher"),
        description=kwargs.get("description", None),
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
        reminder_days_before=kwargs.get("reminder_days_before", [1]),
        min_workers=kwargs.get("min_workers", None),
        max_workers=kwargs.get("max_workers", None),
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
        notice_sent_at=kwargs.get("notice_sent_at", None),
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
