from datetime import date
from uuid import uuid4

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.schemas.models import AssignmentStatus, UserRole
from app.schemas.schedules.models import (
    DatePlan,
    DatePlanStatus,
    MonthlySchedulePreview,
    MonthlyScheduleResult,
    SkippedDate,
)
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
        mock_schedule_service.get_schedule.side_effect = NotFoundError("not found")
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
        mock_schedule_service.generate_schedule.side_effect = BadRequestError("No available workers")
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

    def test_returns_409_when_duplicate_schedule_exists(self, mock_schedule_service):
        mock_schedule_service.generate_schedule.side_effect = ConflictError(
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
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


class TestGetWorkerAssignments:
    def test_returns_200_for_a_worker_the_caller_may_view(self, mock_schedule_service, mock_worker_service):
        worker_id = uuid4()
        mock_schedule_service.get_worker_assignments.return_value = [make_assignment(worker_id=worker_id)]
        client = make_client(schedule_service=mock_schedule_service, worker_service=mock_worker_service)

        response = client.get(f"/api/v1/schedules/workers/{worker_id}/assignments")
        assert response.status_code == 200
        assert len(response.json()) == 1
        mock_worker_service.authorize_view_worker.assert_called_once()

    def test_returns_403_for_someone_elses_assignments(self, mock_schedule_service, mock_worker_service):
        # This endpoint took any logged-in user, so swapping the uuid in the path returned
        # anybody's whole assignment history.
        mock_worker_service.authorize_view_worker.side_effect = PermissionDeniedError("not yours")
        client = make_client(schedule_service=mock_schedule_service, worker_service=mock_worker_service)

        response = client.get(f"/api/v1/schedules/workers/{uuid4()}/assignments")
        assert response.status_code == 403
        mock_schedule_service.get_worker_assignments.assert_not_called()


class TestUpdateAssignmentStatus:
    # The endpoint now resolves the assignment first so it can authorize against its owner,
    # so get_assignment has to be stubbed alongside update_assignment_status.
    def test_returns_200_on_confirm(self, mock_schedule_service, mock_worker_service):
        assignment = make_assignment(status=AssignmentStatus.CONFIRMED)
        mock_schedule_service.get_assignment.return_value = assignment
        mock_schedule_service.update_assignment_status.return_value = assignment
        client = make_client(schedule_service=mock_schedule_service, worker_service=mock_worker_service)

        response = client.patch(
            f"/api/v1/schedules/assignments/{assignment.id}/status?status_update={AssignmentStatus.CONFIRMED.value}",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "confirmed"
        mock_worker_service.authorize_act_for_worker.assert_called_once()

    def test_returns_403_for_another_workers_assignment(self, mock_schedule_service, mock_worker_service):
        assignment = make_assignment()
        mock_schedule_service.get_assignment.return_value = assignment
        mock_worker_service.authorize_act_for_worker.side_effect = PermissionDeniedError("not yours")
        client = make_client(schedule_service=mock_schedule_service, worker_service=mock_worker_service)

        response = client.patch(
            f"/api/v1/schedules/assignments/{assignment.id}/status?status_update={AssignmentStatus.CONFIRMED.value}",
        )
        assert response.status_code == 403
        mock_schedule_service.update_assignment_status.assert_not_called()

    def test_returns_404_when_assignment_not_found(self, mock_schedule_service, mock_worker_service):
        mock_schedule_service.get_assignment.side_effect = NotFoundError("not found")
        client = make_client(schedule_service=mock_schedule_service, worker_service=mock_worker_service)

        response = client.patch(
            f"/api/v1/schedules/assignments/{uuid4()}/status?status_update={AssignmentStatus.CONFIRMED.value}",
        )
        assert response.status_code == 404


class TestUpdateAssignmentRole:
    def test_hod_can_set_role(self, mock_schedule_service):
        role_id = uuid4()
        assignment = make_assignment(department_role_id=role_id)
        mock_schedule_service.update_assignment_role.return_value = assignment
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)

        response = client.patch(
            f"/api/v1/schedules/assignments/{assignment.id}/role?department_role_id={role_id}",
        )
        assert response.status_code == 200
        mock_schedule_service.update_assignment_role.assert_called_once_with(assignment.id, role_id)

    def test_hod_can_clear_role(self, mock_schedule_service):
        assignment = make_assignment(department_role_id=None)
        mock_schedule_service.update_assignment_role.return_value = assignment
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)

        response = client.patch(f"/api/v1/schedules/assignments/{assignment.id}/role")
        assert response.status_code == 200
        mock_schedule_service.update_assignment_role.assert_called_once_with(assignment.id, None)

    def test_returns_400_when_role_in_different_department(self, mock_schedule_service):
        mock_schedule_service.update_assignment_role.side_effect = BadRequestError("does not belong")
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)

        response = client.patch(
            f"/api/v1/schedules/assignments/{uuid4()}/role?department_role_id={uuid4()}",
        )
        assert response.status_code == 400

    def test_returns_403_for_worker_role(self, mock_schedule_service):
        client = make_client(role=UserRole.WORKER, schedule_service=mock_schedule_service)
        response = client.patch(f"/api/v1/schedules/assignments/{uuid4()}/role?department_role_id={uuid4()}")
        assert response.status_code == 403


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


MONTH_PREVIEW_BODY = {
    "scope": "department_only",
    "title": "Sunday Service",
    "year": 2026,
    "month": 3,
    "days_of_week": ["sunday"],
    "start_time": "09:00:00",
    "end_time": "11:00:00",
    "reminder_days_before": 1,
}


class TestListSchedulesByDepartmentRange:
    def test_passes_date_range_to_service(self, mock_schedule_service):
        dept_id = uuid4()
        mock_schedule_service.get_schedules_by_department.return_value = []
        client = make_client(schedule_service=mock_schedule_service)

        response = client.get(
            f"/api/v1/schedules/departments/{dept_id}",
            params={"from": "2026-03-01", "to": "2026-03-31"},
        )

        assert response.status_code == 200
        mock_schedule_service.get_schedules_by_department.assert_called_once_with(
            dept_id, date(2026, 3, 1), date(2026, 3, 31)
        )

    def test_returns_422_for_a_malformed_date(self, mock_schedule_service):
        client = make_client(schedule_service=mock_schedule_service)
        response = client.get(f"/api/v1/schedules/departments/{uuid4()}", params={"from": "not-a-date"})
        assert response.status_code == 422


class TestPreviewMonthlySchedule:
    def test_returns_200_with_the_plan(self, mock_schedule_service):
        mock_schedule_service.preview_monthly_schedule.return_value = MonthlySchedulePreview(
            year=2026,
            month=3,
            workers_needed=2,
            dates=[
                DatePlan(scheduled_date=date(2026, 3, 1), status=DatePlanStatus.PLANNED),
                DatePlan(
                    scheduled_date=date(2026, 3, 8),
                    status=DatePlanStatus.SKIPPED_EXISTING,
                    message="A schedule already exists for this date.",
                ),
            ],
        )
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)

        response = client.post(
            "/api/v1/schedules/generate-month/preview",
            json={**MONTH_PREVIEW_BODY, "department_id": str(uuid4())},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["workers_needed"] == 2
        assert [d["status"] for d in body["dates"]] == ["planned", "skipped_existing"]

    def test_returns_403_for_worker_role(self, mock_schedule_service):
        client = make_client(role=UserRole.WORKER, schedule_service=mock_schedule_service)
        response = client.post(
            "/api/v1/schedules/generate-month/preview",
            json={**MONTH_PREVIEW_BODY, "department_id": str(uuid4())},
        )
        assert response.status_code == 403
        mock_schedule_service.preview_monthly_schedule.assert_not_called()

    def test_returns_422_when_no_weekdays_given(self, mock_schedule_service):
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)
        response = client.post(
            "/api/v1/schedules/generate-month/preview",
            json={**MONTH_PREVIEW_BODY, "department_id": str(uuid4()), "days_of_week": []},
        )
        assert response.status_code == 422

    def test_returns_422_when_end_time_precedes_start_time(self, mock_schedule_service):
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)
        response = client.post(
            "/api/v1/schedules/generate-month/preview",
            json={
                **MONTH_PREVIEW_BODY,
                "department_id": str(uuid4()),
                "start_time": "11:00:00",
                "end_time": "09:00:00",
            },
        )
        assert response.status_code == 422

    def test_returns_422_when_subteam_missing_for_subteam_scope(self, mock_schedule_service):
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)
        response = client.post(
            "/api/v1/schedules/generate-month/preview",
            json={**MONTH_PREVIEW_BODY, "department_id": str(uuid4()), "scope": "subteam"},
        )
        assert response.status_code == 422

    def test_returns_400_when_scope_has_no_workers(self, mock_schedule_service):
        mock_schedule_service.preview_monthly_schedule.side_effect = BadRequestError("No workers found")
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)

        response = client.post(
            "/api/v1/schedules/generate-month/preview",
            json={**MONTH_PREVIEW_BODY, "department_id": str(uuid4())},
        )
        assert response.status_code == 400


class TestGenerateMonthlySchedule:
    def _commit_body(self, worker_id=None):
        return {
            "department_id": str(uuid4()),
            "scope": "department_only",
            "title": "Sunday Service",
            "start_time": "09:00:00",
            "end_time": "11:00:00",
            "reminder_days_before": 1,
            "dates": [
                {"scheduled_date": "2026-03-01", "worker_ids": [str(worker_id or uuid4())]},
            ],
        }

    def test_returns_201_with_created_and_skipped(self, mock_schedule_service):
        mock_schedule_service.commit_monthly_schedule.return_value = MonthlyScheduleResult(
            created=[make_schedule(scheduled_date=date(2026, 3, 1))],
            skipped=[SkippedDate(scheduled_date=date(2026, 3, 8), reason="A schedule already exists for this date.")],
        )
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)

        response = client.post("/api/v1/schedules/generate-month", json=self._commit_body())

        assert response.status_code == 201
        body = response.json()
        assert len(body["created"]) == 1
        assert body["skipped"][0]["scheduled_date"] == "2026-03-08"

    def test_returns_403_for_worker_role(self, mock_schedule_service):
        client = make_client(role=UserRole.WORKER, schedule_service=mock_schedule_service)
        response = client.post("/api/v1/schedules/generate-month", json=self._commit_body())
        assert response.status_code == 403
        mock_schedule_service.commit_monthly_schedule.assert_not_called()

    def test_returns_409_when_every_date_exists(self, mock_schedule_service):
        mock_schedule_service.commit_monthly_schedule.side_effect = ConflictError("already has a schedule")
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)

        response = client.post("/api/v1/schedules/generate-month", json=self._commit_body())
        assert response.status_code == 409

    def test_returns_422_when_a_date_has_no_workers(self, mock_schedule_service):
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)
        body = self._commit_body()
        body["dates"][0]["worker_ids"] = []

        response = client.post("/api/v1/schedules/generate-month", json=body)
        assert response.status_code == 422

    def test_returns_422_for_duplicate_dates(self, mock_schedule_service):
        client = make_client(role=UserRole.HOD, schedule_service=mock_schedule_service)
        body = self._commit_body()
        body["dates"].append({"scheduled_date": "2026-03-01", "worker_ids": [str(uuid4())]})

        response = client.post("/api/v1/schedules/generate-month", json=body)
        assert response.status_code == 422
