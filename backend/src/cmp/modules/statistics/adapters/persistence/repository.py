"""RLS-bound PostgreSQL persistence for typed reference Statistics/QC resources."""

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
from cmp.modules.statistics.application.service import (
    STATISTICAL_PLAN_AGGREGATE_TYPE,
    STATISTICAL_RESULT_AGGREGATE_TYPE,
    RevisionSnapshot,
    StatisticalPlanSnapshot,
    StatisticalResultSnapshot,
    StatisticalRun,
    StatisticsRepository,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE,
    REFERENCE_TENSILE_PAIR_CI_STATUS,
    REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
    REFERENCE_TENSILE_PAIR_GRID_POLICY,
    REFERENCE_TENSILE_PAIR_PLAN_KIND,
    REFERENCE_TENSILE_PAIR_QUANTILE_METHOD,
    REFERENCE_TENSILE_PAIR_SCALAR_FEATURE,
    QcObservation,
    QcOutcome,
    ReferenceTensilePairPlanContent,
    ReferenceTensilePairResultContent,
    ReferenceTensilePairScalarStatistics,
    StatisticalRunStatus,
    StatisticsConflict,
    StatisticsNotFound,
    reference_tensile_pair_plan_canonical,
    reference_tensile_pair_result_canonical,
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


statistical_plan_table = _identity_table(
    "statistical_plan",
    sa.Column("plan_label", sa.String(160), nullable=False),
    sa.Column("plan_kind", sa.String(100), nullable=False),
)
statistical_plan_revision_table = _revision_table(
    "statistical_plan_revision",
    sa.Column("plan_kind", sa.String(100), nullable=False),
    sa.Column("sample_count", sa.SmallInteger(), nullable=False),
    sa.Column("first_selection_id", sa.Uuid(), nullable=False),
    sa.Column("first_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("second_selection_id", sa.Uuid(), nullable=False),
    sa.Column("second_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("input_schema_ref", sa.String(500), nullable=False),
    sa.Column("scalar_feature", sa.String(100), nullable=False),
    sa.Column("curve_grid_policy", sa.String(100), nullable=False),
    sa.Column("assumption_profile", sa.String(100), nullable=False),
    sa.Column("quantile_method", sa.String(100), nullable=False),
    sa.Column("confidence_interval_status", sa.String(100), nullable=False),
    sa.Column("curve_output_schema_ref", sa.String(500), nullable=False),
)
statistical_result_table = _identity_table(
    "statistical_result",
    sa.Column("statistical_run_id", sa.Uuid(), nullable=False),
    sa.Column("result_kind", sa.String(100), nullable=False),
)
statistical_result_revision_table = _revision_table(
    "statistical_result_revision",
    sa.Column("result_kind", sa.String(100), nullable=False),
    sa.Column("statistical_run_id", sa.Uuid(), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("first_selection_id", sa.Uuid(), nullable=False),
    sa.Column("first_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("first_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("first_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("second_selection_id", sa.Uuid(), nullable=False),
    sa.Column("second_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("second_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("second_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("sample_count", sa.SmallInteger(), nullable=False),
    sa.Column("scalar_feature", sa.String(100), nullable=False),
    sa.Column("curve_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("curve_sha256", sa.CHAR(64), nullable=False),
    sa.Column("curve_point_count", sa.BigInteger(), nullable=False),
    sa.Column("first_peak_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("second_peak_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("mean_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("sample_standard_deviation_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("median_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("median_absolute_deviation_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("interquartile_range_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("minimum_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("maximum_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("coefficient_of_variation", sa.Double(), nullable=True),
    sa.Column("assumption_profile", sa.String(100), nullable=False),
    sa.Column("curve_grid_policy", sa.String(100), nullable=False),
    sa.Column("quantile_method", sa.String(100), nullable=False),
    sa.Column("confidence_interval_status", sa.String(100), nullable=False),
)
statistical_run_table = sa.Table(
    "statistical_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("first_selection_id", sa.Uuid(), nullable=False),
    sa.Column("first_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("first_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("first_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("second_selection_id", sa.Uuid(), nullable=False),
    sa.Column("second_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("second_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("second_dataset_revision_id", sa.Uuid(), nullable=False),
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
qc_observation_table = sa.Table(
    "qc_observation",
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


def _plan_content(row: Any) -> ReferenceTensilePairPlanContent:
    if (
        str(row["plan_kind"]) != REFERENCE_TENSILE_PAIR_PLAN_KIND
        or int(row["sample_count"]) != 2
        or str(row["input_schema_ref"])
        != "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0"
        or str(row["scalar_feature"]) != REFERENCE_TENSILE_PAIR_SCALAR_FEATURE
        or str(row["curve_grid_policy"]) != REFERENCE_TENSILE_PAIR_GRID_POLICY
        or str(row["assumption_profile"]) != REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE
        or str(row["quantile_method"]) != REFERENCE_TENSILE_PAIR_QUANTILE_METHOD
        or str(row["confidence_interval_status"]) != REFERENCE_TENSILE_PAIR_CI_STATUS
        or str(row["curve_output_schema_ref"]) != REFERENCE_TENSILE_PAIR_CURVE_SCHEMA
    ):
        raise StatisticsConflict("Statistical Plan revision violates the reference pair contract")
    return ReferenceTensilePairPlanContent(
        plan_label=str(row["plan_label"]),
        first_selection_id=cast(UUID, row["first_selection_id"]),
        first_selection_revision_id=cast(UUID, row["first_selection_revision_id"]),
        second_selection_id=cast(UUID, row["second_selection_id"]),
        second_selection_revision_id=cast(UUID, row["second_selection_revision_id"]),
    )


def _result_content(row: Any) -> ReferenceTensilePairResultContent:
    if (
        str(row["result_kind"]) != REFERENCE_TENSILE_PAIR_PLAN_KIND
        or int(row["sample_count"]) != 2
        or str(row["scalar_feature"]) != REFERENCE_TENSILE_PAIR_SCALAR_FEATURE
        or str(row["assumption_profile"]) != REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE
        or str(row["curve_grid_policy"]) != REFERENCE_TENSILE_PAIR_GRID_POLICY
        or str(row["quantile_method"]) != REFERENCE_TENSILE_PAIR_QUANTILE_METHOD
        or str(row["confidence_interval_status"]) != REFERENCE_TENSILE_PAIR_CI_STATUS
    ):
        raise StatisticsConflict("Statistical Result revision violates the reference pair contract")
    return ReferenceTensilePairResultContent(
        statistical_run_id=cast(UUID, row["statistical_run_id"]),
        plan_id=cast(UUID, row["plan_id"]),
        plan_revision_id=cast(UUID, row["plan_revision_id"]),
        first_selection_id=cast(UUID, row["first_selection_id"]),
        first_selection_revision_id=cast(UUID, row["first_selection_revision_id"]),
        first_dataset_id=cast(UUID, row["first_dataset_id"]),
        first_dataset_revision_id=cast(UUID, row["first_dataset_revision_id"]),
        second_selection_id=cast(UUID, row["second_selection_id"]),
        second_selection_revision_id=cast(UUID, row["second_selection_revision_id"]),
        second_dataset_id=cast(UUID, row["second_dataset_id"]),
        second_dataset_revision_id=cast(UUID, row["second_dataset_revision_id"]),
        curve_artifact_id=cast(UUID, row["curve_artifact_id"]),
        curve_sha256=str(row["curve_sha256"]),
        curve_point_count=int(row["curve_point_count"]),
        scalar=ReferenceTensilePairScalarStatistics(
            first_peak_engineering_stress_pa=float(row["first_peak_engineering_stress_pa"]),
            second_peak_engineering_stress_pa=float(row["second_peak_engineering_stress_pa"]),
            mean_engineering_stress_pa=float(row["mean_engineering_stress_pa"]),
            sample_standard_deviation_engineering_stress_pa=float(
                row["sample_standard_deviation_engineering_stress_pa"]
            ),
            median_engineering_stress_pa=float(row["median_engineering_stress_pa"]),
            median_absolute_deviation_engineering_stress_pa=float(
                row["median_absolute_deviation_engineering_stress_pa"]
            ),
            interquartile_range_engineering_stress_pa=float(
                row["interquartile_range_engineering_stress_pa"]
            ),
            minimum_engineering_stress_pa=float(row["minimum_engineering_stress_pa"]),
            maximum_engineering_stress_pa=float(row["maximum_engineering_stress_pa"]),
            coefficient_of_variation=(
                float(row["coefficient_of_variation"])
                if row["coefficient_of_variation"] is not None
                else None
            ),
        ),
    )


def _plan_values(value: ReferenceTensilePairPlanContent) -> dict[str, object]:
    return {
        "plan_kind": REFERENCE_TENSILE_PAIR_PLAN_KIND,
        "sample_count": 2,
        "first_selection_id": value.first_selection_id,
        "first_selection_revision_id": value.first_selection_revision_id,
        "second_selection_id": value.second_selection_id,
        "second_selection_revision_id": value.second_selection_revision_id,
        "input_schema_ref": "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0",
        "scalar_feature": REFERENCE_TENSILE_PAIR_SCALAR_FEATURE,
        "curve_grid_policy": REFERENCE_TENSILE_PAIR_GRID_POLICY,
        "assumption_profile": REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE,
        "quantile_method": REFERENCE_TENSILE_PAIR_QUANTILE_METHOD,
        "confidence_interval_status": REFERENCE_TENSILE_PAIR_CI_STATUS,
        "curve_output_schema_ref": REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
    }


def _result_values(value: ReferenceTensilePairResultContent) -> dict[str, object]:
    return {
        "result_kind": REFERENCE_TENSILE_PAIR_PLAN_KIND,
        "statistical_run_id": value.statistical_run_id,
        "plan_id": value.plan_id,
        "plan_revision_id": value.plan_revision_id,
        "first_selection_id": value.first_selection_id,
        "first_selection_revision_id": value.first_selection_revision_id,
        "first_dataset_id": value.first_dataset_id,
        "first_dataset_revision_id": value.first_dataset_revision_id,
        "second_selection_id": value.second_selection_id,
        "second_selection_revision_id": value.second_selection_revision_id,
        "second_dataset_id": value.second_dataset_id,
        "second_dataset_revision_id": value.second_dataset_revision_id,
        "sample_count": 2,
        "scalar_feature": REFERENCE_TENSILE_PAIR_SCALAR_FEATURE,
        "curve_artifact_id": value.curve_artifact_id,
        "curve_sha256": value.curve_sha256,
        "curve_point_count": value.curve_point_count,
        "first_peak_engineering_stress_pa": value.scalar.first_peak_engineering_stress_pa,
        "second_peak_engineering_stress_pa": value.scalar.second_peak_engineering_stress_pa,
        "mean_engineering_stress_pa": value.scalar.mean_engineering_stress_pa,
        "sample_standard_deviation_engineering_stress_pa": (
            value.scalar.sample_standard_deviation_engineering_stress_pa
        ),
        "median_engineering_stress_pa": value.scalar.median_engineering_stress_pa,
        "median_absolute_deviation_engineering_stress_pa": (
            value.scalar.median_absolute_deviation_engineering_stress_pa
        ),
        "interquartile_range_engineering_stress_pa": (
            value.scalar.interquartile_range_engineering_stress_pa
        ),
        "minimum_engineering_stress_pa": value.scalar.minimum_engineering_stress_pa,
        "maximum_engineering_stress_pa": value.scalar.maximum_engineering_stress_pa,
        "coefficient_of_variation": value.scalar.coefficient_of_variation,
        "assumption_profile": REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE,
        "curve_grid_policy": REFERENCE_TENSILE_PAIR_GRID_POLICY,
        "quantile_method": REFERENCE_TENSILE_PAIR_QUANTILE_METHOD,
        "confidence_interval_status": REFERENCE_TENSILE_PAIR_CI_STATUS,
    }


_PLAN_TABLES: TypedRevisionTables[ReferenceTensilePairPlanContent] = TypedRevisionTables(
    aggregate_type=STATISTICAL_PLAN_AGGREGATE_TYPE,
    identity_table=statistical_plan_table,
    revision_table=statistical_plan_revision_table,
    canonical_content=reference_tensile_pair_plan_canonical,
    content_values=_plan_values,
    identity_values=lambda value: {
        "plan_label": value.plan_label,
        "plan_kind": REFERENCE_TENSILE_PAIR_PLAN_KIND,
    },
)
_RESULT_TABLES: TypedRevisionTables[ReferenceTensilePairResultContent] = TypedRevisionTables(
    aggregate_type=STATISTICAL_RESULT_AGGREGATE_TYPE,
    identity_table=statistical_result_table,
    revision_table=statistical_result_revision_table,
    canonical_content=reference_tensile_pair_result_canonical,
    content_values=_result_values,
    identity_values=lambda value: {
        "statistical_run_id": value.statistical_run_id,
        "result_kind": REFERENCE_TENSILE_PAIR_PLAN_KIND,
    },
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


def _run(row: Any, qcs: tuple[QcObservation, ...] = ()) -> StatisticalRun:
    return StatisticalRun(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        plan_id=cast(UUID, row["plan_id"]),
        plan_revision_id=cast(UUID, row["plan_revision_id"]),
        first_selection_id=cast(UUID, row["first_selection_id"]),
        first_selection_revision_id=cast(UUID, row["first_selection_revision_id"]),
        first_dataset_id=cast(UUID, row["first_dataset_id"]),
        first_dataset_revision_id=cast(UUID, row["first_dataset_revision_id"]),
        second_selection_id=cast(UUID, row["second_selection_id"]),
        second_selection_revision_id=cast(UUID, row["second_selection_revision_id"]),
        second_dataset_id=cast(UUID, row["second_dataset_id"]),
        second_dataset_revision_id=cast(UUID, row["second_dataset_revision_id"]),
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
        qc_observations=qcs,
    )


class SqlAlchemyStatisticsRepository(StatisticsRepository):
    """Explicit Statistics tables with RLS-bound reads and immutable terminal facts."""

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
    ) -> RevisionStore[ReferenceTensilePairPlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_PLAN_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def result_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensilePairResultContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_RESULT_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _current_plan_statement() -> sa.Select[Any]:
        identity = statistical_plan_table
        revision = statistical_plan_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            identity.c.plan_label,
            *_revision_columns(revision),
            revision.c.plan_kind,
            revision.c.sample_count,
            revision.c.first_selection_id,
            revision.c.first_selection_revision_id,
            revision.c.second_selection_id,
            revision.c.second_selection_revision_id,
            revision.c.input_schema_ref,
            revision.c.scalar_feature,
            revision.c.curve_grid_policy,
            revision.c.assumption_profile,
            revision.c.quantile_method,
            revision.c.confidence_interval_status,
            revision.c.curve_output_schema_ref,
        ).select_from(
            identity.join(
                revision,
                sa.and_(
                    revision.c.id == identity.c.current_revision_id,
                    revision.c.aggregate_id == identity.c.id,
                    revision.c.organization_id == identity.c.organization_id,
                    revision.c.project_id == identity.c.project_id,
                ),
            )
        )

    @staticmethod
    def _plan_snapshot(row: Any) -> StatisticalPlanSnapshot:
        return StatisticalPlanSnapshot(
            id=cast(UUID, row["identity_id"]),
            current=RevisionSnapshot(
                _record(row, STATISTICAL_PLAN_AGGREGATE_TYPE), _plan_content(row)
            ),
        )

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> StatisticalPlanSnapshot:
        statement = self._current_plan_statement().where(
            statistical_plan_table.c.organization_id == context.organization_id,
            statistical_plan_table.c.project_id == context.project_id,
            statistical_plan_table.c.id == plan_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("Statistical Plan is not visible in the selected tenant")
        return self._plan_snapshot(row)

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceTensilePairPlanContent]:
        identity = statistical_plan_table
        revision = statistical_plan_revision_table
        statement = (
            sa.select(
                identity.c.plan_label,
                *_revision_columns(revision),
                revision.c.plan_kind,
                revision.c.sample_count,
                revision.c.first_selection_id,
                revision.c.first_selection_revision_id,
                revision.c.second_selection_id,
                revision.c.second_selection_revision_id,
                revision.c.input_schema_ref,
                revision.c.scalar_feature,
                revision.c.curve_grid_policy,
                revision.c.assumption_profile,
                revision.c.quantile_method,
                revision.c.confidence_interval_status,
                revision.c.curve_output_schema_ref,
            )
            .select_from(
                identity.join(
                    revision,
                    sa.and_(
                        revision.c.aggregate_id == identity.c.id,
                        revision.c.organization_id == identity.c.organization_id,
                        revision.c.project_id == identity.c.project_id,
                    ),
                )
            )
            .where(
                identity.c.organization_id == context.organization_id,
                identity.c.project_id == context.project_id,
                identity.c.id == plan_id,
                revision.c.id == plan_revision_id,
            )
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound(
                "Statistical Plan revision is not visible in the selected tenant"
            )
        return RevisionSnapshot(_record(row, STATISTICAL_PLAN_AGGREGATE_TYPE), _plan_content(row))

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[StatisticalPlanSnapshot, ...]:
        statement = (
            self._current_plan_statement()
            .where(
                statistical_plan_table.c.organization_id == context.organization_id,
                statistical_plan_table.c.project_id == context.project_id,
            )
            .order_by(statistical_plan_table.c.created_at.desc())
            .limit(limit)
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._plan_snapshot(row) for row in rows)

    @staticmethod
    def _current_result_statement() -> sa.Select[Any]:
        identity = statistical_result_table
        revision = statistical_result_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            *_revision_columns(revision),
            revision.c.result_kind,
            revision.c.statistical_run_id,
            revision.c.plan_id,
            revision.c.plan_revision_id,
            revision.c.first_selection_id,
            revision.c.first_selection_revision_id,
            revision.c.first_dataset_id,
            revision.c.first_dataset_revision_id,
            revision.c.second_selection_id,
            revision.c.second_selection_revision_id,
            revision.c.second_dataset_id,
            revision.c.second_dataset_revision_id,
            revision.c.sample_count,
            revision.c.scalar_feature,
            revision.c.curve_artifact_id,
            revision.c.curve_sha256,
            revision.c.curve_point_count,
            revision.c.first_peak_engineering_stress_pa,
            revision.c.second_peak_engineering_stress_pa,
            revision.c.mean_engineering_stress_pa,
            revision.c.sample_standard_deviation_engineering_stress_pa,
            revision.c.median_engineering_stress_pa,
            revision.c.median_absolute_deviation_engineering_stress_pa,
            revision.c.interquartile_range_engineering_stress_pa,
            revision.c.minimum_engineering_stress_pa,
            revision.c.maximum_engineering_stress_pa,
            revision.c.coefficient_of_variation,
            revision.c.assumption_profile,
            revision.c.curve_grid_policy,
            revision.c.quantile_method,
            revision.c.confidence_interval_status,
        ).select_from(
            identity.join(
                revision,
                sa.and_(
                    revision.c.id == identity.c.current_revision_id,
                    revision.c.aggregate_id == identity.c.id,
                    revision.c.organization_id == identity.c.organization_id,
                    revision.c.project_id == identity.c.project_id,
                ),
            )
        )

    @staticmethod
    def _result_snapshot(row: Any) -> StatisticalResultSnapshot:
        return StatisticalResultSnapshot(
            id=cast(UUID, row["identity_id"]),
            current=RevisionSnapshot(
                _record(row, STATISTICAL_RESULT_AGGREGATE_TYPE), _result_content(row)
            ),
        )

    def get_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
    ) -> StatisticalResultSnapshot:
        statement = self._current_result_statement().where(
            statistical_result_table.c.organization_id == context.organization_id,
            statistical_result_table.c.project_id == context.project_id,
            statistical_result_table.c.id == result_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("Statistical Result is not visible in the selected tenant")
        return self._result_snapshot(row)

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: StatisticalRun,
    ) -> StatisticalRun:
        values = {
            "id": run.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
            "plan_id": run.plan_id,
            "plan_revision_id": run.plan_revision_id,
            "first_selection_id": run.first_selection_id,
            "first_selection_revision_id": run.first_selection_revision_id,
            "first_dataset_id": run.first_dataset_id,
            "first_dataset_revision_id": run.first_dataset_revision_id,
            "second_selection_id": run.second_selection_id,
            "second_selection_revision_id": run.second_selection_revision_id,
            "second_dataset_id": run.second_dataset_id,
            "second_dataset_revision_id": run.second_dataset_revision_id,
            "execution_mode": "committed",
            "status": run.status.value,
            "sample_count": 2,
            "result_id": None,
            "result_revision_id": None,
            "curve_artifact_id": None,
            "curve_sha256": None,
            "curve_point_count": None,
            "failure_code": None,
            "change_reason": run.change_reason,
            "started_at": run.started_at,
            "ended_at": None,
            "created_by": run.created_by,
            "request_id": run.request_id,
            "trace_id": run.trace_id,
        }
        try:
            with self._session(context, decision) as session:
                session.execute(sa.insert(statistical_run_table).values(**values))
        except (IntegrityError, DBAPIError) as error:
            raise StatisticsConflict(
                "Statistical Run cannot be created for these pinned inputs"
            ) from error
        return run

    @staticmethod
    def _terminal_values(
        *,
        status: StatisticalRunStatus,
        result: StatisticalResultSnapshot | None,
        failure_code: str | None,
    ) -> dict[str, object]:
        content = result.current.content if result is not None else None
        return {
            "status": status.value,
            "result_id": result.id if result is not None else None,
            "result_revision_id": result.current.record.revision_id if result is not None else None,
            "curve_artifact_id": content.curve_artifact_id if content is not None else None,
            "curve_sha256": content.curve_sha256 if content is not None else None,
            "curve_point_count": content.curve_point_count if content is not None else None,
            "failure_code": failure_code,
            "ended_at": datetime.now(UTC),
        }

    def _terminal_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        values: dict[str, object],
        qc_observations: tuple[QcObservation, ...],
    ) -> StatisticalRun:
        statement = (
            sa.update(statistical_run_table)
            .where(
                statistical_run_table.c.organization_id == context.organization_id,
                statistical_run_table.c.project_id == context.project_id,
                statistical_run_table.c.id == run_id,
                statistical_run_table.c.status == StatisticalRunStatus.EXECUTING.value,
            )
            .values(**values)
            .returning(*statistical_run_table.c)
        )
        try:
            with self._session(context, decision) as session:
                row = session.execute(statement).mappings().one_or_none()
                if row is None:
                    raise StatisticsConflict("Statistical Run is no longer executing")
                recorded_at = cast(datetime, values["ended_at"])
                for ordinal, observation in enumerate(qc_observations):
                    session.execute(
                        sa.insert(qc_observation_table).values(
                            organization_id=context.organization_id,
                            project_id=context.project_id,
                            classification=row["classification"],
                            statistical_run_id=run_id,
                            ordinal=ordinal,
                            check_code=observation.check_code,
                            outcome=observation.outcome.value,
                            detail=observation.detail,
                            expected_point_count=observation.expected_point_count,
                            observed_point_count=observation.observed_point_count,
                            mismatch_index=observation.mismatch_index,
                            recorded_at=recorded_at,
                            recorded_by=context.principal.id,
                        )
                    )
        except StatisticsConflict:
            raise
        except (IntegrityError, DBAPIError) as error:
            raise StatisticsConflict("Statistical Run terminal state was rejected") from error
        return _run(row, qc_observations)

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        result: StatisticalResultSnapshot,
        qc_observations: tuple[QcObservation, ...],
    ) -> StatisticalRun:
        return self._terminal_run(
            context=context,
            decision=decision,
            run_id=run_id,
            values=self._terminal_values(
                status=StatisticalRunStatus.SUCCEEDED,
                result=result,
                failure_code=None,
            ),
            qc_observations=qc_observations,
        )

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
        qc_observations: tuple[QcObservation, ...],
    ) -> StatisticalRun:
        return self._terminal_run(
            context=context,
            decision=decision,
            run_id=run_id,
            values=self._terminal_values(
                status=StatisticalRunStatus.FAILED,
                result=None,
                failure_code=failure_code,
            ),
            qc_observations=qc_observations,
        )

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> StatisticalRun:
        statement = sa.select(statistical_run_table).where(
            statistical_run_table.c.organization_id == context.organization_id,
            statistical_run_table.c.project_id == context.project_id,
            statistical_run_table.c.id == run_id,
        )
        qc_statement = (
            sa.select(qc_observation_table)
            .where(
                qc_observation_table.c.organization_id == context.organization_id,
                qc_observation_table.c.project_id == context.project_id,
                qc_observation_table.c.statistical_run_id == run_id,
            )
            .order_by(qc_observation_table.c.ordinal)
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            qcs = tuple(_qc(value) for value in session.execute(qc_statement).mappings().all())
        if row is None:
            raise StatisticsNotFound("Statistical Run is not visible in the selected tenant")
        return _run(row, qcs)
