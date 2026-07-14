"""RLS-bound PostgreSQL persistence for the reference calibration orchestration slice."""

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
from cmp.modules.modeling.application.calibration import (
    CALIBRATION_PLAN_AGGREGATE_TYPE,
    CalibrationAttempt,
    CalibrationCandidate,
    CalibrationPlanSnapshot,
    CalibrationRepository,
    CalibrationRun,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationAttemptStatus,
    CalibrationCandidateStatus,
    CalibrationConflict,
    CalibrationNotFound,
    CalibrationRunStatus,
    ReferenceLinearElasticCalibrationPlanContent,
    reference_linear_elastic_calibration_plan_canonical,
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

calibration_plan_table = sa.Table(
    "calibration_plan",
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
    sa.Column("plan_kind", sa.String(100), nullable=False),
    schema="modeling",
)
calibration_plan_revision_table = sa.Table(
    "calibration_plan_revision",
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
    sa.Column("plan_kind", sa.String(100), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("model_family_id", sa.String(255), nullable=False),
    sa.Column("model_schema_version", sa.String(64), nullable=False),
    sa.Column("model_schema_digest", sa.CHAR(64), nullable=False),
    sa.Column("test_mode", sa.String(100), nullable=False),
    sa.Column("evaluator_id", sa.String(255), nullable=False),
    sa.Column("evaluator_version", sa.String(64), nullable=False),
    sa.Column("evaluation_mode", sa.String(64), nullable=False),
    sa.Column("calibrator_id", sa.String(255), nullable=False),
    sa.Column("calibrator_version", sa.String(64), nullable=False),
    sa.Column("parameter_name", sa.String(100), nullable=False),
    sa.Column("youngs_modulus_lower_bound_pa", sa.Double(), nullable=False),
    sa.Column("youngs_modulus_initial_value_pa", sa.Double(), nullable=False),
    sa.Column("youngs_modulus_upper_bound_pa", sa.Double(), nullable=False),
    sa.Column("normalization_stress_scale_pa", sa.Double(), nullable=False),
    sa.Column("point_weighting", sa.String(100), nullable=False),
    sa.Column("objective_aggregation", sa.String(100), nullable=False),
    sa.Column("x_domain_policy", sa.String(100), nullable=False),
    sa.Column("missing_data_policy", sa.String(100), nullable=False),
    sa.Column("multistart_count", sa.SmallInteger(), nullable=False),
    sa.Column("random_seed", sa.BigInteger(), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="modeling",
)
calibration_run_table = sa.Table(
    "calibration_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("execution_mode", sa.String(32), nullable=False),
    sa.Column("reproducibility_level", sa.String(16), nullable=False),
    sa.Column("environment_digest", sa.CHAR(64), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("attempt_count", sa.SmallInteger(), nullable=False),
    sa.Column("candidate_count", sa.SmallInteger(), nullable=False),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("change_reason", sa.Text(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="modeling",
)
calibration_attempt_table = sa.Table(
    "calibration_attempt",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("attempt_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("initial_youngs_modulus_pa", sa.Double(), nullable=False),
    sa.Column("random_seed", sa.BigInteger(), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("candidate_id", sa.Uuid(), nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    schema="modeling",
)
calibration_candidate_table = sa.Table(
    "calibration_candidate",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_attempt_id", sa.Uuid(), nullable=False),
    sa.Column("attempt_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("candidate_sha256", sa.CHAR(64), nullable=False),
    sa.Column("youngs_modulus_pa", sa.Double(), nullable=False),
    sa.Column("objective_total", sa.Double(), nullable=False),
    sa.Column("residual_root_mean_square_pa", sa.Double(), nullable=False),
    sa.Column("residual_mean_pa", sa.Double(), nullable=False),
    sa.Column("bound_sticking", sa.Boolean(), nullable=False),
    sa.Column("convergence_reason", sa.String(255), nullable=False),
    sa.Column("identifiability_status", sa.String(100), nullable=False),
    sa.Column("uncertainty_status", sa.String(100), nullable=False),
    sa.Column("diagnostics_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("diagnostics_sha256", sa.CHAR(64), nullable=False),
    sa.Column("diagnostics_point_count", sa.BigInteger(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="modeling",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=CALIBRATION_PLAN_AGGREGATE_TYPE,
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
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
        change_reason=str(row["change_reason"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _plan_content(row: Any) -> ReferenceLinearElasticCalibrationPlanContent:
    return ReferenceLinearElasticCalibrationPlanContent(
        plan_label=str(row["plan_label"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        material_model_id=cast(UUID, row["material_model_id"]),
        material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
        youngs_modulus_lower_bound_pa=float(row["youngs_modulus_lower_bound_pa"]),
        youngs_modulus_initial_value_pa=float(row["youngs_modulus_initial_value_pa"]),
        youngs_modulus_upper_bound_pa=float(row["youngs_modulus_upper_bound_pa"]),
        normalization_stress_scale_pa=float(row["normalization_stress_scale_pa"]),
        multistart_count=int(row["multistart_count"]),
        random_seed=int(row["random_seed"]),
        plan_kind=str(row["plan_kind"]),
        model_family_id=str(row["model_family_id"]),
        model_schema_version=str(row["model_schema_version"]),
        model_schema_digest=str(row["model_schema_digest"]),
        test_mode=str(row["test_mode"]),
        evaluator_id=str(row["evaluator_id"]),
        evaluator_version=str(row["evaluator_version"]),
        evaluation_mode=str(row["evaluation_mode"]),
        calibrator_id=str(row["calibrator_id"]),
        calibrator_version=str(row["calibrator_version"]),
        parameter_name=str(row["parameter_name"]),
        point_weighting=str(row["point_weighting"]),
        objective_aggregation=str(row["objective_aggregation"]),
        x_domain_policy=str(row["x_domain_policy"]),
        missing_data_policy=str(row["missing_data_policy"]),
        non_production=bool(row["non_production"]),
    )


def _plan_values(value: ReferenceLinearElasticCalibrationPlanContent) -> dict[str, object]:
    return {
        "plan_kind": value.plan_kind,
        "selection_id": value.selection_id,
        "selection_revision_id": value.selection_revision_id,
        "material_model_id": value.material_model_id,
        "material_model_revision_id": value.material_model_revision_id,
        "model_family_id": value.model_family_id,
        "model_schema_version": value.model_schema_version,
        "model_schema_digest": value.model_schema_digest,
        "test_mode": value.test_mode,
        "evaluator_id": value.evaluator_id,
        "evaluator_version": value.evaluator_version,
        "evaluation_mode": value.evaluation_mode,
        "calibrator_id": value.calibrator_id,
        "calibrator_version": value.calibrator_version,
        "parameter_name": value.parameter_name,
        "youngs_modulus_lower_bound_pa": value.youngs_modulus_lower_bound_pa,
        "youngs_modulus_initial_value_pa": value.youngs_modulus_initial_value_pa,
        "youngs_modulus_upper_bound_pa": value.youngs_modulus_upper_bound_pa,
        "normalization_stress_scale_pa": value.normalization_stress_scale_pa,
        "point_weighting": value.point_weighting,
        "objective_aggregation": value.objective_aggregation,
        "x_domain_policy": value.x_domain_policy,
        "missing_data_policy": value.missing_data_policy,
        "multistart_count": value.multistart_count,
        "random_seed": value.random_seed,
        "non_production": value.non_production,
    }


_PLAN_TABLES: TypedRevisionTables[ReferenceLinearElasticCalibrationPlanContent] = (
    TypedRevisionTables(
        aggregate_type=CALIBRATION_PLAN_AGGREGATE_TYPE,
        identity_table=calibration_plan_table,
        revision_table=calibration_plan_revision_table,
        canonical_content=reference_linear_elastic_calibration_plan_canonical,
        content_values=_plan_values,
        identity_values=lambda value: {
            "plan_label": value.plan_label,
            "plan_kind": value.plan_kind,
        },
    )
)


def _revision_columns(table: sa.Table) -> tuple[Any, ...]:
    return (
        table.c.id,
        table.c.aggregate_id,
        table.c.organization_id,
        table.c.project_id,
        table.c.classification,
        table.c.revision_no,
        table.c.based_on_revision_id,
        table.c.schema_id,
        table.c.schema_version,
        table.c.content_hash,
        table.c.created_at,
        table.c.created_by,
        table.c.change_reason,
        table.c.request_id,
        table.c.trace_id,
    )


def _plan_content_columns(table: sa.Table) -> tuple[Any, ...]:
    return (
        table.c.plan_kind,
        table.c.selection_id,
        table.c.selection_revision_id,
        table.c.material_model_id,
        table.c.material_model_revision_id,
        table.c.model_family_id,
        table.c.model_schema_version,
        table.c.model_schema_digest,
        table.c.test_mode,
        table.c.evaluator_id,
        table.c.evaluator_version,
        table.c.evaluation_mode,
        table.c.calibrator_id,
        table.c.calibrator_version,
        table.c.parameter_name,
        table.c.youngs_modulus_lower_bound_pa,
        table.c.youngs_modulus_initial_value_pa,
        table.c.youngs_modulus_upper_bound_pa,
        table.c.normalization_stress_scale_pa,
        table.c.point_weighting,
        table.c.objective_aggregation,
        table.c.x_domain_policy,
        table.c.missing_data_policy,
        table.c.multistart_count,
        table.c.random_seed,
        table.c.non_production,
    )


def _run(row: Any) -> CalibrationRun:
    return CalibrationRun(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        plan_id=cast(UUID, row["plan_id"]),
        plan_revision_id=cast(UUID, row["plan_revision_id"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        dataset_id=cast(UUID, row["dataset_id"]),
        dataset_revision_id=cast(UUID, row["dataset_revision_id"]),
        material_model_id=cast(UUID, row["material_model_id"]),
        material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
        execution_mode=str(row["execution_mode"]),
        reproducibility_level=str(row["reproducibility_level"]),
        environment_digest=str(row["environment_digest"]),
        status=CalibrationRunStatus(str(row["status"])),
        attempt_count=int(row["attempt_count"]),
        candidate_count=int(row["candidate_count"]),
        failure_code=cast(str | None, row["failure_code"]),
        change_reason=str(row["change_reason"]),
        started_at=cast(datetime, row["started_at"]),
        ended_at=cast(datetime | None, row["ended_at"]),
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _attempt(row: Any) -> CalibrationAttempt:
    return CalibrationAttempt(
        id=cast(UUID, row["id"]),
        calibration_run_id=cast(UUID, row["calibration_run_id"]),
        attempt_ordinal=int(row["attempt_ordinal"]),
        initial_youngs_modulus_pa=float(row["initial_youngs_modulus_pa"]),
        random_seed=int(row["random_seed"]),
        status=CalibrationAttemptStatus(str(row["status"])),
        candidate_id=cast(UUID | None, row["candidate_id"]),
        failure_code=cast(str | None, row["failure_code"]),
        started_at=cast(datetime, row["started_at"]),
        ended_at=cast(datetime | None, row["ended_at"]),
    )


def _candidate(row: Any) -> CalibrationCandidate:
    return CalibrationCandidate(
        id=cast(UUID, row["id"]),
        calibration_run_id=cast(UUID, row["calibration_run_id"]),
        calibration_attempt_id=cast(UUID, row["calibration_attempt_id"]),
        attempt_ordinal=int(row["attempt_ordinal"]),
        status=CalibrationCandidateStatus(str(row["status"])),
        candidate_sha256=str(row["candidate_sha256"]),
        youngs_modulus_pa=float(row["youngs_modulus_pa"]),
        objective_total=float(row["objective_total"]),
        residual_root_mean_square_pa=float(row["residual_root_mean_square_pa"]),
        residual_mean_pa=float(row["residual_mean_pa"]),
        bound_sticking=bool(row["bound_sticking"]),
        convergence_reason=str(row["convergence_reason"]),
        identifiability_status=str(row["identifiability_status"]),
        uncertainty_status=str(row["uncertainty_status"]),
        diagnostics_artifact_id=cast(UUID, row["diagnostics_artifact_id"]),
        diagnostics_sha256=str(row["diagnostics_sha256"]),
        diagnostics_point_count=int(row["diagnostics_point_count"]),
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
    )


class SqlAlchemyCalibrationRepository(CalibrationRepository):
    """Concrete typed tables; no generic parameter or result EAV structure is used."""

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
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceLinearElasticCalibrationPlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_PLAN_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _current_plan_statement() -> sa.Select[Any]:
        return sa.select(
            calibration_plan_table.c.id.label("identity_id"),
            calibration_plan_table.c.plan_label.label("plan_label"),
            *_revision_columns(calibration_plan_revision_table),
            *_plan_content_columns(calibration_plan_revision_table),
        ).select_from(
            calibration_plan_table.join(
                calibration_plan_revision_table,
                sa.and_(
                    calibration_plan_revision_table.c.id
                    == calibration_plan_table.c.current_revision_id,
                    calibration_plan_revision_table.c.aggregate_id == calibration_plan_table.c.id,
                    calibration_plan_revision_table.c.organization_id
                    == calibration_plan_table.c.organization_id,
                    calibration_plan_revision_table.c.project_id
                    == calibration_plan_table.c.project_id,
                ),
            )
        )

    @staticmethod
    def _plan_snapshot(row: Any) -> CalibrationPlanSnapshot:
        return CalibrationPlanSnapshot(
            cast(UUID, row["identity_id"]),
            RevisionSnapshot(_record(row), _plan_content(row)),
        )

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> CalibrationPlanSnapshot:
        statement = self._current_plan_statement().where(
            calibration_plan_table.c.id == plan_id,
            calibration_plan_table.c.organization_id == context.organization_id,
            calibration_plan_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise CalibrationNotFound("Calibration Plan is not available") from error
        if row is None:
            raise CalibrationNotFound("Calibration Plan is not visible in the selected tenant")
        return self._plan_snapshot(row)

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearElasticCalibrationPlanContent]:
        table = calibration_plan_revision_table
        statement = (
            sa.select(
                calibration_plan_table.c.plan_label.label("plan_label"),
                *_revision_columns(table),
                *_plan_content_columns(table),
            )
            .select_from(
                calibration_plan_table.join(
                    table,
                    sa.and_(
                        table.c.aggregate_id == calibration_plan_table.c.id,
                        table.c.organization_id == calibration_plan_table.c.organization_id,
                        table.c.project_id == calibration_plan_table.c.project_id,
                    ),
                )
            )
            .where(
                table.c.aggregate_id == plan_id,
                table.c.id == plan_revision_id,
                table.c.organization_id == context.organization_id,
                table.c.project_id == context.project_id,
            )
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise CalibrationNotFound("Calibration Plan revision is not available") from error
        if row is None:
            raise CalibrationNotFound(
                "Calibration Plan revision is not visible in the selected tenant"
            )
        return RevisionSnapshot(_record(row), _plan_content(row))

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[CalibrationPlanSnapshot, ...]:
        statement = (
            self._current_plan_statement()
            .where(
                calibration_plan_table.c.organization_id == context.organization_id,
                calibration_plan_table.c.project_id == context.project_id,
            )
            .order_by(calibration_plan_revision_table.c.created_at.desc())
            .limit(limit)
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._plan_snapshot(row) for row in rows)

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: CalibrationRun,
    ) -> CalibrationRun:
        values = {
            "id": run.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
            "plan_id": run.plan_id,
            "plan_revision_id": run.plan_revision_id,
            "selection_id": run.selection_id,
            "selection_revision_id": run.selection_revision_id,
            "dataset_id": run.dataset_id,
            "dataset_revision_id": run.dataset_revision_id,
            "material_model_id": run.material_model_id,
            "material_model_revision_id": run.material_model_revision_id,
            "execution_mode": run.execution_mode,
            "reproducibility_level": run.reproducibility_level,
            "environment_digest": run.environment_digest,
            "status": run.status.value,
            "attempt_count": run.attempt_count,
            "candidate_count": run.candidate_count,
            "failure_code": run.failure_code,
            "change_reason": run.change_reason,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "created_by": run.created_by,
            "request_id": run.request_id,
            "trace_id": run.trace_id,
        }
        with self._session(context, decision) as session:
            try:
                row = session.execute(
                    sa.insert(calibration_run_table).values(**values).returning(calibration_run_table)
                ).mappings().one()
            except IntegrityError as error:
                raise CalibrationConflict(
                    "Calibration Run conflicts with immutable Plan inputs"
                ) from error
        return _run(row)

    def create_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt: CalibrationAttempt,
    ) -> CalibrationAttempt:
        values = {
            "id": attempt.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": self.get_run(
                context=context, decision=decision, run_id=attempt.calibration_run_id
            ).classification.value,
            "calibration_run_id": attempt.calibration_run_id,
            "attempt_ordinal": attempt.attempt_ordinal,
            "initial_youngs_modulus_pa": attempt.initial_youngs_modulus_pa,
            "random_seed": attempt.random_seed,
            "status": attempt.status.value,
            "candidate_id": attempt.candidate_id,
            "failure_code": attempt.failure_code,
            "started_at": attempt.started_at,
            "ended_at": attempt.ended_at,
        }
        with self._session(context, decision) as session:
            try:
                row = session.execute(
                    sa.insert(calibration_attempt_table)
                    .values(**values)
                    .returning(calibration_attempt_table)
                ).mappings().one()
            except IntegrityError as error:
                raise CalibrationConflict(
                    "Calibration Attempt conflicts with immutable Run state"
                ) from error
        return _attempt(row)

    def _terminal_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        values: dict[str, object],
    ) -> CalibrationAttempt:
        statement = (
            sa.update(calibration_attempt_table)
            .where(
                calibration_attempt_table.c.id == attempt_id,
                calibration_attempt_table.c.organization_id == context.organization_id,
                calibration_attempt_table.c.project_id == context.project_id,
                calibration_attempt_table.c.status == CalibrationAttemptStatus.EXECUTING.value,
            )
            .values(**values, ended_at=datetime.now(UTC))
            .returning(calibration_attempt_table)
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CalibrationConflict("Calibration Attempt is not executing or is not visible")
        return _attempt(row)

    def succeed_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        candidate_id: UUID,
    ) -> CalibrationAttempt:
        return self._terminal_attempt(
            context=context,
            decision=decision,
            attempt_id=attempt_id,
            values={
                "status": CalibrationAttemptStatus.SUCCEEDED.value,
                "candidate_id": candidate_id,
                "failure_code": None,
            },
        )

    def fail_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        failure_code: str,
    ) -> CalibrationAttempt:
        return self._terminal_attempt(
            context=context,
            decision=decision,
            attempt_id=attempt_id,
            values={
                "status": CalibrationAttemptStatus.FAILED.value,
                "candidate_id": None,
                "failure_code": failure_code,
            },
        )

    def create_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate: CalibrationCandidate,
    ) -> CalibrationCandidate:
        run = self.get_run(context=context, decision=decision, run_id=candidate.calibration_run_id)
        values = {
            "id": candidate.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
            "calibration_run_id": candidate.calibration_run_id,
            "calibration_attempt_id": candidate.calibration_attempt_id,
            "attempt_ordinal": candidate.attempt_ordinal,
            "status": candidate.status.value,
            "candidate_sha256": candidate.candidate_sha256,
            "youngs_modulus_pa": candidate.youngs_modulus_pa,
            "objective_total": candidate.objective_total,
            "residual_root_mean_square_pa": candidate.residual_root_mean_square_pa,
            "residual_mean_pa": candidate.residual_mean_pa,
            "bound_sticking": candidate.bound_sticking,
            "convergence_reason": candidate.convergence_reason,
            "identifiability_status": candidate.identifiability_status,
            "uncertainty_status": candidate.uncertainty_status,
            "diagnostics_artifact_id": candidate.diagnostics_artifact_id,
            "diagnostics_sha256": candidate.diagnostics_sha256,
            "diagnostics_point_count": candidate.diagnostics_point_count,
            "created_at": candidate.created_at,
            "created_by": candidate.created_by,
        }
        with self._session(context, decision) as session:
            try:
                row = session.execute(
                    sa.insert(calibration_candidate_table)
                    .values(**values)
                    .returning(calibration_candidate_table)
                ).mappings().one()
            except IntegrityError as error:
                raise CalibrationConflict(
                    "Calibration Candidate conflicts with immutable Attempt"
                ) from error
        return _candidate(row)

    def _terminal_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        values: dict[str, object],
    ) -> CalibrationRun:
        statement = (
            sa.update(calibration_run_table)
            .where(
                calibration_run_table.c.id == run_id,
                calibration_run_table.c.organization_id == context.organization_id,
                calibration_run_table.c.project_id == context.project_id,
                calibration_run_table.c.status == CalibrationRunStatus.EXECUTING.value,
            )
            .values(**values, ended_at=datetime.now(UTC))
            .returning(calibration_run_table)
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CalibrationConflict("Calibration Run is not executing or is not visible")
        return _run(row)

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        candidate_count: int,
    ) -> CalibrationRun:
        return self._terminal_run(
            context=context,
            decision=decision,
            run_id=run_id,
            values={
                "status": CalibrationRunStatus.SUCCEEDED.value,
                "candidate_count": candidate_count,
                "failure_code": None,
            },
        )

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> CalibrationRun:
        count = len(self.list_candidates(context=context, decision=decision, run_id=run_id))
        return self._terminal_run(
            context=context,
            decision=decision,
            run_id=run_id,
            values={
                "status": CalibrationRunStatus.FAILED.value,
                "candidate_count": count,
                "failure_code": failure_code,
            },
        )

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> CalibrationRun:
        statement = sa.select(calibration_run_table).where(
            calibration_run_table.c.id == run_id,
            calibration_run_table.c.organization_id == context.organization_id,
            calibration_run_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise CalibrationNotFound("Calibration Run is not available") from error
        if row is None:
            raise CalibrationNotFound("Calibration Run is not visible in the selected tenant")
        return _run(row)

    def list_attempts(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> tuple[CalibrationAttempt, ...]:
        statement = (
            sa.select(calibration_attempt_table)
            .where(
                calibration_attempt_table.c.calibration_run_id == run_id,
                calibration_attempt_table.c.organization_id == context.organization_id,
                calibration_attempt_table.c.project_id == context.project_id,
            )
            .order_by(calibration_attempt_table.c.attempt_ordinal.asc())
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(_attempt(row) for row in rows)

    def list_candidates(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> tuple[CalibrationCandidate, ...]:
        statement = (
            sa.select(calibration_candidate_table)
            .where(
                calibration_candidate_table.c.calibration_run_id == run_id,
                calibration_candidate_table.c.organization_id == context.organization_id,
                calibration_candidate_table.c.project_id == context.project_id,
            )
            .order_by(calibration_candidate_table.c.objective_total.asc())
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(_candidate(row) for row in rows)

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> CalibrationCandidate:
        statement = sa.select(calibration_candidate_table).where(
            calibration_candidate_table.c.id == candidate_id,
            calibration_candidate_table.c.organization_id == context.organization_id,
            calibration_candidate_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise CalibrationNotFound("Calibration Candidate is not available") from error
        if row is None:
            raise CalibrationNotFound("Calibration Candidate is not visible in the selected tenant")
        return _candidate(row)
