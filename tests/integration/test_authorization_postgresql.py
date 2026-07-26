from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.bootstrap.security import build_identity_services
from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.persistence.product_access import (
    SqlAlchemyProductAccessRepository,
)
from cmp.modules.identity_access.adapters.persistence.rls import (
    RlsContextMismatch,
    SqlAlchemyRlsContext,
)
from cmp.modules.identity_access.adapters.persistence.role_bindings import (
    SqlAlchemyRoleBindingRepository,
)
from cmp.modules.identity_access.application.authorization import (
    AuthorizationService,
    GrantProductAccess,
    GrantRoleBinding,
    ProductAccessAdministrationService,
    RevokeRoleBinding,
    RoleBindingAdministrationService,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDenied,
    BindingSubject,
    DataClassification,
    FeatureGrant,
    Permission,
    ProductRole,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]

NOW = datetime(2026, 7, 11, 6, 0, tzinfo=UTC)
ORG_A = UUID("70000000-0000-4000-8000-000000000001")
ORG_B = UUID("70000000-0000-4000-8000-000000000002")
PROJECT_A = UUID("70000000-0000-4000-8000-000000000003")
PROJECT_B = UUID("70000000-0000-4000-8000-000000000004")
PRINCIPAL_A = UUID("70000000-0000-4000-8000-000000000005")
PRINCIPAL_B = UUID("70000000-0000-4000-8000-000000000006")
ISSUER = "https://test-idp.invalid"
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
DOCUMENT_INTERNAL = UUID("70000000-0000-4000-8000-000000000010")
DOCUMENT_CONFIDENTIAL = UUID("70000000-0000-4000-8000-000000000011")
DOCUMENT_RESTRICTED = UUID("70000000-0000-4000-8000-000000000012")
DOCUMENT_EXPORT = UUID("70000000-0000-4000-8000-000000000013")
DOCUMENT_OTHER_PROJECT = UUID("70000000-0000-4000-8000-000000000014")
DOCUMENT_OTHER_ORG = UUID("70000000-0000-4000-8000-000000000015")


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    admin_engine: Engine
    app_engine: Engine
    database_url: URL
    app_role: str
    role_binding: sa.Table
    product_access_assignment: sa.Table
    document: sa.Table
    document_ref: sa.Table


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


def _insert_principal(connection: sa.Connection, principal_id: UUID, name: str) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO identity.principal "
            "(id, principal_type, display_name, active, created_at, updated_at) "
            "VALUES (:id, 'user', :name, true, :now, :now)"
        ),
        {"id": principal_id, "name": name, "now": NOW - timedelta(days=2)},
    )


def _binding_values(
    *,
    binding_id: UUID,
    organization_id: UUID,
    project_id: UUID | None,
    subject_type: str,
    principal_id: UUID | None,
    group_issuer: str | None,
    group_name: str | None,
    role: Role,
    maximum: DataClassification,
    export: bool = False,
    expires_at: datetime | None = None,
    revoked: bool = False,
) -> dict[str, object]:
    created_at = NOW - timedelta(days=2)
    valid_from = NOW - timedelta(days=1)
    return {
        "id": binding_id,
        "organization_id": organization_id,
        "project_id": project_id,
        "classification": "restricted",
        "subject_type": subject_type,
        "principal_id": principal_id,
        "group_issuer": group_issuer,
        "group_name": group_name,
        "role": role.value,
        "max_classification": maximum.value,
        "allow_export_controlled": export,
        "valid_from": valid_from,
        "expires_at": expires_at,
        "created_at": created_at,
        "created_by": PRINCIPAL_A,
        "grant_reason": "synthetic authorization integration fixture",
        "revoked_at": NOW - timedelta(hours=1) if revoked else None,
        "revoked_by": PRINCIPAL_A if revoked else None,
        "revocation_reason": "synthetic revocation" if revoked else None,
    }


def _seed(connection: sa.Connection, role_binding: sa.Table, document: sa.Table) -> None:
    _insert_principal(connection, PRINCIPAL_A, "Authorization User")
    _insert_principal(connection, PRINCIPAL_B, "Other Authorization User")
    connection.execute(
        sa.insert(role_binding),
        [
            _binding_values(
                binding_id=UUID("70000000-0000-4000-8000-000000000020"),
                organization_id=ORG_A,
                project_id=PROJECT_A,
                subject_type="principal",
                principal_id=PRINCIPAL_A,
                group_issuer=None,
                group_name=None,
                role=Role.DATA_STEWARD,
                maximum=DataClassification.CONFIDENTIAL,
            ),
            _binding_values(
                binding_id=UUID("70000000-0000-4000-8000-000000000021"),
                organization_id=ORG_A,
                project_id=PROJECT_A,
                subject_type="group",
                principal_id=None,
                group_issuer=ISSUER,
                group_name="export-reviewers",
                role=Role.DATA_STEWARD,
                maximum=DataClassification.RESTRICTED,
                export=True,
            ),
            _binding_values(
                binding_id=UUID("70000000-0000-4000-8000-000000000022"),
                organization_id=ORG_B,
                project_id=PROJECT_B,
                subject_type="principal",
                principal_id=PRINCIPAL_B,
                group_issuer=None,
                group_name=None,
                role=Role.DATA_STEWARD,
                maximum=DataClassification.RESTRICTED,
            ),
            _binding_values(
                binding_id=UUID("70000000-0000-4000-8000-000000000023"),
                organization_id=ORG_A,
                project_id=PROJECT_A,
                subject_type="principal",
                principal_id=PRINCIPAL_A,
                group_issuer=None,
                group_name=None,
                role=Role.MATERIAL_MODELER,
                maximum=DataClassification.RESTRICTED,
                expires_at=NOW,
            ),
            _binding_values(
                binding_id=UUID("70000000-0000-4000-8000-000000000024"),
                organization_id=ORG_A,
                project_id=PROJECT_A,
                subject_type="principal",
                principal_id=PRINCIPAL_A,
                group_issuer=None,
                group_name=None,
                role=Role.CAE_ANALYST,
                maximum=DataClassification.RESTRICTED,
                revoked=True,
            ),
            _binding_values(
                binding_id=UUID("70000000-0000-4000-8000-000000000025"),
                organization_id=ORG_A,
                project_id=None,
                subject_type="principal",
                principal_id=PRINCIPAL_A,
                group_issuer=None,
                group_name=None,
                role=Role.ORG_ADMIN,
                maximum=DataClassification.INTERNAL,
            ),
        ],
    )
    connection.execute(
        sa.insert(document),
        [
            {
                "id": DOCUMENT_INTERNAL,
                "organization_id": ORG_A,
                "project_id": PROJECT_A,
                "classification": "internal",
                "title": "internal-a",
            },
            {
                "id": DOCUMENT_CONFIDENTIAL,
                "organization_id": ORG_A,
                "project_id": PROJECT_A,
                "classification": "confidential",
                "title": "confidential-a",
            },
            {
                "id": DOCUMENT_RESTRICTED,
                "organization_id": ORG_A,
                "project_id": PROJECT_A,
                "classification": "restricted",
                "title": "restricted-a",
            },
            {
                "id": DOCUMENT_EXPORT,
                "organization_id": ORG_A,
                "project_id": PROJECT_A,
                "classification": "export_controlled",
                "title": "export-a",
            },
            {
                "id": DOCUMENT_OTHER_PROJECT,
                "organization_id": ORG_A,
                "project_id": PROJECT_B,
                "classification": "internal",
                "title": "internal-b",
            },
            {
                "id": DOCUMENT_OTHER_ORG,
                "organization_id": ORG_B,
                "project_id": PROJECT_B,
                "classification": "internal",
                "title": "internal-other-org",
            },
        ],
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t04_{uuid4().hex}"
    app_role = f"cmp_t04_app_{uuid4().hex}"
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
        fixture_sql = (
            PROJECT_ROOT / "tests/migrations/fixtures/T04_authorization_fixture.sql"
        ).read_text(encoding="utf-8")
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(fixture_sql)
            metadata = sa.MetaData()
            metadata.reflect(
                connection,
                schema="identity",
                only=["role_binding", "product_access_assignment"],
            )
            metadata.reflect(
                connection,
                schema="authorization_fixture",
                only=["protected_document", "document_ref"],
            )
            role_binding = metadata.tables["identity.role_binding"]
            product_access_assignment = metadata.tables[
                "identity.product_access_assignment"
            ]
            document = metadata.tables["authorization_fixture.protected_document"]
            document_ref = metadata.tables["authorization_fixture.document_ref"]
            _seed(connection, role_binding, document)
            connection.exec_driver_sql(
                f'GRANT USAGE ON SCHEMA identity, revisioning, access_control, '
                f'authorization_fixture TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT SELECT, INSERT, UPDATE ON identity.role_binding, '
                f'identity.product_access_assignment TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES '
                f'IN SCHEMA authorization_fixture TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None),
            pool_pre_ping=True,
        )
        yield PostgresHarness(
            admin_engine=admin_engine,
            app_engine=app_engine,
            database_url=database_url,
            app_role=app_role,
            role_binding=role_binding,
            product_access_assignment=product_access_assignment,
            document=document,
            document_ref=document_ref,
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        with admin_engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS authorization_fixture CASCADE")
            reviewer_rows = connection.execute(
                sa.text(
                    "SELECT count(*) FROM identity.product_access_assignment "
                    "WHERE product_role = 'reviewer'"
                )
            ).scalar_one()
        # Migration 090 deliberately rejects a lossy downgrade once immutable
        # Reviewer history exists. The isolated database is dropped below, so
        # do not mutate that history only to exercise the generic teardown.
        if reviewer_rows == 0:
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
    *,
    principal_id: UUID = PRINCIPAL_A,
    organization_id: UUID = ORG_A,
    project_id: UUID = PROJECT_A,
    groups: tuple[str, ...] = (),
    request_id: UUID | None = None,
    token_id: str | None = None,
) -> SecurityContext:
    return SecurityContext(
        principal=Principal(principal_id, PrincipalType.USER, "Authorization User", True),
        organization_id=organization_id,
        project_id=project_id,
        issuer=ISSUER,
        subject="authorization-user",
        token_id=token_id or str(uuid4()),
        groups=groups,
        scopes=("openid",),
        request_id=request_id or uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _services(
    postgres: PostgresHarness,
) -> tuple[AuthorizationService, SqlAlchemyRlsContext]:
    sessions = sessionmaker(postgres.app_engine, class_=Session, expire_on_commit=False)
    rls = SqlAlchemyRlsContext()
    repository = SqlAlchemyRoleBindingRepository(
        session_factory=sessions,
        rls_context=rls,
    )
    return AuthorizationService(bindings=repository, clock=lambda: NOW), rls


def test_application_role_is_non_bypass_and_subject_rls_resolves_only_active_bindings(
    postgres: PostgresHarness,
) -> None:
    service, _ = _services(postgres)
    context = _context(groups=("export-reviewers",))
    decision = service.authorize(context, Permission.DATASET_READ)

    with postgres.app_engine.connect() as connection:
        attributes = connection.execute(
            sa.text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
        owned_relations = connection.execute(
            sa.text(
                "SELECT count(*) FROM pg_class "
                "WHERE relowner = (SELECT oid FROM pg_roles WHERE rolname = current_user)"
            )
        ).scalar_one()
        without_context = connection.execute(
            sa.select(sa.func.count()).select_from(postgres.role_binding)
        ).scalar_one()

    assert attributes == (False, False)
    assert owned_relations == 0
    assert without_context == 0
    assert decision.roles == (Role.DATA_STEWARD,)
    assert decision.max_classification is DataClassification.RESTRICTED
    assert decision.allow_export_controlled

    admin_sessions = sessionmaker(postgres.admin_engine, class_=Session)
    with pytest.raises(DBAPIError) as bypass_error, admin_sessions() as session, session.begin():
        SqlAlchemyRlsContext.assert_application_role(session)
    assert getattr(bypass_error.value.orig, "sqlstate", None) == "42501"


def test_runtime_composition_accepts_only_the_non_bypass_application_role(
    postgres: PostgresHarness,
) -> None:
    services = build_identity_services(
        Settings(
            environment="test",
            oidc_issuer=ISSUER,
            oidc_audience="urn:cmp:test-api",
            oidc_jwks_url="https://test-idp.invalid/jwks",
            database_url=postgres.database_url.set(
                username=postgres.app_role,
                password=None,
            ).render_as_string(hide_password=False),
        )
    )
    try:
        assert services.security is not None
        assert services.authorization is not None
        assert services.rls_context is not None
    finally:
        assert services.engine is not None
        services.engine.dispose()

    with pytest.raises(DBAPIError) as owner_error:
        build_identity_services(
            Settings(
                environment="test",
                oidc_issuer=ISSUER,
                oidc_audience="urn:cmp:test-api",
                oidc_jwks_url="https://test-idp.invalid/jwks",
                database_url=postgres.database_url.render_as_string(
                    hide_password=False
                ),
            )
        )
    assert getattr(owner_error.value.orig, "sqlstate", None) == "42501"


def test_list_count_and_facets_hide_other_scope_and_higher_classification(
    postgres: PostgresHarness,
) -> None:
    service, rls = _services(postgres)
    context = _context()
    decision = service.authorize(context, Permission.DATASET_READ)
    sessions = sessionmaker(postgres.app_engine, class_=Session)

    with sessions() as session, session.begin():
        rls.bind_authorization(session, context, decision)
        rows = session.execute(
            sa.select(postgres.document.c.id, postgres.document.c.classification)
            .order_by(postgres.document.c.title)
        ).all()
        count = session.execute(
            sa.select(sa.func.count()).select_from(postgres.document)
        ).scalar_one()
        facets = session.execute(
            sa.select(
                postgres.document.c.classification,
                sa.func.count().label("document_count"),
            )
            .group_by(postgres.document.c.classification)
            .order_by(postgres.document.c.classification)
        ).all()

    assert [(row.id, row.classification) for row in rows] == [
        (DOCUMENT_CONFIDENTIAL, "confidential"),
        (DOCUMENT_INTERNAL, "internal"),
    ]
    assert count == 2
    assert [(row.classification, row.document_count) for row in facets] == [
        ("confidential", 1),
        ("internal", 1),
    ]


def test_exact_group_binding_adds_restricted_and_export_compartment_access(
    postgres: PostgresHarness,
) -> None:
    service, rls = _services(postgres)
    context = _context(groups=("export-reviewers",))
    decision = service.authorize(context, Permission.DATASET_READ)
    sessions = sessionmaker(postgres.app_engine, class_=Session)

    with sessions() as session, session.begin():
        rls.bind_authorization(session, context, decision)
        classifications = tuple(
            session.execute(
                sa.select(postgres.document.c.classification)
                .order_by(postgres.document.c.classification)
            ).scalars()
        )

    assert classifications == (
        "confidential",
        "export_controlled",
        "internal",
        "restricted",
    )


def test_missing_or_wrong_permission_context_returns_no_rows(
    postgres: PostgresHarness,
) -> None:
    service, rls = _services(postgres)
    context = _context()
    wrong_decision = service.authorize(context, Permission.ARTIFACT_READ)
    sessions = sessionmaker(postgres.app_engine, class_=Session)

    with sessions() as session, session.begin():
        missing = session.execute(
            sa.select(sa.func.count()).select_from(postgres.document)
        ).scalar_one()
    with sessions() as session, session.begin():
        rls.bind_authorization(session, context, wrong_decision)
        wrong = session.execute(
            sa.select(sa.func.count()).select_from(postgres.document)
        ).scalar_one()

    assert missing == 0
    assert wrong == 0


def test_write_policy_rejects_other_project_and_above_clearance(
    postgres: PostgresHarness,
) -> None:
    service, rls = _services(postgres)
    context = _context()
    decision = service.authorize(context, Permission.DATASET_WRITE)
    sessions = sessionmaker(postgres.app_engine, class_=Session)
    own_id = uuid4()

    with sessions() as session, session.begin():
        rls.bind_authorization(session, context, decision)
        session.execute(
            sa.insert(postgres.document).values(
                id=own_id,
                organization_id=ORG_A,
                project_id=PROJECT_A,
                classification="internal",
                title="authorized insert",
            )
        )

    with pytest.raises(DBAPIError) as project_error, sessions() as session, session.begin():
        rls.bind_authorization(session, context, decision)
        session.execute(
            sa.insert(postgres.document).values(
                id=uuid4(),
                organization_id=ORG_A,
                project_id=PROJECT_B,
                classification="internal",
                title="cross project insert",
            )
        )
    with pytest.raises(DBAPIError) as clearance_error, sessions() as session, session.begin():
        rls.bind_authorization(session, context, decision)
        session.execute(
            sa.insert(postgres.document).values(
                id=uuid4(),
                organization_id=ORG_A,
                project_id=PROJECT_A,
                classification="restricted",
                title="above clearance insert",
            )
        )

    assert getattr(project_error.value.orig, "sqlstate", None) == "42501"
    assert getattr(clearance_error.value.orig, "sqlstate", None) == "42501"


def _foreign_key_failure(
    postgres: PostgresHarness, target_document_id: UUID
) -> tuple[str | None, str | None]:
    service, rls = _services(postgres)
    context = _context()
    decision = service.authorize(context, Permission.DATASET_WRITE)
    sessions = sessionmaker(postgres.app_engine, class_=Session)
    with pytest.raises(DBAPIError) as raised, sessions() as session, session.begin():
        rls.bind_authorization(session, context, decision)
        session.execute(
            sa.insert(postgres.document_ref).values(
                id=uuid4(),
                organization_id=ORG_A,
                project_id=PROJECT_A,
                classification="internal",
                document_id=target_document_id,
                label="opaque reference",
            )
        )
    return (
        getattr(raised.value.orig, "sqlstate", None),
        getattr(getattr(raised.value.orig, "diag", None), "constraint_name", None),
    )


def test_tenant_composite_fk_has_same_surface_for_hidden_and_unknown_targets(
    postgres: PostgresHarness,
) -> None:
    hidden = _foreign_key_failure(postgres, DOCUMENT_OTHER_PROJECT)
    unknown = _foreign_key_failure(postgres, uuid4())

    assert hidden == unknown == ("23503", "fk_document_ref_document")


def test_transaction_context_cannot_be_rebound_to_another_project(
    postgres: PostgresHarness,
) -> None:
    _, rls = _services(postgres)
    first = _context()
    second = _context(project_id=PROJECT_B, request_id=first.request_id)
    sessions = sessionmaker(postgres.app_engine, class_=Session)

    with sessions() as session, session.begin():
        rls.bind_authentication(session, first)
        with pytest.raises(RlsContextMismatch, match="project_id"):
            rls.bind_authentication(session, second)

    elevated_groups = _context(
        groups=("export-reviewers",),
        request_id=first.request_id,
        token_id=first.token_id,
    )
    with sessions() as session, session.begin():
        rls.bind_authentication(session, first)
        with pytest.raises(RlsContextMismatch, match="groups"):
            rls.bind_authentication(session, elevated_groups)


def test_org_admin_appends_and_revokes_group_binding_through_rls(
    postgres: PostgresHarness,
) -> None:
    sessions = sessionmaker(postgres.app_engine, class_=Session, expire_on_commit=False)
    rls = SqlAlchemyRlsContext()
    repository = SqlAlchemyRoleBindingRepository(
        session_factory=sessions,
        rls_context=rls,
    )
    authorization = AuthorizationService(bindings=repository, clock=lambda: NOW)
    administration = RoleBindingAdministrationService(
        authorization=authorization,
        repository=repository,
        clock=lambda: NOW,
    )
    context = _context()
    binding = administration.grant(
        context,
        GrantRoleBinding(
            organization_id=ORG_A,
            project_id=PROJECT_A,
            subject=BindingSubject.for_group(ISSUER, "temporary-consumers"),
            role=Role.CONSUMER,
            max_classification=DataClassification.INTERNAL,
            allow_export_controlled=False,
            grant_reason="temporary release access",
        ),
    )
    group_context = _context(groups=("temporary-consumers",))

    granted = authorization.authorize(group_context, Permission.RELEASE_READ)
    administration.revoke(
        context,
        RevokeRoleBinding(binding.id, "temporary access ended"),
    )

    assert granted.roles == (Role.CONSUMER,)
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        authorization.authorize(group_context, Permission.RELEASE_READ)


def test_role_binding_grant_fields_are_immutable_and_revocation_is_one_way(
    postgres: PostgresHarness,
) -> None:
    binding_id = UUID("70000000-0000-4000-8000-000000000020")
    with pytest.raises(DBAPIError) as mutation_error, postgres.admin_engine.begin() as connection:
        connection.execute(
            sa.update(postgres.role_binding)
            .where(postgres.role_binding.c.id == binding_id)
            .values(role=Role.ORG_ADMIN.value)
        )
    assert getattr(mutation_error.value.orig, "sqlstate", None) == "55000"

    with postgres.admin_engine.begin() as connection:
        connection.execute(
            sa.update(postgres.role_binding)
            .where(postgres.role_binding.c.id == binding_id)
            .values(
                revoked_at=NOW,
                revoked_by=PRINCIPAL_A,
                revocation_reason="integration revocation",
            )
        )
    with pytest.raises(DBAPIError) as second_error, postgres.admin_engine.begin() as connection:
        connection.execute(
            sa.update(postgres.role_binding)
            .where(postgres.role_binding.c.id == binding_id)
            .values(revocation_reason="rewritten")
        )
    assert getattr(second_error.value.orig, "sqlstate", None) == "55000"


def test_reviewer_preset_is_enforced_and_project_scoped_under_rls(
    postgres: PostgresHarness,
) -> None:
    sessions = sessionmaker(postgres.app_engine, class_=Session, expire_on_commit=False)
    rls = SqlAlchemyRlsContext()
    bindings = SqlAlchemyRoleBindingRepository(session_factory=sessions, rls_context=rls)
    assignments = SqlAlchemyProductAccessRepository(
        session_factory=sessions,
        rls_context=rls,
    )
    authorization = AuthorizationService(
        bindings=bindings,
        product_assignments=assignments,
        clock=lambda: NOW,
    )
    administration = ProductAccessAdministrationService(
        authorization=authorization,
        repository=assignments,
        clock=lambda: NOW,
    )
    administrator = _context()

    assignment = administration.grant(
        administrator,
        GrantProductAccess(
            organization_id=ORG_A,
            project_id=PROJECT_A,
            subject=BindingSubject.for_group(ISSUER, "reviewers"),
            product_role=ProductRole.REVIEWER,
            feature_grants=(),
            max_classification=DataClassification.CONFIDENTIAL,
            allow_export_controlled=False,
            grant_reason="bounded review assignment",
        ),
    )
    modeler = _context(principal_id=PRINCIPAL_B, groups=("reviewers",))

    decision = authorization.authorize(modeler, Permission.CALIBRATION_EXECUTE)

    assert assignment.feature_grants == (
        FeatureGrant.MODEL_APPROVAL,
        FeatureGrant.PROCESSING_CALIBRATION,
        FeatureGrant.SOLVER_CARD_EXPORT,
    )
    assert decision.max_classification is DataClassification.CONFIDENTIAL
    assert authorization.authorize(modeler, Permission.REVIEW_DECIDE).permission is Permission.REVIEW_DECIDE
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        authorization.authorize(
            _context(project_id=PROJECT_B, groups=("reviewers",)),
            Permission.CALIBRATION_EXECUTE,
        )
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        authorization.authorize(modeler, Permission.IDENTITY_MANAGE)

    with postgres.app_engine.connect() as connection:
        without_context = connection.execute(
            sa.select(sa.func.count()).select_from(postgres.product_access_assignment)
        ).scalar_one()
    assert without_context == 0
