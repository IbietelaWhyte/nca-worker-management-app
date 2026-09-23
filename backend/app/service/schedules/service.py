import calendar
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from postgrest.exceptions import APIError

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.repository.availabilities.repository import AvailabilityRepository
from app.repository.department_roles.repository import DepartmentRoleRepository
from app.repository.departments.repository import DepartmentRepository
from app.repository.schedules import queries as q
from app.repository.schedules.repository import ScheduleRepository
from app.repository.subteams.repository import SubteamRepository
from app.repository.worker_leave.repository import WorkerLeaveRepository
from app.repository.workers.repository import WorkerRepository
from app.schemas.department_roles.models import DepartmentRoleResponse
from app.schemas.departments.models import DepartmentResponse
from app.schemas.models import AvailabilityType, DayOfWeek
from app.schemas.schedules.models import (
    AssignableWorker,
    AssignmentResponse,
    DatePlan,
    DatePlanStatus,
    DateSelection,
    MonthlyScheduleCommitRequest,
    MonthlySchedulePreview,
    MonthlySchedulePreviewRequest,
    MonthlyScheduleResult,
    PlannedAssignment,
    PlannedGroup,
    Schedule,
    ScheduleCreate,
    ScheduleEditResult,
    ScheduleResponse,
    ScopeType,
    SkippedDate,
)
from app.schemas.subteams.models import SubteamResponse
from app.schemas.workers.models import Worker, WorkerResponse
from app.service.schedules.planner import GroupContext, PlanContext, plan_month
from app.service.sms.service import SMSService

logger = get_logger(__name__)

# Postgres unique_violation — raised by the partial unique indexes on schedules when a
# concurrent request claims a date between preview and commit.
UNIQUE_VIOLATION = "23505"


@dataclass
class ScopeGroup:
    """One roster to staff, with the band it has to fill on each date.

    `subteam` is None for the department-only roster (workers in no subteam).
    """

    subteam: SubteamResponse | None
    min_workers: int
    max_workers: int
    workers: list[Worker]

    @property
    def key(self) -> str:
        """Stable identity used to match planner results back to this group."""
        return str(self.subteam.id) if self.subteam else ""


def _staffing_band(subteam: SubteamResponse | None, department: DepartmentResponse) -> tuple[int, int]:
    """The (minimum, maximum) a group has to staff to.

    A subteam overrides the whole band or inherits the whole band — `chk_subteam_inherit_both`
    makes a half-set override unrepresentable — so one `is None` test settles both bounds.

    Tested with `is None` rather than the old `subteam.workers_per_slot or ...`: a minimum of 0
    ("use whoever is free, never flag it short") is now a legitimate setting, and `or` would
    silently discard it in favour of the department's. The old expression was only ever safe
    because a CHECK forbade 0, and that guard does not survive the split.

    Args:
        subteam: The group's subteam, or None for the department-only roster.
        department: The department, which supplies the band when the subteam inherits.

    Returns:
        tuple[int, int]: Minimum and maximum workers for this group on one date.
    """
    if subteam is not None and subteam.min_workers_per_slot is not None:
        # max is guaranteed non-None alongside min by chk_subteam_inherit_both; the `or` is a
        # belt-and-braces default for a row that predates the constraint.
        return subteam.min_workers_per_slot, subteam.max_workers_per_slot or subteam.min_workers_per_slot
    return department.min_workers_per_slot, department.max_workers_per_slot


def _active(workers: list[WorkerResponse]) -> list[Worker]:
    """Narrow a repository response to active workers as plain `Worker` models."""
    return [worker for w in workers if (worker := Worker(**w.model_dump())).is_active]


def _scope_description(scope: ScopeType) -> str:
    """Human-readable scope name, used in error messages."""
    return {
        ScopeType.SUBTEAM: "subteam",
        ScopeType.DEPARTMENT_ONLY: "department (department-only workers)",
        ScopeType.DEPARTMENT_ALL: "department",
    }.get(scope, "scope")


def _subteam_for_assignment(
    subteams: dict[UUID, UUID | None], worker_id: UUID, schedule_subteam_id: str | None
) -> str | None:
    """The subteam to stamp on an assignment row.

    Only DEPARTMENT_ALL populates `subteams` per worker; every other scope falls back to
    the schedule's own subteam (or None).
    """
    if worker_id not in subteams:
        return schedule_subteam_id
    resolved = subteams[worker_id]
    return str(resolved) if resolved else None


def _scope_of(schedule: ScheduleResponse) -> ScopeType:
    """Work out which scope a generated schedule was made with.

    The row records only `subteam_id`, not the `ScopeType` that produced it, and the edit paths
    need the scope to decide who may be added. A subteam id pins it; otherwise the assignments
    tell the two department scopes apart, because only DEPARTMENT_ALL stamps a subteam onto the
    rows of a schedule that has none of its own.

    The one ambiguous case is a department-wide rota whose every pick happened to be a worker in
    no subteam, which reads back as DEPARTMENT_ONLY. That narrows who may be added rather than
    widening it, so the failure is a head being told somebody is not eligible — visible and
    correctable — instead of a Seekers worker silently appearing on the wrong rota.

    Args:
        schedule: The schedule being edited, with its assignments embedded.

    Returns:
        ScopeType: The scope this rota was generated under.
    """
    if schedule.subteam_id is not None:
        return ScopeType.SUBTEAM
    if any(a.subteam_id is not None for a in schedule.schedule_assignments):
        return ScopeType.DEPARTMENT_ALL
    return ScopeType.DEPARTMENT_ONLY


def _describe_when(schedule: Schedule) -> str:
    """Render a duty for an SMS, e.g. "Sun 02 Aug at 09:00".

    Deliberately the same string `ReminderService._describe` builds, and deliberately a second
    copy of one line: the alternative is the schedules service importing the reminder service
    for a strftime call. Keep them identical — a worker reading a notice and a cancellation
    about the same date should not have to reconcile two formats.
    """
    return f"{schedule.scheduled_date.strftime('%a %d %b')} at {schedule.start_time.strftime('%H:%M')}"


def _last_day_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _dates_in_month(year: int, month: int, days_of_week: list[DayOfWeek]) -> list[date]:
    """Every date in the month falling on one of the given weekdays, ascending.

    DayOfWeek.to_number() is 0=Sunday (the DB convention); Python's weekday() is
    0=Monday, hence the shift.
    """
    wanted = {day.to_number() for day in days_of_week}
    last_day = _last_day_of_month(year, month).day
    return [
        candidate
        for day in range(1, last_day + 1)
        if ((candidate := date(year, month, day)).weekday() + 1) % 7 in wanted
    ]


class ScheduleService:
    def __init__(
        self,
        schedule_repo: ScheduleRepository,
        worker_repo: WorkerRepository,
        department_repo: DepartmentRepository,
        subteam_repo: SubteamRepository,
        availability_repo: AvailabilityRepository,
        department_role_repo: DepartmentRoleRepository,
        leave_repo: WorkerLeaveRepository,
        sms_service: SMSService,
    ) -> None:
        self.schedule_repo = schedule_repo
        self.worker_repo = worker_repo
        self.department_repo = department_repo
        self.subteam_repo = subteam_repo
        self.availability_repo = availability_repo
        self.leave_repo = leave_repo
        self.department_role_repo = department_role_repo
        # Editing a rota texts both people affected inline, rather than leaving it to the
        # sweep: the head is standing in front of them, and a cancellation has no row left
        # for a sweep to find.
        self.sms_service = sms_service

        # bind the logger to the service name for structured logging
        self.logger = logger.bind(service="ScheduleService")

    def get_schedule(self, schedule_id: UUID) -> ScheduleResponse:
        # bind the method and schedule_id for better traceability in logs
        log = self.logger.bind(method="get_schedule", schedule_id=str(schedule_id))
        schedule = self.schedule_repo.get_with_assignments(schedule_id)
        if not schedule:
            log.warning("schedule_not_found")
            raise NotFoundError(f"Schedule {schedule_id} not found")
        return schedule

    def get_schedules_by_department(
        self,
        department_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[ScheduleResponse]:
        # bind the method and department_id for better traceability in logs
        log = self.logger.bind(method="get_schedules_by_department", department_id=str(department_id))
        if from_date and to_date and from_date > to_date:
            raise BadRequestError("'from' must not be after 'to'")
        schedules = self.schedule_repo.get_by_department(department_id, from_date, to_date)
        log.info(
            "fetched_schedules_by_department",
            count=len(schedules),
        )
        return schedules

    def get_worker_assignments(self, worker_id: UUID) -> list[AssignmentResponse]:
        log = self.logger.bind(method="get_worker_assignments", worker_id=str(worker_id))
        log.info("fetching_worker_assignments")
        return self.schedule_repo.get_assignments_for_worker(worker_id)

    def generate_schedule(self, data: ScheduleCreate, created_by: str) -> ScheduleResponse | None:
        """Generate one date's rota.

        Runs through the same `plan_month` the monthly path uses, with a one-date list. Two
        implementations of "whose turn is it" had drifted apart in every dimension that
        matters — the old single-date sort had no tiebreaker (so two runs could legitimately
        pick different people), no month-count term (so three ad-hoc dates in one month went
        to overlapping people), and issued one history query per worker from inside the sort
        key. Every selection rule now lives in the planner, gets written once, and is tested
        there without a single mock.

        Args:
            data: What to schedule, for whom, and when.
            created_by: Email of the signed-in user, recorded as the schedule's author.

        Returns:
            ScheduleResponse | None: The created schedule with its assignments embedded.

        Raises:
            ConflictError: If a schedule already exists for this department/date/subteam.
            BadRequestError: If the scope has no workers, or none of them can serve that day.
            NotFoundError: If the department, subteam, or the author's worker record is missing.
        """
        log = self.logger.bind(
            method="generate_schedule",
            department_id=str(data.department_id),
            scope=data.scope.value,
            subteam_id=str(data.subteam_id) if data.subteam_id else None,
            scheduled_date=data.scheduled_date.isoformat(),
        )
        log.info("schedule_generation_started")

        # Kept ahead of the planner rather than left to its SKIPPED_EXISTING: this message
        # names the existing schedule's id, which is what the frontend offers a link to.
        check_subteam_id = data.subteam_id if data.scope == ScopeType.SUBTEAM else None
        existing_schedule = self.schedule_repo.get_existing_schedule(
            data.department_id, data.scheduled_date, check_subteam_id
        )
        if existing_schedule:
            scope_description = "subteam" if existing_schedule.subteam_id else "department"
            raise ConflictError(
                f"A schedule already exists for this {scope_description} on {data.scheduled_date.isoformat()}. "
                f"Please edit or delete the existing schedule (ID: {existing_schedule.id}) instead."
            )

        groups = self._resolve_scope_groups(data.department_id, data.scope, data.subteam_id)
        min_workers = sum(g.min_workers for g in groups)
        max_workers = sum(g.max_workers for g in groups)

        log.info(
            "scope_groups_resolved",
            groups=len(groups),
            min_workers=min_workers,
            max_workers=max_workers,
            eligible_workers=sum(len(g.workers) for g in groups),
        )

        if not any(g.workers for g in groups):
            raise BadRequestError(f"No workers found for this {_scope_description(data.scope)}")

        scheduled_date = data.scheduled_date
        context = self._build_plan_context(
            groups=groups,
            department_id=data.department_id,
            scope=data.scope,
            subteam_id=data.subteam_id,
            dates=[scheduled_date],
            # The month around the date, so the fairness count sees the rest of it. Generating
            # three ad-hoc dates in one month now spreads them rather than reusing the same
            # people, which the old per-date sort could not do.
            month_start=scheduled_date.replace(day=1),
            month_end=_last_day_of_month(scheduled_date.year, scheduled_date.month),
        )
        plan = plan_month([scheduled_date], context)[0]

        if plan.status == DatePlanStatus.SKIPPED_NO_WORKERS:
            # The planner's message separates unavailable from already-scheduled, which the
            # hand-rolled one this replaced did not.
            raise BadRequestError(plan.message or f"No available workers found for {scheduled_date}")
        if plan.status == DatePlanStatus.SKIPPED_EXISTING:
            # Unreachable — the pre-check above already raised. Defensive, and loud if the two
            # ever disagree about what "already exists" means.
            raise ConflictError(plan.message or "A schedule already exists for this date.")

        workers_by_id = {w.id: w for group in groups for w in group.workers}
        selected: list[Worker] = []
        selected_subteams: dict[UUID, UUID | None] = {}
        subteam_by_key = {g.key: g.subteam for g in groups}
        for group_plan in plan.groups:
            subteam = subteam_by_key.get(group_plan.key)
            for worker_id in group_plan.selected:
                selected.append(workers_by_id[worker_id])
                selected_subteams[worker_id] = subteam.id if subteam else None

        if plan.status == DatePlanStatus.UNDERSTAFFED:
            # Created anyway. A head generating one date wants the rota even when it is short —
            # a partial rota they can fill by hand beats no rota at all.
            log.warning("schedule_understaffed", message=plan.message, selected=len(selected))

        created_by_user = self.worker_repo.get_by_email(created_by)
        if not created_by_user:
            raise NotFoundError(f"User with email {created_by} not found")

        # Only SUBTEAM scope pins the schedule to a subteam; the others are department-level.
        schedule_subteam_id = str(data.subteam_id) if data.scope == ScopeType.SUBTEAM else None

        schedule_data = {
            q.Columns.DEPARTMENT_ID: str(data.department_id),
            q.Columns.SUBTEAM_ID: schedule_subteam_id,
            q.Columns.TITLE: data.title,
            q.Columns.SCHEDULED_DATE: scheduled_date.isoformat(),
            q.Columns.START_TIME: data.start_time.isoformat(),
            q.Columns.END_TIME: data.end_time.isoformat(),
            q.Columns.NOTES: data.notes,
            q.Columns.REMINDER_DAYS_BEFORE: data.reminder_days_before,
            # Frozen here rather than re-read on every render: the department's numbers may
            # change before this date comes round, and this rota was planned against these.
            q.Columns.MIN_WORKERS: min_workers,
            q.Columns.MAX_WORKERS: max_workers,
            q.Columns.CREATED_BY: str(created_by_user.id),
        }
        schedule = self.schedule_repo.create(schedule_data)

        # Auto-fill each assignment's role from the worker's standing department role.
        # The HOD can override an individual assignment's role later via update_assignment_role.
        worker_roles = self._resolve_worker_roles([w.id for w in selected], data.department_id)
        log.info("worker_roles_resolved", count=len(worker_roles))

        assignments = [
            {
                "schedule_id": str(schedule.id),
                "worker_id": str(worker.id),
                # The group already told us which subteam each worker fills.
                "subteam_id": _subteam_for_assignment(selected_subteams, worker.id, schedule_subteam_id),
                "department_role_id": str(role.id) if (role := worker_roles.get(worker.id)) else None,
            }
            for worker in selected
        ]
        self.schedule_repo.bulk_create_assignments(assignments)

        log.info(
            "schedule_generation_completed",
            schedule_id=str(schedule.id),
            assignments_created=len(assignments),
        )

        return self.schedule_repo.get_with_assignments(schedule.id)

    def get_assignment(self, assignment_id: UUID) -> AssignmentResponse:
        """Fetch one assignment, with its worker, subteam and role embedded.

        Exists so the router can authorize against the assignment's owner without reaching past
        the service for it.

        Args:
            assignment_id: The assignment to fetch.

        Returns:
            AssignmentResponse: The assignment.

        Raises:
            NotFoundError: If no assignment has that id.
        """
        assignment = self.schedule_repo.get_assignment_by_id(assignment_id)
        if not assignment:
            self.logger.bind(method="get_assignment", assignment_id=str(assignment_id)).warning("assignment_not_found")
            raise NotFoundError(f"Assignment {assignment_id} not found")
        return assignment

    def update_assignment_role(self, assignment_id: UUID, department_role_id: UUID | None) -> AssignmentResponse:
        """Override the department role on a schedule assignment.

        Validates that the role (when provided) belongs to the same department as the
        assignment's schedule, preventing a role from another department being applied.

        Args:
            assignment_id: Unique identifier of the assignment to update.
            department_role_id: The role to set, or None to clear it.

        Returns:
            AssignmentResponse: The updated assignment.

        Raises:
            NotFoundError: If the assignment, its schedule, or the role is not found.
            BadRequestError: If the role belongs to a different department.
        """
        log = self.logger.bind(
            method="update_assignment_role",
            assignment_id=str(assignment_id),
            department_role_id=str(department_role_id) if department_role_id else None,
        )

        assignment = self.schedule_repo.get_assignment_by_id(assignment_id)
        if not assignment:
            log.warning("assignment_not_found")
            raise NotFoundError(f"Assignment {assignment_id} not found")

        if department_role_id is not None:
            schedule = self.schedule_repo.get_by_id(assignment.schedule_id)
            if not schedule:
                log.warning("schedule_not_found", schedule_id=str(assignment.schedule_id))
                raise NotFoundError(f"Schedule {assignment.schedule_id} not found")

            role = self.department_role_repo.get_by_id(department_role_id)
            if not role:
                log.warning("role_not_found")
                raise NotFoundError(f"Department role {department_role_id} not found")
            if role.department_id != schedule.department_id:
                log.warning("role_department_mismatch", role_department_id=str(role.department_id))
                raise BadRequestError("Role does not belong to the schedule's department")

        updated = self.schedule_repo.update_assignment_role(assignment_id, department_role_id)
        if not updated:
            log.warning("assignment_not_found")
            raise NotFoundError(f"Assignment {assignment_id} not found")
        log.info("assignment_role_updated")
        return updated

    # ----------------------------------------------------------------
    # Editing a generated rota
    #
    # A generated rota is almost right and then somebody pulls out. Until these three
    # methods the only repair was to delete the schedule and regenerate it, which throws
    # away every manual correction on it and re-texts the whole team.
    #
    # The shared stance: an edit that makes the rota *worse* is still allowed, with a
    # warning. A head recording what has actually happened must be able to, and refusing
    # leaves the rota saying something untrue — the same line `worker_leave` already takes,
    # where clashes are reported rather than enforced.
    # ----------------------------------------------------------------

    def get_assignable_workers(self, schedule_id: UUID) -> list[AssignableWorker]:
        """Everyone who may still be added to this rota, each with the subteam they would fill.

        Resolved through `_resolve_scope_groups` — the same call `_eligible_worker` checks
        against and generation staffs from — so the picker offers exactly the people an add
        would accept. Working it out on the frontend instead would mean a second copy of
        `_scope_of` and the department-only rule in JavaScript, which would drift: a
        DEPARTMENT_ONLY rota excludes everybody who is in a subteam, and a list that shows
        them anyway is a list of names that 400.

        Anyone already on the rota is left out, so the result doubles as the swap candidates:
        you cannot swap somebody for a person already serving that date.

        Args:
            schedule_id: The rota being edited.

        Returns:
            list[AssignableWorker]: Candidates in group order — subteams by name, then the
                                    department-only roster.

        Raises:
            NotFoundError: If the schedule or its department does not exist.
        """
        schedule = self._require_schedule(schedule_id)
        taken = {a.worker_id for a in schedule.schedule_assignments}
        groups = self._resolve_scope_groups(schedule.department_id, _scope_of(schedule), schedule.subteam_id)
        return [
            AssignableWorker(worker=worker, subteam=group.subteam)
            for group in groups
            for worker in group.workers
            if worker.id not in taken
        ]

    def add_assignment(self, schedule_id: UUID, worker_id: UUID) -> ScheduleEditResult:
        """Put another worker on a generated rota.

        Their subteam and role come from their standing membership, exactly as generation
        resolves them — a head picks a person, not a slot, so they cannot accidentally file a
        Discovery worker under Seekers.

        Args:
            schedule_id: The rota to add to.
            worker_id: The worker to add.

        Returns:
            ScheduleEditResult: The re-read schedule, and anything the head should know.

        Raises:
            NotFoundError: If the schedule or the worker does not exist.
            BadRequestError: If the worker is not an active member of the schedule's scope.
            ConflictError: If they are already on it, or it is already at its maximum.
        """
        log = self.logger.bind(method="add_assignment", schedule_id=str(schedule_id), worker_id=str(worker_id))
        schedule = self._require_schedule(schedule_id)

        if any(a.worker_id == worker_id for a in schedule.schedule_assignments):
            raise ConflictError("That worker is already on this rota.")
        # Judged against the band frozen on the row, which is the number every screen shows.
        # Re-deriving the department's current maximum would refuse an add at a figure nothing
        # on screen names; a rota planned for four is full at four however the department has
        # been reconfigured since. A row predating the band has no ceiling to enforce.
        if schedule.max_workers is not None and len(schedule.schedule_assignments) >= schedule.max_workers:
            raise ConflictError(
                f"This rota is already at its maximum of {schedule.max_workers}. "
                f"Take somebody off before adding another."
            )

        worker, subteam_id = self._eligible_worker(schedule, worker_id)
        role = self._resolve_worker_roles([worker_id], schedule.department_id).get(worker_id)

        try:
            assignment = self.schedule_repo.create_assignment(
                {
                    q.AssignmentColumns.SCHEDULE_ID: str(schedule_id),
                    q.AssignmentColumns.WORKER_ID: str(worker_id),
                    q.AssignmentColumns.SUBTEAM_ID: str(subteam_id) if subteam_id else None,
                    q.AssignmentColumns.DEPARTMENT_ROLE_ID: str(role.id) if role else None,
                }
            )
        except APIError as error:
            # unique (schedule_id, worker_id). The pre-check above catches this in every
            # ordinary case; this is the backstop for two heads editing the same rota at once.
            if error.code == UNIQUE_VIOLATION:
                raise ConflictError("That worker is already on this rota.") from error
            raise

        warnings = self._clash_warnings(worker, schedule)
        warnings += self._announce_assignment(assignment.id, worker, schedule)
        log.info("assignment_added", assignment_id=str(assignment.id), warnings=len(warnings))
        return ScheduleEditResult(schedule=self._require_schedule(schedule_id), warnings=warnings)

    def replace_assignment_worker(self, assignment_id: UUID, worker_id: UUID) -> ScheduleEditResult:
        """Swap one worker out of a duty and another in.

        Both people are texted: the one coming off is told they are no longer scheduled, the
        one going on gets the ordinary "you have been scheduled" notice. A swap is the one edit
        where saying nothing leaves two people with the wrong idea.

        Args:
            assignment_id: The duty to hand over.
            worker_id: The worker taking it on.

        Returns:
            ScheduleEditResult: The re-read schedule, and anything the head should know.

        Raises:
            NotFoundError: If the assignment, its schedule, or the incoming worker is missing.
            BadRequestError: If the incoming worker is not an active member of the scope.
            ConflictError: If they are already on this rota.
        """
        log = self.logger.bind(
            method="replace_assignment_worker", assignment_id=str(assignment_id), worker_id=str(worker_id)
        )
        assignment = self.schedule_repo.get_assignment_with_schedule(assignment_id)
        if not assignment:
            log.warning("assignment_not_found")
            raise NotFoundError(f"Assignment {assignment_id} not found")

        outgoing = assignment.workers
        if worker_id == assignment.worker_id:
            raise ConflictError("That worker already holds this duty.")

        schedule = self._require_schedule(assignment.schedule_id)
        if any(a.worker_id == worker_id for a in schedule.schedule_assignments):
            raise ConflictError("That worker is already on this rota.")

        incoming, subteam_id = self._eligible_worker(schedule, worker_id)
        role = self._resolve_worker_roles([worker_id], schedule.department_id).get(worker_id)

        try:
            self.schedule_repo.reassign_assignment(assignment_id, worker_id, subteam_id, role.id if role else None)
        except APIError as error:
            if error.code == UNIQUE_VIOLATION:
                raise ConflictError("That worker is already on this rota.") from error
            raise

        warnings = self._clash_warnings(incoming, schedule)
        warnings += self._announce_assignment(assignment_id, incoming, schedule)
        if outgoing:
            warnings += self._announce_cancellation(outgoing, schedule)
        log.info("assignment_worker_replaced", warnings=len(warnings))
        return ScheduleEditResult(schedule=self._require_schedule(schedule.id), warnings=warnings)

    def remove_assignment(self, assignment_id: UUID) -> ScheduleEditResult:
        """Take a worker off a rota and tell them.

        **Never refuses.** Dropping below the minimum is a warning, not an error: a head
        recording that somebody has pulled out must be able to, and a rota that still lists
        them is worse than a short one that is true.

        Args:
            assignment_id: The duty to remove.

        Returns:
            ScheduleEditResult: The re-read schedule, and anything the head should know.

        Raises:
            NotFoundError: If the assignment or its schedule does not exist.
        """
        log = self.logger.bind(method="remove_assignment", assignment_id=str(assignment_id))
        assignment = self.schedule_repo.get_assignment_with_schedule(assignment_id)
        if not assignment:
            log.warning("assignment_not_found")
            raise NotFoundError(f"Assignment {assignment_id} not found")

        schedule = self._require_schedule(assignment.schedule_id)
        worker = assignment.workers

        self.schedule_repo.delete_assignment(assignment_id)

        warnings: list[str] = []
        remaining = len([a for a in schedule.schedule_assignments if a.id != assignment_id])
        if schedule.min_workers is not None and remaining < schedule.min_workers:
            short = schedule.min_workers - remaining
            warnings.append(f"This rota is now {short} short of the {schedule.min_workers} it was planned for.")
        if worker:
            warnings += self._announce_cancellation(worker, schedule)
        log.info("assignment_removed", remaining=remaining, warnings=len(warnings))
        return ScheduleEditResult(schedule=self._require_schedule(schedule.id), warnings=warnings)

    # ----------------------------------------------------------------
    # Edit helpers
    # ----------------------------------------------------------------

    def _require_schedule(self, schedule_id: UUID) -> ScheduleResponse:
        """The schedule with its assignments, or `NotFoundError`.

        Read again after every write: the caller replaces its whole copy of the schedule, and
        a PostgREST write returns base-table columns with none of the embeds it renders.
        """
        schedule = self.schedule_repo.get_with_assignments(schedule_id)
        if not schedule:
            raise NotFoundError(f"Schedule {schedule_id} not found")
        return schedule

    def _eligible_worker(self, schedule: ScheduleResponse, worker_id: UUID) -> tuple[Worker, UUID | None]:
        """Check a worker may serve on this rota, and say which subteam they would fill.

        Eligibility is resolved through `_resolve_scope_groups` rather than a fresh membership
        query, so "who may be on this rota" has exactly one definition and an edit can never
        admit somebody generation would have excluded.

        Args:
            schedule: The rota being edited.
            worker_id: The worker being added or swapped in.

        Returns:
            tuple[Worker, UUID | None]: The worker, and the subteam to stamp on their row.

        Raises:
            NotFoundError: If no worker has that id.
            BadRequestError: If they are not an active member of the schedule's scope.
        """
        worker_record = self.worker_repo.get_by_id(worker_id)
        if not worker_record:
            raise NotFoundError(f"Worker {worker_id} not found")

        scope = _scope_of(schedule)
        groups = self._resolve_scope_groups(schedule.department_id, scope, schedule.subteam_id)
        for group in groups:
            for candidate in group.workers:
                if candidate.id == worker_id:
                    return candidate, group.subteam.id if group.subteam else None

        name = f"{worker_record.first_name} {worker_record.last_name}".strip()
        raise BadRequestError(f"{name} is not an active member of this {_scope_description(scope)}.")

    def _clash_warnings(self, worker: Worker, schedule: ScheduleResponse) -> list[str]:
        """Everything true of this worker on this date that a head would want to know.

        Reported, never enforced. A head moving somebody onto a date they marked off is
        usually doing it having already spoken to them, and the app is not in a position to
        overrule that conversation.
        """
        name = f"{worker.first_name} {worker.last_name}".strip()
        when = schedule.scheduled_date.strftime("%-d %B")
        warnings: list[str] = []

        blocked = self._build_unavailability_map(
            [worker.id], [schedule.scheduled_date], schedule.scheduled_date, schedule.scheduled_date
        )
        if worker.id in blocked.get(schedule.scheduled_date, set()):
            # Leave and "cannot serve" are unioned upstream, so this cannot tell them apart.
            warnings.append(f"{name} is marked unavailable or on leave on {when}.")

        # Safe without excluding this schedule: both callers have already established that the
        # worker is not on it, so any hit on the date is a different rota.
        if worker.id in self.schedule_repo.get_workers_scheduled_on_date(schedule.scheduled_date):
            warnings.append(f"{name} is already on another rota on {when}.")
        return warnings

    def _announce_assignment(self, assignment_id: UUID, worker: Worker, schedule: ScheduleResponse) -> list[str]:
        """Text a newly added worker straight away, and mark the notice as sent.

        The sweep would find this row on its own — `notice_sent_at` is NULL on a fresh or
        reassigned assignment — but only within `notice_interval_minutes`, and the head is
        standing in front of both people now. On a send failure the marker is deliberately
        left NULL so the sweep retries; that is why this raises nothing and warns about
        nothing except the one case retrying cannot fix.
        """
        name = f"{worker.first_name} {worker.last_name}".strip()
        if not worker.phone:
            return [f"{name} has no phone number, so they have not been told."]

        sent = self.sms_service.send_assignment_notice(
            to=worker.phone,
            worker_name=name,
            duties=[(self._department_name(schedule.department_id), _describe_when(schedule))],
        )
        if not sent:
            self.logger.warning("assignment_notice_failed_will_retry", assignment_id=str(assignment_id))
            return []
        self.schedule_repo.mark_notice_sent([assignment_id])
        return []

    def _announce_cancellation(self, worker: WorkerResponse | Worker, schedule: ScheduleResponse) -> list[str]:
        """Tell a worker they are off a date.

        **This one has no safety net.** The row is gone, so there is nothing for a sweep to
        find and retry; a failure here means the worker is never told by the app at all. Hence
        the warning handed back to the head rather than a log line nobody reads.
        """
        name = f"{worker.first_name} {worker.last_name}".strip()
        if not worker.phone:
            return [f"{name} has no phone number, so they have not been told."]

        sent = self.sms_service.send_assignment_cancelled(
            to=worker.phone,
            worker_name=name,
            department_name=self._department_name(schedule.department_id),
            when=_describe_when(schedule),
        )
        if not sent:
            self.logger.error("assignment_cancellation_failed", worker_id=str(worker.id))
            return [f"Could not text {name}. Let them know another way."]
        return []

    def _department_name(self, department_id: UUID) -> str:
        """The department's name for a message, or "" if it cannot be resolved.

        Blank rather than raising: the department is context on the text, not the text itself,
        and `SMSService` drops the framing when it sees an empty string.
        """
        department = self.department_repo.get_by_id(department_id)
        return department.name if department else ""

    def delete_schedule(self, schedule_id: UUID) -> None:
        log = self.logger.bind(method="delete_schedule", schedule_id=str(schedule_id))
        self.schedule_repo.delete_assignments_for_schedule(schedule_id)
        self.schedule_repo.delete(schedule_id)
        log.info("schedule_deleted")

    # ----------------------------------------------------------------
    # Monthly generation
    # ----------------------------------------------------------------

    def preview_monthly_schedule(self, data: MonthlySchedulePreviewRequest) -> MonthlySchedulePreview:
        """Plan a whole month without writing anything.

        Expands the requested weekdays into concrete dates, preloads all planning state in
        a fixed number of queries, and returns the proposed rota for the HOD to review.

        Args:
            data: Department, scope, month, weekdays and the shared schedule fields.

        Returns:
            MonthlySchedulePreview: One entry per candidate date, each holding a group per
                                   subteam (plus one for un-subteamed workers) with its
                                   assignments, alternates, and an outcome status.

        Raises:
            NotFoundError: If the department or subteam does not exist.
            BadRequestError: If the scope has no eligible workers at all.
        """
        log = self.logger.bind(
            method="preview_monthly_schedule",
            department_id=str(data.department_id),
            scope=data.scope.value,
            year=data.year,
            month=data.month,
        )
        log.info("monthly_preview_started")

        groups = self._resolve_scope_groups(data.department_id, data.scope, data.subteam_id)
        if not any(g.workers for g in groups):
            raise BadRequestError(f"No workers found for this {_scope_description(data.scope)}")

        dates = _dates_in_month(data.year, data.month, data.days_of_week)
        month_start = date(data.year, data.month, 1)
        month_end = _last_day_of_month(data.year, data.month)

        ctx = self._build_plan_context(
            groups=groups,
            department_id=data.department_id,
            scope=data.scope,
            subteam_id=data.subteam_id,
            dates=dates,
            month_start=month_start,
            month_end=month_end,
        )

        plans = plan_month(dates, ctx)

        # Resolve display data once for every worker who could appear in the plan.
        all_workers = [w for g in groups for w in g.workers]
        workers_by_id = {w.id: w for w in all_workers}
        roles = self._resolve_worker_roles(list(workers_by_id), data.department_id)
        subteam_by_key = {g.key: g.subteam for g in groups}

        def to_worker(worker_id: UUID) -> WorkerResponse:
            return WorkerResponse(**workers_by_id[worker_id].model_dump())

        log.info("monthly_preview_completed", dates=len(plans), groups=len(groups))
        return MonthlySchedulePreview(
            year=data.year,
            month=data.month,
            min_workers=sum(g.min_workers for g in groups),
            max_workers=sum(g.max_workers for g in groups),
            dates=[
                DatePlan(
                    scheduled_date=plan.scheduled_date,
                    status=plan.status,
                    message=plan.message,
                    groups=[
                        PlannedGroup(
                            subteam=subteam_by_key.get(group.key),
                            min_workers=group.min_workers,
                            max_workers=group.max_workers,
                            status=group.status,
                            assignments=[
                                PlannedAssignment(
                                    worker=to_worker(wid),
                                    department_role=roles.get(wid),
                                    subteam_id=(subteam.id if (subteam := subteam_by_key.get(group.key)) else None),
                                )
                                for wid in group.selected
                                if wid in workers_by_id
                            ],
                            alternates=[to_worker(wid) for wid in group.alternates if wid in workers_by_id],
                            message=group.message,
                        )
                        for group in plan.groups
                    ],
                )
                for plan in plans
            ],
        )

    def commit_monthly_schedule(self, data: MonthlyScheduleCommitRequest, created_by: str) -> MonthlyScheduleResult:
        """Persist the month the HOD approved.

        Takes the exact worker selection from the reviewed preview rather than re-planning,
        so manual swaps survive. Dates that gained a schedule since the preview are skipped
        rather than failing the run.

        Args:
            data: The shared schedule fields plus the approved per-date worker selection.
            created_by: Email of the requesting user, recorded as the schedule creator.

        Returns:
            MonthlyScheduleResult: Created schedules and any dates that were skipped.

        Raises:
            NotFoundError: If the department, subteam, or requesting user does not exist.
            BadRequestError: If a selected worker is not eligible for the scope.
            ConflictError: If every requested date already has a schedule.
        """
        log = self.logger.bind(
            method="commit_monthly_schedule",
            department_id=str(data.department_id),
            scope=data.scope.value,
            dates=len(data.dates),
        )
        log.info("monthly_commit_started")

        # Validates the department/subteam exist before anything is written, and tells us
        # which subteam each worker fills.
        groups = self._resolve_scope_groups(data.department_id, data.scope, data.subteam_id)
        subteam_by_worker: dict[UUID, UUID | None] = {
            w.id: (group.subteam.id if group.subteam else None) for group in groups for w in group.workers
        }
        eligible = set(subteam_by_worker)

        requested = sorted(d.scheduled_date for d in data.dates)
        existing_dates = self._existing_schedule_dates(
            data.department_id, data.scope, data.subteam_id, requested[0], requested[-1]
        )

        created_by_user = self.worker_repo.get_by_email(created_by)
        if not created_by_user:
            raise NotFoundError(f"User with email {created_by} not found")

        schedule_subteam_id = str(data.subteam_id) if data.scope == ScopeType.SUBTEAM else None

        skipped: list[SkippedDate] = []
        to_create: list[DateSelection] = []
        for selection in sorted(data.dates, key=lambda d: d.scheduled_date):
            if selection.scheduled_date in existing_dates:
                skipped.append(
                    SkippedDate(
                        scheduled_date=selection.scheduled_date,
                        reason="A schedule already exists for this date.",
                    )
                )
                continue

            unknown = [wid for wid in selection.worker_ids if wid not in eligible]
            if unknown:
                raise BadRequestError(
                    f"Worker {unknown[0]} is not eligible for this {_scope_description(data.scope)} "
                    f"(date {selection.scheduled_date.isoformat()})"
                )
            to_create.append(selection)

        if not to_create:
            raise ConflictError("Every requested date already has a schedule. Delete the existing ones to regenerate.")

        selected_ids = {wid for s in to_create for wid in s.worker_ids}
        roles = self._resolve_worker_roles(list(selected_ids), data.department_id)

        schedule_rows = [
            {
                q.Columns.DEPARTMENT_ID: str(data.department_id),
                q.Columns.SUBTEAM_ID: schedule_subteam_id,
                q.Columns.TITLE: data.title,
                q.Columns.SCHEDULED_DATE: selection.scheduled_date.isoformat(),
                q.Columns.START_TIME: data.start_time.isoformat(),
                q.Columns.END_TIME: data.end_time.isoformat(),
                q.Columns.NOTES: data.notes,
                q.Columns.REMINDER_DAYS_BEFORE: data.reminder_days_before,
                q.Columns.MIN_WORKERS: sum(g.min_workers for g in groups),
                q.Columns.MAX_WORKERS: sum(g.max_workers for g in groups),
                q.Columns.CREATED_BY: str(created_by_user.id),
            }
            for selection in to_create
        ]

        try:
            created_schedules = self.schedule_repo.bulk_create_schedules(schedule_rows)
        except APIError as exc:
            # The partial unique indexes on (department_id, scheduled_date, subteam_id)
            # catch a race between preview and commit that the date check above missed.
            if exc.code == UNIQUE_VIOLATION:
                raise ConflictError(
                    "A schedule was created for one of these dates while you were reviewing. "
                    "Re-run the preview and try again."
                ) from exc
            raise

        schedule_by_date = {s.scheduled_date: s for s in created_schedules}
        assignments = [
            {
                "schedule_id": str(schedule_by_date[selection.scheduled_date].id),
                "worker_id": str(worker_id),
                "subteam_id": _subteam_for_assignment(subteam_by_worker, worker_id, schedule_subteam_id),
                "department_role_id": str(roles[worker_id].id) if roles.get(worker_id) else None,
            }
            for selection in to_create
            if selection.scheduled_date in schedule_by_date
            for worker_id in selection.worker_ids
        ]

        try:
            self.schedule_repo.bulk_create_assignments(assignments)
        except Exception:
            # No transaction spans the two inserts — undo the schedules so a failed
            # commit does not leave a month of empty rotas behind.
            log.error("monthly_commit_assignments_failed_rolling_back", schedules=len(created_schedules))
            self.schedule_repo.delete_schedules([s.id for s in created_schedules])
            raise

        result_schedules = [
            full for s in created_schedules if (full := self.schedule_repo.get_with_assignments(s.id)) is not None
        ]

        log.info(
            "monthly_commit_completed",
            created=len(result_schedules),
            skipped=len(skipped),
            assignments=len(assignments),
        )
        return MonthlyScheduleResult(created=result_schedules, skipped=skipped)

    # ----------------------------------------------------------------
    # Private helpers
    # ----------------------------------------------------------------

    def _resolve_scope_groups(self, department_id: UUID, scope: ScopeType, subteam_id: UUID | None) -> list[ScopeGroup]:
        """Resolve the rosters to staff, each with its own staffing band.

        A department-wide schedule is not one pool sharing the department's band — each
        subteam has to be staffed to its own, so Children's Ministry fields four Seekers,
        three Discovery, and so on. That means one group per subteam that has members, plus
        one for workers in no subteam. Subteam-scoped and department-only schedules resolve
        to a single group.

        Args:
            department_id: The department being scheduled.
            scope: Which workers the schedule covers.
            subteam_id: Required when scope is SUBTEAM, None otherwise.

        Returns:
            list[ScopeGroup]: Groups in a stable order — subteams by name, then the
                             department-only roster last. Groups with no members are
                             omitted, except the sole group of a single-group scope.

        Raises:
            NotFoundError: If the department or the named subteam does not exist.
        """
        department = self.department_repo.get_by_id(department_id)
        if not department:
            raise NotFoundError(f"Department {department_id} not found")

        if scope == ScopeType.SUBTEAM:
            # Type assertion: validator ensures subteam_id is not None when scope is SUBTEAM
            assert subteam_id is not None
            subteam = self.subteam_repo.get_by_id(subteam_id)
            if not subteam:
                raise NotFoundError(f"Subteam {subteam_id} not found")
            members = self.subteam_repo.get_with_workers(subteam_id)
            workers = [w.worker for w in members if w.worker and w.worker.is_active] if members else []
            minimum, maximum = _staffing_band(subteam, department)
            return [ScopeGroup(subteam=subteam, min_workers=minimum, max_workers=maximum, workers=workers)]

        if scope == ScopeType.DEPARTMENT_ONLY:
            response = self.worker_repo.get_department_only_workers(department_id)
            minimum, maximum = _staffing_band(None, department)
            return [ScopeGroup(subteam=None, min_workers=minimum, max_workers=maximum, workers=_active(response))]

        # ScopeType.DEPARTMENT_ALL — one group per subteam, plus the un-subteamed workers.
        grouped = self.worker_repo.get_workers_by_department_grouped_by_subteam(department_id)
        subteams = sorted(self.subteam_repo.get_by_department(department_id), key=lambda s: s.name)

        groups: list[ScopeGroup] = []
        for subteam in subteams:
            subteam_workers = _active(grouped.get(subteam.id, []))
            if not subteam_workers:
                continue
            minimum, maximum = _staffing_band(subteam, department)
            groups.append(
                ScopeGroup(subteam=subteam, min_workers=minimum, max_workers=maximum, workers=subteam_workers)
            )

        department_only = _active(grouped.get(None, []))
        if department_only:
            minimum, maximum = _staffing_band(None, department)
            groups.append(ScopeGroup(subteam=None, min_workers=minimum, max_workers=maximum, workers=department_only))

        return groups

    def _build_plan_context(
        self,
        groups: list[ScopeGroup],
        department_id: UUID,
        scope: ScopeType,
        subteam_id: UUID | None,
        dates: list[date],
        month_start: date,
        month_end: date,
    ) -> PlanContext:
        """Preload every input `plan_month` needs, in a fixed number of queries.

        Deliberately batched: the single-date path costs two availability queries and a
        full history fetch per worker, which multiplied by a month's dates would be
        hundreds of round-trips against a capped connection pool.
        """
        plan_groups = [
            GroupContext(key=g.key, workers=g.workers, min_workers=g.min_workers, max_workers=g.max_workers)
            for g in groups
        ]
        worker_ids = [w.id for g in groups for w in g.workers]
        if not dates:
            return PlanContext(groups=plan_groups)

        range_start, range_end = min(dates), max(dates)

        unavailable = self._build_unavailability_map(worker_ids, dates, range_start, range_end)
        already_scheduled = self.schedule_repo.get_workers_scheduled_in_range(range_start, range_end)
        existing_dates = self._existing_schedule_dates(department_id, scope, subteam_id, range_start, range_end)

        # Round-robin history is scoped the same way the single-date path scopes it:
        # a subteam schedule only counts subteam assignments, a department schedule only
        # counts department-level ones.
        scope_subteam_id = subteam_id if scope == ScopeType.SUBTEAM else None
        history = self.schedule_repo.get_assignment_history_for_workers(worker_ids, department_id)

        last_assigned: dict[UUID, date] = {}
        month_count: dict[UUID, int] = {}
        for assignment in history:
            schedule = assignment.schedules
            if schedule is None or schedule.scheduled_date is None:
                continue
            if schedule.subteam_id != scope_subteam_id:
                continue
            worker_id = assignment.worker_id
            assigned_date = schedule.scheduled_date
            if assigned_date > last_assigned.get(worker_id, date.min):
                last_assigned[worker_id] = assigned_date
            if month_start <= assigned_date <= month_end:
                month_count[worker_id] = month_count.get(worker_id, 0) + 1

        return PlanContext(
            groups=plan_groups,
            last_assigned=last_assigned,
            month_count=month_count,
            unavailable=unavailable,
            already_scheduled=already_scheduled,
            existing_dates=existing_dates,
        )

    def _build_unavailability_map(
        self, worker_ids: list[UUID], dates: list[date], range_start: date, range_end: date
    ) -> dict[date, set[UUID]]:
        """Resolve who cannot be picked on each date, from two batched fetches.

        Mirrors `_is_worker_available`: a specific-date override beats the recurring
        weekly setting, and a worker with no record at all is available.

        Leave is unioned in here rather than given its own channel so the planner stays
        unchanged and pure — to it, a worker away on a date is simply one who cannot be
        picked. The cost is that a plan's "3 unavailable" message does not separate the two.
        """
        records = self.availability_repo.get_for_workers(worker_ids, range_start, range_end)
        leave_records = self.leave_repo.get_for_workers(worker_ids, range_start, range_end)

        recurring: dict[tuple[UUID, int], bool] = {}
        specific: dict[tuple[UUID, date], bool] = {}
        for record in records:
            if record.availability_type == AvailabilityType.SPECIFIC_DATE and record.specific_date is not None:
                specific[(record.worker_id, record.specific_date)] = record.is_available
            elif record.availability_type == AvailabilityType.RECURRING and record.day_of_week is not None:
                recurring[(record.worker_id, record.day_of_week.to_number())] = record.is_available

        unavailable: dict[date, set[UUID]] = {}
        for scheduled_date in dates:
            # DB stores 0=Sunday; Python's weekday() is 0=Monday.
            db_day_of_week = (scheduled_date.weekday() + 1) % 7
            blocked = {
                worker_id
                for worker_id in worker_ids
                if not specific.get(
                    (worker_id, scheduled_date),
                    recurring.get((worker_id, db_day_of_week), True),
                )
            }
            blocked |= {leave.worker_id for leave in leave_records if leave.covers(scheduled_date)}
            if blocked:
                unavailable[scheduled_date] = blocked
        return unavailable

    def _existing_schedule_dates(
        self,
        department_id: UUID,
        scope: ScopeType,
        subteam_id: UUID | None,
        range_start: date,
        range_end: date,
    ) -> set[date]:
        """Dates in range that already carry a schedule for this department/scope.

        DEPARTMENT_ONLY and DEPARTMENT_ALL share the subteam_id IS NULL key, matching
        the single-date duplicate check.
        """
        check_subteam_id = subteam_id if scope == ScopeType.SUBTEAM else None
        existing = self.schedule_repo.get_by_department(department_id, range_start, range_end)
        return {s.scheduled_date for s in existing if s.subteam_id == check_subteam_id}

    def _resolve_worker_roles(self, worker_ids: list[UUID], department_id: UUID) -> dict[UUID, DepartmentRoleResponse]:
        """Each worker's standing department role, used to auto-fill assignments."""
        roles: dict[UUID, DepartmentRoleResponse] = {}
        for worker_id in worker_ids:
            role = self.department_role_repo.get_role_for_worker_in_department(worker_id, department_id)
            if role:
                roles[worker_id] = role
        return roles
