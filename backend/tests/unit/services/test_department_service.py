from uuid import uuid4

import pytest

from app.schemas.departments.models import DepartmentCreate, DepartmentUpdate
from app.service.departments.service import DepartmentService
from tests.unit.services.conftest import make_department


@pytest.fixture
def service(mock_department_repo):
    return DepartmentService(department_repo=mock_department_repo)


class TestGetDepartment:
    def test_returns_department_when_found(self, service, mock_department_repo):
        dept = make_department()
        mock_department_repo.get_by_id.return_value = dept
        result = service.get_department(dept.id)
        assert result == dept

    def test_raises_when_not_found(self, service, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.get_department(uuid4())


class TestCreateDepartment:
    def test_creates_successfully(self, service, mock_department_repo):
        dept = make_department(name="Choir")
        mock_department_repo.get_by_name.return_value = None
        mock_department_repo.create.return_value = dept

        result = service.create_department(DepartmentCreate(name="Choir", workers_per_slot=3))
        assert result.name == "Choir"
        mock_department_repo.create.assert_called_once()

    def test_raises_on_duplicate_name(self, service, mock_department_repo):
        existing = make_department(name="Choir")
        mock_department_repo.get_by_name.return_value = existing

        with pytest.raises(ValueError, match="already exists"):
            service.create_department(DepartmentCreate(name="Choir"))
        mock_department_repo.create.assert_not_called()


class TestUpdateDepartment:
    def test_updates_successfully(self, service, mock_department_repo):
        dept = make_department()
        updated = make_department(workers_per_slot=5)
        mock_department_repo.get_by_id.return_value = dept
        mock_department_repo.update.return_value = updated

        result = service.update_department(dept.id, DepartmentUpdate(workers_per_slot=5))
        assert result.workers_per_slot == 5

    def test_raises_when_not_found(self, service, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.update_department(uuid4(), DepartmentUpdate(name="New Name"))


class TestAssignWorker:
    def test_assigns_successfully(self, service, mock_department_repo):
        dept = make_department()
        worker_id = uuid4()
        mock_department_repo.get_by_id.return_value = dept

        service.assign_worker(dept.id, worker_id)
        mock_department_repo.assign_worker.assert_called_once_with(dept.id, worker_id)

    def test_raises_when_department_not_found(self, service, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.assign_worker(uuid4(), uuid4())


class TestSetHod:
    def test_sets_hod_successfully(self, service, mock_department_repo):
        dept = make_department()
        worker_id = uuid4()
        updated = make_department(hod_id=worker_id)
        mock_department_repo.get_by_id.return_value = dept
        mock_department_repo.update.return_value = updated

        result = service.set_hod(dept.id, worker_id)
        assert result.hod_id == worker_id
