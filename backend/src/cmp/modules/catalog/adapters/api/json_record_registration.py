"""HTTP boundary for installed-format JSON Catalog Record registration."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain import ArtifactKind
from cmp.modules.catalog.adapters.api.catalog import CatalogHttpError, _scope
from cmp.modules.catalog.application.json_record_registration import (
    JsonRecordRegistrationService,
    JsonRegistrationSaveResult,
)
from cmp.modules.catalog.domain.json_record_registration import (
    JSON_MEDIA_TYPE,
    JSON_PACKAGE_MEDIA_TYPE,
    MAX_PACKAGE_ARCHIVE_BYTES,
    MAX_SINGLE_JSON_BYTES,
    JsonRegistrationFile,
    verify_registration_package,
)
from cmp.modules.identity_access.domain.authorization import DataClassification

type Dependency = Callable[..., object]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


LiteralJsonMediaType = Annotated[
    str,
    StringConstraints(pattern=r"^application/(json|zip)$"),
]


class JsonRegistrationArtifactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    artifact_id: UUID
    sha256: Sha256
    media_type: LiteralJsonMediaType = JSON_MEDIA_TYPE


class JsonReferencePinInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    pointer: Annotated[str, StringConstraints(pattern=r"^/", max_length=2000)]
    identifier: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    record_id: UUID
    revision_id: UUID
    content_hash: Sha256


class JsonDomainBindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    component: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    kind: Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=r"^[a-z_]+$")]
    object_id: UUID
    revision_id: UUID


class JsonRegistrationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format_revision_id: UUID | None = None
    classification: DataClassification = DataClassification.INTERNAL
    files: tuple[JsonRegistrationArtifactInput, ...] = Field(min_length=1, max_length=100)
    reference_pins: tuple[JsonReferencePinInput, ...] = ()
    domain_bindings: tuple[JsonDomainBindingInput, ...] = ()


class JsonRegistrationSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format_revision_id: UUID | None = None
    package_sha256: Sha256
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    reference_pins: tuple[JsonReferencePinInput, ...] = ()
    domain_bindings: tuple[JsonDomainBindingInput, ...] | None = None


class JsonRegistrationFormatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[dict[str, Any], ...]


def _pins(
    values: tuple[JsonReferencePinInput, ...],
) -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    for item in values:
        pin = {
            "identifier": item.identifier,
            "record_id": str(item.record_id),
            "revision_id": str(item.revision_id),
            "content_hash": item.content_hash,
        }
        result[(item.file, item.pointer)] = pin
        result[(item.file, item.identifier)] = pin
    return result


def _domain_bindings(
    values: tuple[JsonDomainBindingInput, ...],
) -> tuple[tuple[str, str, str, UUID, UUID], ...]:
    return tuple(
        (item.file, item.component, item.kind, item.object_id, item.revision_id)
        for item in values
    )


def _problem_detail(error: Exception) -> str:
    detail = str(error).strip()
    return (detail or "The JSON registration command was rejected.")[:2000]


def _error(context: Any, error: Exception) -> CatalogHttpError:
    detail = _problem_detail(error)
    if "not configured" in detail or "unavailable" in detail:
        return CatalogHttpError(
            context=context,
            status_code=503,
            title="JSON Record registration unavailable",
            detail=detail,
            code="CMP-CATALOG-0030",
        )
    if isinstance(error, ValueError):
        return CatalogHttpError(
            context=context,
            status_code=422,
            title="Invalid JSON Record registration request",
            detail=detail,
            code="CMP-CATALOG-0032",
        )
    return CatalogHttpError(
        context=context,
        status_code=409,
        title="JSON Record registration rejected",
        detail=detail,
        code="CMP-CATALOG-0031",
    )


def install_json_record_registration_api(
    application: FastAPI,
    *,
    service: JsonRecordRegistrationService | None,
    artifact_service: ArtifactService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    """Install only additive JSON routes; legacy tabular routes remain in records.py."""

    def required(context: Any) -> JsonRecordRegistrationService:
        if service is None:
            raise CatalogHttpError(
                context=context,
                status_code=503,
                title="JSON Record registration unavailable",
                detail="The installed-format JSON Record service is not configured.",
                code="CMP-CATALOG-0030",
            )
        return service

    @application.get(
        "/api/v1/catalog/json-record-formats",
        response_model=JsonRegistrationFormatsResponse,
        operation_id="listInstalledJsonRecordFormats",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-records"],
    )
    async def list_formats(request: Request) -> JsonRegistrationFormatsResponse:
        context, decision = _scope(request)
        try:
            value = await required(context).list_formats_async(context, decision)
            return JsonRegistrationFormatsResponse(items=tuple(item.response() for item in value))
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/json-record-registrations:preview",
        operation_id="previewCatalogJsonRecordRegistration",
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-records"],
    )
    async def preview_json_registration(
        request: Request, body: JsonRegistrationPreviewRequest
    ) -> dict[str, Any]:
        context, decision = _scope(request)
        if artifact_service is None:
            raise _error(context, RuntimeError("immutable Artifact reader is unavailable"))
        try:
            files: list[JsonRegistrationFile] = []
            package_artifact_id: UUID | None = None
            if len(body.files) > 1 and any(
                item.media_type != JSON_PACKAGE_MEDIA_TYPE for item in body.files
            ):
                raise ValueError(
                    "multiple JSON files must be uploaded as one canonical deterministic ZIP"
                )
            for item in body.files:
                artifact_record, raw = await artifact_service.read_verified_bytes(
                    context,
                    decision,
                    item.artifact_id,
                    maximum_bytes=MAX_PACKAGE_ARCHIVE_BYTES,
                )
                artifact = artifact_record.artifact
                if artifact.artifact_kind is not ArtifactKind.RAW:
                    raise ValueError(f"{item.filename}: JSON registration requires a Raw Artifact")
                if artifact.classification != body.classification:
                    raise ValueError(
                        f"{item.filename}: Artifact classification does not match "
                        "the requested batch"
                    )
                if artifact.media_type != item.media_type or artifact.sha256 != item.sha256:
                    raise ValueError(
                        f"{item.filename}: media type or SHA-256 does not match the Artifact"
                    )
                if item.media_type == JSON_PACKAGE_MEDIA_TYPE:
                    if len(body.files) != 1:
                        raise ValueError("a JSON package must be uploaded as the only source item")
                    package_artifact_id = item.artifact_id
                    files.extend(
                        JsonRegistrationFile(
                            component.filename,
                            component.content,
                            JSON_MEDIA_TYPE,
                            None,
                            component.sha256,
                            component.package_path,
                        )
                        for component in verify_registration_package(
                            raw, expected_classification=body.classification.value
                        )
                    )
                else:
                    if len(body.files) != 1:
                        raise ValueError(
                            "multiple raw JSON Artifacts are not accepted; upload one canonical ZIP"
                        )
                    if len(raw) > MAX_SINGLE_JSON_BYTES:
                        raise ValueError(
                            "one raw JSON source must not exceed 25 MiB; upload a canonical ZIP"
                        )
                    files.append(
                        JsonRegistrationFile(
                            item.filename,
                            raw,
                            JSON_MEDIA_TYPE,
                            str(item.artifact_id),
                            item.sha256,
                        )
                    )
            value = await required(context).preview_async(
                context,
                decision,
                format_revision_id=body.format_revision_id,
                files=files,
                classification=body.classification,
                reference_pins=_pins(body.reference_pins),
                domain_bindings=_domain_bindings(body.domain_bindings),
                package_artifact_id=package_artifact_id,
                package_sha256=(
                    body.files[0].sha256
                    if package_artifact_id is not None and body.files
                    else None
                ),
            )
            return value.as_dict()
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.post(
        "/api/v1/catalog/json-record-registrations/{preview_token}:save",
        operation_id="saveCatalogJsonRecordRegistration",
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-records"],
    )
    async def save_json_registration(
        request: Request, preview_token: str, body: JsonRegistrationSaveRequest
    ) -> dict[str, Any]:
        context, decision = _scope(request)
        try:
            value: JsonRegistrationSaveResult = await required(context).save_async(
                context,
                decision,
                token=preview_token,
                format_revision_id=body.format_revision_id,
                package_sha256=body.package_sha256,
                change_reason=body.change_reason,
                reference_pins=_pins(body.reference_pins),
                domain_bindings=(
                    _domain_bindings(body.domain_bindings)
                    if body.domain_bindings is not None
                    else None
                ),
            )
            return value.as_dict()
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/records/{record_id}/revisions/{record_revision_id}/source-availability",
        operation_id="getExactJsonCatalogRecordSourceAvailability",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-records"],
    )
    async def source_availability(
        request: Request,
        record_id: UUID,
        record_revision_id: UUID,
    ) -> dict[str, bool]:
        context, decision = _scope(request)
        try:
            return await required(context).source_availability_async(
                context,
                decision,
                record_id=record_id,
                revision_id=record_revision_id,
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/records/{record_id}/revisions/{record_revision_id}/source.json",
        operation_id="downloadExactJsonCatalogRecordSource",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-records"],
    )
    async def download_json_source(
        request: Request,
        record_id: UUID,
        record_revision_id: UUID,
        published_only: bool = Query(default=False),
    ) -> Response:
        context, decision = _scope(request)
        try:
            filename, media_type, value = await required(context).source_download_async(
                context,
                decision,
                record_id=record_id,
                revision_id=record_revision_id,
                published_only=published_only,
            )
            response = Response(content=value, media_type=media_type)
            response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            response.headers["X-Content-SHA256"] = hashlib.sha256(value).hexdigest()
            return response
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error

    @application.get(
        "/api/v1/catalog/records/{record_id}/revisions/{record_revision_id}/source.csv",
        operation_id="downloadExactJsonCatalogRecordSourceCsv",
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog-records"],
    )
    async def download_csv_source(
        request: Request,
        record_id: UUID,
        record_revision_id: UUID,
        published_only: bool = Query(default=False),
    ) -> Response:
        context, decision = _scope(request)
        try:
            filename, media_type, value = await required(context).source_csv_download_async(
                context,
                decision,
                record_id=record_id,
                revision_id=record_revision_id,
                published_only=published_only,
            )
            response = Response(content=value, media_type=media_type)
            response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            response.headers["X-Content-SHA256"] = hashlib.sha256(value).hexdigest()
            return response
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _error(context, error) from error


__all__ = [
    "JsonDomainBindingInput",
    "JsonRegistrationArtifactInput",
    "JsonRegistrationFormatsResponse",
    "JsonRegistrationPreviewRequest",
    "JsonRegistrationSaveRequest",
    "install_json_record_registration_api",
]
