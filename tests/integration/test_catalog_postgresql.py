from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.catalog.adapters.persistence.repository import (
    SqlAlchemyCatalogRepository,
    material_lot_revision_table,
    material_revision_table,
    process_run_lot_flow_table,
    process_run_revision_table,
    state_genealogy_revision_table,
)
from cmp.modules.catalog.application.service import (
    CatalogService,
    CreateMaterial,
    CreateMaterialLot,
    CreateMaterialState,
    CreateProcessDefinition,
    CreateProcessRun,
    CreatePropertySet,
    CreateStateGenealogy,
    ReviseMaterial,
    ReviseProcessRun,
    ReviseStateGenealogy,
)
from cmp.modules.catalog.domain.model import (
    CatalogConflict,
    CatalogNotFound,
    LotKind,
    MaterialClass,
    MaterialContent,
    MaterialLotContent,
    MaterialStateContent,
    ProcessDefinitionContent,
    ProcessKind,
    PropertySetContent,
    PropertySource,
    PropertySourceKind,
    StateGenealogyContent,
)
from cmp.modules.catalog.domain.process_run import BalanceBasis, LotFlow, ProcessRunContent
from cmp.modules.exporting.adapters.persistence.repository import (
    SqlAlchemyExportingRepository,
    solver_card_revision_table,
)
from cmp.modules.exporting.application.service import (
    CreateReferenceOpenRadiossCard,
    SolverCardService,
)
from cmp.modules.exporting.domain.openradioss_elast import (
    ExportTarget,
    SolverCardNotFound,
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
from cmp.modules.modeling.adapters.persistence.linear_viscoelasticity_repository import (
    SqlAlchemyLinearViscoelasticRepository,
)
from cmp.modules.modeling.adapters.persistence.repository import (
    SqlAlchemyModelingRepository,
    material_model_revision_table,
)
from cmp.modules.modeling.application.linear_viscoelasticity import (
    CreateReferenceLinearViscoelasticModel,
    LinearViscoelasticModelService,
)
from cmp.modules.modeling.application.service import (
    CreateReferenceLinearElasticModel,
    MaterialModelService,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import ReferenceModelNotFound
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    PronyTerm,
)
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.testing.adapters.persistence.repository import (
    SqlAlchemyTestingRepository,
    specimen_source_lot_table,
)
from cmp.modules.testing.adapters.persistence.test_context_repository import (
    SqlAlchemyTestContextRepository,
    calibration_revision_table,
)
from cmp.modules.testing.application.service import (
    CreateReferenceTensileMethod,
    CreateReferenceTensileRun,
    CreateSpecimen,
    CreateSpecimenSource,
)
from cmp.modules.testing.application.service import TestingService as _TestingApplicationService
from cmp.modules.testing.application.test_context import (
    CreateCalibration,
    CreateCampaign,
    CreateCondition,
    CreateInstrument,
    CreateRunContext,
)
from cmp.modules.testing.application.test_context import (
    TestContextService as _TestContextApplicationService,
)
from cmp.modules.testing.domain.reference_tensile import TestingConflict as _TestingConflict
from cmp.modules.testing.domain.specimen_source import (
    SpecimenSourceContent,
    SpecimenSourceLot,
)
from cmp.modules.testing.domain.test_context import (
    CalibrationResult,
    InstrumentCalibrationContent,
    InstrumentContent,
    LoadingRateUnit,
    StandardConformance,
)
from cmp.modules.testing.domain.test_context import (
    TestCampaignContent as _TestCampaignContent,
)
from cmp.modules.testing.domain.test_context import (
    TestConditionContent as _TestConditionContent,
)
from cmp.modules.testing.domain.test_context import (
    TestRunContextContent as _TestRunContextContent,
)
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
    linear_viscoelasticity: LinearViscoelasticModelService
    exporting: SolverCardService
    testing: _TestingApplicationService
    test_context: _TestContextApplicationService


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
                "provenance, audit, catalog, testing, modeling, exporting, artifact, "
                f'plugin TO "{app_role}"'
            )
            for schema in (
                "identity",
                "governance",
                "provenance",
                "audit",
                "catalog",
                "testing",
                "modeling",
                "exporting",
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
        exporting = SolverCardService(
            repository=SqlAlchemyExportingRepository(
                session_factory=sessions,
                rls_context=rls,
                revision_hooks=(
                    SqlInitialLifecycleHook(),
                    SqlAlchemyRevisionProvenanceHook(),
                    SqlAlchemyRevisionAuditHook(),
                ),
            )
        )
        linear_viscoelasticity = LinearViscoelasticModelService(
            repository=SqlAlchemyLinearViscoelasticRepository(
                session_factory=sessions,
                rls_context=rls,
                revision_hooks=(
                    SqlInitialLifecycleHook(),
                    SqlAlchemyRevisionProvenanceHook(),
                    SqlAlchemyRevisionAuditHook(),
                ),
            ),
            material_models=modeling,
        )
        testing = _TestingApplicationService(
            repository=SqlAlchemyTestingRepository(
                session_factory=sessions,
                rls_context=rls,
                revision_hooks=(
                    SqlInitialLifecycleHook(),
                    SqlAlchemyRevisionProvenanceHook(),
                    SqlAlchemyRevisionAuditHook(),
                ),
            )
        )
        test_context = _TestContextApplicationService(
            repository=SqlAlchemyTestContextRepository(
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
            linear_viscoelasticity=linear_viscoelasticity,
            exporting=exporting,
            testing=testing,
            test_context=test_context,
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
            if permission
            in {
                Permission.MODELING_READ,
                Permission.MODELING_WRITE,
                Permission.EXPORT_READ,
                Permission.EXPORT_EXECUTE,
            }
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
            MaterialContent(
                "S355 Structural Steel",
                "S355",
                "steel",
                material_class=MaterialClass.METAL,
            ),
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
    assert detail.material.current.content.material_class is MaterialClass.METAL
    assert postgres.service.list_materials(context, read, material_class=MaterialClass.METAL) == (
        material,
    )
    assert detail.states == (state,)
    assert detail.property_sets == (property_set,)
    assert detail.property_sets[0].current.content.youngs_modulus_pa == 210_000_000_000.0

    revised = postgres.service.revise_material(
        context,
        write,
        material.id,
        ReviseMaterial(
            material.current.record.revision_id,
            MaterialContent(
                "S355 Structural Steel",
                "S355JR",
                "steel",
                material_class=MaterialClass.METAL,
            ),
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
                MaterialContent(
                    "S355 Structural Steel",
                    "stale",
                    "steel",
                    material_class=MaterialClass.METAL,
                ),
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


def test_process_run_lot_and_state_genealogy_are_revision_pinned_and_tenant_scoped(
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
            MaterialContent("Reference genealogy steel", "GEN-01", "steel"),
            "create genealogy material",
        ),
    )
    state = postgres.service.create_material_state(
        context,
        write,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "Quenched and tempered",
            ),
            "create genealogy state",
        ),
    )
    manufacturing = postgres.service.create_process_definition(
        context,
        write,
        CreateProcessDefinition(
            DataClassification.INTERNAL,
            ProcessDefinitionContent(
                "MFG-FORGING-01", "Closed-die forging", ProcessKind.MANUFACTURING
            ),
            "register manufacturing process",
        ),
    )
    heat = postgres.service.create_process_definition(
        context,
        write,
        CreateProcessDefinition(
            DataClassification.INTERNAL,
            ProcessDefinitionContent("HT-QT-01", "Quench and temper", ProcessKind.HEAT_TREATMENT),
            "register heat-treatment process",
        ),
    )
    lot = postgres.service.create_material_lot(
        context,
        write,
        CreateMaterialLot(
            MaterialLotContent(
                material.id,
                material.current.record.revision_id,
                "HEAT-2026-0716",
                LotKind.BATCH,
                manufacturer="Reference mill",
            ),
            "register source heat",
        ),
    )
    output_lot_a = postgres.service.create_material_lot(
        context,
        write,
        CreateMaterialLot(
            MaterialLotContent(
                material.id,
                material.current.record.revision_id,
                "HEAT-2026-0716-A",
                LotKind.BATCH,
            ),
            "register first split output",
        ),
    )
    output_lot_b = postgres.service.create_material_lot(
        context,
        write,
        CreateMaterialLot(
            MaterialLotContent(
                material.id,
                material.current.record.revision_id,
                "HEAT-2026-0716-B",
                LotKind.BATCH,
            ),
            "register second split output",
        ),
    )
    genealogy = postgres.service.create_state_genealogy(
        context,
        write,
        CreateStateGenealogy(
            StateGenealogyContent(
                material_state_id=state.id,
                material_state_revision_id=state.current.record.revision_id,
                manufacturing_process_id=manufacturing.id,
                manufacturing_process_revision_id=manufacturing.current.record.revision_id,
                heat_treatment_process_id=heat.id,
                heat_treatment_process_revision_id=heat.current.record.revision_id,
                material_lot_id=lot.id,
                material_lot_revision_id=lot.current.record.revision_id,
            ),
            "pin exact genealogy sources",
        ),
    )
    run_content = ProcessRunContent(
        process_definition_id=manufacturing.id,
        process_definition_revision_id=manufacturing.current.record.revision_id,
        material_state_id=state.id,
        material_state_revision_id=state.current.record.revision_id,
        run_code="SPLIT-2026-0716",
        started_at=NOW,
        ended_at=NOW + timedelta(hours=1),
        operator_name="Reference operator",
        equipment_reference="PRESS-01",
        balance_basis=BalanceBasis.MASS,
        balance_tolerance_fraction=Decimal("0.001"),
        balance_not_assessed_reason=None,
        inputs=(
            LotFlow.from_original(
                material_lot_id=lot.id,
                material_lot_revision_id=lot.current.record.revision_id,
                original_quantity=Decimal("1"),
                original_unit="kg",
            ),
        ),
        outputs=(
            LotFlow.from_original(
                material_lot_id=output_lot_a.id,
                material_lot_revision_id=output_lot_a.current.record.revision_id,
                original_quantity=Decimal("400"),
                original_unit="g",
            ),
            LotFlow.from_original(
                material_lot_id=output_lot_b.id,
                material_lot_revision_id=output_lot_b.current.record.revision_id,
                original_quantity=Decimal("600"),
                original_unit="g",
            ),
        ),
    )
    process_run = postgres.service.create_process_run(
        context, write, CreateProcessRun(run_content, "record physical split")
    )
    testing_write = _decision(context, Permission.TESTING_WRITE)
    testing_read = _decision(context, Permission.TESTING_READ)
    specimen = postgres.testing.create_specimen(
        context,
        testing_write,
        CreateSpecimen(
            state.id,
            state.current.record.revision_id,
            "GEN-SPECIMEN-01",
            "rolling",
            "cut from first split output",
            "register genealogy specimen",
        ),
    )
    specimen_source = postgres.testing.create_specimen_source(
        context,
        testing_write,
        CreateSpecimenSource(
            SpecimenSourceContent(
                specimen_id=specimen.id,
                specimen_revision_id=specimen.current.record.revision_id,
                sources=(
                    SpecimenSourceLot(
                        output_lot_a.id,
                        output_lot_a.current.record.revision_id,
                        "source split Lot",
                    ),
                ),
            ),
            "pin specimen source Lot",
        ),
    )

    assert postgres.service.list_process_definitions(context, read) == (
        manufacturing,
        heat,
    )
    assert postgres.service.list_material_lots(context, read, material.id) == (
        lot,
        output_lot_a,
        output_lot_b,
    )
    assert postgres.service.get_state_genealogy_for_state(context, read, state.id) == genealogy
    assert postgres.service.list_process_runs_for_state(context, read, state.id) == (process_run,)
    assert process_run.current.content.balance is not None
    assert process_run.current.content.balance.input_total == Decimal("1.000000000000")
    assert (
        postgres.testing.get_specimen_source_for_specimen(context, testing_read, specimen.id)
        == specimen_source
    )

    revised_run = postgres.service.revise_process_run(
        context,
        write,
        process_run.id,
        ReviseProcessRun(
            process_run.current.record.revision_id,
            replace(run_content, note="reviewed physical split"),
            "record Process Run review",
        ),
    )
    assert revised_run.current.record.revision_no == 2

    with pytest.raises(DBAPIError):
        postgres.service.create_process_run(
            context,
            write,
            CreateProcessRun(
                ProcessRunContent(
                    process_definition_id=manufacturing.id,
                    process_definition_revision_id=(manufacturing.current.record.revision_id),
                    material_state_id=state.id,
                    material_state_revision_id=state.current.record.revision_id,
                    run_code="CYCLE-REJECTED",
                    started_at=NOW + timedelta(hours=2),
                    ended_at=None,
                    operator_name=None,
                    equipment_reference=None,
                    balance_basis=BalanceBasis.MASS,
                    balance_tolerance_fraction=Decimal("0"),
                    balance_not_assessed_reason=None,
                    inputs=(
                        LotFlow.from_original(
                            material_lot_id=output_lot_a.id,
                            material_lot_revision_id=(output_lot_a.current.record.revision_id),
                            original_quantity=Decimal("1"),
                            original_unit="kg",
                        ),
                    ),
                    outputs=(
                        LotFlow.from_original(
                            material_lot_id=lot.id,
                            material_lot_revision_id=lot.current.record.revision_id,
                            original_quantity=Decimal("1"),
                            original_unit="kg",
                        ),
                    ),
                ),
                "prove graph cycle is rejected",
            ),
        )

    with pytest.raises(CatalogConflict, match="matching process kind"):
        postgres.service.revise_state_genealogy(
            context,
            write,
            genealogy.id,
            ReviseStateGenealogy(
                genealogy.current.record.revision_id,
                StateGenealogyContent(
                    material_state_id=state.id,
                    material_state_revision_id=state.current.record.revision_id,
                    heat_treatment_process_id=manufacturing.id,
                    heat_treatment_process_revision_id=(manufacturing.current.record.revision_id),
                ),
                "reject role mismatch",
            ),
        )

    revised = postgres.service.revise_state_genealogy(
        context,
        write,
        genealogy.id,
        ReviseStateGenealogy(
            genealogy.current.record.revision_id,
            StateGenealogyContent(
                material_state_id=state.id,
                material_state_revision_id=state.current.record.revision_id,
                manufacturing_process_id=manufacturing.id,
                manufacturing_process_revision_id=manufacturing.current.record.revision_id,
                heat_treatment_process_id=heat.id,
                heat_treatment_process_revision_id=heat.current.record.revision_id,
                material_lot_id=lot.id,
                material_lot_revision_id=lot.current.record.revision_id,
                note="Reviewed genealogy",
            ),
            "record genealogy review note",
        ),
    )
    assert revised.current.record.revision_no == 2
    assert revised.current.record.based_on_revision_id == genealogy.current.record.revision_id

    with pytest.raises(DBAPIError):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, write)
            session.execute(
                sa.update(state_genealogy_revision_table)
                .where(state_genealogy_revision_table.c.id == genealogy.current.record.revision_id)
                .values(note="mutated immutable link")
            )

    other_context = _context(PROJECT_B)
    assert (
        postgres.service.get_state_genealogy_for_state(
            other_context,
            _decision(other_context, Permission.CATALOG_READ),
            state.id,
        )
        is None
    )

    with postgres.admin_engine.connect() as connection:
        secured_tables = {
            str(row[0]): bool(row[1])
            for row in connection.execute(
                sa.text(
                    "SELECT c.relname, c.relrowsecurity AND c.relforcerowsecurity "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='catalog' AND c.relname IN "
                    "('process_definition','process_definition_revision','material_lot',"
                    "'material_lot_revision','state_genealogy','state_genealogy_revision',"
                    "'process_run','process_run_revision','process_run_lot_flow')"
                )
            ).all()
        }
        triggers = {
            str(row[0])
            for row in connection.execute(
                sa.text(
                    "SELECT g.tgname FROM pg_trigger g JOIN pg_class c ON c.oid=g.tgrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='catalog' AND c.relname='state_genealogy_revision' "
                    "AND NOT g.tgisinternal"
                )
            ).all()
        }
        testing_secured = {
            str(row[0]): bool(row[1])
            for row in connection.execute(
                sa.text(
                    "SELECT c.relname, c.relrowsecurity AND c.relforcerowsecurity "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='testing' AND c.relname IN "
                    "('specimen_source_genealogy','specimen_source_genealogy_revision',"
                    "'specimen_source_lot')"
                )
            ).all()
        }
    assert secured_tables == {
        "process_definition": True,
        "process_definition_revision": True,
        "material_lot": True,
        "material_lot_revision": True,
        "state_genealogy": True,
        "state_genealogy_revision": True,
        "process_run": True,
        "process_run_revision": True,
        "process_run_lot_flow": True,
    }
    assert "catalog_state_genealogy_source_guard" in triggers
    assert testing_secured == {
        "specimen_source_genealogy": True,
        "specimen_source_genealogy_revision": True,
        "specimen_source_lot": True,
    }

    with pytest.raises(DBAPIError):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, write)
            session.execute(
                sa.update(material_lot_revision_table)
                .where(material_lot_revision_table.c.id == lot.current.record.revision_id)
                .values(lot_code="MUTATED")
            )

    with pytest.raises(DBAPIError):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.update(process_run_lot_flow_table)
                .where(
                    process_run_lot_flow_table.c.process_run_revision_id
                    == process_run.current.record.revision_id
                )
                .values(original_quantity=Decimal("2"))
            )

    with pytest.raises(DBAPIError):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.update(specimen_source_lot_table)
                .where(
                    specimen_source_lot_table.c.specimen_source_revision_id
                    == specimen_source.current.record.revision_id
                )
                .values(note="mutated immutable source")
            )

    with postgres.admin_engine.connect() as connection:
        revision_count = connection.scalar(
            sa.select(sa.func.count()).select_from(process_run_revision_table)
        )
    assert revision_count == 2


def test_test_run_context_pins_valid_calibration_and_rejects_stale_or_overlap(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    catalog_write = _decision(context, Permission.CATALOG_WRITE)
    testing_write = _decision(context, Permission.TESTING_WRITE)
    testing_read = _decision(context, Permission.TESTING_READ)
    material = postgres.service.create_material(
        context,
        catalog_write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent("T40 context steel", f"T40-{uuid4().hex[:8]}", "steel"),
            "create T40 material",
        ),
    )
    state = postgres.service.create_material_state(
        context,
        catalog_write,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "T40 governed state",
            ),
            "create T40 state",
        ),
    )
    specimen = postgres.testing.create_specimen(
        context,
        testing_write,
        CreateSpecimen(
            state.id,
            state.current.record.revision_id,
            f"T40-{uuid4().hex[:8]}",
            "rolling",
            None,
            "create T40 specimen",
        ),
    )
    method = postgres.testing.create_reference_tensile_method(
        context,
        testing_write,
        CreateReferenceTensileMethod(DataClassification.INTERNAL, "create T40 method"),
    )
    run = postgres.testing.create_reference_tensile_run(
        context,
        testing_write,
        CreateReferenceTensileRun(
            specimen.id,
            specimen.current.record.revision_id,
            method.id,
            method.current.record.revision_id,
            f"T40-RUN-{uuid4().hex[:8]}",
            NOW,
            296.15,
            2.0,
            "create T40 run",
        ),
    )
    campaign = postgres.test_context.create_campaign(
        context,
        testing_write,
        CreateCampaign(
            _TestCampaignContent(
                method.id,
                method.current.record.revision_id,
                f"T40-CMP-{uuid4().hex[:8]}",
                "Governed tensile campaign",
                "Characterize the selected State",
                "Three rolling-direction coupons",
                3,
                StandardConformance.CONFORMANT,
                "ISO 6892-1",
                "2019",
                None,
            ),
            "create T40 campaign",
        ),
    )
    instrument = postgres.test_context.create_instrument(
        context,
        testing_write,
        CreateInstrument(
            DataClassification.INTERNAL,
            InstrumentContent(
                f"UTM-{uuid4().hex[:8]}",
                "Reference universal tester",
                f"SN-{uuid4().hex[:8]}",
                "Reference laboratory",
                None,
                None,
                None,
            ),
            "create T40 instrument",
        ),
    )
    calibration = postgres.test_context.create_calibration(
        context,
        testing_write,
        CreateCalibration(
            InstrumentCalibrationContent(
                instrument.id,
                instrument.current.record.revision_id,
                f"CAL-{uuid4().hex[:8]}",
                "CERT-T40",
                "Reference calibration laboratory",
                NOW - timedelta(days=10),
                NOW - timedelta(days=10),
                NOW + timedelta(days=355),
                CalibrationResult.PASSED,
                None,
            ),
            "record valid T40 calibration",
        ),
    )
    stale_calibration = postgres.test_context.create_calibration(
        context,
        testing_write,
        CreateCalibration(
            InstrumentCalibrationContent(
                instrument.id,
                instrument.current.record.revision_id,
                f"CAL-STALE-{uuid4().hex[:8]}",
                "CERT-T40-STALE",
                "Reference calibration laboratory",
                NOW - timedelta(days=400),
                NOW - timedelta(days=400),
                NOW - timedelta(days=20),
                CalibrationResult.PASSED,
                None,
            ),
            "record historical expired calibration",
        ),
    )
    condition = postgres.test_context.create_condition(
        context,
        testing_write,
        CreateCondition(
            _TestConditionContent(
                method.id,
                method.current.record.revision_id,
                NOW,
                None,
                Decimal("296.15"),
                None,
                Decimal("48.5"),
                Decimal("2"),
                LoadingRateUnit.MILLIMETER_PER_MINUTE,
                "rolling",
                "air",
                None,
            ),
            "capture typed T40 conditions",
        ),
    )
    with pytest.raises(_TestingConflict, match="not usable"):
        postgres.test_context.create_run_context(
            context,
            testing_write,
            CreateRunContext(
                _TestRunContextContent(
                    run.id,
                    run.current.record.revision_id,
                    campaign.id,
                    campaign.current.record.revision_id,
                    condition.id,
                    condition.current.record.revision_id,
                    instrument.id,
                    instrument.current.record.revision_id,
                    stale_calibration.id,
                    stale_calibration.current.record.revision_id,
                    None,
                ),
                "reject stale T40 calibration",
            ),
        )
    linked = postgres.test_context.create_run_context(
        context,
        testing_write,
        CreateRunContext(
            _TestRunContextContent(
                run.id,
                run.current.record.revision_id,
                campaign.id,
                campaign.current.record.revision_id,
                condition.id,
                condition.current.record.revision_id,
                instrument.id,
                instrument.current.record.revision_id,
                calibration.id,
                calibration.current.record.revision_id,
                None,
            ),
            "bind exact T40 execution context",
        ),
    )

    assert postgres.test_context.get_run_context_for_run(context, testing_read, run.id) == linked
    with pytest.raises(_TestingConflict, match="cannot overlap"):
        postgres.test_context.create_calibration(
            context,
            testing_write,
            CreateCalibration(
                replace(
                    calibration.current.content,
                    calibration_code=f"CAL-OVERLAP-{uuid4().hex[:8]}",
                    certificate_reference="CERT-OVERLAP",
                ),
                "reject overlapping calibration",
            ),
        )
    with pytest.raises(DBAPIError):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, testing_write)
            session.execute(
                sa.update(calibration_revision_table)
                .where(calibration_revision_table.c.id == calibration.current.record.revision_id)
                .values(certificate_reference="MUTATED")
            )
    other = _context(PROJECT_B)
    assert (
        postgres.test_context.list_instruments(other, _decision(other, Permission.TESTING_READ))
        == ()
    )


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
            sa.text(
                "SELECT count(*) FROM audit.event "
                "WHERE action = 'modeling.material_model.revision.create'"
            ),
        )
    assert lifecycle_count == provenance_count == audit_count == 1


def test_solver_card_is_source_pinned_immutable_provenanced_and_tenant_scoped(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    catalog_write = _decision(context, Permission.CATALOG_WRITE)
    modeling_write = _decision(context, Permission.MODELING_WRITE)
    export_read = _decision(context, Permission.EXPORT_READ)
    export_execute = _decision(context, Permission.EXPORT_EXECUTE)
    material = postgres.service.create_material(
        context,
        catalog_write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent("Reference export steel", "REF-CARD", "steel"),
            "create solver-card source material",
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
            "create solver-card source state",
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
            "record typed export source values",
        ),
    )
    model = postgres.modeling.create_reference_linear_elastic_model(
        context,
        modeling_write,
        CreateReferenceLinearElasticModel(
            material_state_id=state.id,
            property_set_revision_id=property_set.current.record.revision_id,
            change_reason="project source revision into reference IR",
        ),
    )
    target = ExportTarget("openradioss", "2025", "kg_m_s")
    report = postgres.exporting.preflight_reference_openradioss(
        context,
        export_read,
        model.id,
        target,
    )
    card, returned_report = postgres.exporting.create_reference_openradioss_card(
        context,
        export_execute,
        CreateReferenceOpenRadiossCard(
            material_model_id=model.id,
            material_model_revision_id=model.current.record.revision_id,
            target=target,
            expected_mapping_report_sha256=report.digest,
            solver_material_id=17,
            card_title="Reference export steel",
            change_reason="generate acknowledged reference solver card",
        ),
    )

    assert returned_report == report
    assert card.current.content.material_model_revision_id == model.current.record.revision_id
    assert card.current.content.mapping_report_sha256 == report.digest
    assert "/MAT/ELAST/17/1" in card.current.content.card_text
    assert postgres.exporting.get_solver_card(context, export_read, card.id) == card
    assert postgres.exporting.list_solver_cards_for_model(context, export_read, model.id) == (card,)
    assert postgres.exporting.list_solver_card_revisions(context, export_read, card.id) == (
        card.current,
    )

    with pytest.raises(DBAPIError):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, export_execute)
            session.execute(
                sa.update(solver_card_revision_table)
                .where(solver_card_revision_table.c.id == card.current.record.revision_id)
                .values(card_text="mutated immutable card")
            )

    other_context = _context(PROJECT_B)
    with pytest.raises(SolverCardNotFound):
        postgres.exporting.get_solver_card(
            other_context,
            _decision(other_context, Permission.EXPORT_READ),
            card.id,
        )

    with postgres.admin_engine.connect() as connection:
        lifecycle_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM governance.lifecycle_event "
                "WHERE aggregate_type = 'exporting.solver_card'"
            )
        )
        provenance_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM provenance.entity "
                "WHERE reference_type = 'exporting.solver_card.revision'"
            )
        )
        usage_count = connection.scalar(
            sa.text("SELECT count(*) FROM provenance.usage WHERE role = 'material_model_ir'")
        )
        derivation_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM provenance.derivation "
                "WHERE derivation_kind = 'solver_card_export'"
            )
        )
        audit_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM audit.event "
                "WHERE action = 'exporting.solver_card.revision.create'"
            ),
        )
    assert lifecycle_count == provenance_count == audit_count == 1
    assert usage_count == derivation_count == 1


def test_linear_viscoelastic_model_persists_ordered_terms_and_exact_source_revisions(
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
            MaterialContent(
                "Reference polymer",
                "REF-PRONY",
                "polymer",
                material_class=MaterialClass.POLYMER,
            ),
            "create polymer source",
        ),
    )
    state = postgres.service.create_material_state(
        context,
        catalog_write,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "Conditioned 23 C",
            ),
            "create conditioned source state",
        ),
    )
    property_set = postgres.service.create_property_set(
        context,
        catalog_write,
        CreatePropertySet(
            PropertySetContent(
                state.id,
                state.current.record.revision_id,
                density_kg_per_m3=1_200.0,
                density_source=_source(),
                youngs_modulus_pa=3_000_000_000.0,
                youngs_modulus_source=_source(),
                poisson_ratio=0.35,
                poisson_ratio_source=_source(),
            ),
            "record polymer instantaneous elastic values",
        ),
    )
    model = postgres.linear_viscoelasticity.create_model(
        context,
        modeling_write,
        CreateReferenceLinearViscoelasticModel(
            material_state_id=state.id,
            property_set_revision_id=property_set.current.record.revision_id,
            bulk_relaxation_status=BulkRelaxationStatus.NOT_CHARACTERIZED,
            terms=(PronyTerm(0.2, 0.0, 0.1), PronyTerm(0.3, 0.0, 10.0)),
            change_reason="create typed reference Prony IR",
        ),
    )
    restored = postgres.linear_viscoelasticity.get_model(context, modeling_read, model.id)
    assert restored == model
    assert restored.current.content.material_revision_id == material.current.record.revision_id
    assert restored.current.content.material_state_revision_id == state.current.record.revision_id
    assert (
        restored.current.content.property_set_revision_id == property_set.current.record.revision_id
    )
    assert tuple(term.relaxation_time_s for term in restored.current.content.terms) == (
        0.1,
        10.0,
    )

    with postgres.admin_engine.connect() as connection:
        row = connection.execute(
            sa.text(
                "SELECT r.term_count, count(t.ordinal), sum(t.g_ratio), sum(t.k_ratio) "
                "FROM modeling.linear_viscoelastic_revision r "
                "JOIN modeling.linear_viscoelastic_prony_term t "
                "ON t.organization_id=r.organization_id AND t.project_id=r.project_id "
                "AND t.material_model_revision_id=r.material_model_revision_id "
                "WHERE r.material_model_revision_id=:revision_id GROUP BY r.term_count"
            ),
            {"revision_id": model.current.record.revision_id},
        ).one()
    assert row == (2, 2, pytest.approx(0.5), pytest.approx(0.0))


def test_linear_viscoelastic_migration_installs_typed_rls_constraints_and_guards(
    postgres: PostgresHarness,
) -> None:
    with postgres.admin_engine.connect() as connection:
        tables = {
            str(row[0]): bool(row[1])
            for row in connection.execute(
                sa.text(
                    "SELECT t.relname, t.relrowsecurity AND t.relforcerowsecurity "
                    "FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace "
                    "WHERE n.nspname='modeling' AND t.relname IN "
                    "('linear_viscoelastic_revision','linear_viscoelastic_prony_term')"
                )
            ).all()
        }
        triggers = {
            str(row[0])
            for row in connection.execute(
                sa.text(
                    "SELECT g.tgname FROM pg_trigger g JOIN pg_class t ON t.oid=g.tgrelid "
                    "JOIN pg_namespace n ON n.oid=t.relnamespace "
                    "WHERE n.nspname='modeling' AND NOT g.tgisinternal"
                )
            ).all()
        }
        constraints = {
            str(row[0])
            for row in connection.execute(
                sa.text(
                    "SELECT c.conname FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid "
                    "JOIN pg_namespace n ON n.oid=t.relnamespace "
                    "WHERE n.nspname='modeling' AND t.relname IN "
                    "('linear_viscoelastic_revision','linear_viscoelastic_prony_term')"
                )
            ).all()
        }
    assert tables == {
        "linear_viscoelastic_revision": True,
        "linear_viscoelastic_prony_term": True,
    }
    assert "modeling_linear_viscoelastic_source_guard" in triggers
    assert "modeling_linear_viscoelastic_revision_immutable" in triggers
    assert "modeling_linear_viscoelastic_prony_term_immutable" in triggers
    assert "fk_modeling_linear_viscoelastic_revision_model" in constraints
    assert "fk_modeling_linear_viscoelastic_prony_summary" in constraints


def test_elastoplastic_migration_installs_typed_scoped_constraints_and_guards(
    postgres: PostgresHarness,
) -> None:
    with postgres.admin_engine.connect() as connection:
        constraints: dict[str, str] = {
            str(row[0]): str(row[1])
            for row in connection.execute(
                sa.text(
                    "SELECT c.conname, pg_get_constraintdef(c.oid) "
                    "FROM pg_constraint AS c "
                    "JOIN pg_class AS t ON t.oid = c.conrelid "
                    "JOIN pg_namespace AS n ON n.oid = t.relnamespace "
                    "WHERE (n.nspname, t.relname) IN "
                    "(('modeling', 'material_model_revision'), "
                    " ('exporting', 'solver_card_revision'))"
                )
            ).all()
        }
        triggers = {
            row[0]
            for row in connection.execute(
                sa.text(
                    "SELECT tgname FROM pg_trigger AS g "
                    "JOIN pg_class AS t ON t.oid = g.tgrelid "
                    "JOIN pg_namespace AS n ON n.oid = t.relnamespace "
                    "WHERE NOT g.tgisinternal AND (n.nspname, t.relname) IN "
                    "(('modeling', 'material_model_revision'), "
                    " ('exporting', 'solver_card_revision'))"
                )
            ).all()
        }
        rls: dict[str, bool] = {
            str(row[0]): bool(row[1])
            for row in connection.execute(
                sa.text(
                    "SELECT n.nspname || '.' || t.relname, t.relrowsecurity "
                    "FROM pg_class AS t "
                    "JOIN pg_namespace AS n ON n.oid = t.relnamespace "
                    "WHERE (n.nspname, t.relname) IN "
                    "(('modeling', 'material_model_revision'), "
                    " ('exporting', 'solver_card_revision'))"
                )
            ).all()
        }

    model_source_fk = constraints["fk_modeling_material_model_plastic_dataset_revision"]
    curve_artifact_fk = constraints["fk_modeling_material_model_hardening_artifact"]
    card_artifact_fk = constraints["fk_exporting_solver_card_hardening_artifact"]
    for definition in (model_source_fk, curve_artifact_fk, card_artifact_fk):
        assert "organization_id" in definition
        assert "project_id" in definition
        assert "classification" in definition
        assert "ON DELETE RESTRICT" in definition
    assert "source_point_count" in constraints["ck_modeling_material_model_plastic_counts"]
    assert "modeling_material_model_family_stable" in triggers
    assert "modeling_material_model_hardening_artifact_valid" in triggers
    assert rls == {
        "exporting.solver_card_revision": True,
        "modeling.material_model_revision": True,
    }
