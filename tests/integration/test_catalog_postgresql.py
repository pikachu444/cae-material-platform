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
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.catalog.adapters.persistence.repository import (
    SqlAlchemyCatalogRepository,
    material_revision_table,
)
from cmp.modules.catalog.application.service import (
    CatalogService,
    CreateMaterial,
    CreateMaterialState,
    CreatePropertySet,
    ReviseMaterial,
)
from cmp.modules.catalog.domain.model import (
    CatalogNotFound,
    MaterialContent,
    MaterialStateContent,
    PropertySetContent,
    PropertySource,
    PropertySourceKind,
)
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import database_permissions_for
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
from cmp.modules.modeling.adapters.persistence.repository import (
    SqlAlchemyModelingRepository,
    material_model_revision_table,
)
from cmp.modules.modeling.application.service import (
    CreateReferenceLinearElasticModel,
    MaterialModelService,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import ReferenceModelNotFound
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.shared.domain.revisions import RevisionConflict
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        POSTGRES_DSN is None,
        reason="CMP_TEST_POSTGRES_DSN is required for PostgreSQL integration",
    ),
]

NOW = datetime(2026, 7, 13, 16, 0, tzinfo=UTC)
ORG = UUID("c9000000-0000-4000-8000-000000000001")
PROJECT_A = UUID("c9000000-0000-4000-8000-000000000002")
PROJECT_B = UUID("c9000000-0000-4000-8000-000000000003")
ACTOR = UUID("c9000000-0000-4000-8000-000000000004")
TRACE = "00-000000000000000000000000000000c9-00000000000000c9-01"


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    admin_engine: Engine
    sessions: sessionmaker[Session]
    rls: SqlAlchemyRlsContext
    service: CatalogService
    modeling: MaterialModelService


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


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t07_{uuid4().hex}"
    app_role = f"cmp_t07_app_{uuid4().hex}"
    cluster = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster.connect() as connection:
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
            connection.execute(
                sa.text(
                    "INSERT INTO identity.principal "
                    "(id, principal_type, display_name, active, created_at, updated_at) "
                    "VALUES (:id, 'user', 'T07 Catalog Steward', true, :now, :now)"
                ),
                {"id": ACTOR, "now": NOW - timedelta(days=1)},
            )
            connection.exec_driver_sql(
                "GRANT USAGE ON SCHEMA identity, revisioning, access_control, governance, "
                f'provenance, audit, catalog, modeling, artifact, plugin TO "{app_role}"'
            )
            for schema in (
                "identity",
                "governance",
                "provenance",
                "audit",
                "catalog",
                "modeling",
                "artifact",
                "plugin",
            ):
                connection.exec_driver_sql(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} "
                    f'TO "{app_role}"'
                )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control, revisioning, audit "
                f'TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        repository = SqlAlchemyCatalogRepository(
            session_factory=sessions,
            rls_context=rls,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
        modeling = MaterialModelService(
            repository=SqlAlchemyModelingRepository(
                session_factory=sessions,
                rls_context=rls,
                revision_hooks=(
                    SqlInitialLifecycleHook(),
                    SqlAlchemyRevisionProvenanceHook(),
                    SqlAlchemyRevisionAuditHook(),
                ),
            )
        )
        yield PostgresHarness(
            admin_engine=admin_engine,
            sessions=sessions,
            rls=rls,
            service=CatalogService(repository=repository),
            modeling=modeling,
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        admin_engine.dispose()
        with cluster.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            connection.exec_driver_sql(f'DROP ROLE "{app_role}"')
        cluster.dispose()


def _context(project_id: UUID = PROJECT_A) -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "T07 Catalog Steward", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext, permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=(
            (Role.MATERIAL_MODELER,)
            if permission in {Permission.MODELING_READ, Permission.MODELING_WRITE}
            else (Role.DATA_STEWARD,)
        ),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _source() -> PropertySource:
    return PropertySource(PropertySourceKind.MANUAL)


def test_material_state_property_revisions_are_immutable_tenant_scoped_and_provenanced(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    write = _decision(context, Permission.CATALOG_WRITE)
    read = _decision(context, Permission.CATALOG_READ)
    material = postgres.service.create_material(
        context,
        write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent("S355 Structural Steel", "S355", "steel"),
            "create reference material",
        ),
    )
    state = postgres.service.create_material_state(
        context,
        write,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "As received",
                manufacturing_route="hot rolled",
                lot_or_batch="DEMO-001",
            ),
            "record material state",
        ),
    )
    property_set = postgres.service.create_property_set(
        context,
        write,
        CreatePropertySet(
            PropertySetContent(
                state.id,
                state.current.record.revision_id,
                density_kg_per_m3=7850.0,
                density_source=_source(),
                youngs_modulus_pa=210_000_000_000.0,
                youngs_modulus_source=_source(),
                poisson_ratio=0.3,
                poisson_ratio_source=_source(),
            ),
            "record reference elastic property set",
        ),
    )

    detail = postgres.service.get_material_detail(context, read, material.id)
    assert detail.material.current.content.material_code == "S355"
    assert detail.states == (state,)
    assert detail.property_sets == (property_set,)
    assert detail.property_sets[0].current.content.youngs_modulus_pa == 210_000_000_000.0

    revised = postgres.service.revise_material(
        context,
        write,
        material.id,
        ReviseMaterial(
            material.current.record.revision_id,
            MaterialContent("S355 Structural Steel", "S355JR", "steel"),
            "correct material code",
        ),
    )
    assert revised.current.record.revision_no == 2
    assert revised.current.record.based_on_revision_id == material.current.record.revision_id

    with pytest.raises(RevisionConflict):
        postgres.service.revise_material(
            context,
            write,
            material.id,
            ReviseMaterial(
                material.current.record.revision_id,
                MaterialContent("S355 Structural Steel", "stale", "steel"),
                "prove stale revision is rejected",
            ),
        )

    with pytest.raises(DBAPIError):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, write)
            session.execute(
                sa.update(material_revision_table)
                .where(material_revision_table.c.id == material.current.record.revision_id)
                .values(material_code="mutated-original")
            )

    other_context = _context(PROJECT_B)
    with pytest.raises(CatalogNotFound):
        postgres.service.get_material(
            other_context,
            _decision(other_context, Permission.CATALOG_READ),
            material.id,
        )

    with postgres.admin_engine.connect() as connection:
        lifecycle_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM governance.lifecycle_event "
                "WHERE aggregate_type LIKE 'catalog.%'"
            )
        )
        provenance_count = connection.scalar(
            sa.text("SELECT count(*) FROM provenance.entity WHERE reference_type LIKE 'catalog.%'")
        )
        audit_count = connection.scalar(
            sa.text("SELECT count(*) FROM audit.event WHERE action LIKE 'catalog.%'")
        )
    assert lifecycle_count == provenance_count == audit_count == 4


def test_reference_material_model_is_immutable_source_pinned_and_tenant_scoped(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    catalog_write = _decision(context, Permission.CATALOG_WRITE)
    modeling_write = _decision(context, Permission.MODELING_WRITE)
    modeling_read = _decision(context, Permission.MODELING_READ)
    material = postgres.service.create_material(
        context,
        catalog_write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent("Reference steel", "REF-ELAST", "steel"),
            "create source material",
        ),
    )
    state = postgres.service.create_material_state(
        context,
        catalog_write,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "As supplied",
            ),
            "create source state",
        ),
    )
    property_set = postgres.service.create_property_set(
        context,
        catalog_write,
        CreatePropertySet(
            PropertySetContent(
                state.id,
                state.current.record.revision_id,
                density_kg_per_m3=7850.0,
                density_source=_source(),
                youngs_modulus_pa=210_000_000_000.0,
                youngs_modulus_source=_source(),
                poisson_ratio=0.3,
                poisson_ratio_source=_source(),
                yield_stress_pa=355_000_000.0,
                yield_stress_source=_source(),
            ),
            "record source elastic values",
        ),
    )

    model = postgres.modeling.create_reference_linear_elastic_model(
        context,
        modeling_write,
        CreateReferenceLinearElasticModel(
            material_state_id=state.id,
            property_set_revision_id=property_set.current.record.revision_id,
            change_reason="project typed source revision into reference IR",
        ),
    )

    assert model.current.content.material_revision_id == material.current.record.revision_id
    assert model.current.content.material_state_revision_id == state.current.record.revision_id
    assert model.current.content.property_set_revision_id == property_set.current.record.revision_id
    assert model.current.content.source_yield_stress_pa == 355_000_000.0
    assert postgres.modeling.get_material_model(context, modeling_read, model.id) == model
    assert postgres.modeling.list_material_models_for_state(context, modeling_read, state.id) == (
        model,
    )
    assert postgres.modeling.list_material_model_revisions(
        context,
        modeling_read,
        model.id,
    ) == (model.current,)

    with pytest.raises(DBAPIError):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, modeling_write)
            session.execute(
                sa.update(material_model_revision_table)
                .where(material_model_revision_table.c.id == model.current.record.revision_id)
                .values(youngs_modulus_pa=100_000_000_000.0)
            )

    other_context = _context(PROJECT_B)
    with pytest.raises(ReferenceModelNotFound):
        postgres.modeling.get_material_model(
            other_context,
            _decision(other_context, Permission.MODELING_READ),
            model.id,
        )

    with postgres.admin_engine.connect() as connection:
        lifecycle_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM governance.lifecycle_event "
                "WHERE aggregate_type = 'modeling.material_model'"
            )
        )
        provenance_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM provenance.entity "
                "WHERE reference_type = 'modeling.material_model.revision'"
            )
        )
        audit_count = connection.scalar(
            sa.text("SELECT count(*) FROM audit.event WHERE action = 'modeling.material_model'"),
        )
    assert lifecycle_count == provenance_count == audit_count == 1
