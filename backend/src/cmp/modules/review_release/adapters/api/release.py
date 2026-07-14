"""Protected T-30 reference Release manifest/package resources."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.review_release.application.release_service import ReleaseService
from cmp.modules.review_release.domain.release import (
    CreateRelease,
    InvalidRelease,
    ReleaseConflict,
    ReleaseManifestRecord,
    ReleaseNotFound,
    ReleaseRecord,
)

type Dependency = Callable[..., object]
type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ReleaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    release_code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")]
    title: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    material_model_content_sha256: Sha256
    solver_card_id: UUID
    solver_card_revision_id: UUID
    solver_card_content_sha256: Sha256
    mapping_report_sha256: Sha256
    card_sha256: Sha256
    validation_result_id: UUID
    validation_result_sha256: Sha256
    review_request_id: UUID
    review_manifest_sha256: Sha256
    provenance_snapshot_sha256: Sha256
    reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]

    def to_domain(self) -> CreateRelease:
        return CreateRelease(**self.model_dump())


class ReleaseManifestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_manifest_id: UUID
    release_id: UUID
    manifest_sha256: Sha256
    package_sha256: Sha256
    package_size_bytes: int
    package_media_type: Literal["application/vnd.cmp.release-manifest+json"]
    state: Literal["released"]
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    material_model_content_sha256: Sha256
    solver_card_id: UUID
    solver_card_revision_id: UUID
    solver_card_content_sha256: Sha256
    mapping_report_sha256: Sha256
    card_sha256: Sha256
    validation_result_id: UUID
    validation_result_sha256: Sha256
    review_request_id: UUID
    review_manifest_sha256: Sha256
    provenance_snapshot_sha256: Sha256
    created_at: str
    created_by: UUID
    reason: str

    @classmethod
    def from_domain(cls, value: ReleaseManifestRecord) -> ReleaseManifestResponse:
        return cls(
            release_manifest_id=value.id,
            release_id=value.release_id,
            manifest_sha256=value.manifest_sha256,
            package_sha256=value.package_sha256,
            package_size_bytes=value.package_size_bytes,
            package_media_type=cast(
                Literal["application/vnd.cmp.release-manifest+json"],
                value.package_media_type,
            ),
            state=value.state.value,
            material_id=value.material_id,
            material_revision_id=value.material_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            property_set_id=value.property_set_id,
            property_set_revision_id=value.property_set_revision_id,
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            material_model_content_sha256=value.material_model_content_sha256,
            solver_card_id=value.solver_card_id,
            solver_card_revision_id=value.solver_card_revision_id,
            solver_card_content_sha256=value.solver_card_content_sha256,
            mapping_report_sha256=value.mapping_report_sha256,
            card_sha256=value.card_sha256,
            validation_result_id=value.validation_result_id,
            validation_result_sha256=value.validation_result_sha256,
            review_request_id=value.review_request_id,
            review_manifest_sha256=value.review_manifest_sha256,
            provenance_snapshot_sha256=value.provenance_snapshot_sha256,
            created_at=value.created_at.isoformat(),
            created_by=value.created_by,
            reason=value.reason,
        )


class ReleaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: UUID
    classification: DataClassification
    release_code: str
    title: str
    channel: Literal["reference"]
    created_at: str
    created_by: UUID
    manifest: ReleaseManifestResponse
    links: dict[str, str]

    @classmethod
    def from_domain(cls, value: ReleaseRecord) -> ReleaseResponse:
        return cls(
            release_id=value.id,
            classification=value.classification,
            release_code=value.release_code,
            title=value.title,
            channel=cast(Literal["reference"], value.channel),
            created_at=value.created_at.isoformat(),
            created_by=value.created_by,
            manifest=ReleaseManifestResponse.from_domain(value.manifest),
            links={
                "self": f"/api/v1/releases/{value.id}",
                "download": f"/api/v1/releases/{value.id}/download",
            },
        )


class ReleaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ReleaseResponse, ...]


class ReleaseProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: int
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-RELEASE-[0-9]{4}$")]
    trace_id: Label


class ReleaseHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status_code: int,
        title: str,
        detail: str,
        code: str,
    ) -> None:
        self.context = context
        self.problem = ReleaseProblem(
            type="urn:cmp:problem:release",
            title=title,
            status=status_code,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _scope(request: Request) -> SecurityContext:
    context = getattr(request.state, "security_context", None)
    if not isinstance(context, SecurityContext):
        raise RuntimeError("release route dependencies did not initialize request scope")
    return context


def _translate(context: SecurityContext, error: Exception) -> ReleaseHttpError:
    if isinstance(error, ReleaseNotFound):
        return ReleaseHttpError(
            context=context,
            status_code=404,
            title="Release resource not found",
            detail="No visible Release or immutable source component matches the request.",
            code="CMP-RELEASE-0001",
        )
    if isinstance(error, (InvalidRelease, ValueError)):
        return ReleaseHttpError(
            context=context,
            status_code=422,
            title="Invalid release request",
            detail="The typed release component references, digest, or reason is invalid.",
            code="CMP-RELEASE-0002",
        )
    if isinstance(error, ReleaseConflict):
        return ReleaseHttpError(
            context=context,
            status_code=409,
            title="Release completeness gate rejected",
            detail=(
                "The release is incomplete, unapproved, stale, non-integral, or conflicts with "
                "an existing immutable release."
            ),
            code="CMP-RELEASE-0003",
        )
    return ReleaseHttpError(
        context=context,
        status_code=409,
        title="Release command rejected",
        detail="The release command could not be committed.",
        code="CMP-RELEASE-0004",
    )


def _unavailable(context: SecurityContext) -> ReleaseHttpError:
    return ReleaseHttpError(
        context=context,
        status_code=503,
        title="Release service unavailable",
        detail="The release persistence boundary is not configured for this API process.",
        code="CMP-RELEASE-0005",
    )


def install_release_api(
    application: FastAPI,
    *,
    service: ReleaseService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    publish_dependency: Dependency,
) -> None:
    @application.exception_handler(ReleaseHttpError)
    async def release_error_handler(request: Request, error: ReleaseHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store", "X-Request-ID": str(error.context.request_id)},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Release read or publish is not authorized."},
        404: {"description": "No visible Release or source component matches."},
        409: {"description": "Release completeness, integrity, approval, or identity conflict."},
        422: {"description": "Typed release input is invalid."},
        503: {"description": "Release service unavailable."},
    }

    @application.post(
        "/api/v1/releases",
        operation_id="createRelease",
        response_model=ReleaseResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(publish_dependency)],
        tags=["governance", "release"],
        summary="Create one immutable reference Release after the completeness gate passes.",
    )
    def create_release(body: ReleaseCreateRequest, request: Request) -> ReleaseResponse:
        context = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create(
                context,
                request.state.authorization_decision,
                body.to_domain(),
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ReleaseResponse.from_domain(value)

    @application.get(
        "/api/v1/releases",
        operation_id="listReleases",
        response_model=ReleaseListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["governance", "release"],
        summary="List immutable reference Releases visible in the selected tenant.",
    )
    def list_releases(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> ReleaseListResponse:
        context = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list(
                context,
                request.state.authorization_decision,
                limit=limit,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ReleaseListResponse(
            items=tuple(ReleaseResponse.from_domain(value) for value in values)
        )

    @application.get(
        "/api/v1/releases/{release_id}",
        operation_id="getRelease",
        response_model=ReleaseResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["governance", "release"],
        summary="Read one immutable reference Release manifest.",
    )
    def get_release(release_id: UUID, request: Request) -> ReleaseResponse:
        context = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get(
                context,
                request.state.authorization_decision,
                release_id,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return ReleaseResponse.from_domain(value)

    @application.get(
        "/api/v1/releases/{release_id}/download",
        operation_id="downloadRelease",
        responses={**errors, 200: {"description": "Immutable release manifest package bytes."}},
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["governance", "release"],
        summary="Download the immutable reference Release package.",
    )
    def download_release(release_id: UUID, request: Request) -> Response:
        context = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get(
                context,
                request.state.authorization_decision,
                release_id,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return Response(
            content=value.package_text.encode("utf-8"),
            media_type=value.manifest.package_media_type,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{value.release_code}.cmp-release.json"'
                ),
                "ETag": f'"sha256:{value.manifest.package_sha256}"',
                "Cache-Control": "no-store",
            },
        )
