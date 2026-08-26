from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.schedules.repository import ScheduleRepository


def _make_repo_with_mock_client() -> tuple[ScheduleRepository, MagicMock]:
    client = MagicMock()
    chain = client.table.return_value.select.return_value.eq.return_value.gte.return_value
    chain.order.return_value.execute.return_value.data = []
    return ScheduleRepository(client), client


class TestGetUpcomingAssignmentsForWorker:
    def test_selects_schedules_with_an_inner_join(self):
        """Without !inner PostgREST nulls the embedded schedule instead of dropping the row,
        which would make every past assignment look upcoming."""
        repo, client = _make_repo_with_mock_client()

        repo.get_upcoming_assignments_for_worker(uuid4(), date(2026, 8, 26))

        select_arg = client.table.return_value.select.call_args.args[0]
        assert "schedules!inner" in select_arg

    def test_filters_by_worker_and_scheduled_date(self):
        repo, client = _make_repo_with_mock_client()
        worker_id = uuid4()

        repo.get_upcoming_assignments_for_worker(worker_id, date(2026, 8, 26))

        select_chain = client.table.return_value.select.return_value
        assert select_chain.eq.call_args.args == ("worker_id", str(worker_id))
        # The date filter targets the joined table, so it must be dot-qualified.
        assert select_chain.eq.return_value.gte.call_args.args == (
            "schedules.scheduled_date",
            "2026-08-26",
        )

    def test_queries_the_assignments_table(self):
        repo, client = _make_repo_with_mock_client()

        repo.get_upcoming_assignments_for_worker(uuid4(), date(2026, 8, 26))

        assert client.table.call_args.args == ("schedule_assignments",)
