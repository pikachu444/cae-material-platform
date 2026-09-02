"""Approval, usability, and exact-context ports for linear-viscoelastic Plans.

The shared review module owns review requests and decisions.  This module owns the modeling
projection that makes an approved Plan executable, including append-only active/superseded/
withdrawn facts.  The in-memory implementation is intentionally an explicit fixture injector;
production composition uses the SQL adapter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    ExactRevisionPin,
    LinearViscoelasticCalibrationPlan,
)
from cmp.shared.domain.revisions import canonical_json_bytes

PLAN_AGGREGATE_TYPE = "modeling.linear_viscoelastic_calibration_plan"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PlanApprovalState(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class PlanGovernanceError(Exception):
    """Stable typed failure at the approval, source, or usability boundary."""

    def __init__(self, message: str, *, code: str, recovery_hint: str) -> None:
        self.code = code
        self.recovery_hint = recovery_hint
        super().__init__(message)


def _sha256(name: str, value: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValueError(f"{name} must be a non-zero UUID")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _pin_equal(left: ExactRevisionPin | None, right: ExactRevisionPin | None) -> bool:
    if left is None or right is None:
        return left is right
    return (
        left.aggregate_id == right.aggregate_id
        and left.revision_id == right.revision_id
        and (right.sha256 is None or left.sha256 == right.sha256)
    )


@dataclass(frozen=True, slots=True)
class PlanApprovalRecord:
    """Immutable projection of one approved Plan revision and its review evidence."""

    plan_id: UUID
    plan_revision_id: UUID
    plan_sha256: str
    classification: DataClassification
    plan_created_by: UUID
    review_request_id: UUID
    review_decision_id: UUID
    evidence_sha256: str
    approved_at: datetime
    approved_by: UUID
    state: PlanApprovalState
    setup_name: str
    material: ExactRevisionPin
    material_state: ExactRevisionPin
    test_data: ExactRevisionPin
    processing_output: ExactRevisionPin | None
    input_mode: str
    organization_id: UUID | None = None
    project_id: UUID | None = None
    superseded_by_plan_id: UUID | None = None
    superseded_by_plan_revision_id: UUID | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("plan_id", self.plan_id),
            ("plan_revision_id", self.plan_revision_id),
            ("plan_created_by", self.plan_created_by),
            ("review_request_id", self.review_request_id),
            ("review_decision_id", self.review_decision_id),
            ("approved_by", self.approved_by),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("superseded_by_plan_id", self.superseded_by_plan_id),
            ("superseded_by_plan_revision_id", self.superseded_by_plan_revision_id),
        ):
            if value is not None:
                _uuid(name, value)
        _sha256("plan_sha256", self.plan_sha256)
        _sha256("evidence_sha256", self.evidence_sha256)
        _aware("approved_at", self.approved_at)
        if (
            not self.setup_name
            or self.setup_name != self.setup_name.strip()
            or len(self.setup_name) > 255
        ):
            raise ValueError("setup_name must be trimmed and contain 1..255 characters")
        if self.input_mode not in {"relaxation", "dma", "dma_frequency_master_curve"}:
            raise ValueError("input_mode is unsupported")
        if (self.superseded_by_plan_id is None) != (self.superseded_by_plan_revision_id is None):
            raise ValueError("superseded successor identity and revision must be paired")
        if self.state is not PlanApprovalState.SUPERSEDED and any(
            item is not None
            for item in (self.superseded_by_plan_id, self.superseded_by_plan_revision_id)
        ):
            raise ValueError("only a superseded approval may carry a successor")

    @property
    def approval_refs(self) -> dict[str, object]:
        return {
            "review_request_id": self.review_request_id,
            "review_decision_id": self.review_decision_id,
            "evidence_sha256": self.evidence_sha256,
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "state": self.state.value,
        }

    def canonical(self) -> dict[str, object]:
        def pin(value: ExactRevisionPin | None) -> object:
            return value.canonical() if value is not None else None

        return {
            "plan_id": str(self.plan_id),
            "plan_revision_id": str(self.plan_revision_id),
            "plan_sha256": self.plan_sha256,
            "classification": self.classification.value,
            "plan_created_by": str(self.plan_created_by),
            "review_request_id": str(self.review_request_id),
            "review_decision_id": str(self.review_decision_id),
            "evidence_sha256": self.evidence_sha256,
            "approved_at": self.approved_at.isoformat(),
            "approved_by": str(self.approved_by),
            "state": self.state.value,
            "setup_name": self.setup_name,
            "material": pin(self.material),
            "material_state": pin(self.material_state),
            "test_data": pin(self.test_data),
            "processing_output": pin(self.processing_output),
            "input_mode": self.input_mode,
            "superseded_by_plan_id": (
                str(self.superseded_by_plan_id) if self.superseded_by_plan_id else None
            ),
            "superseded_by_plan_revision_id": (
                str(self.superseded_by_plan_revision_id)
                if self.superseded_by_plan_revision_id
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class PlanUsabilityFact:
    """Append-only state fact.  It never mutates the historical approval projection."""

    fact_id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    state: PlanApprovalState
    actor_id: UUID
    reason: str
    occurred_at: datetime
    organization_id: UUID | None = None
    project_id: UUID | None = None
    successor_plan_id: UUID | None = None
    successor_plan_revision_id: UUID | None = None
    request_id: UUID | None = None
    trace_id: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("fact_id", self.fact_id),
            ("plan_id", self.plan_id),
            ("plan_revision_id", self.plan_revision_id),
            ("actor_id", self.actor_id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("successor_plan_id", self.successor_plan_id),
            ("successor_plan_revision_id", self.successor_plan_revision_id),
            ("request_id", self.request_id),
        ):
            if value is not None:
                _uuid(name, value)
        if not self.reason or self.reason != self.reason.strip() or len(self.reason) > 2000:
            raise ValueError("usability reason must be trimmed and contain 1..2000 characters")
        _aware("occurred_at", self.occurred_at)
        if (self.successor_plan_id is None) != (self.successor_plan_revision_id is None):
            raise ValueError("successor identity and revision must be paired")
        if self.state is PlanApprovalState.SUPERSEDED:
            if self.successor_plan_id is None:
                raise ValueError("superseded facts require an exact successor")
        elif self.successor_plan_id is not None:
            raise ValueError("active and withdrawn facts cannot have a successor")
        if self.trace_id is not None and (
            not self.trace_id or self.trace_id != self.trace_id.strip() or len(self.trace_id) > 255
        ):
            raise ValueError("trace_id must be trimmed and contain 1..255 characters")

    def canonical(self) -> dict[str, object]:
        return {
            "fact_id": str(self.fact_id),
            "plan_id": str(self.plan_id),
            "plan_revision_id": str(self.plan_revision_id),
            "state": self.state.value,
            "actor_id": str(self.actor_id),
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
            "successor_plan_id": str(self.successor_plan_id) if self.successor_plan_id else None,
            "successor_plan_revision_id": (
                str(self.successor_plan_revision_id) if self.successor_plan_revision_id else None
            ),
        }


@dataclass(frozen=True, slots=True)
class PlanContextQuery:
    material: ExactRevisionPin
    material_state: ExactRevisionPin
    test_data: ExactRevisionPin
    processing_output: ExactRevisionPin | None
    input_mode: str

    def __post_init__(self) -> None:
        if self.input_mode not in {"relaxation", "dma", "dma_frequency_master_curve"}:
            raise ValueError("input_mode is unsupported")


@dataclass(frozen=True, slots=True)
class PlanContextResolution:
    query: PlanContextQuery
    matches: tuple[PlanApprovalRecord, ...]

    @property
    def selection_required(self) -> bool:
        return len(self.matches) != 1

    @property
    def summary(self) -> str:
        count = len(self.matches)
        suffix = "setup" if count == 1 else "setups"
        return (
            f"{count} active approved linear-viscoelastic {suffix} match the exact "
            "Material, Material State, Test Data, Processing Output, and input mode context."
        )


class LinearViscoelasticPlanApprovalPort(Protocol):
    """Application port for the Plan-specific approval read model and usability gate."""

    def get_approval(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> PlanApprovalRecord: ...

    def assert_executable(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan: LinearViscoelasticCalibrationPlan,
        classification: DataClassification,
    ) -> PlanApprovalRecord: ...

    def resolve_exact_context(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: PlanContextQuery,
    ) -> PlanContextResolution: ...

    def supersede(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
        successor_plan: LinearViscoelasticPlanSnapshotLike,
        reason: str,
    ) -> PlanUsabilityFact: ...

    def withdraw(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
        plan_created_by: UUID,
        reason: str,
    ) -> PlanUsabilityFact: ...


class LinearViscoelasticPlanSnapshotLike(Protocol):
    @property
    def id(self) -> UUID: ...

    @property
    def organization_id(self) -> UUID | None: ...

    @property
    def project_id(self) -> UUID | None: ...

    @property
    def created_by(self) -> UUID: ...

    @property
    def classification(self) -> DataClassification: ...

    @property
    def current(self) -> LinearViscoelasticCalibrationPlan: ...

    @property
    def content_hash(self) -> str: ...


def _assert_manager(
    context: SecurityContext,
    decision: AuthorizationDecision,
    *,
    creator_id: UUID,
) -> None:
    if (
        decision.permission is not Permission.REVIEW_DECIDE
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or Role.DOMAIN_REVIEWER not in decision.roles
    ):
        raise PlanGovernanceError(
            "Plan usability changes require REVIEW_DECIDE and DOMAIN_REVIEWER",
            code="PLAN_MANAGER_UNAUTHORIZED",
            recovery_hint="Use a separately authorized domain reviewer to manage Plan usability.",
        )
    if context.principal.id == creator_id:
        raise PlanGovernanceError(
            "the Plan creator cannot supersede or withdraw the same Plan",
            code="PLAN_MANAGER_UNAUTHORIZED",
            recovery_hint="Ask a different domain reviewer to manage this Plan.",
        )


def assert_distinct_plan_approver(*, plan_created_by: UUID, approved_by: UUID) -> None:
    """Reject approval of a Plan by the principal that authored it."""

    if plan_created_by == approved_by:
        raise PlanGovernanceError(
            "the Plan creator cannot approve the same Plan",
            code="PLAN_APPROVER_UNAUTHORIZED",
            recovery_hint="Ask a different domain reviewer to approve this Plan.",
        )


def _source_matches(plan: LinearViscoelasticCalibrationPlan, approval: PlanApprovalRecord) -> bool:
    return (
        _pin_equal(plan.material, approval.material)
        and _pin_equal(plan.material_state, approval.material_state)
        and _pin_equal(plan.test_data, approval.test_data)
        and _pin_equal(plan.processing_output, approval.processing_output)
        and plan.input_mode == approval.input_mode
    )


class InMemoryLinearViscoelasticPlanApproval:
    """Explicit unit/reference fixture for Plan approval and exact-context behavior."""

    def __init__(self) -> None:
        self.approvals: dict[tuple[UUID, UUID], PlanApprovalRecord] = {}
        self.usability_facts: list[PlanUsabilityFact] = []

    def seed_approved_fixture(
        self,
        plan: LinearViscoelasticPlanSnapshotLike,
        *,
        context: SecurityContext | None = None,
        review_request_id: UUID | None = None,
        review_decision_id: UUID | None = None,
        evidence_sha256: str | None = None,
        approved_at: datetime | None = None,
        approved_by: UUID | None = None,
        plan_created_by: UUID | None = None,
    ) -> PlanApprovalRecord:
        """Inject one explicitly approved fixture; never used as a production fallback."""

        if not plan.current.is_governed:
            raise PlanGovernanceError(
                "only a governed Plan can receive an approval fixture",
                code="PLAN_APPROVAL_REQUIRED",
                recovery_hint="Create a governed Plan with exact source context.",
            )
        current = plan.current
        if (
            current.material is None
            or current.material_state is None
            or current.test_data is None
            or current.input_semantics is None
        ):
            raise PlanGovernanceError(
                "governed Plan approval requires complete exact source context",
                code="PLAN_SOURCE_INCOMPATIBLE",
                recovery_hint="Create a governed Plan with complete exact source pins.",
            )
        principal = approved_by or (
            context.principal.id if context is not None else plan.created_by
        )
        record = PlanApprovalRecord(
            plan_id=plan.id,
            plan_revision_id=plan.current.plan_revision_id,
            plan_sha256=plan.content_hash,
            classification=plan.classification,
            plan_created_by=plan_created_by or plan.created_by,
            review_request_id=review_request_id or uuid4(),
            review_decision_id=review_decision_id or uuid4(),
            evidence_sha256=evidence_sha256 or plan.content_hash,
            approved_at=approved_at or datetime.now(UTC),
            approved_by=principal,
            state=PlanApprovalState.ACTIVE,
            setup_name=current.setup_name or "approved setup",
            material=current.material,
            material_state=current.material_state,
            test_data=current.test_data,
            processing_output=current.processing_output,
            input_mode=current.input_mode or current.input_semantics.mode,
            organization_id=(
                context.organization_id if context is not None else plan.organization_id
            ),
            project_id=(context.project_id if context is not None else plan.project_id),
        )
        self.approvals[(record.plan_id, record.plan_revision_id)] = record
        self.usability_facts.append(
            PlanUsabilityFact(
                fact_id=uuid4(),
                plan_id=record.plan_id,
                plan_revision_id=record.plan_revision_id,
                state=PlanApprovalState.ACTIVE,
                actor_id=record.approved_by,
                reason="review-approved",
                occurred_at=record.approved_at,
                organization_id=record.organization_id,
                project_id=record.project_id,
            )
        )
        return record

    def _latest_fact(self, plan_id: UUID, plan_revision_id: UUID) -> PlanUsabilityFact | None:
        facts = [
            item
            for item in self.usability_facts
            if item.plan_id == plan_id and item.plan_revision_id == plan_revision_id
        ]
        return facts[-1] if facts else None

    def get_approval(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> PlanApprovalRecord:
        value = self.approvals.get((plan_id, plan_revision_id))
        if value is None or (
            value.organization_id != context.organization_id
            or value.project_id != context.project_id
            or not decision.allows(
                context.organization_id,
                context.project_id,
                value.classification,
            )
        ):
            raise PlanGovernanceError(
                "no immutable approval exists for this exact Plan revision",
                code="PLAN_APPROVAL_REQUIRED",
                recovery_hint="Submit the exact Plan revision for review and wait for approval.",
            )
        fact = self._latest_fact(plan_id, plan_revision_id)
        if fact is None:
            raise PlanGovernanceError(
                "approved Plan has no usability fact",
                code="PLAN_APPROVAL_REQUIRED",
                recovery_hint="Reconcile the immutable Plan approval projection before execution.",
            )
        return self._with_state(value, fact)

    @staticmethod
    def _with_state(value: PlanApprovalRecord, fact: PlanUsabilityFact) -> PlanApprovalRecord:
        data = {field: getattr(value, field) for field in value.__dataclass_fields__}
        data.update(
            {
                "state": fact.state,
                "superseded_by_plan_id": fact.successor_plan_id,
                "superseded_by_plan_revision_id": fact.successor_plan_revision_id,
            }
        )
        return PlanApprovalRecord(**data)

    def assert_executable(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan: LinearViscoelasticCalibrationPlan,
        classification: DataClassification,
    ) -> PlanApprovalRecord:
        approval = self.get_approval(
            context=context,
            decision=decision,
            plan_id=plan.plan_id,
            plan_revision_id=plan.plan_revision_id,
        )
        if approval.state is PlanApprovalState.SUPERSEDED:
            raise PlanGovernanceError(
                "the exact Plan revision has been superseded",
                code="PLAN_APPROVAL_SUPERSEDED",
                recovery_hint="Resolve the exact context again and select its active successor.",
            )
        if approval.state is PlanApprovalState.WITHDRAWN:
            raise PlanGovernanceError(
                "the exact Plan revision has been withdrawn",
                code="PLAN_APPROVAL_WITHDRAWN",
                recovery_hint="Create or select another active approved setup.",
            )
        if (
            approval.plan_sha256 != plan.digest
            or approval.classification is not classification
            or not _source_matches(plan, approval)
        ):
            raise PlanGovernanceError(
                "approved Plan evidence does not match the exact execution source",
                code="PLAN_SOURCE_TAMPERED",
                recovery_hint="Read the immutable Plan and exact source revisions again.",
            )
        return approval

    def resolve_exact_context(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: PlanContextQuery,
    ) -> PlanContextResolution:
        matches: list[PlanApprovalRecord] = []
        for value in self.approvals.values():
            if (
                value.organization_id != context.organization_id
                or value.project_id != context.project_id
                or not decision.allows(
                    context.organization_id,
                    context.project_id,
                    value.classification,
                )
            ):
                continue
            fact = self._latest_fact(value.plan_id, value.plan_revision_id)
            if fact is None or fact.state is not PlanApprovalState.ACTIVE:
                continue
            if (
                _pin_equal(value.material, query.material)
                and _pin_equal(value.material_state, query.material_state)
                and _pin_equal(value.test_data, query.test_data)
                and _pin_equal(value.processing_output, query.processing_output)
                and value.input_mode == query.input_mode
            ):
                matches.append(self._with_state(value, fact))
        matches.sort(
            key=lambda item: (item.setup_name, str(item.plan_id), str(item.plan_revision_id))
        )
        return PlanContextResolution(query=query, matches=tuple(matches))

    def supersede(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
        successor_plan: LinearViscoelasticPlanSnapshotLike,
        reason: str,
    ) -> PlanUsabilityFact:
        old = self.get_approval(
            context=context, decision=decision, plan_id=plan_id, plan_revision_id=plan_revision_id
        )
        _assert_manager(context, decision, creator_id=old.plan_created_by)
        if old.state is not PlanApprovalState.ACTIVE:
            raise PlanGovernanceError(
                "only an active approved Plan can be superseded",
                code=(
                    "PLAN_APPROVAL_SUPERSEDED"
                    if old.state is PlanApprovalState.SUPERSEDED
                    else "PLAN_APPROVAL_WITHDRAWN"
                ),
                recovery_hint="Resolve the exact context and operate on its active setup.",
            )
        if (
            successor_plan.current.plan_id == plan_id
            and successor_plan.current.plan_revision_id == plan_revision_id
        ):
            raise PlanGovernanceError(
                "a Plan cannot supersede itself",
                code="PLAN_SOURCE_INCOMPATIBLE",
                recovery_hint="Provide a distinct active approved successor Plan.",
            )
        successor = self.assert_executable(
            context=context,
            decision=decision,
            plan=successor_plan.current,
            classification=successor_plan.classification,
        )
        now = datetime.now(UTC)
        fact = PlanUsabilityFact(
            fact_id=uuid4(),
            plan_id=plan_id,
            plan_revision_id=plan_revision_id,
            state=PlanApprovalState.SUPERSEDED,
            actor_id=context.principal.id,
            reason=reason,
            occurred_at=now,
            organization_id=context.organization_id,
            project_id=context.project_id,
            successor_plan_id=successor.plan_id,
            successor_plan_revision_id=successor.plan_revision_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        self.usability_facts.append(fact)
        return fact

    def withdraw(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
        plan_created_by: UUID,
        reason: str,
    ) -> PlanUsabilityFact:
        current = self.get_approval(
            context=context, decision=decision, plan_id=plan_id, plan_revision_id=plan_revision_id
        )
        del plan_created_by
        _assert_manager(context, decision, creator_id=current.plan_created_by)
        if current.state is not PlanApprovalState.ACTIVE:
            raise PlanGovernanceError(
                "only an active approved Plan can be withdrawn",
                code=(
                    "PLAN_APPROVAL_SUPERSEDED"
                    if current.state is PlanApprovalState.SUPERSEDED
                    else "PLAN_APPROVAL_WITHDRAWN"
                ),
                recovery_hint="Resolve the exact context and operate on its active setup.",
            )
        fact = PlanUsabilityFact(
            fact_id=uuid4(),
            plan_id=plan_id,
            plan_revision_id=plan_revision_id,
            state=PlanApprovalState.WITHDRAWN,
            actor_id=context.principal.id,
            reason=reason,
            occurred_at=datetime.now(UTC),
            organization_id=context.organization_id,
            project_id=context.project_id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        self.usability_facts.append(fact)
        return fact


def plan_context_from_values(
    *,
    material: ExactRevisionPin,
    material_state: ExactRevisionPin,
    test_data: ExactRevisionPin,
    processing_output: ExactRevisionPin | None,
    input_mode: str,
) -> PlanContextQuery:
    return PlanContextQuery(
        material=material,
        material_state=material_state,
        test_data=test_data,
        processing_output=processing_output,
        input_mode=input_mode,
    )


def canonical_diff(
    base: LinearViscoelasticCalibrationPlan,
    candidate: LinearViscoelasticCalibrationPlan,
) -> dict[str, object]:
    """Return a server-derived field diff for the numerical Plan body.

    Identity and governance metadata are intentionally excluded: an Advanced submission is a
    new Plan identity, while the diff explains only the explicit calculation changes.
    """

    excluded = {
        "plan_id",
        "plan_revision_id",
        "setup_name",
        "material",
        "material_state",
        "input_mode",
        "based_on_plan_id",
        "based_on_plan_revision_id",
        "override_reason",
        "base_diff",
    }
    before = base.canonical()
    after = candidate.canonical()
    diff: dict[str, object] = {}
    for key in sorted(set(before) | set(after)):
        if key in excluded or before.get(key) == after.get(key):
            continue
        diff[key] = {"before": before.get(key), "after": after.get(key)}
    # Force the same typed JSON validation used by the revision kernel.
    canonical_json_bytes(diff)
    return diff


__all__ = (
    "PLAN_AGGREGATE_TYPE",
    "InMemoryLinearViscoelasticPlanApproval",
    "LinearViscoelasticPlanApprovalPort",
    "PlanApprovalRecord",
    "PlanApprovalState",
    "PlanContextQuery",
    "PlanContextResolution",
    "PlanGovernanceError",
    "PlanUsabilityFact",
    "assert_distinct_plan_approver",
    "canonical_diff",
    "plan_context_from_values",
)
