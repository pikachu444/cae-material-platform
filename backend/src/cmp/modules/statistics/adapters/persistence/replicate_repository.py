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
    SCALAR_DISTRIBUTION_RESULT_AGGREGATE_TYPE,
    SCALAR_DISTRIBUTION_SELECTION_AGGREGATE_TYPE,
    ReplicateRevisionSnapshot,
    ReplicateStatisticalPlanSnapshot,
    ReplicateStatisticalResultSnapshot,
    ReplicateStatisticalRun,
    ReplicateStatisticalRunMember,
    ReplicateStatisticsRepository,
    ScalarDistributionResultSnapshot,
    ScalarDistributionSelectionSnapshot,
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
from cmp.modules.statistics.domain.scalar_distribution import (
    SCALAR_DISTRIBUTION_ALGORITHM_VERSION,
    SCALAR_DISTRIBUTION_RECOMMENDATION_METHOD,
    SCALAR_DISTRIBUTION_RESULT_SCHEMA,
    SCALAR_DISTRIBUTION_RNG,
    DistributionCandidateStatus,
    DistributionFamily,
    DistributionParameter,
    ObservationQuality,
    OutlierAssessmentState,
    ScalarDistributionAnalysisOptions,
    ScalarDistributionCandidate,
    ScalarDistributionComputation,
    ScalarDistributionObservation,
    ScalarDistributionResultContent,
    ScalarDistributionRuntimeManifest,
    ScalarDistributionSelectionContent,
    scalar_distribution_candidate_canonical,
    scalar_distribution_observation_canonical,
    scalar_distribution_result_canonical,
    scalar_distribution_selection_canonical,
)
from cmp.modules.units.domain.profiles import (
    UnitApplication,
    UnitApplicationRole,
    UnitProfilePin,
)
from cmp.modules.units.domain.system import DimensionId
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
    sa.Column("scalar_distribution_enabled", sa.Boolean(), nullable=False),
    sa.Column("distribution_seed", sa.BigInteger(), nullable=True),
    sa.Column("distribution_bootstrap_samples", sa.SmallInteger(), nullable=True),
    sa.Column("unit_profile_id", sa.Uuid(), nullable=True),
    sa.Column("unit_profile_revision_id", sa.Uuid(), nullable=True),
    sa.Column("unit_profile_sha256", sa.CHAR(64), nullable=True),
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
    sa.Column("scalar_distribution_result_id", sa.Uuid(), nullable=True),
    sa.Column("scalar_distribution_result_revision_id", sa.Uuid(), nullable=True),
    sa.Column("scalar_distribution_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("scalar_distribution_sha256", sa.CHAR(64), nullable=True),
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

distribution_result_table = _identity_table(
    "scalar_distribution_result",
    sa.Column("statistical_run_id", sa.Uuid(), nullable=False),
    sa.Column("result_kind", sa.String(100), nullable=False),
)
distribution_result_revision_table = _revision_table(
    "scalar_distribution_result_revision",
    sa.Column("result_kind", sa.String(100), nullable=False),
    sa.Column("statistical_run_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_result_id", sa.Uuid(), nullable=False),
    sa.Column("statistical_result_revision_id", sa.Uuid(), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("scalar_feature", sa.String(100), nullable=False),
    sa.Column("sample_count", sa.SmallInteger(), nullable=False),
    sa.Column("minimum_sample_count", sa.SmallInteger(), nullable=False),
    sa.Column("small_sample_warning_below", sa.SmallInteger(), nullable=False),
    sa.Column("seed", sa.BigInteger(), nullable=False),
    sa.Column("bootstrap_samples", sa.SmallInteger(), nullable=False),
    sa.Column("unit_profile_id", sa.Uuid(), nullable=True),
    sa.Column("unit_profile_revision_id", sa.Uuid(), nullable=True),
    sa.Column("unit_profile_sha256", sa.CHAR(64), nullable=True),
    sa.Column("unit_application_location", sa.String(255), nullable=True),
    sa.Column("unit_application_role", sa.String(32), nullable=True),
    sa.Column("unit_quantity_semantics", sa.String(160), nullable=True),
    sa.Column("unit_dimension", sa.String(80), nullable=True),
    sa.Column("display_unit_id", sa.String(40), nullable=True),
    sa.Column("observations", sa.JSON(), nullable=False),
    sa.Column("candidates", sa.JSON(), nullable=False),
    sa.Column("recommended_families", sa.JSON(), nullable=False),
    sa.Column("recommendation_method", sa.String(160), nullable=False),
    sa.Column("algorithm_version", sa.String(100), nullable=False),
    sa.Column("python_version", sa.String(80), nullable=False),
    sa.Column("numpy_version", sa.String(80), nullable=False),
    sa.Column("scipy_version", sa.String(80), nullable=False),
    sa.Column("rng", sa.String(80), nullable=False),
    sa.Column("source_sha256", sa.CHAR(64), nullable=False),
    sa.Column("lock_sha256", sa.CHAR(64), nullable=False),
    sa.Column("environment_sha256", sa.CHAR(64), nullable=False),
    sa.Column("artifact_id", sa.Uuid(), nullable=False),
    sa.Column("artifact_sha256", sa.CHAR(64), nullable=False),
)
distribution_selection_table = _identity_table(
    "scalar_distribution_selection",
    sa.Column("distribution_result_id", sa.Uuid(), nullable=False),
)
distribution_selection_revision_table = _revision_table(
    "scalar_distribution_selection_revision",
    sa.Column("distribution_result_id", sa.Uuid(), nullable=False),
    sa.Column("distribution_result_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selected_family", sa.String(32), nullable=False),
    sa.Column("candidate_sha256", sa.CHAR(64), nullable=False),
    sa.Column("selection_reason", sa.Text(), nullable=False),
)


def _plan_values(value: ReferenceTensileReplicatePlanContent) -> dict[str, object]:
    distribution = value.scalar_distribution
    unit_profile = distribution.unit_profile if distribution is not None else None
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
        "scalar_distribution_enabled": distribution is not None,
        "distribution_seed": distribution.seed if distribution is not None else None,
        "distribution_bootstrap_samples": (
            distribution.bootstrap_samples if distribution is not None else None
        ),
        "unit_profile_id": unit_profile.profile_id if unit_profile is not None else None,
        "unit_profile_revision_id": (
            unit_profile.revision_id if unit_profile is not None else None
        ),
        "unit_profile_sha256": (unit_profile.content_sha256 if unit_profile is not None else None),
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


def _distribution_result_values(
    value: ScalarDistributionResultContent,
) -> dict[str, object]:
    unit_profile = value.options.unit_profile
    manifest = value.computation.manifest
    return {
        "result_kind": "scalar_distribution_comparison",
        "statistical_run_id": value.statistical_run_id,
        "statistical_result_id": value.statistical_result_id,
        "statistical_result_revision_id": value.statistical_result_revision_id,
        "plan_id": value.plan_id,
        "plan_revision_id": value.plan_revision_id,
        "selection_id": value.selection_id,
        "selection_revision_id": value.selection_revision_id,
        "scalar_feature": REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE,
        "sample_count": len(value.computation.observations),
        "minimum_sample_count": 8,
        "small_sample_warning_below": 20,
        "seed": value.options.seed,
        "bootstrap_samples": value.options.bootstrap_samples,
        "unit_profile_id": unit_profile.profile_id if unit_profile is not None else None,
        "unit_profile_revision_id": (
            unit_profile.revision_id if unit_profile is not None else None
        ),
        "unit_profile_sha256": (unit_profile.content_sha256 if unit_profile is not None else None),
        "unit_application_location": (
            value.unit_applications[0].location if value.unit_applications else None
        ),
        "unit_application_role": (
            value.unit_applications[0].role.value if value.unit_applications else None
        ),
        "unit_quantity_semantics": (
            value.unit_applications[0].quantity_semantics if value.unit_applications else None
        ),
        "unit_dimension": (
            value.unit_applications[0].dimension.value if value.unit_applications else None
        ),
        "display_unit_id": (
            value.unit_applications[0].unit_id if value.unit_applications else None
        ),
        "observations": [
            scalar_distribution_observation_canonical(item)
            for item in value.computation.observations
        ],
        "candidates": [
            scalar_distribution_candidate_canonical(item) for item in value.computation.candidates
        ],
        "recommended_families": [item.value for item in value.computation.recommended_families],
        "recommendation_method": SCALAR_DISTRIBUTION_RECOMMENDATION_METHOD,
        "algorithm_version": manifest.algorithm_version,
        "python_version": manifest.python_version,
        "numpy_version": manifest.numpy_version,
        "scipy_version": manifest.scipy_version,
        "rng": manifest.rng,
        "source_sha256": manifest.source_sha256,
        "lock_sha256": manifest.lock_sha256,
        "environment_sha256": manifest.environment_sha256,
        "artifact_id": value.artifact_id,
        "artifact_sha256": value.artifact_sha256,
    }


def _distribution_selection_values(
    value: ScalarDistributionSelectionContent,
) -> dict[str, object]:
    return {
        "distribution_result_id": value.distribution_result_id,
        "distribution_result_revision_id": value.distribution_result_revision_id,
        "selected_family": value.selected_family.value,
        "candidate_sha256": value.candidate_sha256,
        "selection_reason": value.selection_reason,
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
_DISTRIBUTION_RESULT_TABLES = TypedRevisionTables(
    aggregate_type=SCALAR_DISTRIBUTION_RESULT_AGGREGATE_TYPE,
    identity_table=distribution_result_table,
    revision_table=distribution_result_revision_table,
    canonical_content=scalar_distribution_result_canonical,
    content_values=_distribution_result_values,
    identity_values=lambda value: {
        "statistical_run_id": value.statistical_run_id,
        "result_kind": "scalar_distribution_comparison",
    },
)
_DISTRIBUTION_SELECTION_TABLES = TypedRevisionTables(
    aggregate_type=SCALAR_DISTRIBUTION_SELECTION_AGGREGATE_TYPE,
    identity_table=distribution_selection_table,
    revision_table=distribution_selection_revision_table,
    canonical_content=scalar_distribution_selection_canonical,
    content_values=_distribution_selection_values,
    identity_values=lambda value: {
        "distribution_result_id": value.distribution_result_id,
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
        or str(row["curve_output_schema_ref"]) not in REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMAS
    ):
        raise StatisticsConflict("replicate Statistical Plan violates its typed contract")
    distribution = None
    if bool(row["scalar_distribution_enabled"]):
        if row["distribution_seed"] is None or row["distribution_bootstrap_samples"] is None:
            raise StatisticsConflict("replicate distribution Plan options are incomplete")
        unit_profile = None
        if row["unit_profile_id"] is not None:
            if row["unit_profile_revision_id"] is None or row["unit_profile_sha256"] is None:
                raise StatisticsConflict("replicate distribution Unit Profile pin is incomplete")
            unit_profile = UnitProfilePin(
                cast(UUID, row["unit_profile_id"]),
                cast(UUID, row["unit_profile_revision_id"]),
                str(row["unit_profile_sha256"]),
            )
        distribution = ScalarDistributionAnalysisOptions(
            seed=int(row["distribution_seed"]),
            bootstrap_samples=int(row["distribution_bootstrap_samples"]),
            unit_profile=unit_profile,
        )
    return ReferenceTensileReplicatePlanContent(
        plan_label=str(row["plan_label"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        sample_count=int(row["sample_count"]),
        curve_output_schema_ref=str(row["curve_output_schema_ref"]),
        scalar_distribution=distribution,
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


def _distribution_observation(value: dict[str, Any]) -> ScalarDistributionObservation:
    scalar = value.get("value_pa")
    return ScalarDistributionObservation(
        ordinal=int(value["ordinal"]),
        dataset_id=UUID(str(value["dataset_id"])),
        dataset_revision_id=UUID(str(value["dataset_revision_id"])),
        test_run_id=UUID(str(value["test_run_id"])),
        test_run_revision_id=UUID(str(value["test_run_revision_id"])),
        value_pa=float(scalar) if scalar is not None else None,
        quality=ObservationQuality(str(value["quality"])),
        outlier_assessment=OutlierAssessmentState(str(value["outlier_assessment"])),
    )


def _distribution_candidate(value: dict[str, Any]) -> ScalarDistributionCandidate:
    return ScalarDistributionCandidate(
        family=DistributionFamily(str(value["family"])),
        status=DistributionCandidateStatus(str(value["status"])),
        support=str(value["support"]),
        estimator=str(value["estimator"]),
        parameters=tuple(
            DistributionParameter(
                name=str(item["name"]),
                value=float(item["estimate"]),
                unit_id=str(item["unit_id"]) if item.get("unit_id") is not None else None,
            )
            for item in cast(list[dict[str, Any]], value["parameters"])
        ),
        log_likelihood=(
            float(value["log_likelihood"]) if value.get("log_likelihood") is not None else None
        ),
        aicc=float(value["aicc"]) if value.get("aicc") is not None else None,
        bic=float(value["bic"]) if value.get("bic") is not None else None,
        anderson_darling=(
            float(value["anderson_darling"]) if value.get("anderson_darling") is not None else None
        ),
        bootstrap_p_value=(
            float(value["bootstrap_p_value"])
            if value.get("bootstrap_p_value") is not None
            else None
        ),
        bootstrap_success_count=int(value["bootstrap_success_count"]),
        bootstrap_failure_count=int(value["bootstrap_failure_count"]),
        delta_aicc=(float(value["delta_aicc"]) if value.get("delta_aicc") is not None else None),
        recommended=bool(value["recommended"]),
        reason_codes=tuple(str(item) for item in value["reason_codes"]),
        warnings=tuple(str(item) for item in value["warnings"]),
        candidate_sha256=str(value["candidate_sha256"]),
    )


def _distribution_result_content(row: Any) -> ScalarDistributionResultContent:
    if (
        str(row["result_kind"]) != "scalar_distribution_comparison"
        or str(row["scalar_feature"]) != REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE
        or int(row["minimum_sample_count"]) != 8
        or int(row["small_sample_warning_below"]) != 20
        or str(row["recommendation_method"]) != SCALAR_DISTRIBUTION_RECOMMENDATION_METHOD
        or str(row["algorithm_version"]) != SCALAR_DISTRIBUTION_ALGORITHM_VERSION
        or str(row["rng"]) != SCALAR_DISTRIBUTION_RNG
    ):
        raise StatisticsConflict("scalar-distribution Result violates its typed contract")
    unit_profile = None
    if row["unit_profile_id"] is not None:
        if row["unit_profile_revision_id"] is None or row["unit_profile_sha256"] is None:
            raise StatisticsConflict("scalar-distribution Unit Profile pin is incomplete")
        unit_profile = UnitProfilePin(
            cast(UUID, row["unit_profile_id"]),
            cast(UUID, row["unit_profile_revision_id"]),
            str(row["unit_profile_sha256"]),
        )
    applications = (
        (
            UnitApplication(
                location=str(row["unit_application_location"]),
                role=UnitApplicationRole(str(row["unit_application_role"])),
                quantity_semantics=str(row["unit_quantity_semantics"]),
                dimension=DimensionId(str(row["unit_dimension"])),
                unit_id=str(row["display_unit_id"]),
            ),
        )
        if row["unit_application_location"] is not None
        else ()
    )
    manifest = ScalarDistributionRuntimeManifest(
        algorithm_version=str(row["algorithm_version"]),
        schema_ref=SCALAR_DISTRIBUTION_RESULT_SCHEMA,
        python_version=str(row["python_version"]),
        numpy_version=str(row["numpy_version"]),
        scipy_version=str(row["scipy_version"]),
        rng=str(row["rng"]),
        source_sha256=str(row["source_sha256"]),
        lock_sha256=str(row["lock_sha256"]),
        environment_sha256=str(row["environment_sha256"]),
    )
    observations = tuple(
        _distribution_observation(item) for item in cast(list[dict[str, Any]], row["observations"])
    )
    candidates = tuple(
        _distribution_candidate(item) for item in cast(list[dict[str, Any]], row["candidates"])
    )
    if len(observations) != int(row["sample_count"]):
        raise StatisticsConflict("scalar-distribution observation count has changed")
    return ScalarDistributionResultContent(
        statistical_run_id=cast(UUID, row["statistical_run_id"]),
        statistical_result_id=cast(UUID, row["statistical_result_id"]),
        statistical_result_revision_id=cast(UUID, row["statistical_result_revision_id"]),
        plan_id=cast(UUID, row["plan_id"]),
        plan_revision_id=cast(UUID, row["plan_revision_id"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        artifact_id=cast(UUID, row["artifact_id"]),
        artifact_sha256=str(row["artifact_sha256"]),
        options=ScalarDistributionAnalysisOptions(
            seed=int(row["seed"]),
            bootstrap_samples=int(row["bootstrap_samples"]),
            unit_profile=unit_profile,
        ),
        unit_applications=applications,
        computation=ScalarDistributionComputation(
            observations=observations,
            candidates=candidates,
            recommended_families=tuple(
                DistributionFamily(str(item)) for item in row["recommended_families"]
            ),
            manifest=manifest,
        ),
    )


def _distribution_selection_content(row: Any) -> ScalarDistributionSelectionContent:
    return ScalarDistributionSelectionContent(
        distribution_result_id=cast(UUID, row["distribution_result_id"]),
        distribution_result_revision_id=cast(UUID, row["distribution_result_revision_id"]),
        selected_family=DistributionFamily(str(row["selected_family"])),
        candidate_sha256=str(row["candidate_sha256"]),
        selection_reason=str(row["selection_reason"]),
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
        scalar_distribution_result_id=cast(UUID | None, row["scalar_distribution_result_id"]),
        scalar_distribution_result_revision_id=cast(
            UUID | None, row["scalar_distribution_result_revision_id"]
        ),
        scalar_distribution_artifact_id=cast(UUID | None, row["scalar_distribution_artifact_id"]),
        scalar_distribution_sha256=cast(str | None, row["scalar_distribution_sha256"]),
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

    def distribution_result_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ScalarDistributionResultContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_DISTRIBUTION_RESULT_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def distribution_selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ScalarDistributionSelectionContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_DISTRIBUTION_SELECTION_TABLES,
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
            revision.c.scalar_distribution_enabled,
            revision.c.distribution_seed,
            revision.c.distribution_bootstrap_samples,
            revision.c.unit_profile_id,
            revision.c.unit_profile_revision_id,
            revision.c.unit_profile_sha256,
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
    def _distribution_result_statement(*, current: bool) -> sa.Select[Any]:
        revision = distribution_result_revision_table
        statement = sa.select(
            distribution_result_table.c.id.label("identity_id"),
            *_revision_columns(revision),
            *(
                revision.c[column.name]
                for column in revision.c
                if column.name
                not in {
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
            ),
        ).select_from(
            distribution_result_table.join(
                revision,
                sa.and_(
                    revision.c.aggregate_id == distribution_result_table.c.id,
                    revision.c.organization_id == distribution_result_table.c.organization_id,
                    revision.c.project_id == distribution_result_table.c.project_id,
                ),
            )
        )
        if current:
            statement = statement.where(
                revision.c.id == distribution_result_table.c.current_revision_id
            )
        return statement

    def get_distribution_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
        revision_id: UUID | None = None,
    ) -> ScalarDistributionResultSnapshot:
        statement = self._distribution_result_statement(current=revision_id is None).where(
            distribution_result_table.c.organization_id == context.organization_id,
            distribution_result_table.c.project_id == context.project_id,
            distribution_result_table.c.id == result_id,
        )
        if revision_id is not None:
            statement = statement.where(distribution_result_revision_table.c.id == revision_id)
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("scalar-distribution Result is not visible")
        return ScalarDistributionResultSnapshot(
            cast(UUID, row["identity_id"]),
            ReplicateRevisionSnapshot(
                _record(row, SCALAR_DISTRIBUTION_RESULT_AGGREGATE_TYPE),
                _distribution_result_content(row),
            ),
        )

    @staticmethod
    def _distribution_selection_statement() -> sa.Select[Any]:
        revision = distribution_selection_revision_table
        return sa.select(
            distribution_selection_table.c.id.label("identity_id"),
            *_revision_columns(revision),
            revision.c.distribution_result_id,
            revision.c.distribution_result_revision_id,
            revision.c.selected_family,
            revision.c.candidate_sha256,
            revision.c.selection_reason,
        ).select_from(
            distribution_selection_table.join(
                revision,
                sa.and_(
                    revision.c.id == distribution_selection_table.c.current_revision_id,
                    revision.c.aggregate_id == distribution_selection_table.c.id,
                    revision.c.organization_id == distribution_selection_table.c.organization_id,
                    revision.c.project_id == distribution_selection_table.c.project_id,
                ),
            )
        )

    @staticmethod
    def _distribution_selection_snapshot(row: Any) -> ScalarDistributionSelectionSnapshot:
        return ScalarDistributionSelectionSnapshot(
            cast(UUID, row["identity_id"]),
            ReplicateRevisionSnapshot(
                _record(row, SCALAR_DISTRIBUTION_SELECTION_AGGREGATE_TYPE),
                _distribution_selection_content(row),
            ),
        )

    def get_distribution_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> ScalarDistributionSelectionSnapshot:
        statement = self._distribution_selection_statement().where(
            distribution_selection_table.c.organization_id == context.organization_id,
            distribution_selection_table.c.project_id == context.project_id,
            distribution_selection_table.c.id == selection_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise StatisticsNotFound("scalar-distribution selection is not visible")
        return self._distribution_selection_snapshot(row)

    def list_distribution_selections(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        result_id: UUID,
    ) -> tuple[ScalarDistributionSelectionSnapshot, ...]:
        statement = (
            self._distribution_selection_statement()
            .where(
                distribution_selection_table.c.organization_id == context.organization_id,
                distribution_selection_table.c.project_id == context.project_id,
                distribution_selection_revision_table.c.distribution_result_id == result_id,
            )
            .order_by(distribution_selection_table.c.updated_at.desc())
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._distribution_selection_snapshot(row) for row in rows)

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
            "scalar_distribution_result_id": run.scalar_distribution_result_id,
            "scalar_distribution_result_revision_id": (run.scalar_distribution_result_revision_id),
            "scalar_distribution_artifact_id": run.scalar_distribution_artifact_id,
            "scalar_distribution_sha256": run.scalar_distribution_sha256,
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
        distribution_result: ScalarDistributionResultSnapshot | None,
        qc_observations: tuple[QcObservation, ...],
    ) -> ReplicateStatisticalRun:
        content = result.current.content
        distribution = (
            distribution_result.current.content if distribution_result is not None else None
        )
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
                "scalar_distribution_result_id": (
                    distribution_result.id if distribution_result is not None else None
                ),
                "scalar_distribution_result_revision_id": (
                    distribution_result.current.record.revision_id
                    if distribution_result is not None
                    else None
                ),
                "scalar_distribution_artifact_id": (
                    distribution.artifact_id if distribution is not None else None
                ),
                "scalar_distribution_sha256": (
                    distribution.artifact_sha256 if distribution is not None else None
                ),
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

    def list_runs(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_revision_id: UUID,
        limit: int,
    ) -> tuple[ReplicateStatisticalRun, ...]:
        statement = (
            sa.select(run_table)
            .where(
                run_table.c.organization_id == context.organization_id,
                run_table.c.project_id == context.project_id,
                run_table.c.plan_revision_id == plan_revision_id,
            )
            .order_by(run_table.c.started_at.desc())
            .limit(limit)
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
            return tuple(self._load_run_related(session, row) for row in rows)
