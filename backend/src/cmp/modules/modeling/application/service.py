"""Create and retrieve the first typed Material Model IR revision."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    REFERENCE_MODEL_SCHEMA_VERSION,
    ReferenceLinearElasticContent,
    ReferenceModelConflict,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

MATERIAL_MODEL_AGGREGATE_TYPE = "modeling.material_model"
MATERIAL_MODEL_SCHEMA_ID = "urn:cmp:modeling:reference-isotropic-linear-elasticity:1.0.0"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class MaterialModelSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[ReferenceLinearElasticContent]


@dataclass(frozen=True, slots=True)
class ReferencePropertySource:
    """Concrete Catalog revisions selected as the immutable IR source."""

    classification: DataClassification
    content: ReferenceLinearElasticContent


@dataclass(frozen=True, slots=True)
class CreateReferenceLinearElasticModel:
    material_state_id: UUID
    property_set_revision_id: UUID
    change_reason: str


class ModelingRepository(Protocol):
    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceLinearElasticContent]: ...

    def load_reference_property_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        property_set_revision_id: UUID,
    ) -> ReferencePropertySource: ...

    def get_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> MaterialModelSnapshot: ...

    def list_material_models_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[MaterialModelSnapshot, ...]: ...

    def list_material_model_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[RevisionSnapshot[ReferenceLinearElasticContent], ...]: ...

    def get_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearElasticContent]: ...


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


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
        raise ReferenceModelConflict("authorization decision does not match Material Model request")


def _require_capability(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    """Authorize a bounded downstream command with an expanded Modeling read capability."""

    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise ReferenceModelConflict(
            "authorization decision lacks the required Modeling capability"
        )


class MaterialModelService:
    """Create immutable reference IRs from explicit, concrete Catalog Property Set revisions."""

    def __init__(
        self,
        *,
        repository: ModelingRepository,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("model id_factory returned a zero UUID")
        return value

    def create_reference_linear_elastic_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceLinearElasticModel,
    ) -> MaterialModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_WRITE)
        reason = _reason(command.change_reason)
        source = self._repository.load_reference_property_source(
            context=context,
            decision=decision,
            material_state_id=command.material_state_id,
            property_set_revision_id=command.property_set_revision_id,
        )
        if source.content.material_state_id != command.material_state_id:
            raise ReferenceModelConflict(
                "selected Property Set revision belongs to another Material State"
            )
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            source.classification.value,
        )
        aggregate_id = self._id()
        record = RevisionService(
            aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
            store=self._repository.material_model_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=scope,
                schema_id=MATERIAL_MODEL_SCHEMA_ID,
                schema_version=REFERENCE_MODEL_SCHEMA_VERSION,
                content=source.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return MaterialModelSnapshot(
            id=aggregate_id,
            material_state_id=source.content.material_state_id,
            current=RevisionSnapshot(record, source.content),
        )

    def get_material_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> MaterialModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )

    def list_material_models_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[MaterialModelSnapshot, ...]:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.list_material_models_for_state(
            context=context,
            decision=decision,
            material_state_id=material_state_id,
        )

    def list_material_model_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[RevisionSnapshot[ReferenceLinearElasticContent], ...]:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.list_material_model_revisions(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )

    def get_material_model_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearElasticContent]:
        """Expose one fixed IR revision to the authorized Calibration capability."""

        _require_capability(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model_revision(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
            material_model_revision_id=material_model_revision_id,
        )
