"""Committed reference crop Processing Runs with pinned Selection and Recipe revisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactRecord
from cmp.modules.datasets.application.service import (
    DatasetService,
    ImportReferenceTensileCsv,
    RegisterProcessedReferenceTensileDataset,
)
from cmp.modules.datasets.domain.reference_tensile import (
    DatasetError,
    DatasetRepresentation,
    ReferenceTensileMapping,
    normalized_points_from_parquet,
    processed_parquet_bytes,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.domain.reference_import import ImportRunStatus
from cmp.modules.processing.domain.reference_tensile_alignment import (
    REFERENCE_TENSILE_ALIGNMENT_RECIPE_KIND,
    REFERENCE_TENSILE_ALIGNMENT_SCHEMA_ID,
    REFERENCE_TENSILE_ALIGNMENT_SCHEMA_VERSION,
    ReferenceTensileAlignmentRecipeContent,
    align_reference_tensile_curve,
    common_intersection_domain,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    REFERENCE_TENSILE_CROP_RECIPE_KIND,
    REFERENCE_TENSILE_CROP_SCHEMA_VERSION,
    ProcessingConflict,
    ProcessingRunStatus,
    ReferenceTensileCropRecipeContent,
    crop_reference_tensile_points,
)
from cmp.modules.testing.application.service import TestingService
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

PROCESSING_RECIPE_AGGREGATE_TYPE = "processing.processing_recipe"
PROCESSING_RECIPE_SCHEMA_ID = "urn:cmp:processing:reference-tensile-crop-recipe:1.0.0"
type ProcessingRecipeContent = (
    ReferenceTensileCropRecipeContent | ReferenceTensileAlignmentRecipeContent
)


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class ProcessingRecipeSnapshot:
    id: UUID
    current: RevisionSnapshot[ProcessingRecipeContent]


@dataclass(frozen=True, slots=True)
class ProcessingRun:
    id: UUID
    classification: DataClassification
    selection_id: UUID
    selection_revision_id: UUID
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
    run_kind: str = REFERENCE_TENSILE_CROP_RECIPE_KIND
    batch_id: UUID | None = None
    member_ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class ReplicateAlignmentBatch:
    id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    recipe_id: UUID
    recipe_revision_id: UUID
    common_domain_start: float
    common_domain_end: float
    runs: tuple[ProcessingRun, ...]


@dataclass(frozen=True, slots=True)
class ImportRun:
    id: UUID
    classification: DataClassification
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    import_mapping_id: UUID
    import_mapping_revision_id: UUID
    mapping_sha256: str
    importer_id: str
    importer_version: str
    status: ImportRunStatus
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
class CreateReferenceTensileCropRecipe:
    classification: DataClassification
    content: ReferenceTensileCropRecipeContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceTensileCropRecipe:
    expected_current_revision_id: UUID
    content: ReferenceTensileCropRecipeContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceTensileAlignmentRecipe:
    classification: DataClassification
    content: ReferenceTensileAlignmentRecipeContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceTensileCrop:
    selection_id: UUID
    selection_revision_id: UUID
    recipe_id: UUID
    recipe_revision_id: UUID
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceTensileAlignment:
    selection_id: UUID
    selection_revision_id: UUID
    recipe_id: UUID
    recipe_revision_id: UUID
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceImport:
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    import_mapping_id: UUID
    import_mapping_revision_id: UUID
    change_reason: str


class ProcessingRepository(Protocol):
    def recipe_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ProcessingRecipeContent]: ...

    def get_recipe(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
    ) -> ProcessingRecipeSnapshot: ...

    def get_recipe_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        recipe_revision_id: UUID,
    ) -> RevisionSnapshot[ProcessingRecipeContent]: ...

    def list_recipes(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ProcessingRecipeSnapshot, ...]: ...

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ProcessingRun,
    ) -> ProcessingRun: ...

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
        removed_point_count: int | None,
    ) -> ProcessingRun: ...

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        artifact: ArtifactRecord | None,
        failure_code: str,
    ) -> ProcessingRun: ...

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ProcessingRun: ...

    def create_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ImportRun,
    ) -> ImportRun: ...

    def succeed_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        output_dataset_id: UUID,
        output_dataset_revision_id: UUID,
    ) -> ImportRun: ...

    def fail_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> ImportRun: ...

    def get_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ImportRun: ...


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
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


class ProcessingService:
    """Own recipe/run orchestration while delegating Dataset writes to the Dataset module."""

    def __init__(
        self,
        *,
        repository: ProcessingRepository,
        datasets: DatasetService,
        testing: TestingService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._datasets = datasets
        self._testing = testing
        self._artifacts = artifacts
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("processing id_factory returned a zero UUID")
        return value

    def create_reference_tensile_crop_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileCropRecipe,
    ) -> ProcessingRecipeSnapshot:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        reason = _reason(command.change_reason)
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            command.classification.value,
        )
        recipe_id = self._id()
        record = RevisionService(
            aggregate_type=PROCESSING_RECIPE_AGGREGATE_TYPE,
            store=self._repository.recipe_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=recipe_id,
                scope=scope,
                schema_id=PROCESSING_RECIPE_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_CROP_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessingRecipeSnapshot(recipe_id, RevisionSnapshot(record, command.content))

    def create_reference_tensile_alignment_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileAlignmentRecipe,
    ) -> ProcessingRecipeSnapshot:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        reason = _reason(command.change_reason)
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            command.classification.value,
        )
        recipe_id = self._id()
        record = RevisionService(
            aggregate_type=PROCESSING_RECIPE_AGGREGATE_TYPE,
            store=self._repository.recipe_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=recipe_id,
                scope=scope,
                schema_id=REFERENCE_TENSILE_ALIGNMENT_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_ALIGNMENT_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessingRecipeSnapshot(recipe_id, RevisionSnapshot(record, command.content))

    def revise_reference_tensile_crop_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        command: ReviseReferenceTensileCropRecipe,
    ) -> ProcessingRecipeSnapshot:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        reason = _reason(command.change_reason)
        existing = self._repository.get_recipe(
            context=context, decision=decision, recipe_id=recipe_id
        )
        if not isinstance(existing.current.content, ReferenceTensileCropRecipeContent):
            raise ProcessingConflict("crop revision endpoint requires a crop Recipe identity")
        if command.content.recipe_label != existing.current.content.recipe_label:
            raise ProcessingConflict(
                "Processing Recipe label is a stable identity and cannot change"
            )
        record = RevisionService(
            aggregate_type=PROCESSING_RECIPE_AGGREGATE_TYPE,
            store=self._repository.recipe_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=recipe_id,
                scope=existing.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=PROCESSING_RECIPE_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_CROP_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessingRecipeSnapshot(recipe_id, RevisionSnapshot(record, command.content))

    def get_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
    ) -> ProcessingRecipeSnapshot:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.get_recipe(context=context, decision=decision, recipe_id=recipe_id)

    def list_recipes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int = 100,
    ) -> tuple[ProcessingRecipeSnapshot, ...]:
        _require(context, decision, Permission.PROCESSING_READ)
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        return self._repository.list_recipes(context=context, decision=decision, limit=limit)

    async def execute_reference_tensile_crop(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceTensileCrop,
    ) -> ProcessingRun:
        """Commit an output Dataset after all pinned inputs and typed semantics validate.

        This deliberately has no preview mode.  The only produced Artifact is committed through
        the immutable Artifact service and becomes a Dataset only after a persisted Run exists.
        """

        _require(context, decision, Permission.PROCESSING_EXECUTE)
        reason = _reason(command.change_reason)
        recipe = self._repository.get_recipe_revision(
            context=context,
            decision=decision,
            recipe_id=command.recipe_id,
            recipe_revision_id=command.recipe_revision_id,
        )
        if not isinstance(recipe.content, ReferenceTensileCropRecipeContent):
            raise ProcessingConflict("reference crop requires a crop Recipe revision")
        selection = self._datasets.get_reference_dataset_selection_revision_for_processing(
            context,
            decision,
            command.selection_id,
            command.selection_revision_id,
        )
        if recipe.record.scope != selection.revision.record.scope:
            raise ProcessingConflict("Processing Recipe and Selection revisions must share scope")
        input_snapshot = self._datasets.get_dataset_revision_for_processing(
            context,
            decision,
            selection.revision.content.dataset_revision_id,
        )
        if input_snapshot.dataset_id != selection.revision.content.dataset_id:
            raise ProcessingConflict(
                "Selection Dataset identity does not match its pinned revision"
            )
        input_content = input_snapshot.revision.content
        if input_content.representation is not DatasetRepresentation.NORMALIZED:
            raise ProcessingConflict(
                "reference crop only accepts a normalized reference tensile Dataset revision"
            )
        if input_snapshot.revision.record.scope != recipe.record.scope:
            raise ProcessingConflict("Processing input Dataset is outside the Recipe tenant scope")
        input_artifact, input_bytes = await self._artifacts.read_verified_bytes(
            context,
            decision,
            input_content.data_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        if input_artifact.artifact.schema_ref != recipe.content.input_schema_ref:
            raise ProcessingConflict(
                "input Dataset Artifact schema differs from the exact Recipe revision"
            )
        try:
            input_points = normalized_points_from_parquet(input_bytes)
        except DatasetError as error:
            raise ProcessingConflict(
                "normalized input Dataset cannot be read for Processing"
            ) from error
        if len(input_points) != input_content.point_count:
            raise ProcessingConflict("input Dataset Artifact point count differs from its revision")
        outcome = crop_reference_tensile_points(input_points, recipe.content)
        run = ProcessingRun(
            id=self._id(),
            classification=DataClassification(recipe.record.scope.classification),
            selection_id=command.selection_id,
            selection_revision_id=command.selection_revision_id,
            recipe_id=command.recipe_id,
            recipe_revision_id=command.recipe_revision_id,
            input_dataset_id=input_snapshot.dataset_id,
            input_dataset_revision_id=input_snapshot.revision.record.revision_id,
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
                artifact_role="dataset.processed_reference_tensile_curve",
                schema_ref=recipe.content.output_schema_ref,
                media_type="application/vnd.apache.parquet",
                value=processed_parquet_bytes(
                    outcome.points,
                    input_content.mapping,
                    schema_ref=recipe.content.output_schema_ref,
                ),
                idempotency_key=f"processing:{created.id}:reference-tensile-crop",
            )
            output = self._datasets.register_processed_reference_tensile_dataset(
                context,
                decision,
                RegisterProcessedReferenceTensileDataset(
                    source_dataset_revision_id=input_snapshot.revision.record.revision_id,
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
                # The processed Dataset revision is already immutable.  Never mark this Run
                # failed merely because its terminal projection could not be persisted after
                # that commit; doing so would falsely sever ownership/provenance.  Leave the
                # durable Run executing for explicit reconciliation instead.
                raise ProcessingConflict(
                    "processed Dataset output committed but Processing Run terminal state "
                    "requires reconciliation"
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
                # Preserve the original command error; a future durable Job retry/reconciliation
                # path can surface a terminal-state update failure independently.
                pass
            raise

    async def execute_reference_tensile_alignment(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceTensileAlignment,
    ) -> ReplicateAlignmentBatch:
        """Align every pinned replicate to one explicit grid as separate outputs."""

        _require(context, decision, Permission.PROCESSING_EXECUTE)
        reason = _reason(command.change_reason)
        recipe = self._repository.get_recipe_revision(
            context=context,
            decision=decision,
            recipe_id=command.recipe_id,
            recipe_revision_id=command.recipe_revision_id,
        )
        if not isinstance(recipe.content, ReferenceTensileAlignmentRecipeContent):
            raise ProcessingConflict("replicate alignment requires an alignment Recipe revision")
        selection = (
            self._datasets.get_reference_tensile_replicate_selection_revision_for_processing(
                context,
                decision,
                command.selection_id,
                command.selection_revision_id,
            )
        )
        if recipe.record.scope != selection.revision.record.scope:
            raise ProcessingConflict("alignment Recipe and replicate Selection must share scope")

        inputs = []
        curves = []
        for member in selection.revision.content.members:
            snapshot = self._datasets.get_dataset_revision_for_processing(
                context, decision, member.dataset_revision_id
            )
            if snapshot.dataset_id != member.dataset_id:
                raise ProcessingConflict("replicate member Dataset identity does not match")
            if snapshot.revision.record.scope != recipe.record.scope:
                raise ProcessingConflict("replicate Dataset is outside the Recipe tenant scope")
            content = snapshot.revision.content
            if content.representation is not DatasetRepresentation.NORMALIZED:
                raise ProcessingConflict(
                    "reference alignment currently accepts normalized Dataset revisions only"
                )
            input_artifact, payload = await self._artifacts.read_verified_bytes(
                context,
                decision,
                content.data_artifact_id,
                maximum_bytes=16 * 1024 * 1024,
            )
            if input_artifact.artifact.schema_ref != recipe.content.input_schema_ref:
                raise ProcessingConflict(
                    "replicate Artifact schema differs from the exact alignment Recipe revision"
                )
            try:
                points = normalized_points_from_parquet(payload)
            except DatasetError as error:
                raise ProcessingConflict("replicate Dataset cannot be read") from error
            if len(points) != content.point_count:
                raise ProcessingConflict("replicate Artifact point count differs from revision")
            inputs.append(snapshot)
            curves.append(points)

        common_domain = common_intersection_domain(tuple(curves))
        outcomes = tuple(
            align_reference_tensile_curve(
                points,
                recipe.content,
                common_domain=common_domain,
            )
            for points in curves
        )
        batch_id = self._id()
        results: list[ProcessingRun] = []
        for member, input_snapshot, outcome in zip(
            selection.revision.content.members, inputs, outcomes, strict=True
        ):
            run = ProcessingRun(
                id=self._id(),
                classification=DataClassification(recipe.record.scope.classification),
                selection_id=command.selection_id,
                selection_revision_id=command.selection_revision_id,
                recipe_id=command.recipe_id,
                recipe_revision_id=command.recipe_revision_id,
                input_dataset_id=input_snapshot.dataset_id,
                input_dataset_revision_id=input_snapshot.revision.record.revision_id,
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
                run_kind=REFERENCE_TENSILE_ALIGNMENT_RECIPE_KIND,
                batch_id=batch_id,
                member_ordinal=member.ordinal,
            )
            created = self._repository.create_run(context=context, decision=decision, run=run)
            artifact: ArtifactRecord | None = None
            output_registered = False
            try:
                artifact = await self._artifacts.finalize_derived_bytes(
                    context,
                    decision,
                    classification=created.classification,
                    artifact_role="dataset.processed_reference_tensile_curve",
                    schema_ref=recipe.content.output_schema_ref,
                    media_type="application/vnd.apache.parquet",
                    value=processed_parquet_bytes(
                        outcome.points,
                        input_snapshot.revision.content.mapping,
                        schema_ref=recipe.content.output_schema_ref,
                    ),
                    idempotency_key=(
                        f"processing:{created.id}:reference-tensile-common-grid"
                    ),
                )
                output = self._datasets.register_processed_reference_tensile_dataset(
                    context,
                    decision,
                    RegisterProcessedReferenceTensileDataset(
                        source_dataset_revision_id=input_snapshot.revision.record.revision_id,
                        processing_run_id=created.id,
                        artifact=artifact,
                        point_count=outcome.output_point_count,
                        change_reason=reason,
                    ),
                )
                output_registered = True
                results.append(
                    self._repository.succeed_run(
                        context=context,
                        decision=decision,
                        run_id=created.id,
                        artifact=artifact,
                        output_dataset_id=output.id,
                        output_dataset_revision_id=output.current.record.revision_id,
                        output_point_count=outcome.output_point_count,
                        removed_point_count=None,
                    )
                )
            except Exception as error:
                if output_registered:
                    raise ProcessingConflict(
                        "aligned Dataset committed but Run terminal state requires reconciliation"
                    ) from error
                try:
                    self._repository.fail_run(
                        context=context,
                        decision=decision,
                        run_id=created.id,
                        artifact=artifact,
                        failure_code="alignment_command_failed",
                    )
                except Exception:
                    pass
                raise
        return ReplicateAlignmentBatch(
            id=batch_id,
            selection_id=command.selection_id,
            selection_revision_id=command.selection_revision_id,
            recipe_id=command.recipe_id,
            recipe_revision_id=command.recipe_revision_id,
            common_domain_start=common_domain[0],
            common_domain_end=common_domain[1],
            runs=tuple(results),
        )

    async def execute_reference_import(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceImport,
    ) -> ImportRun:
        """Run the bounded reference adapter from an immutable, human-approved Mapping revision.

        The adapter is deliberately non-production and inline for this small reference slice.
        It uses the Dataset owner's public application port; no Processing code writes Dataset
        tables or changes raw bytes directly.
        """

        _require(context, decision, Permission.PROCESSING_EXECUTE)
        reason = _reason(command.change_reason)
        mapping = self._testing.get_import_mapping_revision_for_processing(
            context,
            decision,
            command.import_mapping_id,
            command.import_mapping_revision_id,
        )
        mapping_content = mapping.revision.content
        test_run = self._testing.get_test_run_revision_for_processing(
            context,
            decision,
            command.test_run_id,
            command.test_run_revision_id,
        )
        if test_run.record.scope != mapping.revision.record.scope:
            raise ProcessingConflict(
                "Import Mapping and Test Run revisions must share the same tenant scope"
            )
        if not test_run.content.reference_only:
            raise ProcessingConflict(
                "reference Import Run requires a reference Test Run revision"
            )
        if (
            command.raw_asset_id != mapping_content.raw_asset_id
            or command.raw_artifact_id != mapping_content.raw_artifact_id
        ):
            raise ProcessingConflict(
                "Import Run Raw Asset and Artifact must match the approved Mapping revision"
            )
        scope = mapping.revision.record.scope
        run = ImportRun(
            id=self._id(),
            classification=DataClassification(scope.classification),
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
            raw_asset_id=command.raw_asset_id,
            raw_artifact_id=command.raw_artifact_id,
            import_mapping_id=command.import_mapping_id,
            import_mapping_revision_id=command.import_mapping_revision_id,
            mapping_sha256=mapping_content.dataset_mapping_digest,
            importer_id=mapping_content.importer_id,
            importer_version=mapping_content.importer_version,
            status=ImportRunStatus.EXECUTING,
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
        created = self._repository.create_import_run(
            context=context, decision=decision, run=run
        )
        output_registered = False
        try:
            output = await self._datasets.import_reference_tensile_csv_for_processing(
                context,
                decision,
                ImportReferenceTensileCsv(
                    test_run_id=created.test_run_id,
                    test_run_revision_id=created.test_run_revision_id,
                    raw_asset_id=created.raw_asset_id,
                    raw_artifact_id=created.raw_artifact_id,
                    mapping=ReferenceTensileMapping(
                        mapping_content.strain_column,
                        mapping_content.stress_column,
                        mapping_content.strain_unit,
                        mapping_content.stress_unit,
                    ),
                    change_reason=created.change_reason,
                ),
            )
            output_registered = True
            output_content = output.current.content
            if (
                output_content.representation is not DatasetRepresentation.NORMALIZED
                or output_content.test_run_id != created.test_run_id
                or output_content.test_run_revision_id != created.test_run_revision_id
                or output_content.raw_asset_id != created.raw_asset_id
                or output_content.raw_artifact_id != created.raw_artifact_id
                or output_content.mapping.digest != created.mapping_sha256
            ):
                raise ProcessingConflict(
                    "Dataset owner output does not match the pinned Import Run inputs"
                )
            return self._repository.succeed_import_run(
                context=context,
                decision=decision,
                run_id=created.id,
                output_dataset_id=output.id,
                output_dataset_revision_id=output.current.record.revision_id,
            )
        except Exception as error:
            if output_registered:
                raise ProcessingConflict(
                    "Dataset output committed but Import Run terminal state requires reconciliation"
                ) from error
            try:
                self._repository.fail_import_run(
                    context=context,
                    decision=decision,
                    run_id=created.id,
                    failure_code="reference_import_failed",
                )
            except Exception:
                pass
            raise

    def get_import_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ImportRun:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.get_import_run(
            context=context, decision=decision, run_id=run_id
        )

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ProcessingRun:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.get_run(context=context, decision=decision, run_id=run_id)
