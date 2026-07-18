"""Application service for reusable, immutable common Processing Recipe revisions (T-54)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.mapping_profiles import MappingProfileService
from cmp.modules.processing.domain.common_pipeline import CommonPipelineError
from cmp.modules.processing.domain.common_recipes import (
    CommonProcessingRecipeContent,
    RecipeLifecycle,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

COMMON_RECIPE_AGGREGATE_TYPE = "processing.common_recipe"
COMMON_RECIPE_SCHEMA_ID = "urn:cmp:processing:common-recipe:1.0.0"
COMMON_RECIPE_SCHEMA_VERSION = "1.0.0"


class CommonRecipeNotFound(CommonPipelineError):
    pass


@dataclass(frozen=True, slots=True)
class CommonRecipeSnapshot:
    id: UUID
    current: RevisionRecord
    content: CommonProcessingRecipeContent


@dataclass(frozen=True, slots=True)
class CreateCommonRecipe:
    classification: DataClassification
    content: CommonProcessingRecipeContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseCommonRecipe:
    expected_current_revision_id: UUID
    content: CommonProcessingRecipeContent
    change_reason: str


class CommonRecipeRepository(Protocol):
    def recipe_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CommonProcessingRecipeContent]: ...

    def get_recipe(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
    ) -> CommonRecipeSnapshot: ...

    def get_recipe_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        revision_id: UUID,
    ) -> CommonRecipeSnapshot: ...

    def list_recipes(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[CommonRecipeSnapshot, ...]: ...


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
        raise CommonPipelineError("authorization decision lacks common Recipe capability")


class CommonRecipeService:
    def __init__(
        self,
        *,
        repository: CommonRecipeRepository,
        profiles: MappingProfileService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._profiles = profiles
        self._id = id_factory

    def _validate_profile_pin(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: str,
        content: CommonProcessingRecipeContent,
    ) -> None:
        profile = self._profiles.get_profile_revision(
            context,
            decision,
            content.mapping_profile_id,
            content.mapping_profile_revision_id,
        )
        if profile.current.scope.classification != classification:
            raise CommonPipelineError(
                "Recipe classification must match the exact Mapping Profile revision"
            )
        if profile.content.digest != content.mapping_profile_sha256:
            raise CommonPipelineError("Recipe Mapping Profile digest pin is inconsistent")

    def create_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateCommonRecipe,
    ) -> CommonRecipeSnapshot:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        if command.content.lifecycle_state is not RecipeLifecycle.DRAFT:
            raise CommonPipelineError("a new Recipe must start as draft")
        self._validate_profile_pin(
            context, decision, command.classification.value, command.content
        )
        recipe_id = self._id()
        record = RevisionService(
            aggregate_type=COMMON_RECIPE_AGGREGATE_TYPE,
            store=self._repository.recipe_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=recipe_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=COMMON_RECIPE_SCHEMA_ID,
                schema_version=COMMON_RECIPE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return CommonRecipeSnapshot(recipe_id, record, command.content)

    def revise_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        command: ReviseCommonRecipe,
    ) -> CommonRecipeSnapshot:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        current = self._repository.get_recipe(
            context=context, decision=decision, recipe_id=recipe_id
        )
        if current.content.recipe_key != command.content.recipe_key:
            raise CommonPipelineError("Recipe key cannot change across revisions")
        if (
            current.content.lifecycle_state is RecipeLifecycle.PUBLISHED
            and command.content.lifecycle_state is RecipeLifecycle.PUBLISHED
        ):
            raise CommonPipelineError(
                "a published Recipe cannot be overwritten; create a new draft revision"
            )
        self._validate_profile_pin(
            context, decision, current.current.scope.classification, command.content
        )
        record = RevisionService(
            aggregate_type=COMMON_RECIPE_AGGREGATE_TYPE,
            store=self._repository.recipe_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=recipe_id,
                scope=current.current.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=COMMON_RECIPE_SCHEMA_ID,
                schema_version=COMMON_RECIPE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return CommonRecipeSnapshot(recipe_id, record, command.content)

    def list_recipes(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[CommonRecipeSnapshot, ...]:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.list_recipes(context=context, decision=decision)

    def get_recipe(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
    ) -> CommonRecipeSnapshot:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.get_recipe(
            context=context, decision=decision, recipe_id=recipe_id
        )

    def get_recipe_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        revision_id: UUID,
    ) -> CommonRecipeSnapshot:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.get_recipe_revision(
            context=context,
            decision=decision,
            recipe_id=recipe_id,
            revision_id=revision_id,
        )
