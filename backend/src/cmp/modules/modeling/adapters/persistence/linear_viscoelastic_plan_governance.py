"""SQL approval projection, usability facts, and exact setup resolution for Issue #377."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.persistence.linear_viscoelastic_calibration_tables import (
    linear_viscoelastic_calibration_plan_revision_table,
    linear_viscoelastic_calibration_plan_table,
)
from cmp.modules.modeling.application.linear_viscoelastic_plan_governance import (
    PLAN_AGGREGATE_TYPE,
    LinearViscoelasticPlanApprovalPort,
    LinearViscoelasticPlanSnapshotLike,
    PlanApprovalRecord,
    PlanApprovalState,
    PlanContextQuery,
    PlanContextResolution,
    PlanGovernanceError,
    PlanUsabilityFact,
    _assert_manager,
    _pin_equal,
    assert_distinct_plan_approver,
)
from cmp.modules.review_release.domain.evidence import (
    EvidenceValidationStatus,
    ReviewEvidenceError,
    ReviewSubjectEvidence,
    SourceArtifactState,
)
from cmp.shared.domain.revisions import canonical_json_bytes

from .linear_viscoelastic_calibration_serialization import plan_from_payload


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()

plan_approval_projection_table = sa.Table(
    "linear_viscoelastic_calibration_plan_approval",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("plan_sha256", sa.CHAR(64), nullable=False),
    sa.Column("plan_created_by", sa.Uuid(), nullable=False),
    sa.Column("review_request_id", sa.Uuid(), nullable=False),
    sa.Column("review_decision_id", sa.Uuid(), nullable=False),
    sa.Column("evidence_sha256", sa.CHAR(64), nullable=False),
    sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("approved_by", sa.Uuid(), nullable=False),
    sa.Column("setup_name", sa.String(255), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_data_id", sa.Uuid(), nullable=False),
    sa.Column("test_data_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_data_sha256", sa.CHAR(64), nullable=False),
    sa.Column("processing_output_id", sa.Uuid(), nullable=True),
    sa.Column("processing_output_revision_id", sa.Uuid(), nullable=True),
    sa.Column("processing_output_sha256", sa.CHAR(64), nullable=True),
    sa.Column("input_mode", sa.String(64), nullable=False),
    schema="modeling",
)

plan_usability_fact_table = sa.Table(
    "linear_viscoelastic_calibration_plan_usability_fact",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("fact_id", sa.Uuid(), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("successor_plan_id", sa.Uuid(), nullable=True),
    sa.Column("successor_plan_revision_id", sa.Uuid(), nullable=True),
    sa.Column("actor_id", sa.Uuid(), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="modeling",
)


def _pin_from_row(row: Any, prefix: str, *, sha_column: str | None = None) -> Any:
    from cmp.modules.modeling.domain.linear_viscoelastic_calibration import ExactRevisionPin

    aggregate_id = row.get(f"{prefix}_id")
    revision_id = row.get(f"{prefix}_revision_id")
    if aggregate_id is None or revision_id is None:
        return None
    sha = row.get(sha_column) if sha_column else None
    return ExactRevisionPin(UUID(str(aggregate_id)), UUID(str(revision_id)), sha)


def _state_error(state: PlanApprovalState) -> PlanGovernanceError:
    return PlanGovernanceError(
        f"the exact Plan revision is {state.value}",
        code=f"PLAN_APPROVAL_{state.value.upper()}",
        recovery_hint=(
            "Resolve the exact context and select an active approved successor."
            if state is PlanApprovalState.SUPERSEDED
            else "Create or select another active approved setup."
        ),
    )


class SqlAlchemyLinearViscoelasticPlanApproval(LinearViscoelasticPlanApprovalPort):
    """Durable Plan-specific projection; shared review publication is never invoked here."""

    subject_type = PLAN_AGGREGATE_TYPE

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    @staticmethod
    def _plan_revision(
        session: Session,
        *,
        context: SecurityContext,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> Any | None:
        return (
            session.execute(
                sa.select(linear_viscoelastic_calibration_plan_revision_table).where(
                    linear_viscoelastic_calibration_plan_revision_table.c.organization_id
                    == context.organization_id,
                    linear_viscoelastic_calibration_plan_revision_table.c.project_id
                    == context.project_id,
                    linear_viscoelastic_calibration_plan_revision_table.c.aggregate_id == plan_id,
                    linear_viscoelastic_calibration_plan_revision_table.c.id == plan_revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _latest_fact(
        session: Session,
        *,
        context: SecurityContext,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> Any | None:
        return (
            session.execute(
                sa.select(plan_usability_fact_table)
                .where(
                    plan_usability_fact_table.c.organization_id == context.organization_id,
                    plan_usability_fact_table.c.project_id == context.project_id,
                    plan_usability_fact_table.c.plan_id == plan_id,
                    plan_usability_fact_table.c.plan_revision_id == plan_revision_id,
                )
                .order_by(
                    plan_usability_fact_table.c.occurred_at.desc(),
                    plan_usability_fact_table.c.fact_id.desc(),
                )
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _record(approval: Any, fact: Any) -> PlanApprovalRecord:
        state = PlanApprovalState(str(fact["state"]))
        return PlanApprovalRecord(
            plan_id=approval["plan_id"],
            plan_revision_id=approval["plan_revision_id"],
            plan_sha256=str(approval["plan_sha256"]),
            classification=DataClassification(str(approval["classification"])),
            plan_created_by=approval["plan_created_by"],
            review_request_id=approval["review_request_id"],
            review_decision_id=approval["review_decision_id"],
            evidence_sha256=str(approval["evidence_sha256"]),
            approved_at=approval["approved_at"],
            approved_by=approval["approved_by"],
            state=state,
            setup_name=str(approval["setup_name"]),
            material=_pin_from_row(approval, "material"),
            material_state=_pin_from_row(approval, "material_state"),
            test_data=_pin_from_row(approval, "test_data", sha_column="test_data_sha256"),
            processing_output=_pin_from_row(
                approval, "processing_output", sha_column="processing_output_sha256"
            ),
            input_mode=str(approval["input_mode"]),
            organization_id=approval["organization_id"],
            project_id=approval["project_id"],
            superseded_by_plan_id=fact.get("successor_plan_id"),
            superseded_by_plan_revision_id=fact.get("successor_plan_revision_id"),
        )

    def get_approval(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> PlanApprovalRecord:
        with self._session(context, decision) as session:
            approval = (
                session.execute(
                    sa.select(plan_approval_projection_table).where(
                        plan_approval_projection_table.c.organization_id == context.organization_id,
                        plan_approval_projection_table.c.project_id == context.project_id,
                        plan_approval_projection_table.c.plan_id == plan_id,
                        plan_approval_projection_table.c.plan_revision_id == plan_revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if approval is None:
                raise PlanGovernanceError(
                    "no immutable approval exists for this exact Plan revision",
                    code="PLAN_APPROVAL_REQUIRED",
                    recovery_hint=(
                        "Submit the exact Plan revision for review and wait for approval."
                    ),
                )
            fact = self._latest_fact(
                session,
                context=context,
                plan_id=plan_id,
                plan_revision_id=plan_revision_id,
            )
            if fact is None:
                raise PlanGovernanceError(
                    "approved Plan has no usability fact",
                    code="PLAN_APPROVAL_REQUIRED",
                    recovery_hint="Reconcile the immutable Plan approval projection.",
                )
            return self._record(approval, fact)

    def assert_executable(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan: Any,
        classification: DataClassification,
    ) -> PlanApprovalRecord:
        approval = self.get_approval(
            context=context,
            decision=decision,
            plan_id=plan.plan_id,
            plan_revision_id=plan.plan_revision_id,
        )
        if approval.state is not PlanApprovalState.ACTIVE:
            raise _state_error(approval.state)
        if (
            approval.plan_sha256 != plan.digest
            or approval.classification is not classification
            or not _pin_equal(plan.material, approval.material)
            or not _pin_equal(plan.material_state, approval.material_state)
            or not _pin_equal(plan.test_data, approval.test_data)
            or not _pin_equal(plan.processing_output, approval.processing_output)
            or plan.input_mode != approval.input_mode
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
        with self._session(context, decision) as session:
            conditions: list[sa.ColumnElement[bool]] = [
                plan_approval_projection_table.c.organization_id == context.organization_id,
                plan_approval_projection_table.c.project_id == context.project_id,
                plan_approval_projection_table.c.material_id == query.material.aggregate_id,
                plan_approval_projection_table.c.material_revision_id == query.material.revision_id,
                plan_approval_projection_table.c.material_state_id
                == query.material_state.aggregate_id,
                plan_approval_projection_table.c.material_state_revision_id
                == query.material_state.revision_id,
                plan_approval_projection_table.c.test_data_id == query.test_data.aggregate_id,
                plan_approval_projection_table.c.test_data_revision_id
                == query.test_data.revision_id,
                plan_approval_projection_table.c.input_mode == query.input_mode,
            ]
            if query.processing_output is None:
                conditions.extend(
                    (
                        plan_approval_projection_table.c.processing_output_id.is_(None),
                        plan_approval_projection_table.c.processing_output_revision_id.is_(None),
                    )
                )
            else:
                conditions.extend(
                    (
                        plan_approval_projection_table.c.processing_output_id
                        == query.processing_output.aggregate_id,
                        plan_approval_projection_table.c.processing_output_revision_id
                        == query.processing_output.revision_id,
                    )
                )
            rows = (
                session.execute(sa.select(plan_approval_projection_table).where(*conditions))
                .mappings()
                .all()
            )
            matches: list[PlanApprovalRecord] = []
            for row in rows:
                if (
                    query.test_data.sha256 is not None
                    and row["test_data_sha256"] != query.test_data.sha256
                ):
                    continue
                if (
                    query.processing_output is not None
                    and query.processing_output.sha256 is not None
                    and row["processing_output_sha256"] != query.processing_output.sha256
                ):
                    continue
                fact = self._latest_fact(
                    session,
                    context=context,
                    plan_id=row["plan_id"],
                    plan_revision_id=row["plan_revision_id"],
                )
                if fact is None or str(fact["state"]) != PlanApprovalState.ACTIVE.value:
                    continue
                matches.append(self._record(row, fact))
            matches.sort(key=lambda item: (item.setup_name, str(item.plan_id)))
            return PlanContextResolution(query=query, matches=tuple(matches))

    def project(
        self,
        *,
        session: Session,
        context: SecurityContext,
        review_request_id: UUID,
        review_decision_id: UUID | None,
        evidence: ReviewSubjectEvidence,
        approved_by: UUID,
        occurred_at: datetime,
    ) -> None:
        if review_decision_id is None:
            raise PlanGovernanceError(
                "Plan approval requires the immutable review decision reference",
                code="PLAN_APPROVAL_REQUIRED",
                recovery_hint="Retry the approval through the generic review decision service.",
            )
        row = self._plan_revision(
            session,
            context=context,
            plan_id=evidence.subject_id,
            plan_revision_id=evidence.subject_revision_id,
        )
        if row is None:
            raise PlanGovernanceError(
                "reviewed Plan revision is not visible",
                code="PLAN_SOURCE_INCOMPATIBLE",
                recovery_hint="Review the exact current Plan revision.",
            )
        assert_distinct_plan_approver(
            plan_created_by=row["created_by"],
            approved_by=approved_by,
        )
        current_revision_id = session.execute(
            sa.select(linear_viscoelastic_calibration_plan_table.c.current_revision_id).where(
                linear_viscoelastic_calibration_plan_table.c.organization_id
                == context.organization_id,
                linear_viscoelastic_calibration_plan_table.c.project_id == context.project_id,
                linear_viscoelastic_calibration_plan_table.c.classification
                == evidence.classification.value,
                linear_viscoelastic_calibration_plan_table.c.id == evidence.subject_id,
            )
        ).scalar_one_or_none()
        if current_revision_id != evidence.subject_revision_id:
            raise PlanGovernanceError(
                "reviewed Plan revision is not current",
                code="PLAN_SOURCE_STALE",
                recovery_hint="Review the exact current Plan revision before approval.",
            )
        if row["content_hash"] != evidence.server_manifest_sha256:
            raise PlanGovernanceError(
                "review evidence does not match the immutable Plan digest",
                code="PLAN_SOURCE_TAMPERED",
                recovery_hint="Resolve the Plan evidence again before approval.",
            )
        plan = plan_from_payload(cast(dict[str, object], row["plan_payload"]))
        if (
            not plan.is_governed
            or plan.setup_name is None
            or plan.material is None
            or plan.material_state is None
        ):
            raise PlanGovernanceError(
                "only a governed Plan can receive a Plan approval projection",
                code="PLAN_SOURCE_INCOMPATIBLE",
                recovery_hint="Create the Plan with exact setup and source context.",
            )
        if plan.test_data is None or plan.input_mode is None:
            raise PlanGovernanceError(
                "reviewed Plan has incomplete exact input evidence",
                code="PLAN_SOURCE_INCOMPATIBLE",
                recovery_hint="Create a new complete governed Plan revision.",
            )
        evidence_digest = hashlib.sha256(canonical_json_bytes(evidence.to_document())).hexdigest()
        approval_values = {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": evidence.classification.value,
            "plan_id": plan.plan_id,
            "plan_revision_id": plan.plan_revision_id,
            "plan_sha256": plan.digest,
            "plan_created_by": row["created_by"],
            "review_request_id": review_request_id,
            "review_decision_id": review_decision_id,
            "evidence_sha256": evidence_digest,
            "approved_at": occurred_at,
            "approved_by": approved_by,
            "setup_name": plan.setup_name,
            "material_id": plan.material.aggregate_id,
            "material_revision_id": plan.material.revision_id,
            "material_state_id": plan.material_state.aggregate_id,
            "material_state_revision_id": plan.material_state.revision_id,
            "test_data_id": plan.test_data.aggregate_id,
            "test_data_revision_id": plan.test_data.revision_id,
            "test_data_sha256": plan.test_data.sha256,
            "processing_output_id": (
                plan.processing_output.aggregate_id if plan.processing_output else None
            ),
            "processing_output_revision_id": (
                plan.processing_output.revision_id if plan.processing_output else None
            ),
            "processing_output_sha256": (
                plan.processing_output.sha256 if plan.processing_output else None
            ),
            "input_mode": plan.input_mode,
        }
        session.execute(sa.insert(plan_approval_projection_table).values(**approval_values))
        session.execute(
            sa.insert(plan_usability_fact_table).values(
                organization_id=context.organization_id,
                project_id=context.project_id,
                classification=evidence.classification.value,
                fact_id=uuid4(),
                plan_id=plan.plan_id,
                plan_revision_id=plan.plan_revision_id,
                state=PlanApprovalState.ACTIVE.value,
                successor_plan_id=None,
                successor_plan_revision_id=None,
                actor_id=approved_by,
                reason="review-approved",
                occurred_at=occurred_at,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )

    def _active_for_change(
        self,
        session: Session,
        *,
        context: SecurityContext,
        plan_id: UUID,
        plan_revision_id: UUID,
        decision: AuthorizationDecision,
    ) -> PlanApprovalRecord:
        del decision
        approval = (
            session.execute(
                sa.select(plan_approval_projection_table).where(
                    plan_approval_projection_table.c.organization_id == context.organization_id,
                    plan_approval_projection_table.c.project_id == context.project_id,
                    plan_approval_projection_table.c.plan_id == plan_id,
                    plan_approval_projection_table.c.plan_revision_id == plan_revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        fact = self._latest_fact(
            session,
            context=context,
            plan_id=plan_id,
            plan_revision_id=plan_revision_id,
        )
        if approval is None or fact is None:
            raise PlanGovernanceError(
                "no immutable approval exists for this exact Plan revision",
                code="PLAN_APPROVAL_REQUIRED",
                recovery_hint="Submit the exact Plan revision for review and wait for approval.",
            )
        value = self._record(approval, fact)
        if value.state is not PlanApprovalState.ACTIVE:
            raise _state_error(value.state)
        return value

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
        with self._session(context, decision) as session:
            old = self._active_for_change(
                session,
                context=context,
                plan_id=plan_id,
                plan_revision_id=plan_revision_id,
                decision=decision,
            )
            _assert_manager(context, decision, creator_id=old.plan_created_by)
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
            if successor.state is not PlanApprovalState.ACTIVE:
                raise _state_error(successor.state)
            fact = PlanUsabilityFact(
                fact_id=uuid4(),
                plan_id=plan_id,
                plan_revision_id=plan_revision_id,
                state=PlanApprovalState.SUPERSEDED,
                successor_plan_id=successor.plan_id,
                successor_plan_revision_id=successor.plan_revision_id,
                actor_id=context.principal.id,
                reason=reason,
                occurred_at=datetime.now(UTC),
                organization_id=context.organization_id,
                project_id=context.project_id,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
            session.execute(
                sa.insert(plan_usability_fact_table).values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=old.classification.value,
                    fact_id=fact.fact_id,
                    plan_id=fact.plan_id,
                    plan_revision_id=fact.plan_revision_id,
                    state=fact.state.value,
                    successor_plan_id=fact.successor_plan_id,
                    successor_plan_revision_id=fact.successor_plan_revision_id,
                    actor_id=fact.actor_id,
                    reason=fact.reason,
                    occurred_at=fact.occurred_at,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
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
        del plan_created_by
        with self._session(context, decision) as session:
            current = self._active_for_change(
                session,
                context=context,
                plan_id=plan_id,
                plan_revision_id=plan_revision_id,
                decision=decision,
            )
            _assert_manager(context, decision, creator_id=current.plan_created_by)
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
            session.execute(
                sa.insert(plan_usability_fact_table).values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=current.classification.value,
                    fact_id=fact.fact_id,
                    plan_id=fact.plan_id,
                    plan_revision_id=fact.plan_revision_id,
                    state=fact.state.value,
                    successor_plan_id=None,
                    successor_plan_revision_id=None,
                    actor_id=fact.actor_id,
                    reason=fact.reason,
                    occurred_at=fact.occurred_at,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            return fact

    def resolve_scoped(
        self,
        *,
        context: SecurityContext | None,
        authorization_decision: AuthorizationDecision | None,
        organization_id: UUID,
        project_id: UUID,
        subject_id: UUID,
        subject_revision_id: UUID,
        expected_manifest_sha256: str | None,
        expected_classification: DataClassification | None,
        requested_by: UUID,
        reason: str,
        occurred_at: datetime,
    ) -> ReviewSubjectEvidence:
        del requested_by, reason, occurred_at
        if context is None or authorization_decision is None:
            raise ReviewEvidenceError("review evidence resolution requires authorization scope")
        if context.organization_id != organization_id or context.project_id != project_id:
            raise ReviewEvidenceError("review evidence scope does not match the request tenant")
        with self._session(context, authorization_decision) as session:
            identity = (
                session.execute(
                    sa.select(linear_viscoelastic_calibration_plan_table).where(
                        linear_viscoelastic_calibration_plan_table.c.organization_id
                        == organization_id,
                        linear_viscoelastic_calibration_plan_table.c.project_id == project_id,
                        linear_viscoelastic_calibration_plan_table.c.id == subject_id,
                        linear_viscoelastic_calibration_plan_table.c.current_revision_id
                        == subject_revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            row = self._plan_revision(
                session,
                context=context,
                plan_id=subject_id,
                plan_revision_id=subject_revision_id,
            )
            if identity is None or row is None:
                raise ReviewEvidenceError("review Plan revision is not visible or not current")
            classification = DataClassification(str(row["classification"]))
            manifest = str(row["content_hash"])
            if (
                expected_classification is not None
                and expected_classification is not classification
            ):
                raise ReviewEvidenceError("review classification hint does not match the Plan")
            if expected_manifest_sha256 is not None and expected_manifest_sha256 != manifest:
                raise ReviewEvidenceError("review manifest hint does not match the Plan")
            plan = plan_from_payload(cast(dict[str, object], row["plan_payload"]))
            if not plan.is_governed or plan.setup_name is None:
                raise ReviewEvidenceError("linear-viscoelastic review requires a governed Plan")
            source = plan.canonical_artifact
            if (
                source is None
                or plan.material is None
                or plan.material_state is None
                or plan.test_data is None
            ):
                raise ReviewEvidenceError("governed Plan review evidence is incomplete")
            exact_input_use_items = [
                f"material:{plan.material.aggregate_id}@{plan.material.revision_id}",
                f"material_state:{plan.material_state.aggregate_id}@{plan.material_state.revision_id}",
                f"test_data:{plan.test_data.aggregate_id}@{plan.test_data.revision_id}",
                f"input_mode:{plan.input_mode}",
            ]
            if plan.processing_output is not None:
                exact_input_use_items.append(
                    "processing_output:"
                    f"{plan.processing_output.aggregate_id}@{plan.processing_output.revision_id}"
                )
            return ReviewSubjectEvidence(
                subject_type=PLAN_AGGREGATE_TYPE,
                subject_id=subject_id,
                subject_revision_id=subject_revision_id,
                label=plan.setup_name,
                classification=classification,
                schema_ref=plan.schema_id,
                schema_version=plan.schema_version,
                server_manifest_sha256=manifest,
                source_artifact_state=SourceArtifactState.ATTACHED,
                source_artifact_id=source.artifact_id,
                source_artifact_sha256=source.sha256,
                validation_status=EvidenceValidationStatus.VALID,
                validation_summary=(
                    "Exact governed linear-viscoelastic setup with server-resolved source pins."
                ),
                created_by=row["created_by"],
                created_at=row["created_at"],
                change_reason=str(row["change_reason"]),
                exact_input_use=tuple(exact_input_use_items),
                affected_record_id=None,
                affected_record_revision_id=None,
            )


SqlAlchemyLinearViscoelasticPlanApprovalProjector = SqlAlchemyLinearViscoelasticPlanApproval

__all__ = (
    "SqlAlchemyLinearViscoelasticPlanApproval",
    "SqlAlchemyLinearViscoelasticPlanApprovalProjector",
    "plan_approval_projection_table",
    "plan_usability_fact_table",
)
