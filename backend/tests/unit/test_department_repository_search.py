from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.departments.repository import DepartmentRepository


def _make_repo_with_mock_client(count: int | None = 0) -> tuple[DepartmentRepository, MagicMock]:
    client = MagicMock()
    builder = MagicMock()
    for method in ("select", "in_", "or_", "order", "range"):
        getattr(builder, method).return_value = builder
    client.table.return_value = builder
    builder.execute.return_value.data = []
    builder.execute.return_value.count = count
    return DepartmentRepository(client), builder


class TestDepartmentRepositorySearch:
    def test_escapes_query_in_or_filter(self):
        repo, builder = _make_repo_with_mock_client()

        repo.search("a,b")

        builder.or_.assert_called_once_with('name.ilike."%a,b%",description.ilike."%a,b%"')

    def test_scopes_to_ids_and_pages(self):
        repo, builder = _make_repo_with_mock_client(count=3)
        dept_id = uuid4()

        departments, total = repo.search(ids=[dept_id], limit=10, offset=20)

        assert (departments, total) == ([], 3)
        builder.in_.assert_called_once_with("id", [str(dept_id)])
        builder.range.assert_called_once_with(20, 29)
        builder.or_.assert_not_called()

    def test_empty_scope_matches_nothing_without_a_query(self):
        repo, builder = _make_repo_with_mock_client()

        assert repo.search(ids=[]) == ([], 0)
        builder.execute.assert_not_called()
