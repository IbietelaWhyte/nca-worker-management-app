"""Judging an arrival against the service it was for.

Pure, with no I/O, for the same reason `schedules/planner.py` and `special_services/rules.py`
are: this is clock arithmetic with a timezone trap in it, and it should be testable against
known real times without a repository in sight.

**The whole zone conversion lives here.** Everything in the schema is zone-less - a schedule
carries a `date` and a bare `time` - while a check-in is a `timestamptz`. Comparing them needs
a named zone, and a server running in UTC comparing `now()` against a 09:00 Toronto service
would judge the entire rota four hours late. `settings.church_timezone` is that zone, and
nothing outside this module should be doing the arithmetic.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.schemas.attendance.models import AttendanceState

# A minute is the finest unit anybody cares about for "how late", and seconds would make the
# stored number look more precise than the observation behind it.
_SECONDS_PER_MINUTE = 60


def service_start(scheduled_date: date, start_time: time, tz: ZoneInfo) -> datetime:
    """The moment a service begins, as an instant rather than a wall-clock reading.

    Args:
        scheduled_date: The day the service falls on.
        start_time: Its start, as the rota records it.
        tz: The church's zone.

    Returns:
        datetime: A timezone-aware datetime for the start of the service.
    """
    return datetime.combine(scheduled_date, start_time, tzinfo=tz)


def lateness(
    scheduled_date: date,
    start_time: time,
    checked_in_at: datetime,
    grace_minutes: int,
    tz: ZoneInfo,
) -> tuple[int | None, bool]:
    """How late an arrival was, and whether that counts as late.

    Returns `(None, False)` when the check-in did not land on the service's own day. A
    correction entered on Tuesday says nothing about who walked in on Sunday morning, and a
    fabricated zero would read as "arrived on time" for somebody nobody saw arrive. Null is the
    honest answer, and the column is nullable to hold it.

    Arriving early is zero minutes late rather than a negative number: the column exists to
    answer "how late", and a rota full of -7s answers a question nobody asked.

    Args:
        scheduled_date: The day the service falls on.
        start_time: Its start, as the rota records it.
        checked_in_at: When the operator marked them present. Must be timezone-aware.
        grace_minutes: Slack before an arrival counts as late; 0 means the start time is meant.
        tz: The church's zone.

    Returns:
        tuple[int | None, bool]: Minutes after the start (clamped at zero, or None when the tap
            was on another day), and whether that beat the grace period.
    """
    local = checked_in_at.astimezone(tz)
    if local.date() != scheduled_date:
        return None, False

    delta = local - service_start(scheduled_date, start_time, tz)
    minutes = max(0, int(delta.total_seconds() // _SECONDS_PER_MINUTE))
    return minutes, minutes > grace_minutes


def state_of(
    checked_in_at: datetime | None,
    marked_absent_at: datetime | None,
    is_late: bool,
    excused: bool,
) -> AttendanceState:
    """Read the three-state record off the pair of timestamps.

    The one place the table in the migration header is turned into a value, so the API, the
    report and the export cannot disagree about what a row means. Note that neither timestamp
    set is **not** absence: it is a duty nobody recorded, and counting it as an absence is the
    exact failure this whole design is shaped to avoid.

    Args:
        checked_in_at: When they were marked present, if they were.
        marked_absent_at: When closing attendance recorded them absent, if it did.
        is_late: The stamped lateness judgement.
        excused: Whether this absence was excused.

    Returns:
        AttendanceState: What the row says happened.
    """
    if checked_in_at is not None:
        return AttendanceState.LATE if is_late else AttendanceState.PRESENT
    if marked_absent_at is not None:
        return AttendanceState.EXCUSED if excused else AttendanceState.ABSENT
    return AttendanceState.NOT_RECORDED


def grace_window_ends(scheduled_date: date, start_time: time, grace_minutes: int, tz: ZoneInfo) -> datetime:
    """The instant after which an arrival is late. Exists so the frontend can say so."""
    return service_start(scheduled_date, start_time, tz) + timedelta(minutes=grace_minutes)
