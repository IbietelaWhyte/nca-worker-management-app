TABLE = "department_roles"
JUNCTION_TABLE = "worker_departments"

SELECT_ALL = "*"


class Columns:
    ID = "id"
    DEPARTMENT_ID = "department_id"
    NAME = "name"
    DESCRIPTION = "description"


class JunctionColumns:
    WORKER_ID = "worker_id"
    DEPARTMENT_ID = "department_id"
    DEPARTMENT_ROLE_ID = "department_role_id"
