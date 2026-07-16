"""Authenticated HTTP API for typed Material, State, and Property Set revisions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.catalog.application.service import (
    CatalogService,
    CreateMaterial,
    CreateMaterialLot,
    CreateMaterialState,
    CreateProcessDefinition,
    CreateProcessRun,
    CreatePropertySet,
    CreateStateGenealogy,
    MaterialDetail,
    MaterialLotSnapshot,
    MaterialSnapshot,
    MaterialStateSnapshot,
    ProcessDefinitionSnapshot,
    ProcessRunSnapshot,
    PropertySetSnapshot,
    ReviseMaterial,
    ReviseMaterialLot,
    ReviseMaterialState,
    ReviseProcessDefinition,
    ReviseProcessRun,
    RevisePropertySet,
    ReviseStateGenealogy,
    RevisionSnapshot,
    StateGenealogySnapshot,
)
from cmp.modules.catalog.domain.model import (
    Applicability,
    CatalogConflict,
    CatalogError,
    CatalogNotFound,
    LotKind,
    MaterialClass,
    MaterialContent,
    MaterialLotContent,
    MaterialStateContent,
    ProcessDefinitionContent,
    ProcessKind,
    PropertySetContent,
    PropertySource,
    PropertySourceKind,
    StateGenealogyContent,
)
from cmp.modules.catalog.domain.process_run import (
    BalanceBasis,
    LotFlow,
    ProcessBalance,
    ProcessRunContent,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.contracts.revisions import (
    InvalidRevisionETag,
    RevisionETag,
    RevisionMetadataResponse,
    RevisionPreconditionFailed,
    require_matching_if_match,
)
from cmp.shared.domain.revisions import (
    AggregateNotFound,
    InvalidRevisionCommand,
    RevisionConflict,
    RevisionKernelError,
    RevisionRecord,
)

type Label = Annotated[str, StringConstraints(min_length=1, max_length=255)]
type Dependency = Callable[..., object]


class MaterialContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    material_code: Annotated[str | None, StringConstraints(min_length=1, max_length=100)] = None
    material_family: Annotated[str | None, StringConstraints(min_length=1, max_length=100)] = None
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=4000)] = None
    material_class: MaterialClass | None = None

    def to_domain(
        self, default_class: MaterialClass = MaterialClass.UNCLASSIFIED
    ) -> MaterialContent:
        return MaterialContent(
            name=self.name,
            material_code=self.material_code,
            material_family=self.material_family,
            description=self.description,
            material_class=self.material_class or default_class,
        )


class MaterialCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification = DataClassification.INTERNAL
    content: MaterialContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class MaterialReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: MaterialContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class MaterialStateContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_revision_id: UUID
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    manufacturing_route: Annotated[str | None, StringConstraints(min_length=1, max_length=500)] = (
        None
    )
    heat_treatment: Annotated[str | None, StringConstraints(min_length=1, max_length=500)] = None
    lot_or_batch: Annotated[str | None, StringConstraints(min_length=1, max_length=255)] = None
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=4000)] = None

    def to_domain(self, material_id: UUID) -> MaterialStateContent:
        return MaterialStateContent(
            material_id=material_id,
            material_revision_id=self.material_revision_id,
            name=self.name,
            manufacturing_route=self.manufacturing_route,
            heat_treatment=self.heat_treatment,
            lot_or_batch=self.lot_or_batch,
            description=self.description,
        )


class MaterialStateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: MaterialStateContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class MaterialStateReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: MaterialStateContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ProcessDefinitionContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_code: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    kind: ProcessKind
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=4000)] = None

    def to_domain(self) -> ProcessDefinitionContent:
        return ProcessDefinitionContent(self.process_code, self.name, self.kind, self.description)


class ProcessDefinitionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: DataClassification = DataClassification.INTERNAL
    content: ProcessDefinitionContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ProcessDefinitionReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: ProcessDefinitionContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class MaterialLotContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_revision_id: UUID
    lot_code: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    kind: LotKind
    manufacturer: Annotated[str | None, StringConstraints(min_length=1, max_length=200)] = None
    supplier: Annotated[str | None, StringConstraints(min_length=1, max_length=200)] = None
    description: Annotated[str | None, StringConstraints(min_length=1, max_length=4000)] = None

    def to_domain(self, material_id: UUID) -> MaterialLotContent:
        return MaterialLotContent(
            material_id,
            self.material_revision_id,
            self.lot_code,
            self.kind,
            self.manufacturer,
            self.supplier,
            self.description,
        )


class MaterialLotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: MaterialLotContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class MaterialLotReviseRequest(MaterialLotCreateRequest):
    pass


class StateGenealogyContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_state_revision_id: UUID
    manufacturing_process_id: UUID | None = None
    manufacturing_process_revision_id: UUID | None = None
    heat_treatment_process_id: UUID | None = None
    heat_treatment_process_revision_id: UUID | None = None
    material_lot_id: UUID | None = None
    material_lot_revision_id: UUID | None = None
    note: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None

    def to_domain(self, material_state_id: UUID) -> StateGenealogyContent:
        return StateGenealogyContent(
            material_state_id=material_state_id,
            material_state_revision_id=self.material_state_revision_id,
            manufacturing_process_id=self.manufacturing_process_id,
            manufacturing_process_revision_id=self.manufacturing_process_revision_id,
            heat_treatment_process_id=self.heat_treatment_process_id,
            heat_treatment_process_revision_id=self.heat_treatment_process_revision_id,
            material_lot_id=self.material_lot_id,
            material_lot_revision_id=self.material_lot_revision_id,
            note=self.note,
        )


class StateGenealogyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: StateGenealogyContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class StateGenealogyReviseRequest(StateGenealogyCreateRequest):
    pass


class LotFlowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_lot_id: UUID
    material_lot_revision_id: UUID
    original_quantity: Decimal = Field(gt=0)
    original_unit: Annotated[str, StringConstraints(min_length=1, max_length=16)]

    def to_domain(self) -> LotFlow:
        return LotFlow.from_original(
            material_lot_id=self.material_lot_id,
            material_lot_revision_id=self.material_lot_revision_id,
            original_quantity=self.original_quantity,
            original_unit=self.original_unit,
        )


class ProcessRunContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_definition_id: UUID
    process_definition_revision_id: UUID
    material_state_revision_id: UUID
    run_code: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    started_at: datetime
    ended_at: datetime | None = None
    operator_name: Annotated[str | None, StringConstraints(min_length=1, max_length=200)] = None
    equipment_reference: Annotated[str | None, StringConstraints(min_length=1, max_length=255)] = (
        None
    )
    balance_basis: BalanceBasis
    balance_tolerance_fraction: Decimal | None = Field(default=None, ge=0, le=1)
    balance_not_assessed_reason: Annotated[
        str | None, StringConstraints(min_length=1, max_length=2000)
    ] = None
    inputs: tuple[LotFlowInput, ...] = Field(min_length=1)
    outputs: tuple[LotFlowInput, ...] = Field(min_length=1)
    note: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None

    def to_domain(self, material_state_id: UUID) -> ProcessRunContent:
        return ProcessRunContent(
            process_definition_id=self.process_definition_id,
            process_definition_revision_id=self.process_definition_revision_id,
            material_state_id=material_state_id,
            material_state_revision_id=self.material_state_revision_id,
            run_code=self.run_code,
            started_at=self.started_at,
            ended_at=self.ended_at,
            operator_name=self.operator_name,
            equipment_reference=self.equipment_reference,
            balance_basis=self.balance_basis,
            balance_tolerance_fraction=self.balance_tolerance_fraction,
            balance_not_assessed_reason=self.balance_not_assessed_reason,
            inputs=tuple(item.to_domain() for item in self.inputs),
            outputs=tuple(item.to_domain() for item in self.outputs),
            note=self.note,
        )


class ProcessRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: ProcessRunContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ProcessRunReviseRequest(ProcessRunCreateRequest):
    pass


class PropertySourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PropertySourceKind
    reference: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None

    def to_domain(self) -> PropertySource:
        return PropertySource(self.kind, self.reference)


class ApplicabilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_min_k: float | None = None
    temperature_max_k: float | None = None
    strain_rate_min_per_s: float | None = None
    strain_rate_max_per_s: float | None = None
    note: Annotated[str | None, StringConstraints(min_length=1, max_length=2000)] = None

    def to_domain(self) -> Applicability:
        return Applicability(
            temperature_min_k=self.temperature_min_k,
            temperature_max_k=self.temperature_max_k,
            strain_rate_min_per_s=self.strain_rate_min_per_s,
            strain_rate_max_per_s=self.strain_rate_max_per_s,
            note=self.note,
        )


class PropertySetContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_state_revision_id: UUID
    density_kg_per_m3: float
    density_source: PropertySourceInput
    youngs_modulus_pa: float
    youngs_modulus_source: PropertySourceInput
    poisson_ratio: float
    poisson_ratio_source: PropertySourceInput
    yield_stress_pa: float | None = None
    yield_stress_source: PropertySourceInput | None = None
    applicability: ApplicabilityInput = Field(default_factory=ApplicabilityInput)

    def to_domain(self, material_state_id: UUID) -> PropertySetContent:
        return PropertySetContent(
            material_state_id=material_state_id,
            material_state_revision_id=self.material_state_revision_id,
            density_kg_per_m3=self.density_kg_per_m3,
            density_source=self.density_source.to_domain(),
            youngs_modulus_pa=self.youngs_modulus_pa,
            youngs_modulus_source=self.youngs_modulus_source.to_domain(),
            poisson_ratio=self.poisson_ratio,
            poisson_ratio_source=self.poisson_ratio_source.to_domain(),
            yield_stress_pa=self.yield_stress_pa,
            yield_stress_source=(
                self.yield_stress_source.to_domain()
                if self.yield_stress_source is not None
                else None
            ),
            applicability=self.applicability.to_domain(),
        )


class PropertySetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: PropertySetContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class PropertySetReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: PropertySetContentInput
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class MaterialContentResponse(MaterialContentInput):
    material_class: MaterialClass

    @classmethod
    def from_domain(cls, content: MaterialContent) -> MaterialContentResponse:
        return cls(
            name=content.name,
            material_code=content.material_code,
            material_family=content.material_family,
            description=content.description,
            material_class=content.material_class,
        )


class MaterialStateContentResponse(MaterialStateContentInput):
    material_id: UUID

    @classmethod
    def from_domain(cls, content: MaterialStateContent) -> MaterialStateContentResponse:
        return cls(
            material_id=content.material_id,
            material_revision_id=content.material_revision_id,
            name=content.name,
            manufacturing_route=content.manufacturing_route,
            heat_treatment=content.heat_treatment,
            lot_or_batch=content.lot_or_batch,
            description=content.description,
        )


class ProcessDefinitionContentResponse(ProcessDefinitionContentInput):
    @classmethod
    def from_domain(cls, content: ProcessDefinitionContent) -> ProcessDefinitionContentResponse:
        return cls(
            process_code=content.process_code,
            name=content.name,
            kind=content.kind,
            description=content.description,
        )


class MaterialLotContentResponse(MaterialLotContentInput):
    material_id: UUID

    @classmethod
    def from_domain(cls, content: MaterialLotContent) -> MaterialLotContentResponse:
        return cls(
            material_id=content.material_id,
            material_revision_id=content.material_revision_id,
            lot_code=content.lot_code,
            kind=content.kind,
            manufacturer=content.manufacturer,
            supplier=content.supplier,
            description=content.description,
        )


class StateGenealogyContentResponse(StateGenealogyContentInput):
    material_state_id: UUID

    @classmethod
    def from_domain(cls, content: StateGenealogyContent) -> StateGenealogyContentResponse:
        return cls(
            material_state_id=content.material_state_id,
            material_state_revision_id=content.material_state_revision_id,
            manufacturing_process_id=content.manufacturing_process_id,
            manufacturing_process_revision_id=content.manufacturing_process_revision_id,
            heat_treatment_process_id=content.heat_treatment_process_id,
            heat_treatment_process_revision_id=content.heat_treatment_process_revision_id,
            material_lot_id=content.material_lot_id,
            material_lot_revision_id=content.material_lot_revision_id,
            note=content.note,
        )


class LotFlowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_lot_id: UUID
    material_lot_revision_id: UUID
    original_quantity: Decimal
    original_unit: str
    quantity_basis: BalanceBasis
    normalized_quantity: Decimal
    normalized_unit: str
    normalization_factor: Decimal

    @classmethod
    def from_domain(cls, value: LotFlow) -> LotFlowResponse:
        return cls(
            material_lot_id=value.material_lot_id,
            material_lot_revision_id=value.material_lot_revision_id,
            original_quantity=value.original_quantity,
            original_unit=value.original_unit,
            quantity_basis=value.quantity_basis,
            normalized_quantity=value.normalized_quantity,
            normalized_unit=value.normalized_unit,
            normalization_factor=value.normalization_factor,
        )


class ProcessBalanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_total: Decimal
    output_total: Decimal
    relative_difference: Decimal
    within_tolerance: bool

    @classmethod
    def from_domain(cls, value: ProcessBalance) -> ProcessBalanceResponse:
        return cls(
            input_total=value.input_total,
            output_total=value.output_total,
            relative_difference=value.relative_difference,
            within_tolerance=value.within_tolerance,
        )


class ProcessRunContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_definition_id: UUID
    process_definition_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    run_code: str
    started_at: datetime
    ended_at: datetime | None
    operator_name: str | None
    equipment_reference: str | None
    balance_basis: BalanceBasis
    balance_tolerance_fraction: Decimal | None
    balance_not_assessed_reason: str | None
    balance: ProcessBalanceResponse | None
    inputs: tuple[LotFlowResponse, ...]
    outputs: tuple[LotFlowResponse, ...]
    note: str | None

    @classmethod
    def from_domain(cls, value: ProcessRunContent) -> ProcessRunContentResponse:
        balance = value.balance
        return cls(
            process_definition_id=value.process_definition_id,
            process_definition_revision_id=value.process_definition_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            run_code=value.run_code,
            started_at=value.started_at,
            ended_at=value.ended_at,
            operator_name=value.operator_name,
            equipment_reference=value.equipment_reference,
            balance_basis=value.balance_basis,
            balance_tolerance_fraction=value.balance_tolerance_fraction,
            balance_not_assessed_reason=value.balance_not_assessed_reason,
            balance=(ProcessBalanceResponse.from_domain(balance) if balance is not None else None),
            inputs=tuple(LotFlowResponse.from_domain(item) for item in value.inputs),
            outputs=tuple(LotFlowResponse.from_domain(item) for item in value.outputs),
            note=value.note,
        )


class PropertySourceResponse(PropertySourceInput):
    @classmethod
    def from_domain(cls, source: PropertySource) -> PropertySourceResponse:
        return cls(kind=source.kind, reference=source.reference)


class ApplicabilityResponse(ApplicabilityInput):
    @classmethod
    def from_domain(cls, value: Applicability) -> ApplicabilityResponse:
        return cls(
            temperature_min_k=value.temperature_min_k,
            temperature_max_k=value.temperature_max_k,
            strain_rate_min_per_s=value.strain_rate_min_per_s,
            strain_rate_max_per_s=value.strain_rate_max_per_s,
            note=value.note,
        )


class PropertySetContentResponse(PropertySetContentInput):
    material_state_id: UUID
    density_source: PropertySourceResponse
    youngs_modulus_source: PropertySourceResponse
    poisson_ratio_source: PropertySourceResponse
    yield_stress_source: PropertySourceResponse | None = None
    applicability: ApplicabilityResponse

    @classmethod
    def from_domain(cls, content: PropertySetContent) -> PropertySetContentResponse:
        return cls(
            material_state_id=content.material_state_id,
            material_state_revision_id=content.material_state_revision_id,
            density_kg_per_m3=content.density_kg_per_m3,
            density_source=PropertySourceResponse.from_domain(content.density_source),
            youngs_modulus_pa=content.youngs_modulus_pa,
            youngs_modulus_source=PropertySourceResponse.from_domain(content.youngs_modulus_source),
            poisson_ratio=content.poisson_ratio,
            poisson_ratio_source=PropertySourceResponse.from_domain(content.poisson_ratio_source),
            yield_stress_pa=content.yield_stress_pa,
            yield_stress_source=(
                PropertySourceResponse.from_domain(content.yield_stress_source)
                if content.yield_stress_source is not None
                else None
            ),
            applicability=ApplicabilityResponse.from_domain(content.applicability),
        )


class ProvenanceSummary(BaseModel):
    """Immutable revision facts shown until the lineage lookup is opened."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str
    reference_type: str
    revision_id: UUID
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    based_on_revision_id: UUID | None
    recorded_at: datetime
    recorded_by: UUID

    @classmethod
    def from_record(cls, aggregate_type: str, record: RevisionRecord) -> ProvenanceSummary:
        reference_type = f"{aggregate_type}.revision"
        return cls(
            entity_type=reference_type,
            reference_type=reference_type,
            revision_id=record.revision_id,
            content_sha256=record.content_hash,
            based_on_revision_id=record.based_on_revision_id,
            recorded_at=record.created_at,
            recorded_by=record.created_by,
        )


class MaterialRevisionResponse(RevisionMetadataResponse):
    content: MaterialContentResponse
    provenance: ProvenanceSummary

    @classmethod
    def from_snapshot(cls, value: RevisionSnapshot[MaterialContent]) -> MaterialRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=MaterialContentResponse.from_domain(value.content),
            provenance=ProvenanceSummary.from_record("catalog.material", value.record),
        )


class MaterialStateRevisionResponse(RevisionMetadataResponse):
    content: MaterialStateContentResponse
    provenance: ProvenanceSummary

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[MaterialStateContent]
    ) -> MaterialStateRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=MaterialStateContentResponse.from_domain(value.content),
            provenance=ProvenanceSummary.from_record("catalog.material_state", value.record),
        )


class PropertySetRevisionResponse(RevisionMetadataResponse):
    content: PropertySetContentResponse
    provenance: ProvenanceSummary

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[PropertySetContent]
    ) -> PropertySetRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=PropertySetContentResponse.from_domain(value.content),
            provenance=ProvenanceSummary.from_record("catalog.property_set", value.record),
        )


class ProcessDefinitionRevisionResponse(RevisionMetadataResponse):
    content: ProcessDefinitionContentResponse
    provenance: ProvenanceSummary

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ProcessDefinitionContent]
    ) -> ProcessDefinitionRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=ProcessDefinitionContentResponse.from_domain(value.content),
            provenance=ProvenanceSummary.from_record("catalog.process_definition", value.record),
        )


class MaterialLotRevisionResponse(RevisionMetadataResponse):
    content: MaterialLotContentResponse
    provenance: ProvenanceSummary

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[MaterialLotContent]
    ) -> MaterialLotRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=MaterialLotContentResponse.from_domain(value.content),
            provenance=ProvenanceSummary.from_record("catalog.material_lot", value.record),
        )


class StateGenealogyRevisionResponse(RevisionMetadataResponse):
    content: StateGenealogyContentResponse
    provenance: ProvenanceSummary

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[StateGenealogyContent]
    ) -> StateGenealogyRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=StateGenealogyContentResponse.from_domain(value.content),
            provenance=ProvenanceSummary.from_record("catalog.state_genealogy", value.record),
        )


class ProcessRunRevisionResponse(RevisionMetadataResponse):
    content: ProcessRunContentResponse
    provenance: ProvenanceSummary

    @classmethod
    def from_snapshot(
        cls, value: RevisionSnapshot[ProcessRunContent]
    ) -> ProcessRunRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(value.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=ProcessRunContentResponse.from_domain(value.content),
            provenance=ProvenanceSummary.from_record("catalog.process_run", value.record),
        )


class MaterialLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self: str
    revisions: str
    states: str


class MaterialResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    current_revision: MaterialRevisionResponse
    links: MaterialLinks

    @classmethod
    def from_snapshot(cls, value: MaterialSnapshot) -> MaterialResponse:
        root = f"/api/v1/materials/{value.id}"
        return cls(
            material_id=value.id,
            current_revision=MaterialRevisionResponse.from_snapshot(value.current),
            links=MaterialLinks(self=root, revisions=f"{root}/revisions", states=f"{root}/states"),
        )


class MaterialStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_state_id: UUID
    material_id: UUID
    current_revision: MaterialStateRevisionResponse
    property_sets_url: str

    @classmethod
    def from_snapshot(cls, value: MaterialStateSnapshot) -> MaterialStateResponse:
        return cls(
            material_state_id=value.id,
            material_id=value.material_id,
            current_revision=MaterialStateRevisionResponse.from_snapshot(value.current),
            property_sets_url=f"/api/v1/material-states/{value.id}/property-sets",
        )


class PropertySetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_set_id: UUID
    material_state_id: UUID
    current_revision: PropertySetRevisionResponse

    @classmethod
    def from_snapshot(cls, value: PropertySetSnapshot) -> PropertySetResponse:
        return cls(
            property_set_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=PropertySetRevisionResponse.from_snapshot(value.current),
        )


class ProcessDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_definition_id: UUID
    current_revision: ProcessDefinitionRevisionResponse

    @classmethod
    def from_snapshot(cls, value: ProcessDefinitionSnapshot) -> ProcessDefinitionResponse:
        return cls(
            process_definition_id=value.id,
            current_revision=ProcessDefinitionRevisionResponse.from_snapshot(value.current),
        )


class MaterialLotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_lot_id: UUID
    material_id: UUID
    current_revision: MaterialLotRevisionResponse

    @classmethod
    def from_snapshot(cls, value: MaterialLotSnapshot) -> MaterialLotResponse:
        return cls(
            material_lot_id=value.id,
            material_id=value.material_id,
            current_revision=MaterialLotRevisionResponse.from_snapshot(value.current),
        )


class StateGenealogyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_genealogy_id: UUID
    material_state_id: UUID
    current_revision: StateGenealogyRevisionResponse

    @classmethod
    def from_snapshot(cls, value: StateGenealogySnapshot) -> StateGenealogyResponse:
        return cls(
            state_genealogy_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=StateGenealogyRevisionResponse.from_snapshot(value.current),
        )


class ProcessRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_run_id: UUID
    material_state_id: UUID
    current_revision: ProcessRunRevisionResponse

    @classmethod
    def from_snapshot(cls, value: ProcessRunSnapshot) -> ProcessRunResponse:
        return cls(
            process_run_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=ProcessRunRevisionResponse.from_snapshot(value.current),
        )


class ProcessDefinitionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[ProcessDefinitionResponse, ...]


class MaterialLotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[MaterialLotResponse, ...]


class ProcessRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: tuple[ProcessRunResponse, ...]


class MaterialListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[MaterialResponse, ...]


class MaterialDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material: MaterialResponse
    states: tuple[MaterialStateResponse, ...]
    property_sets: tuple[PropertySetResponse, ...]

    @classmethod
    def from_detail(cls, value: MaterialDetail) -> MaterialDetailResponse:
        return cls(
            material=MaterialResponse.from_snapshot(value.material),
            states=tuple(MaterialStateResponse.from_snapshot(item) for item in value.states),
            property_sets=tuple(
                PropertySetResponse.from_snapshot(item) for item in value.property_sets
            ),
        )


class MaterialRevisionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    revisions: tuple[MaterialRevisionResponse, ...]


class MaterialRevisionComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    left: MaterialRevisionResponse
    right: MaterialRevisionResponse
    changed_fields: tuple[Label, ...]


class CatalogProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Label
    title: Label
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-CATALOG-[0-9]{4}$")]
    trace_id: Label


class CatalogHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status_code: int,
        title: str,
        detail: str,
        code: str,
        current_etag: RevisionETag | None = None,
    ) -> None:
        self.context = context
        self.problem = CatalogProblem(
            type="urn:cmp:problem:catalog",
            title=title,
            status=status_code,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        self.current_etag = current_etag
        super().__init__(title)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("catalog route dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> CatalogHttpError:
    return CatalogHttpError(
        context=context,
        status_code=503,
        title="Catalog service unavailable",
        detail="The authoritative Material Catalog store is not configured for this deployment.",
        code="CMP-CATALOG-0006",
    )


def _translate(context: SecurityContext, error: Exception) -> CatalogHttpError:
    if isinstance(error, (CatalogNotFound, AggregateNotFound)):
        return CatalogHttpError(
            context=context,
            status_code=404,
            title="Catalog resource not found",
            detail="No Material Catalog resource is visible in the selected tenant context.",
            code="CMP-CATALOG-0001",
        )
    if isinstance(error, (RevisionPreconditionFailed, RevisionConflict)):
        current = error.current
        return CatalogHttpError(
            context=context,
            status_code=412,
            title="Revision precondition failed",
            detail=(
                "The immutable revision head changed; reload the current revision before retrying."
            ),
            code="CMP-CATALOG-0003",
            current_etag=RevisionETag.from_ref(current),
        )
    if isinstance(error, (InvalidRevisionETag, InvalidRevisionCommand, ValueError)):
        return CatalogHttpError(
            context=context,
            status_code=422,
            title="Invalid Catalog request",
            detail="The request does not satisfy the typed Material Catalog contract.",
            code="CMP-CATALOG-0002",
        )
    if isinstance(error, (CatalogConflict, RevisionKernelError, IntegrityError)):
        return CatalogHttpError(
            context=context,
            status_code=409,
            title="Catalog state conflict",
            detail="The request conflicts with immutable Catalog state or a typed parent relation.",
            code="CMP-CATALOG-0004",
        )
    return CatalogHttpError(
        context=context,
        status_code=409,
        title="Catalog command rejected",
        detail="The Material Catalog command could not be completed.",
        code="CMP-CATALOG-0004",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_catalog_api(
    application: FastAPI,
    *,
    service: CatalogService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    previous_validation_handler = cast(
        Callable[[Request, RequestValidationError], Awaitable[Response]],
        application.exception_handlers.get(
            RequestValidationError,
            request_validation_exception_handler,
        ),
    )

    @application.exception_handler(CatalogHttpError)
    async def catalog_error_handler(request: Request, error: CatalogHttpError) -> JSONResponse:
        del request
        headers = {"Cache-Control": "no-store", "X-Request-ID": str(error.context.request_id)}
        if error.current_etag is not None:
            headers["ETag"] = str(error.current_etag)
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers=headers,
        )

    @application.exception_handler(RequestValidationError)
    async def catalog_validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> Response:
        prefixes = (
            "/api/v1/materials",
            "/api/v1/material-states",
            "/api/v1/property-sets",
            "/api/v1/process-definitions",
            "/api/v1/material-lots",
            "/api/v1/state-genealogies",
            "/api/v1/process-runs",
        )
        if not request.url.path.startswith(prefixes):
            return await previous_validation_handler(request, error)
        context = getattr(request.state, "security_context", None)
        if not isinstance(context, SecurityContext):
            return await request_validation_exception_handler(request, error)
        translated = _translate(context, ValueError("validation failed"))
        return JSONResponse(
            status_code=translated.problem.status,
            content=translated.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store", "X-Request-ID": str(context.request_id)},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Authorization denied."},
        404: {"model": CatalogProblem},
        409: {"model": CatalogProblem},
        412: {"model": CatalogProblem, "headers": {"ETag": {"schema": {"type": "string"}}}},
        422: {"model": CatalogProblem},
        503: {"model": CatalogProblem},
    }

    @application.post(
        "/api/v1/process-definitions",
        operation_id="createProcessDefinition",
        response_model=ProcessDefinitionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Create a governed stable Process identity and first immutable revision.",
    )
    def create_process_definition(
        request: Request, response: Response, body: ProcessDefinitionCreateRequest
    ) -> ProcessDefinitionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_process_definition(
                context,
                decision,
                CreateProcessDefinition(
                    body.classification, body.content.to_domain(), body.change_reason
                ),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ProcessDefinitionResponse.from_snapshot(value)

    @application.get(
        "/api/v1/process-definitions",
        operation_id="listProcessDefinitions",
        response_model=ProcessDefinitionListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="List current governed Process revisions by typed role.",
    )
    def list_process_definitions(
        request: Request,
        kind: ProcessKind | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> ProcessDefinitionListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_process_definitions(context, decision, kind=kind, limit=limit)
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return ProcessDefinitionListResponse(
            items=tuple(ProcessDefinitionResponse.from_snapshot(item) for item in values)
        )

    @application.post(
        "/api/v1/process-definitions/{process_definition_id}/revisions",
        operation_id="reviseProcessDefinition",
        response_model=ProcessDefinitionResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Append an immutable Process revision using a strong ETag precondition.",
    )
    def revise_process_definition(
        request: Request,
        response: Response,
        process_definition_id: UUID,
        body: ProcessDefinitionReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ProcessDefinitionResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            current = service.get_process_definition_for_write(
                context, decision, process_definition_id
            )
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = service.revise_process_definition(
                context,
                decision,
                process_definition_id,
                ReviseProcessDefinition(expected, body.content.to_domain(), body.change_reason),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ProcessDefinitionResponse.from_snapshot(value)

    @application.post(
        "/api/v1/materials/{material_id}/lots",
        operation_id="createMaterialLot",
        response_model=MaterialLotResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Create a Lot/Batch identity pinned to a concrete Material revision.",
    )
    def create_material_lot(
        request: Request,
        response: Response,
        material_id: UUID,
        body: MaterialLotCreateRequest,
    ) -> MaterialLotResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_material_lot(
                context,
                decision,
                CreateMaterialLot(body.content.to_domain(material_id), body.change_reason),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return MaterialLotResponse.from_snapshot(value)

    @application.get(
        "/api/v1/materials/{material_id}/lots",
        operation_id="listMaterialLots",
        response_model=MaterialLotListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="List current Lot/Batch revisions for one Material.",
    )
    def list_material_lots(
        request: Request,
        material_id: UUID,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> MaterialLotListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_material_lots(context, decision, material_id, limit=limit)
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return MaterialLotListResponse(
            items=tuple(MaterialLotResponse.from_snapshot(item) for item in values)
        )

    @application.post(
        "/api/v1/material-lots/{material_lot_id}/revisions",
        operation_id="reviseMaterialLot",
        response_model=MaterialLotResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Append an immutable Lot/Batch revision using a strong ETag precondition.",
    )
    def revise_material_lot(
        request: Request,
        response: Response,
        material_lot_id: UUID,
        body: MaterialLotReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> MaterialLotResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            current = service.get_material_lot_for_write(context, decision, material_lot_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = service.revise_material_lot(
                context,
                decision,
                material_lot_id,
                ReviseMaterialLot(
                    expected,
                    body.content.to_domain(current.material_id),
                    body.change_reason,
                ),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return MaterialLotResponse.from_snapshot(value)

    @application.get(
        "/api/v1/material-states/{material_state_id}/genealogy",
        operation_id="getStateGenealogy",
        response_model=StateGenealogyResponse | None,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="Read the current exact revision links for a Material State genealogy.",
    )
    def get_state_genealogy(
        request: Request, response: Response, material_state_id: UUID
    ) -> StateGenealogyResponse | None:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_state_genealogy_for_state(context, decision, material_state_id)
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        if value is None:
            response.headers["Cache-Control"] = "no-store"
            return None
        _etag(response, value.current.record)
        return StateGenealogyResponse.from_snapshot(value)

    @application.post(
        "/api/v1/material-states/{material_state_id}/genealogy",
        operation_id="createStateGenealogy",
        response_model=StateGenealogyResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Create exact Process and Lot revision links for one Material State revision.",
    )
    def create_state_genealogy(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: StateGenealogyCreateRequest,
    ) -> StateGenealogyResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_state_genealogy(
                context,
                decision,
                CreateStateGenealogy(body.content.to_domain(material_state_id), body.change_reason),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return StateGenealogyResponse.from_snapshot(value)

    @application.post(
        "/api/v1/state-genealogies/{state_genealogy_id}/revisions",
        operation_id="reviseStateGenealogy",
        response_model=StateGenealogyResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Append exact genealogy links using a strong ETag precondition.",
    )
    def revise_state_genealogy(
        request: Request,
        response: Response,
        state_genealogy_id: UUID,
        body: StateGenealogyReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> StateGenealogyResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            current = service.get_state_genealogy_for_write(context, decision, state_genealogy_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = service.revise_state_genealogy(
                context,
                decision,
                state_genealogy_id,
                ReviseStateGenealogy(
                    expected,
                    body.content.to_domain(current.material_state_id),
                    body.change_reason,
                ),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return StateGenealogyResponse.from_snapshot(value)

    @application.post(
        "/api/v1/material-states/{material_state_id}/process-runs",
        operation_id="createProcessRun",
        response_model=ProcessRunResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Create a Process Run with exact ordered input and output Lot revisions.",
    )
    def create_process_run(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: ProcessRunCreateRequest,
    ) -> ProcessRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_process_run(
                context,
                decision,
                CreateProcessRun(body.content.to_domain(material_state_id), body.change_reason),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ProcessRunResponse.from_snapshot(value)

    @application.get(
        "/api/v1/material-states/{material_state_id}/process-runs",
        operation_id="listProcessRuns",
        response_model=ProcessRunListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="List current Process Runs and exact Lot flows for a Material State.",
    )
    def list_process_runs(
        request: Request,
        material_state_id: UUID,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> ProcessRunListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_process_runs_for_state(
                context, decision, material_state_id, limit=limit
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return ProcessRunListResponse(
            items=tuple(ProcessRunResponse.from_snapshot(item) for item in values)
        )

    @application.get(
        "/api/v1/process-runs/{process_run_id}",
        operation_id="getProcessRun",
        response_model=ProcessRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="Read a current Process Run revision and its immutable Lot flows.",
    )
    def get_process_run(
        request: Request, response: Response, process_run_id: UUID
    ) -> ProcessRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_process_run(context, decision, process_run_id)
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ProcessRunResponse.from_snapshot(value)

    @application.post(
        "/api/v1/process-runs/{process_run_id}/revisions",
        operation_id="reviseProcessRun",
        response_model=ProcessRunResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Append a Process Run correction using a strong ETag precondition.",
    )
    def revise_process_run(
        request: Request,
        response: Response,
        process_run_id: UUID,
        body: ProcessRunReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ProcessRunResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            current = service.get_process_run_for_write(context, decision, process_run_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = service.revise_process_run(
                context,
                decision,
                process_run_id,
                ReviseProcessRun(
                    expected,
                    body.content.to_domain(current.material_state_id),
                    body.change_reason,
                ),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return ProcessRunResponse.from_snapshot(value)

    @application.post(
        "/api/v1/materials",
        operation_id="createMaterial",
        response_model=MaterialResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Create a stable Material identity and its first immutable revision.",
    )
    def create_material(
        request: Request, response: Response, body: MaterialCreateRequest
    ) -> MaterialResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            result = service.create_material(
                context,
                decision,
                CreateMaterial(body.classification, body.content.to_domain(), body.change_reason),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, result.current.record)
        return MaterialResponse.from_snapshot(result)

    @application.get(
        "/api/v1/materials",
        operation_id="listMaterials",
        response_model=MaterialListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="Search current Material revisions in the selected organization/project.",
    )
    def list_materials(
        request: Request,
        q: Annotated[str | None, Query(max_length=200)] = None,
        material_class: MaterialClass | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> MaterialListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_materials(
                context,
                decision,
                query=q,
                material_class=material_class,
                limit=limit,
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return MaterialListResponse(
            items=tuple(MaterialResponse.from_snapshot(value) for value in values)
        )

    @application.get(
        "/api/v1/materials/{material_id}",
        operation_id="getMaterial",
        response_model=MaterialDetailResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary=(
            "Read a Material with current States, typed Property Sets, and revision provenance."
        ),
    )
    def get_material(
        request: Request, response: Response, material_id: UUID
    ) -> MaterialDetailResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_material_detail(context, decision, material_id)
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.material.current.record)
        return MaterialDetailResponse.from_detail(value)

    @application.get(
        "/api/v1/materials/{material_id}/revisions",
        operation_id="listMaterialRevisions",
        response_model=MaterialRevisionListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="List immutable revisions for one Material identity.",
    )
    def list_material_revisions(
        request: Request, material_id: UUID
    ) -> MaterialRevisionListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            revisions = service.list_material_revisions(context, decision, material_id)
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return MaterialRevisionListResponse(
            material_id=material_id,
            revisions=tuple(MaterialRevisionResponse.from_snapshot(item) for item in revisions),
        )

    @application.get(
        "/api/v1/materials/{material_id}/revisions:compare",
        operation_id="compareMaterialRevisions",
        response_model=MaterialRevisionComparisonResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="Compare two concrete immutable Material revisions.",
    )
    def compare_material_revisions(
        request: Request,
        material_id: UUID,
        left_revision_id: UUID,
        right_revision_id: UUID,
    ) -> MaterialRevisionComparisonResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            left, right, changed = service.compare_material_revisions(
                context,
                decision,
                material_id,
                left_revision_id,
                right_revision_id,
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        return MaterialRevisionComparisonResponse(
            material_id=material_id,
            left=MaterialRevisionResponse.from_snapshot(left),
            right=MaterialRevisionResponse.from_snapshot(right),
            changed_fields=changed,
        )

    @application.post(
        "/api/v1/materials/{material_id}/revisions",
        operation_id="reviseMaterial",
        response_model=MaterialResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Append an immutable Material revision using a strong ETag precondition.",
    )
    def revise_material(
        request: Request,
        response: Response,
        material_id: UUID,
        body: MaterialReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> MaterialResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            current = service.get_material_for_write(context, decision, material_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = service.revise_material(
                context,
                decision,
                material_id,
                ReviseMaterial(
                    expected,
                    body.content.to_domain(current.current.content.material_class),
                    body.change_reason,
                ),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return MaterialResponse.from_snapshot(value)

    @application.post(
        "/api/v1/materials/{material_id}/states",
        operation_id="createMaterialState",
        response_model=MaterialStateResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Create a Material State bound to one concrete Material revision.",
    )
    def create_material_state(
        request: Request,
        response: Response,
        material_id: UUID,
        body: MaterialStateCreateRequest,
    ) -> MaterialStateResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_material_state(
                context,
                decision,
                CreateMaterialState(body.content.to_domain(material_id), body.change_reason),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return MaterialStateResponse.from_snapshot(value)

    @application.get(
        "/api/v1/material-states/{material_state_id}",
        operation_id="getMaterialState",
        response_model=MaterialStateResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="Read one current Material State revision.",
    )
    def get_material_state(
        request: Request, response: Response, material_state_id: UUID
    ) -> MaterialStateResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_material_state(context, decision, material_state_id)
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return MaterialStateResponse.from_snapshot(value)

    @application.post(
        "/api/v1/material-states/{material_state_id}/revisions",
        operation_id="reviseMaterialState",
        response_model=MaterialStateResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Append a Material State revision using a strong ETag precondition.",
    )
    def revise_material_state(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: MaterialStateReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> MaterialStateResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            current = service.get_material_state_for_write(context, decision, material_state_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = service.revise_material_state(
                context,
                decision,
                material_state_id,
                ReviseMaterialState(
                    expected,
                    body.content.to_domain(current.material_id),
                    body.change_reason,
                ),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return MaterialStateResponse.from_snapshot(value)

    @application.post(
        "/api/v1/material-states/{material_state_id}/property-sets",
        operation_id="createPropertySet",
        response_model=PropertySetResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Record typed SI mechanical properties for one concrete Material State revision.",
    )
    def create_property_set(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: PropertySetCreateRequest,
    ) -> PropertySetResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.create_property_set(
                context,
                decision,
                CreatePropertySet(body.content.to_domain(material_state_id), body.change_reason),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return PropertySetResponse.from_snapshot(value)

    @application.get(
        "/api/v1/property-sets/{property_set_id}",
        operation_id="getPropertySet",
        response_model=PropertySetResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["catalog"],
        summary="Read a current explicitly typed property set revision.",
    )
    def get_property_set(
        request: Request, response: Response, property_set_id: UUID
    ) -> PropertySetResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_property_set(context, decision, property_set_id)
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return PropertySetResponse.from_snapshot(value)

    @application.post(
        "/api/v1/property-sets/{property_set_id}/revisions",
        operation_id="revisePropertySet",
        response_model=PropertySetResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["catalog"],
        summary="Append a typed property revision using a strong ETag precondition.",
    )
    def revise_property_set(
        request: Request,
        response: Response,
        property_set_id: UUID,
        body: PropertySetReviseRequest,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> PropertySetResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            current = service.get_property_set_for_write(context, decision, property_set_id)
            expected = require_matching_if_match(if_match, current.current.record.ref)
            value = service.revise_property_set(
                context,
                decision,
                property_set_id,
                RevisePropertySet(
                    expected,
                    body.content.to_domain(current.material_state_id),
                    body.change_reason,
                ),
            )
        except (CatalogError, RevisionKernelError, IntegrityError, ValueError) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return PropertySetResponse.from_snapshot(value)
