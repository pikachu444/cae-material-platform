from __future__ import annotations

import asyncio
import copy
import hashlib
from collections.abc import AsyncIterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from cmp.modules.artifacts.domain.content import IntegrityStatus
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.jobs.application.jobs import ClaimedAttempt
from cmp.modules.jobs.application.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_HISTORY_SCHEMA,
    LINEAR_VISCOELASTIC_OUTPUT_CAPS,
    LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA,
    LINEAR_VISCOELASTIC_RESULT_SCHEMA,
    build_linear_viscoelastic_job_spec,
)
from cmp.modules.jobs.domain.jobs import (
    AttemptRecord,
    AttemptState,
    JobRecord,
    JobState,
    RetryKind,
)
from cmp.modules.modeling.adapters.worker.linear_viscoelastic_calibration_results import (
    LinearViscoelasticCalibrationResultCommitter,
)
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    CreateLinearViscoelasticCalibrationPlan,
    InMemoryLinearViscoelasticCalibrationRepository,
    LinearViscoelasticCalibrationService,
    QueueLinearViscoelasticCalibrationRun,
)
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
    calibrate_linear_viscoelastic,
)
from cmp.modules.plugins.adapters.worker.handler import PluginAttemptHandler
from cmp.modules.plugins.application.execution import ExecutePlugin
from cmp.modules.plugins.domain.execution import (
    InvalidResultManifest,
    ResultStatus,
    RunnerOutput,
    ValidatedPluginResult,
)
from cmp.shared.domain.revisions import canonical_json_bytes

NOW = datetime(2026, 8, 28, tzinfo=UTC)
ORG = UUID(int=10)
PROJECT = UUID(int=11)
ACTOR = UUID(int=12)
SHA = "a" * 64
DEFAULT_JOB_ID = UUID(int=201)
DEFAULT_ATTEMPT_ID = UUID(int=202)


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


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.SERVICE, "Calibration worker", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test.invalid",
        subject=str(ACTOR),
        token_id="worker-token",
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
        roles=(
            (Role.JOB_RUNNER,) if permission is Permission.JOB_EXECUTE else (Role.MATERIAL_MODELER,)
        ),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=UUID(int=13),
        trace_id="00-0000000000000000000000000000000a-000000000000000a-01",
        decided_at=NOW,
    )


def _plan() -> LinearViscoelasticCalibrationPlan:
    return LinearViscoelasticCalibrationPlan.for_terms(
        (1,),
        plan_id=UUID(int=100),
        plan_revision_id=UUID(int=101),
        bounds={
            1: (
                ParameterBound("G_inf_pa", 1, 4, 20, "Pa"),
                ParameterBound("G_1_pa", 1, 2, 10, "Pa"),
                ParameterBound("tau_1_s", 0.01, 0.1, 1, "s"),
            )
        },
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


def _input() -> CanonicalViscoelasticInput:
    return CanonicalViscoelasticInput.from_relaxation(
        (
            RelaxationObservation(0, 0.0, 6.0, PointPartition.EXCLUDED, "INSTANTANEOUS_LIMIT"),
            RelaxationObservation(1, 0.01, 5.809674836071919),
            RelaxationObservation(2, 0.1, 4.735758882342885),
            RelaxationObservation(3, 1.0, 4.000090799859524),
            RelaxationObservation(4, 2.0, 4.1, PointPartition.HOLDOUT),
        ),
        profile_deformation_mode="not-characterized",
        canonical_test_data=ExactRevisionPin(UUID(int=1), UUID(int=2), SHA),
        canonical_artifact=ArtifactPin(UUID(int=3), SHA, "application/json"),
        normalized_artifact=ArtifactPin(UUID(int=4), SHA, "application/vnd.apache.parquet"),
        raw_source_sha256=SHA,
        import_profile=ExactRevisionPin(UUID(int=5), UUID(int=6), SHA),
        profile_sha256=SHA,
    )


class _RecordingArtifacts:
    def __init__(self) -> None:
        self.records: dict[str, object] = {}
        self.calls: list[str] = []

    async def finalize_derived_stream(
        self, context: object, decision: object, **kwargs: object
    ) -> object:
        del context, decision
        chunks = cast(AsyncIterable[bytes], kwargs["chunks"])
        value = b"".join([chunk async for chunk in chunks])
        expected_digest = kwargs["expected_sha256"]
        expected_size = kwargs["expected_size_bytes"]
        assert hashlib.sha256(value).hexdigest() == expected_digest
        assert len(value) == expected_size
        key = str(kwargs["idempotency_key"])
        self.calls.append(key)
        existing = self.records.get(key)
        if existing is not None:
            return existing
        artifact = SimpleNamespace(
            id=uuid5(NAMESPACE_URL, key),
            organization_id=ORG,
            project_id=PROJECT,
            classification=kwargs["classification"],
            artifact_role=kwargs["artifact_role"],
            schema_ref=kwargs["schema_ref"],
            media_type=kwargs["media_type"],
            size_bytes=expected_size,
            sha256=expected_digest,
        )
        record = SimpleNamespace(
            artifact=artifact,
            integrity_status=IntegrityStatus.VERIFIED,
        )
        self.records[key] = record
        return record


class _Planner:
    async def prepare(self, claimed: ClaimedAttempt) -> ExecutePlugin:
        del claimed
        return cast(ExecutePlugin, object())


class _Execution:
    def __init__(self, result: ValidatedPluginResult) -> None:
        self.result = result

    async def execute(self, command: ExecutePlugin, cancellation: object) -> ValidatedPluginResult:
        del command, cancellation
        return self.result


def _claim(
    *,
    run_id: UUID,
    plan: LinearViscoelasticCalibrationPlan,
    attempt_id: UUID = DEFAULT_ATTEMPT_ID,
    job_id: UUID = DEFAULT_JOB_ID,
) -> ClaimedAttempt:
    test_data = plan.test_data
    canonical_artifact = plan.canonical_artifact
    normalized_artifact = plan.normalized_artifact
    assert test_data is not None
    assert canonical_artifact is not None
    assert normalized_artifact is not None
    spec, policy = build_linear_viscoelastic_job_spec(
        job_id=job_id,
        attempt_id=attempt_id,
        run_id=run_id,
        plan_revision_id=plan.plan_revision_id,
        plan_sha256=plan.digest,
        plan_artifact_id=UUID(int=203),
        canonical_test_data_revision_id=test_data.revision_id,
        canonical_test_data_artifact_id=canonical_artifact.artifact_id,
        canonical_test_data_sha256=canonical_artifact.sha256,
        normalized_test_data_revision_id=test_data.revision_id,
        normalized_test_data_artifact_id=normalized_artifact.artifact_id,
        normalized_test_data_sha256=normalized_artifact.sha256,
        package_sha256=SHA,
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        deadline=NOW + timedelta(hours=1),
        traceparent=_context().trace_id,
    )
    job = JobRecord(
        id=job_id,
        organization_id=ORG,
        project_id=PROJECT,
        classification=DataClassification.INTERNAL,
        job_type="plugin.run",
        state=JobState.RUNNING,
        priority=0,
        submitted_at=NOW,
        submitted_by=ACTOR,
        request_id=UUID(int=204),
        trace_id=_context().trace_id,
        deadline=spec.deadline,
        resource_policy=policy,
        attempt_count=1,
        current_attempt_id=attempt_id,
        result_manifest_id=None,
        result_manifest_digest=None,
        failure=None,
        cancel_requested_at=None,
        updated_at=NOW,
    )
    attempt = AttemptRecord(
        id=attempt_id,
        job_id=job_id,
        attempt_no=1,
        state=AttemptState.RUNNING,
        retry_kind=RetryKind.INITIAL,
        retry_reason="initial submission",
        spec=spec,
        runner_id=UUID(int=205),
        lease_token=UUID(int=206),
        lease_expires_at=NOW + timedelta(minutes=5),
        heartbeat_at=NOW,
        claimed_at=NOW,
        started_at=NOW,
        ended_at=None,
        progress_fraction=None,
        progress_phase=None,
        progress_updated_at=None,
        result_manifest_id=None,
        result_manifest_digest=None,
        failure=None,
    )
    return ClaimedAttempt(job, attempt)


def _result(
    tmp_path: Path,
    *,
    plan: LinearViscoelasticCalibrationPlan,
    run_id: UUID,
    job_id: UUID,
    attempt_id: UUID,
) -> ValidatedPluginResult:
    calculation = calibrate_linear_viscoelastic(plan, _input(), run_id=run_id)
    document = {
        "schema_id": LINEAR_VISCOELASTIC_RESULT_SCHEMA,
        "schema_version": "1.0.0",
        **calculation.canonical(),
    }
    run_bytes = canonical_json_bytes(document)
    output_values = (
        (
            "calibration.run-result",
            LINEAR_VISCOELASTIC_RESULT_SCHEMA,
            "application/json",
            run_bytes,
        ),
        (
            "response-residuals",
            LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA,
            "application/vnd.apache.parquet",
            b"residual",
        ),
        (
            "objective-history",
            LINEAR_VISCOELASTIC_HISTORY_SCHEMA,
            "application/vnd.apache.parquet",
            b"history",
        ),
    )
    outputs: list[RunnerOutput] = []
    manifest_outputs: list[dict[str, object]] = []
    for index, (role, schema_ref, media_type, value) in enumerate(output_values, start=1):
        path = tmp_path / f"{index}-{role}.bin"
        path.write_bytes(value)
        digest = hashlib.sha256(value).hexdigest()
        staged = f"runner-output:{index}:sha256:{digest}"
        output = RunnerOutput(role, media_type, schema_ref, staged, digest, len(value), path)
        outputs.append(output)
        manifest_outputs.append(
            {
                "role": role,
                "media_type": media_type,
                "schema_ref": schema_ref,
                "staged_artifact": staged,
                "sha256": digest,
                "size_bytes": len(value),
            }
        )
    manifest = {
        "result_manifest_version": "1.0",
        "job_id": str(job_id),
        "attempt_id": str(attempt_id),
        "status": "succeeded",
        "started_at": "2026-08-28T00:00:00Z",
        "ended_at": "2026-08-28T00:00:00Z",
        "outputs": manifest_outputs,
        "diagnostics": [],
        "metrics": {"wall_time_s": 0.1, "peak_memory_mb": 1.0},
        "reproducibility": {
            "package_digest": f"sha256:{SHA}",
            "dependency_lock_digest": f"sha256:{'b' * 64}",
            "seed": 0,
            "hardware_summary": "unit-test",
        },
        "non_production": True,
    }
    manifest_digest = hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()
    return ValidatedPluginResult(
        ResultStatus.SUCCEEDED,
        manifest,
        manifest_digest,
        tuple(outputs),
    )


def _setup(
    tmp_path: Path,
) -> tuple[
    LinearViscoelasticCalibrationService,
    InMemoryLinearViscoelasticCalibrationRepository,
    SecurityContext,
    AuthorizationDecision,
    LinearViscoelasticCalibrationPlan,
    ClaimedAttempt,
    _RecordingArtifacts,
    ValidatedPluginResult,
]:
    context = _context()
    repository = InMemoryLinearViscoelasticCalibrationRepository()
    service = LinearViscoelasticCalibrationService(
        repository=repository,
        id_factory=iter((UUID(int=200), UUID(int=201))).__next__,
        clock=lambda: NOW,
    )
    plan = _plan()
    service.create_plan(
        context,
        _decision(Permission.CALIBRATION_EXECUTE),
        CreateLinearViscoelasticCalibrationPlan(
            plan, DataClassification.INTERNAL, "create test plan", "plan-key"
        ),
    )
    queued = service.queue_run(
        context,
        _decision(Permission.CALIBRATION_EXECUTE),
        QueueLinearViscoelasticCalibrationRun(
            plan.plan_id, plan.plan_revision_id, "queue test run", "run-key"
        ),
    )
    claimed = _claim(run_id=queued.run_id, plan=plan)
    artifacts = _RecordingArtifacts()
    return (
        service,
        repository,
        context,
        _decision(Permission.JOB_EXECUTE),
        plan,
        claimed,
        artifacts,
        _result(
            tmp_path,
            plan=plan,
            run_id=queued.run_id,
            job_id=queued.job_id,
            attempt_id=claimed.attempt.id,
        ),
    )


def test_real_handler_committer_persists_and_replays_exact_result(tmp_path: Path) -> None:
    (
        service,
        repository,
        context,
        decision,
        _plan_value,
        claimed,
        artifacts,
        result,
    ) = _setup(tmp_path)
    committer = LinearViscoelasticCalibrationResultCommitter(
        context=context,
        decision=decision,
        artifact_service=artifacts,  # type: ignore[arg-type]
        calibration_service=service,
    )
    handler = PluginAttemptHandler(
        planner=_Planner(),  # type: ignore[arg-type]
        execution=_Execution(result),  # type: ignore[arg-type]
        committer=committer,
    )

    first = asyncio.run(handler.execute(claimed, asyncio.Event()))
    replay = asyncio.run(handler.execute(claimed, asyncio.Event()))

    assert first.outcome is AttemptState.SUCCEEDED
    assert replay.outcome is AttemptState.SUCCEEDED
    assert first.result_manifest_id == replay.result_manifest_id
    run = next(iter(repository.runs.values()))
    assert run.result is not None
    assert len(run.execution_ledger) == 1
    assert len(artifacts.records) == 4
    assert len(artifacts.calls) == 8


@pytest.mark.parametrize("kind", ("role", "cap"))
def test_committer_rejects_calibration_output_role_or_cap_before_artifact_writes(
    tmp_path: Path, kind: str
) -> None:
    (
        service,
        _repository,
        context,
        decision,
        _plan_value,
        claimed,
        artifacts,
        result,
    ) = _setup(tmp_path)
    manifest = copy.deepcopy(result.manifest)
    outputs = list(result.outputs)
    if kind == "role":
        outputs[0] = replace(outputs[0], role="unexpected-output")
        manifest["outputs"][0]["role"] = "unexpected-output"  # type: ignore[index]
    else:
        oversized = LINEAR_VISCOELASTIC_OUTPUT_CAPS["calibration.run-result"] + 1
        outputs[0] = replace(outputs[0], size_bytes=oversized)
        manifest["outputs"][0]["size_bytes"] = oversized  # type: ignore[index]
    malformed = replace(
        result,
        outputs=tuple(outputs),
        manifest=manifest,
        manifest_digest=hashlib.sha256(canonical_json_bytes(manifest)).hexdigest(),
    )
    committer = LinearViscoelasticCalibrationResultCommitter(
        context=context,
        decision=decision,
        artifact_service=artifacts,  # type: ignore[arg-type]
        calibration_service=service,
    )

    with pytest.raises(InvalidResultManifest):
        asyncio.run(committer.commit(claimed=claimed, result=malformed))
    assert not artifacts.calls
