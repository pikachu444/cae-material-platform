"""Protected HTTP contract for governed tabular previews, profiles, Runs, and Datasets."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_serializer

from cmp.modules.datasets.adapters.api.datasets import (
    DatasetHttpError,
    _etag,
    _scope,
    _translate,
    _unavailable,
)
from cmp.modules.datasets.application.governed_import import (
    CreateImportProfile,
    ExecuteGovernedImport,
    GovernedDatasetSnapshot,
    GovernedImportService,
    ImportProfileSnapshot,
    ImportRun,
    PreviewTabularSource,
    ReviseImportProfile,
)
from cmp.modules.datasets.domain.governed_tabular import (
    AxisRole,
    GovernedChannelMapping,
    GovernedDatasetRepresentation,
    GovernedImportConflict,
    GovernedImportNotFound,
    GovernedImportProfileContent,
    ImportDiagnostic,
    ImportRunStatus,
    InvalidGovernedImport,
    QuantityKind,
    TabularDataSchema,
    TabularFileFormat,
    TabularPreview,
)
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.contracts.revisions import RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
type IdempotencyKey = Annotated[
    str,
    StringConstraints(min_length=1, max_length=255, pattern=r"^[!-~]+$"),
]


def _translate_governed(context: SecurityContext, error: Exception) -> DatasetHttpError:
    if isinstance(error, GovernedImportNotFound):
        return DatasetHttpError(
            context=context,
            status_code=404,
            title="Governed import resource not found",
            detail="No requested Import Profile, Run, or Dataset is visible in this tenant.",
            code="CMP-DATASET-0001",
        )
    if isinstance(error, InvalidGovernedImport):
        return DatasetHttpError(
            context=context,
            status_code=422,
            title="Invalid governed import request",
            detail=(
                "The tabular source requires explicit format, locale, channel, unit, and schema "
                "settings."
            ),
            code="CMP-DATASET-0002",
        )
    if isinstance(error, GovernedImportConflict):
        return DatasetHttpError(
            context=context,
            status_code=409,
            title="Governed import evidence conflict",
            detail="The command conflicts with exact immutable source or scope evidence.",
            code="CMP-DATASET-0003",
        )
    return _translate(context, error)


class ChannelMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    source_column: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    source_quantity: QuantityKind
    original_unit: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    axis_role: AxisRole

    def to_domain(self) -> GovernedChannelMapping:
        return GovernedChannelMapping(**self.model_dump())


class ChannelMappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    source_column: str
    source_quantity: QuantityKind
    original_unit: str
    normalized_quantity: QuantityKind
    normalized_unit: str
    axis_role: AxisRole

    @classmethod
    def from_domain(cls, value: GovernedChannelMapping) -> ChannelMappingResponse:
        return cls(
            ordinal=value.ordinal,
            source_column=value.source_column,
            source_quantity=value.source_quantity,
            original_unit=value.original_unit,
            normalized_quantity=value.normalized_quantity,
            normalized_unit=value.normalized_unit,
            axis_role=value.axis_role,
        )


class ImportProfileContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    data_schema: TabularDataSchema
    file_format: TabularFileFormat
    sheet_name: str | None = None
    header_row: int = 1
    encoding: str
    delimiter: str | None
    decimal_separator: str
    channels: Annotated[tuple[ChannelMappingInput, ...], Field(min_length=2, max_length=5)]
    initial_gauge_length_m: float | None = None
    initial_cross_section_area_m2: float | None = None
    approval_kind: str = "human_confirmed"
    schema_version: str = "1.1.0"
    deformation_mode: str | None = None

    def to_domain(self) -> GovernedImportProfileContent:
        payload = self.model_dump(exclude={"channels"})
        return GovernedImportProfileContent(
            **payload, channels=tuple(item.to_domain() for item in self.channels)
        )


class ImportProfileContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_label: str
    data_schema: TabularDataSchema
    file_format: TabularFileFormat
    sheet_name: str | None
    header_row: int
    encoding: str
    delimiter: str | None
    decimal_separator: str
    channels: tuple[ChannelMappingResponse, ...]
    initial_gauge_length_m: float | None
    initial_cross_section_area_m2: float | None
    approval_kind: str
    profile_sha256: str
    schema_version: str = "1.1.0"
    deformation_mode: str | None = None

    @model_serializer(mode="wrap")
    def _serialize_legacy_compat(self, handler: Any) -> Any:
        """Keep historical 1.0/1.1 response bytes free of later fields."""

        payload = handler(self)
        if self.schema_version not in {"1.2.0", "1.3.0"}:
            payload.pop("schema_version", None)
            payload.pop("deformation_mode", None)
        return payload

    @classmethod
    def from_domain(
        cls,
        value: GovernedImportProfileContent,
        *,
        profile_sha256: str | None = None,
    ) -> ImportProfileContentResponse:
        return cls(
            **{
                key: getattr(value, key)
                for key in (
                    "profile_label",
                    "data_schema",
                    "file_format",
                    "sheet_name",
                    "header_row",
                    "encoding",
                    "delimiter",
                    "decimal_separator",
                    "initial_gauge_length_m",
                    "initial_cross_section_area_m2",
                    "approval_kind",
                    "schema_version",
                    "deformation_mode",
                )
            },
            channels=tuple(ChannelMappingResponse.from_domain(item) for item in value.channels),
            profile_sha256=profile_sha256 or value.digest,
        )


class ImportProfileCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification
    content: ImportProfileContentInput
    change_reason: Reason


class ImportProfileReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_current_revision_id: UUID
    content: ImportProfileContentInput
    change_reason: Reason


class ImportProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    import_profile_id: UUID
    current_revision: RevisionMetadataResponse
    content: ImportProfileContentResponse

    @classmethod
    def from_snapshot(cls, value: ImportProfileSnapshot) -> ImportProfileResponse:
        return cls(
            import_profile_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(value.current.record, "draft"),
            content=ImportProfileContentResponse.from_domain(
                value.current.content,
                profile_sha256=value.current.record.content_hash,
            ),
        )


class ImportProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[ImportProfileResponse, ...]


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_asset_id: UUID
    raw_artifact_id: UUID
    file_format: TabularFileFormat
    sheet_name: str | None = None
    header_row: int = 1
    encoding: str
    delimiter: str | None = None
    decimal_separator: str = "."


class PreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_report_id: UUID
    classification: DataClassification
    raw_asset_id: UUID
    raw_artifact_id: UUID
    raw_sha256: str
    file_format: TabularFileFormat
    sheet_names: tuple[str, ...]
    selected_sheet_name: str | None
    header_row: int
    encoding: str
    delimiter: str | None
    decimal_separator: str
    header_columns: tuple[str, ...]
    sample_rows: tuple[tuple[str, ...], ...]
    status: str
    report_sha256: str

    @classmethod
    def from_domain(
        cls, preview_id: UUID, classification: DataClassification, value: TabularPreview
    ) -> PreviewResponse:
        return cls(
            preview_report_id=preview_id,
            classification=classification,
            **{
                key: getattr(value, key)
                for key in (
                    "raw_asset_id",
                    "raw_artifact_id",
                    "raw_sha256",
                    "file_format",
                    "sheet_names",
                    "selected_sheet_name",
                    "header_row",
                    "encoding",
                    "delimiter",
                    "decimal_separator",
                    "header_columns",
                    "sample_rows",
                    "status",
                )
            },
            report_sha256=value.digest,
        )


class ImportRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    import_profile_id: UUID
    import_profile_revision_id: UUID
    change_reason: Reason


class ImportDiagnosticResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int
    row_number: int | None
    column_name: str | None
    channel_key: str | None
    error_code: str
    error_detail: str
    recovery_hint: str

    @classmethod
    def from_domain(cls, value: ImportDiagnostic) -> ImportDiagnosticResponse:
        return cls(
            **{
                key: getattr(value, key)
                for key in (
                    "ordinal",
                    "row_number",
                    "column_name",
                    "channel_key",
                    "error_code",
                    "error_detail",
                    "recovery_hint",
                )
            }
        )


class GovernedImportRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    import_run_id: UUID
    classification: DataClassification
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    import_profile_id: UUID
    import_profile_revision_id: UUID
    profile_sha256: str
    idempotency_key: str
    request_sha256: str
    status: ImportRunStatus
    started_at: datetime
    finished_at: datetime | None
    raw_dataset_id: UUID | None
    raw_dataset_revision_id: UUID | None
    normalized_dataset_id: UUID | None
    normalized_dataset_revision_id: UUID | None
    row_count: int | None
    failure_code: str | None
    failure_detail: str | None
    diagnostics: tuple[ImportDiagnosticResponse, ...]

    @classmethod
    def from_domain(cls, value: ImportRun) -> GovernedImportRunResponse:
        return cls(
            import_run_id=value.id,
            classification=DataClassification(value.scope.classification),
            **{
                key: getattr(value, key)
                for key in (
                    "test_run_id",
                    "test_run_revision_id",
                    "raw_asset_id",
                    "raw_artifact_id",
                    "import_profile_id",
                    "import_profile_revision_id",
                    "profile_sha256",
                    "idempotency_key",
                    "request_sha256",
                    "status",
                    "started_at",
                    "finished_at",
                    "raw_dataset_id",
                    "raw_dataset_revision_id",
                    "normalized_dataset_id",
                    "normalized_dataset_revision_id",
                    "row_count",
                    "failure_code",
                    "failure_detail",
                )
            },
            diagnostics=tuple(
                ImportDiagnosticResponse.from_domain(item) for item in value.diagnostics
            ),
        )


class GovernedDatasetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: UUID
    current_revision: RevisionMetadataResponse
    representation: GovernedDatasetRepresentation
    data_schema: TabularDataSchema
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    data_artifact_id: UUID
    data_sha256: str
    import_profile_id: UUID
    import_profile_revision_id: UUID
    source_dataset_revision_id: UUID | None
    row_count: int
    channels: tuple[ChannelMappingResponse, ...]

    @classmethod
    def from_snapshot(cls, value: GovernedDatasetSnapshot) -> GovernedDatasetResponse:
        content = value.current.content
        return cls(
            dataset_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(value.current.record, "draft"),
            channels=tuple(ChannelMappingResponse.from_domain(item) for item in content.channels),
            **{
                key: getattr(content, key)
                for key in (
                    "representation",
                    "data_schema",
                    "test_run_id",
                    "test_run_revision_id",
                    "raw_asset_id",
                    "raw_artifact_id",
                    "data_artifact_id",
                    "data_sha256",
                    "import_profile_id",
                    "import_profile_revision_id",
                    "source_dataset_revision_id",
                    "row_count",
                )
            },
        )


class GovernedDatasetListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[GovernedDatasetResponse, ...]


def install_governed_import_api(
    application: FastAPI,
    *,
    service: GovernedImportService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Dataset permission denied."},
        404: {"description": "Governed import resource not found."},
        409: {"description": "Pinned import evidence conflicts."},
        422: {"description": "Invalid parser, profile, or row data."},
        503: {"description": "Governed importer unavailable."},
    }

    @application.post(
        "/api/v1/tabular-import-previews",
        operation_id="previewGovernedTabularImport",
        response_model=PreviewResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        responses=errors,
        tags=["datasets"],
    )
    async def preview(request: Request, body: PreviewRequest) -> PreviewResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.preview(
                context, decision, PreviewTabularSource(**body.model_dump())
            )
        except Exception as error:
            raise _translate_governed(context, error) from error
        return PreviewResponse.from_domain(*result)

    @application.post(
        "/api/v1/import-profiles",
        operation_id="createGovernedImportProfile",
        response_model=ImportProfileResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        responses=errors,
        tags=["datasets"],
    )
    def create_profile(
        request: Request, response: Response, body: ImportProfileCreateRequest
    ) -> ImportProfileResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_profile(
                context,
                decision,
                CreateImportProfile(
                    classification=body.classification,
                    content=body.content.to_domain(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate_governed(context, error) from error
        response.headers["Location"] = f"/api/v1/import-profiles/{result.id}"
        _etag(response, result.current.record)
        return ImportProfileResponse.from_snapshot(result)

    @application.get(
        "/api/v1/import-profiles",
        operation_id="listGovernedImportProfiles",
        response_model=ImportProfileListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["datasets"],
    )
    def list_profiles(request: Request) -> ImportProfileListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_profiles(context, decision)
        except Exception as error:
            raise _translate_governed(context, error) from error
        return ImportProfileListResponse(
            items=tuple(ImportProfileResponse.from_snapshot(item) for item in items)
        )

    @application.get(
        "/api/v1/import-profiles/{profile_id}",
        operation_id="getGovernedImportProfile",
        response_model=ImportProfileResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["datasets"],
    )
    def get_profile(
        request: Request, response: Response, profile_id: UUID
    ) -> ImportProfileResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_profile(context, decision, profile_id)
        except Exception as error:
            raise _translate_governed(context, error) from error
        _etag(response, result.current.record)
        return ImportProfileResponse.from_snapshot(result)

    @application.post(
        "/api/v1/import-profiles/{profile_id}/revisions",
        operation_id="reviseGovernedImportProfile",
        response_model=ImportProfileResponse,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        responses=errors,
        tags=["datasets"],
    )
    def revise_profile(
        request: Request,
        response: Response,
        profile_id: UUID,
        body: ImportProfileReviseRequest,
    ) -> ImportProfileResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.revise_profile(
                context,
                decision,
                profile_id,
                ReviseImportProfile(
                    expected_current_revision_id=body.expected_current_revision_id,
                    content=body.content.to_domain(),
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate_governed(context, error) from error
        _etag(response, result.current.record)
        return ImportProfileResponse.from_snapshot(result)

    @application.post(
        "/api/v1/tabular-import-runs",
        operation_id="executeGovernedTabularImport",
        response_model=GovernedImportRunResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        responses=errors,
        tags=["datasets"],
    )
    async def execute(
        request: Request,
        body: ImportRunRequest,
        idempotency_key: Annotated[IdempotencyKey, Header(alias="Idempotency-Key")],
    ) -> GovernedImportRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.execute(
                context,
                decision,
                ExecuteGovernedImport(**body.model_dump(), idempotency_key=idempotency_key),
            )
        except Exception as error:
            raise _translate_governed(context, error) from error
        return GovernedImportRunResponse.from_domain(result)

    @application.get(
        "/api/v1/tabular-import-runs/{run_id}",
        operation_id="getGovernedTabularImportRun",
        response_model=GovernedImportRunResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["datasets"],
    )
    def get_run(request: Request, run_id: UUID) -> GovernedImportRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_run(context, decision, run_id)
        except Exception as error:
            raise _translate_governed(context, error) from error
        return GovernedImportRunResponse.from_domain(result)

    @application.get(
        "/api/v1/governed-datasets",
        operation_id="listGovernedTabularDatasets",
        response_model=GovernedDatasetListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["datasets"],
    )
    def list_datasets(
        request: Request,
        test_run_id: UUID,
    ) -> GovernedDatasetListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_datasets_for_test_run(
                context,
                decision,
                test_run_id,
            )
        except Exception as error:
            raise _translate_governed(context, error) from error
        return GovernedDatasetListResponse(
            items=tuple(GovernedDatasetResponse.from_snapshot(value) for value in values)
        )

    @application.get(
        "/api/v1/governed-datasets/{dataset_id}",
        operation_id="getGovernedTabularDataset",
        response_model=GovernedDatasetResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        responses=errors,
        tags=["datasets"],
    )
    def get_dataset(
        request: Request, response: Response, dataset_id: UUID
    ) -> GovernedDatasetResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_dataset(context, decision, dataset_id)
        except Exception as error:
            raise _translate_governed(context, error) from error
        _etag(response, result.current.record)
        return GovernedDatasetResponse.from_snapshot(result)
