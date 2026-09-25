from datetime import date
from uuid import uuid4

from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.models import DayOfWeek, UserRole
from app.schemas.special_services.models import SpecialDate, SpecialService, SpecialServiceKind
from tests.integration.routers.conftest import make_client


def make_rule(**kwargs) -> SpecialService:
    return SpecialService(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "Communion"),
        kind=SpecialServiceKind.RECURRING,
        day_of_week=kwargs.get("day_of_week", DayOfWeek.SUNDAY),
        week_of_month=kwargs.get("week_of_month", 1),
        is_active=kwargs.get("is_active", True),
        created_at="2026-01-01T08:00:00Z",
    )


def make_one_off(**kwargs) -> SpecialService:
    return SpecialService(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "Jesus is Lord Service"),
        kind=SpecialServiceKind.ONE_OFF,
        service_date=kwargs.get("service_date", date(2026, 8, 2)),
        is_active=True,
        created_at="2026-01-01T08:00:00Z",
    )


class TestListSpecialServices:
    def test_a_head_may_read_them(self, mock_special_service_service):
        # Heads need these: the month preview badges the special dates, and that is where a
        # head decides which dates to keep.
        mock_special_service_service.list_special_services.return_value = [make_rule(), make_one_off()]
        client = make_client(role=UserRole.HOD, special_service_service=mock_special_service_service)

        response = client.get("/api/v1/special-services")
        assert response.status_code == 200
        assert [s["kind"] for s in response.json()] == ["recurring", "one_off"]

    def test_a_rule_reports_its_day_by_name(self, mock_special_service_service):
        # The column holds 0-6 with Sunday as 0; the API speaks day names, and the
        # conversion happening at the schema boundary is what keeps the two apart.
        mock_special_service_service.list_special_services.return_value = [make_rule()]
        client = make_client(role=UserRole.HOD, special_service_service=mock_special_service_service)

        response = client.get("/api/v1/special-services")
        assert response.json()[0]["day_of_week"] == "sunday"

    def test_a_plain_worker_may_read_them_too(self, mock_special_service_service):
        mock_special_service_service.list_special_services.return_value = []
        client = make_client(role=UserRole.WORKER, special_service_service=mock_special_service_service)

        assert client.get("/api/v1/special-services").status_code == 200


class TestListSpecialDates:
    def test_resolves_a_window(self, mock_special_service_service):
        mock_special_service_service.list_special_dates.return_value = [
            SpecialDate(service_date=date(2026, 8, 2), name="Communion")
        ]
        client = make_client(role=UserRole.HOD, special_service_service=mock_special_service_service)

        response = client.get("/api/v1/special-services/dates?from=2026-08-01&to=2026-08-31")
        assert response.status_code == 200
        assert response.json() == [{"service_date": "2026-08-02", "name": "Communion"}]

    def test_the_dates_route_is_not_swallowed_by_the_uuid_route(self, mock_special_service_service):
        # "/dates" has to be declared before "/{special_service_id}", or it 422s saying
        # "dates" is not a valid UUID.
        mock_special_service_service.list_special_dates.return_value = []
        client = make_client(role=UserRole.HOD, special_service_service=mock_special_service_service)

        response = client.get("/api/v1/special-services/dates?from=2026-08-01&to=2026-08-31")
        assert response.status_code == 200, response.json()

    def test_rejects_an_inverted_window(self, mock_special_service_service):
        client = make_client(role=UserRole.HOD, special_service_service=mock_special_service_service)

        response = client.get("/api/v1/special-services/dates?from=2026-08-31&to=2026-08-01")
        assert response.status_code == 400
        mock_special_service_service.list_special_dates.assert_not_called()

    def test_rejects_a_window_longer_than_a_year(self, mock_special_service_service):
        # A typo should not turn pure arithmetic into a walk over centuries of months.
        client = make_client(role=UserRole.HOD, special_service_service=mock_special_service_service)

        response = client.get("/api/v1/special-services/dates?from=2026-01-01&to=2030-01-01")
        assert response.status_code == 400
        mock_special_service_service.list_special_dates.assert_not_called()


class TestCreateSpecialService:
    def _body(self, **kwargs) -> dict:
        return {
            "name": kwargs.get("name", "Communion"),
            "kind": kwargs.get("kind", "recurring"),
            "day_of_week": kwargs.get("day_of_week", "sunday"),
            "week_of_month": kwargs.get("week_of_month", 1),
            **({"service_date": kwargs["service_date"]} if "service_date" in kwargs else {}),
        }

    def test_an_admin_can_add_a_rule(self, mock_special_service_service):
        mock_special_service_service.create_special_service.return_value = make_rule()
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        response = client.post("/api/v1/special-services", json=self._body())
        assert response.status_code == 201
        assert response.json()["name"] == "Communion"

    def test_an_admin_can_add_a_one_off(self, mock_special_service_service):
        mock_special_service_service.create_special_service.return_value = make_one_off()
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        response = client.post(
            "/api/v1/special-services",
            json={
                "name": "Jesus is Lord Service",
                "kind": "one_off",
                "service_date": "2026-08-02",
            },
        )
        assert response.status_code == 201

    def test_a_head_of_department_is_refused(self, mock_special_service_service):
        # These rules are not scoped to a department: a head moving "first Sunday" would
        # change which dates every other team rotates specially.
        client = make_client(role=UserRole.HOD, special_service_service=mock_special_service_service)

        response = client.post("/api/v1/special-services", json=self._body())
        assert response.status_code == 403
        mock_special_service_service.create_special_service.assert_not_called()

    def test_rejects_a_recurring_rule_with_no_week(self, mock_special_service_service):
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        response = client.post(
            "/api/v1/special-services",
            json={"name": "Communion", "kind": "recurring", "day_of_week": "sunday"},
        )
        assert response.status_code == 422
        mock_special_service_service.create_special_service.assert_not_called()

    def test_rejects_a_one_off_carrying_a_rule_field(self, mock_special_service_service):
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        response = client.post(
            "/api/v1/special-services",
            json={
                "name": "Jesus is Lord Service",
                "kind": "one_off",
                "service_date": "2026-08-02",
                "week_of_month": 1,
            },
        )
        assert response.status_code == 422

    def test_accepts_the_last_of_the_month_sentinel(self, mock_special_service_service):
        mock_special_service_service.create_special_service.return_value = make_rule(week_of_month=-1)
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        response = client.post("/api/v1/special-services", json=self._body(week_of_month=-1))
        assert response.status_code == 201

    def test_rejects_a_week_of_zero(self, mock_special_service_service):
        # -1 is "the last"; 0 means nothing.
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        assert client.post("/api/v1/special-services", json=self._body(week_of_month=0)).status_code == 422

    def test_returns_409_when_the_same_rule_exists(self, mock_special_service_service):
        mock_special_service_service.create_special_service.side_effect = ConflictError("already set up")
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        assert client.post("/api/v1/special-services", json=self._body()).status_code == 409


class TestUpdateAndDelete:
    def test_an_admin_can_deactivate(self, mock_special_service_service):
        mock_special_service_service.update_special_service.return_value = make_rule(is_active=False)
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        response = client.patch(f"/api/v1/special-services/{uuid4()}", json={"is_active": False})
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_the_day_and_week_cannot_be_moved(self, mock_special_service_service):
        # Deliberately not in SpecialServiceUpdate. Rotas already generated were planned
        # against the date the rule resolved to then.
        mock_special_service_service.update_special_service.return_value = make_rule()
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        client.patch(f"/api/v1/special-services/{uuid4()}", json={"week_of_month": 3})
        changes = mock_special_service_service.update_special_service.call_args.args[1]
        assert not hasattr(changes, "week_of_month")

    def test_a_head_cannot_update(self, mock_special_service_service):
        client = make_client(role=UserRole.HOD, special_service_service=mock_special_service_service)

        response = client.patch(f"/api/v1/special-services/{uuid4()}", json={"name": "New"})
        assert response.status_code == 403
        mock_special_service_service.update_special_service.assert_not_called()

    def test_an_admin_can_delete(self, mock_special_service_service):
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        assert client.delete(f"/api/v1/special-services/{uuid4()}").status_code == 204

    def test_returns_404_for_an_unknown_id(self, mock_special_service_service):
        mock_special_service_service.delete_special_service.side_effect = NotFoundError("not found")
        client = make_client(role=UserRole.ADMIN, special_service_service=mock_special_service_service)

        assert client.delete(f"/api/v1/special-services/{uuid4()}").status_code == 404

    def test_a_head_cannot_delete(self, mock_special_service_service):
        client = make_client(role=UserRole.HOD, special_service_service=mock_special_service_service)

        assert client.delete(f"/api/v1/special-services/{uuid4()}").status_code == 403
        mock_special_service_service.delete_special_service.assert_not_called()
