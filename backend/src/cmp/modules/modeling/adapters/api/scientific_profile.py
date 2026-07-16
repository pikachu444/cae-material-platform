"""Protected API for versioned scientific calibration profiles."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.scientific_profile import (
    CreateScientificProfile,
    ReviseScientificProfile,
    ScientificProfileService,
    ScientificProfileSnapshot,
)
from cmp.modules.modeling.domain.scientific_profile import (
    InvalidScientificProfile,
    OgdenScientificParameters,
    PronyScientificParameters,
    ScientificApprovalStatus,
    ScientificProfileConflict,
    ScientificProfileContent,
    ScientificProfileFamily,
    ScientificProfileNotFound,
    VoceScientificParameters,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import RevisionConflict

type Dependency = Callable[..., object]
type Label = Annotated[str, StringConstraints(min_length=1, max_length=160, strip_whitespace=False)]
type Note = Annotated[str, StringConstraints(min_length=1, max_length=500, strip_whitespace=False)]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class VoceParametersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sigma0_initial_pa: Annotated[float, Field(gt=0)]
    sigma0_lower_pa: Annotated[float, Field(gt=0)]
    sigma0_upper_pa: Annotated[float, Field(gt=0)]
    sigma0_scale_pa: Annotated[float, Field(gt=0)]
    q_initial_pa: Annotated[float, Field(gt=0)]
    q_lower_pa: Annotated[float, Field(gt=0)]
    q_upper_pa: Annotated[float, Field(gt=0)]
    q_scale_pa: Annotated[float, Field(gt=0)]
    b_initial: Annotated[float, Field(gt=0)]
    b_lower: Annotated[float, Field(gt=0)]
    b_upper: Annotated[float, Field(gt=0)]
    b_scale: Annotated[float, Field(gt=0)]


class PronyParametersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term_count_min: Annotated[int, Field(ge=1, le=10)]
    term_count_max: Annotated[int, Field(ge=1, le=10)]
    total_shear_ratio_upper: Annotated[float, Field(gt=0, lt=1)]
    relaxation_time_lower_s: Annotated[float, Field(gt=0)]
    relaxation_time_upper_s: Annotated[float, Field(gt=0)]


class OgdenParametersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mu_initial_pa: Annotated[float, Field(gt=0)]
    mu_lower_pa: Annotated[float, Field(gt=0)]
    mu_upper_pa: Annotated[float, Field(gt=0)]
    mu_scale_pa: Annotated[float, Field(gt=0)]
    alpha_initial: Annotated[float, Field(gt=0)]
    alpha_lower: Annotated[float, Field(gt=0)]
    alpha_upper: Annotated[float, Field(gt=0)]
    alpha_scale: Annotated[float, Field(gt=0)]
    uniaxial_weight: Annotated[float, Field(gt=0)] = 1.0
    planar_weight: Annotated[float, Field(gt=0)] = 1.0
    biaxial_weight: Annotated[float, Field(gt=0)] = 1.0


class ScientificProfileContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_label: Label
    family: ScientificProfileFamily
    approval_status: ScientificApprovalStatus = ScientificApprovalStatus.REFERENCE_UNAPPROVED
    multistart_count: Annotated[int, Field(ge=1, le=32)] = 8
    seed: Annotated[int, Field(ge=0, le=2_147_483_647)] = 20260716
    status_note: Note = "Reference profile; domain sign-off is not recorded."
    voce: VoceParametersRequest | None = None
    prony: PronyParametersRequest | None = None
    ogden: OgdenParametersRequest | None = None

    @model_validator(mode="after")
    def validate_family_block(self) -> ScientificProfileContentRequest:
        expected = {
            ScientificProfileFamily.STEEL_VOCE: (True, False, False),
            ScientificProfileFamily.POLYMER_LINEAR_PRONY: (False, True, False),
            ScientificProfileFamily.ELASTOMER_OGDEN_PRONY: (False, False, True),
        }[self.family]
        if (self.voce is not None, self.prony is not None, self.ogden is not None) != expected:
            raise ValueError("exactly one matching family parameter block is required")
        return self

    def to_domain(self) -> ScientificProfileContent:
        return ScientificProfileContent(
            profile_label=self.profile_label,
            family=self.family,
            approval_status=self.approval_status,
            multistart_count=self.multistart_count,
            seed=self.seed,
            status_note=self.status_note,
            voce=VoceScientificParameters(**self.voce.model_dump()) if self.voce else None,
            prony=PronyScientificParameters(**self.prony.model_dump()) if self.prony else None,
            ogden=OgdenScientificParameters(**self.ogden.model_dump()) if self.ogden else None,
        )


class CreateScientificProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    content: ScientificProfileContentRequest
    change_reason: Reason


class ReviseScientificProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_current_revision_id: UUID
    content: ScientificProfileContentRequest
    change_reason: Reason


class ScientificProfileRevisionResponse(RevisionMetadataResponse):
    content: dict[str, object]


class ScientificProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scientific_profile_id: UUID
    current_revision: ScientificProfileRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: ScientificProfileSnapshot) -> ScientificProfileResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/scientific-profiles/{value.id}"
        return cls(
            scientific_profile_id=value.id,
            current_revision=ScientificProfileRevisionResponse(
                **metadata.model_dump(), content=value.current.content.canonical()
            ),
            links={"self": root, "revisions": f"{root}/revisions"},
        )


class ScientificProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[ScientificProfileResponse, ...]


class ScientificProfileProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class ScientificProfileHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, detail: str) -> None:
        self.problem = ScientificProfileProblem(
            type="urn:cmp:problem:modeling:scientific-profile",
            title="Scientific profile request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-MODELING-{status_code}",
            trace_id=context.trace_id,
        )


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    return request.state.security_context, request.state.authorization_decision


def _translate(context: SecurityContext, error: Exception) -> ScientificProfileHttpError:
    if isinstance(error, ScientificProfileNotFound):
        return ScientificProfileHttpError(context, 404, str(error))
    if isinstance(error, (ScientificProfileConflict, RevisionConflict)):
        return ScientificProfileHttpError(context, 409, str(error))
    if isinstance(error, (InvalidScientificProfile, ValueError)):
        return ScientificProfileHttpError(context, 422, str(error))
    return ScientificProfileHttpError(context, 503, "service is unavailable")


def install_scientific_profile_api(
    application: FastAPI,
    *,
    service: ScientificProfileService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(ScientificProfileHttpError)
    async def handle_error(_: Request, error: ScientificProfileHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(mode="json"), status_code=error.problem.status)

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": ScientificProfileProblem} for code in (404, 409, 422, 503)
    }

    @application.post(
        "/api/v1/scientific-profiles",
        operation_id="createScientificProfile",
        response_model=ScientificProfileResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    def create_profile(
        request: Request, response: Response, body: CreateScientificProfileRequest
    ) -> ScientificProfileResponse:
        context, decision = _scope(request)
        if service is None:
            raise ScientificProfileHttpError(context, 503, "service is unavailable")
        try:
            value = service.create(
                context,
                decision,
                CreateScientificProfile(
                    body.classification.value, body.content.to_domain(), body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        response.headers["Location"] = f"/api/v1/scientific-profiles/{value.id}"
        return ScientificProfileResponse.from_snapshot(value)

    @application.get(
        "/api/v1/scientific-profiles",
        operation_id="listScientificProfiles",
        response_model=ScientificProfileListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def list_profiles(
        request: Request,
        family: Annotated[ScientificProfileFamily | None, Query()] = None,
    ) -> ScientificProfileListResponse:
        context, decision = _scope(request)
        if service is None:
            raise ScientificProfileHttpError(context, 503, "service is unavailable")
        try:
            values = service.list(context, decision, family)
        except Exception as error:
            raise _translate(context, error) from error
        return ScientificProfileListResponse(
            items=tuple(ScientificProfileResponse.from_snapshot(value) for value in values)
        )

    @application.get(
        "/api/v1/scientific-profiles/{profile_id}",
        operation_id="getScientificProfile",
        response_model=ScientificProfileResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_profile(
        request: Request, response: Response, profile_id: UUID
    ) -> ScientificProfileResponse:
        context, decision = _scope(request)
        if service is None:
            raise ScientificProfileHttpError(context, 503, "service is unavailable")
        try:
            value = service.get(context, decision, profile_id)
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        return ScientificProfileResponse.from_snapshot(value)

    @application.post(
        "/api/v1/scientific-profiles/{profile_id}/revisions",
        operation_id="reviseScientificProfile",
        response_model=ScientificProfileResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    def revise_profile(
        request: Request,
        response: Response,
        profile_id: UUID,
        body: ReviseScientificProfileRequest,
    ) -> ScientificProfileResponse:
        context, decision = _scope(request)
        if service is None:
            raise ScientificProfileHttpError(context, 503, "service is unavailable")
        try:
            value = service.revise(
                context,
                decision,
                profile_id,
                ReviseScientificProfile(
                    body.expected_current_revision_id,
                    body.content.to_domain(),
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        response.headers["Location"] = f"/api/v1/scientific-profiles/{value.id}"
        return ScientificProfileResponse.from_snapshot(value)
