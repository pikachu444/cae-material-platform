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
    MaterialStateContent,
    PropertySetContent,
)
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

MATERIAL_SCHEMA_ID = "urn:cmp:catalog:material:2.0.0"
MATERIAL_STATE_SCHEMA_ID = "urn:cmp:catalog:material-state:1.0.0"
PROPERTY_SET_SCHEMA_ID = "urn:cmp:catalog:property-set:1.0.0"
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
