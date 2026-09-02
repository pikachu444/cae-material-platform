"""Application use-cases for the Plan-specific approval projection."""

from __future__ import annotations

from uuid import UUID

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationApplicationState,
    _reason,
    _require,
)
from cmp.modules.modeling.application.linear_viscoelastic_plan_governance import (
    LinearViscoelasticPlanApprovalPort,
    PlanApprovalRecord,
    PlanContextQuery,
    PlanContextResolution,
    PlanGovernanceError,
    PlanUsabilityFact,
)


def _governance_port(
    state: CalibrationApplicationState,
) -> LinearViscoelasticPlanApprovalPort:
    port = state._plan_governance
    if port is None:
        raise PlanGovernanceError(
            "Plan approval persistence is unavailable",
            code="PLAN_APPROVAL_UNAVAILABLE",
            recovery_hint="Configure the durable Plan approval projection before execution.",
        )
    return port


class LinearViscoelasticPlanGovernanceApplication:
    """Keep approval reads and usability changes separate from numerical Plan authoring."""

    def get_plan_approval(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> PlanApprovalRecord:
        _require(context, decision, Permission.MODELING_READ)
        return _governance_port(self).get_approval(
            context=context,
            decision=decision,
            plan_id=plan_id,
            plan_revision_id=plan_revision_id,
        )

    def resolve_plan_context(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: PlanContextQuery,
    ) -> PlanContextResolution:
        _require(context, decision, Permission.MODELING_READ)
        return _governance_port(self).resolve_exact_context(
            context=context,
            decision=decision,
            query=query,
        )

    def supersede_plan(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        plan_id: UUID,
        plan_revision_id: UUID,
        successor_plan_id: UUID,
        successor_plan_revision_id: UUID,
        reason: str,
    ) -> PlanUsabilityFact:
        _require(context, decision, Permission.REVIEW_DECIDE)
        old = self._repository.get_plan(plan_id, context=context, decision=decision)
        successor = self._repository.get_plan(
            successor_plan_id,
            context=context,
            decision=decision,
        )
        if successor.current.plan_revision_id != successor_plan_revision_id:
            raise PlanGovernanceError(
                "successor Plan revision is not current",
                code="PLAN_SOURCE_STALE",
                recovery_hint="Use the exact current successor Plan revision.",
            )
        if old.current.plan_revision_id != plan_revision_id:
            raise PlanGovernanceError(
                "Plan revision is stale",
                code="PLAN_SOURCE_STALE",
                recovery_hint="Read the exact Plan revision before changing usability.",
            )
        return _governance_port(self).supersede(
            context=context,
            decision=decision,
            plan_id=plan_id,
            plan_revision_id=plan_revision_id,
            successor_plan=successor,
            reason=_reason(reason),
        )

    def withdraw_plan(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        plan_id: UUID,
        plan_revision_id: UUID,
        reason: str,
    ) -> PlanUsabilityFact:
        _require(context, decision, Permission.REVIEW_DECIDE)
        plan = self._repository.get_plan(plan_id, context=context, decision=decision)
        if plan.current.plan_revision_id != plan_revision_id:
            raise PlanGovernanceError(
                "Plan revision is stale",
                code="PLAN_SOURCE_STALE",
                recovery_hint="Read the exact Plan revision before changing usability.",
            )
        return _governance_port(self).withdraw(
            context=context,
            decision=decision,
            plan_id=plan_id,
            plan_revision_id=plan_revision_id,
            plan_created_by=plan.created_by,
            reason=_reason(reason),
        )


__all__ = (
    "LinearViscoelasticPlanGovernanceApplication",
)
