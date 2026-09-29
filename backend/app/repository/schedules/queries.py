TABLE = "schedules"
ASSIGNMENTS_TABLE = "schedule_assignments"
REMINDER_SENDS_TABLE = "assignment_reminder_sends"

SELECT_ALL = "*"
# EVERY workers embed off schedule_assignments must name the column it travels, because there are
# now TWO foreign keys from this table to workers: worker_id (whose duty it is) and checked_in_by
# (who marked them present). PostgREST refuses an ambiguous embed outright with PGRST201 "Could not
# embed because more than one relationship was found", so a bare workers(*) here does not degrade
# quietly — it fails every read of every schedule. The `!worker_id` form names the column rather
# than the constraint, so it survives a constraint being renamed, and the returned key is still
# "workers". `subteams/queries.py` already does this for the same reason.
SELECT_WITH_ASSIGNMENTS = "*, schedule_assignments(*, workers!worker_id(*), subteams(*), department_roles(*))"
# Rooted at schedule_assignments, where SELECT_WITH_ASSIGNMENTS above is rooted at schedules.
# Write paths must re-read through this: PostgREST returns base-table columns only from an UPDATE,
# and the schedule detail page renders a row entirely from these embeds — without them a confirmed
# worker turns into "Unknown worker" with no role, in an "Unassigned" group.
SELECT_ASSIGNMENT_WITH_RELATIONS = "*, workers!worker_id(*), subteams(*), department_roles(*)"
# A worker's own duty list names the department and the job they are doing in it, the same two
# facts the SMS and the confirmation page carry — a worker serving in several departments cannot
# tell their Sundays apart from the schedule title alone.
SELECT_ASSIGNMENTS_WITH_SCHEDULE = "*, schedules(*, departments(*)), department_roles(*)"
# Inner join variant: required when filtering on a schedules column, otherwise PostgREST
# nulls the embedded object instead of dropping the assignment row.
SELECT_ASSIGNMENTS_WITH_SCHEDULE_INNER = "*, schedules!inner(*)"
# The public confirmation page names the department that scheduled each duty, and that page has no
# session to look one up with — so the name has to ride along with the assignment. Kept separate
# from the plain inner variant above, which the monthly planner's bulk history preload uses and
# where the extra join buys nothing.
SELECT_ASSIGNMENTS_WITH_SCHEDULE_AND_DEPARTMENT_INNER = "*, schedules!inner(*, departments(*))"
# The edit paths (swap, add, remove) need the assignment, the schedule it sits on and the worker
# who holds it in one read, *before* the row is changed or deleted: the schedule supplies the
# department to authorize against and the date the SMS quotes, and the worker is who to text.
# Afterwards there is nothing left to read the removed worker from.
SELECT_ASSIGNMENT_WITH_SCHEDULE_AND_WORKER = "*, workers!worker_id(*), schedules(*), subteams(*), department_roles(*)"
# The absence report reads a department's month: every rota, who was on it, and what attendance
# recorded. Rooted at schedules because the report counts services as well as people — a month
# where attendance was taken twice out of twelve has to be able to say so, and an
# assignment-rooted read cannot see the rotas that have no attendance on them at all.
SELECT_FOR_ATTENDANCE_REPORT = "*, schedule_assignments(*, workers!worker_id(*))"
FUNCTION_GET_ASSIGNMENTS_DUE_FOR_REMINDER = "get_assignments_due_for_reminder"
FUNCTION_GET_ASSIGNMENTS_DUE_FOR_NOTICE = "get_assignments_due_for_notice"
# The composite primary key of assignment_reminder_sends, and a legal ON CONFLICT arbiter because
# it is a plain index rather than a partial one — recording a send is therefore an idempotent
# upsert, and two scheduler runs racing produce one row rather than two texts.
REMINDER_SEND_CONFLICT_TARGET = "assignment_id,days_before"


class Columns:
    ID = "id"
    ATTENDANCE_CLOSED_AT = "attendance_closed_at"
    ATTENDANCE_CLOSED_BY = "attendance_closed_by"
    DEPARTMENT_ID = "department_id"
    TITLE = "title"
    SCHEDULED_DATE = "scheduled_date"
    START_TIME = "start_time"
    END_TIME = "end_time"
    SUBTEAM_ID = "subteam_id"
    NOTES = "notes"
    REMINDER_DAYS_BEFORE = "reminder_days_before"
    MIN_WORKERS = "min_workers"
    MAX_WORKERS = "max_workers"
    SPECIAL_SERVICE_ID = "special_service_id"
    SPECIAL_SERVICE_NAME = "special_service_name"
    CREATED_BY = "created_by"
    CREATED_AT = "created_at"


class AssignmentColumns:
    ID = "id"
    SCHEDULE_ID = "schedule_id"
    WORKER_ID = "worker_id"
    DEPARTMENT_ROLE_ID = "department_role_id"
    NOTICE_SENT_AT = "notice_sent_at"
    CHECKED_IN_AT = "checked_in_at"
    CHECKED_IN_BY = "checked_in_by"
    MARKED_ABSENT_AT = "marked_absent_at"
    MINUTES_LATE = "minutes_late"
    IS_LATE = "is_late"
    EXCUSED = "excused"
    SUBTEAM_ID = "subteam_id"
    CREATED_AT = "created_at"


class ReminderSendColumns:
    ASSIGNMENT_ID = "assignment_id"
    DAYS_BEFORE = "days_before"
    SENT_AT = "sent_at"
