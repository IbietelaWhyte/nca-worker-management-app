from uuid import uuid4

import pytest
from supabase_auth.errors import AuthApiError

from app.core.config import settings
from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.schemas.models import TokenPayload, UserRole
from app.schemas.workers.models import WorkerContactMatch, WorkerCreate, WorkerUpdate
from app.service.workers.service import WorkerService
from tests.unit.services.conftest import make_assignment, make_department, make_worker


def _token(role: UserRole = UserRole.HOD, email: str | None = "manager@example.com") -> TokenPayload:
    return TokenPayload(sub="sub-123", role=role, email=email)


@pytest.fixture
def service(mock_worker_repo, mock_department_repo, mock_schedule_repo, mock_supabase_client):
    return WorkerService(
        worker_repo=mock_worker_repo,
        department_repo=mock_department_repo,
        schedule_repo=mock_schedule_repo,
        client=mock_supabase_client,
    )


class TestGetWorker:
    def test_returns_worker_when_found(self, service, mock_worker_repo):
        worker = make_worker()
        mock_worker_repo.get_by_id.return_value = worker
        result = service.get_worker(worker.id)
        assert result == worker
        mock_worker_repo.get_by_id.assert_called_once_with(worker.id)

    def test_raises_when_not_found(self, service, mock_worker_repo):
        mock_worker_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.get_worker(uuid4())


class TestCreateWorker:
    def test_creates_worker_successfully(self, service, mock_worker_repo):
        worker = make_worker()
        mock_worker_repo.get_by_email.return_value = None
        mock_worker_repo.get_by_phone.return_value = None
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
        with pytest.raises(ConflictError, match="already exists"):
            service.create_worker(data)
        mock_worker_repo.create.assert_not_called()

    def test_raises_on_duplicate_phone(self, service, mock_worker_repo):
        # Phone is the SMS reminder key, so it is checked even when the email is free. Regression
        # test: this branch used to be unreachable whenever an email was supplied.
        mock_worker_repo.get_by_email.return_value = None
        mock_worker_repo.get_by_phone.return_value = make_worker(phone="+14165550101")

        data = WorkerCreate(
            first_name="John",
            last_name="Doe",
            email="fresh@example.com",
            phone="+14165550101",
        )
        with pytest.raises(ConflictError, match="phone number"):
            service.create_worker(data)
        mock_worker_repo.create.assert_not_called()

    def test_normalizes_email_and_phone_before_saving(self, service, mock_worker_repo):
        mock_worker_repo.get_by_email.return_value = None
        mock_worker_repo.get_by_phone.return_value = None
        mock_worker_repo.create.return_value = make_worker()

        data = WorkerCreate(
            first_name="  John  ",
            last_name="Doe",
            email="John.Doe@Example.com",
            phone="(416) 555-0101",
        )
        service.create_worker(data)

        saved = mock_worker_repo.create.call_args.args[0]
        assert saved["email"] == "john.doe@example.com"
        assert saved["phone"] == "+14165550101"
        assert saved["first_name"] == "John"


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
        with pytest.raises(NotFoundError, match="not found"):
            service.update_worker(uuid4(), WorkerUpdate(first_name="Jane"))

    def test_role_change_syncs_highest_role_to_auth(self, service, mock_worker_repo, mock_supabase_client):
        auth_user_id = uuid4()
        worker = make_worker(auth_user_id=auth_user_id)
        mock_worker_repo.get_by_id.return_value = worker
        # Worker ends up with both worker and admin roles; the JWT must reflect admin.
        mock_worker_repo.get_worker_roles.return_value = [UserRole.WORKER, UserRole.ADMIN]

        service.update_worker(worker.id, WorkerUpdate(roles=[UserRole.WORKER, UserRole.ADMIN]))

        mock_worker_repo.replace_worker_roles.assert_called_once_with(worker.id, [UserRole.WORKER, UserRole.ADMIN])
        mock_supabase_client.auth.admin.update_user_by_id.assert_called_once_with(
            str(auth_user_id), {"app_metadata": {"role": UserRole.ADMIN}}
        )

    def test_role_change_skips_auth_sync_without_account(self, service, mock_worker_repo, mock_supabase_client):
        worker = make_worker(auth_user_id=None)
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = [UserRole.ADMIN]

        service.update_worker(worker.id, WorkerUpdate(roles=[UserRole.ADMIN]))

        mock_worker_repo.replace_worker_roles.assert_called_once()
        mock_supabase_client.auth.admin.update_user_by_id.assert_not_called()

    def test_demotion_syncs_new_highest_role(self, service, mock_worker_repo, mock_supabase_client):
        auth_user_id = uuid4()
        worker = make_worker(auth_user_id=auth_user_id)
        mock_worker_repo.get_by_id.return_value = worker
        # Admin removed; only worker remains.
        mock_worker_repo.get_worker_roles.return_value = [UserRole.WORKER]

        service.update_worker(worker.id, WorkerUpdate(roles=[UserRole.WORKER]))

        mock_supabase_client.auth.admin.update_user_by_id.assert_called_once_with(
            str(auth_user_id), {"app_metadata": {"role": UserRole.WORKER}}
        )

    def test_profile_only_update_does_not_sync_auth(self, service, mock_worker_repo, mock_supabase_client):
        worker = make_worker(auth_user_id=uuid4())
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.update.return_value = make_worker(first_name="Jane")
        mock_worker_repo.get_worker_roles.return_value = [UserRole.WORKER]

        service.update_worker(worker.id, WorkerUpdate(first_name="Jane"))

        mock_worker_repo.replace_worker_roles.assert_not_called()
        mock_supabase_client.auth.admin.update_user_by_id.assert_not_called()


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
        with pytest.raises(NotFoundError, match="not found"):
            service.deactivate_worker(uuid4())


def _setup_deletable(mock_worker_repo, mock_department_repo, mock_schedule_repo, **worker_kwargs):
    """Configure mocks so delete_worker passes every guard, returning the worker."""
    worker = make_worker(is_active=False, **worker_kwargs)
    mock_worker_repo.get_by_id.return_value = worker
    mock_worker_repo.delete.return_value = True
    mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = []
    mock_department_repo.get_departments_by_hod.return_value = []
    return worker


class TestDeleteWorker:
    def test_deletes_inactive_worker(self, service, mock_worker_repo, mock_department_repo, mock_schedule_repo):
        worker = _setup_deletable(mock_worker_repo, mock_department_repo, mock_schedule_repo)

        service.delete_worker(worker.id)

        mock_worker_repo.delete.assert_called_once_with(worker.id)

    def test_raises_when_not_found(self, service, mock_worker_repo):
        mock_worker_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="not found"):
            service.delete_worker(uuid4())

    def test_rejects_active_worker(self, service, mock_worker_repo):
        worker = make_worker(is_active=True)
        mock_worker_repo.get_by_id.return_value = worker

        with pytest.raises(BadRequestError, match="Deactivate"):
            service.delete_worker(worker.id)
        mock_worker_repo.delete.assert_not_called()

    def test_rejects_worker_with_upcoming_assignments(
        self, service, mock_worker_repo, mock_department_repo, mock_schedule_repo
    ):
        worker = _setup_deletable(mock_worker_repo, mock_department_repo, mock_schedule_repo)
        mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = [make_assignment(), make_assignment()]

        with pytest.raises(ConflictError, match="2 upcoming schedule assignments"):
            service.delete_worker(worker.id)
        mock_worker_repo.delete.assert_not_called()

    def test_pluralises_a_single_upcoming_assignment(
        self, service, mock_worker_repo, mock_department_repo, mock_schedule_repo
    ):
        worker = _setup_deletable(mock_worker_repo, mock_department_repo, mock_schedule_repo)
        mock_schedule_repo.get_upcoming_assignments_for_worker.return_value = [make_assignment()]

        with pytest.raises(ConflictError, match="1 upcoming schedule assignment\\."):
            service.delete_worker(worker.id)

    def test_rejects_department_head(self, service, mock_worker_repo, mock_department_repo, mock_schedule_repo):
        worker = _setup_deletable(mock_worker_repo, mock_department_repo, mock_schedule_repo)
        mock_department_repo.get_departments_by_hod.return_value = [make_department(name="Ushers")]

        with pytest.raises(ConflictError, match="head of Ushers"):
            service.delete_worker(worker.id)
        mock_worker_repo.delete.assert_not_called()

    def test_revokes_login_before_deleting_row(
        self, service, mock_worker_repo, mock_department_repo, mock_schedule_repo, mock_supabase_client
    ):
        auth_user_id = uuid4()
        worker = _setup_deletable(mock_worker_repo, mock_department_repo, mock_schedule_repo, auth_user_id=auth_user_id)

        service.delete_worker(worker.id)

        mock_supabase_client.auth.admin.delete_user.assert_called_once_with(str(auth_user_id))

    def test_skips_login_revocation_without_an_account(
        self, service, mock_worker_repo, mock_department_repo, mock_schedule_repo, mock_supabase_client
    ):
        worker = _setup_deletable(mock_worker_repo, mock_department_repo, mock_schedule_repo, auth_user_id=None)

        service.delete_worker(worker.id)

        mock_supabase_client.auth.admin.delete_user.assert_not_called()
        mock_worker_repo.delete.assert_called_once_with(worker.id)

    def test_does_not_delete_row_when_login_revocation_fails(
        self, service, mock_worker_repo, mock_department_repo, mock_schedule_repo, mock_supabase_client
    ):
        worker = _setup_deletable(mock_worker_repo, mock_department_repo, mock_schedule_repo, auth_user_id=uuid4())
        mock_supabase_client.auth.admin.delete_user.side_effect = AuthApiError("boom", 500, "500")

        with pytest.raises(AppError, match="revoke"):
            service.delete_worker(worker.id)
        mock_worker_repo.delete.assert_not_called()

    def test_raises_when_row_delete_reports_no_rows(
        self, service, mock_worker_repo, mock_department_repo, mock_schedule_repo
    ):
        worker = _setup_deletable(mock_worker_repo, mock_department_repo, mock_schedule_repo)
        mock_worker_repo.delete.return_value = False

        with pytest.raises(AppError, match="Failed to delete worker"):
            service.delete_worker(worker.id)


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


class TestGetWorkerForToken:
    def test_returns_worker(self, service, mock_worker_repo):
        worker = make_worker()
        mock_worker_repo.get_by_email.return_value = worker
        assert service.get_worker_for_token(_token()) == worker

    def test_raises_bad_request_when_no_email(self, service):
        with pytest.raises(BadRequestError, match="Email not found"):
            service.get_worker_for_token(_token(email=None))

    def test_raises_not_found_when_no_profile(self, service, mock_worker_repo):
        mock_worker_repo.get_by_email.return_value = None
        with pytest.raises(NotFoundError, match="Worker profile not found"):
            service.get_worker_for_token(_token())


class TestGetManagedDepartmentIds:
    def test_unions_hod_and_assistant_hod_departments(self, service, mock_department_repo):
        hod_dept = make_department()
        assistant_dept_id = make_department().id
        mock_department_repo.get_departments_by_hod.return_value = [hod_dept]
        mock_department_repo.get_assistant_hod_department_ids.return_value = [assistant_dept_id]

        result = service.get_managed_department_ids(uuid4())
        assert result == {hod_dept.id, assistant_dept_id}


def _setup_can_manage(mock_worker_repo, mock_department_repo, *, overlap: bool):
    """Configure mocks so can_manage_worker resolves to the requested overlap result."""
    actor = make_worker()
    managed_dept = make_department()
    mock_worker_repo.get_by_email.return_value = actor
    mock_department_repo.get_departments_by_hod.return_value = [managed_dept]
    mock_department_repo.get_assistant_hod_department_ids.return_value = []
    worker_dept = managed_dept if overlap else make_department()
    mock_department_repo.get_departments_for_worker.return_value = [worker_dept]
    return actor, managed_dept


class TestAuthorizeManageWorker:
    def test_admin_bypasses_lookup(self, service, mock_worker_repo):
        service.authorize_manage_worker(_token(role=UserRole.ADMIN), uuid4())
        mock_worker_repo.get_by_email.assert_not_called()

    def test_allows_when_manager_oversees_worker(self, service, mock_worker_repo, mock_department_repo):
        _setup_can_manage(mock_worker_repo, mock_department_repo, overlap=True)
        service.authorize_manage_worker(_token(), uuid4())  # no raise

    def test_denies_when_not_manager(self, service, mock_worker_repo, mock_department_repo):
        _setup_can_manage(mock_worker_repo, mock_department_repo, overlap=False)
        with pytest.raises(PermissionDeniedError):
            service.authorize_manage_worker(_token(), uuid4())


class TestAuthorizeUpdateWorker:
    def test_admin_bypasses(self, service, mock_worker_repo):
        service.authorize_update_worker(_token(role=UserRole.ADMIN), uuid4(), WorkerUpdate(first_name="J"))
        mock_worker_repo.get_by_email.assert_not_called()

    def test_denies_assigning_restricted_role(self, service, mock_worker_repo, mock_department_repo):
        _setup_can_manage(mock_worker_repo, mock_department_repo, overlap=True)
        with pytest.raises(PermissionDeniedError, match="worker and assistant_hod"):
            service.authorize_update_worker(_token(), uuid4(), WorkerUpdate(roles=[UserRole.ADMIN]))

    def test_denies_assistant_hod_for_unmanaged_department(self, service, mock_worker_repo, mock_department_repo):
        _setup_can_manage(mock_worker_repo, mock_department_repo, overlap=True)
        with pytest.raises(PermissionDeniedError, match="departments you manage"):
            service.authorize_update_worker(_token(), uuid4(), WorkerUpdate(assistant_hod_departments=[uuid4()]))

    def test_allows_permitted_update(self, service, mock_worker_repo, mock_department_repo):
        _, managed_dept = _setup_can_manage(mock_worker_repo, mock_department_repo, overlap=True)
        service.authorize_update_worker(
            _token(),
            uuid4(),
            WorkerUpdate(roles=[UserRole.WORKER], assistant_hod_departments=[managed_dept.id]),
        )  # no raise


class TestAuthorizeCreateAssignment:
    def test_admin_bypasses(self, service, mock_worker_repo):
        service.authorize_create_assignment(_token(role=UserRole.ADMIN), uuid4())
        mock_worker_repo.get_by_email.assert_not_called()

    def test_allows_managed_department(self, service, mock_worker_repo, mock_department_repo):
        actor = make_worker()
        managed_dept = make_department()
        mock_worker_repo.get_by_email.return_value = actor
        mock_department_repo.get_departments_by_hod.return_value = [managed_dept]
        mock_department_repo.get_assistant_hod_department_ids.return_value = []
        service.authorize_create_assignment(_token(), managed_dept.id)  # no raise

    def test_denies_unmanaged_department(self, service, mock_worker_repo, mock_department_repo):
        mock_worker_repo.get_by_email.return_value = make_worker()
        mock_department_repo.get_departments_by_hod.return_value = []
        mock_department_repo.get_assistant_hod_department_ids.return_value = []
        with pytest.raises(PermissionDeniedError):
            service.authorize_create_assignment(_token(), uuid4())


class TestListVisibleWorkers:
    def test_admin_sees_all(self, service, mock_worker_repo):
        mock_worker_repo.get_all.return_value = [make_worker(), make_worker()]
        mock_worker_repo.get_worker_roles.return_value = []
        result = service.list_visible_workers(_token(role=UserRole.ADMIN))
        assert len(result) == 2

    def test_admin_search_delegates_to_search(self, service, mock_worker_repo):
        mock_worker_repo.search.return_value = [make_worker()]
        service.list_visible_workers(_token(role=UserRole.ADMIN), search="jo")
        mock_worker_repo.search.assert_called_once_with("jo")

    def test_hod_sees_only_managed_department_workers(self, service, mock_worker_repo, mock_department_repo):
        actor = make_worker()
        managed_dept = make_department()
        w1, w2 = make_worker(), make_worker()
        mock_worker_repo.get_by_email.return_value = actor
        mock_department_repo.get_departments_by_hod.return_value = [managed_dept]
        mock_department_repo.get_assistant_hod_department_ids.return_value = []
        mock_worker_repo.get_workers_by_department.return_value = [w1, w2]

        result = service.list_visible_workers(_token(role=UserRole.HOD))
        assert {w.id for w in result} == {w1.id, w2.id}

    def test_hod_with_no_departments_sees_none(self, service, mock_worker_repo, mock_department_repo):
        mock_worker_repo.get_by_email.return_value = make_worker()
        mock_department_repo.get_departments_by_hod.return_value = []
        mock_department_repo.get_assistant_hod_department_ids.return_value = []
        assert service.list_visible_workers(_token(role=UserRole.HOD)) == []

    def test_worker_sees_only_self(self, service, mock_worker_repo):
        me = make_worker()
        mock_worker_repo.get_by_email.return_value = me
        mock_worker_repo.get_roles_for_workers.return_value = {me.id: [UserRole.WORKER]}

        result = service.list_visible_workers(_token(role=UserRole.WORKER))

        assert [w.id for w in result] == [me.id]
        # A regular worker never enumerates the full table.
        mock_worker_repo.get_all.assert_not_called()
        mock_worker_repo.search.assert_not_called()


class TestAuthorizeViewWorker:
    def test_admin_bypasses_lookup(self, service, mock_worker_repo):
        service.authorize_view_worker(_token(role=UserRole.ADMIN), uuid4())  # no raise
        mock_worker_repo.get_by_email.assert_not_called()

    def test_manager_allowed_for_managed_worker(self, service, mock_worker_repo, mock_department_repo):
        _setup_can_manage(mock_worker_repo, mock_department_repo, overlap=True)
        service.authorize_view_worker(_token(role=UserRole.HOD), uuid4())  # no raise

    def test_manager_denied_for_unmanaged_worker(self, service, mock_worker_repo, mock_department_repo):
        _setup_can_manage(mock_worker_repo, mock_department_repo, overlap=False)
        with pytest.raises(PermissionDeniedError, match="departments you manage"):
            service.authorize_view_worker(_token(role=UserRole.HOD), uuid4())

    def test_worker_allowed_for_own_record(self, service, mock_worker_repo):
        me = make_worker()
        mock_worker_repo.get_by_email.return_value = me
        service.authorize_view_worker(_token(role=UserRole.WORKER), me.id)  # no raise

    def test_worker_denied_for_other_record(self, service, mock_worker_repo):
        mock_worker_repo.get_by_email.return_value = make_worker()
        with pytest.raises(PermissionDeniedError, match="your own worker record"):
            service.authorize_view_worker(_token(role=UserRole.WORKER), uuid4())


class TestUpdateWorkerRoles:
    def test_update_worker_replaces_roles_atomically(self, service, mock_worker_repo):
        worker = make_worker()
        mock_worker_repo.get_by_id.return_value = worker
        mock_worker_repo.get_worker_roles.return_value = []

        service.update_worker(worker.id, WorkerUpdate(roles=[UserRole.WORKER, UserRole.HOD]))

        mock_worker_repo.replace_worker_roles.assert_called_once_with(worker.id, [UserRole.WORKER, UserRole.HOD])


class TestBatchRoleLoading:
    def test_get_all_workers_loads_roles_in_one_batch(self, service, mock_worker_repo):
        w1, w2 = make_worker(), make_worker()
        mock_worker_repo.get_all.return_value = [w1, w2]
        mock_worker_repo.get_roles_for_workers.return_value = {
            w1.id: [UserRole.WORKER],
            w2.id: [UserRole.HOD],
        }

        result = service.get_all_workers()

        # Single batched query, not one get_worker_roles per worker.
        mock_worker_repo.get_roles_for_workers.assert_called_once_with([w1.id, w2.id])
        mock_worker_repo.get_worker_roles.assert_not_called()
        assert result[0].roles == [UserRole.WORKER]
        assert result[1].roles == [UserRole.HOD]

    def test_get_active_workers_loads_roles_in_one_batch(self, service, mock_worker_repo):
        w1 = make_worker()
        mock_worker_repo.get_active_workers.return_value = [w1]
        mock_worker_repo.get_roles_for_workers.return_value = {}

        result = service.get_active_workers()

        mock_worker_repo.get_roles_for_workers.assert_called_once_with([w1.id])
        mock_worker_repo.get_worker_roles.assert_not_called()
        assert result[0].roles == []  # worker with no roles defaults to empty list

    def test_get_all_workers_forwards_limit_and_offset(self, service, mock_worker_repo):
        mock_worker_repo.get_all.return_value = []
        mock_worker_repo.get_roles_for_workers.return_value = {}

        service.get_all_workers(limit=5, offset=10)

        mock_worker_repo.get_all.assert_called_once_with(limit=5, offset=10)


class TestListVisibleWorkersPagination:
    def test_admin_unfiltered_listing_forwards_limit_and_offset(self, service, mock_worker_repo):
        mock_worker_repo.get_all.return_value = []
        mock_worker_repo.get_roles_for_workers.return_value = {}

        service.list_visible_workers(_token(role=UserRole.ADMIN), limit=5, offset=10)

        mock_worker_repo.get_all.assert_called_once_with(limit=5, offset=10)


def _csv(rows: str) -> bytes:
    """Build CSV bytes with the standard header plus the given data rows."""
    return f"first_name,last_name,email,phone\n{rows}".encode()


def _contact(worker) -> WorkerContactMatch:
    """Build the contact-index entry the repository would return for an existing worker."""
    return WorkerContactMatch(worker_id=worker.id, is_active=worker.is_active)


class TestImportWorkers:
    @pytest.fixture(autouse=True)
    def _department_exists(self, mock_department_repo):
        # Every import targets an existing department unless a test overrides this.
        mock_department_repo.get_by_id.return_value = make_department()

    @pytest.fixture(autouse=True)
    def _no_existing_workers(self, mock_worker_repo):
        # Empty contact index means nothing in the CSV collides with an existing worker.
        mock_worker_repo.get_contact_index.return_value = {}

    def test_creates_and_assigns_valid_rows(self, service, mock_worker_repo, mock_department_repo):
        dept_id = uuid4()
        created = [make_worker(email="a@example.com"), make_worker(email="b@example.com")]
        mock_worker_repo.create_many.return_value = created

        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111\nBob,Kim,b@example.com,+14165550112")
        result = service.import_workers(csv_bytes, dept_id, dry_run=False)

        assert result.ok is True
        assert result.total_rows == 2
        assert result.created == 2
        assert result.errors == 0
        assert all(r.status == "created" for r in result.results)
        assert [r.worker_id for r in result.results] == [w.id for w in created]
        # Two batched statements for the whole file, not two per row.
        mock_worker_repo.create_many.assert_called_once()
        mock_department_repo.assign_workers.assert_called_once_with(dept_id, [w.id for w in created])

    def test_reports_spreadsheet_line_numbers(self, service, mock_worker_repo):
        # The header is line 1, so the first data row must report as line 2 — otherwise the user is
        # sent to the wrong row of their spreadsheet.
        mock_worker_repo.create_many.return_value = [make_worker(email="a@example.com")]

        result = service.import_workers(_csv("Ann,Lee,a@example.com,+14165550111"), uuid4(), dry_run=True)

        assert result.results[0].line_number == 2

    def test_dry_run_performs_no_writes(self, service, mock_worker_repo, mock_department_repo):
        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=True)

        assert result.dry_run is True
        assert result.ok is True
        assert result.valid == 1
        assert result.created == 0
        assert result.results[0].status == "valid"
        mock_worker_repo.create_many.assert_not_called()
        mock_department_repo.assign_workers.assert_not_called()

    def test_normalizes_phone_numbers(self, service, mock_worker_repo):
        mock_worker_repo.create_many.return_value = [make_worker(email="a@example.com")]

        csv_bytes = _csv("Ann,Lee,a@example.com,(416) 555-0111")
        service.import_workers(csv_bytes, uuid4(), dry_run=False)

        saved = mock_worker_repo.create_many.call_args.args[0]
        assert saved[0]["phone"] == "+14165550111"

    def test_rejects_whole_file_on_one_invalid_email(self, service, mock_worker_repo, mock_department_repo):
        # All-or-nothing: the valid second row must not be created either.
        csv_bytes = _csv("Ann,Lee,banana,+14165550111\nBob,Kim,b@example.com,+14165550112")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=False)

        assert result.ok is False
        assert result.errors == 1
        assert result.results[0].status == "error"
        assert result.results[0].field == "email"
        assert result.results[0].value == "banana"
        assert result.results[1].status == "valid"
        mock_worker_repo.create_many.assert_not_called()
        mock_department_repo.assign_workers.assert_not_called()

    def test_rejects_whole_file_on_invalid_phone(self, service, mock_worker_repo):
        result = service.import_workers(_csv("Ann,Lee,a@example.com,555"), uuid4(), dry_run=False)

        assert result.ok is False
        assert result.results[0].status == "error"
        assert result.results[0].field == "phone"
        mock_worker_repo.create_many.assert_not_called()

    def test_reports_blank_cells_without_leaking_pydantic_text(self, service, mock_worker_repo):
        result = service.import_workers(_csv("Ann,Lee,,+14165550111"), uuid4(), dry_run=False)

        assert result.ok is False
        assert result.results[0].status == "error"
        assert result.results[0].error == "Missing value for: email"
        mock_worker_repo.create_many.assert_not_called()

    def test_matches_existing_worker_case_insensitively(self, service, mock_worker_repo):
        # Regression: workers.email is a case-sensitive unique index, so "A@example.com" against an
        # existing "a@example.com" used to sail past both checks and create a second profile.
        existing = make_worker(email="a@example.com")
        mock_worker_repo.get_contact_index.return_value = {"a@example.com": _contact(existing)}

        result = service.import_workers(_csv("Ann,Lee,A@example.com,+14165550111"), uuid4(), dry_run=False)

        assert result.ok is False
        assert result.duplicates == 1
        assert result.results[0].status == "duplicate"
        assert result.results[0].worker_id == existing.id
        mock_worker_repo.create_many.assert_not_called()

    def test_matches_existing_worker_by_phone(self, service, mock_worker_repo):
        existing = make_worker(email="other@example.com")
        mock_worker_repo.get_contact_index.return_value = {"+14165550111": _contact(existing)}

        result = service.import_workers(_csv("Ann,Lee,a@example.com,(416) 555-0111"), uuid4(), dry_run=False)

        assert result.duplicates == 1
        assert result.results[0].status == "duplicate"

    def test_flags_deactivated_worker_distinctly(self, service, mock_worker_repo):
        existing = make_worker(email="a@example.com", is_active=False)
        mock_worker_repo.get_contact_index.return_value = {"a@example.com": _contact(existing)}

        result = service.import_workers(_csv("Ann,Lee,a@example.com,+14165550111"), uuid4(), dry_run=True)

        assert result.ok is False
        assert result.duplicates_inactive == 1
        assert result.results[0].status == "duplicate_inactive"
        assert "reactivate" in (result.results[0].error or "")

    def test_skip_duplicates_imports_the_remainder(self, service, mock_worker_repo, mock_department_repo):
        existing = make_worker(email="a@example.com")
        mock_worker_repo.get_contact_index.return_value = {"a@example.com": _contact(existing)}
        fresh = make_worker(email="b@example.com")
        mock_worker_repo.create_many.return_value = [fresh]

        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111\nBob,Kim,b@example.com,+14165550112")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=False, skip_duplicates=True)

        assert result.ok is True
        assert result.created == 1
        assert result.duplicates == 1
        assert result.results[0].status == "duplicate"
        assert result.results[1].status == "created"
        assert len(mock_worker_repo.create_many.call_args.args[0]) == 1

    def test_skip_duplicates_does_not_override_validation_errors(self, service, mock_worker_repo):
        csv_bytes = _csv("Ann,Lee,banana,+14165550111\nBob,Kim,b@example.com,+14165550112")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=False, skip_duplicates=True)

        assert result.ok is False
        mock_worker_repo.create_many.assert_not_called()

    def test_duplicate_email_within_file_is_an_error(self, service, mock_worker_repo):
        # A repeat inside the file is the user's mistake to fix, not an already-imported worker, so
        # it blocks the import outright rather than being skippable.
        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111\nAnna,Lee,A@example.com,+14165550112")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=False, skip_duplicates=True)

        assert result.ok is False
        assert result.errors == 1
        assert result.results[1].status == "error"
        assert "line 2" in (result.results[1].error or "")
        mock_worker_repo.create_many.assert_not_called()

    def test_duplicate_phone_within_file_is_an_error(self, service, mock_worker_repo):
        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111\nBob,Kim,b@example.com,416-555-0111")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=False)

        assert result.ok is False
        assert result.results[1].status == "error"
        assert result.results[1].field == "phone"
        mock_worker_repo.create_many.assert_not_called()

    def test_rolls_back_created_workers_when_assignment_fails(self, service, mock_worker_repo, mock_department_repo):
        # The two halves are separate statements, so a failed assignment must not leave workers who
        # belong to no department — no HOD would ever see them.
        created = [make_worker(email="a@example.com")]
        mock_worker_repo.create_many.return_value = created
        mock_department_repo.assign_workers.side_effect = Exception("DB error")

        with pytest.raises(AppError, match="no changes were saved"):
            service.import_workers(_csv("Ann,Lee,a@example.com,+14165550111"), uuid4(), dry_run=False)

        mock_worker_repo.delete_many.assert_called_once_with([created[0].id])

    def test_raises_on_missing_required_column(self, service):
        csv_bytes = b"first_name,last_name,email\nAnn,Lee,a@example.com"
        with pytest.raises(BadRequestError, match="missing required column"):
            service.import_workers(csv_bytes, uuid4(), dry_run=False)

    def test_raises_when_header_has_no_rows(self, service):
        with pytest.raises(BadRequestError, match="no workers"):
            service.import_workers(b"first_name,last_name,email,phone\n", uuid4(), dry_run=False)

    def test_raises_when_file_exceeds_size_limit(self, service, monkeypatch):
        monkeypatch.setattr(settings, "max_import_file_bytes", 10)
        with pytest.raises(BadRequestError, match="too large"):
            service.import_workers(_csv("Ann,Lee,a@example.com,+14165550111"), uuid4(), dry_run=False)

    def test_raises_when_row_count_exceeds_limit(self, service, monkeypatch):
        monkeypatch.setattr(settings, "max_import_rows", 1)
        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111\nBob,Kim,b@example.com,+14165550112")
        with pytest.raises(BadRequestError, match="the limit is 1"):
            service.import_workers(csv_bytes, uuid4(), dry_run=False)

    def test_raises_when_department_not_found(self, service, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None
        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111")
        with pytest.raises(NotFoundError, match="not found"):
            service.import_workers(csv_bytes, uuid4(), dry_run=False)
