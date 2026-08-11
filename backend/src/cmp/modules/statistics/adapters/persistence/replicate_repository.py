"""RLS-bound PostgreSQL repository for multi-replicate Statistics/QC."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
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
from cmp.modules.statistics.application.replicate_service import (
    REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
    REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE,
    ReplicateRevisionSnapshot,
    ReplicateStatisticalPlanSnapshot,
    ReplicateStatisticalResultSnapshot,
    ReplicateStatisticalRun,
    ReplicateStatisticalRunMember,
    ReplicateStatisticsRepository,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    QcObservation,
    QcOutcome,
    StatisticalRunStatus,
    StatisticsConflict,
    StatisticsNotFound,
)
from cmp.modules.statistics.domain.reference_tensile_replicates import (
    REFERENCE_TENSILE_REPLICATE_CI_METHOD,
    REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMAS,
    REFERENCE_TENSILE_REPLICATE_GRID_POLICY,
    REFERENCE_TENSILE_REPLICATE_PLAN_KIND,
    REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD,
    REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE,
    ReferenceTensileReplicatePlanContent,
    ReferenceTensileReplicateResultContent,
    ReplicateScalarStatistics,
    reference_tensile_replicate_plan_canonical,
    reference_tensile_replicate_result_canonical,
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


def _identity_table(name: str, *columns: sa.Column[Any]) -> sa.Table:
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


def _revision_table(name: str, *columns: sa.Column[Any]) -> sa.Table:
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


plan_table = _identity_table(
    "replicate_statistical_plan",
    sa.Column("plan_label", sa.String(160), nullable=False),
    sa.Column("plan_kind", sa.String(100), nullable=False),
)
plan_revision_table = _revision_table(
    "replicate_statistical_plan_revision",
    sa.Column("plan_kind", sa.String(100), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("sample_count", sa.SmallInteger(), nullable=False),
    sa.Column("required_input_representation", sa.String(32), nullable=False),
    sa.Column("scalar_feature", sa.String(100), nullable=False),
    sa.Column("curve_grid_policy", sa.String(100), nullable=False),
    sa.Column("quantile_method", sa.String(100), nullable=False),
    sa.Column("confidence_interval_method", sa.String(100), nullable=False),
    sa.Column("curve_output_schema_ref", sa.String(500), nullable=False),
)
result_table = _identity_table(
    "replicate_statistical_result",
    sa.Column("statistical_run_id", sa.Uuid(), nullable=False),
    sa.Column("result_kind", sa.String(100), nullable=False),
)
result_revision_table = _revision_table(
    "replicate_statistical_result_revision",
    sa.Column("result_kind", sa.String(100), nullable=False),
    sa.Column("statistical_run_id", sa.Uuid(), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("sample_count", sa.SmallInteger(), nullable=False),
    sa.Column("scalar_feature", sa.String(100), nullable=False),
    sa.Column("curve_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("curve_sha256", sa.CHAR(64), nullable=False),
    sa.Column("curve_point_count", sa.BigInteger(), nullable=False),
    sa.Column("mean_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("sample_standard_deviation_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("median_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("median_absolute_deviation_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("interquartile_range_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("minimum_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("maximum_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("coefficient_of_variation", sa.Double(), nullable=True),
    sa.Column("mean_confidence_interval_lower_95_pa", sa.Double(), nullable=False),
    sa.Column("mean_confidence_interval_upper_95_pa", sa.Double(), nullable=False),
    sa.Column("curve_grid_policy", sa.String(100), nullable=False),
    sa.Column("quantile_method", sa.String(100), nullable=False),
    sa.Column("confidence_interval_method", sa.String(100), nullable=False),
)
run_table = sa.Table(
    "replicate_statistical_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("execution_mode", sa.String(16), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("sample_count", sa.SmallInteger(), nullable=False),
    sa.Column("result_id", sa.Uuid(), nullable=True),
    sa.Column("result_revision_id", sa.Uuid(), nullable=True),
    sa.Column("curve_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("curve_sha256", sa.CHAR(64), nullable=True),
    sa.Column("curve_point_count", sa.BigInteger(), nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("change_reason", sa.Text(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="statistics",
)
run_member_table = sa.Table(
    "replicate_statistical_run_member",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("statistical_run_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_revision_id", sa.Uuid(), nullable=False),
    schema="statistics",
)
qc_table = sa.Table(
    "replicate_qc_observation",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("statistical_run_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("check_code", sa.String(100), nullable=False),
    sa.Column("outcome", sa.String(16), nullable=False),
    sa.Column("detail", sa.String(500), nullable=False),
    sa.Column("expected_point_count", sa.BigInteger(), nullable=True),
    sa.Column("observed_point_count", sa.BigInteger(), nullable=True),
    sa.Column("mismatch_index", sa.BigInteger(), nullable=True),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_by", sa.Uuid(), nullable=False),
    schema="statistics",
)


def _plan_values(value: ReferenceTensileReplicatePlanContent) -> dict[str, object]:
    return {
        "plan_kind": REFERENCE_TENSILE_REPLICATE_PLAN_KIND,
        "selection_id": value.selection_id,
        "selection_revision_id": value.selection_revision_id,
        "sample_count": value.sample_count,
        "required_input_representation": "processed",
        "scalar_feature": REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE,
        "curve_grid_policy": REFERENCE_TENSILE_REPLICATE_GRID_POLICY,
        "quantile_method": REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD,
        "confidence_interval_method": REFERENCE_TENSILE_REPLICATE_CI_METHOD,
        "curve_output_schema_ref": value.curve_output_schema_ref,
    }


def _result_values(value: ReferenceTensileReplicateResultContent) -> dict[str, object]:
    scalar = value.peak_engineering_stress_pa
    return {
        "result_kind": REFERENCE_TENSILE_REPLICATE_PLAN_KIND,
        "statistical_run_id": value.statistical_run_id,
        "plan_id": value.plan_id,
        "plan_revision_id": value.plan_revision_id,
        "selection_id": value.selection_id,
        "selection_revision_id": value.selection_revision_id,
        "sample_count": scalar.sample_count,
        "scalar_feature": REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE,
        "curve_artifact_id": value.curve_artifact_id,
        "curve_sha256": value.curve_sha256,
        "curve_point_count": value.curve_point_count,
        "mean_engineering_stress_pa": scalar.mean,
        "sample_standard_deviation_engineering_stress_pa": scalar.sample_standard_deviation,
        "median_engineering_stress_pa": scalar.median,
        "median_absolute_deviation_engineering_stress_pa": scalar.median_absolute_deviation,
        "interquartile_range_engineering_stress_pa": scalar.interquartile_range,
        "minimum_engineering_stress_pa": scalar.minimum,
        "maximum_engineering_stress_pa": scalar.maximum,
        "coefficient_of_variation": scalar.coefficient_of_variation,
        "mean_confidence_interval_lower_95_pa": scalar.mean_confidence_interval_lower_95,
        "mean_confidence_interval_upper_95_pa": scalar.mean_confidence_interval_upper_95,
        "curve_grid_policy": REFERENCE_TENSILE_REPLICATE_GRID_POLICY,
        "quantile_method": REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD,
        "confidence_interval_method": REFERENCE_TENSILE_REPLICATE_CI_METHOD,
    }


_PLAN_TABLES = TypedRevisionTables(
    aggregate_type=REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
    identity_table=plan_table,
    revision_table=plan_revision_table,
    canonical_content=reference_tensile_replicate_plan_canonical,
    content_values=_plan_values,
    identity_values=lambda value: {
        "plan_label": value.plan_label,
        "plan_kind": REFERENCE_TENSILE_REPLICATE_PLAN_KIND,
    },
)
_RESULT_TABLES = TypedRevisionTables(
    aggregate_type=REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE,
    identity_table=result_table,
    revision_table=result_revision_table,
    canonical_content=reference_tensile_replicate_result_canonical,
    content_values=_result_values,
    identity_values=lambda value: {
        "statistical_run_id": value.statistical_run_id,
        "result_kind": REFERENCE_TENSILE_REPLICATE_PLAN_KIND,
    },
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


def _plan_content(row: Any) -> ReferenceTensileReplicatePlanContent:
    if (
        str(row["plan_kind"]) != REFERENCE_TENSILE_REPLICATE_PLAN_KIND
        or str(row["required_input_representation"]) != "processed"
        or str(row["scalar_feature"]) != REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE
        or str(row["curve_grid_policy"]) != REFERENCE_TENSILE_REPLICATE_GRID_POLICY
        or str(row["quantile_method"]) != REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD
        or str(row["confidence_interval_method"]) != REFERENCE_TENSILE_REPLICATE_CI_METHOD
        or str(row["curve_output_schema_ref"])
        not in REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMAS
    ):
        raise StatisticsConflict("replicate Statistical Plan violates its typed contract")
    return ReferenceTensileReplicatePlanContent(
        plan_label=str(row["plan_label"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        sample_count=int(row["sample_count"]),
        curve_output_schema_ref=str(row["curve_output_schema_ref"]),
    )


def _result_content(row: Any) -> ReferenceTensileReplicateResultContent:
    if (
        str(row["result_kind"]) != REFERENCE_TENSILE_REPLICATE_PLAN_KIND
        or str(row["scalar_feature"]) != REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE
        or str(row["curve_grid_policy"]) != REFERENCE_TENSILE_REPLICATE_GRID_POLICY
        or str(row["quantile_method"]) != REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD
        or str(row["confidence_interval_method"]) != REFERENCE_TENSILE_REPLICATE_CI_METHOD
    ):
        raise StatisticsConflict("replicate Statistical Result violates its typed contract")
    return ReferenceTensileReplicateResultContent(
        statistical_run_id=cast(UUID, row["statistical_run_id"]),
        plan_id=cast(UUID, row["plan_id"]),
        plan_revision_id=cast(UUID, row["plan_revision_id"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        curve_artifact_id=cast(UUID, row["curve_artifact_id"]),
        curve_sha256=str(row["curve_sha256"]),
        curve_point_count=int(row["curve_point_count"]),
        peak_engineering_stress_pa=ReplicateScalarStatistics(
            sample_count=int(row["sample_count"]),
            mean=float(row["mean_engineering_stress_pa"]),
            sample_standard_deviation=float(row["sample_standard_deviation_engineering_stress_pa"]),
            median=float(row["median_engineering_stress_pa"]),
            median_absolute_deviation=float(row["median_absolute_deviation_engineering_stress_pa"]),
            interquartile_range=float(row["interquartile_range_engineering_stress_pa"]),
            minimum=float(row["minimum_engineering_stress_pa"]),
            maximum=float(row["maximum_engineering_stress_pa"]),
            coefficient_of_variation=(
                float(row["coefficient_of_variation"])
                if row["coefficient_of_variation"] is not None
                else None
            ),
            mean_confidence_interval_lower_95=float(row["mean_confidence_interval_lower_95_pa"]),
            mean_confidence_interval_upper_95=float(row["mean_confidence_interval_upper_95_pa"]),
        ),
    )


def _qc(row: Any) -> QcObservation:
    return QcObservation(
        check_code=str(row["check_code"]),
        outcome=QcOutcome(str(row["outcome"])),
        detail=str(row["detail"]),
        expected_point_count=(
            int(row["expected_point_count"]) if row["expected_point_count"] is not None else None
        ),
        observed_point_count=(
            int(row["observed_point_count"]) if row["observed_point_count"] is not None else None
        ),
        mismatch_index=(int(row["mismatch_index"]) if row["mismatch_index"] is not None else None),
    )


def _member(row: Any) -> ReplicateStatisticalRunMember:
    return ReplicateStatisticalRunMember(
        ordinal=int(row["ordinal"]),
        dataset_id=cast(UUID, row["dataset_id"]),
        dataset_revision_id=cast(UUID, row["dataset_revision_id"]),
        test_run_id=cast(UUID, row["test_run_id"]),
        test_run_revision_id=cast(UUID, row["test_run_revision_id"]),
    )


def _run(
    row: Any,
    members: tuple[ReplicateStatisticalRunMember, ...],
    qcs: tuple[QcObservation, ...],
) -> ReplicateStatisticalRun:
    return ReplicateStatisticalRun(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        plan_id=cast(UUID, row["plan_id"]),
        plan_revision_id=cast(UUID, row["plan_revision_id"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        status=StatisticalRunStatus(str(row["status"])),
        sample_count=int(row["sample_count"]),
        result_id=cast(UUID | None, row["result_id"]),
        result_revision_id=cast(UUID | None, row["result_revision_id"]),
        curve_artifact_id=cast(UUID | None, row["curve_artifact_id"]),
        curve_sha256=cast(str | None, row["curve_sha256"]),
        curve_point_count=(
            int(row["curve_point_count"]) if row["curve_point_count"] is not None else None
        ),
        failure_code=cast(str | None, row["failure_code"]),
        change_reason=str(row["change_reason"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
        members=members,
        qc_observations=qcs,
    )


class SqlAlchemyReplicateStatisticsRepository(ReplicateStatisticsRepository):
    """Persist exact replicate membership, immutable results, and terminal QC facts."""

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
    ) -> RevisionStore[ReferenceTensileReplicatePlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_PLAN_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def result_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensileReplicateResultContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_RESULT_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _plan_statement(*, current: bool) -> sa.Select[Any]:
        revision = plan_revision_table
        statement = sa.select(
            plan_table.c.id.label("identity_id"),
            plan_table.c.plan_label,
            *_revision_columns(revision),
            revision.c.plan_kind,
            revision.c.selection_id,
            revision.c.selection_revision_id,
            revision.c.sample_count,
            revision.c.required_input_representation,
            revision.c.scalar_feature,
            revision.c.curve_grid_policy,
            revision.c.quantile_method,
            revision.c.confidence_interval_method,
            revision.c.curve_output_schema_ref,
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
        if current:
            statement = statement.where(revision.c.id == plan_table.c.current_revision_id)
        return statement

    @staticmethod
    def _plan_snapshot(row: Any) -> ReplicateStatisticalPlanSnapshot:
        return ReplicateStatisticalPlanSnapshot(
            cast(UUID, row["identity_id"]),
            ReplicateRevisionSnapshot(
                _record(row, REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE),
                _plan_content(row),
            ),
        )

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> ReplicateStatisticalPlanSnapshot:
        statement = self._plan_statement(current=True).where(
            plan_table.c.organization_id == context.organization_id,
            plan_table.c.project_id == context.project_id,
            plan_table.c.id == plan_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("replicate Statistical Plan is not visible")
        return self._plan_snapshot(row)

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> ReplicateRevisionSnapshot[ReferenceTensileReplicatePlanContent]:
        statement = self._plan_statement(current=False).where(
            plan_table.c.organization_id == context.organization_id,
            plan_table.c.project_id == context.project_id,
            plan_table.c.id == plan_id,
            plan_revision_table.c.id == plan_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("replicate Statistical Plan revision is not visible")
        return ReplicateRevisionSnapshot(
            _record(row, REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE), _plan_content(row)
        )

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_revision_id: UUID,
        limit: int,
    ) -> tuple[ReplicateStatisticalPlanSnapshot, ...]:
        statement = (
            self._plan_statement(current=True)
            .where(
                plan_table.c.organization_id == context.organization_id,
                plan_table.c.project_id == context.project_id,
                plan_revision_table.c.selection_revision_id == selection_revision_id,
            )
            .order_by(plan_table.c.created_at.desc())
            .limit(limit)
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._plan_snapshot(row) for row in rows)

    @staticmethod
    def _result_statement() -> sa.Select[Any]:
        revision = result_revision_table
        return sa.select(
            result_table.c.id.label("identity_id"),
            *_revision_columns(revision),
            *(
                revision.c[name]
                for name in (
                    "result_kind",
                    "statistical_run_id",
                    "plan_id",
                    "plan_revision_id",
                    "selection_id",
                    "selection_revision_id",
                    "sample_count",
                    "scalar_feature",
                    "curve_artifact_id",
                    "curve_sha256",
                    "curve_point_count",
                    "mean_engineering_stress_pa",
                    "sample_standard_deviation_engineering_stress_pa",
                    "median_engineering_stress_pa",
                    "median_absolute_deviation_engineering_stress_pa",
                    "interquartile_range_engineering_stress_pa",
                    "minimum_engineering_stress_pa",
                    "maximum_engineering_stress_pa",
                    "coefficient_of_variation",
                    "mean_confidence_interval_lower_95_pa",
                    "mean_confidence_interval_upper_95_pa",
                    "curve_grid_policy",
                    "quantile_method",
                    "confidence_interval_method",
                )
            ),
        ).select_from(
            result_table.join(
                revision,
                sa.and_(
                    revision.c.id == result_table.c.current_revision_id,
                    revision.c.aggregate_id == result_table.c.id,
                    revision.c.organization_id == result_table.c.organization_id,
                    revision.c.project_id == result_table.c.project_id,
                ),
            )
        )

    def get_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
    ) -> ReplicateStatisticalResultSnapshot:
        statement = self._result_statement().where(
            result_table.c.organization_id == context.organization_id,
            result_table.c.project_id == context.project_id,
            result_table.c.id == result_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("replicate Statistical Result is not visible")
        return ReplicateStatisticalResultSnapshot(
            cast(UUID, row["identity_id"]),
            ReplicateRevisionSnapshot(
                _record(row, REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE),
                _result_content(row),
            ),
        )

    @staticmethod
    def _run_values(context: SecurityContext, run: ReplicateStatisticalRun) -> dict[str, object]:
        return {
            "id": run.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
            "plan_id": run.plan_id,
            "plan_revision_id": run.plan_revision_id,
            "selection_id": run.selection_id,
            "selection_revision_id": run.selection_revision_id,
            "execution_mode": "committed",
            "status": run.status.value,
            "sample_count": run.sample_count,
            "result_id": run.result_id,
            "result_revision_id": run.result_revision_id,
            "curve_artifact_id": run.curve_artifact_id,
            "curve_sha256": run.curve_sha256,
            "curve_point_count": run.curve_point_count,
            "failure_code": run.failure_code,
            "change_reason": run.change_reason,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "created_by": run.created_by,
            "request_id": run.request_id,
            "trace_id": run.trace_id,
        }

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ReplicateStatisticalRun,
    ) -> ReplicateStatisticalRun:
        try:
            with self._session(context, decision) as session:
                session.execute(run_table.insert().values(self._run_values(context, run)))
                session.execute(
                    run_member_table.insert(),
                    [
                        {
                            "organization_id": context.organization_id,
                            "project_id": context.project_id,
                            "classification": run.classification.value,
                            "statistical_run_id": run.id,
                            "ordinal": member.ordinal,
                            "dataset_id": member.dataset_id,
                            "dataset_revision_id": member.dataset_revision_id,
                            "test_run_id": member.test_run_id,
                            "test_run_revision_id": member.test_run_revision_id,
                        }
                        for member in run.members
                    ],
                )
        except (IntegrityError, DBAPIError) as error:
            raise StatisticsConflict(
                "replicate Statistical Run conflicts with pinned data"
            ) from error
        return run

    @staticmethod
    def _qc_values(
        context: SecurityContext,
        run: ReplicateStatisticalRun,
        observations: tuple[QcObservation, ...],
    ) -> list[dict[str, object]]:
        now = datetime.now(UTC)
        return [
            {
                "organization_id": context.organization_id,
                "project_id": context.project_id,
                "classification": run.classification.value,
                "statistical_run_id": run.id,
                "ordinal": ordinal,
                "check_code": observation.check_code,
                "outcome": observation.outcome.value,
                "detail": observation.detail,
                "expected_point_count": observation.expected_point_count,
                "observed_point_count": observation.observed_point_count,
                "mismatch_index": observation.mismatch_index,
                "recorded_at": now,
                "recorded_by": context.principal.id,
            }
            for ordinal, observation in enumerate(observations)
        ]

    def _terminal_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        values: dict[str, object],
        observations: tuple[QcObservation, ...],
    ) -> ReplicateStatisticalRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(run_table).where(
                        run_table.c.organization_id == context.organization_id,
                        run_table.c.project_id == context.project_id,
                        run_table.c.id == run_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise StatisticsNotFound("replicate Statistical Run is not visible")
            current = self._load_run_related(session, row)
            qc_values = self._qc_values(context, current, observations)
            if qc_values:
                session.execute(qc_table.insert(), qc_values)
            result = (
                session.execute(
                    run_table.update()
                    .where(
                        run_table.c.organization_id == context.organization_id,
                        run_table.c.project_id == context.project_id,
                        run_table.c.id == run_id,
                        run_table.c.status == StatisticalRunStatus.EXECUTING.value,
                    )
                    .values(**values)
                    .returning(*run_table.c)
                )
                .mappings()
                .one_or_none()
            )
            if result is None:
                raise StatisticsConflict("replicate Statistical Run is already terminal")
            return self._load_run_related(session, result)

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        result: ReplicateStatisticalResultSnapshot,
        qc_observations: tuple[QcObservation, ...],
    ) -> ReplicateStatisticalRun:
        content = result.current.content
        return self._terminal_run(
            context=context,
            decision=decision,
            run_id=run_id,
            values={
                "status": StatisticalRunStatus.SUCCEEDED.value,
                "result_id": result.id,
                "result_revision_id": result.current.record.revision_id,
                "curve_artifact_id": content.curve_artifact_id,
                "curve_sha256": content.curve_sha256,
                "curve_point_count": content.curve_point_count,
                "ended_at": datetime.now(UTC),
            },
            observations=qc_observations,
        )

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
        qc_observations: tuple[QcObservation, ...],
    ) -> ReplicateStatisticalRun:
        return self._terminal_run(
            context=context,
            decision=decision,
            run_id=run_id,
            values={
                "status": StatisticalRunStatus.FAILED.value,
                "failure_code": failure_code,
                "ended_at": datetime.now(UTC),
            },
            observations=qc_observations,
        )

    @staticmethod
    def _load_run_related(session: Session, row: Any) -> ReplicateStatisticalRun:
        members = tuple(
            _member(item)
            for item in session.execute(
                sa.select(run_member_table)
                .where(
                    run_member_table.c.organization_id == row["organization_id"],
                    run_member_table.c.project_id == row["project_id"],
                    run_member_table.c.statistical_run_id == row["id"],
                )
                .order_by(run_member_table.c.ordinal)
            ).mappings()
        )
        qcs = tuple(
            _qc(item)
            for item in session.execute(
                sa.select(qc_table)
                .where(
                    qc_table.c.organization_id == row["organization_id"],
                    qc_table.c.project_id == row["project_id"],
                    qc_table.c.statistical_run_id == row["id"],
                )
                .order_by(qc_table.c.ordinal)
            ).mappings()
        )
        return _run(row, members, qcs)

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ReplicateStatisticalRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(run_table).where(
                        run_table.c.organization_id == context.organization_id,
                        run_table.c.project_id == context.project_id,
                        run_table.c.id == run_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise StatisticsNotFound("replicate Statistical Run is not visible")
            return self._load_run_related(session, row)
