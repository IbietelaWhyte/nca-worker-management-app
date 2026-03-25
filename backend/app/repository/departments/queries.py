TABLE = "departments"
JUNCTION_TABLE = "worker_departments"

SELECT_ALL = "*"
SELECT_WITH_WORKERS = "*, workers:worker_departments(workers(*))"


class Columns:
    ID = "id"
    NAME = "name"
    DESCRIPTION = "description"


class JunctionColumns:
    WORKER_ID = "worker_id"
    DEPARTMENT_ID = "department_id"
