"""Generate immutable OpenRadioss LAW36 and Abaqus isotropic-plasticity cards."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.exporting.application.service import (
    SOLVER_CARD_AGGREGATE_TYPE,
    RevisionSnapshot,
)
from cmp.modules.exporting.domain.reference_isotropic_tabulated_plasticity import (
    ElastoplasticExportTarget,
    ElastoplasticMappingReport,
    ElastoplasticSolverCardConflict,
    ReferenceElastoplasticSolverCardContent,
    build_reference_elastoplastic_solver_card,
    preflight_reference_elastoplastic_export,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelService,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

ELASTOPLASTIC_SOLVER_CARD_SCHEMA_ID = (
    "urn:cmp:exporting:reference-isotropic-tabulated-plasticity-card:1.0.0"
)
ELASTOPLASTIC_SOLVER_CARD_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class CreateReferenceElastoplasticSolverCard:
    material_model_id: UUID
    material_model_revision_id: UUID
    target: ElastoplasticExportTarget
    expected_mapping_report_sha256: str
    solver_material_id: int
    material_name: str
    change_reason: str


@dataclass(frozen=True, slots=True)
class ElastoplasticSolverCardSnapshot:
    id: UUID
    material_model_id: UUID
    target: ElastoplasticExportTarget
    solver_material_id: int
    material_name: str
    current: RevisionSnapshot[ReferenceElastoplasticSolverCardContent]


class ElastoplasticExportingRepository(Protocol):
    def solver_card_store(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source_model_revision_id: UUID,
    ) -> RevisionStore[ReferenceElastoplasticSolverCardContent]: ...

    def get_solver_card(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> ElastoplasticSolverCardSnapshot: ...

    def list_solver_cards_for_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[ElastoplasticSolverCardSnapshot, ...]: ...


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
        raise ElastoplasticSolverCardConflict(
            "authorization decision does not match elastoplastic export request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class ElastoplasticSolverCardService:
    def __init__(
        self,
        *,
        repository: ElastoplasticExportingRepository,
        material_models: TabulatedPlasticityModelService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._material_models = material_models
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("solver-card id_factory returned a zero UUID")
        return value

    def preflight(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        material_model_id: UUID,
        material_model_revision_id: UUID,
        target: ElastoplasticExportTarget,
    ) -> ElastoplasticMappingReport:
        _require_decision(context, decision, Permission.EXPORT_READ)
        source = self._material_models.get_model_revision_for_export(
            context,
            decision,
            material_model_id,
            material_model_revision_id,
        )
        return preflight_reference_elastoplastic_export(
            material_model_id=material_model_id,
            material_model_revision_id=source.record.revision_id,
            content=source.content,
            target=target,
        )

    async def create_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceElastoplasticSolverCard,
    ) -> tuple[ElastoplasticSolverCardSnapshot, ElastoplasticMappingReport]:
        _require_decision(context, decision, Permission.EXPORT_EXECUTE)
        reason = _reason(command.change_reason)
        source = self._material_models.get_model_revision_for_export(
            context,
            decision,
            command.material_model_id,
            command.material_model_revision_id,
        )
        points = await self._material_models.read_hardening_curve_for_export(
            context,
            decision,
            source.content,
        )
        report, content = build_reference_elastoplastic_solver_card(
            material_model_id=command.material_model_id,
            material_model_revision_id=source.record.revision_id,
            source=source.content,
            points=points,
            target=command.target,
            expected_mapping_report_sha256=command.expected_mapping_report_sha256,
            solver_material_id=command.solver_material_id,
            material_name=command.material_name,
        )
        aggregate_id = self._id()
        record = RevisionService(
            aggregate_type=SOLVER_CARD_AGGREGATE_TYPE,
            store=self._repository.solver_card_store(
                context=context,
                decision=decision,
                source_model_revision_id=source.record.revision_id,
            ),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    source.record.scope.classification,
                ),
                schema_id=ELASTOPLASTIC_SOLVER_CARD_SCHEMA_ID,
                schema_version=ELASTOPLASTIC_SOLVER_CARD_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return (
            ElastoplasticSolverCardSnapshot(
                id=aggregate_id,
                material_model_id=command.material_model_id,
                target=command.target,
                solver_material_id=command.solver_material_id,
                material_name=command.material_name,
                current=RevisionSnapshot(record, content),
            ),
            report,
        )

    def get_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> ElastoplasticSolverCardSnapshot:
        _require_decision(context, decision, Permission.EXPORT_READ)
        return self._repository.get_solver_card(
            context=context,
            decision=decision,
            solver_card_id=solver_card_id,
        )

    def list_cards_for_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[ElastoplasticSolverCardSnapshot, ...]:
        _require_decision(context, decision, Permission.EXPORT_READ)
        return self._repository.list_solver_cards_for_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )
