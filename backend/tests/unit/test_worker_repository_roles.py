from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.workers.repository import WorkerRepository
from app.schemas.models import UserRole


def _make_repo(current_roles: list[UserRole]) -> tuple[WorkerRepository, MagicMock]:
    client = MagicMock()
    # get_worker_roles reads .data off the select(...).eq(...).execute() chain.
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"role": role.value} for role in current_roles
    ]
    return WorkerRepository(client), client


class TestReplaceWorkerRoles:
    def test_adds_only_missing_roles_in_a_single_insert(self):
        repo, client = _make_repo([UserRole.WORKER])
        worker_id = uuid4()

        repo.replace_worker_roles(worker_id, [UserRole.WORKER, UserRole.HOD])

        # One batch insert containing only the added role; nothing removed.
        insert = client.table.return_value.insert
        insert.assert_called_once()
        inserted_rows = insert.call_args.args[0]
        assert [row["role"] for row in inserted_rows] == [UserRole.HOD]
        client.table.return_value.delete.assert_not_called()

    def test_removes_only_dropped_roles(self):
        repo, client = _make_repo([UserRole.WORKER, UserRole.HOD])
        worker_id = uuid4()

        repo.replace_worker_roles(worker_id, [UserRole.WORKER])

        # HOD removed; nothing added (so no insert call).
        client.table.return_value.insert.assert_not_called()
        delete_eq = client.table.return_value.delete.return_value.eq.return_value.eq
        delete_eq.assert_called_once_with("role", UserRole.HOD)

    def test_no_writes_when_roles_unchanged(self):
        repo, client = _make_repo([UserRole.WORKER, UserRole.HOD])
        worker_id = uuid4()

        repo.replace_worker_roles(worker_id, [UserRole.HOD, UserRole.WORKER])

        client.table.return_value.insert.assert_not_called()
        client.table.return_value.delete.assert_not_called()
