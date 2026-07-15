"""HTTP workflow for human Voce selection and calibrated IR projection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.artifacts.domain.content import ArtifactError, ArtifactNotFound
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.api.tabulated_plasticity import (
    TabulatedPlasticityModelResponse,
)
from cmp.modules.modeling.application.voce_calibration import (
    VoceCalibrationConflict,
    VoceCalibrationNotFound,
)
from cmp.modules.modeling.application.voce_candidate_projection import (
    CreateVoceCandidateSelection,
    ProjectSelectedVoceCandidate,
    VoceCandidateProjectionService,
    VoceCandidateSelectionSnapshot,
)
from cmp.modules.modeling.domain.reference_voce_candidate_selection import (
    InvalidVoceCandidateSelection,
    ReferenceVoceCandidateSelectionContent,
    VoceCandidateSelectionConflict,
    VoceCandidateSelectionError,
    VoceCandidateSelectionNotFound,
)
from cmp.modules.modeling.domain.reference_voce_tabulated_plasticity import (
    InvalidVoceProjection,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Dependency = Callable[..., object]


class VoceSelectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    selection_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    voce_calibration_run_id: UUID
    voce_calibration_candidate_id: UUID
    selection_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class VoceProjectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_revision_id: UUID
    sampling_point_count: Annotated[int, Field(ge=21, le=501)] = 51
    extension_max_true_plastic_strain: Annotated[float, Field(gt=0)]
    acknowledge_constant_extension: bool
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class VoceSelectionContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_label: str
    voce_calibration_run_id: UUID
    voce_calibration_candidate_id: UUID
    candidate_sha256: str
    selection_reason: str
    selection_decision: str
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferenceVoceCandidateSelectionContent
    ) -> VoceSelectionContentResponse:
        return cls(
            selection_label=value.selection_label,
            voce_calibration_run_id=value.voce_calibration_run_id,
            voce_calibration_candidate_id=value.voce_calibration_candidate_id,
            candidate_sha256=f"sha256:{value.candidate_sha256}",
            selection_reason=value.selection_reason,
            selection_decision=value.selection_decision,
            non_production=value.non_production,
        )


class VoceSelectionRevisionResponse(RevisionMetadataResponse):
    content: VoceSelectionContentResponse


class VoceSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voce_candidate_selection_id: UUID
    current_revision: VoceSelectionRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: VoceCandidateSelectionSnapshot) -> VoceSelectionResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/voce-candidate-selections/{value.id}"
        return cls(
            voce_candidate_selection_id=value.id,
            current_revision=VoceSelectionRevisionResponse(
                **metadata.model_dump(),
                content=VoceSelectionContentResponse.from_domain(value.current.content),
            ),
            links={"self": root, "project_tabulated_ir": f"{root}/tabulated-plasticity-models"},
        )


class VoceProjectionProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-CALIBRATION-[0-9]{4}$")]
    trace_id: str


class VoceProjectionHttpError(Exception):
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
        self.problem = VoceProjectionProblem(
            type="urn:cmp:problem:calibration:voce-candidate-projection",
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
        raise RuntimeError("Voce projection route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> VoceProjectionHttpError:
    return VoceProjectionHttpError(
        context=context,
        status_code=503,
        title="Voce Candidate projection service unavailable",
        detail="The authoritative Modeling, Calibration, or Artifact store is not configured.",
        code="CMP-CALIBRATION-0035",
    )


def _translate(context: SecurityContext, error: Exception) -> VoceProjectionHttpError:
    if isinstance(
        error,
        (
            VoceCandidateSelectionNotFound,
            VoceCalibrationNotFound,
            ArtifactNotFound,
            AggregateNotFound,
        ),
    ):
        return VoceProjectionHttpError(
            context=context,
            status_code=404,
            title="Voce Candidate projection resource not found",
            detail=(
                "No requested Selection, Candidate, Run, source revision, or Artifact is visible."
            ),
            code="CMP-CALIBRATION-0031",
        )
    if isinstance(error, (InvalidVoceCandidateSelection, InvalidVoceProjection, ValueError)):
        return VoceProjectionHttpError(
            context=context,
            status_code=422,
            title="Invalid Voce Candidate projection request",
            detail=(
                "Use one succeeded Run and converged Candidate, a human selection reason, "
                "21..501 fixed-grid points, and explicit constant-extension acknowledgement."
            ),
            code="CMP-CALIBRATION-0032",
        )
    if isinstance(
        error,
        (
            VoceCandidateSelectionConflict,
            VoceCandidateSelectionError,
            VoceCalibrationConflict,
            ArtifactError,
            RevisionKernelError,
            IntegrityError,
        ),
    ):
        return VoceProjectionHttpError(
            context=context,
            status_code=409,
            title="Voce Candidate projection state conflict",
            detail=(
                "The accepted Candidate, Selection, source scope, Property Set, or immutable "
                "lineage conflicts with the requested projection."
            ),
            code="CMP-CALIBRATION-0033",
        )
    return VoceProjectionHttpError(
        context=context,
        status_code=409,
        title="Voce Candidate projection rejected",
        detail="The Candidate Selection or solver-neutral IR projection could not be completed.",
        code="CMP-CALIBRATION-0033",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_voce_candidate_projection_api(
    application: FastAPI,
    *,
    service: VoceCandidateProjectionService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(VoceProjectionHttpError)
    async def voce_projection_error_handler(
        request: Request, error: VoceProjectionHttpError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store", "X-Request-ID": str(error.context.request_id)},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Modeling permission is not authorized."},
        404: {"model": VoceProjectionProblem},
        409: {"model": VoceProjectionProblem},
        422: {"model": VoceProjectionProblem},
        503: {"model": VoceProjectionProblem},
    }

    @application.post(
        "/api/v1/voce-candidate-selections",
        operation_id="createReferenceVoceCandidateSelection",
        response_model=VoceSelectionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling", "calibration"],
    )
    def create_selection(
        request: Request, response: Response, body: VoceSelectionCreateRequest
    ) -> VoceSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_selection(
                context,
                decision,
                CreateVoceCandidateSelection(
                    classification=body.classification,
                    selection_label=body.selection_label,
                    voce_calibration_run_id=body.voce_calibration_run_id,
                    voce_calibration_candidate_id=body.voce_calibration_candidate_id,
                    selection_reason=body.selection_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return VoceSelectionResponse.from_snapshot(result)

    @application.get(
        "/api/v1/voce-candidate-selections/{selection_id}",
        operation_id="getReferenceVoceCandidateSelection",
        response_model=VoceSelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling", "calibration"],
    )
    def get_selection(
        request: Request, response: Response, selection_id: UUID
    ) -> VoceSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_selection(context, decision, selection_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return VoceSelectionResponse.from_snapshot(result)

    @application.post(
        "/api/v1/voce-candidate-selections/{selection_id}/tabulated-plasticity-models",
        operation_id="projectSelectedReferenceVoceCandidate",
        response_model=TabulatedPlasticityModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling", "calibration"],
    )
    async def project(
        request: Request,
        response: Response,
        selection_id: UUID,
        body: VoceProjectionRequest,
    ) -> TabulatedPlasticityModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = await service.project(
                context,
                decision,
                selection_id,
                ProjectSelectedVoceCandidate(
                    selection_revision_id=body.selection_revision_id,
                    sampling_point_count=body.sampling_point_count,
                    extension_max_true_plastic_strain=body.extension_max_true_plastic_strain,
                    acknowledge_constant_extension=body.acknowledge_constant_extension,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return TabulatedPlasticityModelResponse.from_snapshot(result)
