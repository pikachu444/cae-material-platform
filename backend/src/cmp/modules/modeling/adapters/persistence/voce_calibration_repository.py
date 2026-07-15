"""RLS-bound PostgreSQL persistence for bounded reference Voce calibration."""

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
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.application.voce_calibration import (
    VOCE_CALIBRATION_PLAN_AGGREGATE_TYPE,
    VoceCalibrationAttempt,
    VoceCalibrationCandidate,
    VoceCalibrationConflict,
    VoceCalibrationNotFound,
    VoceCalibrationPlanSnapshot,
    VoceCalibrationRepository,
    VoceCalibrationRun,
)
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    CalibrationAttemptStatus,
    CalibrationCandidateStatus,
    CalibrationRunStatus,
)
from cmp.modules.modeling.domain.reference_voce_calibration import (
    ReferenceVoceCalibrationPlanContent,
    VoceObjectiveTerm,
    VoceParameterPlan,
    reference_voce_calibration_plan_canonical,
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

voce_plan_table = sa.Table(
    "voce_calibration_plan",
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

_revision_columns_spec = (
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

voce_plan_revision_table = sa.Table(
    "voce_calibration_plan_revision",
    metadata,
    *_revision_columns_spec,
    sa.Column("plan_kind", sa.String(100), nullable=False),
    sa.Column("calibration_input_scope_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_input_scope_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_revision_id", sa.Uuid(), nullable=False),
    sa.Column("youngs_modulus_pa", sa.Double(), nullable=False),
    sa.Column("sigma_0_lower_pa", sa.Double(), nullable=False),
    sa.Column("sigma_0_initial_pa", sa.Double(), nullable=False),
    sa.Column("sigma_0_upper_pa", sa.Double(), nullable=False),
    sa.Column("sigma_0_scale_pa", sa.Double(), nullable=False),
    sa.Column("q_lower_pa", sa.Double(), nullable=False),
    sa.Column("q_initial_pa", sa.Double(), nullable=False),
    sa.Column("q_upper_pa", sa.Double(), nullable=False),
    sa.Column("q_scale_pa", sa.Double(), nullable=False),
    sa.Column("b_lower", sa.Double(), nullable=False),
    sa.Column("b_initial", sa.Double(), nullable=False),
    sa.Column("b_upper", sa.Double(), nullable=False),
    sa.Column("b_scale", sa.Double(), nullable=False),
    sa.Column("normalization_stress_scale_pa", sa.Double(), nullable=False),
    sa.Column("multistart_count", sa.SmallInteger(), nullable=False),
    sa.Column("random_seed", sa.BigInteger(), nullable=False),
    sa.Column("maximum_function_evaluations", sa.Integer(), nullable=False),
    sa.Column("ftol", sa.Double(), nullable=False),
    sa.Column("xtol", sa.Double(), nullable=False),
    sa.Column("gtol", sa.Double(), nullable=False),
    sa.Column("model_family_id", sa.String(255), nullable=False),
    sa.Column("test_mode_adapter_id", sa.String(255), nullable=False),
    sa.Column("evaluator_id", sa.String(255), nullable=False),
    sa.Column("objective_engine_id", sa.String(255), nullable=False),
    sa.Column("optimizer_adapter_id", sa.String(255), nullable=False),
    sa.Column("evaluation_mode", sa.String(64), nullable=False),
    sa.Column("residual_definition", sa.String(100), nullable=False),
    sa.Column("specimen_weighting", sa.String(100), nullable=False),
    sa.Column("point_weighting", sa.String(100), nullable=False),
    sa.Column("objective_aggregation", sa.String(100), nullable=False),
    sa.Column("x_domain_policy", sa.String(100), nullable=False),
    sa.Column("missing_data_policy", sa.String(32), nullable=False),
    sa.Column("optimizer_method", sa.String(32), nullable=False),
    sa.Column("rng_algorithm", sa.String(100), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="modeling",
)

voce_run_table = sa.Table(
    "voce_calibration_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_input_scope_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_input_scope_revision_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_revision_id", sa.Uuid(), nullable=False),
    sa.Column("source_curve_count", sa.SmallInteger(), nullable=False),
    sa.Column("execution_mode", sa.String(64), nullable=False),
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

voce_attempt_table = sa.Table(
    "voce_calibration_attempt",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("attempt_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("initial_sigma_0_pa", sa.Double(), nullable=False),
    sa.Column("initial_q_pa", sa.Double(), nullable=False),
    sa.Column("initial_b", sa.Double(), nullable=False),
    sa.Column("random_seed", sa.BigInteger(), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("candidate_id", sa.Uuid(), nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    schema="modeling",
)

voce_candidate_table = sa.Table(
    "voce_calibration_candidate",
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
    sa.Column("sigma_0_pa", sa.Double(), nullable=False),
    sa.Column("q_pa", sa.Double(), nullable=False),
    sa.Column("b", sa.Double(), nullable=False),
    sa.Column("objective_total", sa.Double(), nullable=False),
    sa.Column("residual_root_mean_square_pa", sa.Double(), nullable=False),
    sa.Column("residual_mean_pa", sa.Double(), nullable=False),
    sa.Column("sigma_0_at_bound", sa.Boolean(), nullable=False),
    sa.Column("q_at_bound", sa.Boolean(), nullable=False),
    sa.Column("b_at_bound", sa.Boolean(), nullable=False),
    sa.Column("convergence_status_code", sa.SmallInteger(), nullable=False),
    sa.Column("convergence_reason", sa.String(255), nullable=False),
    sa.Column("function_evaluations", sa.Integer(), nullable=False),
    sa.Column("jacobian_evaluations", sa.Integer(), nullable=True),
    sa.Column("optimality", sa.Double(), nullable=False),
    sa.Column("warning_at_bound", sa.Boolean(), nullable=False),
    sa.Column("warning_nonconvergence", sa.Boolean(), nullable=False),
    sa.Column("identifiability_status", sa.String(100), nullable=False),
    sa.Column("uncertainty_status", sa.String(100), nullable=False),
    sa.Column("diagnostics_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("diagnostics_sha256", sa.CHAR(64), nullable=False),
    sa.Column("diagnostics_point_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="modeling",
)

voce_objective_term_table = sa.Table(
    "voce_calibration_objective_term",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("candidate_id", sa.Uuid(), nullable=False),
    sa.Column("member_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("point_count", sa.Integer(), nullable=False),
    sa.Column("mean_normalized_squared_residual", sa.Double(), nullable=False),
    schema="modeling",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=VOCE_CALIBRATION_PLAN_AGGREGATE_TYPE,
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


def _plan_content(row: Any) -> ReferenceVoceCalibrationPlanContent:
    return ReferenceVoceCalibrationPlanContent(
        plan_label=str(row["plan_label"]),
        calibration_input_scope_id=cast(UUID, row["calibration_input_scope_id"]),
        calibration_input_scope_revision_id=cast(UUID, row["calibration_input_scope_revision_id"]),
        material_state_id=cast(UUID, row["material_state_id"]),
        material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
        property_set_id=cast(UUID, row["property_set_id"]),
        property_set_revision_id=cast(UUID, row["property_set_revision_id"]),
        youngs_modulus_pa=float(row["youngs_modulus_pa"]),
        sigma_0=VoceParameterPlan(
            "sigma_0_pa",
            "Pa",
            float(row["sigma_0_lower_pa"]),
            float(row["sigma_0_initial_pa"]),
            float(row["sigma_0_upper_pa"]),
            float(row["sigma_0_scale_pa"]),
        ),
        q=VoceParameterPlan(
            "q_pa",
            "Pa",
            float(row["q_lower_pa"]),
            float(row["q_initial_pa"]),
            float(row["q_upper_pa"]),
            float(row["q_scale_pa"]),
        ),
        b=VoceParameterPlan(
            "b",
            "1",
            float(row["b_lower"]),
            float(row["b_initial"]),
            float(row["b_upper"]),
            float(row["b_scale"]),
        ),
        normalization_stress_scale_pa=float(row["normalization_stress_scale_pa"]),
        multistart_count=int(row["multistart_count"]),
        random_seed=int(row["random_seed"]),
        maximum_function_evaluations=int(row["maximum_function_evaluations"]),
        ftol=float(row["ftol"]),
        xtol=float(row["xtol"]),
        gtol=float(row["gtol"]),
        plan_kind=str(row["plan_kind"]),
        model_family_id=str(row["model_family_id"]),
        test_mode_adapter_id=str(row["test_mode_adapter_id"]),
        evaluator_id=str(row["evaluator_id"]),
        objective_engine_id=str(row["objective_engine_id"]),
        optimizer_adapter_id=str(row["optimizer_adapter_id"]),
        evaluation_mode=str(row["evaluation_mode"]),
        residual_definition=str(row["residual_definition"]),
        specimen_weighting=str(row["specimen_weighting"]),
        point_weighting=str(row["point_weighting"]),
        objective_aggregation=str(row["objective_aggregation"]),
        x_domain_policy=str(row["x_domain_policy"]),
        missing_data_policy=str(row["missing_data_policy"]),
        optimizer_method=str(row["optimizer_method"]),
        rng_algorithm=str(row["rng_algorithm"]),
        non_production=bool(row["non_production"]),
    )


def _plan_values(value: ReferenceVoceCalibrationPlanContent) -> dict[str, object]:
    return {
        "plan_kind": value.plan_kind,
        "calibration_input_scope_id": value.calibration_input_scope_id,
        "calibration_input_scope_revision_id": value.calibration_input_scope_revision_id,
        "material_state_id": value.material_state_id,
        "material_state_revision_id": value.material_state_revision_id,
        "property_set_id": value.property_set_id,
        "property_set_revision_id": value.property_set_revision_id,
        "youngs_modulus_pa": value.youngs_modulus_pa,
        "sigma_0_lower_pa": value.sigma_0.lower,
        "sigma_0_initial_pa": value.sigma_0.initial,
        "sigma_0_upper_pa": value.sigma_0.upper,
        "sigma_0_scale_pa": value.sigma_0.scale,
        "q_lower_pa": value.q.lower,
        "q_initial_pa": value.q.initial,
        "q_upper_pa": value.q.upper,
        "q_scale_pa": value.q.scale,
        "b_lower": value.b.lower,
        "b_initial": value.b.initial,
        "b_upper": value.b.upper,
        "b_scale": value.b.scale,
        "normalization_stress_scale_pa": value.normalization_stress_scale_pa,
        "multistart_count": value.multistart_count,
        "random_seed": value.random_seed,
        "maximum_function_evaluations": value.maximum_function_evaluations,
        "ftol": value.ftol,
        "xtol": value.xtol,
        "gtol": value.gtol,
        "model_family_id": value.model_family_id,
        "test_mode_adapter_id": value.test_mode_adapter_id,
        "evaluator_id": value.evaluator_id,
        "objective_engine_id": value.objective_engine_id,
        "optimizer_adapter_id": value.optimizer_adapter_id,
        "evaluation_mode": value.evaluation_mode,
        "residual_definition": value.residual_definition,
        "specimen_weighting": value.specimen_weighting,
        "point_weighting": value.point_weighting,
        "objective_aggregation": value.objective_aggregation,
        "x_domain_policy": value.x_domain_policy,
        "missing_data_policy": value.missing_data_policy,
        "optimizer_method": value.optimizer_method,
        "rng_algorithm": value.rng_algorithm,
        "non_production": value.non_production,
    }


_PLAN_TABLES = TypedRevisionTables(
    aggregate_type=VOCE_CALIBRATION_PLAN_AGGREGATE_TYPE,
    identity_table=voce_plan_table,
    revision_table=voce_plan_revision_table,
    canonical_content=reference_voce_calibration_plan_canonical,
    content_values=_plan_values,
    identity_values=lambda value: {
        "plan_label": value.plan_label,
        "plan_kind": value.plan_kind,
    },
)


def _revision_columns(table: sa.Table) -> tuple[Any, ...]:
    return tuple(
        table.c[name]
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


def _plan_content_columns(table: sa.Table) -> tuple[Any, ...]:
    excluded = {
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
    }
    return tuple(column for column in table.c if column.name not in excluded)


def _run(row: Any) -> VoceCalibrationRun:
    return VoceCalibrationRun(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        plan_id=cast(UUID, row["plan_id"]),
        plan_revision_id=cast(UUID, row["plan_revision_id"]),
        calibration_input_scope_id=cast(UUID, row["calibration_input_scope_id"]),
        calibration_input_scope_revision_id=cast(UUID, row["calibration_input_scope_revision_id"]),
        property_set_id=cast(UUID, row["property_set_id"]),
        property_set_revision_id=cast(UUID, row["property_set_revision_id"]),
        source_curve_count=int(row["source_curve_count"]),
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


def _attempt(row: Any) -> VoceCalibrationAttempt:
    return VoceCalibrationAttempt(
        id=cast(UUID, row["id"]),
        calibration_run_id=cast(UUID, row["calibration_run_id"]),
        attempt_ordinal=int(row["attempt_ordinal"]),
        initial_sigma_0_pa=float(row["initial_sigma_0_pa"]),
        initial_q_pa=float(row["initial_q_pa"]),
        initial_b=float(row["initial_b"]),
        random_seed=int(row["random_seed"]),
        status=CalibrationAttemptStatus(str(row["status"])),
        candidate_id=cast(UUID | None, row["candidate_id"]),
        failure_code=cast(str | None, row["failure_code"]),
        started_at=cast(datetime, row["started_at"]),
        ended_at=cast(datetime | None, row["ended_at"]),
    )


def _term(row: Any) -> VoceObjectiveTerm:
    return VoceObjectiveTerm(
        member_ordinal=int(row["member_ordinal"]),
        dataset_id=cast(UUID, row["dataset_id"]),
        dataset_revision_id=cast(UUID, row["dataset_revision_id"]),
        point_count=int(row["point_count"]),
        mean_normalized_squared_residual=float(row["mean_normalized_squared_residual"]),
    )


def _candidate(row: Any, terms: tuple[VoceObjectiveTerm, ...]) -> VoceCalibrationCandidate:
    return VoceCalibrationCandidate(
        id=cast(UUID, row["id"]),
        calibration_run_id=cast(UUID, row["calibration_run_id"]),
        calibration_attempt_id=cast(UUID, row["calibration_attempt_id"]),
        attempt_ordinal=int(row["attempt_ordinal"]),
        status=CalibrationCandidateStatus(str(row["status"])),
        candidate_sha256=str(row["candidate_sha256"]),
        sigma_0_pa=float(row["sigma_0_pa"]),
        q_pa=float(row["q_pa"]),
        b=float(row["b"]),
        objective_total=float(row["objective_total"]),
        residual_root_mean_square_pa=float(row["residual_root_mean_square_pa"]),
        residual_mean_pa=float(row["residual_mean_pa"]),
        sigma_0_at_bound=bool(row["sigma_0_at_bound"]),
        q_at_bound=bool(row["q_at_bound"]),
        b_at_bound=bool(row["b_at_bound"]),
        convergence_status_code=int(row["convergence_status_code"]),
        convergence_reason=str(row["convergence_reason"]),
        function_evaluations=int(row["function_evaluations"]),
        jacobian_evaluations=(
            int(row["jacobian_evaluations"]) if row["jacobian_evaluations"] is not None else None
        ),
        optimality=float(row["optimality"]),
        warning_at_bound=bool(row["warning_at_bound"]),
        warning_nonconvergence=bool(row["warning_nonconvergence"]),
        identifiability_status=str(row["identifiability_status"]),
        uncertainty_status=str(row["uncertainty_status"]),
        diagnostics_artifact_id=cast(UUID, row["diagnostics_artifact_id"]),
        diagnostics_sha256=str(row["diagnostics_sha256"]),
        diagnostics_point_count=int(row["diagnostics_point_count"]),
        objective_terms=terms,
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
    )


class SqlAlchemyVoceCalibrationRepository(VoceCalibrationRepository):
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
    ) -> RevisionStore[ReferenceVoceCalibrationPlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_PLAN_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _current_plan_statement() -> sa.Select[Any]:
        return sa.select(
            voce_plan_table.c.id.label("identity_id"),
            voce_plan_table.c.plan_label,
            *_revision_columns(voce_plan_revision_table),
            *_plan_content_columns(voce_plan_revision_table),
        ).select_from(
            voce_plan_table.join(
                voce_plan_revision_table,
                sa.and_(
                    voce_plan_revision_table.c.id == voce_plan_table.c.current_revision_id,
                    voce_plan_revision_table.c.aggregate_id == voce_plan_table.c.id,
                    voce_plan_revision_table.c.organization_id == voce_plan_table.c.organization_id,
                    voce_plan_revision_table.c.project_id == voce_plan_table.c.project_id,
                ),
            )
        )

    @staticmethod
    def _plan_snapshot(row: Any) -> VoceCalibrationPlanSnapshot:
        return VoceCalibrationPlanSnapshot(
            cast(UUID, row["identity_id"]), RevisionSnapshot(_record(row), _plan_content(row))
        )

    def get_plan(
        self, *, context: SecurityContext, decision: AuthorizationDecision, plan_id: UUID
    ) -> VoceCalibrationPlanSnapshot:
        statement = self._current_plan_statement().where(
            voce_plan_table.c.id == plan_id,
            voce_plan_table.c.organization_id == context.organization_id,
            voce_plan_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise VoceCalibrationNotFound("Voce Plan is not visible in the selected tenant")
        return self._plan_snapshot(row)

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceVoceCalibrationPlanContent]:
        table = voce_plan_revision_table
        statement = (
            sa.select(
                voce_plan_table.c.plan_label,
                *_revision_columns(table),
                *_plan_content_columns(table),
            )
            .select_from(
                voce_plan_table.join(
                    table,
                    sa.and_(
                        table.c.aggregate_id == voce_plan_table.c.id,
                        table.c.organization_id == voce_plan_table.c.organization_id,
                        table.c.project_id == voce_plan_table.c.project_id,
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
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise VoceCalibrationNotFound("Voce Plan revision is not visible")
        return RevisionSnapshot(_record(row), _plan_content(row))

    def list_plans(
        self, *, context: SecurityContext, decision: AuthorizationDecision, limit: int
    ) -> tuple[VoceCalibrationPlanSnapshot, ...]:
        statement = (
            self._current_plan_statement()
            .where(
                voce_plan_table.c.organization_id == context.organization_id,
                voce_plan_table.c.project_id == context.project_id,
            )
            .order_by(voce_plan_revision_table.c.created_at.desc())
            .limit(limit)
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._plan_snapshot(row) for row in rows)

    def create_run(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run: VoceCalibrationRun
    ) -> VoceCalibrationRun:
        values = {
            name: getattr(run, name)
            for name in (
                "id",
                "plan_id",
                "plan_revision_id",
                "calibration_input_scope_id",
                "calibration_input_scope_revision_id",
                "property_set_id",
                "property_set_revision_id",
                "source_curve_count",
                "execution_mode",
                "reproducibility_level",
                "environment_digest",
                "attempt_count",
                "candidate_count",
                "failure_code",
                "change_reason",
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
            status=run.status.value,
        )
        with self._session(context, decision) as session:
            try:
                row = (
                    session.execute(
                        sa.insert(voce_run_table).values(**values).returning(voce_run_table)
                    )
                    .mappings()
                    .one()
                )
            except IntegrityError as error:
                raise VoceCalibrationConflict("Voce Run conflicts with pinned inputs") from error
        return _run(row)

    def create_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt: VoceCalibrationAttempt,
    ) -> VoceCalibrationAttempt:
        run = self.get_run(context=context, decision=decision, run_id=attempt.calibration_run_id)
        values = {
            name: getattr(attempt, name)
            for name in (
                "id",
                "calibration_run_id",
                "attempt_ordinal",
                "initial_sigma_0_pa",
                "initial_q_pa",
                "initial_b",
                "random_seed",
                "candidate_id",
                "failure_code",
                "started_at",
                "ended_at",
            )
        }
        values.update(
            organization_id=context.organization_id,
            project_id=context.project_id,
            classification=run.classification.value,
            status=attempt.status.value,
        )
        with self._session(context, decision) as session:
            try:
                row = (
                    session.execute(
                        sa.insert(voce_attempt_table).values(**values).returning(voce_attempt_table)
                    )
                    .mappings()
                    .one()
                )
            except IntegrityError as error:
                raise VoceCalibrationConflict("Voce Attempt conflicts with Run") from error
        return _attempt(row)

    def _terminal_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        values: dict[str, object],
    ) -> VoceCalibrationAttempt:
        statement = (
            sa.update(voce_attempt_table)
            .where(
                voce_attempt_table.c.id == attempt_id,
                voce_attempt_table.c.organization_id == context.organization_id,
                voce_attempt_table.c.project_id == context.project_id,
                voce_attempt_table.c.status == CalibrationAttemptStatus.EXECUTING.value,
            )
            .values(**values, ended_at=datetime.now(UTC))
            .returning(voce_attempt_table)
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise VoceCalibrationConflict("Voce Attempt is not executing or visible")
        return _attempt(row)

    def succeed_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        candidate_id: UUID,
    ) -> VoceCalibrationAttempt:
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
    ) -> VoceCalibrationAttempt:
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
        candidate: VoceCalibrationCandidate,
    ) -> VoceCalibrationCandidate:
        run = self.get_run(context=context, decision=decision, run_id=candidate.calibration_run_id)
        names = tuple(
            column.name
            for column in voce_candidate_table.c
            if column.name
            not in {
                "organization_id",
                "project_id",
                "classification",
            }
        )
        values = {name: getattr(candidate, name) for name in names}
        values["status"] = candidate.status.value
        values.update(
            organization_id=context.organization_id,
            project_id=context.project_id,
            classification=run.classification.value,
        )
        with self._session(context, decision) as session:
            try:
                row = (
                    session.execute(
                        sa.insert(voce_candidate_table)
                        .values(**values)
                        .returning(voce_candidate_table)
                    )
                    .mappings()
                    .one()
                )
                session.execute(
                    sa.insert(voce_objective_term_table),
                    [
                        {
                            "organization_id": context.organization_id,
                            "project_id": context.project_id,
                            "classification": run.classification.value,
                            "candidate_id": candidate.id,
                            "member_ordinal": term.member_ordinal,
                            "dataset_id": term.dataset_id,
                            "dataset_revision_id": term.dataset_revision_id,
                            "point_count": term.point_count,
                            "mean_normalized_squared_residual": (
                                term.mean_normalized_squared_residual
                            ),
                        }
                        for term in candidate.objective_terms
                    ],
                )
            except IntegrityError as error:
                raise VoceCalibrationConflict("Voce Candidate conflicts with Attempt") from error
        return _candidate(row, candidate.objective_terms)

    def _terminal_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        values: dict[str, object],
    ) -> VoceCalibrationRun:
        statement = (
            sa.update(voce_run_table)
            .where(
                voce_run_table.c.id == run_id,
                voce_run_table.c.organization_id == context.organization_id,
                voce_run_table.c.project_id == context.project_id,
                voce_run_table.c.status == CalibrationRunStatus.EXECUTING.value,
            )
            .values(**values, ended_at=datetime.now(UTC))
            .returning(voce_run_table)
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise VoceCalibrationConflict("Voce Run is not executing or visible")
        return _run(row)

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        candidate_count: int,
    ) -> VoceCalibrationRun:
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
    ) -> VoceCalibrationRun:
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
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> VoceCalibrationRun:
        statement = sa.select(voce_run_table).where(
            voce_run_table.c.id == run_id,
            voce_run_table.c.organization_id == context.organization_id,
            voce_run_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise VoceCalibrationNotFound("Voce Run is not available") from error
        if row is None:
            raise VoceCalibrationNotFound("Voce Run is not visible")
        return _run(row)

    def list_attempts(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> tuple[VoceCalibrationAttempt, ...]:
        statement = (
            sa.select(voce_attempt_table)
            .where(
                voce_attempt_table.c.calibration_run_id == run_id,
                voce_attempt_table.c.organization_id == context.organization_id,
                voce_attempt_table.c.project_id == context.project_id,
            )
            .order_by(voce_attempt_table.c.attempt_ordinal)
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(_attempt(row) for row in rows)

    def list_candidates(
        self, *, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> tuple[VoceCalibrationCandidate, ...]:
        statement = (
            sa.select(voce_candidate_table)
            .where(
                voce_candidate_table.c.calibration_run_id == run_id,
                voce_candidate_table.c.organization_id == context.organization_id,
                voce_candidate_table.c.project_id == context.project_id,
            )
            .order_by(voce_candidate_table.c.objective_total)
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
            candidates = []
            for row in rows:
                term_rows = (
                    session.execute(
                        sa.select(voce_objective_term_table)
                        .where(
                            voce_objective_term_table.c.candidate_id == row["id"],
                            voce_objective_term_table.c.organization_id == context.organization_id,
                            voce_objective_term_table.c.project_id == context.project_id,
                        )
                        .order_by(voce_objective_term_table.c.member_ordinal)
                    )
                    .mappings()
                    .all()
                )
                candidates.append(_candidate(row, tuple(_term(term) for term in term_rows)))
        return tuple(candidates)

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> VoceCalibrationCandidate:
        statement = sa.select(voce_candidate_table).where(
            voce_candidate_table.c.id == candidate_id,
            voce_candidate_table.c.organization_id == context.organization_id,
            voce_candidate_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise VoceCalibrationNotFound("Voce Candidate is not visible")
            term_rows = (
                session.execute(
                    sa.select(voce_objective_term_table)
                    .where(
                        voce_objective_term_table.c.candidate_id == candidate_id,
                        voce_objective_term_table.c.organization_id == context.organization_id,
                        voce_objective_term_table.c.project_id == context.project_id,
                    )
                    .order_by(voce_objective_term_table.c.member_ordinal)
                )
                .mappings()
                .all()
            )
        return _candidate(row, tuple(_term(term) for term in term_rows))
