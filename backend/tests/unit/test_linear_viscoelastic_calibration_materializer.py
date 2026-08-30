from __future__ import annotations

import asyncio
import hashlib
import io
import json
import stat
import zipfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactKind,
    ArtifactRecord,
    IntegrityStatus,
    content_object_key,
)
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
    LINEAR_VISCOELASTIC_CALIBRATOR_ID,
    LINEAR_VISCOELASTIC_CALIBRATOR_VERSION,
    LINEAR_VISCOELASTIC_CONFIG_SCHEMA,
    LINEAR_VISCOELASTIC_HISTORY_SCHEMA,
    LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA,
    LINEAR_VISCOELASTIC_RESULT_SCHEMA,
    build_linear_viscoelastic_job_spec,
)
from cmp.modules.jobs.domain.jobs import (
    AttemptRecord,
    AttemptState,
    ImmutableJobSpec,
    JobRecord,
    JobState,
    RetryKind,
)
from cmp.modules.modeling.adapters.worker.linear_viscoelastic_calibration_materializer import (
    LinearViscoelasticCalibrationMaterializer,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
)
from cmp.modules.plugins.domain.execution import InvalidExecutionRequest, PackageIntegrityError
from cmp.modules.plugins.domain.registry import (
    ActivationRecord,
    ArtifactReference,
    ExtensionType,
    ImmutablePluginManifest,
    PackageRecord,
    PackageState,
    SchemaDocument,
    SchemaRole,
)
from cmp.shared.domain.revisions import content_sha256

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
ORG = UUID(int=10)
PROJECT = UUID(int=11)
ACTOR = UUID(int=12)
JOB = UUID(int=13)
ATTEMPT = UUID(int=14)
RUN = UUID(int=15)
PLAN_REVISION = UUID(int=16)
PLAN_ARTIFACT = UUID(int=17)
CANONICAL_ARTIFACT = UUID(int=18)
NORMALIZED_ARTIFACT = UUID(int=19)
PACKAGE_ARTIFACT = UUID(int=20)
TRACE = "00-0000000000000000000000000000000a-000000000000000a-01"


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
        request_id=UUID(int=21),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=Permission.ARTIFACT_READ,
        roles=(Role.JOB_RUNNER,),
        database_permissions=database_permissions_for(Permission.ARTIFACT_READ),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _schema_document(schema_id: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        "type": "object",
        "additionalProperties": False,
    }


def _package(
    tmp_path: Path, *, entries: tuple[tuple[str, bytes], ...] | None = None
) -> tuple[PackageRecord, bytes, str]:
    package_entries = entries or (
        ("dependency.lock", b"numpy==2.2.6\n"),
        ("linear_viscoelastic_calibrator/plugin.py", b"# never imported by the host\n"),
    )
    package_stream = io.BytesIO()
    with zipfile.ZipFile(package_stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, value in package_entries:
            archive.writestr(name, value)
    package_bytes = package_stream.getvalue()
    package_sha256 = hashlib.sha256(package_bytes).hexdigest()
    manifest_document = {
        "manifest_version": "1.0",
        "plugin_id": LINEAR_VISCOELASTIC_CALIBRATOR_ID,
        "display_name": "Linear Viscoelastic Calibrator",
        "plugin_version": LINEAR_VISCOELASTIC_CALIBRATOR_VERSION,
        "package_digest": f"sha256:{package_sha256}",
        "contract_api": ">=1.0 <2.0",
        "extensions": [
            {
                "type": ExtensionType.CALIBRATOR.value,
                "entrypoint": "linear_viscoelastic_calibrator.plugin:LinearViscoelasticCalibrator",
                "capabilities": ["generalized-maxwell-shear"],
            }
        ],
        "permissions": {
            "network": "none",
            "artifact_read_roles": [
                "calibration.plan",
                "test-data.canonical",
                "test-data.normalized",
            ],
            "artifact_write_roles": [
                "calibration.run-result",
                "objective-history",
                "response-residuals",
            ],
        },
        "resources": {"cpu": 2.0, "memory_mb": 4096, "gpu": 0, "timeout_s": 3600},
        "non_production": True,
    }
    manifest = ImmutablePluginManifest.from_validated_document(manifest_document)
    schema_specs = (
        (LINEAR_VISCOELASTIC_CONFIG_SCHEMA, SchemaRole.CONFIG),
        (LINEAR_VISCOELASTIC_RESULT_SCHEMA, SchemaRole.OUTPUT),
        (LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA, SchemaRole.EVIDENCE),
        (LINEAR_VISCOELASTIC_HISTORY_SCHEMA, SchemaRole.EVIDENCE),
    )
    schemas = tuple(
        SchemaDocument.from_validated_document(
            schema_id=schema_id,
            extension_ordinal=1,
            role=role,
            document=_schema_document(schema_id),
            expected_sha256=content_sha256(_schema_document(schema_id)),
        )
        for schema_id, role in schema_specs
    )
    package = PackageRecord(
        id=UUID(int=22),
        definition_id=UUID(int=23),
        organization_id=ORG,
        project_id=PROJECT,
        classification=DataClassification.INTERNAL,
        manifest=manifest,
        package_artifact=ArtifactReference(
            PACKAGE_ARTIFACT,
            package_sha256,
            len(package_bytes),
            "application/zip",
        ),
        signature_artifact=ArtifactReference(UUID(int=24), "b" * 64, 1, "application/json"),
        sbom_artifact=ArtifactReference(UUID(int=25), "c" * 64, 1, "application/json"),
        schemas=schemas,
        state=PackageState.ELIGIBLE,
        state_events=(),
        submitted_at=NOW,
        submitted_by=ACTOR,
        submission_request_id=UUID(int=26),
        submission_trace_id=TRACE,
        activation=ActivationRecord(
            UUID(int=27), UUID(int=22), NOW, ACTOR, "test", UUID(int=28), TRACE
        ),
    )
    return package, package_bytes, hashlib.sha256(b"numpy==2.2.6\n").hexdigest()


def _artifact_record(
    artifact_id: UUID,
    value: bytes,
    *,
    role: str,
    media_type: str,
    organization_id: UUID = ORG,
    project_id: UUID = PROJECT,
) -> ArtifactRecord:
    digest = hashlib.sha256(value).hexdigest()
    artifact = Artifact(
        id=artifact_id,
        organization_id=organization_id,
        project_id=project_id,
        classification=DataClassification.INTERNAL,
        artifact_kind=ArtifactKind.DERIVED,
        artifact_role=role,
        schema_ref="urn:cmp:test:artifact:1.0.0",
        media_type=media_type,
        size_bytes=len(value),
        sha256=digest,
        storage_key=content_object_key(ORG, PROJECT, DataClassification.INTERNAL, digest),
        encryption_profile="test",
        source_raw_asset_id=None,
        source_pending_id=UUID(int=29 + artifact_id.int),
        created_at=NOW,
        created_by=ACTOR,
    )
    return ArtifactRecord(artifact, IntegrityStatus.VERIFIED, NOW, UUID(int=100 + artifact_id.int))


class _ArtifactReader:
    def __init__(self, values: dict[UUID, tuple[ArtifactRecord, bytes]]) -> None:
        self.values = values
        self.calls: list[UUID] = []

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]:
        assert context.organization_id == ORG
        assert decision.permission is Permission.ARTIFACT_READ
        assert maximum_bytes > 0
        self.calls.append(artifact_id)
        return self.values[artifact_id]

    async def stream_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, Any]:
        assert context.organization_id == ORG
        assert decision.permission is Permission.ARTIFACT_READ
        assert maximum_bytes > 0
        self.calls.append(artifact_id)
        record, value = self.values[artifact_id]

        async def chunks() -> Any:
            for offset in range(0, len(value), 3):
                yield value[offset : offset + 3]

        return record, chunks()


def _claim(
    package_sha256: str, *, package: PackageRecord
) -> tuple[ClaimedAttempt, dict[str, Any], dict[UUID, tuple[ArtifactRecord, bytes]]]:
    plan_bytes = b'{"plan":"exact"}'
    canonical_bytes = b'{"canonical":"exact"}'
    normalized_bytes = b"PARQUET-CANONICAL"
    plan_sha256 = hashlib.sha256(plan_bytes).hexdigest()
    canonical_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
    normalized_sha256 = hashlib.sha256(normalized_bytes).hexdigest()
    spec, policy = build_linear_viscoelastic_job_spec(
        job_id=JOB,
        attempt_id=ATTEMPT,
        run_id=RUN,
        plan_revision_id=PLAN_REVISION,
        plan_sha256=plan_sha256,
        plan_artifact_id=PLAN_ARTIFACT,
        canonical_test_data_revision_id=UUID(int=30),
        canonical_test_data_artifact_id=CANONICAL_ARTIFACT,
        canonical_test_data_sha256=canonical_sha256,
        normalized_test_data_revision_id=UUID(int=30),
        normalized_test_data_artifact_id=NORMALIZED_ARTIFACT,
        normalized_test_data_sha256=normalized_sha256,
        package_sha256=package_sha256,
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        deadline=NOW + timedelta(hours=1),
        traceparent=TRACE,
    )
    job = JobRecord(
        id=JOB,
        organization_id=ORG,
        project_id=PROJECT,
        classification=DataClassification.INTERNAL,
        job_type="plugin.run",
        state=JobState.RUNNING,
        priority=0,
        submitted_at=NOW,
        submitted_by=ACTOR,
        request_id=UUID(int=31),
        trace_id=TRACE,
        deadline=spec.deadline,
        resource_policy=policy,
        attempt_count=1,
        current_attempt_id=ATTEMPT,
        result_manifest_id=None,
        result_manifest_digest=None,
        failure=None,
        cancel_requested_at=None,
        updated_at=NOW,
    )
    attempt = AttemptRecord(
        id=ATTEMPT,
        job_id=JOB,
        attempt_no=1,
        state=AttemptState.RUNNING,
        retry_kind=RetryKind.INITIAL,
        retry_reason="initial submission",
        spec=spec,
        runner_id=UUID(int=32),
        lease_token=UUID(int=33),
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
    values = {
        package.package_artifact.artifact_id: (
            _artifact_record(
                PACKAGE_ARTIFACT,
                b"package-placeholder",
                role="plugin.package",
                media_type="application/zip",
            ),
            b"package-placeholder",
        ),
        PLAN_ARTIFACT: (
            _artifact_record(
                PLAN_ARTIFACT, plan_bytes, role="calibration.plan", media_type="application/json"
            ),
            plan_bytes,
        ),
        CANONICAL_ARTIFACT: (
            _artifact_record(
                CANONICAL_ARTIFACT,
                canonical_bytes,
                role="test-data.canonical-json",
                media_type="application/vnd.cmp.test-data+json",
            ),
            canonical_bytes,
        ),
        NORMALIZED_ARTIFACT: (
            _artifact_record(
                NORMALIZED_ARTIFACT,
                normalized_bytes,
                role="test-data.normalized-parquet",
                media_type="application/vnd.apache.parquet",
            ),
            normalized_bytes,
        ),
    }
    return ClaimedAttempt(job, attempt), spec.document(), values


def _setup(
    tmp_path: Path,
    *,
    entries: tuple[tuple[str, bytes], ...] | None = None,
) -> tuple[
    LinearViscoelasticCalibrationMaterializer,
    PackageRecord,
    ClaimedAttempt,
    dict[str, Any],
    _ArtifactReader,
    str,
]:
    package, package_bytes, lock_digest = _package(tmp_path, entries=entries)
    # The package Artifact bytes are replaced with the deterministic archive bytes after the
    # PackageRecord is built so the fake remains an authoritative content-addressed reader.
    package_sha256 = hashlib.sha256(package_bytes).hexdigest()
    claim, document, values = _claim(package_sha256, package=package)
    values[PACKAGE_ARTIFACT] = (
        _artifact_record(
            PACKAGE_ARTIFACT,
            package_bytes,
            role="plugin.package",
            media_type="application/zip",
        ),
        package_bytes,
    )
    context = _context()
    reader = _ArtifactReader(values)
    materializer = LinearViscoelasticCalibrationMaterializer(
        context=context,
        decision=_decision(context),
        artifact_service=reader,  # type: ignore[arg-type]
        temporary_parent=tmp_path,
    )
    return materializer, package, claim, document, reader, lock_digest


def test_materializes_exact_package_inputs_and_runner_allowlist(tmp_path: Path) -> None:
    materializer, package, claim, document, reader, lock_digest = _setup(tmp_path)

    result = asyncio.run(
        materializer.materialize(
            claimed=claim,
            package=package,
            extension_ordinal=1,
            job_spec=document,
        )
    )

    root = result.archive_path.parent
    assert result.dependency_lock_digest == lock_digest
    assert result.archive_path.is_file()
    assert result.output_staging_root.parent == root
    assert not result.output_staging_root.exists()
    assert {item.role for item in result.staged_inputs} == {
        "calibration.plan",
        "test-data.canonical",
        "test-data.normalized",
    }
    assert tuple(item.max_bytes for item in result.allowed_outputs) == (
        33_554_432,
        268_435_456,
        134_217_728,
    )
    assert {path.name for path in root.iterdir()} == {"package.zip", "inputs"}
    assert {path.name for path in (root / "inputs").iterdir()} == {
        f"{PLAN_ARTIFACT}.input",
        f"{CANONICAL_ARTIFACT}.input",
        f"{NORMALIZED_ARTIFACT}.input",
    }
    assert reader.calls == [
        PACKAGE_ARTIFACT,
        PLAN_ARTIFACT,
        CANONICAL_ARTIFACT,
        NORMALIZED_ARTIFACT,
    ]
    assert all(
        not path.is_symlink() and stat.S_ISREG(path.stat().st_mode)
        for path in root.rglob("*")
        if path.is_file()
    )

    materializer.cleanup(result)
    assert not root.exists()


def test_cleanup_all_removes_attempt_root_when_runner_does_not_return_normally(
    tmp_path: Path,
) -> None:
    materializer, package, claim, document, _reader, _lock_digest = _setup(tmp_path)
    result = asyncio.run(
        materializer.materialize(
            claimed=claim,
            package=package,
            extension_ordinal=1,
            job_spec=document,
        )
    )
    root = result.archive_path.parent
    assert root.exists()

    materializer.cleanup_all()

    assert not root.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", ("digest", "tenant", "role"))
def test_rejects_authoritative_input_mismatch_before_leaking_files(
    tmp_path: Path, failure: str
) -> None:
    materializer, package, claim, document, reader, _lock_digest = _setup(tmp_path)
    artifact_id = CANONICAL_ARTIFACT
    record, value = reader.values[artifact_id]
    if failure == "digest":
        wrong = replace(
            record.artifact,
            sha256="f" * 64,
            storage_key=content_object_key(ORG, PROJECT, DataClassification.INTERNAL, "f" * 64),
        )
        reader.values[artifact_id] = (replace(record, artifact=wrong), value)
    elif failure == "tenant":
        wrong = replace(
            record.artifact,
            project_id=UUID(int=999),
            storage_key=content_object_key(
                ORG, UUID(int=999), DataClassification.INTERNAL, record.artifact.sha256
            ),
        )
        reader.values[artifact_id] = (replace(record, artifact=wrong), value)
    else:
        wrong = replace(record.artifact, artifact_role="test-data.canonical")
        reader.values[artifact_id] = (replace(record, artifact=wrong), value)

    with pytest.raises(PackageIntegrityError, match="Artifact"):
        asyncio.run(
            materializer.materialize(
                claimed=claim,
                package=package,
                extension_ordinal=1,
                job_spec=document,
            )
        )
    assert list(tmp_path.iterdir()) == []


def test_rejects_missing_registered_schema_and_does_not_read_artifacts(tmp_path: Path) -> None:
    materializer, package, claim, document, reader, _lock_digest = _setup(tmp_path)
    package = replace(package, schemas=package.schemas[:-1])

    with pytest.raises(InvalidExecutionRequest, match="four calibrator schemas"):
        asyncio.run(
            materializer.materialize(
                claimed=claim,
                package=package,
                extension_ordinal=1,
                job_spec=document,
            )
        )
    assert reader.calls == []
    assert list(tmp_path.iterdir()) == []


def test_rejects_evidence_schema_advertised_as_output(tmp_path: Path) -> None:
    materializer, package, claim, document, reader, _lock_digest = _setup(tmp_path)
    package = replace(
        package,
        schemas=tuple(
            replace(schema, role=SchemaRole.OUTPUT)
            if schema.schema_id == LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA
            else schema
            for schema in package.schemas
        ),
    )

    with pytest.raises(InvalidExecutionRequest, match="schema roles or identities"):
        asyncio.run(
            materializer.materialize(
                claimed=claim,
                package=package,
                extension_ordinal=1,
                job_spec=document,
            )
        )
    assert reader.calls == []
    assert list(tmp_path.iterdir()) == []


def test_rejects_zip_traversal_and_cleans_only_owned_attempt_root(tmp_path: Path) -> None:
    materializer, package, claim, document, reader, _lock_digest = _setup(
        tmp_path,
        entries=(
            ("dependency.lock", b"numpy==2.2.6\n"),
            ("../credentials", b"must never be extracted"),
        ),
    )

    with pytest.raises(PackageIntegrityError, match="unsafe path"):
        asyncio.run(
            materializer.materialize(
                claimed=claim,
                package=package,
                extension_ordinal=1,
                job_spec=document,
            )
        )
    assert list(tmp_path.iterdir()) == []
    assert reader.calls == [PACKAGE_ARTIFACT]


def test_rejects_nonzero_seed_and_foreign_cleanup_path(tmp_path: Path) -> None:
    materializer, package, claim, document, reader, _lock_digest = _setup(tmp_path)
    malformed = json.loads(json.dumps(document))
    malformed["execution"]["seed"] = 1
    malformed_spec = ImmutableJobSpec.from_validated_document(malformed)
    claim = replace(claim, attempt=replace(claim.attempt, spec=malformed_spec))

    with pytest.raises(InvalidExecutionRequest, match="execution policy"):
        asyncio.run(
            materializer.materialize(
                claimed=claim,
                package=package,
                extension_ordinal=1,
                job_spec=malformed,
            )
        )
    assert reader.calls == []
    assert list(tmp_path.iterdir()) == []
