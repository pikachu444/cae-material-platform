"""Protected API for human Prony Candidate Selection and IR promotion."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.api.linear_viscoelasticity import (
    LinearViscoelasticModelResponse,
)
from cmp.modules.modeling.application.prony_candidate_promotion import (
    CreatePronyCandidateSelection,
    PromoteSelectedPronyCandidate,
    PronyCandidatePromotionService,
    PronyCandidateSelectionSnapshot,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    InvalidLinearViscoelasticModel,
    LinearViscoelasticConflict,
)
from cmp.modules.modeling.domain.reference_prony_candidate_selection import (
    InvalidPronyCandidateSelection,
    PronyCandidateSelectionConflict,
    PronyCandidateSelectionNotFound,
    ReferencePronyCandidateSelectionContent,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]

LOGGER = logging.getLogger(__name__)


class CreatePronySelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification = DataClassification.INTERNAL
    selection_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    selection_reason: Reason


class PromotePronySelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_revision_id: UUID
    change_reason: Reason


class PronySelectionContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_label: str
    prony_calibration_run_id: UUID
    prony_calibration_candidate_id: UUID
    candidate_sha256: str
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    selection_reason: str
    selection_decision: str
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferencePronyCandidateSelectionContent
    ) -> PronySelectionContentResponse:
        return cls(
            selection_label=value.selection_label,
            prony_calibration_run_id=value.prony_calibration_run_id,
            prony_calibration_candidate_id=value.prony_calibration_candidate_id,
            candidate_sha256=f"sha256:{value.candidate_sha256}",
            baseline_model_id=value.baseline_model_id,
            baseline_model_revision_id=value.baseline_model_revision_id,
            selection_reason=value.selection_reason,
            selection_decision=value.selection_decision,
            non_production=value.non_production,
        )


class PronySelectionRevisionResponse(RevisionMetadataResponse):
    content: PronySelectionContentResponse


class PronySelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prony_candidate_selection_id: UUID
    current_revision: PronySelectionRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(
        cls, value: PronyCandidateSelectionSnapshot
    ) -> PronySelectionResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/prony-candidate-selections/{value.id}"
        return cls(
            prony_candidate_selection_id=value.id,
            current_revision=PronySelectionRevisionResponse(
                **metadata.model_dump(),
                content=PronySelectionContentResponse.from_domain(value.current.content),
            ),
            links={"self": root, "promote": f"{root}/promotions"},
        )


class PronySelectionProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class PronySelectionHttpError(Exception):
    def __init__(self, context: SecurityContext, status_code: int, detail: str) -> None:
        self.problem = PronySelectionProblem(
            type="urn:cmp:problem:modeling:prony-candidate-selection",
            title="Prony Candidate Selection request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-PRONY-SELECTION-{status_code}",
            trace_id=context.trace_id,
        )
        super().__init__(detail)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(
        decision, AuthorizationDecision
    ):
        raise RuntimeError("Prony Selection dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> PronySelectionHttpError:
    if isinstance(error, PronyCandidateSelectionNotFound):
        return PronySelectionHttpError(context, 404, str(error))
    if isinstance(error, (PronyCandidateSelectionConflict, LinearViscoelasticConflict)):
        return PronySelectionHttpError(context, 409, str(error))
    if isinstance(
        error,
        (InvalidPronyCandidateSelection, InvalidLinearViscoelasticModel, ValueError),
    ):
        return PronySelectionHttpError(context, 422, str(error))
    LOGGER.exception("Unhandled Prony Candidate Selection failure", exc_info=error)
    return PronySelectionHttpError(context, 503, "service is unavailable")


def install_prony_candidate_promotion_api(
    application: FastAPI,
    *,
    service: PronyCandidatePromotionService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(PronySelectionHttpError)
    async def handle_error(
        _: Request, error: PronySelectionHttpError
    ) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(mode="json"), status_code=error.problem.status)

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": PronySelectionProblem} for code in (404, 409, 422, 503)
    }

    @application.post(
        "/api/v1/prony-candidate-selections",
        operation_id="createReferencePronyCandidateSelection",
        response_model=PronySelectionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    def create_selection(
        request: Request, response: Response, body: CreatePronySelectionRequest
    ) -> PronySelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise PronySelectionHttpError(context, 503, "service is unavailable")
        try:
            value = service.create_selection(
                context,
                decision,
                CreatePronyCandidateSelection(
                    body.classification,
                    body.selection_label,
                    body.calibration_run_id,
                    body.calibration_candidate_id,
                    body.selection_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        response.headers["Location"] = f"/api/v1/prony-candidate-selections/{value.id}"
        return PronySelectionResponse.from_snapshot(value)

    @application.get(
        "/api/v1/prony-candidate-selections/{selection_id}",
        operation_id="getReferencePronyCandidateSelection",
        response_model=PronySelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_selection(request: Request, selection_id: UUID) -> PronySelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise PronySelectionHttpError(context, 503, "service is unavailable")
        try:
            return PronySelectionResponse.from_snapshot(
                service.get_selection(context, decision, selection_id)
            )
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/prony-candidate-selections/{selection_id}/promotions",
        operation_id="promoteReferencePronyCandidate",
        response_model=LinearViscoelasticModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    def promote(
        request: Request,
        response: Response,
        selection_id: UUID,
        body: PromotePronySelectionRequest,
    ) -> LinearViscoelasticModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise PronySelectionHttpError(context, 503, "service is unavailable")
        try:
            value = service.promote(
                context,
                decision,
                selection_id,
                PromoteSelectedPronyCandidate(
                    body.selection_revision_id, body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        response.headers["Location"] = f"/api/v1/linear-viscoelastic-models/{value.id}"
        return LinearViscoelasticModelResponse.from_snapshot(value)
