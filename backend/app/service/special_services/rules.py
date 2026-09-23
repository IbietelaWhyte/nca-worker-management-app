"""Resolving special-service rules to actual dates.

Pure, with no I/O, for the same reason `planner.py` is: this is calendar arithmetic with
an off-by-one trap in it, and it should be testable against known real dates without a
repository in sight.

**The whole day-of-week conversion lives here.** The database stores `0 = Sunday`, which
is what `DayOfWeek.to_number()` follows; Python's `date.weekday()` uses `0 = Monday`.
CLAUDE.md flags that mismatch as a trap and this is its third site, so `_to_python_weekday`
is the only place in this module that knows about it. Do not do the arithmetic inline.
"""

from calendar import monthrange
from datetime import date, timedelta

# Sunday is 6 in Python's weekday() and 0 in the database's convention.
_DB_SUNDAY = 0
_PYTHON_SUNDAY = 6

# week_of_month sentinel: the last occurrence in the month, whichever it turns out to be.
LAST_WEEK_OF_MONTH = -1


def _to_python_weekday(db_day_of_week: int) -> int:
    """Convert the database's 0=Sunday to Python's 0=Monday.

    Args:
        db_day_of_week: 0 (Sunday) through 6 (Saturday), the DB convention.

    Returns:
        int: 0 (Monday) through 6 (Sunday), what `date.weekday()` returns.
    """
    return (db_day_of_week - 1) % 7


def nth_weekday_of_month(year: int, month: int, db_day_of_week: int, nth: int) -> date | None:
    """The nth given weekday of a month, or None when the month has no such occurrence.

    "The fifth Sunday of February" is a real thing to ask and usually has no answer. That
    is not an error — it means the rule simply does not fire that month — so it returns
    None rather than raising or spilling into the next month.

    Args:
        year: Calendar year.
        month: 1-12.
        db_day_of_week: Which weekday, in the DB's 0=Sunday convention.
        nth: 1-5 for the first through fifth occurrence, or `LAST_WEEK_OF_MONTH` (-1)
            for the last one in the month.

    Returns:
        date | None: The resolved date, or None if the month has no nth such weekday.
    """
    wanted = _to_python_weekday(db_day_of_week)
    days_in_month = monthrange(year, month)[1]

    first = date(year, month, 1)
    # How far forward from the 1st to the first occurrence of the wanted weekday.
    offset = (wanted - first.weekday()) % 7
    first_occurrence = first + timedelta(days=offset)

    if nth == LAST_WEEK_OF_MONTH:
        # Step forward in weeks while the next one is still inside the month.
        last = first_occurrence
        while (nxt := last + timedelta(days=7)).month == month:
            last = nxt
        return last

    candidate = first_occurrence + timedelta(days=7 * (nth - 1))
    return candidate if candidate.day <= days_in_month and candidate.month == month else None


def _months_between(start: date, end: date) -> list[tuple[int, int]]:
    """Every (year, month) pair the window touches, inclusive at both ends."""
    months: list[tuple[int, int]] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def resolve_special_dates(
    rules: list[tuple[int, int, str]],
    one_offs: list[tuple[date, str]],
    start: date,
    end: date,
) -> dict[date, str]:
    """Every special date in a window, mapped to what to call it.

    A named one-off wins the label over a rule landing on the same day. Somebody sat down
    and typed "Jesus is Lord Service" against that date; "First Sunday" is what the
    calendar says when nobody has said anything better.

    Args:
        rules: (day_of_week in the DB convention, week_of_month, name) for each recurring
            rule. `week_of_month` of -1 means the last such weekday in the month.
        one_offs: (date, name) for each named date.
        start: First date of the window, inclusive.
        end: Last date of the window, inclusive.

    Returns:
        dict[date, str]: Special dates inside the window, each mapped to its name.
    """
    if start > end:
        return {}

    resolved: dict[date, str] = {}

    for year, month in _months_between(start, end):
        for day_of_week, week_of_month, name in rules:
            occurrence = nth_weekday_of_month(year, month, day_of_week, week_of_month)
            # A month with no fifth Sunday, or an occurrence outside the asked-for window
            # — a window rarely starts on the 1st.
            if occurrence is not None and start <= occurrence <= end:
                resolved[occurrence] = name

    # Second, so they overwrite a rule's label on the same day.
    for service_date, name in one_offs:
        if start <= service_date <= end:
            resolved[service_date] = name

    return resolved
