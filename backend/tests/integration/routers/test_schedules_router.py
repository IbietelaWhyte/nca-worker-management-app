from uuid import uuid4

from app.schemas.models import AssignmentStatus, UserRole
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_assignment, make_schedule


class TestListSchedulesByDepartment:
    def test_returns_200_with_schedules(self, mock_schedule_service):
        dept_id = uuid4()
        schedules = [make_schedule(department_id=dept_id)]
        mock_schedule_service.get_schedules_by_department.return_value = schedules
        client = make_client(schedule_service=mock_schedule_service)

        response = client.get(f"/api/v1/schedules/departments/{dept_id}")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestGetSchedule:
    def test_returns_200_when_found(self, mock_schedule_service):
        schedule = make_schedule()
        mock_schedule_service.get_schedule.return_value = schedule
        client = make_client(schedule_service=mock_schedule_service)

        response = client.get(f"/api/v1/schedules/{schedule.id}")
        assert response.status_code == 200

    def test_returns_404_when_not_found(self, mock_schedule_service):
        mock_schedule_service.get_schedule.side_effect = ValueError("not found")
        client = make_client(schedule_service=mock_schedule_service)

        response = client.get(f"/api/v1/schedules/{uuid4()}")
        assert response.status_code == 404


class TestGenerateSchedule:
    def test_returns_201_when_generated(self, mock_schedule_service):
        schedule = make_schedule()
        mock_schedule_service.generate_schedule.return_value = schedule
        client = make_client(
            role=UserRole.HOD,
            schedule_service=mock_schedule_service,
        )

        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "department_id": str(uuid4()),
                "scope": "department_only",
                "title": "Sunday Service",
                "scheduled_date": "2026-03-15",
                "start_time": "09:00:00",
                "end_time": "11:00:00",
                "reminder_days_before": 1,
            },
        )
        assert response.status_code == 201

    def test_returns_400_when_no_available_workers(self, mock_schedule_service):
        mock_schedule_service.generate_schedule.side_effect = ValueError("No available workers")
        client = make_client(
            role=UserRole.HOD,
            schedule_service=mock_schedule_service,
        )

        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "department_id": str(uuid4()),
                "scope": "department_all",
                "title": "Sunday Service",
                "scheduled_date": "2026-03-15",
                "start_time": "09:00:00",
                "end_time": "11:00:00",
                "reminder_days_before": 1,
            },
        )
        assert response.status_code == 400

    def test_returns_403_for_worker_role(self, mock_schedule_service):
        client = make_client(
            role=UserRole.WORKER,
            schedule_service=mock_schedule_service,
        )
        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "department_id": str(uuid4()),
                "scope": "subteam",
                "subteam_id": str(uuid4()),
                "title": "Sunday Service",
                "scheduled_date": "2026-03-15",
                "start_time": "09:00:00",
                "end_time": "11:00:00",
                "reminder_days_before": 1,
            },
        )
        assert response.status_code == 403

    def test_returns_400_when_duplicate_schedule_exists(self, mock_schedule_service):
        mock_schedule_service.generate_schedule.side_effect = ValueError(
            "A schedule already exists for this department on 2026-03-15"
        )
        client = make_client(
            role=UserRole.HOD,
            schedule_service=mock_schedule_service,
        )

        response = client.post(
            "/api/v1/schedules/generate",
            json={
                "department_id": str(uuid4()),
                "scope": "department_only",
                "title": "Sunday Service",
                "scheduled_date": "2026-03-15",
                "start_time": "09:00:00",
                "end_time": "11:00:00",
                "reminder_days_before": 1,
            },
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


class TestUpdateAssignmentStatus:
    def test_returns_200_on_confirm(self, mock_schedule_service):
        assignment = make_assignment(status=AssignmentStatus.CONFIRMED)
        mock_schedule_service.update_assignment_status.return_value = assignment
        client = make_client(schedule_service=mock_schedule_service)

        response = client.patch(
            f"/api/v1/schedules/assignments/{assignment.id}/status?status_update={AssignmentStatus.CONFIRMED.value}",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "confirmed"

    def test_returns_404_when_assignment_not_found(self, mock_schedule_service):
        mock_schedule_service.update_assignment_status.side_effect = ValueError("not found")
        client = make_client(schedule_service=mock_schedule_service)

        response = client.patch(
            f"/api/v1/schedules/assignments/{uuid4()}/status?status_update={AssignmentStatus.CONFIRMED.value}",
        )
        assert response.status_code == 404


class TestTriggerReminders:
    def test_returns_200_with_sent_count(self, mock_reminder_service):
        mock_reminder_service.trigger_manually.return_value = 5
        client = make_client(
            role=UserRole.HOD,
            reminder_service=mock_reminder_service,
        )

        response = client.post("/api/v1/schedules/reminders/trigger")
        assert response.status_code == 200
        assert "5" in response.json()["message"]

    def test_returns_403_for_worker_role(self, mock_reminder_service):
        client = make_client(
            role=UserRole.WORKER,
            reminder_service=mock_reminder_service,
        )
        response = client.post("/api/v1/schedules/reminders/trigger")
        assert response.status_code == 403
