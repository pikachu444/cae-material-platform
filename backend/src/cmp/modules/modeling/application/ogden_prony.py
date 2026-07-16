"""Create and read the bounded manual Ogden-Prony reference IR."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_ogden_prony import (
    REFERENCE_OGDEN_PRONY_SCHEMA_ID,
    REFERENCE_OGDEN_PRONY_SCHEMA_VERSION,
    ReferenceOgdenPronyConflict,
    ReferenceOgdenPronyContent,
    ReferenceOgdenTerm,
    ReferenceShearPronyTerm,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope


@dataclass(frozen=True, slots=True)
class CreateReferenceOgdenPronyModel:
    material_state_id: UUID
    property_set_revision_id: UUID
    ogden_mu_pa: float
    ogden_alpha: float
    prony_terms: tuple[ReferenceShearPronyTerm, ...]
    change_reason: str


@dataclass(frozen=True, slots=True)
class OgdenPronyModelSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[ReferenceOgdenPronyContent]


class OgdenPronyRepository(Protocol):
    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceOgdenPronyContent]: ...

    def get_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> OgdenPronyModelSnapshot: ...

    def get_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceOgdenPronyContent]: ...

    def list_material_models_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[OgdenPronyModelSnapshot, ...]: ...


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
        raise ReferenceOgdenPronyConflict(
            "authorization decision does not match Ogden-Prony request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


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
        raise ReferenceOgdenPronyConflict(
            "authorization decision lacks Ogden-Prony model read capability"
        )


class OgdenPronyModelService:
    def __init__(
        self,
        *,
        repository: OgdenPronyRepository,
        material_models: MaterialModelService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._material_models = material_models
        self._id_factory = id_factory

    def create_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceOgdenPronyModel,
    ) -> OgdenPronyModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_WRITE)
        source = self._material_models.get_reference_property_source_for_linear_viscoelasticity(
            context,
            decision,
            material_state_id=command.material_state_id,
            property_set_revision_id=command.property_set_revision_id,
        )
        if source.material_class != "elastomer":
            raise ReferenceOgdenPronyConflict(
                "the reference Ogden-Prony family requires an elastomer Material revision"
            )
        properties = source.content
        content = ReferenceOgdenPronyContent(
            material_id=properties.material_id,
            material_revision_id=properties.material_revision_id,
            material_state_id=properties.material_state_id,
            material_state_revision_id=properties.material_state_revision_id,
            property_set_id=properties.property_set_id,
            property_set_revision_id=properties.property_set_revision_id,
            density_kg_per_m3=properties.density_kg_per_m3,
            catalog_youngs_modulus_pa=properties.youngs_modulus_pa,
            catalog_poisson_ratio=properties.poisson_ratio,
            ogden_term=ReferenceOgdenTerm(command.ogden_mu_pa, command.ogden_alpha),
            prony_terms=command.prony_terms,
            reference_temperature_k=properties.reference_temperature_k,
        )
        aggregate_id = self._id_factory()
        if aggregate_id.int == 0:
            raise RuntimeError("Ogden-Prony id_factory returned a zero UUID")
        record = RevisionService(
            aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
            store=self._repository.material_model_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    source.classification.value,
                ),
                schema_id=REFERENCE_OGDEN_PRONY_SCHEMA_ID,
                schema_version=REFERENCE_OGDEN_PRONY_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return OgdenPronyModelSnapshot(
            aggregate_id,
            command.material_state_id,
            RevisionSnapshot(record, content),
        )

    def get_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> OgdenPronyModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model(
            context=context, decision=decision, material_model_id=material_model_id
        )

    def list_models_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[OgdenPronyModelSnapshot, ...]:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.list_material_models_for_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

    def get_model_revision_for_export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceOgdenPronyContent]:
        if decision.permission not in {Permission.EXPORT_READ, Permission.EXPORT_EXECUTE}:
            raise ReferenceOgdenPronyConflict("Ogden-Prony export permission is required")
        _require_decision(context, decision, decision.permission)
        snapshot = self._repository.get_material_model(
            context=context, decision=decision, material_model_id=material_model_id
        )
        if snapshot.current.record.revision_id != material_model_revision_id:
            raise ReferenceOgdenPronyConflict(
                "the requested immutable Ogden-Prony revision is not current"
            )
        return snapshot.current

    def get_model_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceOgdenPronyContent]:
        _require_capability(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model_revision(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
            material_model_revision_id=material_model_revision_id,
        )
