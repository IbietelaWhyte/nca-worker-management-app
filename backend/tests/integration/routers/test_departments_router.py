from uuid import uuid4

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.schemas.models import UserRole
from app.schemas.workers.models import WorkerImportResult, WorkerImportRowResult
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_department, make_subteam


class TestListDepartments:
    def test_returns_200_with_departments(self, mock_department_service):
        depts = [make_department(), make_department(name="Choir")]
        mock_department_service.get_all_departments.return_value = depts
        client = make_client(department_service=mock_department_service)

        response = client.get("/api/v1/departments")
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestListSubteams:
    def test_returns_200_with_subteams(self, mock_subteam_service):
        dept_id = uuid4()
        subteams = [
            make_subteam(department_id=dept_id, name="Toddlers"),
            make_subteam(department_id=dept_id, name="Juniors"),
        ]
        mock_subteam_service.get_subteams_by_department.return_value = subteams
        client = make_client(subteam_service=mock_subteam_service)

        response = client.get(f"/api/v1/departments/{dept_id}/subteams")
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestGetDepartment:
    def test_returns_200_when_found(self, mock_department_service):
        dept = make_department()
        mock_department_service.get_department.return_value = dept
        client = make_client(department_service=mock_department_service)

        response = client.get(f"/api/v1/departments/{dept.id}")
        assert response.status_code == 200
        assert response.json()["name"] == dept.name

    def test_returns_404_when_not_found(self, mock_department_service):
        mock_department_service.get_department.side_effect = NotFoundError("not found")
        client = make_client(department_service=mock_department_service)

        response = client.get(f"/api/v1/departments/{uuid4()}")
        assert response.status_code == 404


class TestCreateDepartment:
    def test_returns_201_when_created(self, mock_department_service):
        dept = make_department(name="Choir")
        mock_department_service.create_department.return_value = dept
        client = make_client(role=UserRole.ADMIN, department_service=mock_department_service)

        response = client.post("/api/v1/departments", json={"name": "Choir", "workers_per_slot": 2})
        assert response.status_code == 201
        assert response.json()["name"] == "Choir"

    def test_returns_409_on_duplicate_name(self, mock_department_service):
        mock_department_service.create_department.side_effect = ConflictError("already exists")
        client = make_client(role=UserRole.ADMIN, department_service=mock_department_service)

        response = client.post("/api/v1/departments", json={"name": "Choir"})
        assert response.status_code == 409

    def test_returns_403_for_non_admin(self, mock_department_service):
        client = make_client(role=UserRole.WORKER, department_service=mock_department_service)
        response = client.post("/api/v1/departments", json={"name": "Choir"})
        assert response.status_code == 403


class TestAssignWorker:
    def test_returns_200_on_assign(self, mock_department_service):
        dept = make_department()
        worker_id = uuid4()
        mock_department_service.get_department.return_value = dept
        client = make_client(role=UserRole.HOD, department_service=mock_department_service)

        response = client.post(f"/api/v1/departments/{dept.id}/workers/{worker_id}")
        assert response.status_code == 200

    def test_returns_403_for_worker_role(self, mock_department_service):
        client = make_client(role=UserRole.WORKER, department_service=mock_department_service)
        response = client.post(f"/api/v1/departments/{uuid4()}/workers/{uuid4()}")
        assert response.status_code == 403


class TestSetHod:
    def test_returns_200_on_set(self, mock_department_service):
        dept = make_department()
        worker_id = uuid4()
        updated = make_department(hod_id=worker_id)
        mock_department_service.set_hod.return_value = updated
        client = make_client(role=UserRole.ADMIN, department_service=mock_department_service)

        response = client.patch(f"/api/v1/departments/{dept.id}/hod/{worker_id}")
        assert response.status_code == 200
        assert response.json()["hod_id"] == str(worker_id)

    def test_returns_403_for_hod_role(self, mock_department_service):
        client = make_client(role=UserRole.HOD, department_service=mock_department_service)
        response = client.patch(f"/api/v1/departments/{uuid4()}/hod/{uuid4()}")
        assert response.status_code == 403


def _csv_upload(rows: str = "Ann,Lee,a@example.com,+14165550111"):
    content = f"first_name,last_name,email,phone\n{rows}".encode()
    return {"file": ("workers.csv", content, "text/csv")}


def _result(**kwargs) -> WorkerImportResult:
    """Build a WorkerImportResult, defaulting every count so tests only state what they assert on."""
    results = kwargs.get("results", [])
    return WorkerImportResult(
        dry_run=kwargs.get("dry_run", False),
        ok=kwargs.get("ok", True),
        total_rows=kwargs.get("total_rows", len(results)),
        valid=kwargs.get("valid", 0),
        created=kwargs.get("created", 0),
        duplicates=kwargs.get("duplicates", 0),
        duplicates_inactive=kwargs.get("duplicates_inactive", 0),
        errors=kwargs.get("errors", 0),
        results=results,
    )


class TestImportWorkers:
    def test_returns_403_for_worker_role(self, mock_worker_service):
        client = make_client(role=UserRole.WORKER, worker_service=mock_worker_service)
        response = client.post(f"/api/v1/departments/{uuid4()}/workers/import", files=_csv_upload())
        assert response.status_code == 403
        mock_worker_service.import_workers.assert_not_called()

    def test_dry_run_previews_without_writing(self, mock_worker_service):
        dept_id = uuid4()
        mock_worker_service.import_workers.return_value = _result(
            dry_run=True,
            ok=True,
            valid=1,
            results=[WorkerImportRowResult(line_number=2, status="valid", name="Ann Lee", email="a@example.com")],
        )
        client = make_client(role=UserRole.HOD, worker_service=mock_worker_service)

        response = client.post(f"/api/v1/departments/{dept_id}/workers/import?dry_run=true", files=_csv_upload())
        assert response.status_code == 200
        body = response.json()
        assert body["dry_run"] is True
        assert body["ok"] is True
        assert body["valid"] == 1
        _, kwargs = mock_worker_service.import_workers.call_args
        assert kwargs["dry_run"] is True
        assert kwargs["skip_duplicates"] is False

    def test_commit_imports_and_reports(self, mock_worker_service):
        dept_id = uuid4()
        mock_worker_service.import_workers.return_value = _result(
            ok=True,
            created=1,
            results=[
                WorkerImportRowResult(
                    line_number=2, status="created", name="Ann Lee", email="a@example.com", worker_id=uuid4()
                )
            ],
        )
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.post(f"/api/v1/departments/{dept_id}/workers/import", files=_csv_upload())
        assert response.status_code == 200
        assert response.json()["created"] == 1

    def test_forwards_skip_duplicates(self, mock_worker_service):
        mock_worker_service.import_workers.return_value = _result(ok=True, created=1)
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.post(
            f"/api/v1/departments/{uuid4()}/workers/import?skip_duplicates=true", files=_csv_upload()
        )
        assert response.status_code == 200
        _, kwargs = mock_worker_service.import_workers.call_args
        assert kwargs["skip_duplicates"] is True

    def test_returns_200_with_ok_false_when_rejected(self, mock_worker_service):
        # A rejected file is a report, not an error status — the per-row detail is the payload.
        mock_worker_service.import_workers.return_value = _result(
            dry_run=True,
            ok=False,
            errors=1,
            results=[
                WorkerImportRowResult(
                    line_number=2,
                    status="error",
                    name="Ann Lee",
                    email="banana",
                    field="email",
                    value="banana",
                    error="'banana' is not a valid email address",
                )
            ],
        )
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.post(f"/api/v1/departments/{uuid4()}/workers/import?dry_run=true", files=_csv_upload())
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["results"][0]["field"] == "email"
        assert body["results"][0]["line_number"] == 2

    def test_returns_400_when_file_is_not_a_valid_csv(self, mock_worker_service):
        mock_worker_service.import_workers.side_effect = BadRequestError("CSV is missing required column(s): phone")
        client = make_client(role=UserRole.ADMIN, worker_service=mock_worker_service)

        response = client.post(f"/api/v1/departments/{uuid4()}/workers/import", files=_csv_upload())
        assert response.status_code == 400
        assert "missing required column" in response.json()["detail"]

    def test_returns_403_when_hod_does_not_manage_department(self, mock_worker_service):
        mock_worker_service.authorize_create_assignment.side_effect = PermissionDeniedError("nope")
        client = make_client(role=UserRole.HOD, worker_service=mock_worker_service)

        response = client.post(f"/api/v1/departments/{uuid4()}/workers/import", files=_csv_upload())
        assert response.status_code == 403
        mock_worker_service.import_workers.assert_not_called()
