"""RLS-bound PostgreSQL repository for multi-replicate outlier review."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.statistics.application.replicate_outlier_service import (
    CALIBRATION_INPUT_SCOPE_AGGREGATE_TYPE,
    OUTLIER_ASSESSMENT_AGGREGATE_TYPE,
    OUTLIER_PLAN_AGGREGATE_TYPE,
    CalibrationInputScopeSnapshot,
    ReplicateOutlierAssessmentSnapshot,
    ReplicateOutlierDetectionRun,
    ReplicateOutlierPlanSnapshot,
    ReplicateOutlierRepository,
)
from cmp.modules.statistics.application.replicate_service import ReplicateRevisionSnapshot
from cmp.modules.statistics.domain.reference_tensile_pair import (
    StatisticsConflict,
    StatisticsNotFound,
)
from cmp.modules.statistics.domain.reference_tensile_replicate_outlier import (
    REFERENCE_CALIBRATION_SCOPE_KIND,
    REFERENCE_REPLICATE_OUTLIER_DETECTOR,
    REFERENCE_REPLICATE_OUTLIER_FEATURE,
    REFERENCE_REPLICATE_OUTLIER_FORMULA_VERSION,
    REFERENCE_REPLICATE_OUTLIER_PLAN_KIND,
    CalibrationInputScopeMember,
    CalibrationScopeDisposition,
    ReferenceCalibrationInputScopeContent,
    ReferenceReplicateOutlierAssessmentContent,
    ReferenceReplicateOutlierCandidate,
    ReferenceReplicateOutlierPlanContent,
    ReplicateOutlierAssessmentDecision,
    ReplicateOutlierEvidenceCode,
    ReplicateOutlierMemberEvidence,
    reference_calibration_input_scope_canonical,
    reference_replicate_outlier_assessment_canonical,
    reference_replicate_outlier_plan_canonical,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionRecord, TenantScope


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()


def _identity(name: str, *columns: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *columns,
        schema="statistics",
    )


def _revision(name: str, *columns: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.BigInteger(), nullable=False),
        sa.Column("based_on_revision_id", sa.Uuid(), nullable=True),
        sa.Column("schema_id", sa.String(255), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.CHAR(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        *columns,
        schema="statistics",
    )


plan_table = _identity(
    "replicate_outlier_detection_plan",
    sa.Column("plan_label", sa.String(160), nullable=False),
    sa.Column("plan_kind", sa.String(100), nullable=False),
)
plan_revision_table = _revision(
    "replicate_outlier_detection_plan_revision",
    sa.Column("plan_kind", sa.String(100), nullable=False),
    sa.Column("statistical_result_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_result_revision_id", sa.Uuid(), nullable=False),
    sa.Column("detector", sa.String(100), nullable=False),
    sa.Column("formula_version", sa.String(64), nullable=False),
    sa.Column("feature", sa.String(100), nullable=False),
    sa.Column("absolute_modified_z_threshold", sa.Double(), nullable=False),
    sa.Column("automatic_exclusion", sa.Boolean(), nullable=False),
)
assessment_table = _identity(
    "replicate_outlier_assessment",
    sa.Column("candidate_id", sa.Uuid(), nullable=False),
)
assessment_revision_table = _revision(
    "replicate_outlier_assessment_revision",
    sa.Column("candidate_id", sa.Uuid(), nullable=False),
    sa.Column("detection_plan_id", sa.Uuid(), nullable=False),
    sa.Column("detection_plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("decision", sa.String(40), nullable=False),
    sa.Column("assessment_reason", sa.Text(), nullable=False),
    sa.Column("automatic_exclusion", sa.Boolean(), nullable=False),
)
scope_table = _identity(
    "calibration_input_scope",
    sa.Column("scope_label", sa.String(160), nullable=False),
    sa.Column("scope_kind", sa.String(100), nullable=False),
)
scope_revision_table = _revision(
    "calibration_input_scope_revision",
    sa.Column("scope_kind", sa.String(100), nullable=False),
    sa.Column("source_selection_id", sa.Uuid(), nullable=False),
    sa.Column("source_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_result_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_result_revision_id", sa.Uuid(), nullable=False),
    sa.Column("detection_plan_id", sa.Uuid(), nullable=False),
    sa.Column("detection_plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("source_member_count", sa.SmallInteger(), nullable=False),
    sa.Column("included_member_count", sa.SmallInteger(), nullable=False),
    sa.Column("excluded_member_count", sa.SmallInteger(), nullable=False),
)
scope_member_table = sa.Table(
    "calibration_input_scope_member",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("scope_id", sa.Uuid(), nullable=False),
    sa.Column("scope_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("disposition", sa.String(16), nullable=False),
    sa.Column("candidate_id", sa.Uuid(), nullable=True),
    sa.Column("assessment_id", sa.Uuid(), nullable=True),
    sa.Column("assessment_revision_id", sa.Uuid(), nullable=True),
    schema="statistics",
)
detection_run_table = sa.Table(
    "replicate_outlier_detection_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("detection_plan_id", sa.Uuid(), nullable=False),
    sa.Column("detection_plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_result_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_result_revision_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_plan_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("sample_count", sa.SmallInteger(), nullable=False),
    sa.Column("sample_median_peak_stress_pa", sa.Double(), nullable=False),
    sa.Column("sample_mad_peak_stress_pa", sa.Double(), nullable=False),
    sa.Column("candidate_count", sa.SmallInteger(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="statistics",
)
candidate_table = sa.Table(
    "replicate_outlier_candidate",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("detection_run_id", sa.Uuid(), nullable=False),
    sa.Column("detection_plan_id", sa.Uuid(), nullable=False),
    sa.Column("detection_plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_result_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_result_revision_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_plan_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("peak_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("sample_count", sa.SmallInteger(), nullable=False),
    sa.Column("sample_median_peak_stress_pa", sa.Double(), nullable=False),
    sa.Column("sample_mad_peak_stress_pa", sa.Double(), nullable=False),
    sa.Column("absolute_modified_z_score", sa.Double(), nullable=True),
    sa.Column("threshold", sa.Double(), nullable=False),
    sa.Column("evidence_code", sa.String(64), nullable=False),
    schema="statistics",
)


def _plan_values(value: ReferenceReplicateOutlierPlanContent) -> dict[str, object]:
    return {
        "plan_kind": REFERENCE_REPLICATE_OUTLIER_PLAN_KIND,
        "statistical_result_id": value.statistical_result_id,
        "statistical_result_revision_id": value.statistical_result_revision_id,
        "detector": REFERENCE_REPLICATE_OUTLIER_DETECTOR,
        "formula_version": REFERENCE_REPLICATE_OUTLIER_FORMULA_VERSION,
        "feature": REFERENCE_REPLICATE_OUTLIER_FEATURE,
        "absolute_modified_z_threshold": value.absolute_modified_z_threshold,
        "automatic_exclusion": False,
    }


def _assessment_values(
    value: ReferenceReplicateOutlierAssessmentContent,
) -> dict[str, object]:
    return {
        "candidate_id": value.candidate_id,
        "detection_plan_id": value.detection_plan_id,
        "detection_plan_revision_id": value.detection_plan_revision_id,
        "decision": value.decision.value,
        "assessment_reason": value.assessment_reason,
        "automatic_exclusion": False,
    }


def _scope_values(value: ReferenceCalibrationInputScopeContent) -> dict[str, object]:
    return {
        "scope_kind": REFERENCE_CALIBRATION_SCOPE_KIND,
        "source_selection_id": value.source_selection_id,
        "source_selection_revision_id": value.source_selection_revision_id,
        "statistical_result_id": value.statistical_result_id,
        "statistical_result_revision_id": value.statistical_result_revision_id,
        "detection_plan_id": value.detection_plan_id,
        "detection_plan_revision_id": value.detection_plan_revision_id,
        "source_member_count": len(value.members),
        "included_member_count": sum(
            member.disposition is CalibrationScopeDisposition.INCLUDED
            for member in value.members
        ),
        "excluded_member_count": sum(
            member.disposition is CalibrationScopeDisposition.EXCLUDED
            for member in value.members
        ),
    }


def _write_scope_members(session: Session, draft: Any) -> None:
    content = cast(ReferenceCalibrationInputScopeContent, draft.content)
    session.execute(
        scope_member_table.insert(),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "scope_id": draft.aggregate_id,
                "scope_revision_id": draft.revision_id,
                "ordinal": member.ordinal,
                "dataset_id": member.dataset_id,
                "dataset_revision_id": member.dataset_revision_id,
                "test_run_id": member.test_run_id,
                "test_run_revision_id": member.test_run_revision_id,
                "disposition": member.disposition.value,
                "candidate_id": member.candidate_id,
                "assessment_id": member.assessment_id,
                "assessment_revision_id": member.assessment_revision_id,
            }
            for member in content.members
        ],
    )


_PLAN_TABLES = TypedRevisionTables(
    aggregate_type=OUTLIER_PLAN_AGGREGATE_TYPE,
    identity_table=plan_table,
    revision_table=plan_revision_table,
    canonical_content=reference_replicate_outlier_plan_canonical,
    content_values=_plan_values,
    identity_values=lambda value: {
        "plan_label": value.plan_label,
        "plan_kind": REFERENCE_REPLICATE_OUTLIER_PLAN_KIND,
    },
)
_ASSESSMENT_TABLES = TypedRevisionTables(
    aggregate_type=OUTLIER_ASSESSMENT_AGGREGATE_TYPE,
    identity_table=assessment_table,
    revision_table=assessment_revision_table,
    canonical_content=reference_replicate_outlier_assessment_canonical,
    content_values=_assessment_values,
    identity_values=lambda value: {"candidate_id": value.candidate_id},
)
_SCOPE_TABLES = TypedRevisionTables(
    aggregate_type=CALIBRATION_INPUT_SCOPE_AGGREGATE_TYPE,
    identity_table=scope_table,
    revision_table=scope_revision_table,
    canonical_content=reference_calibration_input_scope_canonical,
    content_values=_scope_values,
    identity_values=lambda value: {
        "scope_label": value.scope_label,
        "scope_kind": REFERENCE_CALIBRATION_SCOPE_KIND,
    },
    revision_content_writer=_write_scope_members,
)


def _record(row: Any, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=aggregate_type,
        aggregate_id=cast(UUID, row["aggregate_id"]),
        scope=TenantScope(
            cast(UUID, row["organization_id"]),
            cast(UUID, row["project_id"]),
            str(row["classification"]),
        ),
        revision_no=int(row["revision_no"]),
        based_on_revision_id=cast(UUID | None, row["based_on_revision_id"]),
        schema_id=str(row["schema_id"]),
        schema_version=str(row["schema_version"]),
        content_hash=str(row["content_hash"]),
        created_at=row["created_at"],
        created_by=cast(UUID, row["created_by"]),
        change_reason=str(row["change_reason"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _revision_columns(table: sa.Table) -> tuple[Any, ...]:
    return tuple(
        table.c[name].label(name)
        for name in (
            "id",
            "aggregate_id",
            "organization_id",
            "project_id",
            "classification",
            "revision_no",
            "based_on_revision_id",
            "schema_id",
            "schema_version",
            "content_hash",
            "created_at",
            "created_by",
            "change_reason",
            "request_id",
            "trace_id",
        )
    )


def _plan_content(row: Any) -> ReferenceReplicateOutlierPlanContent:
    if (
        str(row["plan_kind"]) != REFERENCE_REPLICATE_OUTLIER_PLAN_KIND
        or str(row["detector"]) != REFERENCE_REPLICATE_OUTLIER_DETECTOR
        or str(row["formula_version"]) != REFERENCE_REPLICATE_OUTLIER_FORMULA_VERSION
        or str(row["feature"]) != REFERENCE_REPLICATE_OUTLIER_FEATURE
        or bool(row["automatic_exclusion"])
    ):
        raise StatisticsConflict("outlier Plan violates its typed contract")
    return ReferenceReplicateOutlierPlanContent(
        plan_label=str(row["plan_label"]),
        statistical_result_id=cast(UUID, row["statistical_result_id"]),
        statistical_result_revision_id=cast(UUID, row["statistical_result_revision_id"]),
        absolute_modified_z_threshold=float(row["absolute_modified_z_threshold"]),
    )


def _assessment_content(row: Any) -> ReferenceReplicateOutlierAssessmentContent:
    if bool(row["automatic_exclusion"]):
        raise StatisticsConflict("outlier Assessment cannot be automatic")
    return ReferenceReplicateOutlierAssessmentContent(
        candidate_id=cast(UUID, row["candidate_id"]),
        detection_plan_id=cast(UUID, row["detection_plan_id"]),
        detection_plan_revision_id=cast(UUID, row["detection_plan_revision_id"]),
        decision=ReplicateOutlierAssessmentDecision(str(row["decision"])),
        assessment_reason=str(row["assessment_reason"]),
    )


def _scope_member(row: Any) -> CalibrationInputScopeMember:
    return CalibrationInputScopeMember(
        ordinal=int(row["ordinal"]),
        dataset_id=cast(UUID, row["dataset_id"]),
        dataset_revision_id=cast(UUID, row["dataset_revision_id"]),
        test_run_id=cast(UUID, row["test_run_id"]),
        test_run_revision_id=cast(UUID, row["test_run_revision_id"]),
        disposition=CalibrationScopeDisposition(str(row["disposition"])),
        candidate_id=cast(UUID | None, row["candidate_id"]),
        assessment_id=cast(UUID | None, row["assessment_id"]),
        assessment_revision_id=cast(UUID | None, row["assessment_revision_id"]),
    )


def _candidate(row: Any) -> ReferenceReplicateOutlierCandidate:
    return ReferenceReplicateOutlierCandidate(
        id=cast(UUID, row["id"]),
        detection_run_id=cast(UUID, row["detection_run_id"]),
        detection_plan_id=cast(UUID, row["detection_plan_id"]),
        detection_plan_revision_id=cast(UUID, row["detection_plan_revision_id"]),
        statistical_result_id=cast(UUID, row["statistical_result_id"]),
        statistical_result_revision_id=cast(UUID, row["statistical_result_revision_id"]),
        statistical_plan_id=cast(UUID, row["statistical_plan_id"]),
        statistical_plan_revision_id=cast(UUID, row["statistical_plan_revision_id"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        member=ReplicateOutlierMemberEvidence(
            ordinal=int(row["ordinal"]),
            dataset_id=cast(UUID, row["dataset_id"]),
            dataset_revision_id=cast(UUID, row["dataset_revision_id"]),
            test_run_id=cast(UUID, row["test_run_id"]),
            test_run_revision_id=cast(UUID, row["test_run_revision_id"]),
            peak_engineering_stress_pa=float(row["peak_engineering_stress_pa"]),
        ),
        sample_count=int(row["sample_count"]),
        sample_median_peak_stress_pa=float(row["sample_median_peak_stress_pa"]),
        sample_mad_peak_stress_pa=float(row["sample_mad_peak_stress_pa"]),
        absolute_modified_z_score=(
            float(row["absolute_modified_z_score"])
            if row["absolute_modified_z_score"] is not None
            else None
        ),
        threshold=float(row["threshold"]),
        evidence_code=ReplicateOutlierEvidenceCode(str(row["evidence_code"])),
    )


class SqlAlchemyReplicateOutlierRepository(ReplicateOutlierRepository):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        revision_hooks: tuple[SqlRevisionHook, ...] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = revision_hooks

    def _bind(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceReplicateOutlierPlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_PLAN_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def assessment_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceReplicateOutlierAssessmentContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_ASSESSMENT_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def scope_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceCalibrationInputScopeContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_SCOPE_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _plan_statement() -> sa.Select[Any]:
        revision = plan_revision_table
        return sa.select(
            plan_table.c.id.label("identity_id"),
            plan_table.c.plan_label,
            *_revision_columns(revision),
            revision.c.plan_kind,
            revision.c.statistical_result_id,
            revision.c.statistical_result_revision_id,
            revision.c.detector,
            revision.c.formula_version,
            revision.c.feature,
            revision.c.absolute_modified_z_threshold,
            revision.c.automatic_exclusion,
        ).select_from(
            plan_table.join(
                revision,
                sa.and_(
                    revision.c.aggregate_id == plan_table.c.id,
                    revision.c.organization_id == plan_table.c.organization_id,
                    revision.c.project_id == plan_table.c.project_id,
                ),
            )
        )

    @staticmethod
    def _plan_snapshot(row: Any) -> ReplicateOutlierPlanSnapshot:
        return ReplicateOutlierPlanSnapshot(
            cast(UUID, row["identity_id"]),
            ReplicateRevisionSnapshot(
                _record(row, OUTLIER_PLAN_AGGREGATE_TYPE), _plan_content(row)
            ),
        )

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> ReplicateRevisionSnapshot[ReferenceReplicateOutlierPlanContent]:
        statement = self._plan_statement().where(
            plan_table.c.organization_id == context.organization_id,
            plan_table.c.project_id == context.project_id,
            plan_table.c.id == plan_id,
            plan_revision_table.c.id == plan_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("outlier Plan revision is not visible")
        return ReplicateRevisionSnapshot(
            _record(row, OUTLIER_PLAN_AGGREGATE_TYPE), _plan_content(row)
        )

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        statistical_result_revision_id: UUID,
    ) -> tuple[ReplicateOutlierPlanSnapshot, ...]:
        statement = (
            self._plan_statement()
            .where(
                plan_table.c.organization_id == context.organization_id,
                plan_table.c.project_id == context.project_id,
                plan_revision_table.c.id == plan_table.c.current_revision_id,
                plan_revision_table.c.statistical_result_revision_id
                == statistical_result_revision_id,
            )
            .order_by(plan_table.c.created_at.desc())
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._plan_snapshot(row) for row in rows)

    def create_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ReplicateOutlierDetectionRun,
    ) -> ReplicateOutlierDetectionRun:
        values = {
            key: getattr(run, key)
            for key in (
                "id",
                "detection_plan_id",
                "detection_plan_revision_id",
                "statistical_result_id",
                "statistical_result_revision_id",
                "statistical_plan_id",
                "statistical_plan_revision_id",
                "selection_id",
                "selection_revision_id",
                "sample_count",
                "sample_median_peak_stress_pa",
                "sample_mad_peak_stress_pa",
                "candidate_count",
                "started_at",
                "ended_at",
                "created_by",
                "request_id",
                "trace_id",
            )
        }
        values.update(
            organization_id=context.organization_id,
            project_id=context.project_id,
            classification=run.classification.value,
        )
        candidate_values = []
        for candidate in run.candidates:
            candidate_values.append(
                {
                    "id": candidate.id,
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                    "classification": run.classification.value,
                    "detection_run_id": candidate.detection_run_id,
                    "detection_plan_id": candidate.detection_plan_id,
                    "detection_plan_revision_id": candidate.detection_plan_revision_id,
                    "statistical_result_id": candidate.statistical_result_id,
                    "statistical_result_revision_id": candidate.statistical_result_revision_id,
                    "statistical_plan_id": candidate.statistical_plan_id,
                    "statistical_plan_revision_id": candidate.statistical_plan_revision_id,
                    "selection_id": candidate.selection_id,
                    "selection_revision_id": candidate.selection_revision_id,
                    "ordinal": candidate.member.ordinal,
                    "dataset_id": candidate.member.dataset_id,
                    "dataset_revision_id": candidate.member.dataset_revision_id,
                    "test_run_id": candidate.member.test_run_id,
                    "test_run_revision_id": candidate.member.test_run_revision_id,
                    "peak_engineering_stress_pa": candidate.member.peak_engineering_stress_pa,
                    "sample_count": candidate.sample_count,
                    "sample_median_peak_stress_pa": candidate.sample_median_peak_stress_pa,
                    "sample_mad_peak_stress_pa": candidate.sample_mad_peak_stress_pa,
                    "absolute_modified_z_score": candidate.absolute_modified_z_score,
                    "threshold": candidate.threshold,
                    "evidence_code": candidate.evidence_code.value,
                }
            )
        try:
            with self._session(context, decision) as session:
                session.execute(detection_run_table.insert().values(values))
                if candidate_values:
                    session.execute(candidate_table.insert(), candidate_values)
        except (IntegrityError, DBAPIError) as error:
            raise StatisticsConflict("outlier Detection Run conflicts with pinned data") from error
        return run

    def get_detection_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ReplicateOutlierDetectionRun:
        statement = sa.select(detection_run_table).where(
            detection_run_table.c.organization_id == context.organization_id,
            detection_run_table.c.project_id == context.project_id,
            detection_run_table.c.id == run_id,
        )
        candidates_statement = (
            sa.select(candidate_table)
            .where(
                candidate_table.c.organization_id == context.organization_id,
                candidate_table.c.project_id == context.project_id,
                candidate_table.c.detection_run_id == run_id,
            )
            .order_by(candidate_table.c.ordinal)
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            candidate_rows = session.execute(candidates_statement).mappings().all()
        if row is None:
            raise StatisticsNotFound("outlier Detection Run is not visible")
        return ReplicateOutlierDetectionRun(
            id=cast(UUID, row["id"]),
            classification=DataClassification(str(row["classification"])),
            detection_plan_id=cast(UUID, row["detection_plan_id"]),
            detection_plan_revision_id=cast(UUID, row["detection_plan_revision_id"]),
            statistical_result_id=cast(UUID, row["statistical_result_id"]),
            statistical_result_revision_id=cast(UUID, row["statistical_result_revision_id"]),
            statistical_plan_id=cast(UUID, row["statistical_plan_id"]),
            statistical_plan_revision_id=cast(UUID, row["statistical_plan_revision_id"]),
            selection_id=cast(UUID, row["selection_id"]),
            selection_revision_id=cast(UUID, row["selection_revision_id"]),
            sample_count=int(row["sample_count"]),
            sample_median_peak_stress_pa=float(row["sample_median_peak_stress_pa"]),
            sample_mad_peak_stress_pa=float(row["sample_mad_peak_stress_pa"]),
            candidate_count=int(row["candidate_count"]),
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            created_by=cast(UUID, row["created_by"]),
            request_id=cast(UUID, row["request_id"]),
            trace_id=str(row["trace_id"]),
            candidates=tuple(_candidate(item) for item in candidate_rows),
        )

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> ReferenceReplicateOutlierCandidate:
        statement = sa.select(candidate_table).where(
            candidate_table.c.organization_id == context.organization_id,
            candidate_table.c.project_id == context.project_id,
            candidate_table.c.id == candidate_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("outlier Candidate is not visible")
        return _candidate(row)

    @staticmethod
    def _assessment_statement() -> sa.Select[Any]:
        revision = assessment_revision_table
        return sa.select(
            assessment_table.c.id.label("identity_id"),
            *_revision_columns(revision),
            revision.c.candidate_id,
            revision.c.detection_plan_id,
            revision.c.detection_plan_revision_id,
            revision.c.decision,
            revision.c.assessment_reason,
            revision.c.automatic_exclusion,
        ).select_from(
            assessment_table.join(
                revision,
                sa.and_(
                    revision.c.aggregate_id == assessment_table.c.id,
                    revision.c.organization_id == assessment_table.c.organization_id,
                    revision.c.project_id == assessment_table.c.project_id,
                ),
            )
        )

    @staticmethod
    def _assessment_snapshot(row: Any) -> ReplicateOutlierAssessmentSnapshot:
        return ReplicateOutlierAssessmentSnapshot(
            cast(UUID, row["identity_id"]),
            ReplicateRevisionSnapshot(
                _record(row, OUTLIER_ASSESSMENT_AGGREGATE_TYPE),
                _assessment_content(row),
            ),
        )

    def get_assessment_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assessment_revision_id: UUID,
    ) -> ReplicateOutlierAssessmentSnapshot:
        statement = self._assessment_statement().where(
            assessment_revision_table.c.organization_id == context.organization_id,
            assessment_revision_table.c.project_id == context.project_id,
            assessment_revision_table.c.id == assessment_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("outlier Assessment revision is not visible")
        return self._assessment_snapshot(row)

    def list_assessments(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> tuple[ReplicateOutlierAssessmentSnapshot, ...]:
        statement = (
            self._assessment_statement()
            .where(
                assessment_revision_table.c.organization_id == context.organization_id,
                assessment_revision_table.c.project_id == context.project_id,
                assessment_revision_table.c.id == assessment_table.c.current_revision_id,
                assessment_revision_table.c.candidate_id == candidate_id,
            )
            .order_by(assessment_table.c.created_at.desc())
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._assessment_snapshot(row) for row in rows)

    @staticmethod
    def _scope_statement(*, current_only: bool = True) -> sa.Select[Any]:
        revision = scope_revision_table
        join_predicates = [
            revision.c.aggregate_id == scope_table.c.id,
            revision.c.organization_id == scope_table.c.organization_id,
            revision.c.project_id == scope_table.c.project_id,
        ]
        if current_only:
            join_predicates.append(revision.c.id == scope_table.c.current_revision_id)
        return sa.select(
            scope_table.c.id.label("identity_id"),
            scope_table.c.scope_label,
            *_revision_columns(revision),
            revision.c.scope_kind,
            revision.c.source_selection_id,
            revision.c.source_selection_revision_id,
            revision.c.statistical_result_id,
            revision.c.statistical_result_revision_id,
            revision.c.detection_plan_id,
            revision.c.detection_plan_revision_id,
            revision.c.source_member_count,
            revision.c.included_member_count,
            revision.c.excluded_member_count,
        ).select_from(
            scope_table.join(
                revision,
                sa.and_(*join_predicates),
            )
        )

    def _scope_snapshot(
        self, row: Any, members: tuple[CalibrationInputScopeMember, ...]
    ) -> CalibrationInputScopeSnapshot:
        if (
            str(row["scope_kind"]) != REFERENCE_CALIBRATION_SCOPE_KIND
            or int(row["source_member_count"]) != len(members)
        ):
            raise StatisticsConflict("calibration Scope violates its typed contract")
        content = ReferenceCalibrationInputScopeContent(
            scope_label=str(row["scope_label"]),
            source_selection_id=cast(UUID, row["source_selection_id"]),
            source_selection_revision_id=cast(UUID, row["source_selection_revision_id"]),
            statistical_result_id=cast(UUID, row["statistical_result_id"]),
            statistical_result_revision_id=cast(UUID, row["statistical_result_revision_id"]),
            detection_plan_id=cast(UUID, row["detection_plan_id"]),
            detection_plan_revision_id=cast(UUID, row["detection_plan_revision_id"]),
            members=members,
        )
        return CalibrationInputScopeSnapshot(
            cast(UUID, row["identity_id"]),
            ReplicateRevisionSnapshot(
                _record(row, CALIBRATION_INPUT_SCOPE_AGGREGATE_TYPE), content
            ),
        )

    def get_scope(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        scope_id: UUID,
    ) -> CalibrationInputScopeSnapshot:
        statement = self._scope_statement().where(
            scope_table.c.organization_id == context.organization_id,
            scope_table.c.project_id == context.project_id,
            scope_table.c.id == scope_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise StatisticsNotFound("calibration input Scope is not visible")
            member_rows = session.execute(
                sa.select(scope_member_table)
                .where(
                    scope_member_table.c.organization_id == context.organization_id,
                    scope_member_table.c.project_id == context.project_id,
                    scope_member_table.c.scope_revision_id == row["id"],
                )
                .order_by(scope_member_table.c.ordinal)
            ).mappings().all()
        return self._scope_snapshot(row, tuple(_scope_member(item) for item in member_rows))

    def get_scope_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        scope_id: UUID,
        scope_revision_id: UUID,
    ) -> CalibrationInputScopeSnapshot:
        statement = self._scope_statement(current_only=False).where(
            scope_table.c.organization_id == context.organization_id,
            scope_table.c.project_id == context.project_id,
            scope_table.c.id == scope_id,
            scope_revision_table.c.id == scope_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise StatisticsNotFound("calibration input Scope revision is not visible")
            member_rows = session.execute(
                sa.select(scope_member_table)
                .where(
                    scope_member_table.c.organization_id == context.organization_id,
                    scope_member_table.c.project_id == context.project_id,
                    scope_member_table.c.scope_revision_id == scope_revision_id,
                )
                .order_by(scope_member_table.c.ordinal)
            ).mappings().all()
        return self._scope_snapshot(row, tuple(_scope_member(item) for item in member_rows))

    def list_scopes(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        statistical_result_revision_id: UUID,
    ) -> tuple[CalibrationInputScopeSnapshot, ...]:
        statement = (
            self._scope_statement()
            .where(
                scope_table.c.organization_id == context.organization_id,
                scope_table.c.project_id == context.project_id,
                scope_revision_table.c.statistical_result_revision_id
                == statistical_result_revision_id,
            )
            .order_by(scope_table.c.created_at.desc())
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
            snapshots = []
            for row in rows:
                member_rows = session.execute(
                    sa.select(scope_member_table)
                    .where(
                        scope_member_table.c.organization_id == context.organization_id,
                        scope_member_table.c.project_id == context.project_id,
                        scope_member_table.c.scope_revision_id == row["id"],
                    )
                    .order_by(scope_member_table.c.ordinal)
                ).mappings().all()
                snapshots.append(
                    self._scope_snapshot(
                        row, tuple(_scope_member(item) for item in member_rows)
                    )
                )
        return tuple(snapshots)
