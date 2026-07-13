"""RLS-bound persistence for explicit immutable OpenRadioss reference solver cards."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.exporting.application.service import (
    SOLVER_CARD_AGGREGATE_TYPE,
    ExportingRepository,
    ReferenceMaterialModelSource,
    RevisionSnapshot,
    SolverCardSnapshot,
)
from cmp.modules.exporting.domain.openradioss_elast import (
    ExportTarget,
    MappingStatus,
    ReferenceOpenRadiossCardContent,
    SolverCardConflict,
    SolverCardNotFound,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    REFERENCE_MODEL_FAMILY_ID,
    REFERENCE_MODEL_SCHEMA_DIGEST,
    ReferenceLinearElasticContent,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionCreated, RevisionRecord, TenantScope


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()

solver_card_table = sa.Table(
    "solver_card",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("target_solver", sa.String(64), nullable=False),
    sa.Column("target_version", sa.String(64), nullable=False),
    sa.Column("target_unit_system", sa.String(64), nullable=False),
    sa.Column("solver_material_id", sa.BigInteger(), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="exporting",
)

solver_card_revision_table = sa.Table(
    "solver_card_revision",
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
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("model_schema_digest", sa.CHAR(64), nullable=False),
    sa.Column("target_solver", sa.String(64), nullable=False),
    sa.Column("target_version", sa.String(64), nullable=False),
    sa.Column("target_unit_system", sa.String(64), nullable=False),
    sa.Column("solver_material_id", sa.BigInteger(), nullable=False),
    sa.Column("card_title", sa.String(100), nullable=False),
    sa.Column("density_kg_per_m3", sa.Double(), nullable=False),
    sa.Column("youngs_modulus_pa", sa.Double(), nullable=False),
    sa.Column("poisson_ratio", sa.Double(), nullable=False),
    sa.Column("source_yield_stress_pa", sa.Double(), nullable=True),
    sa.Column("applicable_temperature_min_k", sa.Double(), nullable=True),
    sa.Column("applicable_temperature_max_k", sa.Double(), nullable=True),
    sa.Column("applicable_strain_rate_min_per_s", sa.Double(), nullable=True),
    sa.Column("applicable_strain_rate_max_per_s", sa.Double(), nullable=True),
    sa.Column("density_mapping_status", sa.String(32), nullable=False),
    sa.Column("youngs_modulus_mapping_status", sa.String(32), nullable=False),
    sa.Column("poisson_ratio_mapping_status", sa.String(32), nullable=False),
    sa.Column("source_yield_mapping_status", sa.String(32), nullable=False),
    sa.Column("temperature_applicability_mapping_status", sa.String(32), nullable=False),
    sa.Column("strain_rate_applicability_mapping_status", sa.String(32), nullable=False),
    sa.Column("unit_system_mapping_status", sa.String(32), nullable=False),
    sa.Column("mapping_report_sha256", sa.CHAR(64), nullable=False),
    sa.Column("card_text", sa.Text(), nullable=False),
    sa.Column("card_sha256", sa.CHAR(64), nullable=False),
    sa.Column("exporter_id", sa.String(255), nullable=False),
    sa.Column("exporter_version", sa.String(64), nullable=False),
    sa.Column("exporter_digest", sa.CHAR(64), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="exporting",
)

# The exporter consumes only public Modeling relation names and concrete revision IDs.  It never
# imports the Modeling persistence adapter, preserving the modular-monolith boundary.
modeling_material_model_table = sa.Table(
    "material_model",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    schema="modeling",
)
modeling_material_model_revision_table = sa.Table(
    "material_model_revision",
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
    sa.Column("model_family_id", sa.String(255), nullable=False),
    sa.Column("model_schema_digest", sa.CHAR(64), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_revision_id", sa.Uuid(), nullable=False),
    sa.Column("density_kg_per_m3", sa.Double(), nullable=False),
    sa.Column("youngs_modulus_pa", sa.Double(), nullable=False),
    sa.Column("poisson_ratio", sa.Double(), nullable=False),
    sa.Column("source_yield_stress_pa", sa.Double(), nullable=True),
    sa.Column("applicable_temperature_min_k", sa.Double(), nullable=True),
    sa.Column("applicable_temperature_max_k", sa.Double(), nullable=True),
    sa.Column("applicable_strain_rate_min_per_s", sa.Double(), nullable=True),
    sa.Column("applicable_strain_rate_max_per_s", sa.Double(), nullable=True),
    sa.Column("applicability_note", sa.Text(), nullable=True),
    sa.Column("reference_temperature_k", sa.Double(), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="modeling",
)

# Minimal public provenance relations used only to connect a Solver Card revision to the frozen
# Material Model revision that generated it.  They duplicate no domain table/payload.
provenance_entity_table = sa.Table(
    "entity",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("reference_kind", sa.String(32), nullable=False),
    sa.Column("reference_type", sa.String(100), nullable=False),
    sa.Column("reference_id", sa.Uuid(), nullable=False),
    schema="provenance",
)
provenance_generation_table = sa.Table(
    "generation",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("entity_id", sa.Uuid(), nullable=False),
    sa.Column("activity_id", sa.Uuid(), nullable=False),
    schema="provenance",
)
provenance_usage_table = sa.Table(
    "usage",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("activity_id", sa.Uuid(), nullable=False),
    sa.Column("entity_id", sa.Uuid(), nullable=False),
    sa.Column("role", sa.String(100), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_by", sa.Uuid(), nullable=False),
    schema="provenance",
)
provenance_derivation_table = sa.Table(
    "derivation",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("generated_entity_id", sa.Uuid(), nullable=False),
    sa.Column("used_entity_id", sa.Uuid(), nullable=False),
    sa.Column("activity_id", sa.Uuid(), nullable=True),
    sa.Column("derivation_kind", sa.String(100), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_by", sa.Uuid(), nullable=False),
    schema="provenance",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=SOLVER_CARD_AGGREGATE_TYPE,
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


def _model_content(row: Any) -> ReferenceLinearElasticContent:
    return ReferenceLinearElasticContent(
        material_id=cast(UUID, row["material_id"]),
        material_revision_id=cast(UUID, row["material_revision_id"]),
        material_state_id=cast(UUID, row["material_state_id"]),
        material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
        property_set_id=cast(UUID, row["property_set_id"]),
        property_set_revision_id=cast(UUID, row["property_set_revision_id"]),
        density_kg_per_m3=float(row["density_kg_per_m3"]),
        youngs_modulus_pa=float(row["youngs_modulus_pa"]),
        poisson_ratio=float(row["poisson_ratio"]),
        source_yield_stress_pa=row["source_yield_stress_pa"],
        applicable_temperature_min_k=row["applicable_temperature_min_k"],
        applicable_temperature_max_k=row["applicable_temperature_max_k"],
        applicable_strain_rate_min_per_s=row["applicable_strain_rate_min_per_s"],
        applicable_strain_rate_max_per_s=row["applicable_strain_rate_max_per_s"],
        applicability_note=row["applicability_note"],
        reference_temperature_k=float(row["reference_temperature_k"]),
    )


def _mapping_status(row: Any, column: str) -> MappingStatus:
    return cast(MappingStatus, str(row[column]))


def _card_content(row: Any) -> ReferenceOpenRadiossCardContent:
    return ReferenceOpenRadiossCardContent(
        material_model_id=cast(UUID, row["material_model_id"]),
        material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
        model_schema_digest=str(row["model_schema_digest"]),
        solver_material_id=int(row["solver_material_id"]),
        card_title=str(row["card_title"]),
        density_kg_per_m3=float(row["density_kg_per_m3"]),
        youngs_modulus_pa=float(row["youngs_modulus_pa"]),
        poisson_ratio=float(row["poisson_ratio"]),
        source_yield_stress_pa=row["source_yield_stress_pa"],
        applicable_temperature_min_k=row["applicable_temperature_min_k"],
        applicable_temperature_max_k=row["applicable_temperature_max_k"],
        applicable_strain_rate_min_per_s=row["applicable_strain_rate_min_per_s"],
        applicable_strain_rate_max_per_s=row["applicable_strain_rate_max_per_s"],
        density_mapping_status=_mapping_status(row, "density_mapping_status"),
        youngs_modulus_mapping_status=_mapping_status(row, "youngs_modulus_mapping_status"),
        poisson_ratio_mapping_status=_mapping_status(row, "poisson_ratio_mapping_status"),
        source_yield_mapping_status=_mapping_status(row, "source_yield_mapping_status"),
        temperature_applicability_mapping_status=_mapping_status(
            row,
            "temperature_applicability_mapping_status",
        ),
        strain_rate_applicability_mapping_status=_mapping_status(
            row,
            "strain_rate_applicability_mapping_status",
        ),
        unit_system_mapping_status=_mapping_status(row, "unit_system_mapping_status"),
        mapping_report_sha256=str(row["mapping_report_sha256"]),
        card_text=str(row["card_text"]),
        card_sha256=str(row["card_sha256"]),
        exporter_id=str(row["exporter_id"]),
        exporter_version=str(row["exporter_version"]),
        exporter_digest=str(row["exporter_digest"]),
        target_solver=str(row["target_solver"]),
        target_version=str(row["target_version"]),
        target_unit_system=str(row["target_unit_system"]),
        non_production=bool(row["non_production"]),
    )


def _content_values(content: ReferenceOpenRadiossCardContent) -> dict[str, Any]:
    return {
        "material_model_id": content.material_model_id,
        "material_model_revision_id": content.material_model_revision_id,
        "model_schema_digest": content.model_schema_digest,
        "target_solver": content.target_solver,
        "target_version": content.target_version,
        "target_unit_system": content.target_unit_system,
        "solver_material_id": content.solver_material_id,
        "card_title": content.card_title,
        "density_kg_per_m3": content.density_kg_per_m3,
        "youngs_modulus_pa": content.youngs_modulus_pa,
        "poisson_ratio": content.poisson_ratio,
        "source_yield_stress_pa": content.source_yield_stress_pa,
        "applicable_temperature_min_k": content.applicable_temperature_min_k,
        "applicable_temperature_max_k": content.applicable_temperature_max_k,
        "applicable_strain_rate_min_per_s": content.applicable_strain_rate_min_per_s,
        "applicable_strain_rate_max_per_s": content.applicable_strain_rate_max_per_s,
        "density_mapping_status": content.density_mapping_status,
        "youngs_modulus_mapping_status": content.youngs_modulus_mapping_status,
        "poisson_ratio_mapping_status": content.poisson_ratio_mapping_status,
        "source_yield_mapping_status": content.source_yield_mapping_status,
        "temperature_applicability_mapping_status": (
            content.temperature_applicability_mapping_status
        ),
        "strain_rate_applicability_mapping_status": (
            content.strain_rate_applicability_mapping_status
        ),
        "unit_system_mapping_status": content.unit_system_mapping_status,
        "mapping_report_sha256": content.mapping_report_sha256,
        "card_text": content.card_text,
        "card_sha256": content.card_sha256,
        "exporter_id": content.exporter_id,
        "exporter_version": content.exporter_version,
        "exporter_digest": content.exporter_digest,
        "non_production": content.non_production,
    }


_TABLES: TypedRevisionTables[ReferenceOpenRadiossCardContent] = TypedRevisionTables(
    aggregate_type=SOLVER_CARD_AGGREGATE_TYPE,
    identity_table=solver_card_table,
    revision_table=solver_card_revision_table,
    canonical_content=lambda content: content.canonical(),
    content_values=_content_values,
    identity_values=lambda content: {
        "material_model_id": content.material_model_id,
        "target_solver": content.target_solver,
        "target_version": content.target_version,
        "target_unit_system": content.target_unit_system,
        "solver_material_id": content.solver_material_id,
    },
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
        table.c.material_model_id.label("material_model_id"),
        table.c.material_model_revision_id.label("material_model_revision_id"),
        table.c.model_schema_digest.label("model_schema_digest"),
        table.c.target_solver.label("target_solver"),
        table.c.target_version.label("target_version"),
        table.c.target_unit_system.label("target_unit_system"),
        table.c.solver_material_id.label("solver_material_id"),
        table.c.card_title.label("card_title"),
        table.c.density_kg_per_m3.label("density_kg_per_m3"),
        table.c.youngs_modulus_pa.label("youngs_modulus_pa"),
        table.c.poisson_ratio.label("poisson_ratio"),
        table.c.source_yield_stress_pa.label("source_yield_stress_pa"),
        table.c.applicable_temperature_min_k.label("applicable_temperature_min_k"),
        table.c.applicable_temperature_max_k.label("applicable_temperature_max_k"),
        table.c.applicable_strain_rate_min_per_s.label("applicable_strain_rate_min_per_s"),
        table.c.applicable_strain_rate_max_per_s.label("applicable_strain_rate_max_per_s"),
        table.c.density_mapping_status.label("density_mapping_status"),
        table.c.youngs_modulus_mapping_status.label("youngs_modulus_mapping_status"),
        table.c.poisson_ratio_mapping_status.label("poisson_ratio_mapping_status"),
        table.c.source_yield_mapping_status.label("source_yield_mapping_status"),
        table.c.temperature_applicability_mapping_status.label(
            "temperature_applicability_mapping_status"
        ),
        table.c.strain_rate_applicability_mapping_status.label(
            "strain_rate_applicability_mapping_status"
        ),
        table.c.unit_system_mapping_status.label("unit_system_mapping_status"),
        table.c.mapping_report_sha256.label("mapping_report_sha256"),
        table.c.card_text.label("card_text"),
        table.c.card_sha256.label("card_sha256"),
        table.c.exporter_id.label("exporter_id"),
        table.c.exporter_version.label("exporter_version"),
        table.c.exporter_digest.label("exporter_digest"),
        table.c.non_production.label("non_production"),
    )


class SqlSolverCardInputProvenanceHook:
    """Attach one card revision to its frozen IR revision after the generic provenance hook."""

    def __init__(self, source_model_revision_id: UUID) -> None:
        self._source_model_revision_id = source_model_revision_id

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        scope = revision.scope
        source_entity_id = session.scalar(
            sa.select(provenance_entity_table.c.id).where(
                provenance_entity_table.c.organization_id == scope.organization_id,
                provenance_entity_table.c.project_id == scope.project_id,
                provenance_entity_table.c.classification == scope.classification,
                provenance_entity_table.c.reference_kind == "revision",
                provenance_entity_table.c.reference_type == "modeling.material_model.revision",
                provenance_entity_table.c.reference_id == self._source_model_revision_id,
            )
        )
        generated_entity_id = session.scalar(
            sa.select(provenance_entity_table.c.id).where(
                provenance_entity_table.c.organization_id == scope.organization_id,
                provenance_entity_table.c.project_id == scope.project_id,
                provenance_entity_table.c.classification == scope.classification,
                provenance_entity_table.c.reference_kind == "revision",
                provenance_entity_table.c.reference_type == "exporting.solver_card.revision",
                provenance_entity_table.c.reference_id == revision.revision_id,
            )
        )
        if source_entity_id is None or generated_entity_id is None:
            raise SolverCardConflict("required source or generated provenance Entity is missing")
        activity_id = session.scalar(
            sa.select(provenance_generation_table.c.activity_id).where(
                provenance_generation_table.c.organization_id == scope.organization_id,
                provenance_generation_table.c.project_id == scope.project_id,
                provenance_generation_table.c.classification == scope.classification,
                provenance_generation_table.c.entity_id == generated_entity_id,
            )
        )
        if activity_id is None:
            raise SolverCardConflict("generated Solver Card provenance Activity is missing")
        values = {
            "organization_id": scope.organization_id,
            "project_id": scope.project_id,
            "classification": scope.classification,
            "recorded_at": revision.created_at,
            "recorded_by": revision.created_by,
        }
        session.execute(
            sa.insert(provenance_usage_table).values(
                **values,
                activity_id=activity_id,
                entity_id=source_entity_id,
                role="material_model_ir",
                ordinal=0,
            )
        )
        session.execute(
            sa.insert(provenance_derivation_table).values(
                **values,
                generated_entity_id=generated_entity_id,
                used_entity_id=source_entity_id,
                activity_id=activity_id,
                derivation_kind="solver_card_export",
            )
        )


class SqlAlchemyExportingRepository(ExportingRepository):
    """Select frozen Modeling inputs and persist typed solver-card revisions under RLS."""

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
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def _model_source_statement(self) -> sa.Select[Any]:
        model = modeling_material_model_table
        revision = modeling_material_model_revision_table
        return sa.select(
            model.c.id.label("material_model_id"),
            revision.c.id.label("id"),
            revision.c.aggregate_id.label("aggregate_id"),
            revision.c.organization_id.label("organization_id"),
            revision.c.project_id.label("project_id"),
            revision.c.classification.label("classification"),
            revision.c.revision_no.label("revision_no"),
            revision.c.based_on_revision_id.label("based_on_revision_id"),
            revision.c.schema_id.label("schema_id"),
            revision.c.schema_version.label("schema_version"),
            revision.c.content_hash.label("content_hash"),
            revision.c.created_at.label("created_at"),
            revision.c.created_by.label("created_by"),
            revision.c.change_reason.label("change_reason"),
            revision.c.request_id.label("request_id"),
            revision.c.trace_id.label("trace_id"),
            revision.c.model_family_id.label("model_family_id"),
            revision.c.model_schema_digest.label("model_schema_digest"),
            revision.c.material_id.label("material_id"),
            revision.c.material_revision_id.label("material_revision_id"),
            revision.c.material_state_id.label("material_state_id"),
            revision.c.material_state_revision_id.label("material_state_revision_id"),
            revision.c.property_set_id.label("property_set_id"),
            revision.c.property_set_revision_id.label("property_set_revision_id"),
            revision.c.density_kg_per_m3.label("density_kg_per_m3"),
            revision.c.youngs_modulus_pa.label("youngs_modulus_pa"),
            revision.c.poisson_ratio.label("poisson_ratio"),
            revision.c.source_yield_stress_pa.label("source_yield_stress_pa"),
            revision.c.applicable_temperature_min_k.label("applicable_temperature_min_k"),
            revision.c.applicable_temperature_max_k.label("applicable_temperature_max_k"),
            revision.c.applicable_strain_rate_min_per_s.label(
                "applicable_strain_rate_min_per_s"
            ),
            revision.c.applicable_strain_rate_max_per_s.label(
                "applicable_strain_rate_max_per_s"
            ),
            revision.c.applicability_note.label("applicability_note"),
            revision.c.reference_temperature_k.label("reference_temperature_k"),
            revision.c.non_production.label("non_production"),
        ).select_from(
            model.join(
                revision,
                sa.and_(
                    revision.c.aggregate_id == model.c.id,
                    revision.c.organization_id == model.c.organization_id,
                    revision.c.project_id == model.c.project_id,
                ),
            )
        )

    def _source_from_row(self, row: Any) -> ReferenceMaterialModelSource:
        if (
            row["model_family_id"] != REFERENCE_MODEL_FAMILY_ID
            or row["model_schema_digest"] != REFERENCE_MODEL_SCHEMA_DIGEST
            or not row["non_production"]
        ):
            raise SolverCardNotFound(
                "the selected Material Model is not the supported reference IR"
            )
        record = RevisionRecord(
            revision_id=cast(UUID, row["id"]),
            aggregate_type="modeling.material_model",
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
        return ReferenceMaterialModelSource(
            material_model_id=cast(UUID, row["material_model_id"]),
            classification=DataClassification(str(row["classification"])),
            revision=RevisionSnapshot(record, _model_content(row)),
        )

    def load_current_reference_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> ReferenceMaterialModelSource:
        model = modeling_material_model_table
        revision = modeling_material_model_revision_table
        statement = self._model_source_statement().where(
            model.c.id == material_model_id,
            model.c.organization_id == context.organization_id,
            model.c.project_id == context.project_id,
            revision.c.id == model.c.current_revision_id,
        )
        return self._load_model_source(context, decision, statement)

    def load_reference_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> ReferenceMaterialModelSource:
        model = modeling_material_model_table
        revision = modeling_material_model_revision_table
        statement = self._model_source_statement().where(
            model.c.id == material_model_id,
            model.c.organization_id == context.organization_id,
            model.c.project_id == context.project_id,
            revision.c.id == material_model_revision_id,
        )
        return self._load_model_source(context, decision, statement)

    def _load_model_source(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        statement: sa.Select[Any],
    ) -> ReferenceMaterialModelSource:
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise SolverCardNotFound("Material Model source is not available") from error
        if row is None:
            raise SolverCardNotFound("Material Model source is not visible in the selected tenant")
        return self._source_from_row(row)

    def solver_card_store(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source_model_revision_id: UUID,
    ) -> RevisionStore[ReferenceOpenRadiossCardContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=(*self._hooks, SqlSolverCardInputProvenanceHook(source_model_revision_id)),
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def _card_snapshot(self, row: Any) -> SolverCardSnapshot:
        content = _card_content(row)
        return SolverCardSnapshot(
            id=cast(UUID, row["aggregate_id"]),
            material_model_id=content.material_model_id,
            target=ExportTarget(
                content.target_solver,
                content.target_version,
                content.target_unit_system,
            ),
            solver_material_id=content.solver_material_id,
            current=RevisionSnapshot(_record(row), content),
        )

    def _current_card_statement(self) -> sa.Select[Any]:
        identity = solver_card_table
        revision = solver_card_revision_table
        return sa.select(*_revision_columns(revision)).select_from(
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

    def get_solver_card(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> SolverCardSnapshot:
        statement = self._current_card_statement().where(
            solver_card_table.c.id == solver_card_id,
            solver_card_table.c.organization_id == context.organization_id,
            solver_card_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise SolverCardNotFound("Solver Card is not available") from error
        if row is None:
            raise SolverCardNotFound("Solver Card is not visible in the selected tenant")
        return self._card_snapshot(row)

    def list_solver_cards_for_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[SolverCardSnapshot, ...]:
        statement = (
            self._current_card_statement()
            .where(
                solver_card_table.c.material_model_id == material_model_id,
                solver_card_table.c.organization_id == context.organization_id,
                solver_card_table.c.project_id == context.project_id,
            )
            .order_by(solver_card_revision_table.c.created_at.desc())
        )
        with self._session(context, decision) as session:
            try:
                rows = session.execute(statement).mappings().all()
            except DBAPIError as error:
                raise SolverCardNotFound("Solver Cards are not available") from error
        return tuple(self._card_snapshot(row) for row in rows)

    def list_solver_card_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> tuple[RevisionSnapshot[ReferenceOpenRadiossCardContent], ...]:
        revision = solver_card_revision_table
        statement = (
            sa.select(*_revision_columns(revision))
            .where(
                revision.c.aggregate_id == solver_card_id,
                revision.c.organization_id == context.organization_id,
                revision.c.project_id == context.project_id,
            )
            .order_by(revision.c.revision_no.desc())
        )
        with self._session(context, decision) as session:
            try:
                rows = session.execute(statement).mappings().all()
            except DBAPIError as error:
                raise SolverCardNotFound("Solver Card revisions are not available") from error
        if not rows:
            raise SolverCardNotFound("Solver Card is not visible in the selected tenant")
        return tuple(RevisionSnapshot(_record(row), _card_content(row)) for row in rows)
