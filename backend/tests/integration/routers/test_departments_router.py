from uuid import uuid4

from app.schemas.models import UserRole
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
        mock_department_service.get_department.side_effect = ValueError("not found")
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
        mock_department_service.create_department.side_effect = ValueError("already exists")
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
