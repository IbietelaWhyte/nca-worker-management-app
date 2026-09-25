"""Pure monthly-rota planning.

This module holds no I/O. Everything it needs is preloaded into a `PlanContext` by
`ScheduleService`, which lets the whole month be planned in memory and keeps the
fairness rules testable without mocking a single repository.

Two things shape the design:

- **Dates are planned together**, walking ascending and carrying each pick forward into
  the next date's ordering. Without that carry-forward every date would sort from the
  same starting state and the same handful of workers would win every week.
- **A date is filled group by group.** A department-wide schedule has to staff each
  subteam to its own band — Seekers needs its four people and Discovery its three — so
  a group is planned against its own roster and its own band, and fairness rotates
  within it. A subteam-scoped or department-only schedule is simply the one-group case.
- **A group has a range, not a quota.** `max_workers` is how many to take when the
  people are there; `min_workers` is the only figure that judges the outcome. A group
  that fields three against a band of 2-4 is planned, not short.
- **Every date belongs to a *kind*, and fairness is measured within a kind.** The ordinary
  Sundays are one kind; each named special service is its own. To a single least-served-first
  sort one Sunday looks exactly like the next, so the same few names land on every big
  service — and a single tally lumping all specials together is barely better, because it
  happily pays somebody's six Thanksgivings off against somebody else's three Christmas
  services and calls that level. A count and a recency are kept per kind instead.
- **A run of consecutive turns at one kind pushes you behind everyone on a shorter run.**
  The counts alone say how *many* turns each person gets, never how they are spaced, so a
  roster can come out perfectly balanced with one person on four Thanksgivings in a row
  and then nothing for three months. The streak is a sort term and not a filter, so it
  reorders the queue without ever refusing to staff a date: where there are more slots than
  fresh people, the shortest runs come back up. Eligibility is untouched.

  It counts *consecutive* turns rather than just flagging the last one, because flagging
  cannot tell somebody on their second service running from somebody on their fifth. Where
  a group is small enough that somebody must repeat — four slots filled from seven people
  means at least one every time — that distinction is the whole difference between the
  repeat rotating and one person absorbing all of them.
"""

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from app.schemas.schedules.models import DatePlanStatus
from app.schemas.workers.models import Worker

# The kind of an ordinary service. A special date's kind is its name, so the two live in
# one keyspace and neither the tallies nor the streaks need to branch on which it is.
ORDINARY = ""


@dataclass
class GroupContext:
    """One roster to staff on each date, with its own quota.

    Attributes:
        key: Stable identity for the group — a subteam id as a string, or "" for the
            department-only roster. Used to match results back to a subteam.
        workers: Eligible, active workers for this group.
        min_workers: The number below which this group cannot run. The only figure that
            judges an outcome — short of `max_workers` but at or above this one is
            fully planned, not understaffed.
        max_workers: Slots to fill when enough people are free. Never exceeded.
    """

    key: str
    workers: list[Worker]
    min_workers: int
    max_workers: int


@dataclass
class PlanContext:
    """Everything `plan_month` needs, preloaded.

    The tallies are keyed by worker and shared across groups; a worker belongs to at most
    one group, so there is no interference.

    Attributes:
        groups: The rosters to staff, each with its own quota.
        last_assigned: Worker -> most recent scheduled_date in scope, of any kind,
            `date.min` if never.
        month_count: Worker -> assignments already held in scope within the planned month.
            Deliberately windowed: it is what guarantees nobody serves twice in a month
            before everybody has served once.
        total_count: Worker -> assignments held in scope **all time**. The tie-break under
            both load terms, and the only one that survives a month boundary — without it
            the remainder of a month that does not divide evenly is forgotten every time
            `month_count` resets, and the drift compounds into whole services over a year.
        unavailable: Date -> workers who declared themselves unavailable then.
        already_scheduled: Date -> workers already booked anywhere in the org that day.
        existing_dates: Dates that already carry a schedule for this department/scope.
        special_dates: Date -> the name of the special service falling on it. The name is
            the kind, so two rules sharing a date share a tally only if they share a name.
        special_count: (worker, special service name) -> turns served at **that** service,
            all time. Not windowed to the month: a given special falls perhaps a dozen
            times a year, so a within-month count would be 0 for everybody and order
            nothing — which is exactly what used to happen to the ordinary tie-break on
            any first-Sunday rule, the commonest shape there is.
        last_served: (worker, kind) -> most recent date served of that kind, `date.min` if
            never. The spacing tie-break behind the streak.
        streak: (worker, kind) -> how many of that kind's most recent consecutive
            occurrences the worker served, counting back from the latest one and stopping
            at the first they missed. 0 means they sat the last one out, which is the
            front of the queue.
    """

    groups: list[GroupContext]
    last_assigned: dict[UUID, date] = field(default_factory=dict)
    month_count: dict[UUID, int] = field(default_factory=dict)
    total_count: dict[UUID, int] = field(default_factory=dict)
    unavailable: dict[date, set[UUID]] = field(default_factory=dict)
    already_scheduled: dict[date, set[UUID]] = field(default_factory=dict)
    existing_dates: set[date] = field(default_factory=set)
    special_dates: dict[date, str] = field(default_factory=dict)
    special_count: dict[tuple[UUID, str], int] = field(default_factory=dict)
    last_served: dict[tuple[UUID, str], date] = field(default_factory=dict)
    streak: dict[tuple[UUID, str], int] = field(default_factory=dict)


@dataclass
class _Tallies:
    """The running fairness state, carried date to date within one `plan_month` call.

    Bundled rather than passed as six parallel dictionaries: every one of them is read by
    the sort key and written by the pick, so they only ever travel together.
    """

    month_count: dict[UUID, int]
    total_count: dict[UUID, int]
    special_count: dict[tuple[UUID, str], int]
    last_served: dict[tuple[UUID, str], date]
    last_assigned: dict[UUID, date]
    streak: dict[tuple[UUID, str], int]


@dataclass
class GroupPlanResult:
    """One group's outcome on one date. Worker ids are in priority order."""

    key: str
    min_workers: int
    max_workers: int
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
    # Whether this date rotated on the special tally. Carried out so the preview can badge
    # it and the commit can stamp the schedule without re-resolving the rules.
    is_special: bool = False


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
    tallies = _Tallies(
        month_count=dict(ctx.month_count),
        total_count=dict(ctx.total_count),
        special_count=dict(ctx.special_count),
        last_served=dict(ctx.last_served),
        last_assigned=dict(ctx.last_assigned),
        streak=dict(ctx.streak),
    )
    already_scheduled = {d: set(ids) for d, ids in ctx.already_scheduled.items()}

    results: list[DatePlanResult] = []

    for scheduled_date in sorted(dates):
        kind = ctx.special_dates.get(scheduled_date, ORDINARY)
        is_special = kind != ORDINARY

        if scheduled_date in ctx.existing_dates:
            results.append(
                DatePlanResult(
                    scheduled_date=scheduled_date,
                    status=DatePlanStatus.SKIPPED_EXISTING,
                    message="A schedule already exists for this date.",
                    is_special=is_special,
                )
            )
            continue

        unavailable = ctx.unavailable.get(scheduled_date, set())
        booked = already_scheduled.setdefault(scheduled_date, set())

        group_results = [_plan_group(group, scheduled_date, kind, unavailable, booked, tallies) for group in ctx.groups]

        results.append(_aggregate(scheduled_date, group_results, is_special))

    return results


def _plan_group(
    group: GroupContext,
    scheduled_date: date,
    kind: str,
    unavailable: set[UUID],
    booked: set[UUID],
    tallies: _Tallies,
) -> GroupPlanResult:
    """Staff one group on one date, mutating the running fairness and booking state."""
    free = [w for w in group.workers if w.id not in unavailable and w.id not in booked]

    if not free:
        return GroupPlanResult(
            key=group.key,
            min_workers=group.min_workers,
            max_workers=group.max_workers,
            status=DatePlanStatus.SKIPPED_NO_WORKERS,
            message=_no_workers_message(group.workers, unavailable, booked),
        )

    free.sort(key=lambda w: _fairness_key(w, kind, tallies))

    # Fill to the ceiling when the people are there. The floor never limits the take —
    # it only judges the result afterwards.
    selected = free[: group.max_workers]
    alternates = free[group.max_workers :]

    # The streak is the one tally that moves for everybody, not just the picked: sitting a
    # service out is precisely what ends a run, and a worker left out because they were
    # unavailable has still not served it. Done before the picks below extend theirs.
    chosen = {w.id for w in selected}
    for worker in group.workers:
        if worker.id not in chosen:
            tallies.streak.pop((worker.id, kind), None)

    # Carry this group's picks forward so later dates — and later groups on this date —
    # see them. This is the entire balancing mechanism.
    for worker in selected:
        tallies.streak[(worker.id, kind)] = tallies.streak.get((worker.id, kind), 0) + 1
        tallies.month_count[worker.id] = tallies.month_count.get(worker.id, 0) + 1
        tallies.total_count[worker.id] = tallies.total_count.get(worker.id, 0) + 1
        if kind != ORDINARY:
            # Every counter, not just this service's. A big service is still a turn, so it
            # has to cost an ordinary one too — otherwise whoever draws the special date
            # gets a free extra Sunday.
            tallies.special_count[(worker.id, kind)] = tallies.special_count.get((worker.id, kind), 0) + 1
        tallies.last_served[(worker.id, kind)] = scheduled_date
        tallies.last_assigned[worker.id] = scheduled_date
        booked.add(worker.id)

    return GroupPlanResult(
        key=group.key,
        min_workers=group.min_workers,
        max_workers=group.max_workers,
        status=_group_status(len(selected), group),
        selected=[w.id for w in selected],
        alternates=[w.id for w in alternates],
        message=_staffing_message(len(selected), group),
    )


def _group_status(filled: int, group: GroupContext) -> DatePlanStatus:
    """UNDERSTAFFED is judged against the minimum alone.

    Short of the maximum is not a problem worth flagging: the maximum says how many to use
    when they are there, the minimum says the number below which the group cannot run. A
    band of 2-4 that fields 3 is planned.
    """
    return DatePlanStatus.UNDERSTAFFED if filled < group.min_workers else DatePlanStatus.PLANNED


def _staffing_message(filled: int, group: GroupContext) -> str | None:
    """Say what was filled, but only when it is worth saying.

    Below the floor is a problem and names the floor. Between the two is worth mentioning —
    a head may want to add somebody — but against the ceiling, so it does not read as a
    complaint. At the ceiling there is nothing to say.
    """
    if filled < group.min_workers:
        return f"Only {filled} of {group.min_workers} workers available."
    if filled < group.max_workers:
        return f"{filled} of {group.max_workers} slots filled."
    return None


def _aggregate(scheduled_date: date, groups: list[GroupPlanResult], is_special: bool = False) -> DatePlanResult:
    """Roll group outcomes up into the date's own status.

    A date is only PLANNED when every group reached its minimum; it is SKIPPED_NO_WORKERS
    only when no group could field anyone at all.
    """
    if groups and all(g.status == DatePlanStatus.SKIPPED_NO_WORKERS for g in groups):
        return DatePlanResult(
            scheduled_date=scheduled_date,
            status=DatePlanStatus.SKIPPED_NO_WORKERS,
            groups=groups,
            message="No workers available for this date.",
            is_special=is_special,
        )

    short = [g for g in groups if g.status != DatePlanStatus.PLANNED]
    if short:
        filled = sum(len(g.selected) for g in groups)
        # Minimums, not maximums: the date is only UNDERSTAFFED because a group fell below
        # its floor, so totalling ceilings here would contradict the per-group message.
        needed = sum(g.min_workers for g in groups)
        return DatePlanResult(
            scheduled_date=scheduled_date,
            status=DatePlanStatus.UNDERSTAFFED,
            groups=groups,
            message=f"{filled} of {needed} slots filled.",
            is_special=is_special,
        )

    return DatePlanResult(
        scheduled_date=scheduled_date, status=DatePlanStatus.PLANNED, groups=groups, is_special=is_special
    )


def _fairness_key(
    worker: Worker,
    kind: str,
    tallies: _Tallies,
) -> tuple[int, int, int, date, date, str]:
    """Shortest run first, then least-served, then longest-waiting — within this kind of date.

    Six terms, each earning its place:

    1. **How many of this kind they have served in a row.** Spacing, and the only term that
       is about *when* rather than *how many*. A balanced rota is not automatically a humane
       one: counts alone are equally happy with four Thanksgivings in a row followed by
       three months off. Anyone who sat the last one out leads at 0, and above that a
       shorter run outranks a longer one, so a monthly special hands round instead of
       settling on whoever is otherwise quietest — and somebody who served the last one
       gets to attend the next as a worshipper. It is a sort and not a filter, so where
       fewer people are fresh than the group needs the rest come straight back up and the
       date is still staffed.
    2. **The load for this kind.** On an ordinary date that is the month count, which is
       what guarantees nobody serves twice in a month before everybody has served once. On
       a special date it is the all-time count for *that named service*, so Thanksgiving
       balances against Thanksgiving. A single tally across all specials cannot do this: it
       reads six Thanksgivings and no Christmas as level with the reverse, and settles for
       somebody serving one big service every year and another never.
    3. **Turns overall, all time.** The tie-break under both, and the only term that
       outlives a month boundary. A month of four Sundays over seven people is sixteen
       slots and a remainder of two; without this the remainder is forgotten each time the
       month count resets, and a year of remainders is whole services of difference.
    4. **Longest since this kind**, so the queue behind the streak is still ordered by who
       has waited longest for *this* service rather than for any service.
    5. **Longest since anything**, which spaces across kinds — a special one week should
       not be followed by an ordinary the next while somebody else has had neither.
    6. The worker id, so a preview is stable and a re-plan of identical input is identical.

    `date.min` stands in for "never", which puts a worker new to the rota at the front.
    """
    load = (
        tallies.month_count.get(worker.id, 0) if kind == ORDINARY else tallies.special_count.get((worker.id, kind), 0)
    )
    return (
        tallies.streak.get((worker.id, kind), 0),
        load,
        tallies.total_count.get(worker.id, 0),
        tallies.last_served.get((worker.id, kind), date.min),
        tallies.last_assigned.get(worker.id, date.min),
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
