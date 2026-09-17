from datetime import date, datetime, timedelta
from uuid import uuid4

from app.core.exceptions import ConflictError
from app.schemas.models import UserRole
from app.schemas.worker_leave.models import (
    CurrentLeave,
    LeaveClash,
    LeaveClashReport,
    WorkerLeaveResponse,
)
from tests.integration.routers.conftest import make_client

TODAY = date.today()


def make_leave(**kwargs) -> WorkerLeaveResponse:
    return WorkerLeaveResponse(
        id=kwargs.get("id", uuid4()),
        worker_id=kwargs.get("worker_id", uuid4()),
        start_date=kwargs.get("start_date", TODAY),
        end_date=kwargs.get("end_date", TODAY + timedelta(days=7)),
        reason=kwargs.get("reason", None),
        created_by=kwargs.get("created_by", None),
        created_at=kwargs.get("created_at", datetime.now()),
    )


def leave_client(leave_service, worker_service, role=UserRole.HOD):
    return make_client(role=role, worker_leave_service=leave_service, worker_service=worker_service)


class TestAuthorization:
    def test_a_plain_worker_cannot_set_leave(self, mock_worker_leave_service, mock_worker_service):
        # Leave is agreed with a head, not self-declared — that is what /availability is for.
        # A worker reaching this endpoint is stopped by the role guard before any scope check.
        client = leave_client(mock_worker_leave_service, mock_worker_service, role=UserRole.WORKER)

        response = client.post(
            f"/api/v1/leave/workers/{uuid4()}",
            json={"start_date": TODAY.isoformat(), "end_date": (TODAY + timedelta(days=7)).isoformat()},
        )
        assert response.status_code == 403
        mock_worker_leave_service.create_leave.assert_not_called()

    def test_a_plain_worker_cannot_list_who_is_away(self, mock_worker_leave_service, mock_worker_service):
        client = leave_client(mock_worker_leave_service, mock_worker_service, role=UserRole.WORKER)
        assert client.get("/api/v1/leave/current").status_code == 403

    def test_a_head_is_still_scoped_to_their_own_departments(self, mock_worker_leave_service, mock_worker_service):
        # The role guard lets any head through; authorize_manage_worker is what narrows it.
        mock_worker_leave_service.create_leave.return_value = make_leave()
        client = leave_client(mock_worker_leave_service, mock_worker_service)
        client.post(
            f"/api/v1/leave/workers/{uuid4()}",
            json={"start_date": TODAY.isoformat(), "end_date": (TODAY + timedelta(days=7)).isoformat()},
        )
        mock_worker_service.authorize_manage_worker.assert_called_once()


class TestCreateLeave:
    def test_returns_201_with_the_stored_leave(self, mock_worker_leave_service, mock_worker_service):
        worker_id = uuid4()
        mock_worker_leave_service.create_leave.return_value = make_leave(worker_id=worker_id)
        client = leave_client(mock_worker_leave_service, mock_worker_service)

        response = client.post(
            f"/api/v1/leave/workers/{worker_id}",
            json={
                "start_date": TODAY.isoformat(),
                "end_date": (TODAY + timedelta(days=7)).isoformat(),
                "reason": "Travelling",
            },
        )
        assert response.status_code == 201
        assert response.json()["worker_id"] == str(worker_id)

    def test_a_backwards_range_is_a_422(self, mock_worker_leave_service, mock_worker_service):
        client = leave_client(mock_worker_leave_service, mock_worker_service)
        response = client.post(
            f"/api/v1/leave/workers/{uuid4()}",
            json={"start_date": (TODAY + timedelta(days=7)).isoformat(), "end_date": TODAY.isoformat()},
        )
        assert response.status_code == 422
        mock_worker_leave_service.create_leave.assert_not_called()

    def test_an_overlap_is_a_409(self, mock_worker_leave_service, mock_worker_service):
        mock_worker_leave_service.create_leave.side_effect = ConflictError("This overlaps leave already recorded")
        client = leave_client(mock_worker_leave_service, mock_worker_service)

        response = client.post(
            f"/api/v1/leave/workers/{uuid4()}",
            json={"start_date": TODAY.isoformat(), "end_date": (TODAY + timedelta(days=7)).isoformat()},
        )
        assert response.status_code == 409
        assert "overlaps" in response.json()["detail"]


class TestClashes:
    def test_returns_the_duties_that_fall_inside_the_window(self, mock_worker_leave_service, mock_worker_service):
        mock_worker_leave_service.get_clashes.return_value = LeaveClashReport(
            clashes=[
                LeaveClash(schedule_id=uuid4(), scheduled_date=TODAY + timedelta(days=3), department_name="Ushering")
            ]
        )
        client = leave_client(mock_worker_leave_service, mock_worker_service)

        response = client.get(
            f"/api/v1/leave/workers/{uuid4()}/clashes",
            params={"start_date": TODAY.isoformat(), "end_date": (TODAY + timedelta(days=7)).isoformat()},
        )
        assert response.status_code == 200
        assert response.json()["clashes"][0]["department_name"] == "Ushering"


class TestCurrentLeave:
    def test_lists_who_is_away(self, mock_worker_leave_service, mock_worker_service):
        worker_id = uuid4()
        mock_worker_leave_service.get_current_leave.return_value = [
            CurrentLeave(worker_id=worker_id, start_date=TODAY, end_date=TODAY + timedelta(days=3))
        ]
        client = leave_client(mock_worker_leave_service, mock_worker_service)

        response = client.get("/api/v1/leave/current")
        assert response.status_code == 200
        assert response.json()[0]["worker_id"] == str(worker_id)

    def test_current_is_not_parsed_as_a_leave_id(self, mock_worker_leave_service, mock_worker_service):
        # It shares a prefix with DELETE /{leave_id}; "current" is not a UUID.
        mock_worker_leave_service.get_current_leave.return_value = []
        client = leave_client(mock_worker_leave_service, mock_worker_service)
        assert client.get("/api/v1/leave/current").status_code == 200


class TestDeleteLeave:
    def test_returns_204(self, mock_worker_leave_service, mock_worker_service):
        leave_id = uuid4()
        mock_worker_leave_service.get_owner_id.return_value = uuid4()
        client = leave_client(mock_worker_leave_service, mock_worker_service)

        response = client.delete(f"/api/v1/leave/{leave_id}")
        assert response.status_code == 204
        mock_worker_leave_service.delete_leave.assert_called_once_with(leave_id)

    def test_the_owner_is_resolved_before_the_scope_check(self, mock_worker_leave_service, mock_worker_service):
        # The URL names a leave, not a worker, so there is nothing to check against until the
        # owner is looked up.
        owner_id = uuid4()
        mock_worker_leave_service.get_owner_id.return_value = owner_id
        client = leave_client(mock_worker_leave_service, mock_worker_service)

        client.delete(f"/api/v1/leave/{uuid4()}")
        assert mock_worker_service.authorize_manage_worker.call_args.args[1] == owner_id
