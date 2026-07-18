from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.processing.application.common_batches import (
    BatchSourceInput,
    CommonBatchRepository,
    CommonBatchService,
    ExecuteBatch,
)
from cmp.modules.processing.application.common_outputs import ProcessingOutputPreflight
from cmp.modules.processing.application.common_recipes import (
    CommonRecipeService,
    CommonRecipeSnapshot,
)
from cmp.modules.processing.domain.common_batches import (
    BatchAttempt,
    BatchAttemptStatus,
    BatchStatus,
    CommonProcessingBatch,
)
from cmp.modules.processing.domain.common_pipeline import (
    CommonPipelineError,
    CurveStage,
    ProcessingPreview,
    ProcessingStep,
)
from cmp.modules.processing.domain.common_recipes import (
    CommonProcessingRecipeContent,
    RecipeLifecycle,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

NOW = datetime(2026, 7, 18, 20, 0, tzinfo=UTC)
ORG = UUID("d5410000-0000-4000-8000-000000000001")
PROJECT = UUID("d5410000-0000-4000-8000-000000000002")
ACTOR = UUID("d5410000-0000-4000-8000-000000000003")
RECIPE = UUID("d5410000-0000-4000-8000-000000000004")
RECIPE_REVISION = UUID("d5410000-0000-4000-8000-000000000005")
PROFILE = UUID("d5410000-0000-4000-8000-000000000006")
PROFILE_REVISION = UUID("d5410000-0000-4000-8000-000000000007")
SOURCE_ONE = BatchSourceInput(
    UUID("d5410000-0000-4000-8000-000000000008"),
    UUID("d5410000-0000-4000-8000-000000000009"),
)
SOURCE_TWO = BatchSourceInput(
    UUID("d5410000-0000-4000-8000-000000000010"),
    UUID("d5410000-0000-4000-8000-000000000011"),
)


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="urn:cmp:test",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id="00-0000000000000000000000000000d541-000000000000d541-01",
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


def _recipe() -> CommonRecipeSnapshot:
    content = CommonProcessingRecipeContent(
        recipe_key="dp600-cleanup",
        label="DP600 cleanup",
        description=None,
        mapping_profile_id=PROFILE,
        mapping_profile_revision_id=PROFILE_REVISION,
        mapping_profile_sha256="a" * 64,
        steps=(ProcessingStep("rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}),),
        lifecycle_state=RecipeLifecycle.PUBLISHED,
    )
    record = RevisionRecord(
        RECIPE_REVISION,
        "processing.common_recipe",
        RECIPE,
        TenantScope(ORG, PROJECT, "internal"),
        2,
        uuid4(),
        "urn:cmp:processing:common-recipe:1.0.0",
        "1.0.0",
        content.digest,
        NOW,
        ACTOR,
        "publish",
        CONTEXT.request_id,
        CONTEXT.trace_id,
    )
    return CommonRecipeSnapshot(RECIPE, record, content)


class _Recipes:
    def get_recipe_revision(self, *_: Any) -> CommonRecipeSnapshot:
        return _recipe()


class _Outputs:
    def __init__(self) -> None:
        self.failed_once = False

    async def preflight(self, *_: Any) -> ProcessingOutputPreflight:
        preview = ProcessingPreview(
            "b" * 64,
            "a" * 64,
            "strain.engineering",
            (CurveStage(0, "source", "1.0.0", 3, (), ()),),
        )
        return ProcessingOutputPreflight("b" * 64, "c" * 64, "a" * 64, preview)

    async def commit(self, _context: Any, _decision: Any, command: Any) -> Any:
        if command.source_document.aggregate_id == SOURCE_TWO.document_id and not self.failed_once:
            self.failed_once = True
            raise RuntimeError("reference member failure")
        return SimpleNamespace(
            id=uuid4(), current=SimpleNamespace(revision_id=uuid4())
        )


class _IncompatibleOutputs(_Outputs):
    async def preflight(
        self, _context: Any, _decision: Any, command: Any
    ) -> ProcessingOutputPreflight:
        if command.source_document.aggregate_id == SOURCE_TWO.document_id:
            raise CommonPipelineError("required normalized stress channel is missing")
        return await super().preflight(_context, _decision, command)


class _Repository(CommonBatchRepository):
    def __init__(self) -> None:
        self.batch: CommonProcessingBatch | None = None

    def create_batch(self, **values: Any) -> None:
        self.batch = values["batch"]

    def append_attempt(self, **values: Any) -> None:
        assert self.batch is not None and values["batch_id"] == self.batch.batch_id
        attempt = cast(BatchAttempt, values["attempt"])
        self.batch = CommonProcessingBatch(
            **{
                field: getattr(self.batch, field)
                for field in CommonProcessingBatch.__dataclass_fields__
                if field != "attempts"
            },
            attempts=(*self.batch.attempts, attempt),
        )

    def get_batch(self, **_: Any) -> CommonProcessingBatch:
        assert self.batch is not None
        return self.batch

    def list_batches(self, **_: Any) -> tuple[CommonProcessingBatch, ...]:
        return (self.batch,) if self.batch else ()


def test_batch_preserves_success_and_retries_only_failed_member() -> None:
    async def scenario() -> None:
        repository = _Repository()
        ticks = iter(NOW + timedelta(seconds=value) for value in range(20))
        service = CommonBatchService(
            repository=repository,
            recipes=cast(CommonRecipeService, _Recipes()),
            outputs=cast(Any, _Outputs()),
            clock=lambda: next(ticks),
        )
        batch = await service.execute(
            CONTEXT,
            DECISION,
            ExecuteBatch(
                DataClassification.INTERNAL,
                "DP600 two-specimen batch",
                RECIPE,
                RECIPE_REVISION,
                (SOURCE_ONE, SOURCE_TWO),
                "execute published recipe",
            ),
        )
        assert batch.status is BatchStatus.PARTIAL
        assert [item.status for item in batch.attempts] == [
            BatchAttemptStatus.SUCCEEDED,
            BatchAttemptStatus.FAILED,
        ]
        first_output = batch.attempts[0].output

        retried = await service.retry_failed(CONTEXT, DECISION, batch.batch_id)
        assert retried.status is BatchStatus.SUCCEEDED
        assert len(retried.attempts) == 3
        assert retried.attempts[0].output == first_output
        assert retried.attempts[-1].attempt_no == 2
        assert retried.attempts[-1].status is BatchAttemptStatus.SUCCEEDED

    asyncio.run(scenario())


def test_incompatible_member_blocks_batch_persistence_before_execution() -> None:
    async def scenario() -> None:
        repository = _Repository()
        service = CommonBatchService(
            repository=repository,
            recipes=cast(CommonRecipeService, _Recipes()),
            outputs=cast(Any, _IncompatibleOutputs()),
        )
        with pytest.raises(CommonPipelineError, match="member ordinals: 1"):
            await service.execute(
                CONTEXT,
                DECISION,
                ExecuteBatch(
                    DataClassification.INTERNAL,
                    "blocked batch",
                    RECIPE,
                    RECIPE_REVISION,
                    (SOURCE_ONE, SOURCE_TWO),
                    "must not persist incompatible selection",
                ),
            )
        assert repository.batch is None

    asyncio.run(scenario())
