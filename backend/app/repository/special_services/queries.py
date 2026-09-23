TABLE = "special_services"

SELECT_ALL = "*"


class Columns:
    ID = "id"
    NAME = "name"
    KIND = "kind"
    # Stored as a smallint with 0 = Sunday, the schema-wide convention. The API speaks
    # DayOfWeek names; the repository is where the two meet.
    DAY_OF_WEEK = "day_of_week"
    WEEK_OF_MONTH = "week_of_month"
    SERVICE_DATE = "service_date"
    IS_ACTIVE = "is_active"
    CREATED_BY = "created_by"
    CREATED_AT = "created_at"
