"""Protected HTTP resources for reusable common Processing Recipes (T-54)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.adapters.api.common_pipeline import ProcessingStepInput
from cmp.modules.processing.application.common_recipes import (
    CommonRecipeNotFound,
    CommonRecipeService,
    CommonRecipeSnapshot,
    CreateCommonRecipe,
    ReviseCommonRecipe,
)
from cmp.modules.processing.domain.common_pipeline import (
    MAX_PIPELINE_STEPS,
    CommonPipelineError,
)
from cmp.modules.processing.domain.common_recipes import (
    CommonProcessingRecipeContent,
    RecipeLifecycle,
)
from cmp.shared.contracts.revisions import (
    InvalidRevisionETag,
    RevisionETag,
    RevisionMetadataResponse,
    RevisionPreconditionFailed,
    require_matching_if_match,
)
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    RevisionConflict,
    RevisionKernelError,
)

type Dependency = Callable[..., object]
type Text160 = Annotated[str, StringConstraints(min_length=1, max_length=160)]
type Text200 = Annotated[str, StringConstraints(min_length=1, max_length=200)]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CommonRecipeContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe_key: Text160
    label: Text200
    description: Reason | None = None
    mapping_profile_id: UUID
    mapping_profile_revision_id: UUID
    mapping_profile_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    steps: Annotated[
        tuple[ProcessingStepInput, ...], Field(min_length=1, max_length=MAX_PIPELINE_STEPS)
    ]
    lifecycle_state: RecipeLifecycle = RecipeLifecycle.DRAFT

    def to_domain(self) -> CommonProcessingRecipeContent:
        return CommonProcessingRecipeContent(
            recipe_key=self.recipe_key,
            label=self.label,
            description=self.description,
            mapping_profile_id=self.mapping_profile_id,
            mapping_profile_revision_id=self.mapping_profile_revision_id,
            mapping_profile_sha256=self.mapping_profile_sha256,
            steps=tuple(item.to_domain() for item in self.steps),
            lifecycle_state=self.lifecycle_state,
        )

    @classmethod
    def from_domain(cls, value: CommonProcessingRecipeContent) -> CommonRecipeContentInput:
        return cls(
            recipe_key=value.recipe_key,
            label=value.label,
            description=value.description,
            mapping_profile_id=value.mapping_profile_id,
            mapping_profile_revision_id=value.mapping_profile_revision_id,
            mapping_profile_sha256=value.mapping_profile_sha256,
            steps=tuple(
                ProcessingStepInput(
                    method_id=item.method_id,
                    method_version=item.method_version,
                    options=item.options,
                )
                for item in value.steps
            ),
            lifecycle_state=value.lifecycle_state,
        )


class CreateCommonRecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification
    content: CommonRecipeContentInput
    change_reason: Reason


class ReviseCommonRecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: CommonRecipeContentInput
    change_reason: Reason


class CommonRecipeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processing_recipe_id: UUID
    current_revision: RevisionMetadataResponse
    content: CommonRecipeContentInput

    @classmethod
    def from_snapshot(cls, value: CommonRecipeSnapshot) -> CommonRecipeResponse:
        return cls(
            processing_recipe_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(
                value.current, value.content.lifecycle_state.value
            ),
            content=CommonRecipeContentInput.from_domain(value.content),
        )


class CommonRecipeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[CommonRecipeResponse, ...]


def install_common_recipe_api(
    app: FastAPI,
    *,
    service: CommonRecipeService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    def scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
        context = getattr(request.state, "security_context", None)
        decision = getattr(request.state, "authorization_decision", None)
        if not isinstance(context, SecurityContext) or not isinstance(
            decision, AuthorizationDecision
        ):
            raise RuntimeError("Recipe dependencies did not initialize request scope")
        return context, decision

    def etag(response: Response, snapshot: CommonRecipeSnapshot) -> None:
        response.headers["ETag"] = str(RevisionETag.from_ref(snapshot.current.ref))
        response.headers["Cache-Control"] = "no-store"

    def require_service() -> CommonRecipeService:
        if service is None:
            raise HTTPException(status_code=503, detail="common Recipe store unavailable")
        return service

    @app.post(
        "/api/v1/common-processing-recipes",
        response_model=CommonRecipeResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-recipes"],
    )
    def create_recipe(
        body: CreateCommonRecipeRequest, request: Request, response: Response
    ) -> CommonRecipeResponse:
        context, decision = scope(request)
        try:
            snapshot = require_service().create_recipe(
                context,
                decision,
                CreateCommonRecipe(
                    body.classification, body.content.to_domain(), body.change_reason
                ),
            )
        except (CommonPipelineError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except (AggregateAlreadyExists, IntegrityError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        etag(response, snapshot)
        return CommonRecipeResponse.from_snapshot(snapshot)

    @app.get(
        "/api/v1/common-processing-recipes",
        response_model=CommonRecipeListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-recipes"],
    )
    def list_recipes(request: Request) -> CommonRecipeListResponse:
        context, decision = scope(request)
        return CommonRecipeListResponse(
            items=tuple(
                CommonRecipeResponse.from_snapshot(item)
                for item in require_service().list_recipes(context, decision)
            )
        )

    @app.get(
        "/api/v1/common-processing-recipes/{recipe_id}",
        response_model=CommonRecipeResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["processing-recipes"],
    )
    def get_recipe(
        recipe_id: UUID, request: Request, response: Response
    ) -> CommonRecipeResponse:
        context, decision = scope(request)
        try:
            snapshot = require_service().get_recipe(context, decision, recipe_id)
        except CommonRecipeNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        etag(response, snapshot)
        return CommonRecipeResponse.from_snapshot(snapshot)

    @app.post(
        "/api/v1/common-processing-recipes/{recipe_id}/revisions",
        response_model=CommonRecipeResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["processing-recipes"],
    )
    def revise_recipe(
        recipe_id: UUID,
        body: ReviseCommonRecipeRequest,
        request: Request,
        response: Response,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> CommonRecipeResponse:
        context, decision = scope(request)
        resolved = require_service()
        try:
            current = resolved.get_recipe(context, decision, recipe_id)
            expected = require_matching_if_match(if_match, current.current.ref)
            snapshot = resolved.revise_recipe(
                context,
                decision,
                recipe_id,
                ReviseCommonRecipe(expected, body.content.to_domain(), body.change_reason),
            )
        except InvalidRevisionETag as error:
            raise HTTPException(status_code=428, detail=str(error)) from error
        except RevisionPreconditionFailed as error:
            raise HTTPException(status_code=412, detail=str(error)) from error
        except CommonRecipeNotFound as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (RevisionConflict, RevisionKernelError, IntegrityError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (CommonPipelineError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        etag(response, snapshot)
        return CommonRecipeResponse.from_snapshot(snapshot)
