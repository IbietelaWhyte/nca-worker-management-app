TABLE = "workers"
JUNCTION_TABLE = "worker_departments"

SELECT_ALL = "*"
SELECT_SUMMARY = "id, first_name, last_name, status, phone"
SELECT_WITH_DEPARTMENTS = "*, worker_departments(departments(*))"


class Columns:
    ID = "id"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    PHONE = "phone"
    STATUS = "status"


class JunctionColumns:
    WORKER_ID = "worker_id"
    DEPARTMENT_ID = "department_id"
