from supabase import Client

from app.core.logging import get_logger
from app.repository.repository import BaseRepository
from app.repository.special_services import queries as q
from app.schemas.special_services.models import SpecialService, SpecialServiceKind

logger = get_logger(__name__)


class SpecialServiceRepository(BaseRepository[SpecialService]):
    """Recurring rules and named one-off dates.

    `create`, `update`, `delete` and `get_by_id` come from `BaseRepository` unchanged — there is
    nothing special about writing one of these rows. Only the two reads below are domain
    queries, and `list_all` is named to avoid overriding the base's paginated `get_all` with an
    incompatible signature.
    """

    def __init__(self, client: Client) -> None:
        """
        Initialize the SpecialServiceRepository with a Supabase client.

        Args:
            client (Client): The Supabase client instance used for database operations.
        """
        super().__init__(client, q.TABLE, SpecialService)
        self.logger = logger.bind(repository="SpecialServiceRepository")

    def list_all(self, active_only: bool = False) -> list[SpecialService]:
        """
        Retrieve every special service, recurring rules and one-offs together.

        Unpaginated on purpose: this is church-wide configuration measured in tens of rows, and
        every caller wants both kinds at once — the admin page lists them and the resolver needs
        the whole set to walk a window of months.

        Args:
            active_only (bool): Exclude deactivated entries.

        Returns:
            list[SpecialService]: One-offs by date, then rules by weekday and week.
        """
        log = self.logger.bind(method="list_all", active_only=active_only)
        query = self.client.table(q.TABLE).select(q.SELECT_ALL)
        if active_only:
            query = query.eq(q.Columns.IS_ACTIVE, True)
        response = (
            query.order(q.Columns.KIND)
            .order(q.Columns.SERVICE_DATE)
            .order(q.Columns.DAY_OF_WEEK)
            .order(q.Columns.WEEK_OF_MONTH)
            .execute()
        )
        services = self._to_model_list(response.data or [])
        log.debug("fetched_special_services", count=len(services))
        return services

    def get_active_by_kind(self) -> tuple[list[SpecialService], list[SpecialService]]:
        """
        The active entries split by kind, which is how the resolver consumes them.

        One round-trip rather than two: the table is small enough that splitting in Python
        costs less than a second query, and the resolver always wants both halves.

        Returns:
            tuple[list[SpecialService], list[SpecialService]]: (recurring rules, one-offs).
        """
        active = self.list_all(active_only=True)
        return (
            [s for s in active if s.kind == SpecialServiceKind.RECURRING],
            [s for s in active if s.kind == SpecialServiceKind.ONE_OFF],
        )
