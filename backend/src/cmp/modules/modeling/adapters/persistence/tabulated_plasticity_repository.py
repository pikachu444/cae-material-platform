"""PostgreSQL persistence for the typed reference tabulated-plasticity IR family."""

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
from cmp.modules.modeling.application.service import MATERIAL_MODEL_AGGREGATE_TYPE, RevisionSnapshot
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelSnapshot,
    TabulatedPlasticityRepository,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
    ReferenceIsotropicTabulatedPlasticityContent,
    TabulatedPlasticityNotFound,
    reference_isotropic_tabulated_plasticity_canonical,
)
from cmp.modules.modeling.domain.reference_processed_tabulated_plasticity import (
    REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID,
    ReferenceProcessedRecipeBatchEvidence,
    ReferenceProcessedTabulatedPlasticityContent,
    reference_processed_tabulated_plasticity_canonical,
)
from cmp.modules.modeling.domain.reference_voce_tabulated_plasticity import (
    REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID,
    ReferenceVoceTabulatedPlasticityContent,
    reference_voce_tabulated_plasticity_canonical,
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


type TabulatedPlasticityContent = (
    ReferenceIsotropicTabulatedPlasticityContent
    | ReferenceVoceTabulatedPlasticityContent
    | ReferenceProcessedTabulatedPlasticityContent
)


def _content(row: Any) -> TabulatedPlasticityContent:
    if str(row["model_family_id"]) == REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID:
        return ReferenceProcessedTabulatedPlasticityContent(
            material_id=cast(UUID, row["material_id"]),
            material_revision_id=cast(UUID, row["material_revision_id"]),
            material_state_id=cast(UUID, row["material_state_id"]),
            material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
            property_set_id=cast(UUID, row["property_set_id"]),
            property_set_revision_id=cast(UUID, row["property_set_revision_id"]),
            processing_output_id=cast(UUID, row["processing_output_id"]),
            processing_output_revision_id=cast(UUID, row["processing_output_revision_id"]),
            processing_output_sha256=str(row["processing_output_sha256"]),
            source_test_data_id=cast(UUID, row["processing_source_document_id"]),
            source_test_data_revision_id=cast(UUID, row["processing_source_document_revision_id"]),
            mapping_profile_id=cast(UUID, row["processing_mapping_profile_id"]),
            mapping_profile_revision_id=cast(UUID, row["processing_mapping_profile_revision_id"]),
            recipe_batch=(
                ReferenceProcessedRecipeBatchEvidence(
                    recipe_id=cast(UUID, row["processing_recipe_id"]),
                    recipe_revision_id=cast(UUID, row["processing_recipe_revision_id"]),
                    recipe_sha256=str(row["processing_recipe_sha256"]),
                    batch_id=cast(UUID, row["processing_batch_id"]),
                    batch_member_id=cast(UUID, row["processing_batch_member_id"]),
                    batch_attempt_id=cast(UUID, row["processing_batch_attempt_id"]),
                    batch_attempt_no=int(row["processing_batch_attempt_no"]),
                )
                if row["processing_recipe_id"] is not None
                else None
            ),
            candidate_families=tuple(row["hardening_candidate_families"]),
            primary_family=str(row["hardening_primary_family"]),
            secondary_family=str(row["hardening_secondary_family"]),
            primary_weight=float(row["hardening_primary_weight"]),
            fit_minimum_true_plastic_strain=float(row["hardening_fit_minimum_strain"]),
            characterized_max_true_plastic_strain=float(
                row["characterized_max_true_plastic_strain"]
            ),
            extension_max_true_plastic_strain=float(row["extension_max_true_plastic_strain"]),
            hardening_curve_artifact_id=cast(UUID, row["hardening_curve_artifact_id"]),
            hardening_curve_sha256=str(row["hardening_curve_sha256"]),
            hardening_curve_point_count=int(row["hardening_curve_point_count"]),
            density_kg_per_m3=float(row["density_kg_per_m3"]),
            youngs_modulus_pa=float(row["youngs_modulus_pa"]),
            poisson_ratio=float(row["poisson_ratio"]),
            initial_yield_stress_pa=float(row["source_yield_stress_pa"]),
            post_necking_approximation_acknowledged=bool(
                row["post_necking_approximation_acknowledged"]
            ),
            applicable_temperature_min_k=row["applicable_temperature_min_k"],
            applicable_temperature_max_k=row["applicable_temperature_max_k"],
            applicable_strain_rate_min_per_s=row["applicable_strain_rate_min_per_s"],
            applicable_strain_rate_max_per_s=row["applicable_strain_rate_max_per_s"],
            applicability_note=row["applicability_note"],
            reference_temperature_k=float(row["reference_temperature_k"]),
            model_family_id=str(row["model_family_id"]),
            model_schema_version=str(row["schema_version"]),
            model_schema_digest=str(row["model_schema_digest"]),
            hardening_curve_schema_ref=str(row["hardening_curve_schema_ref"]),
            transformation_profile_id=str(row["transformation_profile_id"]),
            transformation_profile_version=str(row["transformation_profile_version"]),
            transformation_profile_digest=str(row["transformation_profile_digest"]),
            post_necking_extension_policy=str(row["post_necking_extension_policy"]),
            non_production=bool(row["non_production"]),
        )
    if str(row["model_family_id"]) == REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID:
        return ReferenceVoceTabulatedPlasticityContent(
            material_id=cast(UUID, row["material_id"]),
            material_revision_id=cast(UUID, row["material_revision_id"]),
            material_state_id=cast(UUID, row["material_state_id"]),
            material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
            property_set_id=cast(UUID, row["property_set_id"]),
            property_set_revision_id=cast(UUID, row["property_set_revision_id"]),
            calibration_input_scope_id=cast(UUID, row["calibration_input_scope_id"]),
            calibration_input_scope_revision_id=cast(
                UUID, row["calibration_input_scope_revision_id"]
            ),
            voce_calibration_plan_id=cast(UUID, row["voce_calibration_plan_id"]),
            voce_calibration_plan_revision_id=cast(UUID, row["voce_calibration_plan_revision_id"]),
            voce_calibration_run_id=cast(UUID, row["voce_calibration_run_id"]),
            voce_calibration_candidate_id=cast(UUID, row["voce_calibration_candidate_id"]),
            voce_calibration_candidate_sha256=str(row["voce_calibration_candidate_sha256"]),
            voce_candidate_selection_id=cast(UUID, row["voce_candidate_selection_id"]),
            voce_candidate_selection_revision_id=cast(
                UUID, row["voce_candidate_selection_revision_id"]
            ),
            hardening_curve_artifact_id=cast(UUID, row["hardening_curve_artifact_id"]),
            hardening_curve_sha256=str(row["hardening_curve_sha256"]),
            hardening_curve_point_count=int(row["hardening_curve_point_count"]),
            sampling_point_count=int(row["voce_sampling_point_count"]),
            density_kg_per_m3=float(row["density_kg_per_m3"]),
            youngs_modulus_pa=float(row["youngs_modulus_pa"]),
            poisson_ratio=float(row["poisson_ratio"]),
            initial_yield_stress_pa=float(row["source_yield_stress_pa"]),
            q_pa=float(row["voce_q_pa"]),
            b=float(row["voce_b"]),
            characterized_max_true_plastic_strain=float(
                row["characterized_max_true_plastic_strain"]
            ),
            extension_max_true_plastic_strain=float(row["extension_max_true_plastic_strain"]),
            post_necking_approximation_acknowledged=bool(
                row["post_necking_approximation_acknowledged"]
            ),
            applicable_temperature_min_k=row["applicable_temperature_min_k"],
            applicable_temperature_max_k=row["applicable_temperature_max_k"],
            applicable_strain_rate_min_per_s=row["applicable_strain_rate_min_per_s"],
            applicable_strain_rate_max_per_s=row["applicable_strain_rate_max_per_s"],
            applicability_note=row["applicability_note"],
            reference_temperature_k=float(row["reference_temperature_k"]),
            model_family_id=str(row["model_family_id"]),
            model_schema_digest=str(row["model_schema_digest"]),
            hardening_curve_schema_ref=str(row["hardening_curve_schema_ref"]),
            transformation_profile_id=str(row["transformation_profile_id"]),
            transformation_profile_version=str(row["transformation_profile_version"]),
            transformation_profile_digest=str(row["transformation_profile_digest"]),
            post_necking_extension_policy=str(row["post_necking_extension_policy"]),
            non_production=bool(row["non_production"]),
        )
    return ReferenceIsotropicTabulatedPlasticityContent(
        material_id=cast(UUID, row["material_id"]),
        material_revision_id=cast(UUID, row["material_revision_id"]),
        material_state_id=cast(UUID, row["material_state_id"]),
        material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
        property_set_id=cast(UUID, row["property_set_id"]),
        property_set_revision_id=cast(UUID, row["property_set_revision_id"]),
        source_dataset_id=cast(UUID, row["source_dataset_id"]),
        source_dataset_revision_id=cast(UUID, row["source_dataset_revision_id"]),
        hardening_curve_artifact_id=cast(UUID, row["hardening_curve_artifact_id"]),
        hardening_curve_sha256=str(row["hardening_curve_sha256"]),
        hardening_curve_point_count=int(row["hardening_curve_point_count"]),
        source_point_count=int(row["source_point_count"]),
        pre_yield_excluded_point_count=int(row["pre_yield_excluded_point_count"]),
        post_necking_excluded_point_count=int(row["post_necking_excluded_point_count"]),
        necking_source_point_index=int(row["necking_source_point_index"]),
        density_kg_per_m3=float(row["density_kg_per_m3"]),
        youngs_modulus_pa=float(row["youngs_modulus_pa"]),
        poisson_ratio=float(row["poisson_ratio"]),
        initial_yield_stress_pa=float(row["source_yield_stress_pa"]),
        necking_engineering_strain=float(row["necking_engineering_strain"]),
        characterized_max_true_plastic_strain=float(row["characterized_max_true_plastic_strain"]),
        extension_max_true_plastic_strain=float(row["extension_max_true_plastic_strain"]),
        post_necking_approximation_acknowledged=bool(
            row["post_necking_approximation_acknowledged"]
        ),
        applicable_temperature_min_k=row["applicable_temperature_min_k"],
        applicable_temperature_max_k=row["applicable_temperature_max_k"],
        applicable_strain_rate_min_per_s=row["applicable_strain_rate_min_per_s"],
        applicable_strain_rate_max_per_s=row["applicable_strain_rate_max_per_s"],
        applicability_note=row["applicability_note"],
        reference_temperature_k=float(row["reference_temperature_k"]),
        model_family_id=str(row["model_family_id"]),
        model_schema_digest=str(row["model_schema_digest"]),
        hardening_curve_schema_ref=str(row["hardening_curve_schema_ref"]),
        transformation_profile_id=str(row["transformation_profile_id"]),
        transformation_profile_version=str(row["transformation_profile_version"]),
        transformation_profile_digest=str(row["transformation_profile_digest"]),
        post_necking_extension_policy=str(row["post_necking_extension_policy"]),
        non_production=bool(row["non_production"]),
    )


def _content_values(content: TabulatedPlasticityContent) -> dict[str, Any]:
    values: dict[str, Any] = {
        "model_family_id": content.model_family_id,
        "model_schema_digest": content.model_schema_digest,
        "material_id": content.material_id,
        "material_revision_id": content.material_revision_id,
        "material_state_id": content.material_state_id,
        "material_state_revision_id": content.material_state_revision_id,
        "property_set_id": content.property_set_id,
        "property_set_revision_id": content.property_set_revision_id,
        "source_dataset_id": getattr(content, "source_dataset_id", None),
        "source_dataset_revision_id": getattr(content, "source_dataset_revision_id", None),
        "hardening_curve_artifact_id": content.hardening_curve_artifact_id,
        "hardening_curve_sha256": content.hardening_curve_sha256,
        "hardening_curve_schema_ref": content.hardening_curve_schema_ref,
        "hardening_curve_point_count": content.hardening_curve_point_count,
        "source_point_count": getattr(content, "source_point_count", None),
        "pre_yield_excluded_point_count": getattr(content, "pre_yield_excluded_point_count", None),
        "post_necking_excluded_point_count": getattr(
            content, "post_necking_excluded_point_count", None
        ),
        "necking_source_point_index": getattr(content, "necking_source_point_index", None),
        "transformation_profile_id": content.transformation_profile_id,
        "transformation_profile_version": content.transformation_profile_version,
        "transformation_profile_digest": content.transformation_profile_digest,
        "necking_engineering_strain": getattr(content, "necking_engineering_strain", None),
        "characterized_max_true_plastic_strain": (content.characterized_max_true_plastic_strain),
        "extension_max_true_plastic_strain": content.extension_max_true_plastic_strain,
        "post_necking_extension_policy": content.post_necking_extension_policy,
        "post_necking_approximation_acknowledged": (
            content.post_necking_approximation_acknowledged
        ),
        "density_kg_per_m3": content.density_kg_per_m3,
        "youngs_modulus_pa": content.youngs_modulus_pa,
        "poisson_ratio": content.poisson_ratio,
        "source_yield_stress_pa": content.initial_yield_stress_pa,
        "applicable_temperature_min_k": content.applicable_temperature_min_k,
        "applicable_temperature_max_k": content.applicable_temperature_max_k,
        "applicable_strain_rate_min_per_s": content.applicable_strain_rate_min_per_s,
        "applicable_strain_rate_max_per_s": content.applicable_strain_rate_max_per_s,
        "applicability_note": content.applicability_note,
        "reference_temperature_k": content.reference_temperature_k,
        "calibration_evidence_kind": (
            "processing_recipe_selection"
            if isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
            else "manual_catalog_projection"
        ),
        "calibration_selection_id": None,
        "calibration_selection_revision_id": None,
        "calibration_run_id": None,
        "calibration_candidate_id": None,
        "calibration_candidate_sha256": None,
        "calibration_diagnostics_artifact_id": None,
        "calibration_diagnostics_sha256": None,
        "calibration_input_scope_id": getattr(content, "calibration_input_scope_id", None),
        "calibration_input_scope_revision_id": getattr(
            content, "calibration_input_scope_revision_id", None
        ),
        "voce_calibration_plan_id": getattr(content, "voce_calibration_plan_id", None),
        "voce_calibration_plan_revision_id": getattr(
            content, "voce_calibration_plan_revision_id", None
        ),
        "voce_calibration_run_id": getattr(content, "voce_calibration_run_id", None),
        "voce_calibration_candidate_id": getattr(content, "voce_calibration_candidate_id", None),
        "voce_calibration_candidate_sha256": getattr(
            content, "voce_calibration_candidate_sha256", None
        ),
        "voce_candidate_selection_id": getattr(content, "voce_candidate_selection_id", None),
        "voce_candidate_selection_revision_id": getattr(
            content, "voce_candidate_selection_revision_id", None
        ),
        "voce_sampling_point_count": getattr(content, "sampling_point_count", None),
        "voce_q_pa": getattr(content, "q_pa", None),
        "voce_b": getattr(content, "b", None),
        "processing_output_id": getattr(content, "processing_output_id", None),
        "processing_output_revision_id": getattr(content, "processing_output_revision_id", None),
        "processing_output_sha256": getattr(content, "processing_output_sha256", None),
        "processing_source_document_id": getattr(content, "source_test_data_id", None),
        "processing_source_document_revision_id": getattr(
            content, "source_test_data_revision_id", None
        ),
        "processing_mapping_profile_id": getattr(content, "mapping_profile_id", None),
        "processing_mapping_profile_revision_id": getattr(
            content, "mapping_profile_revision_id", None
        ),
        "processing_recipe_id": (
            content.recipe_batch.recipe_id
            if isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
            and content.recipe_batch is not None
            else None
        ),
        "processing_recipe_revision_id": (
            content.recipe_batch.recipe_revision_id
            if isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
            and content.recipe_batch is not None
            else None
        ),
        "processing_recipe_sha256": (
            content.recipe_batch.recipe_sha256
            if isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
            and content.recipe_batch is not None
            else None
        ),
        "processing_batch_id": (
            content.recipe_batch.batch_id
            if isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
            and content.recipe_batch is not None
            else None
        ),
        "processing_batch_member_id": (
            content.recipe_batch.batch_member_id
            if isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
            and content.recipe_batch is not None
            else None
        ),
        "processing_batch_attempt_id": (
            content.recipe_batch.batch_attempt_id
            if isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
            and content.recipe_batch is not None
            else None
        ),
        "processing_batch_attempt_no": (
            content.recipe_batch.batch_attempt_no
            if isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
            and content.recipe_batch is not None
            else None
        ),
        "hardening_candidate_families": list(content.candidate_families)
        if isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
        else None,
        "hardening_primary_family": getattr(content, "primary_family", None),
        "hardening_secondary_family": getattr(content, "secondary_family", None),
        "hardening_primary_weight": getattr(content, "primary_weight", None),
        "hardening_fit_minimum_strain": getattr(content, "fit_minimum_true_plastic_strain", None),
        "non_production": True,
    }
    return values


def _canonical(content: TabulatedPlasticityContent) -> dict[str, object]:
    if isinstance(content, ReferenceProcessedTabulatedPlasticityContent):
        return reference_processed_tabulated_plasticity_canonical(content)
    if isinstance(content, ReferenceVoceTabulatedPlasticityContent):
        return reference_voce_tabulated_plasticity_canonical(content)
    return reference_isotropic_tabulated_plasticity_canonical(content)


_TABLES: TypedRevisionTables[TabulatedPlasticityContent] = TypedRevisionTables(
    aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
    identity_table=material_model_table,
    revision_table=material_model_revision_table,
    canonical_content=_canonical,
    content_values=_content_values,
    identity_values=lambda content: {"material_state_id": content.material_state_id},
)


def _revision_columns(table: sa.Table) -> tuple[Any, ...]:
    return (
        table.c.id.label("id"),
        table.c.aggregate_id.label("aggregate_id"),
        table.c.organization_id.label("organization_id"),
        table.c.project_id.label("project_id"),
        table.c.classification.label("classification"),
        table.c.revision_no.label("revision_no"),
        table.c.based_on_revision_id.label("based_on_revision_id"),
        table.c.schema_id.label("schema_id"),
        table.c.schema_version.label("schema_version"),
        table.c.content_hash.label("content_hash"),
        table.c.created_at.label("created_at"),
        table.c.created_by.label("created_by"),
        table.c.change_reason.label("change_reason"),
        table.c.request_id.label("request_id"),
        table.c.trace_id.label("trace_id"),
    )


def _content_columns(table: sa.Table) -> tuple[Any, ...]:
    return (
        table.c.model_family_id,
        table.c.model_schema_digest,
        table.c.material_id,
        table.c.material_revision_id,
        table.c.material_state_id,
        table.c.material_state_revision_id,
        table.c.property_set_id,
        table.c.property_set_revision_id,
        table.c.source_dataset_id,
        table.c.source_dataset_revision_id,
        table.c.hardening_curve_artifact_id,
        table.c.hardening_curve_sha256,
        table.c.hardening_curve_schema_ref,
        table.c.hardening_curve_point_count,
        table.c.source_point_count,
        table.c.pre_yield_excluded_point_count,
        table.c.post_necking_excluded_point_count,
        table.c.necking_source_point_index,
        table.c.transformation_profile_id,
        table.c.transformation_profile_version,
        table.c.transformation_profile_digest,
        table.c.necking_engineering_strain,
        table.c.characterized_max_true_plastic_strain,
        table.c.extension_max_true_plastic_strain,
        table.c.post_necking_extension_policy,
        table.c.post_necking_approximation_acknowledged,
        table.c.density_kg_per_m3,
        table.c.youngs_modulus_pa,
        table.c.poisson_ratio,
        table.c.source_yield_stress_pa,
        table.c.applicable_temperature_min_k,
        table.c.applicable_temperature_max_k,
        table.c.applicable_strain_rate_min_per_s,
        table.c.applicable_strain_rate_max_per_s,
        table.c.applicability_note,
        table.c.reference_temperature_k,
        table.c.calibration_input_scope_id,
        table.c.calibration_input_scope_revision_id,
        table.c.voce_calibration_plan_id,
        table.c.voce_calibration_plan_revision_id,
        table.c.voce_calibration_run_id,
        table.c.voce_calibration_candidate_id,
        table.c.voce_calibration_candidate_sha256,
        table.c.voce_candidate_selection_id,
        table.c.voce_candidate_selection_revision_id,
        table.c.voce_sampling_point_count,
        table.c.voce_q_pa,
        table.c.voce_b,
        table.c.processing_output_id,
        table.c.processing_output_revision_id,
        table.c.processing_output_sha256,
        table.c.processing_source_document_id,
        table.c.processing_source_document_revision_id,
        table.c.processing_mapping_profile_id,
        table.c.processing_mapping_profile_revision_id,
        table.c.processing_recipe_id,
        table.c.processing_recipe_revision_id,
        table.c.processing_recipe_sha256,
        table.c.processing_batch_id,
        table.c.processing_batch_member_id,
        table.c.processing_batch_attempt_id,
        table.c.processing_batch_attempt_no,
        table.c.hardening_candidate_families,
        table.c.hardening_primary_family,
        table.c.hardening_secondary_family,
        table.c.hardening_primary_weight,
        table.c.hardening_fit_minimum_strain,
        table.c.non_production,
    )


class SqlAlchemyTabulatedPlasticityRepository(TabulatedPlasticityRepository):
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
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TabulatedPlasticityContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def _current_statement(self) -> sa.Select[Any]:
        identity = material_model_table
        revision = material_model_revision_table
        return (
            sa.select(*_revision_columns(revision), *_content_columns(revision))
            .select_from(
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
            .where(
                revision.c.model_family_id.in_(
                    (
                        REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
                        REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID,
                        REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID,
                    )
                )
            )
        )

    @staticmethod
    def _snapshot(row: Any) -> TabulatedPlasticityModelSnapshot:
        content = _content(row)
        return TabulatedPlasticityModelSnapshot(
            id=cast(UUID, row["aggregate_id"]),
            material_state_id=content.material_state_id,
            current=RevisionSnapshot(_record(row), content),
        )

    def get_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> TabulatedPlasticityModelSnapshot:
        statement = self._current_statement().where(
            material_model_table.c.id == material_model_id,
            material_model_table.c.organization_id == context.organization_id,
            material_model_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise TabulatedPlasticityNotFound(
                    "tabulated-plasticity Material Model is not available"
                ) from error
        if row is None:
            raise TabulatedPlasticityNotFound(
                "tabulated-plasticity Material Model is not visible in this tenant"
            )
        return self._snapshot(row)

    def list_material_models_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TabulatedPlasticityModelSnapshot, ...]:
        statement = (
            self._current_statement()
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
            except DBAPIError as error:
                raise TabulatedPlasticityNotFound(
                    "tabulated-plasticity Material Models are not available"
                ) from error
        return tuple(self._snapshot(row) for row in rows)

    def get_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[TabulatedPlasticityContent]:
        revision = material_model_revision_table
        statement = sa.select(*_revision_columns(revision), *_content_columns(revision)).where(
            revision.c.aggregate_id == material_model_id,
            revision.c.id == material_model_revision_id,
            revision.c.model_family_id.in_(
                (
                    REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
                    REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID,
                    REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID,
                )
            ),
            revision.c.organization_id == context.organization_id,
            revision.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise TabulatedPlasticityNotFound(
                    "tabulated-plasticity Material Model revision is not available"
                ) from error
        if row is None:
            raise TabulatedPlasticityNotFound(
                "tabulated-plasticity Material Model revision is not visible in this tenant"
            )
        return RevisionSnapshot(_record(row), _content(row))
