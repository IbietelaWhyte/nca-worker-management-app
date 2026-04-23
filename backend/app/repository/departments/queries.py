TABLE = "departments"
JUNCTION_TABLE = "worker_departments"
ASSISTANT_HOD_JUNCTION_TABLE = "department_assistant_hods"

SELECT_ALL = "*"
SELECT_WITH_WORKERS = "*, workers:worker_departments(workers(*))"
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
