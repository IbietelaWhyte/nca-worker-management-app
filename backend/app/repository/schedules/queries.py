TABLE = "schedules"
ASSIGNMENTS_TABLE = "schedule_assignments"

SELECT_ALL = "*"
SELECT_WITH_ASSIGNMENTS = "*, schedule_assignments(*, workers(*))"
SELECT_ASSIGNMENTS_WITH_SCHEDULE = "*, schedules(*)"
SELECT_ASSIGNMENTS_WITH_WORKERS = "*, workers(*), schedules(*)"
FUNCTION_GET_ASSIGNMENTS_DUE_FOR_REMINDER = "get_assignments_due_for_reminder"


class Columns:
    ID = "id"
    DEPARTMENT_ID = "department_id"
    SCHEDULED_DATE = "scheduled_date"
    START_TIME = "start_time"
    END_TIME = "end_time"
    SUBTEAM_ID = "subteam_id"
    NOTES = "notes"
    REMINDER_DAYS_BEFORE = "reminder_days_before"


class AssignmentColumns:
    ID = "id"
    SCHEDULE_ID = "schedule_id"
    WORKER_ID = "worker_id"
    DEPARTMENT_ROLE_ID = "department_role_id"
    STATUS = "status"
    REMINDER_SENT_AT = "reminder_sent_at"
    SUBTEAM_ID = "subteam_id"
    CREATED_AT = "created_at"
