"""Streaming upload session and immutable Raw Asset HTTP resources."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.artifacts.application.uploads import (
    CancelUpload,
    CompleteUpload,
    CreateUpload,
    RecordUploadPart,
    UploadService,
)
from cmp.modules.artifacts.domain.uploads import (
    DigestMismatch,
    IngestionEvent,
    InvalidUpload,
    ObjectStoreError,
    RawAsset,
    RawAssetStorageState,
    UploadAccessDenied,
    UploadError,
    UploadExpired,
    UploadNotFound,
    UploadPart,
    UploadSession,
    UploadState,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type Dependency = Callable[..., object]


class CreateUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    original_filename: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=255,
            pattern=r"^[^/\\\x00\s](?:[^/\\\x00]*[^/\\\x00\s])?$",
        ),
    ]
    media_type: Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=255,
            pattern=r"^[^\x00\s](?:[^\x00]*[^\x00\s])?$",
        ),
    ]
    expected_size_bytes: Annotated[int, Field(ge=1, le=9223372036854775807)]
    expected_sha256: Sha256
    part_size_bytes: Annotated[int, Field(ge=1, le=536870912)] | None = None
    test_run_revision_id: UUID | None = None


class UploadPartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_number: int
    size_bytes: int
    sha256: Sha256
    storage_etag: str
    recorded_at: datetime

    @classmethod
    def from_record(cls, value: UploadPart) -> UploadPartResponse:
        return cls(
            part_number=value.part_number,
            size_bytes=value.size_bytes,
            sha256=value.sha256,
            storage_etag=value.storage_etag,
            recorded_at=value.recorded_at,
        )


class UploadLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self: str
    complete: str
    cancel: str


class UploadSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    state: UploadState
    original_filename: str
    media_type: str
    expected_size_bytes: int
    expected_sha256: Sha256
    part_size_bytes: int
    expected_part_count: int
    test_run_revision_id: UUID | None
    created_at: datetime
    expires_at: datetime
    created_by: UUID
    updated_at: datetime
    terminal_at: datetime | None
    raw_asset_id: UUID | None
    failure_code: str | None
    parts: list[UploadPartResponse]
    links: UploadLinks

    @classmethod
    def from_record(cls, value: UploadSession) -> UploadSessionResponse:
        root = f"/api/v1/uploads/{value.id}"
        return cls(
            upload_id=value.id,
            organization_id=value.organization_id,
            project_id=value.project_id,
            classification=value.classification,
            state=value.state,
            original_filename=value.original_filename,
            media_type=value.media_type,
            expected_size_bytes=value.expected_size_bytes,
            expected_sha256=value.expected_sha256,
            part_size_bytes=value.part_size_bytes,
            expected_part_count=value.expected_part_count,
            test_run_revision_id=value.test_run_revision_id,
            created_at=value.created_at,
            expires_at=value.expires_at,
            created_by=value.created_by,
            updated_at=value.updated_at,
            terminal_at=value.terminal_at,
            raw_asset_id=value.raw_asset_id,
            failure_code=value.failure_code,
            parts=[UploadPartResponse.from_record(item) for item in value.parts],
            links=UploadLinks(
                self=root,
                complete=f"{root}:complete",
                cancel=f"{root}:cancel",
            ),
        )


class CreateUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload: UploadSessionResponse
    upload_capability: Annotated[str, StringConstraints(min_length=32, max_length=4096)]


class RawAssetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_asset_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    sha256: Sha256
    size_bytes: int
    media_type: str
    original_filename: str
    storage_state: RawAssetStorageState
    created_at: datetime
    created_by: UUID
    links: dict[str, str]

    @classmethod
    def from_record(cls, value: RawAsset) -> RawAssetResponse:
        return cls(
            raw_asset_id=value.id,
            organization_id=value.organization_id,
            project_id=value.project_id,
            classification=value.classification,
            sha256=value.sha256,
            size_bytes=value.size_bytes,
            media_type=value.media_type,
            original_filename=value.original_filename,
            storage_state=value.storage_state,
            created_at=value.created_at,
            created_by=value.created_by,
            links={"self": f"/api/v1/raw-assets/{value.id}"},
        )


class IngestionEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestion_event_id: UUID
    upload_session_id: UUID
    raw_asset_id: UUID
    test_run_revision_id: UUID | None
    duplicate_content: bool
    occurred_at: datetime
    actor_id: UUID
    request_id: UUID
    trace_id: str

    @classmethod
    def from_record(cls, value: IngestionEvent) -> IngestionEventResponse:
        return cls(
            ingestion_event_id=value.id,
            upload_session_id=value.upload_session_id,
            raw_asset_id=value.raw_asset_id,
            test_run_revision_id=value.test_run_revision_id,
            duplicate_content=value.duplicate_content,
            occurred_at=value.occurred_at,
            actor_id=value.actor_id,
            request_id=value.request_id,
            trace_id=value.trace_id,
        )


class CompleteUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload: UploadSessionResponse
    raw_asset: RawAssetResponse
    ingestion_event: IngestionEventResponse
    duplicate_content: bool


class UploadProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-UPLOAD-[0-9]{4}$")]
    trace_id: Label


class UploadHttpError(Exception):
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
        self.problem = UploadProblem(
            type="urn:cmp:problem:streaming-upload",
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
        raise RuntimeError("upload route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> UploadHttpError:
    return UploadHttpError(
        context=context,
        status=503,
        title="Upload service unavailable",
        detail="Streaming object storage is not configured for this deployment.",
        code="CMP-UPLOAD-0006",
    )


def _safe_detail(error: Exception) -> str:
    if isinstance(error, ObjectStoreError):
        return "The object store could not complete the upload operation."
    detail = str(error).strip()
    return (detail or "The upload command was rejected.")[:2000]


def _translate(context: SecurityContext, error: Exception) -> UploadHttpError:
    if isinstance(error, UploadNotFound):
        return UploadHttpError(
            context=context,
            status=404,
            title="Upload resource not found",
            detail="No upload resource is visible in the selected tenant context.",
            code="CMP-UPLOAD-0001",
        )
    if isinstance(error, UploadAccessDenied):
        return UploadHttpError(
            context=context,
            status=403,
            title="Upload capability denied",
            detail="The upload capability is invalid for this actor or tenant.",
            code="CMP-UPLOAD-0002",
        )
    if isinstance(error, UploadExpired):
        return UploadHttpError(
            context=context,
            status=410,
            title="Upload capability expired",
            detail="The upload session capability has expired.",
            code="CMP-UPLOAD-0003",
        )
    if isinstance(error, (InvalidUpload, DigestMismatch, ValueError)):
        return UploadHttpError(
            context=context,
            status=422,
            title="Invalid upload manifest",
            detail=_safe_detail(error),
            code="CMP-UPLOAD-0004",
        )
    if isinstance(error, ObjectStoreError):
        return UploadHttpError(
            context=context,
            status=503,
            title="Object store unavailable",
            detail=_safe_detail(error),
            code="CMP-UPLOAD-0006",
        )
    return UploadHttpError(
        context=context,
        status=409,
        title="Upload state conflict",
        detail=_safe_detail(error),
        code="CMP-UPLOAD-0005",
    )


def install_upload_api(
    application: FastAPI,
    *,
    service: UploadService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    previous_validation_handler = cast(
        Callable[[Request, RequestValidationError], Awaitable[Response]],
        application.exception_handlers.get(
            RequestValidationError, request_validation_exception_handler
        ),
    )

    @application.exception_handler(UploadHttpError)
    async def upload_error_handler(
        request: Request, error: UploadHttpError
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
    async def upload_validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        if not (
            request.url.path.startswith("/api/v1/uploads")
            or request.url.path.startswith("/api/v1/raw-assets")
        ):
            return cast(JSONResponse, await previous_validation_handler(request, error))
        context = getattr(request.state, "security_context", None)
        if not isinstance(context, SecurityContext):
            return await request_validation_exception_handler(request, error)
        problem = UploadProblem(
            type="urn:cmp:problem:streaming-upload",
            title="Invalid upload request",
            status=422,
            detail="The request does not satisfy the streaming upload contract.",
            code="CMP-UPLOAD-0004",
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
        403: {"model": UploadProblem},
        404: {"model": UploadProblem},
        409: {"model": UploadProblem},
        410: {"model": UploadProblem},
        422: {"model": UploadProblem},
        503: {"model": UploadProblem},
    }

    @application.post(
        "/api/v1/uploads",
        operation_id="createUploadSession",
        response_model=CreateUploadResponse,
        status_code=201,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["artifacts"],
        summary="Create a resumable, digest-pinned multipart upload session.",
    )
    async def create_upload(
        request: Request,
        response: Response,
        body: CreateUploadRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=255,
                pattern=r"^[\x21-\x7e]+$",
            ),
        ],
    ) -> CreateUploadResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.create(
                context,
                decision,
                CreateUpload(
                    classification=body.classification,
                    original_filename=body.original_filename,
                    media_type=body.media_type,
                    expected_size_bytes=body.expected_size_bytes,
                    expected_sha256=body.expected_sha256,
                    part_size_bytes=body.part_size_bytes,
                    test_run_revision_id=body.test_run_revision_id,
                    idempotency_key=idempotency_key,
                ),
            )
        except (UploadError, ValueError) as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/uploads/{result.session.id}"
        response.headers["Idempotent-Replay"] = "true" if result.replayed else "false"
        response.headers["Cache-Control"] = "no-store"
        return CreateUploadResponse(
            upload=UploadSessionResponse.from_record(result.session),
            upload_capability=result.capability,
        )

    @application.get(
        "/api/v1/uploads/{upload_id}",
        operation_id="getUploadSession",
        response_model=UploadSessionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["artifacts"],
    )
    def get_upload(request: Request, upload_id: UUID) -> UploadSessionResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_upload(context, decision, upload_id)
        except (UploadError, ValueError) as error:
            raise _translate(context, error) from error
        return UploadSessionResponse.from_record(value)

    @application.put(
        "/api/v1/uploads/{upload_id}/parts/{part_number}",
        operation_id="uploadPart",
        response_model=UploadSessionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["artifacts"],
        summary="Stream one immutable multipart chunk without buffering the whole object.",
    )
    async def upload_part(
        request: Request,
        upload_id: UUID,
        part_number: Annotated[int, Field(ge=1, le=100000)],
        upload_capability: Annotated[
            str,
            Header(alias="Upload-Capability", min_length=32, max_length=4096),
        ],
    ) -> UploadSessionResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.record_part(
                context,
                decision,
                RecordUploadPart(upload_id, part_number, upload_capability),
                request.stream(),
            )
        except (UploadError, ValueError) as error:
            raise _translate(context, error) from error
        return UploadSessionResponse.from_record(value)

    @application.post(
        "/api/v1/uploads/{upload_id}:complete",
        operation_id="completeUpload",
        response_model=CompleteUploadResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["artifacts"],
    )
    async def complete_upload(
        request: Request,
        upload_id: UUID,
        upload_capability: Annotated[
            str,
            Header(alias="Upload-Capability", min_length=32, max_length=4096),
        ],
    ) -> CompleteUploadResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.complete(
                context, decision, CompleteUpload(upload_id, upload_capability)
            )
        except (UploadError, ValueError) as error:
            raise _translate(context, error) from error
        return CompleteUploadResponse(
            upload=UploadSessionResponse.from_record(value.session),
            raw_asset=RawAssetResponse.from_record(value.raw_asset),
            ingestion_event=IngestionEventResponse.from_record(
                value.ingestion_event
            ),
            duplicate_content=value.duplicate_content,
        )

    @application.post(
        "/api/v1/uploads/{upload_id}:cancel",
        operation_id="cancelUpload",
        response_model=UploadSessionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["artifacts"],
    )
    async def cancel_upload(
        request: Request,
        upload_id: UUID,
        upload_capability: Annotated[
            str,
            Header(alias="Upload-Capability", min_length=32, max_length=4096),
        ],
    ) -> UploadSessionResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.cancel(
                context, decision, CancelUpload(upload_id, upload_capability)
            )
        except (UploadError, ValueError) as error:
            raise _translate(context, error) from error
        return UploadSessionResponse.from_record(value)

    @application.get(
        "/api/v1/raw-assets/{raw_asset_id}",
        operation_id="getRawAsset",
        response_model=RawAssetResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["artifacts"],
    )
    def get_raw_asset(request: Request, raw_asset_id: UUID) -> RawAssetResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_raw_asset(context, decision, raw_asset_id)
        except (UploadError, ValueError) as error:
            raise _translate(context, error) from error
        return RawAssetResponse.from_record(value)
