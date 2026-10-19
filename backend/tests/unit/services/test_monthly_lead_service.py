from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, call
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.repository.monthly_leads.repository import MonthlyLeadRepository
from app.schemas.monthly_leads.models import MonthlyLeadResponse
from app.service.monthly_leads.service import MonthlyLeadService
from tests.unit.services.conftest import make_department

TITLE = "Teacher of the Month"
NOVEMBER = date(2026, 11, 1)


@pytest.fixture
def mock_lead_repo():
    repo = MagicMock(spec=MonthlyLeadRepository)
    repo.get_for_month.return_value = []
    return repo


@pytest.fixture
def service(mock_lead_repo, mock_department_repo):
    return MonthlyLeadService(lead_repo=mock_lead_repo, department_repo=mock_department_repo)


def _department(title=TITLE, members=(), inactive=()):
    """The department-with-members read, reduced to the fields set_leads looks at."""
    workers = [SimpleNamespace(id=i, is_active=True) for i in members]
    workers += [SimpleNamespace(id=i, is_active=False) for i in inactive]
    return SimpleNamespace(id=uuid4(), monthly_lead_title=title, workers=workers)


def _lead(worker_id):
    return MonthlyLeadResponse(
        id=uuid4(), department_id=uuid4(), worker_id=worker_id, month=NOVEMBER, created_at=datetime.now()
    )


class TestGetLeads:
    def test_returns_title_and_leads_for_the_month(self, service, mock_lead_repo, mock_department_repo):
        dept = make_department().model_copy(update={"monthly_lead_title": TITLE})
        mock_department_repo.get_by_id.return_value = dept

        result = service.get_leads(dept.id, date(2026, 11, 17))

        assert result.title == TITLE
        assert result.month == NOVEMBER
        mock_lead_repo.get_for_month.assert_called_once_with(dept.id, NOVEMBER)

    def test_department_without_a_title_reads_no_leads(self, service, mock_lead_repo, mock_department_repo):
        dept = make_department()
        mock_department_repo.get_by_id.return_value = dept

        result = service.get_leads(dept.id, NOVEMBER)

        assert result.title is None
        assert result.leads == []
        mock_lead_repo.get_for_month.assert_not_called()

    def test_raises_for_unknown_department(self, service, mock_department_repo):
        mock_department_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.get_leads(uuid4(), NOVEMBER)


class TestLeadIdsByMonth:
    def test_groups_lead_ids_by_month(self, service, mock_lead_repo, mock_department_repo):
        dept = make_department().model_copy(update={"monthly_lead_title": TITLE})
        mock_department_repo.get_by_id.return_value = dept
        a, b, c = uuid4(), uuid4(), uuid4()
        december = date(2026, 12, 1)
        mock_lead_repo.get_in_range.return_value = [
            _lead(a),
            _lead(b),
            _lead(c).model_copy(update={"month": december}),
        ]

        result = service.lead_ids_by_month(dept.id, date(2026, 11, 8), date(2026, 12, 27))

        assert result == {NOVEMBER: {a, b}, december: {c}}
        mock_lead_repo.get_in_range.assert_called_once_with(dept.id, NOVEMBER, december)

    def test_a_department_without_a_title_excludes_nobody(self, service, mock_lead_repo, mock_department_repo):
        # Turning the feature off must also stop it taking people off the rota.
        mock_department_repo.get_by_id.return_value = make_department()

        assert service.lead_ids_by_month(uuid4(), NOVEMBER, NOVEMBER) == {}
        mock_lead_repo.get_in_range.assert_not_called()


class TestSetLeads:
    @pytest.fixture(autouse=True)
    def _titled_department_for_the_reread(self, mock_department_repo):
        # set_leads re-reads the month through get_leads, which looks the department up by id.
        mock_department_repo.get_by_id.return_value = make_department().model_copy(update={"monthly_lead_title": TITLE})

    def test_adds_new_and_removes_dropped_names(self, service, mock_lead_repo, mock_department_repo):
        keep, drop, new = uuid4(), uuid4(), uuid4()
        dept = _department(members=[keep, drop, new])
        mock_department_repo.get_with_workers.return_value = dept
        mock_lead_repo.get_for_month.return_value = [_lead(keep), _lead(drop)]
        actor = uuid4()

        service.set_leads(dept.id, date(2026, 11, 9), [keep, new], actor)

        mock_lead_repo.add.assert_called_once_with(dept.id, NOVEMBER, [new], actor)
        mock_lead_repo.remove.assert_called_once_with(dept.id, NOVEMBER, [drop])

    def test_inserts_before_it_deletes(self, service, mock_lead_repo, mock_department_repo):
        old, new = uuid4(), uuid4()
        dept = _department(members=[old, new])
        mock_department_repo.get_with_workers.return_value = dept
        mock_lead_repo.get_for_month.return_value = [_lead(old)]

        service.set_leads(dept.id, NOVEMBER, [new], None)

        writes = [c for c in mock_lead_repo.mock_calls if c[0] in ("add", "remove")]
        assert writes == [
            call.add(dept.id, NOVEMBER, [new], None),
            call.remove(dept.id, NOVEMBER, [old]),
        ]

    def test_empty_list_clears_the_month(self, service, mock_lead_repo, mock_department_repo):
        a, b = uuid4(), uuid4()
        dept = _department(members=[a, b])
        mock_department_repo.get_with_workers.return_value = dept
        mock_lead_repo.get_for_month.return_value = [_lead(a), _lead(b)]

        service.set_leads(dept.id, NOVEMBER, [], None)

        mock_lead_repo.add.assert_called_once_with(dept.id, NOVEMBER, [], None)
        removed = mock_lead_repo.remove.call_args.args[2]
        assert set(removed) == {a, b}

    def test_duplicates_are_ignored(self, service, mock_lead_repo, mock_department_repo):
        a = uuid4()
        dept = _department(members=[a])
        mock_department_repo.get_with_workers.return_value = dept

        service.set_leads(dept.id, NOVEMBER, [a, a], None)

        mock_lead_repo.add.assert_called_once_with(dept.id, NOVEMBER, [a], None)

    def test_refuses_over_the_cap(self, service, mock_lead_repo, mock_department_repo):
        ids = [uuid4() for _ in range(4)]
        mock_department_repo.get_with_workers.return_value = _department(members=ids)

        with pytest.raises(BadRequestError, match="at most 3"):
            service.set_leads(uuid4(), NOVEMBER, ids, None)
        mock_lead_repo.add.assert_not_called()
        mock_lead_repo.remove.assert_not_called()

    def test_refuses_non_members_and_writes_nothing(self, service, mock_lead_repo, mock_department_repo):
        member, outsider = uuid4(), uuid4()
        mock_department_repo.get_with_workers.return_value = _department(members=[member])

        with pytest.raises(BadRequestError, match="not active members") as exc:
            service.set_leads(uuid4(), NOVEMBER, [member, outsider], None)
        assert str(outsider) in str(exc.value)
        assert str(member) not in str(exc.value)
        mock_lead_repo.add.assert_not_called()
        mock_lead_repo.remove.assert_not_called()

    def test_refuses_inactive_members(self, service, mock_lead_repo, mock_department_repo):
        inactive = uuid4()
        mock_department_repo.get_with_workers.return_value = _department(inactive=[inactive])

        with pytest.raises(BadRequestError, match="not active members"):
            service.set_leads(uuid4(), NOVEMBER, [inactive], None)
        mock_lead_repo.add.assert_not_called()

    def test_refuses_a_department_without_a_title(self, service, mock_lead_repo, mock_department_repo):
        a = uuid4()
        mock_department_repo.get_with_workers.return_value = _department(title=None, members=[a])

        with pytest.raises(BadRequestError, match="not have monthly leads turned on"):
            service.set_leads(uuid4(), NOVEMBER, [a], None)
        mock_lead_repo.add.assert_not_called()

    def test_raises_for_unknown_department(self, service, mock_department_repo):
        mock_department_repo.get_with_workers.return_value = None
        with pytest.raises(NotFoundError):
            service.set_leads(uuid4(), NOVEMBER, [], None)
