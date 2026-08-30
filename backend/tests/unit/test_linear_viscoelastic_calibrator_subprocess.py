"""Fixture-driven regression for the isolated linear-viscoelastic plugin boundary."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import importlib.util
import io
import json
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

import pyarrow as pa
import pyarrow.parquet as pq
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
    build_linear_viscoelastic_job_spec,
)
from cmp.modules.jobs.domain.jobs import (
    AttemptRecord,
    AttemptState,
    JobRecord,
    JobState,
    RetryKind,
)
from cmp.modules.modeling.adapters.persistence import (
    linear_viscoelastic_calibration_serialization as lve_serialization,
)
from cmp.modules.modeling.adapters.worker.linear_viscoelastic_calibration_results import (
    LinearViscoelasticCalibrationResultCommitter,
)
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CreateLinearViscoelasticCalibrationPlan,
    QueueLinearViscoelasticCalibrationRun,
)
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    InMemoryLinearViscoelasticCalibrationRepository,
    LinearViscoelasticCalibrationService,
)
from cmp.modules.modeling.application.linear_viscoelastic_result_import import (
    parse_calibration_run_result,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
    LinearViscoelasticCalibrationPlan,
)
from cmp.modules.plugins.adapters.contracts.runner import JsonSchemaRunnerContractValidator
from cmp.modules.plugins.adapters.runner.subprocess import SubprocessPluginRunner
from cmp.modules.plugins.application.execution import ExecutePlugin, PluginExecutionService
from cmp.modules.plugins.domain.execution import (
    AllowedOutput,
    ExecutablePluginPackage,
    ExecutionSchema,
    RunnerLimits,
    SandboxPolicy,
    StagedInput,
    ValidatedPluginResult,
)
from cmp.modules.plugins.domain.registry import ExtensionType
from cmp.modules.testing.domain.public_shear_dma import load_public_shear_dma_fixture
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256
from cmp.tools.linear_viscoelastic_synthetic_acceptance import (
    calibration_bounds,
    calibration_start_vectors,
)

ROOT = Path(__file__).parents[3]
PLUGIN_ROOT = ROOT / "plugins/production/linear_viscoelastic_calibrator"
PUBLIC_FIXTURE = ROOT / "fixtures/public/smp-shear-dma-283.15k-v1.csv"


def _build_package(root: Path, output: Path) -> tuple[dict[str, object], str, str]:
    builder_path = ROOT / "scripts/build_linear_viscoelastic_calibrator.py"
    spec = importlib.util.spec_from_file_location("test_lve_subprocess_builder", builder_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest_path = output.with_suffix(".json")
    manifest = module.build_package(root, output, manifest_path)
    package_digest = hashlib.sha256(output.read_bytes()).hexdigest()
    lock_digest = hashlib.sha256((root / "dependency.lock").read_bytes()).hexdigest()
    return manifest, package_digest, lock_digest


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f") if value else "0"


def _fixture_documents() -> tuple[bytes, bytes]:
    fixture = load_public_shear_dma_fixture(PUBLIC_FIXTURE)
    rows = tuple(csv.DictReader(io.StringIO(fixture.source_bytes.decode("utf-8"))))
    quantity_contracts = {
        "temperature": (
            "physics.temperature",
            "independent",
            "Cel",
            "K",
            Decimal("1"),
            Decimal("273.15"),
        ),
        "frequency": (
            "frequency.cyclic",
            "independent",
            "Hz",
            "Hz",
            Decimal("1"),
            Decimal("0"),
        ),
        "storage_modulus": (
            "mechanics.modulus.storage",
            "dependent",
            "MPa",
            "Pa",
            Decimal("1000000"),
            Decimal("0"),
        ),
        "loss_modulus": (
            "mechanics.modulus.loss",
            "dependent",
            "MPa",
            "Pa",
            Decimal("1000000"),
            Decimal("0"),
        ),
    }
    channels: list[dict[str, object]] = []
    columns: dict[str, list[float]] = {}
    for channel in fixture.channels:
        source_quantity = str(channel["source_quantity"])
        semantics, axis_role, original_unit, normalized_unit, scale, offset = quantity_contracts[
            source_quantity
        ]
        key = str(channel["source_column"])
        originals = [Decimal(row[key]) for row in rows]
        normalized = [item * scale + offset for item in originals]
        channels.append(
            {
                "key": key,
                "name": key,
                "quantity_semantics": semantics,
                "axis_role": axis_role,
                "original_unit_string": original_unit,
                "normalized_unit": normalized_unit,
                "normalization": {
                    "scale": _decimal_text(scale),
                    "offset": _decimal_text(offset),
                },
                "original_values": [_decimal_text(item) for item in originals],
                "normalized_values": [_decimal_text(item) for item in normalized],
                "missing_reasons": [None] * len(rows),
            }
        )
        columns[key] = [float(item) for item in normalized]
    canonical = {
        "document_type": "cmp.test-data",
        "schema_version": "1.0.0",
        "document_id": "CMP-PUBLIC-SMP-DMA-28315",
        "material": {"maker": "fixture", "grade": "fixture", "lot_batch": None},
        "test": {
            "operator": "fixture",
            "laboratory": "fixture",
            "method": "reference shear DMA frequency sweep",
            "equipment_maker": None,
            "equipment_model": None,
        },
        "specimen": {"specimen_id": "fixture", "description": None},
        "conditions": [],
        "channels": channels,
        "source": {
            "file_name": PUBLIC_FIXTURE.name,
            "media_type": "text/csv",
            "sha256": fixture.derived_sha256,
        },
    }
    parquet = io.BytesIO()
    table = pa.table(columns)
    metadata = {
        f"cmp.channel.{key}.quantity_semantics".encode(): str(
            channel["quantity_semantics"]
        ).encode()
        for key, channel in zip(columns, channels, strict=True)
    }
    table = table.replace_schema_metadata(metadata)
    pq.write_table(  # type: ignore[no-untyped-call]
        table, parquet, compression="zstd", write_statistics=True
    )
    return (
        json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode(),
        parquet.getvalue(),
    )


def _plan_document(
    *, canonical_sha256: str = "2" * 64, normalized_sha256: str = "3" * 64
) -> dict[str, object]:
    fixture = load_public_shear_dma_fixture(PUBLIC_FIXTURE)
    row_count = fixture.row_count
    holdout_count = max(1, row_count // 6)
    semantics = {
        "mode": "dma",
        "deformation_mode": "shear",
        "channels": [
            {
                "key": "temperature_c",
                "quantity_semantics": "physics.temperature",
                "axis_role": "independent",
                "original_unit_string": "Cel",
                "normalized_unit": "K",
            },
            {
                "key": "frequency_hz",
                "quantity_semantics": "frequency.cyclic",
                "axis_role": "independent",
                "original_unit_string": "Hz",
                "normalized_unit": "Hz",
            },
            {
                "key": "storage_modulus_mpa",
                "quantity_semantics": "mechanics.modulus.storage",
                "axis_role": "dependent",
                "original_unit_string": "MPa",
                "normalized_unit": "Pa",
            },
            {
                "key": "loss_modulus_mpa",
                "quantity_semantics": "mechanics.modulus.loss",
                "axis_role": "dependent",
                "original_unit_string": "MPa",
                "normalized_unit": "Pa",
            },
        ],
        "point_dispositions": [
            {
                "ordinal": ordinal,
                "partition": "HOLDOUT" if ordinal >= row_count - holdout_count else "CALIBRATION",
                "exclusion_reason": None,
            }
            for ordinal in range(row_count)
        ],
        "selected_temperature_k": "283.15",
        "temperature_source": "channel",
        "strain_amplitude": "0.001",
        "strain_amplitude_quantity": "mechanics.strain.shear",
        "strain_amplitude_unit": "1",
        "frequency_kind": "cyclic_hz",
        "angular_frequency_conversion": "omega_rad_per_s=2*pi*frequency_hz",
    }
    term_counts = (1, 2)
    return {
        "schema_id": "urn:cmp:modeling:linear-viscoelastic-calibration-plan:1.0.0",
        "schema_version": "1.0.0",
        "plan_id": str(UUID(int=1)),
        "plan_revision_id": str(UUID(int=2)),
        "test_data": {"id": str(UUID(int=3)), "revision_id": str(UUID(int=4)), "sha256": "1" * 64},
        "canonical_artifact": {
            "artifact_id": str(UUID(int=105)),
            "sha256": canonical_sha256,
            "media_type": "application/vnd.cmp.test-data+json",
        },
        "normalized_artifact": {
            "artifact_id": str(UUID(int=107)),
            "sha256": normalized_sha256,
            "media_type": "application/vnd.apache.parquet",
        },
        "raw_source_sha256": "4" * 64,
        "import_profile": {
            "id": str(UUID(int=7)),
            "revision_id": str(UUID(int=8)),
            "sha256": "5" * 64,
        },
        "profile_sha256": "5" * 64,
        "input_semantics": semantics,
        "recommendation_policy": LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        "term_counts": list(term_counts),
        "parameter_bounds": {str(term): calibration_bounds(term) for term in term_counts},
        "start_vectors": calibration_start_vectors(term_counts),
        "weights": {
            "relaxation_weight": "1",
            "dma_storage_weight": "0.5",
            "dma_loss_weight": "0.5",
            "relaxation_scale_pa": "1000000000",
            "dma_storage_scale_pa": "1000000000",
            "dma_loss_scale_pa": "1000000000",
            "q_rule_version": "equal_per_point@1.0.0",
        },
        "optimizer": {
            "method": "trf",
            "x_scale": "jac",
            "transform": "ln",
            "ftol": 1e-8,
            "xtol": 1e-8,
            "gtol": 1e-8,
            "max_nfev": 5000,
        },
        "seed": 0,
        "seed_status": "not_applicable",
        "statuses": {
            "ramp": "NOT_PROVIDED",
            "sweep": "PROVIDED",
            "preconditioning": "NOT_PROVIDED",
            "linear_range": "NOT_PROVIDED",
        },
    }


_WORKER_NOW = datetime.now(UTC)
_WORKER_ORG = UUID(int=10)
_WORKER_PROJECT = UUID(int=11)
_WORKER_ACTOR = UUID(int=12)
_WORKER_TRACE = "00-0000000000000000000000000000000a-000000000000000a-01"


def _worker_context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(_WORKER_ACTOR, PrincipalType.SERVICE, "Calibration worker", True),
        organization_id=_WORKER_ORG,
        project_id=_WORKER_PROJECT,
        issuer="https://test.invalid",
        subject=str(_WORKER_ACTOR),
        token_id="fixture-worker-token",
        groups=(),
        scopes=(),
        request_id=UUID(int=13),
        trace_id=_WORKER_TRACE,
        authenticated_at=_WORKER_NOW,
    )


def _worker_decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=_WORKER_ACTOR,
        organization_id=_WORKER_ORG,
        project_id=_WORKER_PROJECT,
        permission=permission,
        roles=(Role.JOB_RUNNER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=UUID(int=13),
        trace_id=_WORKER_TRACE,
        decided_at=_WORKER_NOW,
    )


class _FixtureArtifactService:
    """Outer artifact port fake that retains immutable bytes and idempotency."""

    def __init__(self) -> None:
        self.records: dict[str, object] = {}
        self.calls: list[str] = []

    async def finalize_derived_stream(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        **kwargs: object,
    ) -> object:
        del context, decision
        chunks = cast(AsyncIterable[bytes], kwargs["chunks"])
        value = b"".join([chunk async for chunk in chunks])
        expected_digest = kwargs["expected_sha256"]
        expected_size = kwargs["expected_size_bytes"]
        assert isinstance(expected_digest, str)
        assert isinstance(expected_size, int)
        assert hashlib.sha256(value).hexdigest() == expected_digest
        assert len(value) == expected_size
        key = str(kwargs["idempotency_key"])
        self.calls.append(key)
        existing = self.records.get(key)
        if existing is not None:
            return existing
        artifact = SimpleNamespace(
            id=uuid5(NAMESPACE_URL, key),
            organization_id=_WORKER_ORG,
            project_id=_WORKER_PROJECT,
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


def _fixture_claim(
    *,
    plan: LinearViscoelasticCalibrationPlan,
    package_sha256: str,
    canonical_sha256: str,
    normalized_sha256: str,
    job_id: UUID,
    attempt_id: UUID,
    run_id: UUID,
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
        plan_artifact_id=UUID(int=104),
        canonical_test_data_revision_id=test_data.revision_id,
        canonical_test_data_artifact_id=canonical_artifact.artifact_id,
        canonical_test_data_sha256=canonical_sha256,
        normalized_test_data_revision_id=test_data.revision_id,
        normalized_test_data_artifact_id=normalized_artifact.artifact_id,
        normalized_test_data_sha256=normalized_sha256,
        package_sha256=package_sha256,
        recommendation_policy=plan.recommendation_policy,
        deadline=datetime.now(UTC) + timedelta(hours=1),
        traceparent=_WORKER_TRACE,
    )
    job = JobRecord(
        id=job_id,
        organization_id=_WORKER_ORG,
        project_id=_WORKER_PROJECT,
        classification=DataClassification.INTERNAL,
        job_type="plugin.run",
        state=JobState.RUNNING,
        priority=0,
        submitted_at=_WORKER_NOW,
        submitted_by=_WORKER_ACTOR,
        request_id=UUID(int=14),
        trace_id=_WORKER_TRACE,
        deadline=spec.deadline,
        resource_policy=policy,
        attempt_count=1,
        current_attempt_id=attempt_id,
        result_manifest_id=None,
        result_manifest_digest=None,
        failure=None,
        cancel_requested_at=None,
        updated_at=_WORKER_NOW,
    )
    attempt = AttemptRecord(
        id=attempt_id,
        job_id=job_id,
        attempt_no=1,
        state=AttemptState.RUNNING,
        retry_kind=RetryKind.INITIAL,
        retry_reason="fixture execution",
        spec=spec,
        runner_id=UUID(int=15),
        lease_token=UUID(int=16),
        lease_expires_at=_WORKER_NOW + timedelta(minutes=5),
        heartbeat_at=_WORKER_NOW,
        claimed_at=_WORKER_NOW,
        started_at=_WORKER_NOW,
        ended_at=None,
        progress_fraction=None,
        progress_phase=None,
        progress_updated_at=None,
        result_manifest_id=None,
        result_manifest_digest=None,
        failure=None,
    )
    return ClaimedAttempt(job, attempt)


def _run_public_plugin(
    tmp_path: Path,
    *,
    job_id: UUID,
    attempt_id: UUID,
    run_id: UUID,
) -> tuple[ValidatedPluginResult, str, LinearViscoelasticCalibrationPlan]:
    canonical, normalized = _fixture_documents()
    plan = lve_serialization.plan_from_payload(
        _plan_document(
            canonical_sha256=hashlib.sha256(canonical).hexdigest(),
            normalized_sha256=hashlib.sha256(normalized).hexdigest(),
        )
    )
    plan_bytes = canonical_json_bytes(plan.canonical())
    package_zip = tmp_path / "calibrator.zip"
    manifest, package_digest, lock_digest = _build_package(PLUGIN_ROOT, package_zip)
    package_manifest = json.loads(json.dumps(manifest))
    assert isinstance(package_manifest, dict)
    extensions = package_manifest.get("extensions")
    assert isinstance(extensions, list) and extensions
    extension = extensions[0]
    assert isinstance(extension, dict)
    entrypoint = str(extension["entrypoint"])
    config_schema_document = json.loads(
        (PLUGIN_ROOT / "schemas/config.schema.json").read_text(encoding="utf-8")
    )
    assert isinstance(config_schema_document, dict)
    config_schema = ExecutionSchema(
        schema_id=str(config_schema_document["$id"]),
        document=config_schema_document,
        sha256=content_sha256(config_schema_document),
    )
    job_spec, _ = build_linear_viscoelastic_job_spec(
        job_id=job_id,
        attempt_id=attempt_id,
        run_id=run_id,
        plan_revision_id=plan.plan_revision_id,
        plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
        plan_artifact_id=UUID(int=104),
        canonical_test_data_revision_id=plan.test_data.revision_id
        if plan.test_data is not None
        else UUID(int=4),
        canonical_test_data_artifact_id=UUID(int=105),
        canonical_test_data_sha256=hashlib.sha256(canonical).hexdigest(),
        normalized_test_data_revision_id=plan.test_data.revision_id
        if plan.test_data is not None
        else UUID(int=4),
        normalized_test_data_artifact_id=UUID(int=107),
        normalized_test_data_sha256=hashlib.sha256(normalized).hexdigest(),
        package_sha256=package_digest,
        recommendation_policy=plan.recommendation_policy,
        deadline=datetime.now(UTC) + timedelta(hours=1),
        traceparent=_WORKER_TRACE,
    )
    payloads = {
        "calibration.plan": plan_bytes,
        "test-data.canonical": canonical,
        "test-data.normalized": normalized,
    }
    media_types = {
        "calibration.plan": "application/json",
        "test-data.canonical": "application/vnd.cmp.test-data+json",
        "test-data.normalized": "application/vnd.apache.parquet",
    }
    artifact_ids = {
        "calibration.plan": UUID(int=104),
        "test-data.canonical": UUID(int=105),
        "test-data.normalized": UUID(int=107),
    }
    staged: list[StagedInput] = []
    for role, payload in payloads.items():
        path = tmp_path / f"{role.replace('.', '-')}.input"
        path.write_bytes(payload)
        staged.append(
            StagedInput(
                role=role,
                artifact_id=artifact_ids[role],
                sha256=hashlib.sha256(payload).hexdigest(),
                media_type=media_types[role],
                source_path=path,
                size_bytes=len(payload),
            )
        )
    package = ExecutablePluginPackage(
        package_id=UUID(int=108),
        plugin_id="cmp.linear_viscoelastic.calibrator",
        plugin_version="1.0.0",
        package_digest=package_digest,
        extension_type=ExtensionType.CALIBRATOR,
        entrypoint=entrypoint,
        capabilities=("generalized-maxwell-shear",),
        artifact_read_roles=("calibration.plan", "test-data.canonical", "test-data.normalized"),
        artifact_write_roles=("calibration.run-result", "objective-history", "response-residuals"),
        requested_cpu=2.0,
        requested_memory_mb=4096,
        requested_gpu=0,
        requested_timeout=timedelta(hours=1),
        config_schema=config_schema,
        archive_path=package_zip,
        dependency_lock_digest=lock_digest,
        active=True,
        non_production=True,
    )
    allowed_outputs = (
        AllowedOutput(
            "calibration.run-result",
            "urn:cmp:modeling:linear-viscoelastic-calibration-result:1.0.0",
            ("application/json",),
            33_554_432,
        ),
        AllowedOutput(
            "response-residuals",
            "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0",
            ("application/vnd.apache.parquet",),
            268_435_456,
        ),
        AllowedOutput(
            "objective-history",
            "urn:cmp:modeling:linear-viscoelastic-calibration-objective-history:1.0.0",
            ("application/vnd.apache.parquet",),
            134_217_728,
        ),
    )
    command = ExecutePlugin(
        job_spec=job_spec.document(),
        package=package,
        staged_inputs=tuple(staged),
        allowed_outputs=allowed_outputs,
        limits=RunnerLimits(
            cpu=2.0,
            memory_mb=4096,
            gpu=0,
            timeout=timedelta(hours=1),
            cancellation_grace=timedelta(seconds=2),
            max_total_output_bytes=436_207_616,
        ),
        sandbox=SandboxPolicy.development_subprocess(),
        output_staging_root=tmp_path / "outputs",
        production=False,
    )
    result = asyncio.run(
        PluginExecutionService(
            runner=SubprocessPluginRunner(temporary_root=tmp_path),
            validator=JsonSchemaRunnerContractValidator(),
        ).execute(command, asyncio.Event())
    )
    return result, package_digest, plan


def test_public_fixture_succeeds_through_isolated_subprocess_and_generic_manifest(
    tmp_path: Path,
) -> None:
    result, _, _ = _run_public_plugin(
        tmp_path,
        job_id=UUID(int=101),
        attempt_id=UUID(int=102),
        run_id=UUID(int=103),
    )
    assert result.status.value == "succeeded"
    assert {output.role for output in result.outputs} == {
        "calibration.run-result",
        "response-residuals",
        "objective-history",
    }
    run_result = next(
        output for output in result.outputs if output.role == "calibration.run-result"
    )
    parsed = parse_calibration_run_result(
        run_result.path.read_bytes(), expected_document_sha256=run_result.sha256
    )
    assert parsed.run_id == UUID(int=103)
    assert parsed.plan_revision_id == UUID(int=2)
    assert parsed.candidates


def test_public_fixture_commits_through_calibration_result_boundary(tmp_path: Path) -> None:
    run_id = UUID(int=103)
    job_id = UUID(int=101)
    attempt_id = UUID(int=102)
    result, package_digest, plan = _run_public_plugin(
        tmp_path,
        job_id=job_id,
        attempt_id=attempt_id,
        run_id=run_id,
    )
    assert result.status.value == "succeeded"
    canonical, normalized = _fixture_documents()
    repository = InMemoryLinearViscoelasticCalibrationRepository()
    service = LinearViscoelasticCalibrationService(
        repository=repository,
        id_factory=iter((run_id, job_id)).__next__,
        clock=lambda: _WORKER_NOW,
    )
    context = _worker_context()
    service.create_plan(
        context,
        _worker_decision(Permission.CALIBRATION_EXECUTE),
        CreateLinearViscoelasticCalibrationPlan(
            plan=plan,
            classification=DataClassification.INTERNAL,
            change_reason="fixture result boundary",
            idempotency_key="fixture-plan",
        ),
    )
    queued = service.queue_run(
        context,
        _worker_decision(Permission.CALIBRATION_EXECUTE),
        QueueLinearViscoelasticCalibrationRun(
            plan_id=plan.plan_id,
            plan_revision_id=plan.plan_revision_id,
            change_reason="fixture result boundary",
            idempotency_key="fixture-run",
        ),
    )
    assert queued.run_id == run_id
    assert queued.job_id == job_id
    claimed = _fixture_claim(
        plan=plan,
        package_sha256=package_digest,
        canonical_sha256=hashlib.sha256(canonical).hexdigest(),
        normalized_sha256=hashlib.sha256(normalized).hexdigest(),
        job_id=job_id,
        attempt_id=attempt_id,
        run_id=run_id,
    )
    artifacts = _FixtureArtifactService()
    committed = asyncio.run(
        LinearViscoelasticCalibrationResultCommitter(
            context=context,
            decision=_worker_decision(Permission.JOB_EXECUTE),
            artifact_service=artifacts,  # type: ignore[arg-type]
            calibration_service=service,
        ).commit(claimed=claimed, result=result)
    )
    assert committed.manifest_digest == result.manifest_digest
    persisted = repository.get_run(
        run_id, context=context, decision=_worker_decision(Permission.JOB_EXECUTE)
    )
    assert persisted.status == "succeeded"
    assert persisted.result is not None
    assert persisted.result.candidates
    assert len(artifacts.records) == 4
