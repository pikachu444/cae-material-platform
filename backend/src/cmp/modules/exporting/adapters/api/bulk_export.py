"""Protected API for immutable Bulk Export Selections, Jobs, and Bundles."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.exporting.application.bulk_export import (
    BulkExportBundle,
    BulkExportJob,
    BulkExportService,
    CommittedBulkExportOutput,
    CreateExportSelection,
    ExportCandidate,
    ExportSelectionSnapshot,
    RequestedExportMember,
)
from cmp.modules.exporting.domain.bulk_bundle import (
    BulkExportConflict,
    BulkExportError,
    BulkExportLimitExceeded,
    BulkExportNotFound,
    ExportMemberKind,
    ExportSelectionMember,
    ExportSelectionOmission,
    ExportSourceRef,
    InvalidBulkExport,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.contracts.revisions import RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ExportSourceRefModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ExportMemberKind
    raw_asset_id: UUID | None = None
    artifact_id: UUID | None = None
    dataset_id: UUID | None = None
    dataset_revision_id: UUID | None = None
    material_model_id: UUID | None = None
    material_model_revision_id: UUID | None = None
    solver_card_id: UUID | None = None
    solver_card_revision_id: UUID | None = None

    def domain(self) -> ExportSourceRef:
        return ExportSourceRef(
            self.kind,
            self.raw_asset_id,
            self.artifact_id,
            self.dataset_id,
            self.dataset_revision_id,
            self.material_model_id,
            self.material_model_revision_id,
            self.solver_card_id,
            self.solver_card_revision_id,
        )

    @classmethod
    def from_domain(cls, value: ExportSourceRef) -> ExportSourceRefModel:
        return cls(
            kind=value.kind,
            raw_asset_id=value.raw_asset_id,
            artifact_id=value.artifact_id,
            dataset_id=value.dataset_id,
            dataset_revision_id=value.dataset_revision_id,
            material_model_id=value.material_model_id,
            material_model_revision_id=value.material_model_revision_id,
            solver_card_id=value.solver_card_id,
            solver_card_revision_id=value.solver_card_revision_id,
        )


class ExportCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: ExportSourceRefModel
    classification: DataClassification
    source_sha256: str
    source_size_bytes: int
    media_type: str
    default_archive_path: str
    label: str

    @classmethod
    def from_domain(cls, value: ExportCandidate) -> ExportCandidateResponse:
        return cls(
            source=ExportSourceRefModel.from_domain(value.source),
            classification=value.classification,
            source_sha256=f"sha256:{value.source_sha256}",
            source_size_bytes=value.source_size_bytes,
            media_type=value.media_type,
            default_archive_path=value.default_archive_path,
            label=value.label,
        )


class ExportCandidateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ExportCandidateResponse, ...]


class RequestedExportMemberModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int = Field(ge=1, le=1000)
    source: ExportSourceRefModel
    required: bool = True
    archive_path: Annotated[str, StringConstraints(min_length=1, max_length=512)] | None = None


class CreateExportSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    selection_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    members: tuple[RequestedExportMemberModel, ...] = Field(min_length=1, max_length=1000)
    change_reason: Reason


class ExportMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    source: ExportSourceRefModel
    archive_path: str
    source_sha256: str
    source_size_bytes: int
    media_type: str
    classification: DataClassification
    label: str

    @classmethod
    def from_domain(cls, value: ExportSelectionMember) -> ExportMemberResponse:
        return cls(
            ordinal=value.ordinal,
            source=ExportSourceRefModel.from_domain(value.source),
            archive_path=value.archive_path,
            source_sha256=f"sha256:{value.source_sha256}",
            source_size_bytes=value.source_size_bytes,
            media_type=value.media_type,
            classification=value.classification,
            label=value.label,
        )


class ExportOmissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    source: ExportSourceRefModel
    reason_code: str
    reason: str

    @classmethod
    def from_domain(cls, value: ExportSelectionOmission) -> ExportOmissionResponse:
        return cls(
            ordinal=value.ordinal,
            source=ExportSourceRefModel.from_domain(value.source),
            reason_code=value.reason_code,
            reason=value.reason,
        )


class ExportSelectionContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_label: str
    classification: DataClassification
    expected_size_bytes: int
    selection_digest: str
    members: tuple[ExportMemberResponse, ...]
    omissions: tuple[ExportOmissionResponse, ...]


class ResourceLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self: str
    create_job: str | None = None
    bundle: str | None = None
    download_authorizations: str | None = None


class ExportSelectionRevisionResponse(RevisionMetadataResponse):
    content: ExportSelectionContentResponse


class ExportSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_selection_id: UUID
    current_revision: ExportSelectionRevisionResponse
    links: ResourceLinks

    @classmethod
    def from_domain(cls, value: ExportSelectionSnapshot) -> ExportSelectionResponse:
        content = value.content
        metadata = RevisionMetadataResponse.from_record(value.current, "draft")
        return cls(
            export_selection_id=value.id,
            current_revision=ExportSelectionRevisionResponse(
                **metadata.model_dump(),
                content=ExportSelectionContentResponse(
                    selection_label=content.selection_label,
                    classification=content.classification,
                    expected_size_bytes=content.expected_size_bytes,
                    selection_digest=f"sha256:{content.digest}",
                    members=tuple(
                        ExportMemberResponse.from_domain(member) for member in content.members
                    ),
                    omissions=tuple(
                        ExportOmissionResponse.from_domain(omission)
                        for omission in content.omissions
                    ),
                ),
            ),
            links=ResourceLinks(
                self=f"/api/v1/export-selections/{value.id}",
                create_job="/api/v1/export-jobs",
            ),
        )


class CreateExportJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_selection_id: UUID


class BulkExportCommittedOutputResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_commit_id: UUID
    archive_artifact_id: UUID
    archive_sha256: str
    archive_size_bytes: int
    manifest_sha256: str
    committed_at: datetime
    committed_by: UUID

    @classmethod
    def from_domain(
        cls, value: CommittedBulkExportOutput
    ) -> BulkExportCommittedOutputResponse:
        return cls(
            output_commit_id=value.id,
            archive_artifact_id=value.archive_artifact_id,
            archive_sha256=f"sha256:{value.archive_sha256}",
            archive_size_bytes=value.archive_size_bytes,
            manifest_sha256=f"sha256:{value.manifest_sha256}",
            committed_at=value.committed_at,
            committed_by=value.committed_by,
        )


class BulkExportJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_job_id: UUID
    classification: DataClassification
    export_selection_id: UUID
    export_selection_revision_id: UUID
    state: str
    attempt_count: int
    bundle_id: UUID | None
    failure_code: str | None
    failure_detail: str | None
    submitted_at: datetime
    submitted_by: UUID
    started_at: datetime | None
    completed_at: datetime | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    committed_output: BulkExportCommittedOutputResponse | None
    links: ResourceLinks

    @classmethod
    def from_domain(
        cls,
        value: BulkExportJob,
        output: CommittedBulkExportOutput | None = None,
    ) -> BulkExportJobResponse:
        return cls(
            export_job_id=value.id,
            classification=value.classification,
            export_selection_id=value.selection_id,
            export_selection_revision_id=value.selection_revision_id,
            state=value.state.value,
            attempt_count=value.attempt_count,
            bundle_id=value.bundle_id,
            failure_code=value.failure_code,
            failure_detail=value.failure_detail,
            submitted_at=value.submitted_at,
            submitted_by=value.submitted_by,
            started_at=value.started_at,
            completed_at=value.completed_at,
            lease_expires_at=value.lease_expires_at,
            heartbeat_at=value.heartbeat_at,
            committed_output=(
                BulkExportCommittedOutputResponse.from_domain(output)
                if output is not None
                else None
            ),
            links=ResourceLinks(
                self=f"/api/v1/export-jobs/{value.id}",
                bundle=(f"/api/v1/export-bundles/{value.bundle_id}" if value.bundle_id else None),
            ),
        )

class BulkExportJobListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[BulkExportJobResponse, ...]


class BulkExportBundleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_bundle_id: UUID
    classification: DataClassification
    export_selection_id: UUID
    export_selection_revision_id: UUID
    archive_artifact_id: UUID
    archive_sha256: str
    archive_size_bytes: int
    manifest_sha256: str
    component_count: int
    omission_count: int
    created_at: datetime
    created_by: UUID
    links: ResourceLinks

    @classmethod
    def from_domain(cls, value: BulkExportBundle) -> BulkExportBundleResponse:
        root = f"/api/v1/export-bundles/{value.id}"
        return cls(
            export_bundle_id=value.id,
            classification=value.classification,
            export_selection_id=value.selection_id,
            export_selection_revision_id=value.selection_revision_id,
            archive_artifact_id=value.archive_artifact_id,
            archive_sha256=f"sha256:{value.archive_sha256}",
            archive_size_bytes=value.archive_size_bytes,
            manifest_sha256=f"sha256:{value.manifest_sha256}",
            component_count=value.component_count,
            omission_count=value.omission_count,
            created_at=value.created_at,
            created_by=value.created_by,
            links=ResourceLinks(
                self=root,
                download_authorizations=f"{root}/download-authorizations",
            ),
        )


class BulkExportBundleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[BulkExportBundleResponse, ...]


class BundleDownloadAuthorizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    transfer_url: str
    transfer_token: str
    expires_at: datetime
    sha256: str
    size_bytes: int
    media_type: str


class BulkExportProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class BulkExportHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, detail: str) -> None:
        self.problem = BulkExportProblem(
            type="urn:cmp:problem:exporting:bulk-export",
            title="Bulk Export request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-BULK-EXPORT-{status_code}",
            trace_id=context.trace_id,
        )
        super().__init__(detail)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("Bulk Export dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> BulkExportHttpError:
    if isinstance(error, BulkExportNotFound):
        return BulkExportHttpError(context, 404, str(error))
    if isinstance(error, (BulkExportConflict,)):
        return BulkExportHttpError(context, 409, str(error))
    if isinstance(error, (BulkExportLimitExceeded,)):
        return BulkExportHttpError(context, 413, str(error))
    if isinstance(error, (InvalidBulkExport, ValueError)):
        return BulkExportHttpError(context, 422, str(error))
    if isinstance(error, BulkExportError):
        return BulkExportHttpError(context, 503, str(error))
    return BulkExportHttpError(context, 503, "Bulk Export service is unavailable")


def install_bulk_export_api(
    application: FastAPI,
    *,
    service: BulkExportService | None,
    artifacts: ArtifactService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(BulkExportHttpError)
    async def handle_error(_: Request, error: BulkExportHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(mode="json"), status_code=error.problem.status)

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": BulkExportProblem} for code in (404, 409, 413, 422, 503)
    }

    def require(context: SecurityContext) -> BulkExportService:
        if service is None:
            raise BulkExportHttpError(context, 503, "Bulk Export service is unavailable")
        return service

    @application.get(
        "/api/v1/bulk-export-candidates",
        operation_id="listBulkExportCandidates",
        response_model=ExportCandidateListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    async def list_candidates(request: Request, material_id: UUID) -> ExportCandidateListResponse:
        context, decision = _scope(request)
        try:
            values = await require(context).discover(context, decision, material_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ExportCandidateListResponse(
            items=tuple(ExportCandidateResponse.from_domain(value) for value in values)
        )

    @application.post(
        "/api/v1/export-selections",
        operation_id="createBulkExportSelection",
        response_model=ExportSelectionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["exporting"],
    )
    async def create_selection(
        request: Request, response: Response, body: CreateExportSelectionRequest
    ) -> ExportSelectionResponse:
        context, decision = _scope(request)
        try:
            snapshot = await require(context).create_selection(
                context,
                decision,
                CreateExportSelection(
                    body.classification,
                    body.selection_label,
                    tuple(
                        RequestedExportMember(
                            item.ordinal,
                            item.source.domain(),
                            item.required,
                            item.archive_path,
                        )
                        for item in body.members
                    ),
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/export-selections/{snapshot.id}"
        response.headers["ETag"] = (
            f'"revision:{snapshot.current.revision_no}:sha256:{snapshot.current.content_hash}"'
        )
        return ExportSelectionResponse.from_domain(snapshot)

    @application.get(
        "/api/v1/export-selections/{selection_id}",
        operation_id="getBulkExportSelection",
        response_model=ExportSelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def get_selection(request: Request, selection_id: UUID) -> ExportSelectionResponse:
        context, decision = _scope(request)
        try:
            value = require(context).get_selection(context, decision, selection_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ExportSelectionResponse.from_domain(value)

    @application.post(
        "/api/v1/export-jobs",
        operation_id="createBulkExportJob",
        response_model=BulkExportJobResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            **errors,
            status.HTTP_202_ACCEPTED: {
                "model": BulkExportJobResponse,
                "description": "Durable Job queued for external Bundle assembly.",
            },
        },
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["exporting"],
    )
    async def create_job(
        request: Request, response: Response, body: CreateExportJobRequest
    ) -> BulkExportJobResponse:
        context, decision = _scope(request)
        try:
            job, bundle = await require(context).create_job(
                context, decision, body.export_selection_id
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/export-jobs/{job.id}"
        if bundle is None:
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            response.headers["X-CMP-Bundle"] = f"/api/v1/export-bundles/{bundle.id}"
        output = require(context).get_output_commit(context, decision, job.id)
        return BulkExportJobResponse.from_domain(job, output)

    @application.get(
        "/api/v1/export-jobs",
        operation_id="listBulkExportJobs",
        response_model=BulkExportJobListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def list_jobs(request: Request) -> BulkExportJobListResponse:
        context, decision = _scope(request)
        try:
            exporting = require(context)
            values = exporting.list_jobs(context, decision)
            items = tuple(
                BulkExportJobResponse.from_domain(
                    value,
                    exporting.get_output_commit(context, decision, value.id),
                )
                for value in values
            )
        except Exception as error:
            raise _translate(context, error) from error
        return BulkExportJobListResponse(items=items)

    @application.get(
        "/api/v1/export-jobs/{job_id}",
        operation_id="getBulkExportJob",
        response_model=BulkExportJobResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def get_job(request: Request, job_id: UUID) -> BulkExportJobResponse:
        context, decision = _scope(request)
        try:
            exporting = require(context)
            value = exporting.get_job(context, decision, job_id)
            output = exporting.get_output_commit(context, decision, job_id)
        except Exception as error:
            raise _translate(context, error) from error
        return BulkExportJobResponse.from_domain(value, output)

    @application.get(
        "/api/v1/export-bundles",
        operation_id="listBulkExportBundles",
        response_model=BulkExportBundleListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def list_bundles(request: Request) -> BulkExportBundleListResponse:
        context, decision = _scope(request)
        try:
            values = require(context).list_bundles(context, decision)
        except Exception as error:
            raise _translate(context, error) from error
        return BulkExportBundleListResponse(
            items=tuple(BulkExportBundleResponse.from_domain(value) for value in values)
        )

    @application.get(
        "/api/v1/export-bundles/{bundle_id}",
        operation_id="getBulkExportBundle",
        response_model=BulkExportBundleResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def get_bundle(request: Request, bundle_id: UUID) -> BulkExportBundleResponse:
        context, decision = _scope(request)
        try:
            value = require(context).get_bundle(context, decision, bundle_id)
        except Exception as error:
            raise _translate(context, error) from error
        return BulkExportBundleResponse.from_domain(value)

    @application.post(
        "/api/v1/export-bundles/{bundle_id}/download-authorizations",
        operation_id="authorizeBulkExportBundleDownload",
        response_model=BundleDownloadAuthorizationResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    async def authorize_download(
        request: Request, bundle_id: UUID
    ) -> BundleDownloadAuthorizationResponse:
        context, decision = _scope(request)
        if artifacts is None:
            raise BulkExportHttpError(context, 503, "Artifact service is unavailable")
        try:
            bundle = require(context).get_bundle(context, decision, bundle_id)
            grant = await artifacts.issue_download_with_capability(
                context, decision, bundle.archive_artifact_id
            )
        except Exception as error:
            raise _translate(context, error) from error
        return BundleDownloadAuthorizationResponse(
            artifact_id=grant.artifact_id,
            transfer_url=grant.transfer_path,
            transfer_token=grant.token,
            expires_at=grant.expires_at,
            sha256=f"sha256:{grant.sha256}",
            size_bytes=grant.size_bytes,
            media_type=grant.media_type,
        )
