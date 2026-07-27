"""SQLAlchemy repository for explicit Material Catalog identity/revision tables."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from cmp.modules.catalog.application.service import (
    MATERIAL_AGGREGATE_TYPE,
    MATERIAL_LOT_AGGREGATE_TYPE,
    MATERIAL_STATE_AGGREGATE_TYPE,
    PROCESS_DEFINITION_AGGREGATE_TYPE,
    PROCESS_RUN_AGGREGATE_TYPE,
    PROPERTY_SET_AGGREGATE_TYPE,
    STATE_GENEALOGY_AGGREGATE_TYPE,
    CatalogRepository,
    MaterialDetail,
    MaterialLotSnapshot,
    MaterialSearchResult,
    MaterialSnapshot,
    MaterialStateSnapshot,
    ProcessDefinitionSnapshot,
    ProcessRunSnapshot,
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
from cmp.modules.catalog.domain.process_run import (
    BalanceBasis,
    LotFlow,
    ProcessRunContent,
    process_run_canonical,
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

process_run_table = sa.Table(
    "process_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("run_code", sa.String(100), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="catalog",
)
process_run_revision_table = sa.Table(
    "process_run_revision",
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
    sa.Column("process_definition_id", sa.Uuid(), nullable=False),
    sa.Column("process_definition_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("run_code", sa.String(100), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("operator_name", sa.String(200), nullable=True),
    sa.Column("equipment_reference", sa.String(255), nullable=True),
    sa.Column("balance_basis", sa.String(32), nullable=False),
    sa.Column("balance_tolerance_fraction", sa.Numeric(36, 24), nullable=True),
    sa.Column("balance_not_assessed_reason", sa.Text(), nullable=True),
    sa.Column("balance_input_total", sa.Numeric(54, 24), nullable=True),
    sa.Column("balance_output_total", sa.Numeric(54, 24), nullable=True),
    sa.Column("balance_relative_difference", sa.Numeric(36, 24), nullable=True),
    sa.Column("balance_within_tolerance", sa.Boolean(), nullable=True),
    sa.Column("note", sa.Text(), nullable=True),
    schema="catalog",
)
process_run_lot_flow_table = sa.Table(
    "process_run_lot_flow",
    metadata,
    sa.Column("process_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("process_run_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("flow_role", sa.String(8), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("material_lot_id", sa.Uuid(), nullable=False),
    sa.Column("material_lot_revision_id", sa.Uuid(), nullable=False),
    sa.Column("original_quantity", sa.Numeric(54, 24), nullable=False),
    sa.Column("original_unit", sa.String(16), nullable=False),
    sa.Column("quantity_basis", sa.String(16), nullable=False),
    sa.Column("normalized_quantity", sa.Numeric(54, 24), nullable=False),
    sa.Column("normalized_unit", sa.String(16), nullable=False),
    sa.Column("normalization_factor", sa.Numeric(36, 18), nullable=False),
    schema="catalog",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=row["id"],
        aggregate_type=row["aggregate_type"],
        aggregate_id=row["aggregate_id"],
        scope=TenantScope(row["organization_id"], row["project_id"], row["classification"]),
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


def _lot_flow_content(row: Any) -> LotFlow:
    return LotFlow(
        material_lot_id=row["material_lot_id"],
        material_lot_revision_id=row["material_lot_revision_id"],
        original_quantity=row["original_quantity"].normalize(),
        original_unit=row["original_unit"],
        quantity_basis=BalanceBasis(row["quantity_basis"]),
        normalized_quantity=row["normalized_quantity"].normalize(),
        normalized_unit=row["normalized_unit"],
        normalization_factor=row["normalization_factor"].normalize(),
    )


def _process_run_content(
    row: Any,
    inputs: tuple[LotFlow, ...],
    outputs: tuple[LotFlow, ...],
) -> ProcessRunContent:
    return ProcessRunContent(
        process_definition_id=row["process_definition_id"],
        process_definition_revision_id=row["process_definition_revision_id"],
        material_state_id=row["material_state_id"],
        material_state_revision_id=row["material_state_revision_id"],
        run_code=row["run_code"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        operator_name=row["operator_name"],
        equipment_reference=row["equipment_reference"],
        balance_basis=BalanceBasis(row["balance_basis"]),
        balance_tolerance_fraction=(
            row["balance_tolerance_fraction"].normalize()
            if row["balance_tolerance_fraction"] is not None
            else None
        ),
        balance_not_assessed_reason=row["balance_not_assessed_reason"],
        inputs=inputs,
        outputs=outputs,
        note=row["note"],
    )


def _source(row: Any, prefix: str) -> PropertySource:
    return PropertySource(
        PropertySourceKind(row[f"{prefix}_source_kind"]),
        row[f"{prefix}_source_reference"],
    )


def _property_set_content(row: Any) -> PropertySetContent:
    yield_source = _source(row, "yield_stress") if row["yield_stress_pa"] is not None else None
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


def _process_run_values(content: ProcessRunContent) -> dict[str, Any]:
    balance = content.balance
    return {
        "process_definition_id": content.process_definition_id,
        "process_definition_revision_id": content.process_definition_revision_id,
        "material_state_id": content.material_state_id,
        "material_state_revision_id": content.material_state_revision_id,
        "run_code": content.run_code,
        "started_at": content.started_at,
        "ended_at": content.ended_at,
        "operator_name": content.operator_name,
        "equipment_reference": content.equipment_reference,
        "balance_basis": content.balance_basis.value,
        "balance_tolerance_fraction": content.balance_tolerance_fraction,
        "balance_not_assessed_reason": content.balance_not_assessed_reason,
        "balance_input_total": balance.input_total if balance is not None else None,
        "balance_output_total": balance.output_total if balance is not None else None,
        "balance_relative_difference": (
            balance.relative_difference if balance is not None else None
        ),
        "balance_within_tolerance": balance.within_tolerance if balance is not None else None,
        "note": content.note,
    }


def _write_process_run_flows(session: Session, draft: Any) -> None:
    content = draft.content
    if not isinstance(content, ProcessRunContent):
        raise TypeError("Process Run child writer requires ProcessRunContent")
    rows: list[dict[str, Any]] = []
    for role, flows in (("input", content.inputs), ("output", content.outputs)):
        for ordinal, flow in enumerate(flows):
            rows.append(
                {
                    "process_run_revision_id": draft.revision_id,
                    "process_run_id": draft.aggregate_id,
                    "organization_id": draft.scope.organization_id,
                    "project_id": draft.scope.project_id,
                    "classification": draft.scope.classification,
                    "flow_role": role,
                    "ordinal": ordinal,
                    "material_lot_id": flow.material_lot_id,
                    "material_lot_revision_id": flow.material_lot_revision_id,
                    "original_quantity": flow.original_quantity,
                    "original_unit": flow.original_unit,
                    "quantity_basis": flow.quantity_basis.value,
                    "normalized_quantity": flow.normalized_quantity,
                    "normalized_unit": flow.normalized_unit,
                    "normalization_factor": flow.normalization_factor,
                }
            )
    session.execute(sa.insert(process_run_lot_flow_table), rows)


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
_PROCESS_RUN_TABLES: TypedRevisionTables[ProcessRunContent] = TypedRevisionTables(
    aggregate_type=PROCESS_RUN_AGGREGATE_TYPE,
    identity_table=process_run_table,
    revision_table=process_run_revision_table,
    canonical_content=process_run_canonical,
    content_values=_process_run_values,
    identity_values=lambda content: {
        "material_state_id": content.material_state_id,
        "run_code": content.run_code,
    },
    revision_content_writer=_write_process_run_flows,
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
            session_binder=lambda session: self._rls.bind_authorization(session, context, decision),
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
        return self._store(context=context, decision=decision, tables=_PROCESS_DEFINITION_TABLES)

    def material_lot_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[MaterialLotContent]:
        return self._store(context=context, decision=decision, tables=_MATERIAL_LOT_TABLES)

    def state_genealogy_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[StateGenealogyContent]:
        return self._store(context=context, decision=decision, tables=_STATE_GENEALOGY_TABLES)

    def process_run_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ProcessRunContent]:
        return self._store(context=context, decision=decision, tables=_PROCESS_RUN_TABLES)

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
    def _process_run_content_for_row(session: Session, row: Any) -> ProcessRunContent:
        flows = (
            session.execute(
                sa.select(process_run_lot_flow_table)
                .where(
                    process_run_lot_flow_table.c.organization_id == row["organization_id"],
                    process_run_lot_flow_table.c.project_id == row["project_id"],
                    process_run_lot_flow_table.c.process_run_revision_id == row["id"],
                )
                .order_by(
                    process_run_lot_flow_table.c.flow_role.asc(),
                    process_run_lot_flow_table.c.ordinal.asc(),
                )
            )
            .mappings()
            .all()
        )
        inputs = tuple(_lot_flow_content(flow) for flow in flows if flow["flow_role"] == "input")
        outputs = tuple(_lot_flow_content(flow) for flow in flows if flow["flow_role"] == "output")
        return _process_run_content(row, inputs, outputs)

    @classmethod
    def _process_run_snapshot(cls, session: Session, row: Any) -> ProcessRunSnapshot:
        return ProcessRunSnapshot(
            row["identity_id"],
            row["identity_material_state_id"],
            RevisionSnapshot(_record(row), cls._process_run_content_for_row(session, row)),
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
            *_revision_columns(state_genealogy_revision_table, STATE_GENEALOGY_AGGREGATE_TYPE),
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
    def _current_process_run_statement() -> sa.Select[Any]:
        return sa.select(
            process_run_table.c.id.label("identity_id"),
            process_run_table.c.material_state_id.label("identity_material_state_id"),
            *_revision_columns(process_run_revision_table, PROCESS_RUN_AGGREGATE_TYPE),
            process_run_revision_table.c.process_definition_id,
            process_run_revision_table.c.process_definition_revision_id,
            process_run_revision_table.c.material_state_id,
            process_run_revision_table.c.material_state_revision_id,
            process_run_revision_table.c.run_code,
            process_run_revision_table.c.started_at,
            process_run_revision_table.c.ended_at,
            process_run_revision_table.c.operator_name,
            process_run_revision_table.c.equipment_reference,
            process_run_revision_table.c.balance_basis,
            process_run_revision_table.c.balance_tolerance_fraction,
            process_run_revision_table.c.balance_not_assessed_reason,
            process_run_revision_table.c.balance_input_total,
            process_run_revision_table.c.balance_output_total,
            process_run_revision_table.c.balance_relative_difference,
            process_run_revision_table.c.balance_within_tolerance,
            process_run_revision_table.c.note,
        ).select_from(
            SqlAlchemyCatalogRepository._current_join(process_run_table, process_run_revision_table)
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
        offset: int,
        sort_by: str,
        sort_direction: str,
        limit: int,
    ) -> MaterialSearchResult:
        scoped_statement = self._current_material_statement()
        if query is not None:
            escaped = query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            pattern = f"%{escaped}%"
            scoped_statement = scoped_statement.where(
                sa.or_(
                    material_revision_table.c.name.ilike(pattern, escape="!"),
                    material_revision_table.c.material_code.ilike(pattern, escape="!"),
                    material_revision_table.c.material_family.ilike(pattern, escape="!"),
                )
            )
        if material_class is not None:
            if material_class is MaterialClass.UNCLASSIFIED:
                scoped_statement = scoped_statement.where(
                    sa.or_(
                        material_revision_table.c.material_class.is_(None),
                        material_revision_table.c.material_class
                        == MaterialClass.UNCLASSIFIED.value,
                    )
                )
            else:
                scoped_statement = scoped_statement.where(
                    material_revision_table.c.material_class == material_class.value
                )
        # One statement, one scoped CTE: rows, total, and facets see the same RLS-filtered
        # PostgreSQL snapshot even when the requested page is empty or out of range.
        scoped = scoped_statement.cte("scoped_materials")
        order_column = (
            scoped.c.material_class
            if sort_by == "material_class"
            else scoped.c.name
        )
        order_expression = order_column.desc() if sort_direction == "descending" else order_column.asc()
        page = (
            sa.select(scoped)
            .order_by(order_expression, scoped.c.identity_id.asc())
            .offset(offset)
            .limit(limit)
            .cte("material_page")
        )
        facet_counts = (
            sa.select(
                scoped.c.material_class.label("material_class"),
                sa.func.count().label("facet_count"),
            )
            .group_by(scoped.c.material_class)
            .cte("material_facet_counts")
        )
        facet_json = sa.select(
            sa.func.coalesce(
                sa.func.jsonb_agg(
                    sa.func.jsonb_build_object(
                        "material_class", facet_counts.c.material_class,
                        "facet_count", facet_counts.c.facet_count,
                    )
                ),
                sa.literal([], type_=postgresql.JSONB),
            )
        ).scalar_subquery()
        metadata = sa.select(
            sa.select(sa.func.count()).select_from(scoped).scalar_subquery().label("search_total_count"),
            facet_json.label("search_facets"),
        ).cte("material_search_metadata")
        page_order_column = (
            page.c.material_class
            if sort_by == "material_class"
            else page.c.name
        )
        page_order_expression = (
            page_order_column.desc()
            if sort_direction == "descending"
            else page_order_column.asc()
        )
        statement = (
            sa.select(page, metadata.c.search_total_count, metadata.c.search_facets)
            .select_from(metadata.outerjoin(page, sa.true()))
            .order_by(page_order_expression, page.c.identity_id.asc())
        )
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        metadata_row = rows[0]
        total_count = int(metadata_row["search_total_count"])
        facet_rows = metadata_row["search_facets"]
        return MaterialSearchResult(
            tuple(self._material_snapshot(row) for row in rows if row["identity_id"] is not None),
            total_count,
            offset=offset,
            limit=limit,
            # Material class is the only contextual facet whose governed semantics are
            # available on the Material search projection. Provider, evidence source,
            # validation, solver readiness, and condition-aware properties intentionally
            # remain absent until their own server projections are defined.
            facets=tuple(
                (MaterialClass(row["material_class"] or MaterialClass.UNCLASSIFIED.value), int(row["facet_count"]))
                for row in facet_rows
            ),
        )

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
        material = self.get_material(context=context, decision=decision, material_id=material_id)
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
            statement = statement.where(process_definition_revision_table.c.kind == kind.value)
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

    def list_process_runs_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        limit: int,
    ) -> tuple[ProcessRunSnapshot, ...]:
        statement = (
            self._current_process_run_statement()
            .where(process_run_table.c.material_state_id == material_state_id)
            .order_by(
                process_run_revision_table.c.started_at.desc(),
                process_run_revision_table.c.run_code.asc(),
            )
            .limit(limit)
        )
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings().all()
            return tuple(self._process_run_snapshot(session, row) for row in rows)

    def get_process_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_run_id: UUID,
    ) -> ProcessRunSnapshot:
        statement = self._current_process_run_statement().where(
            process_run_table.c.id == process_run_id
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise CatalogNotFound(str(process_run_id))
            return self._process_run_snapshot(session, row)

    def get_process_run_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        process_run_id: UUID,
        revision_id: UUID,
    ) -> RevisionSnapshot[ProcessRunContent]:
        statement = self._revision_statement(
            process_run_revision_table, PROCESS_RUN_AGGREGATE_TYPE
        ).where(
            process_run_revision_table.c.aggregate_id == process_run_id,
            process_run_revision_table.c.id == revision_id,
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise CatalogNotFound(str(revision_id))
            return RevisionSnapshot(_record(row), self._process_run_content_for_row(session, row))
