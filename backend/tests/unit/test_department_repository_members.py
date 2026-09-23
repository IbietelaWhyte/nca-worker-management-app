from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.departments.repository import DepartmentRepository


def _make_repo(worker_rows: list[dict]) -> tuple[DepartmentRepository, MagicMock]:
    """A repository whose get_with_workers query returns the given junction rows."""
    client = MagicMock()
    chain = client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    chain.execute.return_value.data = {
        "id": str(uuid4()),
        "name": "Children's Ministry",
        "description": None,
        "hod_id": None,
        "min_workers_per_slot": 2,
        "max_workers_per_slot": 4,
        "created_at": "2026-01-01T08:00:00Z",
        "workers": worker_rows,
    }
    return DepartmentRepository(client), client


def _worker(**kwargs) -> dict:
    return {
        "id": str(kwargs.get("id", uuid4())),
        "first_name": kwargs.get("first_name", "Ada"),
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "phone": "+14165550101",
        "is_active": True,
        "created_at": "2026-01-01T08:00:00Z",
    }


def _subteam(name: str) -> dict:
    return {
        "id": str(uuid4()),
        "department_id": str(uuid4()),
        "name": name,
        "description": None,
        "min_workers_per_slot": None,
        "max_workers_per_slot": None,
        "created_at": "2026-01-01T08:00:00Z",
    }


class TestGetWithWorkers:
    """The junction carries the membership facts, and the flatten is what surfaces them."""

    def test_asks_for_the_subteam_on_the_junction(self):
        # Without it, nothing that lists a department's members can say where each one sits —
        # and putting somebody in a subteam UPDATES this row, so it moves them out of whichever
        # one they were in. A picker that cannot show that cannot warn about it.
        repo, client = _make_repo([])

        repo.get_with_workers(uuid4())

        assert "subteams(*)" in client.table.return_value.select.call_args.args[0]

    def test_attaches_each_members_subteam(self):
        seekers = _subteam("Seekers")
        repo, _ = _make_repo([{"workers": _worker(), "department_roles": None, "subteams": seekers}])

        department = repo.get_with_workers(uuid4())

        assert department is not None
        assert department.workers[0].subteam is not None
        assert department.workers[0].subteam.name == "Seekers"

    def test_a_member_in_no_subteam_reads_as_none(self):
        # Not an anomaly: department-only members are exactly who a DEPARTMENT_ONLY rota staffs.
        repo, _ = _make_repo([{"workers": _worker(), "department_roles": None, "subteams": None}])

        department = repo.get_with_workers(uuid4())

        assert department is not None
        assert department.workers[0].subteam is None

    def test_the_role_still_comes_through_beside_it(self):
        role = {"id": str(uuid4()), "department_id": str(uuid4()), "name": "Head Usher", "description": None}
        repo, _ = _make_repo([{"workers": _worker(), "department_roles": role, "subteams": _subteam("Seekers")}])

        department = repo.get_with_workers(uuid4())

        assert department is not None
        assert department.workers[0].department_role is not None
        assert department.workers[0].department_role.name == "Head Usher"
        assert department.workers[0].subteam is not None
