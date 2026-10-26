TABLE = "worker_leave"

SELECT_ALL = "*"


class Columns:
    ID = "id"
    WORKER_ID = "worker_id"
    START_DATE = "start_date"
    END_DATE = "end_date"
    REASON = "reason"
    CREATED_BY = "created_by"
    CREATED_AT = "created_at"


def ends_on_or_after(day: str, column: str = Columns.END_DATE) -> str:
    """An `or()` filter: the leave runs to `day` or later, or has no end date at all.

    A NULL end_date means "until further notice", so a bare `end_date >= day` would silently
    drop every open-ended leave — the very people most certainly still away. `day` is always an
    ISO date we produced, never user input, so it needs no quoting.
    """
    return f"{column}.gte.{day},{column}.is.null"
