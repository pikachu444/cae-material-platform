"""PostgreSQL projection for immutable Neutral Material JSON and typed hyperelastic IR."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.neutral_material import (
    NEUTRAL_MATERIAL_AGGREGATE_TYPE,
    NeutralMaterialNotFound,
    NeutralMaterialRepository,
    NeutralMaterialRevisionContent,
    NeutralMaterialStoredRevision,
)
from cmp.modules.modeling.domain.neutral_material import (
    EvidenceStatus,
    NeutralCandidateSelection,
    NeutralElastoplasticIR,
    NeutralHyperelasticIR,
    NeutralLinearViscoelasticIR,
    NeutralProcessingSelection,
    NeutralPronyProcessingSelection,
    RevisionReference,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()

neutral_material_table = sa.Table(
    "neutral_material",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="modeling",
)

neutral_material_revision_table = sa.Table(
    "neutral_material_revision",
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
    sa.Column("document_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("document_artifact_sha256", sa.CHAR(64), nullable=False),
    sa.Column("document_content_sha256", sa.CHAR(64), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_revision_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_plan_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("scientific_profile_id", sa.Uuid(), nullable=False),
    sa.Column("scientific_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_profile_status", sa.String(32), nullable=False),
    sa.Column("mapping_profile_reason", sa.String(500), nullable=False),
    sa.Column("mapping_profile_id", sa.Uuid(), nullable=True),
    sa.Column("mapping_profile_revision_id", sa.Uuid(), nullable=True),
    sa.Column("processing_recipe_status", sa.String(32), nullable=False),
    sa.Column("processing_recipe_reason", sa.String(500), nullable=False),
    sa.Column("processing_recipe_id", sa.Uuid(), nullable=True),
    sa.Column("processing_recipe_revision_id", sa.Uuid(), nullable=True),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("family_candidate_id", sa.Uuid(), nullable=False),
    sa.Column("candidate_sha256", sa.CHAR(64), nullable=False),
    sa.Column("selection_reason", sa.Text(), nullable=False),
    sa.Column("diagnostics_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("diagnostics_sha256", sa.CHAR(64), nullable=False),
    sa.Column("family", sa.String(32), nullable=False),
    sa.Column("c10_pa", sa.Double(), nullable=True),
    sa.Column("c01_pa", sa.Double(), nullable=True),
    sa.Column("c20_pa", sa.Double(), nullable=True),
    sa.Column("c30_pa", sa.Double(), nullable=True),
    sa.Column("ogden_mu_pa", sa.Double(), nullable=True),
    sa.Column("ogden_alpha", sa.Double(), nullable=True),
    sa.Column("density_kg_per_m3", sa.Double(), nullable=False),
    sa.Column("applicable_strain_min", sa.Double(), nullable=False),
    sa.Column("applicable_strain_max", sa.Double(), nullable=False),
    sa.Column("validation_status", sa.String(160), nullable=False),
    sa.Column("model_schema_digest", sa.CHAR(64), nullable=False),
    sa.Column("maturity", sa.String(32), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    sa.Column("model_family", sa.String(64), nullable=False),
    sa.Column("selection_kind", sa.String(64), nullable=False),
    sa.Column("processing_output_id", sa.Uuid(), nullable=True),
    sa.Column("processing_output_revision_id", sa.Uuid(), nullable=True),
    sa.Column("processing_output_sha256", sa.CHAR(64), nullable=True),
    sa.Column("selected_series", sa.String(160), nullable=True),
    sa.Column("candidate_families", sa.ARRAY(sa.Text()), nullable=True),
    sa.Column("primary_family", sa.String(64), nullable=True),
    sa.Column("secondary_family", sa.String(64), nullable=True),
    sa.Column("primary_weight", sa.Double(), nullable=True),
    sa.Column("fit_decision_evidence", sa.JSON(), nullable=True),
    sa.Column("prony_selection_mode", sa.String(32), nullable=True),
    sa.Column("prony_selected_term_count", sa.Integer(), nullable=True),
    sa.Column("prony_normalized_rmse", sa.Double(), nullable=True),
    sa.Column("prony_bic", sa.Double(), nullable=True),
    sa.Column("prony_fitted_g0_pa", sa.Double(), nullable=True),
    sa.Column("prony_catalog_g0_pa", sa.Double(), nullable=True),
    sa.Column("prony_relative_mismatch", sa.Double(), nullable=True),
    sa.Column("prony_acknowledged_max_mismatch", sa.Double(), nullable=True),
    sa.Column("youngs_modulus_pa", sa.Double(), nullable=True),
    sa.Column("poisson_ratio", sa.Double(), nullable=True),
    sa.Column("initial_yield_stress_pa", sa.Double(), nullable=True),
    sa.Column("hardening_curve_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("hardening_curve_sha256", sa.CHAR(64), nullable=True),
    sa.Column("hardening_curve_schema_ref", sa.String(255), nullable=True),
    sa.Column("hardening_curve_point_count", sa.Integer(), nullable=True),
    sa.Column("characterized_strain_max", sa.Double(), nullable=True),
    sa.Column("extension_strain_max", sa.Double(), nullable=True),
    sa.Column("extrapolation_policy", sa.String(255), nullable=True),
    sa.Column("approximation_acknowledged", sa.Boolean(), nullable=True),
    sa.Column("bulk_relaxation_status", sa.String(64), nullable=True),
    sa.Column("reference_temperature_k", sa.Double(), nullable=True),
    sa.Column("applicable_time_min_s", sa.Double(), nullable=True),
    sa.Column("applicable_time_max_s", sa.Double(), nullable=True),
    sa.Column("prony_overlay_status", sa.String(32), nullable=True),
    sa.Column("prony_overlay_reason", sa.String(500), nullable=True),
    sa.Column("prony_overlay_model_id", sa.Uuid(), nullable=True),
    sa.Column("prony_overlay_model_revision_id", sa.Uuid(), nullable=True),
    schema="modeling",
)

neutral_material_source_dataset_table = sa.Table(
    "neutral_material_source_dataset",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("neutral_material_id", sa.Uuid(), nullable=False),
    sa.Column("neutral_material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("dataset_id", sa.Uuid(), nullable=False),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("role", sa.String(32), nullable=False),
    sa.Column("test_mode", sa.String(64), nullable=False),
    sa.Column("normalized_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("normalized_artifact_sha256", sa.CHAR(64), nullable=False),
    sa.Column("source_kind", sa.String(64), nullable=False),
    schema="modeling",
)

neutral_material_prony_term_table = sa.Table(
    "neutral_material_prony_term",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("neutral_material_id", sa.Uuid(), nullable=False),
    sa.Column("neutral_material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("usage", sa.String(16), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("g_ratio", sa.Double(), nullable=False),
    sa.Column("k_ratio", sa.Double(), nullable=False),
    sa.Column("relaxation_time_s", sa.Double(), nullable=False),
    schema="modeling",
)


def _reference_values(status: EvidenceStatus, reference: Any) -> tuple[UUID | None, UUID | None]:
    if status is EvidenceStatus.NOT_APPLICABLE:
        return None, None
    assert reference is not None
    return reference.object_id, reference.revision_id


def _content_values(content: NeutralMaterialRevisionContent) -> dict[str, Any]:
    document = content.document
    material_ir = document.material_model_ir
    selection = document.selection
    calibration_plan = document.calibration_plan
    scientific_profile = document.scientific_profile
    plan_reference = (
        calibration_plan
        if isinstance(calibration_plan, RevisionReference)
        else calibration_plan.reference
    )
    profile_reference = (
        scientific_profile
        if isinstance(scientific_profile, RevisionReference)
        else scientific_profile.reference
    )
    mapping_id, mapping_revision_id = _reference_values(
        document.mapping_profile.status, document.mapping_profile.reference
    )
    recipe_id, recipe_revision_id = _reference_values(
        document.processing_recipe.status, document.processing_recipe.reference
    )
    values: dict[str, Any] = {
        "document_artifact_id": content.document_artifact_id,
        "document_artifact_sha256": content.document_artifact_sha256,
        "document_content_sha256": document.content_sha256,
        "material_id": document.material.object_id,
        "material_revision_id": document.material.revision_id,
        "material_state_id": document.material_state.object_id,
        "material_state_revision_id": document.material_state.revision_id,
        "property_set_id": document.property_set.object_id,
        "property_set_revision_id": document.property_set.revision_id,
        "calibration_plan_id": plan_reference.object_id if plan_reference else None,
        "calibration_plan_revision_id": plan_reference.revision_id if plan_reference else None,
        "scientific_profile_id": profile_reference.object_id if profile_reference else None,
        "scientific_profile_revision_id": (
            profile_reference.revision_id if profile_reference else None
        ),
        "mapping_profile_status": document.mapping_profile.status.value,
        "mapping_profile_reason": document.mapping_profile.reason,
        "mapping_profile_id": mapping_id,
        "mapping_profile_revision_id": mapping_revision_id,
        "processing_recipe_status": document.processing_recipe.status.value,
        "processing_recipe_reason": document.processing_recipe.reason,
        "processing_recipe_id": recipe_id,
        "processing_recipe_revision_id": recipe_revision_id,
        "selection_reason": selection.reason,
        "density_kg_per_m3": material_ir.density_kg_per_m3,
        "applicable_strain_min": document.applicable_strain_min,
        "applicable_strain_max": document.applicable_strain_max,
        "applicable_time_min_s": document.applicable_time_min_s,
        "applicable_time_max_s": document.applicable_time_max_s,
        "validation_status": document.validation_status,
        "model_schema_digest": material_ir.model_schema_digest,
        "maturity": material_ir.maturity.value,
        "non_production": material_ir.non_production,
        "model_family": material_ir.family.value,
        "fit_decision_evidence": (
            selection.fit_decision.canonical()
            if isinstance(
                selection,
                (NeutralProcessingSelection, NeutralPronyProcessingSelection),
            )
            and selection.fit_decision is not None
            else None
        ),
    }
    if isinstance(selection, NeutralCandidateSelection):
        values.update(
            selection_kind="candidate",
            calibration_run_id=selection.calibration_run_id,
            family_candidate_id=selection.candidate_id,
            candidate_sha256=selection.candidate_sha256,
            diagnostics_artifact_id=selection.diagnostics_artifact_id,
            diagnostics_sha256=selection.diagnostics_sha256,
        )
    elif isinstance(selection, NeutralProcessingSelection):
        values.update(
            selection_kind="processing_output",
            processing_output_id=selection.processing_output.object_id,
            processing_output_revision_id=selection.processing_output.revision_id,
            processing_output_sha256=selection.processing_output_sha256,
            selected_series=selection.selected_series,
            candidate_families=list(selection.candidate_families),
            primary_family=selection.primary_family,
            secondary_family=selection.secondary_family,
            primary_weight=selection.primary_weight,
        )
    elif isinstance(selection, NeutralPronyProcessingSelection):
        values.update(
            selection_kind="prony_processing_output",
            processing_output_id=selection.processing_output.object_id,
            processing_output_revision_id=selection.processing_output.revision_id,
            processing_output_sha256=selection.processing_output_sha256,
            selected_series=selection.selected_series,
            prony_selection_mode=selection.selection_mode,
            prony_selected_term_count=selection.selected_term_count,
            prony_normalized_rmse=selection.normalized_rmse,
            prony_bic=selection.bic,
            prony_fitted_g0_pa=selection.fitted_instantaneous_shear_modulus_pa,
            prony_catalog_g0_pa=selection.catalog_instantaneous_shear_modulus_pa,
            prony_relative_mismatch=selection.instantaneous_modulus_relative_mismatch,
            prony_acknowledged_max_mismatch=(
                selection.acknowledged_maximum_relative_mismatch
            ),
        )
    else:  # pragma: no cover - closed domain union
        raise ValueError("unsupported Neutral Material selection")

    if isinstance(material_ir, NeutralHyperelasticIR):
        parameters = material_ir.parameters
        values.update(
            family=parameters.family.value,
            c10_pa=parameters.c10_pa,
            c01_pa=parameters.c01_pa,
            c20_pa=parameters.c20_pa,
            c30_pa=parameters.c30_pa,
            ogden_mu_pa=parameters.mu_pa,
            ogden_alpha=parameters.alpha,
        )
        overlay = material_ir.prony_overlay
        if overlay is not None:
            values.update(
                prony_overlay_status=overlay.status.value,
                prony_overlay_reason=overlay.reason,
                prony_overlay_model_id=(
                    overlay.source_model.object_id if overlay.source_model else None
                ),
                prony_overlay_model_revision_id=(
                    overlay.source_model.revision_id if overlay.source_model else None
                ),
            )
    elif isinstance(material_ir, NeutralElastoplasticIR):
        curve = material_ir.hardening_curve
        values.update(
            family=material_ir.family.value,
            youngs_modulus_pa=material_ir.youngs_modulus_pa,
            poisson_ratio=material_ir.poisson_ratio,
            initial_yield_stress_pa=material_ir.initial_yield_stress_pa,
            hardening_curve_artifact_id=curve.artifact_id,
            hardening_curve_sha256=curve.sha256,
            hardening_curve_schema_ref=curve.schema_ref,
            hardening_curve_point_count=curve.point_count,
            candidate_families=list(material_ir.candidate_families),
            primary_family=material_ir.primary_family,
            secondary_family=material_ir.secondary_family,
            primary_weight=material_ir.primary_weight,
            characterized_strain_max=material_ir.characterized_max_true_plastic_strain,
            extension_strain_max=material_ir.extension_max_true_plastic_strain,
            extrapolation_policy=material_ir.extrapolation_policy,
            approximation_acknowledged=material_ir.approximation_acknowledged,
        )
    elif isinstance(material_ir, NeutralLinearViscoelasticIR):
        values.update(
            family=material_ir.family.value,
            youngs_modulus_pa=material_ir.youngs_modulus_pa,
            poisson_ratio=material_ir.poisson_ratio,
            bulk_relaxation_status=material_ir.bulk_relaxation_status,
            reference_temperature_k=material_ir.reference_temperature_k,
        )
    else:  # pragma: no cover - closed domain union
        raise ValueError("unsupported Neutral Material IR")
    return values


def _write_sources(session: Session, draft: RevisionDraft[NeutralMaterialRevisionContent]) -> None:
    session.execute(
        sa.insert(neutral_material_source_dataset_table),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "neutral_material_id": draft.aggregate_id,
                "neutral_material_revision_id": draft.revision_id,
                "ordinal": ordinal,
                "dataset_id": source.dataset.object_id,
                "dataset_revision_id": source.dataset.revision_id,
                "role": source.role.value,
                "test_mode": source.test_mode.value,
                "normalized_artifact_id": source.normalized_artifact_id,
                "normalized_artifact_sha256": source.normalized_artifact_sha256,
                "source_kind": source.source_kind.value,
            }
            for ordinal, source in enumerate(draft.content.document.source_datasets)
        ],
    )
    material_ir = draft.content.document.material_model_ir
    rows: list[dict[str, object]] = []
    terms = (
        material_ir.terms if isinstance(material_ir, NeutralLinearViscoelasticIR) else ()
    )
    for term in terms:
        rows.append(
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "neutral_material_id": draft.aggregate_id,
                "neutral_material_revision_id": draft.revision_id,
                "usage": "linear",
                "ordinal": term.ordinal,
                "g_ratio": term.g_ratio,
                "k_ratio": term.k_ratio,
                "relaxation_time_s": term.relaxation_time_s,
            }
        )
    overlay = (
        material_ir.prony_overlay if isinstance(material_ir, NeutralHyperelasticIR) else None
    )
    for term in overlay.terms if overlay is not None else ():
        rows.append(
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "neutral_material_id": draft.aggregate_id,
                "neutral_material_revision_id": draft.revision_id,
                "usage": "overlay",
                "ordinal": term.ordinal,
                "g_ratio": term.g_ratio,
                "k_ratio": term.k_ratio,
                "relaxation_time_s": term.relaxation_time_s,
            }
        )
    if rows:
        session.execute(sa.insert(neutral_material_prony_term_table), rows)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=NEUTRAL_MATERIAL_AGGREGATE_TYPE,
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


class SqlAlchemyNeutralMaterialRepository(NeutralMaterialRepository):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[SqlRevisionHook] = (),
    ) -> None:
        self._session_factory = session_factory
        self._rls_context = rls_context
        self._revision_hooks = tuple(revision_hooks)

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._session_factory() as session, session.begin():
            self._rls_context.bind_authorization(session, context, decision)
            yield session

    def neutral_material_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[NeutralMaterialRevisionContent]:
        tables = TypedRevisionTables(
            aggregate_type=NEUTRAL_MATERIAL_AGGREGATE_TYPE,
            identity_table=neutral_material_table,
            revision_table=neutral_material_revision_table,
            canonical_content=lambda value: {
                "document": value.document.canonical(),
                "document_artifact_id": str(value.document_artifact_id),
                "document_artifact_sha256": value.document_artifact_sha256,
            },
            content_values=_content_values,
            identity_values=lambda value: {
                "material_state_id": value.document.material_state.object_id
            },
            revision_content_writer=_write_sources,
        )
        return SqlAlchemyRevisionStore(
            session_factory=self._session_factory,
            tables=tables,
            hooks=self._revision_hooks,
            session_binder=lambda session: self._rls_context.bind_authorization(
                session, context, decision
            ),
        )

    @staticmethod
    def _stored(row: Any) -> NeutralMaterialStoredRevision:
        return NeutralMaterialStoredRevision(
            neutral_material_id=cast(UUID, row["aggregate_id"]),
            record=_record(row),
            document_artifact_id=cast(UUID, row["document_artifact_id"]),
            document_artifact_sha256=str(row["document_artifact_sha256"]),
        )

    def get_current_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
    ) -> NeutralMaterialStoredRevision:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(neutral_material_revision_table)
                    .join(
                        neutral_material_table,
                        sa.and_(
                            neutral_material_table.c.organization_id
                            == neutral_material_revision_table.c.organization_id,
                            neutral_material_table.c.project_id
                            == neutral_material_revision_table.c.project_id,
                            neutral_material_table.c.current_revision_id
                            == neutral_material_revision_table.c.id,
                        ),
                    )
                    .where(neutral_material_table.c.id == neutral_material_id)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise NeutralMaterialNotFound(str(neutral_material_id))
        return self._stored(row)

    def get_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
        neutral_material_revision_id: UUID,
    ) -> NeutralMaterialStoredRevision:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(neutral_material_revision_table).where(
                        neutral_material_revision_table.c.aggregate_id
                        == neutral_material_id,
                        neutral_material_revision_table.c.id
                        == neutral_material_revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise NeutralMaterialNotFound("exact Neutral Material revision is not visible")
        return self._stored(row)

    def find_by_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> NeutralMaterialStoredRevision | None:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(neutral_material_revision_table).where(
                        neutral_material_revision_table.c.family_candidate_id == candidate_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        return self._stored(row) if row is not None else None
