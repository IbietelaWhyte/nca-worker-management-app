from datetime import date

from app.service.special_services.rules import (
    LAST_WEEK_OF_MONTH,
    nth_weekday_of_month,
    resolve_special_dates,
)

# 0 = Sunday in the database's convention, which is what these rules are stored in.
SUNDAY = 0
MONDAY = 1
SATURDAY = 6


class TestNthWeekdayOfMonth:
    def test_first_sunday_of_a_real_month(self):
        # August 2026 begins on a Saturday, so the first Sunday is the 2nd. Asserted
        # against a date anybody can check on a calendar, because the whole point of this
        # function is a convention mismatch that a self-consistent test would not catch.
        assert nth_weekday_of_month(2026, 8, SUNDAY, 1) == date(2026, 8, 2)

    def test_the_weekday_numbering_is_the_databases_not_pythons(self):
        # THE trap. The DB stores 0 = Sunday; Python's weekday() has 0 = Monday. Read
        # with Python's numbering, "day_of_week = 0" would resolve to 3 August, a Monday.
        first = nth_weekday_of_month(2026, 8, SUNDAY, 1)
        assert first == date(2026, 8, 2)
        assert first.weekday() == 6, "6 is Sunday in Python — 0 would mean Monday"

        assert nth_weekday_of_month(2026, 8, MONDAY, 1) == date(2026, 8, 3)
        assert nth_weekday_of_month(2026, 8, SATURDAY, 1) == date(2026, 8, 1)

    def test_second_third_and_fourth(self):
        assert nth_weekday_of_month(2026, 8, SUNDAY, 2) == date(2026, 8, 9)
        assert nth_weekday_of_month(2026, 8, SUNDAY, 3) == date(2026, 8, 16)
        assert nth_weekday_of_month(2026, 8, SUNDAY, 4) == date(2026, 8, 23)

    def test_a_fifth_occurrence_that_exists(self):
        assert nth_weekday_of_month(2026, 8, SUNDAY, 5) == date(2026, 8, 30)

    def test_a_fifth_occurrence_that_does_not_exist_returns_none(self):
        # September 2026 has four Sundays. The rule does not fire that month, which is
        # correct rather than an error — and it must not spill into October.
        assert nth_weekday_of_month(2026, 9, SUNDAY, 5) is None

    def test_last_is_the_last_whichever_it_is(self):
        # -1 is not "the fifth": in a month with four it is the fourth.
        assert nth_weekday_of_month(2026, 8, SUNDAY, LAST_WEEK_OF_MONTH) == date(2026, 8, 30)
        assert nth_weekday_of_month(2026, 9, SUNDAY, LAST_WEEK_OF_MONTH) == date(2026, 9, 27)

    def test_february_in_a_common_year(self):
        # 2026 is not a leap year: 28 days, exactly four Sundays.
        assert nth_weekday_of_month(2026, 2, SUNDAY, 1) == date(2026, 2, 1)
        assert nth_weekday_of_month(2026, 2, SUNDAY, 4) == date(2026, 2, 22)
        assert nth_weekday_of_month(2026, 2, SUNDAY, 5) is None
        assert nth_weekday_of_month(2026, 2, SUNDAY, LAST_WEEK_OF_MONTH) == date(2026, 2, 22)

    def test_february_in_a_leap_year(self):
        # 2028 is a leap year and its February starts on a Tuesday, so the 29th is a
        # fifth Tuesday — the case that only exists once every few years.
        TUESDAY = 2
        assert nth_weekday_of_month(2028, 2, TUESDAY, 1) == date(2028, 2, 1)
        assert nth_weekday_of_month(2028, 2, TUESDAY, 5) == date(2028, 2, 29)
        assert nth_weekday_of_month(2028, 2, TUESDAY, LAST_WEEK_OF_MONTH) == date(2028, 2, 29)

    def test_a_month_beginning_on_the_wanted_weekday(self):
        # The offset arithmetic must not skip a week when the 1st is already the target.
        # 1 February 2026 is a Sunday.
        assert nth_weekday_of_month(2026, 2, SUNDAY, 1) == date(2026, 2, 1)


class TestResolveSpecialDates:
    def test_a_rule_fires_once_per_month_across_a_window(self):
        resolved = resolve_special_dates(
            rules=[(SUNDAY, 1, "Communion")],
            one_offs=[],
            start=date(2026, 8, 1),
            end=date(2026, 10, 31),
        )
        assert resolved == {
            date(2026, 8, 2): "Communion",
            date(2026, 9, 6): "Communion",
            date(2026, 10, 4): "Communion",
        }

    def test_a_named_date_beats_a_rule_on_the_same_day(self):
        # Somebody sat down and typed the name. "First Sunday" is what the calendar says
        # when nobody has said anything better.
        resolved = resolve_special_dates(
            rules=[(SUNDAY, 1, "Communion")],
            one_offs=[(date(2026, 8, 2), "Jesus is Lord Service")],
            start=date(2026, 8, 1),
            end=date(2026, 8, 31),
        )
        assert resolved == {date(2026, 8, 2): "Jesus is Lord Service"}

    def test_occurrences_outside_the_window_are_dropped(self):
        # A window rarely starts on the 1st, and the resolver walks whole months.
        resolved = resolve_special_dates(
            rules=[(SUNDAY, 1, "Communion")],
            one_offs=[],
            start=date(2026, 8, 10),
            end=date(2026, 9, 30),
        )
        assert resolved == {date(2026, 9, 6): "Communion"}

    def test_a_month_with_no_fifth_sunday_contributes_nothing(self):
        resolved = resolve_special_dates(
            rules=[(SUNDAY, 5, "Fifth Sunday")],
            one_offs=[],
            start=date(2026, 9, 1),
            end=date(2026, 9, 30),
        )
        assert resolved == {}

    def test_several_rules_coexist(self):
        # "Second and fourth Sunday" is two rows, deliberately — there is no syntax for it.
        resolved = resolve_special_dates(
            rules=[(SUNDAY, 2, "Youth Sunday"), (SUNDAY, 4, "Thanksgiving")],
            one_offs=[],
            start=date(2026, 8, 1),
            end=date(2026, 8, 31),
        )
        assert resolved == {
            date(2026, 8, 9): "Youth Sunday",
            date(2026, 8, 23): "Thanksgiving",
        }

    def test_a_window_spanning_a_year_boundary(self):
        resolved = resolve_special_dates(
            rules=[(SUNDAY, 1, "Communion")],
            one_offs=[],
            start=date(2026, 12, 1),
            end=date(2027, 1, 31),
        )
        assert resolved == {
            date(2026, 12, 6): "Communion",
            date(2027, 1, 3): "Communion",
        }

    def test_an_inverted_window_is_empty_rather_than_an_error(self):
        assert resolve_special_dates([(SUNDAY, 1, "Communion")], [], date(2026, 9, 1), date(2026, 8, 1)) == {}

    def test_nothing_configured_is_not_an_error(self):
        assert resolve_special_dates([], [], date(2026, 8, 1), date(2026, 8, 31)) == {}
