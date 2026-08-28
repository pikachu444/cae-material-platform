"""PostgreSQL persistence for configurable Catalog folders and records (T-50)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Any, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from cmp.modules.catalog.adapters.persistence.configurable import RlsContext
from cmp.modules.catalog.application.configurable import ConfigRevision
from cmp.modules.catalog.application.records import (
    FOLDER_AGGREGATE_TYPE,
    RECORD_AGGREGATE_TYPE,
    CatalogRecordRepository,
    CreateRecord,
    CurveOwnership,
    CurveOwnershipPointer,
    CurveOwnershipSource,
    FolderSnapshot,
    RecordDomainBinding,
    RecordFacetBucket,
    RecordSearchResult,
    RecordSnapshot,
    RegistrationCellError,
    RegistrationSourceEvidence,
    StoredRegistrationPreview,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    ConfigurableCatalogConflict,
    ConfigurableCatalogNotFound,
)
from cmp.modules.catalog.domain.records import (
    CatalogFolderContent,
    CatalogRecordContent,
    CatalogRecordQuery,
    CatalogRecordValue,
    folder_canonical,
    record_canonical,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlAlchemyRevisionTransaction,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import (
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
    TenantScope,
    content_sha256,
)

metadata = sa.MetaData()
_uuid = sa.Uuid()


def _identity_table(name: str, *extra: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("id", _uuid, nullable=False),
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("current_revision_id", _uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", _uuid, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *extra,
        schema="catalog",
    )


def _revision_table(name: str, *extra: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        f"{name}_revision",
        metadata,
        sa.Column("id", _uuid, nullable=False),
        sa.Column("aggregate_id", _uuid, nullable=False),
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("revision_no", sa.BigInteger(), nullable=False),
        sa.Column("based_on_revision_id", _uuid, nullable=True),
        sa.Column("schema_id", sa.String(255), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.CHAR(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", _uuid, nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("request_id", _uuid, nullable=False),
        sa.Column("trace_id", sa.String(255), nullable=False),
        *extra,
        schema="catalog",
    )


folder = _identity_table("folder", sa.Column("table_id", _uuid, nullable=False))
folder_revision = _revision_table(
    "folder",
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("parent_folder_id", _uuid, nullable=True),
    sa.Column("parent_folder_revision_id", _uuid, nullable=True),
)
catalog_record = _identity_table("catalog_record", sa.Column("table_id", _uuid, nullable=False))
catalog_record_revision = _revision_table(
    "catalog_record",
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("external_key", sa.String(255), nullable=True),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("folder_id", _uuid, nullable=True),
    sa.Column("folder_revision_id", _uuid, nullable=True),
)
schema_table = sa.Table(
    "schema_table",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    schema="catalog",
)
schema_table_revision = sa.Table(
    "schema_table_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("data_category", sa.String(32), nullable=True),
    schema="catalog",
)
# The binding tables are owned by the Catalog links adapter.  A read-only
# declaration here lets the single server query constrain current Record
# revisions without importing a domain/plugin implementation or issuing an
# N+1 binding lookup.  The migration is the authority for constraints/RLS.
domain_record_binding = sa.Table(
    "domain_record_binding",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("record_id", _uuid, nullable=False),
    sa.Column("record_revision_id", _uuid, nullable=False),
    sa.Column("domain_kind", sa.String(32), nullable=False),
    sa.Column("domain_object_id", _uuid, nullable=False),
    sa.Column("domain_revision_id", _uuid, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", _uuid, nullable=False),
    sa.Column("request_id", _uuid, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)
material = sa.Table(
    "material",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    schema="catalog",
)
material_revision = sa.Table(
    "material_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_code", sa.String(100), nullable=True),
    schema="catalog",
)
material_state = sa.Table(
    "material_state",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    sa.Column("material_id", _uuid, nullable=False),
    schema="catalog",
)
material_state_revision = sa.Table(
    "material_state_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_id", _uuid, nullable=False),
    sa.Column("material_revision_id", _uuid, nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    schema="catalog",
)
record_registration_preview = sa.Table(
    "record_registration_preview",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("principal_id", _uuid, nullable=False),
    sa.Column("token_digest", sa.CHAR(64), nullable=False),
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("source_artifact_id", _uuid, nullable=True),
    sa.Column("source_digest", sa.CHAR(64), nullable=False),
    sa.Column("source_format", sa.String(16), nullable=False),
    sa.Column("sheet_name", sa.String(255), nullable=True),
    sa.Column("has_header", sa.Boolean(), nullable=False),
    sa.Column("encoding", sa.String(64), nullable=True),
    sa.Column("delimiter", sa.String(8), nullable=True),
    sa.Column("decimal_separator", sa.String(1), nullable=True),
    sa.Column("unit_mapping_evidence", sa.JSON(), nullable=False),
    sa.Column("rows", sa.JSON(), nullable=False),
    sa.Column("mapping", sa.JSON(), nullable=False),
    sa.Column("state_selection", sa.JSON(), nullable=True),
    sa.Column("errors", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("consumed_by", _uuid, nullable=True),
    schema="catalog",
)
publication_marker = sa.Table(
    "publication_marker",
    metadata,
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("aggregate_type", sa.String(100), nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("revision_id", _uuid, nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("published_by", _uuid, nullable=False),
    schema="catalog",
)
review_publication_projection = sa.Table(
    "review_publication_projection",
    metadata,
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("review_request_id", _uuid, nullable=False),
    sa.Column("subject_type", sa.String(64), nullable=False),
    sa.Column("subject_id", _uuid, nullable=False),
    sa.Column("subject_revision_id", _uuid, nullable=False),
    sa.Column("neutral_material_id", _uuid, nullable=True),
    sa.Column("neutral_material_revision_id", _uuid, nullable=True),
    sa.Column("neutral_artifact_sha256", sa.CHAR(64), nullable=True),
    sa.Column("record_id", _uuid, nullable=False),
    sa.Column("record_revision_id", _uuid, nullable=False),
    sa.Column("record_table_id", _uuid, nullable=False),
    sa.Column("record_table_revision_id", _uuid, nullable=False),
    schema="governance",
)

_test_data_document = sa.Table(
    "test_data_document",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    schema="datasets",
)
_test_data_document_revision = sa.Table(
    "test_data_document_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("normalized_artifact_id", _uuid, nullable=False),
    sa.Column("normalized_sha256", sa.CHAR(64), nullable=False),
    sa.Column("governed_source", sa.JSON(), nullable=True),
    schema="datasets",
)
_dataset_revision = sa.Table(
    "dataset_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("data_artifact_id", _uuid, nullable=False),
    sa.Column("data_sha256", sa.CHAR(64), nullable=False),
    schema="datasets",
)
_pair_statistical_result_revision = sa.Table(
    "statistical_result_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("statistical_run_id", _uuid, nullable=False),
    sa.Column("plan_id", _uuid, nullable=False),
    sa.Column("plan_revision_id", _uuid, nullable=False),
    sa.Column("first_dataset_id", _uuid, nullable=False),
    sa.Column("first_dataset_revision_id", _uuid, nullable=False),
    sa.Column("second_dataset_id", _uuid, nullable=False),
    sa.Column("second_dataset_revision_id", _uuid, nullable=False),
    sa.Column("curve_artifact_id", _uuid, nullable=False),
    sa.Column("curve_sha256", sa.CHAR(64), nullable=False),
    schema="statistics",
)
_replicate_statistical_result_revision = sa.Table(
    "replicate_statistical_result_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("statistical_run_id", _uuid, nullable=False),
    sa.Column("plan_id", _uuid, nullable=False),
    sa.Column("plan_revision_id", _uuid, nullable=False),
    sa.Column("selection_id", _uuid, nullable=False),
    sa.Column("selection_revision_id", _uuid, nullable=False),
    sa.Column("curve_artifact_id", _uuid, nullable=False),
    sa.Column("curve_sha256", sa.CHAR(64), nullable=False),
    schema="statistics",
)
_replicate_statistical_run_member = sa.Table(
    "replicate_statistical_run_member",
    metadata,
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("statistical_run_id", _uuid, nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("dataset_id", _uuid, nullable=False),
    sa.Column("dataset_revision_id", _uuid, nullable=False),
    schema="statistics",
)
_test_run = sa.Table(
    "test_run",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    schema="testing",
)
_specimen_revision = sa.Table(
    "specimen_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    schema="testing",
)
_test_run_revision = sa.Table(
    "test_run_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    schema="testing",
)
_material_model = sa.Table(
    "material_model",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    schema="modeling",
)
_material_model_revision = sa.Table(
    "material_model_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_id", _uuid, nullable=False),
    sa.Column("material_revision_id", _uuid, nullable=False),
    sa.Column("material_state_id", _uuid, nullable=False),
    sa.Column("material_state_revision_id", _uuid, nullable=False),
    sa.Column("source_dataset_id", _uuid, nullable=True),
    sa.Column("source_dataset_revision_id", _uuid, nullable=True),
    sa.Column("processing_output_id", _uuid, nullable=True),
    sa.Column("processing_output_revision_id", _uuid, nullable=True),
    schema="modeling",
)
_processing_output = sa.Table(
    "common_processing_output",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    schema="processing",
)
_processing_output_revision = sa.Table(
    "common_processing_output_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    schema="processing",
)
_solver_card = sa.Table(
    "solver_card",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    schema="exporting",
)
_solver_card_revision = sa.Table(
    "solver_card_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", _uuid, nullable=False),
    sa.Column("material_model_revision_id", _uuid, nullable=False),
    schema="exporting",
)
_neutral_solver_card = sa.Table(
    "neutral_solver_card",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    schema="exporting",
)
_neutral_solver_card_revision = sa.Table(
    "neutral_solver_card_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("neutral_material_id", _uuid, nullable=False),
    sa.Column("neutral_material_revision_id", _uuid, nullable=False),
    schema="exporting",
)
_neutral_material = sa.Table(
    "neutral_material",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", _uuid, nullable=False),
    schema="modeling",
)
_neutral_material_revision = sa.Table(
    "neutral_material_revision",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("aggregate_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("prony_overlay_model_id", _uuid, nullable=True),
    sa.Column("prony_overlay_model_revision_id", _uuid, nullable=True),
    sa.Column("processing_output_id", _uuid, nullable=True),
    sa.Column("processing_output_revision_id", _uuid, nullable=True),
    schema="modeling",
)
_release_manifest = sa.Table(
    "release_manifest",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("release_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    schema="governance",
)
domain_record_identity_binding = sa.Table(
    "domain_record_identity_binding",
    metadata,
    sa.Column("organization_id", _uuid, primary_key=True),
    sa.Column("project_id", _uuid, primary_key=True),
    sa.Column("classification", sa.String(64), primary_key=True),
    sa.Column("domain_kind", sa.String(32), primary_key=True),
    sa.Column("domain_object_id", _uuid, primary_key=True),
    sa.Column("domain_revision_id", _uuid, primary_key=True),
    sa.Column("record_id", _uuid, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", _uuid, nullable=False),
    sa.Column("request_id", _uuid, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)


def _value_table(name: str, *columns: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("organization_id", _uuid, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("record_id", _uuid, nullable=False),
        sa.Column("record_revision_id", _uuid, nullable=False),
        sa.Column("attribute_definition_id", _uuid, nullable=False),
        sa.Column("attribute_definition_revision_id", _uuid, nullable=False),
        *columns,
        schema="catalog",
    )


record_number_value = _value_table(
    "record_number_value",
    sa.Column("original_value", sa.Numeric(), nullable=False),
    sa.Column("original_unit_string", sa.String(64), nullable=False),
    sa.Column("normalized_value", sa.Numeric(), nullable=False),
    sa.Column("normalized_unit", sa.String(64), nullable=False),
    sa.Column("quantity_semantics", sa.String(255), nullable=False),
)
record_integer_value = _value_table(
    "record_integer_value", sa.Column("value", sa.BigInteger(), nullable=False)
)
record_text_value = _value_table("record_text_value", sa.Column("value", sa.Text(), nullable=False))
record_boolean_value = _value_table(
    "record_boolean_value", sa.Column("value", sa.Boolean(), nullable=False)
)
record_date_value = _value_table("record_date_value", sa.Column("value", sa.Date(), nullable=False))
record_discrete_value = _value_table(
    "record_discrete_value", sa.Column("value", sa.String(255), nullable=False)
)
record_file_value = _value_table(
    "record_file_value",
    sa.Column("artifact_id", _uuid, nullable=False),
    sa.Column("artifact_sha256", sa.CHAR(64), nullable=False),
)
record_curve_value = _value_table(
    "record_curve_value",
    sa.Column("artifact_id", _uuid, nullable=False),
    sa.Column("artifact_sha256", sa.CHAR(64), nullable=False),
)
record_reference_value = _value_table(
    "record_reference_value",
    sa.Column("target_record_id", _uuid, nullable=False),
    sa.Column("target_record_revision_id", _uuid, nullable=False),
)

_SCALAR_TABLES: dict[AttributeDataType, sa.Table] = {
    AttributeDataType.INTEGER: record_integer_value,
    AttributeDataType.TEXT: record_text_value,
    AttributeDataType.BOOLEAN: record_boolean_value,
    AttributeDataType.DATE: record_date_value,
    AttributeDataType.DISCRETE: record_discrete_value,
}
_ARTIFACT_TABLES: dict[AttributeDataType, sa.Table] = {
    AttributeDataType.FILE: record_file_value,
    AttributeDataType.CURVE: record_curve_value,
}


def _record(row: Any, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=row["id"],
        aggregate_type=aggregate_type,
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


def _folder_content(row: Any) -> CatalogFolderContent:
    return CatalogFolderContent(
        table_id=row["table_id"],
        table_revision_id=row["table_revision_id"],
        name=row["name"],
        description=row["description"],
        parent_folder_id=row["parent_folder_id"],
        parent_folder_revision_id=row["parent_folder_revision_id"],
    )


def _record_content(row: Any, values: tuple[CatalogRecordValue, ...]) -> CatalogRecordContent:
    return CatalogRecordContent(
        table_id=row["table_id"],
        table_revision_id=row["table_revision_id"],
        name=row["name"],
        external_key=row["external_key"],
        description=row["description"],
        folder_id=row["folder_id"],
        folder_revision_id=row["folder_revision_id"],
        values=values,
    )


def _folder_values(content: CatalogFolderContent) -> dict[str, Any]:
    return {
        "table_id": content.table_id,
        "table_revision_id": content.table_revision_id,
        "name": content.name,
        "description": content.description,
        "parent_folder_id": content.parent_folder_id,
        "parent_folder_revision_id": content.parent_folder_revision_id,
    }


def _record_values(content: CatalogRecordContent) -> dict[str, Any]:
    return {
        "table_id": content.table_id,
        "table_revision_id": content.table_revision_id,
        "name": content.name,
        "external_key": content.external_key,
        "description": content.description,
        "folder_id": content.folder_id,
        "folder_revision_id": content.folder_revision_id,
    }


def _base_child_values(draft: Any, value: CatalogRecordValue) -> dict[str, Any]:
    return {
        "organization_id": draft.scope.organization_id,
        "project_id": draft.scope.project_id,
        "classification": draft.scope.classification,
        "record_id": draft.aggregate_id,
        "record_revision_id": draft.revision_id,
        "attribute_definition_id": value.attribute_definition_id,
        "attribute_definition_revision_id": value.attribute_definition_revision_id,
    }


def _write_record_children(session: Session, draft: Any) -> None:
    content = draft.content
    if not isinstance(content, CatalogRecordContent):
        raise TypeError("Catalog Record child writer requires CatalogRecordContent")
    grouped: dict[sa.Table, list[dict[str, Any]]] = defaultdict(list)
    for value in content.values:
        encoded = _base_child_values(draft, value)
        if value.data_type is AttributeDataType.NUMBER:
            encoded.update(
                original_value=value.original_value,
                original_unit_string=value.original_unit_string,
                normalized_value=value.normalized_value,
                normalized_unit=value.normalized_unit,
                quantity_semantics=value.quantity_semantics,
            )
            grouped[record_number_value].append(encoded)
        elif value.data_type in _SCALAR_TABLES:
            encoded["value"] = value.value
            grouped[_SCALAR_TABLES[value.data_type]].append(encoded)
        elif value.data_type in _ARTIFACT_TABLES:
            encoded.update(artifact_id=value.artifact_id, artifact_sha256=value.artifact_sha256)
            grouped[_ARTIFACT_TABLES[value.data_type]].append(encoded)
        elif value.data_type is AttributeDataType.RECORD_REFERENCE:
            encoded.update(
                target_record_id=value.target_record_id,
                target_record_revision_id=value.target_record_revision_id,
            )
            grouped[record_reference_value].append(encoded)
        else:  # pragma: no cover - exhaustive enum guard
            raise TypeError(f"unsupported Catalog record value type: {value.data_type}")
    for table, rows in grouped.items():
        session.execute(sa.insert(table), rows)


_FOLDERS = TypedRevisionTables(
    aggregate_type=FOLDER_AGGREGATE_TYPE,
    identity_table=folder,
    revision_table=folder_revision,
    canonical_content=folder_canonical,
    content_values=_folder_values,
    identity_values=lambda content: {"table_id": content.table_id},
)
_RECORDS = TypedRevisionTables(
    aggregate_type=RECORD_AGGREGATE_TYPE,
    identity_table=catalog_record,
    revision_table=catalog_record_revision,
    canonical_content=record_canonical,
    content_values=_record_values,
    identity_values=lambda content: {"table_id": content.table_id},
    revision_content_writer=_write_record_children,
)


def _revision_columns(table: sa.Table, aggregate_type: str) -> tuple[Any, ...]:
    return (
        table.c.id,
        sa.literal(aggregate_type).label("aggregate_type"),
        table.c.aggregate_id,
        table.c.organization_id,
        table.c.project_id,
        table.c.classification,
        table.c.revision_no,
        table.c.based_on_revision_id,
        table.c.schema_id,
        table.c.schema_version,
        table.c.content_hash,
        table.c.created_at,
        table.c.created_by,
        table.c.change_reason,
        table.c.request_id,
        table.c.trace_id,
    )


class SqlAlchemyCatalogRecordRepository(CatalogRecordRepository):
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[SqlRevisionHook] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = tuple(revision_hooks)

    @contextmanager
    def _transaction(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    def _store[ContentT](
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        tables: TypedRevisionTables[ContentT],
    ) -> RevisionStore[ContentT]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=tables,
            hooks=self._hooks,
            session_binder=lambda session: self._rls.bind_authorization(session, context, decision),
        )

    def folder_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogFolderContent]:
        return self._store(context, decision, _FOLDERS)

    def record_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CatalogRecordContent]:
        return self._store(context, decision, _RECORDS)

    def resolve_registration_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection: dict[str, str],
    ) -> tuple[tuple[str, UUID, UUID], ...] | None:
        """Resolve only the exact authorized Material/State revisions selected by the user."""

        try:
            material_id = UUID(selection["material_id"])
            material_revision_id = UUID(selection["material_revision_id"])
            state_id = UUID(selection["state_id"])
            state_revision_id = UUID(selection["state_revision_id"])
        except (KeyError, ValueError):
            return None
        with self._transaction(context, decision) as session:
            pair = session.execute(
                sa.select(material_revision.c.id, material_state_revision.c.id)
                .select_from(
                    material_revision.join(
                        material_state_revision,
                        sa.and_(
                            material_state_revision.c.material_id == material_id,
                            material_state_revision.c.material_revision_id
                            == material_revision.c.id,
                        ),
                    )
                )
                .where(
                    material_revision.c.aggregate_id == material_id,
                    material_revision.c.id == material_revision_id,
                    material_state_revision.c.aggregate_id == state_id,
                    material_state_revision.c.id == state_revision_id,
                    material_revision.c.organization_id == context.organization_id,
                    material_revision.c.project_id == context.project_id,
                    material_state_revision.c.organization_id == context.organization_id,
                    material_state_revision.c.project_id == context.project_id,
                )
            ).first()
            if pair is None:
                return None
        # A Catalog Record revision has exactly one governed-domain binding.
        # The exact Material State revision already pins its exact Material
        # revision, so retain the more specific binding after validating both.
        return (("material_state", state_id, state_revision_id),)

    def resolve_registration_material_state_label(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_code: str,
        state_name: str,
    ) -> tuple[tuple[tuple[str, UUID, UUID], ...], str] | None:
        """Resolve one current exact state from the human labels supplied in a row."""

        with self._transaction(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(
                        material.c.id.label("material_id"),
                        material_revision.c.id.label("material_revision_id"),
                        material_state.c.id.label("state_id"),
                        material_state_revision.c.id.label("state_revision_id"),
                        material_state_revision.c.name.label("state_name"),
                    )
                    .select_from(
                        material.join(
                            material_revision,
                            sa.and_(
                                material_revision.c.aggregate_id == material.c.id,
                                material_revision.c.id == material.c.current_revision_id,
                                material_revision.c.organization_id == material.c.organization_id,
                                material_revision.c.project_id == material.c.project_id,
                                material_revision.c.classification == material.c.classification,
                            ),
                        )
                        .join(
                            material_state,
                            sa.and_(
                                material_state.c.material_id == material.c.id,
                                material_state.c.organization_id == material.c.organization_id,
                                material_state.c.project_id == material.c.project_id,
                                material_state.c.classification == material.c.classification,
                            ),
                        )
                        .join(
                            material_state_revision,
                            sa.and_(
                                material_state_revision.c.aggregate_id == material_state.c.id,
                                material_state_revision.c.id
                                == material_state.c.current_revision_id,
                                material_state_revision.c.material_id == material.c.id,
                                material_state_revision.c.material_revision_id
                                == material_revision.c.id,
                                material_state_revision.c.organization_id
                                == material_state.c.organization_id,
                                material_state_revision.c.project_id == material_state.c.project_id,
                                material_state_revision.c.classification
                                == material_state.c.classification,
                            ),
                        )
                    )
                    .where(
                        material.c.organization_id == context.organization_id,
                        material.c.project_id == context.project_id,
                        sa.func.lower(material_revision.c.material_code)
                        == material_code.strip().lower(),
                        sa.func.lower(material_state_revision.c.name) == state_name.strip().lower(),
                    )
                    .limit(2)
                )
                .mappings()
                .all()
            )
        if len(rows) != 1:
            return None
        row = rows[0]
        return (
            (("material_state", row["state_id"], row["state_revision_id"]),),
            row["state_name"],
        )

    def registration_binding_owner(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding: tuple[str, UUID, UUID],
    ) -> UUID | None:
        """Return the existing Catalog identity for one exact domain revision."""

        kind, object_id, revision_id = binding
        with self._transaction(context, decision) as session:
            return session.scalar(
                sa.select(domain_record_identity_binding.c.record_id).where(
                    domain_record_identity_binding.c.organization_id == context.organization_id,
                    domain_record_identity_binding.c.project_id == context.project_id,
                    domain_record_identity_binding.c.domain_kind == kind,
                    domain_record_identity_binding.c.domain_object_id == object_id,
                    domain_record_identity_binding.c.domain_revision_id == revision_id,
                )
            )

    def validate_exact_domain_binding(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        binding: tuple[str, UUID, UUID],
    ) -> bool:
        """Check one caller-supplied domain pin without resolving a mutable head.

        Cross-module revision tables are protected by their own RLS policies.  The
        boolean-only database helper performs the caller-scoped Catalog permission
        check before its SECURITY DEFINER exact-tuple lookup, so this adapter never
        bypasses those policies with a direct cross-module SELECT.
        """

        kind, object_id, revision_id = binding
        with self._transaction(context, decision) as session:
            return bool(
                session.scalar(
                    sa.select(
                        sa.func.access_control.catalog_domain_revision_exists(
                            context.organization_id,
                            context.project_id,
                            sa.cast(classification.value, postgresql.TEXT()),
                            sa.cast(kind, postgresql.TEXT()),
                            object_id,
                            revision_id,
                        )
                    )
                )
            )

    @staticmethod
    def _preview_digest(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def save_registration_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: str,
        token: str,
        table_id: UUID,
        table_revision_id: UUID,
        rows: tuple[dict[str, Any], ...],
        mapping: dict[str, Any],
        common_material_state: dict[str, str] | None,
        source: RegistrationSourceEvidence,
        errors: tuple[RegistrationCellError, ...],
    ) -> None:
        """Persist normalized user input; the opaque token itself is never stored."""

        now = datetime.now(UTC)
        manual_source = repr((rows, mapping, common_material_state)).encode("utf-8")
        with self._transaction(context, decision) as session:
            session.execute(
                sa.insert(record_registration_preview).values(
                    id=uuid4(),
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=classification,
                    principal_id=context.principal.id,
                    token_digest=self._preview_digest(token),
                    table_id=table_id,
                    table_revision_id=table_revision_id,
                    source_artifact_id=source.artifact_id,
                    source_digest=source.sha256 or sha256(manual_source).hexdigest(),
                    source_format=source.file_format,
                    sheet_name=source.sheet_name,
                    has_header=True,
                    encoding=source.encoding,
                    delimiter=source.delimiter,
                    decimal_separator=source.decimal_separator,
                    unit_mapping_evidence=list(source.unit_mappings),
                    rows=list(rows),
                    mapping=mapping,
                    state_selection=common_material_state,
                    errors=[
                        {
                            "row": item.row,
                            "column": item.column,
                            "message": item.message,
                            "action": item.action,
                        }
                        for item in errors
                    ],
                    created_at=now,
                    expires_at=now + timedelta(hours=1),
                    consumed_at=None,
                    consumed_by=None,
                )
            )

    def get_registration_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
    ) -> StoredRegistrationPreview | None:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    sa.select(record_registration_preview).where(
                        record_registration_preview.c.organization_id == context.organization_id,
                        record_registration_preview.c.project_id == context.project_id,
                        record_registration_preview.c.principal_id == context.principal.id,
                        record_registration_preview.c.token_digest == self._preview_digest(token),
                        record_registration_preview.c.consumed_at.is_(None),
                        record_registration_preview.c.expires_at > datetime.now(UTC),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return StoredRegistrationPreview(
                table_id=row["table_id"],
                table_revision_id=row["table_revision_id"],
                rows=tuple(row["rows"]),
                mapping=dict(row["mapping"]),
                common_material_state=(
                    dict(row["state_selection"]) if row["state_selection"] is not None else None
                ),
                source=RegistrationSourceEvidence(
                    row["source_artifact_id"],
                    str(row["source_digest"]),
                    str(row["source_format"]),
                    row["sheet_name"],
                    row["encoding"],
                    row["delimiter"],
                    str(row["decimal_separator"] or "."),
                    tuple(dict(item) for item in row["unit_mapping_evidence"]),
                ),
            )

    def consume_registration_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
    ) -> bool:
        with self._transaction(context, decision) as session:
            result = cast(
                CursorResult[Any],
                session.execute(
                    sa.update(record_registration_preview)
                    .where(
                        record_registration_preview.c.organization_id == context.organization_id,
                        record_registration_preview.c.project_id == context.project_id,
                        record_registration_preview.c.principal_id == context.principal.id,
                        record_registration_preview.c.token_digest == self._preview_digest(token),
                        record_registration_preview.c.consumed_at.is_(None),
                        record_registration_preview.c.expires_at > datetime.now(UTC),
                    )
                    .values(consumed_at=datetime.now(UTC), consumed_by=context.principal.id)
                ),
            )
            return result.rowcount == 1

    def create_records_atomically(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        records: Sequence[tuple[UUID, CreateRecord]],
        registration_token: str | None = None,
        after_create: Callable[[Session, Sequence[RecordSnapshot]], None] | None = None,
    ) -> tuple[RecordSnapshot, ...]:
        """Create a registration batch in one outer database transaction.

        The normal per-record store correctly owns a session per command, so
        it cannot implement a batch boundary.  This repository method builds
        the same typed revision drafts and child values against the one RLS
        bound outer session.  Any exception leaves that outer transaction and
        therefore every row, value and staged hook rolled back.
        """

        with self._transaction(context, decision) as session:
            # Lock and consume the durable preview in this same outer transaction.
            # A separate read/update transaction admitted a concurrent publish between
            # record insertion and token consumption.  The scope/principal predicates
            # deliberately make token use non-transferable.
            preview_id: UUID | None = None
            if registration_token is not None:
                preview = (
                    session.execute(
                        sa.select(record_registration_preview)
                        .where(
                            record_registration_preview.c.organization_id
                            == context.organization_id,
                            record_registration_preview.c.project_id == context.project_id,
                            record_registration_preview.c.principal_id == context.principal.id,
                            record_registration_preview.c.token_digest
                            == self._preview_digest(registration_token),
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if preview is None:
                    raise ConfigurableCatalogConflict("registration preview token was not found")
                if preview["consumed_at"] is not None:
                    raise ConfigurableCatalogConflict("registration preview was already consumed")
                if preview["expires_at"] <= datetime.now(UTC):
                    raise ConfigurableCatalogConflict("registration preview token has expired")
                preview_id = preview["id"]
            transaction = SqlAlchemyRevisionTransaction(session, _RECORDS, self._hooks)
            snapshots: list[RecordSnapshot] = []
            seen_external_keys: set[tuple[UUID, str]] = set()
            for record_id, command in records:
                external_key = command.content.external_key
                if external_key is not None:
                    key = (command.content.table_id, external_key.casefold())
                    if key in seen_external_keys:
                        raise ConfigurableCatalogConflict(
                            "Record external key is duplicated in the registration batch"
                        )
                    seen_external_keys.add(key)
                    existing = session.scalar(
                        sa.select(sa.literal(True))
                        .select_from(
                            catalog_record.join(
                                catalog_record_revision,
                                sa.and_(
                                    catalog_record_revision.c.aggregate_id
                                    == catalog_record.c.id,
                                    catalog_record_revision.c.id
                                    == catalog_record.c.current_revision_id,
                                    catalog_record_revision.c.organization_id
                                    == catalog_record.c.organization_id,
                                    catalog_record_revision.c.project_id
                                    == catalog_record.c.project_id,
                                    catalog_record_revision.c.classification
                                    == catalog_record.c.classification,
                                ),
                            )
                        )
                        .where(
                            catalog_record.c.table_id == command.content.table_id,
                            sa.func.lower(sa.func.btrim(catalog_record_revision.c.external_key))
                            == external_key.strip().casefold(),
                        )
                    )
                    if existing:
                        raise ConfigurableCatalogConflict(
                            "Record external key is already in use"
                        )
                for kind, object_id, revision_id in command.domain_bindings:
                    existing_record_id = session.scalar(
                        sa.select(domain_record_identity_binding.c.record_id).where(
                            domain_record_identity_binding.c.organization_id
                            == context.organization_id,
                            domain_record_identity_binding.c.project_id == context.project_id,
                            domain_record_identity_binding.c.classification
                            == command.classification.value,
                            domain_record_identity_binding.c.domain_kind == kind,
                            domain_record_identity_binding.c.domain_object_id == object_id,
                            domain_record_identity_binding.c.domain_revision_id == revision_id,
                        )
                    )
                    if existing_record_id is not None and existing_record_id != record_id:
                        raise ConfigurableCatalogConflict(
                            "선택한 재료 상태는 이미 다른 데이터에 연결되어 있습니다."
                        )
                scope = TenantScope(
                    context.organization_id, context.project_id, command.classification.value
                )
                draft = RevisionDraft(
                    revision_id=uuid4(),
                    aggregate_type=RECORD_AGGREGATE_TYPE,
                    aggregate_id=record_id,
                    scope=scope,
                    schema_id="urn:cmp:catalog:record:1.0.0",
                    schema_version="1.0.0",
                    content=command.content,
                    content_hash=content_sha256(record_canonical(command.content)),
                    created_at=datetime.now(UTC),
                    created_by=context.principal.id,
                    change_reason=command.change_reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
                record = transaction.create(draft)
                transaction.stage(RevisionCreated(record, "draft"))
                if command.domain_bindings:
                    for kind, object_id, revision_id in command.domain_bindings:
                        session.execute(
                            postgresql.insert(domain_record_identity_binding)
                            .values(
                                organization_id=context.organization_id,
                                project_id=context.project_id,
                                classification=command.classification.value,
                                domain_kind=kind,
                                domain_object_id=object_id,
                                domain_revision_id=revision_id,
                                record_id=record_id,
                                created_at=datetime.now(UTC),
                                created_by=context.principal.id,
                                request_id=context.request_id,
                                trace_id=context.trace_id,
                            )
                            .on_conflict_do_nothing()
                        )
                    session.execute(
                        sa.insert(domain_record_binding),
                        [
                            {
                                "id": uuid4(),
                                "organization_id": context.organization_id,
                                "project_id": context.project_id,
                                "classification": command.classification.value,
                                "record_id": record_id,
                                "record_revision_id": record.revision_id,
                                "domain_kind": kind,
                                "domain_object_id": object_id,
                                "domain_revision_id": revision_id,
                                "created_at": datetime.now(UTC),
                                "created_by": context.principal.id,
                                "request_id": context.request_id,
                                "trace_id": context.trace_id,
                            }
                            for kind, object_id, revision_id in command.domain_bindings
                        ],
                    )
                snapshots.append(
                    RecordSnapshot(
                        record_id,
                        command.content.table_id,
                        ConfigRevision(record, command.content),
                    )
                )
            if preview_id is not None:
                consumed = cast(
                    CursorResult[Any],
                    session.execute(
                        sa.update(record_registration_preview)
                        .where(
                            record_registration_preview.c.id == preview_id,
                            record_registration_preview.c.consumed_at.is_(None),
                        )
                        .values(consumed_at=datetime.now(UTC), consumed_by=context.principal.id)
                    )
                )
                if consumed.rowcount != 1:
                    raise ConfigurableCatalogConflict("registration preview was already consumed")
            if after_create is not None:
                after_create(session, tuple(snapshots))
            return tuple(snapshots)

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
    def _folder_statement() -> sa.Select[Any]:
        return sa.select(
            folder.c.id.label("identity_id"),
            folder.c.table_id.label("identity_table_id"),
            *_revision_columns(folder_revision, FOLDER_AGGREGATE_TYPE),
            folder_revision.c.table_id,
            folder_revision.c.table_revision_id,
            folder_revision.c.name,
            folder_revision.c.description,
            folder_revision.c.parent_folder_id,
            folder_revision.c.parent_folder_revision_id,
        ).select_from(SqlAlchemyCatalogRecordRepository._current_join(folder, folder_revision))

    @staticmethod
    def _record_statement(*, current: bool) -> sa.Select[Any]:
        columns = (
            catalog_record.c.id.label("identity_id"),
            catalog_record.c.table_id.label("identity_table_id"),
            *_revision_columns(catalog_record_revision, RECORD_AGGREGATE_TYPE),
            catalog_record_revision.c.table_id,
            catalog_record_revision.c.table_revision_id,
            catalog_record_revision.c.name,
            catalog_record_revision.c.external_key,
            catalog_record_revision.c.description,
            catalog_record_revision.c.folder_id,
            catalog_record_revision.c.folder_revision_id,
        )
        if current:
            return sa.select(*columns).select_from(
                SqlAlchemyCatalogRecordRepository._current_join(
                    catalog_record, catalog_record_revision
                )
            )
        return sa.select(*columns).select_from(
            catalog_record.join(
                catalog_record_revision,
                sa.and_(
                    catalog_record_revision.c.aggregate_id == catalog_record.c.id,
                    catalog_record_revision.c.organization_id == catalog_record.c.organization_id,
                    catalog_record_revision.c.project_id == catalog_record.c.project_id,
                    catalog_record_revision.c.classification == catalog_record.c.classification,
                ),
            )
        )

    @staticmethod
    def _values_by_revision(
        session: Session, revision_ids: Sequence[UUID]
    ) -> dict[UUID, tuple[CatalogRecordValue, ...]]:
        grouped: dict[UUID, list[CatalogRecordValue]] = defaultdict(list)
        if not revision_ids:
            return {}
        number_rows = session.execute(
            sa.select(record_number_value).where(
                record_number_value.c.record_revision_id.in_(revision_ids)
            )
        ).mappings()
        for row in number_rows:
            grouped[row["record_revision_id"]].append(
                CatalogRecordValue(
                    row["attribute_definition_id"],
                    row["attribute_definition_revision_id"],
                    AttributeDataType.NUMBER,
                    original_value=Decimal(row["original_value"]),
                    original_unit_string=row["original_unit_string"],
                    normalized_value=Decimal(row["normalized_value"]),
                    normalized_unit=row["normalized_unit"],
                    quantity_semantics=row["quantity_semantics"],
                )
            )
        for data_type, table in _SCALAR_TABLES.items():
            rows = session.execute(
                sa.select(table).where(table.c.record_revision_id.in_(revision_ids))
            ).mappings()
            for row in rows:
                grouped[row["record_revision_id"]].append(
                    CatalogRecordValue(
                        row["attribute_definition_id"],
                        row["attribute_definition_revision_id"],
                        data_type,
                        value=row["value"],
                    )
                )
        for data_type, table in _ARTIFACT_TABLES.items():
            rows = session.execute(
                sa.select(table).where(table.c.record_revision_id.in_(revision_ids))
            ).mappings()
            for row in rows:
                grouped[row["record_revision_id"]].append(
                    CatalogRecordValue(
                        row["attribute_definition_id"],
                        row["attribute_definition_revision_id"],
                        data_type,
                        artifact_id=row["artifact_id"],
                        artifact_sha256=row["artifact_sha256"],
                    )
                )
        reference_rows = session.execute(
            sa.select(record_reference_value).where(
                record_reference_value.c.record_revision_id.in_(revision_ids)
            )
        ).mappings()
        for row in reference_rows:
            grouped[row["record_revision_id"]].append(
                CatalogRecordValue(
                    row["attribute_definition_id"],
                    row["attribute_definition_revision_id"],
                    AttributeDataType.RECORD_REFERENCE,
                    target_record_id=row["target_record_id"],
                    target_record_revision_id=row["target_record_revision_id"],
                )
            )
        return {
            revision_id: tuple(sorted(values, key=lambda value: str(value.attribute_definition_id)))
            for revision_id, values in grouped.items()
        }

    def external_key_exists(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        external_key: str,
    ) -> bool:
        with self._transaction(context, decision) as session:
            statement = self._record_statement(current=True).where(
                catalog_record_revision.c.table_id == table_id,
                sa.func.lower(sa.func.btrim(catalog_record_revision.c.external_key))
                == external_key.strip().casefold(),
            )
            return session.execute(statement.limit(1)).first() is not None

    def resolve_current_record_by_external_key(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        external_key: str,
    ) -> RecordSnapshot | None:
        with self._transaction(context, decision) as session:
            rows = (
                session.execute(
                    self._record_statement(current=True).where(
                        catalog_record_revision.c.table_id == table_id,
                        sa.func.lower(sa.func.btrim(catalog_record_revision.c.external_key))
                        == external_key.strip().casefold(),
                    )
                )
                .mappings()
                .all()
            )
            if not rows:
                return None
            if len(rows) != 1:
                raise ConfigurableCatalogConflict(
                    "Record external key resolves to more than one current item"
                )
            values = self._values_by_revision(session, (rows[0]["id"],))
            return self._record_snapshot(rows[0], values)

    def resolve_record_history_by_external_key(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        external_key: str,
    ) -> tuple[RecordSnapshot, ...]:
        """Return every published exact revision for one business identifier.

        JSON registration may auto-resolve a reference only when this complete history query
        yields one immutable published revision.  It intentionally never returns a current/head
        projection or picks the first row.
        """

        statement = (
            self._record_statement(current=False)
            .join(
                publication_marker,
                sa.and_(
                    publication_marker.c.organization_id == catalog_record.c.organization_id,
                    publication_marker.c.project_id == catalog_record.c.project_id,
                    publication_marker.c.classification == catalog_record.c.classification,
                    publication_marker.c.aggregate_type == RECORD_AGGREGATE_TYPE,
                    publication_marker.c.aggregate_id == catalog_record.c.id,
                    publication_marker.c.revision_id == catalog_record_revision.c.id,
                ),
            )
            .where(
                catalog_record_revision.c.table_id == table_id,
                sa.func.lower(sa.func.btrim(catalog_record_revision.c.external_key))
                == external_key.strip().casefold(),
            )
            .order_by(
                catalog_record_revision.c.revision_no.asc(),
                catalog_record_revision.c.id.asc(),
            )
        )
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings().all()
            if not rows:
                return ()
            values = self._values_by_revision(session, tuple(row["id"] for row in rows))
            return tuple(self._record_snapshot(row, values) for row in rows)

    def resolve_record_candidates_by_external_key(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        external_key: str,
    ) -> tuple[RecordSnapshot, ...]:
        """Return every scoped immutable revision eligible for an authorized draft pin.

        Draft registration may reference a prior DRAFT, IN_REVIEW, APPROVED, or PUBLISHED
        Record revision.  The Record store has no mutable lifecycle field; exact visibility
        and scope are enforced by the RLS-bound revision query, while publication remains a
        separate Materials projection concern.
        """

        statement = (
            self._record_statement(current=False)
            .where(
                catalog_record_revision.c.table_id == table_id,
                sa.func.lower(sa.func.btrim(catalog_record_revision.c.external_key))
                == external_key.strip().casefold(),
            )
            .order_by(
                catalog_record_revision.c.revision_no.asc(),
                catalog_record_revision.c.id.asc(),
            )
        )
        with self._transaction(context, decision) as session:
            rows = session.execute(statement).mappings().all()
            if not rows:
                return ()
            values = self._values_by_revision(session, tuple(row["id"] for row in rows))
            return tuple(self._record_snapshot(row, values) for row in rows)

    @staticmethod
    def _folder_snapshot(row: Any) -> FolderSnapshot:
        return FolderSnapshot(
            row["identity_id"],
            row["identity_table_id"],
            ConfigRevision(_record(row, FOLDER_AGGREGATE_TYPE), _folder_content(row)),
        )

    @staticmethod
    def _record_snapshot(
        row: Any,
        values: dict[UUID, tuple[CatalogRecordValue, ...]],
        bindings: dict[UUID, tuple[RecordDomainBinding, ...]] | None = None,
    ) -> RecordSnapshot:
        revision_bindings = () if bindings is None else bindings.get(row["id"], ())
        return RecordSnapshot(
            row["identity_id"],
            row["identity_table_id"],
            ConfigRevision(
                _record(row, RECORD_AGGREGATE_TYPE),
                _record_content(row, values.get(row["id"], ())),
            ),
            revision_bindings[0] if revision_bindings else None,
            revision_bindings,
        )

    @staticmethod
    def _binding_path(kind: str, object_id: UUID, revision_id: UUID) -> str:
        query = f"object_id={object_id}&revision_id={revision_id}"
        roots = {
            "material": f"/materials/{object_id}?revision_id={revision_id}",
            "material_state": f"/materials?{query}",
            "specimen": f"/tests?{query}",
            "test_run": f"/tests?{query}",
            "test_data": f"/datasets/test-json?document_id={object_id}&revision_id={revision_id}",
            "processing_output": f"/datasets/processing?{query}",
            "material_model": f"/models/material-models/{object_id}/revisions/{revision_id}",
            "neutral_material": f"/models/neutral-materials/{object_id}/revisions/{revision_id}",
            "solver_card": f"/exports/cards/{object_id}/revisions/{revision_id}?kind=solver_card",
            "neutral_solver_card": (
                f"/exports/cards/{object_id}/revisions/{revision_id}?kind=neutral_solver_card"
            ),
            "release": f"/governance?{query}",
        }
        return roots[kind]

    def _bindings_by_revision(
        self,
        session: Session,
        revision_ids: Sequence[UUID],
        kind: str | None,
    ) -> dict[UUID, tuple[RecordDomainBinding, ...]]:
        if not revision_ids:
            return {}
        predicate: sa.ColumnElement[bool] = domain_record_binding.c.record_revision_id.in_(
            revision_ids
        )
        if kind is not None:
            predicate = sa.and_(predicate, domain_record_binding.c.domain_kind == kind)
        rows = session.execute(sa.select(domain_record_binding).where(predicate)).mappings()
        bindings: dict[UUID, list[RecordDomainBinding]] = defaultdict(list)
        for row in rows:
            bindings[row["record_revision_id"]].append(
                RecordDomainBinding(
                    binding_id=row["id"],
                    kind=row["domain_kind"],
                    object_id=row["domain_object_id"],
                    revision_id=row["domain_revision_id"],
                    workbench_path=self._binding_path(
                        row["domain_kind"], row["domain_object_id"], row["domain_revision_id"]
                    ),
                    record_id=row["record_id"],
                    record_revision_id=row["record_revision_id"],
                )
            )
        # A Record revision can pin several exact governed revisions (for
        # example a Material and its Material State).  Keep the legacy single
        # projection deterministic while returning the complete set.
        return {
            revision_id: tuple(sorted(items, key=lambda item: (item.kind, str(item.binding_id))))
            for revision_id, items in bindings.items()
        }

    def list_folders(
        self, *, context: SecurityContext, decision: AuthorizationDecision, table_id: UUID
    ) -> tuple[FolderSnapshot, ...]:
        with self._transaction(context, decision) as session:
            rows = session.execute(
                self._folder_statement()
                .where(folder.c.table_id == table_id)
                .order_by(folder_revision.c.name.asc(), folder.c.id.asc())
            ).mappings()
            return tuple(self._folder_snapshot(row) for row in rows)

    def get_folder(
        self, *, context: SecurityContext, decision: AuthorizationDecision, folder_id: UUID
    ) -> FolderSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(self._folder_statement().where(folder.c.id == folder_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Folder was not found")
            return self._folder_snapshot(row)

    def get_folder_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        folder_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogFolderContent]:
        statement = sa.select(
            *_revision_columns(folder_revision, FOLDER_AGGREGATE_TYPE),
            folder_revision.c.table_id,
            folder_revision.c.table_revision_id,
            folder_revision.c.name,
            folder_revision.c.description,
            folder_revision.c.parent_folder_id,
            folder_revision.c.parent_folder_revision_id,
        ).where(
            folder_revision.c.aggregate_id == folder_id,
            folder_revision.c.id == revision_id,
        )
        with self._transaction(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Folder revision was not found")
            return ConfigRevision(_record(row, FOLDER_AGGREGATE_TYPE), _folder_content(row))

    def get_record(
        self, *, context: SecurityContext, decision: AuthorizationDecision, record_id: UUID
    ) -> RecordSnapshot:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    self._record_statement(current=True).where(catalog_record.c.id == record_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Record was not found")
            values = self._values_by_revision(session, (row["id"],))
            return self._record_snapshot(row, values)

    def list_direct_records(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        folder_id: UUID | None,
    ) -> tuple[RecordSnapshot, ...]:
        folder_predicate = (
            catalog_record_revision.c.folder_id.is_(None)
            if folder_id is None
            else catalog_record_revision.c.folder_id == folder_id
        )
        with self._transaction(context, decision) as session:
            rows = (
                session.execute(
                    self._record_statement(current=True)
                    .where(catalog_record.c.table_id == table_id, folder_predicate)
                    .order_by(catalog_record_revision.c.name.asc(), catalog_record.c.id.asc())
                )
                .mappings()
                .all()
            )
            values = self._values_by_revision(session, tuple(row["id"] for row in rows))
            return tuple(self._record_snapshot(row, values) for row in rows)

    def get_record_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogRecordContent]:
        with self._transaction(context, decision) as session:
            row = (
                session.execute(
                    self._record_statement(current=False).where(
                        catalog_record.c.id == record_id,
                        catalog_record_revision.c.id == revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ConfigurableCatalogNotFound("Catalog Record revision was not found")
            values = self._values_by_revision(session, (revision_id,))
            return ConfigRevision(
                _record(row, RECORD_AGGREGATE_TYPE),
                _record_content(row, values.get(revision_id, ())),
            )

    def resolve_curve_ownership(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID,
        artifact_id: UUID,
        artifact_sha256: str,
    ) -> CurveOwnership | None:
        """Resolve only exact, RLS-visible owners already recorded by domain modules."""

        with self._transaction(context, decision) as session:
            canonical_rows = (
                session.execute(
                    sa.select(
                        _test_data_document_revision.c.aggregate_id,
                        _test_data_document_revision.c.id,
                        _test_data_document_revision.c.governed_source,
                        _test_data_document_revision.c.organization_id,
                        _test_data_document_revision.c.project_id,
                        _test_data_document_revision.c.classification,
                    ).where(
                        _test_data_document_revision.c.normalized_artifact_id == artifact_id,
                        _test_data_document_revision.c.normalized_sha256 == artifact_sha256,
                    )
                )
                .mappings()
                .all()
            )
            if len(canonical_rows) == 1:
                canonical = canonical_rows[0]
                document_id = canonical["aggregate_id"]
                document_revision_id = canonical["id"]
                sources: tuple[CurveOwnershipSource, ...] = ()
                provenance: tuple[CurveOwnershipPointer, ...] = ()
                governed = canonical["governed_source"]
                test_run = governed.get("test_run") if isinstance(governed, dict) else None
                if isinstance(test_run, dict):
                    try:
                        test_run_id = UUID(str(test_run["aggregate_id"]))
                        test_run_revision_id = UUID(str(test_run["revision_id"]))
                    except (KeyError, TypeError, ValueError):
                        pass
                    else:
                        sources = (
                            CurveOwnershipSource("test_run", test_run_id, test_run_revision_id),
                        )
                        provenance = (
                            CurveOwnershipPointer("input_usage", test_run_id, test_run_revision_id),
                        )
                binding_row = (
                    session.execute(
                        sa.select(domain_record_binding)
                        .join(
                            catalog_record,
                            sa.and_(
                                catalog_record.c.id == domain_record_binding.c.record_id,
                                catalog_record.c.current_revision_id
                                == domain_record_binding.c.record_revision_id,
                                catalog_record.c.organization_id
                                == domain_record_binding.c.organization_id,
                                catalog_record.c.project_id == domain_record_binding.c.project_id,
                                catalog_record.c.classification
                                == domain_record_binding.c.classification,
                            ),
                        )
                        .where(
                            domain_record_binding.c.domain_kind == "test_data",
                            domain_record_binding.c.domain_object_id == document_id,
                            domain_record_binding.c.domain_revision_id == document_revision_id,
                            domain_record_binding.c.organization_id == canonical["organization_id"],
                            domain_record_binding.c.project_id == canonical["project_id"],
                            domain_record_binding.c.classification == canonical["classification"],
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                binding = (
                    RecordDomainBinding(
                        binding_id=binding_row["id"],
                        kind="test_data",
                        object_id=document_id,
                        revision_id=document_revision_id,
                        workbench_path=self._binding_path(
                            "test_data", document_id, document_revision_id
                        ),
                        record_id=binding_row["record_id"],
                        record_revision_id=binding_row["record_revision_id"],
                    )
                    if binding_row is not None
                    else None
                )
                return CurveOwnership(
                    "test_data_document",
                    document_id,
                    document_revision_id,
                    sources,
                    provenance,
                    binding,
                )

            pair_rows = (
                session.execute(
                    sa.select(_pair_statistical_result_revision).where(
                        _pair_statistical_result_revision.c.curve_artifact_id == artifact_id,
                        _pair_statistical_result_revision.c.curve_sha256 == artifact_sha256,
                    )
                )
                .mappings()
                .all()
            )
            replicate_rows = (
                session.execute(
                    sa.select(_replicate_statistical_result_revision).where(
                        _replicate_statistical_result_revision.c.curve_artifact_id == artifact_id,
                        _replicate_statistical_result_revision.c.curve_sha256 == artifact_sha256,
                    )
                )
                .mappings()
                .all()
            )
            if len(pair_rows) + len(replicate_rows) != 1:
                return None
            if pair_rows:
                pair = pair_rows[0]
                source_rows = (
                    session.execute(
                        sa.select(_dataset_revision).where(
                            sa.tuple_(
                                _dataset_revision.c.aggregate_id,
                                _dataset_revision.c.id,
                            ).in_(
                                (
                                    (
                                        pair["first_dataset_id"],
                                        pair["first_dataset_revision_id"],
                                    ),
                                    (
                                        pair["second_dataset_id"],
                                        pair["second_dataset_revision_id"],
                                    ),
                                )
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
                if len(source_rows) != 2:
                    return None
                source_by_revision = {row["id"]: row for row in source_rows}
                ordered_sources = []
                for dataset_id_key, revision_id_key in (
                    ("first_dataset_id", "first_dataset_revision_id"),
                    ("second_dataset_id", "second_dataset_revision_id"),
                ):
                    row = source_by_revision.get(pair[revision_id_key])
                    if row is None or row["aggregate_id"] != pair[dataset_id_key]:
                        return None
                    ordered_sources.append(
                        CurveOwnershipSource(
                            "dataset",
                            row["aggregate_id"],
                            row["id"],
                            row["data_artifact_id"],
                            row["data_sha256"],
                        )
                    )
                return CurveOwnership(
                    "statistical_result",
                    pair["aggregate_id"],
                    pair["id"],
                    tuple(ordered_sources),
                    (
                        CurveOwnershipPointer(
                            "calculation_plan",
                            pair["plan_id"],
                            pair["plan_revision_id"],
                        ),
                        CurveOwnershipPointer("calculation_run", pair["statistical_run_id"]),
                        CurveOwnershipPointer(
                            "calculation_result",
                            pair["aggregate_id"],
                            pair["id"],
                        ),
                    ),
                )

            statistical = replicate_rows[0]
            member_rows = (
                session.execute(
                    sa.select(
                        _replicate_statistical_run_member.c.dataset_id,
                        _replicate_statistical_run_member.c.dataset_revision_id,
                        _dataset_revision.c.data_artifact_id,
                        _dataset_revision.c.data_sha256,
                    )
                    .join(
                        _dataset_revision,
                        sa.and_(
                            _dataset_revision.c.id
                            == _replicate_statistical_run_member.c.dataset_revision_id,
                            _dataset_revision.c.aggregate_id
                            == _replicate_statistical_run_member.c.dataset_id,
                            _dataset_revision.c.organization_id
                            == _replicate_statistical_run_member.c.organization_id,
                            _dataset_revision.c.project_id
                            == _replicate_statistical_run_member.c.project_id,
                            _dataset_revision.c.classification
                            == _replicate_statistical_run_member.c.classification,
                        ),
                    )
                    .where(
                        _replicate_statistical_run_member.c.statistical_run_id
                        == statistical["statistical_run_id"]
                    )
                    .order_by(_replicate_statistical_run_member.c.ordinal)
                )
                .mappings()
                .all()
            )
            return CurveOwnership(
                "replicate_statistical_result",
                statistical["aggregate_id"],
                statistical["id"],
                tuple(
                    CurveOwnershipSource(
                        "dataset",
                        row["dataset_id"],
                        row["dataset_revision_id"],
                        row["data_artifact_id"],
                        row["data_sha256"],
                    )
                    for row in member_rows
                ),
                (
                    CurveOwnershipPointer(
                        "calculation_plan",
                        statistical["plan_id"],
                        statistical["plan_revision_id"],
                    ),
                    CurveOwnershipPointer("calculation_run", statistical["statistical_run_id"]),
                    CurveOwnershipPointer(
                        "calculation_result",
                        statistical["aggregate_id"],
                        statistical["id"],
                    ),
                ),
            )

    def list_record_revisions(
        self, *, context: SecurityContext, decision: AuthorizationDecision, record_id: UUID
    ) -> tuple[ConfigRevision[CatalogRecordContent], ...]:
        with self._transaction(context, decision) as session:
            rows = (
                session.execute(
                    self._record_statement(current=False)
                    .where(catalog_record.c.id == record_id)
                    .order_by(catalog_record_revision.c.revision_no.asc())
                )
                .mappings()
                .all()
            )
            if not rows:
                raise ConfigurableCatalogNotFound("Catalog Record was not found")
            values = self._values_by_revision(session, tuple(row["id"] for row in rows))
            return tuple(
                ConfigRevision(
                    _record(row, RECORD_AGGREGATE_TYPE),
                    _record_content(row, values.get(row["id"], ())),
                )
                for row in rows
            )

    @staticmethod
    def _review_subject_heads() -> sa.Subquery:
        """Current heads used to re-evaluate review-backed Record publication."""

        def head(table: sa.Table, subject_type: str) -> sa.Select[Any]:
            return sa.select(
                table.c.organization_id.label("organization_id"),
                table.c.project_id.label("project_id"),
                table.c.classification.label("classification"),
                sa.literal(subject_type).label("subject_type"),
                table.c.id.label("subject_id"),
                table.c.current_revision_id.label("subject_revision_id"),
            )

        return sa.union_all(
            head(material, "catalog.material"),
            head(catalog_record, "catalog.configurable_record"),
            head(_test_data_document, "datasets.test_data_document"),
            head(_material_model, "modeling.material_model"),
            head(_solver_card, "exporting.solver_card"),
            head(_neutral_solver_card, "exporting.neutral_solver_card"),
        ).subquery("review_subject_current_head")

    @staticmethod
    def _filtered_statement(query: CatalogRecordQuery) -> sa.Select[Any]:
        if query.published_only:
            published_revision = catalog_record_revision.alias("published_record_revision")
            latest_published_revision_id = (
                sa.select(publication_marker.c.revision_id)
                .join(
                    published_revision,
                    sa.and_(
                        published_revision.c.id == publication_marker.c.revision_id,
                        published_revision.c.aggregate_id == publication_marker.c.aggregate_id,
                        published_revision.c.organization_id
                        == publication_marker.c.organization_id,
                        published_revision.c.project_id == publication_marker.c.project_id,
                    ),
                )
                .where(
                    publication_marker.c.organization_id == catalog_record.c.organization_id,
                    publication_marker.c.project_id == catalog_record.c.project_id,
                    publication_marker.c.aggregate_type == RECORD_AGGREGATE_TYPE,
                    publication_marker.c.aggregate_id == catalog_record.c.id,
                )
                .order_by(published_revision.c.revision_no.desc())
                .limit(1)
                .scalar_subquery()
            )
            # Legacy markers predate review-backed currentness.  A marker may still
            # point at a superseded immutable revision, so keep the same head check
            # used by the review projection branch before exposing it as published.
            # Review-backed markers are evaluated by the subject-currentness branch below.
            # Treating those rows as legacy markers would keep a Record visible after its
            # upstream immutable subject advances, because the marker itself still names the
            # old Record revision.  Only markers with no review projection retain legacy
            # current-head semantics.
            review_marker = sa.exists(
                sa.select(1).where(
                    review_publication_projection.c.organization_id
                    == catalog_record.c.organization_id,
                    review_publication_projection.c.project_id == catalog_record.c.project_id,
                    review_publication_projection.c.classification
                    == catalog_record_revision.c.classification,
                    review_publication_projection.c.record_id == catalog_record.c.id,
                    review_publication_projection.c.record_revision_id
                    == catalog_record_revision.c.id,
                )
            )
            legacy_published = sa.and_(
                catalog_record_revision.c.id == latest_published_revision_id,
                sa.not_(review_marker),
            )
            subject_heads = SqlAlchemyCatalogRecordRepository._review_subject_heads()
            subject_binding_match: sa.ColumnElement[bool] = sa.true()
            if (
                query.domain_binding_kind is not None
                and query.domain_binding_object_id is not None
                and query.domain_binding_revision_id is not None
            ):
                subject_type_for_binding = {
                    "material": "catalog.material",
                    "test_data": "datasets.test_data_document",
                    "material_model": "modeling.material_model",
                    "solver_card": "exporting.solver_card",
                    "neutral_solver_card": "exporting.neutral_solver_card",
                }.get(query.domain_binding_kind)
                if subject_type_for_binding is None:
                    subject_binding_match = sa.false()
                else:
                    subject_binding_match = sa.and_(
                        review_publication_projection.c.subject_type == subject_type_for_binding,
                        review_publication_projection.c.subject_id
                        == query.domain_binding_object_id,
                        review_publication_projection.c.subject_revision_id
                        == query.domain_binding_revision_id,
                    )
                # A Record review may publish a requested domain binding only
                # when that exact binding is attached to the same immutable
                # Record revision.  Keep this scoped to the Record subject so
                # an approved solver card or another Record cannot expose a
                # sibling or stale binding through this query.
                exact_record_binding = sa.exists(
                    sa.select(1).where(
                        domain_record_binding.c.organization_id
                        == review_publication_projection.c.organization_id,
                        domain_record_binding.c.project_id
                        == review_publication_projection.c.project_id,
                        domain_record_binding.c.classification
                        == review_publication_projection.c.classification,
                        domain_record_binding.c.record_id
                        == review_publication_projection.c.record_id,
                        domain_record_binding.c.record_revision_id
                        == review_publication_projection.c.record_revision_id,
                        domain_record_binding.c.domain_kind == query.domain_binding_kind,
                        domain_record_binding.c.domain_object_id == query.domain_binding_object_id,
                        domain_record_binding.c.domain_revision_id
                        == query.domain_binding_revision_id,
                    )
                )
                subject_binding_match = sa.or_(
                    subject_binding_match,
                    sa.and_(
                        review_publication_projection.c.subject_type
                        == "catalog.configurable_record",
                        review_publication_projection.c.subject_id
                        == review_publication_projection.c.record_id,
                        review_publication_projection.c.subject_revision_id
                        == review_publication_projection.c.record_revision_id,
                        exact_record_binding,
                    ),
                )
            # Keep the current Material binding as a safe Materials context when
            # another exact subject (Test Data, selected model, or card) is the
            # approved review subject.  This lets Materials open its row and
            # datasheet while the per-binding projection below still hides
            # unrelated unapproved siblings.
            if query.domain_binding_kind == "material":
                material_context = [
                    domain_record_binding.c.organization_id == catalog_record.c.organization_id,
                    domain_record_binding.c.project_id == catalog_record.c.project_id,
                    domain_record_binding.c.classification
                    == catalog_record_revision.c.classification,
                    domain_record_binding.c.record_id == catalog_record.c.id,
                    domain_record_binding.c.record_revision_id == catalog_record_revision.c.id,
                    domain_record_binding.c.domain_kind == "material",
                ]
                if query.domain_binding_object_id is not None:
                    material_context.extend(
                        (
                            domain_record_binding.c.domain_object_id
                            == query.domain_binding_object_id,
                            domain_record_binding.c.domain_revision_id
                            == query.domain_binding_revision_id,
                        )
                    )
                context_match = sa.exists(sa.select(1).where(*material_context))
                subject_binding_match = sa.or_(subject_binding_match, context_match)
            review_current_subject = sa.exists(
                sa.select(1)
                .select_from(
                    review_publication_projection.join(
                        subject_heads,
                        sa.and_(
                            review_publication_projection.c.organization_id
                            == subject_heads.c.organization_id,
                            review_publication_projection.c.project_id
                            == subject_heads.c.project_id,
                            review_publication_projection.c.classification
                            == subject_heads.c.classification,
                            review_publication_projection.c.subject_type
                            == subject_heads.c.subject_type,
                            review_publication_projection.c.subject_id
                            == subject_heads.c.subject_id,
                            review_publication_projection.c.subject_revision_id
                            == subject_heads.c.subject_revision_id,
                        ),
                    )
                )
                .where(
                    review_publication_projection.c.organization_id
                    == catalog_record.c.organization_id,
                    review_publication_projection.c.project_id == catalog_record.c.project_id,
                    review_publication_projection.c.classification
                    == catalog_record_revision.c.classification,
                    review_publication_projection.c.record_id == catalog_record.c.id,
                    review_publication_projection.c.record_revision_id
                    == catalog_record_revision.c.id,
                    catalog_record.c.current_revision_id == catalog_record_revision.c.id,
                    review_publication_projection.c.record_table_id
                    == catalog_record_revision.c.table_id,
                    review_publication_projection.c.record_table_revision_id
                    == catalog_record_revision.c.table_revision_id,
                    subject_binding_match,
                    sa.or_(
                        sa.and_(
                            review_publication_projection.c.subject_type
                            == "catalog.configurable_record",
                            review_publication_projection.c.subject_id == catalog_record.c.id,
                            review_publication_projection.c.subject_revision_id
                            == catalog_record_revision.c.id,
                        ),
                        sa.exists(
                            sa.select(1).where(
                                domain_record_binding.c.organization_id
                                == review_publication_projection.c.organization_id,
                                domain_record_binding.c.project_id
                                == review_publication_projection.c.project_id,
                                domain_record_binding.c.classification
                                == review_publication_projection.c.classification,
                                domain_record_binding.c.record_id
                                == review_publication_projection.c.record_id,
                                domain_record_binding.c.record_revision_id
                                == review_publication_projection.c.record_revision_id,
                                domain_record_binding.c.domain_object_id
                                == review_publication_projection.c.subject_id,
                                domain_record_binding.c.domain_revision_id
                                == review_publication_projection.c.subject_revision_id,
                                sa.or_(
                                    sa.and_(
                                        review_publication_projection.c.subject_type
                                        == "catalog.material",
                                        domain_record_binding.c.domain_kind == "material",
                                    ),
                                    sa.and_(
                                        review_publication_projection.c.subject_type
                                        == "datasets.test_data_document",
                                        domain_record_binding.c.domain_kind == "test_data",
                                    ),
                                    sa.and_(
                                        review_publication_projection.c.subject_type
                                        == "modeling.material_model",
                                        domain_record_binding.c.domain_kind == "material_model",
                                    ),
                                    sa.and_(
                                        review_publication_projection.c.subject_type
                                        == "exporting.solver_card",
                                        domain_record_binding.c.domain_kind == "solver_card",
                                    ),
                                    sa.and_(
                                        review_publication_projection.c.subject_type
                                        == "exporting.neutral_solver_card",
                                        domain_record_binding.c.domain_kind
                                        == "neutral_solver_card",
                                    ),
                                ),
                            )
                        ),
                    ),
                    sa.or_(
                        review_publication_projection.c.neutral_material_id.is_(None),
                        sa.exists(
                            sa.select(1).where(
                                _neutral_material.c.organization_id
                                == review_publication_projection.c.organization_id,
                                _neutral_material.c.project_id
                                == review_publication_projection.c.project_id,
                                _neutral_material.c.classification
                                == review_publication_projection.c.classification,
                                _neutral_material.c.id
                                == review_publication_projection.c.neutral_material_id,
                                _neutral_material.c.current_revision_id
                                == review_publication_projection.c.neutral_material_revision_id,
                            )
                        ),
                    ),
                    # A reviewed Record is also tied to the exact current Table
                    # schema used to interpret its values.  Advancing that schema
                    # invalidates the published read model without mutating history.
                    sa.exists(
                        sa.select(1).where(
                            schema_table.c.organization_id
                            == catalog_record_revision.c.organization_id,
                            schema_table.c.project_id == catalog_record_revision.c.project_id,
                            schema_table.c.classification
                            == catalog_record_revision.c.classification,
                            schema_table.c.id == catalog_record_revision.c.table_id,
                            schema_table.c.current_revision_id
                            == catalog_record_revision.c.table_revision_id,
                        )
                    ),
                    # Material Model revisions carry typed exact Material,
                    # Material State, Test Data and Processing Output pins.  A
                    # later head in any of those aggregates invalidates a card's
                    # approved Record projection.
                    sa.or_(
                        sa.not_(
                            review_publication_projection.c.subject_type.in_(
                                (
                                    "modeling.material_model",
                                    "exporting.solver_card",
                                )
                            )
                        ),
                        sa.exists(
                            sa.select(1).where(
                                _material_model_revision.c.organization_id
                                == review_publication_projection.c.organization_id,
                                _material_model_revision.c.project_id
                                == review_publication_projection.c.project_id,
                                _material_model_revision.c.classification
                                == review_publication_projection.c.classification,
                                _material_model_revision.c.aggregate_id
                                == sa.case(
                                    (
                                        review_publication_projection.c.subject_type
                                        == "modeling.material_model",
                                        review_publication_projection.c.subject_id,
                                    ),
                                    (
                                        review_publication_projection.c.subject_type
                                        == "exporting.solver_card",
                                        sa.select(_solver_card_revision.c.material_model_id)
                                        .where(
                                            _solver_card_revision.c.organization_id
                                            == review_publication_projection.c.organization_id,
                                            _solver_card_revision.c.project_id
                                            == review_publication_projection.c.project_id,
                                            _solver_card_revision.c.classification
                                            == review_publication_projection.c.classification,
                                            _solver_card_revision.c.aggregate_id
                                            == review_publication_projection.c.subject_id,
                                            _solver_card_revision.c.id
                                            == review_publication_projection.c.subject_revision_id,
                                        )
                                        .scalar_subquery(),
                                    ),
                                ),
                                _material_model_revision.c.id
                                == sa.case(
                                    (
                                        review_publication_projection.c.subject_type
                                        == "modeling.material_model",
                                        review_publication_projection.c.subject_revision_id,
                                    ),
                                    (
                                        review_publication_projection.c.subject_type
                                        == "exporting.solver_card",
                                        sa.select(
                                            _solver_card_revision.c.material_model_revision_id
                                        )
                                        .where(
                                            _solver_card_revision.c.organization_id
                                            == review_publication_projection.c.organization_id,
                                            _solver_card_revision.c.project_id
                                            == review_publication_projection.c.project_id,
                                            _solver_card_revision.c.classification
                                            == review_publication_projection.c.classification,
                                            _solver_card_revision.c.aggregate_id
                                            == review_publication_projection.c.subject_id,
                                            _solver_card_revision.c.id
                                            == review_publication_projection.c.subject_revision_id,
                                        )
                                        .scalar_subquery(),
                                    ),
                                ),
                                sa.exists(
                                    sa.select(1).where(
                                        material.c.organization_id
                                        == _material_model_revision.c.organization_id,
                                        material.c.project_id
                                        == _material_model_revision.c.project_id,
                                        material.c.classification
                                        == _material_model_revision.c.classification,
                                        material.c.id == _material_model_revision.c.material_id,
                                        material.c.current_revision_id
                                        == _material_model_revision.c.material_revision_id,
                                    )
                                ),
                                sa.exists(
                                    sa.select(1).where(
                                        material_state.c.organization_id
                                        == _material_model_revision.c.organization_id,
                                        material_state.c.project_id
                                        == _material_model_revision.c.project_id,
                                        material_state.c.classification
                                        == _material_model_revision.c.classification,
                                        material_state.c.id
                                        == _material_model_revision.c.material_state_id,
                                        material_state.c.current_revision_id
                                        == _material_model_revision.c.material_state_revision_id,
                                    )
                                ),
                                sa.or_(
                                    _material_model_revision.c.source_dataset_id.is_(None),
                                    sa.exists(
                                        sa.select(1).where(
                                            _test_data_document.c.organization_id
                                            == _material_model_revision.c.organization_id,
                                            _test_data_document.c.project_id
                                            == _material_model_revision.c.project_id,
                                            _test_data_document.c.classification
                                            == _material_model_revision.c.classification,
                                            _test_data_document.c.id
                                            == _material_model_revision.c.source_dataset_id,
                                            _test_data_document.c.current_revision_id
                                            == (
                                                _material_model_revision.c.source_dataset_revision_id
                                            ),
                                        )
                                    ),
                                ),
                                sa.or_(
                                    _material_model_revision.c.processing_output_id.is_(None),
                                    sa.exists(
                                        sa.select(1).where(
                                            _processing_output.c.organization_id
                                            == _material_model_revision.c.organization_id,
                                            _processing_output.c.project_id
                                            == _material_model_revision.c.project_id,
                                            _processing_output.c.classification
                                            == _material_model_revision.c.classification,
                                            _processing_output.c.id
                                            == _material_model_revision.c.processing_output_id,
                                            _processing_output.c.current_revision_id
                                            == (
                                                _material_model_revision.c.processing_output_revision_id
                                            ),
                                        )
                                    ),
                                ),
                            )
                        ),
                    ),
                    # Neutral Solver Cards carry a typed exact Neutral pin.  Keep
                    # that pin current independently of the projection's copy.
                    sa.or_(
                        review_publication_projection.c.subject_type
                        != "exporting.neutral_solver_card",
                        sa.exists(
                            sa.select(1).where(
                                _neutral_solver_card_revision.c.organization_id
                                == review_publication_projection.c.organization_id,
                                _neutral_solver_card_revision.c.project_id
                                == review_publication_projection.c.project_id,
                                _neutral_solver_card_revision.c.classification
                                == review_publication_projection.c.classification,
                                _neutral_solver_card_revision.c.aggregate_id
                                == review_publication_projection.c.subject_id,
                                _neutral_solver_card_revision.c.id
                                == review_publication_projection.c.subject_revision_id,
                                _neutral_solver_card_revision.c.neutral_material_id
                                == review_publication_projection.c.neutral_material_id,
                                _neutral_solver_card_revision.c.neutral_material_revision_id
                                == review_publication_projection.c.neutral_material_revision_id,
                            )
                        ),
                    ),
                    # Canonical Test Data embeds typed governed Material and
                    # Material State references.  Re-evaluate those heads so a
                    # stale document cannot remain in Materials after an
                    # upstream condition revision advances.
                    sa.or_(
                        review_publication_projection.c.subject_type
                        != "datasets.test_data_document",
                        sa.exists(
                            sa.select(1).where(
                                _test_data_document_revision.c.organization_id
                                == review_publication_projection.c.organization_id,
                                _test_data_document_revision.c.project_id
                                == review_publication_projection.c.project_id,
                                _test_data_document_revision.c.classification
                                == review_publication_projection.c.classification,
                                _test_data_document_revision.c.aggregate_id
                                == review_publication_projection.c.subject_id,
                                _test_data_document_revision.c.id
                                == review_publication_projection.c.subject_revision_id,
                                sa.or_(
                                    _test_data_document_revision.c.governed_source.is_(None),
                                    sa.and_(
                                        sa.exists(
                                            sa.select(1).where(
                                                material.c.organization_id
                                                == _test_data_document_revision.c.organization_id,
                                                material.c.project_id
                                                == _test_data_document_revision.c.project_id,
                                                material.c.classification
                                                == _test_data_document_revision.c.classification,
                                                material.c.id
                                                == sa.cast(
                                                    _test_data_document_revision.c.governed_source[
                                                        "material"
                                                    ]["aggregate_id"].as_string(),
                                                    _uuid,
                                                ),
                                                material.c.current_revision_id
                                                == sa.cast(
                                                    _test_data_document_revision.c.governed_source[
                                                        "material"
                                                    ]["revision_id"].as_string(),
                                                    _uuid,
                                                ),
                                            )
                                        ),
                                        sa.exists(
                                            sa.select(1).where(
                                                material_state.c.organization_id
                                                == _test_data_document_revision.c.organization_id,
                                                material_state.c.project_id
                                                == _test_data_document_revision.c.project_id,
                                                material_state.c.classification
                                                == _test_data_document_revision.c.classification,
                                                material_state.c.id
                                                == sa.cast(
                                                    _test_data_document_revision.c.governed_source[
                                                        "material_state"
                                                    ]["aggregate_id"].as_string(),
                                                    _uuid,
                                                ),
                                                material_state.c.current_revision_id
                                                == sa.cast(
                                                    _test_data_document_revision.c.governed_source[
                                                        "material_state"
                                                    ]["revision_id"].as_string(),
                                                    _uuid,
                                                ),
                                            )
                                        ),
                                        sa.exists(
                                            sa.select(1).where(
                                                _test_run.c.organization_id
                                                == _test_data_document_revision.c.organization_id,
                                                _test_run.c.project_id
                                                == _test_data_document_revision.c.project_id,
                                                _test_run.c.classification
                                                == _test_data_document_revision.c.classification,
                                                _test_run.c.id
                                                == sa.cast(
                                                    _test_data_document_revision.c.governed_source[
                                                        "test_run"
                                                    ]["aggregate_id"].as_string(),
                                                    _uuid,
                                                ),
                                                _test_run.c.current_revision_id
                                                == sa.cast(
                                                    _test_data_document_revision.c.governed_source[
                                                        "test_run"
                                                    ]["revision_id"].as_string(),
                                                    _uuid,
                                                ),
                                            )
                                        ),
                                    ),
                                ),
                            )
                        ),
                    ),
                    # A reviewed Material Model may publish the Neutral revision
                    # selected by its exact model or Processing Output pin.  Do
                    # not expose the Record if that Neutral revision no longer
                    # carries either exact lineage pin.
                    sa.or_(
                        review_publication_projection.c.subject_type != "modeling.material_model",
                        sa.exists(
                            sa.select(1).where(
                                _neutral_material_revision.c.organization_id
                                == review_publication_projection.c.organization_id,
                                _neutral_material_revision.c.project_id
                                == review_publication_projection.c.project_id,
                                _neutral_material_revision.c.classification
                                == review_publication_projection.c.classification,
                                _neutral_material_revision.c.aggregate_id
                                == review_publication_projection.c.neutral_material_id,
                                _neutral_material_revision.c.id
                                == review_publication_projection.c.neutral_material_revision_id,
                                sa.or_(
                                    sa.and_(
                                        _neutral_material_revision.c.prony_overlay_model_id
                                        == review_publication_projection.c.subject_id,
                                        _neutral_material_revision.c.prony_overlay_model_revision_id
                                        == review_publication_projection.c.subject_revision_id,
                                    ),
                                    sa.exists(
                                        sa.select(1).where(
                                            _material_model_revision.c.organization_id
                                            == _neutral_material_revision.c.organization_id,
                                            _material_model_revision.c.project_id
                                            == _neutral_material_revision.c.project_id,
                                            _material_model_revision.c.classification
                                            == _neutral_material_revision.c.classification,
                                            _material_model_revision.c.aggregate_id
                                            == review_publication_projection.c.subject_id,
                                            _material_model_revision.c.id
                                            == review_publication_projection.c.subject_revision_id,
                                            _material_model_revision.c.processing_output_id
                                            == _neutral_material_revision.c.processing_output_id,
                                            _material_model_revision.c.processing_output_revision_id
                                            == (
                                                _neutral_material_revision.c.processing_output_revision_id
                                            ),
                                        )
                                    ),
                                ),
                            )
                        ),
                    ),
                )
            )
            statement = SqlAlchemyCatalogRecordRepository._record_statement(current=False).where(
                sa.or_(legacy_published, review_current_subject)
            )
        else:
            statement = SqlAlchemyCatalogRecordRepository._record_statement(current=True)
        if query.table_id is not None:
            statement = statement.where(catalog_record.c.table_id == query.table_id)
        else:
            assert query.data_category is not None
            category_kinds = {
                "technical_data": ("material", "material_state"),
                "test_data": ("specimen", "test_run", "test_data"),
                "simulation_data": (
                    "processing_output",
                    "material_model",
                    "neutral_material",
                ),
                "solver_cards": ("solver_card", "neutral_solver_card"),
            }
            all_category_kinds = tuple(
                kind for values in category_kinds.values() for kind in values
            )
            binding_scope = (
                domain_record_binding.c.organization_id
                == catalog_record_revision.c.organization_id,
                domain_record_binding.c.project_id == catalog_record_revision.c.project_id,
                domain_record_binding.c.classification == catalog_record_revision.c.classification,
                domain_record_binding.c.record_id == catalog_record.c.id,
                domain_record_binding.c.record_revision_id == catalog_record_revision.c.id,
            )
            categorized_binding = sa.exists(
                sa.select(1).where(
                    *binding_scope,
                    domain_record_binding.c.domain_kind.in_(all_category_kinds),
                )
            )
            requested_binding = sa.exists(
                sa.select(1).where(
                    *binding_scope,
                    domain_record_binding.c.domain_kind.in_(category_kinds[query.data_category]),
                )
            )
            configured_table_category = sa.exists(
                sa.select(1)
                .select_from(
                    schema_table.join(
                        schema_table_revision,
                        sa.and_(
                            schema_table_revision.c.id == schema_table.c.current_revision_id,
                            schema_table_revision.c.aggregate_id == schema_table.c.id,
                            schema_table_revision.c.organization_id
                            == schema_table.c.organization_id,
                            schema_table_revision.c.project_id == schema_table.c.project_id,
                            schema_table_revision.c.classification == schema_table.c.classification,
                        ),
                    )
                )
                .where(
                    schema_table.c.id == catalog_record.c.table_id,
                    schema_table_revision.c.id == catalog_record_revision.c.table_revision_id,
                    schema_table_revision.c.data_category == query.data_category,
                )
            )
            statement = statement.where(
                sa.or_(
                    requested_binding,
                    sa.and_(sa.not_(categorized_binding), configured_table_category),
                )
            )
        if query.text is not None:
            pattern = f"%{query.text.lower()}%"
            statement = statement.where(
                sa.or_(
                    sa.func.lower(catalog_record_revision.c.name).like(pattern),
                    sa.func.lower(
                        sa.func.coalesce(catalog_record_revision.c.external_key, "")
                    ).like(pattern),
                    sa.func.lower(sa.func.coalesce(catalog_record_revision.c.description, "")).like(
                        pattern
                    ),
                    sa.exists(
                        sa.select(1).where(
                            record_text_value.c.organization_id
                            == catalog_record_revision.c.organization_id,
                            record_text_value.c.project_id == catalog_record_revision.c.project_id,
                            record_text_value.c.record_revision_id == catalog_record_revision.c.id,
                            sa.func.lower(record_text_value.c.value).like(pattern),
                        )
                    ),
                )
            )
        if query.folder_id is not None:
            if not query.include_descendants:
                statement = statement.where(catalog_record_revision.c.folder_id == query.folder_id)
            else:
                # Keep Folder scope in the same SQL set as rows, totals and
                # facets.  The recursive CTE follows exact current Folder
                # revisions and is bounded by the requested Table.
                folder_scope = (
                    sa.select(folder.c.id.label("folder_id"))
                    .where(
                        folder.c.id == query.folder_id,
                        folder.c.table_id == query.table_id,
                    )
                    .cte("record_folder_scope", recursive=True)
                )
                child_folder = folder.alias("child_folder")
                child_revision = folder_revision.alias("child_folder_revision")
                folder_scope = folder_scope.union_all(
                    sa.select(child_folder.c.id)
                    .select_from(
                        child_folder.join(
                            child_revision,
                            sa.and_(
                                child_revision.c.id == child_folder.c.current_revision_id,
                                child_revision.c.aggregate_id == child_folder.c.id,
                                child_revision.c.organization_id == child_folder.c.organization_id,
                                child_revision.c.project_id == child_folder.c.project_id,
                                child_revision.c.classification == child_folder.c.classification,
                            ),
                        ).join(
                            folder_scope,
                            child_revision.c.parent_folder_id == folder_scope.c.folder_id,
                        )
                    )
                    .where(child_folder.c.table_id == query.table_id)
                )
                statement = statement.where(
                    catalog_record_revision.c.folder_id.in_(sa.select(folder_scope.c.folder_id))
                )
        if query.record_id is not None:
            statement = statement.where(catalog_record.c.id == query.record_id)
        if query.domain_binding_kind is not None:
            statement = statement.where(
                sa.exists(
                    sa.select(1).where(
                        domain_record_binding.c.organization_id
                        == catalog_record_revision.c.organization_id,
                        domain_record_binding.c.project_id == catalog_record_revision.c.project_id,
                        domain_record_binding.c.classification
                        == catalog_record_revision.c.classification,
                        domain_record_binding.c.record_id == catalog_record.c.id,
                        domain_record_binding.c.record_revision_id == catalog_record_revision.c.id,
                        domain_record_binding.c.domain_kind == query.domain_binding_kind,
                        *(
                            ()
                            if query.domain_binding_object_id is None
                            else (
                                domain_record_binding.c.domain_object_id
                                == query.domain_binding_object_id,
                                domain_record_binding.c.domain_revision_id
                                == query.domain_binding_revision_id,
                            )
                        ),
                    )
                )
            )
        for discrete_filter in query.discrete_filters:
            discrete_predicates = (
                record_discrete_value.c.organization_id
                == catalog_record_revision.c.organization_id,
                record_discrete_value.c.project_id == catalog_record_revision.c.project_id,
                record_discrete_value.c.record_revision_id == catalog_record_revision.c.id,
                record_discrete_value.c.attribute_definition_id
                == discrete_filter.attribute_definition_id,
                record_discrete_value.c.value.in_(discrete_filter.values),
            )
            text_predicates = (
                record_text_value.c.organization_id == catalog_record_revision.c.organization_id,
                record_text_value.c.project_id == catalog_record_revision.c.project_id,
                record_text_value.c.record_revision_id == catalog_record_revision.c.id,
                record_text_value.c.attribute_definition_id
                == discrete_filter.attribute_definition_id,
                record_text_value.c.value.in_(discrete_filter.values),
            )
            statement = statement.where(
                sa.or_(
                    sa.exists(sa.select(1).where(*discrete_predicates)),
                    sa.exists(sa.select(1).where(*text_predicates)),
                )
            )
        for number_filter in query.number_filters:
            predicates: list[Any] = [
                record_number_value.c.organization_id == catalog_record_revision.c.organization_id,
                record_number_value.c.project_id == catalog_record_revision.c.project_id,
                record_number_value.c.record_revision_id == catalog_record_revision.c.id,
                record_number_value.c.attribute_definition_id
                == number_filter.attribute_definition_id,
            ]
            if number_filter.minimum is not None:
                predicates.append(record_number_value.c.normalized_value >= number_filter.minimum)
            if number_filter.maximum is not None:
                predicates.append(record_number_value.c.normalized_value <= number_filter.maximum)
            statement = statement.where(sa.exists(sa.select(1).where(*predicates)))
        return statement

    def search_records(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: CatalogRecordQuery,
    ) -> RecordSearchResult:
        base = self._filtered_statement(query)
        matched = (
            base.with_only_columns(
                catalog_record_revision.c.organization_id.label("organization_id"),
                catalog_record_revision.c.project_id.label("project_id"),
                catalog_record_revision.c.id.label("record_revision_id"),
            )
            .order_by(None)
            .subquery()
        )
        with self._transaction(context, decision) as session:
            total_count = int(session.scalar(sa.select(sa.func.count()).select_from(matched)) or 0)
            sort_expression: Any
            if query.sort_by == "name":
                sort_expression = catalog_record_revision.c.name
            elif query.sort_by == "external_key":
                sort_expression = sa.func.coalesce(catalog_record_revision.c.external_key, "")
            else:
                assert query.sort_attribute_id is not None
                attribute_predicates = (
                    record_text_value.c.organization_id
                    == catalog_record_revision.c.organization_id,
                    record_text_value.c.project_id == catalog_record_revision.c.project_id,
                    record_text_value.c.record_revision_id == catalog_record_revision.c.id,
                    record_text_value.c.attribute_definition_id == query.sort_attribute_id,
                )
                discrete_predicates = (
                    record_discrete_value.c.organization_id
                    == catalog_record_revision.c.organization_id,
                    record_discrete_value.c.project_id == catalog_record_revision.c.project_id,
                    record_discrete_value.c.record_revision_id == catalog_record_revision.c.id,
                    record_discrete_value.c.attribute_definition_id == query.sort_attribute_id,
                )
                number_predicates = (
                    record_number_value.c.organization_id
                    == catalog_record_revision.c.organization_id,
                    record_number_value.c.project_id == catalog_record_revision.c.project_id,
                    record_number_value.c.record_revision_id == catalog_record_revision.c.id,
                    record_number_value.c.attribute_definition_id == query.sort_attribute_id,
                )
                integer_predicates = (
                    record_integer_value.c.organization_id
                    == catalog_record_revision.c.organization_id,
                    record_integer_value.c.project_id == catalog_record_revision.c.project_id,
                    record_integer_value.c.record_revision_id == catalog_record_revision.c.id,
                    record_integer_value.c.attribute_definition_id == query.sort_attribute_id,
                )
                # Text/discrete values cover Material provider/source and
                # grade facets; numeric values remain available as a numeric
                # first branch for condition-aware properties.
                numeric_sort = sa.func.coalesce(
                    sa.select(record_number_value.c.normalized_value)
                    .where(*number_predicates)
                    .limit(1)
                    .scalar_subquery(),
                    sa.select(record_integer_value.c.value)
                    .where(*integer_predicates)
                    .limit(1)
                    .scalar_subquery(),
                )
                text_sort = sa.func.coalesce(
                    sa.select(record_text_value.c.value)
                    .where(*attribute_predicates)
                    .limit(1)
                    .scalar_subquery(),
                    sa.select(record_discrete_value.c.value)
                    .where(*discrete_predicates)
                    .limit(1)
                    .scalar_subquery(),
                )
                # The two branches keep PostgreSQL from coercing numeric
                # Attributes to text (which would make 10 sort before 2).
                sort_expression = (numeric_sort, text_sort)
            if isinstance(sort_expression, tuple):
                direction = tuple(
                    (
                        item.desc() if query.sort_direction == "descending" else item.asc()
                    ).nulls_last()
                    for item in sort_expression
                )
            else:
                direction = (
                    sort_expression.desc().nulls_last()
                    if query.sort_direction == "descending"
                    else sort_expression.asc().nulls_last(),
                )
            rows = (
                session.execute(
                    base.order_by(*direction, catalog_record.c.id.asc())
                    .offset(query.offset)
                    .limit(query.limit)
                )
                .mappings()
                .all()
            )
            values = self._values_by_revision(session, tuple(row["id"] for row in rows))
            bindings = self._bindings_by_revision(
                session, tuple(row["id"] for row in rows), query.domain_binding_kind
            )
            facets: tuple[RecordFacetBucket, ...] = ()
            if query.facet_attribute_ids:
                facet_values = sa.union_all(
                    sa.select(
                        record_text_value.c.attribute_definition_id.label(
                            "attribute_definition_id"
                        ),
                        record_text_value.c.value.label("value"),
                    )
                    .select_from(
                        record_text_value.join(
                            matched,
                            sa.and_(
                                matched.c.organization_id == record_text_value.c.organization_id,
                                matched.c.project_id == record_text_value.c.project_id,
                                matched.c.record_revision_id
                                == record_text_value.c.record_revision_id,
                            ),
                        )
                    )
                    .where(
                        record_text_value.c.attribute_definition_id.in_(query.facet_attribute_ids)
                    ),
                    sa.select(
                        record_discrete_value.c.attribute_definition_id.label(
                            "attribute_definition_id"
                        ),
                        record_discrete_value.c.value.label("value"),
                    )
                    .select_from(
                        record_discrete_value.join(
                            matched,
                            sa.and_(
                                matched.c.organization_id
                                == record_discrete_value.c.organization_id,
                                matched.c.project_id == record_discrete_value.c.project_id,
                                matched.c.record_revision_id
                                == record_discrete_value.c.record_revision_id,
                            ),
                        )
                    )
                    .where(
                        record_discrete_value.c.attribute_definition_id.in_(
                            query.facet_attribute_ids
                        )
                    ),
                ).subquery("record_facet_values")
                facet_rows = session.execute(
                    sa.select(
                        facet_values.c.attribute_definition_id,
                        facet_values.c.value,
                        sa.func.count().label("bucket_count"),
                    )
                    .select_from(facet_values)
                    .group_by(
                        facet_values.c.attribute_definition_id,
                        facet_values.c.value,
                    )
                    .order_by(
                        facet_values.c.attribute_definition_id.asc(),
                        sa.func.count().desc(),
                        facet_values.c.value.asc(),
                    )
                ).mappings()
                facets = tuple(
                    RecordFacetBucket(
                        row["attribute_definition_id"], row["value"], int(row["bucket_count"])
                    )
                    for row in facet_rows
                )
            return RecordSearchResult(
                tuple(self._record_snapshot(row, values, bindings) for row in rows),
                total_count,
                facets,
            )
