TABLE = "subteams"
JUNCTION_TABLE = "worker_departments"

SELECT_ALL = "*"
SELECT_WITH_WORKERS = "*, workers(*)"



class Columns:
    ID = "id"
    DEPARTMENT_ID = "department_id"
    NAME = "name"
    DESCRIPTION = "description"
    WORKERS_PER_SLOT = "workers_per_slot"


class JunctionColumns:
    WORKER_ID = "worker_id"
    SUBTEAM_ID = "subteam_id"


