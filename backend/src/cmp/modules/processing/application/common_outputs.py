"""Commit common pipeline previews as exact, immutable Processing Output evidence (T-53)."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.canonical_test_data import CanonicalTestDataService
from cmp.modules.datasets.domain.canonical_test_data import parse_canonical_test_data
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.mapping_profiles import MappingProfileService
from cmp.modules.processing.domain.common_pipeline import (
    CommonPipelineError,
    ProcessingPreview,
    ProcessingStep,
    preview_pipeline,
    processing_preview_canonical,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import (
    RevisionRecord,
    TenantScope,
    canonical_json_bytes,
)

PROCESSING_OUTPUT_AGGREGATE_TYPE = "processing.common_output"
PROCESSING_OUTPUT_SCHEMA_ID = "urn:cmp:processing:common-output:1.1.0"
PROCESSING_OUTPUT_SCHEMA_VERSION = "1.1.0"
PROCESSING_OUTPUT_MEDIA_TYPE = "application/vnd.cmp.processing-output+json"


class ProcessingOutputNotFound(CommonPipelineError):
    pass


@dataclass(frozen=True, slots=True)
class ExactRevisionPin:
    aggregate_id: UUID
    revision_id: UUID


@dataclass(frozen=True, slots=True)
class ProcessingWorkupOverride:
    """A manual physical-workup decision that affected an executed output.

    This is deliberately separate from strict method options: the pipeline only
    receives options it understands, while the immutable output records the
    engineer-entered quantity, its canonical form, and why it was used.
    """

    kind: Literal["youngs_modulus", "necking_boundary"]
    original_value: float
    original_unit: str
    canonical_value: float
    canonical_unit: str
    reason: str

    def __post_init__(self) -> None:
        if self.kind not in {"youngs_modulus", "necking_boundary"}:
            raise CommonPipelineError("unsupported workup override kind")
        if not math.isfinite(self.original_value) or not math.isfinite(self.canonical_value):
            raise CommonPipelineError("workup override values must be finite")
        if not self.original_unit.strip() or not self.canonical_unit.strip():
            raise CommonPipelineError("workup overrides require original and canonical units")
        if not self.reason.strip() or len(self.reason) > 2000:
            raise CommonPipelineError("workup override reason must contain 1..2000 characters")
        if self.kind == "youngs_modulus":
            if self.original_value <= 0 or self.canonical_value <= 0:
                raise CommonPipelineError("Young's modulus override values must be positive")
            if self.canonical_unit != "Pa":
                raise CommonPipelineError("Young's modulus overrides must use canonical Pa")
        if self.kind == "necking_boundary" and self.canonical_unit != "observed-point-index":
            raise CommonPipelineError(
                "necking-boundary overrides must use canonical observed-point-index"
            )


def validate_workup_overrides(
    steps: tuple[ProcessingStep, ...],
    overrides: tuple[ProcessingWorkupOverride, ...],
) -> None:
    """Bind manual workup evidence to the exact options about to be executed."""

    by_kind: dict[str, ProcessingWorkupOverride] = {}
    for override in overrides:
        if override.kind in by_kind:
            raise CommonPipelineError("a Processing Output may contain one override per kind")
        by_kind[override.kind] = override

    manual_modulus = tuple(
        step
        for step in steps
        if step.method_id == "metal.elastic_modulus" and step.options.get("method") == "manual"
    )
    manual_necking = tuple(
        step
        for step in steps
        if step.method_id == "metal.engineering_to_true_plastic"
        and step.options.get("necking_policy") == "manual_index"
    )
    if len(manual_modulus) > 1 or len(manual_necking) > 1:
        raise CommonPipelineError(
            "Processing Output workup evidence is ambiguous across repeated steps"
        )

    _validate_youngs_modulus_override(
        manual_modulus[0] if manual_modulus else None,
        by_kind.get("youngs_modulus"),
    )
    _validate_necking_boundary_override(
        manual_necking[0] if manual_necking else None,
        by_kind.get("necking_boundary"),
    )


def _validate_youngs_modulus_override(
    step: ProcessingStep | None, override: ProcessingWorkupOverride | None
) -> None:
    if step is None:
        if override is not None:
            raise CommonPipelineError(
                "Young's modulus workup override requires an executed manual modulus step"
            )
        return
    if override is None:
        raise CommonPipelineError(
            "an executed manual Young's modulus step requires workup provenance"
        )
    if override.canonical_unit != "Pa" or override.original_unit not in {"GPa", "MPa"}:
        raise CommonPipelineError(
            "Young's modulus provenance requires GPa or MPa original unit and Pa"
        )
    executed = _finite_number(step.options.get("manual_modulus_pa"), "manual_modulus_pa")
    expected = override.original_value * (1e9 if override.original_unit == "GPa" else 1e6)
    if not _same_quantity(override.canonical_value, executed) or not _same_quantity(
        expected, override.canonical_value
    ):
        raise CommonPipelineError(
            "Young's modulus workup provenance must match the executed manual_modulus_pa"
        )


def _validate_necking_boundary_override(
    step: ProcessingStep | None, override: ProcessingWorkupOverride | None
) -> None:
    if step is None:
        if override is not None:
            raise CommonPipelineError(
                "necking-boundary workup override requires an executed manual-index step"
            )
        return
    if override is None:
        raise CommonPipelineError("an executed manual necking boundary requires workup provenance")
    if (
        override.original_unit != "observed-point-index"
        or override.canonical_unit != "observed-point-index"
    ):
        raise CommonPipelineError("necking-boundary provenance requires observed-point-index units")
    if (
        not float(override.original_value).is_integer()
        or not float(override.canonical_value).is_integer()
        or override.original_value < 0
        or override.canonical_value < 0
        or override.original_value != override.canonical_value
    ):
        raise CommonPipelineError(
            "necking-boundary provenance must be one nonnegative observed point index"
        )
    executed = step.options.get("manual_necking_index")
    if isinstance(executed, bool) or not isinstance(executed, int) or executed < 0:
        raise CommonPipelineError("manual_necking_index must be a nonnegative integer")
    if int(override.canonical_value) != executed:
        raise CommonPipelineError(
            "necking-boundary workup provenance must match the executed manual_necking_index"
        )


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CommonPipelineError(f"{label} must be a finite number")
    return float(value)


def _same_quantity(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-6)


@dataclass(frozen=True, slots=True)
class ProcessingOutputContent:
    label: str
    source_document: ExactRevisionPin
    source_document_sha256: str
    source_canonical_artifact_sha256: str
    mapping_profile: ExactRevisionPin
    mapping_profile_sha256: str
    steps: tuple[ProcessingStep, ...]
    independent_quantity: str
    stage_count: int
    final_point_count: int
    output_artifact_id: UUID
    output_sha256: str
    workup_overrides: tuple[ProcessingWorkupOverride, ...] = ()

    def __post_init__(self) -> None:
        if not self.label.strip() or len(self.label) > 200:
            raise CommonPipelineError("Processing Output label must contain 1..200 characters")
        if not self.steps:
            raise CommonPipelineError("committed Processing Output requires at least one step")
        if self.stage_count != len(self.steps) + 1 or self.final_point_count < 2:
            raise CommonPipelineError("Processing Output stage or point count is inconsistent")
        if len({override.kind for override in self.workup_overrides}) != len(self.workup_overrides):
            raise CommonPipelineError("a Processing Output may contain one override per kind")


@dataclass(frozen=True, slots=True)
class ProcessingOutputSnapshot:
    id: UUID
    current: RevisionRecord
    content: ProcessingOutputContent


@dataclass(frozen=True, slots=True)
class ProcessingOutputPreflight:
    source_document_sha256: str
    source_canonical_artifact_sha256: str
    mapping_profile_sha256: str
    preview: ProcessingPreview


@dataclass(frozen=True, slots=True)
class CommitProcessingOutput:
    classification: DataClassification
    label: str
    source_document: ExactRevisionPin
    mapping_profile: ExactRevisionPin
    steps: tuple[ProcessingStep, ...]
    change_reason: str
    workup_overrides: tuple[ProcessingWorkupOverride, ...] = ()


class ProcessingOutputRepository(Protocol):
    def output_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ProcessingOutputContent]: ...

    def get_output(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
    ) -> ProcessingOutputSnapshot: ...

    def list_outputs(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ProcessingOutputSnapshot, ...]: ...


def processing_output_content_canonical(value: ProcessingOutputContent) -> dict[str, object]:
    return {
        "label": value.label,
        "source_document": {
            "aggregate_id": str(value.source_document.aggregate_id),
            "revision_id": str(value.source_document.revision_id),
        },
        "source_document_sha256": value.source_document_sha256,
        "source_canonical_artifact_sha256": value.source_canonical_artifact_sha256,
        "mapping_profile": {
            "aggregate_id": str(value.mapping_profile.aggregate_id),
            "revision_id": str(value.mapping_profile.revision_id),
        },
        "mapping_profile_sha256": value.mapping_profile_sha256,
        "steps": [
            {
                "method_id": step.method_id,
                "method_version": step.method_version,
                "options": step.options,
            }
            for step in value.steps
        ],
        "independent_quantity": value.independent_quantity,
        "stage_count": value.stage_count,
        "final_point_count": value.final_point_count,
        "output_artifact_id": str(value.output_artifact_id),
        "output_sha256": value.output_sha256,
        "workup_overrides": [
            {
                "kind": override.kind,
                "original_value": override.original_value,
                "original_unit": override.original_unit,
                "canonical_value": override.canonical_value,
                "canonical_unit": override.canonical_unit,
                "reason": override.reason,
            }
            for override in value.workup_overrides
        ],
    }


def processing_output_document(
    *,
    output_id: UUID,
    source: ExactRevisionPin,
    source_canonical_sha256: str,
    profile: ExactRevisionPin,
    steps: tuple[ProcessingStep, ...],
    preview: ProcessingPreview,
    workup_overrides: tuple[ProcessingWorkupOverride, ...] = (),
) -> dict[str, object]:
    return {
        "document_type": "cmp.processing-output",
        "document_version": PROCESSING_OUTPUT_SCHEMA_VERSION,
        "output_id": str(output_id),
        "source_document": {
            "aggregate_id": str(source.aggregate_id),
            "revision_id": str(source.revision_id),
        },
        "source_canonical_artifact_sha256": source_canonical_sha256,
        "mapping_profile": {
            "aggregate_id": str(profile.aggregate_id),
            "revision_id": str(profile.revision_id),
        },
        "steps": [
            {
                "method_id": step.method_id,
                "method_version": step.method_version,
                "options": step.options,
            }
            for step in steps
        ],
        "workup_overrides": [
            {
                "kind": override.kind,
                "original_value": override.original_value,
                "original_unit": override.original_unit,
                "canonical_value": override.canonical_value,
                "canonical_unit": override.canonical_unit,
                "reason": override.reason,
            }
            for override in workup_overrides
        ],
        "result": processing_preview_canonical(preview),
    }


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
        raise CommonPipelineError("authorization decision lacks Processing Output capability")


class CommonProcessingOutputService:
    def __init__(
        self,
        *,
        repository: ProcessingOutputRepository,
        test_data: CanonicalTestDataService,
        profiles: MappingProfileService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._test_data = test_data
        self._profiles = profiles
        self._artifacts = artifacts
        self._id = id_factory

    async def preflight(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CommitProcessingOutput,
    ) -> ProcessingOutputPreflight:
        """Validate exact inputs and execute without persisting an output."""

        _require(context, decision, Permission.PROCESSING_EXECUTE)
        validate_workup_overrides(command.steps, command.workup_overrides)
        source_snapshot, source_bytes = await self._test_data.export_document(
            context,
            decision,
            command.source_document.aggregate_id,
            command.source_document.revision_id,
        )
        profile_snapshot = self._profiles.get_profile_revision(
            context,
            decision,
            command.mapping_profile.aggregate_id,
            command.mapping_profile.revision_id,
        )
        if (
            source_snapshot.current.scope.classification != command.classification.value
            or profile_snapshot.current.scope.classification != command.classification.value
        ):
            raise CommonPipelineError(
                "Processing Output classification must match both exact input revisions"
            )
        document = parse_canonical_test_data(json.loads(source_bytes))
        preview = preview_pipeline(document, profile_snapshot.content, command.steps)
        if preview.mapping_profile_sha256 != profile_snapshot.content.digest:
            raise CommonPipelineError("Mapping Profile digest pin differs from executed profile")
        return ProcessingOutputPreflight(
            source_document_sha256=preview.source_document_sha256,
            source_canonical_artifact_sha256=source_snapshot.content.canonical_sha256,
            mapping_profile_sha256=preview.mapping_profile_sha256,
            preview=preview,
        )

    async def commit(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CommitProcessingOutput,
    ) -> ProcessingOutputSnapshot:
        resolved = await self.preflight(context, decision, command)
        preview = resolved.preview
        output_id = self._id()
        output_bytes = canonical_json_bytes(
            processing_output_document(
                output_id=output_id,
                source=command.source_document,
                source_canonical_sha256=resolved.source_canonical_artifact_sha256,
                profile=command.mapping_profile,
                steps=command.steps,
                preview=preview,
                workup_overrides=command.workup_overrides,
            )
        )
        artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=command.classification,
            artifact_role="processing.common-output-json",
            schema_ref=PROCESSING_OUTPUT_SCHEMA_ID,
            media_type=PROCESSING_OUTPUT_MEDIA_TYPE,
            value=output_bytes,
            idempotency_key=f"common-processing-output:{output_id}",
        )
        content = ProcessingOutputContent(
            label=command.label,
            source_document=command.source_document,
            source_document_sha256=preview.source_document_sha256,
            source_canonical_artifact_sha256=resolved.source_canonical_artifact_sha256,
            mapping_profile=command.mapping_profile,
            mapping_profile_sha256=preview.mapping_profile_sha256,
            steps=command.steps,
            independent_quantity=preview.independent_quantity,
            stage_count=len(preview.stages),
            final_point_count=preview.stages[-1].point_count,
            output_artifact_id=artifact.artifact.id,
            output_sha256=artifact.artifact.sha256,
            workup_overrides=command.workup_overrides,
        )
        record = RevisionService(
            aggregate_type=PROCESSING_OUTPUT_AGGREGATE_TYPE,
            store=self._repository.output_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=output_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=PROCESSING_OUTPUT_SCHEMA_ID,
                schema_version=PROCESSING_OUTPUT_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessingOutputSnapshot(output_id, record, content)

    def list_outputs(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ProcessingOutputSnapshot, ...]:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.list_outputs(context=context, decision=decision)

    async def export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
    ) -> tuple[ProcessingOutputSnapshot, bytes]:
        _require(context, decision, Permission.PROCESSING_READ)
        snapshot = self._repository.get_output(
            context=context, decision=decision, output_id=output_id
        )
        artifact, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            snapshot.content.output_artifact_id,
            maximum_bytes=64 * 1024 * 1024,
        )
        if artifact.artifact.sha256 != snapshot.content.output_sha256:
            raise CommonPipelineError("Processing Output Artifact digest pin is inconsistent")
        return snapshot, value

    async def export_exact(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
        output_revision_id: UUID,
    ) -> tuple[ProcessingOutputSnapshot, bytes]:
        snapshot, value = await self.export(context, decision, output_id)
        if snapshot.current.revision_id != output_revision_id:
            raise ProcessingOutputNotFound("exact Processing Output revision is not visible")
        return snapshot, value
