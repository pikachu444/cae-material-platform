"""HTTP resources for governed Test Campaign and execution context."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.testing.adapters.api.testing import _etag, _scope, _translate, _unavailable
from cmp.modules.testing.application.test_context import (
    CalibrationSnapshot,
    CampaignSnapshot,
    ConditionSnapshot,
    CreateCalibration,
    CreateCampaign,
    CreateCondition,
    CreateInstrument,
    CreateRunContext,
    InstrumentSnapshot,
    RunContextSnapshot,
    TestContextService,
)
from cmp.modules.testing.domain.test_context import (
    CalibrationResult,
    InstrumentCalibrationContent,
    InstrumentContent,
    LoadingRateUnit,
    StandardConformance,
    TestCampaignContent,
    TestConditionContent,
    TestRunContextContent,
    calibration_canonical,
    campaign_canonical,
    condition_canonical,
    instrument_canonical,
    run_context_canonical,
)
from cmp.shared.contracts.revisions import RevisionMetadataResponse

type Dependency = Callable[..., object]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class CampaignContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_method_id: UUID
    test_method_revision_id: UUID
    campaign_code: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    objective: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    population_description: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    planned_specimen_count: int = Field(ge=1, le=1_000_000)
    standard_conformance: StandardConformance
    standard_designation: str | None = None
    standard_edition: str | None = None
    standard_deviation_reason: str | None = None
    reference_only: bool = True

    def to_domain(self) -> TestCampaignContent:
        return TestCampaignContent(**self.model_dump())


class CampaignCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: CampaignContentInput
    change_reason: Reason


class InstrumentContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_code: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    serial_number: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    manufacturer: str | None = None
    model: str | None = None
    location: str | None = None
    description: str | None = None

    def to_domain(self) -> InstrumentContent:
        return InstrumentContent(**self.model_dump())


class InstrumentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification
    content: InstrumentContentInput
    change_reason: Reason


class CalibrationContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_revision_id: UUID
    calibration_code: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    certificate_reference: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    provider: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    calibrated_at: datetime
    valid_from: datetime
    valid_until: datetime
    result: CalibrationResult
    limitation_note: str | None = None

    def to_domain(self, instrument_id: UUID) -> InstrumentCalibrationContent:
        return InstrumentCalibrationContent(instrument_id=instrument_id, **self.model_dump())


class CalibrationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: CalibrationContentInput
    change_reason: Reason


class ConditionContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_method_id: UUID
    test_method_revision_id: UUID
    captured_at: datetime
    temperature_setpoint_k: Decimal | None = None
    temperature_observed_k: Decimal | None = None
    humidity_setpoint_pct: Decimal | None = None
    humidity_observed_pct: Decimal | None = None
    loading_rate_value: Decimal | None = None
    loading_rate_unit: LoadingRateUnit | None = None
    orientation: str | None = None
    medium: str | None = None
    note: str | None = None

    def to_domain(self) -> TestConditionContent:
        return TestConditionContent(**self.model_dump())


class ConditionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: ConditionContentInput
    change_reason: Reason


class RunContextContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_run_revision_id: UUID
    test_campaign_id: UUID
    test_campaign_revision_id: UUID
    test_condition_id: UUID
    test_condition_revision_id: UUID
    instrument_id: UUID
    instrument_revision_id: UUID
    calibration_id: UUID
    calibration_revision_id: UUID
    note: str | None = None

    def to_domain(self, test_run_id: UUID) -> TestRunContextContent:
        return TestRunContextContent(test_run_id=test_run_id, **self.model_dump())


class RunContextCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: RunContextContentInput
    change_reason: Reason


class ContextRevisionResponse(RevisionMetadataResponse):
    content: dict[str, Any]


class ContextResourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: UUID
    current_revision: ContextRevisionResponse
    links: dict[str, str]


class ContextListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[ContextResourceResponse, ...]


def _resource(
    resource_id: UUID,
    record: Any,
    content: dict[str, object],
    root: str,
) -> ContextResourceResponse:
    metadata = RevisionMetadataResponse.from_record(record, "draft")
    return ContextResourceResponse(
        resource_id=resource_id,
        current_revision=ContextRevisionResponse(**metadata.model_dump(), content=content),
        links={"self": root, "revisions": f"{root}/revisions"},
    )


def _campaign(value: CampaignSnapshot) -> ContextResourceResponse:
    return _resource(
        value.id,
        value.current.record,
        campaign_canonical(value.current.content),
        f"/api/v1/test-campaigns/{value.id}",
    )


def _instrument(value: InstrumentSnapshot) -> ContextResourceResponse:
    return _resource(
        value.id,
        value.current.record,
        instrument_canonical(value.current.content),
        f"/api/v1/instruments/{value.id}",
    )


def _calibration(value: CalibrationSnapshot) -> ContextResourceResponse:
    return _resource(
        value.id,
        value.current.record,
        calibration_canonical(value.current.content),
        f"/api/v1/instrument-calibrations/{value.id}",
    )


def _condition(value: ConditionSnapshot) -> ContextResourceResponse:
    return _resource(
        value.id,
        value.current.record,
        condition_canonical(value.current.content),
        f"/api/v1/test-conditions/{value.id}",
    )


def _run_context(value: RunContextSnapshot) -> ContextResourceResponse:
    return _resource(
        value.id,
        value.current.record,
        run_context_canonical(value.current.content),
        f"/api/v1/test-run-contexts/{value.id}",
    )


def install_test_context_api(
    application: FastAPI,
    *,
    service: TestContextService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Testing permission required."},
        404: {"description": "Exact source revision not found."},
        409: {"description": "Execution context conflicts with immutable source state."},
        422: {"description": "Invalid explicit execution context."},
        503: {"description": "Testing service unavailable."},
    }

    def scope(request: Request, *, write: bool = False) -> tuple[Any, Any]:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        return context, decision

    @application.get(
        "/api/v1/test-campaigns",
        operation_id="listCampaigns",
        response_model=ContextListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing-context"],
    )
    def list_campaigns(request: Request) -> ContextListResponse:
        context, decision = scope(request)
        assert service is not None
        try:
            return ContextListResponse(
                items=tuple(_campaign(v) for v in service.list_campaigns(context, decision))
            )
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/test-campaigns",
        operation_id="createCampaign",
        response_model=ContextResourceResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing-context"],
    )
    def create_campaign(
        request: Request, response: Response, body: CampaignCreateRequest
    ) -> ContextResourceResponse:
        context, decision = scope(request, write=True)
        assert service is not None
        try:
            result = service.create_campaign(
                context, decision, CreateCampaign(body.content.to_domain(), body.change_reason)
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return _campaign(result)

    @application.get(
        "/api/v1/instruments",
        operation_id="listInstruments",
        response_model=ContextListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing-context"],
    )
    def list_instruments(request: Request) -> ContextListResponse:
        context, decision = scope(request)
        assert service is not None
        try:
            return ContextListResponse(
                items=tuple(_instrument(v) for v in service.list_instruments(context, decision))
            )
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/instruments",
        operation_id="createInstrument",
        response_model=ContextResourceResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing-context"],
    )
    def create_instrument(
        request: Request, response: Response, body: InstrumentCreateRequest
    ) -> ContextResourceResponse:
        context, decision = scope(request, write=True)
        assert service is not None
        try:
            result = service.create_instrument(
                context,
                decision,
                CreateInstrument(body.classification, body.content.to_domain(), body.change_reason),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return _instrument(result)

    @application.get(
        "/api/v1/instruments/{instrument_id}/calibrations",
        operation_id="listCalibrations",
        response_model=ContextListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing-context"],
    )
    def list_calibrations(request: Request, instrument_id: UUID) -> ContextListResponse:
        context, decision = scope(request)
        assert service is not None
        try:
            return ContextListResponse(
                items=tuple(
                    _calibration(v)
                    for v in service.list_calibrations(context, decision, instrument_id)
                )
            )
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/instruments/{instrument_id}/calibrations",
        operation_id="createCalibration",
        response_model=ContextResourceResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing-context"],
    )
    def create_calibration(
        request: Request, response: Response, instrument_id: UUID, body: CalibrationCreateRequest
    ) -> ContextResourceResponse:
        context, decision = scope(request, write=True)
        assert service is not None
        try:
            result = service.create_calibration(
                context,
                decision,
                CreateCalibration(body.content.to_domain(instrument_id), body.change_reason),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return _calibration(result)

    @application.get(
        "/api/v1/test-conditions",
        operation_id="listConditions",
        response_model=ContextListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing-context"],
    )
    def list_conditions(request: Request) -> ContextListResponse:
        context, decision = scope(request)
        assert service is not None
        try:
            return ContextListResponse(
                items=tuple(_condition(v) for v in service.list_conditions(context, decision))
            )
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/test-conditions",
        operation_id="createCondition",
        response_model=ContextResourceResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing-context"],
    )
    def create_condition(
        request: Request, response: Response, body: ConditionCreateRequest
    ) -> ContextResourceResponse:
        context, decision = scope(request, write=True)
        assert service is not None
        try:
            result = service.create_condition(
                context, decision, CreateCondition(body.content.to_domain(), body.change_reason)
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return _condition(result)

    @application.get(
        "/api/v1/test-runs/{test_run_id}/context",
        operation_id="getRunContext",
        response_model=ContextResourceResponse | None,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing-context"],
    )
    def get_run_context(request: Request, test_run_id: UUID) -> ContextResourceResponse | None:
        context, decision = scope(request)
        assert service is not None
        try:
            result = service.get_run_context_for_run(context, decision, test_run_id)
            return None if result is None else _run_context(result)
        except Exception as error:
            raise _translate(context, error) from error

    @application.post(
        "/api/v1/test-runs/{test_run_id}/context",
        operation_id="createRunContext",
        response_model=ContextResourceResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing-context"],
    )
    def create_run_context(
        request: Request, response: Response, test_run_id: UUID, body: RunContextCreateRequest
    ) -> ContextResourceResponse:
        context, decision = scope(request, write=True)
        assert service is not None
        try:
            result = service.create_run_context(
                context,
                decision,
                CreateRunContext(body.content.to_domain(test_run_id), body.change_reason),
            )
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return _run_context(result)
