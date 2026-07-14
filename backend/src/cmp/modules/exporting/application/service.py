"""Create immutable reference solver cards from one frozen Material Model IR revision."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.exporting.domain.openradioss_elast import (
    ExportTarget,
    ReferenceMappingReport,
    ReferenceOpenRadiossCardContent,
    SolverCardConflict,
    build_reference_openradioss_card,
    preflight_reference_openradioss_elast,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_linear_elasticity import ReferenceLinearElasticContent
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

SOLVER_CARD_AGGREGATE_TYPE = "exporting.solver_card"
SOLVER_CARD_SCHEMA_ID = "urn:cmp:exporting:reference-openradioss-elast:1.0.0"
SOLVER_CARD_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class ReferenceMaterialModelSource:
    """A concrete, visible reference IR revision selected as an exporter input."""

    material_model_id: UUID
    classification: DataClassification
    revision: RevisionSnapshot[ReferenceLinearElasticContent]


@dataclass(frozen=True, slots=True)
class SolverCardSnapshot:
    id: UUID
    material_model_id: UUID
    target: ExportTarget
    solver_material_id: int
    current: RevisionSnapshot[ReferenceOpenRadiossCardContent]


@dataclass(frozen=True, slots=True)
class CreateReferenceOpenRadiossCard:
    material_model_id: UUID
    material_model_revision_id: UUID
    target: ExportTarget
    expected_mapping_report_sha256: str
    solver_material_id: int
    card_title: str
    change_reason: str


class ExportingRepository(Protocol):
    def load_current_reference_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> ReferenceMaterialModelSource: ...

    def load_reference_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> ReferenceMaterialModelSource: ...

    def solver_card_store(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source_model_revision_id: UUID,
    ) -> RevisionStore[ReferenceOpenRadiossCardContent]: ...

    def get_solver_card(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> SolverCardSnapshot: ...

    def list_solver_cards_for_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[SolverCardSnapshot, ...]: ...

    def list_solver_card_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> tuple[RevisionSnapshot[ReferenceOpenRadiossCardContent], ...]: ...

    def get_solver_card_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
        solver_card_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceOpenRadiossCardContent]: ...


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
        raise SolverCardConflict("authorization decision does not match solver-card request")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class SolverCardService:
    """Bounded reference exporter; all persisted outputs use the shared revision kernel."""

    def __init__(
        self,
        *,
        repository: ExportingRepository,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("solver-card id_factory returned a zero UUID")
        return value

    def preflight_reference_openradioss(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        target: ExportTarget,
    ) -> ReferenceMappingReport:
        _require_decision(context, decision, Permission.EXPORT_READ)
        source = self._repository.load_current_reference_material_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )
        return preflight_reference_openradioss_elast(
            material_model_id=source.material_model_id,
            material_model_revision_id=source.revision.record.revision_id,
            content=source.revision.content,
            target=target,
        )

    def create_reference_openradioss_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceOpenRadiossCard,
    ) -> tuple[SolverCardSnapshot, ReferenceMappingReport]:
        _require_decision(context, decision, Permission.EXPORT_EXECUTE)
        reason = _reason(command.change_reason)
        source = self._repository.load_reference_material_model_revision(
            context=context,
            decision=decision,
            material_model_id=command.material_model_id,
            material_model_revision_id=command.material_model_revision_id,
        )
        report, content = build_reference_openradioss_card(
            material_model_id=source.material_model_id,
            material_model_revision_id=source.revision.record.revision_id,
            source=source.revision.content,
            target=command.target,
            expected_mapping_report_sha256=command.expected_mapping_report_sha256,
            solver_material_id=command.solver_material_id,
            card_title=command.card_title,
        )
        aggregate_id = self._id()
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            source.classification.value,
        )
        record = RevisionService(
            aggregate_type=SOLVER_CARD_AGGREGATE_TYPE,
            store=self._repository.solver_card_store(
                context=context,
                decision=decision,
                source_model_revision_id=source.revision.record.revision_id,
            ),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=scope,
                schema_id=SOLVER_CARD_SCHEMA_ID,
                schema_version=SOLVER_CARD_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return (
            SolverCardSnapshot(
                id=aggregate_id,
                material_model_id=source.material_model_id,
                target=command.target,
                solver_material_id=command.solver_material_id,
                current=RevisionSnapshot(record, content),
            ),
            report,
        )

    def get_solver_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> SolverCardSnapshot:
        _require_decision(context, decision, Permission.EXPORT_READ)
        return self._repository.get_solver_card(
            context=context,
            decision=decision,
            solver_card_id=solver_card_id,
        )

    def list_solver_cards_for_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[SolverCardSnapshot, ...]:
        _require_decision(context, decision, Permission.EXPORT_READ)
        return self._repository.list_solver_cards_for_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )

    def list_solver_card_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> tuple[RevisionSnapshot[ReferenceOpenRadiossCardContent], ...]:
        _require_decision(context, decision, Permission.EXPORT_READ)
        return self._repository.list_solver_card_revisions(
            context=context,
            decision=decision,
            solver_card_id=solver_card_id,
        )

    def get_solver_card_revision_for_validation(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
        solver_card_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceOpenRadiossCardContent]:
        """Expose one exact immutable Solver Card revision to Validation."""

        if (
            decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
            or decision.request_id != context.request_id
            or decision.trace_id != context.trace_id
            or Permission.EXPORT_READ.value not in decision.database_permissions
        ):
            raise SolverCardConflict("authorization lacks the required Export capability")
        return self._repository.get_solver_card_revision(
            context=context,
            decision=decision,
            solver_card_id=solver_card_id,
            solver_card_revision_id=solver_card_revision_id,
        )
