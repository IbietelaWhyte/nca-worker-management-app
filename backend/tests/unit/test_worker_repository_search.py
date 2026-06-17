from unittest.mock import MagicMock

from app.repository.workers.repository import WorkerRepository


def _make_repo_with_mock_client() -> tuple[WorkerRepository, MagicMock]:
    client = MagicMock()
    # search() does `response.data or []`, so return an empty list to keep _to_model_list happy.
    client.table.return_value.select.return_value.or_.return_value.execute.return_value.data = []
    return WorkerRepository(client), client


class TestWorkerRepositorySearch:
    def test_escapes_query_in_or_filter(self):
        repo, client = _make_repo_with_mock_client()

        # The comma here is the PostgREST condition delimiter; a raw interpolation would let this
        # payload inject a second condition. It must end up quoted inside the ilike value instead.
        repo.search("a,b")

        or_filter = client.table.return_value.select.return_value.or_.call_args.args[0]
        assert or_filter == 'first_name.ilike."%a,b%",last_name.ilike."%a,b%"'

    def test_benign_query_builds_expected_filter(self):
        repo, client = _make_repo_with_mock_client()

        repo.search("john")

        or_filter = client.table.return_value.select.return_value.or_.call_args.args[0]
        assert or_filter == 'first_name.ilike."%john%",last_name.ilike."%john%"'
