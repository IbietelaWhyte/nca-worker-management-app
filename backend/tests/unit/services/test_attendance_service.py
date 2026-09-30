"""Tests for AttendanceService.

The rule every one of these defends: **attendance nobody closed records nothing.** Absence is
stamped by `close_attendance` and by nothing else, so forgetting attendance - or repairing a rota
after it - can never manufacture an absence against somebody who was there.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.schemas.worker_leave.models import WorkerLeaveResponse
from app.service.attendance.service import AttendanceService
from tests.unit.services.conftest import make_assignment, make_schedule, make_worker

PAST = date(2026, 3, 15)
CLOSED_AT = datetime(2026, 3, 15, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def service(mock_schedule_repo, mock_leave_repo, mock_worker_repo):
    mock_worker_repo.get_by_email.return_value = make_worker(email="head@example.com")
    return AttendanceService(
        schedule_repo=mock_schedule_repo,
        leave_repo=mock_leave_repo,
        worker_repo=mock_worker_repo,
    )


def rota(repo, *assignments, closed_at=None, scheduled_date=PAST):
    """Point the repository at one schedule carrying these assignments."""
    schedule = make_schedule(
        scheduled_date=scheduled_date,
        attendance_closed_at=closed_at,
        schedule_assignments=list(assignments),
    )
    repo.get_with_assignments.return_value = schedule
    if assignments:
        repo.get_assignment_by_id.return_value = assignments[0]
    return schedule


def leave_for(worker_id, on=PAST):
    return WorkerLeaveResponse(
        id=uuid4(),
        worker_id=worker_id,
        start_date=on,
        end_date=on,
        reason=None,
        created_by=None,
        created_at=datetime.now(timezone.utc),
    )


class TestNothingIsRecordedUntilAttendanceIsClosed:
    def test_an_open_attendance_stamps_no_absences(self, service, mock_schedule_repo):
        # The requirement in one test. Three people on the rota, one tapped, attendance left open -
        # and the two untapped must not acquire an absence from anywhere.
        present, missing, other = (make_assignment(schedule_id=uuid4()) for _ in range(3))
        schedule = rota(mock_schedule_repo, present, missing, other)
        mock_schedule_repo.get_assignment_by_id.return_value = present
        mock_schedule_repo.get_with_assignments.return_value = schedule

        service.check_in(present.id, "head@example.com")

        mock_schedule_repo.mark_absent.assert_not_called()

    def test_closing_stamps_everyone_untapped_absent(self, service, mock_schedule_repo):
        here = make_assignment(checked_in_at=datetime(2026, 3, 15, 13, 0, tzinfo=timezone.utc))
        away_one, away_two = make_assignment(), make_assignment()
        schedule = rota(mock_schedule_repo, here, away_one, away_two)

        service.close_attendance(schedule.id, "head@example.com")

        args, kwargs = mock_schedule_repo.mark_absent.call_args_list[0]
        assert set(args[0]) == {away_one.id, away_two.id}
        assert kwargs["excused"] is False
        # The person somebody actually saw is left alone.
        assert here.id not in args[0]

    def test_closing_an_untouched_rota_warns_loudly(self, service, mock_schedule_repo):
        # Almost always a misclick, and the number goes to the workers' head.
        schedule = rota(mock_schedule_repo, make_assignment(), make_assignment())

        result = service.close_attendance(schedule.id, "head@example.com")

        assert any("Nobody was marked present" in w for w in result.warnings)

    def test_closing_twice_is_refused(self, service, mock_schedule_repo):
        schedule = rota(mock_schedule_repo, make_assignment(), closed_at=CLOSED_AT)

        with pytest.raises(ConflictError):
            service.close_attendance(schedule.id, "head@example.com")

    def test_a_future_service_cannot_be_closed(self, service, mock_schedule_repo):
        # The mirror image of a false absence: nobody can have failed to turn up to a service
        # that has not happened.
        schedule = rota(mock_schedule_repo, make_assignment(), scheduled_date=date.today() + timedelta(days=7))

        with pytest.raises(BadRequestError):
            service.close_attendance(schedule.id, "head@example.com")

    def test_a_future_service_cannot_be_checked_into(self, service, mock_schedule_repo):
        future = make_assignment()
        rota(mock_schedule_repo, future, scheduled_date=date.today() + timedelta(days=7))

        with pytest.raises(BadRequestError):
            service.check_in(future.id, "head@example.com")


class TestLeaveIsExcusedRatherThanAbsent:
    def test_a_worker_on_leave_is_excused(self, service, mock_schedule_repo, mock_leave_repo):
        # Leave never edits the rota by design, so somebody away is still on it. Marking them
        # absent would put every volunteer who took a holiday in their head's report.
        away = make_assignment()
        missing = make_assignment()
        schedule = rota(mock_schedule_repo, away, missing)
        mock_leave_repo.get_for_workers.return_value = [leave_for(away.worker_id)]

        result = service.close_attendance(schedule.id, "head@example.com")

        calls = {kwargs["excused"]: args[0] for args, kwargs in mock_schedule_repo.mark_absent.call_args_list}
        assert calls[True] == [away.id]
        assert calls[False] == [missing.id]
        assert any("on leave" in w for w in result.warnings)

    def test_leave_is_looked_up_for_the_service_date_not_today(self, service, mock_schedule_repo, mock_leave_repo):
        schedule = rota(mock_schedule_repo, make_assignment())

        service.close_attendance(schedule.id, "head@example.com")

        _, start, end = mock_leave_repo.get_for_workers.call_args.args
        assert start == end == PAST


class TestUndoAndReopen:
    def test_undo_on_open_attendance_leaves_no_record(self, service, mock_schedule_repo):
        here = make_assignment(checked_in_at=CLOSED_AT)
        rota(mock_schedule_repo, here)

        service.undo_check_in(here.id)

        mock_schedule_repo.clear_check_in.assert_called_once_with(here.id, None)

    def test_undo_on_closed_attendance_leaves_them_absent(self, service, mock_schedule_repo):
        # Closed attendance must not develop a hole that says neither present nor absent - the
        # report reads no record as "nobody checked" and would stop counting a decided duty.
        here = make_assignment(checked_in_at=CLOSED_AT)
        rota(mock_schedule_repo, here, closed_at=CLOSED_AT)

        service.undo_check_in(here.id)

        mock_schedule_repo.clear_check_in.assert_called_once_with(here.id, CLOSED_AT)

    def test_reopening_clears_absences_and_keeps_check_ins(self, service, mock_schedule_repo):
        here = make_assignment(checked_in_at=CLOSED_AT)
        absent = make_assignment(marked_absent_at=CLOSED_AT)
        schedule = rota(mock_schedule_repo, here, absent, closed_at=CLOSED_AT)

        service.reopen_attendance(schedule.id)

        mock_schedule_repo.clear_absences.assert_called_once_with([absent.id])
        mock_schedule_repo.set_attendance_closed.assert_called_once_with(schedule.id, None, None)

    def test_reopening_open_attendance_is_refused(self, service, mock_schedule_repo):
        schedule = rota(mock_schedule_repo, make_assignment())

        with pytest.raises(ConflictError):
            service.reopen_attendance(schedule.id)


class TestExcusing:
    def test_only_an_absence_can_be_excused(self, service, mock_schedule_repo):
        here = make_assignment(checked_in_at=CLOSED_AT)
        rota(mock_schedule_repo, here)

        with pytest.raises(BadRequestError):
            service.set_excused(here.id, True)

    def test_excusing_an_absence_is_allowed(self, service, mock_schedule_repo):
        absent = make_assignment(marked_absent_at=CLOSED_AT)
        rota(mock_schedule_repo, absent)

        service.set_excused(absent.id, True)

        mock_schedule_repo.set_excused.assert_called_once_with(absent.id, True)


class TestCounts:
    def test_the_tally_separates_all_five_states(self, service, mock_schedule_repo):
        schedule = rota(
            mock_schedule_repo,
            make_assignment(checked_in_at=CLOSED_AT),
            make_assignment(checked_in_at=CLOSED_AT, is_late=True, minutes_late=20),
            make_assignment(marked_absent_at=CLOSED_AT),
            make_assignment(marked_absent_at=CLOSED_AT, excused=True),
            make_assignment(),
            closed_at=CLOSED_AT,
        )

        counts = service.count(schedule)

        assert (counts.assigned, counts.present, counts.late) == (5, 2, 1)
        assert (counts.absent, counts.excused, counts.not_recorded) == (1, 1, 1)


class TestReport:
    def test_only_recorded_duties_count_toward_the_rate(self, service, mock_schedule_repo):
        # Dividing by rostered duties instead would flatter a department that never takes the
        # register, which is exactly the wrong incentive to build in.
        worker = make_worker()
        mock_schedule_repo.get_for_attendance_report.return_value = [
            make_schedule(
                scheduled_date=date(2026, 3, 1),
                attendance_closed_at=CLOSED_AT,
                schedule_assignments=[make_assignment(worker_id=worker.id, workers=worker, marked_absent_at=CLOSED_AT)],
            ),
            make_schedule(
                scheduled_date=date(2026, 3, 8),
                schedule_assignments=[make_assignment(worker_id=worker.id, workers=worker)],
            ),
        ]

        report = service.get_report(uuid4(), date(2026, 3, 1), date(2026, 3, 31))

        row = report.rows[0]
        assert (row.duties, row.absences, row.not_recorded) == (1, 1, 1)
        assert row.absence_rate == 1.0
        assert (report.services, report.services_with_attendance) == (2, 1)

    def test_an_excused_absence_stays_in_the_denominator(self, service, mock_schedule_repo):
        worker = make_worker()
        mock_schedule_repo.get_for_attendance_report.return_value = [
            make_schedule(
                scheduled_date=date(2026, 3, 1),
                attendance_closed_at=CLOSED_AT,
                schedule_assignments=[
                    make_assignment(worker_id=worker.id, workers=worker, marked_absent_at=CLOSED_AT, excused=True)
                ],
            )
        ]

        row = service.get_report(uuid4(), date(2026, 3, 1), date(2026, 3, 31)).rows[0]

        assert (row.duties, row.excused, row.absences) == (1, 1, 0)
        assert row.absence_rate == 0.0

    def test_a_backwards_window_is_refused(self, service):
        with pytest.raises(BadRequestError):
            service.get_report(uuid4(), date(2026, 3, 31), date(2026, 3, 1))

    def test_rows_come_back_worst_first(self, service, mock_schedule_repo):
        # The reason somebody opens this is to find who to speak to.
        steady, flaky = make_worker(email="a@x.com"), make_worker(email="b@x.com")
        mock_schedule_repo.get_for_attendance_report.return_value = [
            make_schedule(
                scheduled_date=date(2026, 3, d),
                attendance_closed_at=CLOSED_AT,
                schedule_assignments=[
                    make_assignment(worker_id=steady.id, workers=steady, checked_in_at=CLOSED_AT),
                    make_assignment(worker_id=flaky.id, workers=flaky, marked_absent_at=CLOSED_AT),
                ],
            )
            for d in (1, 8)
        ]

        report = service.get_report(uuid4(), date(2026, 3, 1), date(2026, 3, 31))

        assert report.rows[0].worker_id == flaky.id
        assert report.rows[0].absences == 2
        assert report.rows[0].last_absent_on == date(2026, 3, 8)


class TestMissingRecords:
    def test_an_unknown_assignment_is_not_found(self, service, mock_schedule_repo):
        mock_schedule_repo.get_assignment_by_id.return_value = None

        with pytest.raises(NotFoundError):
            service.check_in(uuid4(), "head@example.com")

    def test_an_unknown_schedule_is_not_found(self, service, mock_schedule_repo):
        mock_schedule_repo.get_with_assignments.return_value = None

        with pytest.raises(NotFoundError):
            service.close_attendance(uuid4(), "head@example.com")

    def test_an_operator_without_a_worker_record_can_still_take_attendance(
        self, service, mock_schedule_repo, mock_worker_repo
    ):
        # An admin need not have a worker profile, and that is no reason to refuse them the
        # register - checked_in_by is nullable precisely so the act can be recorded without them.
        mock_worker_repo.get_by_email.return_value = None
        here = make_assignment()
        rota(mock_schedule_repo, here)

        service.check_in(here.id, "admin@example.com")

        assert mock_schedule_repo.set_check_in.call_args.args[4] is None
