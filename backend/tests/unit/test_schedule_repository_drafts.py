from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.schedules.repository import ScheduleRepository
from app.schemas.schedules.models import ScheduleStatus


def _builder() -> MagicMock:
    builder = MagicMock()
    for method in ("select", "eq", "in_", "gte", "lte", "is_", "order", "update"):
        getattr(builder, method).return_value = builder
    builder.not_ = builder
    builder.execute.return_value = MagicMock(data=[])
    return builder


def _repo(builder: MagicMock) -> ScheduleRepository:
    client = MagicMock()
    client.table.return_value = builder
    return ScheduleRepository(client)


class TestDraftsStayOutOfWorkerReads:
    """Every service test mocks the repository and cannot see these strings, hence these."""

    def test_a_workers_own_duties_hide_drafts(self):
        builder = _builder()
        _repo(builder).get_assignments_for_worker(uuid4())

        # Inner, or the filter would only blank the embed and leave the draft assignment behind.
        assert "schedules!inner(" in builder.select.call_args.args[0]
        builder.is_.assert_called_once_with("schedules.finalized_at", "null")

    def test_the_attendance_report_counts_finalized_rotas_only(self):
        builder = _builder()
        _repo(builder).get_for_attendance_report(uuid4(), date(2026, 3, 1), date(2026, 3, 31))
        builder.is_.assert_called_once_with("finalized_at", "null")


class TestStatusFilter:
    def test_drafts(self):
        builder = _builder()
        _repo(builder).get_by_department(uuid4(), status=ScheduleStatus.DRAFT)
        builder.is_.assert_called_once_with("finalized_at", "null")
        # Three FKs from schedules to workers: an unnamed embed is PGRST201 on every drafts read.
        assert "creator:workers!created_by(first_name,last_name)" in builder.select.call_args.args[0]

    def test_both_when_no_status_is_given(self):
        # The generators' "is this date taken" check: a draft occupies its date.
        builder = _builder()
        _repo(builder).get_by_department(uuid4())
        builder.is_.assert_not_called()

    def test_finalize_only_touches_drafts(self):
        builder = _builder()
        _repo(builder).finalize([uuid4()], None)
        # A second finalize must not move the original stamp.
        builder.is_.assert_called_once_with("finalized_at", "null")
        assert builder.update.call_args.args[0]["finalized_by"] is None
