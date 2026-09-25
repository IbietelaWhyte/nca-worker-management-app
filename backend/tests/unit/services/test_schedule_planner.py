"""Tests for the pure monthly planner.

`plan_month` does no I/O, so these need no mocks — every input is constructed directly.
"""

from collections import Counter
from datetime import date, timedelta

from app.schemas.schedules.models import DatePlanStatus
from app.service.schedules.planner import GroupContext, PlanContext, plan_month
from tests.unit.services.conftest import make_worker

# Four consecutive Sundays in March 2026.
SUNDAYS = [date(2026, 3, 1), date(2026, 3, 8), date(2026, 3, 15), date(2026, 3, 22)]

# The first Sunday of each month of 2026 — a year of a monthly special, and the shape that
# exposes spacing, since the counts alone cannot tell a hand-round from a run.
FIRST_SUNDAYS = [
    date(2026, month, 1) + timedelta(days=(6 - date(2026, month, 1).weekday()) % 7) for month in range(1, 13)
]

# A date's "kind" is the name of the special falling on it, so named services tally apart.
THANKSGIVING = "Thanksgiving Service"
CHRISTMAS = "Christmas Service"


def thanksgiving(*dates) -> dict:
    """`special_dates` for one or more dates of the same named service."""
    return {d: THANKSGIVING for d in dates}


def make_workers(count: int):
    return [make_worker(first_name=f"Worker{i}", email=f"worker{i}@example.com") for i in range(count)]


def one_group(workers, band, **kwargs) -> PlanContext:
    """A single-group context — the subteam-scoped / department-only shape.

    `band` is (min, max), or a bare int for a band of exactly N — which is how every group
    behaved before the minimum and maximum were split apart.
    """
    minimum, maximum = band if isinstance(band, tuple) else (band, band)
    return PlanContext(
        groups=[GroupContext(key="", workers=workers, min_workers=minimum, max_workers=maximum)], **kwargs
    )


def selected(plan, index: int = 0):
    """Worker ids picked for one group of a date plan."""
    return plan.groups[index].selected if plan.groups else []


def alternates(plan, index: int = 0):
    return plan.groups[index].alternates if plan.groups else []


class TestFairness:
    def test_spreads_turns_evenly_across_the_month(self):
        # 8 workers, 4 dates, 2 per slot -> every worker serves exactly once.
        workers = make_workers(8)
        ctx = one_group(workers, 2)

        plans = plan_month(SUNDAYS, ctx)

        assert [p.status for p in plans] == [DatePlanStatus.PLANNED] * 4
        served = [wid for plan in plans for wid in selected(plan)]
        assert len(served) == 8
        assert len(set(served)) == 8, "no worker should serve twice while others have not served"

    def test_nobody_serves_twice_before_everyone_serves_once(self):
        # 3 workers, 4 dates, 1 per slot -> the fourth date reuses the first worker only
        # after all three have had a turn.
        workers = make_workers(3)
        ctx = one_group(workers, 1)

        plans = plan_month(SUNDAYS, ctx)

        first_round = {selected(plans[0])[0], selected(plans[1])[0], selected(plans[2])[0]}
        assert len(first_round) == 3
        assert selected(plans[3])[0] in first_round

    def test_prior_history_orders_the_first_date(self):
        # The worker assigned longest ago leads; one never assigned leads outright.
        recent, older, never = make_workers(3)
        ctx = one_group(
            [recent, older, never],
            1,
            last_assigned={recent.id: date(2026, 2, 22), older.id: date(2026, 1, 4)},
        )

        plans = plan_month(SUNDAYS, ctx)

        assert selected(plans[0]) == [never.id]
        assert selected(plans[1]) == [older.id]
        assert selected(plans[2]) == [recent.id]

    def test_existing_assignments_this_month_count_against_a_worker(self):
        # `already_served` starts the month with one turn banked, so they go last.
        already_served, fresh = make_workers(2)
        ctx = one_group([already_served, fresh], 1, month_count={already_served.id: 1})

        plans = plan_month(SUNDAYS[:2], ctx)

        assert selected(plans[0]) == [fresh.id]
        assert selected(plans[1]) == [already_served.id]

    def test_is_deterministic_for_identical_input(self):
        workers = make_workers(5)
        ctx = one_group(workers, 2)

        first = plan_month(SUNDAYS, ctx)
        second = plan_month(SUNDAYS, ctx)

        assert [selected(p) for p in first] == [selected(p) for p in second]

    def test_does_not_mutate_the_context(self):
        workers = make_workers(4)
        ctx = one_group(workers, 2, month_count={}, last_assigned={})

        plan_month(SUNDAYS, ctx)

        assert ctx.month_count == {}
        assert ctx.last_assigned == {}


class TestAvailability:
    def test_unavailable_worker_is_skipped_on_that_date_only(self):
        away, other = make_workers(2)
        ctx = one_group([away, other], 1, unavailable={SUNDAYS[0]: {away.id}})

        plans = plan_month(SUNDAYS[:2], ctx)

        assert selected(plans[0]) == [other.id]
        # Still eligible the following week, and now owed a turn.
        assert selected(plans[1]) == [away.id]

    def test_worker_booked_elsewhere_is_excluded(self):
        booked, free = make_workers(2)
        ctx = one_group([booked, free], 1, already_scheduled={SUNDAYS[0]: {booked.id}})

        plans = plan_month(SUNDAYS[:1], ctx)

        assert selected(plans[0]) == [free.id]

    def test_a_pick_blocks_that_worker_for_the_same_date(self):
        # Two dates planned; the carry-forward must not let a worker be double-booked
        # within the run itself.
        workers = make_workers(4)
        ctx = one_group(workers, 2)

        plans = plan_month(SUNDAYS[:2], ctx)

        for plan in plans:
            assert len(set(selected(plan))) == len(selected(plan))


class TestOutcomes:
    def test_understaffed_when_fewer_workers_than_needed(self):
        workers = make_workers(1)
        ctx = one_group(workers, 3)

        plans = plan_month(SUNDAYS[:1], ctx)

        assert plans[0].status == DatePlanStatus.UNDERSTAFFED
        assert len(selected(plans[0])) == 1
        assert plans[0].groups[0].message is not None
        assert "1 of 3" in plans[0].groups[0].message

    def test_skips_dates_that_already_have_a_schedule(self):
        workers = make_workers(4)
        ctx = one_group(workers, 2, existing_dates={SUNDAYS[1]})

        plans = plan_month(SUNDAYS, ctx)

        assert plans[1].status == DatePlanStatus.SKIPPED_EXISTING
        assert selected(plans[1]) == []
        # The rest of the month is still planned.
        assert [p.status for p in plans if p.scheduled_date != SUNDAYS[1]] == [DatePlanStatus.PLANNED] * 3

    def test_reports_no_workers_without_aborting_the_month(self):
        workers = make_workers(2)
        ctx = one_group(workers, 1, unavailable={SUNDAYS[0]: {w.id for w in workers}})

        plans = plan_month(SUNDAYS[:2], ctx)

        assert plans[0].status == DatePlanStatus.SKIPPED_NO_WORKERS
        assert plans[0].message is not None
        assert "2 unavailable" in plans[0].groups[0].message
        assert plans[1].status == DatePlanStatus.PLANNED

    def test_unpicked_workers_are_returned_as_alternates(self):
        workers = make_workers(5)
        ctx = one_group(workers, 2)

        plans = plan_month(SUNDAYS[:1], ctx)

        assert len(selected(plans[0])) == 2
        assert len(alternates(plans[0])) == 3
        assert not set(selected(plans[0])) & set(alternates(plans[0]))

    def test_returns_dates_in_ascending_order_regardless_of_input(self):
        workers = make_workers(4)
        ctx = one_group(workers, 1)

        plans = plan_month(list(reversed(SUNDAYS)), ctx)

        assert [p.scheduled_date for p in plans] == SUNDAYS

    def test_empty_date_list_produces_no_plans(self):
        ctx = one_group(make_workers(3), 1)
        assert plan_month([], ctx) == []


class TestGroups:
    """Department-wide planning: each subteam is staffed to its own quota."""

    def test_each_group_is_filled_to_its_own_quota(self):
        # Mirrors Children's Ministry: subteams with different workers_per_slot.
        seekers, discovery, checkin = make_workers(6), make_workers(5), make_workers(2)
        ctx = PlanContext(
            groups=[
                GroupContext(key="seekers", workers=seekers, min_workers=4, max_workers=4),
                GroupContext(key="discovery", workers=discovery, min_workers=3, max_workers=3),
                GroupContext(key="checkin", workers=checkin, min_workers=1, max_workers=1),
            ]
        )

        plans = plan_month(SUNDAYS[:1], ctx)

        assert plans[0].status == DatePlanStatus.PLANNED
        assert [(g.key, len(g.selected)) for g in plans[0].groups] == [
            ("seekers", 4),
            ("discovery", 3),
            ("checkin", 1),
        ]

    def test_no_group_is_left_empty(self):
        # The bug this replaced: a flat department quota staffed only the first few
        # workers, leaving whole subteams with nobody.
        ctx = PlanContext(
            groups=[
                GroupContext(key=f"team{i}", workers=make_workers(3), min_workers=2, max_workers=2) for i in range(4)
            ]
        )

        plans = plan_month(SUNDAYS, ctx)

        for plan in plans:
            assert all(len(g.selected) == 2 for g in plan.groups), f"{plan.scheduled_date} left a group empty"

    def test_a_worker_is_only_drawn_from_their_own_group(self):
        seekers, discovery = make_workers(4), make_workers(4)
        ctx = PlanContext(
            groups=[
                GroupContext(key="seekers", workers=seekers, min_workers=2, max_workers=2),
                GroupContext(key="discovery", workers=discovery, min_workers=2, max_workers=2),
            ]
        )

        plans = plan_month(SUNDAYS, ctx)

        seeker_ids, discovery_ids = {w.id for w in seekers}, {w.id for w in discovery}
        for plan in plans:
            by_key = {g.key: set(g.selected) for g in plan.groups}
            assert by_key["seekers"] <= seeker_ids
            assert by_key["discovery"] <= discovery_ids

    def test_alternates_stay_within_the_group(self):
        seekers, discovery = make_workers(4), make_workers(4)
        ctx = PlanContext(
            groups=[
                GroupContext(key="seekers", workers=seekers, min_workers=2, max_workers=2),
                GroupContext(key="discovery", workers=discovery, min_workers=2, max_workers=2),
            ]
        )

        plans = plan_month(SUNDAYS[:1], ctx)

        by_key = {g.key: set(g.alternates) for g in plans[0].groups}
        assert by_key["seekers"] <= {w.id for w in seekers}
        assert by_key["discovery"] <= {w.id for w in discovery}

    def test_each_group_rotates_independently(self):
        # 4 seekers / 2 per slot and 2 checkin / 1 per slot both spread evenly.
        seekers, checkin = make_workers(4), make_workers(2)
        ctx = PlanContext(
            groups=[
                GroupContext(key="seekers", workers=seekers, min_workers=2, max_workers=2),
                GroupContext(key="checkin", workers=checkin, min_workers=1, max_workers=1),
            ]
        )

        plans = plan_month(SUNDAYS, ctx)

        for key, expected_turns in (("seekers", [2, 2, 2, 2]), ("checkin", [2, 2])):
            served = [wid for plan in plans for g in plan.groups if g.key == key for wid in g.selected]
            counts = sorted({w: served.count(w) for w in set(served)}.values())
            assert counts == expected_turns, f"{key} rotated unevenly: {counts}"

    def test_one_short_group_marks_the_date_understaffed_but_others_still_fill(self):
        full, thin = make_workers(4), make_workers(1)
        ctx = PlanContext(
            groups=[
                GroupContext(key="full", workers=full, min_workers=2, max_workers=2),
                GroupContext(key="thin", workers=thin, min_workers=3, max_workers=3),
            ]
        )

        plans = plan_month(SUNDAYS[:1], ctx)

        assert plans[0].status == DatePlanStatus.UNDERSTAFFED
        by_key = {g.key: g for g in plans[0].groups}
        assert by_key["full"].status == DatePlanStatus.PLANNED
        assert len(by_key["full"].selected) == 2
        assert by_key["thin"].status == DatePlanStatus.UNDERSTAFFED
        assert len(by_key["thin"].selected) == 1
        assert plans[0].message == "3 of 5 slots filled."

    def test_date_is_skipped_only_when_every_group_is_empty(self):
        seekers, discovery = make_workers(2), make_workers(2)
        everyone = {w.id for w in seekers + discovery}
        ctx = PlanContext(
            groups=[
                GroupContext(key="seekers", workers=seekers, min_workers=1, max_workers=1),
                GroupContext(key="discovery", workers=discovery, min_workers=1, max_workers=1),
            ],
            unavailable={SUNDAYS[0]: everyone, SUNDAYS[1]: {w.id for w in seekers}},
        )

        plans = plan_month(SUNDAYS[:2], ctx)

        assert plans[0].status == DatePlanStatus.SKIPPED_NO_WORKERS
        # Only Seekers is out on the second date, so the date is understaffed, not skipped.
        assert plans[1].status == DatePlanStatus.UNDERSTAFFED
        assert {g.key: len(g.selected) for g in plans[1].groups} == {"seekers": 0, "discovery": 1}

    def test_a_group_with_no_members_reports_why(self):
        ctx = PlanContext(
            groups=[
                GroupContext(key="staffed", workers=make_workers(2), min_workers=1, max_workers=1),
                GroupContext(key="empty", workers=[], min_workers=2, max_workers=2),
            ]
        )

        plans = plan_month(SUNDAYS[:1], ctx)

        empty = next(g for g in plans[0].groups if g.key == "empty")
        assert empty.status == DatePlanStatus.SKIPPED_NO_WORKERS
        assert empty.message == "This group has no workers."


class TestStaffingBand:
    """The band itself: fill to the ceiling, judge against the floor.

    Pure, like the rest of this file — the rules that decide who serves and whether a date is
    short belong here, where they are tested without a single repository mock.
    """

    def test_fills_to_the_maximum_when_enough_are_free(self):
        ctx = one_group(make_workers(5), (2, 4))

        plan = plan_month(SUNDAYS[:1], ctx)[0]

        assert len(selected(plan)) == 4
        assert plan.status == DatePlanStatus.PLANNED

    def test_between_the_bounds_is_planned_not_short(self):
        # The whole point of splitting the number: three people on a 2-4 band is a working
        # rota, and flagging it would train heads to ignore the flag.
        ctx = one_group(make_workers(3), (2, 4))

        plan = plan_month(SUNDAYS[:1], ctx)[0]

        assert len(selected(plan)) == 3
        assert plan.status == DatePlanStatus.PLANNED
        assert plan.groups[0].message == "3 of 4 slots filled."

    def test_understaffed_only_below_the_minimum(self):
        ctx = one_group(make_workers(1), (2, 4))

        plan = plan_month(SUNDAYS[:1], ctx)[0]

        assert plan.status == DatePlanStatus.UNDERSTAFFED
        assert plan.groups[0].message == "Only 1 of 2 workers available."

    def test_at_the_maximum_says_nothing(self):
        ctx = one_group(make_workers(4), (2, 4))

        plan = plan_month(SUNDAYS[:1], ctx)[0]

        assert plan.groups[0].message is None

    def test_a_band_of_one_number_behaves_exactly_as_before(self):
        # The migration's regression guard. Every department starts life with min == max,
        # backfilled from workers_per_slot, and must keep behaving as it did.
        ctx = one_group(make_workers(5), 3)

        plan = plan_month(SUNDAYS[:1], ctx)[0]

        assert len(selected(plan)) == 3
        assert plan.status == DatePlanStatus.PLANNED
        assert plan.groups[0].message is None

    def test_a_minimum_of_zero_is_never_short(self):
        # "Use whoever is free, never chase me about it" is a legitimate setting — which is
        # why the band is resolved with `is None` rather than `or`, where 0 would be discarded.
        ctx = one_group(make_workers(1), (0, 3))

        plan = plan_month(SUNDAYS[:1], ctx)[0]

        assert plan.status == DatePlanStatus.PLANNED

    def test_alternates_are_everyone_past_the_maximum(self):
        ctx = one_group(make_workers(6), (2, 4))

        plan = plan_month(SUNDAYS[:1], ctx)[0]

        assert len(selected(plan)) == 4
        assert len(alternates(plan)) == 2

    def test_the_dates_message_counts_minimums(self):
        # A date is only short because a group fell below its floor, so totalling ceilings
        # here would contradict the per-group message sitting right beside it.
        ctx = PlanContext(
            groups=[
                GroupContext(key="seekers", workers=make_workers(2), min_workers=2, max_workers=5),
                GroupContext(key="discovery", workers=make_workers(1), min_workers=3, max_workers=6),
            ]
        )

        plan = plan_month(SUNDAYS[:1], ctx)[0]

        assert plan.status == DatePlanStatus.UNDERSTAFFED
        assert plan.message == "3 of 5 slots filled."

    def test_a_wide_band_still_spreads_turns_across_the_month(self):
        # Filling to the ceiling must not mean the same people every week: with 8 workers and
        # a 2-4 band over four Sundays, everyone should serve twice.
        workers = make_workers(8)
        ctx = one_group(workers, (2, 4))

        plans = plan_month(SUNDAYS, ctx)

        counts = {w.id: 0 for w in workers}
        for plan in plans:
            for worker_id in selected(plan):
                counts[worker_id] += 1
        assert set(counts.values()) == {2}


class TestSpecialServices:
    """A special date rotates on its own tally, so the big services hand round."""

    def test_a_special_date_orders_by_the_special_tally(self):
        # The single clearest statement of the feature. Ada has served three ordinary
        # turns and no special ones; Grace has served none this month but two specials.
        # On an ordinary date Grace leads (fewer turns this month). On a special date Ada
        # leads, because the tally that matters is the one the date rotates on.
        ada, grace = make_workers(2)
        ordinary_date, special_date = date(2026, 3, 1), date(2026, 3, 8)
        counts = {
            "month_count": {ada.id: 3, grace.id: 0},
            "special_count": {(grace.id, THANKSGIVING): 2},
        }

        ordinary = plan_month([ordinary_date], one_group([ada, grace], 1, **counts))[0]
        assert selected(ordinary) == [grace.id]

        special = plan_month(
            [special_date], one_group([ada, grace], 1, special_dates=thanksgiving(special_date), **counts)
        )[0]
        assert selected(special) == [ada.id]

    def test_each_named_service_keeps_its_own_tally(self):
        # The heart of it. Ada has served five Thanksgivings and no Christmas services;
        # Grace the reverse. A single tally across all specials calls that level and picks
        # on some unrelated tie-break, which is how somebody ends up on every Thanksgiving
        # for a year while a colleague has never seen one.
        ada, grace = make_workers(2)
        thanksgiving_date, christmas_date = date(2026, 3, 1), date(2026, 3, 8)
        ctx = one_group(
            [ada, grace],
            1,
            special_dates={thanksgiving_date: THANKSGIVING, christmas_date: CHRISTMAS},
            special_count={(ada.id, THANKSGIVING): 5, (grace.id, CHRISTMAS): 5},
        )

        plans = plan_month([thanksgiving_date, christmas_date], ctx)

        # Each service goes to whoever has served fewer of *that* service.
        assert selected(plans[0]) == [grace.id]
        assert selected(plans[1]) == [ada.id]

    def test_overall_turns_break_a_tie_on_a_special_date(self):
        # Between two people who have each served two Thanksgivings, the one with fewer
        # turns overall goes on, so a special date cannot ignore the wider balance.
        #
        # This deliberately uses the all-time count rather than the month's. A rule like
        # "first Sunday" always resolves to the earliest date in its month, so at the point
        # it is planned the month count is still zero for everybody and orders nothing —
        # the tie-break it used to use could never fire for the commonest shape of rule.
        busy, quiet = make_workers(2)
        special_date = date(2026, 3, 1)
        ctx = one_group(
            [busy, quiet],
            1,
            special_dates=thanksgiving(special_date),
            total_count={busy.id: 9, quiet.id: 2},
            special_count={(busy.id, THANKSGIVING): 2, (quiet.id, THANKSGIVING): 2},
        )

        assert selected(plan_month([special_date], ctx)[0]) == [quiet.id]

    def test_a_special_pick_increments_both_tallies(self):
        # A big service is still a turn. If it only cost a special count, whoever drew the
        # special date would get a free extra Sunday on top of their month's share.
        workers = make_workers(2)
        special_date, next_date = date(2026, 3, 1), date(2026, 3, 8)
        ctx = one_group(workers, 1, special_dates=thanksgiving(special_date))

        plans = plan_month([special_date, next_date], ctx)

        # The worker who took the special date does not also take the ordinary one.
        assert selected(plans[0]) != selected(plans[1])

    def test_twelve_first_sundays_spread_evenly_over_three_workers(self):
        # A year of communion Sundays. Without a separate tally the same name leads every
        # time, because to an ordinary sort one Sunday looks exactly like the next.
        workers = make_workers(3)
        ctx = one_group(workers, 1, special_dates={d: THANKSGIVING for d in FIRST_SUNDAYS})

        plans = plan_month(FIRST_SUNDAYS, ctx)

        served = [wid for plan in plans for wid in selected(plan)]
        assert len(served) == 12
        assert sorted(Counter(served).values()) == [4, 4, 4]

    def test_an_ordinary_month_is_unchanged_by_the_feature(self):
        # No special dates configured means the planner behaves exactly as it did before,
        # which is what lets all thirty-two existing tests stand unmodified.
        workers = make_workers(8)

        assert plan_month(SUNDAYS, one_group(workers, 2)) == plan_month(
            SUNDAYS, one_group(workers, 2, special_dates={}, special_count={})
        )

    def test_the_date_carries_its_own_specialness_out(self):
        # The preview badges it and the commit stamps the schedule from this, rather than
        # re-resolving the rules and risking a different answer.
        workers = make_workers(4)
        ctx = one_group(workers, 1, special_dates=thanksgiving(SUNDAYS[1]))

        plans = plan_month(SUNDAYS, ctx)

        assert [p.is_special for p in plans] == [False, True, False, False]

    def test_eligibility_is_untouched(self):
        # A special date is staffed from exactly the same roster. Somebody unavailable is
        # still unavailable; the tally changes the order, never who is in the running.
        ada, grace = make_workers(2)
        special_date = date(2026, 3, 1)
        ctx = one_group(
            [ada, grace],
            1,
            special_dates=thanksgiving(special_date),
            unavailable={special_date: {ada.id}},
            special_count={(grace.id, THANKSGIVING): 5},
        )

        # Ada leads the special tally by a mile and is still not picked.
        assert selected(plan_month([special_date], ctx)[0]) == [grace.id]

    def test_a_skipped_existing_date_still_reports_being_special(self):
        # The preview lists it with a badge even though nothing was planned for it.
        workers = make_workers(2)
        ctx = one_group(workers, 1, special_dates=thanksgiving(SUNDAYS[0]), existing_dates={SUNDAYS[0]})

        plan = plan_month([SUNDAYS[0]], ctx)[0]

        assert plan.status == DatePlanStatus.SKIPPED_EXISTING
        assert plan.is_special is True


class TestSpacing:
    """Turns are spaced, not just counted. A balanced rota is not automatically a humane one."""

    def test_nobody_serves_two_specials_running_while_somebody_is_fresh(self):
        # Four people, one slot, a year of monthly Thanksgivings. Everyone gets three, and
        # nobody is ever on two in a row.
        workers = make_workers(4)
        ctx = one_group(workers, 1, special_dates={d: THANKSGIVING for d in FIRST_SUNDAYS})

        served = [selected(plan)[0] for plan in plan_month(FIRST_SUNDAYS, ctx)]

        assert sorted(Counter(served).values()) == [3, 3, 3, 3]
        assert all(a != b for a, b in zip(served, served[1:]))

    def test_the_unavoidable_repeat_rotates_rather_than_landing_on_one_person(self):
        # Four slots from seven people means at least one person serves every consecutive
        # pair — there is no arrangement where nobody repeats. What must not happen is the
        # same person absorbing every repeat, which is what a tally with no spacing term
        # does: it hands the extra slot to whoever is quietest overall, every single time.
        workers = make_workers(7)
        ctx = one_group(workers, 4, special_dates={d: THANKSGIVING for d in FIRST_SUNDAYS})

        rosters = [set(selected(plan)) for plan in plan_month(FIRST_SUNDAYS, ctx)]

        longest = Counter()
        for worker in workers:
            run = 0
            for roster in rosters:
                run = run + 1 if worker.id in roster else 0
                longest[worker.id] = max(longest[worker.id], run)
        # Two in a row is forced; three is a failure of rotation.
        assert max(longest.values()) == 2

    def test_a_run_is_only_broken_by_actually_sitting_one_out(self):
        # The streak has to move for people who were not picked, or it never resets and the
        # term stops ordering anything after the first round.
        workers = make_workers(3)
        dates = FIRST_SUNDAYS[:4]
        ctx = one_group(workers, 1, special_dates={d: THANKSGIVING for d in dates})

        served = [selected(plan)[0] for plan in plan_month(dates, ctx)]

        # Everyone serves once before anyone serves twice, and the fourth date necessarily
        # returns to whoever went first — their run had been reset by sitting out two.
        assert len(set(served[:3])) == 3
        assert served[3] == served[0]

    def test_being_unavailable_counts_as_sitting_it_out(self):
        # Somebody passed over because they were away has not served it, so their run ends
        # exactly as if they had been rested. Otherwise a fortnight of leave would leave
        # them stuck behind a run they never actually had.
        ada, grace = make_workers(2)
        first, second = FIRST_SUNDAYS[0], FIRST_SUNDAYS[1]
        ctx = one_group(
            [ada, grace],
            1,
            special_dates={first: THANKSGIVING, second: THANKSGIVING},
            streak={(ada.id, THANKSGIVING): 3},
            unavailable={first: {ada.id}},
        )

        plans = plan_month([first, second], ctx)

        assert selected(plans[0]) == [grace.id]
        # Ada's run ended when she missed the first, so she leads the second.
        assert selected(plans[1]) == [ada.id]

    def test_a_run_at_one_service_does_not_hold_somebody_back_from_another(self):
        # Runs are per kind. Three Thanksgivings running says nothing about whether
        # somebody should be on the ordinary Sunday that follows.
        ada, grace = make_workers(2)
        ordinary_date = date(2026, 3, 8)
        ctx = one_group(
            [ada, grace],
            1,
            streak={(ada.id, THANKSGIVING): 3},
            total_count={ada.id: 0, grace.id: 4},
        )

        assert selected(plan_month([ordinary_date], ctx)[0]) == [ada.id]

    def test_ordinary_turns_are_spaced_too(self):
        # The same term covers ordinary Sundays: two people, one slot, nobody twice running.
        workers = make_workers(2)
        ctx = one_group(workers, 1)

        served = [selected(plan)[0] for plan in plan_month(SUNDAYS, ctx)]

        assert all(a != b for a, b in zip(served, served[1:]))

    def test_the_month_boundary_does_not_reset_the_balance(self):
        # month_count restarts at each month, so a month whose slots do not divide evenly
        # leaves a remainder that is forgotten unless something outlives the reset. Here
        # three people share two slots: whoever got the extra turn last month must not get
        # it again while somebody else has had none.
        first, second, third = make_workers(3)
        march = [date(2026, 3, 1), date(2026, 3, 8)]
        ctx = one_group(
            [first, second, third],
            2,
            # Last month: two turns each for the first two, one for the third.
            total_count={first.id: 2, second.id: 2, third.id: 1},
        )

        plans = plan_month(march, ctx)

        assert third.id in selected(plans[0])
