"""Protected API for Catalog Schema Definition Bundle planning, apply, and export."""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.artifacts.domain.content import (
    ArtifactAccessDenied,
    ArtifactIntegrityError,
    ArtifactNotFound,
    InvalidArtifact,
)
from cmp.modules.catalog.adapters.api.catalog import CatalogHttpError, _scope
from cmp.modules.catalog.application.schema_bundles import (
    ApplySchemaDefinitionBundle,
    PlanSchemaDefinitionBundle,
    SchemaBundleApplicationNotFound,
    SchemaBundleExportConflict,
    SchemaBundleIdempotencyConflict,
    SchemaBundleMigrationRequired,
    SchemaBundlePlannerService,
    SchemaBundleSourceConflict,
    SchemaBundleStalePlan,
    SchemaBundleVersionConflict,
)

type Dependency = Callable[..., object]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type OptionalText2000 = Annotated[str, StringConstraints(min_length=1, max_length=2000)] | None
type VisibleAscii255 = Annotated[str, StringConstraints(pattern=r"^[!-~]{1,255}$")]
type BundleKey = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,62}[a-z0-9]$|^[a-z]$")
]


class SchemaBundlePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    artifact_sha256: Sha256


class SchemaBundleApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    artifact_sha256: Sha256
    plan_fingerprint: Sha256
    delete_missing: Literal[False] = False


class SourceArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: Literal["internal", "confidential", "restricted", "export_controlled"]
    media_type: str
    size_bytes: Annotated[int, Field(ge=0, le=64 * 1024 * 1024)]
    sha256: Sha256


class BundleScopeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    project_id: UUID
    classification: Literal["internal", "confidential", "restricted", "export_controlled"]


class BundleSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_key: str
    bundle_version: str
    scope: BundleScopeResponse
    database_key: str
    profile_key: str
    record_schema_count: int
    unit_profile_count: int
    dependency_order: tuple[str, ...]


class CurrentPlanIdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None
    revision_id: UUID | None
    content_hash: Sha256
    published: bool


class ProjectedDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    description: str | None
    data_category: Literal["technical_data", "test_data", "simulation_data"] | None = None


class ProjectedProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_key: str
    key: str
    name: str
    description: str | None


class ProjectedAdapterSemanticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_key: bool
    identity_rule: str | None
    nullable: bool
    suggested_values: tuple[str, ...] | None
    curve: dict[str, str] | None
    indexed: bool | None
    searchable: bool | None


class ProjectedAttributeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    data_type: Literal[
        "number",
        "integer",
        "text",
        "boolean",
        "date",
        "discrete",
        "curve",
        "record_reference",
    ]
    required: bool
    quantity_semantics: str | None
    normalized_unit: str | None
    minimum_number: float | None
    maximum_number: float | None
    minimum_length: int | None
    maximum_length: int | None
    pattern: str | None
    allowed_values: tuple[str, ...]
    reference_table_key: str | None
    help_text: OptionalText2000
    source_pointer: str
    adapter_semantics: ProjectedAdapterSemanticsResponse
    business_key: bool = False


class ProjectedLayoutItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attribute_key: str
    section: str
    ordinal: int


class ProjectedLayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: OptionalText2000
    items: tuple[ProjectedLayoutItemResponse, ...]


class ProjectedPlacementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_key: str
    table_key: str


class ProjectedLinkTypeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    source_table_key: str
    target_table_key: str
    forward_label: str
    reverse_label: str
    source_cardinality: Literal["one", "many"]
    target_cardinality: Literal["one", "many"]
    description: OptionalText2000


type ProjectedCatalogResponse = (
    ProjectedDefinitionResponse
    | ProjectedProfileResponse
    | ProjectedAttributeResponse
    | ProjectedLayoutResponse
    | ProjectedPlacementResponse
    | ProjectedLinkTypeResponse
)


class SchemaBundlePlanActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    disposition: Literal["create", "update", "no-op", "conflict", "error"]
    target_type: Literal[
        "bundle",
        "database",
        "profile",
        "table",
        "attribute",
        "layout",
        "profile_table_placement",
        "link_type",
    ]
    external_key: str
    parent_external_key: str | None
    current: CurrentPlanIdentityResponse | None
    projected: ProjectedCatalogResponse | None
    reason_codes: tuple[str, ...]


class SchemaBundleDiagnosticResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["warning", "error"]
    code: Annotated[
        str,
        StringConstraints(pattern=r"^CMP-SCHEMA-(?:BUNDLE|SOURCE)-[0-9]{4}$"),
    ]
    location: str
    message: str
    remediation: str


class SchemaBundleActionCountsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    create: int
    update: int
    no_op: int = Field(validation_alias="no-op", serialization_alias="no-op")
    conflict: int
    error: int


class SchemaBundlePlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: str = Field(validation_alias="$schema", serialization_alias="$schema")
    contract_version: Literal["1.0.0"]
    source_artifact: SourceArtifactResponse
    bundle: BundleSummaryResponse | None
    catalog_snapshot_fingerprint: Sha256
    plan_fingerprint: Sha256
    valid: bool
    action_counts: SchemaBundleActionCountsResponse
    actions: tuple[SchemaBundlePlanActionResponse, ...]
    diagnostics: tuple[SchemaBundleDiagnosticResponse, ...]
    mutations_applied: Literal[False]
    delete_missing: Literal[False]
    write_set: Annotated[tuple[str, ...], Field(max_length=0)]


class AppliedSchemaObjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    disposition: Literal["create", "update", "no-op"]
    target_type: Literal[
        "database",
        "profile",
        "table",
        "attribute",
        "layout",
        "profile_table_placement",
        "link_type",
    ]
    external_key: str
    parent_external_key: str | None
    aggregate_id: UUID | None
    revision_id: UUID | None
    content_hash: Sha256
    published: bool
    source_schema_id: str
    source_schema_version: str
    source_file: str | None
    source_file_sha256: Sha256 | None
    source_pointer: str


class SchemaBundleApplicationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: str = Field(validation_alias="$schema", serialization_alias="$schema")
    contract_version: Literal["1.0.0"]
    application_id: UUID
    bundle_id: UUID
    bundle_key: str
    bundle_version: str
    classification: Literal["internal", "confidential", "restricted", "export_controlled"]
    source_artifact: SourceArtifactResponse
    plan_fingerprint: Sha256
    before_snapshot_fingerprint: Sha256
    after_snapshot_fingerprint: Sha256
    results: tuple[AppliedSchemaObjectResponse, ...]
    mutations_applied: bool
    delete_missing: Literal[False]
    applied_at: str
    applied_by: UUID
    idempotency_key: VisibleAscii255


def _http_error(context: Any, error: Exception) -> CatalogHttpError:
    if isinstance(error, ArtifactNotFound):
        return CatalogHttpError(
            context=context,
            status_code=404,
            title="Schema Definition Bundle Artifact not found",
            detail="No verified Artifact is visible for the selected tenant context.",
            code="CMP-CATALOG-0201",
        )
    if isinstance(error, ArtifactAccessDenied):
        return CatalogHttpError(
            context=context,
            status_code=403,
            title="Schema Definition Bundle access denied",
            detail="The Artifact classification or capability is not authorized.",
            code="CMP-CATALOG-0203",
        )
    if isinstance(error, SchemaBundleApplicationNotFound):
        return CatalogHttpError(
            context=context,
            status_code=404,
            title="Schema Definition Bundle application not found",
            detail="No applied bundle state is visible for the selected tenant context.",
            code="CMP-CATALOG-0206",
        )
    if isinstance(error, SchemaBundleStalePlan):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Schema Definition Bundle plan is stale",
            detail=(
                "The server re-plan against the locked current Catalog does not match "
                "the approved plan_fingerprint. Plan again before applying."
            ),
            code="CMP-CATALOG-0207",
        )
    if isinstance(error, SchemaBundleIdempotencyConflict):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Schema Definition Bundle idempotency conflict",
            detail="The Idempotency-Key already identifies different immutable apply evidence.",
            code="CMP-CATALOG-0208",
        )
    if isinstance(error, SchemaBundleVersionConflict):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Schema Definition Bundle version conflict",
            detail="The stable bundle version is already bound to different canonical content.",
            code="CMP-CATALOG-0209",
        )
    if isinstance(error, SchemaBundleMigrationRequired):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Catalog Record migration required",
            detail=(
                "Current Records pin a schema revision affected by this bundle. "
                "Apply is blocked; no user migration code is executed."
            ),
            code="CMP-CATALOG-0210",
        )
    if isinstance(error, SchemaBundleExportConflict):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Schema Definition Bundle export drift",
            detail="Current Catalog heads or publication markers differ from the applied bindings.",
            code="CMP-CATALOG-0211",
        )
    if isinstance(
        error,
        (
            ArtifactIntegrityError,
            InvalidArtifact,
            SchemaBundleSourceConflict,
            ValueError,
        ),
    ):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Schema Definition Bundle source conflict",
            detail=(
                "The exact Artifact digest, media type, integrity, or tenant evidence "
                "does not satisfy the planning request."
            ),
            code="CMP-CATALOG-0202",
        )
    return CatalogHttpError(
        context=context,
        status_code=409,
        title="Schema Definition Bundle operation failed",
        detail="The Catalog Schema Definition Bundle operation could not be completed.",
        code="CMP-CATALOG-0204",
    )


def install_schema_bundle_planner_api(
    application: FastAPI,
    *,
    service: SchemaBundlePlannerService | None,
    security_dependency: Dependency,
    write_dependency: Dependency,
    apply_dependency: Dependency,
) -> None:
    if CatalogHttpError not in application.exception_handlers:

        @application.exception_handler(CatalogHttpError)
        async def schema_bundle_error_handler(
            request: Request, error: CatalogHttpError
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

    def required(context: Any) -> SchemaBundlePlannerService:
        if service is None:
            raise CatalogHttpError(
                context=context,
                status_code=503,
                title="Schema Definition Bundle planner unavailable",
                detail="Artifact storage or the authoritative Catalog snapshot is not configured.",
                code="CMP-CATALOG-0205",
            )
        return service

    @application.post(
        "/api/v1/catalog/schema-definition-bundles:plan",
        operation_id="planCatalogSchemaDefinitionBundle",
        response_model=SchemaBundlePlanResponse,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog-schema"],
        responses={
            401: {"description": "Authentication required."},
            403: {"description": "Catalog schema planning is not authorized."},
            404: {"description": "The exact Artifact is absent or hidden by RLS."},
            409: {"description": "Artifact evidence or read-only snapshot planning conflict."},
            503: {"description": "Artifact or Catalog snapshot service unavailable."},
        },
    )
    async def plan_schema_definition_bundle(
        request: Request,
        body: SchemaBundlePlanRequest,
    ) -> SchemaBundlePlanResponse:
        context, decision = _scope(request)
        try:
            result = await required(context).plan(
                context,
                decision,
                PlanSchemaDefinitionBundle(body.artifact_id, body.artifact_sha256),
            )
            return SchemaBundlePlanResponse.model_validate(result.canonical())
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _http_error(context, error) from error

    @application.post(
        "/api/v1/catalog/schema-definition-bundles:apply",
        operation_id="applyCatalogSchemaDefinitionBundle",
        response_model=SchemaBundleApplicationResponse,
        status_code=201,
        dependencies=[Depends(security_dependency), Depends(apply_dependency)],
        tags=["catalog-schema"],
        responses={
            200: {
                "description": "Exact idempotent replay.",
                "headers": {
                    "Location": {"schema": {"type": "string"}},
                    "Idempotent-Replay": {
                        "schema": {"type": "string", "enum": ["true"]}
                    },
                },
            },
            201: {
                "description": "Exact server-owned plan committed atomically.",
                "headers": {
                    "Location": {"schema": {"type": "string"}},
                    "Idempotent-Replay": {
                        "schema": {"type": "string", "enum": ["false"]}
                    },
                },
            },
            401: {"description": "Authentication required."},
            403: {"description": "Catalog schema apply approval is not authorized."},
            404: {"description": "The exact Artifact is absent or hidden by RLS."},
            409: {"description": "Stale plan, migration, version, or idempotency conflict."},
            503: {"description": "Artifact or Catalog apply service unavailable."},
        },
    )
    async def apply_schema_definition_bundle(
        request: Request,
        response: Response,
        body: SchemaBundleApplyRequest,
        idempotency_key: Annotated[VisibleAscii255, Header(alias="Idempotency-Key")],
    ) -> SchemaBundleApplicationResponse:
        context, decision = _scope(request)
        try:
            result = await required(context).apply(
                context,
                decision,
                ApplySchemaDefinitionBundle(
                    artifact_id=body.artifact_id,
                    expected_sha256=body.artifact_sha256,
                    plan_fingerprint=body.plan_fingerprint,
                    idempotency_key=idempotency_key,
                    delete_missing=body.delete_missing,
                ),
            )
            response.status_code = 200 if result.replayed else 201
            response.headers["Location"] = (
                f"/api/v1/catalog/schema-definition-bundle-applications/{result.application_id}"
            )
            response.headers["Idempotent-Replay"] = str(result.replayed).lower()
            response.headers["Cache-Control"] = "no-store"
            return SchemaBundleApplicationResponse.model_validate(result.canonical())
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _http_error(context, error) from error

    @application.get(
        "/api/v1/catalog/schema-definition-bundle-applications/{application_id}",
        operation_id="getCatalogSchemaDefinitionBundleApplication",
        response_model=SchemaBundleApplicationResponse,
        dependencies=[Depends(security_dependency), Depends(apply_dependency)],
        tags=["catalog-schema"],
        responses={
            401: {"description": "Authentication required."},
            403: {"description": "Catalog schema application read-back is not authorized."},
            404: {"description": "The application is absent or hidden by RLS."},
        },
    )
    async def get_schema_definition_bundle_application(
        request: Request,
        application_id: UUID,
    ) -> SchemaBundleApplicationResponse:
        context, decision = _scope(request)
        try:
            result = required(context).get_application(context, decision, application_id)
            return SchemaBundleApplicationResponse.model_validate(result.canonical())
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _http_error(context, error) from error

    @application.get(
        "/api/v1/catalog/schema-definition-bundles/{bundle_key}:export",
        operation_id="exportCatalogSchemaDefinitionBundle",
        response_class=Response,
        dependencies=[Depends(security_dependency), Depends(apply_dependency)],
        tags=["catalog-schema"],
        responses={
            200: {
                "description": "Exact original bytes of the current applied source Artifact.",
                "headers": {
                    "ETag": {"schema": {"type": "string"}},
                    "Digest": {"schema": {"type": "string"}},
                    "X-CMP-Bundle-Application-ID": {
                        "schema": {"type": "string", "format": "uuid"}
                    },
                    "X-CMP-Source-Artifact-ID": {
                        "schema": {"type": "string", "format": "uuid"}
                    },
                    "X-CMP-Source-Artifact-SHA256": {
                        "schema": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
                    },
                },
                "content": {
                    "application/vnd.cmp.catalog-schema-definition-bundle+json": {},
                    "application/vnd.cmp.catalog-schema-source-set+json": {},
                    "application/vnd.cmp.catalog-schema-source-set+zip": {},
                    "application/zip": {},
                },
            },
            401: {"description": "Authentication required."},
            403: {"description": "Catalog schema export is not authorized."},
            404: {"description": "The applied bundle is absent or hidden by RLS."},
            409: {"description": "Applied bindings or immutable source evidence drifted."},
        },
    )
    async def export_schema_definition_bundle(
        request: Request,
        bundle_key: BundleKey,
    ) -> Response:
        context, decision = _scope(request)
        try:
            result = await required(context).export(context, decision, bundle_key)
            return Response(
                content=result.value,
                media_type=result.media_type,
                headers={
                    "Cache-Control": "no-store",
                    "ETag": f'"sha256:{result.sha256}"',
                    "Digest": (
                        "sha-256=" + base64.b64encode(bytes.fromhex(result.sha256)).decode("ascii")
                    ),
                    "X-CMP-Bundle-Application-ID": str(result.application_id),
                    "X-CMP-Source-Artifact-ID": str(result.source_artifact_id),
                    "X-CMP-Source-Artifact-SHA256": result.source_artifact_sha256,
                },
            )
        except CatalogHttpError:
            raise
        except Exception as error:
            raise _http_error(context, error) from error
