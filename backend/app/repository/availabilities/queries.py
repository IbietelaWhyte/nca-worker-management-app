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


UPSERT_CONFLICT_TARGET = "worker_id,day_of_week"
