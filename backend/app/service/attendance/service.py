"""Recording who turned up, and reporting who keeps not turning up.

A rota says who was asked; this says who came. The whole feature turns on one rule, and the
schema, the service and the UI all exist to keep it true:

    **A roll call nobody closed records nothing.**

Absence is stamped by `close_roll_call` and by nothing else, so an operator who forgets - or who
never takes the register at all - leaves every duty reading "not recorded" rather than marking a
department absent. The alternative, deriving absence from "the register closed and this one has no
check-in", also marks anyone *added to the rota after closure* absent, and a head repairing a rota
after the fact is adding exactly the person who did turn up.

Its own package rather than more `ScheduleService`, which is already the largest service here and
owns the generation machinery this shares none of. The writes still go through `ScheduleRepository`,
because that repository owns both tables.
"""

from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.repository.schedules.repository import ScheduleRepository
from app.repository.worker_leave.repository import WorkerLeaveRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.attendance.models import (
    AbsenceReport,
    AbsenceRow,
    AttendanceState,
    RollCallCount,
)
from app.schemas.schedules.models import AssignmentResponse, RollCallResult, ScheduleResponse
from app.schemas.workers.models import WorkerResponse
from app.service.attendance import rules

logger = get_logger(__name__)


class AttendanceService:
    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        leave_repo: WorkerLeaveRepository,
        worker_repo: WorkerRepository,
    ) -> None:
        self.schedule_repo = schedule_repo
        self.leave_repo = leave_repo
        self.worker_repo = worker_repo
        self.logger = logger.bind(service="AttendanceService")

    # ------------------------------------------------------------------
    # Taking the register
    # ------------------------------------------------------------------

    def check_in(self, assignment_id: UUID, actor_email: str | None) -> RollCallResult:
        """Mark one worker present, judging lateness against the service they were on.

        Clears any absence already stamped against them, so somebody who arrives after the
        register was closed is simply tapped in - the commonest correction there is - without the
        head reopening the whole thing first.

        Args:
            assignment_id: The duty being marked.
            actor_email: The signed-in operator, recorded as who saw them.

        Returns:
            RollCallResult: The re-read rota and its tally.

        Raises:
            NotFoundError: If the assignment or its schedule is gone.
            BadRequestError: If the service has not happened yet.
        """
        log = self.logger.bind(method="check_in", assignment_id=str(assignment_id))
        assignment = self._require_assignment(assignment_id)
        schedule = self._require_schedule(assignment.schedule_id)
        self._reject_future(schedule.scheduled_date, "check workers in")

        now = datetime.now(timezone.utc)
        minutes_late, is_late = rules.lateness(
            schedule.scheduled_date,
            schedule.start_time,
            now,
            settings.attendance_grace_minutes,
            self._tz(),
        )
        actor = self._actor(actor_email)
        self.schedule_repo.set_check_in(assignment_id, now, minutes_late, is_late, actor.id if actor else None)
        log.info("checked_in", is_late=is_late, minutes_late=minutes_late)
        return self._result(schedule.id)

    def undo_check_in(self, assignment_id: UUID) -> RollCallResult:
        """Take a check-in back.

        Where it lands depends on the register: on an open one the duty returns to "not recorded",
        and on a closed one it returns to absent. A closed register must not develop a hole that
        says neither, because the report reads the absence of a record as "nobody checked" and
        would quietly stop counting a duty somebody did decide about.

        Args:
            assignment_id: The duty being un-marked.

        Returns:
            RollCallResult: The re-read rota and its tally.

        Raises:
            NotFoundError: If the assignment or its schedule is gone.
        """
        log = self.logger.bind(method="undo_check_in", assignment_id=str(assignment_id))
        assignment = self._require_assignment(assignment_id)
        schedule = self._require_schedule(assignment.schedule_id)

        self.schedule_repo.clear_check_in(assignment_id, schedule.roll_call_closed_at)
        log.info("check_in_undone", roll_call_closed=schedule.roll_call_closed_at is not None)
        return self._result(schedule.id)

    def close_roll_call(self, schedule_id: UUID, actor_email: str | None) -> RollCallResult:
        """Finish the register: everyone untapped is recorded absent, from this moment.

        The only writer of `marked_absent_at`, which is what makes "a roll call nobody closed
        records nothing" true by construction rather than by a predicate somebody can forget.

        **Workers on leave are excused, not absent.** Leave never edits the rota by design - a
        head is told about the clash and reassigns - so somebody away is still on the roster and
        would otherwise be marked absent for a fortnight they agreed in advance. The very first
        report would then name everyone who took a holiday.

        Args:
            schedule_id: The rota whose register it is.
            actor_email: The signed-in operator.

        Returns:
            RollCallResult: The re-read rota, its tally, and anything worth saying about it.

        Raises:
            NotFoundError: If the schedule is gone.
            ConflictError: If the register is already closed.
            BadRequestError: If the service has not happened yet.
        """
        log = self.logger.bind(method="close_roll_call", schedule_id=str(schedule_id))
        schedule = self._require_schedule(schedule_id)
        if schedule.roll_call_closed_at is not None:
            raise ConflictError("The roll call for this rota is already closed. Reopen it to make changes.")
        self._reject_future(schedule.scheduled_date, "close a roll call")

        assignments = schedule.schedule_assignments
        unmarked = [a for a in assignments if a.checked_in_at is None]
        on_leave = self._workers_on_leave([a.worker_id for a in unmarked], schedule.scheduled_date)

        now = datetime.now(timezone.utc)
        excused_ids = [a.id for a in unmarked if a.worker_id in on_leave]
        absent_ids = [a.id for a in unmarked if a.worker_id not in on_leave]
        self.schedule_repo.mark_absent(absent_ids, now, excused=False)
        self.schedule_repo.mark_absent(excused_ids, now, excused=True)

        actor = self._actor(actor_email)
        self.schedule_repo.set_roll_call_closed(schedule_id, now, actor.id if actor else None)

        warnings: list[str] = []
        present = len(assignments) - len(unmarked)
        if assignments and present == 0:
            # Loud, because it is almost always a misclick: closing an untouched register records
            # the whole team absent, and that number goes to their head.
            warnings.append(
                "Nobody was marked present, so everyone on this rota has been recorded absent. "
                "Reopen the roll call if that is not right."
            )
        if excused_ids:
            warnings.append(
                f"{len(excused_ids)} worker(s) were on leave for this date and have been excused "
                "rather than marked absent."
            )
        log.info("roll_call_closed", present=present, absent=len(absent_ids), excused=len(excused_ids))
        return self._result(schedule_id, warnings)

    def reopen_roll_call(self, schedule_id: UUID) -> RollCallResult:
        """Reopen the register, erasing the absences closing it stamped.

        Check-ins survive. Closing invents absences; it does not invent the arrivals somebody
        stood there and observed, and erasing those would lose real information to fix a mistake
        about different rows.

        Args:
            schedule_id: The rota whose register it is.

        Returns:
            RollCallResult: The re-read rota and its tally.

        Raises:
            NotFoundError: If the schedule is gone.
            ConflictError: If the register is not closed.
        """
        log = self.logger.bind(method="reopen_roll_call", schedule_id=str(schedule_id))
        schedule = self._require_schedule(schedule_id)
        if schedule.roll_call_closed_at is None:
            raise ConflictError("The roll call for this rota is not closed.")

        absent_ids = [a.id for a in schedule.schedule_assignments if a.marked_absent_at is not None]
        cleared = self.schedule_repo.clear_absences(absent_ids)
        self.schedule_repo.set_roll_call_closed(schedule_id, None, None)
        log.info("roll_call_reopened", absences_cleared=cleared)
        return self._result(schedule_id)

    def set_excused(self, assignment_id: UUID, excused: bool) -> RollCallResult:
        """Mark an absence as not counting against the worker, or put it back.

        Args:
            assignment_id: The absence to excuse.
            excused: Whether it should count.

        Returns:
            RollCallResult: The re-read rota and its tally.

        Raises:
            NotFoundError: If the assignment or its schedule is gone.
            BadRequestError: If the duty is not an absence.
        """
        assignment = self._require_assignment(assignment_id)
        if assignment.marked_absent_at is None:
            raise BadRequestError("Only an absence can be excused.")
        self.schedule_repo.set_excused(assignment_id, excused)
        return self._result(assignment.schedule_id)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_report(self, department_id: UUID, from_date: date, to_date: date) -> AbsenceReport:
        """A department's attendance over a window, per worker.

        Counts **services** as well as people. A month whose register was taken twice out of
        twelve has to be able to say so, or the report reads as near-perfect attendance and
        teaches whoever opens it to distrust the feature.

        Args:
            department_id: The department to report on.
            from_date: First day of the window, inclusive.
            to_date: Last day, inclusive.

        Returns:
            AbsenceReport: One row per worker who held a duty in the window.

        Raises:
            BadRequestError: If the window runs backwards.
        """
        if from_date > to_date:
            raise BadRequestError("The start of the window must not be after its end.")

        schedules = self.schedule_repo.get_for_attendance_report(department_id, from_date, to_date)
        rows: dict[UUID, AbsenceRow] = {}
        workers: dict[UUID, WorkerResponse] = {}

        for schedule in schedules:
            for assignment in schedule.schedule_assignments:
                row = rows.setdefault(
                    assignment.worker_id,
                    AbsenceRow(
                        worker_id=assignment.worker_id,
                        department_id=department_id,
                        duties=0,
                        present=0,
                        late=0,
                        absences=0,
                        excused=0,
                        not_recorded=0,
                    ),
                )
                if assignment.workers and assignment.worker_id not in workers:
                    workers[assignment.worker_id] = assignment.workers
                self._tally(row, assignment, schedule.scheduled_date)

        for worker_id, row in rows.items():
            row.worker = workers.get(worker_id)

        report_rows = sorted(
            rows.values(),
            # Worst first, because the reason somebody opens this is to find who to speak to.
            key=lambda r: (-r.absences, -r.absence_rate, str(r.worker_id)),
        )
        return AbsenceReport(
            department_id=department_id,
            from_date=from_date,
            to_date=to_date,
            services=len(schedules),
            services_with_roll_call=sum(1 for s in schedules if s.roll_call_closed_at is not None),
            window_days=settings.attendance_window_days,
            repeat_threshold=settings.attendance_repeat_threshold,
            rows=report_rows,
        )

    def department_for_assignment(self, assignment_id: UUID) -> UUID:
        """Which department's rota a duty belongs to, so the router can authorize against it.

        Exists for the same reason `ScheduleService.get_assignment` does: the router needs the
        owning department before it lets the call through, and it should not reach past the
        service for it.

        Args:
            assignment_id: The duty in question.

        Returns:
            UUID: The department that owns the rota this duty sits on.

        Raises:
            NotFoundError: If the assignment or its schedule is gone.
        """
        return self._require_schedule(self._require_assignment(assignment_id).schedule_id).department_id

    def department_for_schedule(self, schedule_id: UUID) -> UUID:
        """Which department a rota belongs to, so the router can authorize against it.

        Args:
            schedule_id: The rota in question.

        Returns:
            UUID: The owning department.

        Raises:
            NotFoundError: If the schedule is gone.
        """
        return self._require_schedule(schedule_id).department_id

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _tally(row: AbsenceRow, assignment: AssignmentResponse, on: date) -> None:
        """Fold one duty into a worker's running row.

        `duties` counts only what was actually recorded, so the absence rate is judged against
        what is known. Dividing by rostered duties instead would flatter a department that never
        takes the register, which is precisely the wrong incentive to build in.
        """
        state = rules.state_of(
            assignment.checked_in_at, assignment.marked_absent_at, assignment.is_late, assignment.excused
        )
        if state is AttendanceState.NOT_RECORDED:
            row.not_recorded += 1
            return

        row.duties += 1
        if state is AttendanceState.PRESENT:
            row.present += 1
        elif state is AttendanceState.LATE:
            row.present += 1
            row.late += 1
            row.late_dates.append(on)
        elif state is AttendanceState.EXCUSED:
            row.excused += 1
        else:
            row.absences += 1
            row.absent_dates.append(on)
            if row.last_absent_on is None or on > row.last_absent_on:
                row.last_absent_on = on

    def _workers_on_leave(self, worker_ids: list[UUID], on: date) -> set[UUID]:
        """Who among these is away on this date, in one round-trip."""
        if not worker_ids:
            return set()
        records = self.leave_repo.get_for_workers(worker_ids, on, on)
        return {leave.worker_id for leave in records if leave.covers(on)}

    def _result(self, schedule_id: UUID, warnings: list[str] | None = None) -> RollCallResult:
        """Re-read the rota and count it, so the caller replaces its copy wholesale."""
        schedule = self._require_schedule(schedule_id)
        return RollCallResult(schedule=schedule, counts=self.count(schedule), warnings=warnings or [])

    @staticmethod
    def count(schedule: ScheduleResponse) -> RollCallCount:
        """The tally an operator watches while taking the register."""
        states = [
            rules.state_of(a.checked_in_at, a.marked_absent_at, a.is_late, a.excused)
            for a in schedule.schedule_assignments
        ]
        return RollCallCount(
            assigned=len(states),
            present=sum(1 for s in states if s in (AttendanceState.PRESENT, AttendanceState.LATE)),
            late=sum(1 for s in states if s is AttendanceState.LATE),
            absent=sum(1 for s in states if s is AttendanceState.ABSENT),
            excused=sum(1 for s in states if s is AttendanceState.EXCUSED),
            not_recorded=sum(1 for s in states if s is AttendanceState.NOT_RECORDED),
        )

    def _actor(self, email: str | None) -> WorkerResponse | None:
        """Who to credit with the record, or None.

        Deliberately forgiving: an admin need not have a worker profile, and a token can arrive
        without an email claim. Neither is a reason to refuse a head the register - the column is
        nullable precisely so the act can be recorded without the actor.
        """
        return self.worker_repo.get_by_email(email) if email else None

    @staticmethod
    def _tz() -> ZoneInfo:
        return ZoneInfo(settings.church_timezone)

    def _reject_future(self, scheduled_date: date, action: str) -> None:
        """Refuse to record attendance for a service that has not happened.

        The mirror image of a false absence: marking somebody present for next Sunday is a claim
        nobody could have observed. Judged in the church's own zone, because a server in UTC rolls
        over to tomorrow while the congregation is still in the building.
        """
        today = datetime.now(self._tz()).date()
        if scheduled_date > today:
            raise BadRequestError(f"You cannot {action} for a service that has not happened yet.")

    def _require_assignment(self, assignment_id: UUID) -> AssignmentResponse:
        assignment = self.schedule_repo.get_assignment_by_id(assignment_id)
        if not assignment:
            raise NotFoundError(f"Assignment {assignment_id} not found")
        return assignment

    def _require_schedule(self, schedule_id: UUID) -> ScheduleResponse:
        schedule = self.schedule_repo.get_with_assignments(schedule_id)
        if not schedule:
            raise NotFoundError(f"Schedule {schedule_id} not found")
        return schedule
