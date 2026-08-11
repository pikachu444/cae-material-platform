from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.processing.application import metal_fit_runs as metal_fit_runs_module
from cmp.modules.processing.application.common_outputs import (
    CommonPipelineError,
    CommonProcessingOutputService,
    ExactRevisionPin,
    ProcessingOutputPreflight,
)
from cmp.modules.processing.application.metal_fit_runs import (
    ExecuteMetalFitRun,
    MetalFitAttempt,
    MetalFitAttemptStatus,
    MetalFitRun,
    MetalFitRunRepository,
    MetalFitRunService,
    MetalFitRunStatus,
)
from cmp.modules.processing.domain.common_pipeline import (
    CurveStage,
    ProcessingPreview,
    ProcessingStep,
)
from cmp.modules.processing.domain.metal_hardening import HARDENING_FAMILIES
from cmp.modules.units.domain.profiles import (
    UnitApplication,
    UnitApplicationRole,
    UnitProfilePin,
)
from cmp.modules.units.domain.system import DimensionId

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
ORG = UUID("d1580000-0000-4000-8000-000000000001")
PROJECT = UUID("d1580000-0000-4000-8000-000000000002")
ACTOR = UUID("d1580000-0000-4000-8000-000000000003")
SOURCE_OUTPUT = UUID("d1580000-0000-4000-8000-000000000004")
SOURCE_OUTPUT_REVISION = UUID("d1580000-0000-4000-8000-000000000005")
SOURCE_DOCUMENT = UUID("d1580000-0000-4000-8000-000000000006")
SOURCE_DOCUMENT_REVISION = UUID("d1580000-0000-4000-8000-000000000007")
MAPPING_PROFILE = UUID("d1580000-0000-4000-8000-000000000008")
MAPPING_PROFILE_REVISION = UUID("d1580000-0000-4000-8000-000000000009")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Fit modeler", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="urn:cmp:metal-fit-test",
        subject=str(ACTOR),
        token_id="metal-fit-test-token",
        groups=(),
        scopes=("openid",),
        request_id=UUID("d1580000-0000-4000-8000-00000000000a"),
        trace_id="00-0000000000000000000000000000d158-000000000000d158-01",
        authenticated_at=NOW,
    )


CONTEXT = _context()
DECISION = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.PROCESSING_EXECUTE,
    roles=(Role.MATERIAL_MODELER,),
    database_permissions=database_permissions_for(Permission.PROCESSING_EXECUTE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=CONTEXT.trace_id,
    decided_at=NOW,
)


def _candidate(family: str, *, convergence: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        family=family,
        response=(1.0, 2.0),
        residual=(0.1, -0.1),
        tangent=(1.0, 1.0),
        parameter_names=("coefficient",),
        parameter_units=("Pa",),
        lower=(0.0,),
        initial=(0.5,),
        fitted=(0.6,),
        upper=(1.0,),
        rmse_pa=1.0,
        relative_rmse=0.01,
        objective=0.02,
        scipy_cost=0.01,
        convergence=convergence,
        optimizer_status=1,
        optimizer_message="converged" if convergence else "fixture failure",
        nfev=2,
        active_bound=(),
        jacobian_rank=1,
        jacobian_tolerance=1e-12,
        jacobian_condition=None,
        identifiability="identified",
        uncertainty="not_provided",
        objective_history=(1.0, 0.1),
    )


def _source() -> Any:
    return SimpleNamespace(
        content=SimpleNamespace(
            output_sha256="a" * 64,
            source_document=ExactRevisionPin(SOURCE_DOCUMENT, SOURCE_DOCUMENT_REVISION),
            source_document_sha256="b" * 64,
            source_canonical_artifact_sha256="c" * 64,
            mapping_profile=ExactRevisionPin(MAPPING_PROFILE, MAPPING_PROFILE_REVISION),
            mapping_profile_sha256="d" * 64,
            steps=(ProcessingStep("metal.elastic_modulus", "1.0.0", {"method": "automatic"}),),
        )
    )


class _Outputs:
    def __init__(self, candidates: tuple[Any, ...]) -> None:
        self.source = _source()
        self.preview = ProcessingOutputPreflight(
            source_document_sha256=self.source.content.source_document_sha256,
            source_canonical_artifact_sha256=self.source.content.source_canonical_artifact_sha256,
            mapping_profile_sha256=self.source.content.mapping_profile_sha256,
            preview=ProcessingPreview(
                self.source.content.source_document_sha256,
                self.source.content.mapping_profile_sha256,
                "strain.plastic",
                (
                    CurveStage(
                        0,
                        "metal.hardening_fit_extrapolate",
                        "1.0.0",
                        2,
                        (),
                        (),
                        fit_candidates=candidates,
                    ),
                ),
            ),
        )
        self.error: Exception | None = None

    async def export_exact(self, *_: Any) -> tuple[Any, bytes]:
        return self.source, b"fixture-output"

    async def preflight(self, *_: Any, **__: Any) -> ProcessingOutputPreflight:
        if self.error is not None:
            raise self.error
        return self.preview


class _Repository(MetalFitRunRepository):
    def __init__(self) -> None:
        self.runs: dict[UUID, MetalFitRun] = {}
        self.attempts: dict[UUID, MetalFitAttempt] = {}

    def create_run(self, *, run: MetalFitRun, **_: Any) -> MetalFitRun:
        self.runs[run.id] = run
        return run

    def create_attempt(self, *, attempt: MetalFitAttempt, **_: Any) -> MetalFitAttempt:
        self.attempts[attempt.id] = attempt
        return attempt

    def succeed_attempt(
        self,
        *,
        attempt_id: UUID,
        result: dict[str, Any],
        objective_history: tuple[float, ...] = (),
        **_: Any,
    ) -> MetalFitAttempt:
        current = self.attempts[attempt_id]
        updated = replace(
            current,
            status=MetalFitAttemptStatus.SUCCEEDED,
            result=result,
            objective_history=objective_history,
            ended_at=NOW,
        )
        self.attempts[attempt_id] = updated
        return updated

    def fail_attempt(
        self,
        *,
        attempt_id: UUID,
        failure_code: str,
        failure_reason: str,
        result: dict[str, Any] | None = None,
        objective_history: tuple[float, ...] = (),
        **_: Any,
    ) -> MetalFitAttempt:
        current = self.attempts[attempt_id]
        updated = replace(
            current,
            status=MetalFitAttemptStatus.FAILED,
            result=result,
            objective_history=objective_history,
            failure_code=failure_code,
            failure_reason=failure_reason,
            ended_at=NOW,
        )
        self.attempts[attempt_id] = updated
        return updated

    def succeed_run(
        self, *, run_id: UUID, reproducibility_evidence: dict[str, Any], **_: Any
    ) -> MetalFitRun:
        updated = replace(
            self.runs[run_id],
            status=MetalFitRunStatus.SUCCEEDED,
            reproducibility_evidence=reproducibility_evidence,
            ended_at=NOW,
        )
        self.runs[run_id] = updated
        return updated

    def fail_run(
        self, *, run_id: UUID, failure_code: str, failure_reason: str, **_: Any
    ) -> MetalFitRun:
        updated = replace(
            self.runs[run_id],
            status=MetalFitRunStatus.FAILED,
            failure_code=failure_code,
            failure_reason=failure_reason,
            ended_at=NOW,
        )
        self.runs[run_id] = updated
        return updated

    def get_run(self, *, run_id: UUID, **_: Any) -> MetalFitRun:
        return self.runs[run_id]

    def list_runs(self, **_: Any) -> tuple[MetalFitRun, ...]:
        return tuple(self.runs.values())

    def list_attempts(self, *, run_id: UUID, **_: Any) -> tuple[MetalFitAttempt, ...]:
        return tuple(
            sorted(
                (item for item in self.attempts.values() if item.run_id == run_id),
                key=lambda item: item.ordinal,
            )
        )


def _service(
    *, candidates: tuple[Any, ...] | None = None
) -> tuple[MetalFitRunService, _Repository, _Outputs]:
    repository = _Repository()
    outputs = _Outputs(candidates or tuple(_candidate(family) for family in HARDENING_FAMILIES))
    ids = iter(UUID(f"d1580000-0000-4000-8000-{value:012d}") for value in range(10, 20))
    service = MetalFitRunService(
        repository=repository,
        outputs=cast(CommonProcessingOutputService, outputs),
        id_factory=lambda: next(ids),
        clock=lambda: NOW,
    )
    return service, repository, outputs


def _command(families: list[str] | None = None) -> ExecuteMetalFitRun:
    return ExecuteMetalFitRun(
        classification=DataClassification.INTERNAL,
        source_processing_output=ExactRevisionPin(SOURCE_OUTPUT, SOURCE_OUTPUT_REVISION),
        fit_step=ProcessingStep(
            "metal.hardening_fit_extrapolate",
            "1.0.0",
            {"families": families or list(HARDENING_FAMILIES)},
        ),
        change_reason="deterministic metal Fit fixture",
    )


def test_execute_requires_exactly_the_four_unique_families() -> None:
    service, repository, _ = _service()

    with pytest.raises(CommonPipelineError, match="exactly the four unique candidate families"):
        asyncio.run(service.execute(CONTEXT, DECISION, _command(list(HARDENING_FAMILIES[:-1]))))

    assert repository.runs == {}
    assert repository.attempts == {}


def test_initial_calculation_failure_retains_pending_reproducibility_and_runtime_markers() -> None:
    service, repository, outputs = _service()
    outputs.error = RuntimeError("synthetic optimizer unavailable")

    with pytest.raises(RuntimeError, match="synthetic optimizer unavailable"):
        asyncio.run(service.execute(CONTEXT, DECISION, _command()))

    assert len(repository.runs) == 1
    run = next(iter(repository.runs.values()))
    assert run.status is MetalFitRunStatus.FAILED
    assert run.failure_code == "calculation_failed"
    assert run.reproducibility_evidence["execution"] == "pending"
    assert run.reproducibility_evidence["exact_source_digest"] == "a" * 64
    runtime = run.reproducibility_evidence["runtime"]
    assert runtime["python"]
    assert runtime["source_commit"]
    assert runtime["bounded_source_tree_sha256"]
    assert (
        runtime["bounded_source_tree_file_count"]
        >= runtime["bounded_source_tree_hashed_file_count"]
    )
    assert "uv_lock_sha256" in runtime
    assert runtime["in_process_plugin"] == "N/A"
    assert runtime["container"] == "N/A"
    assert all(item.status is MetalFitAttemptStatus.FAILED for item in repository.attempts.values())


def test_runtime_evidence_excludes_cache_and_runtime_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path
    backend_source_root = root / "backend" / "src"
    source_root = backend_source_root / "cmp"
    source_root.mkdir(parents=True)
    (source_root / "z_module.py").write_bytes(b"z")
    nested = source_root / "nested"
    nested.mkdir()
    (nested / "a_module.py").write_bytes(b"a")
    pycache = source_root / "__pycache__"
    pycache.mkdir()
    (pycache / "generated.py").write_bytes(b"must be ignored")
    (pycache / "generated.pyc").write_bytes(b"must be ignored")
    pytest_cache = source_root / ".pytest_cache"
    pytest_cache.mkdir()
    (pytest_cache / "generated.py").write_bytes(b"must be ignored")
    (root / "uv.lock").write_bytes(b"fixture lock")
    monkeypatch.setattr(metal_fit_runs_module, "_repository_root", lambda: root)
    monkeypatch.setattr(metal_fit_runs_module, "_source_commit", lambda _: "fixture-commit")
    monkeypatch.setattr(metal_fit_runs_module, "_installed_version", lambda _: None)

    evidence = metal_fit_runs_module._runtime_evidence()
    source_files = metal_fit_runs_module._runtime_source_files(backend_source_root)
    digest = hashlib.sha256()
    for path in source_files:
        digest.update(path.relative_to(backend_source_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")

    assert [path.relative_to(backend_source_root).as_posix() for path in source_files] == [
        "cmp/nested/a_module.py",
        "cmp/z_module.py",
    ]
    assert evidence["bounded_source_tree_file_count"] == 2
    assert evidence["bounded_source_tree_hashed_file_count"] == 2
    assert evidence["bounded_source_tree_truncated"] is False
    assert evidence["bounded_source_tree_sha256"] == digest.hexdigest()
    assert evidence["source_commit"] == "fixture-commit"


def test_success_merges_terminal_evidence_without_erasing_reproducibility_facts() -> None:
    service, repository, _ = _service()
    detail = asyncio.run(service.execute(CONTEXT, DECISION, _command()))

    assert detail.run.status is MetalFitRunStatus.SUCCEEDED
    evidence = detail.run.reproducibility_evidence
    assert evidence["execution"] == "completed"
    assert evidence["equation_contract"]
    assert evidence["exact_source_digest"] == "a" * 64
    assert evidence["source_processing_output_sha256"] == "a" * 64
    assert evidence["runtime"]["python"]
    assert evidence["candidates"] == list(HARDENING_FAMILIES)
    assert all(item.status is MetalFitAttemptStatus.SUCCEEDED for item in detail.attempts)
    assert repository.runs[detail.run.id].reproducibility_evidence == evidence


def test_fit_run_inherits_exact_unit_profile_and_application_trace_from_process_output() -> None:
    pin = UnitProfilePin(
        UUID("d1580000-0000-4000-8000-000000000020"),
        UUID("d1580000-0000-4000-8000-000000000021"),
        "e" * 64,
    )
    applications = (
        UnitApplication(
            "processing.input.stress.true",
            UnitApplicationRole.INPUT,
            "stress.true",
            DimensionId.FORCE_PER_AREA,
            "Pa",
        ),
    )
    service, repository, outputs = _service()
    outputs.source.content.unit_profile = pin
    outputs.source.content.unit_applications = applications
    outputs.preview = replace(
        outputs.preview,
        unit_profile=pin,
        unit_applications=applications,
    )

    detail = asyncio.run(service.execute(CONTEXT, DECISION, _command()))

    assert detail.run.unit_profile == pin
    assert detail.run.unit_applications == applications
    assert detail.run.reproducibility_evidence["unit_profile"] == {
        "profile_id": str(pin.profile_id),
        "revision_id": str(pin.revision_id),
        "content_sha256": pin.content_sha256,
    }
    assert detail.run.reproducibility_evidence["unit_applications"][0] == {
        "location": applications[0].location,
        "role": "input",
        "quantity_semantics": "stress.true",
        "dimension": "force_per_area",
        "unit_id": "Pa",
    }
    assert repository.runs[detail.run.id].unit_profile == pin


def test_prior_successful_attempt_is_not_overwritten_by_a_later_family_failure() -> None:
    candidates = tuple(
        _candidate(family, convergence=family != "swift") for family in HARDENING_FAMILIES
    )
    service, _, _ = _service(candidates=candidates)
    detail = asyncio.run(service.execute(CONTEXT, DECISION, _command()))

    assert detail.run.status is MetalFitRunStatus.FAILED
    attempts = {item.family: item for item in detail.attempts}
    assert attempts["voce"].status is MetalFitAttemptStatus.SUCCEEDED
    assert attempts["voce"].result is not None
    assert attempts["swift"].status is MetalFitAttemptStatus.FAILED
    assert attempts["swift"].failure_code == "optimizer_not_converged"
    assert attempts["hockett_sherby"].status is MetalFitAttemptStatus.SUCCEEDED
    assert attempts["ghosh"].status is MetalFitAttemptStatus.SUCCEEDED
