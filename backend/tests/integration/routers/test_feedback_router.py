from app.core.exceptions import TooManyRequestsError
from app.schemas.feedback.models import FeedbackResponse
from app.schemas.models import UserRole
from tests.integration.routers.conftest import make_client

VALID = {
    "kind": "bug",
    "title": "Availability will not save",
    "details": "I tap the 12th and it goes red but when I come back it is gone again.",
}


class TestSubmitFeedback:
    def test_a_worker_may_report(self, mock_feedback_service):
        mock_feedback_service.submit.return_value = FeedbackResponse(reference=12)
        client = make_client(role=UserRole.WORKER, feedback_service=mock_feedback_service)

        response = client.post("/api/v1/feedback", json=VALID)
        assert response.status_code == 201
        assert response.json()["reference"] == 12

    def test_forwards_the_browser_context(self, mock_feedback_service):
        mock_feedback_service.submit.return_value = FeedbackResponse(reference=1)
        client = make_client(role=UserRole.WORKER, feedback_service=mock_feedback_service)

        client.post("/api/v1/feedback", json={**VALID, "page": "/availability", "viewport": "393x852"})
        _, data = mock_feedback_service.submit.call_args.args
        assert data.page == "/availability"
        assert data.viewport == "393x852"

    def test_rejects_a_report_too_short_to_act_on(self, mock_feedback_service):
        client = make_client(role=UserRole.WORKER, feedback_service=mock_feedback_service)

        response = client.post("/api/v1/feedback", json={**VALID, "details": "broken"})
        assert response.status_code == 422
        mock_feedback_service.submit.assert_not_called()

    def test_rejects_a_title_of_whitespace(self, mock_feedback_service):
        client = make_client(role=UserRole.WORKER, feedback_service=mock_feedback_service)

        response = client.post("/api/v1/feedback", json={**VALID, "title": "   "})
        assert response.status_code == 422

    def test_rejects_an_unknown_kind(self, mock_feedback_service):
        client = make_client(role=UserRole.WORKER, feedback_service=mock_feedback_service)

        response = client.post("/api/v1/feedback", json={**VALID, "kind": "complaint"})
        assert response.status_code == 422

    def test_a_rate_limited_worker_gets_429(self, mock_feedback_service):
        mock_feedback_service.submit.side_effect = TooManyRequestsError("Please try again later.")
        client = make_client(role=UserRole.WORKER, feedback_service=mock_feedback_service)

        response = client.post("/api/v1/feedback", json=VALID)
        assert response.status_code == 429
        assert "try again" in response.json()["detail"].lower()


class TestFeedbackConfig:
    def test_reports_enabled_when_credentials_are_present(self, mock_feedback_service):
        mock_feedback_service.is_enabled = True
        client = make_client(role=UserRole.WORKER, feedback_service=mock_feedback_service)

        response = client.get("/api/v1/feedback/config")
        assert response.status_code == 200
        assert response.json() == {"enabled": True}

    def test_reports_disabled_without_them(self, mock_feedback_service):
        mock_feedback_service.is_enabled = False
        client = make_client(role=UserRole.WORKER, feedback_service=mock_feedback_service)

        assert client.get("/api/v1/feedback/config").json() == {"enabled": False}
