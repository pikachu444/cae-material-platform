"""RLS-bound persistence for bounded reference Prony calibration."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
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
from cmp.modules.modeling.application.prony_calibration import (
    PRONY_CALIBRATION_PLAN_AGGREGATE_TYPE,
    PersistedPronyCandidate,
    PronyCalibrationConflict,
    PronyCalibrationNotFound,
    PronyCalibrationRepository,
    PronyCalibrationRun,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_prony_calibration import (
    PronyCalibrationCandidate,
    PronyParameterPlan,
    ReferencePronyCalibrationPlanContent,
)
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
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

prony_plan_table = sa.Table(
    "prony_calibration_plan",
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

_revision_columns = (
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
)

prony_plan_revision_table = sa.Table(
    "prony_calibration_plan_revision",
    metadata,
    *_revision_columns,
    sa.Column("plan_kind", sa.String(100), nullable=False),
    sa.Column("plan_label", sa.String(160), nullable=False),
    sa.Column("input_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("input_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("total_g_lower", sa.Double(), nullable=False),
    sa.Column("total_g_initial", sa.Double(), nullable=False),
    sa.Column("total_g_upper", sa.Double(), nullable=False),
    sa.Column("fast_fraction_lower", sa.Double(), nullable=False),
    sa.Column("fast_fraction_initial", sa.Double(), nullable=False),
    sa.Column("fast_fraction_upper", sa.Double(), nullable=False),
    sa.Column("fast_tau_lower_s", sa.Double(), nullable=False),
    sa.Column("fast_tau_initial_s", sa.Double(), nullable=False),
    sa.Column("fast_tau_upper_s", sa.Double(), nullable=False),
    sa.Column("slow_tau_lower_s", sa.Double(), nullable=False),
    sa.Column("slow_tau_initial_s", sa.Double(), nullable=False),
    sa.Column("slow_tau_upper_s", sa.Double(), nullable=False),
    sa.Column("normalization_modulus_pa", sa.Double(), nullable=False),
    sa.Column("multistart_count", sa.SmallInteger(), nullable=False),
    sa.Column("random_seed", sa.BigInteger(), nullable=False),
    sa.Column("maximum_function_evaluations", sa.Integer(), nullable=False),
    sa.Column("ftol", sa.Double(), nullable=False),
    sa.Column("xtol", sa.Double(), nullable=False),
    sa.Column("gtol", sa.Double(), nullable=False),
    sa.Column("test_mode_adapter_id", sa.String(255), nullable=False),
    sa.Column("evaluator_id", sa.String(255), nullable=False),
    sa.Column("objective_engine_id", sa.String(255), nullable=False),
    sa.Column("optimizer_adapter_id", sa.String(255), nullable=False),
    sa.Column("residual_definition", sa.String(100), nullable=False),
    sa.Column("point_weighting", sa.String(32), nullable=False),
    sa.Column("objective_aggregation", sa.String(100), nullable=False),
    sa.Column("missing_data_policy", sa.String(32), nullable=False),
    sa.Column("optimizer_method", sa.String(32), nullable=False),
    sa.Column("rng_algorithm", sa.String(100), nullable=False),
    sa.Column("term_count", sa.SmallInteger(), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="modeling",
)

prony_run_table = sa.Table(
    "prony_calibration_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("input_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("input_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("environment_digest", sa.CHAR(64), nullable=False),
    sa.Column("attempt_count", sa.SmallInteger(), nullable=False),
    sa.Column("candidate_count", sa.SmallInteger(), nullable=False),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("change_reason", sa.Text(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="modeling",
)

prony_attempt_table = sa.Table(
    "prony_calibration_attempt",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("attempt_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("initial_total_g_ratio", sa.Double(), nullable=False),
    sa.Column("initial_fast_term_fraction", sa.Double(), nullable=False),
    sa.Column("initial_fast_tau_s", sa.Double(), nullable=False),
    sa.Column("initial_slow_tau_s", sa.Double(), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("candidate_id", sa.Uuid(), nullable=False),
    schema="modeling",
)

prony_candidate_table = sa.Table(
    "prony_calibration_candidate",
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
    sa.Column("total_g_ratio", sa.Double(), nullable=False),
    sa.Column("fast_term_fraction", sa.Double(), nullable=False),
    sa.Column("fast_g_ratio", sa.Double(), nullable=False),
    sa.Column("slow_g_ratio", sa.Double(), nullable=False),
    sa.Column("fast_relaxation_time_s", sa.Double(), nullable=False),
    sa.Column("slow_relaxation_time_s", sa.Double(), nullable=False),
    sa.Column("objective_total", sa.Double(), nullable=False),
    sa.Column("residual_root_mean_square_pa", sa.Double(), nullable=False),
    sa.Column("residual_mean_pa", sa.Double(), nullable=False),
    sa.Column("convergence_status_code", sa.SmallInteger(), nullable=False),
    sa.Column("convergence_reason", sa.String(255), nullable=False),
    sa.Column("function_evaluations", sa.Integer(), nullable=False),
    sa.Column("jacobian_evaluations", sa.Integer(), nullable=True),
    sa.Column("optimality", sa.Double(), nullable=False),
    sa.Column("parameter_at_bound", sa.Boolean(), nullable=False),
    sa.Column("identifiability_status", sa.String(100), nullable=False),
    sa.Column("uncertainty_status", sa.String(100), nullable=False),
    sa.Column("diagnostics_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("diagnostics_sha256", sa.CHAR(64), nullable=False),
    sa.Column("diagnostics_point_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="modeling",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=PRONY_CALIBRATION_PLAN_AGGREGATE_TYPE,
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


def _parameter(
    name: str,
    unit: str,
    transform: str,
    prefix: str,
    row: Any,
    *,
    seconds_suffix: bool = False,
) -> PronyParameterPlan:
    suffix = "_s" if seconds_suffix else ""
    return PronyParameterPlan(
        name,
        unit,
        float(row[f"{prefix}_lower{suffix}"]),
        float(row[f"{prefix}_initial{suffix}"]),
        float(row[f"{prefix}_upper{suffix}"]),
        transform,
    )


def _content(row: Any) -> ReferencePronyCalibrationPlanContent:
    return ReferencePronyCalibrationPlanContent(
        plan_label=str(row["plan_label"]),
        input_dataset_id=cast(UUID, row["input_dataset_id"]),
        input_dataset_revision_id=cast(UUID, row["input_dataset_revision_id"]),
        baseline_model_id=cast(UUID, row["baseline_model_id"]),
        baseline_model_revision_id=cast(UUID, row["baseline_model_revision_id"]),
        total_g_ratio=_parameter("total_g_ratio", "1", "none", "total_g", row),
        fast_term_fraction=_parameter(
            "fast_term_fraction", "1", "none", "fast_fraction", row
        ),
        fast_relaxation_time_s=_parameter(
            "fast_relaxation_time_s",
            "s",
            "log",
            "fast_tau",
            row,
            seconds_suffix=True,
        ),
        slow_relaxation_time_s=_parameter(
            "slow_relaxation_time_s",
            "s",
            "log",
            "slow_tau",
            row,
            seconds_suffix=True,
        ),
        normalization_modulus_pa=float(row["normalization_modulus_pa"]),
        multistart_count=int(row["multistart_count"]),
        random_seed=int(row["random_seed"]),
        maximum_function_evaluations=int(row["maximum_function_evaluations"]),
        ftol=float(row["ftol"]),
        xtol=float(row["xtol"]),
        gtol=float(row["gtol"]),
        plan_kind=str(row["plan_kind"]),
        test_mode_adapter_id=str(row["test_mode_adapter_id"]),
        evaluator_id=str(row["evaluator_id"]),
        objective_engine_id=str(row["objective_engine_id"]),
        optimizer_adapter_id=str(row["optimizer_adapter_id"]),
        residual_definition=str(row["residual_definition"]),
        point_weighting=str(row["point_weighting"]),
        objective_aggregation=str(row["objective_aggregation"]),
        missing_data_policy=str(row["missing_data_policy"]),
        optimizer_method=str(row["optimizer_method"]),
        rng_algorithm=str(row["rng_algorithm"]),
        term_count=int(row["term_count"]),
        non_production=bool(row["non_production"]),
    )


def _values(value: ReferencePronyCalibrationPlanContent) -> dict[str, object]:
    result: dict[str, object] = {
        "plan_kind": value.plan_kind,
        "plan_label": value.plan_label,
        "input_dataset_id": value.input_dataset_id,
        "input_dataset_revision_id": value.input_dataset_revision_id,
        "baseline_model_id": value.baseline_model_id,
        "baseline_model_revision_id": value.baseline_model_revision_id,
        "normalization_modulus_pa": value.normalization_modulus_pa,
        "multistart_count": value.multistart_count,
        "random_seed": value.random_seed,
        "maximum_function_evaluations": value.maximum_function_evaluations,
        "ftol": value.ftol,
        "xtol": value.xtol,
        "gtol": value.gtol,
        "test_mode_adapter_id": value.test_mode_adapter_id,
        "evaluator_id": value.evaluator_id,
        "objective_engine_id": value.objective_engine_id,
        "optimizer_adapter_id": value.optimizer_adapter_id,
        "residual_definition": value.residual_definition,
        "point_weighting": value.point_weighting,
        "objective_aggregation": value.objective_aggregation,
        "missing_data_policy": value.missing_data_policy,
        "optimizer_method": value.optimizer_method,
        "rng_algorithm": value.rng_algorithm,
        "term_count": value.term_count,
        "non_production": value.non_production,
    }
    for prefix, parameter, suffix in (
        ("total_g", value.total_g_ratio, ""),
        ("fast_fraction", value.fast_term_fraction, ""),
        ("fast_tau", value.fast_relaxation_time_s, "_s"),
        ("slow_tau", value.slow_relaxation_time_s, "_s"),
    ):
        result[f"{prefix}_lower{suffix}"] = parameter.lower
        result[f"{prefix}_initial{suffix}"] = parameter.initial
        result[f"{prefix}_upper{suffix}"] = parameter.upper
    return result


_TABLES = TypedRevisionTables(
    aggregate_type=PRONY_CALIBRATION_PLAN_AGGREGATE_TYPE,
    identity_table=prony_plan_table,
    revision_table=prony_plan_revision_table,
    canonical_content=lambda value: value.canonical(),
    content_values=_values,
    identity_values=lambda value: {
        "plan_label": value.plan_label,
        "plan_kind": value.plan_kind,
    },
)


def _candidate(row: Any) -> PersistedPronyCandidate:
    value = PronyCalibrationCandidate(
        attempt_ordinal=int(row["attempt_ordinal"]),
        initial_values=(
            float(row["initial_total_g_ratio"]),
            float(row["initial_fast_term_fraction"]),
            float(row["initial_fast_tau_s"]),
            float(row["initial_slow_tau_s"]),
        ),
        total_g_ratio=float(row["total_g_ratio"]),
        fast_term_fraction=float(row["fast_term_fraction"]),
        fast_g_ratio=float(row["fast_g_ratio"]),
        slow_g_ratio=float(row["slow_g_ratio"]),
        fast_relaxation_time_s=float(row["fast_relaxation_time_s"]),
        slow_relaxation_time_s=float(row["slow_relaxation_time_s"]),
        objective_total=float(row["objective_total"]),
        residual_root_mean_square_pa=float(row["residual_root_mean_square_pa"]),
        residual_mean_pa=float(row["residual_mean_pa"]),
        status=str(row["status"]),
        convergence_status_code=int(row["convergence_status_code"]),
        convergence_reason=str(row["convergence_reason"]),
        function_evaluations=int(row["function_evaluations"]),
        jacobian_evaluations=(
            int(row["jacobian_evaluations"])
            if row["jacobian_evaluations"] is not None
            else None
        ),
        optimality=float(row["optimality"]),
        parameter_at_bound=bool(row["parameter_at_bound"]),
        identifiability_status=str(row["identifiability_status"]),
        uncertainty_status=str(row["uncertainty_status"]),
        predicted_modulus_pa=(),
        residual_pa=(),
        candidate_sha256=str(row["candidate_sha256"]),
    )
    return PersistedPronyCandidate(
        id=cast(UUID, row["id"]),
        attempt_id=cast(UUID, row["calibration_attempt_id"]),
        calibration_run_id=cast(UUID, row["calibration_run_id"]),
        value=value,
        diagnostics_artifact_id=cast(UUID, row["diagnostics_artifact_id"]),
        diagnostics_sha256=str(row["diagnostics_sha256"]),
        diagnostics_point_count=int(row["diagnostics_point_count"]),
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
    )


class SqlAlchemyPronyCalibrationRepository(PronyCalibrationRepository):
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
    ) -> RevisionStore[ReferencePronyCalibrationPlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferencePronyCalibrationPlanContent]:
        statement = sa.select(prony_plan_revision_table).where(
            prony_plan_revision_table.c.aggregate_id == plan_id,
            prony_plan_revision_table.c.id == plan_revision_id,
            prony_plan_revision_table.c.organization_id == context.organization_id,
            prony_plan_revision_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise PronyCalibrationNotFound("Prony calibration Plan revision is not visible")
            return RevisionSnapshot(_record(row), _content(row))

    @staticmethod
    def _candidate_statement() -> sa.Select[Any]:
        return sa.select(
            prony_candidate_table,
            prony_attempt_table.c.initial_total_g_ratio,
            prony_attempt_table.c.initial_fast_term_fraction,
            prony_attempt_table.c.initial_fast_tau_s,
            prony_attempt_table.c.initial_slow_tau_s,
        ).join(
            prony_attempt_table,
            sa.and_(
                prony_attempt_table.c.id
                == prony_candidate_table.c.calibration_attempt_id,
                prony_attempt_table.c.organization_id
                == prony_candidate_table.c.organization_id,
                prony_attempt_table.c.project_id == prony_candidate_table.c.project_id,
            ),
        )

    def save_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: PronyCalibrationRun,
    ) -> PronyCalibrationRun:
        scope = {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
        }
        try:
            with self._session(context, decision) as session:
                session.execute(
                    sa.insert(prony_run_table).values(
                        **scope,
                        id=run.id,
                        plan_id=run.plan_id,
                        plan_revision_id=run.plan_revision_id,
                        input_dataset_id=run.input_dataset_id,
                        input_dataset_revision_id=run.input_dataset_revision_id,
                        baseline_model_id=run.baseline_model_id,
                        baseline_model_revision_id=run.baseline_model_revision_id,
                        status=run.status.value,
                        environment_digest=run.environment_digest,
                        attempt_count=run.attempt_count,
                        candidate_count=run.candidate_count,
                        failure_code=run.failure_code,
                        change_reason=run.change_reason,
                        started_at=run.started_at,
                        ended_at=run.ended_at,
                        created_by=run.created_by,
                        request_id=run.request_id,
                        trace_id=run.trace_id,
                    )
                )
                for candidate in run.candidates:
                    value = candidate.value
                    session.execute(
                        sa.insert(prony_attempt_table).values(
                            **scope,
                            id=candidate.attempt_id,
                            calibration_run_id=run.id,
                            attempt_ordinal=value.attempt_ordinal,
                            initial_total_g_ratio=value.initial_values[0],
                            initial_fast_term_fraction=value.initial_values[1],
                            initial_fast_tau_s=value.initial_values[2],
                            initial_slow_tau_s=value.initial_values[3],
                            status=value.status,
                            candidate_id=candidate.id,
                        )
                    )
                    session.execute(
                        sa.insert(prony_candidate_table).values(
                            **scope,
                            id=candidate.id,
                            calibration_run_id=run.id,
                            calibration_attempt_id=candidate.attempt_id,
                            attempt_ordinal=value.attempt_ordinal,
                            status=value.status,
                            candidate_sha256=value.candidate_sha256,
                            total_g_ratio=value.total_g_ratio,
                            fast_term_fraction=value.fast_term_fraction,
                            fast_g_ratio=value.fast_g_ratio,
                            slow_g_ratio=value.slow_g_ratio,
                            fast_relaxation_time_s=value.fast_relaxation_time_s,
                            slow_relaxation_time_s=value.slow_relaxation_time_s,
                            objective_total=value.objective_total,
                            residual_root_mean_square_pa=value.residual_root_mean_square_pa,
                            residual_mean_pa=value.residual_mean_pa,
                            convergence_status_code=value.convergence_status_code,
                            convergence_reason=value.convergence_reason,
                            function_evaluations=value.function_evaluations,
                            jacobian_evaluations=value.jacobian_evaluations,
                            optimality=value.optimality,
                            parameter_at_bound=value.parameter_at_bound,
                            identifiability_status=value.identifiability_status,
                            uncertainty_status=value.uncertainty_status,
                            diagnostics_artifact_id=candidate.diagnostics_artifact_id,
                            diagnostics_sha256=candidate.diagnostics_sha256,
                            diagnostics_point_count=candidate.diagnostics_point_count,
                            created_at=candidate.created_at,
                            created_by=candidate.created_by,
                        )
                    )
            return run
        except (IntegrityError, DBAPIError) as error:
            raise PronyCalibrationConflict(
                "Prony calibration Run could not be persisted"
            ) from error

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> PronyCalibrationRun:
        with self._session(context, decision) as session:
            row = session.execute(
                sa.select(prony_run_table).where(
                    prony_run_table.c.id == run_id,
                    prony_run_table.c.organization_id == context.organization_id,
                    prony_run_table.c.project_id == context.project_id,
                )
            ).mappings().one_or_none()
            if row is None:
                raise PronyCalibrationNotFound("Prony calibration Run is not visible")
            candidates = tuple(
                _candidate(value)
                for value in session.execute(
                    self._candidate_statement()
                    .where(prony_candidate_table.c.calibration_run_id == run_id)
                    .order_by(prony_candidate_table.c.attempt_ordinal)
                ).mappings()
            )
            return PronyCalibrationRun(
                id=cast(UUID, row["id"]),
                classification=DataClassification(str(row["classification"])),
                plan_id=cast(UUID, row["plan_id"]),
                plan_revision_id=cast(UUID, row["plan_revision_id"]),
                input_dataset_id=cast(UUID, row["input_dataset_id"]),
                input_dataset_revision_id=cast(UUID, row["input_dataset_revision_id"]),
                baseline_model_id=cast(UUID, row["baseline_model_id"]),
                baseline_model_revision_id=cast(UUID, row["baseline_model_revision_id"]),
                status=ProcessingRunStatus(str(row["status"])),
                environment_digest=str(row["environment_digest"]),
                attempt_count=int(row["attempt_count"]),
                candidate_count=int(row["candidate_count"]),
                failure_code=cast(str | None, row["failure_code"]),
                change_reason=str(row["change_reason"]),
                started_at=cast(datetime, row["started_at"]),
                ended_at=cast(datetime, row["ended_at"]),
                created_by=cast(UUID, row["created_by"]),
                request_id=cast(UUID, row["request_id"]),
                trace_id=str(row["trace_id"]),
                candidates=candidates,
            )

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> PersistedPronyCandidate:
        with self._session(context, decision) as session:
            row = session.execute(
                self._candidate_statement().where(
                    prony_candidate_table.c.id == candidate_id,
                    prony_candidate_table.c.organization_id == context.organization_id,
                    prony_candidate_table.c.project_id == context.project_id,
                )
            ).mappings().one_or_none()
            if row is None:
                raise PronyCalibrationNotFound("Prony calibration Candidate is not visible")
            return _candidate(row)
