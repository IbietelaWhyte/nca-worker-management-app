from datetime import date
from uuid import uuid4

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.schemas.models import UserRole
from app.schemas.schedules.models import (
    AssignableWorker,
    DatePlan,
    DatePlanStatus,
    MonthlySchedulePreview,
    MonthlyScheduleResult,
    ScheduleEditResult,
    SkippedDate,
)
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_assignment, make_schedule, make_subteam, make_worker


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
                "reminder_days_before": [1],
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
                "reminder_days_before": [1],
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
                "reminder_days_before": [1],
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
                "reminder_days_before": [1],
            },
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


class TestReminderLeadTimes:
    """The ladder is set once, at generation, so the request body is the only place to guard it."""

    def _generate(self, service, lead_times):
        client = make_client(role=UserRole.HOD, schedule_service=service)
        return client.post(
            "/api/v1/schedules/generate",
            json={
                "department_id": str(uuid4()),
                "scope": "department_only",
                "title": "Sunday Service",
                "scheduled_date": "2026-03-15",
                "start_time": "09:00:00",
                "end_time": "11:00:00",
                "reminder_days_before": lead_times,
            },
        )

    def test_accepts_a_ladder(self, mock_schedule_service):
        mock_schedule_service.generate_schedule.return_value = make_schedule()
        assert self._generate(mock_schedule_service, [7, 3, 1]).status_code == 201
        assert mock_schedule_service.generate_schedule.call_args.args[0].reminder_days_before == [7, 3, 1]

    def test_accepts_no_reminders_at_all(self, mock_schedule_service):
        # A real choice for a team that works off the printed rota. Forcing one reminder would
        # spend their money for them, and the notice still goes out either way.
        mock_schedule_service.generate_schedule.return_value = make_schedule()
        assert self._generate(mock_schedule_service, []).status_code == 201
        assert mock_schedule_service.generate_schedule.call_args.args[0].reminder_days_before == []

    def test_orders_the_ladder_furthest_out_first(self, mock_schedule_service):
        mock_schedule_service.generate_schedule.return_value = make_schedule()
        self._generate(mock_schedule_service, [1, 7, 3])
        assert mock_schedule_service.generate_schedule.call_args.args[0].reminder_days_before == [7, 3, 1]

    def test_collapses_a_repeated_lead_time_rather_than_refusing_it(self, mock_schedule_service):
        # A slip, not an error worth a 422 — and the send table's primary key would make the
        # second text a no-op anyway.
        mock_schedule_service.generate_schedule.return_value = make_schedule()
        assert self._generate(mock_schedule_service, [3, 3, 1]).status_code == 201
        assert mock_schedule_service.generate_schedule.call_args.args[0].reminder_days_before == [3, 1]

    def test_rejects_a_negative_lead_time(self, mock_schedule_service):
        assert self._generate(mock_schedule_service, [-1]).status_code == 422
        mock_schedule_service.generate_schedule.assert_not_called()

    def test_rejects_more_lead_times_than_a_phone_bill_can_bear(self, mock_schedule_service):
        assert self._generate(mock_schedule_service, [1, 2, 3, 4, 5, 6]).status_code == 422
        mock_schedule_service.generate_schedule.assert_not_called()


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
    "reminder_days_before": [1],
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
            min_workers=2,
            max_workers=4,
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
        assert (body["min_workers"], body["max_workers"]) == (2, 4)
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
            "reminder_days_before": [1],
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


def _edit_result(schedule=None, warnings=None) -> ScheduleEditResult:
    """What every edit endpoint returns: the whole re-read schedule, plus any warnings."""
    return ScheduleEditResult(schedule=schedule or make_schedule(), warnings=warnings or [])


class TestListAssignableWorkers:
    def test_returns_candidates_with_their_subteam(self, mock_schedule_service, mock_worker_service):
        subteam = make_subteam(name="Seekers")
        worker = make_worker(first_name="Ada", last_name="Lovelace")
        mock_schedule_service.get_schedule.return_value = make_schedule()
        mock_schedule_service.get_assignable_workers.return_value = [AssignableWorker(worker=worker, subteam=subteam)]
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.get(f"/api/v1/schedules/{uuid4()}/assignable-workers")
        assert response.status_code == 200
        body = response.json()
        assert body[0]["worker"]["first_name"] == "Ada"
        assert body[0]["subteam"]["name"] == "Seekers"

    def test_a_department_only_candidate_has_no_subteam(self, mock_schedule_service, mock_worker_service):
        mock_schedule_service.get_schedule.return_value = make_schedule()
        mock_schedule_service.get_assignable_workers.return_value = [
            AssignableWorker(worker=make_worker(), subteam=None)
        ]
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.get(f"/api/v1/schedules/{uuid4()}/assignable-workers")
        assert response.status_code == 200
        assert response.json()[0]["subteam"] is None

    def test_returns_403_for_worker_role(self, mock_schedule_service, mock_worker_service):
        # A department's roster minus whoever is serving is not something a plain worker
        # should be able to enumerate.
        client = make_client(
            role=UserRole.WORKER, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )
        response = client.get(f"/api/v1/schedules/{uuid4()}/assignable-workers")
        assert response.status_code == 403
        mock_schedule_service.get_assignable_workers.assert_not_called()

    def test_returns_403_when_the_head_does_not_manage_the_department(self, mock_schedule_service, mock_worker_service):
        mock_schedule_service.get_schedule.return_value = make_schedule()
        mock_worker_service.authorize_create_assignment.side_effect = PermissionDeniedError("not yours")
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.get(f"/api/v1/schedules/{uuid4()}/assignable-workers")
        assert response.status_code == 403
        mock_schedule_service.get_assignable_workers.assert_not_called()


class TestAddAssignment:
    def test_returns_201_with_the_whole_schedule(self, mock_schedule_service, mock_worker_service):
        schedule = make_schedule()
        mock_schedule_service.get_schedule.return_value = schedule
        mock_schedule_service.add_assignment.return_value = _edit_result(schedule)
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )
        worker_id = uuid4()

        response = client.post(f"/api/v1/schedules/{schedule.id}/assignments", json={"worker_id": str(worker_id)})
        assert response.status_code == 201
        assert response.json()["schedule"]["id"] == str(schedule.id)
        mock_schedule_service.add_assignment.assert_called_once_with(schedule.id, worker_id)

    def test_returns_200_with_warnings_when_the_worker_clashes(self, mock_schedule_service, mock_worker_service):
        # Allowed, and the head is told. The clash is reported, never enforced.
        schedule = make_schedule()
        mock_schedule_service.get_schedule.return_value = schedule
        mock_schedule_service.add_assignment.return_value = _edit_result(
            schedule, ["Ada Lovelace is already on another rota on 2 August."]
        )
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.post(f"/api/v1/schedules/{schedule.id}/assignments", json={"worker_id": str(uuid4())})
        assert response.status_code == 201
        assert "already on another rota" in response.json()["warnings"][0]

    def test_returns_409_when_the_rota_is_full(self, mock_schedule_service, mock_worker_service):
        mock_schedule_service.get_schedule.return_value = make_schedule()
        mock_schedule_service.add_assignment.side_effect = ConflictError("already at its maximum of 4")
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.post(f"/api/v1/schedules/{uuid4()}/assignments", json={"worker_id": str(uuid4())})
        assert response.status_code == 409

    def test_returns_400_when_the_worker_is_not_a_member(self, mock_schedule_service, mock_worker_service):
        mock_schedule_service.get_schedule.return_value = make_schedule()
        mock_schedule_service.add_assignment.side_effect = BadRequestError("is not an active member")
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.post(f"/api/v1/schedules/{uuid4()}/assignments", json={"worker_id": str(uuid4())})
        assert response.status_code == 400

    def test_returns_403_for_worker_role(self, mock_schedule_service, mock_worker_service):
        client = make_client(
            role=UserRole.WORKER, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )
        response = client.post(f"/api/v1/schedules/{uuid4()}/assignments", json={"worker_id": str(uuid4())})
        assert response.status_code == 403
        mock_schedule_service.add_assignment.assert_not_called()

    def test_returns_403_when_the_head_does_not_manage_the_department(self, mock_schedule_service, mock_worker_service):
        mock_schedule_service.get_schedule.return_value = make_schedule()
        mock_worker_service.authorize_create_assignment.side_effect = PermissionDeniedError("not yours")
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.post(f"/api/v1/schedules/{uuid4()}/assignments", json={"worker_id": str(uuid4())})
        assert response.status_code == 403
        mock_schedule_service.add_assignment.assert_not_called()


class TestReplaceAssignmentWorker:
    def test_returns_200_and_forwards_both_ids(self, mock_schedule_service, mock_worker_service):
        assignment = make_assignment()
        mock_schedule_service.get_assignment.return_value = assignment
        mock_schedule_service.get_schedule.return_value = make_schedule()
        mock_schedule_service.replace_assignment_worker.return_value = _edit_result()
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )
        worker_id = uuid4()

        response = client.patch(
            f"/api/v1/schedules/assignments/{assignment.id}/worker", json={"worker_id": str(worker_id)}
        )
        assert response.status_code == 200
        mock_schedule_service.replace_assignment_worker.assert_called_once_with(assignment.id, worker_id)

    def test_returns_404_for_an_unknown_assignment(self, mock_schedule_service, mock_worker_service):
        mock_schedule_service.get_assignment.side_effect = NotFoundError("not found")
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.patch(f"/api/v1/schedules/assignments/{uuid4()}/worker", json={"worker_id": str(uuid4())})
        assert response.status_code == 404

    def test_returns_403_for_worker_role(self, mock_schedule_service, mock_worker_service):
        client = make_client(
            role=UserRole.WORKER, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )
        response = client.patch(f"/api/v1/schedules/assignments/{uuid4()}/worker", json={"worker_id": str(uuid4())})
        assert response.status_code == 403
        mock_schedule_service.replace_assignment_worker.assert_not_called()


class TestRemoveAssignment:
    def test_the_assignment_route_is_declared_before_the_schedule_route(
        self, mock_schedule_service, mock_worker_service
    ):
        # THE route-order guard. DELETE /schedules/assignments/{id} has to be declared ahead of
        # DELETE /schedules/{schedule_id}; the other way round, "assignments" is parsed as a
        # schedule uuid and every removal comes back 422 with nothing in the logs to explain it.
        assignment = make_assignment()
        mock_schedule_service.get_assignment.return_value = assignment
        mock_schedule_service.get_schedule.return_value = make_schedule()
        mock_schedule_service.remove_assignment.return_value = _edit_result()
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.delete(f"/api/v1/schedules/assignments/{assignment.id}")
        assert response.status_code == 200, response.json()
        mock_schedule_service.remove_assignment.assert_called_once_with(assignment.id)
        mock_schedule_service.delete_schedule.assert_not_called()

    def test_returns_the_warning_when_the_rota_drops_below_its_minimum(
        self, mock_schedule_service, mock_worker_service
    ):
        mock_schedule_service.get_assignment.return_value = make_assignment()
        mock_schedule_service.get_schedule.return_value = make_schedule()
        mock_schedule_service.remove_assignment.return_value = _edit_result(
            warnings=["This rota is now 1 short of the 2 it was planned for."]
        )
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )

        response = client.delete(f"/api/v1/schedules/assignments/{uuid4()}")
        assert response.status_code == 200
        assert "1 short of the 2" in response.json()["warnings"][0]

    def test_deleting_a_schedule_still_works(self, mock_schedule_service, mock_worker_service):
        # The other half of the ordering guard: the uuid route must not have been shadowed.
        client = make_client(
            role=UserRole.HOD, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )
        schedule_id = uuid4()

        response = client.delete(f"/api/v1/schedules/{schedule_id}")
        assert response.status_code == 204
        mock_schedule_service.delete_schedule.assert_called_once_with(schedule_id)
        mock_schedule_service.remove_assignment.assert_not_called()

    def test_returns_403_for_worker_role(self, mock_schedule_service, mock_worker_service):
        client = make_client(
            role=UserRole.WORKER, schedule_service=mock_schedule_service, worker_service=mock_worker_service
        )
        response = client.delete(f"/api/v1/schedules/assignments/{uuid4()}")
        assert response.status_code == 403
        mock_schedule_service.remove_assignment.assert_not_called()
