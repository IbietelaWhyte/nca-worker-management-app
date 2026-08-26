TABLE = "workers"
JUNCTION_TABLE = "worker_departments"

SELECT_ALL = "*"
SELECT_WITH_DEPARTMENTS = "*, worker_departments(departments(*))"
# Just the columns needed to detect duplicate workers, so the import dedup check can pull the
# whole contact list in one round trip instead of a query per CSV row.
SELECT_CONTACT_INDEX = "id, email, phone, is_active"


class Columns:
    ID = "id"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    PHONE = "phone"
    IS_ACTIVE = "is_active"


class JunctionColumns:
    WORKER_ID = "worker_id"
    DEPARTMENT_ID = "department_id"
