from unittest.mock import MagicMock

from postgrest import CountMethod

from app.repository.workers.repository import WorkerRepository


class TestCount:
    def test_uses_head_request_to_avoid_transferring_rows(self):
        client = MagicMock()
        client.table.return_value.select.return_value.execute.return_value.count = 7
        repo = WorkerRepository(client)

        assert repo.count() == 7
        # head=True => PostgREST returns only the count, no row payload.
        assert client.table.return_value.select.call_args.kwargs == {
            "count": CountMethod.exact,
            "head": True,
        }


class TestGetAll:
    def test_passes_limit_and_offset_as_range(self):
        client = MagicMock()
        client.table.return_value.select.return_value.range.return_value.execute.return_value.data = []
        repo = WorkerRepository(client)

        repo.get_all(limit=10, offset=20)

        client.table.return_value.select.return_value.range.assert_called_once_with(20, 29)
