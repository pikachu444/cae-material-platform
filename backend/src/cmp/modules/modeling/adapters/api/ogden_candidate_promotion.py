"""Protected API for human Ogden Candidate Selection and iterative IR promotion."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.api.ogden_prony import OgdenPronyModelResponse
from cmp.modules.modeling.application.ogden_candidate_promotion import (
    CreateOgdenCandidateSelection,
    OgdenCandidatePromotionService,
    OgdenCandidateSelectionSnapshot,
    PromoteSelectedOgdenCandidate,
)
from cmp.modules.modeling.domain.reference_ogden_candidate_selection import (
    InvalidOgdenCandidateSelection,
    OgdenCandidateSelectionConflict,
    OgdenCandidateSelectionNotFound,
    ReferenceOgdenCandidateSelectionContent,
)
from cmp.modules.modeling.domain.reference_ogden_prony import (
    InvalidReferenceOgdenProny,
    ReferenceOgdenPronyConflict,
)
from cmp.shared.contracts.revisions import (
    InvalidRevisionETag,
    RevisionETag,
    RevisionMetadataResponse,
    RevisionPreconditionFailed,
    require_matching_if_match,
)
from cmp.shared.domain.revisions import RevisionConflict

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CreateOgdenSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification = DataClassification.INTERNAL
    selection_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    selection_reason: Reason


class PromoteOgdenSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_revision_id: UUID
    change_reason: Reason


class OgdenSelectionContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_label: str
    ogden_calibration_run_id: UUID
    ogden_calibration_candidate_id: UUID
    candidate_sha256: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    selection_reason: str
    selection_decision: str
    non_production: bool

    @classmethod
    def from_domain(
        cls, value: ReferenceOgdenCandidateSelectionContent
    ) -> OgdenSelectionContentResponse:
        return cls(
            selection_label=value.selection_label,
            ogden_calibration_run_id=value.ogden_calibration_run_id,
            ogden_calibration_candidate_id=value.ogden_calibration_candidate_id,
            candidate_sha256=f"sha256:{value.candidate_sha256}",
            diagnostics_artifact_id=value.diagnostics_artifact_id,
            diagnostics_sha256=f"sha256:{value.diagnostics_sha256}",
            baseline_model_id=value.baseline_model_id,
            baseline_model_revision_id=value.baseline_model_revision_id,
            selection_reason=value.selection_reason,
            selection_decision=value.selection_decision,
            non_production=value.non_production,
        )


class OgdenSelectionRevisionResponse(RevisionMetadataResponse):
    content: OgdenSelectionContentResponse


class OgdenSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ogden_candidate_selection_id: UUID
    current_revision: OgdenSelectionRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(
        cls, value: OgdenCandidateSelectionSnapshot
    ) -> OgdenSelectionResponse:
        metadata = RevisionMetadataResponse.from_record(value.current.record, "draft")
        root = f"/api/v1/ogden-candidate-selections/{value.id}"
        return cls(
            ogden_candidate_selection_id=value.id,
            current_revision=OgdenSelectionRevisionResponse(
                **metadata.model_dump(),
                content=OgdenSelectionContentResponse.from_domain(value.current.content),
            ),
            links={"self": root, "promote": f"{root}/promotions"},
        )


class OgdenSelectionProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class OgdenSelectionHttpError(Exception):
    def __init__(
        self,
        context: SecurityContext,
        status_code: int,
        detail: str,
        *,
        current_etag: RevisionETag | None = None,
    ) -> None:
        self.problem = OgdenSelectionProblem(
            type="urn:cmp:problem:modeling:ogden-candidate-selection",
            title="Ogden Candidate Selection request failed",
            status=status_code,
            detail=detail,
            code=f"CMP-OGDEN-SELECTION-{status_code}",
            trace_id=context.trace_id,
        )
        self.current_etag = current_etag
        super().__init__(detail)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(
        decision, AuthorizationDecision
    ):
        raise RuntimeError("Ogden Selection dependencies did not initialize request scope")
    return context, decision


def _translate(context: SecurityContext, error: Exception) -> OgdenSelectionHttpError:
    if isinstance(error, OgdenCandidateSelectionNotFound):
        return OgdenSelectionHttpError(context, 404, str(error))
    if isinstance(error, (RevisionPreconditionFailed, RevisionConflict)):
        return OgdenSelectionHttpError(
            context,
            412,
            "The Ogden-Prony revision head changed; reload before promoting.",
            current_etag=RevisionETag.from_ref(error.current),
        )
    if isinstance(
        error,
        (OgdenCandidateSelectionConflict, ReferenceOgdenPronyConflict, IntegrityError),
    ):
        detail = (
            "The Candidate or Selection is already used by a promotion."
            if isinstance(error, IntegrityError)
            else str(error)
        )
        return OgdenSelectionHttpError(context, 409, detail)
    if isinstance(
        error,
        (InvalidOgdenCandidateSelection, InvalidReferenceOgdenProny, InvalidRevisionETag),
    ):
        return OgdenSelectionHttpError(context, 422, str(error))
    if isinstance(error, ValueError):
        return OgdenSelectionHttpError(context, 422, str(error))
    return OgdenSelectionHttpError(context, 503, "service is unavailable")


def install_ogden_candidate_promotion_api(
    application: FastAPI,
    *,
    service: OgdenCandidatePromotionService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(OgdenSelectionHttpError)
    async def handle_error(_: Request, error: OgdenSelectionHttpError) -> JSONResponse:
        headers = (
            {"ETag": str(error.current_etag)}
            if error.current_etag is not None
            else None
        )
        return JSONResponse(
            error.problem.model_dump(mode="json"),
            status_code=error.problem.status,
            headers=headers,
        )

    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": OgdenSelectionProblem} for code in (404, 409, 412, 422, 503)
    }

    @application.post(
        "/api/v1/ogden-candidate-selections",
        operation_id="createReferenceOgdenCandidateSelection",
        response_model=OgdenSelectionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    def create_selection(
        request: Request, response: Response, body: CreateOgdenSelectionRequest
    ) -> OgdenSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenSelectionHttpError(context, 503, "service is unavailable")
        try:
            value = service.create_selection(
                context,
                decision,
                CreateOgdenCandidateSelection(
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
        response.headers["Location"] = f"/api/v1/ogden-candidate-selections/{value.id}"
        return OgdenSelectionResponse.from_snapshot(value)

    @application.get(
        "/api/v1/ogden-candidate-selections/{selection_id}",
        operation_id="getReferenceOgdenCandidateSelection",
        response_model=OgdenSelectionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_selection(request: Request, selection_id: UUID) -> OgdenSelectionResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenSelectionHttpError(context, 503, "service is unavailable")
        try:
            return OgdenSelectionResponse.from_snapshot(
                service.get_selection(context, decision, selection_id)
            )
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/ogden-candidate-selections/{selection_id}/promotions",
        operation_id="promoteReferenceOgdenCandidate",
        response_model=OgdenPronyModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
    )
    def promote(
        request: Request,
        response: Response,
        selection_id: UUID,
        body: PromoteOgdenSelectionRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> OgdenPronyModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise OgdenSelectionHttpError(context, 503, "service is unavailable")
        try:
            current = service.get_current_model_for_promotion(
                context, decision, selection_id, body.selection_revision_id
            )
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = service.promote(
                context,
                decision,
                selection_id,
                PromoteSelectedOgdenCandidate(
                    body.selection_revision_id, expected, body.change_reason
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["ETag"] = str(RevisionETag.from_ref(value.current.record.ref))
        response.headers["Location"] = f"/api/v1/ogden-prony-models/{value.id}"
        return OgdenPronyModelResponse.from_snapshot(value)
