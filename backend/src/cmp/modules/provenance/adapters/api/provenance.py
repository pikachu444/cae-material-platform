"""Protected T-13 Entity lookup and bounded lineage API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.provenance.application.lineage import ProvenanceLineageService
from cmp.modules.provenance.application.service import ProvenanceService
from cmp.modules.provenance.domain.lineage import (
    CompletenessIssue,
    CompletenessReportState,
    LineageDirection,
    LineageNode,
    LineagePage,
    ProvenanceCompletenessReport,
)
from cmp.modules.provenance.domain.model import (
    CompletenessState,
    EntityReferenceKind,
    GenerationRequirement,
    ProvenanceConflict,
    ProvenanceError,
    ProvenanceNotFound,
    ProvenanceRecord,
)

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type ReferenceType = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z][a-z0-9]*([._-][a-z0-9]+)+$",
    ),
]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type Dependency = Callable[..., object]


class EntityReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EntityReferenceKind
    type: str
    id: UUID
    sha256: Sha256


class CompletenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: CompletenessState
    issues: tuple[str, ...]


class ProvenanceLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self: str
    lineage: str
    impact: str
    completeness: str


class ProvenanceEntityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    entity_type: str
    reference: EntityReferenceResponse
    generation_requirement: GenerationRequirement
    generation_activity_id: UUID | None
    created_at: datetime
    recorded_at: datetime
    recorded_by: UUID
    completeness: CompletenessResponse
    links: ProvenanceLinks

    @classmethod
    def from_record(cls, value: ProvenanceRecord) -> ProvenanceEntityResponse:
        entity = value.entity
        root = f"/api/v1/provenance/entities/{entity.id}"
        return cls(
            entity_id=entity.id,
            organization_id=entity.scope.organization_id,
            project_id=entity.scope.project_id,
            classification=entity.scope.classification,
            entity_type=entity.entity_type,
            reference=EntityReferenceResponse(
                kind=entity.reference.kind,
                type=entity.reference.reference_type,
                id=entity.reference.reference_id,
                sha256=entity.reference.content_sha256,
            ),
            generation_requirement=entity.generation_requirement,
            generation_activity_id=value.generation_activity_id,
            created_at=entity.created_at,
            recorded_at=entity.recorded_at,
            recorded_by=entity.recorded_by,
            completeness=CompletenessResponse(
                state=value.completeness.state,
                issues=value.completeness.issues,
            ),
            links=ProvenanceLinks(
                self=root,
                lineage=f"{root}/lineage",
                impact=f"{root}/impact",
                completeness=f"{root}/completeness",
            ),
        )


class LineageNodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: UUID
    entity_type: str
    reference: EntityReferenceResponse
    generation_activity_id: UUID | None
    completeness: CompletenessResponse
    depth: Annotated[int, Field(ge=0, le=100)]
    path: tuple[UUID, ...]
    via_relation: str | None

    @classmethod
    def from_node(cls, value: LineageNode) -> LineageNodeResponse:
        record = value.record
        entity = record.entity
        return cls(
            entity_id=entity.id,
            entity_type=entity.entity_type,
            reference=EntityReferenceResponse(
                kind=entity.reference.kind,
                type=entity.reference.reference_type,
                id=entity.reference.reference_id,
                sha256=entity.reference.content_sha256,
            ),
            generation_activity_id=record.generation_activity_id,
            completeness=CompletenessResponse(
                state=record.completeness.state,
                issues=record.completeness.issues,
            ),
            depth=value.depth,
            path=value.path,
            via_relation=(value.via_relation.value if value.via_relation is not None else None),
        )


class LineagePageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_entity_id: UUID
    direction: LineageDirection
    max_depth: Annotated[int, Field(ge=1, le=20)]
    limit: Annotated[int, Field(ge=1, le=1000)]
    target_entity_type: str | None
    nodes: tuple[LineageNodeResponse, ...]
    next_cursor: str | None
    graph_truncated: bool
    total_discovered: Annotated[int, Field(ge=0, le=10000)]

    @classmethod
    def from_page(cls, value: LineagePage) -> LineagePageResponse:
        return cls(
            root_entity_id=value.root_entity_id,
            direction=value.direction,
            max_depth=value.max_depth,
            limit=value.limit,
            target_entity_type=value.target_entity_type,
            nodes=tuple(LineageNodeResponse.from_node(node) for node in value.nodes),
            next_cursor=value.next_cursor,
            graph_truncated=value.graph_truncated,
            total_discovered=value.total_discovered,
        )


class CompletenessIssueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    entity_id: UUID | None
    activity_id: UUID | None

    @classmethod
    def from_issue(cls, value: CompletenessIssue) -> CompletenessIssueResponse:
        return cls(
            code=value.code.value,
            entity_id=value.entity_id,
            activity_id=value.activity_id,
        )


class ProvenanceCompletenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_entity_id: UUID
    state: CompletenessReportState
    eligible: bool
    nodes_evaluated: Annotated[int, Field(ge=1, le=10000)]
    edges_evaluated: Annotated[int, Field(ge=0)]
    max_depth_reached: Annotated[int, Field(ge=0, le=20)]
    issues: tuple[CompletenessIssueResponse, ...]

    @classmethod
    def from_report(cls, value: ProvenanceCompletenessReport) -> ProvenanceCompletenessResponse:
        return cls(
            root_entity_id=value.root_entity_id,
            state=value.state,
            eligible=value.eligible,
            nodes_evaluated=value.nodes_evaluated,
            edges_evaluated=value.edges_evaluated,
            max_depth_reached=value.max_depth_reached,
            issues=tuple(CompletenessIssueResponse.from_issue(issue) for issue in value.issues),
        )


class ProvenanceProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-PROVENANCE-[0-9]{4}$")]
    trace_id: Label


class ProvenanceHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status: int,
        title: str,
        detail: str,
        code: str,
    ) -> None:
        self.context = context
        self.problem = ProvenanceProblem(
            type="urn:cmp:problem:provenance",
            title=title,
            status=status,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _request_scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("provenance route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> ProvenanceHttpError:
    return ProvenanceHttpError(
        context=context,
        status=503,
        title="Provenance service unavailable",
        detail="The authoritative provenance store is not configured for this deployment.",
        code="CMP-PROVENANCE-0003",
    )


def _translate(context: SecurityContext, error: Exception) -> ProvenanceHttpError:
    if isinstance(error, ProvenanceNotFound):
        return ProvenanceHttpError(
            context=context,
            status=404,
            title="Provenance Entity not found",
            detail="No Entity is visible in the selected tenant context.",
            code="CMP-PROVENANCE-0001",
        )
    if isinstance(error, ValueError):
        return ProvenanceHttpError(
            context=context,
            status=422,
            title="Invalid provenance query",
            detail="The query does not satisfy the bounded lineage contract.",
            code="CMP-PROVENANCE-0002",
        )
    if isinstance(error, ProvenanceConflict):
        return ProvenanceHttpError(
            context=context,
            status=409,
            title="Provenance query conflict",
            detail="The provenance query conflicts with immutable graph state.",
            code="CMP-PROVENANCE-0004",
        )
    return ProvenanceHttpError(
        context=context,
        status=409,
        title="Provenance query rejected",
        detail="The provenance query could not be completed.",
        code="CMP-PROVENANCE-0004",
    )


def install_provenance_api(
    application: FastAPI,
    *,
    service: ProvenanceService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    lineage_service: ProvenanceLineageService | None = None,
) -> None:
    previous_validation_handler = cast(
        Callable[[Request, RequestValidationError], Awaitable[Response]],
        application.exception_handlers.get(
            RequestValidationError, request_validation_exception_handler
        ),
    )

    @application.exception_handler(ProvenanceHttpError)
    async def provenance_error_handler(
        request: Request, error: ProvenanceHttpError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(RequestValidationError)
    async def provenance_validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/provenance"):
            return cast(JSONResponse, await previous_validation_handler(request, error))
        context = getattr(request.state, "security_context", None)
        if not isinstance(context, SecurityContext):
            return await request_validation_exception_handler(request, error)
        problem = _translate(context, ValueError("invalid query")).problem
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store"},
        )

    responses: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": ProvenanceProblem},
        404: {"model": ProvenanceProblem},
        409: {"model": ProvenanceProblem},
        422: {"model": ProvenanceProblem},
        503: {"model": ProvenanceProblem},
    }

    @application.get(
        "/api/v1/provenance/entities/by-reference",
        operation_id="findProvenanceEntityByReference",
        response_model=ProvenanceEntityResponse,
        responses=responses,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["provenance"],
        summary="Resolve one immutable provenance Entity from its typed reference.",
    )
    def find_entity_by_reference(
        request: Request,
        reference_type: ReferenceType,
        reference_id: UUID,
    ) -> ProvenanceEntityResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            record = service.find_entity_by_reference(
                context,
                decision,
                reference_type=reference_type,
                reference_id=reference_id,
            )
        except ProvenanceError as error:
            raise _translate(context, error) from error
        return ProvenanceEntityResponse.from_record(record)

    @application.get(
        "/api/v1/provenance/entities/{entity_id}",
        operation_id="getProvenanceEntity",
        response_model=ProvenanceEntityResponse,
        responses=responses,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["provenance"],
        summary="Read one immutable provenance Entity and completeness status.",
    )
    def get_entity(request: Request, entity_id: UUID) -> ProvenanceEntityResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            record = service.get_entity(context, decision, entity_id)
        except ProvenanceError as error:
            raise _translate(context, error) from error
        return ProvenanceEntityResponse.from_record(record)

    @application.get(
        "/api/v1/provenance/entities/{entity_id}/lineage",
        operation_id="getProvenanceLineage",
        response_model=LineagePageResponse,
        responses=responses,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["provenance"],
        summary="Traverse a bounded typed upstream or downstream provenance subgraph.",
    )
    def get_lineage(
        request: Request,
        entity_id: UUID,
        direction: LineageDirection = LineageDirection.UPSTREAM,
        max_depth: Annotated[int, Query(ge=1, le=20)] = 10,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        cursor: Annotated[str | None, Query(max_length=4096)] = None,
        target_entity_type: Annotated[str | None, Query(min_length=3, max_length=100)] = None,
    ) -> LineagePageResponse:
        context, decision = _request_scope(request)
        if lineage_service is None:
            raise _unavailable(context)
        try:
            page = lineage_service.query(
                context,
                decision,
                entity_id,
                direction=direction,
                max_depth=max_depth,
                limit=limit,
                cursor=cursor,
                target_entity_type=target_entity_type,
            )
        except (ProvenanceError, ValueError) as error:
            raise _translate(context, error) from error
        return LineagePageResponse.from_page(page)

    @application.get(
        "/api/v1/provenance/entities/{entity_id}/impact",
        operation_id="getProvenanceImpact",
        response_model=LineagePageResponse,
        responses=responses,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["provenance"],
        summary="Find bounded downstream impact from one immutable Entity.",
    )
    def get_impact(
        request: Request,
        entity_id: UUID,
        max_depth: Annotated[int, Query(ge=1, le=20)] = 10,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        cursor: Annotated[str | None, Query(max_length=4096)] = None,
        target_entity_type: Annotated[str | None, Query(min_length=3, max_length=100)] = None,
    ) -> LineagePageResponse:
        context, decision = _request_scope(request)
        if lineage_service is None:
            raise _unavailable(context)
        try:
            page = lineage_service.impact(
                context,
                decision,
                entity_id,
                max_depth=max_depth,
                limit=limit,
                cursor=cursor,
                target_entity_type=target_entity_type,
            )
        except (ProvenanceError, ValueError) as error:
            raise _translate(context, error) from error
        return LineagePageResponse.from_page(page)

    @application.get(
        "/api/v1/provenance/entities/{entity_id}/completeness",
        operation_id="getProvenanceCompleteness",
        response_model=ProvenanceCompletenessResponse,
        responses=responses,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["provenance"],
        summary="Evaluate the bounded upstream provenance completeness gate.",
    )
    def get_completeness(request: Request, entity_id: UUID) -> ProvenanceCompletenessResponse:
        context, decision = _request_scope(request)
        if lineage_service is None:
            raise _unavailable(context)
        try:
            report = lineage_service.completeness(context, decision, entity_id)
        except (ProvenanceError, ValueError) as error:
            raise _translate(context, error) from error
        return ProvenanceCompletenessResponse.from_report(report)
