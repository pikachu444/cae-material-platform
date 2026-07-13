"""Protected Specimen, reference Test Method, and Test Run HTTP resources."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.application.service import (
    CreateReferenceTensileMethod,
    CreateReferenceTensileRun,
    CreateSpecimen,
    RevisionSnapshot,
    SpecimenSnapshot,
    TestingService,
    TestMethodSnapshot,
    TestRunSnapshot,
)
from cmp.modules.testing.domain.reference_tensile import (
    InvalidTestingData,
    SpecimenContent,
    TestingConflict,
    TestingError,
    TestingNotFound,
    TestMethodContent,
    TestRunContent,
)
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateAlreadyExists, RevisionKernelError, RevisionRecord

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class SpecimenCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_state_revision_id: UUID
    specimen_code: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    orientation: Annotated[str, StringConstraints(min_length=1, max_length=100)] | None = None
    preparation_note: Annotated[str, StringConstraints(min_length=1, max_length=2000)] | None = None
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReferenceMethodCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class TestRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    performed_at: datetime
    test_temperature_k: float | None = Field(default=None, gt=0.0)
    crosshead_speed_mm_per_min: float | None = Field(default=None, gt=0.0)
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class SpecimenContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    specimen_code: str
    orientation: str | None
    preparation_note: str | None

    @classmethod
    def from_domain(cls, value: SpecimenContent) -> SpecimenContentResponse:
        return cls(
            material_id=value.material_id,
            material_revision_id=value.material_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            specimen_code=value.specimen_code,
            orientation=value.orientation,
            preparation_note=value.preparation_note,
        )


class TestMethodContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_code: str
    display_name: str
    reference_only: bool

    @classmethod
    def from_domain(cls, value: TestMethodContent) -> TestMethodContentResponse:
        return cls(
            method_code=value.method_code,
            display_name=value.display_name,
            reference_only=value.reference_only,
        )


class TestRunContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: str
    performed_at: datetime
    test_temperature_k: float | None
    crosshead_speed_mm_per_min: float | None
    reference_only: bool

    @classmethod
    def from_domain(cls, value: TestRunContent) -> TestRunContentResponse:
        return cls(
            specimen_id=value.specimen_id,
            specimen_revision_id=value.specimen_revision_id,
            test_method_id=value.test_method_id,
            test_method_revision_id=value.test_method_revision_id,
            run_label=value.run_label,
            performed_at=value.performed_at,
            test_temperature_k=value.test_temperature_k,
            crosshead_speed_mm_per_min=value.crosshead_speed_mm_per_min,
            reference_only=value.reference_only,
        )


class SpecimenRevisionResponse(RevisionMetadataResponse):
    content: SpecimenContentResponse

    @classmethod
    def from_snapshot(cls, value: RevisionSnapshot[SpecimenContent]) -> SpecimenRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=SpecimenContentResponse.from_domain(value.content),
        )


class TestMethodRevisionResponse(RevisionMetadataResponse):
    content: TestMethodContentResponse

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[TestMethodContent]
    ) -> TestMethodRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=TestMethodContentResponse.from_domain(value.content),
        )


class TestRunRevisionResponse(RevisionMetadataResponse):
    content: TestRunContentResponse

    @classmethod
    def from_snapshot(cls, value: RevisionSnapshot[TestRunContent]) -> TestRunRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=TestRunContentResponse.from_domain(value.content),
        )


class SpecimenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specimen_id: UUID
    material_state_id: UUID
    current_revision: SpecimenRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: SpecimenSnapshot) -> SpecimenResponse:
        return cls(
            specimen_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=SpecimenRevisionResponse.from_snapshot(value.current),
            links={"self": f"/api/v1/specimens/{value.id}"},
        )


class TestMethodResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_method_id: UUID
    current_revision: TestMethodRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: TestMethodSnapshot) -> TestMethodResponse:
        return cls(
            test_method_id=value.id,
            current_revision=TestMethodRevisionResponse.from_snapshot(value.current),
            links={"self": f"/api/v1/test-methods/{value.id}"},
        )


class TestRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_run_id: UUID
    specimen_id: UUID
    test_method_id: UUID
    current_revision: TestRunRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(cls, value: TestRunSnapshot) -> TestRunResponse:
        return cls(
            test_run_id=value.id,
            specimen_id=value.specimen_id,
            test_method_id=value.test_method_id,
            current_revision=TestRunRevisionResponse.from_snapshot(value.current),
            links={"self": f"/api/v1/test-runs/{value.id}"},
        )


class SpecimenListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[SpecimenResponse, ...]


class TestMethodListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[TestMethodResponse, ...]


class TestRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[TestRunResponse, ...]


class TestingProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-TESTING-[0-9]{4}$")]
    trace_id: Label


class TestingHttpError(Exception):
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
        self.problem = TestingProblem(
            type="urn:cmp:problem:testing",
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
        raise RuntimeError("Testing route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> TestingHttpError:
    return TestingHttpError(
        context=context,
        status_code=503,
        title="Testing service unavailable",
        detail="The authoritative testing store is not configured for this deployment.",
        code="CMP-TESTING-0005",
    )


def _translate(context: SecurityContext, error: Exception) -> TestingHttpError:
    if isinstance(error, TestingNotFound):
        return TestingHttpError(
            context=context,
            status_code=404,
            title="Testing resource not found",
            detail="No requested concrete testing record is visible in the selected tenant.",
            code="CMP-TESTING-0001",
        )
    if isinstance(error, (InvalidTestingData, ValueError)):
        return TestingHttpError(
            context=context,
            status_code=422,
            title="Invalid testing request",
            detail=(
                "The reference testing record requires valid explicit fields and "
                "concrete revisions."
            ),
            code="CMP-TESTING-0002",
        )
    if isinstance(
        error,
        (TestingConflict, AggregateAlreadyExists, RevisionKernelError, IntegrityError),
    ):
        return TestingHttpError(
            context=context,
            status_code=409,
            title="Testing state conflict",
            detail="The testing command conflicts with immutable source or revision state.",
            code="CMP-TESTING-0003",
        )
    if isinstance(error, TestingError):
        return TestingHttpError(
            context=context,
            status_code=409,
            title="Testing command rejected",
            detail="The testing command could not be completed.",
            code="CMP-TESTING-0003",
        )
    return TestingHttpError(
        context=context,
        status_code=409,
        title="Testing command rejected",
        detail="The testing command could not be completed.",
        code="CMP-TESTING-0003",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_testing_api(
    application: FastAPI,
    *,
    service: TestingService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(TestingHttpError)
    async def testing_error_handler(request: Request, error: TestingHttpError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store", "X-Request-ID": str(error.context.request_id)},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"model": TestingProblem},
        404: {"model": TestingProblem},
        409: {"model": TestingProblem},
        422: {"model": TestingProblem},
        503: {"model": TestingProblem},
    }

    @application.post(
        "/api/v1/material-states/{material_state_id}/specimens",
        operation_id="createSpecimen",
        response_model=SpecimenResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def create_specimen(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: SpecimenCreateRequest,
    ) -> SpecimenResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_specimen(
                context,
                decision,
                CreateSpecimen(
                    material_state_id,
                    body.material_state_revision_id,
                    body.specimen_code,
                    body.orientation,
                    body.preparation_note,
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/specimens/{result.id}"
        _etag(response, result.current.record)
        return SpecimenResponse.from_snapshot(result)

    @application.get(
        "/api/v1/material-states/{material_state_id}/specimens",
        operation_id="listMaterialStateSpecimens",
        response_model=SpecimenListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def list_specimens(request: Request, material_state_id: UUID) -> SpecimenListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_specimens_for_material_state(context, decision, material_state_id)
        except Exception as error:
            raise _translate(context, error) from error
        return SpecimenListResponse(
            items=tuple(SpecimenResponse.from_snapshot(item) for item in items)
        )

    @application.post(
        "/api/v1/test-methods/reference-uniaxial-tensile",
        operation_id="createReferenceTensileTestMethod",
        response_model=TestMethodResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def create_reference_method(
        request: Request, response: Response, body: ReferenceMethodCreateRequest
    ) -> TestMethodResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_tensile_method(
                context,
                decision,
                CreateReferenceTensileMethod(body.classification, body.change_reason),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-methods/{result.id}"
        _etag(response, result.current.record)
        return TestMethodResponse.from_snapshot(result)

    @application.get(
        "/api/v1/test-methods",
        operation_id="listTestMethods",
        response_model=TestMethodListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def list_methods(request: Request) -> TestMethodListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_test_methods(context, decision)
        except Exception as error:
            raise _translate(context, error) from error
        return TestMethodListResponse(
            items=tuple(TestMethodResponse.from_snapshot(item) for item in items)
        )

    @application.post(
        "/api/v1/test-runs",
        operation_id="createReferenceTensileTestRun",
        response_model=TestRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["testing"],
    )
    def create_test_run(
        request: Request, response: Response, body: TestRunCreateRequest
    ) -> TestRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_reference_tensile_run(
                context,
                decision,
                CreateReferenceTensileRun(
                    body.specimen_id,
                    body.specimen_revision_id,
                    body.test_method_id,
                    body.test_method_revision_id,
                    body.run_label,
                    body.performed_at,
                    body.test_temperature_k,
                    body.crosshead_speed_mm_per_min,
                    body.change_reason,
                ),
            )
        except Exception as error:
            raise _translate(context, error) from error
        response.headers["Location"] = f"/api/v1/test-runs/{result.id}"
        _etag(response, result.current.record)
        return TestRunResponse.from_snapshot(result)

    @application.get(
        "/api/v1/test-runs/{test_run_id}",
        operation_id="getTestRun",
        response_model=TestRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def get_test_run(request: Request, test_run_id: UUID, response: Response) -> TestRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.get_test_run(context, decision, test_run_id)
        except Exception as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return TestRunResponse.from_snapshot(result)

    @application.get(
        "/api/v1/material-states/{material_state_id}/test-runs",
        operation_id="listMaterialStateTestRuns",
        response_model=TestRunListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["testing"],
    )
    def list_test_runs(request: Request, material_state_id: UUID) -> TestRunListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            items = service.list_test_runs_for_material_state(context, decision, material_state_id)
        except Exception as error:
            raise _translate(context, error) from error
        return TestRunListResponse(
            items=tuple(TestRunResponse.from_snapshot(item) for item in items)
        )
