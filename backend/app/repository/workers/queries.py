TABLE = "workers"
JUNCTION_TABLE = "worker_departments"

SELECT_ALL = "*"
SELECT_WITH_DEPARTMENTS = "*, worker_departments(departments(*))"
# Just the columns needed to detect duplicate workers, so the import dedup check can pull the
# whole contact list in one round trip instead of a query per CSV row.
SELECT_CONTACT_INDEX = "id, email, phone, is_active"
# Inner embeds for the filtered list, each added only when its filter is set: an !inner embed
# drops every worker with no matching row. worker_leave has two FKs to workers (worker_id and
# created_by), so its embed must name the column or PostgREST refuses it with PGRST201.
EMBED_DEPARTMENTS = "worker_departments!inner(department_id)"
EMBED_APP_ROLES = "worker_app_roles!inner(role)"
EMBED_LEAVE = "worker_leave!worker_id!inner(start_date,end_date)"
# Embedded-column paths that the filters above are applied to.
FILTER_DEPARTMENT_ID = "worker_departments.department_id"
FILTER_APP_ROLE = "worker_app_roles.role"
FILTER_LEAVE_START = "worker_leave.start_date"
FILTER_LEAVE_END = "worker_leave.end_date"
# A search query is split into at most this many words, each of which must match somewhere.
MAX_SEARCH_TERMS = 3


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
    SUBTEAM_ID = "subteam_id"
