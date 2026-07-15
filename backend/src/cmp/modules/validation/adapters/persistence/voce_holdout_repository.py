"""PostgreSQL persistence for solver-independent reference Voce holdout evidence."""

from __future__ import annotations

from collections.abc import Sequence
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
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.validation.application.voce_holdout import (
    VOCE_HOLDOUT_PLAN_AGGREGATE_TYPE,
    VoceHoldoutPlanSnapshot,
    VoceHoldoutRepository,
)
from cmp.modules.validation.domain.reference_voce_holdout import (
    ReferenceVoceHoldoutMetrics,
    ReferenceVoceHoldoutPlanContent,
    ReferenceVoceHoldoutResult,
    VoceHoldoutConflict,
    VoceHoldoutNotFound,
    VoceHoldoutVerdict,
    reference_voce_holdout_plan_canonical,
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
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


class VoceHoldoutResultHook(Protocol):
    def __call__(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        result: ReferenceVoceHoldoutResult,
        change_reason: str,
    ) -> None: ...


metadata = sa.MetaData()
plan_table = sa.Table(
    "voce_holdout_plan",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("plan_label", sa.String(160), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    schema="validation",
)
plan_revision_table = sa.Table(
    "voce_holdout_plan_revision",
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
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("holdout_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("holdout_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("metric_profile_id", sa.String(255), nullable=False),
    sa.Column("threshold_profile_id", sa.String(255), nullable=False),
    sa.Column("relative_rmse_threshold", sa.Double(), nullable=False),
    sa.Column("overlap_policy", sa.String(128), nullable=False),
    sa.Column("evaluation_mode", sa.String(64), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="validation",
)
run_table = sa.Table(
    "voce_holdout_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("holdout_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("holdout_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("execution_mode", sa.String(64), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("result_id", sa.Uuid(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    sa.Column("change_reason", sa.Text(), nullable=False),
    schema="validation",
)
result_table = sa.Table(
    "voce_holdout_result",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("run_id", sa.Uuid(), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_input_scope_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_input_scope_revision_id", sa.Uuid(), nullable=False),
    sa.Column("voce_calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("voce_calibration_candidate_id", sa.Uuid(), nullable=False),
    sa.Column("voce_candidate_selection_id", sa.Uuid(), nullable=False),
    sa.Column("voce_candidate_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("holdout_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("holdout_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("holdout_test_run_id", sa.Uuid(), nullable=False),
    sa.Column("holdout_test_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("source_data_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("source_data_sha256", sa.CHAR(64), nullable=False),
    sa.Column("comparison_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("comparison_sha256", sa.CHAR(64), nullable=False),
    sa.Column("comparison_point_count", sa.Integer(), nullable=False),
    sa.Column("root_mean_squared_error_pa", sa.Double(), nullable=False),
    sa.Column("relative_root_mean_squared_error", sa.Double(), nullable=False),
    sa.Column("normalization_stress_scale_pa", sa.Double(), nullable=False),
    sa.Column("characterized_max_true_plastic_strain", sa.Double(), nullable=False),
    sa.Column("verdict", sa.String(32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="validation",
)
comparison_point_table = sa.Table(
    "voce_holdout_comparison_point",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("result_id", sa.Uuid(), nullable=False),
    sa.Column("point_ordinal", sa.Integer(), nullable=False),
    sa.Column("source_point_ordinal", sa.Integer(), nullable=False),
    sa.Column("true_plastic_strain", sa.Double(), nullable=False),
    sa.Column("observed_true_yield_stress_pa", sa.Double(), nullable=False),
    sa.Column("predicted_true_yield_stress_pa", sa.Double(), nullable=False),
    sa.Column("residual_true_yield_stress_pa", sa.Double(), nullable=False),
    schema="validation",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=VOCE_HOLDOUT_PLAN_AGGREGATE_TYPE,
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


def _content(row: Any) -> ReferenceVoceHoldoutPlanContent:
    return ReferenceVoceHoldoutPlanContent(
        plan_label=str(row["plan_label"]),
        material_model_id=cast(UUID, row["material_model_id"]),
        material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
        holdout_dataset_id=cast(UUID, row["holdout_dataset_id"]),
        holdout_dataset_revision_id=cast(UUID, row["holdout_dataset_revision_id"]),
        metric_profile_id=str(row["metric_profile_id"]),
        threshold_profile_id=str(row["threshold_profile_id"]),
        relative_rmse_threshold=float(row["relative_rmse_threshold"]),
        overlap_policy=str(row["overlap_policy"]),
        evaluation_mode=str(row["evaluation_mode"]),
        non_production=bool(row["non_production"]),
    )


def _plan_values(value: ReferenceVoceHoldoutPlanContent) -> dict[str, object]:
    return {
        "material_model_id": value.material_model_id,
        "material_model_revision_id": value.material_model_revision_id,
        "holdout_dataset_id": value.holdout_dataset_id,
        "holdout_dataset_revision_id": value.holdout_dataset_revision_id,
        "metric_profile_id": value.metric_profile_id,
        "threshold_profile_id": value.threshold_profile_id,
        "relative_rmse_threshold": value.relative_rmse_threshold,
        "overlap_policy": value.overlap_policy,
        "evaluation_mode": value.evaluation_mode,
        "non_production": value.non_production,
    }


_TABLES = TypedRevisionTables(
    aggregate_type=VOCE_HOLDOUT_PLAN_AGGREGATE_TYPE,
    identity_table=plan_table,
    revision_table=plan_revision_table,
    canonical_content=reference_voce_holdout_plan_canonical,
    content_values=_plan_values,
    identity_values=lambda value: {
        "plan_label": value.plan_label,
        "material_model_id": value.material_model_id,
    },
)


def _plan_columns() -> tuple[Any, ...]:
    return (*plan_revision_table.c, plan_table.c.plan_label)


class SqlAlchemyVoceHoldoutRepository(VoceHoldoutRepository):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[SqlRevisionHook] = (),
        result_hooks: Sequence[VoceHoldoutResultHook] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = tuple(revision_hooks)
        self._result_hooks = tuple(result_hooks)

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
    ) -> RevisionStore[ReferenceVoceHoldoutPlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _plan_statement() -> sa.Select[Any]:
        return sa.select(*_plan_columns()).select_from(
            plan_table.join(
                plan_revision_table,
                sa.and_(
                    plan_revision_table.c.aggregate_id == plan_table.c.id,
                    plan_revision_table.c.organization_id == plan_table.c.organization_id,
                    plan_revision_table.c.project_id == plan_table.c.project_id,
                ),
            )
        )

    @staticmethod
    def _plan_snapshot(row: Any) -> VoceHoldoutPlanSnapshot:
        return VoceHoldoutPlanSnapshot(
            id=cast(UUID, row["aggregate_id"]),
            current=RevisionSnapshot(_record(row), _content(row)),
        )

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> VoceHoldoutPlanSnapshot:
        statement = self._plan_statement().where(
            plan_table.c.id == plan_id,
            plan_revision_table.c.id == plan_table.c.current_revision_id,
            plan_table.c.organization_id == context.organization_id,
            plan_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise VoceHoldoutNotFound("holdout Plan is not visible")
        return self._plan_snapshot(row)

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceVoceHoldoutPlanContent]:
        statement = self._plan_statement().where(
            plan_table.c.id == plan_id,
            plan_revision_table.c.id == plan_revision_id,
            plan_table.c.organization_id == context.organization_id,
            plan_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise VoceHoldoutNotFound("holdout Plan revision is not visible")
        return RevisionSnapshot(_record(row), _content(row))

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[VoceHoldoutPlanSnapshot, ...]:
        statement = (
            self._plan_statement()
            .where(
                plan_revision_table.c.id == plan_table.c.current_revision_id,
                plan_table.c.organization_id == context.organization_id,
                plan_table.c.project_id == context.project_id,
            )
            .order_by(plan_table.c.updated_at.desc(), plan_table.c.id)
            .limit(limit)
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._plan_snapshot(row) for row in rows)

    def create_succeeded_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        result: ReferenceVoceHoldoutResult,
        change_reason: str,
    ) -> ReferenceVoceHoldoutResult:
        scope = {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": classification.value,
        }
        try:
            with self._session(context, decision) as session:
                session.execute(
                    sa.insert(run_table).values(
                        **scope,
                        id=result.run_id,
                        plan_id=result.plan_id,
                        plan_revision_id=result.plan_revision_id,
                        material_model_id=result.material_model_id,
                        material_model_revision_id=result.material_model_revision_id,
                        holdout_dataset_id=result.holdout_dataset_id,
                        holdout_dataset_revision_id=result.holdout_dataset_revision_id,
                        execution_mode="closed_form_curve",
                        status="succeeded",
                        result_id=result.id,
                        started_at=result.created_at,
                        ended_at=result.created_at,
                        created_by=result.created_by,
                        request_id=context.request_id,
                        trace_id=context.trace_id,
                        change_reason=change_reason,
                    )
                )
                session.execute(
                    sa.insert(result_table).values(
                        **scope,
                        id=result.id,
                        run_id=result.run_id,
                        plan_id=result.plan_id,
                        plan_revision_id=result.plan_revision_id,
                        material_model_id=result.material_model_id,
                        material_model_revision_id=result.material_model_revision_id,
                        calibration_input_scope_id=result.calibration_input_scope_id,
                        calibration_input_scope_revision_id=(
                            result.calibration_input_scope_revision_id
                        ),
                        voce_calibration_run_id=result.voce_calibration_run_id,
                        voce_calibration_candidate_id=result.voce_calibration_candidate_id,
                        voce_candidate_selection_id=result.voce_candidate_selection_id,
                        voce_candidate_selection_revision_id=(
                            result.voce_candidate_selection_revision_id
                        ),
                        holdout_dataset_id=result.holdout_dataset_id,
                        holdout_dataset_revision_id=result.holdout_dataset_revision_id,
                        holdout_test_run_id=result.holdout_test_run_id,
                        holdout_test_run_revision_id=result.holdout_test_run_revision_id,
                        source_data_artifact_id=result.source_data_artifact_id,
                        source_data_sha256=result.source_data_sha256,
                        comparison_artifact_id=result.comparison_artifact_id,
                        comparison_sha256=result.comparison_sha256,
                        comparison_point_count=len(result.metrics.points),
                        root_mean_squared_error_pa=(result.metrics.root_mean_squared_error_pa),
                        relative_root_mean_squared_error=(
                            result.metrics.relative_root_mean_squared_error
                        ),
                        normalization_stress_scale_pa=(
                            result.metrics.normalization_stress_scale_pa
                        ),
                        characterized_max_true_plastic_strain=(
                            result.metrics.characterized_max_true_plastic_strain
                        ),
                        verdict=result.metrics.verdict.value,
                        created_at=result.created_at,
                        created_by=result.created_by,
                    )
                )
                session.execute(
                    sa.insert(comparison_point_table),
                    [
                        {
                            **scope,
                            "result_id": result.id,
                            "point_ordinal": ordinal,
                            "source_point_ordinal": point.source_point_ordinal,
                            "true_plastic_strain": point.true_plastic_strain,
                            "observed_true_yield_stress_pa": (point.observed_true_yield_stress_pa),
                            "predicted_true_yield_stress_pa": (
                                point.predicted_true_yield_stress_pa
                            ),
                            "residual_true_yield_stress_pa": (point.residual_true_yield_stress_pa),
                        }
                        for ordinal, point in enumerate(result.metrics.points)
                    ],
                )
                for hook in self._result_hooks:
                    hook(
                        session,
                        context,
                        decision,
                        classification,
                        result,
                        change_reason,
                    )
        except (DBAPIError, IntegrityError) as error:
            raise VoceHoldoutConflict("holdout Result conflicts with immutable lineage") from error
        return result

    @staticmethod
    def _result(row: Any, point_rows: Sequence[Any]) -> ReferenceVoceHoldoutResult:
        from cmp.modules.validation.domain.reference_voce_holdout import (
            ReferenceVoceHoldoutComparisonPoint,
        )

        points = tuple(
            ReferenceVoceHoldoutComparisonPoint(
                source_point_ordinal=int(point["source_point_ordinal"]),
                true_plastic_strain=float(point["true_plastic_strain"]),
                observed_true_yield_stress_pa=float(point["observed_true_yield_stress_pa"]),
                predicted_true_yield_stress_pa=float(point["predicted_true_yield_stress_pa"]),
                residual_true_yield_stress_pa=float(point["residual_true_yield_stress_pa"]),
            )
            for point in point_rows
        )
        if len(points) != int(row["comparison_point_count"]):
            raise VoceHoldoutConflict("holdout comparison projection is incomplete")
        return ReferenceVoceHoldoutResult(
            id=cast(UUID, row["id"]),
            run_id=cast(UUID, row["run_id"]),
            plan_id=cast(UUID, row["plan_id"]),
            plan_revision_id=cast(UUID, row["plan_revision_id"]),
            material_model_id=cast(UUID, row["material_model_id"]),
            material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
            calibration_input_scope_id=cast(UUID, row["calibration_input_scope_id"]),
            calibration_input_scope_revision_id=cast(
                UUID, row["calibration_input_scope_revision_id"]
            ),
            voce_calibration_run_id=cast(UUID, row["voce_calibration_run_id"]),
            voce_calibration_candidate_id=cast(UUID, row["voce_calibration_candidate_id"]),
            voce_candidate_selection_id=cast(UUID, row["voce_candidate_selection_id"]),
            voce_candidate_selection_revision_id=cast(
                UUID, row["voce_candidate_selection_revision_id"]
            ),
            holdout_dataset_id=cast(UUID, row["holdout_dataset_id"]),
            holdout_dataset_revision_id=cast(UUID, row["holdout_dataset_revision_id"]),
            holdout_test_run_id=cast(UUID, row["holdout_test_run_id"]),
            holdout_test_run_revision_id=cast(UUID, row["holdout_test_run_revision_id"]),
            source_data_artifact_id=cast(UUID, row["source_data_artifact_id"]),
            source_data_sha256=str(row["source_data_sha256"]),
            comparison_artifact_id=cast(UUID, row["comparison_artifact_id"]),
            comparison_sha256=str(row["comparison_sha256"]),
            metrics=ReferenceVoceHoldoutMetrics(
                points=points,
                root_mean_squared_error_pa=float(row["root_mean_squared_error_pa"]),
                relative_root_mean_squared_error=float(row["relative_root_mean_squared_error"]),
                normalization_stress_scale_pa=float(row["normalization_stress_scale_pa"]),
                characterized_max_true_plastic_strain=float(
                    row["characterized_max_true_plastic_strain"]
                ),
                verdict=VoceHoldoutVerdict(str(row["verdict"])),
            ),
            created_at=row["created_at"],
            created_by=cast(UUID, row["created_by"]),
        )

    @staticmethod
    def _result_statement() -> sa.Select[Any]:
        return sa.select(result_table)

    def get_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
    ) -> ReferenceVoceHoldoutResult:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    self._result_statement().where(
                        result_table.c.id == result_id,
                        result_table.c.organization_id == context.organization_id,
                        result_table.c.project_id == context.project_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            points = (
                session.execute(
                    sa.select(comparison_point_table)
                    .where(
                        comparison_point_table.c.result_id == result_id,
                        comparison_point_table.c.organization_id == context.organization_id,
                        comparison_point_table.c.project_id == context.project_id,
                    )
                    .order_by(comparison_point_table.c.point_ordinal)
                )
                .mappings()
                .all()
            )
        if row is None:
            raise VoceHoldoutNotFound("holdout Result is not visible")
        return self._result(row, points)

    def list_results_for_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        limit: int,
    ) -> tuple[ReferenceVoceHoldoutResult, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    self._result_statement()
                    .where(
                        result_table.c.material_model_id == material_model_id,
                        result_table.c.organization_id == context.organization_id,
                        result_table.c.project_id == context.project_id,
                    )
                    .order_by(result_table.c.created_at.desc(), result_table.c.id)
                    .limit(limit)
                )
                .mappings()
                .all()
            )
            result_ids = [cast(UUID, row["id"]) for row in rows]
            point_rows = (
                session.execute(
                    sa.select(comparison_point_table)
                    .where(
                        comparison_point_table.c.result_id.in_(result_ids),
                        comparison_point_table.c.organization_id == context.organization_id,
                        comparison_point_table.c.project_id == context.project_id,
                    )
                    .order_by(
                        comparison_point_table.c.result_id,
                        comparison_point_table.c.point_ordinal,
                    )
                )
                .mappings()
                .all()
                if result_ids
                else []
            )
        grouped: dict[UUID, list[Any]] = {result_id: [] for result_id in result_ids}
        for point in point_rows:
            grouped[cast(UUID, point["result_id"])].append(point)
        return tuple(self._result(row, grouped[cast(UUID, row["id"])]) for row in rows)
