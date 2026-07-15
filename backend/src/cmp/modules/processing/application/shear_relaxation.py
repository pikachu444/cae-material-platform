"""Committed shear-relaxation crop with exact Dataset and Recipe revision pins."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactRecord
from cmp.modules.datasets.application.shear_relaxation import (
    RegisterProcessedShearRelaxationDataset,
    ShearRelaxationDatasetService,
)
from cmp.modules.datasets.domain.reference_shear_relaxation import (
    shear_relaxation_parquet_bytes,
    shear_relaxation_points_from_parquet,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.domain.reference_shear_relaxation_crop import (
    REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA,
    REFERENCE_SHEAR_RELAXATION_CROP_SCHEMA_ID,
    REFERENCE_SHEAR_RELAXATION_CROP_SCHEMA_VERSION,
    ReferenceShearRelaxationCropRecipeContent,
    crop_reference_shear_relaxation_points,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    ProcessingConflict,
    ProcessingRunStatus,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

SHEAR_RELAXATION_RECIPE_AGGREGATE_TYPE = "processing.shear_relaxation_recipe"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot:
    record: RevisionRecord
    content: ReferenceShearRelaxationCropRecipeContent


@dataclass(frozen=True, slots=True)
class ShearRelaxationRecipeSnapshot:
    id: UUID
    current: RevisionSnapshot


@dataclass(frozen=True, slots=True)
class ShearRelaxationProcessingRun:
    id: UUID
    classification: DataClassification
    recipe_id: UUID
    recipe_revision_id: UUID
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    status: ProcessingRunStatus
    input_point_count: int
    output_point_count: int | None
    removed_point_count: int | None
    result_artifact_id: UUID | None
    result_sha256: str | None
    output_dataset_id: UUID | None
    output_dataset_revision_id: UUID | None
    failure_code: str | None
    change_reason: str
    started_at: datetime
    ended_at: datetime | None
    created_by: UUID
    request_id: UUID
    trace_id: str


@dataclass(frozen=True, slots=True)
class CreateShearRelaxationCropRecipe:
    classification: DataClassification
    content: ReferenceShearRelaxationCropRecipeContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteShearRelaxationCrop:
    recipe_id: UUID
    recipe_revision_id: UUID
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    change_reason: str


class ShearRelaxationProcessingRepository(Protocol):
    def recipe_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceShearRelaxationCropRecipeContent]: ...

    def get_recipe_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        recipe_revision_id: UUID,
    ) -> RevisionSnapshot: ...

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ShearRelaxationProcessingRun,
    ) -> ShearRelaxationProcessingRun: ...

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        artifact: ArtifactRecord,
        output_dataset_id: UUID,
        output_dataset_revision_id: UUID,
        output_point_count: int,
        removed_point_count: int,
    ) -> ShearRelaxationProcessingRun: ...

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        artifact: ArtifactRecord | None,
        failure_code: str,
    ) -> ShearRelaxationProcessingRun: ...

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ShearRelaxationProcessingRun: ...


def _require(
    context: SecurityContext, decision: AuthorizationDecision, permission: Permission
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise ProcessingConflict("authorization decision does not match Processing request")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class ShearRelaxationProcessingService:
    def __init__(
        self,
        *,
        repository: ShearRelaxationProcessingRepository,
        datasets: ShearRelaxationDatasetService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._datasets = datasets
        self._artifacts = artifacts
        self._id_factory = id_factory

    def create_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateShearRelaxationCropRecipe,
    ) -> ShearRelaxationRecipeSnapshot:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        recipe_id = self._id_factory()
        record = RevisionService(
            aggregate_type=SHEAR_RELAXATION_RECIPE_AGGREGATE_TYPE,
            store=self._repository.recipe_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=recipe_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=REFERENCE_SHEAR_RELAXATION_CROP_SCHEMA_ID,
                schema_version=REFERENCE_SHEAR_RELAXATION_CROP_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ShearRelaxationRecipeSnapshot(recipe_id, RevisionSnapshot(record, command.content))

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteShearRelaxationCrop,
    ) -> ShearRelaxationProcessingRun:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        reason = _reason(command.change_reason)
        recipe = self._repository.get_recipe_revision(
            context=context,
            decision=decision,
            recipe_id=command.recipe_id,
            recipe_revision_id=command.recipe_revision_id,
        )
        source = self._datasets.get_revision_for_processing(
            context,
            decision,
            command.input_dataset_id,
            command.input_dataset_revision_id,
        )
        if source.content.representation != "normalized":
            raise ProcessingConflict(
                "shear-relaxation crop accepts only a normalized Dataset revision"
            )
        if source.record.scope != recipe.record.scope:
            raise ProcessingConflict("Recipe and Dataset revisions must share tenant scope")
        _, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            source.content.data_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        points = shear_relaxation_points_from_parquet(value)
        if len(points) != source.content.point_count:
            raise ProcessingConflict("input Artifact point count differs from Dataset revision")
        outcome = crop_reference_shear_relaxation_points(points, recipe.content)
        run = ShearRelaxationProcessingRun(
            id=self._id_factory(),
            classification=DataClassification(recipe.record.scope.classification),
            recipe_id=command.recipe_id,
            recipe_revision_id=command.recipe_revision_id,
            input_dataset_id=command.input_dataset_id,
            input_dataset_revision_id=command.input_dataset_revision_id,
            status=ProcessingRunStatus.EXECUTING,
            input_point_count=outcome.input_point_count,
            output_point_count=None,
            removed_point_count=None,
            result_artifact_id=None,
            result_sha256=None,
            output_dataset_id=None,
            output_dataset_revision_id=None,
            failure_code=None,
            change_reason=reason,
            started_at=datetime.now(UTC),
            ended_at=None,
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        created = self._repository.create_run(context=context, decision=decision, run=run)
        artifact: ArtifactRecord | None = None
        output_registered = False
        try:
            artifact = await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=created.classification,
                artifact_role="dataset.processed_shear_relaxation_curve",
                schema_ref=REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA,
                media_type="application/vnd.apache.parquet",
                value=shear_relaxation_parquet_bytes(outcome.points),
                idempotency_key=f"processing:{created.id}:shear-relaxation-time-crop",
            )
            output = self._datasets.register_processed(
                context,
                decision,
                RegisterProcessedShearRelaxationDataset(
                    source_dataset_id=command.input_dataset_id,
                    source_dataset_revision_id=command.input_dataset_revision_id,
                    processing_run_id=created.id,
                    artifact=artifact,
                    point_count=outcome.output_point_count,
                    change_reason=reason,
                ),
            )
            output_registered = True
            return self._repository.succeed_run(
                context=context,
                decision=decision,
                run_id=created.id,
                artifact=artifact,
                output_dataset_id=output.id,
                output_dataset_revision_id=output.current.record.revision_id,
                output_point_count=outcome.output_point_count,
                removed_point_count=outcome.removed_point_count,
            )
        except Exception as error:
            if output_registered:
                raise ProcessingConflict(
                    "processed Dataset committed but Run projection requires reconciliation"
                ) from error
            try:
                self._repository.fail_run(
                    context=context,
                    decision=decision,
                    run_id=created.id,
                    artifact=artifact,
                    failure_code="processing_command_failed",
                )
            except Exception:
                pass
            raise

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ShearRelaxationProcessingRun:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.get_run(
            context=context, decision=decision, run_id=run_id
        )
