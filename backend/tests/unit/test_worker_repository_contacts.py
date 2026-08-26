from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.workers.repository import WorkerRepository


def _make_repo() -> tuple[WorkerRepository, MagicMock]:
    return WorkerRepository(MagicMock()), None  # type: ignore[return-value]


class TestGetActiveWorkers:
    def test_filters_on_is_active_not_a_status_column(self):
        # Regression: this filtered .eq("status", "active"), but workers has no status column — only
        # is_active. Every admin call to GET /workers?active_only=true returned a 500. The service
        # tests mock the repository, so only a call-chain assertion catches it.
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        repo = WorkerRepository(client)

        repo.get_active_workers()

        assert client.table.return_value.select.return_value.eq.call_args.args == ("is_active", True)


class TestGetContactIndex:
    def test_keys_on_lowercased_email_and_normalized_phone(self):
        worker_id = uuid4()
        client = MagicMock()
        client.table.return_value.select.return_value.execute.return_value.data = [
            {"id": str(worker_id), "email": "Jane@Example.com", "phone": "(416) 555-0101", "is_active": True}
        ]
        repo = WorkerRepository(client)

        index = repo.get_contact_index()

        # Both sides are normalized, so a CSV row in any casing or phone format still matches.
        assert index["jane@example.com"].worker_id == worker_id
        assert index["+14165550101"].worker_id == worker_id
        assert index["jane@example.com"].is_active is True

    def test_carries_the_deactivated_flag(self):
        client = MagicMock()
        client.table.return_value.select.return_value.execute.return_value.data = [
            {"id": str(uuid4()), "email": "gone@example.com", "phone": None, "is_active": False}
        ]
        repo = WorkerRepository(client)

        assert repo.get_contact_index()["gone@example.com"].is_active is False

    def test_skips_unparseable_stored_phones(self):
        # Rows predating normalization may hold anything; they must not break the index.
        client = MagicMock()
        client.table.return_value.select.return_value.execute.return_value.data = [
            {"id": str(uuid4()), "email": "a@example.com", "phone": "ext. 4501", "is_active": True}
        ]
        repo = WorkerRepository(client)

        index = repo.get_contact_index()
        assert list(index) == ["a@example.com"]

    def test_returns_empty_when_no_workers_exist(self):
        client = MagicMock()
        client.table.return_value.select.return_value.execute.return_value.data = []
        assert WorkerRepository(client).get_contact_index() == {}


class TestBatchWrites:
    def test_create_many_inserts_once(self):
        client = MagicMock()
        client.table.return_value.insert.return_value.execute.return_value.data = []
        repo = WorkerRepository(client)

        rows = [{"first_name": "Ann"}, {"first_name": "Bob"}]
        repo.create_many(rows)

        # One statement for the batch, so Postgres applies it atomically.
        client.table.return_value.insert.assert_called_once_with(rows)

    def test_create_many_skips_the_call_when_empty(self):
        client = MagicMock()
        assert WorkerRepository(client).create_many([]) == []
        client.table.return_value.insert.assert_not_called()

    def test_delete_many_filters_on_the_given_ids(self):
        client = MagicMock()
        repo = WorkerRepository(client)
        ids = [uuid4(), uuid4()]

        repo.delete_many(ids)

        assert client.table.return_value.delete.return_value.in_.call_args.args == ("id", [str(i) for i in ids])

    def test_delete_many_skips_the_call_when_empty(self):
        client = MagicMock()
        WorkerRepository(client).delete_many([])
        client.table.return_value.delete.assert_not_called()
