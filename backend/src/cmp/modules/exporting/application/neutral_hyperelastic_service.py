"""Persist native cards from exact canonical Neutral Material revisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.exporting.application.service import RevisionSnapshot
from cmp.modules.exporting.domain.neutral_hyperelastic import (
    NeutralHyperelasticExportTarget,
    NeutralHyperelasticMappingReport,
    NeutralHyperelasticSolverCardConflict,
    NeutralHyperelasticSolverCardContent,
    build_neutral_hyperelastic_solver_card,
    preflight_neutral_hyperelastic_export,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.neutral_material import NeutralMaterialService
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

NEUTRAL_SOLVER_CARD_AGGREGATE_TYPE = "exporting.neutral_solver_card"
NEUTRAL_SOLVER_CARD_SCHEMA_ID = "urn:cmp:exporting:neutral-hyperelastic-card:1.0.0"
NEUTRAL_SOLVER_CARD_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class CreateNeutralHyperelasticSolverCard:
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    target: NeutralHyperelasticExportTarget
    expected_mapping_report_sha256: str
    solver_material_id: int
    material_name: str
    change_reason: str


@dataclass(frozen=True, slots=True)
class NeutralHyperelasticSolverCardSnapshot:
    id: UUID
    neutral_material_id: UUID
    target: NeutralHyperelasticExportTarget
    solver_material_id: int
    material_name: str
    current: RevisionSnapshot[NeutralHyperelasticSolverCardContent]


class NeutralHyperelasticExportingRepository(Protocol):
    def solver_card_store(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[NeutralHyperelasticSolverCardContent]: ...

    def get_solver_card(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> NeutralHyperelasticSolverCardSnapshot: ...

    def list_solver_cards_for_neutral_material(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
    ) -> tuple[NeutralHyperelasticSolverCardSnapshot, ...]: ...


def _require(
    context: SecurityContext, decision: AuthorizationDecision, permission: Permission
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise NeutralHyperelasticSolverCardConflict(
            "authorization decision does not match Neutral hyperelastic export request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class NeutralHyperelasticSolverCardService:
    def __init__(
        self,
        *,
        repository: NeutralHyperelasticExportingRepository,
        neutral_materials: NeutralMaterialService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._neutral_materials = neutral_materials
        self._id_factory = id_factory

    async def preflight(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        neutral_material_id: UUID,
        neutral_material_revision_id: UUID,
        target: NeutralHyperelasticExportTarget,
    ) -> NeutralHyperelasticMappingReport:
        _require(context, decision, Permission.EXPORT_READ)
        source = await self._neutral_materials.get_neutral_material_revision_for_export(
            context,
            decision,
            neutral_material_id,
            neutral_material_revision_id,
        )
        return preflight_neutral_hyperelastic_export(
            neutral_material_id=source.id,
            neutral_material_revision_id=source.current.revision_id,
            source=source.document,
            target=target,
        )

    async def create_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateNeutralHyperelasticSolverCard,
    ) -> tuple[NeutralHyperelasticSolverCardSnapshot, NeutralHyperelasticMappingReport]:
        _require(context, decision, Permission.EXPORT_EXECUTE)
        source = await self._neutral_materials.get_neutral_material_revision_for_export(
            context,
            decision,
            command.neutral_material_id,
            command.neutral_material_revision_id,
        )
        report, content = build_neutral_hyperelastic_solver_card(
            neutral_material_id=source.id,
            neutral_material_revision_id=source.current.revision_id,
            source=source.document,
            target=command.target,
            expected_mapping_report_sha256=command.expected_mapping_report_sha256,
            solver_material_id=command.solver_material_id,
            material_name=command.material_name,
        )
        aggregate_id = self._id_factory()
        if aggregate_id.int == 0:
            raise RuntimeError("solver-card id_factory returned a zero UUID")
        record = RevisionService(
            aggregate_type=NEUTRAL_SOLVER_CARD_AGGREGATE_TYPE,
            store=self._repository.solver_card_store(context=context, decision=decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    source.current.scope.classification,
                ),
                schema_id=NEUTRAL_SOLVER_CARD_SCHEMA_ID,
                schema_version=NEUTRAL_SOLVER_CARD_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        snapshot = NeutralHyperelasticSolverCardSnapshot(
            aggregate_id,
            source.id,
            command.target,
            command.solver_material_id,
            command.material_name,
            RevisionSnapshot(record, content),
        )
        return snapshot, report

    def get_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> NeutralHyperelasticSolverCardSnapshot:
        _require(context, decision, Permission.EXPORT_READ)
        return self._repository.get_solver_card(
            context=context, decision=decision, solver_card_id=solver_card_id
        )

    def list_cards(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
    ) -> tuple[NeutralHyperelasticSolverCardSnapshot, ...]:
        _require(context, decision, Permission.EXPORT_READ)
        return self._repository.list_solver_cards_for_neutral_material(
            context=context,
            decision=decision,
            neutral_material_id=neutral_material_id,
        )

    async def mapping_report(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> NeutralHyperelasticMappingReport:
        _require(context, decision, Permission.EXPORT_READ)
        card = self._repository.get_solver_card(
            context=context, decision=decision, solver_card_id=solver_card_id
        )
        source = await self._neutral_materials.get_neutral_material_revision_for_export(
            context,
            decision,
            card.current.content.neutral_material_id,
            card.current.content.neutral_material_revision_id,
        )
        report = preflight_neutral_hyperelastic_export(
            neutral_material_id=source.id,
            neutral_material_revision_id=source.current.revision_id,
            source=source.document,
            target=card.target,
        )
        if report.digest != card.current.content.mapping_report_sha256:
            raise NeutralHyperelasticSolverCardConflict(
                "persisted card no longer reproduces its mapping report"
            )
        return report
