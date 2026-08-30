from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

from cmp.apps.demo import (
    _BOOTSTRAP_PRINCIPAL_ID,
    _DEMO_ROLES,
    _grant_runtime_privileges,
    _seed_demo_role_bindings,
)
from cmp.bootstrap.demo_identity import (
    DEMO_GROUP,
    DEMO_PROJECT_ID,
    DEMO_REVIEWER_GROUP,
    DEMO_USER_GROUP,
    DEMO_WORKER_CLIENT_ID,
    DEMO_WORKER_RUNNER_ID,
)


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


def test_demo_administrator_group_has_plugin_registry_authority() -> None:
    assert "org_admin" in _DEMO_ROLES
    assert "plugin_maintainer" in _DEMO_ROLES


def test_plugin_registry_authority_is_not_seeded_for_user_or_reviewer_groups() -> None:
    connection = _SeedConnection()

    _seed_demo_role_bindings(cast(Any, connection), "urn:cmp:demo-identity")

    group_bindings = [
        parameters
        for statement, parameters in connection.statements
        if "INSERT INTO identity.role_binding" in statement
        and parameters is not None
        and parameters.get("group_name") is not None
    ]
    admin_roles = {
        parameters["role"]
        for parameters in group_bindings
        if parameters["group_name"] == DEMO_GROUP
    }
    assert {"org_admin", "plugin_maintainer"}.issubset(admin_roles)
    org_admin = next(
        parameters for parameters in group_bindings if parameters["role"] == "org_admin"
    )
    plugin_maintainer = next(
        parameters for parameters in group_bindings if parameters["role"] == "plugin_maintainer"
    )
    assert org_admin["project_id"] is None
    assert plugin_maintainer["project_id"] == DEMO_PROJECT_ID
    assert all(
        parameters["project_id"] == DEMO_PROJECT_ID
        for parameters in group_bindings
        if parameters["role"] != "org_admin"
    )
    assert not any(
        parameters["group_name"] in {DEMO_USER_GROUP, DEMO_REVIEWER_GROUP}
        and parameters["role"] in {"org_admin", "plugin_maintainer"}
        for parameters in group_bindings
    )


def test_demo_group_has_auditor_role_for_the_local_operations_view() -> None:
    assert "auditor" in _DEMO_ROLES


def test_demo_human_group_does_not_receive_the_worker_service_role() -> None:
    assert "job_runner" not in _DEMO_ROLES


@dataclass
class _SeedConnection:
    statements: list[tuple[str, dict[str, object] | None]] = field(default_factory=list)

    def execute(self, statement: Any, parameters: Any = None) -> None:
        self.statements.append((str(statement), cast(dict[str, object] | None, parameters)))


def test_demo_bootstrap_binds_job_runner_to_the_worker_service_principal() -> None:
    connection = _SeedConnection()

    _seed_demo_role_bindings(cast(Any, connection), "urn:cmp:demo-identity")

    external_identity = next(
        parameters
        for statement, parameters in connection.statements
        if "INSERT INTO identity.external_identity" in statement
    )
    assert external_identity is not None
    assert external_identity["principal_id"] == _BOOTSTRAP_PRINCIPAL_ID
    assert external_identity["subject"] == DEMO_WORKER_CLIENT_ID

    job_runner = next(
        parameters
        for statement, parameters in connection.statements
        if "'job_runner'" in statement
    )
    assert job_runner is not None
    assert job_runner["principal_id"] == _BOOTSTRAP_PRINCIPAL_ID
    assert isinstance(job_runner["id"], UUID)

    role_binding_statement = next(
        statement
        for statement, _ in connection.statements
        if "INSERT INTO identity.role_binding" in statement and "'job_runner'" in statement
    )
    assert "'principal'" in role_binding_statement
    assert "'group'" not in role_binding_statement

    runner = next(
        parameters
        for statement, parameters in connection.statements
        if "INSERT INTO jobs.runner (" in statement
    )
    assert runner is not None
    assert runner["id"] == DEMO_WORKER_RUNNER_ID
    assert runner["organization_id"] == UUID("d0000000-0000-4000-8000-000000000001")

    capability = next(
        parameters
        for statement, parameters in connection.statements
        if "INSERT INTO jobs.runner_job_type (" in statement
    )
    assert capability is not None
    assert capability["runner_id"] == DEMO_WORKER_RUNNER_ID
