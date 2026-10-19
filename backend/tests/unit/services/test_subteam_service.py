from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.schemas.subteams.models import SubteamCreate, SubteamUpdate
from app.service.subteams.service import SubteamService
from tests.unit.services.conftest import make_subteam


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
        with pytest.raises(NotFoundError, match="not found"):
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

        with pytest.raises(ConflictError, match="already exists"):
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
        with pytest.raises(NotFoundError, match="not found"):
            service.update_subteam(uuid4(), SubteamUpdate(name="New Name"))


def _department_with(dept_id, member_ids):
    """The department-with-members read, reduced to the one field assign_workers looks at."""
    return SimpleNamespace(id=dept_id, workers=[SimpleNamespace(id=i) for i in member_ids])


class TestAssignWorkers:
    def test_assigns_every_worker_in_one_call(self, service, mock_subteam_repo, mock_department_repo):
        dept_id = uuid4()
        subteam = make_subteam(department_id=dept_id)
        worker_ids = [uuid4(), uuid4(), uuid4()]
        mock_subteam_repo.get_by_id.return_value = subteam
        mock_department_repo.get_with_workers.return_value = _department_with(dept_id, [*worker_ids, uuid4()])

        service.assign_workers(subteam.id, worker_ids)

        mock_department_repo.get_with_workers.assert_called_once_with(dept_id)
        mock_subteam_repo.assign_workers.assert_called_once_with(dept_id, subteam.id, worker_ids)

    def test_drops_duplicate_ids(self, service, mock_subteam_repo, mock_department_repo):
        dept_id = uuid4()
        subteam = make_subteam(department_id=dept_id)
        a, b = uuid4(), uuid4()
        mock_subteam_repo.get_by_id.return_value = subteam
        mock_department_repo.get_with_workers.return_value = _department_with(dept_id, [a, b])

        service.assign_workers(subteam.id, [a, b, a])

        mock_subteam_repo.assign_workers.assert_called_once_with(dept_id, subteam.id, [a, b])

    def test_raises_when_subteam_not_found(self, service, mock_subteam_repo):
        mock_subteam_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.assign_workers(uuid4(), [uuid4()])
        mock_subteam_repo.assign_workers.assert_not_called()

    def test_writes_nothing_when_any_worker_is_outside_the_department(
        self, service, mock_subteam_repo, mock_department_repo
    ):
        dept_id = uuid4()
        subteam = make_subteam(department_id=dept_id)
        member, outsider = uuid4(), uuid4()
        mock_subteam_repo.get_by_id.return_value = subteam
        mock_department_repo.get_with_workers.return_value = _department_with(dept_id, [member])

        with pytest.raises(BadRequestError, match="not assigned to department") as exc:
            service.assign_workers(subteam.id, [member, outsider])
        assert str(outsider) in str(exc.value)
        assert str(member) not in str(exc.value)
        mock_subteam_repo.assign_workers.assert_not_called()

    def test_raises_when_department_has_no_members(self, service, mock_subteam_repo, mock_department_repo):
        subteam = make_subteam()
        mock_subteam_repo.get_by_id.return_value = subteam
        mock_department_repo.get_with_workers.return_value = None

        with pytest.raises(BadRequestError, match="not assigned to department"):
            service.assign_workers(subteam.id, [uuid4()])
        mock_subteam_repo.assign_workers.assert_not_called()


class TestUnassignWorker:
    def test_unassigns_successfully(self, service, mock_subteam_repo):
        subteam = make_subteam()
        worker_id = uuid4()
        mock_subteam_repo.get_by_id.return_value = subteam

        service.unassign_worker(subteam.id, worker_id)
        mock_subteam_repo.unassign_worker.assert_called_once_with(subteam.id, worker_id)

    def test_raises_when_subteam_not_found(self, service, mock_subteam_repo):
        mock_subteam_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.unassign_worker(uuid4(), uuid4())
