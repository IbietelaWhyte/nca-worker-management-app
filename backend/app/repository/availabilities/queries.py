TABLE = "availability"

SELECT_ALL = "*"
SELECT_WITH_WORKERS = "*, workers(*)"


class Columns:
    ID = "id"
    WORKER_ID = "worker_id"
    DAY_OF_WEEK = "day_of_week"
    IS_AVAILABLE = "is_available"
    AVAILABILITY_TYPE = "availability_type"
    SPECIFIC_DATE = "specific_date"


# Recurring and specific-date rows need different conflict targets. A specific-date row leaves
# day_of_week NULL, and Postgres treats NULLs as distinct, so the recurring target below can never
# match one — it inserts a duplicate instead of updating. Each is backed by its own unique index:
# unique_worker_day and uq_availability_worker_specific_date respectively.
UPSERT_CONFLICT_TARGET = "worker_id,day_of_week"
UPSERT_SPECIFIC_DATE_CONFLICT_TARGET = "worker_id,specific_date"
