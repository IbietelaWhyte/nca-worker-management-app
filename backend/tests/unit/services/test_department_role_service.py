from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.schemas.department_roles.models import DepartmentRoleCreate, DepartmentRoleUpdate
from app.service.department_roles.service import DepartmentRoleService
from tests.unit.services.conftest import make_department, make_department_role


@pytest.fixture
def service(mock_department_role_repo, mock_department_repo):
    return DepartmentRoleService(department_role_repo=mock_department_role_repo, department_repo=mock_department_repo)


class TestGetRole:
    def test_returns_role_when_found(self, service, mock_department_role_repo):
        role = make_department_role()
        mock_department_role_repo.get_by_id.return_value = role
        assert service.get_role(role.id) == role

    def test_raises_when_not_found(self, service, mock_department_role_repo):
        mock_department_role_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.get_role(uuid4())


class TestCreateRole:
    def test_creates_successfully(self, service, mock_department_role_repo):
        dept_id = uuid4()
        role = make_department_role(name="Teacher", department_id=dept_id)
        mock_department_role_repo.get_by_name_in_department.return_value = None
        mock_department_role_repo.create.return_value = role

        result = service.create_role(DepartmentRoleCreate(name="Teacher", department_id=dept_id))
        assert result.name == "Teacher"
        mock_department_role_repo.create.assert_called_once()

    def test_raises_on_duplicate_name_in_department(self, service, mock_department_role_repo):
        dept_id = uuid4()
        existing = make_department_role(name="Teacher", department_id=dept_id)
        mock_department_role_repo.get_by_name_in_department.return_value = existing

        with pytest.raises(ConflictError, match="already exists"):
            service.create_role(DepartmentRoleCreate(name="Teacher", department_id=dept_id))
        mock_department_role_repo.create.assert_not_called()

    def test_rejects_permission_level_as_name(self, service, mock_department_role_repo):
        with pytest.raises(BadRequestError, match="permission level"):
            service.create_role(DepartmentRoleCreate(name="HOD", department_id=uuid4()))
        mock_department_role_repo.create.assert_not_called()


class TestUpdateRole:
    def test_updates_successfully(self, service, mock_department_role_repo):
        role = make_department_role()
        updated = make_department_role(name="Helper")
        mock_department_role_repo.get_by_id.return_value = role
        mock_department_role_repo.get_by_name_in_department.return_value = None
        mock_department_role_repo.update.return_value = updated

        result = service.update_role(role.id, DepartmentRoleUpdate(name="Helper"))
        assert result.name == "Helper"

    def test_raises_when_not_found(self, service, mock_department_role_repo):
        mock_department_role_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.update_role(uuid4(), DepartmentRoleUpdate(name="New Name"))

    def test_rejects_permission_level_as_name(self, service, mock_department_role_repo):
        role = make_department_role()
        mock_department_role_repo.get_by_id.return_value = role

        with pytest.raises(BadRequestError, match="permission level"):
            service.update_role(role.id, DepartmentRoleUpdate(name="Head of Department"))
        mock_department_role_repo.update.assert_not_called()

    def test_raises_on_rename_onto_existing_name(self, service, mock_department_role_repo):
        dept_id = uuid4()
        role = make_department_role(name="Teacher", department_id=dept_id)
        other = make_department_role(name="Helper", department_id=dept_id)
        mock_department_role_repo.get_by_id.return_value = role
        mock_department_role_repo.get_by_name_in_department.return_value = other

        with pytest.raises(ConflictError, match="already exists"):
            service.update_role(role.id, DepartmentRoleUpdate(name="Helper"))
        mock_department_role_repo.update.assert_not_called()

    def test_allows_renaming_a_role_to_its_own_name(self, service, mock_department_role_repo):
        role = make_department_role(name="Teacher")
        mock_department_role_repo.get_by_id.return_value = role
        # The uniqueness probe finds the role being renamed, which is not a collision.
        mock_department_role_repo.get_by_name_in_department.return_value = role
        mock_department_role_repo.update.return_value = role

        assert service.update_role(role.id, DepartmentRoleUpdate(name="Teacher")).name == "Teacher"

    def test_skips_name_checks_when_only_description_changes(self, service, mock_department_role_repo):
        role = make_department_role()
        mock_department_role_repo.get_by_id.return_value = role
        mock_department_role_repo.update.return_value = role

        service.update_role(role.id, DepartmentRoleUpdate(description="Leads the under-fives"))
        mock_department_role_repo.get_by_name_in_department.assert_not_called()


class TestReservedRoleNames:
    @pytest.mark.parametrize(
        "name",
        [
            "HOD",
            "hod",
            "H.O.D.",
            " hod ",
            "Head of Department",
            "head-of-department",
            "Department Head",
            "Assistant HOD",
            "Asst. HOD",
            "assistant_hod",
            "Assistant Head of Department",
            "Admin",
            "Administrator",
            "Worker",
        ],
    )
    def test_rejects_permission_level_names(self, service, mock_department_role_repo, name):
        with pytest.raises(BadRequestError, match="permission level"):
            service.create_role(DepartmentRoleCreate(name=name, department_id=uuid4()))
        mock_department_role_repo.create.assert_not_called()

    @pytest.mark.parametrize(
        "name",
        # Every one of these is a real seeded role — a substring rule on "head" or "assistant"
        # would wrongly reject them.
        ["Head Usher", "Assistant", "Ministry Lead", "Teacher", "Choir Director", "Technical Lead"],
    )
    def test_allows_real_job_names(self, service, mock_department_role_repo, name):
        dept_id = uuid4()
        mock_department_role_repo.get_by_name_in_department.return_value = None
        mock_department_role_repo.create.return_value = make_department_role(name=name, department_id=dept_id)

        assert service.create_role(DepartmentRoleCreate(name=name, department_id=dept_id)).name == name


class TestDeleteRole:
    def test_deletes_successfully(self, service, mock_department_role_repo):
        role = make_department_role()
        mock_department_role_repo.get_by_id.return_value = role

        service.delete_role(role.id)
        mock_department_role_repo.delete.assert_called_once_with(role.id)

    def test_raises_when_not_found(self, service, mock_department_role_repo):
        mock_department_role_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.delete_role(uuid4())


class TestAssignWorker:
    def test_assigns_when_worker_in_department(self, service, mock_department_role_repo, mock_department_repo):
        dept_id = uuid4()
        role = make_department_role(department_id=dept_id)
        worker_id = uuid4()
        mock_department_role_repo.get_by_id.return_value = role
        mock_department_repo.get_departments_for_worker.return_value = [make_department(id=dept_id)]

        service.assign_worker(role.id, worker_id)
        mock_department_role_repo.assign_worker_role.assert_called_once_with(role.id, worker_id)

    def test_raises_when_role_not_found(self, service, mock_department_role_repo):
        mock_department_role_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.assign_worker(uuid4(), uuid4())

    def test_raises_when_worker_not_in_department(self, service, mock_department_role_repo, mock_department_repo):
        role = make_department_role(department_id=uuid4())
        mock_department_role_repo.get_by_id.return_value = role
        mock_department_repo.get_departments_for_worker.return_value = [make_department(id=uuid4())]

        with pytest.raises(BadRequestError, match="not assigned to department"):
            service.assign_worker(role.id, uuid4())
        mock_department_role_repo.assign_worker_role.assert_not_called()


class TestUnassignWorker:
    def test_unassigns_successfully(self, service, mock_department_role_repo):
        role = make_department_role()
        worker_id = uuid4()
        mock_department_role_repo.get_by_id.return_value = role

        service.unassign_worker(role.id, worker_id)
        mock_department_role_repo.unassign_worker_role.assert_called_once_with(role.id, worker_id)

    def test_raises_when_role_not_found(self, service, mock_department_role_repo):
        mock_department_role_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.unassign_worker(uuid4(), uuid4())
