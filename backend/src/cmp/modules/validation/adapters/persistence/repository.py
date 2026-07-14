"""RLS-bound PostgreSQL persistence for T-27 validation template/Plan/run facts."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
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
from cmp.modules.validation.application.service import (
    VALIDATION_PLAN_AGGREGATE_TYPE,
    VALIDATION_TEMPLATE_AGGREGATE_TYPE,
    NumericalHealthReport,
    ReferenceValidationResult,
    RevisionSnapshot,
    ValidationPlanSnapshot,
    ValidationRepository,
    ValidationResponseExtraction,
    ValidationRun,
    ValidationRunDetail,
    ValidationRunResultManifest,
    ValidationTemplateSnapshot,
)
from cmp.modules.validation.domain.reference_result_interpretation import (
    HoldoutIndependenceStatus,
    NumericalHealthAssessment,
    NumericalHealthStatus,
    ReferenceComparisonPoint,
    ReferenceMetricAssessment,
    ReferenceNumericalHealthReportContent,
    ReferenceValidationResultContent,
    ResponseExtractionStatus,
    ValidationVerdict,
)
from cmp.modules.validation.domain.reference_virtual_specimen import (
    ReferenceValidationPlanContent,
    ReferenceVirtualSpecimenTemplateContent,
    SolverTerminationStatus,
    ValidationArtifactReference,
    ValidationConflict,
    ValidationExecutionMode,
    ValidationNotFound,
    ValidationRunResultManifestContent,
    ValidationRunStatus,
    reference_validation_plan_canonical,
    reference_virtual_specimen_template_canonical,
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


type ValidationRunProvenanceHook = Callable[
    [
        Session,
        SecurityContext,
        AuthorizationDecision,
        ValidationRun,
        ValidationRunResultManifest,
        ValidationRunStatus,
        datetime,
    ],
    None,
]
type ValidationRunAuditHook = Callable[[Session, SecurityContext, UUID, str, str, datetime], None]
type ValidationResultProvenanceHook = Callable[
    [
        Session,
        SecurityContext,
        AuthorizationDecision,
        ValidationRun,
        ValidationRunResultManifest,
        ReferenceValidationResult,
        datetime,
    ],
    None,
]


metadata = sa.MetaData()


def _identity_table(name: str, *, label: str, kind: str) -> sa.Table:
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
        sa.Column(label, sa.String(160), nullable=False),
        sa.Column(kind, sa.String(100), nullable=False),
        schema="validation",
    )


def _revision_prefix(name: str) -> list[sa.Column[Any]]:
    del name
    return [
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
    ]


validation_template_table = _identity_table(
    "validation_template", label="template_label", kind="template_kind"
)
validation_template_revision_table = sa.Table(
    "validation_template_revision",
    metadata,
    *_revision_prefix("validation_template_revision"),
    sa.Column("template_kind", sa.String(100), nullable=False),
    sa.Column("gauge_length_m", sa.Double(), nullable=False),
    sa.Column("cross_section_area_m2", sa.Double(), nullable=False),
    sa.Column("axial_element_count", sa.Integer(), nullable=False),
    sa.Column("axial_displacement_end_m", sa.Double(), nullable=False),
    sa.Column("output_sample_count", sa.Integer(), nullable=False),
    sa.Column("result_extraction_profile_id", sa.String(255), nullable=False),
    sa.Column("metric_profile_id", sa.String(255), nullable=False),
    sa.Column("target_solver", sa.String(64), nullable=False),
    sa.Column("target_version", sa.String(64), nullable=False),
    sa.Column("target_unit_system", sa.String(64), nullable=False),
    sa.Column("runner_command_id", sa.String(100), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="validation",
)

validation_plan_table = _identity_table("validation_plan", label="plan_label", kind="plan_kind")
validation_plan_revision_table = sa.Table(
    "validation_plan_revision",
    metadata,
    *_revision_prefix("validation_plan_revision"),
    sa.Column("plan_kind", sa.String(100), nullable=False),
    sa.Column("template_id", sa.Uuid(), nullable=False),
    sa.Column("template_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("experimental_selection_id", sa.Uuid(), nullable=False),
    sa.Column("experimental_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("runner_id", sa.String(255), nullable=False),
    sa.Column("runner_version", sa.String(64), nullable=False),
    sa.Column("runner_digest", sa.CHAR(64), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="validation",
)

validation_run_table = sa.Table(
    "validation_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("template_id", sa.Uuid(), nullable=False),
    sa.Column("template_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("experimental_selection_id", sa.Uuid(), nullable=False),
    sa.Column("experimental_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("execution_mode", sa.String(32), nullable=False),
    sa.Column("runner_id", sa.String(255), nullable=False),
    sa.Column("runner_version", sa.String(64), nullable=False),
    sa.Column("runner_digest", sa.CHAR(64), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("deck_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("deck_sha256", sa.CHAR(64), nullable=False),
    sa.Column("external_job_reference", sa.String(256), nullable=True),
    sa.Column("result_manifest_id", sa.Uuid(), nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    sa.Column("change_reason", sa.Text(), nullable=False),
    schema="validation",
)

validation_run_result_manifest_table = sa.Table(
    "validation_run_result_manifest",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("validation_run_id", sa.Uuid(), nullable=False),
    sa.Column("execution_mode", sa.String(32), nullable=False),
    sa.Column("solver_termination", sa.String(32), nullable=False),
    sa.Column("external_job_reference", sa.String(256), nullable=True),
    sa.Column("deck_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("deck_sha256", sa.CHAR(64), nullable=False),
    sa.Column("stdout_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("stdout_sha256", sa.CHAR(64), nullable=False),
    sa.Column("stderr_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("stderr_sha256", sa.CHAR(64), nullable=False),
    sa.Column("native_result_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("native_result_sha256", sa.CHAR(64), nullable=True),
    sa.Column("native_result_state", sa.String(32), nullable=False),
    sa.Column("manifest_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("manifest_sha256", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="validation",
)

validation_response_extraction_table = sa.Table(
    "validation_response_extraction",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("validation_run_id", sa.Uuid(), nullable=False),
    sa.Column("validation_result_manifest_id", sa.Uuid(), nullable=False),
    sa.Column("source_native_result_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("source_native_result_sha256", sa.CHAR(64), nullable=True),
    sa.Column("extraction_status", sa.String(32), nullable=False),
    sa.Column("normalized_response_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("normalized_response_sha256", sa.CHAR(64), nullable=True),
    sa.Column("point_count", sa.Integer(), nullable=True),
    sa.Column("reason_code", sa.String(100), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="validation",
)

validation_numerical_health_report_table = sa.Table(
    "validation_numerical_health_report",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("validation_run_id", sa.Uuid(), nullable=False),
    sa.Column("validation_result_manifest_id", sa.Uuid(), nullable=False),
    sa.Column("response_extraction_id", sa.Uuid(), nullable=False),
    sa.Column("health_status", sa.String(32), nullable=False),
    sa.Column("solver_termination", sa.String(32), nullable=False),
    sa.Column("native_result_state", sa.String(32), nullable=False),
    sa.Column("expected_output_point_count", sa.Integer(), nullable=False),
    sa.Column("observed_output_point_count", sa.Integer(), nullable=True),
    sa.Column("output_complete", sa.Boolean(), nullable=False),
    sa.Column("finite_values", sa.Boolean(), nullable=False),
    sa.Column("strictly_increasing_strain", sa.Boolean(), nullable=False),
    sa.Column("reason_code", sa.String(100), nullable=True),
    sa.Column("report_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("report_sha256", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="validation",
)

validation_result_table = sa.Table(
    "validation_result",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("validation_run_id", sa.Uuid(), nullable=False),
    sa.Column("validation_result_manifest_id", sa.Uuid(), nullable=False),
    sa.Column("response_extraction_id", sa.Uuid(), nullable=False),
    sa.Column("numerical_health_report_id", sa.Uuid(), nullable=False),
    sa.Column("experimental_selection_id", sa.Uuid(), nullable=False),
    sa.Column("experimental_selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("normalized_response_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("normalized_response_sha256", sa.CHAR(64), nullable=True),
    sa.Column("numerical_health_report_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("numerical_health_report_sha256", sa.CHAR(64), nullable=False),
    sa.Column("metric_profile_id", sa.String(255), nullable=False),
    sa.Column("threshold_profile_id", sa.String(255), nullable=False),
    sa.Column("alignment_profile_id", sa.String(255), nullable=False),
    sa.Column("relative_rmse_threshold", sa.Double(), nullable=False),
    sa.Column("experimental_point_count", sa.Integer(), nullable=False),
    sa.Column("simulated_point_count", sa.Integer(), nullable=True),
    sa.Column("compared_point_count", sa.Integer(), nullable=False),
    sa.Column("root_mean_squared_error_pa", sa.Double(), nullable=True),
    sa.Column("relative_root_mean_squared_error", sa.Double(), nullable=True),
    sa.Column("normalization_stress_scale_pa", sa.Double(), nullable=True),
    sa.Column("holdout_independence", sa.String(64), nullable=False),
    sa.Column("verdict", sa.String(32), nullable=False),
    sa.Column("reason_code", sa.String(100), nullable=True),
    sa.Column("result_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("result_sha256", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("change_reason", sa.Text(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="validation",
)

validation_result_comparison_point_table = sa.Table(
    "validation_result_comparison_point",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("validation_result_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("engineering_strain", sa.Double(), nullable=False),
    sa.Column("observed_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("simulated_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("residual_engineering_stress_pa", sa.Double(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="validation",
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
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
        change_reason=str(row["change_reason"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _template_content(row: Any) -> ReferenceVirtualSpecimenTemplateContent:
    return ReferenceVirtualSpecimenTemplateContent(
        template_label=str(row["template_label"]),
        gauge_length_m=float(row["gauge_length_m"]),
        cross_section_area_m2=float(row["cross_section_area_m2"]),
        axial_element_count=int(row["axial_element_count"]),
        axial_displacement_end_m=float(row["axial_displacement_end_m"]),
        output_sample_count=int(row["output_sample_count"]),
        result_extraction_profile_id=str(row["result_extraction_profile_id"]),
        metric_profile_id=str(row["metric_profile_id"]),
        template_kind=str(row["template_kind"]),
        target_solver=str(row["target_solver"]),
        target_version=str(row["target_version"]),
        target_unit_system=str(row["target_unit_system"]),
        runner_command_id=str(row["runner_command_id"]),
        non_production=bool(row["non_production"]),
    )


def _template_values(value: ReferenceVirtualSpecimenTemplateContent) -> dict[str, object]:
    return {
        "template_kind": value.template_kind,
        "gauge_length_m": value.gauge_length_m,
        "cross_section_area_m2": value.cross_section_area_m2,
        "axial_element_count": value.axial_element_count,
        "axial_displacement_end_m": value.axial_displacement_end_m,
        "output_sample_count": value.output_sample_count,
        "result_extraction_profile_id": value.result_extraction_profile_id,
        "metric_profile_id": value.metric_profile_id,
        "target_solver": value.target_solver,
        "target_version": value.target_version,
        "target_unit_system": value.target_unit_system,
        "runner_command_id": value.runner_command_id,
        "non_production": value.non_production,
    }


def _plan_content(row: Any) -> ReferenceValidationPlanContent:
    return ReferenceValidationPlanContent(
        plan_label=str(row["plan_label"]),
        template_id=cast(UUID, row["template_id"]),
        template_revision_id=cast(UUID, row["template_revision_id"]),
        material_model_id=cast(UUID, row["material_model_id"]),
        material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
        solver_card_id=cast(UUID, row["solver_card_id"]),
        solver_card_revision_id=cast(UUID, row["solver_card_revision_id"]),
        experimental_selection_id=cast(UUID, row["experimental_selection_id"]),
        experimental_selection_revision_id=cast(UUID, row["experimental_selection_revision_id"]),
        runner_id=str(row["runner_id"]),
        runner_version=str(row["runner_version"]),
        runner_digest=str(row["runner_digest"]),
        plan_kind=str(row["plan_kind"]),
        non_production=bool(row["non_production"]),
    )


def _plan_values(value: ReferenceValidationPlanContent) -> dict[str, object]:
    return {
        "plan_kind": value.plan_kind,
        "template_id": value.template_id,
        "template_revision_id": value.template_revision_id,
        "material_model_id": value.material_model_id,
        "material_model_revision_id": value.material_model_revision_id,
        "solver_card_id": value.solver_card_id,
        "solver_card_revision_id": value.solver_card_revision_id,
        "experimental_selection_id": value.experimental_selection_id,
        "experimental_selection_revision_id": value.experimental_selection_revision_id,
        "runner_id": value.runner_id,
        "runner_version": value.runner_version,
        "runner_digest": value.runner_digest,
        "non_production": value.non_production,
    }


_TEMPLATE_TABLES: TypedRevisionTables[ReferenceVirtualSpecimenTemplateContent] = (
    TypedRevisionTables(
        aggregate_type=VALIDATION_TEMPLATE_AGGREGATE_TYPE,
        identity_table=validation_template_table,
        revision_table=validation_template_revision_table,
        canonical_content=reference_virtual_specimen_template_canonical,
        content_values=_template_values,
        identity_values=lambda value: {
            "template_label": value.template_label,
            "template_kind": value.template_kind,
        },
    )
)

_PLAN_TABLES: TypedRevisionTables[ReferenceValidationPlanContent] = TypedRevisionTables(
    aggregate_type=VALIDATION_PLAN_AGGREGATE_TYPE,
    identity_table=validation_plan_table,
    revision_table=validation_plan_revision_table,
    canonical_content=reference_validation_plan_canonical,
    content_values=_plan_values,
    identity_values=lambda value: {
        "plan_label": value.plan_label,
        "plan_kind": value.plan_kind,
    },
)


def _run(row: Any) -> ValidationRun:
    return ValidationRun(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        plan_id=cast(UUID, row["plan_id"]),
        plan_revision_id=cast(UUID, row["plan_revision_id"]),
        template_id=cast(UUID, row["template_id"]),
        template_revision_id=cast(UUID, row["template_revision_id"]),
        material_model_id=cast(UUID, row["material_model_id"]),
        material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
        solver_card_id=cast(UUID, row["solver_card_id"]),
        solver_card_revision_id=cast(UUID, row["solver_card_revision_id"]),
        experimental_selection_id=cast(UUID, row["experimental_selection_id"]),
        experimental_selection_revision_id=cast(UUID, row["experimental_selection_revision_id"]),
        execution_mode=ValidationExecutionMode(str(row["execution_mode"])),
        runner_id=str(row["runner_id"]),
        runner_version=str(row["runner_version"]),
        runner_digest=str(row["runner_digest"]),
        status=ValidationRunStatus(str(row["status"])),
        deck=ValidationArtifactReference(
            cast(UUID, row["deck_artifact_id"]), str(row["deck_sha256"])
        ),
        external_job_reference=cast(str | None, row["external_job_reference"]),
        failure_code=cast(str | None, row["failure_code"]),
        submitted_at=cast(datetime, row["submitted_at"]),
        started_at=cast(datetime | None, row["started_at"]),
        ended_at=cast(datetime | None, row["ended_at"]),
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
        change_reason=str(row["change_reason"]),
    )


def _manifest(row: Any) -> ValidationRunResultManifest:
    native_id = cast(UUID | None, row["native_result_artifact_id"])
    native_digest = cast(str | None, row["native_result_sha256"])
    native = (
        ValidationArtifactReference(native_id, native_digest)
        if native_id is not None and native_digest is not None
        else None
    )
    content = ValidationRunResultManifestContent(
        validation_run_id=cast(UUID, row["validation_run_id"]),
        execution_mode=ValidationExecutionMode(str(row["execution_mode"])),
        solver_termination=SolverTerminationStatus(str(row["solver_termination"])),
        external_job_reference=cast(str | None, row["external_job_reference"]),
        deck=ValidationArtifactReference(
            cast(UUID, row["deck_artifact_id"]), str(row["deck_sha256"])
        ),
        stdout=ValidationArtifactReference(
            cast(UUID, row["stdout_artifact_id"]), str(row["stdout_sha256"])
        ),
        stderr=ValidationArtifactReference(
            cast(UUID, row["stderr_artifact_id"]), str(row["stderr_sha256"])
        ),
        native_result=native,
        native_result_state=str(row["native_result_state"]),
    )
    return ValidationRunResultManifest(
        id=cast(UUID, row["id"]),
        content=content,
        manifest_artifact=ValidationArtifactReference(
            cast(UUID, row["manifest_artifact_id"]), str(row["manifest_sha256"])
        ),
        manifest_sha256=str(row["manifest_sha256"]),
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
    )


def _optional_reference(
    row: Any, id_column: str, digest_column: str
) -> ValidationArtifactReference | None:
    artifact_id = cast(UUID | None, row[id_column])
    digest = cast(str | None, row[digest_column])
    if artifact_id is None and digest is None:
        return None
    if artifact_id is None or digest is None:
        raise ValidationNotFound("Validation Artifact pointer columns are inconsistent")
    return ValidationArtifactReference(artifact_id, digest)


def _response_extraction(row: Any) -> ValidationResponseExtraction:
    return ValidationResponseExtraction(
        id=cast(UUID, row["id"]),
        validation_run_id=cast(UUID, row["validation_run_id"]),
        validation_result_manifest_id=cast(UUID, row["validation_result_manifest_id"]),
        source_native_result=_optional_reference(
            row, "source_native_result_artifact_id", "source_native_result_sha256"
        ),
        status=ResponseExtractionStatus(str(row["extraction_status"])),
        normalized_response=_optional_reference(
            row, "normalized_response_artifact_id", "normalized_response_sha256"
        ),
        point_count=cast(int | None, row["point_count"]),
        reason_code=cast(str | None, row["reason_code"]),
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
    )


def _health_report(row: Any) -> NumericalHealthReport:
    assessment = NumericalHealthAssessment(
        status=NumericalHealthStatus(str(row["health_status"])),
        expected_point_count=int(row["expected_output_point_count"]),
        observed_point_count=cast(int | None, row["observed_output_point_count"]),
        output_complete=bool(row["output_complete"]),
        finite_values=bool(row["finite_values"]),
        strictly_increasing_strain=bool(row["strictly_increasing_strain"]),
        reason_code=cast(str | None, row["reason_code"]),
    )
    content = ReferenceNumericalHealthReportContent(
        validation_run_id=cast(UUID, row["validation_run_id"]),
        validation_result_manifest_id=cast(UUID, row["validation_result_manifest_id"]),
        response_extraction_id=cast(UUID, row["response_extraction_id"]),
        solver_termination=SolverTerminationStatus(str(row["solver_termination"])),
        native_result_state=str(row["native_result_state"]),
        assessment=assessment,
    )
    report_artifact = ValidationArtifactReference(
        cast(UUID, row["report_artifact_id"]), str(row["report_sha256"])
    )
    return NumericalHealthReport(
        id=cast(UUID, row["id"]),
        validation_run_id=content.validation_run_id,
        validation_result_manifest_id=content.validation_result_manifest_id,
        response_extraction_id=content.response_extraction_id,
        content=content,
        report_artifact=report_artifact,
        report_sha256=str(row["report_sha256"]),
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
    )


def _validation_result(
    row: Any,
    extraction: ValidationResponseExtraction,
    health: NumericalHealthReport,
    points: tuple[ReferenceComparisonPoint, ...],
) -> ReferenceValidationResult:
    compared_point_count = int(row["compared_point_count"])
    if compared_point_count != len(points):
        raise ValidationNotFound("Validation Result comparison point count is inconsistent")
    rmse = cast(float | None, row["root_mean_squared_error_pa"])
    relative_rmse = cast(float | None, row["relative_root_mean_squared_error"])
    scale = cast(float | None, row["normalization_stress_scale_pa"])
    if rmse is None and relative_rmse is None and scale is None:
        metrics: ReferenceMetricAssessment | None = None
    elif rmse is None or relative_rmse is None or scale is None:
        raise ValidationNotFound("Validation Result metric columns are inconsistent")
    else:
        metrics = ReferenceMetricAssessment(float(rmse), float(relative_rmse), float(scale), points)
    content = ReferenceValidationResultContent(
        validation_run_id=cast(UUID, row["validation_run_id"]),
        validation_result_manifest_id=cast(UUID, row["validation_result_manifest_id"]),
        response_extraction_id=cast(UUID, row["response_extraction_id"]),
        numerical_health_report_id=cast(UUID, row["numerical_health_report_id"]),
        experimental_selection_id=cast(UUID, row["experimental_selection_id"]),
        experimental_selection_revision_id=cast(UUID, row["experimental_selection_revision_id"]),
        normalized_response=_optional_reference(
            row, "normalized_response_artifact_id", "normalized_response_sha256"
        ),
        numerical_health_report=ValidationArtifactReference(
            cast(UUID, row["numerical_health_report_artifact_id"]),
            str(row["numerical_health_report_sha256"]),
        ),
        metric_profile_id=str(row["metric_profile_id"]),
        threshold_profile_id=str(row["threshold_profile_id"]),
        alignment_profile_id=str(row["alignment_profile_id"]),
        relative_rmse_threshold=float(row["relative_rmse_threshold"]),
        experimental_point_count=int(row["experimental_point_count"]),
        simulated_point_count=cast(int | None, row["simulated_point_count"]),
        metrics=metrics,
        holdout_independence=HoldoutIndependenceStatus(str(row["holdout_independence"])),
        verdict=ValidationVerdict(str(row["verdict"])),
        reason_code=cast(str | None, row["reason_code"]),
    )
    result_artifact = ValidationArtifactReference(
        cast(UUID, row["result_artifact_id"]), str(row["result_sha256"])
    )
    return ReferenceValidationResult(
        id=cast(UUID, row["id"]),
        validation_run_id=content.validation_run_id,
        validation_result_manifest_id=content.validation_result_manifest_id,
        response_extraction=extraction,
        numerical_health_report=health,
        content=content,
        result_artifact=result_artifact,
        result_sha256=str(row["result_sha256"]),
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
    )


class SqlAlchemyValidationRepository(ValidationRepository):
    """Persist explicit typed Validation tables under transaction-local RLS context."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[SqlRevisionHook] = (),
        result_provenance_hook: ValidationRunProvenanceHook,
        result_audit_hook: ValidationRunAuditHook,
        evaluation_provenance_hook: ValidationResultProvenanceHook,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = tuple(revision_hooks)
        self._result_provenance_hook = result_provenance_hook
        self._result_audit_hook = result_audit_hook
        self._evaluation_provenance_hook = evaluation_provenance_hook

    def _bind(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @contextmanager
    def _session(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def template_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceVirtualSpecimenTemplateContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TEMPLATE_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceValidationPlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_PLAN_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _template_statement() -> sa.Select[Any]:
        identity = validation_template_table
        revision = validation_template_revision_table
        return sa.select(
            identity.c.id.label("template_id"),
            identity.c.template_label.label("template_label"),
            *revision.c,
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
    def _plan_statement() -> sa.Select[Any]:
        identity = validation_plan_table
        revision = validation_plan_revision_table
        return sa.select(
            identity.c.id.label("plan_id"),
            identity.c.plan_label.label("plan_label"),
            *revision.c,
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
    def _template_snapshot(row: Any) -> ValidationTemplateSnapshot:
        return ValidationTemplateSnapshot(
            cast(UUID, row["template_id"]),
            RevisionSnapshot(
                _record(row, VALIDATION_TEMPLATE_AGGREGATE_TYPE), _template_content(row)
            ),
        )

    @staticmethod
    def _plan_snapshot(row: Any) -> ValidationPlanSnapshot:
        return ValidationPlanSnapshot(
            cast(UUID, row["plan_id"]),
            RevisionSnapshot(_record(row, VALIDATION_PLAN_AGGREGATE_TYPE), _plan_content(row)),
        )

    def get_template(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        template_id: UUID,
    ) -> ValidationTemplateSnapshot:
        statement = self._template_statement().where(
            validation_template_table.c.id == template_id,
            validation_template_table.c.organization_id == context.organization_id,
            validation_template_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise ValidationNotFound("Validation Template is not available") from error
        if row is None:
            raise ValidationNotFound("Validation Template is not visible in this tenant")
        return self._template_snapshot(row)

    def get_template_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        template_id: UUID,
        template_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceVirtualSpecimenTemplateContent]:
        table = validation_template_revision_table
        statement = (
            sa.select(validation_template_table.c.template_label.label("template_label"), *table.c)
            .select_from(
                validation_template_table.join(
                    table,
                    sa.and_(
                        table.c.aggregate_id == validation_template_table.c.id,
                        table.c.organization_id == validation_template_table.c.organization_id,
                        table.c.project_id == validation_template_table.c.project_id,
                    ),
                )
            )
            .where(
                validation_template_table.c.id == template_id,
                table.c.id == template_revision_id,
                table.c.organization_id == context.organization_id,
                table.c.project_id == context.project_id,
            )
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise ValidationNotFound("Validation Template revision is not visible in this tenant")
        return RevisionSnapshot(
            _record(row, VALIDATION_TEMPLATE_AGGREGATE_TYPE), _template_content(row)
        )

    def list_templates(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ValidationTemplateSnapshot, ...]:
        statement = (
            self._template_statement()
            .where(
                validation_template_table.c.organization_id == context.organization_id,
                validation_template_table.c.project_id == context.project_id,
            )
            .order_by(validation_template_revision_table.c.created_at.desc())
            .limit(limit)
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._template_snapshot(row) for row in rows)

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> ValidationPlanSnapshot:
        statement = self._plan_statement().where(
            validation_plan_table.c.id == plan_id,
            validation_plan_table.c.organization_id == context.organization_id,
            validation_plan_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise ValidationNotFound("Validation Plan is not available") from error
        if row is None:
            raise ValidationNotFound("Validation Plan is not visible in this tenant")
        return self._plan_snapshot(row)

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceValidationPlanContent]:
        table = validation_plan_revision_table
        statement = (
            sa.select(validation_plan_table.c.plan_label.label("plan_label"), *table.c)
            .select_from(
                validation_plan_table.join(
                    table,
                    sa.and_(
                        table.c.aggregate_id == validation_plan_table.c.id,
                        table.c.organization_id == validation_plan_table.c.organization_id,
                        table.c.project_id == validation_plan_table.c.project_id,
                    ),
                )
            )
            .where(
                validation_plan_table.c.id == plan_id,
                table.c.id == plan_revision_id,
                table.c.organization_id == context.organization_id,
                table.c.project_id == context.project_id,
            )
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise ValidationNotFound("Validation Plan revision is not visible in this tenant")
        return RevisionSnapshot(_record(row, VALIDATION_PLAN_AGGREGATE_TYPE), _plan_content(row))

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ValidationPlanSnapshot, ...]:
        statement = (
            self._plan_statement()
            .where(
                validation_plan_table.c.organization_id == context.organization_id,
                validation_plan_table.c.project_id == context.project_id,
            )
            .order_by(validation_plan_revision_table.c.created_at.desc())
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
        run: ValidationRun,
    ) -> ValidationRun:
        values = {
            "id": run.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
            "plan_id": run.plan_id,
            "plan_revision_id": run.plan_revision_id,
            "template_id": run.template_id,
            "template_revision_id": run.template_revision_id,
            "material_model_id": run.material_model_id,
            "material_model_revision_id": run.material_model_revision_id,
            "solver_card_id": run.solver_card_id,
            "solver_card_revision_id": run.solver_card_revision_id,
            "experimental_selection_id": run.experimental_selection_id,
            "experimental_selection_revision_id": run.experimental_selection_revision_id,
            "execution_mode": run.execution_mode.value,
            "runner_id": run.runner_id,
            "runner_version": run.runner_version,
            "runner_digest": run.runner_digest,
            "status": run.status.value,
            "deck_artifact_id": run.deck.artifact_id,
            "deck_sha256": run.deck.sha256,
            "external_job_reference": run.external_job_reference,
            "result_manifest_id": None,
            "failure_code": None,
            "submitted_at": run.submitted_at,
            "started_at": None,
            "ended_at": None,
            "created_by": run.created_by,
            "request_id": run.request_id,
            "trace_id": run.trace_id,
            "change_reason": run.change_reason,
        }
        with self._session(context, decision) as session:
            try:
                row = (
                    session.execute(
                        sa.insert(validation_run_table)
                        .values(**values)
                        .returning(validation_run_table)
                    )
                    .mappings()
                    .one()
                )
            except IntegrityError as error:
                raise ValidationConflict(
                    "Validation Run conflicts with immutable Plan inputs"
                ) from error
            self._result_audit_hook(
                session,
                context,
                run.id,
                "validation.run.submit",
                run.change_reason,
                run.submitted_at,
            )
        return _run(row)

    @staticmethod
    def _validation_result_in_session(
        session: Session, *, validation_run_id: UUID
    ) -> ReferenceValidationResult | None:
        result_row = (
            session.execute(
                sa.select(validation_result_table).where(
                    validation_result_table.c.validation_run_id == validation_run_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if result_row is None:
            return None
        extraction_row = (
            session.execute(
                sa.select(validation_response_extraction_table).where(
                    validation_response_extraction_table.c.id
                    == result_row["response_extraction_id"]
                )
            )
            .mappings()
            .one_or_none()
        )
        health_row = (
            session.execute(
                sa.select(validation_numerical_health_report_table).where(
                    validation_numerical_health_report_table.c.id
                    == result_row["numerical_health_report_id"]
                )
            )
            .mappings()
            .one_or_none()
        )
        if extraction_row is None or health_row is None:
            raise ValidationNotFound("Validation Result component rows are not visible")
        point_rows = (
            session.execute(
                sa.select(validation_result_comparison_point_table)
                .where(
                    validation_result_comparison_point_table.c.validation_result_id
                    == result_row["id"]
                )
                .order_by(validation_result_comparison_point_table.c.ordinal.asc())
            )
            .mappings()
            .all()
        )
        points = tuple(
            ReferenceComparisonPoint(
                engineering_strain=float(point["engineering_strain"]),
                observed_engineering_stress_pa=float(point["observed_engineering_stress_pa"]),
                simulated_engineering_stress_pa=float(point["simulated_engineering_stress_pa"]),
                residual_engineering_stress_pa=float(point["residual_engineering_stress_pa"]),
            )
            for point in point_rows
        )
        return _validation_result(
            result_row,
            _response_extraction(extraction_row),
            _health_report(health_row),
            points,
        )

    def _detail_in_session(self, session: Session, run_id: UUID) -> ValidationRunDetail | None:
        run_row = (
            session.execute(
                sa.select(validation_run_table).where(validation_run_table.c.id == run_id)
            )
            .mappings()
            .one_or_none()
        )
        if run_row is None:
            return None
        manifest_row = (
            session.execute(
                sa.select(validation_run_result_manifest_table).where(
                    validation_run_result_manifest_table.c.validation_run_id == run_id
                )
            )
            .mappings()
            .one_or_none()
        )
        return ValidationRunDetail(
            _run(run_row),
            _manifest(manifest_row) if manifest_row else None,
            self._validation_result_in_session(session, validation_run_id=run_id),
        )

    def get_run_detail(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ValidationRunDetail:
        with self._session(context, decision) as session:
            try:
                detail = self._detail_in_session(session, run_id)
            except DBAPIError as error:
                raise ValidationNotFound("Validation Run is not available") from error
        if detail is None:
            raise ValidationNotFound("Validation Run is not visible in this tenant")
        return detail

    def start_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ValidationRun:
        now = datetime.now(UTC)
        statement = (
            sa.update(validation_run_table)
            .where(
                validation_run_table.c.id == run_id,
                validation_run_table.c.organization_id == context.organization_id,
                validation_run_table.c.project_id == context.project_id,
                validation_run_table.c.status == ValidationRunStatus.QUEUED.value,
            )
            .values(status=ValidationRunStatus.RUNNING.value, started_at=now)
            .returning(validation_run_table)
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise ValidationConflict("Validation Run is not queued or is not visible")
            self._result_audit_hook(
                session,
                context,
                run_id,
                "validation.run.start",
                "Start non-production reference mock runner",
                now,
            )
        return _run(row)

    def cancel_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        reason: str,
    ) -> ValidationRun:
        now = datetime.now(UTC)
        statement = (
            sa.update(validation_run_table)
            .where(
                validation_run_table.c.id == run_id,
                validation_run_table.c.organization_id == context.organization_id,
                validation_run_table.c.project_id == context.project_id,
                validation_run_table.c.status.in_(
                    (ValidationRunStatus.QUEUED.value, ValidationRunStatus.WAITING_MANUAL.value)
                ),
            )
            .values(
                status=ValidationRunStatus.CANCELLED.value,
                failure_code="cancelled",
                ended_at=now,
            )
            .returning(validation_run_table)
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise ValidationConflict("Validation Run cannot be cancelled in its current state")
            self._result_audit_hook(
                session,
                context,
                run_id,
                "validation.run.cancel",
                reason,
                now,
            )
        return _run(row)

    def record_result_manifest(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        manifest: ValidationRunResultManifest,
        terminal_status: ValidationRunStatus,
        failure_code: str | None,
        change_reason: str,
    ) -> ValidationRunDetail:
        if terminal_status not in {
            ValidationRunStatus.SUCCEEDED,
            ValidationRunStatus.FAILED,
        }:
            raise ValidationConflict(
                "Result Manifest requires a succeeded or failed terminal state"
            )
        if manifest.content.validation_run_id != run_id:
            raise ValidationConflict("Result Manifest is bound to a different Validation Run")
        if manifest.manifest_artifact.sha256 != manifest.manifest_sha256:
            raise ValidationConflict(
                "Result Manifest Artifact digest differs from its canonical content"
            )
        now = datetime.now(UTC)
        with self._session(context, decision) as session:
            current = self._detail_in_session(session, run_id)
            if current is None:
                raise ValidationNotFound("Validation Run is not visible in this tenant")
            if current.result_manifest is not None:
                if current.result_manifest.manifest_sha256 == manifest.manifest_sha256:
                    return current
                raise ValidationConflict(
                    "Validation Run already has a different immutable Result Manifest"
                )
            allowed = {
                ValidationExecutionMode.REFERENCE_INLINE_MOCK: ValidationRunStatus.RUNNING,
                ValidationExecutionMode.MANUAL_ATTACH: ValidationRunStatus.WAITING_MANUAL,
            }
            if current.run.status is not allowed[current.run.execution_mode]:
                raise ValidationConflict("Validation Run is not ready to collect a Result Manifest")
            if manifest.content.execution_mode is not current.run.execution_mode:
                raise ValidationConflict("Result Manifest execution mode differs from the Run")
            if manifest.content.deck != current.run.deck:
                raise ValidationConflict("Result Manifest deck differs from the pinned Run deck")
            values = {
                "id": manifest.id,
                "organization_id": context.organization_id,
                "project_id": context.project_id,
                "classification": current.run.classification.value,
                "validation_run_id": run_id,
                "execution_mode": manifest.content.execution_mode.value,
                "solver_termination": manifest.content.solver_termination.value,
                "external_job_reference": manifest.content.external_job_reference,
                "deck_artifact_id": manifest.content.deck.artifact_id,
                "deck_sha256": manifest.content.deck.sha256,
                "stdout_artifact_id": manifest.content.stdout.artifact_id,
                "stdout_sha256": manifest.content.stdout.sha256,
                "stderr_artifact_id": manifest.content.stderr.artifact_id,
                "stderr_sha256": manifest.content.stderr.sha256,
                "native_result_artifact_id": (
                    manifest.content.native_result.artifact_id
                    if manifest.content.native_result is not None
                    else None
                ),
                "native_result_sha256": (
                    manifest.content.native_result.sha256
                    if manifest.content.native_result is not None
                    else None
                ),
                "native_result_state": manifest.content.native_result_state,
                "manifest_artifact_id": manifest.manifest_artifact.artifact_id,
                "manifest_sha256": manifest.manifest_sha256,
                "created_at": manifest.created_at,
                "created_by": manifest.created_by,
            }
            try:
                session.execute(sa.insert(validation_run_result_manifest_table).values(**values))
                run_row = (
                    session.execute(
                        sa.update(validation_run_table)
                        .where(
                            validation_run_table.c.id == run_id,
                            validation_run_table.c.status == current.run.status.value,
                            validation_run_table.c.result_manifest_id.is_(None),
                        )
                        .values(
                            status=terminal_status.value,
                            result_manifest_id=manifest.id,
                            failure_code=failure_code,
                            ended_at=now,
                        )
                        .returning(validation_run_table)
                    )
                    .mappings()
                    .one_or_none()
                )
            except IntegrityError as error:
                raise ValidationConflict(
                    "Result Manifest conflicts with immutable run evidence"
                ) from error
            if run_row is None:
                raise ValidationConflict("Validation Run changed before Result Manifest collection")
            self._result_provenance_hook(
                session,
                context,
                decision,
                _run(run_row),
                manifest,
                terminal_status,
                now,
            )
            self._result_audit_hook(
                session,
                context,
                run_id,
                "validation.run.collect",
                change_reason,
                now,
            )
            return ValidationRunDetail(_run(run_row), manifest)

    def record_result_evaluation(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        response_extraction: ValidationResponseExtraction,
        numerical_health_report: NumericalHealthReport,
        validation_result: ReferenceValidationResult,
        change_reason: str,
    ) -> ValidationRunDetail:
        if (
            response_extraction.validation_run_id != run_id
            or numerical_health_report.validation_run_id != run_id
            or validation_result.validation_run_id != run_id
            or validation_result.response_extraction.id != response_extraction.id
            or validation_result.numerical_health_report.id != numerical_health_report.id
        ):
            raise ValidationConflict(
                "Validation Result components belong to different Validation Runs"
            )
        if (
            numerical_health_report.report_artifact.sha256 != numerical_health_report.report_sha256
            or validation_result.result_artifact.sha256 != validation_result.result_sha256
        ):
            raise ValidationConflict(
                "Validation Result Artifact digest differs from canonical content"
            )
        if (
            validation_result.content.validation_result_manifest_id
            != response_extraction.validation_result_manifest_id
            or validation_result.content.validation_result_manifest_id
            != numerical_health_report.validation_result_manifest_id
        ):
            raise ValidationConflict(
                "Validation Result components do not share one Result Manifest"
            )
        now = datetime.now(UTC)
        with self._session(context, decision) as session:
            current = self._detail_in_session(session, run_id)
            if current is None:
                raise ValidationNotFound("Validation Run is not visible in this tenant")
            if current.validation_result is not None:
                if current.validation_result.result_sha256 == validation_result.result_sha256:
                    return current
                raise ValidationConflict(
                    "Validation Run already has a different immutable Validation Result"
                )
            manifest = current.result_manifest
            if manifest is None or manifest.id != validation_result.validation_result_manifest_id:
                raise ValidationConflict(
                    "Validation Result requires the pinned terminal Result Manifest"
                )
            if current.run.status not in {
                ValidationRunStatus.SUCCEEDED,
                ValidationRunStatus.FAILED,
            }:
                raise ValidationConflict("Validation Result requires a terminal Validation Run")
            extraction_values = {
                "id": response_extraction.id,
                "organization_id": context.organization_id,
                "project_id": context.project_id,
                "classification": current.run.classification.value,
                "validation_run_id": run_id,
                "validation_result_manifest_id": response_extraction.validation_result_manifest_id,
                "source_native_result_artifact_id": (
                    response_extraction.source_native_result.artifact_id
                    if response_extraction.source_native_result is not None
                    else None
                ),
                "source_native_result_sha256": (
                    response_extraction.source_native_result.sha256
                    if response_extraction.source_native_result is not None
                    else None
                ),
                "extraction_status": response_extraction.status.value,
                "normalized_response_artifact_id": (
                    response_extraction.normalized_response.artifact_id
                    if response_extraction.normalized_response is not None
                    else None
                ),
                "normalized_response_sha256": (
                    response_extraction.normalized_response.sha256
                    if response_extraction.normalized_response is not None
                    else None
                ),
                "point_count": response_extraction.point_count,
                "reason_code": response_extraction.reason_code,
                "created_at": response_extraction.created_at,
                "created_by": response_extraction.created_by,
            }
            health = numerical_health_report.content.assessment
            health_values = {
                "id": numerical_health_report.id,
                "organization_id": context.organization_id,
                "project_id": context.project_id,
                "classification": current.run.classification.value,
                "validation_run_id": run_id,
                "validation_result_manifest_id": (
                    numerical_health_report.validation_result_manifest_id
                ),
                "response_extraction_id": numerical_health_report.response_extraction_id,
                "health_status": health.status.value,
                "solver_termination": numerical_health_report.content.solver_termination.value,
                "native_result_state": numerical_health_report.content.native_result_state,
                "expected_output_point_count": health.expected_point_count,
                "observed_output_point_count": health.observed_point_count,
                "output_complete": health.output_complete,
                "finite_values": health.finite_values,
                "strictly_increasing_strain": health.strictly_increasing_strain,
                "reason_code": health.reason_code,
                "report_artifact_id": numerical_health_report.report_artifact.artifact_id,
                "report_sha256": numerical_health_report.report_sha256,
                "created_at": numerical_health_report.created_at,
                "created_by": numerical_health_report.created_by,
            }
            content = validation_result.content
            metrics = content.metrics
            result_values = {
                "id": validation_result.id,
                "organization_id": context.organization_id,
                "project_id": context.project_id,
                "classification": current.run.classification.value,
                "validation_run_id": run_id,
                "validation_result_manifest_id": validation_result.validation_result_manifest_id,
                "response_extraction_id": validation_result.response_extraction.id,
                "numerical_health_report_id": validation_result.numerical_health_report.id,
                "experimental_selection_id": content.experimental_selection_id,
                "experimental_selection_revision_id": content.experimental_selection_revision_id,
                "normalized_response_artifact_id": (
                    content.normalized_response.artifact_id
                    if content.normalized_response is not None
                    else None
                ),
                "normalized_response_sha256": (
                    content.normalized_response.sha256
                    if content.normalized_response is not None
                    else None
                ),
                "numerical_health_report_artifact_id": content.numerical_health_report.artifact_id,
                "numerical_health_report_sha256": content.numerical_health_report.sha256,
                "metric_profile_id": content.metric_profile_id,
                "threshold_profile_id": content.threshold_profile_id,
                "alignment_profile_id": content.alignment_profile_id,
                "relative_rmse_threshold": content.relative_rmse_threshold,
                "experimental_point_count": content.experimental_point_count,
                "simulated_point_count": content.simulated_point_count,
                "compared_point_count": len(metrics.comparison_points)
                if metrics is not None
                else 0,
                "root_mean_squared_error_pa": (
                    metrics.root_mean_squared_error_pa if metrics is not None else None
                ),
                "relative_root_mean_squared_error": (
                    metrics.relative_root_mean_squared_error if metrics is not None else None
                ),
                "normalization_stress_scale_pa": (
                    metrics.normalization_stress_scale_pa if metrics is not None else None
                ),
                "holdout_independence": content.holdout_independence.value,
                "verdict": content.verdict.value,
                "reason_code": content.reason_code,
                "result_artifact_id": validation_result.result_artifact.artifact_id,
                "result_sha256": validation_result.result_sha256,
                "created_at": validation_result.created_at,
                "created_by": validation_result.created_by,
                "change_reason": change_reason,
                "request_id": context.request_id,
                "trace_id": context.trace_id,
            }
            try:
                session.execute(
                    sa.insert(validation_response_extraction_table).values(**extraction_values)
                )
                session.execute(
                    sa.insert(validation_numerical_health_report_table).values(**health_values)
                )
                session.execute(sa.insert(validation_result_table).values(**result_values))
                if metrics is not None:
                    session.execute(
                        sa.insert(validation_result_comparison_point_table),
                        [
                            {
                                "organization_id": context.organization_id,
                                "project_id": context.project_id,
                                "classification": current.run.classification.value,
                                "validation_result_id": validation_result.id,
                                "ordinal": ordinal,
                                "engineering_strain": point.engineering_strain,
                                "observed_engineering_stress_pa": (
                                    point.observed_engineering_stress_pa
                                ),
                                "simulated_engineering_stress_pa": (
                                    point.simulated_engineering_stress_pa
                                ),
                                "residual_engineering_stress_pa": (
                                    point.residual_engineering_stress_pa
                                ),
                                "created_at": validation_result.created_at,
                                "created_by": validation_result.created_by,
                            }
                            for ordinal, point in enumerate(metrics.comparison_points)
                        ],
                    )
            except IntegrityError as error:
                raise ValidationConflict(
                    "Validation Result conflicts with immutable execution evidence"
                ) from error
            self._evaluation_provenance_hook(
                session,
                context,
                decision,
                current.run,
                manifest,
                validation_result,
                now,
            )
            self._result_audit_hook(
                session,
                context,
                run_id,
                "validation.result.evaluate",
                change_reason,
                now,
            )
            detail = self._detail_in_session(session, run_id)
            if detail is None:
                raise ValidationNotFound("Validation Result is not visible after recording")
            return detail

    def get_validation_result(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        validation_result_id: UUID,
    ) -> ReferenceValidationResult:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(validation_result_table.c.validation_run_id).where(
                        validation_result_table.c.id == validation_result_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ValidationNotFound("Validation Result is not visible in this tenant")
            value = self._validation_result_in_session(
                session, validation_run_id=cast(UUID, row["validation_run_id"])
            )
        if value is None or value.id != validation_result_id:
            raise ValidationNotFound("Validation Result is not visible in this tenant")
        return value
