"""Attempt-scoped materialization for the linear-viscoelastic T-18 plugin.

This adapter is deliberately a byte boundary, not a plugin loader.  The registry owns the
immutable package and schema records; the ArtifactService owns authorization and content
integrity.  Here we bind those records to one claimed ``plugin.run`` attempt and create only
the files the isolated runner is allowed to see.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import tempfile
import zipfile
from collections.abc import AsyncIterable, Mapping
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple, cast
from uuid import UUID

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import IntegrityStatus
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.application.jobs import ClaimedAttempt
from cmp.modules.jobs.application.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_CALIBRATOR_ID,
    LINEAR_VISCOELASTIC_CALIBRATOR_VERSION,
    LINEAR_VISCOELASTIC_CONFIG_SCHEMA,
    LINEAR_VISCOELASTIC_HISTORY_SCHEMA,
    LINEAR_VISCOELASTIC_OUTPUT_CAPS,
    LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA,
    LINEAR_VISCOELASTIC_RESULT_SCHEMA,
    linear_viscoelastic_resource_policy,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
)
from cmp.modules.plugins.application.planning import (
    ExecutionMaterialization,
    PluginExecutionMaterializer,
)
from cmp.modules.plugins.domain.execution import (
    AllowedOutput,
    InvalidExecutionRequest,
    PackageIntegrityError,
    StagedInput,
)
from cmp.modules.plugins.domain.registry import (
    ExtensionType,
    PackageRecord,
    SchemaRole,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PLUGIN_JOB_TYPE = "plugin.run"
_ZIP_MEDIA_TYPE = "application/zip"
_JSON_MEDIA_TYPE = "application/json"
_PARQUET_MEDIA_TYPE = "application/vnd.apache.parquet"
_MAX_ARTIFACT_READ_BYTES = 268_435_456


class _InputArtifactContract(NamedTuple):
    """Persisted Artifact facts for one plugin-facing input role."""

    media_type: str
    persisted_role: str


_EXPECTED_INPUTS: dict[str, _InputArtifactContract] = {
    "calibration.plan": _InputArtifactContract(_JSON_MEDIA_TYPE, "calibration.plan"),
    "test-data.canonical": _InputArtifactContract(
        "application/vnd.cmp.test-data+json", "test-data.canonical-json"
    ),
    "test-data.normalized": _InputArtifactContract(
        _PARQUET_MEDIA_TYPE, "test-data.normalized-parquet"
    ),
    "processing-output.metadata": _InputArtifactContract(
        "application/vnd.cmp.processing-output+json", "processing.common-output-json"
    ),
    "processing-output.result": _InputArtifactContract(
        _PARQUET_MEDIA_TYPE, "processing.dma-result-parquet"
    ),
}
_REQUIRED_INPUT_ROLES = {
    "calibration.plan",
    "test-data.canonical",
    "test-data.normalized",
}
_EXPECTED_OUTPUTS: dict[str, tuple[str, tuple[str, ...], int]] = {
    "calibration.run-result": (
        LINEAR_VISCOELASTIC_RESULT_SCHEMA,
        (_JSON_MEDIA_TYPE,),
        LINEAR_VISCOELASTIC_OUTPUT_CAPS["calibration.run-result"],
    ),
    "response-residuals": (
        LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA,
        (_PARQUET_MEDIA_TYPE,),
        LINEAR_VISCOELASTIC_OUTPUT_CAPS["response-residuals"],
    ),
    "objective-history": (
        LINEAR_VISCOELASTIC_HISTORY_SCHEMA,
        (_PARQUET_MEDIA_TYPE,),
        LINEAR_VISCOELASTIC_OUTPUT_CAPS["objective-history"],
    ),
}


def _invalid(detail: str) -> InvalidExecutionRequest:
    return InvalidExecutionRequest(detail)


def _integrity(detail: str) -> PackageIntegrityError:
    return PackageIntegrityError(detail)


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


def _timestamp(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise _invalid(f"{name} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _invalid(f"{name} must be an RFC3339 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _invalid(f"{name} must be timezone-aware")
    return parsed


def _safe_archive_path(name: str) -> PurePosixPath:
    """Apply the same no-traversal ZIP policy as the isolated runner."""

    if "\\" in name or "\x00" in name or re.match(r"^[A-Za-z]:", name):
        raise _integrity("plugin package archive entry has an unsafe path")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise _integrity("plugin package archive entry has an unsafe path")
    return path


def _zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_IFMT(mode) == stat.S_IFLNK


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_bytes(path: Path, value: bytes) -> None:
    """Write a fetched Artifact through bounded chunks without following a link."""

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o400)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            view = memoryview(value)
            for offset in range(0, len(view), 1024 * 1024):
                stream.write(view[offset : offset + 1024 * 1024])
    finally:
        os.close(descriptor)
    try:
        path.chmod(stat.S_IREAD)
    except OSError:
        pass


class LinearViscoelasticCalibrationMaterializer(PluginExecutionMaterializer):
    """Materialize one exact calibrator attempt for the isolated T-18 runner.

    The returned paths are owned by this materializer instance until :meth:`cleanup` is
    called.  The caller must invoke cleanup after either a successful or failed runner cycle;
    cleanup refuses paths not allocated by this instance and never follows a symlink.
    """

    def __init__(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_service: ArtifactService,
        temporary_parent: Path | None = None,
        max_package_bytes: int = 512 * 1024 * 1024,
        max_package_entries: int = 10_000,
        max_control_document_bytes: int = 4 * 1024 * 1024,
    ) -> None:
        if decision.permission is not Permission.ARTIFACT_READ:
            raise ValueError("calibration materialization requires an ARTIFACT_READ decision")
        if (
            decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
            or decision.request_id != context.request_id
            or decision.trace_id != context.trace_id
        ):
            raise ValueError("artifact authorization decision differs from its security context")
        if not 1 <= max_package_bytes <= 512 * 1024 * 1024:
            raise ValueError("max_package_bytes is outside the T-18 platform limit")
        if not 1 <= max_package_entries <= 100_000:
            raise ValueError("max_package_entries is outside the T-18 platform limit")
        if not 1 <= max_control_document_bytes <= 4 * 1024 * 1024:
            raise ValueError("max_control_document_bytes is outside the T-18 platform limit")
        parent = (temporary_parent or Path(tempfile.gettempdir())).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError("temporary parent must be a real directory")
        self._context = context
        self._decision = decision
        self._artifacts = artifact_service
        self._temporary_parent = parent
        self._max_package_bytes = max_package_bytes
        self._max_package_entries = max_package_entries
        self._max_control_document_bytes = max_control_document_bytes
        self._owned_roots: set[Path] = set()

    def _validate_scope(self, claimed: ClaimedAttempt, package: PackageRecord) -> None:
        job = claimed.job
        if job.job_type != _PLUGIN_JOB_TYPE:
            raise _invalid("claimed Job is not the plugin.run contract")
        if (
            job.organization_id != self._context.organization_id
            or job.project_id != self._context.project_id
            or not self._decision.allows(job.organization_id, job.project_id, job.classification)
        ):
            raise _invalid("claimed Job tenant or classification is outside the worker scope")
        if (
            package.organization_id != self._context.organization_id
            or package.project_id != self._context.project_id
            or package.classification is not job.classification
            or not self._decision.allows(
                package.organization_id, package.project_id, package.classification
            )
        ):
            raise _invalid("plugin package tenant or classification is outside the worker scope")
        if not package.active:
            raise _invalid("plugin package is not active")
        if claimed.attempt.job_id != job.id or claimed.attempt.id != job.current_attempt_id:
            raise _invalid("claimed Attempt is not the current Attempt of the Job")
        if (
            claimed.attempt.spec.job_id != job.id
            or claimed.attempt.spec.attempt_id != claimed.attempt.id
        ):
            raise _invalid("claimed Job Spec identity differs from the Job and Attempt")

    @staticmethod
    def _validate_job_document(
        claimed: ClaimedAttempt,
        package: PackageRecord,
        extension_ordinal: int,
        job_spec: Mapping[str, object],
    ) -> tuple[UUID, UUID, str, list[Mapping[str, object]]]:
        if job_spec != claimed.attempt.spec.document():
            raise _invalid("materializer received a Job Spec different from the claimed Attempt")
        if job_spec.get("job_spec_version") != "1.0":
            raise _invalid("Job Spec version is invalid")
        if job_spec.get("job_id") != str(claimed.job.id):
            raise _invalid("Job Spec job identity differs from the claim")
        if job_spec.get("attempt_id") != str(claimed.attempt.id):
            raise _invalid("Job Spec Attempt identity differs from the claim")
        if job_spec.get("operation") != "execute_plan":
            raise _invalid("calibration Job Spec operation must be execute_plan")
        extension = _object(job_spec.get("extension"), "Job Spec extension")
        if extension.get("type") != ExtensionType.CALIBRATOR.value:
            raise _invalid("Job Spec extension type is not the calibrator")
        if extension.get("plugin_id") != LINEAR_VISCOELASTIC_CALIBRATOR_ID:
            raise _invalid("Job Spec plugin identity is not the linear-viscoelastic calibrator")
        if extension.get("plugin_version") != LINEAR_VISCOELASTIC_CALIBRATOR_VERSION:
            raise _invalid("Job Spec plugin version is not the approved calibrator version")
        package_sha256 = _digest_ref(extension.get("package_digest"), "package_digest")
        if set(extension) != {"type", "plugin_id", "plugin_version", "package_digest"}:
            raise _invalid("Job Spec extension contains unexpected fields")
        if package.manifest.plugin_id != LINEAR_VISCOELASTIC_CALIBRATOR_ID:
            raise _invalid(
                "active package plugin identity is not the linear-viscoelastic calibrator"
            )
        if package.manifest.plugin_version != LINEAR_VISCOELASTIC_CALIBRATOR_VERSION:
            raise _invalid("active package plugin version is not approved")
        if package.manifest.package_digest != package_sha256:
            raise _invalid("Job Spec package digest differs from the active package")
        if package.package_artifact.sha256 != package_sha256:
            raise _integrity("package Artifact digest differs from the package manifest")
        if package.package_artifact.media_type != _ZIP_MEDIA_TYPE:
            raise _integrity("package Artifact media type is not application/zip")
        if package.manifest.document().get("non_production") is not True:
            raise _invalid("linear-viscoelastic package must remain non-production")
        extensions = tuple(
            item for item in package.manifest.extensions if item.ordinal == extension_ordinal
        )
        if len(extensions) != 1 or extensions[0].extension_type is not ExtensionType.CALIBRATOR:
            raise _invalid("active package extension ordinal is not the calibrator")

        config_schema = job_spec.get("config_schema_ref")
        if config_schema != LINEAR_VISCOELASTIC_CONFIG_SCHEMA:
            raise _invalid("calibration Job Spec config schema is invalid")
        config = _object(job_spec.get("config"), "Job Spec config")
        if (
            set(config)
            != {
                "schema_version",
                "run_id",
                "plan_revision_id",
                "plan_sha256",
                "recommendation_policy",
                "seed_status",
            }
            or config.get("schema_version") != "1.0.0"
            or config.get("recommendation_policy") != LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY
            or config.get("seed_status") != "not_applicable"
        ):
            raise _invalid("calibration Job Spec config is not exact")
        run_id = _uuid(config.get("run_id"), "config.run_id")
        plan_revision_id = _uuid(config.get("plan_revision_id"), "config.plan_revision_id")
        plan_sha256 = _digest(config.get("plan_sha256"), "config.plan_sha256")

        execution = _object(job_spec.get("execution"), "Job Spec execution")
        if (
            set(execution) != {"seed", "deadline", "traceparent", "locale", "timezone"}
            or type(execution.get("seed")) is not int
            or execution.get("seed") != 0
            or execution.get("locale") != "C"
            or execution.get("timezone") != "UTC"
            or execution.get("traceparent") != claimed.job.trace_id
        ):
            raise _invalid("calibration Job Spec execution policy is not exact")
        deadline = _timestamp(execution.get("deadline"), "execution.deadline")
        if deadline != claimed.job.deadline:
            raise _invalid("Job Spec deadline differs from the durable Job")

        expected_outputs = job_spec.get("expected_outputs")
        if not isinstance(expected_outputs, list) or len(expected_outputs) != len(
            _EXPECTED_OUTPUTS
        ):
            raise _invalid("calibration Job Spec must declare exactly three outputs")
        output_roles: set[str] = set()
        for raw in expected_outputs:
            output = _object(raw, "Job Spec expected output")
            role = output.get("role")
            schema_ref = output.get("schema_ref")
            if not isinstance(role, str) or role in output_roles:
                raise _invalid("Job Spec expected output roles must be unique")
            output_roles.add(role)
            contract = _EXPECTED_OUTPUTS.get(role)
            if (
                contract is None
                or schema_ref != contract[0]
                or set(output) != {"role", "schema_ref"}
            ):
                raise _invalid(
                    "Job Spec expected output schema differs from the calibrator contract"
                )
        if output_roles != set(_EXPECTED_OUTPUTS):
            raise _invalid("Job Spec expected output roles are not exact")

        raw_inputs = job_spec.get("inputs")
        if not isinstance(raw_inputs, list) or len(raw_inputs) not in {
            len(_REQUIRED_INPUT_ROLES),
            len(_EXPECTED_INPUTS),
        }:
            raise _invalid("calibration Job Spec must declare direct or processed input roles")
        inputs: list[Mapping[str, object]] = []
        input_roles: set[str] = set()
        for raw in raw_inputs:
            item = _object(raw, "Job Spec input")
            role = item.get("role")
            if not isinstance(role, str) or role in input_roles or role not in _EXPECTED_INPUTS:
                raise _invalid("Job Spec input roles are not exact")
            input_contract = _EXPECTED_INPUTS[role]
            if set(item) != {
                "role",
                "entity_revision_id",
                "artifact_id",
                "sha256",
                "media_type",
                "access",
            }:
                raise _invalid("Job Spec input contains unexpected or missing fields")
            if item.get("media_type") != input_contract.media_type:
                raise _invalid("Job Spec input media type differs from the role contract")
            if item.get("access") != "read_exact_artifact":
                raise _invalid("Job Spec input access policy is not exact")
            _uuid(item.get("entity_revision_id"), f"{role}.entity_revision_id")
            _uuid(item.get("artifact_id"), f"{role}.artifact_id")
            _digest(item.get("sha256"), f"{role}.sha256")
            input_roles.add(role)
            inputs.append(item)
        if input_roles != _REQUIRED_INPUT_ROLES and input_roles != set(_EXPECTED_INPUTS):
            raise _invalid("Job Spec input roles are not exact")
        plan = next(item for item in inputs if item.get("role") == "calibration.plan")
        if (
            plan.get("entity_revision_id") != str(plan_revision_id)
            or plan.get("sha256") != plan_sha256
        ):
            raise _invalid("calibration.plan input does not pin the configured Plan revision")
        resource = claimed.job.resource_policy
        expected_resource = linear_viscoelastic_resource_policy()
        if resource != expected_resource:
            raise _invalid("Job resource policy differs from the calibrator contract")
        manifest = package.manifest
        manifest_read_roles = set(manifest.artifact_read_roles)
        allowed_manifest_roles = (_REQUIRED_INPUT_ROLES, set(_EXPECTED_INPUTS))
        if (
            manifest.network != "none"
            or manifest.cpu != 2.0
            or manifest.memory_mb != 4_096
            or manifest.gpu != 0
            or manifest.timeout_s != 3_600
            or manifest_read_roles not in allowed_manifest_roles
            or (
                input_roles == set(_EXPECTED_INPUTS)
                and manifest_read_roles != set(_EXPECTED_INPUTS)
            )
            or set(manifest.artifact_write_roles) != set(_EXPECTED_OUTPUTS)
        ):
            raise _invalid("active package resource or artifact role policy differs")
        return run_id, plan_revision_id, plan_sha256, inputs

    @staticmethod
    def _validate_schemas(package: PackageRecord, extension_ordinal: int) -> None:
        schemas = tuple(
            item for item in package.schemas if item.extension_ordinal == extension_ordinal
        )
        if len(schemas) != 1 + len(_EXPECTED_OUTPUTS):
            raise _invalid("active package must register exactly four calibrator schemas")
        seen: set[tuple[SchemaRole, str]] = set()
        expected: dict[tuple[SchemaRole, str], None] = {
            (SchemaRole.CONFIG, LINEAR_VISCOELASTIC_CONFIG_SCHEMA): None,
            (SchemaRole.OUTPUT, LINEAR_VISCOELASTIC_RESULT_SCHEMA): None,
            (SchemaRole.EVIDENCE, LINEAR_VISCOELASTIC_RESIDUAL_SCHEMA): None,
            (SchemaRole.EVIDENCE, LINEAR_VISCOELASTIC_HISTORY_SCHEMA): None,
        }
        for schema in schemas:
            key = (schema.role, schema.schema_id)
            if key in seen or key not in expected:
                raise _invalid("active package schema roles or identities are not exact")
            if schema.document().get("$id") != schema.schema_id:
                raise _invalid("registered package schema identity differs from its document")
            seen.add(key)
        if seen != set(expected):
            raise _invalid("active package is missing a required calibrator schema")

    def _validate_artifact_record(
        self,
        *,
        record: object,
        artifact_id: UUID,
        expected_sha256: str,
        expected_size_bytes: int | None,
        expected_media_type: str,
        expected_artifact_role: str | None,
        classification: DataClassification,
        package: bool = False,
    ) -> int:
        if expected_size_bytes is not None and expected_size_bytes < 0:
            raise _integrity("Artifact size is invalid")
        artifact = getattr(record, "artifact", None)
        if (
            getattr(record, "integrity_status", None) is not IntegrityStatus.VERIFIED
            or artifact is None
            or getattr(artifact, "id", None) != artifact_id
            or getattr(artifact, "organization_id", None) != self._context.organization_id
            or getattr(artifact, "project_id", None) != self._context.project_id
            or getattr(artifact, "classification", None) is not classification
            or getattr(artifact, "media_type", None) != expected_media_type
            or getattr(artifact, "sha256", None) != expected_sha256
            or not isinstance(getattr(artifact, "size_bytes", None), int)
            or getattr(artifact, "size_bytes", -1) < 0
        ):
            kind = "package" if package else "input"
            raise _integrity(f"authoritative {kind} Artifact differs from its immutable pin")
        size_bytes = cast(int, artifact.size_bytes)
        if expected_size_bytes is not None and size_bytes != expected_size_bytes:
            raise _integrity("Artifact size differs from its immutable package pin")
        if (
            expected_artifact_role is not None
            and getattr(artifact, "artifact_role", None) != expected_artifact_role
        ):
            raise _integrity("Artifact role differs from its exact persisted role contract")
        return size_bytes

    async def _stream_artifact_to_file(
        self,
        *,
        destination: Path,
        artifact_id: UUID,
        expected_sha256: str,
        expected_size_bytes: int | None,
        expected_media_type: str,
        expected_artifact_role: str | None,
        classification: DataClassification,
        package: bool = False,
    ) -> int:
        """Stream one authorized Artifact into a fresh file and verify its final digest."""

        if expected_size_bytes is not None and expected_size_bytes > self._max_package_bytes:
            raise _integrity("Artifact exceeds the capability-safe materializer stream limit")
        maximum = self._max_package_bytes
        stream_method = getattr(self._artifacts, "stream_verified_bytes", None)
        if callable(stream_method):
            record, chunks = await stream_method(
                self._context,
                self._decision,
                artifact_id,
                maximum_bytes=maximum,
            )
            declared_size = self._validate_artifact_record(
                record=record,
                artifact_id=artifact_id,
                expected_sha256=expected_sha256,
                expected_size_bytes=expected_size_bytes,
                expected_media_type=expected_media_type,
                expected_artifact_role=expected_artifact_role,
                classification=classification,
                package=package,
            )
            digest = hashlib.sha256()
            observed = 0
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(destination, flags, 0o400)
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as stream:
                    async for chunk in cast(AsyncIterable[bytes], chunks):
                        if not isinstance(chunk, bytes):
                            raise _integrity("Artifact stream yielded a non-byte chunk")
                        observed += len(chunk)
                        if observed > maximum:
                            raise _integrity("Artifact exceeds the capability-safe stream limit")
                        digest.update(chunk)
                        for offset in range(0, len(chunk), 1024 * 1024):
                            stream.write(chunk[offset : offset + 1024 * 1024])
            finally:
                os.close(descriptor)
            if observed != declared_size or digest.hexdigest() != expected_sha256:
                raise _integrity("Artifact stream bytes differ from its immutable pin")
            try:
                destination.chmod(stat.S_IREAD)
            except OSError:
                pass
            return observed

        # Compatibility for existing test-only ArtifactService ports.  The production service
        # implements stream_verified_bytes; this fallback retains the older bounded API without
        # bypassing authorization or digest verification.
        fallback_maximum = min(maximum, _MAX_ARTIFACT_READ_BYTES)
        if expected_size_bytes is not None:
            fallback_maximum = max(1, min(fallback_maximum, expected_size_bytes))
        record, value = await self._artifacts.read_verified_bytes(
            self._context,
            self._decision,
            artifact_id,
            maximum_bytes=fallback_maximum,
        )
        declared_size = self._validate_artifact_record(
            record=record,
            artifact_id=artifact_id,
            expected_sha256=expected_sha256,
            expected_size_bytes=expected_size_bytes,
            expected_media_type=expected_media_type,
            expected_artifact_role=expected_artifact_role,
            classification=classification,
            package=package,
        )
        if not isinstance(value, bytes) or len(value) != declared_size:
            raise _integrity("Artifact bytes differ from their immutable manifest")
        if _hash_bytes(value) != expected_sha256:
            raise _integrity("Artifact bytes differ from their immutable pin")
        _write_bytes(destination, value)
        return declared_size

    def _validate_archive(self, archive_path: Path, package: PackageRecord) -> str:
        if archive_path.is_symlink() or not archive_path.is_file():
            raise _integrity("materialized package is not a regular file")
        details = archive_path.stat()
        if details.st_size != package.package_artifact.size_bytes:
            raise _integrity("materialized package size differs from its immutable pin")
        if details.st_size < 1 or details.st_size > self._max_package_bytes:
            raise _integrity("materialized package size is outside the runner limit")
        try:
            archive = zipfile.ZipFile(archive_path)
        except (OSError, zipfile.BadZipFile) as error:
            raise _integrity("plugin package is not a valid ZIP archive") from error
        seen: set[PurePosixPath] = set()
        expanded = 0
        lock_bytes: bytes | None = None
        with archive:
            infos = archive.infolist()
            if not infos or len(infos) > self._max_package_entries:
                raise _integrity("plugin package entry count is invalid")
            for info in infos:
                path = _safe_archive_path(info.filename.rstrip("/"))
                if path in seen or info.flag_bits & 0x1 or _zip_symlink(info):
                    raise _integrity(
                        "plugin package contains duplicate, encrypted, or linked entries"
                    )
                seen.add(path)
                expanded += info.file_size
                if expanded > self._max_package_bytes:
                    raise _integrity("plugin package expands beyond its size limit")
                if path == PurePosixPath("dependency.lock"):
                    if info.is_dir() or info.file_size < 1:
                        raise _integrity("plugin dependency.lock must be a regular file")
                    if info.file_size > self._max_control_document_bytes:
                        raise _integrity("plugin dependency.lock exceeds its control limit")
                    try:
                        lock_bytes = archive.read(info)
                    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                        raise _integrity("plugin dependency.lock cannot be read") from error
            if lock_bytes is None:
                raise _integrity("plugin package does not contain dependency.lock")
        lock_digest = _hash_bytes(lock_bytes)
        return lock_digest

    def _new_root(self, attempt_id: UUID) -> Path:
        root = Path(
            tempfile.mkdtemp(
                prefix=f"cmp-lve-{attempt_id}-",
                dir=str(self._temporary_parent),
            )
        ).resolve()
        if root.parent != self._temporary_parent or root.is_symlink() or not root.is_dir():
            raise _invalid("materializer allocated an unsafe attempt root")
        self._owned_roots.add(root)
        return root

    def _remove_root(self, root: Path) -> None:
        resolved = root.resolve(strict=False)
        if resolved not in self._owned_roots:
            raise ValueError("attempt root is not owned by this materializer")
        if (
            resolved.parent != self._temporary_parent
            or resolved.is_symlink()
            or not resolved.is_dir()
        ):
            raise ValueError("attempt root is not a removable materializer directory")
        self._owned_roots.remove(resolved)
        # Staged inputs are read-only for the child process.  Windows refuses to remove
        # read-only files, so restore write permission only inside this owned tree before
        # deleting it.  Symlinks are never traversed.
        for child in resolved.rglob("*"):
            if child.is_symlink():
                continue
            try:
                child.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            except OSError:
                pass
        try:
            resolved.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        except OSError:
            pass
        shutil.rmtree(resolved)

    def cleanup(self, materialization: ExecutionMaterialization) -> None:
        """Remove only the attempt root allocated by this materializer instance."""

        root = Path(materialization.archive_path).resolve(strict=False).parent
        output_root = Path(materialization.output_staging_root).resolve(strict=False)
        if output_root.parent != root:
            raise ValueError("materialization output root is outside its attempt root")
        self._remove_root(root)

    def cleanup_all(self) -> None:
        """Remove every attempt root still owned by this materializer.

        A worker cycle can be cancelled between materialization and the runner's normal
        completion path, so the composition root uses this bounded cleanup hook from a
        ``finally`` block.  Each root is still checked by :meth:`_remove_root`; no caller
        supplied path is accepted and a cleanup error does not prevent the remaining owned
        roots from being attempted.
        """

        failures: list[Exception] = []
        for root in tuple(self._owned_roots):
            try:
                self._remove_root(root)
            except Exception as error:  # pragma: no cover - defensive filesystem boundary
                failures.append(error)
        if failures:
            raise RuntimeError("one or more materializer attempt roots could not be cleaned") from (
                failures[0]
            )

    async def materialize(
        self,
        *,
        claimed: ClaimedAttempt,
        package: PackageRecord,
        extension_ordinal: int,
        job_spec: dict[str, Any],
    ) -> ExecutionMaterialization:
        self._validate_scope(claimed, package)
        if extension_ordinal < 1:
            raise _invalid("extension ordinal must be positive")
        document = _object(job_spec, "Job Spec")
        _run_id, _plan_revision_id, _plan_sha256, inputs = self._validate_job_document(
            claimed, package, extension_ordinal, document
        )
        self._validate_schemas(package, extension_ordinal)

        root = self._new_root(claimed.attempt.id)
        try:
            package_path = root / "package.zip"
            await self._stream_artifact_to_file(
                destination=package_path,
                artifact_id=package.package_artifact.artifact_id,
                expected_sha256=package.package_artifact.sha256,
                expected_size_bytes=package.package_artifact.size_bytes,
                expected_media_type=_ZIP_MEDIA_TYPE,
                expected_artifact_role=None,
                classification=package.classification,
                package=True,
            )
            dependency_lock_digest = self._validate_archive(package_path, package)

            input_root = root / "inputs"
            input_root.mkdir()
            staged: list[StagedInput] = []
            for item in inputs:
                role = cast(str, item["role"])
                contract = _EXPECTED_INPUTS[role]
                artifact_id = _uuid(item["artifact_id"], f"{role}.artifact_id")
                digest = _digest(item["sha256"], f"{role}.sha256")
                media_type = cast(str, item["media_type"])
                source_path = input_root / f"{artifact_id}.input"
                size_bytes = await self._stream_artifact_to_file(
                    destination=source_path,
                    artifact_id=artifact_id,
                    expected_sha256=digest,
                    expected_size_bytes=None,
                    expected_media_type=media_type,
                    expected_artifact_role=contract.persisted_role,
                    classification=claimed.job.classification,
                )
                staged.append(
                    StagedInput(
                        role=role,
                        artifact_id=artifact_id,
                        sha256=digest,
                        media_type=media_type,
                        source_path=source_path,
                        size_bytes=size_bytes,
                    )
                )
            expected_names = {f"{item.artifact_id}.input" for item in staged}
            actual_names = {path.name for path in input_root.iterdir()}
            if actual_names != expected_names or any(
                path.is_symlink() or not path.is_file() for path in input_root.iterdir()
            ):
                raise _invalid("materializer input directory contains an unexpected file")
            output_root = root / "outputs"
            # SubprocessPluginRunner creates this path with exist_ok=False.  A nonexistent path
            # is the fresh, empty staging root required by that boundary.
            allowed = tuple(
                AllowedOutput(role, schema, media_types, cap)
                for role, (schema, media_types, cap) in _EXPECTED_OUTPUTS.items()
            )
            return ExecutionMaterialization(
                archive_path=package_path,
                dependency_lock_digest=dependency_lock_digest,
                staged_inputs=tuple(staged),
                allowed_outputs=allowed,
                output_staging_root=output_root,
            )
        except BaseException:
            self._remove_root(root)
            raise
