TABLE = "monthly_leads"

SELECT_ALL = "*"
# Two FKs point at workers (worker_id and created_by), so a bare workers(*) is ambiguous and
# PostgREST refuses it with PGRST201. Naming the column keeps the returned key "workers".
SELECT_WITH_WORKER = "*, workers!worker_id(*)"


class Columns:
    ID = "id"
    DEPARTMENT_ID = "department_id"
    WORKER_ID = "worker_id"
    MONTH = "month"
    CREATED_BY = "created_by"
    CREATED_AT = "created_at"
