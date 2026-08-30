"""Metal-specific deterministic Fit run orchestration.

Runs are execution evidence, separate from a saved Processing Output.  A run is created (and
its family attempts are inserted) before numerical evaluation starts, so a 422/503 calculation
failure remains searchable without producing an authoritative output revision.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_outputs import (
    CommitProcessingOutput,
    CommonPipelineError,
    CommonProcessingOutputService,
    ExactRevisionPin,
)
from cmp.modules.processing.domain.common_pipeline import ProcessingPreview, ProcessingStep
from cmp.modules.processing.domain.metal_hardening import (
    HARDENING_EQUATION_CONTRACT,
    HARDENING_FAMILIES,
)
from cmp.modules.units.domain.profiles import UnitApplication, UnitProfilePin

_RUNTIME_ROOT_SEARCH_LIMIT = 12
_RUNTIME_SOURCE_FILE_LIMIT = 5000
_RUNTIME_IGNORED_DIRECTORY_NAMES = frozenset(
    {"__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)
_DEPLOYMENT_COMMIT_ENV = (
    "CMP_SOURCE_COMMIT",
    "SOURCE_COMMIT",
    "GIT_COMMIT",
    "COMMIT_SHA",
    "DEPLOYMENT_COMMIT",
    "RENDER_GIT_COMMIT",
    "VERCEL_GIT_COMMIT_SHA",
)


def _repository_root() -> Path | None:
    """Find the repository from this module, never from the process CWD."""

    candidate = Path(__file__).resolve().parent
    for _ in range(_RUNTIME_ROOT_SEARCH_LIMIT):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "uv.lock").is_file()
            and (candidate / "backend" / "src").is_dir()
        ):
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def _source_commit(root: Path | None) -> str:
    for name in _DEPLOYMENT_COMMIT_ENV:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    if root is None or not (root / ".git").exists():
        return "unavailable"
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    value = completed.stdout.strip()
    return value if value else "unavailable"


def _installed_version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _runtime_source_files(source_root: Path) -> list[Path]:
    """Return deterministic Python source paths, excluding generated/cache trees."""

    return sorted(
        (
            path
            for path in source_root.rglob("*.py")
            if path.is_file()
            and not any(part in _RUNTIME_IGNORED_DIRECTORY_NAMES for part in path.parts)
        ),
        key=lambda path: path.relative_to(source_root).as_posix(),
    )


def _runtime_evidence() -> dict[str, Any]:
    """Capture bounded, replay-relevant runtime facts without reading user data."""

    root = _repository_root()
    source_root = root / "backend" / "src" if root is not None else None
    source_files: list[Path] = []
    if source_root is not None:
        source_files = _runtime_source_files(source_root)
    total_file_count = len(source_files)
    bounded_files = source_files[:_RUNTIME_SOURCE_FILE_LIMIT]
    digest = hashlib.sha256()
    if source_root is not None:
        for path in bounded_files:
            digest.update(path.relative_to(source_root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    uv_lock = root / "uv.lock" if root is not None else None
    uv_digest = (
        hashlib.sha256(uv_lock.read_bytes()).hexdigest() if uv_lock and uv_lock.is_file() else None
    )
    versions = {
        "cae-material-platform": _installed_version("cae-material-platform"),
        "numpy": _installed_version("numpy"),
        "scipy": _installed_version("scipy"),
        "sqlalchemy": _installed_version("sqlalchemy"),
        "fastapi": _installed_version("fastapi"),
        "pydantic": _installed_version("pydantic"),
    }
    return {
        "python": sys.version.split()[0],
        "numpy": versions["numpy"],
        "scipy": versions["scipy"],
        "sqlalchemy": versions["sqlalchemy"],
        "fastapi": versions["fastapi"],
        "pydantic": versions["pydantic"],
        "project_version": versions["cae-material-platform"],
        "package_version": versions["cae-material-platform"],
        "platform": platform.platform(),
        "source_commit": _source_commit(root),
        "bounded_source_tree_sha256": digest.hexdigest(),
        "bounded_source_tree_file_count": total_file_count,
        "bounded_source_tree_hashed_file_count": len(bounded_files),
        "bounded_source_tree_truncated": total_file_count > _RUNTIME_SOURCE_FILE_LIMIT,
        "uv_lock_sha256": uv_digest,
        "in_process_plugin": "N/A",
        "container": "N/A",
    }


class MetalFitRunStatus(StrEnum):
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetalFitAttemptStatus(StrEnum):
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetalFitTerminalConflict(CommonPipelineError):
    """A terminal run/attempt is immutable and cannot be transitioned again."""


@dataclass(frozen=True, slots=True)
class MetalFitRun:
    id: UUID
    classification: DataClassification
    source_processing_output: ExactRevisionPin
    source_processing_output_sha256: str
    source_document: ExactRevisionPin
    mapping_profile: ExactRevisionPin
    options: dict[str, Any]
    reproducibility_evidence: dict[str, Any]
    status: MetalFitRunStatus
    failure_code: str | None
    failure_reason: str | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str
    unit_profile: UnitProfilePin | None = None
    unit_applications: tuple[UnitApplication, ...] = ()

    def __post_init__(self) -> None:
        if (self.unit_profile is None) != (not self.unit_applications):
            raise CommonPipelineError(
                "metal Fit Unit Profile pin and application trace must be stored together"
            )


@dataclass(frozen=True, slots=True)
class MetalFitAttempt:
    id: UUID
    run_id: UUID
    ordinal: int
    family: str
    status: MetalFitAttemptStatus
    result: dict[str, Any] | None
    objective_history: tuple[float, ...]
    failure_code: str | None
    failure_reason: str | None
    started_at: datetime
    ended_at: datetime | None


@dataclass(frozen=True, slots=True)
class MetalFitRunDetail:
    run: MetalFitRun
    attempts: tuple[MetalFitAttempt, ...]
    # The execute response carries the exact server calculation that produced
    # the persisted run.  List/get reconstruct evidence from durable attempts
    # and therefore leave this ephemeral field unset.
    preview: ProcessingPreview | None = None


@dataclass(frozen=True, slots=True)
class ExecuteMetalFitRun:
    classification: DataClassification
    source_processing_output: ExactRevisionPin
    fit_step: ProcessingStep
    change_reason: str


class MetalFitRunRepository(Protocol):
    def create_run(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run: MetalFitRun
    ) -> MetalFitRun: ...
    def create_attempt(
        self, *, context: SecurityContext, decision: AuthorizationDecision, attempt: MetalFitAttempt
    ) -> MetalFitAttempt: ...
    def succeed_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        result: dict[str, Any],
        objective_history: tuple[float, ...] = (),
    ) -> MetalFitAttempt: ...
    def fail_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        failure_code: str,
        failure_reason: str,
        result: dict[str, Any] | None = None,
        objective_history: tuple[float, ...] = (),
    ) -> MetalFitAttempt: ...
    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        reproducibility_evidence: dict[str, Any],
    ) -> MetalFitRun: ...
    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
        failure_reason: str,
    ) -> MetalFitRun: ...
    def get_run(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> MetalFitRun: ...
    def list_runs(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[MetalFitRun, ...]: ...
    def list_attempts(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> tuple[MetalFitAttempt, ...]: ...


def _require(
    context: SecurityContext, decision: AuthorizationDecision, permission: Permission
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise CommonPipelineError("authorization decision lacks metal Fit run capability")


class MetalFitRunService:
    def __init__(
        self,
        *,
        repository: MetalFitRunRepository,
        outputs: CommonProcessingOutputService,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._outputs = outputs
        self._id = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteMetalFitRun,
    ) -> MetalFitRunDetail:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        if command.fit_step.method_id != "metal.hardening_fit_extrapolate":
            raise CommonPipelineError("metal Fit run requires metal.hardening_fit_extrapolate")
        source, _ = await self._outputs.export_exact(
            context,
            decision,
            command.source_processing_output.aggregate_id,
            command.source_processing_output.revision_id,
        )
        mapping_profile = source.content.mapping_profile
        mapping_profile_sha256 = source.content.mapping_profile_sha256
        if mapping_profile is None or mapping_profile_sha256 is None:
            raise CommonPipelineError(
                "metal Fit requires a Processing Output backed by a common Mapping Profile"
            )
        unit_profile = getattr(source.content, "unit_profile", None)
        unit_applications = tuple(getattr(source.content, "unit_applications", ()))
        families = command.fit_step.options.get("families")
        if (
            not isinstance(families, list)
            or len(families) != len(HARDENING_FAMILIES)
            or any(not isinstance(item, str) for item in families)
            or len(set(families)) != len(families)
            or set(families) != set(HARDENING_FAMILIES)
        ):
            raise CommonPipelineError(
                "3B metal Fit run requires exactly the four unique candidate families: "
                + ", ".join(HARDENING_FAMILIES)
            )
        base_reproducibility_evidence: dict[str, Any] = {
            "execution": "pending",
            "equation": HARDENING_EQUATION_CONTRACT,
            "equation_contract": HARDENING_EQUATION_CONTRACT,
            "objective": "normalized_predicted_minus_observed_sum_squares_v1",
            "exact_source_digest": source.content.output_sha256,
            "source_processing_output_sha256": source.content.output_sha256,
            "source_processing_output": {
                "aggregate_id": str(command.source_processing_output.aggregate_id),
                "revision_id": str(command.source_processing_output.revision_id),
            },
            "source_document": {
                "aggregate_id": str(source.content.source_document.aggregate_id),
                "revision_id": str(source.content.source_document.revision_id),
            },
            "source_document_sha256": source.content.source_document_sha256,
            "source_canonical_artifact_sha256": source.content.source_canonical_artifact_sha256,
            "mapping_profile": {
                "aggregate_id": str(mapping_profile.aggregate_id),
                "revision_id": str(mapping_profile.revision_id),
            },
            "mapping_profile_sha256": mapping_profile_sha256,
            "exact_options": dict(command.fit_step.options),
            "input_plan": {
                "source": "exact_processing_output",
                "steps": [
                    {
                        "method_id": step.method_id,
                        "method_version": step.method_version,
                        "options": dict(step.options),
                    }
                    for step in (*source.content.steps, command.fit_step)
                ],
            },
            "seed_policy": "not_applicable_no_randomness",
            "production_multistart_policy": "not_configured",
            "fixture_recovery_start": "synthetic_reference_only",
            "runtime": _runtime_evidence(),
        }
        if unit_profile is not None:
            base_reproducibility_evidence["unit_profile"] = {
                "profile_id": str(unit_profile.profile_id),
                "revision_id": str(unit_profile.revision_id),
                "content_sha256": unit_profile.content_sha256,
            }
            base_reproducibility_evidence["unit_applications"] = [
                {
                    "location": item.location,
                    "role": item.role.value,
                    "quantity_semantics": item.quantity_semantics,
                    "dimension": item.dimension.value,
                    "unit_id": item.unit_id,
                }
                for item in unit_applications
            ]
        now = self._clock()
        run = self._repository.create_run(
            context=context,
            decision=decision,
            run=MetalFitRun(
                id=self._id(),
                classification=command.classification,
                source_processing_output=command.source_processing_output,
                source_processing_output_sha256=source.content.output_sha256,
                source_document=source.content.source_document,
                mapping_profile=mapping_profile,
                options=dict(command.fit_step.options),
                reproducibility_evidence=base_reproducibility_evidence,
                status=MetalFitRunStatus.EXECUTING,
                failure_code=None,
                failure_reason=None,
                started_at=now,
                ended_at=None,
                created_at=now,
                created_by=context.principal.id,
                request_id=context.request_id,
                trace_id=context.trace_id,
                unit_profile=unit_profile,
                unit_applications=unit_applications,
            ),
        )
        attempts: list[MetalFitAttempt] = []
        for ordinal, family in enumerate(families):
            attempts.append(
                self._repository.create_attempt(
                    context=context,
                    decision=decision,
                    attempt=MetalFitAttempt(
                        id=self._id(),
                        run_id=run.id,
                        ordinal=ordinal,
                        family=str(family),
                        status=MetalFitAttemptStatus.EXECUTING,
                        result=None,
                        objective_history=(),
                        failure_code=None,
                        failure_reason=None,
                        started_at=now,
                        ended_at=None,
                    ),
                )
            )
        # Keep an in-memory terminal projection so a later family failure can
        # never turn already-successful attempts back into failed evidence.
        attempt_state = {item.id: item for item in attempts}

        def _finite_or_none(value: Any) -> float | None:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return None
            return number if number == number and abs(number) != float("inf") else None

        def _candidate_result(candidate: Any) -> dict[str, Any]:
            tangent = [_finite_or_none(item) for item in candidate.tangent]
            nonfinite_tangent = any(item is None for item in tangent)
            diagnostics = []
            if nonfinite_tangent:
                diagnostics.append(
                    "analytical tangent contained a non-finite value; persisted as null "
                    "(documented singular limit)"
                )
            return {
                "family": candidate.family,
                "response": [float(item) for item in candidate.response],
                "residual": [float(item) for item in candidate.residual],
                "tangent": tangent,
                "parameter_names": list(candidate.parameter_names),
                "parameter_units": list(candidate.parameter_units),
                "lower": [float(item) for item in candidate.lower],
                "initial": [float(item) for item in candidate.initial],
                "fitted": [float(item) for item in candidate.fitted],
                "upper": [float(item) for item in candidate.upper],
                "rmse_pa": float(candidate.rmse_pa),
                "relative_rmse": float(candidate.relative_rmse),
                "objective": float(candidate.objective),
                "scipy_cost": float(candidate.scipy_cost),
                "convergence": bool(candidate.convergence),
                "optimizer_status": int(getattr(candidate, "optimizer_status", 0)),
                "optimizer_message": str(getattr(candidate, "optimizer_message", "")),
                "nfev": int(candidate.nfev),
                "active_bound": list(candidate.active_bound),
                "jacobian_rank": int(candidate.jacobian_rank),
                "jacobian_tolerance": float(candidate.jacobian_tolerance),
                "jacobian_condition": (
                    None
                    if candidate.jacobian_condition is None
                    else float(candidate.jacobian_condition)
                ),
                "identifiability": candidate.identifiability,
                "uncertainty": candidate.uncertainty,
                "objective_history": [float(item) for item in candidate.objective_history],
                "warnings": diagnostics,
            }

        try:
            preview = await self._outputs.preflight(
                context,
                decision,
                CommitProcessingOutput(
                    classification=command.classification,
                    label=f"Metal Fit run {run.id}",
                    source_document=source.content.source_document,
                    mapping_profile=mapping_profile,
                    steps=(*source.content.steps, command.fit_step),
                    change_reason=command.change_reason,
                    source_processing_output=command.source_processing_output,
                    unit_profile=unit_profile,
                ),
                validate_selection=False,
            )
            if (
                preview.unit_profile != unit_profile
                or preview.unit_applications != unit_applications
            ):
                raise CommonPipelineError(
                    "metal Fit execution did not preserve the source Unit Profile application trace"
                )
            stage = preview.preview.stages[-1]
            by_family = {candidate.family: candidate for candidate in stage.fit_candidates}
            failed_families: list[str] = []
            for attempt in attempts:
                candidate = by_family.get(attempt.family)
                if candidate is None:
                    failed = self._repository.fail_attempt(
                        context=context,
                        decision=decision,
                        attempt_id=attempt.id,
                        failure_code="candidate_missing",
                        failure_reason=f"server result did not contain family {attempt.family}",
                    )
                    attempt_state[attempt.id] = failed
                    failed_families.append(attempt.family)
                    continue
                result = _candidate_result(candidate)
                if not bool(candidate.convergence):
                    failed = self._repository.fail_attempt(
                        context=context,
                        decision=decision,
                        attempt_id=attempt.id,
                        failure_code="optimizer_not_converged",
                        failure_reason=str(
                            getattr(candidate, "optimizer_message", "optimizer did not converge")
                        ),
                        result=result,
                        objective_history=tuple(
                            float(item) for item in candidate.objective_history
                        ),
                    )
                    attempt_state[attempt.id] = failed
                    failed_families.append(attempt.family)
                    continue
                succeeded_attempt = self._repository.succeed_attempt(
                    context=context,
                    decision=decision,
                    attempt_id=attempt.id,
                    result=result,
                    objective_history=tuple(float(item) for item in candidate.objective_history),
                )
                attempt_state[attempt.id] = succeeded_attempt
            if failed_families:
                failed_run = self._repository.fail_run(
                    context=context,
                    decision=decision,
                    run_id=run.id,
                    failure_code="candidate_failed",
                    failure_reason="candidate families failed: " + ", ".join(failed_families),
                )
                return MetalFitRunDetail(
                    failed_run,
                    self._repository.list_attempts(
                        context=context, decision=decision, run_id=run.id
                    ),
                    preview.preview,
                )
            evidence = {
                **base_reproducibility_evidence,
                "execution": "completed",
                "candidates": [
                    by_family[item.family].family for item in attempts if item.family in by_family
                ],
            }
            succeeded = self._repository.succeed_run(
                context=context,
                decision=decision,
                run_id=run.id,
                reproducibility_evidence=evidence,
            )
        except Exception as error:
            reason = str(error) or error.__class__.__name__
            for attempt in attempts:
                if attempt_state.get(attempt.id, attempt).status is MetalFitAttemptStatus.EXECUTING:
                    failed = self._repository.fail_attempt(
                        context=context,
                        decision=decision,
                        attempt_id=attempt.id,
                        failure_code="calculation_failed",
                        failure_reason=reason,
                    )
                    attempt_state[attempt.id] = failed
            self._repository.fail_run(
                context=context,
                decision=decision,
                run_id=run.id,
                failure_code="calculation_failed",
                failure_reason=reason,
            )
            raise
        return MetalFitRunDetail(
            succeeded,
            self._repository.list_attempts(context=context, decision=decision, run_id=run.id),
            preview.preview,
        )

    def get(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> MetalFitRunDetail:
        _require(context, decision, Permission.PROCESSING_READ)
        run = self._repository.get_run(context=context, decision=decision, run_id=run_id)
        return MetalFitRunDetail(
            run, self._repository.list_attempts(context=context, decision=decision, run_id=run_id)
        )

    def list(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[MetalFitRun, ...]:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.list_runs(context=context, decision=decision)
