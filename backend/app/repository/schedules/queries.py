TABLE = "schedules"
ASSIGNMENTS_TABLE = "schedule_assignments"

SELECT_ALL = "*"
SELECT_WITH_ASSIGNMENTS = "*, schedule_assignments(*, workers(*))"
SELECT_ASSIGNMENTS_WITH_SCHEDULE = "*, schedules(*)"
SELECT_ASSIGNMENTS_WITH_WORKERS = "*, workers(*), schedules(*)"
FUNCTION_GET_ASSIGNMENTS_DUE_FOR_REMINDERS = "get_assignments_due_for_reminders"


class Columns:
    ID = "id"
    DEPARTMENT_ID = "department_id"
    START_DATE = "start_date"
    END_DATE = "end_date"


class AssignmentColumns:
    ID = "id"
    SCHEDULE_ID = "schedule_id"
    WORKER_ID = "worker_id"
    SCHEDULE_DATE = "schedule_date"
    STATUS = "status"
    REMINDER_SENT_AT = "reminder_sent_at"
