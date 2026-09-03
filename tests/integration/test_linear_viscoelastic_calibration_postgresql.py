from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.catalog.adapters.persistence.repository import SqlAlchemyCatalogRepository
from cmp.modules.catalog.application.service import (
    CatalogService,
    CreateMaterial,
    CreateMaterialState,
    CreatePropertySet,
    MaterialSnapshot,
    MaterialStateSnapshot,
    PropertySetSnapshot,
    RevisePropertySet,
)
from cmp.modules.catalog.domain.model import (
    Applicability,
    MaterialClass,
    MaterialContent,
    MaterialStateContent,
    PropertySetContent,
    PropertySource,
    PropertySourceKind,
)
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.adapters.persistence.linear_viscoelastic_calibration_repository import (
    SqlAlchemyLinearViscoelasticCalibrationRepository,
)
from cmp.modules.modeling.adapters.persistence.linear_viscoelasticity_repository import (
    SqlAlchemyLinearViscoelasticRepository,
)
from cmp.modules.modeling.adapters.persistence.repository import SqlAlchemyModelingRepository
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    CreateLinearViscoelasticCalibrationPlan,
    CreateLinearViscoelasticCalibrationSelection,
    LinearViscoelasticCalibrationConflict,
    LinearViscoelasticCalibrationService,
    PromoteLinearViscoelasticCalibrationSelection,
    QueueLinearViscoelasticCalibrationRun,
)
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelService,
)
from cmp.modules.modeling.application.service import MaterialModelService
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
    ArtifactPin,
    CalibrationWeights,
    CanonicalViscoelasticInput,
    ExactRevisionPin,
    GovernedViscoelasticInputSemantics,
    InputChannelSemantics,
    LinearViscoelasticCalibrationPlan,
    ParameterBound,
    PointDisposition,
    PointPartition,
    RelaxationObservation,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")
NOW = datetime(2026, 8, 28, tzinfo=UTC)
ORG = UUID("8d000000-0000-4000-8000-000000000001")
PROJECT = UUID("8d000000-0000-4000-8000-000000000002")
OTHER_ORG = UUID("8d000000-0000-4000-8000-000000000003")
OTHER_PROJECT = UUID("8d000000-0000-4000-8000-000000000004")
ACTOR = UUID("8d000000-0000-4000-8000-000000000005")
SHA = "d" * 64


def _input_semantics() -> GovernedViscoelasticInputSemantics:
    return GovernedViscoelasticInputSemantics(
        mode="relaxation",
        deformation_mode="shear",
        channels=(
            InputChannelSemantics("time", "time.elapsed", "independent", "s", "s"),
            InputChannelSemantics(
                "shear_modulus",
                "mechanics.modulus.shear.relaxation",
                "dependent",
                "Pa",
                "Pa",
            ),
        ),
        point_dispositions=(
            PointDisposition(0, PointPartition.EXCLUDED, "INSTANTANEOUS_LIMIT"),
            PointDisposition(1, PointPartition.CALIBRATION),
            PointDisposition(2, PointPartition.CALIBRATION),
            PointDisposition(3, PointPartition.CALIBRATION),
        ),
        selected_temperature_k=298.15,
        temperature_source="condition",
    )


pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.container_service,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]


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


@pytest.fixture(scope="module")
def postgres() -> Iterator[tuple[sessionmaker[Session], SqlAlchemyRlsContext]]:
    assert POSTGRES_DSN is not None
    admin_url = _url(POSTGRES_DSN)
    database_name = f"cmp_lve_{uuid4().hex}"
    app_role = f"cmp_lve_app_{uuid4().hex}"
    app_password = f"cmp_lve_pw_{uuid4().hex}"
    cluster = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        connection.exec_driver_sql(
            f'CREATE ROLE "{app_role}" LOGIN NOSUPERUSER NOCREATEDB '
            f"NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD '{app_password}'"
        )
    database_url = admin_url.set(database=database_name)
    admin_engine = sa.create_engine(database_url, pool_pre_ping=True)
    app_engine: sa.Engine | None = None
    try:
        command.upgrade(_config(database_url), "head")
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(
                "GRANT USAGE ON SCHEMA catalog, modeling, access_control, revisioning "
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA catalog TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA modeling TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control, revisioning "
                f'TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=app_password), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        yield sessions, rls
    finally:
        if app_engine is not None:
            app_engine.dispose()
        try:
            command.downgrade(_config(database_url), "base")
        except RuntimeError as error:
            if str(error) != (
                "cannot downgrade linear-viscoelastic calibration while calibration rows exist"
            ):
                raise
        finally:
            admin_engine.dispose()
            with cluster.connect() as connection:
                connection.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                    ),
                    {"database_name": database_name},
                )
                connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            cluster.dispose()


def _context(organization_id: UUID, project_id: UUID) -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "LVE integration", True),
        organization_id=organization_id,
        project_id=project_id,
        issuer="https://integration.invalid",
        subject=str(ACTOR),
        token_id="lve-integration-token",
        groups=(),
        scopes=(),
        request_id=UUID("8d000000-0000-4000-8000-000000000006"),
        trace_id="00-0000000000000000000000000000008d-000000000000008d-01",
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext, permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=(
            "calibration.execute",
            "catalog.read",
            "catalog.write",
            "job.execute",
            "modeling.read",
            "modeling.write",
        ),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _plan() -> LinearViscoelasticCalibrationPlan:
    bounds = {
        1: (
            ParameterBound("G_inf_pa", 1, 4, 20, "Pa"),
            ParameterBound("G_1_pa", 1, 2, 10, "Pa"),
            ParameterBound("tau_1_s", 0.01, 0.1, 1, "s"),
        )
    }
    return LinearViscoelasticCalibrationPlan.for_terms(
        (1,),
        bounds=bounds,
        start_vectors={1: ((4.0, 2.0, 0.1),)},
        test_data=ExactRevisionPin(UUID(int=1), UUID(int=2), SHA),
        canonical_artifact=ArtifactPin(UUID(int=3), SHA, "application/vnd.cmp.test-data+json"),
        normalized_artifact=ArtifactPin(UUID(int=4), SHA, "application/vnd.apache.parquet"),
        raw_source_sha256=SHA,
        import_profile=ExactRevisionPin(UUID(int=5), UUID(int=6), SHA),
        profile_sha256=SHA,
        input_semantics=_input_semantics(),
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        weights=CalibrationWeights(relaxation_scale_pa=Decimal(1)),
    )


def _processed_plan() -> LinearViscoelasticCalibrationPlan:
    source = _plan()
    semantics = GovernedViscoelasticInputSemantics(
        mode="dma_frequency_master_curve",
        deformation_mode="shear",
        channels=(
            InputChannelSemantics(
                "reduced_angular_frequency_rad_per_s",
                "frequency.angular.reduced",
                "independent",
                "rad/s",
                "rad/s",
            ),
            InputChannelSemantics(
                "storage_modulus_pa",
                "mechanics.modulus.storage",
                "dependent",
                "Pa",
                "Pa",
            ),
            InputChannelSemantics(
                "loss_modulus_pa",
                "mechanics.modulus.loss",
                "dependent",
                "Pa",
                "Pa",
            ),
        ),
        point_dispositions=tuple(
            PointDisposition(index, PointPartition.CALIBRATION) for index in range(3)
        ),
        selected_temperature_k=313.15,
        temperature_source="processing_reference_temperature",
        frequency_kind="reduced_angular_rad_per_s",
        angular_frequency_conversion=(
            "omega_reduced_rad_per_s=omega_rad_per_s*shift_factor;"
            "frequency_reduced_hz=omega_reduced_rad_per_s/(2*pi)"
        ),
        source_kind="processing_output",
        processing_method="polymer.dma_frequency_master_curve@1.0.0",
        dma_domain_policy="nondecreasing_observations",
    )
    return replace(
        source,
        plan_id=UUID(int=101),
        plan_revision_id=UUID(int=102),
        input_semantics=semantics,
        processing_output=ExactRevisionPin(UUID(int=103), UUID(int=104), "e" * 64),
        processing_metadata_artifact=ArtifactPin(
            UUID(int=105),
            "f" * 64,
            "application/vnd.cmp.processing-output+json",
        ),
        processing_result_artifact=ArtifactPin(
            UUID(int=106), "1" * 64, "application/vnd.apache.parquet"
        ),
    )


def _input() -> CanonicalViscoelasticInput:
    return CanonicalViscoelasticInput.from_relaxation(
        (
            RelaxationObservation(0, 0.0, 6.0, PointPartition.EXCLUDED, "INSTANTANEOUS_LIMIT"),
            RelaxationObservation(1, 0.01, 5.809674836071919),
            RelaxationObservation(2, 0.1, 4.735758882342885),
            RelaxationObservation(3, 1.0, 4.000090799859524),
        ),
        profile_deformation_mode="not-characterized",
        canonical_test_data=ExactRevisionPin(UUID(int=1), UUID(int=2), SHA),
        canonical_artifact=ArtifactPin(UUID(int=3), SHA, "application/json"),
        normalized_artifact=ArtifactPin(UUID(int=4), SHA, "application/vnd.apache.parquet"),
        raw_source_sha256=SHA,
        import_profile=ExactRevisionPin(UUID(int=5), UUID(int=6), SHA),
        profile_sha256=SHA,
    )


class _Authorization:
    def authorize(self, context: SecurityContext, permission: Permission) -> AuthorizationDecision:
        return _decision(context, permission)


def _catalog_source(
    sessions: sessionmaker[Session],
    rls: SqlAlchemyRlsContext,
    context: SecurityContext,
) -> tuple[MaterialSnapshot, MaterialStateSnapshot, PropertySetSnapshot]:
    service = CatalogService(
        repository=SqlAlchemyCatalogRepository(session_factory=sessions, rls_context=rls)
    )
    write = _decision(context, Permission.CATALOG_WRITE)
    material = service.create_material(
        context,
        write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent("LVE acceptance polymer", material_class=MaterialClass.POLYMER),
            "create exact promotion source Material",
        ),
    )
    state = service.create_material_state(
        context,
        write,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "isothermal acceptance state",
            ),
            "create exact promotion source State",
        ),
    )
    manual = PropertySource(PropertySourceKind.MANUAL)
    properties = service.create_property_set(
        context,
        write,
        CreatePropertySet(
            PropertySetContent(
                state.id,
                state.current.record.revision_id,
                1050.0,
                manual,
                12.0,
                manual,
                0.49,
                manual,
                applicability=Applicability(298.15, 298.15, note="single isothermal domain"),
            ),
            "create exact promotion source Property Set",
        ),
    )
    return material, state, properties


def test_plan_run_result_selection_survive_reconstruction_and_tenant_scope(
    postgres: tuple[sessionmaker[Session], SqlAlchemyRlsContext],
) -> None:
    sessions, rls = postgres
    context = _context(ORG, PROJECT)
    execute = _decision(context, Permission.CALIBRATION_EXECUTE)
    modeling_write = _decision(context, Permission.MODELING_WRITE)
    job_execute = _decision(context, Permission.JOB_EXECUTE)
    read = _decision(context, Permission.MODELING_READ)
    repository = SqlAlchemyLinearViscoelasticCalibrationRepository(
        session_factory=sessions, rls_context=rls
    )
    service = LinearViscoelasticCalibrationService(
        repository=repository,
        clock=lambda: NOW,
        allow_reference_execution=True,
    )
    plan = _plan()
    test_data = plan.test_data
    import_profile = plan.import_profile
    assert test_data is not None
    assert import_profile is not None
    snapshot = service.create_plan(
        context,
        execute,
        CreateLinearViscoelasticCalibrationPlan(
            plan, DataClassification.INTERNAL, "persist integration plan", "plan-key"
        ),
    )
    service.bind_input(snapshot.id, _input())
    queued = service.queue_run(
        context,
        execute,
        QueueLinearViscoelasticCalibrationRun(
            snapshot.id, plan.plan_revision_id, "persist integration run", "run-key"
        ),
    )
    finished = service.execute_reference_run(
        context, job_execute, run_id=queued.run_id, package_sha256=SHA
    )
    assert finished.result is not None
    first_candidate = finished.result.candidates[0]

    reconstructed = LinearViscoelasticCalibrationService(
        repository=SqlAlchemyLinearViscoelasticCalibrationRepository(
            session_factory=sessions, rls_context=rls
        ),
        clock=lambda: NOW,
    )
    reloaded_plan = reconstructed.get_plan(context, read, snapshot.id)
    assert reloaded_plan.current.digest == plan.digest
    assert reloaded_plan.current.recommendation_policy == LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY
    processed_plan = _processed_plan()
    processed_snapshot = reconstructed.create_plan(
        context,
        execute,
        CreateLinearViscoelasticCalibrationPlan(
            processed_plan,
            DataClassification.INTERNAL,
            "persist exact DMA TTS input evidence",
            "processed-plan-key",
        ),
    )
    processed_reloaded = LinearViscoelasticCalibrationService(
        repository=SqlAlchemyLinearViscoelasticCalibrationRepository(
            session_factory=sessions, rls_context=rls
        ),
        clock=lambda: NOW,
    ).get_plan(context, read, processed_snapshot.id)
    assert processed_reloaded.current.digest == processed_plan.digest
    assert processed_reloaded.current.processing_output == processed_plan.processing_output
    assert (
        processed_reloaded.current.processing_metadata_artifact
        == processed_plan.processing_metadata_artifact
    )
    assert (
        processed_reloaded.current.processing_result_artifact
        == processed_plan.processing_result_artifact
    )
    reloaded = reconstructed.get_run(context, read, queued.run_id)
    assert reloaded.result is not None
    assert reloaded.result.digest == finished.result.digest
    selection = reconstructed.create_selection(
        context,
        modeling_write,
        CreateLinearViscoelasticCalibrationSelection(
            plan.plan_revision_id,
            queued.run_id,
            first_candidate.candidate_id,
            first_candidate.digest,
            "persist integration selection",
            (),
            "persist integration selection",
            "selection-key",
        ),
    )
    reloaded_selection = LinearViscoelasticCalibrationService(
        repository=SqlAlchemyLinearViscoelasticCalibrationRepository(
            session_factory=sessions, rls_context=rls
        ),
        clock=lambda: NOW,
    ).get_selection(context, read, selection.value.selection_id)
    assert reloaded_selection.value.candidate_digest == first_candidate.digest
    replayed_selection = reconstructed.create_selection(
        context,
        modeling_write,
        CreateLinearViscoelasticCalibrationSelection(
            plan.plan_revision_id,
            queued.run_id,
            first_candidate.candidate_id,
            first_candidate.digest,
            "persist integration selection",
            (),
            "persist integration selection",
            "selection-key",
        ),
    )
    assert replayed_selection.value.selection_id == selection.value.selection_id

    replay = reconstructed.queue_run(
        context,
        execute,
        QueueLinearViscoelasticCalibrationRun(
            snapshot.id, plan.plan_revision_id, "persist integration run", "run-key"
        ),
    )
    assert replay.run_id == queued.run_id
    with pytest.raises(LinearViscoelasticCalibrationConflict, match="idempotency"):
        reconstructed.queue_run(
            context,
            execute,
            QueueLinearViscoelasticCalibrationRun(
                snapshot.id, plan.plan_revision_id, "different request", "run-key"
            ),
        )

    other_context = _context(OTHER_ORG, OTHER_PROJECT)
    other_read = _decision(other_context, Permission.MODELING_READ)
    with pytest.raises(Exception, match="not visible"):
        reconstructed.get_plan(other_context, other_read, snapshot.id)

    material, state, properties = _catalog_source(sessions, rls, context)
    material_models = MaterialModelService(
        repository=SqlAlchemyModelingRepository(session_factory=sessions, rls_context=rls)
    )
    linear_models = LinearViscoelasticModelService(
        repository=SqlAlchemyLinearViscoelasticRepository(
            session_factory=sessions, rls_context=rls
        ),
        material_models=material_models,
    )
    promotion_service = LinearViscoelasticCalibrationService(
        repository=SqlAlchemyLinearViscoelasticCalibrationRepository(
            session_factory=sessions, rls_context=rls
        ),
        clock=lambda: NOW,
        authorization=_Authorization(),  # type: ignore[arg-type]
        linear_viscoelastic_models=linear_models,
    )
    promote = PromoteLinearViscoelasticCalibrationSelection(
        selection_id=selection.value.selection_id,
        material_id=material.id,
        material_revision_id=material.current.record.revision_id,
        material_state_id=state.id,
        material_state_revision_id=state.current.record.revision_id,
        property_set_id=properties.id,
        property_set_revision_id=properties.current.record.revision_id,
        change_reason="promote exact engineer selection",
    )
    promoted = promotion_service.promote_selection(context, execute, promote)
    reloaded_model = linear_models.get_model(context, read, promoted.id)
    evidence = reloaded_model.current.content.calibration_evidence
    assert reloaded_model.current.record.schema_version == "1.4.0"
    assert reloaded_model.current.content.non_production is True
    assert evidence is not None
    assert evidence.plan_revision_id == plan.plan_revision_id
    assert evidence.run_id == queued.run_id
    assert evidence.candidate_id == selection.value.candidate_id
    assert evidence.selection_revision_id == selection.value.selection_revision_id
    assert evidence.canonical_test_data_revision_id == test_data.revision_id
    assert evidence.canonical_test_data_sha256 == test_data.sha256
    assert evidence.import_profile_revision_id == import_profile.revision_id
    assert evidence.import_profile_sha256 == import_profile.sha256

    replayed_model = promotion_service.promote_selection(context, execute, promote)
    assert replayed_model.id == promoted.id
    assert replayed_model.current.record.revision_id == promoted.current.record.revision_id

    original_model_hash = reloaded_model.current.record.content_hash
    revised_properties = CatalogService(
        repository=SqlAlchemyCatalogRepository(session_factory=sessions, rls_context=rls)
    ).revise_property_set(
        context,
        _decision(context, Permission.CATALOG_WRITE),
        properties.id,
        RevisePropertySet(
            expected_current_revision_id=properties.current.record.revision_id,
            content=replace(properties.current.content, density_kg_per_m3=1060.0),
            change_reason="create a new exact upstream Property Set revision",
        ),
    )
    assert revised_properties.current.record.revision_id != properties.current.record.revision_id
    with pytest.raises(LinearViscoelasticCalibrationConflict, match="stale or mismatched"):
        promotion_service.promote_selection(context, execute, promote)
    historical_model = linear_models.get_model(context, read, promoted.id)
    assert historical_model.current.record.content_hash == original_model_hash
    assert historical_model.current.content == reloaded_model.current.content

    with pytest.raises(LinearViscoelasticCalibrationConflict, match="not visible"):
        promotion_service.promote_selection(
            context,
            execute,
            PromoteLinearViscoelasticCalibrationSelection(
                selection_id=selection.value.selection_id,
                material_id=material.id,
                material_revision_id=material.current.record.revision_id,
                material_state_id=state.id,
                material_state_revision_id=state.current.record.revision_id,
                property_set_id=properties.id,
                property_set_revision_id=uuid4(),
                change_reason="reject stale exact Property Set revision",
            ),
        )
