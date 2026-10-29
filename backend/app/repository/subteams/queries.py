TABLE = "subteams"
JUNCTION_TABLE = "worker_departments"

SELECT_ALL = "*"
SELECT_WITH_WORKERS = "*, workers:worker_departments!subteam_id(workers(*))"
# One FK links the two tables, so the bare embed is unambiguous.
SELECT_WITH_ROLE_REQUIREMENTS = "*, role_requirements:subteam_role_requirements(department_role_id,min_count)"

REQUIREMENTS_TABLE = "subteam_role_requirements"


class Columns:
    ID = "id"
    DEPARTMENT_ID = "department_id"
    NAME = "name"
    DESCRIPTION = "description"
    WORKERS_PER_SLOT = "workers_per_slot"


class RequirementColumns:
    SUBTEAM_ID = "subteam_id"
    DEPARTMENT_ROLE_ID = "department_role_id"
    MIN_COUNT = "min_count"


# The primary key, and so the upsert's conflict target.
REQUIREMENTS_CONFLICT = f"{RequirementColumns.SUBTEAM_ID},{RequirementColumns.DEPARTMENT_ROLE_ID}"


class JunctionColumns:
    WORKER_ID = "worker_id"
    DEPARTMENT_ID = "department_id"
    SUBTEAM_ID = "subteam_id"
