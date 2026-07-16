"""Material Catalog commands coordinated through the shared revision kernel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.catalog.domain.model import (
    CatalogConflict,
    MaterialClass,
    MaterialContent,
    MaterialLotContent,
    MaterialStateContent,
    ProcessDefinitionContent,
    ProcessKind,
    PropertySetContent,
    StateGenealogyContent,
)
from cmp.modules.catalog.domain.process_run import ProcessRunContent
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

MATERIAL_AGGREGATE_TYPE = "catalog.material"
MATERIAL_STATE_AGGREGATE_TYPE = "catalog.material_state"
PROPERTY_SET_AGGREGATE_TYPE = "catalog.property_set"
PROCESS_DEFINITION_AGGREGATE_TYPE = "catalog.process_definition"
MATERIAL_LOT_AGGREGATE_TYPE = "catalog.material_lot"
STATE_GENEALOGY_AGGREGATE_TYPE = "catalog.state_genealogy"
PROCESS_RUN_AGGREGATE_TYPE = "catalog.process_run"

MATERIAL_SCHEMA_ID = "urn:cmp:catalog:material:2.0.0"
MATERIAL_STATE_SCHEMA_ID = "urn:cmp:catalog:material-state:1.0.0"
PROPERTY_SET_SCHEMA_ID = "urn:cmp:catalog:property-set:1.0.0"
PROCESS_DEFINITION_SCHEMA_ID = "urn:cmp:catalog:process-definition:1.0.0"
MATERIAL_LOT_SCHEMA_ID = "urn:cmp:catalog:material-lot:1.0.0"
STATE_GENEALOGY_SCHEMA_ID = "urn:cmp:catalog:state-genealogy:1.0.0"
PROCESS_RUN_SCHEMA_ID = "urn:cmp:catalog:process-run:1.0.0"
SCHEMA_VERSION = "1.0.0"
MATERIAL_SCHEMA_VERSION = "2.0.0"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class MaterialSnapshot:
    id: UUID
    current: RevisionSnapshot[MaterialContent]


@dataclass(frozen=True, slots=True)
class MaterialStateSnapshot:
    id: UUID
    material_id: UUID
    current: RevisionSnapshot[MaterialStateContent]


@dataclass(frozen=True, slots=True)
class PropertySetSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[PropertySetContent]


@dataclass(frozen=True, slots=True)
class ProcessDefinitionSnapshot:
    id: UUID
    current: RevisionSnapshot[ProcessDefinitionContent]


@dataclass(frozen=True, slots=True)
class MaterialLotSnapshot:
    id: UUID
    material_id: UUID
    current: RevisionSnapshot[MaterialLotContent]


@dataclass(frozen=True, slots=True)
class StateGenealogySnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[StateGenealogyContent]


@dataclass(frozen=True, slots=True)
class ProcessRunSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[ProcessRunContent]


@dataclass(frozen=True, slots=True)
class MaterialDetail:
    material: MaterialSnapshot
    states: tuple[MaterialStateSnapshot, ...]
    property_sets: tuple[PropertySetSnapshot, ...]


@dataclass(frozen=True, slots=True)
class CreateMaterial:
    classification: DataClassification
    content: MaterialContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseMaterial:
    expected_current_revision_id: UUID
    content: MaterialContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateMaterialState:
    content: MaterialStateContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseMaterialState:
    expected_current_revision_id: UUID
    content: MaterialStateContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreatePropertySet:
    content: PropertySetContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class RevisePropertySet:
    expected_current_revision_id: UUID
    content: PropertySetContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateProcessDefinition:
    classification: DataClassification
    content: ProcessDefinitionContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseProcessDefinition:
    expected_current_revision_id: UUID
    content: ProcessDefinitionContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateMaterialLot:
    content: MaterialLotContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseMaterialLot:
    expected_current_revision_id: UUID
    content: MaterialLotContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateStateGenealogy:
    content: StateGenealogyContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseStateGenealogy:
    expected_current_revision_id: UUID
    content: StateGenealogyContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateProcessRun:
    content: ProcessRunContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseProcessRun:
    expected_current_revision_id: UUID
    content: ProcessRunContent
    change_reason: str


class CatalogRepository(Protocol):
    """Catalog-owned persistence port; all methods enforce tenant RLS in their adapter."""

    def material_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[MaterialContent]: ...

    def material_state_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[MaterialStateContent]: ...

    def property_set_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[PropertySetContent]: ...

    def process_definition_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ProcessDefinitionContent]: ...

    def material_lot_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[MaterialLotContent]: ...

    def state_genealogy_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[StateGenealogyContent]: ...

    def process_run_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ProcessRunContent]: ...

    def list_materials(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: str | None,
        material_class: MaterialClass | None,
        limit: int,
    ) -> tuple[MaterialSnapshot, ...]: ...

    def get_material(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> MaterialSnapshot: ...

    def get_material_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[MaterialContent]: ...

    def list_material_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> tuple[RevisionSnapshot[MaterialContent], ...]: ...

    def get_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> MaterialStateSnapshot: ...

    def get_material_state_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[MaterialStateContent]: ...

    def get_property_set(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        property_set_id: UUID,
    ) -> PropertySetSnapshot: ...

    def get_property_set_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        property_set_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[PropertySetContent]: ...

    def get_material_detail(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> MaterialDetail: ...

    def list_process_definitions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        kind: ProcessKind | None,
        limit: int,
    ) -> tuple[ProcessDefinitionSnapshot, ...]: ...

    def get_process_definition(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_definition_id: UUID,
    ) -> ProcessDefinitionSnapshot: ...

    def get_process_definition_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_definition_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[ProcessDefinitionContent]: ...

    def list_material_lots(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        limit: int,
    ) -> tuple[MaterialLotSnapshot, ...]: ...

    def get_material_lot(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_lot_id: UUID,
    ) -> MaterialLotSnapshot: ...

    def get_material_lot_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_lot_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[MaterialLotContent]: ...

    def get_state_genealogy_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> StateGenealogySnapshot | None: ...

    def get_state_genealogy(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        state_genealogy_id: UUID,
    ) -> StateGenealogySnapshot: ...

    def list_process_runs_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        limit: int,
    ) -> tuple[ProcessRunSnapshot, ...]: ...

    def get_process_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_run_id: UUID,
    ) -> ProcessRunSnapshot: ...

    def get_process_run_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_run_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[ProcessRunContent]: ...


def _require_decision(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise CatalogConflict("authorization decision does not match catalog request context")


def _require_capability(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise CatalogConflict("authorization decision lacks the required catalog capability")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class CatalogService:
    """Create, query, and append typed Material Catalog revisions.

    Classification is fixed at Material creation and inherited by its State and Property Set
    descendants.  This keeps the first vertical slice from creating cross-classification
    hierarchy edges while preserving a clear future place for governed reclassification.
    """

    def __init__(
        self,
        *,
        repository: CatalogRepository,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("catalog id_factory returned a zero UUID")
        return value

    @staticmethod
    def _scope(context: SecurityContext, classification: str) -> TenantScope:
        return TenantScope(context.organization_id, context.project_id, classification)

    @staticmethod
    def _revision_service[ContentT](
        aggregate_type: str,
        store: RevisionStore[ContentT],
    ) -> RevisionService[ContentT]:
        return RevisionService(aggregate_type=aggregate_type, store=store)

    @staticmethod
    def _validate_material_parent(
        content: MaterialStateContent,
        parent: RevisionSnapshot[MaterialContent],
        material_id: UUID,
    ) -> None:
        if content.material_id != material_id or parent.record.aggregate_id != material_id:
            raise CatalogConflict("Material State must reference the selected Material identity")

    @staticmethod
    def _validate_state_parent(
        content: PropertySetContent,
        parent: RevisionSnapshot[MaterialStateContent],
        material_state_id: UUID,
    ) -> None:
        if (
            content.material_state_id != material_state_id
            or parent.record.aggregate_id != material_state_id
        ):
            raise CatalogConflict(
                "Property Set must reference the selected Material State identity"
            )

    def create_material(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateMaterial,
    ) -> MaterialSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        reason = _reason(command.change_reason)
        aggregate_id = self._id()
        record = self._revision_service(
            MATERIAL_AGGREGATE_TYPE,
            self._repository.material_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=self._scope(context, command.classification.value),
                schema_id=MATERIAL_SCHEMA_ID,
                schema_version=MATERIAL_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return MaterialSnapshot(aggregate_id, RevisionSnapshot(record, command.content))

    def revise_material(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        command: ReviseMaterial,
    ) -> MaterialSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_material(
            context=context, decision=decision, material_id=material_id
        )
        record = self._revision_service(
            MATERIAL_AGGREGATE_TYPE,
            self._repository.material_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=material_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=MATERIAL_SCHEMA_ID,
                schema_version=MATERIAL_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return MaterialSnapshot(material_id, RevisionSnapshot(record, command.content))

    def create_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateMaterialState,
    ) -> MaterialStateSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        material_revision = self._repository.get_material_revision(
            context=context,
            decision=decision,
            material_id=command.content.material_id,
            revision_id=command.content.material_revision_id,
        )
        self._validate_material_parent(
            command.content, material_revision, command.content.material_id
        )
        aggregate_id = self._id()
        record = self._revision_service(
            MATERIAL_STATE_AGGREGATE_TYPE,
            self._repository.material_state_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=material_revision.record.scope,
                schema_id=MATERIAL_STATE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return MaterialStateSnapshot(
            aggregate_id,
            command.content.material_id,
            RevisionSnapshot(record, command.content),
        )

    def revise_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        command: ReviseMaterialState,
    ) -> MaterialStateSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )
        if command.content.material_id != current.material_id:
            raise CatalogConflict("Material State cannot move to another Material identity")
        material_revision = self._repository.get_material_revision(
            context=context,
            decision=decision,
            material_id=current.material_id,
            revision_id=command.content.material_revision_id,
        )
        self._validate_material_parent(command.content, material_revision, current.material_id)
        if material_revision.record.scope != current.current.record.scope:
            raise CatalogConflict("Material State cannot cross classification boundaries")
        record = self._revision_service(
            MATERIAL_STATE_AGGREGATE_TYPE,
            self._repository.material_state_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=material_state_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=MATERIAL_STATE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return MaterialStateSnapshot(
            material_state_id,
            current.material_id,
            RevisionSnapshot(record, command.content),
        )

    def create_property_set(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreatePropertySet,
    ) -> PropertySetSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        state_revision = self._repository.get_material_state_revision(
            context=context,
            decision=decision,
            material_state_id=command.content.material_state_id,
            revision_id=command.content.material_state_revision_id,
        )
        self._validate_state_parent(
            command.content, state_revision, command.content.material_state_id
        )
        aggregate_id = self._id()
        record = self._revision_service(
            PROPERTY_SET_AGGREGATE_TYPE,
            self._repository.property_set_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=state_revision.record.scope,
                schema_id=PROPERTY_SET_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return PropertySetSnapshot(
            aggregate_id,
            command.content.material_state_id,
            RevisionSnapshot(record, command.content),
        )

    def revise_property_set(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        property_set_id: UUID,
        command: RevisePropertySet,
    ) -> PropertySetSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_property_set(
            context=context, decision=decision, property_set_id=property_set_id
        )
        if command.content.material_state_id != current.material_state_id:
            raise CatalogConflict("Property Set cannot move to another Material State identity")
        state_revision = self._repository.get_material_state_revision(
            context=context,
            decision=decision,
            material_state_id=current.material_state_id,
            revision_id=command.content.material_state_revision_id,
        )
        self._validate_state_parent(command.content, state_revision, current.material_state_id)
        if state_revision.record.scope != current.current.record.scope:
            raise CatalogConflict("Property Set cannot cross classification boundaries")
        record = self._revision_service(
            PROPERTY_SET_AGGREGATE_TYPE,
            self._repository.property_set_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=property_set_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=PROPERTY_SET_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return PropertySetSnapshot(
            property_set_id,
            current.material_state_id,
            RevisionSnapshot(record, command.content),
        )

    def create_process_definition(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateProcessDefinition,
    ) -> ProcessDefinitionSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        aggregate_id = self._id()
        record = self._revision_service(
            PROCESS_DEFINITION_AGGREGATE_TYPE,
            self._repository.process_definition_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=self._scope(context, command.classification.value),
                schema_id=PROCESS_DEFINITION_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessDefinitionSnapshot(aggregate_id, RevisionSnapshot(record, command.content))

    def revise_process_definition(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_definition_id: UUID,
        command: ReviseProcessDefinition,
    ) -> ProcessDefinitionSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_process_definition(
            context=context,
            decision=decision,
            process_definition_id=process_definition_id,
        )
        record = self._revision_service(
            PROCESS_DEFINITION_AGGREGATE_TYPE,
            self._repository.process_definition_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=process_definition_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=PROCESS_DEFINITION_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessDefinitionSnapshot(
            process_definition_id, RevisionSnapshot(record, command.content)
        )

    def create_material_lot(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateMaterialLot,
    ) -> MaterialLotSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        material_revision = self._repository.get_material_revision(
            context=context,
            decision=decision,
            material_id=command.content.material_id,
            revision_id=command.content.material_revision_id,
        )
        aggregate_id = self._id()
        record = self._revision_service(
            MATERIAL_LOT_AGGREGATE_TYPE,
            self._repository.material_lot_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=material_revision.record.scope,
                schema_id=MATERIAL_LOT_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return MaterialLotSnapshot(
            aggregate_id,
            command.content.material_id,
            RevisionSnapshot(record, command.content),
        )

    def revise_material_lot(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_lot_id: UUID,
        command: ReviseMaterialLot,
    ) -> MaterialLotSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_material_lot(
            context=context, decision=decision, material_lot_id=material_lot_id
        )
        if command.content.material_id != current.material_id:
            raise CatalogConflict("Material Lot cannot move to another Material identity")
        material_revision = self._repository.get_material_revision(
            context=context,
            decision=decision,
            material_id=current.material_id,
            revision_id=command.content.material_revision_id,
        )
        if material_revision.record.scope != current.current.record.scope:
            raise CatalogConflict("Material Lot cannot cross classification boundaries")
        record = self._revision_service(
            MATERIAL_LOT_AGGREGATE_TYPE,
            self._repository.material_lot_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=material_lot_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=MATERIAL_LOT_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return MaterialLotSnapshot(
            material_lot_id,
            current.material_id,
            RevisionSnapshot(record, command.content),
        )

    def _validate_genealogy_sources(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: StateGenealogyContent,
    ) -> RevisionSnapshot[MaterialStateContent]:
        state = self._repository.get_material_state_revision(
            context=context,
            decision=decision,
            material_state_id=content.material_state_id,
            revision_id=content.material_state_revision_id,
        )
        process_links = (
            (
                content.manufacturing_process_id,
                content.manufacturing_process_revision_id,
                ProcessKind.MANUFACTURING,
            ),
            (
                content.heat_treatment_process_id,
                content.heat_treatment_process_revision_id,
                ProcessKind.HEAT_TREATMENT,
            ),
        )
        for identity, revision_id, required_kind in process_links:
            if identity is None:
                continue
            assert revision_id is not None
            process = self._repository.get_process_definition_revision(
                context=context,
                decision=decision,
                process_definition_id=identity,
                revision_id=revision_id,
            )
            if process.record.scope != state.record.scope:
                raise CatalogConflict("State genealogy cannot cross process scope boundaries")
            if process.content.kind is not required_kind:
                raise CatalogConflict(
                    f"{required_kind.value} link must reference a matching process kind"
                )
        if content.material_lot_id is not None:
            assert content.material_lot_revision_id is not None
            lot = self._repository.get_material_lot_revision(
                context=context,
                decision=decision,
                material_lot_id=content.material_lot_id,
                revision_id=content.material_lot_revision_id,
            )
            if lot.record.scope != state.record.scope:
                raise CatalogConflict("State genealogy cannot cross Material Lot scope boundaries")
            if (
                lot.content.material_id != state.content.material_id
                or lot.content.material_revision_id != state.content.material_revision_id
            ):
                raise CatalogConflict(
                    "State genealogy Lot must pin the same Material identity and revision"
                )
        return state

    def create_state_genealogy(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateStateGenealogy,
    ) -> StateGenealogySnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        state_revision = self._validate_genealogy_sources(context, decision, command.content)
        if (
            self._repository.get_state_genealogy_for_state(
                context=context,
                decision=decision,
                material_state_id=command.content.material_state_id,
            )
            is not None
        ):
            raise CatalogConflict("Material State already has a stable genealogy identity")
        aggregate_id = self._id()
        record = self._revision_service(
            STATE_GENEALOGY_AGGREGATE_TYPE,
            self._repository.state_genealogy_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=state_revision.record.scope,
                schema_id=STATE_GENEALOGY_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return StateGenealogySnapshot(
            aggregate_id,
            command.content.material_state_id,
            RevisionSnapshot(record, command.content),
        )

    def revise_state_genealogy(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        state_genealogy_id: UUID,
        command: ReviseStateGenealogy,
    ) -> StateGenealogySnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_state_genealogy(
            context=context, decision=decision, state_genealogy_id=state_genealogy_id
        )
        if command.content.material_state_id != current.material_state_id:
            raise CatalogConflict("State Genealogy cannot move to another Material State")
        state_revision = self._validate_genealogy_sources(context, decision, command.content)
        if state_revision.record.scope != current.current.record.scope:
            raise CatalogConflict("State Genealogy cannot cross classification boundaries")
        record = self._revision_service(
            STATE_GENEALOGY_AGGREGATE_TYPE,
            self._repository.state_genealogy_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=state_genealogy_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=STATE_GENEALOGY_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return StateGenealogySnapshot(
            state_genealogy_id,
            current.material_state_id,
            RevisionSnapshot(record, command.content),
        )

    def _validate_process_run_sources(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ProcessRunContent,
    ) -> RevisionSnapshot[MaterialStateContent]:
        state = self._repository.get_material_state_revision(
            context=context,
            decision=decision,
            material_state_id=content.material_state_id,
            revision_id=content.material_state_revision_id,
        )
        process = self._repository.get_process_definition_revision(
            context=context,
            decision=decision,
            process_definition_id=content.process_definition_id,
            revision_id=content.process_definition_revision_id,
        )
        if process.record.scope != state.record.scope:
            raise CatalogConflict("Process Run definition and Material State scopes must match")
        for flow in (*content.inputs, *content.outputs):
            lot = self._repository.get_material_lot_revision(
                context=context,
                decision=decision,
                material_lot_id=flow.material_lot_id,
                revision_id=flow.material_lot_revision_id,
            )
            if lot.record.scope != state.record.scope:
                raise CatalogConflict("Process Run Lot cannot cross scope boundaries")
            if (
                lot.content.material_id != state.content.material_id
                or lot.content.material_revision_id != state.content.material_revision_id
            ):
                raise CatalogConflict(
                    "Process Run Lot must pin the Material revision used by the State"
                )
        return state

    def create_process_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateProcessRun,
    ) -> ProcessRunSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        state = self._validate_process_run_sources(context, decision, command.content)
        aggregate_id = self._id()
        record = self._revision_service(
            PROCESS_RUN_AGGREGATE_TYPE,
            self._repository.process_run_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=state.record.scope,
                schema_id=PROCESS_RUN_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessRunSnapshot(
            aggregate_id,
            command.content.material_state_id,
            RevisionSnapshot(record, command.content),
        )

    def revise_process_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_run_id: UUID,
        command: ReviseProcessRun,
    ) -> ProcessRunSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        current = self._repository.get_process_run(
            context=context, decision=decision, process_run_id=process_run_id
        )
        if command.content.material_state_id != current.material_state_id:
            raise CatalogConflict("Process Run cannot move to another Material State")
        state = self._validate_process_run_sources(context, decision, command.content)
        if state.record.scope != current.current.record.scope:
            raise CatalogConflict("Process Run cannot cross classification boundaries")
        if command.content.run_code != current.current.content.run_code:
            raise CatalogConflict("Process Run stable code cannot change across revisions")
        record = self._revision_service(
            PROCESS_RUN_AGGREGATE_TYPE,
            self._repository.process_run_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=process_run_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=PROCESS_RUN_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessRunSnapshot(
            process_run_id,
            current.material_state_id,
            RevisionSnapshot(record, command.content),
        )

    def list_materials(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        query: str | None = None,
        material_class: MaterialClass | None = None,
        limit: int = 50,
    ) -> tuple[MaterialSnapshot, ...]:
        _require_decision(context, decision, Permission.CATALOG_READ)
        if query is not None and (query != query.strip() or not query or len(query) > 200):
            raise ValueError("material search query must be trimmed and contain 1..200 characters")
        if not 1 <= limit <= 100:
            raise ValueError("material search limit must be between 1 and 100")
        return self._repository.list_materials(
            context=context,
            decision=decision,
            query=query,
            material_class=material_class,
            limit=limit,
        )

    def list_process_definitions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        kind: ProcessKind | None = None,
        limit: int = 100,
    ) -> tuple[ProcessDefinitionSnapshot, ...]:
        _require_decision(context, decision, Permission.CATALOG_READ)
        if not 1 <= limit <= 100:
            raise ValueError("process definition limit must be between 1 and 100")
        return self._repository.list_process_definitions(
            context=context, decision=decision, kind=kind, limit=limit
        )

    def list_material_lots(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        *,
        limit: int = 100,
    ) -> tuple[MaterialLotSnapshot, ...]:
        _require_decision(context, decision, Permission.CATALOG_READ)
        if not 1 <= limit <= 100:
            raise ValueError("Material Lot limit must be between 1 and 100")
        self._repository.get_material(context=context, decision=decision, material_id=material_id)
        return self._repository.list_material_lots(
            context=context,
            decision=decision,
            material_id=material_id,
            limit=limit,
        )

    def list_process_runs_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        *,
        limit: int = 100,
    ) -> tuple[ProcessRunSnapshot, ...]:
        _require_decision(context, decision, Permission.CATALOG_READ)
        if not 1 <= limit <= 100:
            raise ValueError("Process Run limit must be between 1 and 100")
        self._repository.get_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )
        return self._repository.list_process_runs_for_state(
            context=context,
            decision=decision,
            material_state_id=material_state_id,
            limit=limit,
        )

    def get_process_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_run_id: UUID,
    ) -> ProcessRunSnapshot:
        _require_decision(context, decision, Permission.CATALOG_READ)
        return self._repository.get_process_run(
            context=context, decision=decision, process_run_id=process_run_id
        )

    def get_process_run_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_run_id: UUID,
    ) -> ProcessRunSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_process_run(
            context=context, decision=decision, process_run_id=process_run_id
        )

    def get_state_genealogy_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> StateGenealogySnapshot | None:
        _require_decision(context, decision, Permission.CATALOG_READ)
        return self._repository.get_state_genealogy_for_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

    def get_state_genealogy_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        state_genealogy_id: UUID,
    ) -> StateGenealogySnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_state_genealogy(
            context=context, decision=decision, state_genealogy_id=state_genealogy_id
        )

    def get_process_definition_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_definition_id: UUID,
    ) -> ProcessDefinitionSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_process_definition(
            context=context,
            decision=decision,
            process_definition_id=process_definition_id,
        )

    def get_material_lot_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_lot_id: UUID,
    ) -> MaterialLotSnapshot:
        _require_decision(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_material_lot(
            context=context, decision=decision, material_lot_id=material_lot_id
        )

    def get_material(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> MaterialSnapshot:
        _require_decision(context, decision, Permission.CATALOG_READ)
        return self._repository.get_material(
            context=context, decision=decision, material_id=material_id
        )

    def get_material_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> MaterialSnapshot:
        """Read the current head while a catalog.write command owns the DB capability."""

        _require_decision(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_material(
            context=context, decision=decision, material_id=material_id
        )

    def get_material_state_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> MaterialStateSnapshot:
        """Read a State head solely to validate its revision precondition."""

        _require_decision(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

    def get_property_set_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        property_set_id: UUID,
    ) -> PropertySetSnapshot:
        """Read a Property Set head solely to validate its revision precondition."""

        _require_decision(context, decision, Permission.CATALOG_WRITE)
        return self._repository.get_property_set(
            context=context, decision=decision, property_set_id=property_set_id
        )

    def get_material_detail(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> MaterialDetail:
        _require_decision(context, decision, Permission.CATALOG_READ)
        return self._repository.get_material_detail(
            context=context, decision=decision, material_id=material_id
        )

    def get_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> MaterialStateSnapshot:
        _require_decision(context, decision, Permission.CATALOG_READ)
        return self._repository.get_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

    def get_property_set(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        property_set_id: UUID,
    ) -> PropertySetSnapshot:
        _require_decision(context, decision, Permission.CATALOG_READ)
        return self._repository.get_property_set(
            context=context, decision=decision, property_set_id=property_set_id
        )

    def get_property_set_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        property_set_id: UUID,
        property_set_revision_id: UUID,
    ) -> RevisionSnapshot[PropertySetContent]:
        """Resolve the exact typed property source for an authorized calibration command."""

        _require_capability(context, decision, Permission.CATALOG_READ)
        return self._repository.get_property_set_revision(
            context=context,
            decision=decision,
            property_set_id=property_set_id,
            revision_id=property_set_revision_id,
        )

    def list_material_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> tuple[RevisionSnapshot[MaterialContent], ...]:
        _require_decision(context, decision, Permission.CATALOG_READ)
        return self._repository.list_material_revisions(
            context=context, decision=decision, material_id=material_id
        )

    def compare_material_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        left_revision_id: UUID,
        right_revision_id: UUID,
    ) -> tuple[
        RevisionSnapshot[MaterialContent], RevisionSnapshot[MaterialContent], tuple[str, ...]
    ]:
        _require_decision(context, decision, Permission.CATALOG_READ)
        left = self._repository.get_material_revision(
            context=context,
            decision=decision,
            material_id=material_id,
            revision_id=left_revision_id,
        )
        right = self._repository.get_material_revision(
            context=context,
            decision=decision,
            material_id=material_id,
            revision_id=right_revision_id,
        )
        changed = tuple(
            name
            for name in (
                "name",
                "material_code",
                "material_family",
                "description",
                "material_class",
            )
            if getattr(left.content, name) != getattr(right.content, name)
        )
        return left, right, changed
