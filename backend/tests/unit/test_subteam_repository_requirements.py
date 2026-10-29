from unittest.mock import MagicMock
from uuid import uuid4

from app.repository.department_roles.repository import DepartmentRoleRepository
from app.repository.subteams.repository import SubteamRepository
from app.schemas.subteams.models import RoleRequirement


def _builder() -> MagicMock:
    builder = MagicMock()
    for method in ("select", "eq", "in_", "upsert", "delete", "is_"):
        getattr(builder, method).return_value = builder
    builder.not_ = builder
    builder.execute.return_value = MagicMock(data=[])
    return builder


def _client(builder: MagicMock) -> MagicMock:
    client = MagicMock()
    client.table.return_value = builder
    return client


class TestRoleRequirementQueries:
    """Every service test mocks these repositories and cannot see the strings, hence these."""

    def test_the_department_list_embeds_the_requirements(self):
        builder = _builder()
        SubteamRepository(_client(builder)).get_by_department(uuid4())
        assert "subteam_role_requirements(department_role_id,min_count)" in builder.select.call_args.args[0]

    def test_replace_upserts_on_the_primary_key_then_deletes_the_rest(self):
        builder = _builder()
        client = _client(builder)
        subteam_id, role_id = uuid4(), uuid4()

        SubteamRepository(client).replace_role_requirements(
            subteam_id, [RoleRequirement(department_role_id=role_id, min_count=2)]
        )

        # A non-partial primary key, so a legal on_conflict target (the 42P10 trap).
        assert builder.upsert.call_args.kwargs["on_conflict"] == "subteam_id,department_role_id"
        builder.in_.assert_called_with("department_role_id", [str(role_id)])
        # Written before deleted: a failure in between leaves an extra row, never a lost one.
        names = [c[0] for c in builder.method_calls if c[0] in ("upsert", "delete")]
        assert names == ["upsert", "delete"]

    def test_replace_with_nothing_only_deletes(self):
        builder = _builder()
        SubteamRepository(_client(builder)).replace_role_requirements(uuid4(), [])
        builder.upsert.assert_not_called()
        builder.delete.assert_called_once()

    def test_requirements_are_grouped_by_subteam(self):
        builder = _builder()
        subteam_id, role_id = uuid4(), uuid4()
        builder.execute.return_value = MagicMock(
            data=[{"subteam_id": str(subteam_id), "department_role_id": str(role_id), "min_count": 2}]
        )
        result = SubteamRepository(_client(builder)).get_role_requirements([subteam_id])
        assert result == {subteam_id: {role_id: 2}}

    def test_no_subteams_makes_no_query(self):
        client = _client(_builder())
        assert SubteamRepository(client).get_role_requirements([]) == {}
        client.table.assert_not_called()

    def test_worker_roles_are_one_query_and_skip_members_without_one(self):
        builder = _builder()
        worker_id, role_id = uuid4(), uuid4()
        builder.execute.return_value = MagicMock(
            data=[{"worker_id": str(worker_id), "department_role_id": str(role_id)}]
        )
        result = DepartmentRoleRepository(_client(builder)).get_role_ids_for_department(uuid4())
        assert result == {worker_id: role_id}
        builder.is_.assert_called_once_with("department_role_id", "null")
