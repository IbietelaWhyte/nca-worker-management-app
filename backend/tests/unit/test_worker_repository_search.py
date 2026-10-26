from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.workers.repository import WorkerRepository
from app.schemas.models import UserRole, WorkerStatus


def _make_repo_with_mock_client(count: int | None = 0) -> tuple[WorkerRepository, MagicMock]:
    client = MagicMock()
    # Every filter returns the same builder, so assertions don't depend on the order of the chain.
    builder = MagicMock()
    for method in ("select", "in_", "eq", "lte", "gte", "or_", "order", "range"):
        getattr(builder, method).return_value = builder
    client.table.return_value = builder
    builder.execute.return_value.data = []
    builder.execute.return_value.count = count
    return WorkerRepository(client), builder


def _or_filters(builder: MagicMock) -> list[str]:
    return [c.args[0] for c in builder.or_.call_args_list]


class TestWorkerRepositorySearch:
    def test_escapes_query_in_or_filter(self):
        repo, builder = _make_repo_with_mock_client()

        # The comma here is the PostgREST condition delimiter; a raw interpolation would let this
        # payload inject a second condition. It must end up quoted inside the ilike value instead.
        repo.search("a,b")

        assert _or_filters(builder) == ['first_name.ilike."%a,b%",last_name.ilike."%a,b%",email.ilike."%a,b%"']

    def test_each_word_must_match_somewhere(self):
        # "john smi" has to find John Smith, which no single ilike over one column can do.
        repo, builder = _make_repo_with_mock_client()

        repo.search("john  smi")

        assert _or_filters(builder) == [
            'first_name.ilike."%john%",last_name.ilike."%john%",email.ilike."%john%"',
            'first_name.ilike."%smi%",last_name.ilike."%smi%",email.ilike."%smi%"',
        ]

    def test_no_filters_selects_plain_rows_and_pages(self):
        repo, builder = _make_repo_with_mock_client(count=42)

        workers, total = repo.search(limit=25, offset=50)

        assert (workers, total) == ([], 42)
        assert builder.select.call_args.args == ("*",)
        builder.or_.assert_not_called()
        builder.range.assert_called_once_with(50, 74)

    def test_embeds_only_the_filters_in_use(self):
        # An !inner embed drops every worker without a matching row, so adding one for a filter
        # that is not set would silently hide people with no department, role or leave.
        repo, builder = _make_repo_with_mock_client()

        repo.search(role=UserRole.HOD)

        assert builder.select.call_args.args == ("*, worker_app_roles!inner(role)",)
        builder.eq.assert_called_once_with("worker_app_roles.role", "hod")

    def test_department_filter(self):
        repo, builder = _make_repo_with_mock_client()
        dept_id = uuid4()

        repo.search(department_ids=[dept_id])

        assert builder.select.call_args.args == ("*, worker_departments!inner(department_id)",)
        builder.in_.assert_called_once_with("worker_departments.department_id", [str(dept_id)])

    def test_empty_department_scope_matches_nobody_without_a_query(self):
        repo, builder = _make_repo_with_mock_client()

        assert repo.search(department_ids=[]) == ([], 0)
        builder.execute.assert_not_called()

    def test_on_leave_embed_names_the_worker_id_fk(self):
        # worker_leave has two FKs to workers (worker_id, created_by); a bare embed is PGRST201.
        repo, builder = _make_repo_with_mock_client()

        repo.search(status=WorkerStatus.ON_LEAVE, today=date(2026, 10, 14))

        assert builder.select.call_args.args == ("*, worker_leave!worker_id!inner(start_date,end_date)",)
        builder.lte.assert_called_once_with("worker_leave.start_date", "2026-10-14")
        # Open-ended leave has a NULL end_date, and those are the people most certainly away.
        builder.or_.assert_called_once_with("end_date.gte.2026-10-14,end_date.is.null", reference_table="worker_leave")
        builder.gte.assert_not_called()

    def test_active_and_inactive_filter_on_is_active(self):
        repo, builder = _make_repo_with_mock_client()

        repo.search(status=WorkerStatus.INACTIVE)

        builder.eq.assert_called_once_with("is_active", False)
