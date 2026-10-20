from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, NotFoundError, PermissionDeniedError
from app.schemas.models import UserRole
from app.schemas.monthly_leads.models import MonthlyLeadsResponse
from app.service.monthly_leads.service import MonthlyLeadService
from tests.integration.routers.conftest import make_client
from tests.unit.services.conftest import make_worker


@pytest.fixture
def mock_lead_service():
    service = MagicMock(spec=MonthlyLeadService)
    response = MonthlyLeadsResponse(title="Teacher of the Month", month=date(2026, 11, 1), leads=[])
    service.get_leads.return_value = response
    service.set_leads.return_value = response
    return service


class TestGetMonthlyLeads:
    def test_a_head_of_the_department_can_read(self, mock_lead_service):
        dept_id = uuid4()
        client = make_client(role=UserRole.HOD, monthly_lead_service=mock_lead_service)

        response = client.get(f"/api/v1/departments/{dept_id}/monthly-leads", params={"month": "2026-11-17"})

        assert response.status_code == 200
        assert response.json()["title"] == "Teacher of the Month"
        mock_lead_service.get_leads.assert_called_once_with(dept_id, date(2026, 11, 17))

    def test_a_plain_worker_cannot_read(self, mock_lead_service):
        # Each lead embeds the worker's phone and email; the names are only shown to heads.
        client = make_client(role=UserRole.WORKER, monthly_lead_service=mock_lead_service)
        response = client.get(f"/api/v1/departments/{uuid4()}/monthly-leads", params={"month": "2026-11-01"})
        assert response.status_code == 403
        mock_lead_service.get_leads.assert_not_called()

    def test_a_head_of_another_department_cannot_read(self, mock_lead_service, mock_worker_service):
        mock_worker_service.authorize_create_assignment.side_effect = PermissionDeniedError("not yours")
        client = make_client(
            role=UserRole.HOD, worker_service=mock_worker_service, monthly_lead_service=mock_lead_service
        )
        response = client.get(f"/api/v1/departments/{uuid4()}/monthly-leads", params={"month": "2026-11-01"})
        assert response.status_code == 403
        mock_lead_service.get_leads.assert_not_called()

    def test_requires_a_month(self, mock_lead_service):
        client = make_client(role=UserRole.HOD, monthly_lead_service=mock_lead_service)
        response = client.get(f"/api/v1/departments/{uuid4()}/monthly-leads")
        assert response.status_code == 422

    def test_returns_404_for_unknown_department(self, mock_lead_service):
        mock_lead_service.get_leads.side_effect = NotFoundError("Department not found")
        client = make_client(role=UserRole.HOD, monthly_lead_service=mock_lead_service)
        response = client.get(f"/api/v1/departments/{uuid4()}/monthly-leads", params={"month": "2026-11-01"})
        assert response.status_code == 404


class TestSetMonthlyLeads:
    def _body(self, *worker_ids, month="2026-11-20"):
        return {"month": month, "worker_ids": [str(w) for w in worker_ids]}

    def test_hod_sets_leads_normalised_to_the_first(self, mock_lead_service, mock_worker_service):
        dept_id, worker_id = uuid4(), uuid4()
        actor = make_worker()
        mock_worker_service.get_worker_for_token.return_value = actor
        client = make_client(
            role=UserRole.HOD, worker_service=mock_worker_service, monthly_lead_service=mock_lead_service
        )

        response = client.put(f"/api/v1/departments/{dept_id}/monthly-leads", json=self._body(worker_id))

        assert response.status_code == 200
        mock_worker_service.authorize_create_assignment.assert_called_once()
        mock_lead_service.set_leads.assert_called_once_with(dept_id, date(2026, 11, 1), [worker_id], actor.id)

    def test_admin_is_recorded_as_nobody(self, mock_lead_service, mock_worker_service):
        dept_id = uuid4()
        client = make_client(
            role=UserRole.ADMIN, worker_service=mock_worker_service, monthly_lead_service=mock_lead_service
        )

        response = client.put(f"/api/v1/departments/{dept_id}/monthly-leads", json=self._body())

        assert response.status_code == 200
        mock_worker_service.get_worker_for_token.assert_not_called()
        mock_lead_service.set_leads.assert_called_once_with(dept_id, date(2026, 11, 1), [], None)

    def test_returns_403_for_worker_role(self, mock_lead_service, mock_worker_service):
        client = make_client(
            role=UserRole.WORKER, worker_service=mock_worker_service, monthly_lead_service=mock_lead_service
        )
        response = client.put(f"/api/v1/departments/{uuid4()}/monthly-leads", json=self._body())
        assert response.status_code == 403
        mock_lead_service.set_leads.assert_not_called()

    def test_returns_403_for_head_of_another_department(self, mock_lead_service, mock_worker_service):
        mock_worker_service.authorize_create_assignment.side_effect = PermissionDeniedError("not yours")
        client = make_client(
            role=UserRole.HOD, worker_service=mock_worker_service, monthly_lead_service=mock_lead_service
        )
        response = client.put(f"/api/v1/departments/{uuid4()}/monthly-leads", json=self._body())
        assert response.status_code == 403
        mock_lead_service.set_leads.assert_not_called()

    def test_returns_400_from_the_service(self, mock_lead_service, mock_worker_service):
        mock_lead_service.set_leads.side_effect = BadRequestError("You can name at most 3 people for a month")
        client = make_client(
            role=UserRole.ADMIN, worker_service=mock_worker_service, monthly_lead_service=mock_lead_service
        )
        response = client.put(f"/api/v1/departments/{uuid4()}/monthly-leads", json=self._body(uuid4()))
        assert response.status_code == 400
        assert "at most 3" in response.json()["detail"]
