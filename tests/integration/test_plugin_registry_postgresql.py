from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import (
    database_permissions_for,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.plugins.adapters.contracts.jsonschema import (
    JsonSchemaPluginContractValidator,
)
from cmp.modules.plugins.adapters.persistence.registry import (
    SqlAlchemyPluginRegistryRepository,
)
from cmp.modules.plugins.application.registry import (
    ActivatePackage,
    ControlPackage,
    PluginRegistryService,
    RegisterPackage,
    RegisterSchema,
)
from cmp.modules.plugins.domain.registry import (
    ArtifactReference,
    InvalidPackageState,
    PackageConflict,
    PackageNotFound,
    PackageState,
    SchemaRole,
)
from cmp.shared.domain.revisions import content_sha256
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.container_service,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]

NOW = datetime(2026, 7, 11, 10, 0, tzinfo=UTC)
ORG = UUID("87000000-0000-4000-8000-000000000001")
PROJECT_A = UUID("87000000-0000-4000-8000-000000000002")
PROJECT_B = UUID("87000000-0000-4000-8000-000000000003")
MAINTAINER = UUID("87000000-0000-4000-8000-000000000004")
ADMIN = UUID("87000000-0000-4000-8000-000000000005")
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    admin_engine: Engine
    app_engine: Engine
    service: PluginRegistryService


def _psycopg_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("CMP_TEST_POSTGRES_DSN must use PostgreSQL with psycopg")
    return url


def _alembic_config(database_url: URL) -> Config:
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"))
    configuration.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return configuration


def _seed(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO identity.principal "
            "(id, principal_type, display_name, active, created_at, updated_at) "
            "VALUES (:id, 'user', :display_name, true, :created_at, :updated_at)"
        ),
        [
            {
                "id": MAINTAINER,
                "display_name": "Plugin Maintainer",
                "created_at": NOW - timedelta(days=1),
                "updated_at": NOW - timedelta(days=1),
            },
            {
                "id": ADMIN,
                "display_name": "Plugin Organization Admin",
                "created_at": NOW - timedelta(days=1),
                "updated_at": NOW - timedelta(days=1),
            },
        ],
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t17_{uuid4().hex}"
    app_role = f"cmp_t17_app_{uuid4().hex}"
    cluster_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        connection.exec_driver_sql(
            f'CREATE ROLE "{app_role}" LOGIN NOSUPERUSER NOCREATEDB '
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    database_url = admin_url.set(database=database_name)
    admin_engine = sa.create_engine(database_url, pool_pre_ping=True)
    app_engine: Engine | None = None
    try:
        command.upgrade(_alembic_config(database_url), "head")
        with admin_engine.begin() as connection:
            _seed(connection)
            connection.exec_driver_sql(
                "GRANT USAGE ON SCHEMA identity, revisioning, access_control, plugin "
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA plugin "
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA "
                f'access_control, revisioning, plugin TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        repository = SqlAlchemyPluginRegistryRepository(
            session_factory=sessions,
            rls_context=rls,
        )
        yield PostgresHarness(
            admin_engine,
            app_engine,
            PluginRegistryService(
                repository=repository,
                validator=JsonSchemaPluginContractValidator(),
                clock=lambda: NOW,
            ),
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        command.downgrade(_alembic_config(database_url), "base")
        admin_engine.dispose()
        with cluster_engine.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            connection.exec_driver_sql(f'DROP ROLE "{app_role}"')
        cluster_engine.dispose()


def _context(
    principal_id: UUID,
    *,
    project_id: UUID = PROJECT_A,
) -> SecurityContext:
    return SecurityContext(
        principal=Principal(principal_id, PrincipalType.USER, "Plugin Actor", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(principal_id),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext, permission: Permission
) -> AuthorizationDecision:
    role = Role.PLUGIN_MAINTAINER if permission is Permission.PLUGIN_SUBMIT else Role.ORG_ADMIN
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=(role,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _manifest(
    *,
    plugin_id: str,
    version: str,
    digest: str,
) -> dict[str, Any]:
    document = cast(
        dict[str, Any],
        json.loads(
            (PROJECT_ROOT / "contracts/examples/positive/plugin-manifest.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["plugin_id"] = plugin_id
    document["plugin_version"] = version
    document["package_digest"] = f"sha256:{digest}"
    return document


def _command(
    *,
    plugin_id: str = "org.example.t17.reference",
    version: str = "1.0.0",
    digest: str | None = None,
    idempotency_key: str | None = None,
) -> RegisterPackage:
    resolved_digest = digest or content_sha256(
        {"plugin_id": plugin_id, "version": version}
    )
    manifest = _manifest(
        plugin_id=plugin_id, version=version, digest=resolved_digest
    )
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:cmp:plugin:{plugin_id}:{version}:config",
        "type": "object",
        "additionalProperties": False,
    }
    return RegisterPackage(
        DataClassification.INTERNAL,
        manifest,
        ArtifactReference(uuid4(), resolved_digest, 4096, "application/zip"),
        ArtifactReference(uuid4(), "b" * 64, 512, "application/json"),
        ArtifactReference(uuid4(), "c" * 64, 1024, "application/spdx+json"),
        (
            RegisterSchema(
                str(schema["$id"]),
                1,
                SchemaRole.CONFIG,
                schema,
                content_sha256(schema),
            ),
        ),
        idempotency_key or f"{plugin_id}-{version}-{resolved_digest[:8]}",
    )


def _register(
    postgres: PostgresHarness,
    command_value: RegisterPackage,
) -> tuple[SecurityContext, Any]:
    context = _context(MAINTAINER)
    result = postgres.service.register(
        context,
        _decision(context, Permission.PLUGIN_SUBMIT),
        command_value,
    )
    return context, result


def test_register_verify_activate_is_idempotent_and_append_only(
    postgres: PostgresHarness,
) -> None:
    command_value = _command(plugin_id="org.example.t17.lifecycle")
    maintainer, registered = _register(postgres, command_value)
    replay = postgres.service.register(
        maintainer,
        _decision(maintainer, Permission.PLUGIN_SUBMIT),
        command_value,
    )

    assert registered.package.id != registered.package.definition_id
    assert registered.package.state is PackageState.CONTRACT_VALIDATED
    assert replay.replayed is True
    assert replay.package.id == registered.package.id

    administrator = _context(ADMIN)
    activation_decision = _decision(administrator, Permission.PLUGIN_ACTIVATE)
    verified = postgres.service.verify(
        administrator,
        activation_decision,
        ControlPackage(
            registered.package.id,
            "signature, SBOM, compatibility, and policy evidence verified",
        ),
    )
    activated = postgres.service.activate(
        administrator,
        activation_decision,
        ActivatePackage(registered.package.id, "approved for this project"),
    )

    assert verified.state is PackageState.ELIGIBLE
    assert activated.active is True
    assert [item.to_state for item in activated.state_events] == [
        PackageState.CONTRACT_VALIDATED,
        PackageState.ELIGIBLE,
    ]
    assert activated.state_events[0].actor_id == MAINTAINER
    assert activated.state_events[1].actor_id == ADMIN
    assert activated.activation is not None
    assert activated.activation.activated_by == ADMIN

    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE plugin.package SET display_name = 'substituted' "
                    "WHERE id = :package_id"
                ),
                {"package_id": registered.package.id},
            )
    with pytest.raises(DBAPIError, match="sealed"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO plugin.capability ("
                    "organization_id, project_id, classification, package_id, "
                    "extension_ordinal, capability"
                    ") VALUES ("
                    ":organization_id, :project_id, 'internal', :package_id, 1, "
                    "'post_registration_substitution'"
                    ")"
                ),
                {
                    "organization_id": ORG,
                    "project_id": PROJECT_A,
                    "package_id": registered.package.id,
                },
            )
    with pytest.raises(DBAPIError, match="same transaction"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO plugin.package_state_event ("
                    "organization_id, project_id, id, classification, package_id, "
                    "sequence_no, from_state, to_state, occurred_at, actor_id, reason, "
                    "request_id, trace_id"
                    ") VALUES ("
                    ":organization_id, :project_id, :id, 'internal', :package_id, "
                    "3, 'eligible', 'revoked', :occurred_at, :actor_id, :reason, "
                    ":request_id, :trace_id"
                    ")"
                ),
                {
                    "organization_id": ORG,
                    "project_id": PROJECT_A,
                    "id": uuid4(),
                    "package_id": registered.package.id,
                    "occurred_at": NOW,
                    "actor_id": ADMIN,
                    "reason": "orphan event must not commit",
                    "request_id": uuid4(),
                    "trace_id": TRACE,
                },
            )
    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE plugin.package_state_event SET reason = 'rewritten' "
                    "WHERE package_id = :package_id"
                ),
                {"package_id": registered.package.id},
            )


def test_stable_definition_reuses_identity_and_rejects_version_digest_substitution(
    postgres: PostgresHarness,
) -> None:
    plugin_id = "org.example.t17.versioned"
    _, first = _register(
        postgres,
        _command(plugin_id=plugin_id, version="1.0.0", digest="d" * 64),
    )
    _, second = _register(
        postgres,
        _command(plugin_id=plugin_id, version="1.1.0", digest="e" * 64),
    )

    assert first.package.definition_id == second.package.definition_id
    assert first.package.id != second.package.id
    assert first.package.manifest.package_digest != second.package.manifest.package_digest

    maintainer = _context(MAINTAINER)
    with pytest.raises(PackageConflict, match="different digest"):
        postgres.service.register(
            maintainer,
            _decision(maintainer, Permission.PLUGIN_SUBMIT),
            _command(
                plugin_id=plugin_id,
                version="1.0.0",
                digest="f" * 64,
                idempotency_key="version-digest-substitution",
            ),
        )


def test_revoked_package_and_cross_project_context_cannot_activate(
    postgres: PostgresHarness,
) -> None:
    _, registered = _register(
        postgres, _command(plugin_id="org.example.t17.revocation")
    )
    administrator = _context(ADMIN)
    activation_decision = _decision(administrator, Permission.PLUGIN_ACTIVATE)
    postgres.service.verify(
        administrator,
        activation_decision,
        ControlPackage(registered.package.id, "supply-chain evidence verified"),
    )
    revoked = postgres.service.revoke(
        administrator,
        activation_decision,
        ControlPackage(registered.package.id, "package vulnerability revoked eligibility"),
    )
    assert revoked.state is PackageState.REVOKED
    assert revoked.active is False
    with pytest.raises(InvalidPackageState):
        postgres.service.activate(
            administrator,
            activation_decision,
            ActivatePackage(registered.package.id, "must remain revoked"),
        )

    other_project = _context(ADMIN, project_id=PROJECT_B)
    with pytest.raises(PackageNotFound):
        postgres.service.get(
            other_project,
            _decision(other_project, Permission.PLUGIN_READ),
            registered.package.id,
        )
    with pytest.raises(PackageNotFound):
        postgres.service.activate(
            other_project,
            _decision(other_project, Permission.PLUGIN_ACTIVATE),
            ActivatePackage(registered.package.id, "cross-project activation denied"),
        )


def test_active_execution_lookup_is_digest_pinned_revocation_aware_and_tenant_scoped(
    postgres: PostgresHarness,
) -> None:
    plugin_id = "org.example.t18.execution-lookup"
    digest = "8" * 64
    _, registered = _register(
        postgres,
        _command(plugin_id=plugin_id, version="1.8.0", digest=digest),
    )
    administrator = _context(ADMIN)
    activation_decision = _decision(administrator, Permission.PLUGIN_ACTIVATE)
    postgres.service.verify(
        administrator,
        activation_decision,
        ControlPackage(registered.package.id, "runner contract evidence verified"),
    )
    postgres.service.activate(
        administrator,
        activation_decision,
        ActivatePackage(registered.package.id, "approved for isolated execution"),
    )
    read_decision = _decision(administrator, Permission.PLUGIN_READ)

    active = postgres.service.get_active(
        administrator,
        read_decision,
        plugin_id=plugin_id,
        plugin_version="1.8.0",
        package_digest=digest,
    )

    assert active.id == registered.package.id
    assert active.active
    with pytest.raises(PackageNotFound):
        postgres.service.get_active(
            administrator,
            read_decision,
            plugin_id=plugin_id,
            plugin_version="1.8.0",
            package_digest="9" * 64,
        )
    other_project = _context(ADMIN, project_id=PROJECT_B)
    with pytest.raises(PackageNotFound):
        postgres.service.get_active(
            other_project,
            _decision(other_project, Permission.PLUGIN_READ),
            plugin_id=plugin_id,
            plugin_version="1.8.0",
            package_digest=digest,
        )

    postgres.service.revoke(
        administrator,
        activation_decision,
        ControlPackage(registered.package.id, "package revoked after activation"),
    )
    with pytest.raises(PackageNotFound):
        postgres.service.get_active(
            administrator,
            read_decision,
            plugin_id=plugin_id,
            plugin_version="1.8.0",
            package_digest=digest,
        )


@pytest.mark.parametrize(
    ("table", "trigger", "message"),
    [
        ("capability", "capability_immutable", "exact declared capabilities"),
        ("schema", "schema_immutable", "at least one registered schema"),
    ],
)
def test_database_activation_guard_rejects_incomplete_normalized_contract(
    postgres: PostgresHarness,
    table: str,
    trigger: str,
    message: str,
) -> None:
    _, registered = _register(
        postgres,
        _command(plugin_id=f"org.example.t17.missing-{table}"),
    )
    administrator = _context(ADMIN)
    decision = _decision(administrator, Permission.PLUGIN_ACTIVATE)
    postgres.service.verify(
        administrator,
        decision,
        ControlPackage(registered.package.id, "supply-chain evidence verified"),
    )
    with postgres.admin_engine.begin() as connection:
        connection.exec_driver_sql(
            f"ALTER TABLE plugin.{table} DISABLE TRIGGER {trigger}"
        )
        connection.execute(
            sa.text(f"DELETE FROM plugin.{table} WHERE package_id = :package_id"),
            {"package_id": registered.package.id},
        )
        connection.exec_driver_sql(
            f"ALTER TABLE plugin.{table} ENABLE TRIGGER {trigger}"
        )

    with pytest.raises(DBAPIError, match=message):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO plugin.activation ("
                    "organization_id, project_id, id, classification, package_id, "
                    "activated_at, activated_by, reason, request_id, trace_id"
                    ") VALUES ("
                    ":organization_id, :project_id, :id, 'internal', :package_id, "
                    ":activated_at, :activated_by, :reason, :request_id, :trace_id"
                    ")"
                ),
                {
                    "organization_id": ORG,
                    "project_id": PROJECT_A,
                    "id": uuid4(),
                    "package_id": registered.package.id,
                    "activated_at": NOW,
                    "activated_by": ADMIN,
                    "reason": "must fail closed",
                    "request_id": uuid4(),
                    "trace_id": TRACE,
                },
            )
