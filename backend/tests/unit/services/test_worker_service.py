from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.schemas.models import TokenPayload, UserRole
from app.schemas.workers.models import WorkerCreate, WorkerUpdate
from app.service.workers.service import WorkerService
from tests.unit.services.conftest import make_department, make_worker


def _token(role: UserRole = UserRole.HOD, email: str | None = "manager@example.com") -> TokenPayload:
    return TokenPayload(sub="sub-123", role=role, email=email)


@pytest.fixture
def service(mock_worker_repo, mock_department_repo, mock_supabase_client):
    return WorkerService(
        worker_repo=mock_worker_repo,
        department_repo=mock_department_repo,
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


class TestImportWorkers:
    @pytest.fixture(autouse=True)
    def _department_exists(self, mock_department_repo):
        # Every import targets an existing department unless a test overrides this.
        mock_department_repo.get_by_id.return_value = make_department()

    def test_creates_and_assigns_valid_rows(self, service, mock_worker_repo, mock_department_repo):
        dept_id = uuid4()
        mock_worker_repo.get_by_email.return_value = None
        mock_worker_repo.create.side_effect = [
            make_worker(email="a@example.com"),
            make_worker(email="b@example.com"),
        ]

        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111\nBob,Kim,b@example.com,+14165550112")
        result = service.import_workers(csv_bytes, dept_id, dry_run=False)

        assert result.total_rows == 2
        assert result.created == 2
        assert result.skipped_duplicate == 0
        assert result.errors == 0
        assert all(r.status == "created" for r in result.results)
        assert mock_worker_repo.create.call_count == 2
        assert mock_department_repo.assign_worker.call_count == 2

    def test_dry_run_performs_no_writes(self, service, mock_worker_repo, mock_department_repo):
        mock_worker_repo.get_by_email.return_value = None

        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=True)

        assert result.dry_run is True
        assert result.valid == 1
        assert result.created == 0
        assert result.results[0].status == "valid"
        mock_worker_repo.create.assert_not_called()
        mock_department_repo.assign_worker.assert_not_called()

    def test_skips_existing_worker_in_db(self, service, mock_worker_repo):
        mock_worker_repo.get_by_email.return_value = make_worker(email="a@example.com")

        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=False)

        assert result.skipped_duplicate == 1
        assert result.created == 0
        assert result.results[0].status == "skipped_duplicate"
        mock_worker_repo.create.assert_not_called()

    def test_skips_duplicate_email_within_file(self, service, mock_worker_repo):
        mock_worker_repo.get_by_email.return_value = None
        mock_worker_repo.create.return_value = make_worker(email="a@example.com")

        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111\nAnna,Lee,A@example.com,+14165550112")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=False)

        assert result.created == 1
        assert result.skipped_duplicate == 1
        assert result.results[1].status == "skipped_duplicate"
        # Email match is case-insensitive, so the DB is only checked for the first occurrence.
        mock_worker_repo.get_by_email.assert_called_once()

    def test_reports_invalid_row_but_processes_others(self, service, mock_worker_repo):
        mock_worker_repo.get_by_email.return_value = None
        mock_worker_repo.create.return_value = make_worker(email="b@example.com")

        # First row is missing the email cell; second row is valid.
        csv_bytes = _csv("Ann,Lee,,+14165550111\nBob,Kim,b@example.com,+14165550112")
        result = service.import_workers(csv_bytes, uuid4(), dry_run=False)

        assert result.errors == 1
        assert result.created == 1
        assert result.results[0].status == "error"
        assert result.results[1].status == "created"

    def test_raises_on_missing_required_column(self, service):
        csv_bytes = b"first_name,last_name,email\nAnn,Lee,a@example.com"
        with pytest.raises(BadRequestError, match="missing required column"):
            service.import_workers(csv_bytes, uuid4(), dry_run=False)

    def test_raises_when_department_not_found(self, service, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None
        csv_bytes = _csv("Ann,Lee,a@example.com,+14165550111")
        with pytest.raises(NotFoundError, match="not found"):
            service.import_workers(csv_bytes, uuid4(), dry_run=False)
