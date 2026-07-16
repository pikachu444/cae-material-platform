from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from cmp.apps.demo import _DEMO_ROLES, _grant_runtime_privileges


@dataclass
class _ScalarResult:
    value: str

    def scalar_one(self) -> str:
        return self.value


@dataclass
class _Connection:
    statements: list[str] = field(default_factory=list)

    def execute(self, statement: Any, parameters: Any = None) -> _ScalarResult:
        del parameters
        assert "SELECT current_database()" in str(statement)
        return _ScalarResult("cmp")

    def exec_driver_sql(self, statement: str) -> None:
        self.statements.append(statement)


def test_demo_bootstrap_grants_processing_and_statistics_schemas_to_non_owner_application_role(
) -> None:
    connection = _Connection()

    _grant_runtime_privileges(cast(Any, connection))

    assert any('"processing"' in statement for statement in connection.statements)
    assert any(
        "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA \"processing\" TO cmp_app"
        == statement
        for statement in connection.statements
    )
    assert any('"statistics"' in statement for statement in connection.statements)
    assert any(
        "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA \"statistics\" TO cmp_app"
        == statement
        for statement in connection.statements
    )
    assert any(
        "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA \"validation\" TO cmp_app"
        == statement
        for statement in connection.statements
    )


def test_demo_group_has_the_explicit_cae_analyst_role_for_validation_commands() -> None:
    assert "cae_analyst" in _DEMO_ROLES


def test_demo_group_has_auditor_role_for_the_local_operations_view() -> None:
    assert "auditor" in _DEMO_ROLES
