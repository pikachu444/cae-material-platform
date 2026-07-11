"""Protected T-17 plugin package registration and activation resources."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.plugins.application.registry import (
    ActivatePackage,
    ControlPackage,
    PluginRegistryService,
    RegisterPackage,
    RegisterSchema,
)
from cmp.modules.plugins.domain.registry import (
    ActivationRecord,
    ArtifactReference,
    ExtensionType,
    InvalidManifest,
    PackageAccessDenied,
    PackageConflict,
    PackageNotFound,
    PackageRecord,
    PackageState,
    PackageStateEventRecord,
    PluginRegistryError,
    SchemaDocument,
    SchemaRole,
)

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type PackageDigest = Annotated[
    str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")
]
type Dependency = Callable[..., object]


class ArtifactReferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    sha256: Sha256
    size_bytes: Annotated[int, Field(ge=1, le=9223372036854775807)]
    media_type: Annotated[str, StringConstraints(min_length=1, max_length=255)]

    def domain(self) -> ArtifactReference:
        return ArtifactReference(
            self.artifact_id, self.sha256, self.size_bytes, self.media_type
        )


class RegisterSchemaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    extension_ordinal: Annotated[int, Field(ge=1, le=32767)]
    role: SchemaRole
    document: dict[str, Any]
    sha256: Sha256

    def command(self) -> RegisterSchema:
        return RegisterSchema(
            self.schema_id,
            self.extension_ordinal,
            self.role,
            self.document,
            self.sha256,
        )


class RegisterPluginPackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    manifest: dict[str, Any]
    package_artifact: ArtifactReferenceRequest
    signature_artifact: ArtifactReferenceRequest
    sbom_artifact: ArtifactReferenceRequest
    schemas: Annotated[list[RegisterSchemaRequest], Field(min_length=1, max_length=100)]


class ControlPluginPackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class ArtifactReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    sha256: Sha256
    size_bytes: int
    media_type: str

    @classmethod
    def from_record(cls, value: ArtifactReference) -> ArtifactReferenceResponse:
        return cls(
            artifact_id=value.artifact_id,
            sha256=value.sha256,
            size_bytes=value.size_bytes,
            media_type=value.media_type,
        )


class ExtensionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordinal: int
    type: ExtensionType
    entrypoint: str
    capabilities: list[str]


class PluginSchemaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str
    extension_ordinal: int
    role: SchemaRole
    document: dict[str, Any]
    sha256: Sha256

    @classmethod
    def from_record(cls, value: SchemaDocument) -> PluginSchemaResponse:
        return cls(
            schema_id=value.schema_id,
            extension_ordinal=value.extension_ordinal,
            role=value.role,
            document=value.document(),
            sha256=value.sha256,
        )


class PackageStateEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    sequence_no: int
    from_state: PackageState | None
    to_state: PackageState
    occurred_at: datetime
    actor_id: UUID
    reason: str
    request_id: UUID
    trace_id: str

    @classmethod
    def from_record(
        cls, value: PackageStateEventRecord
    ) -> PackageStateEventResponse:
        return cls(
            event_id=value.id,
            sequence_no=value.sequence_no,
            from_state=value.from_state,
            to_state=value.to_state,
            occurred_at=value.occurred_at,
            actor_id=value.actor_id,
            reason=value.reason,
            request_id=value.request_id,
            trace_id=value.trace_id,
        )


class ActivationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_id: UUID
    activated_at: datetime
    activated_by: UUID
    reason: str
    request_id: UUID
    trace_id: str

    @classmethod
    def from_record(cls, value: ActivationRecord) -> ActivationResponse:
        return cls(
            activation_id=value.id,
            activated_at=value.activated_at,
            activated_by=value.activated_by,
            reason=value.reason,
            request_id=value.request_id,
            trace_id=value.trace_id,
        )


class ResourceRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: float
    memory_mb: int
    gpu: int
    timeout_s: int


class PackageLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self: str


class PluginPackageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: UUID
    definition_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    plugin_id: str
    display_name: str
    plugin_version: str
    package_digest: PackageDigest
    manifest: dict[str, Any]
    manifest_digest: Sha256
    contract_api: str
    extensions: list[ExtensionResponse]
    network_policy: str
    artifact_read_roles: list[str]
    artifact_write_roles: list[str]
    resources: ResourceRequestResponse
    package_artifact: ArtifactReferenceResponse
    signature_artifact: ArtifactReferenceResponse
    sbom_artifact: ArtifactReferenceResponse
    schemas: list[PluginSchemaResponse]
    state: PackageState
    activation_eligible: bool
    active: bool
    state_history: list[PackageStateEventResponse]
    submitted_at: datetime
    submitted_by: UUID
    submission_request_id: UUID
    submission_trace_id: str
    activation: ActivationResponse | None
    links: PackageLinks

    @classmethod
    def from_record(cls, value: PackageRecord) -> PluginPackageResponse:
        manifest = value.manifest
        activation = (
            ActivationResponse.from_record(value.activation)
            if value.activation is not None
            else None
        )
        return cls(
            package_id=value.id,
            definition_id=value.definition_id,
            organization_id=value.organization_id,
            project_id=value.project_id,
            classification=value.classification,
            plugin_id=manifest.plugin_id,
            display_name=manifest.display_name,
            plugin_version=manifest.plugin_version,
            package_digest=f"sha256:{manifest.package_digest}",
            manifest=manifest.document(),
            manifest_digest=manifest.manifest_digest,
            contract_api=manifest.contract_api,
            extensions=[
                ExtensionResponse(
                    ordinal=item.ordinal,
                    type=item.extension_type,
                    entrypoint=item.entrypoint,
                    capabilities=list(item.capabilities),
                )
                for item in manifest.extensions
            ],
            network_policy=manifest.network,
            artifact_read_roles=list(manifest.artifact_read_roles),
            artifact_write_roles=list(manifest.artifact_write_roles),
            resources=ResourceRequestResponse(
                cpu=manifest.cpu,
                memory_mb=manifest.memory_mb,
                gpu=manifest.gpu,
                timeout_s=manifest.timeout_s,
            ),
            package_artifact=ArtifactReferenceResponse.from_record(
                value.package_artifact
            ),
            signature_artifact=ArtifactReferenceResponse.from_record(
                value.signature_artifact
            ),
            sbom_artifact=ArtifactReferenceResponse.from_record(value.sbom_artifact),
            schemas=[PluginSchemaResponse.from_record(item) for item in value.schemas],
            state=value.state,
            activation_eligible=value.activation_eligible,
            active=value.active,
            state_history=[
                PackageStateEventResponse.from_record(item)
                for item in value.state_events
            ],
            submitted_at=value.submitted_at,
            submitted_by=value.submitted_by,
            submission_request_id=value.submission_request_id,
            submission_trace_id=value.submission_trace_id,
            activation=activation,
            links=PackageLinks(self=f"/api/v1/plugins/packages/{value.id}"),
        )


class PluginProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Reason
    code: Annotated[str, StringConstraints(pattern=r"^CMP-PLUGIN-[0-9]{4}$")]
    trace_id: Label


class PluginHttpError(Exception):
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
        self.problem = PluginProblem(
            type="urn:cmp:problem:plugin-registry",
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
        raise RuntimeError("plugin route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> PluginHttpError:
    return PluginHttpError(
        context=context,
        status=503,
        title="Plugin registry unavailable",
        detail="The immutable plugin registry is not configured for this deployment.",
        code="CMP-PLUGIN-0005",
    )


def _problem_detail(error: Exception) -> str:
    detail = str(error).strip()
    return (detail or "The plugin registry command was rejected.")[:2000]


def _translate(context: SecurityContext, error: Exception) -> PluginHttpError:
    if isinstance(error, PackageAccessDenied):
        return PluginHttpError(
            context=context,
            status=403,
            title="Plugin package access denied",
            detail="The selected package classification exceeds the authorized clearance.",
            code="CMP-PLUGIN-0006",
        )
    if isinstance(error, PackageNotFound):
        return PluginHttpError(
            context=context,
            status=404,
            title="Plugin package not found",
            detail="No plugin package is visible in the selected tenant context.",
            code="CMP-PLUGIN-0001",
        )
    if isinstance(error, (InvalidManifest, ValueError)):
        return PluginHttpError(
            context=context,
            status=422,
            title="Invalid plugin package contract",
            detail=_problem_detail(error),
            code="CMP-PLUGIN-0002",
        )
    if isinstance(error, PackageConflict):
        return PluginHttpError(
            context=context,
            status=409,
            title="Plugin package conflict",
            detail=_problem_detail(error),
            code="CMP-PLUGIN-0003",
        )
    return PluginHttpError(
        context=context,
        status=409,
        title="Invalid plugin package state",
        detail=_problem_detail(error),
        code="CMP-PLUGIN-0004",
    )


def install_plugin_registry_api(
    application: FastAPI,
    *,
    service: PluginRegistryService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    submit_dependency: Dependency,
    activate_dependency: Dependency,
) -> None:
    previous_validation_handler = cast(
        Callable[[Request, RequestValidationError], Awaitable[Response]],
        application.exception_handlers.get(
            RequestValidationError, request_validation_exception_handler
        ),
    )

    @application.exception_handler(PluginHttpError)
    async def plugin_error_handler(
        request: Request, error: PluginHttpError
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
    async def plugin_validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/plugins"):
            return cast(JSONResponse, await previous_validation_handler(request, error))
        context = getattr(request.state, "security_context", None)
        if not isinstance(context, SecurityContext):
            return await request_validation_exception_handler(request, error)
        problem = PluginProblem(
            type="urn:cmp:problem:plugin-registry",
            title="Invalid plugin package request",
            status=422,
            detail="The request does not satisfy the versioned plugin registry contract.",
            code="CMP-PLUGIN-0002",
            trace_id=context.trace_id,
        )
        return JSONResponse(
            status_code=422,
            content=problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={
                "Cache-Control": "no-store",
                "X-Request-ID": str(context.request_id),
            },
        )

    authentication_errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "The plugin action is not authorized."},
    }
    problem_errors: dict[int | str, dict[str, Any]] = {
        404: {"model": PluginProblem},
        409: {"model": PluginProblem},
        422: {"model": PluginProblem},
        503: {"model": PluginProblem},
    }
    register_errors: dict[int | str, dict[str, Any]] = {
        **authentication_errors,
        409: problem_errors[409],
        422: problem_errors[422],
        503: problem_errors[503],
    }
    read_errors: dict[int | str, dict[str, Any]] = {
        **authentication_errors,
        404: problem_errors[404],
        422: problem_errors[422],
        503: problem_errors[503],
    }
    control_errors: dict[int | str, dict[str, Any]] = {
        **authentication_errors,
        **problem_errors,
    }

    @application.post(
        "/api/v1/plugins/packages",
        operation_id="registerPluginPackage",
        response_model=PluginPackageResponse,
        status_code=201,
        responses=register_errors,
        dependencies=[Depends(security_dependency), Depends(submit_dependency)],
        tags=["plugins"],
        summary="Register one immutable manifest, package digest, and schema bundle.",
    )
    def register_package(
        request: Request,
        response: Response,
        body: RegisterPluginPackageRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                max_length=255,
                pattern=r"^[\x21-\x7e]+$",
            ),
        ],
    ) -> PluginPackageResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.register(
                context,
                decision,
                RegisterPackage(
                    classification=body.classification,
                    manifest=body.manifest,
                    package_artifact=body.package_artifact.domain(),
                    signature_artifact=body.signature_artifact.domain(),
                    sbom_artifact=body.sbom_artifact.domain(),
                    schemas=tuple(item.command() for item in body.schemas),
                    idempotency_key=idempotency_key,
                ),
            )
        except (PluginRegistryError, ValueError) as error:
            raise _translate(context, error) from error
        response.headers["Location"] = (
            f"/api/v1/plugins/packages/{result.package.id}"
        )
        response.headers["Idempotent-Replay"] = (
            "true" if result.replayed else "false"
        )
        return PluginPackageResponse.from_record(result.package)

    @application.get(
        "/api/v1/plugins/packages/{package_id}",
        operation_id="getPluginPackage",
        response_model=PluginPackageResponse,
        responses=read_errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["plugins"],
        summary="Read an immutable package and its append-only state history.",
    )
    def get_package(request: Request, package_id: UUID) -> PluginPackageResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            package = service.get(context, decision, package_id)
        except (PluginRegistryError, ValueError) as error:
            raise _translate(context, error) from error
        return PluginPackageResponse.from_record(package)

    def control(
        request: Request,
        package_id: UUID,
        reason: str,
        action: Literal["verify", "activate", "revoke"],
    ) -> PluginPackageResponse:
        context, decision = _request_scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            if action == "verify":
                package = service.verify(
                    context, decision, ControlPackage(package_id, reason)
                )
            elif action == "activate":
                package = service.activate(
                    context, decision, ActivatePackage(package_id, reason)
                )
            else:
                package = service.revoke(
                    context, decision, ControlPackage(package_id, reason)
                )
        except (PluginRegistryError, ValueError) as error:
            raise _translate(context, error) from error
        return PluginPackageResponse.from_record(package)

    @application.post(
        "/api/v1/plugins/packages/{package_id}:verify",
        operation_id="verifyPluginPackage",
        response_model=PluginPackageResponse,
        responses=control_errors,
        dependencies=[Depends(security_dependency), Depends(activate_dependency)],
        tags=["plugins"],
        summary="Record operator verification of signature, SBOM, and policy evidence.",
    )
    def verify_package(
        request: Request, package_id: UUID, body: ControlPluginPackageRequest
    ) -> PluginPackageResponse:
        return control(request, package_id, body.reason, "verify")

    @application.post(
        "/api/v1/plugins/packages/{package_id}:activate",
        operation_id="activatePluginPackage",
        response_model=PluginPackageResponse,
        responses=control_errors,
        dependencies=[Depends(security_dependency), Depends(activate_dependency)],
        tags=["plugins"],
        summary="Append the project allowlist activation for an eligible package.",
    )
    def activate_package(
        request: Request, package_id: UUID, body: ControlPluginPackageRequest
    ) -> PluginPackageResponse:
        return control(request, package_id, body.reason, "activate")

    @application.post(
        "/api/v1/plugins/packages/{package_id}:revoke",
        operation_id="revokePluginPackage",
        response_model=PluginPackageResponse,
        responses=control_errors,
        dependencies=[Depends(security_dependency), Depends(activate_dependency)],
        tags=["plugins"],
        summary="Append package revocation without deleting historical execution identity.",
    )
    def revoke_package(
        request: Request, package_id: UUID, body: ControlPluginPackageRequest
    ) -> PluginPackageResponse:
        return control(request, package_id, body.reason, "revoke")
