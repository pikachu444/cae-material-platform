"""T-10 immutable Artifact metadata and scoped streaming transfer API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import (
    ArtifactAccessDenied,
    ArtifactConflict,
    ArtifactError,
    ArtifactIntegrityError,
    ArtifactKind,
    ArtifactNotFound,
    ArtifactRecord,
    ArtifactStateError,
    ArtifactTransferExpired,
    IntegrityStatus,
    InvalidArtifact,
)
from cmp.modules.artifacts.domain.uploads import ObjectStoreError
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type Dependency = Callable[..., object]


class ArtifactLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self: str
    download_token: str
    content: str


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    artifact_kind: ArtifactKind
    artifact_role: str
    schema_ref: str | None
    media_type: str
    size_bytes: int
    sha256: Sha256
    encryption_profile: str
    source_raw_asset_id: UUID | None
    created_at: datetime
    created_by: UUID
    integrity_status: IntegrityStatus
    last_checked_at: datetime
    links: ArtifactLinks

    @classmethod
    def from_record(cls, value: ArtifactRecord) -> ArtifactResponse:
        artifact = value.artifact
        root = f"/api/v1/artifacts/{artifact.id}"
        return cls(
            artifact_id=artifact.id,
            organization_id=artifact.organization_id,
            project_id=artifact.project_id,
            classification=artifact.classification,
            artifact_kind=artifact.artifact_kind,
            artifact_role=artifact.artifact_role,
            schema_ref=artifact.schema_ref,
            media_type=artifact.media_type,
            size_bytes=artifact.size_bytes,
            sha256=artifact.sha256,
            encryption_profile=artifact.encryption_profile,
            source_raw_asset_id=artifact.source_raw_asset_id,
            created_at=artifact.created_at,
            created_by=artifact.created_by,
            integrity_status=value.integrity_status,
            last_checked_at=value.last_checked_at,
            links=ArtifactLinks(
                self=root,
                download_token=f"{root}:download-token",
                content=f"{root}/content",
            ),
        )


class ArtifactDownloadGrantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    transfer_token: Annotated[
        str, StringConstraints(min_length=32, max_length=4096)
    ]
    expires_at: datetime
    transfer_path: str
    sha256: Sha256
    size_bytes: Annotated[int, Field(ge=0)]
    media_type: str


class ArtifactProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-ARTIFACT-[0-9]{4}$")]
    trace_id: Label


class ArtifactHttpError(Exception):
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
        self.problem = ArtifactProblem(
            type="urn:cmp:problem:content-artifact",
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
    if not isinstance(context, SecurityContext) or not isinstance(
        decision, AuthorizationDecision
    ):
        raise RuntimeError("Artifact route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> ArtifactHttpError:
    return ArtifactHttpError(
        context=context,
        status=503,
        title="Artifact service unavailable",
        detail="Immutable object storage is not configured for this deployment.",
        code="CMP-ARTIFACT-0006",
    )


def _translate(context: SecurityContext, error: Exception) -> ArtifactHttpError:
    if isinstance(error, ArtifactNotFound):
        return ArtifactHttpError(
            context=context,
            status=404,
            title="Artifact not found",
            detail="No Artifact is visible in the selected tenant context.",
            code="CMP-ARTIFACT-0001",
        )
    if isinstance(error, ArtifactAccessDenied):
        return ArtifactHttpError(
            context=context,
            status=403,
            title="Artifact transfer denied",
            detail="The Artifact transfer capability is invalid for this actor or tenant.",
            code="CMP-ARTIFACT-0002",
        )
    if isinstance(error, ArtifactTransferExpired):
        return ArtifactHttpError(
            context=context,
            status=410,
            title="Artifact transfer expired",
            detail="The short-lived Artifact transfer capability has expired.",
            code="CMP-ARTIFACT-0003",
        )
    if isinstance(error, (InvalidArtifact, ValueError)):
        return ArtifactHttpError(
            context=context,
            status=422,
            title="Invalid Artifact request",
            detail="The request does not satisfy the immutable Artifact contract.",
            code="CMP-ARTIFACT-0004",
        )
    if isinstance(error, ArtifactIntegrityError):
        return ArtifactHttpError(
            context=context,
            status=409,
            title="Artifact integrity unavailable",
            detail="The Artifact object is missing, corrupt, or not currently verified.",
            code="CMP-ARTIFACT-0005",
        )
    if isinstance(error, ObjectStoreError):
        return ArtifactHttpError(
            context=context,
            status=503,
            title="Object store unavailable",
            detail="The object store could not complete the Artifact operation.",
            code="CMP-ARTIFACT-0006",
        )
    if isinstance(error, (ArtifactConflict, ArtifactStateError)):
        return ArtifactHttpError(
            context=context,
            status=409,
            title="Artifact state conflict",
            detail="The Artifact command conflicts with immutable state.",
            code="CMP-ARTIFACT-0007",
        )
    return ArtifactHttpError(
        context=context,
        status=409,
        title="Artifact command rejected",
        detail="The Artifact command could not be completed.",
        code="CMP-ARTIFACT-0007",
    )


def install_content_artifact_api(
    application: FastAPI,
    *,
    service: ArtifactService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
) -> None:
    previous_validation_handler = cast(
        Callable[[Request, RequestValidationError], Awaitable[Response]],
        application.exception_handlers.get(
            RequestValidationError, request_validation_exception_handler
        ),
    )

    @application.exception_handler(ArtifactHttpError)
    async def artifact_error_handler(
        request: Request, error: ArtifactHttpError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={
                "Cache-Control": "no-store",
                "X-Request-ID": str(error.context.request_id),
            },
        )

    @application.exception_handler(RequestValidationError)
    async def artifact_validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/artifacts"):
            return cast(JSONResponse, await previous_validation_handler(request, error))
        context = getattr(request.state, "security_context", None)
        if not isinstance(context, SecurityContext):
            return await request_validation_exception_handler(request, error)
        problem = ArtifactProblem(
            type="urn:cmp:problem:content-artifact",
            title="Invalid Artifact request",
            status=422,
            detail="The request does not satisfy the immutable Artifact contract.",
            code="CMP-ARTIFACT-0004",
            trace_id=context.trace_id,
        )
        return JSONResponse(
            status_code=422,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store"},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": ArtifactProblem},
        404: {"model": ArtifactProblem},
        409: {"model": ArtifactProblem},
        410: {"model": ArtifactProblem},
        422: {"model": ArtifactProblem},
        503: {"model": ArtifactProblem},
    }

    @application.get(
        "/api/v1/artifacts/{artifact_id}",
        operation_id="getArtifact",
        response_model=ArtifactResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["artifacts"],
        summary="Read an immutable content-addressed Artifact manifest.",
    )
    def get_artifact(request: Request, artifact_id: UUID) -> ArtifactResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            record = service.get_artifact(context, decision, artifact_id)
        except (ArtifactError, ValueError) as error:
            raise _translate(context, error) from error
        return ArtifactResponse.from_record(record)

    @application.post(
        "/api/v1/artifacts/{artifact_id}:download-token",
        operation_id="issueArtifactDownloadToken",
        response_model=ArtifactDownloadGrantResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["artifacts"],
        summary="Issue an actor- and tenant-scoped short-lived transfer capability.",
    )
    async def issue_download_token(
        request: Request, response: Response, artifact_id: UUID
    ) -> ArtifactDownloadGrantResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            grant = await service.issue_download(context, decision, artifact_id)
        except (ArtifactError, ObjectStoreError, ValueError) as error:
            raise _translate(context, error) from error
        response.headers["Cache-Control"] = "private, no-store"
        return ArtifactDownloadGrantResponse(
            artifact_id=grant.artifact_id,
            transfer_token=grant.token,
            expires_at=grant.expires_at,
            transfer_path=grant.transfer_path,
            sha256=grant.sha256,
            size_bytes=grant.size_bytes,
            media_type=grant.media_type,
        )

    @application.get(
        "/api/v1/artifacts/{artifact_id}/content",
        operation_id="downloadArtifactContent",
        response_class=StreamingResponse,
        responses={
            **errors,
            200: {
                "description": "Immutable Artifact bytes.",
                "content": {
                    "application/octet-stream": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                },
            },
        },
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["artifacts"],
        summary="Stream immutable Artifact bytes without exposing the object key.",
    )
    async def download_content(
        request: Request,
        artifact_id: UUID,
        transfer_token: Annotated[
            str,
            Header(alias="Artifact-Transfer-Token", min_length=32, max_length=4096),
        ],
    ) -> StreamingResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            download = await service.open_download(
                context, decision, artifact_id, transfer_token
            )
        except (ArtifactError, ObjectStoreError, ValueError) as error:
            raise _translate(context, error) from error
        artifact = download.record.artifact
        return StreamingResponse(
            download.chunks,
            media_type=artifact.media_type,
            headers={
                "Cache-Control": "private, no-store",
                "Content-Length": str(artifact.size_bytes),
                "Content-Disposition": f'attachment; filename="artifact-{artifact.id}"',
                "X-Content-SHA256": artifact.sha256,
            },
        )
