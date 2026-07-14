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


def _content(row: Any) -> ReferenceIsotropicTabulatedPlasticityContent:
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


def _content_values(content: ReferenceIsotropicTabulatedPlasticityContent) -> dict[str, Any]:
    return {
        "model_family_id": content.model_family_id,
        "model_schema_digest": content.model_schema_digest,
        "material_id": content.material_id,
        "material_revision_id": content.material_revision_id,
        "material_state_id": content.material_state_id,
        "material_state_revision_id": content.material_state_revision_id,
        "property_set_id": content.property_set_id,
        "property_set_revision_id": content.property_set_revision_id,
        "source_dataset_id": content.source_dataset_id,
        "source_dataset_revision_id": content.source_dataset_revision_id,
        "hardening_curve_artifact_id": content.hardening_curve_artifact_id,
        "hardening_curve_sha256": content.hardening_curve_sha256,
        "hardening_curve_schema_ref": content.hardening_curve_schema_ref,
        "hardening_curve_point_count": content.hardening_curve_point_count,
        "source_point_count": content.source_point_count,
        "pre_yield_excluded_point_count": content.pre_yield_excluded_point_count,
        "post_necking_excluded_point_count": content.post_necking_excluded_point_count,
        "necking_source_point_index": content.necking_source_point_index,
        "transformation_profile_id": content.transformation_profile_id,
        "transformation_profile_version": content.transformation_profile_version,
        "transformation_profile_digest": content.transformation_profile_digest,
        "necking_engineering_strain": content.necking_engineering_strain,
        "characterized_max_true_plastic_strain": (
            content.characterized_max_true_plastic_strain
        ),
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
        "calibration_evidence_kind": "manual_catalog_projection",
        "calibration_selection_id": None,
        "calibration_selection_revision_id": None,
        "calibration_run_id": None,
        "calibration_candidate_id": None,
        "calibration_candidate_sha256": None,
        "calibration_diagnostics_artifact_id": None,
        "calibration_diagnostics_sha256": None,
        "non_production": True,
    }


_TABLES: TypedRevisionTables[ReferenceIsotropicTabulatedPlasticityContent] = (
    TypedRevisionTables(
        aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
        identity_table=material_model_table,
        revision_table=material_model_revision_table,
        canonical_content=reference_isotropic_tabulated_plasticity_canonical,
        content_values=_content_values,
        identity_values=lambda content: {"material_state_id": content.material_state_id},
    )
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
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceIsotropicTabulatedPlasticityContent]:
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
                revision.c.model_family_id == REFERENCE_TABULATED_PLASTICITY_FAMILY_ID
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
    ) -> RevisionSnapshot[ReferenceIsotropicTabulatedPlasticityContent]:
        revision = material_model_revision_table
        statement = sa.select(*_revision_columns(revision), *_content_columns(revision)).where(
            revision.c.aggregate_id == material_model_id,
            revision.c.id == material_model_revision_id,
            revision.c.model_family_id == REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
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
