"""SQLAlchemy repository for explicit Material Catalog identity/revision tables."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cmp.modules.catalog.application.service import (
    MATERIAL_AGGREGATE_TYPE,
    MATERIAL_LOT_AGGREGATE_TYPE,
    MATERIAL_STATE_AGGREGATE_TYPE,
    PROCESS_DEFINITION_AGGREGATE_TYPE,
    PROPERTY_SET_AGGREGATE_TYPE,
    STATE_GENEALOGY_AGGREGATE_TYPE,
    CatalogRepository,
    MaterialDetail,
    MaterialLotSnapshot,
    MaterialSnapshot,
    MaterialStateSnapshot,
    ProcessDefinitionSnapshot,
    PropertySetSnapshot,
    RevisionSnapshot,
    StateGenealogySnapshot,
)
from cmp.modules.catalog.domain.model import (
    Applicability,
    CatalogNotFound,
    LotKind,
    MaterialClass,
    MaterialContent,
    MaterialLotContent,
    MaterialStateContent,
    ProcessDefinitionContent,
    ProcessKind,
    PropertySetContent,
    PropertySource,
    PropertySourceKind,
    StateGenealogyContent,
    material_canonical,
    material_lot_canonical,
    material_state_canonical,
    process_definition_canonical,
    property_set_canonical,
    state_genealogy_canonical,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
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

material_table = sa.Table(
    "material",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="catalog",
)
material_revision_table = sa.Table(
    "material_revision",
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
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("material_code", sa.String(100), nullable=True),
    sa.Column("material_family", sa.String(100), nullable=True),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("material_class", sa.String(32), nullable=True),
    schema="catalog",
)

material_state_table = sa.Table(
    "material_state",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="catalog",
)
material_state_revision_table = sa.Table(
    "material_state_revision",
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
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("manufacturing_route", sa.String(500), nullable=True),
    sa.Column("heat_treatment", sa.String(500), nullable=True),
    sa.Column("lot_or_batch", sa.String(255), nullable=True),
    sa.Column("description", sa.Text(), nullable=True),
    schema="catalog",
)

property_set_table = sa.Table(
    "property_set",
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
    schema="catalog",
)
property_set_revision_table = sa.Table(
    "property_set_revision",
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
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("density_kg_per_m3", sa.Double(), nullable=False),
    sa.Column("density_source_kind", sa.String(32), nullable=False),
    sa.Column("density_source_reference", sa.Text(), nullable=True),
    sa.Column("youngs_modulus_pa", sa.Double(), nullable=False),
    sa.Column("youngs_modulus_source_kind", sa.String(32), nullable=False),
    sa.Column("youngs_modulus_source_reference", sa.Text(), nullable=True),
    sa.Column("poisson_ratio", sa.Double(), nullable=False),
    sa.Column("poisson_ratio_source_kind", sa.String(32), nullable=False),
    sa.Column("poisson_ratio_source_reference", sa.Text(), nullable=True),
    sa.Column("yield_stress_pa", sa.Double(), nullable=True),
    sa.Column("yield_stress_source_kind", sa.String(32), nullable=True),
    sa.Column("yield_stress_source_reference", sa.Text(), nullable=True),
    sa.Column("applicable_temperature_min_k", sa.Double(), nullable=True),
    sa.Column("applicable_temperature_max_k", sa.Double(), nullable=True),
    sa.Column("applicable_strain_rate_min_per_s", sa.Double(), nullable=True),
    sa.Column("applicable_strain_rate_max_per_s", sa.Double(), nullable=True),
    sa.Column("applicability_note", sa.Text(), nullable=True),
    schema="catalog",
)

process_definition_table = sa.Table(
    "process_definition",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="catalog",
)
process_definition_revision_table = sa.Table(
    "process_definition_revision",
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
    sa.Column("process_code", sa.String(100), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("kind", sa.String(32), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    schema="catalog",
)

material_lot_table = sa.Table(
    "material_lot",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="catalog",
)
material_lot_revision_table = sa.Table(
    "material_lot_revision",
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
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("lot_code", sa.String(100), nullable=False),
    sa.Column("kind", sa.String(16), nullable=False),
    sa.Column("manufacturer", sa.String(200), nullable=True),
    sa.Column("supplier", sa.String(200), nullable=True),
    sa.Column("description", sa.Text(), nullable=True),
    schema="catalog",
)

state_genealogy_table = sa.Table(
    "state_genealogy",
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
    schema="catalog",
)
state_genealogy_revision_table = sa.Table(
    "state_genealogy_revision",
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
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("manufacturing_process_id", sa.Uuid(), nullable=True),
    sa.Column("manufacturing_process_revision_id", sa.Uuid(), nullable=True),
    sa.Column("heat_treatment_process_id", sa.Uuid(), nullable=True),
    sa.Column("heat_treatment_process_revision_id", sa.Uuid(), nullable=True),
    sa.Column("material_lot_id", sa.Uuid(), nullable=True),
    sa.Column("material_lot_revision_id", sa.Uuid(), nullable=True),
    sa.Column("note", sa.Text(), nullable=True),
    schema="catalog",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=row["id"],
        aggregate_type=row["aggregate_type"],
        aggregate_id=row["aggregate_id"],
        scope=TenantScope(
            row["organization_id"], row["project_id"], row["classification"]
        ),
        revision_no=int(row["revision_no"]),
        based_on_revision_id=row["based_on_revision_id"],
        schema_id=row["schema_id"],
        schema_version=row["schema_version"],
        content_hash=row["content_hash"],
        created_at=row["created_at"],
        created_by=row["created_by"],
        change_reason=row["change_reason"],
        request_id=row["request_id"],
        trace_id=row["trace_id"],
    )


def _material_content(row: Any) -> MaterialContent:
    return MaterialContent(
        name=row["name"],
        material_code=row["material_code"],
        material_family=row["material_family"],
        description=row["description"],
        material_class=MaterialClass(row["material_class"] or MaterialClass.UNCLASSIFIED.value),
    )


def _material_state_content(row: Any) -> MaterialStateContent:
    return MaterialStateContent(
        material_id=row["material_id"],
        material_revision_id=row["material_revision_id"],
        name=row["name"],
        manufacturing_route=row["manufacturing_route"],
        heat_treatment=row["heat_treatment"],
        lot_or_batch=row["lot_or_batch"],
        description=row["description"],
    )


def _process_definition_content(row: Any) -> ProcessDefinitionContent:
    return ProcessDefinitionContent(
        process_code=row["process_code"],
        name=row["name"],
        kind=ProcessKind(row["kind"]),
        description=row["description"],
    )


def _material_lot_content(row: Any) -> MaterialLotContent:
    return MaterialLotContent(
        material_id=row["material_id"],
        material_revision_id=row["material_revision_id"],
        lot_code=row["lot_code"],
        kind=LotKind(row["kind"]),
        manufacturer=row["manufacturer"],
        supplier=row["supplier"],
        description=row["description"],
    )


def _state_genealogy_content(row: Any) -> StateGenealogyContent:
    return StateGenealogyContent(
        material_state_id=row["material_state_id"],
        material_state_revision_id=row["material_state_revision_id"],
        manufacturing_process_id=row["manufacturing_process_id"],
        manufacturing_process_revision_id=row["manufacturing_process_revision_id"],
        heat_treatment_process_id=row["heat_treatment_process_id"],
        heat_treatment_process_revision_id=row["heat_treatment_process_revision_id"],
        material_lot_id=row["material_lot_id"],
        material_lot_revision_id=row["material_lot_revision_id"],
        note=row["note"],
    )


def _source(row: Any, prefix: str) -> PropertySource:
    return PropertySource(
        PropertySourceKind(row[f"{prefix}_source_kind"]),
        row[f"{prefix}_source_reference"],
    )


def _property_set_content(row: Any) -> PropertySetContent:
    yield_source = (
        _source(row, "yield_stress") if row["yield_stress_pa"] is not None else None
    )
    return PropertySetContent(
        material_state_id=row["material_state_id"],
        material_state_revision_id=row["material_state_revision_id"],
        density_kg_per_m3=float(row["density_kg_per_m3"]),
        density_source=_source(row, "density"),
        youngs_modulus_pa=float(row["youngs_modulus_pa"]),
        youngs_modulus_source=_source(row, "youngs_modulus"),
        poisson_ratio=float(row["poisson_ratio"]),
        poisson_ratio_source=_source(row, "poisson_ratio"),
        yield_stress_pa=(
            float(row["yield_stress_pa"]) if row["yield_stress_pa"] is not None else None
        ),
        yield_stress_source=yield_source,
        applicability=Applicability(
            temperature_min_k=row["applicable_temperature_min_k"],
            temperature_max_k=row["applicable_temperature_max_k"],
            strain_rate_min_per_s=row["applicable_strain_rate_min_per_s"],
            strain_rate_max_per_s=row["applicable_strain_rate_max_per_s"],
            note=row["applicability_note"],
        ),
    )


def _material_values(content: MaterialContent) -> dict[str, Any]:
    return material_canonical(content)


def _material_state_values(content: MaterialStateContent) -> dict[str, Any]:
    return {
        "material_id": content.material_id,
        "material_revision_id": content.material_revision_id,
        "name": content.name,
        "manufacturing_route": content.manufacturing_route,
        "heat_treatment": content.heat_treatment,
        "lot_or_batch": content.lot_or_batch,
        "description": content.description,
    }


def _process_definition_values(content: ProcessDefinitionContent) -> dict[str, Any]:
    return {
        "process_code": content.process_code,
        "name": content.name,
        "kind": content.kind.value,
        "description": content.description,
    }


def _material_lot_values(content: MaterialLotContent) -> dict[str, Any]:
    return {
        "material_id": content.material_id,
        "material_revision_id": content.material_revision_id,
        "lot_code": content.lot_code,
        "kind": content.kind.value,
        "manufacturer": content.manufacturer,
        "supplier": content.supplier,
        "description": content.description,
    }


def _state_genealogy_values(content: StateGenealogyContent) -> dict[str, Any]:
    return {
        "material_state_id": content.material_state_id,
        "material_state_revision_id": content.material_state_revision_id,
        "manufacturing_process_id": content.manufacturing_process_id,
        "manufacturing_process_revision_id": content.manufacturing_process_revision_id,
        "heat_treatment_process_id": content.heat_treatment_process_id,
        "heat_treatment_process_revision_id": content.heat_treatment_process_revision_id,
        "material_lot_id": content.material_lot_id,
        "material_lot_revision_id": content.material_lot_revision_id,
        "note": content.note,
    }


def _property_set_values(content: PropertySetContent) -> dict[str, Any]:
    return {
        "material_state_id": content.material_state_id,
        "material_state_revision_id": content.material_state_revision_id,
        "density_kg_per_m3": content.density_kg_per_m3,
        "density_source_kind": content.density_source.kind.value,
        "density_source_reference": content.density_source.reference,
        "youngs_modulus_pa": content.youngs_modulus_pa,
        "youngs_modulus_source_kind": content.youngs_modulus_source.kind.value,
        "youngs_modulus_source_reference": content.youngs_modulus_source.reference,
        "poisson_ratio": content.poisson_ratio,
        "poisson_ratio_source_kind": content.poisson_ratio_source.kind.value,
        "poisson_ratio_source_reference": content.poisson_ratio_source.reference,
        "yield_stress_pa": content.yield_stress_pa,
        "yield_stress_source_kind": (
            content.yield_stress_source.kind.value
            if content.yield_stress_source is not None
            else None
        ),
        "yield_stress_source_reference": (
            content.yield_stress_source.reference
            if content.yield_stress_source is not None
            else None
        ),
        "applicable_temperature_min_k": content.applicability.temperature_min_k,
        "applicable_temperature_max_k": content.applicability.temperature_max_k,
        "applicable_strain_rate_min_per_s": content.applicability.strain_rate_min_per_s,
        "applicable_strain_rate_max_per_s": content.applicability.strain_rate_max_per_s,
        "applicability_note": content.applicability.note,
    }


_MATERIAL_TABLES: TypedRevisionTables[MaterialContent] = TypedRevisionTables(
    aggregate_type=MATERIAL_AGGREGATE_TYPE,
    identity_table=material_table,
    revision_table=material_revision_table,
    canonical_content=material_canonical,
    content_values=_material_values,
)
_MATERIAL_STATE_TABLES: TypedRevisionTables[MaterialStateContent] = TypedRevisionTables(
    aggregate_type=MATERIAL_STATE_AGGREGATE_TYPE,
    identity_table=material_state_table,
    revision_table=material_state_revision_table,
    canonical_content=material_state_canonical,
    content_values=_material_state_values,
    identity_values=lambda content: {"material_id": content.material_id},
)
_PROPERTY_SET_TABLES: TypedRevisionTables[PropertySetContent] = TypedRevisionTables(
    aggregate_type=PROPERTY_SET_AGGREGATE_TYPE,
    identity_table=property_set_table,
    revision_table=property_set_revision_table,
    canonical_content=property_set_canonical,
    content_values=_property_set_values,
    identity_values=lambda content: {"material_state_id": content.material_state_id},
)
_PROCESS_DEFINITION_TABLES: TypedRevisionTables[ProcessDefinitionContent] = TypedRevisionTables(
    aggregate_type=PROCESS_DEFINITION_AGGREGATE_TYPE,
    identity_table=process_definition_table,
    revision_table=process_definition_revision_table,
    canonical_content=process_definition_canonical,
    content_values=_process_definition_values,
)
_MATERIAL_LOT_TABLES: TypedRevisionTables[MaterialLotContent] = TypedRevisionTables(
    aggregate_type=MATERIAL_LOT_AGGREGATE_TYPE,
    identity_table=material_lot_table,
    revision_table=material_lot_revision_table,
    canonical_content=material_lot_canonical,
    content_values=_material_lot_values,
    identity_values=lambda content: {"material_id": content.material_id},
)
_STATE_GENEALOGY_TABLES: TypedRevisionTables[StateGenealogyContent] = TypedRevisionTables(
    aggregate_type=STATE_GENEALOGY_AGGREGATE_TYPE,
    identity_table=state_genealogy_table,
    revision_table=state_genealogy_revision_table,
    canonical_content=state_genealogy_canonical,
    content_values=_state_genealogy_values,
    identity_values=lambda content: {"material_state_id": content.material_state_id},
)


def _revision_columns(table: sa.Table, aggregate_type: str) -> tuple[Any, ...]:
    return (
        table.c.id.label("id"),
        sa.literal(aggregate_type).label("aggregate_type"),
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


class SqlAlchemyCatalogRepository(CatalogRepository):
    """Use per-call sessions and transaction-local RLS capability bindings."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[SqlRevisionHook] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._revision_hooks = tuple(revision_hooks)

    @contextmanager
    def _transaction(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    def _store[ContentT](
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        tables: TypedRevisionTables[ContentT],
    ) -> RevisionStore[ContentT]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=tables,
            hooks=self._revision_hooks,
            session_binder=lambda session: self._rls.bind_authorization(
                session, context, decision
            ),
        )

    def material_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[MaterialContent]:
        return self._store(context=context, decision=decision, tables=_MATERIAL_TABLES)

    def material_state_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[MaterialStateContent]:
        return self._store(context=context, decision=decision, tables=_MATERIAL_STATE_TABLES)

    def property_set_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[PropertySetContent]:
        return self._store(context=context, decision=decision, tables=_PROPERTY_SET_TABLES)

    def process_definition_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ProcessDefinitionContent]:
        return self._store(
            context=context, decision=decision, tables=_PROCESS_DEFINITION_TABLES
        )

    def material_lot_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[MaterialLotContent]:
        return self._store(context=context, decision=decision, tables=_MATERIAL_LOT_TABLES)

    def state_genealogy_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[StateGenealogyContent]:
        return self._store(
            context=context, decision=decision, tables=_STATE_GENEALOGY_TABLES
        )

    @staticmethod
    def _current_join(identity: sa.Table, revision: sa.Table) -> Any:
        return identity.join(
            revision,
            sa.and_(
                revision.c.id == identity.c.current_revision_id,
                revision.c.aggregate_id == identity.c.id,
                revision.c.organization_id == identity.c.organization_id,
                revision.c.project_id == identity.c.project_id,
                revision.c.classification == identity.c.classification,
            ),
        )

    @staticmethod
    def _material_snapshot(row: Any) -> MaterialSnapshot:
        return MaterialSnapshot(
            row["identity_id"],
            RevisionSnapshot(_record(row), _material_content(row)),
        )

    @staticmethod
    def _material_state_snapshot(row: Any) -> MaterialStateSnapshot:
        return MaterialStateSnapshot(
            row["identity_id"],
            row["identity_material_id"],
            RevisionSnapshot(_record(row), _material_state_content(row)),
        )

    @staticmethod
    def _property_set_snapshot(row: Any) -> PropertySetSnapshot:
        return PropertySetSnapshot(
            row["identity_id"],
            row["identity_material_state_id"],
            RevisionSnapshot(_record(row), _property_set_content(row)),
        )

    @staticmethod
    def _process_definition_snapshot(row: Any) -> ProcessDefinitionSnapshot:
        return ProcessDefinitionSnapshot(
            row["identity_id"],
            RevisionSnapshot(_record(row), _process_definition_content(row)),
        )

    @staticmethod
    def _material_lot_snapshot(row: Any) -> MaterialLotSnapshot:
        return MaterialLotSnapshot(
            row["identity_id"],
            row["identity_material_id"],
            RevisionSnapshot(_record(row), _material_lot_content(row)),
        )

    @staticmethod
    def _state_genealogy_snapshot(row: Any) -> StateGenealogySnapshot:
        return StateGenealogySnapshot(
            row["identity_id"],
            row["identity_material_state_id"],
            RevisionSnapshot(_record(row), _state_genealogy_content(row)),
        )

    @staticmethod
    def _current_material_statement() -> sa.Select[Any]:
        return sa.select(
            material_table.c.id.label("identity_id"),
            *_revision_columns(material_revision_table, MATERIAL_AGGREGATE_TYPE),
            material_revision_table.c.name,
            material_revision_table.c.material_code,
            material_revision_table.c.material_family,
            material_revision_table.c.description,
            material_revision_table.c.material_class,
        ).select_from(
            SqlAlchemyCatalogRepository._current_join(material_table, material_revision_table)
        )

    @staticmethod
    def _current_state_statement() -> sa.Select[Any]:
        return sa.select(
            material_state_table.c.id.label("identity_id"),
            material_state_table.c.material_id.label("identity_material_id"),
            *_revision_columns(material_state_revision_table, MATERIAL_STATE_AGGREGATE_TYPE),
            material_state_revision_table.c.material_id,
            material_state_revision_table.c.material_revision_id,
            material_state_revision_table.c.name,
            material_state_revision_table.c.manufacturing_route,
            material_state_revision_table.c.heat_treatment,
            material_state_revision_table.c.lot_or_batch,
            material_state_revision_table.c.description,
        ).select_from(
            SqlAlchemyCatalogRepository._current_join(
                material_state_table, material_state_revision_table
            )
        )

    @staticmethod
    def _current_property_set_statement() -> sa.Select[Any]:
        return sa.select(
            property_set_table.c.id.label("identity_id"),
            property_set_table.c.material_state_id.label("identity_material_state_id"),
            *_revision_columns(property_set_revision_table, PROPERTY_SET_AGGREGATE_TYPE),
            property_set_revision_table.c.material_state_id,
            property_set_revision_table.c.material_state_revision_id,
            property_set_revision_table.c.density_kg_per_m3,
            property_set_revision_table.c.density_source_kind,
            property_set_revision_table.c.density_source_reference,
            property_set_revision_table.c.youngs_modulus_pa,
            property_set_revision_table.c.youngs_modulus_source_kind,
            property_set_revision_table.c.youngs_modulus_source_reference,
            property_set_revision_table.c.poisson_ratio,
            property_set_revision_table.c.poisson_ratio_source_kind,
            property_set_revision_table.c.poisson_ratio_source_reference,
            property_set_revision_table.c.yield_stress_pa,
            property_set_revision_table.c.yield_stress_source_kind,
            property_set_revision_table.c.yield_stress_source_reference,
            property_set_revision_table.c.applicable_temperature_min_k,
            property_set_revision_table.c.applicable_temperature_max_k,
            property_set_revision_table.c.applicable_strain_rate_min_per_s,
            property_set_revision_table.c.applicable_strain_rate_max_per_s,
            property_set_revision_table.c.applicability_note,
        ).select_from(
            SqlAlchemyCatalogRepository._current_join(
                property_set_table, property_set_revision_table
            )
        )

    @staticmethod
    def _current_process_definition_statement() -> sa.Select[Any]:
        return sa.select(
            process_definition_table.c.id.label("identity_id"),
            *_revision_columns(
                process_definition_revision_table, PROCESS_DEFINITION_AGGREGATE_TYPE
            ),
            process_definition_revision_table.c.process_code,
            process_definition_revision_table.c.name,
            process_definition_revision_table.c.kind,
            process_definition_revision_table.c.description,
        ).select_from(
            SqlAlchemyCatalogRepository._current_join(
                process_definition_table, process_definition_revision_table
            )
        )

    @staticmethod
    def _current_material_lot_statement() -> sa.Select[Any]:
        return sa.select(
            material_lot_table.c.id.label("identity_id"),
            material_lot_table.c.material_id.label("identity_material_id"),
            *_revision_columns(material_lot_revision_table, MATERIAL_LOT_AGGREGATE_TYPE),
            material_lot_revision_table.c.material_id,
            material_lot_revision_table.c.material_revision_id,
            material_lot_revision_table.c.lot_code,
            material_lot_revision_table.c.kind,
            material_lot_revision_table.c.manufacturer,
            material_lot_revision_table.c.supplier,
            material_lot_revision_table.c.description,
        ).select_from(
            SqlAlchemyCatalogRepository._current_join(
                material_lot_table, material_lot_revision_table
            )
        )

    @staticmethod
    def _current_state_genealogy_statement() -> sa.Select[Any]:
        return sa.select(
            state_genealogy_table.c.id.label("identity_id"),
            state_genealogy_table.c.material_state_id.label("identity_material_state_id"),
            *_revision_columns(
                state_genealogy_revision_table, STATE_GENEALOGY_AGGREGATE_TYPE
            ),
            state_genealogy_revision_table.c.material_state_id,
            state_genealogy_revision_table.c.material_state_revision_id,
            state_genealogy_revision_table.c.manufacturing_process_id,
            state_genealogy_revision_table.c.manufacturing_process_revision_id,
            state_genealogy_revision_table.c.heat_treatment_process_id,
            state_genealogy_revision_table.c.heat_treatment_process_revision_id,
            state_genealogy_revision_table.c.material_lot_id,
            state_genealogy_revision_table.c.material_lot_revision_id,
            state_genealogy_revision_table.c.note,
        ).select_from(
            SqlAlchemyCatalogRepository._current_join(
                state_genealogy_table, state_genealogy_revision_table
            )
        )

    @staticmethod
    def _revision_statement(table: sa.Table, aggregate_type: str) -> sa.Select[Any]:
        return sa.select(*_revision_columns(table, aggregate_type), *table.c)

    def list_materials(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: str | None,
        material_class: MaterialClass | None,
        limit: int,
    ) -> tuple[MaterialSnapshot, ...]:
        statement = self._current_material_statement()
        if query is not None:
            escaped = query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            pattern = f"%{escaped}%"
            statement = statement.where(
                sa.or_(
                    material_revision_table.c.name.ilike(pattern, escape="!"),
                    material_revision_table.c.material_code.ilike(pattern, escape="!"),
                    material_revision_table.c.material_family.ilike(pattern, escape="!"),
                )
            )
        if material_class is not None:
            if material_class is MaterialClass.UNCLASSIFIED:
                statement = statement.where(
                    sa.or_(
                        material_revision_table.c.material_class.is_(None),
                        material_revision_table.c.material_class
                        == MaterialClass.UNCLASSIFIED.value,
                    )
                )
            else:
                statement = statement.where(
                    material_revision_table.c.material_class == material_class.value
                )
        statement = statement.order_by(
            material_revision_table.c.name.asc(), material_table.c.id.asc()
        ).limit(limit)
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._material_snapshot(row) for row in rows)

    def get_material(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> MaterialSnapshot:
        statement = self._current_material_statement().where(material_table.c.id == material_id)
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(material_id))
        return self._material_snapshot(row)

    def get_material_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[MaterialContent]:
        statement = self._revision_statement(
            material_revision_table, MATERIAL_AGGREGATE_TYPE
        ).where(
            material_revision_table.c.aggregate_id == material_id,
            material_revision_table.c.id == revision_id,
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(revision_id))
        return RevisionSnapshot(_record(row), _material_content(row))

    def list_material_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> tuple[RevisionSnapshot[MaterialContent], ...]:
        statement = (
            self._revision_statement(material_revision_table, MATERIAL_AGGREGATE_TYPE)
            .where(material_revision_table.c.aggregate_id == material_id)
            .order_by(material_revision_table.c.revision_no.desc())
        )
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        if not rows:
            raise CatalogNotFound(str(material_id))
        return tuple(RevisionSnapshot(_record(row), _material_content(row)) for row in rows)

    def get_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> MaterialStateSnapshot:
        statement = self._current_state_statement().where(
            material_state_table.c.id == material_state_id
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(material_state_id))
        return self._material_state_snapshot(row)

    def get_material_state_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[MaterialStateContent]:
        statement = self._revision_statement(
            material_state_revision_table, MATERIAL_STATE_AGGREGATE_TYPE
        ).where(
            material_state_revision_table.c.aggregate_id == material_state_id,
            material_state_revision_table.c.id == revision_id,
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(revision_id))
        return RevisionSnapshot(_record(row), _material_state_content(row))

    def get_property_set(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        property_set_id: UUID,
    ) -> PropertySetSnapshot:
        statement = self._current_property_set_statement().where(
            property_set_table.c.id == property_set_id
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(property_set_id))
        return self._property_set_snapshot(row)

    def get_property_set_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        property_set_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[PropertySetContent]:
        statement = self._revision_statement(
            property_set_revision_table, PROPERTY_SET_AGGREGATE_TYPE
        ).where(
            property_set_revision_table.c.aggregate_id == property_set_id,
            property_set_revision_table.c.id == revision_id,
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(revision_id))
        return RevisionSnapshot(_record(row), _property_set_content(row))

    def get_material_detail(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> MaterialDetail:
        material = self.get_material(
            context=context, decision=decision, material_id=material_id
        )
        state_statement = (
            self._current_state_statement()
            .where(material_state_table.c.material_id == material_id)
            .order_by(material_state_revision_table.c.name.asc(), material_state_table.c.id.asc())
        )
        with self._transaction(context, decision) as session:
            state_rows = session.execute(state_statement).mappings().all()
        states = tuple(self._material_state_snapshot(row) for row in state_rows)
        if not states:
            return MaterialDetail(material, (), ())
        state_ids = tuple(state.id for state in states)
        property_statement = (
            self._current_property_set_statement()
            .where(property_set_table.c.material_state_id.in_(state_ids))
            .order_by(
                property_set_revision_table.c.created_at.desc(), property_set_table.c.id.asc()
            )
        )
        with self._transaction(context, decision) as session:
            property_rows = session.execute(property_statement).mappings().all()
        return MaterialDetail(
            material,
            states,
            tuple(self._property_set_snapshot(row) for row in property_rows),
        )

    def list_process_definitions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        kind: ProcessKind | None,
        limit: int,
    ) -> tuple[ProcessDefinitionSnapshot, ...]:
        statement = self._current_process_definition_statement()
        if kind is not None:
            statement = statement.where(
                process_definition_revision_table.c.kind == kind.value
            )
        statement = statement.order_by(
            process_definition_revision_table.c.name.asc(),
            process_definition_table.c.id.asc(),
        ).limit(limit)
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._process_definition_snapshot(row) for row in rows)

    def get_process_definition(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_definition_id: UUID,
    ) -> ProcessDefinitionSnapshot:
        statement = self._current_process_definition_statement().where(
            process_definition_table.c.id == process_definition_id
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(process_definition_id))
        return self._process_definition_snapshot(row)

    def get_process_definition_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_definition_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[ProcessDefinitionContent]:
        statement = self._revision_statement(
            process_definition_revision_table, PROCESS_DEFINITION_AGGREGATE_TYPE
        ).where(
            process_definition_revision_table.c.aggregate_id == process_definition_id,
            process_definition_revision_table.c.id == revision_id,
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(revision_id))
        return RevisionSnapshot(_record(row), _process_definition_content(row))

    def list_material_lots(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
        limit: int,
    ) -> tuple[MaterialLotSnapshot, ...]:
        statement = (
            self._current_material_lot_statement()
            .where(material_lot_table.c.material_id == material_id)
            .order_by(
                material_lot_revision_table.c.lot_code.asc(),
                material_lot_table.c.id.asc(),
            )
            .limit(limit)
        )
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._material_lot_snapshot(row) for row in rows)

    def get_material_lot(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_lot_id: UUID,
    ) -> MaterialLotSnapshot:
        statement = self._current_material_lot_statement().where(
            material_lot_table.c.id == material_lot_id
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(material_lot_id))
        return self._material_lot_snapshot(row)

    def get_material_lot_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_lot_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[MaterialLotContent]:
        statement = self._revision_statement(
            material_lot_revision_table, MATERIAL_LOT_AGGREGATE_TYPE
        ).where(
            material_lot_revision_table.c.aggregate_id == material_lot_id,
            material_lot_revision_table.c.id == revision_id,
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(revision_id))
        return RevisionSnapshot(_record(row), _material_lot_content(row))

    def get_state_genealogy_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> StateGenealogySnapshot | None:
        statement = self._current_state_genealogy_statement().where(
            state_genealogy_table.c.material_state_id == material_state_id
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        return self._state_genealogy_snapshot(row) if row is not None else None

    def get_state_genealogy(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        state_genealogy_id: UUID,
    ) -> StateGenealogySnapshot:
        statement = self._current_state_genealogy_statement().where(
            state_genealogy_table.c.id == state_genealogy_id
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise CatalogNotFound(str(state_genealogy_id))
        return self._state_genealogy_snapshot(row)
