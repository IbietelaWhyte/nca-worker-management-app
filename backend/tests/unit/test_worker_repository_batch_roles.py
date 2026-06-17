from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.workers.repository import WorkerRepository
from app.schemas.models import UserRole


class TestGetRolesForWorkers:
    def test_groups_roles_by_worker_in_one_query(self):
        client = MagicMock()
        w1, w2 = uuid4(), uuid4()
        client.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"worker_id": str(w1), "role": "worker"},
            {"worker_id": str(w1), "role": "hod"},
            {"worker_id": str(w2), "role": "worker"},
        ]
        repo = WorkerRepository(client)

        result = repo.get_roles_for_workers([w1, w2])

        assert result == {
            w1: [UserRole.WORKER, UserRole.HOD],
            w2: [UserRole.WORKER],
        }
        # A single batched query via .in_(), not one per worker.
        client.table.return_value.select.return_value.in_.assert_called_once()
        assert client.table.return_value.select.return_value.in_.call_args.args[0] == "worker_id"

    def test_empty_input_returns_empty_dict_without_querying(self):
        client = MagicMock()
        repo = WorkerRepository(client)

        assert repo.get_roles_for_workers([]) == {}
        client.table.assert_not_called()
