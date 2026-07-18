"""PostgreSQL persistence for typed multi-test Ogden Plans, Runs, and Candidates."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.persistence.repository import metadata
from cmp.modules.modeling.application.ogden_calibration import (
    OGDEN_CALIBRATION_PLAN_AGGREGATE_TYPE,
    OgdenCalibrationNotFound,
    OgdenCalibrationRepository,
    OgdenCalibrationRun,
    PersistedHyperelasticFamilyCandidate,
    PersistedOgdenCandidate,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.hyperelastic_families import (
    HyperelasticFamily,
    HyperelasticFamilyCandidate,
    HyperelasticParameter,
)
from cmp.modules.modeling.domain.reference_ogden_calibration import (
    OgdenCalibrationCandidate,
    OgdenCalibrationMember,
    OgdenCalibrationRole,
    OgdenTestMode,
    ReferenceOgdenCalibrationPlanContent,
)
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


ogden_calibration_plan_table = sa.Table(
    "ogden_calibration_plan",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_label", sa.String(160), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_id", sa.Uuid(), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="modeling",
)
ogden_calibration_plan_revision_table = sa.Table(
    "ogden_calibration_plan_revision",
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
    sa.Column("plan_label", sa.String(160), nullable=False),
    sa.Column("scientific_profile_id", sa.Uuid(), nullable=False),
    sa.Column("scientific_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("member_count", sa.SmallInteger(), nullable=False),
    sa.Column("calibration_member_count", sa.SmallInteger(), nullable=False),
    sa.Column("holdout_member_count", sa.SmallInteger(), nullable=False),
    sa.Column("test_mode_count", sa.SmallInteger(), nullable=False),
    sa.Column("evaluator", sa.String(80), nullable=False),
    sa.Column("objective", sa.String(80), nullable=False),
    sa.Column("aggregation_order", sa.String(80), nullable=False),
    sa.Column("holdout_policy", sa.String(32), nullable=False),
    sa.Column("maximum_function_evaluations", sa.Integer(), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="modeling",
)
ogden_calibration_member_table = sa.Table(
    "ogden_calibration_plan_member",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("role", sa.String(16), nullable=False),
    sa.Column("test_mode", sa.String(32), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("weight", sa.Double(), nullable=False),
    schema="modeling",
)
ogden_calibration_run_table = sa.Table(
    "ogden_calibration_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("scientific_profile_id", sa.Uuid(), nullable=False),
    sa.Column("scientific_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_id", sa.Uuid(), nullable=False),
    sa.Column("baseline_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("environment_digest", sa.String(71), nullable=False),
    sa.Column("calibration_curve_count", sa.SmallInteger(), nullable=False),
    sa.Column("holdout_curve_count", sa.SmallInteger(), nullable=False),
    sa.Column("test_mode_count", sa.SmallInteger(), nullable=False),
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
ogden_calibration_attempt_table = sa.Table(
    "ogden_calibration_attempt",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("attempt_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("initial_mu_pa", sa.Double(), nullable=False),
    sa.Column("initial_alpha", sa.Double(), nullable=False),
    sa.Column("candidate_id", sa.Uuid(), nullable=False),
    schema="modeling",
)
ogden_calibration_candidate_table = sa.Table(
    "ogden_calibration_candidate",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_attempt_id", sa.Uuid(), nullable=False),
    sa.Column("attempt_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("candidate_sha256", sa.CHAR(64), nullable=False),
    sa.Column("mu_pa", sa.Double(), nullable=False),
    sa.Column("alpha", sa.Double(), nullable=False),
    sa.Column("objective_total", sa.Double(), nullable=False),
    sa.Column("uniaxial_objective", sa.Double(), nullable=False),
    sa.Column("planar_objective", sa.Double(), nullable=False),
    sa.Column("biaxial_objective", sa.Double(), nullable=False),
    sa.Column("calibration_rmse_pa", sa.Double(), nullable=False),
    sa.Column("calibration_normalized_rmse", sa.Double(), nullable=False),
    sa.Column("holdout_rmse_pa", sa.Double(), nullable=True),
    sa.Column("holdout_normalized_rmse", sa.Double(), nullable=True),
    sa.Column("status", sa.String(24), nullable=False),
    sa.Column("convergence_status_code", sa.Integer(), nullable=False),
    sa.Column("convergence_reason", sa.String(255), nullable=False),
    sa.Column("function_evaluations", sa.Integer(), nullable=False),
    sa.Column("jacobian_evaluations", sa.Integer(), nullable=True),
    sa.Column("optimality", sa.Double(), nullable=False),
    sa.Column("parameter_at_bound", sa.Boolean(), nullable=False),
    sa.Column("jacobian_rank", sa.SmallInteger(), nullable=False),
    sa.Column("jacobian_condition_number", sa.Double(), nullable=True),
    sa.Column("identifiability_status", sa.String(32), nullable=False),
    sa.Column("uncertainty_status", sa.String(48), nullable=False),
    sa.Column("mu_standard_error_pa", sa.Double(), nullable=True),
    sa.Column("alpha_standard_error", sa.Double(), nullable=True),
    sa.Column("mu_confidence_lower_pa", sa.Double(), nullable=True),
    sa.Column("mu_confidence_upper_pa", sa.Double(), nullable=True),
    sa.Column("alpha_confidence_lower", sa.Double(), nullable=True),
    sa.Column("alpha_confidence_upper", sa.Double(), nullable=True),
    sa.Column("diagnostics_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("diagnostics_sha256", sa.CHAR(64), nullable=False),
    sa.Column("diagnostics_point_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="modeling",
)
ogden_calibration_warning_table = sa.Table(
    "ogden_calibration_candidate_warning",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("candidate_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("warning_code", sa.String(64), nullable=False),
    schema="modeling",
)
hyperelastic_family_candidate_table = sa.Table(
    "hyperelastic_family_candidate",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("family", sa.String(32), nullable=False),
    sa.Column("candidate_sha256", sa.CHAR(64), nullable=False),
    sa.Column("c10_pa", sa.Double(), nullable=True),
    sa.Column("c01_pa", sa.Double(), nullable=True),
    sa.Column("c20_pa", sa.Double(), nullable=True),
    sa.Column("c30_pa", sa.Double(), nullable=True),
    sa.Column("ogden_mu_pa", sa.Double(), nullable=True),
    sa.Column("ogden_alpha", sa.Double(), nullable=True),
    sa.Column("objective_total", sa.Double(), nullable=False),
    sa.Column("uniaxial_objective", sa.Double(), nullable=False),
    sa.Column("planar_objective", sa.Double(), nullable=False),
    sa.Column("biaxial_objective", sa.Double(), nullable=False),
    sa.Column("calibration_normalized_rmse", sa.Double(), nullable=False),
    sa.Column("holdout_normalized_rmse", sa.Double(), nullable=True),
    sa.Column("function_evaluations", sa.Integer(), nullable=False),
    sa.Column("convergence_reason", sa.String(255), nullable=False),
    sa.Column("stability_status", sa.String(48), nullable=False),
    sa.Column("diagnostics_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("diagnostics_sha256", sa.CHAR(64), nullable=True),
    sa.Column("diagnostics_point_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="modeling",
)
hyperelastic_family_candidate_warning_table = sa.Table(
    "hyperelastic_family_candidate_warning",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("candidate_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("warning_code", sa.String(64), nullable=False),
    schema="modeling",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=OGDEN_CALIBRATION_PLAN_AGGREGATE_TYPE,
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


def _write_members(
    session: Session, draft: RevisionDraft[ReferenceOgdenCalibrationPlanContent]
) -> None:
    session.execute(
        sa.insert(ogden_calibration_member_table),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "plan_id": draft.aggregate_id,
                "plan_revision_id": draft.revision_id,
                "ordinal": item.ordinal,
                "role": item.role.value,
                "test_mode": item.test_mode.value,
                "dataset_id": item.dataset_id,
                "dataset_revision_id": item.dataset_revision_id,
                "weight": item.weight,
            }
            for item in draft.content.members
        ],
    )


_PLAN_TABLES = TypedRevisionTables[ReferenceOgdenCalibrationPlanContent](
    aggregate_type=OGDEN_CALIBRATION_PLAN_AGGREGATE_TYPE,
    identity_table=ogden_calibration_plan_table,
    revision_table=ogden_calibration_plan_revision_table,
    canonical_content=lambda value: value.canonical(),
    content_values=lambda value: {
        "plan_label": value.plan_label,
        "scientific_profile_id": value.scientific_profile_id,
        "scientific_profile_revision_id": value.scientific_profile_revision_id,
        "material_state_id": value.material_state_id,
        "material_state_revision_id": value.material_state_revision_id,
        "baseline_model_id": value.baseline_model_id,
        "baseline_model_revision_id": value.baseline_model_revision_id,
        "member_count": len(value.members),
        "calibration_member_count": sum(
            item.role is OgdenCalibrationRole.CALIBRATION for item in value.members
        ),
        "holdout_member_count": sum(
            item.role is OgdenCalibrationRole.HOLDOUT for item in value.members
        ),
        "test_mode_count": len({item.test_mode for item in value.members}),
        "evaluator": value.evaluator,
        "objective": value.objective,
        "aggregation_order": value.aggregation_order,
        "holdout_policy": value.holdout_policy,
        "maximum_function_evaluations": value.maximum_function_evaluations,
        "non_production": value.non_production,
    },
    identity_values=lambda value: {
        "plan_label": value.plan_label,
        "material_state_id": value.material_state_id,
        "baseline_model_id": value.baseline_model_id,
    },
    revision_content_writer=_write_members,
)


def _members(session: Session, revision_id: UUID) -> tuple[OgdenCalibrationMember, ...]:
    rows = (
        session.execute(
            sa.select(ogden_calibration_member_table)
            .where(ogden_calibration_member_table.c.plan_revision_id == revision_id)
            .order_by(ogden_calibration_member_table.c.ordinal)
        )
        .mappings()
        .all()
    )
    return tuple(
        OgdenCalibrationMember(
            int(row["ordinal"]),
            OgdenCalibrationRole(str(row["role"])),
            OgdenTestMode(str(row["test_mode"])),
            cast(UUID, row["dataset_id"]),
            cast(UUID, row["dataset_revision_id"]),
            float(row["weight"]),
        )
        for row in rows
    )


def _plan_content(session: Session, row: Any) -> ReferenceOgdenCalibrationPlanContent:
    content = ReferenceOgdenCalibrationPlanContent(
        plan_label=str(row["plan_label"]),
        scientific_profile_id=cast(UUID, row["scientific_profile_id"]),
        scientific_profile_revision_id=cast(UUID, row["scientific_profile_revision_id"]),
        material_state_id=cast(UUID, row["material_state_id"]),
        material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
        baseline_model_id=cast(UUID, row["baseline_model_id"]),
        baseline_model_revision_id=cast(UUID, row["baseline_model_revision_id"]),
        members=_members(session, cast(UUID, row["id"])),
        evaluator=str(row["evaluator"]),
        objective=str(row["objective"]),
        aggregation_order=str(row["aggregation_order"]),
        holdout_policy=str(row["holdout_policy"]),
        maximum_function_evaluations=int(row["maximum_function_evaluations"]),
        non_production=bool(row["non_production"]),
    )
    if (
        len(content.members) != int(row["member_count"])
        or sum(item.role is OgdenCalibrationRole.CALIBRATION for item in content.members)
        != int(row["calibration_member_count"])
        or sum(item.role is OgdenCalibrationRole.HOLDOUT for item in content.members)
        != int(row["holdout_member_count"])
        or len({item.test_mode for item in content.members}) != int(row["test_mode_count"])
    ):
        raise OgdenCalibrationNotFound("Ogden calibration Plan membership is incomplete")
    return content


def _candidate_value(row: Any, warnings: tuple[str, ...]) -> OgdenCalibrationCandidate:
    return OgdenCalibrationCandidate(
        attempt_ordinal=int(row["attempt_ordinal"]),
        initial_mu_pa=float(row["initial_mu_pa"]),
        initial_alpha=float(row["initial_alpha"]),
        mu_pa=float(row["mu_pa"]),
        alpha=float(row["alpha"]),
        objective_total=float(row["objective_total"]),
        uniaxial_objective=float(row["uniaxial_objective"]),
        planar_objective=float(row["planar_objective"]),
        biaxial_objective=float(row["biaxial_objective"]),
        calibration_rmse_pa=float(row["calibration_rmse_pa"]),
        calibration_normalized_rmse=float(row["calibration_normalized_rmse"]),
        holdout_rmse_pa=(
            float(row["holdout_rmse_pa"]) if row["holdout_rmse_pa"] is not None else None
        ),
        holdout_normalized_rmse=(
            float(row["holdout_normalized_rmse"])
            if row["holdout_normalized_rmse"] is not None
            else None
        ),
        status=str(row["status"]),
        convergence_status_code=int(row["convergence_status_code"]),
        convergence_reason=str(row["convergence_reason"]),
        function_evaluations=int(row["function_evaluations"]),
        jacobian_evaluations=cast(int | None, row["jacobian_evaluations"]),
        optimality=float(row["optimality"]),
        parameter_at_bound=bool(row["parameter_at_bound"]),
        jacobian_rank=int(row["jacobian_rank"]),
        jacobian_condition_number=(
            float(row["jacobian_condition_number"])
            if row["jacobian_condition_number"] is not None
            else None
        ),
        identifiability_status=str(row["identifiability_status"]),
        uncertainty_status=str(row["uncertainty_status"]),
        mu_standard_error_pa=(
            float(row["mu_standard_error_pa"])
            if row["mu_standard_error_pa"] is not None
            else None
        ),
        alpha_standard_error=(
            float(row["alpha_standard_error"])
            if row["alpha_standard_error"] is not None
            else None
        ),
        mu_confidence_lower_pa=(
            float(row["mu_confidence_lower_pa"])
            if row["mu_confidence_lower_pa"] is not None
            else None
        ),
        mu_confidence_upper_pa=(
            float(row["mu_confidence_upper_pa"])
            if row["mu_confidence_upper_pa"] is not None
            else None
        ),
        alpha_confidence_lower=(
            float(row["alpha_confidence_lower"])
            if row["alpha_confidence_lower"] is not None
            else None
        ),
        alpha_confidence_upper=(
            float(row["alpha_confidence_upper"])
            if row["alpha_confidence_upper"] is not None
            else None
        ),
        warnings=warnings,
        candidate_sha256=str(row["candidate_sha256"]),
        diagnostics=(),
    )


def _family_parameter_columns(
    candidate: HyperelasticFamilyCandidate,
) -> dict[str, float | None]:
    values = {item.name: item.value for item in candidate.parameters}
    return {
        "c10_pa": values.get("c10_pa"),
        "c01_pa": values.get("c01_pa"),
        "c20_pa": values.get("c20_pa"),
        "c30_pa": values.get("c30_pa"),
        "ogden_mu_pa": values.get("mu_pa"),
        "ogden_alpha": values.get("alpha"),
    }


def _family_parameters(row: Any) -> tuple[HyperelasticParameter, ...]:
    family = HyperelasticFamily(str(row["family"]))
    names = {
        HyperelasticFamily.NEO_HOOKEAN: ("c10_pa",),
        HyperelasticFamily.MOONEY_RIVLIN: ("c10_pa", "c01_pa"),
        HyperelasticFamily.YEOH: ("c10_pa", "c20_pa", "c30_pa"),
        HyperelasticFamily.OGDEN_1: ("ogden_mu_pa", "ogden_alpha"),
    }[family]
    return tuple(
        HyperelasticParameter(
            "mu_pa" if name == "ogden_mu_pa" else "alpha" if name == "ogden_alpha" else name,
            float(row[name]),
            "1" if name == "ogden_alpha" else "Pa",
        )
        for name in names
    )


def _family_candidate_value(
    row: Any, warnings: tuple[str, ...]
) -> HyperelasticFamilyCandidate:
    return HyperelasticFamilyCandidate(
        family=HyperelasticFamily(str(row["family"])),
        parameters=_family_parameters(row),
        objective_total=float(row["objective_total"]),
        calibration_normalized_rmse=float(row["calibration_normalized_rmse"]),
        holdout_normalized_rmse=(
            float(row["holdout_normalized_rmse"])
            if row["holdout_normalized_rmse"] is not None
            else None
        ),
        objective_by_mode=(
            (OgdenTestMode.UNIAXIAL_TENSION, float(row["uniaxial_objective"])),
            (OgdenTestMode.PLANAR_TENSION, float(row["planar_objective"])),
            (OgdenTestMode.BIAXIAL_TENSION, float(row["biaxial_objective"])),
        ),
        function_evaluations=int(row["function_evaluations"]),
        convergence_reason=str(row["convergence_reason"]),
        stability_status=str(row["stability_status"]),
        warnings=warnings,
        candidate_sha256=str(row["candidate_sha256"]),
    )


class SqlAlchemyOgdenCalibrationRepository(OgdenCalibrationRepository):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[SqlRevisionHook] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = tuple(revision_hooks)

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
    ) -> RevisionStore[ReferenceOgdenCalibrationPlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_PLAN_TABLES,
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
    ) -> RevisionSnapshot[ReferenceOgdenCalibrationPlanContent]:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(ogden_calibration_plan_revision_table).where(
                        ogden_calibration_plan_revision_table.c.aggregate_id == plan_id,
                        ogden_calibration_plan_revision_table.c.id == plan_revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise OgdenCalibrationNotFound("Ogden calibration Plan revision is not visible")
            return RevisionSnapshot(_record(row), _plan_content(session, row))

    @staticmethod
    def _candidate_statement() -> sa.Select[Any]:
        return sa.select(
            ogden_calibration_candidate_table,
            ogden_calibration_attempt_table.c.initial_mu_pa,
            ogden_calibration_attempt_table.c.initial_alpha,
        ).join(
            ogden_calibration_attempt_table,
            sa.and_(
                ogden_calibration_attempt_table.c.id
                == ogden_calibration_candidate_table.c.calibration_attempt_id,
                ogden_calibration_attempt_table.c.organization_id
                == ogden_calibration_candidate_table.c.organization_id,
                ogden_calibration_attempt_table.c.project_id
                == ogden_calibration_candidate_table.c.project_id,
            ),
        )

    @staticmethod
    def _warnings(session: Session, candidate_id: UUID) -> tuple[str, ...]:
        return tuple(
            str(value)
            for value in session.execute(
                sa.select(ogden_calibration_warning_table.c.warning_code)
                .where(ogden_calibration_warning_table.c.candidate_id == candidate_id)
                .order_by(ogden_calibration_warning_table.c.ordinal)
            ).scalars()
        )

    @staticmethod
    def _family_warnings(session: Session, candidate_id: UUID) -> tuple[str, ...]:
        return tuple(
            str(value)
            for value in session.execute(
                sa.select(hyperelastic_family_candidate_warning_table.c.warning_code)
                .where(
                    hyperelastic_family_candidate_warning_table.c.candidate_id
                    == candidate_id
                )
                .order_by(hyperelastic_family_candidate_warning_table.c.ordinal)
            ).scalars()
        )

    @classmethod
    def _family_candidate(
        cls, session: Session, row: Any
    ) -> PersistedHyperelasticFamilyCandidate:
        candidate_id = cast(UUID, row["id"])
        return PersistedHyperelasticFamilyCandidate(
            id=candidate_id,
            calibration_run_id=cast(UUID, row["calibration_run_id"]),
            value=_family_candidate_value(
                row, cls._family_warnings(session, candidate_id)
            ),
            created_at=row["created_at"],
            created_by=cast(UUID, row["created_by"]),
            diagnostics_artifact_id=cast(UUID | None, row["diagnostics_artifact_id"]),
            diagnostics_sha256=cast(str | None, row["diagnostics_sha256"]),
            diagnostics_point_count=int(row["diagnostics_point_count"]),
        )

    @classmethod
    def _candidate(cls, session: Session, row: Any) -> PersistedOgdenCandidate:
        candidate_id = cast(UUID, row["id"])
        return PersistedOgdenCandidate(
            id=candidate_id,
            attempt_id=cast(UUID, row["calibration_attempt_id"]),
            calibration_run_id=cast(UUID, row["calibration_run_id"]),
            value=_candidate_value(row, cls._warnings(session, candidate_id)),
            diagnostics_artifact_id=cast(UUID, row["diagnostics_artifact_id"]),
            diagnostics_sha256=str(row["diagnostics_sha256"]),
            diagnostics_point_count=int(row["diagnostics_point_count"]),
            created_at=row["created_at"],
            created_by=cast(UUID, row["created_by"]),
        )

    def save_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: OgdenCalibrationRun,
    ) -> OgdenCalibrationRun:
        scope = {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
        }
        with self._session(context, decision) as session:
            try:
                session.execute(
                    sa.insert(ogden_calibration_run_table).values(
                        **scope,
                        id=run.id,
                        plan_id=run.plan_id,
                        plan_revision_id=run.plan_revision_id,
                        scientific_profile_id=run.scientific_profile_id,
                        scientific_profile_revision_id=run.scientific_profile_revision_id,
                        material_state_id=run.material_state_id,
                        material_state_revision_id=run.material_state_revision_id,
                        baseline_model_id=run.baseline_model_id,
                        baseline_model_revision_id=run.baseline_model_revision_id,
                        status=run.status.value,
                        environment_digest=run.environment_digest,
                        calibration_curve_count=run.calibration_curve_count,
                        holdout_curve_count=run.holdout_curve_count,
                        test_mode_count=run.test_mode_count,
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
                for persisted in run.candidates:
                    value = persisted.value
                    session.execute(
                        sa.insert(ogden_calibration_attempt_table).values(
                            **scope,
                            id=persisted.attempt_id,
                            calibration_run_id=run.id,
                            attempt_ordinal=value.attempt_ordinal,
                            initial_mu_pa=value.initial_mu_pa,
                            initial_alpha=value.initial_alpha,
                            candidate_id=persisted.id,
                        )
                    )
                    session.execute(
                        sa.insert(ogden_calibration_candidate_table).values(
                            **scope,
                            id=persisted.id,
                            calibration_run_id=run.id,
                            calibration_attempt_id=persisted.attempt_id,
                            attempt_ordinal=value.attempt_ordinal,
                            candidate_sha256=value.candidate_sha256,
                            mu_pa=value.mu_pa,
                            alpha=value.alpha,
                            objective_total=value.objective_total,
                            uniaxial_objective=value.uniaxial_objective,
                            planar_objective=value.planar_objective,
                            biaxial_objective=value.biaxial_objective,
                            calibration_rmse_pa=value.calibration_rmse_pa,
                            calibration_normalized_rmse=value.calibration_normalized_rmse,
                            holdout_rmse_pa=value.holdout_rmse_pa,
                            holdout_normalized_rmse=value.holdout_normalized_rmse,
                            status=value.status,
                            convergence_status_code=value.convergence_status_code,
                            convergence_reason=value.convergence_reason,
                            function_evaluations=value.function_evaluations,
                            jacobian_evaluations=value.jacobian_evaluations,
                            optimality=value.optimality,
                            parameter_at_bound=value.parameter_at_bound,
                            jacobian_rank=value.jacobian_rank,
                            jacobian_condition_number=value.jacobian_condition_number,
                            identifiability_status=value.identifiability_status,
                            uncertainty_status=value.uncertainty_status,
                            mu_standard_error_pa=value.mu_standard_error_pa,
                            alpha_standard_error=value.alpha_standard_error,
                            mu_confidence_lower_pa=value.mu_confidence_lower_pa,
                            mu_confidence_upper_pa=value.mu_confidence_upper_pa,
                            alpha_confidence_lower=value.alpha_confidence_lower,
                            alpha_confidence_upper=value.alpha_confidence_upper,
                            diagnostics_artifact_id=persisted.diagnostics_artifact_id,
                            diagnostics_sha256=persisted.diagnostics_sha256,
                            diagnostics_point_count=persisted.diagnostics_point_count,
                            created_at=persisted.created_at,
                            created_by=persisted.created_by,
                        )
                    )
                    if value.warnings:
                        session.execute(
                            sa.insert(ogden_calibration_warning_table),
                            [
                                {
                                    **scope,
                                    "candidate_id": persisted.id,
                                    "ordinal": ordinal,
                                    "warning_code": warning,
                                }
                                for ordinal, warning in enumerate(value.warnings)
                            ],
                        )
                for family_persisted in run.family_candidates:
                    family_value = family_persisted.value
                    objectives = dict(family_value.objective_by_mode)
                    session.execute(
                        sa.insert(hyperelastic_family_candidate_table).values(
                            **scope,
                            id=family_persisted.id,
                            calibration_run_id=run.id,
                            family=family_value.family.value,
                            candidate_sha256=family_value.candidate_sha256,
                            **_family_parameter_columns(family_value),
                            objective_total=family_value.objective_total,
                            uniaxial_objective=objectives[OgdenTestMode.UNIAXIAL_TENSION],
                            planar_objective=objectives[OgdenTestMode.PLANAR_TENSION],
                            biaxial_objective=objectives[OgdenTestMode.BIAXIAL_TENSION],
                            calibration_normalized_rmse=(
                                family_value.calibration_normalized_rmse
                            ),
                            holdout_normalized_rmse=family_value.holdout_normalized_rmse,
                            function_evaluations=family_value.function_evaluations,
                            convergence_reason=family_value.convergence_reason,
                            stability_status=family_value.stability_status,
                            diagnostics_artifact_id=(
                                family_persisted.diagnostics_artifact_id
                            ),
                            diagnostics_sha256=family_persisted.diagnostics_sha256,
                            diagnostics_point_count=(
                                family_persisted.diagnostics_point_count
                            ),
                            created_at=family_persisted.created_at,
                            created_by=family_persisted.created_by,
                        )
                    )
                    if family_value.warnings:
                        session.execute(
                            sa.insert(hyperelastic_family_candidate_warning_table),
                            [
                                {
                                    **scope,
                                    "candidate_id": family_persisted.id,
                                    "ordinal": ordinal,
                                    "warning_code": warning,
                                }
                                for ordinal, warning in enumerate(family_value.warnings)
                            ],
                        )
            except DBAPIError as error:
                raise OgdenCalibrationNotFound(
                    "Ogden calibration Run could not be persisted"
                ) from error
        return run

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> OgdenCalibrationRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(ogden_calibration_run_table).where(
                        ogden_calibration_run_table.c.id == run_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise OgdenCalibrationNotFound("Ogden calibration Run is not visible")
            candidates = tuple(
                self._candidate(session, candidate)
                for candidate in session.execute(
                    self._candidate_statement()
                    .where(ogden_calibration_candidate_table.c.calibration_run_id == run_id)
                    .order_by(ogden_calibration_candidate_table.c.attempt_ordinal)
                )
                .mappings()
                .all()
            )
            family_candidates = tuple(
                self._family_candidate(session, candidate)
                for candidate in session.execute(
                    sa.select(hyperelastic_family_candidate_table)
                    .where(
                        hyperelastic_family_candidate_table.c.calibration_run_id == run_id
                    )
                    .order_by(hyperelastic_family_candidate_table.c.family)
                )
                .mappings()
                .all()
            )
            return OgdenCalibrationRun(
                id=cast(UUID, row["id"]),
                classification=DataClassification(str(row["classification"])),
                plan_id=cast(UUID, row["plan_id"]),
                plan_revision_id=cast(UUID, row["plan_revision_id"]),
                scientific_profile_id=cast(UUID, row["scientific_profile_id"]),
                scientific_profile_revision_id=cast(
                    UUID, row["scientific_profile_revision_id"]
                ),
                material_state_id=cast(UUID, row["material_state_id"]),
                material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
                baseline_model_id=cast(UUID, row["baseline_model_id"]),
                baseline_model_revision_id=cast(UUID, row["baseline_model_revision_id"]),
                status=ProcessingRunStatus(str(row["status"])),
                environment_digest=str(row["environment_digest"]),
                calibration_curve_count=int(row["calibration_curve_count"]),
                holdout_curve_count=int(row["holdout_curve_count"]),
                test_mode_count=int(row["test_mode_count"]),
                attempt_count=int(row["attempt_count"]),
                candidate_count=int(row["candidate_count"]),
                failure_code=cast(str | None, row["failure_code"]),
                change_reason=str(row["change_reason"]),
                started_at=row["started_at"],
                ended_at=row["ended_at"],
                created_by=cast(UUID, row["created_by"]),
                request_id=cast(UUID, row["request_id"]),
                trace_id=str(row["trace_id"]),
                candidates=candidates,
                family_candidates=family_candidates,
            )

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> PersistedOgdenCandidate:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    self._candidate_statement().where(
                        ogden_calibration_candidate_table.c.id == candidate_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise OgdenCalibrationNotFound("Ogden calibration Candidate is not visible")
            return self._candidate(session, row)

    def get_family_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> PersistedHyperelasticFamilyCandidate:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(hyperelastic_family_candidate_table).where(
                        hyperelastic_family_candidate_table.c.id == candidate_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise OgdenCalibrationNotFound(
                    "hyperelastic family Candidate is not visible"
                )
            return self._family_candidate(session, row)
