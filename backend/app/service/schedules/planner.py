"""Pure monthly-rota planning.

This module holds no I/O. Everything it needs is preloaded into a `PlanContext` by
`ScheduleService`, which lets the whole month be planned in memory and keeps the
fairness rules testable without mocking a single repository.

Two things shape the design:

- **Dates are planned together**, walking ascending and carrying each pick forward into
  the next date's ordering. Without that carry-forward every date would sort from the
  same starting state and the same handful of workers would win every week.
- **A date is filled group by group.** A department-wide schedule has to staff each
  subteam to its own `workers_per_slot` — Seekers needs its four people and Discovery
  its three — so a group is planned against its own roster and its own quota, and
  fairness rotates within it. A subteam-scoped or department-only schedule is simply
  the one-group case.
"""

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from app.schemas.schedules.models import DatePlanStatus
from app.schemas.workers.models import Worker


@dataclass
class GroupContext:
    """One roster to staff on each date, with its own quota.

    Attributes:
        key: Stable identity for the group — a subteam id as a string, or "" for the
            department-only roster. Used to match results back to a subteam.
        workers: Eligible, active workers for this group.
        workers_needed: Slots this group must fill on each date.
    """

    key: str
    workers: list[Worker]
    workers_needed: int


@dataclass
class PlanContext:
    """Everything `plan_month` needs, preloaded.

    `last_assigned` and `month_count` are keyed by worker and shared across groups; a
    worker belongs to at most one group, so there is no interference.

    Attributes:
        groups: The rosters to staff, each with its own quota.
        last_assigned: Worker -> most recent scheduled_date in scope, `date.min` if never.
        month_count: Worker -> assignments already held in scope within the planned month.
        unavailable: Date -> workers who declared themselves unavailable then.
        already_scheduled: Date -> workers already booked anywhere in the org that day.
        existing_dates: Dates that already carry a schedule for this department/scope.
    """

    groups: list[GroupContext]
    last_assigned: dict[UUID, date] = field(default_factory=dict)
    month_count: dict[UUID, int] = field(default_factory=dict)
    unavailable: dict[date, set[UUID]] = field(default_factory=dict)
    already_scheduled: dict[date, set[UUID]] = field(default_factory=dict)
    existing_dates: set[date] = field(default_factory=set)


@dataclass
class GroupPlanResult:
    """One group's outcome on one date. Worker ids are in priority order."""

    key: str
    workers_needed: int
    status: DatePlanStatus
    selected: list[UUID] = field(default_factory=list)
    alternates: list[UUID] = field(default_factory=list)
    message: str | None = None


@dataclass
class DatePlanResult:
    """One date's outcome, aggregated over its groups."""

    scheduled_date: date
    status: DatePlanStatus
    groups: list[GroupPlanResult] = field(default_factory=list)
    message: str | None = None


def plan_month(dates: list[date], ctx: PlanContext) -> list[DatePlanResult]:
    """Plan a whole month's rota, balancing turns across every date.

    A date that cannot be filled does not abort the month, and a group that comes up
    short does not abort the date — both come back with a non-PLANNED status and the
    rest is still planned. Partial success is the point: one holiday with nobody free
    must not cost the HOD the other four weeks.

    Args:
        dates: Target dates. Planned in ascending order regardless of input order.
        ctx: Preloaded planning state. Not mutated — working copies are taken.

    Returns:
        One result per date, in ascending date order.
    """
    # Work on copies so callers can re-plan from the same context (e.g. preview twice).
    month_count = dict(ctx.month_count)
    last_assigned = dict(ctx.last_assigned)
    already_scheduled = {d: set(ids) for d, ids in ctx.already_scheduled.items()}

    results: list[DatePlanResult] = []

    for scheduled_date in sorted(dates):
        if scheduled_date in ctx.existing_dates:
            results.append(
                DatePlanResult(
                    scheduled_date=scheduled_date,
                    status=DatePlanStatus.SKIPPED_EXISTING,
                    message="A schedule already exists for this date.",
                )
            )
            continue

        unavailable = ctx.unavailable.get(scheduled_date, set())
        booked = already_scheduled.setdefault(scheduled_date, set())

        group_results = [
            _plan_group(group, scheduled_date, unavailable, booked, month_count, last_assigned) for group in ctx.groups
        ]

        results.append(_aggregate(scheduled_date, group_results))

    return results


def _plan_group(
    group: GroupContext,
    scheduled_date: date,
    unavailable: set[UUID],
    booked: set[UUID],
    month_count: dict[UUID, int],
    last_assigned: dict[UUID, date],
) -> GroupPlanResult:
    """Staff one group on one date, mutating the running fairness and booking state."""
    free = [w for w in group.workers if w.id not in unavailable and w.id not in booked]

    if not free:
        return GroupPlanResult(
            key=group.key,
            workers_needed=group.workers_needed,
            status=DatePlanStatus.SKIPPED_NO_WORKERS,
            message=_no_workers_message(group.workers, unavailable, booked),
        )

    free.sort(key=lambda w: _fairness_key(w, month_count, last_assigned))

    selected = free[: group.workers_needed]
    alternates = free[group.workers_needed :]

    # Carry this group's picks forward so later dates — and later groups on this date —
    # see them. This is the entire balancing mechanism.
    for worker in selected:
        month_count[worker.id] = month_count.get(worker.id, 0) + 1
        last_assigned[worker.id] = scheduled_date
        booked.add(worker.id)

    understaffed = len(selected) < group.workers_needed
    return GroupPlanResult(
        key=group.key,
        workers_needed=group.workers_needed,
        status=DatePlanStatus.UNDERSTAFFED if understaffed else DatePlanStatus.PLANNED,
        selected=[w.id for w in selected],
        alternates=[w.id for w in alternates],
        message=(f"Only {len(selected)} of {group.workers_needed} workers available." if understaffed else None),
    )


def _aggregate(scheduled_date: date, groups: list[GroupPlanResult]) -> DatePlanResult:
    """Roll group outcomes up into the date's own status.

    A date is only PLANNED when every group is fully staffed; it is SKIPPED_NO_WORKERS
    only when no group could field anyone at all.
    """
    if groups and all(g.status == DatePlanStatus.SKIPPED_NO_WORKERS for g in groups):
        return DatePlanResult(
            scheduled_date=scheduled_date,
            status=DatePlanStatus.SKIPPED_NO_WORKERS,
            groups=groups,
            message="No workers available for this date.",
        )

    short = [g for g in groups if g.status != DatePlanStatus.PLANNED]
    if short:
        filled = sum(len(g.selected) for g in groups)
        needed = sum(g.workers_needed for g in groups)
        return DatePlanResult(
            scheduled_date=scheduled_date,
            status=DatePlanStatus.UNDERSTAFFED,
            groups=groups,
            message=f"{filled} of {needed} slots filled.",
        )

    return DatePlanResult(scheduled_date=scheduled_date, status=DatePlanStatus.PLANNED, groups=groups)


def _fairness_key(
    worker: Worker,
    month_count: dict[UUID, int],
    last_assigned: dict[UUID, date],
) -> tuple[int, date, str]:
    """Least-served first.

    Count comes first: it is what guarantees nobody serves twice in the month until
    everyone has served once. `last_assigned` then breaks ties using history from
    outside the planned month (`date.min` for a worker never assigned in scope, so they
    lead), and the worker id makes the ordering deterministic for a stable preview.
    """
    return (
        month_count.get(worker.id, 0),
        last_assigned.get(worker.id, date.min),
        str(worker.id),
    )


def _no_workers_message(workers: list[Worker], unavailable: set[UUID], booked: set[UUID]) -> str:
    """Explain why a group came up empty, counting only its own members."""
    ids = {w.id for w in workers}
    if not ids:
        return "This group has no workers."

    reasons = []
    blocked = len(ids & unavailable)
    if blocked:
        reasons.append(f"{blocked} unavailable")
    clashing = len((ids & booked) - unavailable)
    if clashing:
        reasons.append(f"{clashing} already scheduled")
    if not reasons:
        return "No workers available for this date."
    return f"No workers available for this date ({', '.join(reasons)})."
