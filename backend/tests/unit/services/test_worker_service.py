from uuid import uuid4

import pytest

from app.schemas.workers.models import WorkerCreate, WorkerUpdate
from app.service.workers.service import WorkerService
from tests.unit.services.conftest import make_worker


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
