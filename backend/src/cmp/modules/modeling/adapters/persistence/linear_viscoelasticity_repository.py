"""PostgreSQL persistence for typed linear-viscoelastic IR and Prony terms."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.persistence.repository import (
    material_model_revision_table,
    material_model_table,
)
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelSnapshot,
    LinearViscoelasticRepository,
)
from cmp.modules.modeling.application.service import MATERIAL_MODEL_AGGREGATE_TYPE, RevisionSnapshot
from cmp.modules.modeling.domain.fit_decision_evidence import (
    fit_decision_evidence_from_canonical,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID,
    BulkRelaxationStatus,
    LinearViscoelasticNotFound,
    PronyTerm,
    ReferenceLinearViscoelasticCalibrationEvidence,
    ReferenceLinearViscoelasticContent,
    ReferencePronyProcessingEvidence,
    ReferencePronyPromotionEvidence,
    ReferenceRecipeBatchEvidence,
    reference_linear_viscoelastic_canonical,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope

metadata = material_model_table.metadata

linear_viscoelastic_revision_table = sa.Table(
    "linear_viscoelastic_revision",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("bulk_relaxation_status", sa.String(32), nullable=False),
    sa.Column("term_count", sa.Integer(), nullable=False),
    sa.Column("promotion_kind", sa.String(32), nullable=False),
    schema="modeling",
)
linear_viscoelastic_prony_term_table = sa.Table(
    "linear_viscoelastic_prony_term",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("g_ratio", sa.Double(), nullable=False),
    sa.Column("k_ratio", sa.Double(), nullable=False),
    sa.Column("relaxation_time_s", sa.Double(), nullable=False),
    schema="modeling",
)
linear_viscoelastic_processing_evidence_table = sa.Table(
    "linear_viscoelastic_processing_evidence",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("processing_output_id", sa.Uuid(), nullable=False),
    sa.Column("processing_output_revision_id", sa.Uuid(), nullable=False),
    sa.Column("processing_output_sha256", sa.CHAR(64), nullable=False),
    sa.Column("source_test_data_id", sa.Uuid(), nullable=False),
    sa.Column("source_test_data_revision_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_profile_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_mode", sa.String(32), nullable=False),
    sa.Column("selected_term_count", sa.Integer(), nullable=False),
    sa.Column("normalized_rmse", sa.Double(), nullable=False),
    sa.Column("bic", sa.Double(), nullable=False),
    sa.Column("fitted_instantaneous_shear_modulus_pa", sa.Double(), nullable=False),
    sa.Column("catalog_instantaneous_shear_modulus_pa", sa.Double(), nullable=False),
    sa.Column("instantaneous_modulus_relative_mismatch", sa.Double(), nullable=False),
    sa.Column("acknowledged_maximum_relative_mismatch", sa.Double(), nullable=False),
    sa.Column("fit_decision_evidence", sa.JSON(none_as_null=True), nullable=True),
    sa.Column("processing_recipe_id", sa.Uuid(), nullable=True),
    sa.Column("processing_recipe_revision_id", sa.Uuid(), nullable=True),
    sa.Column("processing_recipe_sha256", sa.CHAR(64), nullable=True),
    sa.Column("processing_batch_id", sa.Uuid(), nullable=True),
    sa.Column("processing_batch_member_id", sa.Uuid(), nullable=True),
    sa.Column("processing_batch_attempt_id", sa.Uuid(), nullable=True),
    sa.Column("processing_batch_attempt_no", sa.Integer(), nullable=True),
    schema="modeling",
)
linear_viscoelastic_calibration_evidence_table = sa.Table(
    "linear_viscoelastic_calibration_evidence",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("plan_sha256", sa.CHAR(64), nullable=False),
    sa.Column("run_id", sa.Uuid(), nullable=False),
    sa.Column("run_sha256", sa.CHAR(64), nullable=False),
    sa.Column("candidate_id", sa.Uuid(), nullable=False),
    sa.Column("candidate_sha256", sa.CHAR(64), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_sha256", sa.CHAR(64), nullable=False),
    sa.Column("recommendation_id", sa.Uuid(), nullable=False),
    sa.Column("recommendation_sha256", sa.CHAR(64), nullable=False),
    sa.Column("canonical_test_data_id", sa.Uuid(), nullable=False),
    sa.Column("canonical_test_data_revision_id", sa.Uuid(), nullable=False),
    sa.Column("canonical_test_data_sha256", sa.CHAR(64), nullable=False),
    sa.Column("canonical_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("canonical_artifact_sha256", sa.CHAR(64), nullable=False),
    sa.Column("normalized_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("normalized_artifact_sha256", sa.CHAR(64), nullable=False),
    sa.Column("import_profile_id", sa.Uuid(), nullable=False),
    sa.Column("import_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("import_profile_sha256", sa.CHAR(64), nullable=False),
    schema="modeling",
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
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


def _content_values(content: ReferenceLinearViscoelasticContent) -> dict[str, Any]:
    evidence = content.prony_promotion_evidence
    return {
        "model_family_id": content.model_family_id,
        "model_schema_digest": content.model_schema_digest,
        "material_id": content.material_id,
        "material_revision_id": content.material_revision_id,
        "material_state_id": content.material_state_id,
        "material_state_revision_id": content.material_state_revision_id,
        "property_set_id": content.property_set_id,
        "property_set_revision_id": content.property_set_revision_id,
        "density_kg_per_m3": content.density_kg_per_m3,
        "youngs_modulus_pa": content.youngs_modulus_pa,
        "poisson_ratio": content.poisson_ratio,
        "source_yield_stress_pa": None,
        "applicable_temperature_min_k": content.applicable_temperature_min_k,
        "applicable_temperature_max_k": content.applicable_temperature_max_k,
        "applicable_strain_rate_min_per_s": content.applicable_strain_rate_min_per_s,
        "applicable_strain_rate_max_per_s": content.applicable_strain_rate_max_per_s,
        "applicability_note": content.applicability_note,
        "reference_temperature_k": content.reference_temperature_k,
        "calibration_evidence_kind": (
            "reference_prony_candidate_selection"
            if evidence is not None
            else "linear_viscoelastic_calibration_selection"
            if content.calibration_evidence is not None
            else "manual_catalog_projection"
        ),
        "prony_selection_id": evidence.selection_id if evidence is not None else None,
        "prony_selection_revision_id": (
            evidence.selection_revision_id if evidence is not None else None
        ),
        "prony_calibration_run_id": (evidence.calibration_run_id if evidence is not None else None),
        "prony_calibration_candidate_id": (
            evidence.calibration_candidate_id if evidence is not None else None
        ),
        "prony_calibration_candidate_sha256": (
            evidence.candidate_sha256 if evidence is not None else None
        ),
        "prony_diagnostics_artifact_id": (
            evidence.diagnostics_artifact_id if evidence is not None else None
        ),
        "prony_diagnostics_sha256": (evidence.diagnostics_sha256 if evidence is not None else None),
        "non_production": True,
    }


def _write_terms(
    session: Session, draft: RevisionDraft[ReferenceLinearViscoelasticContent]
) -> None:
    content = draft.content
    scope = draft.scope
    session.execute(
        sa.insert(linear_viscoelastic_revision_table).values(
            organization_id=scope.organization_id,
            project_id=scope.project_id,
            classification=scope.classification,
            material_model_id=draft.aggregate_id,
            material_model_revision_id=draft.revision_id,
            bulk_relaxation_status=content.bulk_relaxation_status.value,
            term_count=len(content.terms),
            promotion_kind=(
                "processing_output"
                if content.processing_promotion_evidence is not None
                else "calibration_selection"
                if content.calibration_evidence is not None
                else "candidate_selection"
                if content.prony_promotion_evidence is not None
                else "manual"
            ),
        )
    )
    session.execute(
        sa.insert(linear_viscoelastic_prony_term_table),
        [
            {
                "organization_id": scope.organization_id,
                "project_id": scope.project_id,
                "classification": scope.classification,
                "material_model_id": draft.aggregate_id,
                "material_model_revision_id": draft.revision_id,
                "ordinal": ordinal,
                "g_ratio": term.g_ratio,
                "k_ratio": term.k_ratio,
                "relaxation_time_s": term.relaxation_time_s,
            }
            for ordinal, term in enumerate(content.terms, 1)
        ],
    )
    evidence = content.processing_promotion_evidence
    if evidence is not None:
        session.execute(
            sa.insert(linear_viscoelastic_processing_evidence_table).values(
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                classification=scope.classification,
                material_model_id=draft.aggregate_id,
                material_model_revision_id=draft.revision_id,
                processing_output_id=evidence.processing_output_id,
                processing_output_revision_id=evidence.processing_output_revision_id,
                processing_output_sha256=evidence.processing_output_sha256,
                source_test_data_id=evidence.source_test_data_id,
                source_test_data_revision_id=evidence.source_test_data_revision_id,
                mapping_profile_id=evidence.mapping_profile_id,
                mapping_profile_revision_id=evidence.mapping_profile_revision_id,
                selection_mode=evidence.selection_mode,
                selected_term_count=evidence.selected_term_count,
                normalized_rmse=evidence.normalized_rmse,
                bic=evidence.bic,
                fitted_instantaneous_shear_modulus_pa=(
                    evidence.fitted_instantaneous_shear_modulus_pa
                ),
                catalog_instantaneous_shear_modulus_pa=(
                    evidence.catalog_instantaneous_shear_modulus_pa
                ),
                instantaneous_modulus_relative_mismatch=(
                    evidence.instantaneous_modulus_relative_mismatch
                ),
                acknowledged_maximum_relative_mismatch=(
                    evidence.acknowledged_maximum_relative_mismatch
                ),
                fit_decision_evidence=(
                    evidence.fit_decision.canonical() if evidence.fit_decision else None
                ),
                processing_recipe_id=(
                    evidence.recipe_batch.recipe_id if evidence.recipe_batch else None
                ),
                processing_recipe_revision_id=(
                    evidence.recipe_batch.recipe_revision_id if evidence.recipe_batch else None
                ),
                processing_recipe_sha256=(
                    evidence.recipe_batch.recipe_sha256 if evidence.recipe_batch else None
                ),
                processing_batch_id=(
                    evidence.recipe_batch.batch_id if evidence.recipe_batch else None
                ),
                processing_batch_member_id=(
                    evidence.recipe_batch.batch_member_id if evidence.recipe_batch else None
                ),
                processing_batch_attempt_id=(
                    evidence.recipe_batch.batch_attempt_id if evidence.recipe_batch else None
                ),
                processing_batch_attempt_no=(
                    evidence.recipe_batch.batch_attempt_no if evidence.recipe_batch else None
                ),
            )
        )
    calibration = content.calibration_evidence
    if calibration is not None:
        session.execute(
            sa.insert(linear_viscoelastic_calibration_evidence_table).values(
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                classification=scope.classification,
                material_model_id=draft.aggregate_id,
                material_model_revision_id=draft.revision_id,
                plan_id=calibration.plan_id,
                plan_revision_id=calibration.plan_revision_id,
                plan_sha256=calibration.plan_sha256,
                run_id=calibration.run_id,
                run_sha256=calibration.run_sha256,
                candidate_id=calibration.candidate_id,
                candidate_sha256=calibration.candidate_sha256,
                selection_id=calibration.selection_id,
                selection_revision_id=calibration.selection_revision_id,
                selection_sha256=calibration.selection_sha256,
                recommendation_id=calibration.recommendation_id,
                recommendation_sha256=calibration.recommendation_sha256,
                canonical_test_data_id=calibration.canonical_test_data_id,
                canonical_test_data_revision_id=(
                    calibration.canonical_test_data_revision_id
                ),
                canonical_test_data_sha256=calibration.canonical_test_data_sha256,
                canonical_artifact_id=calibration.canonical_artifact_id,
                canonical_artifact_sha256=calibration.canonical_artifact_sha256,
                normalized_artifact_id=calibration.normalized_artifact_id,
                normalized_artifact_sha256=calibration.normalized_artifact_sha256,
                import_profile_id=calibration.import_profile_id,
                import_profile_revision_id=calibration.import_profile_revision_id,
                import_profile_sha256=calibration.import_profile_sha256,
            )
        )


_TABLES = TypedRevisionTables[ReferenceLinearViscoelasticContent](
    aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
    identity_table=material_model_table,
    revision_table=material_model_revision_table,
    canonical_content=reference_linear_viscoelastic_canonical,
    content_values=_content_values,
    identity_values=lambda content: {"material_state_id": content.material_state_id},
    revision_content_writer=_write_terms,
)


def _revision_columns(table: sa.Table) -> tuple[Any, ...]:
    names = (
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
        "model_family_id",
        "model_schema_digest",
        "material_id",
        "material_revision_id",
        "material_state_id",
        "material_state_revision_id",
        "property_set_id",
        "property_set_revision_id",
        "density_kg_per_m3",
        "youngs_modulus_pa",
        "poisson_ratio",
        "applicable_temperature_min_k",
        "applicable_temperature_max_k",
        "applicable_strain_rate_min_per_s",
        "applicable_strain_rate_max_per_s",
        "applicability_note",
        "reference_temperature_k",
        "non_production",
        "calibration_evidence_kind",
        "prony_selection_id",
        "prony_selection_revision_id",
        "prony_calibration_run_id",
        "prony_calibration_candidate_id",
        "prony_calibration_candidate_sha256",
        "prony_diagnostics_artifact_id",
        "prony_diagnostics_sha256",
    )
    return tuple(table.c[name] for name in names)


def _content(
    row: Any,
    terms: tuple[PronyTerm, ...],
    processing_evidence: ReferencePronyProcessingEvidence | None = None,
    calibration_evidence: ReferenceLinearViscoelasticCalibrationEvidence | None = None,
) -> ReferenceLinearViscoelasticContent:
    evidence = (
        ReferencePronyPromotionEvidence(
            selection_id=cast(UUID, row["prony_selection_id"]),
            selection_revision_id=cast(UUID, row["prony_selection_revision_id"]),
            calibration_run_id=cast(UUID, row["prony_calibration_run_id"]),
            calibration_candidate_id=cast(UUID, row["prony_calibration_candidate_id"]),
            candidate_sha256=str(row["prony_calibration_candidate_sha256"]),
            diagnostics_artifact_id=cast(UUID, row["prony_diagnostics_artifact_id"]),
            diagnostics_sha256=str(row["prony_diagnostics_sha256"]),
        )
        if row["calibration_evidence_kind"] == "reference_prony_candidate_selection"
        else None
    )
    return ReferenceLinearViscoelasticContent(
        material_id=cast(UUID, row["material_id"]),
        material_revision_id=cast(UUID, row["material_revision_id"]),
        material_state_id=cast(UUID, row["material_state_id"]),
        material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
        property_set_id=cast(UUID, row["property_set_id"]),
        property_set_revision_id=cast(UUID, row["property_set_revision_id"]),
        density_kg_per_m3=float(row["density_kg_per_m3"]),
        youngs_modulus_pa=float(row["youngs_modulus_pa"]),
        poisson_ratio=float(row["poisson_ratio"]),
        bulk_relaxation_status=BulkRelaxationStatus(row["bulk_relaxation_status"]),
        terms=terms,
        applicable_temperature_min_k=row["applicable_temperature_min_k"],
        applicable_temperature_max_k=row["applicable_temperature_max_k"],
        applicable_strain_rate_min_per_s=row["applicable_strain_rate_min_per_s"],
        applicable_strain_rate_max_per_s=row["applicable_strain_rate_max_per_s"],
        applicability_note=row["applicability_note"],
        reference_temperature_k=float(row["reference_temperature_k"]),
        prony_promotion_evidence=evidence,
        processing_promotion_evidence=processing_evidence,
        calibration_evidence=calibration_evidence,
        model_family_id=str(row["model_family_id"]),
        model_schema_digest=str(row["model_schema_digest"]),
        non_production=bool(row["non_production"]),
    )


class SqlAlchemyLinearViscoelasticRepository(LinearViscoelasticRepository):
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

    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceLinearViscoelasticContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _base_statement() -> sa.Select[Any]:
        revision = material_model_revision_table
        summary = linear_viscoelastic_revision_table
        return (
            sa.select(*_revision_columns(revision), summary.c.bulk_relaxation_status)
            .select_from(
                material_model_table.join(
                    revision,
                    sa.and_(
                        revision.c.id == material_model_table.c.current_revision_id,
                        revision.c.aggregate_id == material_model_table.c.id,
                        revision.c.organization_id == material_model_table.c.organization_id,
                        revision.c.project_id == material_model_table.c.project_id,
                    ),
                ).join(
                    summary,
                    sa.and_(
                        summary.c.material_model_id == revision.c.aggregate_id,
                        summary.c.material_model_revision_id == revision.c.id,
                        summary.c.organization_id == revision.c.organization_id,
                        summary.c.project_id == revision.c.project_id,
                    ),
                )
            )
            .where(revision.c.model_family_id == REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID)
        )

    @staticmethod
    def _exact_revision_statement() -> sa.Select[Any]:
        revision = material_model_revision_table
        summary = linear_viscoelastic_revision_table
        return (
            sa.select(*_revision_columns(revision), summary.c.bulk_relaxation_status)
            .select_from(
                material_model_table.join(
                    revision,
                    sa.and_(
                        revision.c.aggregate_id == material_model_table.c.id,
                        revision.c.organization_id == material_model_table.c.organization_id,
                        revision.c.project_id == material_model_table.c.project_id,
                    ),
                ).join(
                    summary,
                    sa.and_(
                        summary.c.material_model_id == revision.c.aggregate_id,
                        summary.c.material_model_revision_id == revision.c.id,
                        summary.c.organization_id == revision.c.organization_id,
                        summary.c.project_id == revision.c.project_id,
                    ),
                )
            )
            .where(revision.c.model_family_id == REFERENCE_LINEAR_VISCOELASTIC_FAMILY_ID)
        )

    @staticmethod
    def _terms(session: Session, row: Any) -> tuple[PronyTerm, ...]:
        rows = session.execute(
            sa.select(
                linear_viscoelastic_prony_term_table.c.g_ratio,
                linear_viscoelastic_prony_term_table.c.k_ratio,
                linear_viscoelastic_prony_term_table.c.relaxation_time_s,
            )
            .where(
                linear_viscoelastic_prony_term_table.c.organization_id == row["organization_id"],
                linear_viscoelastic_prony_term_table.c.project_id == row["project_id"],
                linear_viscoelastic_prony_term_table.c.material_model_id == row["aggregate_id"],
                linear_viscoelastic_prony_term_table.c.material_model_revision_id == row["id"],
            )
            .order_by(linear_viscoelastic_prony_term_table.c.ordinal)
        ).mappings()
        return tuple(
            PronyTerm(
                float(value["g_ratio"]),
                float(value["k_ratio"]),
                float(value["relaxation_time_s"]),
            )
            for value in rows
        )

    @staticmethod
    def _processing_evidence(session: Session, row: Any) -> ReferencePronyProcessingEvidence | None:
        value = (
            session.execute(
                sa.select(linear_viscoelastic_processing_evidence_table).where(
                    linear_viscoelastic_processing_evidence_table.c.organization_id
                    == row["organization_id"],
                    linear_viscoelastic_processing_evidence_table.c.project_id == row["project_id"],
                    linear_viscoelastic_processing_evidence_table.c.material_model_id
                    == row["aggregate_id"],
                    linear_viscoelastic_processing_evidence_table.c.material_model_revision_id
                    == row["id"],
                )
            )
            .mappings()
            .one_or_none()
        )
        if value is None:
            return None
        return ReferencePronyProcessingEvidence(
            processing_output_id=cast(UUID, value["processing_output_id"]),
            processing_output_revision_id=cast(UUID, value["processing_output_revision_id"]),
            processing_output_sha256=str(value["processing_output_sha256"]),
            source_test_data_id=cast(UUID, value["source_test_data_id"]),
            source_test_data_revision_id=cast(UUID, value["source_test_data_revision_id"]),
            mapping_profile_id=cast(UUID, value["mapping_profile_id"]),
            mapping_profile_revision_id=cast(UUID, value["mapping_profile_revision_id"]),
            selection_mode=str(value["selection_mode"]),
            selected_term_count=int(value["selected_term_count"]),
            normalized_rmse=float(value["normalized_rmse"]),
            bic=float(value["bic"]),
            fitted_instantaneous_shear_modulus_pa=float(
                value["fitted_instantaneous_shear_modulus_pa"]
            ),
            catalog_instantaneous_shear_modulus_pa=float(
                value["catalog_instantaneous_shear_modulus_pa"]
            ),
            instantaneous_modulus_relative_mismatch=float(
                value["instantaneous_modulus_relative_mismatch"]
            ),
            acknowledged_maximum_relative_mismatch=float(
                value["acknowledged_maximum_relative_mismatch"]
            ),
            fit_decision=fit_decision_evidence_from_canonical(
                value["fit_decision_evidence"]
            ),
            recipe_batch=(
                ReferenceRecipeBatchEvidence(
                    recipe_id=cast(UUID, value["processing_recipe_id"]),
                    recipe_revision_id=cast(UUID, value["processing_recipe_revision_id"]),
                    recipe_sha256=str(value["processing_recipe_sha256"]),
                    batch_id=cast(UUID, value["processing_batch_id"]),
                    batch_member_id=cast(UUID, value["processing_batch_member_id"]),
                    batch_attempt_id=cast(UUID, value["processing_batch_attempt_id"]),
                    batch_attempt_no=int(value["processing_batch_attempt_no"]),
                )
                if value["processing_recipe_id"] is not None
                else None
            ),
        )

    @staticmethod
    def _calibration_evidence(
        session: Session, row: Any
    ) -> ReferenceLinearViscoelasticCalibrationEvidence | None:
        value = (
            session.execute(
                sa.select(linear_viscoelastic_calibration_evidence_table).where(
                    linear_viscoelastic_calibration_evidence_table.c.organization_id
                    == row["organization_id"],
                    linear_viscoelastic_calibration_evidence_table.c.project_id
                    == row["project_id"],
                    linear_viscoelastic_calibration_evidence_table.c.material_model_id
                    == row["aggregate_id"],
                    linear_viscoelastic_calibration_evidence_table.c.material_model_revision_id
                    == row["id"],
                )
            )
            .mappings()
            .one_or_none()
        )
        if value is None:
            return None
        return ReferenceLinearViscoelasticCalibrationEvidence(
            plan_id=cast(UUID, value["plan_id"]),
            plan_revision_id=cast(UUID, value["plan_revision_id"]),
            plan_sha256=str(value["plan_sha256"]),
            run_id=cast(UUID, value["run_id"]),
            run_sha256=str(value["run_sha256"]),
            candidate_id=cast(UUID, value["candidate_id"]),
            candidate_sha256=str(value["candidate_sha256"]),
            selection_id=cast(UUID, value["selection_id"]),
            selection_revision_id=cast(UUID, value["selection_revision_id"]),
            selection_sha256=str(value["selection_sha256"]),
            recommendation_id=cast(UUID, value["recommendation_id"]),
            recommendation_sha256=str(value["recommendation_sha256"]),
            canonical_test_data_id=cast(UUID, value["canonical_test_data_id"]),
            canonical_test_data_revision_id=cast(
                UUID, value["canonical_test_data_revision_id"]
            ),
            canonical_test_data_sha256=str(value["canonical_test_data_sha256"]),
            canonical_artifact_id=cast(UUID, value["canonical_artifact_id"]),
            canonical_artifact_sha256=str(value["canonical_artifact_sha256"]),
            normalized_artifact_id=cast(UUID, value["normalized_artifact_id"]),
            normalized_artifact_sha256=str(value["normalized_artifact_sha256"]),
            import_profile_id=cast(UUID, value["import_profile_id"]),
            import_profile_revision_id=cast(UUID, value["import_profile_revision_id"]),
            import_profile_sha256=str(value["import_profile_sha256"]),
        )

    def _snapshot(self, session: Session, row: Any) -> LinearViscoelasticModelSnapshot:
        content = _content(
            row,
            self._terms(session, row),
            self._processing_evidence(session, row),
            self._calibration_evidence(session, row),
        )
        return LinearViscoelasticModelSnapshot(
            cast(UUID, row["aggregate_id"]),
            content.material_state_id,
            RevisionSnapshot(_record(row), content),
        )

    def get_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> LinearViscoelasticModelSnapshot:
        statement = self._base_statement().where(
            material_model_table.c.id == material_model_id,
            material_model_table.c.organization_id == context.organization_id,
            material_model_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
                if row is None:
                    raise LinearViscoelasticNotFound(
                        "linear-viscoelastic Material Model is not visible"
                    )
                return self._snapshot(session, row)
            except DBAPIError as error:
                raise LinearViscoelasticNotFound(
                    "linear-viscoelastic Material Model is not available"
                ) from error

    def list_material_models_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[LinearViscoelasticModelSnapshot, ...]:
        statement = (
            self._base_statement()
            .where(
                material_model_table.c.material_state_id == material_state_id,
                material_model_table.c.organization_id == context.organization_id,
                material_model_table.c.project_id == context.project_id,
            )
            .order_by(material_model_revision_table.c.created_at.desc())
        )
        with self._session(context, decision) as session:
            try:
                rows = session.execute(statement).mappings().all()
                return tuple(self._snapshot(session, row) for row in rows)
            except DBAPIError as error:
                raise LinearViscoelasticNotFound(
                    "linear-viscoelastic Material Models are not available"
                ) from error

    def get_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceLinearViscoelasticContent]:
        statement = self._exact_revision_statement().where(
            material_model_table.c.id == material_model_id,
            material_model_table.c.organization_id == context.organization_id,
            material_model_table.c.project_id == context.project_id,
            material_model_revision_table.c.id == material_model_revision_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
                if row is None:
                    raise LinearViscoelasticNotFound(
                        "linear-viscoelastic Material Model revision is not visible"
                    )
                return RevisionSnapshot(
                    _record(row),
                    _content(
                        row,
                        self._terms(session, row),
                        self._processing_evidence(session, row),
                        self._calibration_evidence(session, row),
                    ),
                )
            except DBAPIError as error:
                raise LinearViscoelasticNotFound(
                    "linear-viscoelastic Material Model revision is not available"
                ) from error
