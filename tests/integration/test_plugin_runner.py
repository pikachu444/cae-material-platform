from __future__ import annotations

import asyncio
import hashlib
import json
import stat
import zipfile
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.plugins.adapters.contracts.runner import (
    JsonSchemaRunnerContractValidator,
)
from cmp.modules.plugins.adapters.runner.subprocess import SubprocessPluginRunner
from cmp.modules.plugins.application.execution import ExecutePlugin, PluginExecutionService
from cmp.modules.plugins.domain.execution import (
    AllowedOutput,
    ExecutablePluginPackage,
    ExecutionSchema,
    InvalidResultManifest,
    PackageIntegrityError,
    PluginExecutionCancelled,
    PluginExecutionTimedOut,
    ResultStatus,
    RunnerLimits,
    RunnerResponse,
    SandboxPolicy,
    StagedInput,
)
from cmp.modules.plugins.domain.registry import ExtensionType
from cmp.shared.domain.revisions import content_sha256

PROJECT_ROOT = Path(__file__).parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "plugins/reference/contract_echo"
PLUGIN_ID = "org.example.cmp.contract-echo"
PLUGIN_VERSION = "0.1.0"
OUTPUT_ROLE = "contract-output"
OUTPUT_SCHEMA = "urn:cmp:tck:contract-echo:output:1.0.0"
CONFIG_SCHEMA = "urn:cmp:tck:contract-echo:config:1.0.0"

ENTRYPOINTS = {
    ExtensionType.IMPORTER: "contract_echo.plugin:ImporterExtension",
    ExtensionType.PROCESSOR: "contract_echo.plugin:ProcessorExtension",
    ExtensionType.STATISTICAL_ANALYZER: (
        "contract_echo.plugin:StatisticalAnalyzerExtension"
    ),
    ExtensionType.MATERIAL_MODEL: "contract_echo.plugin:MaterialModelExtension",
    ExtensionType.CALIBRATOR: "contract_echo.plugin:CalibratorExtension",
    ExtensionType.VALIDATOR: "contract_echo.plugin:ValidatorExtension",
    ExtensionType.SOLVER_EXPORTER: "contract_echo.plugin:SolverExporterExtension",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_entry(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o444) << 16
    archive.writestr(info, payload)


def _package_archive(tmp_path: Path, *, unsafe_path: str | None = None) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    archive_path = tmp_path / f"package-{uuid4()}.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for source in sorted(FIXTURE_ROOT.rglob("*")):
            if source.is_file() and source.name != "README.md":
                _write_entry(
                    archive,
                    source.relative_to(FIXTURE_ROOT).as_posix(),
                    source.read_bytes(),
                )
        if unsafe_path is not None:
            _write_entry(archive, unsafe_path, b"escape")
    return archive_path


def _command(
    tmp_path: Path,
    *,
    extension_type: ExtensionType = ExtensionType.PROCESSOR,
    behavior: str = "echo",
    timeout: timedelta = timedelta(seconds=5),
    archive_path: Path | None = None,
) -> ExecutePlugin:
    archive = archive_path or _package_archive(tmp_path)
    package_digest = _sha256(archive)
    dependency_lock_digest = hashlib.sha256(
        (FIXTURE_ROOT / "dependency.lock").read_bytes()
    ).hexdigest()
    config_schema = json.loads(
        (FIXTURE_ROOT / "schemas/config.schema.json").read_text(encoding="utf-8")
    )
    job_id = uuid4()
    attempt_id = uuid4()
    job_spec: dict[str, object] = {
        "job_spec_version": "1.0",
        "job_id": str(job_id),
        "attempt_id": str(attempt_id),
        "extension": {
            "type": extension_type.value,
            "plugin_id": PLUGIN_ID,
            "plugin_version": PLUGIN_VERSION,
            "package_digest": f"sha256:{package_digest}",
        },
        "operation": "run",
        "inputs": [],
        "config": {
            "behavior": behavior,
            "media_type": "application/octet-stream",
            **({"output_bytes": 64} if behavior == "oversize" else {}),
        },
        "config_schema_ref": CONFIG_SCHEMA,
        "expected_outputs": [
            {"role": OUTPUT_ROLE, "schema_ref": OUTPUT_SCHEMA},
        ],
        "execution": {
            "seed": 714_2026,
            "deadline": (datetime.now(UTC) + timedelta(seconds=30))
            .isoformat()
            .replace("+00:00", "Z"),
            "traceparent": "00-00000000000000000000000000000018-0000000000000018-01",
            "locale": "C",
            "timezone": "UTC",
        },
    }
    package = ExecutablePluginPackage(
        package_id=UUID("84000000-0000-4000-8000-000000000018"),
        plugin_id=PLUGIN_ID,
        plugin_version=PLUGIN_VERSION,
        package_digest=package_digest,
        extension_type=extension_type,
        entrypoint=ENTRYPOINTS[extension_type],
        capabilities=("contract_echo",),
        artifact_read_roles=(),
        artifact_write_roles=(OUTPUT_ROLE,),
        requested_cpu=1.0,
        requested_memory_mb=128,
        requested_gpu=0,
        requested_timeout=timedelta(seconds=30),
        config_schema=ExecutionSchema(
            CONFIG_SCHEMA,
            config_schema,
            content_sha256(config_schema),
        ),
        archive_path=archive,
        dependency_lock_digest=dependency_lock_digest,
        active=True,
        non_production=True,
    )
    output_root = tmp_path / f"output-{attempt_id}"
    return ExecutePlugin(
        job_spec=job_spec,
        package=package,
        staged_inputs=(),
        allowed_outputs=(
            AllowedOutput(
                OUTPUT_ROLE,
                OUTPUT_SCHEMA,
                ("application/octet-stream",),
                32,
            ),
        ),
        limits=RunnerLimits(
            cpu=1.0,
            memory_mb=128,
            gpu=0,
            timeout=timeout,
            cancellation_grace=timedelta(seconds=1),
            max_total_output_bytes=32,
        ),
        sandbox=SandboxPolicy.development_subprocess(),
        output_staging_root=output_root,
    )


def _service(tmp_path: Path) -> PluginExecutionService:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir(parents=True, exist_ok=True)
    return PluginExecutionService(
        runner=SubprocessPluginRunner(temporary_root=runner_temp),
        validator=JsonSchemaRunnerContractValidator(),
    )


@pytest.mark.parametrize("extension_type", tuple(ExtensionType))
def test_synthetic_seven_extension_types_pass_the_isolated_contract(
    tmp_path: Path,
    extension_type: ExtensionType,
) -> None:
    command = _command(tmp_path, extension_type=extension_type)

    result = asyncio.run(_service(tmp_path).execute(command, asyncio.Event()))

    assert result.status is ResultStatus.SUCCEEDED
    assert len(result.outputs) == 1
    assert result.outputs[0].path.read_bytes() == b"contract-echo"
    assert result.manifest["non_production"] is True


@pytest.mark.parametrize(
    "behavior",
    (
        "network",
        "process",
        "path_traversal",
        "ambient_read",
        "symlink",
        "oversize",
    ),
)
def test_development_runner_fails_closed_for_ambient_or_oversized_operations(
    tmp_path: Path,
    behavior: str,
) -> None:
    command = _command(tmp_path, behavior=behavior)

    result = asyncio.run(_service(tmp_path).execute(command, asyncio.Event()))

    assert result.status is ResultStatus.FAILED
    assert result.outputs == ()
    diagnostics = result.manifest["diagnostics"]
    assert isinstance(diagnostics, list)
    assert isinstance(diagnostics[0], dict)
    assert diagnostics[0]["code"] == "CMP-RUNNER-0005"


def test_identical_seed_produces_identical_output_bytes(tmp_path: Path) -> None:
    first_command = _command(tmp_path / "first", behavior="rng")
    second_command = _command(tmp_path / "second", behavior="rng")

    first = asyncio.run(
        _service(tmp_path / "first").execute(first_command, asyncio.Event())
    )
    second = asyncio.run(
        _service(tmp_path / "second").execute(second_command, asyncio.Event())
    )

    assert first.outputs[0].sha256 == second.outputs[0].sha256
    assert first.outputs[0].path.read_bytes() == second.outputs[0].path.read_bytes()


def test_staged_input_is_rehashed_and_echoed_through_scoped_sdk_io(
    tmp_path: Path,
) -> None:
    command = _command(tmp_path)
    payload = b"immutable-scoped-input"
    source = tmp_path / "source.bin"
    source.write_bytes(payload)
    artifact_id = uuid4()
    digest = hashlib.sha256(payload).hexdigest()
    job_spec = deepcopy(command.job_spec)
    assert isinstance(job_spec, dict)
    job_spec["inputs"] = [
        {
            "role": "source",
            "entity_revision_id": str(uuid4()),
            "artifact_id": str(artifact_id),
            "sha256": digest,
            "media_type": "application/octet-stream",
            "access": "runner-scoped-reference",
        }
    ]
    scoped = replace(
        command,
        job_spec=job_spec,
        package=replace(command.package, artifact_read_roles=("source",)),
        staged_inputs=(
            StagedInput(
                "source",
                artifact_id,
                digest,
                "application/octet-stream",
                source,
                len(payload),
            ),
        ),
    )

    result = asyncio.run(_service(tmp_path).execute(scoped, asyncio.Event()))

    assert result.status is ResultStatus.SUCCEEDED
    assert result.outputs[0].path.read_bytes() == payload


def test_failed_attempt_output_requires_explicit_diagnostic_retention_policy(
    tmp_path: Path,
) -> None:
    command = _command(tmp_path, behavior="failed_output")

    with pytest.raises(InvalidResultManifest, match="allowlist"):
        asyncio.run(_service(tmp_path).execute(command, asyncio.Event()))

    retained = replace(
        command,
        output_staging_root=tmp_path / "retained-output",
        allowed_outputs=(replace(command.allowed_outputs[0], retain_on_failure=True),),
    )
    result = asyncio.run(_service(tmp_path).execute(retained, asyncio.Event()))

    assert result.status is ResultStatus.FAILED
    assert len(result.outputs) == 1


def test_subprocess_timeout_is_enforced_by_parent(tmp_path: Path) -> None:
    command = _command(
        tmp_path,
        behavior="hang",
        timeout=timedelta(seconds=1),
    )

    with pytest.raises(PluginExecutionTimedOut):
        asyncio.run(_service(tmp_path).execute(command, asyncio.Event()))


def test_subprocess_honors_cooperative_cancellation(tmp_path: Path) -> None:
    command = _command(tmp_path, behavior="cancel")
    cancellation = asyncio.Event()

    async def run() -> ResultStatus:
        task = asyncio.create_task(_service(tmp_path).execute(command, cancellation))
        for _ in range(100):
            if command.output_staging_root.exists():
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.2)
        cancellation.set()
        try:
            return (await task).status
        except PluginExecutionCancelled:
            return ResultStatus.CANCELLED

    assert asyncio.run(run()) is ResultStatus.CANCELLED


@pytest.mark.parametrize(
    "kind", ("digest_substitution", "path_traversal", "corrupt_zip")
)
def test_package_integrity_and_archive_paths_are_revalidated(
    tmp_path: Path,
    kind: str,
) -> None:
    archive = _package_archive(
        tmp_path,
        unsafe_path="../escape.py" if kind == "path_traversal" else None,
    )
    if kind == "corrupt_zip":
        archive.write_bytes(b"not-a-zip-package")
    command = _command(tmp_path, archive_path=archive)
    if kind == "digest_substitution":
        archive.write_bytes(archive.read_bytes() + b"substitution")

    with pytest.raises(PackageIntegrityError):
        asyncio.run(_service(tmp_path).execute(command, asyncio.Event()))


class _CorruptManifestRunner:
    def __init__(self, *, non_production: bool = True) -> None:
        self._non_production = non_production

    async def execute(
        self,
        command: ExecutePlugin,
        cancellation: asyncio.Event,
    ) -> RunnerResponse:
        del cancellation
        job = cast(dict[str, Any], command.job_spec)
        execution = cast(dict[str, Any], job["execution"])
        return RunnerResponse(
            {
                "result_manifest_version": "1.0",
                "job_id": str(job["job_id"]),
                "attempt_id": str(job["attempt_id"]),
                "status": "succeeded",
                "started_at": "2026-07-12T00:00:00Z",
                "ended_at": "2026-07-12T00:00:01Z",
                "outputs": [],
                "diagnostics": [],
                "metrics": {"wall_time_s": 1.0, "peak_memory_mb": 1.0},
                "reproducibility": {
                    "package_digest": command.package.package_digest_ref,
                    "dependency_lock_digest": (
                        command.package.dependency_lock_digest_ref
                    ),
                    "seed": execution["seed"],
                    "hardware_summary": "synthetic",
                },
                "non_production": self._non_production,
            },
            (),
            command.sandbox,
        )


def test_core_rejects_schema_valid_manifest_missing_expected_output(tmp_path: Path) -> None:
    command = _command(tmp_path)
    service = PluginExecutionService(
        runner=_CorruptManifestRunner(),
        validator=JsonSchemaRunnerContractValidator(),
    )

    with pytest.raises(InvalidResultManifest, match="every expected output"):
        asyncio.run(service.execute(command, asyncio.Event()))


def test_core_rejects_result_with_mismatched_execution_mode(tmp_path: Path) -> None:
    command = _command(tmp_path)
    service = PluginExecutionService(
        runner=_CorruptManifestRunner(non_production=False),
        validator=JsonSchemaRunnerContractValidator(),
    )

    with pytest.raises(InvalidResultManifest, match="execution mode"):
        asyncio.run(service.execute(command, asyncio.Event()))
