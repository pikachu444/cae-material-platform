"""Create and read the manual reference linear-viscoelastic Material Model IR."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_ID,
    REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_ID,
    REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
    BulkRelaxationStatus,
    LinearViscoelasticConflict,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
    ReferencePronyPromotionEvidence,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope


@dataclass(frozen=True, slots=True)
class CreateReferenceLinearViscoelasticModel:
    material_state_id: UUID
    property_set_revision_id: UUID
    bulk_relaxation_status: BulkRelaxationStatus
    terms: tuple[PronyTerm, ...]
    change_reason: str


@dataclass(frozen=True, slots=True)
class PromoteReferencePronyCandidate:
    material_model_id: UUID
    baseline_model_revision_id: UUID
    terms: tuple[PronyTerm, PronyTerm]
    evidence: ReferencePronyPromotionEvidence
    change_reason: str


@dataclass(frozen=True, slots=True)
class LinearViscoelasticModelSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[ReferenceLinearViscoelasticContent]


class LinearViscoelasticRepository(Protocol):
    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceLinearViscoelasticContent]: ...

    def get_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> LinearViscoelasticModelSnapshot: ...

    def list_material_models_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[LinearViscoelasticModelSnapshot, ...]: ...

    def get_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearViscoelasticContent]: ...


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
        raise LinearViscoelasticConflict(
            "authorization decision does not match linear-viscoelastic request"
        )


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
        raise LinearViscoelasticConflict(
            "authorization decision lacks the required Modeling capability"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class LinearViscoelasticModelService:
    """Manual Prony IR creation with exact Catalog revision lineage."""

    def __init__(
        self,
        *,
        repository: LinearViscoelasticRepository,
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
        command: CreateReferenceLinearViscoelasticModel,
    ) -> LinearViscoelasticModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_WRITE)
        source = self._material_models.get_reference_property_source_for_linear_viscoelasticity(
            context,
            decision,
            material_state_id=command.material_state_id,
            property_set_revision_id=command.property_set_revision_id,
        )
        if source.material_class not in {"polymer", "elastomer"}:
            raise LinearViscoelasticConflict(
                "linear viscoelasticity requires a polymer- or elastomer-classified "
                "Material revision"
            )
        properties = source.content
        content = ReferenceLinearViscoelasticContent(
            material_id=properties.material_id,
            material_revision_id=properties.material_revision_id,
            material_state_id=properties.material_state_id,
            material_state_revision_id=properties.material_state_revision_id,
            property_set_id=properties.property_set_id,
            property_set_revision_id=properties.property_set_revision_id,
            density_kg_per_m3=properties.density_kg_per_m3,
            youngs_modulus_pa=properties.youngs_modulus_pa,
            poisson_ratio=properties.poisson_ratio,
            bulk_relaxation_status=command.bulk_relaxation_status,
            terms=command.terms,
            applicable_temperature_min_k=properties.applicable_temperature_min_k,
            applicable_temperature_max_k=properties.applicable_temperature_max_k,
            applicable_strain_rate_min_per_s=properties.applicable_strain_rate_min_per_s,
            applicable_strain_rate_max_per_s=properties.applicable_strain_rate_max_per_s,
            applicability_note=properties.applicability_note,
            reference_temperature_k=properties.reference_temperature_k,
        )
        aggregate_id = self._id_factory()
        if aggregate_id.int == 0:
            raise RuntimeError("linear-viscoelastic id_factory returned a zero UUID")
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
                schema_id=REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_ID,
                schema_version=REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return LinearViscoelasticModelSnapshot(
            aggregate_id,
            command.material_state_id,
            RevisionSnapshot(record, content),
        )

    def get_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> LinearViscoelasticModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )

    def promote_candidate(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromoteReferencePronyCandidate,
    ) -> LinearViscoelasticModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_WRITE)
        baseline = self._repository.get_material_model(
            context=context,
            decision=decision,
            material_model_id=command.material_model_id,
        )
        if baseline.current.record.revision_id != command.baseline_model_revision_id:
            raise LinearViscoelasticConflict(
                "Candidate promotion requires the exact baseline revision to remain current"
            )
        if baseline.current.content.prony_promotion_evidence is not None:
            raise LinearViscoelasticConflict(
                "a promoted linear-Prony revision cannot silently replace its evidence"
            )
        content = replace(
            baseline.current.content,
            terms=command.terms,
            prony_promotion_evidence=command.evidence,
        )
        record = RevisionService(
            aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
            store=self._repository.material_model_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=command.material_model_id,
                scope=baseline.current.record.scope,
                expected_current_revision_id=command.baseline_model_revision_id,
                based_on_revision_id=command.baseline_model_revision_id,
                schema_id=REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_ID,
                schema_version=REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return LinearViscoelasticModelSnapshot(
            command.material_model_id,
            content.material_state_id,
            RevisionSnapshot(record, content),
        )

    def list_models_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[LinearViscoelasticModelSnapshot, ...]:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.list_material_models_for_state(
            context=context,
            decision=decision,
            material_state_id=material_state_id,
        )

    def get_model_revision_for_export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearViscoelasticContent]:
        if decision.permission not in {Permission.EXPORT_READ, Permission.EXPORT_EXECUTE}:
            raise LinearViscoelasticConflict(
                "linear-viscoelastic export requires export.read or export.execute"
            )
        _require_decision(context, decision, decision.permission)
        snapshot = self._repository.get_material_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )
        if snapshot.current.record.revision_id != material_model_revision_id:
            raise LinearViscoelasticConflict(
                "the exact requested immutable Material Model revision is not current"
            )
        return snapshot.current

    def get_model_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearViscoelasticContent]:
        _require_capability(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model_revision(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
            material_model_revision_id=material_model_revision_id,
        )
