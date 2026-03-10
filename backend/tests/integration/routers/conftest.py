from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.authentication import verify_token
from app.core.dependencies import (
    get_availability_service,
    get_department_service,
    get_reminder_service,
    get_schedule_service,
    get_subteam_service,
    get_worker_service,
)
from app.main import app
from app.schemas.models import TokenPayload, UserRole
from app.service.availabilities.service import AvailabilityService
from app.service.departments.service import DepartmentService
from app.service.reminders.service import ReminderService
from app.service.schedules.service import ScheduleService
from app.service.subteams.service import SubteamService
from app.service.workers.service import WorkerService


def make_token_payload(role: UserRole = UserRole.WORKER) -> TokenPayload:
    return TokenPayload(sub=str(uuid4()), role=role, email="test@example.com")


@pytest.fixture
def mock_worker_service():
    return MagicMock(spec=WorkerService)


@pytest.fixture
def mock_department_service():
    return MagicMock(spec=DepartmentService)


@pytest.fixture
def mock_schedule_service():
    return MagicMock(spec=ScheduleService)


@pytest.fixture
def mock_availability_service():
    return MagicMock(spec=AvailabilityService)


@pytest.fixture
def mock_subteam_service():
    return MagicMock(spec=SubteamService)


@pytest.fixture
def mock_reminder_service():
    return MagicMock(spec=ReminderService)


def make_client(
    role: UserRole = UserRole.WORKER,
    worker_service=None,
    department_service=None,
    schedule_service=None,
    availability_service=None,
    subteam_service=None,
    reminder_service=None,
) -> TestClient:
    app.dependency_overrides[verify_token] = lambda: make_token_payload(role)

    if worker_service:
        app.dependency_overrides[get_worker_service] = lambda: worker_service
    if department_service:
        app.dependency_overrides[get_department_service] = lambda: department_service
    if schedule_service:
        app.dependency_overrides[get_schedule_service] = lambda: schedule_service
    if availability_service:
        app.dependency_overrides[get_availability_service] = lambda: availability_service
    if subteam_service:
        app.dependency_overrides[get_subteam_service] = lambda: subteam_service
    if reminder_service:
        app.dependency_overrides[get_reminder_service] = lambda: reminder_service

    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()
