"""Tests for the pure attendance rules.

No I/O and no mocks, like `test_schedule_planner.py` and `test_special_service_rules.py`.
Asserted against real clock arithmetic in a real zone, so a self-consistent timezone bug -
the whole reason this module exists - cannot pass.
"""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.schemas.attendance.models import AttendanceState
from app.service.attendance.rules import lateness, state_of

TORONTO = ZoneInfo("America/Toronto")
# A real Sunday, and one in daylight-saving time so the UTC offset is -04:00 rather than -05:00.
SERVICE_DATE = date(2026, 3, 15)
SERVICE_START = time(9, 0)
GRACE = 10


def tapped(hour: int, minute: int, tz: ZoneInfo = TORONTO) -> datetime:
    return datetime(SERVICE_DATE.year, SERVICE_DATE.month, SERVICE_DATE.day, hour, minute, tzinfo=tz)


class TestLateness:
    def test_arriving_before_the_start_is_not_late(self):
        assert lateness(SERVICE_DATE, SERVICE_START, tapped(8, 45), GRACE, TORONTO) == (0, False)

    def test_early_is_zero_minutes_rather_than_negative(self):
        # The column answers "how late"; a rota full of -15s answers a question nobody asked.
        minutes, _ = lateness(SERVICE_DATE, SERVICE_START, tapped(8, 45), GRACE, TORONTO)
        assert minutes == 0

    def test_inside_the_grace_period_counts_the_minutes_but_is_not_late(self):
        assert lateness(SERVICE_DATE, SERVICE_START, tapped(9, 5), GRACE, TORONTO) == (5, False)

    def test_the_grace_boundary_itself_is_not_late(self):
        # Exactly ten minutes with ten minutes' grace is on time. The comparison is > and not >=,
        # so the setting reads as "ten minutes of slack" rather than nine.
        assert lateness(SERVICE_DATE, SERVICE_START, tapped(9, 10), GRACE, TORONTO) == (10, False)

    def test_past_the_grace_period_is_late(self):
        assert lateness(SERVICE_DATE, SERVICE_START, tapped(9, 11), GRACE, TORONTO) == (11, True)

    def test_zero_grace_means_the_start_time_is_meant(self):
        assert lateness(SERVICE_DATE, SERVICE_START, tapped(9, 1), 0, TORONTO) == (1, True)
        assert lateness(SERVICE_DATE, SERVICE_START, tapped(9, 0), 0, TORONTO) == (0, False)

    def test_a_utc_timestamp_is_judged_in_the_church_s_zone(self):
        # The bug this module exists to prevent. 13:02 UTC is 09:02 in Toronto in March, which is
        # two minutes late and not four hours; a server comparing raw UTC would late the whole rota.
        utc_tap = datetime(2026, 3, 15, 13, 2, tzinfo=timezone.utc)
        assert lateness(SERVICE_DATE, SERVICE_START, utc_tap, GRACE, TORONTO) == (2, False)

    def test_a_tap_on_another_day_judges_nothing(self):
        # A correction entered on Tuesday says nothing about who walked in on Sunday morning, and
        # a fabricated zero would read as "arrived on time" for somebody nobody saw arrive.
        tuesday = datetime(2026, 3, 17, 9, 5, tzinfo=TORONTO)
        assert lateness(SERVICE_DATE, SERVICE_START, tuesday, GRACE, TORONTO) == (None, False)

    def test_a_tap_late_at_night_utc_still_belongs_to_the_service_day(self):
        # 01:30 UTC on the 16th is 21:30 on the 15th in Toronto - the same day locally, so it is
        # judged rather than discarded. date.today() on a UTC server would get this backwards.
        late_utc = datetime(2026, 3, 16, 1, 30, tzinfo=timezone.utc)
        minutes, is_late = lateness(SERVICE_DATE, SERVICE_START, late_utc, GRACE, TORONTO)
        assert (minutes, is_late) == (750, True)


class TestStateOf:
    def test_neither_timestamp_is_not_recorded_rather_than_absent(self):
        # The single most important assertion in the feature. A duty nobody recorded attendance for
        # is unknown, and counting it as an absence is the failure the design exists to prevent.
        assert state_of(None, None, False, False) is AttendanceState.NOT_RECORDED

    def test_a_check_in_is_present(self):
        assert state_of(tapped(9, 0), None, False, False) is AttendanceState.PRESENT

    def test_a_late_check_in_is_late_rather_than_present(self):
        # Late is its own state and never folded into present: a head chasing punctuality and a
        # head chasing no-shows want different numbers.
        assert state_of(tapped(9, 30), None, True, False) is AttendanceState.LATE

    def test_a_stamped_absence_is_absent(self):
        assert state_of(None, tapped(11, 0), False, False) is AttendanceState.ABSENT

    def test_an_excused_absence_is_excused_rather_than_absent(self):
        assert state_of(None, tapped(11, 0), False, True) is AttendanceState.EXCUSED

    def test_a_check_in_wins_over_everything(self):
        # The columns are mutually exclusive by check constraint, so this cannot arise from the
        # database - but if it ever did, somebody was seen, and that beats a stamp nobody observed.
        assert state_of(tapped(9, 0), tapped(11, 0), False, False) is AttendanceState.PRESENT
