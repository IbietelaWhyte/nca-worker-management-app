from uuid import uuid4

import pytest

from app.schemas.subteams.models import SubteamCreate, SubteamUpdate
from app.service.subteams.service import SubteamService
from tests.unit.services.conftest import make_department, make_subteam


@pytest.fixture
def service(mock_subteam_repo, mock_department_repo):
    return SubteamService(subteam_repo=mock_subteam_repo, department_repo=mock_department_repo)


class TestGetSubteam:
    def test_returns_subteam_when_found(self, service, mock_subteam_repo):
        subteam = make_subteam()
        mock_subteam_repo.get_by_id.return_value = subteam
        result = service.get_subteam(subteam.id)
        assert result == subteam

    def test_raises_when_not_found(self, service, mock_subteam_repo):
        mock_subteam_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.get_subteam(uuid4())


class TestCreateSubteam:
    def test_creates_successfully(self, service, mock_subteam_repo):
        dept_id = uuid4()
        subteam = make_subteam(name="Toddlers", department_id=dept_id)
        mock_subteam_repo.get_by_name.return_value = None
        mock_subteam_repo.create.return_value = subteam

        result = service.create_subteam(SubteamCreate(name="Toddlers", department_id=dept_id))
        assert result.name == "Toddlers"
        mock_subteam_repo.create.assert_called_once()

    def test_raises_on_duplicate_name(self, service, mock_subteam_repo):
        existing = make_subteam(name="Toddlers")
        mock_subteam_repo.get_by_name.return_value = existing

        with pytest.raises(ValueError, match="already exists"):
            service.create_subteam(SubteamCreate(name="Toddlers", department_id=uuid4()))
        mock_subteam_repo.create.assert_not_called()


class TestUpdateSubteam:
    def test_updates_successfully(self, service, mock_subteam_repo):
        subteam = make_subteam()
        updated = make_subteam(name="Juniors")
        mock_subteam_repo.get_by_id.return_value = subteam
        mock_subteam_repo.update.return_value = updated

        result = service.update_subteam(subteam.id, SubteamUpdate(name="Juniors"))
        assert result.name == "Juniors"

    def test_raises_when_not_found(self, service, mock_subteam_repo):
        mock_subteam_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.update_subteam(uuid4(), SubteamUpdate(name="New Name"))


class TestAssignWorker:
    def test_assigns_successfully_when_worker_in_parent_department(
        self, service, mock_subteam_repo, mock_department_repo
    ):
        dept_id = uuid4()
        subteam = make_subteam(department_id=dept_id)
        worker_id = uuid4()
        mock_subteam_repo.get_by_id.return_value = subteam

        # Worker is assigned to the parent department
        mock_department_repo.get_departments_for_worker.return_value = [make_department(id=dept_id)]

        service.assign_worker(subteam.id, worker_id)
        mock_subteam_repo.assign_worker.assert_called_once_with(subteam.id, worker_id)

    def test_raises_when_subteam_not_found(self, service, mock_subteam_repo):
        mock_subteam_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.assign_worker(uuid4(), uuid4())

    def test_raises_when_worker_not_in_parent_department(self, service, mock_subteam_repo, mock_department_repo):
        dept_id = uuid4()
        subteam = make_subteam(department_id=dept_id)
        worker_id = uuid4()
        mock_subteam_repo.get_by_id.return_value = subteam

        # Worker is assigned to a different department
        other_dept_id = uuid4()
        mock_department_repo.get_departments_for_worker.return_value = [make_department(id=other_dept_id)]

        with pytest.raises(ValueError, match="not assigned to department"):
            service.assign_worker(subteam.id, worker_id)
        mock_subteam_repo.assign_worker.assert_not_called()

    def test_raises_when_worker_not_in_any_department(self, service, mock_subteam_repo, mock_department_repo):
        dept_id = uuid4()
        subteam = make_subteam(department_id=dept_id)
        worker_id = uuid4()
        mock_subteam_repo.get_by_id.return_value = subteam

        # Worker is not assigned to any department
        mock_department_repo.get_departments_for_worker.return_value = []

        with pytest.raises(ValueError, match="not assigned to department"):
            service.assign_worker(subteam.id, worker_id)
        mock_subteam_repo.assign_worker.assert_not_called()


class TestUnassignWorker:
    def test_unassigns_successfully(self, service, mock_subteam_repo):
        subteam = make_subteam()
        worker_id = uuid4()
        mock_subteam_repo.get_by_id.return_value = subteam

        service.unassign_worker(subteam.id, worker_id)
        mock_subteam_repo.unassign_worker.assert_called_once_with(subteam.id, worker_id)

    def test_raises_when_subteam_not_found(self, service, mock_subteam_repo):
        mock_subteam_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="not found"):
            service.unassign_worker(uuid4(), uuid4())
