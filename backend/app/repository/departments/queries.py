TABLE = "departments"
JUNCTION_TABLE = "worker_departments"
ASSISTANT_HOD_JUNCTION_TABLE = "department_assistant_hods"

SELECT_ALL = "*"
# The junction carries subteam_id, so the subteam rides along for free. It is needed because a
# worker holds at most one row per department: putting somebody in a subteam UPDATES that row
# and therefore moves them out of whichever subteam they were in. A picker that cannot show
# where they already are cannot warn that adding them takes them from somewhere else.
SELECT_WITH_WORKERS = "*, workers:worker_departments(workers(*), department_roles(*), subteams(*))"
# for fetching departments where a worker is an assistant HOD,
# we need to select from the assistant HOD junction table and include department details
SELECT_ASSISTANT_HOD_DEPARTMENTS = "departments(*)"


class Columns:
    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"


class JunctionColumns:
    WORKER_ID = "worker_id"
    DEPARTMENT_ID = "department_id"


class AssistantHodJunctionColumns:
    WORKER_ID = "worker_id"
    DEPARTMENT_ID = "department_id"
