"""Endpoint behaviour for the attendance router.

The hardest requirement in the feature is negative: **a worker cannot record attendance.** Every
route is parametrised over that below, so a sixth route added later without the gate fails here
rather than in production.
"""

from datetime import date
from uuid import uuid4

import pytest

from app.core.exceptions import PermissionDeniedError
from app.schemas.attendance.models import AbsenceReport, RollCallCount
from app.schemas.models import UserRole
from app.schemas.schedules.models import RollCallResult
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_schedule

ASSIGNMENT_ID = uuid4()
SCHEDULE_ID = uuid4()
DEPARTMENT_ID = uuid4()

# (method, path) for every write. The report is a read and is listed separately below, because it
# is the one route whose department comes from the URL rather than from a lookup.
WRITE_ROUTES = [
    ("post", f"/api/v1/attendance/assignments/{ASSIGNMENT_ID}/check-in"),
    ("delete", f"/api/v1/attendance/assignments/{ASSIGNMENT_ID}/check-in"),
    ("patch", f"/api/v1/attendance/assignments/{ASSIGNMENT_ID}/excused"),
    ("post", f"/api/v1/attendance/schedules/{SCHEDULE_ID}/close"),
    ("post", f"/api/v1/attendance/schedules/{SCHEDULE_ID}/reopen"),
]
ALL_ROUTES = WRITE_ROUTES + [
    ("get", f"/api/v1/attendance/departments/{DEPARTMENT_ID}/report?from=2026-03-01&to=2026-03-31")
]


def roll_call_result() -> RollCallResult:
    return RollCallResult(
        schedule=make_schedule(id=SCHEDULE_ID, department_id=DEPARTMENT_ID),
        counts=RollCallCount(assigned=0, present=0, late=0, absent=0, excused=0, not_recorded=0),
    )


def absence_report() -> AbsenceReport:
    return AbsenceReport(
        department_id=DEPARTMENT_ID,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        services=0,
        services_with_roll_call=0,
        window_days=90,
        repeat_threshold=2,
    )


def stub(service):
    service.department_for_assignment.return_value = DEPARTMENT_ID
    service.department_for_schedule.return_value = DEPARTMENT_ID
    service.check_in.return_value = roll_call_result()
    service.undo_check_in.return_value = roll_call_result()
    service.set_excused.return_value = roll_call_result()
    service.close_roll_call.return_value = roll_call_result()
    service.reopen_roll_call.return_value = roll_call_result()
    service.get_report.return_value = absence_report()
    return service


def call(client, method, path):
    """Fire the request. Only the PATCH carries a body; GET and DELETE take none."""
    kwargs = {"json": {"excused": True}} if method == "patch" else {}
    return getattr(client, method)(path, **kwargs)


class TestAWorkerCannotRecordAttendance:
    """The feature's hardest requirement, one test per route."""

    @pytest.mark.parametrize(("method", "path"), ALL_ROUTES)
    def test_a_worker_is_refused(self, method, path, mock_attendance_service, mock_worker_service):
        client = make_client(
            role=UserRole.WORKER,
            attendance_service=stub(mock_attendance_service),
            worker_service=mock_worker_service,
        )

        response = call(client, method, path)

        assert response.status_code == 403

    @pytest.mark.parametrize(("method", "path"), ALL_ROUTES)
    def test_the_service_is_never_reached(self, method, path, mock_attendance_service, mock_worker_service):
        # Refused by the dependency before any work happens, so a worker cannot even probe which
        # assignment ids exist.
        client = make_client(
            role=UserRole.WORKER,
            attendance_service=stub(mock_attendance_service),
            worker_service=mock_worker_service,
        )

        call(client, method, path)

        mock_attendance_service.check_in.assert_not_called()
        mock_attendance_service.close_roll_call.assert_not_called()
        mock_attendance_service.get_report.assert_not_called()


class TestAHeadIsScopedToTheirOwnDepartments:
    @pytest.mark.parametrize(("method", "path"), ALL_ROUTES)
    def test_another_department_is_refused(self, method, path, mock_attendance_service, mock_worker_service):
        # HODUser alone would let a head of Ushering close the Choir's roll call. Every route has
        # to call the fine gate as well; this is what proves each one does.
        mock_worker_service.authorize_record_attendance.side_effect = PermissionDeniedError(
            "You can only record attendance for departments you manage"
        )
        client = make_client(
            role=UserRole.HOD,
            attendance_service=stub(mock_attendance_service),
            worker_service=mock_worker_service,
        )

        response = call(client, method, path)

        assert response.status_code == 403
        mock_worker_service.authorize_record_attendance.assert_called_once()


class TestAHeadCanRecordAttendance:
    def test_check_in_returns_the_rota_and_its_tally(self, mock_attendance_service, mock_worker_service):
        client = make_client(
            role=UserRole.HOD,
            attendance_service=stub(mock_attendance_service),
            worker_service=mock_worker_service,
        )

        response = client.post(f"/api/v1/attendance/assignments/{ASSIGNMENT_ID}/check-in")

        assert response.status_code == 200
        assert response.json()["counts"]["assigned"] == 0
        mock_attendance_service.check_in.assert_called_once()

    def test_closing_the_roll_call_is_allowed(self, mock_attendance_service, mock_worker_service):
        client = make_client(
            role=UserRole.HOD,
            attendance_service=stub(mock_attendance_service),
            worker_service=mock_worker_service,
        )

        response = client.post(f"/api/v1/attendance/schedules/{SCHEDULE_ID}/close")

        assert response.status_code == 200
        mock_attendance_service.close_roll_call.assert_called_once()

    def test_an_assistant_head_may_record_attendance(self, mock_attendance_service, mock_worker_service):
        # Assistant HODs run services too, and HODUser already admits them.
        client = make_client(
            role=UserRole.ASSISTANT_HOD,
            attendance_service=stub(mock_attendance_service),
            worker_service=mock_worker_service,
        )

        response = client.post(f"/api/v1/attendance/assignments/{ASSIGNMENT_ID}/check-in")

        assert response.status_code == 200

    def test_an_admin_may_record_attendance_anywhere(self, mock_attendance_service, mock_worker_service):
        client = make_client(
            role=UserRole.ADMIN,
            attendance_service=stub(mock_attendance_service),
            worker_service=mock_worker_service,
        )

        response = client.post(f"/api/v1/attendance/schedules/{SCHEDULE_ID}/reopen")

        assert response.status_code == 200

    def test_the_report_takes_its_window_from_the_query(self, mock_attendance_service, mock_worker_service):
        client = make_client(
            role=UserRole.HOD,
            attendance_service=stub(mock_attendance_service),
            worker_service=mock_worker_service,
        )

        response = client.get(f"/api/v1/attendance/departments/{DEPARTMENT_ID}/report?from=2026-03-01&to=2026-03-31")

        assert response.status_code == 200
        assert mock_attendance_service.get_report.call_args.args[1:] == (date(2026, 3, 1), date(2026, 3, 31))


class TestRouteShape:
    def test_no_route_here_can_be_swallowed_by_a_uuid_segment(self):
        # Every path leads with a literal ("assignments", "schedules", "departments") and this
        # router declares no bare /{id} route, so the trap that governs the schedules router
        # cannot bite. A /{id} route added later must be declared last.
        from app.router.attendance.router import router

        # Paths carry the router's own /attendance prefix, so compare the segment after it.
        after_prefix = {route.path.removeprefix("/attendance").strip("/").split("/")[0] for route in router.routes}
        assert after_prefix == {"assignments", "schedules", "departments"}
        assert not any(route.path.removeprefix("/attendance").startswith("/{") for route in router.routes)
