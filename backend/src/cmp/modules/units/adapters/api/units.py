"""Public common unit registry, conversion, and versioned Unit Profile API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.units.application.profiles import (
    CommonUnitService,
    CreateUnitProfile,
    ReviseUnitProfile,
    UnitProfileNotFound,
    UnitProfileSnapshot,
)
from cmp.modules.units.domain.profiles import (
    UnitProfileContent,
    UnitProfileSelection,
)
from cmp.modules.units.domain.system import (
    DimensionId,
    QuantityReference,
    UnitError,
    convert_value,
    decimal_text,
    unit_system_contract,
)
from cmp.shared.contracts.revisions import (
    InvalidRevisionETag,
    RevisionETag,
    RevisionMetadataResponse,
    RevisionPreconditionFailed,
    require_matching_if_match,
)
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    RevisionConflict,
    RevisionKernelError,
)

type Dependency = Callable[..., object]
type Text160 = Annotated[str, StringConstraints(min_length=1, max_length=160)]
type DecimalText = Annotated[
    str,
    StringConstraints(
        pattern=r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$",
        max_length=128,
    ),
]
type UnitIdInput = Literal[
    "Pa",
    "kPa",
    "MPa",
    "GPa",
    "m",
    "cm",
    "mm",
    "um",
    "s",
    "ms",
    "min",
    "h",
    "N",
    "kN",
    "kg",
    "g",
    "mg",
    "kg/m3",
    "g/cm3",
    "K",
    "Cel",
    "1",
    "%",
]
_ORIGINAL_UNIT_TEXTS = (
    "Pa",
    "kPa",
    "MPa",
    "GPa",
    "m",
    "cm",
    "mm",
    "um",
    "µm",
    "μm",
    "s",
    "ms",
    "min",
    "h",
    "N",
    "kN",
    "kg",
    "g",
    "mg",
    "kg/m3",
    "kg/m^3",
    "g/cm3",
    "g/cm^3",
    "K",
    "Cel",
    "degC",
    "°C",
    "1",
    "%",
)
type OriginalUnitTextInput = Literal[
    "Pa",
    "kPa",
    "MPa",
    "GPa",
    "m",
    "cm",
    "mm",
    "um",
    "µm",
    "μm",
    "s",
    "ms",
    "min",
    "h",
    "N",
    "kN",
    "kg",
    "g",
    "mg",
    "kg/m3",
    "kg/m^3",
    "g/cm3",
    "g/cm^3",
    "K",
    "Cel",
    "degC",
    "°C",
    "1",
    "%",
]
type OriginalUnitTextRequest = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64),
    Field(json_schema_extra={"enum": list(_ORIGINAL_UNIT_TEXTS)}),
]


class QuantityReferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension: DimensionId
    quantity_semantics: Text160
    unit_id: UnitIdInput

    def to_domain(self) -> QuantityReference:
        return QuantityReference(**self.model_dump())


class UnitConversionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    value: DecimalText
    original_unit_string: OriginalUnitTextRequest
    source: QuantityReferenceInput
    target: QuantityReferenceInput


class UnitConversionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: str
    original_value: str
    original_unit_string: OriginalUnitTextInput
    source: QuantityReferenceInput
    target: QuantityReferenceInput
    converted_value: str
    conversion_kind: Literal["multiplicative", "affine_absolute"]
    scale: str
    offset: str
    absolute_tolerance: str
    relative_tolerance: str


class UnitProfileSelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity_semantics: Text160
    dimension: DimensionId
    input_unit_id: UnitIdInput
    display_unit_id: UnitIdInput
    solver_export_unit_id: UnitIdInput | None

    def to_domain(self) -> UnitProfileSelection:
        return UnitProfileSelection(**self.model_dump())


class UnitProfileContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_key: Text160
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    description: Annotated[str, StringConstraints(min_length=1, max_length=1000)] | None
    non_production: bool
    selections: Annotated[
        tuple[UnitProfileSelectionInput, ...], Field(min_length=1, max_length=128)
    ]

    def to_domain(self) -> UnitProfileContent:
        return UnitProfileContent(
            profile_key=self.profile_key,
            label=self.label,
            description=self.description,
            non_production=self.non_production,
            selections=tuple(item.to_domain() for item in self.selections),
        )

    @classmethod
    def from_domain(cls, value: UnitProfileContent) -> UnitProfileContentInput:
        return cls(
            profile_key=value.profile_key,
            label=value.label,
            description=value.description,
            non_production=value.non_production,
            selections=tuple(
                UnitProfileSelectionInput(
                    quantity_semantics=item.quantity_semantics,
                    dimension=item.dimension,
                    input_unit_id=cast(UnitIdInput, item.input_unit_id),
                    display_unit_id=cast(UnitIdInput, item.display_unit_id),
                    solver_export_unit_id=cast(UnitIdInput | None, item.solver_export_unit_id),
                )
                for item in value.selections
            ),
        )


class CreateUnitProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: DataClassification
    content: UnitProfileContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ReviseUnitProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: UnitProfileContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class UnitProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_profile_id: UUID
    current_revision: RevisionMetadataResponse
    content: UnitProfileContentInput

    @classmethod
    def from_snapshot(cls, value: UnitProfileSnapshot) -> UnitProfileResponse:
        return cls(
            unit_profile_id=value.id,
            current_revision=RevisionMetadataResponse.from_record(value.current, "draft"),
            content=UnitProfileContentInput.from_domain(value.content),
        )


class UnitProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[UnitProfileResponse, ...]


class UnitDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_id: UnitIdInput
    symbol: str
    dimension: DimensionId
    conversion_kind: Literal["multiplicative", "affine_absolute"]
    scale_to_canonical: str
    offset_to_canonical: str
    backward_compatible_aliases: tuple[str, ...]


class DimensionDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension: DimensionId
    canonical_unit_id: UnitIdInput
    absolute_tolerance: str
    relative_tolerance: str
    units: tuple[UnitDefinitionResponse, ...]


class NumericPolicyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    significant_digits: Literal[34]
    minimum_adjusted_exponent: Literal[-308]
    maximum_adjusted_exponent: Literal[308]


class CompatibilityUnitsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force_per_area: Literal["Pa"]
    length: Literal["m"]
    time: Literal["s"]
    force: Literal["N"]
    mass: Literal["kg"]
    mass_per_volume: Literal["kg/m3"]
    temperature: Literal["K"]
    strain: Literal["1"]


class CompatibilityUnitSystemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit_system_id: Literal["kg_m_s"]
    production_default: Literal[False]
    units: CompatibilityUnitsResponse


class UnitSystemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_version: Literal["1.0.0"]
    numeric_policy: NumericPolicyResponse
    dimensions: tuple[DimensionDefinitionResponse, ...]
    compatibility_unit_systems: tuple[CompatibilityUnitSystemResponse, ...]


class UnitErrorDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Annotated[str, StringConstraints(pattern=r"^CMP-UNIT-[0-9]{4}$")]
    message: str
    location: str
    source_dimension: DimensionId | None
    target_dimension: DimensionId | None


class UnitErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail: UnitErrorDetailResponse


def _unit_error(error: UnitError, status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code, detail=error.detail())


def install_units_api(
    app: FastAPI,
    *,
    service: CommonUnitService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    def scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
        context = getattr(request.state, "security_context", None)
        decision = getattr(request.state, "authorization_decision", None)
        if not isinstance(context, SecurityContext) or not isinstance(
            decision, AuthorizationDecision
        ):
            raise RuntimeError("Unit dependencies did not initialize request scope")
        return context, decision

    @app.get(
        "/api/v1/unit-system",
        operation_id="getUnitSystem",
        response_model=UnitSystemResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["units"],
    )
    def get_unit_system() -> UnitSystemResponse:
        return UnitSystemResponse.model_validate(unit_system_contract())

    @app.post(
        "/api/v1/unit-conversions",
        operation_id="convertUnitValue",
        response_model=UnitConversionResponse,
        responses={422: {"model": UnitErrorResponse}},
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["units"],
    )
    def convert_unit_value(body: UnitConversionRequest) -> UnitConversionResponse:
        try:
            result = convert_value(
                body.value,
                original_unit_string=body.original_unit_string,
                source=body.source.to_domain(),
                target=body.target.to_domain(),
                location=body.location,
            )
        except UnitError as error:
            raise _unit_error(error) from error
        return UnitConversionResponse(
            location=result.location,
            original_value=decimal_text(result.original_value),
            original_unit_string=cast(OriginalUnitTextInput, result.original_unit_string),
            source=QuantityReferenceInput(
                dimension=result.source.dimension,
                quantity_semantics=result.source.quantity_semantics,
                unit_id=cast(UnitIdInput, result.source.unit_id),
            ),
            target=QuantityReferenceInput(
                dimension=result.target.dimension,
                quantity_semantics=result.target.quantity_semantics,
                unit_id=cast(UnitIdInput, result.target.unit_id),
            ),
            converted_value=decimal_text(result.converted_value),
            conversion_kind=result.conversion_kind.value,
            scale=decimal_text(result.scale),
            offset=decimal_text(result.offset),
            absolute_tolerance=decimal_text(result.absolute_tolerance),
            relative_tolerance=decimal_text(result.relative_tolerance),
        )

    def etag(response: Response, snapshot: UnitProfileSnapshot) -> None:
        response.headers["ETag"] = str(RevisionETag.from_ref(snapshot.current.ref))
        response.headers["Cache-Control"] = "no-store"

    @app.post(
        "/api/v1/unit-profiles",
        operation_id="createUnitProfile",
        response_model=UnitProfileResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["units"],
    )
    def create_unit_profile(
        body: CreateUnitProfileRequest, request: Request, response: Response
    ) -> UnitProfileResponse:
        context, decision = scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Unit Profile store unavailable")
        try:
            snapshot = service.create_profile(
                context,
                decision,
                CreateUnitProfile(
                    body.classification,
                    body.content.to_domain(),
                    body.change_reason,
                ),
            )
        except UnitError as error:
            raise _unit_error(error) from error
        except (AggregateAlreadyExists, IntegrityError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        etag(response, snapshot)
        return UnitProfileResponse.from_snapshot(snapshot)

    @app.get(
        "/api/v1/unit-profiles",
        operation_id="listUnitProfiles",
        response_model=UnitProfileListResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["units"],
    )
    def list_unit_profiles(request: Request) -> UnitProfileListResponse:
        context, decision = scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Unit Profile store unavailable")
        return UnitProfileListResponse(
            items=tuple(
                UnitProfileResponse.from_snapshot(item)
                for item in service.list_profiles(context, decision)
            )
        )

    @app.get(
        "/api/v1/unit-profiles/{profile_id}",
        operation_id="getUnitProfile",
        response_model=UnitProfileResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["units"],
    )
    def get_unit_profile(
        profile_id: UUID, request: Request, response: Response
    ) -> UnitProfileResponse:
        context, decision = scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Unit Profile store unavailable")
        try:
            snapshot = service.get_profile(context, decision, profile_id)
        except UnitProfileNotFound as error:
            raise _unit_error(error, 404) from error
        etag(response, snapshot)
        return UnitProfileResponse.from_snapshot(snapshot)

    @app.get(
        "/api/v1/unit-profiles/{profile_id}/revisions/{revision_id}",
        operation_id="getUnitProfileRevision",
        response_model=UnitProfileResponse,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["units"],
    )
    def get_unit_profile_revision(
        profile_id: UUID,
        revision_id: UUID,
        request: Request,
        response: Response,
    ) -> UnitProfileResponse:
        context, decision = scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Unit Profile store unavailable")
        try:
            snapshot = service.get_profile_revision(
                context, decision, profile_id, revision_id
            )
        except UnitProfileNotFound as error:
            raise _unit_error(error, 404) from error
        etag(response, snapshot)
        return UnitProfileResponse.from_snapshot(snapshot)

    @app.post(
        "/api/v1/unit-profiles/{profile_id}/revisions",
        operation_id="reviseUnitProfile",
        response_model=UnitProfileResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["units"],
    )
    def revise_unit_profile(
        profile_id: UUID,
        body: ReviseUnitProfileRequest,
        request: Request,
        response: Response,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> UnitProfileResponse:
        context, decision = scope(request)
        if service is None:
            raise HTTPException(status_code=503, detail="Unit Profile store unavailable")
        try:
            current = service.get_profile(context, decision, profile_id, write=True)
            expected = require_matching_if_match(if_match, current.current.ref)
            snapshot = service.revise_profile(
                context,
                decision,
                profile_id,
                ReviseUnitProfile(
                    expected,
                    body.content.to_domain(),
                    body.change_reason,
                ),
            )
        except InvalidRevisionETag as error:
            raise HTTPException(status_code=428, detail=str(error)) from error
        except RevisionPreconditionFailed as error:
            raise HTTPException(status_code=412, detail=str(error)) from error
        except UnitProfileNotFound as error:
            raise _unit_error(error, 404) from error
        except (RevisionConflict, RevisionKernelError, IntegrityError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except UnitError as error:
            raise _unit_error(error) from error
        etag(response, snapshot)
        return UnitProfileResponse.from_snapshot(snapshot)


__all__ = ["install_units_api"]
