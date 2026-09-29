"""Repository-level guards for attendance.

Two things here that no service test can see: the exact shape of the PostgREST select strings,
and that reassigning a seat takes its attendance record with it.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import app.repository.schedules.queries as q
from app.repository.schedules.repository import ScheduleRepository


class TestWorkerEmbedsNameTheirColumn:
    """`checked_in_by` made a SECOND foreign key from schedule_assignments to workers.

    PostgREST then refuses an ambiguous `workers(*)` outright with PGRST201 rather than degrading
    quietly, so a bare embed does not return slightly wrong data - it fails every read of every
    schedule, including ones that have nothing to do with attendance. These assertions are the
    drift guard, because the service tests all mock the repository and cannot see it.
    """

    def test_every_assignment_rooted_select_disambiguates_workers(self):
        for name in (
            "SELECT_WITH_ASSIGNMENTS",
            "SELECT_ASSIGNMENT_WITH_RELATIONS",
            "SELECT_ASSIGNMENT_WITH_SCHEDULE_AND_WORKER",
            "SELECT_FOR_ATTENDANCE_REPORT",
        ):
            select = getattr(q, name)
            assert "workers!worker_id(*)" in select, f"{name} embeds workers ambiguously"

    def test_no_assignment_select_carries_a_bare_workers_embed(self):
        for name in (
            "SELECT_WITH_ASSIGNMENTS",
            "SELECT_ASSIGNMENT_WITH_RELATIONS",
            "SELECT_ASSIGNMENT_WITH_SCHEDULE_AND_WORKER",
            "SELECT_FOR_ATTENDANCE_REPORT",
        ):
            assert "workers(*)" not in getattr(q, name).replace("workers!worker_id(*)", "")


class TestReassigningClearsAttendance:
    def test_the_whole_record_is_cleared(self):
        """A carried-over record would assert that the NEW worker was present at - or absent
        from - a service they were never on, and that assertion is what their head's report
        shows. Sharper than the stale notice_sent_at this sits beside, which only costs a text."""
        client = MagicMock()
        client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "x"}]
        repo = ScheduleRepository(client)
        repo.get_assignment_by_id = MagicMock(return_value=None)
        repo.delete_reminder_sends = MagicMock(return_value=0)

        repo.reassign_assignment(uuid4(), uuid4(), None, None)

        payload = client.table.return_value.update.call_args.args[0]
        assert payload[q.AssignmentColumns.CHECKED_IN_AT] is None
        assert payload[q.AssignmentColumns.CHECKED_IN_BY] is None
        assert payload[q.AssignmentColumns.MARKED_ABSENT_AT] is None
        assert payload[q.AssignmentColumns.MINUTES_LATE] is None
        assert payload[q.AssignmentColumns.IS_LATE] is False
        assert payload[q.AssignmentColumns.EXCUSED] is False


class TestMarkAbsent:
    def test_an_empty_batch_costs_no_round_trip(self):
        client = MagicMock()
        repo = ScheduleRepository(client)

        assert repo.mark_absent([], datetime.now(timezone.utc), excused=False) == 0
        client.table.assert_not_called()

    def test_a_batch_is_one_statement(self):
        """One statement rather than a loop, for the same reason mark_notice_sent batches: a
        crash mid-loop would leave a register half closed with no way to tell which half."""
        client = MagicMock()
        client.table.return_value.update.return_value.in_.return_value.execute.return_value.data = [{}, {}]
        repo = ScheduleRepository(client)

        marked = repo.mark_absent([uuid4(), uuid4()], datetime.now(timezone.utc), excused=False)

        assert marked == 2
        assert client.table.return_value.update.call_count == 1

    def test_clearing_an_empty_batch_costs_no_round_trip(self):
        client = MagicMock()

        assert ScheduleRepository(client).clear_absences([]) == 0
        client.table.assert_not_called()
