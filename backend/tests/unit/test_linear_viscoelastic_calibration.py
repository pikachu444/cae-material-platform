from __future__ import annotations

import base64
import importlib.util
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import numpy as np
import pytest
from cmp.modules.artifacts.domain.content import IntegrityStatus
from cmp.modules.datasets.domain.governed_tabular import (
    AxisRole,
    GovernedChannelMapping,
    GovernedImportProfileContent,
    QuantityKind,
    TabularDataSchema,
    TabularFileFormat,
    import_profile_canonical,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.jobs.application.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_MAX_TOTAL_OUTPUT_BYTES,
    build_linear_viscoelastic_job_spec,
    linear_viscoelastic_deadline,
)
from cmp.modules.modeling.adapters.persistence.linear_viscoelastic_calibration_repository import (
    plan_from_payload,
)
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    CalibrationJobReference,
    CreateGovernedLinearViscoelasticCalibrationPlan,
    CreateLinearViscoelasticCalibrationPlan,
    CreateLinearViscoelasticCalibrationSelection,
    CreateProcessedLinearViscoelasticCalibrationPlan,
    InMemoryLinearViscoelasticCalibrationRepository,
    LinearViscoelasticCalibrationService,
    QueueLinearViscoelasticCalibrationRun,
)
from cmp.modules.modeling.application.linear_viscoelastic_input_resolution import (
    ResolvedGovernedViscoelasticInput,
)
from cmp.modules.modeling.application.linear_viscoelastic_result_import import (
    parse_calibration_run_result,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
    ArtifactPin,
    CalibrationWeights,
    CanonicalViscoelasticInput,
    ChannelAvailability,
    DataAvailability,
    DmaObservation,
    ExactRevisionPin,
    GovernedViscoelasticInputSemantics,
    InputChannelSemantics,
    LinearViscoelasticCalibrationPlan,
    LinearViscoelasticInputError,
    ParameterBound,
    PointDisposition,
    PointPartition,
    RelaxationObservation,
    calibrate_linear_viscoelastic,
    promote_selected_linear_viscoelastic_candidate,
    rank_diagnostic,
    selected_arrays_digest,
    selection_acknowledgement,
)
from cmp.modules.plugins.domain.execution import InvalidResultManifest
from cmp.modules.plugins.domain.registry import ArtifactReference, PackageState
from cmp.modules.provenance.application.build_provenance import (
    cmp_python_package_tree_sha256,
)
from cmp.tools.linear_viscoelastic_calibration_acceptance import (
    artifact_idempotency_keys,
    detached_signature_document,
    prepare_acceptance_setup,
    register_activate_and_read_back,
)

ROOT = Path(__file__).parents[3]
_builder_spec = importlib.util.spec_from_file_location(
    "test_lve_package_builder", ROOT / "scripts/build_linear_viscoelastic_calibrator.py"
)
assert _builder_spec is not None and _builder_spec.loader is not None
_builder_module = importlib.util.module_from_spec(_builder_spec)
_builder_spec.loader.exec_module(_builder_module)
build_package = _builder_module.build_package
SHA = "a" * 64
TEST_DATA = ExactRevisionPin(UUID(int=1), UUID(int=2), SHA)
CANONICAL = ArtifactPin(UUID(int=3), SHA, "application/vnd.cmp.test-data+json")
NORMALIZED = ArtifactPin(UUID(int=4), SHA, "application/vnd.apache.parquet")
PROFILE = ExactRevisionPin(UUID(int=5), UUID(int=6), SHA)
PROCESSING_OUTPUT = ExactRevisionPin(UUID(int=7), UUID(int=8), SHA)
PROCESSING_METADATA = ArtifactPin(UUID(int=9), SHA, "application/vnd.cmp.processing-output+json")
PROCESSING_RESULT = ArtifactPin(UUID(int=10), SHA, "application/vnd.apache.parquet")
NOW = datetime(2026, 8, 28, tzinfo=UTC)
ORG = UUID(int=10)
PROJECT = UUID(int=11)
ACTOR = UUID(int=12)
INPUT_SEMANTICS = GovernedViscoelasticInputSemantics(
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
        PointDisposition(4, PointPartition.HOLDOUT),
    ),
    selected_temperature_k=298.15,
    temperature_source="condition",
)


def _plan(*, term_counts: tuple[int, ...] = (1,)) -> LinearViscoelasticCalibrationPlan:
    bounds = {
        1: (
            ParameterBound("G_inf_pa", 1, 4, 20, "Pa"),
            ParameterBound("G_1_pa", 1, 2, 10, "Pa"),
            ParameterBound("tau_1_s", 0.01, 0.1, 1, "s"),
        )
    }
    return LinearViscoelasticCalibrationPlan.for_terms(
        term_counts,
        bounds=bounds,
        start_vectors={1: ((4.0, 2.0, 0.1),)},
        test_data=TEST_DATA,
        canonical_artifact=CANONICAL,
        normalized_artifact=NORMALIZED,
        raw_source_sha256=SHA,
        import_profile=PROFILE,
        profile_sha256=SHA,
        input_semantics=INPUT_SEMANTICS,
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        weights=CalibrationWeights(relaxation_scale_pa=Decimal(1)),
    )


def test_candidate_scope_mode_preserves_legacy_bytes_and_persists_automatic_scope() -> None:
    legacy = _plan()
    explicit_manual = replace(legacy, candidate_scope_mode="manual")
    automatic = replace(legacy, candidate_scope_mode="automatic")

    assert explicit_manual.canonical() == legacy.canonical()
    assert explicit_manual.digest == legacy.digest
    assert "candidate_scope_mode" not in explicit_manual.canonical()
    assert automatic.canonical()["candidate_scope_mode"] == "automatic"
    assert plan_from_payload(automatic.canonical()).canonical() == automatic.canonical()


def test_automatic_scope_rejects_a_silent_term_subset() -> None:
    dense_semantics = replace(
        INPUT_SEMANTICS,
        point_dispositions=tuple(
            PointDisposition(index, PointPartition.CALIBRATION) for index in range(5)
        ),
    )

    with pytest.raises(ValueError, match="every feasible term count"):
        replace(_plan(), input_semantics=dense_semantics, candidate_scope_mode="automatic")


def _relaxation_input(*, holdout_modulus: float = 4.1) -> CanonicalViscoelasticInput:
    points = (
        RelaxationObservation(0, 0.0, 6.0, PointPartition.EXCLUDED, "INSTANTANEOUS_LIMIT"),
        RelaxationObservation(1, 0.01, 5.809674836071919),
        RelaxationObservation(2, 0.1, 4.735758882342885),
        RelaxationObservation(3, 1.0, 4.000090799859524),
        RelaxationObservation(4, 2.0, holdout_modulus, PointPartition.HOLDOUT),
    )
    return CanonicalViscoelasticInput.from_relaxation(
        points,
        profile_deformation_mode="not-characterized",
        canonical_test_data=TEST_DATA,
        canonical_artifact=CANONICAL,
        normalized_artifact=NORMALIZED,
        raw_source_sha256=SHA,
        import_profile=PROFILE,
        profile_sha256=SHA,
    )


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Calibration engineer", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test.invalid",
        subject=str(ACTOR),
        token_id="calibration-test-token",
        groups=(),
        scopes=(),
        request_id=UUID(int=13),
        trace_id="00-0000000000000000000000000000000a-000000000000000a-01",
        authenticated_at=NOW,
    )


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=(permission.value,),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=UUID(int=13),
        trace_id="00-0000000000000000000000000000000a-000000000000000a-01",
        decided_at=NOW,
    )


def test_governed_plan_resolves_server_pins_and_replays_idempotently() -> None:
    class _Resolver:
        async def resolve(self, *args: object) -> ResolvedGovernedViscoelasticInput:
            del args
            return ResolvedGovernedViscoelasticInput(
                classification=DataClassification.CONFIDENTIAL,
                test_data=TEST_DATA,
                canonical_artifact=CANONICAL,
                normalized_artifact=NORMALIZED,
                raw_source_sha256=SHA,
                import_profile=PROFILE,
                profile_sha256=SHA,
                semantics=INPUT_SEMANTICS,
            )

    repository = InMemoryLinearViscoelasticCalibrationRepository()
    service = LinearViscoelasticCalibrationService(
        repository=repository,
        input_resolver=_Resolver(),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    source = _plan()
    command = CreateGovernedLinearViscoelasticCalibrationPlan(
        test_data_id=TEST_DATA.aggregate_id,
        test_data_revision_id=TEST_DATA.revision_id,
        selected_temperature_k=298.15,
        point_dispositions=INPUT_SEMANTICS.point_dispositions,
        availability=ChannelAvailability(),
        term_counts=source.term_counts,
        parameter_bounds=source.parameter_bounds,
        start_vectors={
            term: tuple(tuple(float(item) for item in vector) for vector in vectors)
            for term, vectors in source.start_vectors.items()
        },
        weights=source.weights,
        recommendation_policy=source.recommendation_policy,
        ftol=source.ftol,
        xtol=source.xtol,
        gtol=source.gtol,
        max_nfev=source.max_nfev,
        change_reason="Create governed plan",
        idempotency_key="governed-plan-replay",
        candidate_scope_mode="automatic",
    )

    first = service.create_governed_plan(
        _context(), _decision(Permission.CALIBRATION_EXECUTE), command
    )
    second = service.create_governed_plan(
        _context(), _decision(Permission.CALIBRATION_EXECUTE), command
    )
    reloaded = service.get_plan(_context(), _decision(Permission.MODELING_READ), first.id)

    assert second == first == reloaded
    assert first.classification is DataClassification.CONFIDENTIAL
    assert first.current.test_data == TEST_DATA
    assert first.current.canonical_artifact == CANONICAL
    assert first.current.normalized_artifact == NORMALIZED
    assert first.current.import_profile == PROFILE
    assert first.current.input_semantics == INPUT_SEMANTICS
    assert first.current.recommendation_policy == LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY
    assert first.current.term_counts == (1,)
    assert first.current.canonical()["candidate_scope_mode"] == "automatic"
    assert (
        first.current.canonical()["recommendation_policy"]
        == LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY
    )


def test_processed_plan_persists_exact_tts_output_pins() -> None:
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

    class _Resolver:
        async def resolve_processing_output(
            self, *args: object
        ) -> ResolvedGovernedViscoelasticInput:
            del args
            return ResolvedGovernedViscoelasticInput(
                classification=DataClassification.INTERNAL,
                test_data=TEST_DATA,
                canonical_artifact=CANONICAL,
                normalized_artifact=NORMALIZED,
                raw_source_sha256=SHA,
                import_profile=PROFILE,
                profile_sha256=SHA,
                semantics=semantics,
                processing_output=PROCESSING_OUTPUT,
                processing_metadata_artifact=PROCESSING_METADATA,
                processing_result_artifact=PROCESSING_RESULT,
            )

    source = _plan()
    automatic_bounds = {
        **source.parameter_bounds,
        2: (
            ParameterBound("G_inf_pa", 1, 4, 20, "Pa"),
            ParameterBound("G_1_pa", 1, 2, 10, "Pa"),
            ParameterBound("G_2_pa", 1, 2, 10, "Pa"),
            ParameterBound("tau_1_s", 0.001, 0.01, 0.1, "s"),
            ParameterBound("tau_2_s", 1, 10, 100, "s"),
        ),
    }
    automatic_starts = {
        1: ((4.0, 2.0, 0.1),),
        2: ((4.0, 2.0, 2.0, 0.01, 10.0),),
    }
    repository = InMemoryLinearViscoelasticCalibrationRepository()
    service = LinearViscoelasticCalibrationService(
        repository=repository,
        input_resolver=_Resolver(),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    created = service.create_processed_plan(
        _context(),
        _decision(Permission.CALIBRATION_EXECUTE),
        CreateProcessedLinearViscoelasticCalibrationPlan(
            processing_output_id=PROCESSING_OUTPUT.aggregate_id,
            processing_output_revision_id=PROCESSING_OUTPUT.revision_id,
            availability=ChannelAvailability(sweep=DataAvailability.PROVIDED),
            term_counts=(1, 2),
            parameter_bounds=automatic_bounds,
            start_vectors=automatic_starts,
            weights=source.weights,
            recommendation_policy=source.recommendation_policy,
            ftol=source.ftol,
            xtol=source.xtol,
            gtol=source.gtol,
            max_nfev=source.max_nfev,
            change_reason="Create Plan from confirmed DMA TTS output",
            idempotency_key="processed-plan",
            candidate_scope_mode="automatic",
        ),
    )
    reloaded = service.get_plan(_context(), _decision(Permission.MODELING_READ), created.id)

    assert reloaded.current.processing_output == PROCESSING_OUTPUT
    assert reloaded.current.processing_metadata_artifact == PROCESSING_METADATA
    assert reloaded.current.processing_result_artifact == PROCESSING_RESULT
    assert reloaded.current.input_semantics == semantics
    assert reloaded.current.term_counts == (1, 2)
    assert reloaded.current.canonical()["candidate_scope_mode"] == "automatic"
    assert reloaded.current.canonical()["processing_output"] == {
        "id": str(PROCESSING_OUTPUT.aggregate_id),
        "revision_id": str(PROCESSING_OUTPUT.revision_id),
        "sha256": SHA,
    }
    assert plan_from_payload(reloaded.current.canonical()).canonical() == (
        reloaded.current.canonical()
    )


def test_relaxation_fit_is_bounded_and_holdout_does_not_change_fit_or_recommendation() -> None:
    plan = _plan()
    first = calibrate_linear_viscoelastic(
        plan, _relaxation_input(holdout_modulus=4.1), run_id=UUID(int=20)
    )
    second = calibrate_linear_viscoelastic(
        plan, _relaxation_input(holdout_modulus=400.0), run_id=UUID(int=21)
    )

    assert first.status.value == "succeeded"
    assert first.candidates and second.candidates
    assert first.candidates[0].physical_parameters == pytest.approx(
        second.candidates[0].physical_parameters, rel=1e-12
    )
    assert first.recommendation is not None and second.recommendation is not None
    assert first.recommendation.rule_version == second.recommendation.rule_version
    assert first.candidates[0].term_count == second.candidates[0].term_count
    assert first.recommendation.candidate_id == first.candidates[0].candidate_id
    assert second.recommendation.candidate_id == second.candidates[0].candidate_id
    assert first.attempts[0].objective_history
    assert "INPUT_PROCESS_METADATA_NOT_PROVIDED" in first.attempts[0].warnings


def test_input_requires_exact_evidence_and_dma_requires_new_profile_mode() -> None:
    with pytest.raises(LinearViscoelasticInputError) as missing:
        CanonicalViscoelasticInput.from_relaxation(
            (
                RelaxationObservation(1, 0.1, 1),
                RelaxationObservation(2, 0.2, 1),
                RelaxationObservation(3, 0.3, 1),
            )
        )
    assert missing.value.code == "INPUT_CANONICAL_TEST_DATA_REQUIRED"
    dma_points = tuple(
        DmaObservation(index, frequency, 293.15, 4.0, 0.2)
        for index, frequency in enumerate((1.0, 2.0, 3.0))
    )
    with pytest.raises(LinearViscoelasticInputError) as mode_error:
        CanonicalViscoelasticInput.from_dma(
            dma_points,
            canonical_test_data=TEST_DATA,
            canonical_artifact=CANONICAL,
            normalized_artifact=NORMALIZED,
            raw_source_sha256=SHA,
            import_profile=PROFILE,
            profile_sha256=SHA,
        )
    assert mode_error.value.code == "INPUT_DMA_DEFORMATION_MODE_REQUIRED"


def test_application_journey_persists_run_ledger_selection_and_rejects_terminal_retry() -> None:
    context = _context()
    execute = _decision(Permission.CALIBRATION_EXECUTE)
    modeling_write = _decision(Permission.MODELING_WRITE)
    job_execute = _decision(Permission.JOB_EXECUTE)
    repository = InMemoryLinearViscoelasticCalibrationRepository()
    service = LinearViscoelasticCalibrationService(
        repository=repository,
        id_factory=iter(UUID(int=value) for value in range(30, 50)).__next__,
        clock=lambda: NOW,
        allow_reference_execution=True,
    )
    plan = _plan()
    snapshot = service.create_plan(
        context,
        execute,
        CreateLinearViscoelasticCalibrationPlan(
            plan, DataClassification.INTERNAL, "create plan", "plan-key"
        ),
    )
    service.bind_input(snapshot.id, _relaxation_input())
    queued = service.queue_run(
        context,
        execute,
        QueueLinearViscoelasticCalibrationRun(
            snapshot.id, plan.plan_revision_id, "queue run", "run-key"
        ),
    )
    finished = service.execute_reference_run(
        context, job_execute, run_id=queued.run_id, package_sha256=SHA
    )
    assert finished.status == "succeeded"
    assert len(finished.execution_ledger) == 2
    candidate = finished.result.candidates[0]  # type: ignore[union-attr]
    acknowledgement = selection_acknowledgement(
        code="RANK_DEFICIENT",
        rule_version="linear_viscoelastic_calibration:1.0.0",
        plan_revision_id=plan.plan_revision_id,
        run_id=queued.run_id,
        candidate_id=candidate.candidate_id,
        model_revision_id=None,
        actor=ACTOR,
        reason="reviewed warning",
        acknowledged_at=NOW,
    )
    with pytest.raises(Exception, match="authorization decision does not match request"):
        service.create_selection(
            context,
            execute,
            CreateLinearViscoelasticCalibrationSelection(
                plan.plan_revision_id,
                queued.run_id,
                candidate.candidate_id,
                candidate.digest,
                "select candidate",
                (acknowledgement,),
                "persist selection",
                "selection-key",
            ),
        )
    selection = service.create_selection(
        context,
        modeling_write,
        CreateLinearViscoelasticCalibrationSelection(
            plan.plan_revision_id,
            queued.run_id,
            candidate.candidate_id,
            candidate.digest,
            "select candidate",
            (acknowledgement,),
            "persist selection",
            "selection-key",
        ),
    )
    assert selection.value.candidate_digest == candidate.digest
    replayed_selection = service.create_selection(
        context,
        modeling_write,
        CreateLinearViscoelasticCalibrationSelection(
            plan.plan_revision_id,
            queued.run_id,
            candidate.candidate_id,
            candidate.digest,
            "select candidate",
            (acknowledgement,),
            "persist selection",
            "selection-key",
        ),
    )
    assert replayed_selection.value.selection_id == selection.value.selection_id
    with pytest.raises(Exception, match="idempotency"):
        service.create_selection(
            context,
            modeling_write,
            CreateLinearViscoelasticCalibrationSelection(
                plan.plan_revision_id,
                queued.run_id,
                candidate.candidate_id,
                candidate.digest,
                "select a different candidate intent",
                (acknowledgement,),
                "persist selection",
                "selection-key",
            ),
        )
    with pytest.raises(Exception, match="terminal_calibration_requires_new_run"):
        service.retry_terminal_run(context, execute, queued.run_id)


def test_durable_queue_submits_the_real_plugin_job_and_replays_by_calibration_key() -> None:
    context = _context()
    execute = replace(
        _decision(Permission.CALIBRATION_EXECUTE),
        database_permissions=tuple(
            sorted(
                (
                    Permission.CALIBRATION_EXECUTE.value,
                    Permission.PLUGIN_READ.value,
                )
            )
        ),
    )
    plan = _plan()
    submitted: list[Any] = []

    class Artifacts:
        async def finalize_derived_bytes(self, *_args: object, **kwargs: object) -> object:
            return SimpleNamespace(
                artifact=SimpleNamespace(
                    id=UUID(int=100),
                    sha256=plan.digest,
                    media_type=kwargs["media_type"],
                ),
                integrity_status=IntegrityStatus.VERIFIED,
            )

        def get_artifact_with_capability(self, *_args: object) -> object:
            artifact = SimpleNamespace(
                organization_id=ORG,
                project_id=PROJECT,
                sha256=SHA,
                media_type="application/vnd.cmp.test-data+json",
            )
            if _args[-1] == NORMALIZED.artifact_id:
                artifact.media_type = "application/vnd.apache.parquet"
            return SimpleNamespace(artifact=artifact, integrity_status=IntegrityStatus.VERIFIED)

    class Authorization:
        def authorize(self, _context: object, permission: Permission) -> AuthorizationDecision:
            assert permission is not Permission.PLUGIN_READ
            return _decision(permission)

    class Plugins:
        def get_active_for_plugin(self, *_args: object, **_kwargs: object) -> object:
            assert cast(AuthorizationDecision, _args[1]).permission is Permission.PLUGIN_READ
            return SimpleNamespace(
                active=True,
                classification=DataClassification.INTERNAL,
                manifest=SimpleNamespace(package_digest="d" * 64),
            )

    class Jobs:
        def submit(self, _context: object, _decision: object, command: Any) -> object:
            submitted.append(command)
            return SimpleNamespace(
                details=SimpleNamespace(
                    job=SimpleNamespace(
                        id=UUID(command.job_spec["job_id"]),
                        state=SimpleNamespace(value="queued"),
                        submitted_at=NOW,
                    )
                ),
                replayed=False,
            )

    service = LinearViscoelasticCalibrationService(
        repository=InMemoryLinearViscoelasticCalibrationRepository(),
        clock=lambda: NOW,
        job_service=Jobs(),  # type: ignore[arg-type]
        artifact_service=Artifacts(),  # type: ignore[arg-type]
        plugin_registry=Plugins(),  # type: ignore[arg-type]
        authorization=Authorization(),  # type: ignore[arg-type]
    )
    snapshot = service.create_plan(
        context,
        execute,
        CreateLinearViscoelasticCalibrationPlan(plan, DataClassification.INTERNAL, "create", "p"),
    )
    queued = service.queue_run(
        context,
        execute,
        QueueLinearViscoelasticCalibrationRun(
            snapshot.id, plan.plan_revision_id, "queue", "run-key"
        ),
    )
    replay = service.queue_run(
        context,
        execute,
        QueueLinearViscoelasticCalibrationRun(
            snapshot.id, plan.plan_revision_id, "queue", "run-key"
        ),
    )
    repeated = service.queue_run(
        context,
        execute,
        QueueLinearViscoelasticCalibrationRun(
            snapshot.id, plan.plan_revision_id, "queue", "second-run-key"
        ),
    )
    assert queued.job_id == UUID(submitted[0].job_spec["job_id"])
    assert replay == queued
    assert repeated.run_id != queued.run_id
    assert repeated.job_id != queued.job_id
    assert len(submitted) == 2
    command = submitted[0]
    assert command.job_type == "plugin.run"
    assert command.resource_policy.cpu_millis == 2_000
    assert command.resource_policy.memory_mb == 4_096
    assert len(command.job_spec["inputs"]) == 3


def test_selected_array_digest_rank_and_promotion_are_deterministic() -> None:
    matrix = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype="<f8")
    assert selected_arrays_digest(
        matrix, channels=("time", "modulus"), source_ordinals=(1, 2)
    ) == selected_arrays_digest(
        matrix.copy(order="F"), channels=("time", "modulus"), source_ordinals=(1, 2)
    )
    rank = rank_diagnostic(np.ones((3, 3)))
    assert rank.status.value == "RANK_DEFICIENT"
    plan = _plan()
    result = calibrate_linear_viscoelastic(plan, _relaxation_input(), run_id=UUID(int=60))
    candidate = result.candidates[0]
    recommendation = result.recommendation
    assert recommendation is not None
    selection = __import__(
        "cmp.modules.modeling.domain.linear_viscoelastic_calibration",
        fromlist=["LinearViscoelasticSelection"],
    ).LinearViscoelasticSelection(
        UUID(int=61),
        UUID(int=62),
        plan.plan_revision_id,
        result.run_id,
        candidate.candidate_id,
        candidate.digest,
        "selected",
        (),
        ACTOR,
        NOW,
    )
    model = promote_selected_linear_viscoelastic_candidate(
        candidate=candidate,
        selection=selection,
        recommendation=recommendation,
        plan=plan,
        run=result,
        material_id=UUID(int=63),
        material_revision_id=UUID(int=64),
        material_state_id=UUID(int=65),
        material_state_revision_id=UUID(int=66),
        property_set_id=UUID(int=67),
        property_set_revision_id=UUID(int=68),
        density_kg_per_m3=900,
        poisson_ratio=0.3,
        reference_temperature_k=293.15,
    )
    assert model.non_production is True
    assert model.calibration_evidence is not None
    assert sum(term.g_ratio for term in model.terms) < 1
    assert all(term.k_ratio == 0 for term in model.terms)


def test_engineer_selection_can_differ_from_recorded_recommendation() -> None:
    plan = replace(
        _plan(),
        start_vectors={1: ((4.0, 2.0, 0.1), (5.0, 3.0, 0.2))},
    )
    result = calibrate_linear_viscoelastic(plan, _relaxation_input(), run_id=UUID(int=160))
    assert result.recommendation is not None and len(result.candidates) == 2
    selected = next(
        value
        for value in result.candidates
        if value.candidate_id != result.recommendation.candidate_id
    )
    selection = __import__(
        "cmp.modules.modeling.domain.linear_viscoelastic_calibration",
        fromlist=["LinearViscoelasticSelection"],
    ).LinearViscoelasticSelection(
        UUID(int=161),
        UUID(int=162),
        plan.plan_revision_id,
        result.run_id,
        selected.candidate_id,
        selected.digest,
        "Engineer selected a reviewed alternative",
        (),
        ACTOR,
        NOW,
    )

    model = promote_selected_linear_viscoelastic_candidate(
        candidate=selected,
        selection=selection,
        recommendation=result.recommendation,
        plan=plan,
        run=result,
        material_id=UUID(int=163),
        material_revision_id=UUID(int=164),
        material_state_id=UUID(int=165),
        material_state_revision_id=UUID(int=166),
        property_set_id=UUID(int=167),
        property_set_revision_id=UUID(int=168),
        density_kg_per_m3=900,
        poisson_ratio=0.3,
        reference_temperature_k=298.15,
    )

    assert model.calibration_evidence is not None
    assert model.calibration_evidence.candidate_id == selected.candidate_id
    assert model.calibration_evidence.recommendation_id == result.recommendation.recommendation_id


def test_profile_legacy_bytes_are_preserved_and_acceptance_key_precedes_writes(
    tmp_path: Path,
) -> None:
    channels = (
        GovernedChannelMapping(
            0, "temperature", QuantityKind.TEMPERATURE, "degC", AxisRole.INDEPENDENT
        ),
        GovernedChannelMapping(1, "frequency", QuantityKind.FREQUENCY, "Hz", AxisRole.INDEPENDENT),
        GovernedChannelMapping(
            2, "storage", QuantityKind.STORAGE_MODULUS, "MPa", AxisRole.DEPENDENT
        ),
        GovernedChannelMapping(3, "loss", QuantityKind.LOSS_MODULUS, "MPa", AxisRole.DEPENDENT),
    )
    legacy = GovernedImportProfileContent(
        "DMA",
        TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP,
        TabularFileFormat.CSV,
        None,
        1,
        "utf-8",
        ",",
        ".",
        channels,
    )
    current = GovernedImportProfileContent(
        "DMA",
        TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP,
        TabularFileFormat.CSV,
        None,
        1,
        "utf-8",
        ",",
        ".",
        channels,
        schema_version="1.2.0",
        deformation_mode="shear",
    )
    assert "schema_version" not in import_profile_canonical(legacy)
    assert "deformation_mode" not in import_profile_canonical(legacy)
    assert current.effective_deformation_mode == "shear"
    output = tmp_path / "acceptance"
    with pytest.raises(RuntimeError):
        prepare_acceptance_setup(
            package_root=ROOT / "plugins/production/linear_viscoelastic_calibrator",
            output_directory=output,
            environ={},
        )
    assert not output.exists()
    key = base64.b64encode(bytes(range(32))).decode("ascii")
    setup = prepare_acceptance_setup(
        package_root=ROOT / "plugins/production/linear_viscoelastic_calibrator",
        output_directory=output,
        environ={"CMP_CALIBRATION_ACCEPTANCE_ED25519_PRIVATE_KEY_B64": key},
    )
    assert setup["idempotency_keys"] == artifact_idempotency_keys(
        setup["package_sha256"],
        signature_sha256=setup["signature_sha256"],
        sbom_sha256=setup["sbom_sha256"],
    )
    assert all(Path(value).is_file() for value in setup["paths"].values())
    detached_signature_document(
        setup["package_sha256"],
        __import__(
            "cryptography.hazmat.primitives.asymmetric.ed25519", fromlist=["Ed25519PrivateKey"]
        ).Ed25519PrivateKey.from_private_bytes(bytes(range(32))),
    )


class _AcceptancePublisher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def publish(
        self,
        *,
        role: str,
        payload: bytes,
        media_type: str,
        expected_sha256: str,
        idempotency_key: str,
    ) -> ArtifactReference:
        assert idempotency_key.endswith(f":{role}")
        self.calls.append(role)
        return ArtifactReference(
            UUID(int=200 + len(self.calls)),
            expected_sha256,
            len(payload),
            media_type,
        )


class _AcceptanceRegistry:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.package: SimpleNamespace | None = None

    def register(self, context: object, decision: object, command: Any) -> SimpleNamespace:
        del context, decision
        self.calls.append("register")
        assert command.manifest["non_production"] is True
        assert len(command.schemas) == 4
        self.package = SimpleNamespace(
            id=UUID(int=250),
            active=False,
            state=PackageState.CONTRACT_VALIDATED,
            schemas=tuple(
                SimpleNamespace(schema_id=value.schema_id, sha256=value.sha256)
                for value in command.schemas
            ),
        )
        return SimpleNamespace(package=self.package, replayed=False)

    def verify(self, context: object, decision: object, command: object) -> SimpleNamespace:
        del context, decision, command
        self.calls.append("verify")
        assert self.package is not None
        self.package.state = PackageState.ELIGIBLE
        return self.package

    def activate(self, context: object, decision: object, command: object) -> SimpleNamespace:
        del context, decision, command
        self.calls.append("activate")
        assert self.package is not None
        self.package.active = True
        return self.package

    def get(self, context: object, decision: object, package_id: UUID) -> SimpleNamespace:
        del context, decision
        self.calls.append("get")
        assert self.package is not None and package_id == self.package.id
        return self.package

    def get_active(
        self,
        context: object,
        decision: object,
        *,
        plugin_id: str,
        plugin_version: str,
        package_digest: str,
    ) -> SimpleNamespace:
        del context, decision
        self.calls.append("get_active")
        assert plugin_id == "cmp.linear_viscoelastic.calibrator"
        assert plugin_version == "1.0.2"
        assert len(package_digest) == 64
        assert self.package is not None and self.package.active
        return self.package


@pytest.mark.parametrize(
    "environ",
    (
        {},
        {"CMP_CALIBRATION_ACCEPTANCE_ED25519_PRIVATE_KEY_B64": "not-base64"},
        {
            "CMP_CALIBRATION_ACCEPTANCE_ED25519_PRIVATE_KEY_B64": base64.b64encode(b"short").decode(
                "ascii"
            )
        },
    ),
)
def test_acceptance_registration_has_zero_external_writes_for_bad_seed(
    tmp_path: Path, environ: dict[str, str]
) -> None:
    publisher = _AcceptancePublisher()
    registry = _AcceptanceRegistry()
    with pytest.raises(RuntimeError):
        register_activate_and_read_back(
            context=_context(),
            submit_decision=_decision(Permission.PLUGIN_SUBMIT),
            activate_decision=_decision(Permission.PLUGIN_ACTIVATE),
            read_decision=_decision(Permission.PLUGIN_READ),
            registry=registry,  # type: ignore[arg-type]
            artifacts=publisher,
            package_root=ROOT / "plugins/production/linear_viscoelastic_calibrator",
            output_directory=tmp_path / "acceptance",
            environ=environ,
        )
    assert publisher.calls == []
    assert registry.calls == []
    assert not (tmp_path / "acceptance").exists()


def test_acceptance_registers_activates_and_reads_back_exact_digest(tmp_path: Path) -> None:
    key = base64.b64encode(bytes(range(32))).decode("ascii")
    publisher = _AcceptancePublisher()
    registry = _AcceptanceRegistry()
    result = register_activate_and_read_back(
        context=_context(),
        submit_decision=_decision(Permission.PLUGIN_SUBMIT),
        activate_decision=_decision(Permission.PLUGIN_ACTIVATE),
        read_decision=_decision(Permission.PLUGIN_READ),
        registry=registry,  # type: ignore[arg-type]
        artifacts=publisher,
        package_root=ROOT / "plugins/production/linear_viscoelastic_calibrator",
        output_directory=tmp_path / "acceptance",
        environ={"CMP_CALIBRATION_ACCEPTANCE_ED25519_PRIVATE_KEY_B64": key},
    )
    second = prepare_acceptance_setup(
        package_root=ROOT / "plugins/production/linear_viscoelastic_calibrator",
        output_directory=tmp_path / "second",
        environ={"CMP_CALIBRATION_ACCEPTANCE_ED25519_PRIVATE_KEY_B64": key},
    )
    assert publisher.calls == ["package", "signature", "sbom"]
    assert registry.calls == ["register", "verify", "activate", "get", "get_active"]
    assert result["active"] is True and result["state"] == "eligible"
    assert result["package_sha256"] == second["package_sha256"]
    assert result["signature_sha256"] == second["signature_sha256"]
    assert result["sbom_sha256"] == second["sbom_sha256"]


def test_acceptance_retry_with_a_new_ephemeral_key_uses_new_signature_identity(
    tmp_path: Path,
) -> None:
    package_root = ROOT / "plugins/production/linear_viscoelastic_calibrator"
    first = prepare_acceptance_setup(
        package_root=package_root,
        output_directory=tmp_path / "first",
        environ={
            "CMP_CALIBRATION_ACCEPTANCE_ED25519_PRIVATE_KEY_B64": base64.b64encode(
                bytes(range(32))
            ).decode("ascii")
        },
    )
    second = prepare_acceptance_setup(
        package_root=package_root,
        output_directory=tmp_path / "second",
        environ={
            "CMP_CALIBRATION_ACCEPTANCE_ED25519_PRIVATE_KEY_B64": base64.b64encode(
                bytes(reversed(range(32)))
            ).decode("ascii")
        },
    )

    assert first["package_sha256"] == second["package_sha256"]
    assert first["sbom_sha256"] == second["sbom_sha256"]
    assert first["signature_sha256"] != second["signature_sha256"]
    assert first["idempotency_keys"]["signature"] != second["idempotency_keys"]["signature"]
    assert first["idempotency_keys"]["package"] == second["idempotency_keys"]["package"]


def test_deterministic_package_and_python_tree_digest(tmp_path: Path) -> None:
    package_root = ROOT / "plugins/production/linear_viscoelastic_calibrator"
    first_zip = tmp_path / "one.zip"
    first_manifest = tmp_path / "one.json"
    second_zip = tmp_path / "two.zip"
    second_manifest = tmp_path / "two.json"
    first = build_package(package_root, first_zip, first_manifest)
    second = build_package(package_root, second_zip, second_manifest)
    assert first["package_digest"] == second["package_digest"]
    assert first_zip.read_bytes() == second_zip.read_bytes()
    assert cmp_python_package_tree_sha256(ROOT / "backend/src/cmp")


def test_job_spec_pins_exact_inputs_resources_and_deadline() -> None:
    spec, resources = build_linear_viscoelastic_job_spec(
        job_id=UUID(int=70),
        attempt_id=UUID(int=71),
        run_id=UUID(int=72),
        plan_revision_id=UUID(int=73),
        plan_sha256=SHA,
        plan_artifact_id=UUID(int=74),
        canonical_test_data_revision_id=UUID(int=75),
        canonical_test_data_artifact_id=UUID(int=76),
        canonical_test_data_sha256=SHA,
        normalized_test_data_revision_id=UUID(int=77),
        normalized_test_data_artifact_id=UUID(int=78),
        normalized_test_data_sha256=SHA,
        package_sha256=SHA,
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        deadline=linear_viscoelastic_deadline(NOW),
        traceparent="00-0000000000000000000000000000000a-000000000000000a-01",
    )
    document = spec.document()
    assert document["extension"]["plugin_id"] == "cmp.linear_viscoelastic.calibrator"
    assert document["operation"] == "execute_plan"
    assert {item["role"] for item in document["inputs"]} == {
        "calibration.plan",
        "test-data.canonical",
        "test-data.normalized",
    }
    assert document["execution"]["seed"] == 0
    assert resources.cpu_millis == 2_000
    assert resources.memory_mb == 4_096
    assert resources.max_attempts == 3
    assert sum((33_554_432, 268_435_456, 134_217_728)) == LINEAR_VISCOELASTIC_MAX_TOTAL_OUTPUT_BYTES


def _queued_import_service() -> tuple[
    LinearViscoelasticCalibrationService,
    SecurityContext,
    AuthorizationDecision,
    LinearViscoelasticCalibrationPlan,
    CalibrationJobReference,
]:
    context = _context()
    execute = _decision(Permission.CALIBRATION_EXECUTE)
    service = LinearViscoelasticCalibrationService(
        repository=InMemoryLinearViscoelasticCalibrationRepository(),
        clock=lambda: NOW,
    )
    plan = _plan()
    snapshot = service.create_plan(
        context,
        execute,
        CreateLinearViscoelasticCalibrationPlan(plan, DataClassification.INTERNAL, "create", None),
    )
    queued = service.queue_run(
        context,
        execute,
        QueueLinearViscoelasticCalibrationRun(
            snapshot.id,
            plan.plan_revision_id,
            "queue",
            f"run-{plan.plan_id}",
        ),
    )
    return service, context, _decision(Permission.JOB_EXECUTE), plan, queued


def test_validated_run_result_parser_rebuilds_typed_attempts_and_candidate_digest() -> None:
    plan = _plan()
    result = calibrate_linear_viscoelastic(plan, _relaxation_input(), run_id=UUID(int=800))

    parsed = parse_calibration_run_result(
        {
            "schema_id": "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0",
            "schema_version": "1.0.0",
            **result.canonical(),
        }
    )

    assert parsed.digest == result.digest
    assert parsed.attempts[0].term_count == 1
    assert parsed.candidates[0].digest == result.candidates[0].digest
    assert parsed.recommendation is not None
    assert parsed.recommendation.candidate_digest == parsed.candidates[0].digest


def test_import_validated_result_persists_and_replays_idempotently() -> None:
    service, context, worker, plan, queued = _queued_import_service()
    result = calibrate_linear_viscoelastic(plan, _relaxation_input(), run_id=queued.run_id)
    document = {
        "schema_id": "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0",
        "schema_version": "1.0.0",
        **result.canonical(),
    }
    kwargs: dict[str, Any] = {
        "run_id": queued.run_id,
        "job_id": queued.job_id,
        "attempt_id": UUID(int=801),
        "job_attempt_no": 1,
        "package_sha256": SHA,
        "result": document,
        "result_digest": result.digest,
        "result_manifest_artifact_id": UUID(int=802),
        "result_manifest_sha256": "b" * 64,
        "response_residual_artifact_id": UUID(int=803),
        "objective_history_artifact_id": UUID(int=804),
        "submitted_at": NOW,
        "deadline_at": NOW,
    }

    finished = service.import_validated_result(context, worker, **kwargs)
    replay = service.import_validated_result(context, worker, **kwargs)

    assert finished.status == "succeeded"
    assert finished.result is not None
    assert finished.result.digest == result.digest
    assert finished.result.response_residual_artifact_ids == (UUID(int=803),)
    assert finished.result.objective_history_artifact_ids == (UUID(int=804),)
    assert len(finished.execution_ledger) == 1
    assert replay == finished


def test_import_validated_result_rejects_conflict_and_bad_transport_digest() -> None:
    service, context, worker, plan, queued = _queued_import_service()
    result = calibrate_linear_viscoelastic(plan, _relaxation_input(), run_id=queued.run_id)
    service.import_validated_result(
        context,
        worker,
        run_id=queued.run_id,
        job_id=queued.job_id,
        attempt_id=UUID(int=805),
        job_attempt_no=1,
        package_sha256=SHA,
        result={
            "schema_id": "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0",
            "schema_version": "1.0.0",
            **result.canonical(),
        },
        result_digest=result.digest,
        result_manifest_artifact_id=UUID(int=806),
        result_manifest_sha256="c" * 64,
        submitted_at=NOW,
        deadline_at=NOW,
    )
    changed_candidate = replace(result.candidates[0], bic=result.candidates[0].bic + 1.0)
    recommendation = result.recommendation
    assert recommendation is not None
    changed_recommendation = replace(
        recommendation,
        candidate_digest=changed_candidate.digest,
    )
    changed = replace(
        result,
        candidates=(changed_candidate,),
        recommendation=changed_recommendation,
    )
    with pytest.raises(Exception, match="accepted_result_conflict"):
        service.import_validated_result(
            context,
            worker,
            run_id=queued.run_id,
            job_id=queued.job_id,
            attempt_id=UUID(int=807),
            job_attempt_no=2,
            package_sha256=SHA,
            result={
                "schema_id": "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0",
                "schema_version": "1.0.0",
                **changed.canonical(),
            },
            result_digest=changed.digest,
            result_manifest_artifact_id=UUID(int=808),
            result_manifest_sha256="d" * 64,
            submitted_at=NOW,
            deadline_at=NOW,
        )
    with pytest.raises(InvalidResultManifest, match="digest"):
        service.import_validated_result(
            context,
            worker,
            run_id=queued.run_id,
            job_id=queued.job_id,
            attempt_id=UUID(int=809),
            job_attempt_no=2,
            package_sha256=SHA,
            result={
                "schema_id": "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0",
                "schema_version": "1.0.0",
                **result.canonical(),
            },
            result_digest="e" * 64,
            submitted_at=NOW,
            deadline_at=NOW,
        )


def test_import_validated_result_rejects_result_identity_mismatch() -> None:
    service, context, worker, plan, queued = _queued_import_service()
    result = calibrate_linear_viscoelastic(plan, _relaxation_input(), run_id=UUID(int=810))

    with pytest.raises(Exception, match="exact Run"):
        service.import_validated_result(
            context,
            worker,
            run_id=queued.run_id,
            job_id=queued.job_id,
            attempt_id=UUID(int=811),
            job_attempt_no=1,
            package_sha256=SHA,
            result={
                "schema_id": "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0",
                "schema_version": "1.0.0",
                **result.canonical(),
            },
            result_digest=result.digest,
            submitted_at=NOW,
            deadline_at=NOW,
        )


def test_execution_failure_retries_before_recording_terminal_state() -> None:
    service, context, worker, _, queued = _queued_import_service()

    retrying = service.record_execution_failure(
        context,
        worker,
        run_id=queued.run_id,
        job_id=queued.job_id,
        attempt_id=UUID(int=812),
        job_attempt_no=1,
        outcome="failed",
        diagnostic_code="isolation_unavailable",
        package_sha256=SHA,
        submitted_at=NOW,
        deadline_at=NOW,
        retry_scheduled=True,
    )
    assert retrying.status == "retrying"
    assert retrying.result is None
    assert retrying.failure_code == "EXECUTION_ISOLATION_UNAVAILABLE"

    service2, context2, worker2, _, queued2 = _queued_import_service()
    terminal = service2.record_execution_failure(
        context2,
        worker2,
        run_id=queued2.run_id,
        job_id=queued2.job_id,
        attempt_id=UUID(int=813),
        job_attempt_no=1,
        outcome="timed_out",
        package_sha256=SHA,
        submitted_at=NOW,
        deadline_at=NOW,
        retry_scheduled=False,
    )
    assert terminal.status == "failed"
    assert terminal.result is not None
    assert terminal.result.failure_code == "CALCULATION_TIMED_OUT"
    assert terminal.recovery_hint is not None
