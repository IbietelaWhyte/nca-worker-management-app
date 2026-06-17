from uuid import uuid4

import pytest

from app.schemas.workers.models import WorkerCreate, WorkerUpdate
from app.service.workers.service import WorkerService
from tests.unit.services.conftest import make_department, make_worker


@pytest.fixture
def service(mock_worker_repo, mock_department_repo):
    return WorkerService(worker_repo=mock_worker_repo, department_repo=mock_department_repo)


class TestGetWorker:
    def test_returns_worker_when_found(self, service, mock_worker_repo):
        worker = make_worker()
        mock_worker_repo.get_by_id.return_value = worker
        result = service.get_worker(worker.id)
        assert result == worker
        mock_worker_repo.get_by_id.assert_called_once_with(worker.id)

    def test_raises_when_not_found(self, service, mock_worker_repo):
        mock_worker_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.get_worker(uuid4())


class TestCreateWorker:
    def test_creates_worker_successfully(self, service, mock_worker_repo):
        worker = make_worker()
        mock_worker_repo.get_by_email.return_value = None
        mock_worker_repo.create.return_value = worker

        data = WorkerCreate(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+14165550101",
        )
        result = service.create_worker(data)
        assert result == worker
        mock_worker_repo.create.assert_called_once()

    def test_raises_on_duplicate_email(self, service, mock_worker_repo):
        existing = make_worker(email="john.doe@example.com")
        mock_worker_repo.get_by_email.return_value = existing

        data = WorkerCreate(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+14165550101",
        )
        with pytest.raises(ValueError, match="already exists"):
            service.create_worker(data)
        mock_worker_repo.create.assert_not_called()


class TestUpdateWorker:
    def test_updates_worker_successfully(self, service, mock_worker_repo):
        worker = make_worker()
        updated = make_worker(first_name="Jane")
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.update.return_value = updated

        result = service.update_worker(worker.id, WorkerUpdate(first_name="Jane"))
        assert result.first_name == "Jane"

    def test_raises_when_worker_not_found(self, service, mock_worker_repo):
        mock_worker_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.update_worker(uuid4(), WorkerUpdate(first_name="Jane"))


class TestDeactivateWorker:
    def test_deactivates_successfully(self, service, mock_worker_repo):
        worker = make_worker()
        deactivated = make_worker(is_active=False)
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.update.return_value = deactivated

        result = service.deactivate_worker(worker.id)
        assert result.is_active is False

    def test_raises_when_not_found(self, service, mock_worker_repo):
        mock_worker_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.deactivate_worker(uuid4())


class TestSearchWorkers:
    def test_returns_matching_workers(self, service, mock_worker_repo):
        workers = [make_worker(first_name="Samuel"), make_worker(first_name="Sara")]
        mock_worker_repo.search.return_value = workers

        result = service.search_workers("sa")
        assert len(result) == 2
        mock_worker_repo.search.assert_called_once_with("sa")


class TestUpdateWorkerAssistantHodDepartments:
    """Regression tests for the assistant_hod department diff in update_worker.

    The diff compares department IDs (UUIDs) returned by
    department_repo.get_assistant_hod_department_ids against the requested UUID list. A previous
    bug compared DepartmentResponse objects against UUIDs, which both raised TypeError (unhashable
    models) and never matched, so existing assignments were wrongly removed and re-added.
    """

    def test_assigns_new_departments_when_none_exist(self, service, mock_worker_repo, mock_department_repo):
        worker = make_worker()
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = []
        mock_department_repo.get_assistant_hod_department_ids.return_value = []
        dept1, dept2 = uuid4(), uuid4()

        service.update_worker(worker.id, WorkerUpdate(assistant_hod_departments=[dept1, dept2]))

        assert mock_department_repo.assign_assistant_hod.call_count == 2
        mock_department_repo.assign_assistant_hod.assert_any_call(worker.id, dept1)
        mock_department_repo.assign_assistant_hod.assert_any_call(worker.id, dept2)
        mock_department_repo.remove_assistant_hod.assert_not_called()

    def test_removes_only_dropped_department(self, service, mock_worker_repo, mock_department_repo):
        worker = make_worker()
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = []
        dept1, dept2, dept3 = uuid4(), uuid4(), uuid4()
        mock_department_repo.get_assistant_hod_department_ids.return_value = [dept1, dept2, dept3]

        # Keep dept1 and dept2, drop dept3
        service.update_worker(worker.id, WorkerUpdate(assistant_hod_departments=[dept1, dept2]))

        mock_department_repo.remove_assistant_hod.assert_called_once_with(worker.id, dept3)
        mock_department_repo.assign_assistant_hod.assert_not_called()

    def test_no_change_when_departments_identical(self, service, mock_worker_repo, mock_department_repo):
        worker = make_worker()
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = []
        dept1, dept2 = uuid4(), uuid4()
        mock_department_repo.get_assistant_hod_department_ids.return_value = [dept1, dept2]

        service.update_worker(worker.id, WorkerUpdate(assistant_hod_departments=[dept1, dept2]))

        mock_department_repo.assign_assistant_hod.assert_not_called()
        mock_department_repo.remove_assistant_hod.assert_not_called()


class TestCanManageWorker:
    def test_true_when_managed_and_worker_departments_overlap(self, service, mock_department_repo):
        manager_id, worker_id = uuid4(), uuid4()
        hod_dept = make_department()
        shared_dept = make_department()
        mock_department_repo.get_departments_by_hod.return_value = [hod_dept]
        mock_department_repo.get_assistant_hod_department_ids.return_value = [shared_dept.id]
        mock_department_repo.get_departments_for_worker.return_value = [shared_dept]

        assert service.can_manage_worker(manager_id, worker_id) is True
        # The overlap is computed from IDs directly — no per-department re-fetch.
        mock_department_repo.get_by_id.assert_not_called()

    def test_false_when_no_overlap(self, service, mock_department_repo):
        manager_id, worker_id = uuid4(), uuid4()
        mock_department_repo.get_departments_by_hod.return_value = [make_department()]
        mock_department_repo.get_assistant_hod_department_ids.return_value = [uuid4()]
        mock_department_repo.get_departments_for_worker.return_value = [make_department()]

        assert service.can_manage_worker(manager_id, worker_id) is False

    def test_false_when_manager_has_no_departments(self, service, mock_department_repo):
        manager_id, worker_id = uuid4(), uuid4()
        mock_department_repo.get_departments_by_hod.return_value = []
        mock_department_repo.get_assistant_hod_department_ids.return_value = []

        assert service.can_manage_worker(manager_id, worker_id) is False
        mock_department_repo.get_departments_for_worker.assert_not_called()
