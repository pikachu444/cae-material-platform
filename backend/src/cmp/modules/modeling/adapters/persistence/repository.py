"""SQLAlchemy persistence for a typed reference linear-elastic Material Model IR."""

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
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelSnapshot,
    ModelingRepository,
    ReferencePropertySource,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    REFERENCE_MODEL_FAMILY_ID,
    REFERENCE_MODEL_SCHEMA_DIGEST,
    ReferenceLinearElasticContent,
    ReferenceModelNotFound,
    reference_linear_elastic_canonical,
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

material_model_table = sa.Table(
    "material_model",
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

material_model_revision_table = sa.Table(
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

# Cross-module source reads use only public Catalog relation names and concrete revision IDs.
# The modeling application never imports the Catalog persistence adapter.
catalog_property_set_table = sa.Table(
    "property_set",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    schema="catalog",
)
catalog_property_set_revision_table = sa.Table(
    "property_set_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("density_kg_per_m3", sa.Double(), nullable=False),
    sa.Column("youngs_modulus_pa", sa.Double(), nullable=False),
    sa.Column("poisson_ratio", sa.Double(), nullable=False),
    sa.Column("yield_stress_pa", sa.Double(), nullable=True),
    sa.Column("applicable_temperature_min_k", sa.Double(), nullable=True),
    sa.Column("applicable_temperature_max_k", sa.Double(), nullable=True),
    sa.Column("applicable_strain_rate_min_per_s", sa.Double(), nullable=True),
    sa.Column("applicable_strain_rate_max_per_s", sa.Double(), nullable=True),
    sa.Column("applicability_note", sa.Text(), nullable=True),
    schema="catalog",
)
catalog_material_state_revision_table = sa.Table(
    "material_state_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    schema="catalog",
)


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


def _content(row: Any) -> ReferenceLinearElasticContent:
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


def _content_values(content: ReferenceLinearElasticContent) -> dict[str, Any]:
    return {
        "model_family_id": REFERENCE_MODEL_FAMILY_ID,
        "model_schema_digest": REFERENCE_MODEL_SCHEMA_DIGEST,
        "material_id": content.material_id,
        "material_revision_id": content.material_revision_id,
        "material_state_id": content.material_state_id,
        "material_state_revision_id": content.material_state_revision_id,
        "property_set_id": content.property_set_id,
        "property_set_revision_id": content.property_set_revision_id,
        "density_kg_per_m3": content.density_kg_per_m3,
        "youngs_modulus_pa": content.youngs_modulus_pa,
        "poisson_ratio": content.poisson_ratio,
        "source_yield_stress_pa": content.source_yield_stress_pa,
        "applicable_temperature_min_k": content.applicable_temperature_min_k,
        "applicable_temperature_max_k": content.applicable_temperature_max_k,
        "applicable_strain_rate_min_per_s": content.applicable_strain_rate_min_per_s,
        "applicable_strain_rate_max_per_s": content.applicable_strain_rate_max_per_s,
        "applicability_note": content.applicability_note,
        "reference_temperature_k": content.reference_temperature_k,
        "non_production": True,
    }


_TABLES: TypedRevisionTables[ReferenceLinearElasticContent] = TypedRevisionTables(
    aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
    identity_table=material_model_table,
    revision_table=material_model_revision_table,
    canonical_content=reference_linear_elastic_canonical,
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


class SqlAlchemyModelingRepository(ModelingRepository):
    """Tenant/RLS-bound source selection and typed Material Model revision persistence."""

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

    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceLinearElasticContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @contextmanager
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def load_reference_property_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        property_set_revision_id: UUID,
    ) -> ReferencePropertySource:
        property_set = catalog_property_set_table
        property_revision = catalog_property_set_revision_table
        state_revision = catalog_material_state_revision_table
        statement = (
            sa.select(
                property_set.c.id.label("property_set_id"),
                property_revision.c.id.label("property_set_revision_id"),
                property_revision.c.classification.label("classification"),
                property_revision.c.material_state_id.label("material_state_id"),
                property_revision.c.material_state_revision_id.label("material_state_revision_id"),
                property_revision.c.density_kg_per_m3.label("density_kg_per_m3"),
                property_revision.c.youngs_modulus_pa.label("youngs_modulus_pa"),
                property_revision.c.poisson_ratio.label("poisson_ratio"),
                property_revision.c.yield_stress_pa.label("source_yield_stress_pa"),
                property_revision.c.applicable_temperature_min_k.label(
                    "applicable_temperature_min_k"
                ),
                property_revision.c.applicable_temperature_max_k.label(
                    "applicable_temperature_max_k"
                ),
                property_revision.c.applicable_strain_rate_min_per_s.label(
                    "applicable_strain_rate_min_per_s"
                ),
                property_revision.c.applicable_strain_rate_max_per_s.label(
                    "applicable_strain_rate_max_per_s"
                ),
                property_revision.c.applicability_note.label("applicability_note"),
                state_revision.c.material_id.label("material_id"),
                state_revision.c.material_revision_id.label("material_revision_id"),
            )
            .select_from(
                property_set.join(
                    property_revision,
                    sa.and_(
                        property_revision.c.aggregate_id == property_set.c.id,
                        property_revision.c.organization_id == property_set.c.organization_id,
                        property_revision.c.project_id == property_set.c.project_id,
                    ),
                ).join(
                    state_revision,
                    sa.and_(
                        state_revision.c.id == property_revision.c.material_state_revision_id,
                        state_revision.c.aggregate_id == property_revision.c.material_state_id,
                        state_revision.c.organization_id == property_revision.c.organization_id,
                        state_revision.c.project_id == property_revision.c.project_id,
                    ),
                )
            )
        )
        statement = statement.where(
            property_set.c.material_state_id == material_state_id,
            property_revision.c.id == property_set_revision_id,
            property_revision.c.organization_id == context.organization_id,
            property_revision.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise ReferenceModelNotFound(
                    "Catalog Property Set revision is not available"
                ) from error
        if row is None:
            raise ReferenceModelNotFound(
                "Catalog Property Set revision is not visible for this Material State"
            )
        content = ReferenceLinearElasticContent(
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
        )
        return ReferencePropertySource(
            DataClassification(str(row["classification"])),
            content,
        )

    def _snapshot(self, row: Any) -> MaterialModelSnapshot:
        content = _content(row)
        return MaterialModelSnapshot(
            id=cast(UUID, row["aggregate_id"]),
            material_state_id=content.material_state_id,
            current=RevisionSnapshot(_record(row), content),
        )

    def _current_statement(self) -> sa.Select[Any]:
        identity = material_model_table
        revision = material_model_revision_table
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

    def get_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> MaterialModelSnapshot:
        statement = self._current_statement().where(
            material_model_table.c.id == material_model_id,
            material_model_table.c.organization_id == context.organization_id,
            material_model_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise ReferenceModelNotFound("Material Model is not available") from error
        if row is None:
            raise ReferenceModelNotFound("Material Model is not visible in the selected tenant")
        return self._snapshot(row)

    def list_material_models_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[MaterialModelSnapshot, ...]:
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
                raise ReferenceModelNotFound("Material Models are not available") from error
        return tuple(self._snapshot(row) for row in rows)

    def list_material_model_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[RevisionSnapshot[ReferenceLinearElasticContent], ...]:
        revision = material_model_revision_table
        statement = (
            sa.select(*_revision_columns(revision))
            .where(
                revision.c.aggregate_id == material_model_id,
                revision.c.organization_id == context.organization_id,
                revision.c.project_id == context.project_id,
            )
            .order_by(revision.c.revision_no.desc())
        )
        with self._session(context, decision) as session:
            try:
                rows = session.execute(statement).mappings().all()
            except DBAPIError as error:
                raise ReferenceModelNotFound(
                    "Material Model revisions are not available"
                ) from error
        if not rows:
            raise ReferenceModelNotFound("Material Model is not visible in the selected tenant")
        return tuple(RevisionSnapshot(_record(row), _content(row)) for row in rows)
