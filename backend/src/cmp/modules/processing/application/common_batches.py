"""Preflight, execute, and retry exact-selection common Processing Recipe batches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_outputs import (
    CommitProcessingOutput,
    CommonProcessingOutputService,
    ExactRevisionPin,
)
from cmp.modules.processing.application.common_recipes import CommonRecipeService
from cmp.modules.processing.domain.common_batches import (
    BatchAttempt,
    BatchAttemptStatus,
    BatchMemberPlan,
    BatchRevisionPin,
    CommonProcessingBatch,
)
from cmp.modules.processing.domain.common_pipeline import CommonPipelineError, ProcessingStep
from cmp.modules.processing.domain.common_recipes import RecipeLifecycle
from cmp.shared.domain.revisions import TenantScope


class CommonBatchNotFound(CommonPipelineError):
    pass


@dataclass(frozen=True, slots=True)
class BatchSourceInput:
    document_id: UUID
    revision_id: UUID


@dataclass(frozen=True, slots=True)
class PreflightBatch:
    classification: DataClassification
    recipe_id: UUID
    recipe_revision_id: UUID
    sources: tuple[BatchSourceInput, ...]


@dataclass(frozen=True, slots=True)
class BatchPreflightMember:
    ordinal: int
    source: BatchSourceInput
    compatible: bool
    source_document_sha256: str | None
    final_point_count: int | None
    diagnostic: str | None


@dataclass(frozen=True, slots=True)
class BatchPreflight:
    recipe_id: UUID
    recipe_revision_id: UUID
    recipe_sha256: str
    members: tuple[BatchPreflightMember, ...]

    @property
    def compatible(self) -> bool:
        return bool(self.members) and all(item.compatible for item in self.members)


@dataclass(frozen=True, slots=True)
class ExecuteBatch:
    classification: DataClassification
    label: str
    recipe_id: UUID
    recipe_revision_id: UUID
    sources: tuple[BatchSourceInput, ...]
    change_reason: str


class CommonBatchRepository(Protocol):
    def create_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch: CommonProcessingBatch,
    ) -> None: ...

    def append_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch_id: UUID,
        attempt: BatchAttempt,
    ) -> None: ...

    def get_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch_id: UUID,
    ) -> CommonProcessingBatch: ...

    def list_batches(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[CommonProcessingBatch, ...]: ...


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
        raise CommonPipelineError("authorization decision lacks Processing Batch capability")


class CommonBatchService:
    def __init__(
        self,
        *,
        repository: CommonBatchRepository,
        recipes: CommonRecipeService,
        outputs: CommonProcessingOutputService,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._recipes = recipes
        self._outputs = outputs
        self._id = id_factory
        self._clock = clock

    async def preflight(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PreflightBatch,
    ) -> BatchPreflight:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        if not command.sources or len(command.sources) > 500:
            raise CommonPipelineError("Batch preflight requires 1..500 exact inputs")
        if len(set(command.sources)) != len(command.sources):
            raise CommonPipelineError("Batch exact inputs must be unique")
        recipe = self._recipes.get_recipe_revision(
            context, decision, command.recipe_id, command.recipe_revision_id
        )
        if recipe.current.scope.classification != command.classification.value:
            raise CommonPipelineError("Batch classification must match the Recipe revision")
        if recipe.content.lifecycle_state is not RecipeLifecycle.PUBLISHED:
            raise CommonPipelineError("Batch execution requires an exact published Recipe revision")
        members: list[BatchPreflightMember] = []
        for ordinal, source in enumerate(command.sources):
            output_command = self._output_command(
                command.classification,
                recipe.content.label,
                recipe.content.mapping_profile_id,
                recipe.content.mapping_profile_revision_id,
                recipe.content.steps,
                source,
                "batch compatibility preflight",
            )
            try:
                result = await self._outputs.preflight(context, decision, output_command)
                members.append(
                    BatchPreflightMember(
                        ordinal,
                        source,
                        True,
                        result.source_document_sha256,
                        result.preview.stages[-1].point_count,
                        None,
                    )
                )
            except (CommonPipelineError, TypeError, ValueError) as error:
                members.append(
                    BatchPreflightMember(ordinal, source, False, None, None, str(error))
                )
        return BatchPreflight(
            recipe_id=recipe.id,
            recipe_revision_id=recipe.current.revision_id,
            recipe_sha256=recipe.content.digest,
            members=tuple(members),
        )

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteBatch,
    ) -> CommonProcessingBatch:
        preflight = await self.preflight(
            context,
            decision,
            PreflightBatch(
                command.classification,
                command.recipe_id,
                command.recipe_revision_id,
                command.sources,
            ),
        )
        incompatible = [item for item in preflight.members if not item.compatible]
        if incompatible:
            raise CommonPipelineError(
                "Batch compatibility preflight failed for member ordinals: "
                + ", ".join(str(item.ordinal) for item in incompatible)
            )
        recipe = self._recipes.get_recipe_revision(
            context, decision, command.recipe_id, command.recipe_revision_id
        )
        now = self._clock()
        batch = CommonProcessingBatch(
            batch_id=self._id(),
            scope=TenantScope(
                context.organization_id,
                context.project_id,
                command.classification.value,
            ),
            label=command.label,
            recipe=BatchRevisionPin(command.recipe_id, command.recipe_revision_id),
            recipe_sha256=preflight.recipe_sha256,
            members=tuple(
                BatchMemberPlan(
                    member_id=self._id(),
                    ordinal=item.ordinal,
                    source_document=BatchRevisionPin(
                        item.source.document_id, item.source.revision_id
                    ),
                    source_document_sha256=item.source_document_sha256 or "",
                )
                for item in preflight.members
            ),
            attempts=(),
            created_at=now,
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        self._repository.create_batch(
            context=context, decision=decision, batch=batch
        )
        for member in batch.members:
            await self._execute_member(
                context,
                decision,
                batch,
                member,
                recipe.content.label,
                recipe.content.mapping_profile_id,
                recipe.content.mapping_profile_revision_id,
                recipe.content.steps,
                command.change_reason,
                1,
            )
        return self.get_batch(context, decision, batch.batch_id)

    async def retry_failed(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch_id: UUID,
    ) -> CommonProcessingBatch:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        batch = self._repository.get_batch(
            context=context, decision=decision, batch_id=batch_id
        )
        recipe = self._recipes.get_recipe_revision(
            context,
            decision,
            batch.recipe.aggregate_id,
            batch.recipe.revision_id,
        )
        latest = batch.latest_attempts
        failed = [
            member
            for member in batch.members
            if latest.get(member.member_id) is not None
            and latest[member.member_id].status is BatchAttemptStatus.FAILED
        ]
        if not failed:
            raise CommonPipelineError("Batch has no failed members to retry")
        for member in failed:
            await self._execute_member(
                context,
                decision,
                batch,
                member,
                recipe.content.label,
                recipe.content.mapping_profile_id,
                recipe.content.mapping_profile_revision_id,
                recipe.content.steps,
                "retry failed Processing Batch member",
                latest[member.member_id].attempt_no + 1,
            )
        return self.get_batch(context, decision, batch_id)

    async def _execute_member(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch: CommonProcessingBatch,
        member: BatchMemberPlan,
        recipe_label: str,
        profile_id: UUID,
        profile_revision_id: UUID,
        steps: tuple[ProcessingStep, ...],
        change_reason: str,
        attempt_no: int,
    ) -> None:
        started = self._clock()
        output: BatchRevisionPin | None = None
        error_code: str | None = None
        error_detail: str | None = None
        status = BatchAttemptStatus.SUCCEEDED
        try:
            snapshot = await self._outputs.commit(
                context,
                decision,
                self._output_command(
                    DataClassification(batch.scope.classification),
                    f"{batch.label} · {recipe_label} · member {member.ordinal + 1}",
                    profile_id,
                    profile_revision_id,
                    steps,
                    BatchSourceInput(
                        member.source_document.aggregate_id,
                        member.source_document.revision_id,
                    ),
                    change_reason,
                ),
            )
            output = BatchRevisionPin(snapshot.id, snapshot.current.revision_id)
        except Exception as error:  # member isolation is the core batch guarantee
            status = BatchAttemptStatus.FAILED
            error_code = type(error).__name__
            error_detail = str(error)[:2000] or "processing member failed"
        attempt = BatchAttempt(
            attempt_id=self._id(),
            member_id=member.member_id,
            attempt_no=attempt_no,
            status=status,
            output=output,
            error_code=error_code,
            error_detail=error_detail,
            started_at=started,
            completed_at=self._clock(),
        )
        self._repository.append_attempt(
            context=context,
            decision=decision,
            batch_id=batch.batch_id,
            attempt=attempt,
        )

    @staticmethod
    def _output_command(
        classification: DataClassification,
        label: str,
        profile_id: UUID,
        profile_revision_id: UUID,
        steps: tuple[ProcessingStep, ...],
        source: BatchSourceInput,
        change_reason: str,
    ) -> CommitProcessingOutput:
        return CommitProcessingOutput(
            classification=classification,
            label=label[:200],
            source_document=ExactRevisionPin(source.document_id, source.revision_id),
            mapping_profile=ExactRevisionPin(profile_id, profile_revision_id),
            steps=steps,
            change_reason=change_reason,
        )

    def get_batch(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch_id: UUID,
    ) -> CommonProcessingBatch:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.get_batch(
            context=context, decision=decision, batch_id=batch_id
        )

    def list_batches(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[CommonProcessingBatch, ...]:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.list_batches(context=context, decision=decision)
