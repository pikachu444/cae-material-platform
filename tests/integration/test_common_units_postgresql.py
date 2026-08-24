from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.units.adapters.persistence.profiles import SqlAlchemyUnitProfileRepository
from cmp.modules.units.application.profiles import (
    CommonUnitService,
    CreateUnitProfile,
    ReviseUnitProfile,
    UnitProfileNotFound,
)
from cmp.modules.units.domain.profiles import (
    UnitProfileContent,
    UnitProfilePin,
    UnitProfileSelection,
)
from cmp.modules.units.domain.system import DimensionId, UnitError
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

NOW = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
ORG = UUID("20500000-0000-4000-8000-000000000001")
PROJECT_A = UUID("20500000-0000-4000-8000-000000000002")
PROJECT_B = UUID("20500000-0000-4000-8000-000000000003")
ACTOR = UUID("20500000-0000-4000-8000-000000000004")
REQUEST = UUID("20500000-0000-4000-8000-000000000005")
LEGACY_OUTPUT = UUID("20500000-0000-4000-8000-000000000006")
LEGACY_OUTPUT_REVISION = UUID("20500000-0000-4000-8000-000000000007")
TRACE = "00-00000000000000000000000000000205-0000000000000205-01"


@dataclass(frozen=True, slots=True)
class Harness:
    admin: Engine
    sessions: sessionmaker[Session]
    rls: SqlAlchemyRlsContext
    service: CommonUnitService


def _url(value: str) -> URL:
    parsed = make_url(value)
    if parsed.drivername in {"postgres", "postgresql"}:
        return parsed.set(drivername="postgresql+psycopg")
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("CMP_TEST_POSTGRES_DSN must use PostgreSQL with psycopg")
    return parsed


def _config(database_url: URL) -> Config:
    result = Config(str(PROJECT_ROOT / "alembic.ini"))
    result.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return result


def _seed_legacy_processing_output(connection: sa.Connection) -> None:
    connection.exec_driver_sql("SET session_replication_role = 'replica'")
    connection.execute(
        sa.text(
            "INSERT INTO processing.common_processing_output "
            "(id, organization_id, project_id, classification, label, current_revision_id, "
            "created_at, created_by, updated_at) VALUES "
            "(:id, :organization_id, :project_id, 'internal', 'Legacy output', :revision, "
            ":now, :actor, :now)"
        ),
        {
            "id": LEGACY_OUTPUT,
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "revision": LEGACY_OUTPUT_REVISION,
            "now": NOW,
            "actor": ACTOR,
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO processing.common_processing_output_revision "
            "(id, aggregate_id, organization_id, project_id, classification, revision_no, "
            "schema_id, schema_version, content_hash, created_at, created_by, change_reason, "
            "request_id, trace_id, label, source_document_id, source_document_revision_id, "
            "source_document_sha256, source_canonical_artifact_sha256, mapping_profile_id, "
            "mapping_profile_revision_id, mapping_profile_sha256, independent_quantity, "
            "step_count, stage_count, final_point_count, output_artifact_id, output_sha256) "
            "VALUES (:id, :aggregate_id, :organization_id, :project_id, 'internal', 1, "
            ":schema_id, '1.3.0', :content_hash, :now, :actor, 'legacy compatibility', "
            ":request_id, :trace_id, 'Legacy output', :source_id, :source_revision, "
            ":source_sha, :artifact_sha, :mapping_id, :mapping_revision, :mapping_sha, "
            "'strain.engineering', 1, 2, 2, :artifact_id, :output_sha)"
        ),
        {
            "id": LEGACY_OUTPUT_REVISION,
            "aggregate_id": LEGACY_OUTPUT,
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "schema_id": "urn:cmp:processing:common-output:1.3.0",
            "content_hash": "1" * 64,
            "now": NOW,
            "actor": ACTOR,
            "request_id": REQUEST,
            "trace_id": TRACE,
            "source_id": UUID(int=101),
            "source_revision": UUID(int=102),
            "source_sha": "2" * 64,
            "artifact_sha": "3" * 64,
            "mapping_id": UUID(int=103),
            "mapping_revision": UUID(int=104),
            "mapping_sha": "4" * 64,
            "artifact_id": UUID(int=105),
            "output_sha": "5" * 64,
        },
    )
    connection.exec_driver_sql("SET session_replication_role = 'origin'")


def _seed_security(connection: sa.Connection, app_role: str) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO identity.principal "
            "(id, principal_type, display_name, active, created_at, updated_at) "
            "VALUES (:id, 'user', 'Unit data steward', true, :now, :now)"
        ),
        {"id": ACTOR, "now": NOW - timedelta(days=1)},
    )
    connection.execute(
        sa.text(
            "INSERT INTO identity.role_binding "
            "(id, organization_id, project_id, classification, subject_type, principal_id, "
            "role, max_classification, allow_export_controlled, valid_from, created_at, "
            "created_by, grant_reason) VALUES "
            "(:id, :organization_id, :project_id, 'restricted', 'principal', :principal_id, "
            "'data_steward', 'internal', false, :valid_from, :created_at, :created_by, :reason)"
        ),
        {
            "id": UUID(int=106),
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "principal_id": ACTOR,
            "valid_from": NOW - timedelta(hours=1),
            "created_at": NOW - timedelta(hours=2),
            "created_by": ACTOR,
            "reason": "issue 205 Unit Profile PostgreSQL fixture",
        },
    )
    connection.exec_driver_sql(
        "GRANT USAGE ON SCHEMA identity, revisioning, access_control, units "
        f'TO "{app_role}"'
    )
    connection.exec_driver_sql(
        "GRANT SELECT, INSERT, UPDATE ON units.unit_profile, "
        "units.unit_profile_revision, units.unit_profile_selection "
        f'TO "{app_role}"'
    )
    connection.exec_driver_sql(
        f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control TO "{app_role}"'
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[Harness]:
    assert POSTGRES_DSN is not None
    cluster_url = _url(POSTGRES_DSN)
    database_name = f"cmp_issue205_{uuid4().hex}"
    app_role = f"cmp_issue205_app_{uuid4().hex}"
    cluster = sa.create_engine(cluster_url, isolation_level="AUTOCOMMIT")
    with cluster.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        connection.exec_driver_sql(
            f'CREATE ROLE "{app_role}" LOGIN NOSUPERUSER NOCREATEDB '
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    database_url = cluster_url.set(database=database_name)
    admin = sa.create_engine(database_url, pool_pre_ping=True)
    app: Engine | None = None
    try:
        command.upgrade(_config(database_url), "20260925_094_issue160")
        with admin.begin() as connection:
            _seed_legacy_processing_output(connection)
        command.upgrade(_config(database_url), "head")
        with admin.begin() as connection:
            legacy_pin = connection.execute(
                sa.text(
                    "SELECT unit_profile_id, unit_profile_revision_id, unit_profile_sha256 "
                    "FROM processing.common_processing_output_revision WHERE id = :id"
                ),
                {"id": LEGACY_OUTPUT_REVISION},
            ).one()
            assert tuple(legacy_pin) == (None, None, None)
            _seed_security(connection, app_role)
        app = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        yield Harness(
            admin,
            sessions,
            rls,
            CommonUnitService(
                repository=SqlAlchemyUnitProfileRepository(
                    session_factory=sessions,
                    rls_context=rls,
                )
            ),
        )
    finally:
        if app is not None:
            app.dispose()
        if sa.inspect(admin).has_table("unit_profile", schema="units"):
            with admin.begin() as connection:
                connection.exec_driver_sql("SET session_replication_role = 'replica'")
                connection.exec_driver_sql("TRUNCATE TABLE units.unit_profile CASCADE")
                connection.exec_driver_sql("SET session_replication_role = 'origin'")
            command.downgrade(_config(database_url), "20260925_094_issue160")
        admin.dispose()
        with cluster.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            connection.exec_driver_sql(f'DROP ROLE "{app_role}"')
        cluster.dispose()


def _context(project_id: UUID = PROJECT_A) -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Unit data steward", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="urn:cmp:issue205-postgresql",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=REQUEST,
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext, permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=context.project_id,
        permission=permission,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=REQUEST,
        trace_id=TRACE,
        decided_at=NOW,
    )


def _content(label: str = "Engineering SI") -> UnitProfileContent:
    return UnitProfileContent(
        profile_key="engineering_si",
        label=label,
        description="Explicit non-production Unit Profile integration fixture.",
        non_production=True,
        selections=(
            UnitProfileSelection(
                "modulus.young", DimensionId.FORCE_PER_AREA, "MPa", "GPa", "Pa"
            ),
            UnitProfileSelection(
                "mass.density", DimensionId.MASS_PER_VOLUME, "g/cm3", "kg/m3", "kg/m3"
            ),
            UnitProfileSelection(
                "temperature.absolute", DimensionId.TEMPERATURE, "Cel", "K", "K"
            ),
            UnitProfileSelection(
                "temperature.difference", DimensionId.TEMPERATURE, "Cel", "K", "K"
            ),
        ),
    )


def test_stable_identity_immutable_revisions_exact_readback_and_rls(
    postgres: Harness,
) -> None:
    context = _context()
    write = _decision(context, Permission.UNITS_WRITE)
    read = _decision(context, Permission.UNITS_READ)
    created = postgres.service.create_profile(
        context,
        write,
        CreateUnitProfile(
            classification=DataClassification.INTERNAL,
            content=_content(),
            change_reason="create exact Unit Profile revision",
        ),
    )
    revised = postgres.service.revise_profile(
        context,
        write,
        created.id,
        ReviseUnitProfile(
            expected_current_revision_id=created.current.revision_id,
            content=replace(_content(), label="Engineering SI display revision"),
            change_reason="revise display label without mutating revision one",
        ),
    )

    assert revised.id == created.id
    assert revised.current.revision_id != created.current.revision_id
    assert revised.current.revision_no == 2
    assert postgres.service.get_profile(context, read, created.id).content == revised.content
    exact_one = postgres.service.get_profile_revision(
        context, read, created.id, created.current.revision_id
    )
    assert exact_one.content == created.content
    assert exact_one.current.content_hash == created.content.digest
    resolved = postgres.service.resolve_pin(
        context,
        read,
        UnitProfilePin(created.id, created.current.revision_id, created.content.digest),
    )
    assert resolved.content == created.content
    with pytest.raises(UnitError, match="content hash"):
        postgres.service.resolve_pin(
            context,
            read,
            UnitProfilePin(created.id, created.current.revision_id, "f" * 64),
        )

    with postgres.sessions() as session, session.begin():
        postgres.rls.bind_authorization(session, context, write)
        with pytest.raises(DBAPIError):
            session.execute(
                sa.text(
                    "UPDATE units.unit_profile_revision SET label = 'mutated' "
                    "WHERE id = :revision_id"
                ),
                {"revision_id": created.current.revision_id},
            )

    other_context = _context(PROJECT_B)
    other_read = _decision(other_context, Permission.UNITS_READ)
    with pytest.raises(UnitProfileNotFound):
        postgres.service.get_profile_revision(
            other_context,
            other_read,
            created.id,
            created.current.revision_id,
        )
