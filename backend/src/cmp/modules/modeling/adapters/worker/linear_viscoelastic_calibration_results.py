"""Host-side commit boundary for isolated linear-viscoelastic calibration results.

The T-18 worker has already validated the generic Job/Attempt contract.  This adapter repeats
the calibration-specific identity and output checks before any bytes become durable Artifacts,
then hands the bounded JSON document to the application importer.  It deliberately has no
numerical imports and never loads plugin code.
"""

from __future__ import annotations

import hashlib
import re
import stat
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import IntegrityStatus
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.application.jobs import ClaimedAttempt
from cmp.modules.jobs.application.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_CALIBRATOR_ID,
    LINEAR_VISCOELASTIC_CALIBRATOR_VERSION,
    LINEAR_VISCOELASTIC_CONFIG_SCHEMA,
    LINEAR_VISCOELASTIC_HISTORY_SCHEMA,
    LINEAR_VISCOELASTIC_MAX_TOTAL_OUTPUT_BYTES,
    LINEAR_VISCOELASTIC_OUTPUT_CAPS,
    LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA,
    LINEAR_VISCOELASTIC_RESULT_SCHEMA,
)
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    LinearViscoelasticCalibrationService,
)
from cmp.modules.modeling.application.linear_viscoelastic_result_import import (
    parse_calibration_run_result,
)
from cmp.modules.plugins.application.worker import (
    CommittedResultManifest,
    PluginResultCommitter,
)
from cmp.modules.plugins.domain.execution import (
    InvalidResultManifest,
    ResultStatus,
    RunnerOutput,
    ValidatedPluginResult,
)
from cmp.shared.domain.revisions import canonical_json_bytes

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PLUGIN_JOB_TYPE = "plugin.run"
_RESULT_MANIFEST_SCHEMA = "urn:cmp:schema:result-manifest:1.0.0"
_JSON_MEDIA_TYPE = "application/json"
_PARQUET_MEDIA_TYPE = "application/vnd.apache.parquet"
_RESULT_MANIFEST_ROLE = "calibration.result-manifest"
_EXPECTED_OUTPUTS: dict[str, tuple[str, str, int]] = {
    "calibration.run-result": (
        LINEAR_VISCOELASTIC_RESULT_SCHEMA,
        _JSON_MEDIA_TYPE,
        LINEAR_VISCOELASTIC_OUTPUT_CAPS["calibration.run-result"],
    ),
    "response-residuals": (
        LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA,
        _PARQUET_MEDIA_TYPE,
        LINEAR_VISCOELASTIC_OUTPUT_CAPS["response-residuals"],
    ),
    "objective-history": (
        LINEAR_VISCOELASTIC_HISTORY_SCHEMA,
        _PARQUET_MEDIA_TYPE,
        LINEAR_VISCOELASTIC_OUTPUT_CAPS["objective-history"],
    ),
}


def _invalid(detail: str) -> InvalidResultManifest:
    return InvalidResultManifest(detail)


def _object(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _invalid(f"{name} must be an object")
    return cast(Mapping[str, object], value)


def _uuid(value: object, name: str) -> UUID:
    if not isinstance(value, str):
        raise _invalid(f"{name} must be a UUID string")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise _invalid(f"{name} must be a concrete UUID") from error
    if parsed.int == 0:
        raise _invalid(f"{name} must be non-zero")
    return parsed


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise _invalid(f"{name} must be a lowercase SHA-256 digest")
    return value


def _digest_ref(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise _invalid(f"{name} must be a sha256 digest reference")
    return _digest(value.removeprefix("sha256:"), name)


async def _path_chunks(path: Path) -> AsyncIterator[bytes]:
    """Yield staged output bytes in bounded chunks for ArtifactService."""

    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            yield chunk


async def _bytes_chunks(value: bytes) -> AsyncIterator[bytes]:
    yield value


class LinearViscoelasticCalibrationResultCommitter(PluginResultCommitter):
    """Validate and commit one claimed isolated calibrator result."""

    def __init__(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_service: ArtifactService,
        calibration_service: LinearViscoelasticCalibrationService,
    ) -> None:
        self._context = context
        self._decision = decision
        self._artifacts = artifact_service
        self._calibration = calibration_service

    def _validate_scope(self, claimed: ClaimedAttempt) -> None:
        job = claimed.job
        if self._decision.permission is not Permission.JOB_EXECUTE:
            raise _invalid("calibration result requires a JOB_EXECUTE decision")
        if (
            self._decision.principal_id != self._context.principal.id
            or self._decision.organization_id != self._context.organization_id
            or self._decision.project_id != self._context.project_id
            or self._decision.request_id != self._context.request_id
            or self._decision.trace_id != self._context.trace_id
        ):
            raise _invalid("worker authorization decision differs from its security context")
        if (
            job.organization_id != self._context.organization_id
            or job.project_id != self._context.project_id
            or not self._decision.allows(
                job.organization_id, job.project_id, job.classification
            )
        ):
            raise _invalid("claimed Job tenant or classification is outside the worker scope")
        if job.job_type != _PLUGIN_JOB_TYPE:
            raise _invalid("claimed Job is not the plugin.run contract")
        if claimed.attempt.job_id != job.id or job.current_attempt_id != claimed.attempt.id:
            raise _invalid("claimed Attempt does not belong to the current Job")
        if (
            claimed.attempt.spec.job_id != job.id
            or claimed.attempt.spec.attempt_id != claimed.attempt.id
        ):
            raise _invalid("claimed Job Spec identity differs from the Job and Attempt")

    def _validate_spec(self, claimed: ClaimedAttempt) -> tuple[UUID, UUID, str, dict[str, Any]]:
        document = claimed.attempt.spec.document()
        if document.get("job_spec_version") != "1.0":
            raise _invalid("calibration Job Spec version is invalid")
        if document.get("job_id") != str(claimed.job.id):
            raise _invalid("calibration Job Spec job identity differs from the claim")
        if document.get("attempt_id") != str(claimed.attempt.id):
            raise _invalid("calibration Job Spec Attempt identity differs from the claim")
        if document.get("operation") != "execute_plan":
            raise _invalid("calibration Job Spec operation must be execute_plan")

        extension = _object(document.get("extension"), "Job Spec extension")
        if extension.get("type") != "calibrator":
            raise _invalid("Job Spec extension type is not the calibrator")
        if extension.get("plugin_id") != LINEAR_VISCOELASTIC_CALIBRATOR_ID:
            raise _invalid("Job Spec plugin identity is not the linear-viscoelastic calibrator")
        if extension.get("plugin_version") != LINEAR_VISCOELASTIC_CALIBRATOR_VERSION:
            raise _invalid("Job Spec plugin version is not the approved calibrator version")
        package_sha256 = _digest_ref(extension.get("package_digest"), "package_digest")

        config_schema = document.get("config_schema_ref")
        if config_schema != LINEAR_VISCOELASTIC_CONFIG_SCHEMA:
            raise _invalid("calibration Job Spec config schema is invalid")
        config = dict(_object(document.get("config"), "Job Spec config"))
        if config.get("schema_version") != "1.0.0" or config.get("seed_status") != "not_applicable":
            raise _invalid("calibration Job Spec config version or seed status is invalid")
        run_id = _uuid(config.get("run_id"), "config.run_id")
        plan_revision_id = _uuid(config.get("plan_revision_id"), "config.plan_revision_id")
        plan_sha256 = _digest(config.get("plan_sha256"), "config.plan_sha256")

        expected = document.get("expected_outputs")
        if not isinstance(expected, list) or len(expected) != len(_EXPECTED_OUTPUTS):
            raise _invalid("calibration Job Spec must declare exactly three outputs")
        observed: dict[str, object] = {}
        for item in expected:
            value = _object(item, "Job Spec expected output")
            role = value.get("role")
            schema_ref = value.get("schema_ref")
            if not isinstance(role, str) or role in observed:
                raise _invalid("Job Spec output roles must be unique")
            observed[role] = schema_ref
        if set(observed) != set(_EXPECTED_OUTPUTS) or any(
            observed[role] != contract[0] for role, contract in _EXPECTED_OUTPUTS.items()
        ):
            raise _invalid("Job Spec output roles or schemas differ from the calibrator contract")
        return run_id, plan_revision_id, package_sha256, {
            "config": config,
            "plan_sha256": plan_sha256,
        }

    @staticmethod
    def _validate_manifest(
        result: ValidatedPluginResult,
        claimed: ClaimedAttempt,
        package_sha256: str,
    ) -> bytes:
        if result.status is not ResultStatus.SUCCEEDED:
            raise _invalid("calibration result committer accepts only a succeeded result")
        manifest = _object(result.manifest, "Result Manifest")
        if manifest.get("result_manifest_version") != "1.0":
            raise _invalid("Result Manifest version is invalid")
        if manifest.get("job_id") != str(claimed.job.id) or manifest.get("attempt_id") != str(
            claimed.attempt.id
        ):
            raise _invalid("Result Manifest Job or Attempt identity differs from the claim")
        if (
            manifest.get("status") != result.status.value
            or manifest.get("non_production") is not True
        ):
            raise _invalid("Result Manifest status or execution mode is invalid")
        reproducibility = _object(
            manifest.get("reproducibility"), "Result Manifest reproducibility"
        )
        if reproducibility.get("package_digest") != f"sha256:{package_sha256}":
            raise _invalid("Result Manifest package digest differs from the Job Spec")
        try:
            canonical = canonical_json_bytes(manifest)
        except (TypeError, ValueError) as error:
            raise _invalid("Result Manifest is not canonical JSON") from error
        if hashlib.sha256(canonical).hexdigest() != result.manifest_digest:
            raise _invalid("Result Manifest digest differs from its canonical bytes")
        return canonical

    @staticmethod
    async def _read_output(output: RunnerOutput, cap: int) -> bytes | None:
        if output.size_bytes < 1 or output.size_bytes > cap:
            raise _invalid("calibration output exceeds its role size cap")
        path = Path(output.path)
        try:
            file_stat = path.lstat()
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or path.is_symlink()
                or file_stat.st_size != output.size_bytes
            ):
                raise _invalid("calibration output staging file differs from its declaration")
            digest = hashlib.sha256()
            observed = 0
            collected = bytearray() if output.role == "calibration.run-result" else None
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    observed += len(chunk)
                    if observed > cap:
                        raise _invalid("calibration output exceeds its role size cap")
                    digest.update(chunk)
                    if collected is not None:
                        collected.extend(chunk)
            if observed != output.size_bytes or digest.hexdigest() != output.sha256:
                raise _invalid("calibration output bytes differ from the staged digest")
            if not output.staged_artifact.endswith(output.sha256):
                raise _invalid("calibration staged output reference has the wrong digest")
            return bytes(collected) if collected is not None else None
        except InvalidResultManifest:
            raise
        except (OSError, ValueError) as error:
            raise _invalid("calibration output staging file cannot be read") from error

    @staticmethod
    def _validate_output_manifest(
        result: ValidatedPluginResult,
    ) -> dict[str, RunnerOutput]:
        if len(result.outputs) != len(_EXPECTED_OUTPUTS):
            raise _invalid("calibration result must contain exactly three outputs")
        by_role: dict[str, RunnerOutput] = {}
        for output in result.outputs:
            if output.role in by_role or output.role not in _EXPECTED_OUTPUTS:
                raise _invalid("calibration result output roles are not exact")
            schema_ref, media_type, cap = _EXPECTED_OUTPUTS[output.role]
            if output.schema_ref != schema_ref or output.media_type != media_type:
                raise _invalid("calibration result output schema or media type is invalid")
            if output.size_bytes > cap:
                raise _invalid("calibration result output exceeds its role size cap")
            by_role[output.role] = output
        if set(by_role) != set(_EXPECTED_OUTPUTS):
            raise _invalid("calibration result is missing an expected output role")

        raw_outputs = result.manifest.get("outputs")
        if not isinstance(raw_outputs, list) or len(raw_outputs) != len(_EXPECTED_OUTPUTS):
            raise _invalid("Result Manifest must contain exactly three outputs")
        manifest_by_role: dict[str, Mapping[str, object]] = {}
        for raw in raw_outputs:
            item = _object(raw, "Result Manifest output")
            role = item.get("role")
            if not isinstance(role, str) or role in manifest_by_role:
                raise _invalid("Result Manifest output roles are not exact")
            manifest_by_role[role] = item
        if set(manifest_by_role) != set(by_role):
            raise _invalid("Result Manifest output roles differ from staged outputs")
        for role, output in by_role.items():
            item = manifest_by_role[role]
            if (
                item.get("media_type") != output.media_type
                or item.get("schema_ref") != output.schema_ref
                or item.get("staged_artifact") != output.staged_artifact
                or item.get("sha256") != output.sha256
                or item.get("size_bytes") != output.size_bytes
            ):
                raise _invalid("Result Manifest output differs from staged output")
        return by_role

    async def _finalize(
        self,
        claimed: ClaimedAttempt,
        *,
        role: str,
        schema_ref: str,
        media_type: str,
        path: Path | None = None,
        value: bytes | None = None,
        sha256: str,
        size_bytes: int,
        idempotency_key: str,
    ) -> Any:
        if (path is None) == (value is None):
            raise _invalid("Artifact finalization requires exactly one source")
        chunks = _path_chunks(path) if path is not None else _bytes_chunks(cast(bytes, value))
        record = await self._artifacts.finalize_derived_stream(
            self._context,
            self._decision,
            classification=claimed.job.classification,
            artifact_role=role,
            schema_ref=schema_ref,
            media_type=media_type,
            chunks=chunks,
            expected_sha256=sha256,
            expected_size_bytes=size_bytes,
            idempotency_key=idempotency_key,
        )
        artifact = getattr(record, "artifact", None)
        artifact_id = getattr(artifact, "id", None)
        if (
            getattr(record, "integrity_status", None) is not IntegrityStatus.VERIFIED
            or artifact is None
            or not isinstance(artifact_id, UUID)
            or artifact_id.int == 0
            or getattr(artifact, "organization_id", None) != self._context.organization_id
            or getattr(artifact, "project_id", None) != self._context.project_id
            or getattr(artifact, "classification", None) != claimed.job.classification
            or getattr(artifact, "artifact_role", None) != role
            or getattr(artifact, "schema_ref", None) != schema_ref
            or getattr(artifact, "media_type", None) != media_type
            or getattr(artifact, "size_bytes", None) != size_bytes
            or getattr(artifact, "sha256", None) != sha256
        ):
            raise _invalid("ArtifactService returned an unverifiable calibration Artifact")
        return artifact

    async def commit(
        self,
        *,
        claimed: ClaimedAttempt,
        result: ValidatedPluginResult,
    ) -> CommittedResultManifest:
        self._validate_scope(claimed)
        run_id, plan_revision_id, package_sha256, _ = self._validate_spec(claimed)
        manifest_bytes = self._validate_manifest(result, claimed, package_sha256)
        outputs = self._validate_output_manifest(result)

        total = 0
        run_result_bytes: bytes | None = None
        for role, output in outputs.items():
            cap = _EXPECTED_OUTPUTS[role][2]
            path = Path(output.path)
            value = await self._read_output(output, cap)
            total += output.size_bytes
            if total > LINEAR_VISCOELASTIC_MAX_TOTAL_OUTPUT_BYTES:
                raise _invalid("calibration outputs exceed the total size cap")
            if role == "calibration.run-result":
                run_result_bytes = value
            if path.is_symlink():
                raise _invalid("calibration output staging path must not be a symlink")
        if run_result_bytes is None:
            raise _invalid("calibration run-result output is missing")
        try:
            parsed = parse_calibration_run_result(
                run_result_bytes,
                expected_document_sha256=outputs["calibration.run-result"].sha256,
            )
        except InvalidResultManifest:
            raise
        if parsed.run_id != run_id or parsed.plan_revision_id != plan_revision_id:
            raise _invalid("calibration run-result does not pin the Job Spec Run and Plan")

        artifact_ids: dict[str, UUID] = {}
        for role, output in outputs.items():
            artifact = await self._finalize(
                claimed,
                role=role,
                schema_ref=output.schema_ref,
                media_type=output.media_type,
                path=Path(output.path),
                sha256=output.sha256,
                size_bytes=output.size_bytes,
                idempotency_key=(
                    f"linear-viscoelastic-calibration:{claimed.job.id}:{claimed.attempt.id}:output:{role}"
                ),
            )
            artifact_ids[role] = artifact.id

        manifest_artifact = await self._finalize(
            claimed,
            role=_RESULT_MANIFEST_ROLE,
            schema_ref=_RESULT_MANIFEST_SCHEMA,
            media_type=_JSON_MEDIA_TYPE,
            value=manifest_bytes,
            sha256=result.manifest_digest,
            size_bytes=len(manifest_bytes),
            idempotency_key=(
                f"linear-viscoelastic-calibration:{claimed.job.id}:{claimed.attempt.id}:manifest"
            ),
        )
        self._calibration.import_validated_result(
            self._context,
            self._decision,
            run_id=run_id,
            job_id=claimed.job.id,
            attempt_id=claimed.attempt.id,
            job_attempt_no=claimed.attempt.attempt_no,
            package_sha256=package_sha256,
            result=run_result_bytes,
            result_digest=parsed.digest,
            result_sha256=outputs["calibration.run-result"].sha256,
            result_manifest_artifact_id=manifest_artifact.id,
            result_manifest_sha256=result.manifest_digest,
            response_residual_artifact_id=artifact_ids["response-residuals"],
            objective_history_artifact_id=artifact_ids["objective-history"],
            submitted_at=claimed.job.submitted_at,
            deadline_at=claimed.job.deadline,
        )
        return CommittedResultManifest(manifest_artifact.id, result.manifest_digest)


__all__ = ["LinearViscoelasticCalibrationResultCommitter"]
