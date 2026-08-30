"""Protected Specimen, reference Test Method, and Test Run HTTP resources."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.artifacts.domain.content import (
    ArtifactAccessDenied,
    ArtifactError,
    ArtifactIntegrityError,
    ArtifactNotFound,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.application.service import (
    CreateReferenceImportMapping,
    CreateReferenceMultiaxialTensionMethod,
    CreateReferenceShearDmaFrequencySweepMethod,
    CreateReferenceShearDmaFrequencySweepRun,
    CreateReferenceShearDmaTemperatureSweepMethod,
    CreateReferenceShearDmaTemperatureSweepRun,
    CreateReferenceShearRelaxationMethod,
    CreateReferenceShearRelaxationRun,
    CreateReferenceTensileMethod,
    CreateReferenceTensileRun,
    CreateSpecimen,
    CreateSpecimenSource,
    DetectSyntheticCsvImport,
    ImportDetectionReportSnapshot,
    ImportMappingSnapshot,
    ReviseReferenceImportMapping,
    ReviseSpecimenSource,
    RevisionSnapshot,
    SpecimenSnapshot,
    SpecimenSourceSnapshot,
    TestingService,
    TestMethodSnapshot,
    TestRunSnapshot,
)
from cmp.modules.testing.domain.import_mapping import (
    ImportDetectionStatus,
    MappingSuggestionConfidence,
    ReferenceImportMappingContent,
)
from cmp.modules.testing.domain.reference_tensile import (
    InvalidTestingData,
    ReferenceTensionMode,
    SpecimenContent,
    TestingConflict,
    TestingError,
    TestingNotFound,
    TestMethodContent,
    TestRunContent,
)
from cmp.modules.testing.domain.specimen_source import (
    SpecimenSourceContent,
    SpecimenSourceLot,
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
    RevisionRecord,
)

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class SpecimenCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_state_revision_id: UUID
    specimen_code: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    orientation: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None
    preparation_note: Annotated[str, StringConstraints(min_length=1, max_length=2000)] | None = None
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class SpecimenSourceLotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_lot_id: UUID
    material_lot_revision_id: UUID
    note: Annotated[str | None, StringConstraints(min_length=1, max_length=1000)] = None

    def to_domain(self) -> SpecimenSourceLot:
        return SpecimenSourceLot(self.material_lot_id, self.material_lot_revision_id, self.note)


class SpecimenSourceContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_revision_id: UUID
    sources: tuple[SpecimenSourceLotInput, ...] = Field(min_length=1)
    note: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None

    def to_domain(self, specimen_id: UUID) -> SpecimenSourceContent:
        return SpecimenSourceContent(
            specimen_id=specimen_id,
            specimen_revision_id=self.specimen_revision_id,
            sources=tuple(item.to_domain() for item in self.sources),
            note=self.note,
        )


class SpecimenSourceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: SpecimenSourceContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class SpecimenSourceReviseRequest(SpecimenSourceCreateRequest):
    pass


class ReferenceMethodCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceMultiaxialMethodCreateRequest(ReferenceMethodCreateRequest):
    test_mode: ReferenceTensionMode


class TestRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    performed_at: datetime
    test_temperature_k: float | None = Field(default=None, gt=0.0)
    crosshead_speed_mm_per_min: float | None = Field(default=None, gt=0.0)
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ShearRelaxationRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    performed_at: datetime
    test_temperature_k: float | None = Field(default=None, gt=0.0)
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ShearDmaFrequencySweepRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    performed_at: datetime
    test_temperature_k: float | None = Field(default=None, gt=0.0)
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ShearDmaTemperatureSweepRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    performed_at: datetime
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class DetectReferenceImportRequest(BaseModel):
    """Ask the non-production header-only detector for immutable evidence."""

    model_config = ConfigDict(extra="forbid")

    raw_asset_id: UUID
    raw_artifact_id: UUID


class CreateReferenceImportMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_report_id: UUID
    mapping_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    strain_column: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    stress_column: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    strain_unit: Annotated[str, StringConstraints(min_length=1, max_length=16)]
    stress_unit: Annotated[str, StringConstraints(min_length=1, max_length=16)]
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReviseReferenceImportMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_current_revision_id: UUID
    detection_report_id: UUID
    strain_column: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    stress_column: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    strain_unit: Annotated[str, StringConstraints(min_length=1, max_length=16)]
    stress_unit: Annotated[str, StringConstraints(min_length=1, max_length=16)]
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class SpecimenContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    specimen_code: str
    orientation: str | None
    preparation_note: str | None

    @classmethod
    def from_domain(cls, value: SpecimenContent) -> SpecimenContentResponse:
        return cls(
            material_id=value.material_id,
            material_revision_id=value.material_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            specimen_code=value.specimen_code,
            orientation=value.orientation,
            preparation_note=value.preparation_note,
        )


class SpecimenSourceLotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_lot_id: UUID
    material_lot_revision_id: UUID
    note: str | None

    @classmethod
    def from_domain(cls, value: SpecimenSourceLot) -> SpecimenSourceLotResponse:
        return cls(
            material_lot_id=value.material_lot_id,
            material_lot_revision_id=value.material_lot_revision_id,
            note=value.note,
        )


class SpecimenSourceContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    specimen_revision_id: UUID
    sources: tuple[SpecimenSourceLotResponse, ...]
    note: str | None

    @classmethod
    def from_domain(cls, value: SpecimenSourceContent) -> SpecimenSourceContentResponse:
        return cls(
            specimen_id=value.specimen_id,
            specimen_revision_id=value.specimen_revision_id,
            sources=tuple(SpecimenSourceLotResponse.from_domain(item) for item in value.sources),
            note=value.note,
        )


class TestMethodContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_code: str
    display_name: str
    reference_only: bool

    @classmethod
    def from_domain(cls, value: TestMethodContent) -> TestMethodContentResponse:
        return cls(
            method_code=value.method_code,
            display_name=value.display_name,
            reference_only=value.reference_only,
        )


class TestRunContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: str
    performed_at: datetime
    test_temperature_k: float | None
    crosshead_speed_mm_per_min: float | None
    reference_only: bool
    @classmethod
    def from_domain(cls, value: TestRunContent) -> TestRunContentResponse:
        return cls(
            specimen_id=value.specimen_id,
            specimen_revision_id=value.specimen_revision_id,
            test_method_id=value.test_method_id,
            test_method_revision_id=value.test_method_revision_id,
            run_label=value.run_label,
            performed_at=value.performed_at,
            test_temperature_k=value.test_temperature_k,
            crosshead_speed_mm_per_min=value.crosshead_speed_mm_per_min,
            reference_only=value.reference_only,
        )


class ImportMappingSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str | None
    unit: str | None
    confidence: MappingSuggestionConfidence


class ImportDetectionReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    import_detection_report_id: UUID
    classification: DataClassification
    raw_asset_id: UUID
    raw_artifact_id: UUID
    raw_sha256: str
    importer_id: str
    importer_version: str
    status: ImportDetectionStatus
    header_columns: tuple[str, ...]
    strain_suggestion: ImportMappingSuggestionResponse
    stress_suggestion: ImportMappingSuggestionResponse
    report_sha256: str
    reference_only: bool
    created_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: ImportDetectionReportSnapshot) -> ImportDetectionReportResponse:
        report = value.report
        root = f"/api/v1/import-detection-reports/{value.id}"
        return cls(
            import_detection_report_id=value.id,
            classification=value.classification,
            raw_asset_id=report.raw_asset_id,
            raw_artifact_id=report.raw_artifact_id,
            raw_sha256=report.raw_sha256,
            importer_id=report.importer_id,
            importer_version=report.importer_version,
            status=report.status,
            header_columns=report.header_columns,
            strain_suggestion=ImportMappingSuggestionResponse(
                column=report.suggested_strain_column,
                unit=report.suggested_strain_unit,
                confidence=report.strain_confidence,
            ),
            stress_suggestion=ImportMappingSuggestionResponse(
                column=report.suggested_stress_column,
                unit=report.suggested_stress_unit,
                confidence=report.stress_confidence,
            ),
            report_sha256=report.digest,
            reference_only=report.reference_only,
            created_at=value.created_at,
            created_by=value.created_by,
            request_id=value.request_id,
            trace_id=value.trace_id,
            links={"self": root, "create_mapping": "/api/v1/import-mappings"},
        )


class ImportMappingContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_report_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    strain_column: str
    stress_column: str
    strain_unit: str
    stress_unit: str
    dataset_mapping_sha256: str
    importer_id: str
    importer_version: str
    approval_kind: str
    reference_only: bool

    @classmethod
    def from_domain(cls, value: ReferenceImportMappingContent) -> ImportMappingContentResponse:
        return cls(
            detection_report_id=value.detection_report_id,
            raw_asset_id=value.raw_asset_id,
            raw_artifact_id=value.raw_artifact_id,
            strain_column=value.strain_column,
            stress_column=value.stress_column,
            strain_unit=value.strain_unit,
            stress_unit=value.stress_unit,
            dataset_mapping_sha256=value.dataset_mapping_digest,
            importer_id=value.importer_id,
            importer_version=value.importer_version,
            approval_kind=value.approval_kind,
            reference_only=value.reference_only,
        )


class ImportMappingRevisionResponse(RevisionMetadataResponse):
    content: ImportMappingContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ReferenceImportMappingContent]
    ) -> ImportMappingRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=ImportMappingContentResponse.from_domain(value.content),
        )


class ImportMappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    import_mapping_id: UUID
    mapping_label: str
    current_revision: ImportMappingRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: ImportMappingSnapshot) -> ImportMappingResponse:
        root = f"/api/v1/import-mappings/{value.id}"
        return cls(
            import_mapping_id=value.id,
            mapping_label=value.current.content.mapping_label,
            current_revision=ImportMappingRevisionResponse.from_snapshot(value.current),
            links={"self": root, "revisions": f"{root}/revisions", "execute": "/api/v1/imports"},
        )


class SpecimenRevisionResponse(RevisionMetadataResponse):
    content: SpecimenContentResponse

    @classmethod
    def from_snapshot(cls, value: RevisionSnapshot[SpecimenContent]) -> SpecimenRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=SpecimenContentResponse.from_domain(value.content),
        )


class SpecimenSourceRevisionResponse(RevisionMetadataResponse):
    content: SpecimenSourceContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[SpecimenSourceContent]
    ) -> SpecimenSourceRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=SpecimenSourceContentResponse.from_domain(value.content),
        )


class TestMethodRevisionResponse(RevisionMetadataResponse):
    content: TestMethodContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[TestMethodContent]
    ) -> TestMethodRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=TestMethodContentResponse.from_domain(value.content),
        )


class TestRunRevisionResponse(RevisionMetadataResponse):
    content: TestRunContentResponse

    @classmethod
    def from_snapshot(cls, value: RevisionSnapshot[TestRunContent]) -> TestRunRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=TestRunContentResponse.from_domain(value.content),
        )


class SpecimenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    material_state_id: UUID
    current_revision: SpecimenRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: SpecimenSnapshot) -> SpecimenResponse:
        return cls(
            specimen_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=SpecimenRevisionResponse.from_snapshot(value.current),
            links={"self": f"/api/v1/specimens/{value.id}"},
        )


class SpecimenSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_source_genealogy_id: UUID
    specimen_id: UUID
    current_revision: SpecimenSourceRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: SpecimenSourceSnapshot) -> SpecimenSourceResponse:
        root = f"/api/v1/specimen-source-genealogies/{value.id}"
        return cls(
            specimen_source_genealogy_id=value.id,
            specimen_id=value.specimen_id,
            current_revision=SpecimenSourceRevisionResponse.from_snapshot(value.current),
            links={"self": root, "revisions": f"{root}/revisions"},
        )


class TestMethodResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_method_id: UUID
    current_revision: TestMethodRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: TestMethodSnapshot) -> TestMethodResponse:
        return cls(
            test_method_id=value.id,
            current_revision=TestMethodRevisionResponse.from_snapshot(value.current),
            links={"self": f"/api/v1/test-methods/{value.id}"},
        )


class TestRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_run_id: UUID
    specimen_id: UUID
    test_method_id: UUID
    current_revision: TestRunRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: TestRunSnapshot) -> TestRunResponse:
        return cls(
            test_run_id=value.id,
            specimen_id=value.specimen_id,
            test_method_id=value.test_method_id,
            current_revision=TestRunRevisionResponse.from_snapshot(value.current),
            links={"self": f"/api/v1/test-runs/{value.id}"},
        )


class SpecimenListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[SpecimenResponse, ...]


class TestMethodListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[TestMethodResponse, ...]


class TestRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[TestRunResponse, ...]


class TestingProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-TESTING-[0-9]{4}$")]
    trace_id: Label


class TestingHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status_code: int,
        title: str,
        detail: str,
        code: str,
        current_etag: RevisionETag | None = None,
    ) -> None:
        self.context = context
        self.problem = TestingProblem(
            type="urn:cmp:problem:testing",
            title=title,
            status=status_code,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        self.current_etag = current_etag
        super().__init__(title)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("Testing route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> TestingHttpError:
    return TestingHttpError(
        context=context,
        status_code=503,
        title="Testing service unavailable",
        detail="The authoritative testing store is not configured for this deployment.",
        code="CMP-TESTING-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> TestingHttpError:
    if isinstance(error, (TestingNotFound, ArtifactNotFound)):
        return TestingHttpError(
            context=context,
            status_code=404,
            title="Testing resource not found",
            detail="No requested concrete testing record is visible in the selected tenant.",
            code="CMP-TESTING-0001",
        )
    if isinstance(error, (RevisionPreconditionFailed, RevisionConflict)):
        return TestingHttpError(
            context=context,
            status_code=412,
            title="Revision precondition failed",
            detail="The immutable revision head changed; reload it before retrying.",
            code="CMP-TESTING-0004",
            current_etag=RevisionETag.from_ref(error.current),
        )
    if isinstance(error, (InvalidRevisionETag, InvalidTestingData, ValueError)):
        return TestingHttpError(
            context=context,
            status_code=422,
            title="Invalid testing request",
            detail=(
                "The reference testing record requires valid explicit fields and "
                "concrete revisions."
            ),
            code="CMP-TESTING-0002",
        )
    if isinstance(
        error,
        (TestingConflict, AggregateAlreadyExists, RevisionKernelError, IntegrityError),
    ):
        return TestingHttpError(
            context=context,
            status_code=409,
            title="Testing state conflict",
            detail="The testing command conflicts with immutable source or revision state.",
            code="CMP-TESTING-0003",
        )
    if isinstance(error, (ArtifactAccessDenied, ArtifactIntegrityError)):
        return TestingHttpError(
            context=context,
            status_code=409,
            title="Testing input unavailable",
            detail="The pinned immutable input Artifact is not currently usable for detection.",
            code="CMP-TESTING-0003",
        )
    if isinstance(error, (TestingError, ArtifactError)):
        return TestingHttpError(
            context=context,
            status_code=409,
            title="Testing command rejected",
            detail="The testing command could not be completed.",
            code="CMP-TESTING-0003",
        )
    return TestingHttpError(
        context=context,
        status_code=409,
        title="Testing command rejected",
        detail="The testing command could not be completed.",
        code="CMP-TESTING-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_testing_api(
    application: FastAPI,
    *,
    service: TestingService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(TestingHttpError)
    async def testing_error_handler(request: Request, error: TestingHttpError) -> JSONResponse:
        del request
        headers = {
            "Cache-Control": "no-store",
            "X-Request-ID": str(error.context.request_id),
        }
        if error.current_etag is not None:
            headers["ETag"] = str(error.current_etag)
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers=headers,
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": TestingProblem},
        404: {"model": TestingProblem},
        409: {"model": TestingProblem},
        412: {"model": TestingProblem},
        422: {"model": TestingProblem},
        503: {"model": TestingProblem},
    }

    @application.post(
        "/api/v1/material-states/{material_state_id}/specimens",
        operation_id="createSpecimen",
        response_model=SpecimenResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def create_specimen(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: SpecimenCreateRequest,
    ) -> SpecimenResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_specimen(
                context,
                decision,
                CreateSpecimen(
                    material_state_id,
                    body.material_state_revision_id,
                    body.specimen_code,
                    body.orientation,
                    body.preparation_note,
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/specimens/{result.id}"
        _etag(response, result.current.record)
        return SpecimenResponse.from_snapshot(result)

    @application.get(
        "/api/v1/material-states/{material_state_id}/specimens",
        operation_id="listMaterialStateSpecimens",
        response_model=SpecimenListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def list_specimens(request: Request, material_state_id: UUID) -> SpecimenListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_specimens_for_material_state(context, decision, material_state_id)
        except Exception as error:
            raise _translate(context, error) from error
        return SpecimenListResponse(
            items=tuple(SpecimenResponse.from_snapshot(item) for item in items)
        )

    @application.post(
        "/api/v1/specimens/{specimen_id}/source-genealogy",
        operation_id="createSpecimenSourceGenealogy",
        response_model=SpecimenSourceResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
        summary="Create ordered exact Material Lot sources for a Specimen revision.",
    )
    def create_specimen_source(
        request: Request,
        response: Response,
        specimen_id: UUID,
        body: SpecimenSourceCreateRequest,
    ) -> SpecimenSourceResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_specimen_source(
                context,
                decision,
                CreateSpecimenSource(body.content.to_domain(specimen_id), body.change_reason),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/specimen-source-genealogies/{result.id}"
        _etag(response, result.current.record)
        return SpecimenSourceResponse.from_snapshot(result)

    @application.get(
        "/api/v1/specimens/{specimen_id}/source-genealogy",
        operation_id="getSpecimenSourceGenealogy",
        response_model=SpecimenSourceResponse | None,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
        summary="Read exact Material Lot revisions used by the current Specimen source head.",
    )
    def get_specimen_source(
        request: Request, response: Response, specimen_id: UUID
    ) -> SpecimenSourceResponse | None:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_specimen_source_for_specimen(context, decision, specimen_id)
        except Exception as error:
            raise _translate(context, error) from error
        if result is None:
            response.headers["Cache-Control"] = "no-store"
            return None
        _etag(response, result.current.record)
        return SpecimenSourceResponse.from_snapshot(result)

    @application.post(
        "/api/v1/specimen-source-genealogies/{specimen_source_id}/revisions",
        operation_id="reviseSpecimenSourceGenealogy",
        response_model=SpecimenSourceResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
        summary="Append a Specimen source correction using a strong ETag precondition.",
    )
    def revise_specimen_source(
        request: Request,
        response: Response,
        specimen_source_id: UUID,
        body: SpecimenSourceReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> SpecimenSourceResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            current = service.get_specimen_source_for_write(context, decision, specimen_source_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            result = service.revise_specimen_source(
                context,
                decision,
                specimen_source_id,
                ReviseSpecimenSource(
                    expected,
                    body.content.to_domain(current.specimen_id),
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return SpecimenSourceResponse.from_snapshot(result)

    @application.post(
        "/api/v1/test-methods/reference-uniaxial-tensile",
        operation_id="createReferenceTensileTestMethod",
        response_model=TestMethodResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def create_reference_method(
        request: Request, response: Response, body: ReferenceMethodCreateRequest
    ) -> TestMethodResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_tensile_method(
                context,
                decision,
                CreateReferenceTensileMethod(body.classification, body.change_reason),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-methods/{result.id}"
        _etag(response, result.current.record)
        return TestMethodResponse.from_snapshot(result)

    @application.post(
        "/api/v1/test-methods/reference-shear-relaxation",
        operation_id="createReferenceShearRelaxationTestMethod",
        response_model=TestMethodResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def create_reference_shear_relaxation_method(
        request: Request, response: Response, body: ReferenceMethodCreateRequest
    ) -> TestMethodResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_shear_relaxation_method(
                context,
                decision,
                CreateReferenceShearRelaxationMethod(body.classification, body.change_reason),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-methods/{result.id}"
        _etag(response, result.current.record)
        return TestMethodResponse.from_snapshot(result)

    @application.post(
        "/api/v1/test-methods/reference-shear-dma-frequency-sweep",
        operation_id="createReferenceShearDmaFrequencySweepTestMethod",
        response_model=TestMethodResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
        summary="Create the non-production reference shear DMA frequency-sweep Test Method.",
    )
    def create_reference_shear_dma_frequency_sweep_method(
        request: Request, response: Response, body: ReferenceMethodCreateRequest
    ) -> TestMethodResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_shear_dma_frequency_sweep_method(
                context,
                decision,
                CreateReferenceShearDmaFrequencySweepMethod(
                    body.classification, body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-methods/{result.id}"
        _etag(response, result.current.record)
        return TestMethodResponse.from_snapshot(result)

    @application.post(
        "/api/v1/test-methods/reference-shear-dma-temperature-sweep",
        operation_id="createReferenceShearDmaTemperatureSweepTestMethod",
        response_model=TestMethodResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
        summary="Create a fixed-frequency shear DMA temperature-sweep Test Method.",
    )
    def create_reference_shear_dma_temperature_sweep_method(
        request: Request, response: Response, body: ReferenceMethodCreateRequest
    ) -> TestMethodResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_shear_dma_temperature_sweep_method(
                context,
                decision,
                CreateReferenceShearDmaTemperatureSweepMethod(
                    body.classification, body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-methods/{result.id}"
        _etag(response, result.current.record)
        return TestMethodResponse.from_snapshot(result)

    @application.post(
        "/api/v1/test-methods/reference-multiaxial-tension",
        operation_id="createReferenceMultiaxialTensionTestMethod",
        response_model=TestMethodResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
        summary="Register an explicit reference planar or biaxial tension method.",
    )
    def create_reference_multiaxial_tension_method(
        request: Request,
        response: Response,
        body: ReferenceMultiaxialMethodCreateRequest,
    ) -> TestMethodResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_multiaxial_tension_method(
                context,
                decision,
                CreateReferenceMultiaxialTensionMethod(
                    body.classification, body.test_mode, body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-methods/{result.id}"
        _etag(response, result.current.record)
        return TestMethodResponse.from_snapshot(result)

    @application.get(
        "/api/v1/test-methods",
        operation_id="listTestMethods",
        response_model=TestMethodListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def list_methods(request: Request) -> TestMethodListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_test_methods(context, decision)
        except Exception as error:
            raise _translate(context, error) from error
        return TestMethodListResponse(
            items=tuple(TestMethodResponse.from_snapshot(item) for item in items)
        )

    @application.post(
        "/api/v1/test-runs",
        operation_id="createReferenceTensileTestRun",
        response_model=TestRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def create_test_run(
        request: Request, response: Response, body: TestRunCreateRequest
    ) -> TestRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_tensile_run(
                context,
                decision,
                CreateReferenceTensileRun(
                    body.specimen_id,
                    body.specimen_revision_id,
                    body.test_method_id,
                    body.test_method_revision_id,
                    body.run_label,
                    body.performed_at,
                    body.test_temperature_k,
                    body.crosshead_speed_mm_per_min,
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-runs/{result.id}"
        _etag(response, result.current.record)
        return TestRunResponse.from_snapshot(result)

    @application.post(
        "/api/v1/test-runs/reference-shear-relaxation",
        operation_id="createReferenceShearRelaxationTestRun",
        response_model=TestRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def create_shear_relaxation_test_run(
        request: Request,
        response: Response,
        body: ShearRelaxationRunCreateRequest,
    ) -> TestRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_shear_relaxation_run(
                context,
                decision,
                CreateReferenceShearRelaxationRun(
                    body.specimen_id,
                    body.specimen_revision_id,
                    body.test_method_id,
                    body.test_method_revision_id,
                    body.run_label,
                    body.performed_at,
                    body.test_temperature_k,
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-runs/{result.id}"
        _etag(response, result.current.record)
        return TestRunResponse.from_snapshot(result)

    @application.post(
        "/api/v1/test-runs/reference-shear-dma-frequency-sweep",
        operation_id="createReferenceShearDmaFrequencySweepTestRun",
        response_model=TestRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
        summary="Create a reference shear DMA frequency-sweep Test Run.",
    )
    def create_shear_dma_frequency_sweep_test_run(
        request: Request,
        response: Response,
        body: ShearDmaFrequencySweepRunCreateRequest,
    ) -> TestRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_shear_dma_frequency_sweep_run(
                context,
                decision,
                CreateReferenceShearDmaFrequencySweepRun(
                    body.specimen_id,
                    body.specimen_revision_id,
                    body.test_method_id,
                    body.test_method_revision_id,
                    body.run_label,
                    body.performed_at,
                    body.test_temperature_k,
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-runs/{result.id}"
        _etag(response, result.current.record)
        return TestRunResponse.from_snapshot(result)

    @application.post(
        "/api/v1/test-runs/reference-shear-dma-temperature-sweep",
        operation_id="createReferenceShearDmaTemperatureSweepTestRun",
        response_model=TestRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
        summary="Create a fixed-frequency shear DMA temperature-sweep Test Run.",
    )
    def create_shear_dma_temperature_sweep_test_run(
        request: Request,
        response: Response,
        body: ShearDmaTemperatureSweepRunCreateRequest,
    ) -> TestRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_shear_dma_temperature_sweep_run(
                context,
                decision,
                CreateReferenceShearDmaTemperatureSweepRun(
                    body.specimen_id,
                    body.specimen_revision_id,
                    body.test_method_id,
                    body.test_method_revision_id,
                    body.run_label,
                    body.performed_at,
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-runs/{result.id}"
        _etag(response, result.current.record)
        return TestRunResponse.from_snapshot(result)

    @application.get(
        "/api/v1/test-runs/{test_run_id}",
        operation_id="getTestRun",
        response_model=TestRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def get_test_run(request: Request, test_run_id: UUID, response: Response) -> TestRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_test_run(context, decision, test_run_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return TestRunResponse.from_snapshot(result)

    @application.get(
        "/api/v1/material-states/{material_state_id}/test-runs",
        operation_id="listMaterialStateTestRuns",
        response_model=TestRunListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def list_test_runs(request: Request, material_state_id: UUID) -> TestRunListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_test_runs_for_material_state(context, decision, material_state_id)
        except Exception as error:
            raise _translate(context, error) from error
        return TestRunListResponse(
            items=tuple(TestRunResponse.from_snapshot(item) for item in items)
        )

    @application.post(
        "/api/v1/imports:detect",
        operation_id="detectReferenceImport",
        response_model=ImportDetectionReportResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    async def detect_reference_import(
        request: Request,
        response: Response,
        body: DetectReferenceImportRequest,
    ) -> ImportDetectionReportResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.detect_synthetic_csv_import(
                context,
                decision,
                DetectSyntheticCsvImport(
                    raw_asset_id=body.raw_asset_id,
                    raw_artifact_id=body.raw_artifact_id,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/import-detection-reports/{result.id}"
        response.headers["Cache-Control"] = "no-store"
        return ImportDetectionReportResponse.from_snapshot(result)

    @application.get(
        "/api/v1/import-detection-reports/{detection_report_id}",
        operation_id="getImportDetectionReport",
        response_model=ImportDetectionReportResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def get_import_detection_report(
        request: Request,
        detection_report_id: UUID,
    ) -> ImportDetectionReportResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_import_detection_report(context, decision, detection_report_id)
        except Exception as error:
            raise _translate(context, error) from error
        return ImportDetectionReportResponse.from_snapshot(result)

    @application.post(
        "/api/v1/import-mappings",
        operation_id="createReferenceImportMapping",
        response_model=ImportMappingResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def create_import_mapping(
        request: Request,
        response: Response,
        body: CreateReferenceImportMappingRequest,
    ) -> ImportMappingResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_import_mapping(
                context,
                decision,
                CreateReferenceImportMapping(
                    detection_report_id=body.detection_report_id,
                    mapping_label=body.mapping_label,
                    strain_column=body.strain_column,
                    stress_column=body.stress_column,
                    strain_unit=body.strain_unit,
                    stress_unit=body.stress_unit,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/import-mappings/{result.id}"
        _etag(response, result.current.record)
        return ImportMappingResponse.from_snapshot(result)

    @application.get(
        "/api/v1/import-mappings/{mapping_id}",
        operation_id="getImportMapping",
        response_model=ImportMappingResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def get_import_mapping(
        request: Request,
        response: Response,
        mapping_id: UUID,
    ) -> ImportMappingResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_import_mapping(context, decision, mapping_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return ImportMappingResponse.from_snapshot(result)

    @application.post(
        "/api/v1/import-mappings/{mapping_id}/revisions",
        operation_id="reviseReferenceImportMapping",
        response_model=ImportMappingResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def revise_import_mapping(
        request: Request,
        response: Response,
        mapping_id: UUID,
        body: ReviseReferenceImportMappingRequest,
    ) -> ImportMappingResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.revise_reference_import_mapping(
                context,
                decision,
                mapping_id,
                ReviseReferenceImportMapping(
                    expected_current_revision_id=body.expected_current_revision_id,
                    detection_report_id=body.detection_report_id,
                    strain_column=body.strain_column,
                    stress_column=body.stress_column,
                    strain_unit=body.strain_unit,
                    stress_unit=body.stress_unit,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return ImportMappingResponse.from_snapshot(result)
