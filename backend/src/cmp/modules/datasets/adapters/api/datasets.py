"""Protected reference tensile Dataset import, revision, and curve preview resources."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.artifacts.domain.content import (
    ArtifactAccessDenied,
    ArtifactError,
    ArtifactIntegrityError,
    ArtifactNotFound,
    InvalidArtifact,
)
from cmp.modules.datasets.application.service import (
    CreateReferenceDatasetSelection,
    CurvePreview,
    DatasetSelectionSnapshot,
    DatasetService,
    DatasetSnapshot,
    ImportReferenceTensileCsv,
    ReviseReferenceDatasetSelection,
    RevisionSnapshot,
)
from cmp.modules.datasets.domain.reference_tensile import (
    DatasetConflict,
    DatasetContent,
    DatasetError,
    DatasetNotFound,
    DatasetRepresentation,
    InvalidDatasetData,
    ReferenceTensileMapping,
)
from cmp.modules.datasets.domain.selection import ReferenceDatasetSelectionContent
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateAlreadyExists, RevisionKernelError, RevisionRecord

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class ReferenceTensileMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strain_column: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    stress_column: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    strain_unit: Annotated[str, StringConstraints(pattern=r"^(1|%)$")]
    stress_unit: Annotated[str, StringConstraints(pattern=r"^(Pa|kPa|MPa|GPa)$")]

    def to_domain(self) -> ReferenceTensileMapping:
        return ReferenceTensileMapping(
            strain_column=self.strain_column,
            stress_column=self.stress_column,
            strain_unit=self.strain_unit,
            stress_unit=self.stress_unit,
        )


class ReferenceTensileImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    mapping: ReferenceTensileMappingInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceDatasetSelectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    selection_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    dataset_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceDatasetSelectionRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_current_revision_id: UUID
    dataset_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class DatasetChannelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    quantity_kind: str
    original_column: str
    original_unit: str
    normalized_unit: str
    axis_role: str


class DatasetContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    data_artifact_id: UUID
    data_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    representation: DatasetRepresentation
    source_dataset_revision_id: UUID | None
    processing_run_id: UUID | None
    point_count: int
    mapping_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    importer_id: str
    importer_version: str
    reference_only: bool
    channels: tuple[DatasetChannelResponse, ...]

    @classmethod
    def from_domain(cls, value: DatasetContent) -> DatasetContentResponse:
        return cls(
            test_run_id=value.test_run_id,
            test_run_revision_id=value.test_run_revision_id,
            raw_asset_id=value.raw_asset_id,
            raw_artifact_id=value.raw_artifact_id,
            data_artifact_id=value.data_artifact_id,
            data_sha256=value.data_sha256,
            representation=value.representation,
            source_dataset_revision_id=value.source_dataset_revision_id,
            processing_run_id=value.processing_run_id,
            point_count=value.point_count,
            mapping_sha256=value.mapping_sha256,
            importer_id=value.importer_id,
            importer_version=value.importer_version,
            reference_only=True,
            channels=(
                DatasetChannelResponse(
                    name="engineering_strain",
                    quantity_kind="engineering_strain",
                    original_column=value.mapping.strain_column,
                    original_unit=value.mapping.strain_unit,
                    normalized_unit="1",
                    axis_role="independent",
                ),
                DatasetChannelResponse(
                    name="engineering_stress",
                    quantity_kind="engineering_stress",
                    original_column=value.mapping.stress_column,
                    original_unit=value.mapping.stress_unit,
                    normalized_unit="Pa",
                    axis_role="dependent",
                ),
            ),
        )


class DatasetRevisionResponse(RevisionMetadataResponse):
    content: DatasetContentResponse

    @classmethod
    def from_snapshot(cls, value: RevisionSnapshot[DatasetContent]) -> DatasetRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=DatasetContentResponse.from_domain(value.content),
        )


class DatasetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID
    test_run_id: UUID
    current_revision: DatasetRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: DatasetSnapshot) -> DatasetResponse:
        root = f"/api/v1/datasets/{value.id}"
        return cls(
            dataset_id=value.id,
            test_run_id=value.test_run_id,
            current_revision=DatasetRevisionResponse.from_snapshot(value.current),
            links={"self": root, "revisions": f"{root}/revisions"},
        )


class DatasetListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[DatasetResponse, ...]


class DatasetRevisionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID
    revisions: tuple[DatasetRevisionResponse, ...]


class DatasetSelectionContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_kind: str
    member_count: int
    dataset_id: UUID
    dataset_revision_id: UUID

    @classmethod
    def from_domain(
        cls, value: ReferenceDatasetSelectionContent
    ) -> DatasetSelectionContentResponse:
        return cls(
            selection_kind="reference_curve_dataset_revision",
            member_count=1,
            dataset_id=value.dataset_id,
            dataset_revision_id=value.dataset_revision_id,
        )


class DatasetSelectionRevisionResponse(RevisionMetadataResponse):
    content: DatasetSelectionContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ReferenceDatasetSelectionContent]
    ) -> DatasetSelectionRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=DatasetSelectionContentResponse.from_domain(value.content),
        )


class DatasetSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_id: UUID
    selection_label: str
    current_revision: DatasetSelectionRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: DatasetSelectionSnapshot) -> DatasetSelectionResponse:
        root = f"/api/v1/dataset-selections/{value.id}"
        return cls(
            selection_id=value.id,
            selection_label=value.selection_label,
            current_revision=DatasetSelectionRevisionResponse.from_snapshot(value.current),
            links={"self": root, "revisions": f"{root}/revisions"},
        )


class DatasetSelectionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[DatasetSelectionResponse, ...]


class CurvePointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineering_strain: float
    engineering_stress: float


class CurvePreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID
    dataset_revision_id: UUID
    representation: DatasetRepresentation
    point_count: int
    returned_point_count: int
    sampled: bool
    strain_unit: str
    stress_unit: str
    points: tuple[CurvePointResponse, ...]

    @classmethod
    def from_domain(cls, value: CurvePreview) -> CurvePreviewResponse:
        return cls(
            dataset_id=value.dataset_id,
            dataset_revision_id=value.dataset_revision_id,
            representation=value.representation,
            point_count=value.point_count,
            returned_point_count=value.returned_point_count,
            sampled=value.sampled,
            strain_unit=value.strain_unit,
            stress_unit=value.stress_unit,
            points=tuple(
                CurvePointResponse(
                    engineering_strain=point.engineering_strain,
                    engineering_stress=point.engineering_stress,
                )
                for point in value.points
            ),
        )


class DatasetProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-DATASET-[0-9]{4}$")]
    trace_id: Label


class DatasetHttpError(Exception):
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
        self.problem = DatasetProblem(
            type="urn:cmp:problem:datasets",
            title=title,
            status=status_code,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("Dataset route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> DatasetHttpError:
    return DatasetHttpError(
        context=context,
        status_code=503,
        title="Dataset service unavailable",
        detail="The authoritative Dataset store or immutable Artifact store is not configured.",
        code="CMP-DATASET-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> DatasetHttpError:
    if isinstance(error, (DatasetNotFound, ArtifactNotFound)):
        return DatasetHttpError(
            context=context,
            status_code=404,
            title="Dataset resource not found",
            detail="No requested Dataset, Test Run, or source Artifact is visible in this tenant.",
            code="CMP-DATASET-0001",
        )
    if isinstance(error, (InvalidDatasetData, InvalidArtifact, ValueError)):
        return DatasetHttpError(
            context=context,
            status_code=422,
            title="Invalid Dataset request",
            detail="The reference CSV requires explicit columns, supported units, and valid data.",
            code="CMP-DATASET-0002",
        )
    if isinstance(error, (ArtifactAccessDenied, ArtifactIntegrityError)):
        return DatasetHttpError(
            context=context,
            status_code=409,
            title="Dataset source unavailable",
            detail="The immutable source Artifact is not currently usable for Dataset import.",
            code="CMP-DATASET-0003",
        )
    if isinstance(
        error,
        (DatasetConflict, AggregateAlreadyExists, RevisionKernelError, IntegrityError),
    ):
        return DatasetHttpError(
            context=context,
            status_code=409,
            title="Dataset state conflict",
            detail="The Dataset command conflicts with immutable source or revision state.",
            code="CMP-DATASET-0003",
        )
    if isinstance(error, (DatasetError, ArtifactError)):
        return DatasetHttpError(
            context=context,
            status_code=409,
            title="Dataset command rejected",
            detail="The Dataset command could not be completed.",
            code="CMP-DATASET-0003",
        )
    return DatasetHttpError(
        context=context,
        status_code=409,
        title="Dataset command rejected",
        detail="The Dataset command could not be completed.",
        code="CMP-DATASET-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_dataset_api(
    application: FastAPI,
    *,
    service: DatasetService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(DatasetHttpError)
    async def dataset_error_handler(request: Request, error: DatasetHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store", "X-Request-ID": str(error.context.request_id)},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": DatasetProblem},
        404: {"model": DatasetProblem},
        409: {"model": DatasetProblem},
        422: {"model": DatasetProblem},
        503: {"model": DatasetProblem},
    }

    @application.post(
        "/api/v1/datasets/reference-uniaxial-tensile:import",
        operation_id="importReferenceTensileDataset",
        response_model=DatasetResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["datasets"],
    )
    async def import_reference_tensile(
        request: Request, response: Response, body: ReferenceTensileImportRequest
    ) -> DatasetResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.import_reference_tensile_csv(
                context,
                decision,
                ImportReferenceTensileCsv(
                    test_run_id=body.test_run_id,
                    test_run_revision_id=body.test_run_revision_id,
                    raw_asset_id=body.raw_asset_id,
                    raw_artifact_id=body.raw_artifact_id,
                    mapping=body.mapping.to_domain(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/datasets/{result.id}"
        _etag(response, result.current.record)
        return DatasetResponse.from_snapshot(result)

    @application.post(
        "/api/v1/dataset-selections",
        operation_id="createReferenceDatasetSelection",
        response_model=DatasetSelectionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["datasets"],
    )
    def create_reference_selection(
        request: Request,
        response: Response,
        body: ReferenceDatasetSelectionCreateRequest,
    ) -> DatasetSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_dataset_selection(
                context,
                decision,
                CreateReferenceDatasetSelection(
                    classification=body.classification,
                    selection_label=body.selection_label,
                    dataset_revision_id=body.dataset_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/dataset-selections/{result.id}"
        _etag(response, result.current.record)
        return DatasetSelectionResponse.from_snapshot(result)

    @application.get(
        "/api/v1/dataset-selections/{selection_id}",
        operation_id="getDatasetSelection",
        response_model=DatasetSelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    def get_selection(
        request: Request, response: Response, selection_id: UUID
    ) -> DatasetSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_reference_dataset_selection(context, decision, selection_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return DatasetSelectionResponse.from_snapshot(result)

    @application.post(
        "/api/v1/dataset-selections/{selection_id}/revisions",
        operation_id="reviseReferenceDatasetSelection",
        response_model=DatasetSelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["datasets"],
    )
    def revise_selection(
        request: Request,
        response: Response,
        selection_id: UUID,
        body: ReferenceDatasetSelectionRevisionRequest,
    ) -> DatasetSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.revise_reference_dataset_selection(
                context,
                decision,
                selection_id,
                ReviseReferenceDatasetSelection(
                    expected_current_revision_id=body.expected_current_revision_id,
                    dataset_revision_id=body.dataset_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return DatasetSelectionResponse.from_snapshot(result)

    @application.get(
        "/api/v1/datasets/{dataset_id}",
        operation_id="getDataset",
        response_model=DatasetResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    def get_dataset(request: Request, response: Response, dataset_id: UUID) -> DatasetResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_dataset(context, decision, dataset_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return DatasetResponse.from_snapshot(result)

    @application.get(
        "/api/v1/datasets/{dataset_id}/revisions",
        operation_id="listDatasetRevisions",
        response_model=DatasetRevisionListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    def list_revisions(request: Request, dataset_id: UUID) -> DatasetRevisionListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            revisions = service.list_dataset_revisions(context, decision, dataset_id)
        except Exception as error:
            raise _translate(context, error) from error
        return DatasetRevisionListResponse(
            dataset_id=dataset_id,
            revisions=tuple(DatasetRevisionResponse.from_snapshot(item) for item in revisions),
        )

    @application.get(
        "/api/v1/material-states/{material_state_id}/datasets",
        operation_id="listMaterialStateDatasets",
        response_model=DatasetListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    def list_state_datasets(request: Request, material_state_id: UUID) -> DatasetListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_datasets_for_material_state(context, decision, material_state_id)
        except Exception as error:
            raise _translate(context, error) from error
        return DatasetListResponse(
            items=tuple(DatasetResponse.from_snapshot(item) for item in items)
        )

    @application.get(
        "/api/v1/dataset-revisions/{dataset_revision_id}/selections",
        operation_id="listDatasetRevisionSelections",
        response_model=DatasetSelectionListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    def list_revision_selections(
        request: Request, dataset_revision_id: UUID
    ) -> DatasetSelectionListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_reference_dataset_selections_for_revision(
                context,
                decision,
                dataset_revision_id,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return DatasetSelectionListResponse(
            items=tuple(DatasetSelectionResponse.from_snapshot(item) for item in items)
        )

    @application.get(
        "/api/v1/dataset-revisions/{dataset_revision_id}/curve",
        operation_id="previewDatasetCurve",
        response_model=CurvePreviewResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["datasets"],
    )
    async def preview_curve(
        request: Request,
        dataset_revision_id: UUID,
        maximum_points: Annotated[int, Query(ge=2, le=10_000)] = 1_000,
    ) -> CurvePreviewResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.preview_curve(
                context,
                decision,
                dataset_revision_id,
                maximum_points=maximum_points,
            )
        except Exception as error:
            raise _translate(context, error) from error
        return CurvePreviewResponse.from_domain(result)
