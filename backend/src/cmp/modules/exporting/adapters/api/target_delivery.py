"""HTTP contract for the UXC-06C2 atomic native-card delivery command."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.exporting.adapters.api.target_preview import TargetPreviewTargetResponse
from cmp.modules.exporting.application.target_delivery import (
    CreateTargetDelivery,
    DeliveryReceipt,
    TargetDeliveryConflict,
    TargetDeliveryService,
)
from cmp.modules.exporting.domain.neutral_hyperelastic import NeutralHyperelasticExportTarget
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.units.contracts import UnitApplicationResponse, UnitProfilePinInput
from cmp.modules.units.domain.profiles import UnitProfilePin

type Dependency = Callable[..., object]
type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class TargetDeliveryTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    solver: str
    version: str
    unit_system: str


class TargetDeliveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processing_output_id: UUID
    processing_output_revision_id: UUID
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    target: TargetDeliveryTarget
    solver_material_id: Annotated[int, Field(ge=1, le=9_999_999_999)]
    material_name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")]
    preview_identity: Sha256
    expected_mapping_report_sha256: Sha256
    acknowledgement_identity: Sha256 | None = None
    unit_profile: UnitProfilePinInput | None = None


class TargetDeliveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delivery_status: str = "delivered"
    receipt_id: UUID
    delivery_identity: Sha256
    solver_card_id: UUID
    solver_card_revision_id: UUID
    filename: str
    native_sha256: Sha256
    mapping_report_sha256: Sha256
    mapping_statuses: tuple[str, ...]
    source: dict[str, str]
    target: TargetPreviewTargetResponse
    occurred_at: str
    recorded_by: UUID
    unit_profile: UnitProfilePinInput | None
    unit_applications: tuple[UnitApplicationResponse, ...]
    links: dict[str, str]


class DeliveryProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    title: str
    status: int
    detail: str
    code: str
    trace_id: str


class DeliveryHttpError(Exception):
    def __init__(self, context: SecurityContext, status: int, detail: str) -> None:
        self.problem = DeliveryProblem(
            type="urn:cmp:problem:exporting:target-delivery",
            title="Target delivery request failed",
            status=status,
            detail=detail,
            code=f"CMP-TARGET-DELIVERY-{status}",
            trace_id=context.trace_id,
        )


def install_target_delivery_api(
    application: FastAPI,
    *,
    service: TargetDeliveryService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    execute_dependency: Dependency,
) -> None:
    @application.exception_handler(DeliveryHttpError)
    async def error_handler(_: Request, error: DeliveryHttpError) -> JSONResponse:
        return JSONResponse(error.problem.model_dump(), status_code=error.problem.status)

    @application.post(
        "/api/v1/exporting/target-deliveries",
        operation_id="deliverExactTargetPreview",
        response_model=TargetDeliveryResponse,
        responses={code: {"model": DeliveryProblem} for code in (409, 422, 503)},
        dependencies=[Depends(security_dependency), Depends(execute_dependency)],
        tags=["exporting"],
    )
    async def deliver(request: Request, body: TargetDeliveryRequest) -> TargetDeliveryResponse:
        context: SecurityContext = request.state.security_context
        decision: AuthorizationDecision = request.state.authorization_decision
        if service is None:
            raise DeliveryHttpError(
                context, 503, "atomic target-delivery producer is not configured"
            )
        try:
            _, receipt = await service.deliver(
                context,
                decision,
                CreateTargetDelivery(
                    processing_output_id=body.processing_output_id,
                    processing_output_revision_id=body.processing_output_revision_id,
                    neutral_material_id=body.neutral_material_id,
                    neutral_material_revision_id=body.neutral_material_revision_id,
                    target=NeutralHyperelasticExportTarget(
                        body.target.solver, body.target.version, body.target.unit_system
                    ),
                    solver_material_id=body.solver_material_id,
                    material_name=body.material_name,
                    preview_identity=body.preview_identity,
                    expected_mapping_report_sha256=body.expected_mapping_report_sha256,
                    acknowledgement_identity=body.acknowledgement_identity,
                    unit_profile=(
                        None
                        if body.unit_profile is None
                        else UnitProfilePin(
                            profile_id=body.unit_profile.profile_id,
                            revision_id=body.unit_profile.revision_id,
                            content_sha256=body.unit_profile.content_sha256,
                        )
                    ),
                ),
            )
        except TargetDeliveryConflict as error:
            raise DeliveryHttpError(context, 409, str(error)) from error
        except ValueError as error:
            raise DeliveryHttpError(context, 422, str(error)) from error
        return _response(receipt)

    @application.get(
        "/api/v1/exporting/target-deliveries/{receipt_id}",
        operation_id="getTargetDeliveryReceipt",
        response_model=TargetDeliveryResponse,
        responses={code: {"model": DeliveryProblem} for code in (404, 503)},
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["exporting"],
    )
    def get_receipt(request: Request, receipt_id: UUID) -> TargetDeliveryResponse:
        context: SecurityContext = request.state.security_context
        decision: AuthorizationDecision = request.state.authorization_decision
        if service is None:
            raise DeliveryHttpError(
                context, 503, "atomic target-delivery receipt store is not configured"
            )
        receipt = service.get_receipt(context, decision, receipt_id)
        if receipt is None:
            raise DeliveryHttpError(context, 404, "target-delivery receipt was not found")
        return _response(receipt)


def _response(receipt: DeliveryReceipt) -> TargetDeliveryResponse:
    root = f"/api/v1/neutral-solver-cards/{receipt.solver_card_id}"
    return TargetDeliveryResponse(
        receipt_id=receipt.receipt_id,
        delivery_identity=receipt.delivery_identity,
        solver_card_id=receipt.solver_card_id,
        solver_card_revision_id=receipt.solver_card_revision_id,
        filename=receipt.filename,
        native_sha256=receipt.native_sha256,
        mapping_report_sha256=receipt.mapping_report_sha256,
        mapping_statuses=receipt.mapping_statuses,
        source=receipt.source,
        target=TargetPreviewTargetResponse.model_validate(receipt.target),
        occurred_at=receipt.occurred_at,
        recorded_by=receipt.recorded_by,
        unit_profile=(
            None
            if receipt.unit_profile is None
            else UnitProfilePinInput(
                profile_id=receipt.unit_profile.profile_id,
                revision_id=receipt.unit_profile.revision_id,
                content_sha256=receipt.unit_profile.content_sha256,
            )
        ),
        unit_applications=tuple(
            UnitApplicationResponse(
                location=item.location,
                role=item.role.value,
                quantity_semantics=item.quantity_semantics,
                dimension=item.dimension,
                unit_id=item.unit_id,
            )
            for item in receipt.unit_applications
        ),
        links={
            "solver_card": root,
            "preview": f"{root}/preview",
            "download": f"{root}/download",
            "receipt": f"/api/v1/exporting/target-deliveries/{receipt.receipt_id}",
        },
    )
