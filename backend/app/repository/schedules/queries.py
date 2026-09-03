TABLE = "schedules"
ASSIGNMENTS_TABLE = "schedule_assignments"

SELECT_ALL = "*"
SELECT_WITH_ASSIGNMENTS = "*, schedule_assignments(*, workers(*), subteams(*), department_roles(*))"
# Rooted at schedule_assignments, where SELECT_WITH_ASSIGNMENTS above is rooted at schedules.
# Write paths must re-read through this: PostgREST returns base-table columns only from an UPDATE,
# and the schedule detail page renders a row entirely from these embeds — without them a confirmed
# worker turns into "Unknown worker" with no role, in an "Unassigned" group.
SELECT_ASSIGNMENT_WITH_RELATIONS = "*, workers(*), subteams(*), department_roles(*)"
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
FUNCTION_GET_ASSIGNMENTS_DUE_FOR_REMINDER = "get_assignments_due_for_reminder"
FUNCTION_GET_ASSIGNMENTS_DUE_FOR_NOTICE = "get_assignments_due_for_notice"


class Columns:
    ID = "id"
    DEPARTMENT_ID = "department_id"
    TITLE = "title"
    SCHEDULED_DATE = "scheduled_date"
    START_TIME = "start_time"
    END_TIME = "end_time"
    SUBTEAM_ID = "subteam_id"
    NOTES = "notes"
    REMINDER_DAYS_BEFORE = "reminder_days_before"
    CREATED_BY = "created_by"
    CREATED_AT = "created_at"


class AssignmentColumns:
    ID = "id"
    SCHEDULE_ID = "schedule_id"
    WORKER_ID = "worker_id"
    DEPARTMENT_ROLE_ID = "department_role_id"
    STATUS = "status"
    REMINDER_SENT_AT = "reminder_sent_at"
    NOTICE_SENT_AT = "notice_sent_at"
    SUBTEAM_ID = "subteam_id"
    CREATED_AT = "created_at"
