from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.worker_leave.repository import WorkerLeaveRepository

OPEN_OR_FROM = "end_date.gte.{},end_date.is.null"


def _make_repo() -> tuple[WorkerLeaveRepository, MagicMock]:
    builder = MagicMock()
    for method in ("select", "eq", "in_", "lte", "gte", "or_"):
        getattr(builder, method).return_value = builder
    builder.execute.return_value = MagicMock(data=[])
    client = MagicMock()
    client.table.return_value = builder
    return WorkerLeaveRepository(client), builder


class TestOpenEndedLeaveIsNeverDropped:
    """A NULL end_date is leave with no end yet. A bare `end_date >= x` drops those rows, so the
    people most certainly away would be rostered and texted again. Every service test mocks this
    repository and cannot see the filter, hence these."""

    def test_active_on(self):
        repo, builder = _make_repo()
        repo.get_active_on(date(2026, 10, 26))
        builder.or_.assert_called_once_with(OPEN_OR_FROM.format("2026-10-26"))
        builder.gte.assert_not_called()

    def test_for_workers(self):
        repo, builder = _make_repo()
        repo.get_for_workers([uuid4()], date(2026, 11, 1), date(2026, 11, 30))
        builder.or_.assert_called_once_with(OPEN_OR_FROM.format("2026-11-01"))
        builder.lte.assert_called_once_with("start_date", "2026-11-30")
        builder.gte.assert_not_called()

    def test_overlapping_with_an_open_ended_proposal_has_no_upper_bound(self):
        repo, builder = _make_repo()
        repo.get_overlapping(uuid4(), date(2026, 11, 1), None)
        builder.or_.assert_called_once_with(OPEN_OR_FROM.format("2026-11-01"))
        builder.lte.assert_not_called()

    def test_overlapping_with_a_bounded_proposal(self):
        repo, builder = _make_repo()
        repo.get_overlapping(uuid4(), date(2026, 11, 1), date(2026, 11, 8))
        builder.or_.assert_called_once_with(OPEN_OR_FROM.format("2026-11-01"))
        builder.lte.assert_called_once_with("start_date", "2026-11-08")
