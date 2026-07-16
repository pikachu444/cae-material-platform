from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.bootstrap.datasets import (
    SqlReferenceDatasetInputProvenanceHook,
    SqlShearRelaxationProcessedDatasetProvenanceHook,
    SqlViscoelasticDerivedDatasetProvenanceHook,
    SqlViscoelasticSelectionProvenanceHook,
)
from cmp.modules.artifacts.adapters.persistence.content import SqlAlchemyArtifactRepository
from cmp.modules.artifacts.adapters.persistence.uploads import SqlAlchemyUploadRepository
from cmp.modules.artifacts.adapters.storage.filesystem import FilesystemMultipartObjectStore
from cmp.modules.artifacts.application.content import (
    ArtifactPolicy,
    ArtifactService,
    ArtifactTransferCodec,
)
from cmp.modules.artifacts.application.uploads import (
    CompleteUpload,
    CreateUpload,
    RecordUploadPart,
    UploadCapabilityCodec,
    UploadPolicy,
    UploadService,
)
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
from cmp.modules.datasets.adapters.persistence.governed_import_repository import (
    SqlAlchemyGovernedImportRepository,
)
from cmp.modules.datasets.adapters.persistence.repository import SqlAlchemyDatasetRepository
from cmp.modules.datasets.adapters.persistence.viscoelastic_master_repository import (
    SqlAlchemyViscoelasticDatasetRepository,
)
from cmp.modules.datasets.application.governed_import import (
    IMPORT_PROFILE_AGGREGATE_TYPE,
    CreateImportProfile,
    ExecuteGovernedImport,
    GovernedImportService,
)
from cmp.modules.datasets.application.shear_relaxation import (
    ImportReferenceShearRelaxationCsv,
    ShearRelaxationDatasetService,
)
from cmp.modules.datasets.application.viscoelastic_master import (
    CreateViscoelasticSelection,
    ViscoelasticDatasetNotFound,
    ViscoelasticDatasetService,
    ViscoelasticSelectionMemberRef,
    ViscoelasticSelectionSnapshot,
)
from cmp.modules.datasets.domain.governed_tabular import (
    GOVERNED_IMPORT_PROFILE_SCHEMA_ID,
    AxisRole,
    GovernedChannelMapping,
    GovernedImportNotFound,
    GovernedImportProfileContent,
    QuantityKind,
    TabularDataSchema,
    TabularFileFormat,
)
from cmp.modules.datasets.domain.reference_shear_relaxation import ShearRelaxationMapping
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
from cmp.modules.jobs.adapters.persistence.artifact_events import SqlArtifactAvailableOutboxHook
from cmp.modules.modeling.adapters.persistence.linear_viscoelasticity_repository import (
    SqlAlchemyLinearViscoelasticRepository,
)
from cmp.modules.modeling.adapters.persistence.ogden_calibration_repository import (
    SqlAlchemyOgdenCalibrationRepository,
)
from cmp.modules.modeling.adapters.persistence.ogden_prony_repository import (
    SqlAlchemyOgdenPronyRepository,
)
from cmp.modules.modeling.adapters.persistence.repository import (
    SqlAlchemyModelingRepository,
    material_model_revision_table,
)
from cmp.modules.modeling.adapters.persistence.scientific_profile_repository import (
    SqlAlchemyScientificProfileRepository,
)
from cmp.modules.modeling.application.linear_viscoelasticity import (
    CreateReferenceLinearViscoelasticModel,
    LinearViscoelasticModelService,
)
from cmp.modules.modeling.application.ogden_calibration import (
    CreateReferenceOgdenCalibrationPlan,
    ExecuteReferenceOgdenCalibration,
    OgdenCalibrationNotFound,
    ReferenceOgdenCalibrationService,
)
from cmp.modules.modeling.application.ogden_prony import (
    CreateReferenceOgdenPronyModel,
    OgdenPronyModelService,
)
from cmp.modules.modeling.application.scientific_profile import (
    CreateScientificProfile,
    ReviseScientificProfile,
    ScientificProfileService,
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
from cmp.modules.modeling.domain.reference_ogden_calibration import (
    OgdenCalibrationMember,
    OgdenCalibrationRole,
    OgdenTestMode,
    ReferenceOgdenCalibrationPlanContent,
)
from cmp.modules.modeling.domain.reference_ogden_prony import ReferenceShearPronyTerm
from cmp.modules.modeling.domain.scientific_profile import (
    OgdenScientificParameters,
    ScientificApprovalStatus,
    ScientificProfileContent,
    ScientificProfileFamily,
    ScientificProfileNotFound,
)
from cmp.modules.processing.adapters.persistence.viscoelastic_master_curve_repository import (
    SqlAlchemyViscoelasticMasterRepository,
)
from cmp.modules.processing.application.viscoelastic_master_curve import (
    CreateViscoelasticMasterPlan,
    ExecuteViscoelasticMasterPlan,
    ViscoelasticMasterPreview,
    ViscoelasticMasterRun,
    ViscoelasticMasterService,
)
from cmp.modules.processing.domain.viscoelastic_master_curve import (
    ManualShiftFactor,
    ShiftMethod,
    ViscoelasticMasterPlanContent,
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
    CreateReferenceMultiaxialTensionMethod,
    CreateReferenceShearRelaxationMethod,
    CreateReferenceShearRelaxationRun,
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
from cmp.modules.testing.domain.reference_tensile import (
    ReferenceTensionMode,
)
from cmp.modules.testing.domain.reference_tensile import (
    TestingConflict as _TestingConflict,
)
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
from cmp.shared.application.revisions import CreateRevisionedAggregate, RevisionService
from cmp.shared.domain.revisions import RevisionConflict, TenantScope
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
    scientific_profiles: ScientificProfileService
    ogden_prony: OgdenPronyModelService
    ogden_calibration: ReferenceOgdenCalibrationService
    exporting: SolverCardService
    testing: _TestingApplicationService
    test_context: _TestContextApplicationService
    governed_import_repository: SqlAlchemyGovernedImportRepository
    governed_imports: GovernedImportService
    artifacts: ArtifactService
    uploads: UploadService
    shear_datasets: ShearRelaxationDatasetService
    viscoelastic_datasets: ViscoelasticDatasetService
    viscoelastic_processing: ViscoelasticMasterService


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
def postgres(tmp_path_factory: pytest.TempPathFactory) -> Iterator[PostgresHarness]:
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
                "provenance, audit, catalog, testing, datasets, modeling, exporting, artifact, "
                f'processing, events, plugin TO "{app_role}"'
            )
            for schema in (
                "identity",
                "governance",
                "provenance",
                "audit",
                "catalog",
                "testing",
                "datasets",
                "modeling",
                "exporting",
                "artifact",
                "processing",
                "events",
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
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA artifact "
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
        scientific_profiles = ScientificProfileService(
            repository=SqlAlchemyScientificProfileRepository(
                session_factory=sessions,
                rls_context=rls,
                revision_hooks=(
                    SqlInitialLifecycleHook(),
                    SqlAlchemyRevisionProvenanceHook(),
                    SqlAlchemyRevisionAuditHook(),
                ),
            )
        )
        ogden_prony = OgdenPronyModelService(
            repository=SqlAlchemyOgdenPronyRepository(
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
        governed_import_repository = SqlAlchemyGovernedImportRepository(
            session_factory=sessions,
            rls_context=rls,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
        object_store = FilesystemMultipartObjectStore(
            Path(tmp_path_factory.mktemp("t42-object-store"))
        )
        artifacts = ArtifactService(
            repository=SqlAlchemyArtifactRepository(
                session_factory=sessions,
                rls_context=rls,
                available_hooks=(SqlArtifactAvailableOutboxHook(),),
            ),
            object_store=object_store,
            transfers=ArtifactTransferCodec(b"t42-transfer-secret-32-bytes-minimum"),
            policy=ArtifactPolicy(transfer_ttl=timedelta(minutes=5)),
            clock=lambda: NOW,
        )
        uploads = UploadService(
            repository=SqlAlchemyUploadRepository(
                session_factory=sessions,
                rls_context=rls,
            ),
            object_store=object_store,
            capabilities=UploadCapabilityCodec(
                b"t42-upload-secret-32-bytes-minimum!", clock=lambda: NOW
            ),
            raw_asset_finalizer=artifacts,
            policy=UploadPolicy(
                max_object_bytes=2 * 1024 * 1024,
                default_part_bytes=64 * 1024,
                min_part_bytes=64 * 1024,
                max_part_bytes=512 * 1024,
                session_ttl=timedelta(hours=1),
            ),
            clock=lambda: NOW,
        )
        governed_imports = GovernedImportService(
            repository=governed_import_repository,
            testing=testing,
            artifacts=artifacts,
            clock=lambda: NOW,
        )
        ogden_calibration = ReferenceOgdenCalibrationService(
            repository=SqlAlchemyOgdenCalibrationRepository(
                session_factory=sessions,
                rls_context=rls,
                revision_hooks=(
                    SqlInitialLifecycleHook(),
                    SqlAlchemyRevisionProvenanceHook(),
                    SqlAlchemyRevisionAuditHook(),
                ),
            ),
            profiles=scientific_profiles,
            catalog=CatalogService(repository=repository),
            datasets=governed_imports,
            testing=testing,
            models=ogden_prony,
            artifacts=artifacts,
            clock=lambda: NOW,
        )
        shear_datasets = ShearRelaxationDatasetService(
            repository=SqlAlchemyDatasetRepository(
                session_factory=sessions,
                rls_context=rls,
                revision_hooks=(
                    SqlInitialLifecycleHook(),
                    SqlAlchemyRevisionProvenanceHook(),
                    SqlReferenceDatasetInputProvenanceHook(),
                    SqlShearRelaxationProcessedDatasetProvenanceHook(),
                    SqlAlchemyRevisionAuditHook(),
                ),
            ),
            artifacts=artifacts,
        )
        viscoelastic_repository = SqlAlchemyViscoelasticDatasetRepository(
            session_factory=sessions,
            rls_context=rls,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlViscoelasticSelectionProvenanceHook(),
                SqlViscoelasticDerivedDatasetProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
        viscoelastic_datasets = ViscoelasticDatasetService(
            repository=viscoelastic_repository,
            shear_datasets=shear_datasets,
            testing=testing,
        )
        viscoelastic_processing = ViscoelasticMasterService(
            repository=SqlAlchemyViscoelasticMasterRepository(
                session_factory=sessions,
                rls_context=rls,
                revision_hooks=(
                    SqlInitialLifecycleHook(),
                    SqlAlchemyRevisionProvenanceHook(),
                    SqlAlchemyRevisionAuditHook(),
                ),
            ),
            datasets=viscoelastic_datasets,
            shear_datasets=shear_datasets,
            artifacts=artifacts,
            clock=lambda: NOW,
        )
        yield PostgresHarness(
            admin_engine=admin_engine,
            sessions=sessions,
            rls=rls,
            service=CatalogService(repository=repository),
            modeling=modeling,
            linear_viscoelasticity=linear_viscoelasticity,
            scientific_profiles=scientific_profiles,
            ogden_prony=ogden_prony,
            ogden_calibration=ogden_calibration,
            exporting=exporting,
            testing=testing,
            test_context=test_context,
            governed_import_repository=governed_import_repository,
            governed_imports=governed_imports,
            artifacts=artifacts,
            uploads=uploads,
            shear_datasets=shear_datasets,
            viscoelastic_datasets=viscoelastic_datasets,
            viscoelastic_processing=viscoelastic_processing,
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


def test_governed_import_profile_is_typed_immutable_and_project_isolated(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    write = _decision(context, Permission.DATASET_WRITE)
    read = _decision(context, Permission.DATASET_READ)
    profile_id = uuid4()
    content = GovernedImportProfileContent(
        profile_label=f"T41 governed tension {profile_id}",
        data_schema=TabularDataSchema.MONOTONIC_TENSION,
        file_format=TabularFileFormat.CSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter=";",
        decimal_separator=",",
        channels=(
            GovernedChannelMapping(
                0,
                "engineering_strain_pct",
                QuantityKind.ENGINEERING_STRAIN,
                "%",
                AxisRole.INDEPENDENT,
            ),
            GovernedChannelMapping(
                1,
                "engineering_stress_mpa",
                QuantityKind.ENGINEERING_STRESS,
                "MPa",
                AxisRole.DEPENDENT,
            ),
        ),
    )
    record = RevisionService(
        aggregate_type=IMPORT_PROFILE_AGGREGATE_TYPE,
        store=postgres.governed_import_repository.profile_store(context, write),
    ).create(
        CreateRevisionedAggregate(
            aggregate_id=profile_id,
            scope=TenantScope(ORG, PROJECT_A, DataClassification.INTERNAL.value),
            schema_id=GOVERNED_IMPORT_PROFILE_SCHEMA_ID,
            schema_version="1.0.0",
            content=content,
            created_by=ACTOR,
            change_reason="approve reusable T41 profile",
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
    )
    loaded = postgres.governed_import_repository.get_profile(
        context=context,
        decision=read,
        profile_id=profile_id,
    )
    assert loaded.current.record.revision_id == record.revision_id
    assert tuple(item.source_quantity for item in loaded.current.content.channels) == (
        QuantityKind.ENGINEERING_STRAIN,
        QuantityKind.ENGINEERING_STRESS,
    )

    other_context = _context(PROJECT_B)
    other_read = _decision(other_context, Permission.DATASET_READ)
    with pytest.raises(GovernedImportNotFound, match="not visible"):
        postgres.governed_import_repository.get_profile(
            context=other_context,
            decision=other_read,
            profile_id=profile_id,
        )

    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE datasets.import_profile_revision SET header_row=2 "
                    "WHERE organization_id=:organization_id AND project_id=:project_id AND id=:id"
                ),
                {
                    "organization_id": ORG,
                    "project_id": PROJECT_A,
                    "id": record.revision_id,
                },
            )


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


async def _single_chunk(value: bytes) -> AsyncIterator[bytes]:
    yield value


def test_multi_test_ogden_calibration_persists_exact_evidence_in_postgresql(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    catalog_write = _decision(context, Permission.CATALOG_WRITE)
    modeling_write = _decision(context, Permission.MODELING_WRITE)
    testing_write = _decision(context, Permission.TESTING_WRITE)
    dataset_write = _decision(context, Permission.DATASET_WRITE)
    calibration_execute = _decision(context, Permission.CALIBRATION_EXECUTE)
    material = postgres.service.create_material(
        context,
        catalog_write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent(
                f"T43 Elastomer {uuid4().hex[:8]}",
                f"T43-OGDEN-{uuid4().hex[:8]}",
                "elastomer",
                material_class=MaterialClass.ELASTOMER,
            ),
            "create exact T43 elastomer",
        ),
    )
    state = postgres.service.create_material_state(
        context,
        catalog_write,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "Conditioned reference state",
            ),
            "create exact T43 State",
        ),
    )
    properties = postgres.service.create_property_set(
        context,
        catalog_write,
        CreatePropertySet(
            PropertySetContent(
                state.id,
                state.current.record.revision_id,
                density_kg_per_m3=1_100.0,
                density_source=_source(),
                youngs_modulus_pa=6_000_000.0,
                youngs_modulus_source=_source(),
                poisson_ratio=0.49,
                poisson_ratio_source=_source(),
            ),
            "record exact T43 source properties",
        ),
    )
    baseline = postgres.ogden_prony.create_model(
        context,
        modeling_write,
        CreateReferenceOgdenPronyModel(
            material_state_id=state.id,
            property_set_revision_id=properties.current.record.revision_id,
            ogden_mu_pa=2_000_000.0,
            ogden_alpha=2.0,
            prony_terms=(ReferenceShearPronyTerm(0.2, 1.0),),
            change_reason="create exact T43 baseline IR",
        ),
    )
    profile = postgres.scientific_profiles.create(
        context,
        modeling_write,
        CreateScientificProfile(
            "internal",
            ScientificProfileContent(
                profile_label=f"T43 multi-test {uuid4().hex[:8]}",
                family=ScientificProfileFamily.ELASTOMER_OGDEN_PRONY,
                approval_status=ScientificApprovalStatus.REFERENCE_UNAPPROVED,
                multistart_count=3,
                seed=43,
                ogden=OgdenScientificParameters(
                    1_500_000.0,
                    100_000.0,
                    10_000_000.0,
                    1_000_000.0,
                    1.5,
                    0.5,
                    8.0,
                    1.0,
                ),
            ),
            "create exact T43 scientific profile",
        ),
    )
    specimen = postgres.testing.create_specimen(
        context,
        testing_write,
        CreateSpecimen(
            state.id,
            state.current.record.revision_id,
            f"T43-{uuid4().hex[:8]}",
            None,
            "public synthetic calibration fixture",
            "create exact T43 specimen",
        ),
    )
    method = next(
        (
            item
            for item in postgres.testing.list_test_methods(
                context, _decision(context, Permission.TESTING_READ)
            )
            if item.current.content.method_code == "reference_uniaxial_tensile"
        ),
        None,
    )
    if method is None:
        method = postgres.testing.create_reference_tensile_method(
            context,
            testing_write,
            CreateReferenceTensileMethod(
                DataClassification.INTERNAL, "create exact T43 method"
            ),
        )
    planar_method = postgres.testing.create_reference_multiaxial_tension_method(
        context,
        testing_write,
        CreateReferenceMultiaxialTensionMethod(
            DataClassification.INTERNAL,
            ReferenceTensionMode.PLANAR_TENSION,
            "create exact T43 planar method",
        ),
    )
    biaxial_method = postgres.testing.create_reference_multiaxial_tension_method(
        context,
        testing_write,
        CreateReferenceMultiaxialTensionMethod(
            DataClassification.INTERNAL,
            ReferenceTensionMode.BIAXIAL_TENSION,
            "create exact T43 biaxial method",
        ),
    )
    assert planar_method.current.content.method_code == "reference_planar_tension"
    assert biaxial_method.current.content.method_code == "reference_biaxial_tension"
    test_run = postgres.testing.create_reference_tensile_run(
        context,
        testing_write,
        CreateReferenceTensileRun(
            specimen.id,
            specimen.current.record.revision_id,
            method.id,
            method.current.record.revision_id,
            f"T43-RUN-{uuid4().hex[:8]}",
            NOW,
            296.15,
            2.0,
            "create exact T43 run",
        ),
    )
    import_profile = postgres.governed_imports.create_profile(
        context,
        dataset_write,
        CreateImportProfile(
            DataClassification.INTERNAL,
            GovernedImportProfileContent(
                profile_label=f"T43 nominal curve {uuid4().hex[:8]}",
                data_schema=TabularDataSchema.MONOTONIC_TENSION,
                file_format=TabularFileFormat.CSV,
                sheet_name=None,
                header_row=1,
                encoding="utf-8",
                delimiter=",",
                decimal_separator=".",
                channels=(
                    GovernedChannelMapping(
                        0,
                        "engineering_strain",
                        QuantityKind.ENGINEERING_STRAIN,
                        "1",
                        AxisRole.INDEPENDENT,
                    ),
                    GovernedChannelMapping(
                        1,
                        "engineering_stress_pa",
                        QuantityKind.ENGINEERING_STRESS,
                        "Pa",
                        AxisRole.DEPENDENT,
                    ),
                ),
            ),
            "approve exact T43 mapping",
        ),
    )

    async def upload_import_and_fit() -> tuple[UUID, UUID, UUID]:
        strain = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
        rows = ["engineering_strain,engineering_stress_pa"]
        rows.extend(
            f"{item:.8g},{2_000_000.0 * ((1 + item) - (1 + item) ** -2):.12g}"
            for item in strain
        )
        payload = ("\n".join(rows) + "\n").encode()
        artifact_write = _decision(context, Permission.ARTIFACT_WRITE)
        upload = await postgres.uploads.create(
            context,
            artifact_write,
            CreateUpload(
                classification=DataClassification.INTERNAL,
                original_filename="t43-public-synthetic.csv",
                media_type="text/csv",
                expected_size_bytes=len(payload),
                expected_sha256=hashlib.sha256(payload).hexdigest(),
                idempotency_key=f"t43-ogden-{uuid4()}",
                part_size_bytes=64 * 1024,
                test_run_revision_id=test_run.current.record.revision_id,
            ),
        )
        await postgres.uploads.record_part(
            context,
            artifact_write,
            RecordUploadPart(upload.session.id, 1, upload.capability),
            _single_chunk(payload),
        )
        completed = await postgres.uploads.complete(
            context,
            artifact_write,
            CompleteUpload(upload.session.id, upload.capability),
        )
        assert completed.available_artifact_id is not None
        imported = await postgres.governed_imports.execute(
            context,
            dataset_write,
            ExecuteGovernedImport(
                test_run.id,
                test_run.current.record.revision_id,
                completed.raw_asset.id,
                completed.available_artifact_id,
                import_profile.id,
                import_profile.current.record.revision_id,
                "normalize exact T43 public synthetic curve",
            ),
        )
        assert imported.normalized_dataset_id is not None
        assert imported.normalized_dataset_revision_id is not None
        plan = postgres.ogden_calibration.create_plan(
            context,
            calibration_execute,
            CreateReferenceOgdenCalibrationPlan(
                DataClassification.INTERNAL,
                ReferenceOgdenCalibrationPlanContent(
                    plan_label=f"T43 fit {uuid4().hex[:8]}",
                    scientific_profile_id=profile.id,
                    scientific_profile_revision_id=profile.current.record.revision_id,
                    material_state_id=state.id,
                    material_state_revision_id=state.current.record.revision_id,
                    baseline_model_id=baseline.id,
                    baseline_model_revision_id=baseline.current.record.revision_id,
                    members=(
                        OgdenCalibrationMember(
                            0,
                            OgdenCalibrationRole.CALIBRATION,
                            OgdenTestMode.UNIAXIAL_TENSION,
                            imported.normalized_dataset_id,
                            imported.normalized_dataset_revision_id,
                        ),
                    ),
                ),
                "pin exact T43 evidence",
            ),
        )
        fitted = await postgres.ogden_calibration.execute(
            context,
            calibration_execute,
            ExecuteReferenceOgdenCalibration(
                plan.id,
                plan.current.record.revision_id,
                "execute deterministic T43 fit",
            ),
        )
        fitted_best = min(fitted.candidates, key=lambda item: item.value.objective_total)
        return fitted.id, plan.id, fitted_best.id

    run_id, plan_id, candidate_id = asyncio.run(upload_import_and_fit())
    restored = postgres.ogden_calibration.get_run(
        context,
        _decision(context, Permission.MODELING_READ),
        run_id,
    )
    best = min(restored.candidates, key=lambda item: item.value.objective_total)
    assert best.id == candidate_id
    assert best.value.mu_pa == pytest.approx(2_000_000.0, rel=1e-6)
    assert best.value.alpha == pytest.approx(2.0, rel=1e-6)
    assert best.value.uncertainty_status == "estimated_jacobian_covariance"
    assert "no_holdout_data" in best.value.warnings
    assert restored.plan_id == plan_id

    other = _context(PROJECT_B)
    with pytest.raises(OgdenCalibrationNotFound, match="not visible"):
        postgres.ogden_calibration.get_run(
            other,
            _decision(other, Permission.MODELING_READ),
            run_id,
        )
    with postgres.admin_engine.connect() as connection:
        candidate_row = connection.execute(
            sa.text(
                "SELECT mu_pa, alpha, uncertainty_status FROM "
                "modeling.ogden_calibration_candidate WHERE id=:id"
            ),
            {"id": candidate_id},
        ).one()
        rls = connection.scalar(
            sa.text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class t "
                "JOIN pg_namespace n ON n.oid=t.relnamespace "
                "WHERE n.nspname='modeling' AND t.relname='ogden_calibration_candidate'"
            )
        )
    assert candidate_row == (
        pytest.approx(2_000_000.0, rel=1e-6),
        pytest.approx(2.0, rel=1e-6),
        "estimated_jacobian_covariance",
    )
    assert rls is True
    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE modeling.ogden_calibration_candidate "
                    "SET mu_pa=mu_pa+1 WHERE id=:id"
                ),
                {"id": candidate_id},
            )


async def _import_shear_curve(
    postgres: PostgresHarness,
    context: SecurityContext,
    *,
    test_run_id: UUID,
    test_run_revision_id: UUID,
    label: str,
    scale: float,
) -> tuple[UUID, UUID]:
    rows = ["time_s,shear_modulus_mpa"]
    for index in range(9):
        time_s = 10.0 ** (-2.0 + index * 0.5)
        modulus_mpa = scale * (2.0 + 8.0 / (1.0 + time_s**0.6))
        rows.append(f"{time_s:.12g},{modulus_mpa:.12g}")
    payload = ("\n".join(rows) + "\n").encode()
    artifact_write = _decision(context, Permission.ARTIFACT_WRITE)
    created = await postgres.uploads.create(
        context,
        artifact_write,
        CreateUpload(
            classification=DataClassification.INTERNAL,
            original_filename=f"{label}.csv",
            media_type="text/csv",
            expected_size_bytes=len(payload),
            expected_sha256=hashlib.sha256(payload).hexdigest(),
            idempotency_key=f"t42-{label}",
            part_size_bytes=64 * 1024,
            test_run_revision_id=test_run_revision_id,
        ),
    )
    await postgres.uploads.record_part(
        context,
        artifact_write,
        RecordUploadPart(created.session.id, 1, created.capability),
        _single_chunk(payload),
    )
    completed = await postgres.uploads.complete(
        context,
        artifact_write,
        CompleteUpload(created.session.id, created.capability),
    )
    assert completed.available_artifact_id is not None
    dataset = await postgres.shear_datasets.import_csv(
        context,
        _decision(context, Permission.DATASET_WRITE),
        ImportReferenceShearRelaxationCsv(
            test_run_id=test_run_id,
            test_run_revision_id=test_run_revision_id,
            raw_asset_id=completed.raw_asset.id,
            raw_artifact_id=completed.available_artifact_id,
            mapping=ShearRelaxationMapping(
                "time_s", "shear_modulus_mpa", "s", "MPa"
            ),
            change_reason="normalize T42 PostgreSQL fixture",
        ),
    )
    return dataset.id, dataset.current.record.revision_id


def test_viscoelastic_master_curve_is_typed_provenanced_and_previewable_in_postgresql(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    catalog_write = _decision(context, Permission.CATALOG_WRITE)
    testing_write = _decision(context, Permission.TESTING_WRITE)
    material = postgres.service.create_material(
        context,
        catalog_write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent(
                f"T42 Polymer {uuid4()}",
                f"T42-{uuid4().hex[:10]}",
                "polymer",
                material_class=MaterialClass.POLYMER,
            ),
            "create T42 PostgreSQL material",
        ),
    )
    state = postgres.service.create_material_state(
        context,
        catalog_write,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "Conditioned reference state",
            ),
            "create exact T42 state",
        ),
    )
    method = postgres.testing.create_reference_shear_relaxation_method(
        context,
        testing_write,
        CreateReferenceShearRelaxationMethod(
            DataClassification.INTERNAL, "create T42 shear method"
        ),
    )

    async def arrange_and_execute() -> tuple[
        ViscoelasticSelectionSnapshot,
        ViscoelasticMasterRun,
        ViscoelasticMasterPreview,
    ]:
        member_refs: list[ViscoelasticSelectionMemberRef] = []
        for temperature_k, replicate, scale in (
            (293.15, 1, 1.00),
            (293.15, 2, 1.02),
            (313.15, 1, 0.99),
            (313.15, 2, 1.01),
        ):
            specimen = postgres.testing.create_specimen(
                context,
                testing_write,
                CreateSpecimen(
                    state.id,
                    state.current.record.revision_id,
                    f"T42-{temperature_k}-{replicate}-{uuid4().hex[:6]}",
                    None,
                    "public synthetic PostgreSQL fixture",
                    "create T42 specimen",
                ),
            )
            test_run = postgres.testing.create_reference_shear_relaxation_run(
                context,
                testing_write,
                CreateReferenceShearRelaxationRun(
                    specimen.id,
                    specimen.current.record.revision_id,
                    method.id,
                    method.current.record.revision_id,
                    f"T42 {temperature_k} K replicate {replicate} {uuid4().hex[:6]}",
                    NOW,
                    temperature_k,
                    "pin exact temperature evidence",
                ),
            )
            dataset_id, dataset_revision_id = await _import_shear_curve(
                postgres,
                context,
                test_run_id=test_run.id,
                test_run_revision_id=test_run.current.record.revision_id,
                label=f"{int(temperature_k)}-{replicate}-{uuid4().hex[:6]}",
                scale=scale,
            )
            member_refs.append(
                ViscoelasticSelectionMemberRef(dataset_id, dataset_revision_id)
            )
        selection = postgres.viscoelastic_datasets.create_selection(
            context,
            _decision(context, Permission.DATASET_WRITE),
            CreateViscoelasticSelection(
                classification=DataClassification.INTERNAL,
                selection_label=f"T42 exact replicates {uuid4().hex[:8]}",
                members=tuple(member_refs),
                change_reason="pin exact T42 source revisions",
            ),
        )
        plan = postgres.viscoelastic_processing.create_plan(
            context,
            _decision(context, Permission.PROCESSING_EXECUTE),
            CreateViscoelasticMasterPlan(
                classification=DataClassification.INTERNAL,
                content=ViscoelasticMasterPlanContent(
                    plan_label=f"T42 manual master {uuid4().hex[:8]}",
                    selection_id=selection.id,
                    selection_revision_id=selection.current.record.revision_id,
                    reference_temperature_k=293.15,
                    grid_point_count=31,
                    shift_method=ShiftMethod.MANUAL,
                    manual_shift_factors=(
                        ManualShiftFactor(293.15, 0.0),
                        ManualShiftFactor(313.15, -1.0),
                    ),
                ),
                change_reason="define explicit T42 shift evidence",
            ),
        )
        run = await postgres.viscoelastic_processing.execute(
            context,
            _decision(context, Permission.PROCESSING_EXECUTE),
            ExecuteViscoelasticMasterPlan(
                plan.id,
                plan.current.record.revision_id,
                "commit three T42 derived Dataset revisions",
            ),
        )
        preview = await postgres.viscoelastic_processing.preview(
            context,
            _decision(context, Permission.PROCESSING_READ),
            run.id,
        )
        return selection, run, preview

    selection_value, run_value, preview_value = asyncio.run(arrange_and_execute())
    selection = selection_value
    run = run_value
    preview = preview_value
    assert run.status.value == "succeeded"
    assert run.source_curve_count == 4
    assert run.temperature_count == 2
    assert run.aligned_dataset_revision_id is not None
    assert run.statistics_dataset_revision_id is not None
    assert run.master_dataset_revision_id is not None
    assert len(preview.aligned_curves) == 4
    assert len(preview.temperature_statistics) == 2
    assert len(preview.master_curve) == 31
    assert tuple(item.source for item in run.shift_factors) == ("reference", "manual")

    with postgres.admin_engine.connect() as connection:
        domain_activities = connection.execute(
            sa.text(
                "SELECT activity_type, domain_run_type FROM provenance.activity "
                "WHERE domain_run_id=:run_id ORDER BY domain_run_type"
            ),
            {"run_id": run.id},
        ).all()
        output_relations = connection.execute(
            sa.text(
                "SELECT d.representation, "
                "(SELECT count(*) FROM provenance.usage u WHERE u.activity_id=g.activity_id), "
                "(SELECT count(*) FROM provenance.derivation x "
                " WHERE x.generated_entity_id=e.id) "
                "FROM datasets.viscoelastic_derived_dataset_revision d "
                "JOIN provenance.entity e ON e.reference_id=d.id "
                " AND e.reference_type='datasets.viscoelastic_derived_dataset.revision' "
                "JOIN provenance.generation g ON g.entity_id=e.id "
                "WHERE d.processing_run_id=:run_id ORDER BY d.representation"
            ),
            {"run_id": run.id},
        ).all()
        selection_relations = connection.execute(
            sa.text(
                "SELECT (SELECT count(*) FROM provenance.usage u "
                "        WHERE u.activity_id=g.activity_id), "
                "       (SELECT count(*) FROM provenance.derivation x "
                "        WHERE x.generated_entity_id=e.id) "
                "FROM provenance.entity e JOIN provenance.generation g ON g.entity_id=e.id "
                "WHERE e.reference_type='datasets.viscoelastic_selection.revision' "
                "AND e.reference_id=:revision_id"
            ),
            {"revision_id": selection.current.record.revision_id},
        ).one()
    assert {str(row[1]) for row in domain_activities} == {
        "processing.viscoelastic_master_output.aligned",
        "processing.viscoelastic_master_output.statistics",
        "processing.viscoelastic_master_output.master_curve",
    }
    assert [
        (str(row[0]), int(row[1]), int(row[2])) for row in output_relations
    ] == [
        ("aligned", 6, 4),
        ("master_curve", 6, 4),
        ("statistics", 6, 4),
    ]
    assert (int(selection_relations[0]), int(selection_relations[1])) == (4, 4)

    other_context = _context(PROJECT_B)
    with pytest.raises(ViscoelasticDatasetNotFound, match="not visible"):
        postgres.viscoelastic_datasets.get_selection(
            other_context,
            _decision(other_context, Permission.DATASET_READ),
            selection.id,
        )
    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE datasets.viscoelastic_selection_member "
                    "SET temperature_k=temperature_k + 1 "
                    "WHERE selection_revision_id=:revision_id"
                ),
                {"revision_id": selection.current.record.revision_id},
            )


def test_scientific_profile_revisions_are_typed_historical_and_project_isolated(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    write = _decision(context, Permission.MODELING_WRITE)
    read = _decision(context, Permission.MODELING_READ)
    original_content = ScientificProfileContent(
        profile_label=f"T43 Ogden profile {uuid4().hex[:8]}",
        family=ScientificProfileFamily.ELASTOMER_OGDEN_PRONY,
        approval_status=ScientificApprovalStatus.REFERENCE_UNAPPROVED,
        multistart_count=4,
        seed=43,
        ogden=OgdenScientificParameters(
            1_200_000.0,
            1_000.0,
            100_000_000.0,
            1_000_000.0,
            2.4,
            0.1,
            20.0,
            2.0,
        ),
    )
    created = postgres.scientific_profiles.create(
        context,
        write,
        CreateScientificProfile(
            "internal", original_content, "create exact T43 reference profile"
        ),
    )
    revised_content = ScientificProfileContent(
        profile_label=original_content.profile_label,
        family=original_content.family,
        approval_status=original_content.approval_status,
        multistart_count=12,
        seed=43,
        ogden=original_content.ogden,
    )
    revised = postgres.scientific_profiles.revise(
        context,
        write,
        created.id,
        ReviseScientificProfile(
            created.current.record.revision_id,
            revised_content,
            "increase deterministic multistart coverage",
        ),
    )
    restored = postgres.scientific_profiles.get(context, read, created.id)
    historical = postgres.scientific_profiles.get_revision_for_calibration(
        context,
        _decision(context, Permission.CALIBRATION_EXECUTE),
        created.id,
        created.current.record.revision_id,
    )
    assert restored.current.record.revision_id == revised.current.record.revision_id
    assert restored.current.content.multistart_count == 12
    assert historical.content.multistart_count == 4
    assert historical.content.ogden is not None
    assert historical.content.ogden.alpha_upper == 20.0

    other = _context(PROJECT_B)
    with pytest.raises(ScientificProfileNotFound, match="not visible"):
        postgres.scientific_profiles.get(
            other,
            _decision(other, Permission.MODELING_READ),
            created.id,
        )

    with postgres.admin_engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT revision_no, multistart_count, ogden_alpha_upper, "
                "voce_sigma0_initial_pa, prony_term_count_min "
                "FROM modeling.scientific_profile_revision "
                "WHERE aggregate_id=:profile_id ORDER BY revision_no"
            ),
            {"profile_id": created.id},
        ).all()
        rls = connection.execute(
            sa.text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class t "
                "JOIN pg_namespace n ON n.oid=t.relnamespace "
                "WHERE n.nspname='modeling' AND t.relname='scientific_profile_revision'"
            )
        ).scalar_one()
    assert len(rows) == 2
    assert rows[0][0] == 1
    assert rows[0][1] == 4
    assert rows[0][2] == pytest.approx(20.0)
    assert rows[0][3] is None and rows[0][4] is None
    assert rows[1][0] == 2
    assert rows[1][1] == 12
    assert rows[1][2] == pytest.approx(20.0)
    assert rows[1][3] is None and rows[1][4] is None
    assert rls is True

    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE modeling.scientific_profile_revision "
                    "SET multistart_count=16 WHERE id=:revision_id"
                ),
                {"revision_id": created.current.record.revision_id},
            )
