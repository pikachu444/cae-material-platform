"""Create immutable Abaqus cards from exact reference linear-Prony IR revisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.exporting.application.service import (
    SOLVER_CARD_AGGREGATE_TYPE,
    RevisionSnapshot,
)
from cmp.modules.exporting.domain.reference_linear_viscoelasticity import (
    LinearViscoelasticExportTarget,
    LinearViscoelasticMappingReport,
    LinearViscoelasticSolverCardConflict,
    ReferenceLinearViscoelasticSolverCardContent,
    build_reference_linear_viscoelastic_solver_card,
    preflight_reference_linear_viscoelastic_export,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelService,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

LINEAR_VISCOELASTIC_SOLVER_CARD_SCHEMA_ID = (
    "urn:cmp:exporting:reference-linear-viscoelastic-prony-card:1.0.0"
)
LINEAR_VISCOELASTIC_SOLVER_CARD_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class CreateReferenceLinearViscoelasticSolverCard:
    material_model_id: UUID
    material_model_revision_id: UUID
    target: LinearViscoelasticExportTarget
    expected_mapping_report_sha256: str
    solver_material_id: int
    material_name: str
    change_reason: str


@dataclass(frozen=True, slots=True)
class LinearViscoelasticSolverCardSnapshot:
    id: UUID
    material_model_id: UUID
    target: LinearViscoelasticExportTarget
    solver_material_id: int
    material_name: str
    current: RevisionSnapshot[ReferenceLinearViscoelasticSolverCardContent]


class LinearViscoelasticExportingRepository(Protocol):
    def solver_card_store(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source_model_revision_id: UUID,
    ) -> RevisionStore[ReferenceLinearViscoelasticSolverCardContent]: ...

    def get_solver_card(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> LinearViscoelasticSolverCardSnapshot: ...

    def list_solver_cards_for_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[LinearViscoelasticSolverCardSnapshot, ...]: ...


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
        raise LinearViscoelasticSolverCardConflict(
            "authorization decision does not match linear-viscoelastic export request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class LinearViscoelasticSolverCardService:
    def __init__(
        self,
        *,
        repository: LinearViscoelasticExportingRepository,
        material_models: LinearViscoelasticModelService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._material_models = material_models
        self._id_factory = id_factory

    def preflight(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        material_model_id: UUID,
        material_model_revision_id: UUID,
        target: LinearViscoelasticExportTarget,
    ) -> LinearViscoelasticMappingReport:
        _require_decision(context, decision, Permission.EXPORT_READ)
        source = self._material_models.get_model_revision_for_export(
            context, decision, material_model_id, material_model_revision_id
        )
        return preflight_reference_linear_viscoelastic_export(
            material_model_id=material_model_id,
            material_model_revision_id=source.record.revision_id,
            source=source.content,
            target=target,
        )

    def create_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceLinearViscoelasticSolverCard,
    ) -> tuple[LinearViscoelasticSolverCardSnapshot, LinearViscoelasticMappingReport]:
        _require_decision(context, decision, Permission.EXPORT_EXECUTE)
        source = self._material_models.get_model_revision_for_export(
            context,
            decision,
            command.material_model_id,
            command.material_model_revision_id,
        )
        report, content = build_reference_linear_viscoelastic_solver_card(
            material_model_id=command.material_model_id,
            material_model_revision_id=source.record.revision_id,
            source=source.content,
            target=command.target,
            expected_mapping_report_sha256=command.expected_mapping_report_sha256,
            solver_material_id=command.solver_material_id,
            material_name=command.material_name,
        )
        aggregate_id = self._id_factory()
        if aggregate_id.int == 0:
            raise RuntimeError("solver-card id_factory returned a zero UUID")
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
                schema_id=LINEAR_VISCOELASTIC_SOLVER_CARD_SCHEMA_ID,
                schema_version=LINEAR_VISCOELASTIC_SOLVER_CARD_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return (
            LinearViscoelasticSolverCardSnapshot(
                aggregate_id,
                command.material_model_id,
                command.target,
                command.solver_material_id,
                command.material_name,
                RevisionSnapshot(record, content),
            ),
            report,
        )

    def get_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> LinearViscoelasticSolverCardSnapshot:
        _require_decision(context, decision, Permission.EXPORT_READ)
        return self._repository.get_solver_card(
            context=context, decision=decision, solver_card_id=solver_card_id
        )

    def list_cards_for_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[LinearViscoelasticSolverCardSnapshot, ...]:
        _require_decision(context, decision, Permission.EXPORT_READ)
        return self._repository.list_solver_cards_for_model(
            context=context, decision=decision, material_model_id=material_model_id
        )
