"""Protected API for human reference Calibration Candidate Selection and IR promotion."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.api.material_models import MaterialModelResponse
from cmp.modules.modeling.application.candidate_selection import (
    CalibrationCandidateSelectionSnapshot,
    CandidateSelectionService,
    CreateReferenceCalibrationCandidateSelection,
    PromoteSelectedReferenceCalibrationCandidate,
    ReviseReferenceCalibrationCandidateSelection,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_calibration_candidate_selection import (
    CandidateSelectionConflict,
    CandidateSelectionError,
    CandidateSelectionNotFound,
    InvalidCandidateSelection,
    ReferenceCalibrationCandidateSelectionContent,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationConflict,
    CalibrationNotFound,
    InvalidCalibrationPlan,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    ModelingError,
    ReferenceModelNotFound,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class CandidateSelectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    selection_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    selection_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CandidateSelectionReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_current_revision_id: UUID
    selection_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    selection_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CandidateSelectionPromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_revision_id: UUID
    expected_material_model_revision_id: UUID
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CandidateSelectionContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_label: str
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    candidate_sha256: str
    selection_reason: str
    selection_decision: str
    domain_acceptance_status: str
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferenceCalibrationCandidateSelectionContent
    ) -> CandidateSelectionContentResponse:
        return cls(
            selection_label=value.selection_label,
            calibration_run_id=value.calibration_run_id,
            calibration_candidate_id=value.calibration_candidate_id,
            candidate_sha256=f"sha256:{value.candidate_sha256}",
            selection_reason=value.selection_reason,
            selection_decision=value.selection_decision,
            domain_acceptance_status="accepted_by_human_for_reference_ir_promotion",
            non_production=value.non_production,
        )


class CandidateSelectionRevisionResponse(RevisionMetadataResponse):
    content: CandidateSelectionContentResponse

    @classmethod
    def from_snapshot(
        cls,
        value: RevisionSnapshot[ReferenceCalibrationCandidateSelectionContent],
    ) -> CandidateSelectionRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=CandidateSelectionContentResponse.from_domain(value.content),
        )


class CandidateSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_candidate_selection_id: UUID
    current_revision: CandidateSelectionRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(
        cls, value: CalibrationCandidateSelectionSnapshot
    ) -> CandidateSelectionResponse:
        root = f"/api/v1/calibration-candidate-selections/{value.id}"
        return cls(
            calibration_candidate_selection_id=value.id,
            current_revision=CandidateSelectionRevisionResponse.from_snapshot(value.current),
            links={"self": root, "promote_material_model": f"{root}/promote-material-model"},
        )


class CandidateSelectionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[CandidateSelectionResponse, ...]


class CandidateSelectionPromotionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calibration_candidate_selection_id: UUID
    calibration_candidate_selection_revision_id: UUID
    material_model: MaterialModelResponse


class CandidateSelectionProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-CALIBRATION-[0-9]{4}$")]
    trace_id: Label


class CandidateSelectionHttpError(Exception):
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
        self.problem = CandidateSelectionProblem(
            type="urn:cmp:problem:calibration",
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
        raise RuntimeError(
            "Candidate Selection route dependencies did not initialize request scope"
        )
    return context, decision


def _unavailable(context: SecurityContext) -> CandidateSelectionHttpError:
    return CandidateSelectionHttpError(
        context=context,
        status_code=503,
        title="Candidate Selection service unavailable",
        detail="The authoritative Candidate Selection store is not configured for this deployment.",
        code="CMP-CALIBRATION-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> CandidateSelectionHttpError:
    if isinstance(
        error,
        (
            CandidateSelectionNotFound,
            CalibrationNotFound,
            ReferenceModelNotFound,
            AggregateNotFound,
        ),
    ):
        return CandidateSelectionHttpError(
            context=context,
            status_code=404,
            title="Candidate Selection resource not found",
            detail=(
                "No requested immutable Candidate Selection, Calibration Candidate, or Material "
                "Model is visible in this tenant."
            ),
            code="CMP-CALIBRATION-0001",
        )
    if isinstance(error, (InvalidCandidateSelection, InvalidCalibrationPlan, ValueError)):
        return CandidateSelectionHttpError(
            context=context,
            status_code=422,
            title="Invalid Candidate Selection request",
            detail="A human selection reason and one eligible converged Candidate are required.",
            code="CMP-CALIBRATION-0002",
        )
    if isinstance(
        error,
        (
            CandidateSelectionConflict,
            CandidateSelectionError,
            CalibrationConflict,
            ModelingError,
            RevisionKernelError,
            IntegrityError,
        ),
    ):
        return CandidateSelectionHttpError(
            context=context,
            status_code=409,
            title="Candidate Selection state conflict",
            detail=(
                "The Candidate, Selection, or source Material Model revision is immutable or "
                "stale."
            ),
            code="CMP-CALIBRATION-0003",
        )
    return CandidateSelectionHttpError(
        context=context,
        status_code=409,
        title="Candidate Selection command rejected",
        detail="The requested human selection or IR promotion could not be completed.",
        code="CMP-CALIBRATION-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_candidate_selection_api(
    application: FastAPI,
    *,
    service: CandidateSelectionService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(CandidateSelectionHttpError)
    async def candidate_selection_error_handler(
        request: Request, error: CandidateSelectionHttpError
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
        403: {"description": "Modeling read or write is not authorized."},
        404: {"description": "No visible Candidate Selection, Candidate, Run, or Model matches."},
        409: {"description": "Immutable Selection, Candidate, or source Model state conflicts."},
        422: {"description": "Candidate Selection inputs or selection reason are invalid."},
        503: {"description": "Candidate Selection service unavailable."},
    }

    @application.post(
        "/api/v1/calibration-candidate-selections",
        operation_id="createReferenceCalibrationCandidateSelection",
        response_model=CandidateSelectionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling", "calibration"],
        summary="Record an explicit human acceptance of one converged Candidate.",
    )
    def create_selection(
        request: Request, response: Response, body: CandidateSelectionCreateRequest
    ) -> CandidateSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_selection(
                context,
                decision,
                CreateReferenceCalibrationCandidateSelection(
                    classification=body.classification,
                    selection_label=body.selection_label,
                    calibration_run_id=body.calibration_run_id,
                    calibration_candidate_id=body.calibration_candidate_id,
                    selection_reason=body.selection_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return CandidateSelectionResponse.from_snapshot(value)

    @application.patch(
        "/api/v1/calibration-candidate-selections/{selection_id}",
        operation_id="reviseReferenceCalibrationCandidateSelection",
        response_model=CandidateSelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling", "calibration"],
        summary="Append a new immutable human Selection revision for the same Calibration Run.",
    )
    def revise_selection(
        request: Request,
        response: Response,
        selection_id: UUID,
        body: CandidateSelectionReviseRequest,
    ) -> CandidateSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.revise_selection(
                context,
                decision,
                selection_id,
                ReviseReferenceCalibrationCandidateSelection(
                    expected_current_revision_id=body.expected_current_revision_id,
                    selection_label=body.selection_label,
                    calibration_run_id=body.calibration_run_id,
                    calibration_candidate_id=body.calibration_candidate_id,
                    selection_reason=body.selection_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return CandidateSelectionResponse.from_snapshot(value)

    @application.get(
        "/api/v1/calibration-candidate-selections",
        operation_id="listCalibrationCandidateSelections",
        response_model=CandidateSelectionListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling", "calibration"],
        summary="List current human Candidate Selection heads visible in this tenant.",
    )
    def list_selections(
        request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 100
    ) -> CandidateSelectionListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_selections(context, decision, limit=limit)
        except Exception as error:
            raise _translate(context, error) from error
        return CandidateSelectionListResponse(
            items=tuple(CandidateSelectionResponse.from_snapshot(value) for value in values)
        )

    @application.get(
        "/api/v1/calibration-candidate-selections/{selection_id}",
        operation_id="getCalibrationCandidateSelection",
        response_model=CandidateSelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling", "calibration"],
        summary="Read one current immutable human Candidate Selection revision.",
    )
    def get_selection(
        request: Request, response: Response, selection_id: UUID
    ) -> CandidateSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_selection(context, decision, selection_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return CandidateSelectionResponse.from_snapshot(value)

    @application.post(
        "/api/v1/calibration-candidate-selections/{selection_id}/promote-material-model",
        operation_id="promoteSelectedReferenceCalibrationCandidate",
        response_model=CandidateSelectionPromotionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling", "calibration"],
        summary=(
            "Append a new IR revision from an accepted Candidate only when the source IR is "
            "current."
        ),
    )
    def promote_selected_candidate(
        request: Request,
        response: Response,
        selection_id: UUID,
        body: CandidateSelectionPromotionRequest,
    ) -> CandidateSelectionPromotionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            model = service.promote_selected_candidate(
                context,
                decision,
                selection_id,
                PromoteSelectedReferenceCalibrationCandidate(
                    selection_revision_id=body.selection_revision_id,
                    expected_material_model_revision_id=body.expected_material_model_revision_id,
                    change_reason=body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, model.current.record)
        return CandidateSelectionPromotionResponse(
            calibration_candidate_selection_id=selection_id,
            calibration_candidate_selection_revision_id=body.selection_revision_id,
            material_model=MaterialModelResponse.from_snapshot(model),
        )
