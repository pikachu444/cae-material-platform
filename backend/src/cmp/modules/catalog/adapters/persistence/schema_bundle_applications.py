"""Atomic PostgreSQL apply/export boundary for Catalog Schema Definition Bundles."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from cmp.modules.artifacts.domain.content import (
    ArtifactNotFound,
    ArtifactRecord,
    IntegrityStatus,
)
from cmp.modules.audit.domain.model import (
    AuditActorType,
    AuditEventDraft,
    AuditOutcome,
    AuditScope,
    redact_ip_or_client,
)
from cmp.modules.catalog.adapters.persistence.configurable import (
    _ATTRIBUTES,
    _DATABASES,
    _LAYOUTS,
    _PROFILES,
    _TABLES,
    RlsContext,
    attribute_definition,
    database,
    layout,
    profile,
    publication_marker,
    schema_table,
    table_profile_placement,
)
from cmp.modules.catalog.adapters.persistence.links import _LINK_TYPES, link_type
from cmp.modules.catalog.adapters.persistence.records import (
    catalog_record,
    catalog_record_revision,
    record_boolean_value,
    record_curve_value,
    record_date_value,
    record_discrete_value,
    record_file_value,
    record_integer_value,
    record_number_value,
    record_reference_value,
    record_text_value,
)
from cmp.modules.catalog.adapters.persistence.schema_bundles import (
    SqlAlchemySchemaBundleSnapshotRepository,
)
from cmp.modules.catalog.application.configurable import (
    ATTRIBUTE_AGGREGATE_TYPE,
    ATTRIBUTE_SCHEMA_ID,
    DATABASE_AGGREGATE_TYPE,
    DATABASE_SCHEMA_ID,
    LAYOUT_AGGREGATE_TYPE,
    LAYOUT_SCHEMA_ID,
    PROFILE_AGGREGATE_TYPE,
    PROFILE_SCHEMA_ID,
    SCHEMA_VERSION,
    TABLE_AGGREGATE_TYPE,
    TABLE_SCHEMA_ID,
)
from cmp.modules.catalog.application.links import LINK_TYPE_AGGREGATE_TYPE, LINK_TYPE_SCHEMA_ID
from cmp.modules.catalog.application.schema_bundles import (
    APPLICATION_CONTRACT_VERSION,
    APPLIED_EVENT_SCHEMA,
    APPLIED_EVENT_TYPE,
    AppliedSchemaObject,
    ApplySchemaDefinitionBundle,
    SchemaBundleApplication,
    SchemaBundleApplicationNotFound,
    SchemaBundleExportConflict,
    SchemaBundleExportDescriptor,
    SchemaBundleIdempotencyConflict,
    SchemaBundleMigrationRequired,
    SchemaBundleSourceConflict,
    SchemaBundleStalePlan,
    SchemaBundleVersionConflict,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    AttributeDefinitionContent,
    CatalogDatabaseContent,
    CatalogDataCategory,
    CatalogProfileContent,
    CatalogTableContent,
    LayoutContent,
    LayoutItem,
)
from cmp.modules.catalog.domain.links import LinkCardinality, LinkTypeContent
from cmp.modules.catalog.domain.schema_bundles import (
    BUNDLE_CONTRACT_ID,
    BundleDiagnostic,
    PlanDisposition,
    SchemaBundlePlan,
    SchemaBundlePlanAction,
    SourceArtifactIdentity,
    build_schema_bundle_plan,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.domain.events import CloudEventDraft
from cmp.modules.provenance.domain.model import ProvenanceConflict
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
)
from cmp.shared.domain.revisions import (
    RevisionRecord,
    TenantScope,
    content_sha256,
)

metadata = sa.MetaData()
_uuid = postgresql.UUID(as_uuid=True)

schema_definition_bundle = sa.Table(
    "schema_definition_bundle",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("bundle_key", sa.String(64), nullable=False),
    sa.Column("current_application_id", _uuid, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", _uuid, nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="catalog",
)
schema_definition_bundle_version = sa.Table(
    "schema_definition_bundle_version",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("bundle_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("bundle_version", sa.String(64), nullable=False),
    sa.Column("canonical_bundle_sha256", sa.CHAR(64), nullable=False),
    sa.Column("first_source_artifact_id", _uuid, nullable=False),
    sa.Column("first_source_artifact_sha256", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", _uuid, nullable=False),
    schema="catalog",
)
schema_definition_bundle_application = sa.Table(
    "schema_definition_bundle_application",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("bundle_id", _uuid, nullable=False),
    sa.Column("bundle_version_id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("source_artifact_id", _uuid, nullable=False),
    sa.Column("source_artifact_sha256", sa.CHAR(64), nullable=False),
    sa.Column("plan_fingerprint", sa.CHAR(64), nullable=False),
    sa.Column("before_snapshot_fingerprint", sa.CHAR(64), nullable=False),
    sa.Column("after_snapshot_fingerprint", sa.CHAR(64), nullable=False),
    sa.Column("idempotency_key", sa.String(255), nullable=False),
    sa.Column("request_digest", sa.CHAR(64), nullable=False),
    sa.Column("mutations_applied", sa.Boolean(), nullable=False),
    sa.Column("delete_missing", sa.Boolean(), nullable=False),
    sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("applied_by", _uuid, nullable=False),
    sa.Column("request_id", _uuid, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)
schema_definition_bundle_binding = sa.Table(
    "schema_definition_bundle_binding",
    metadata,
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("application_id", _uuid, nullable=False),
    sa.Column("sequence", sa.Integer(), nullable=False),
    sa.Column("disposition", sa.String(16), nullable=False),
    sa.Column("target_type", sa.String(64), nullable=False),
    sa.Column("external_key", sa.String(255), nullable=False),
    sa.Column("parent_external_key", sa.String(255), nullable=True),
    sa.Column("aggregate_id", _uuid, nullable=True),
    sa.Column("revision_id", _uuid, nullable=True),
    sa.Column("content_hash", sa.CHAR(64), nullable=False),
    sa.Column("published", sa.Boolean(), nullable=False),
    sa.Column("source_schema_id", sa.String(500), nullable=False),
    sa.Column("source_schema_version", sa.String(64), nullable=False),
    sa.Column("source_file", sa.String(1000), nullable=True),
    sa.Column("source_file_sha256", sa.CHAR(64), nullable=True),
    sa.Column("source_pointer", sa.String(2000), nullable=False),
    schema="catalog",
)

_VALUE_TABLES = (
    record_number_value,
    record_integer_value,
    record_text_value,
    record_boolean_value,
    record_date_value,
    record_discrete_value,
    record_file_value,
    record_curve_value,
    record_reference_value,
)
_PUBLISHABLE = {
    "database": (DATABASE_AGGREGATE_TYPE, database),
    "profile": (PROFILE_AGGREGATE_TYPE, profile),
    "table": (TABLE_AGGREGATE_TYPE, schema_table),
    "attribute": (ATTRIBUTE_AGGREGATE_TYPE, attribute_definition),
    "layout": (LAYOUT_AGGREGATE_TYPE, layout),
    "link_type": (LINK_TYPE_AGGREGATE_TYPE, link_type),
}


def _request_digest(command: ApplySchemaDefinitionBundle) -> str:
    return content_sha256(
        {
            "artifact_id": str(command.artifact_id),
            "artifact_sha256": command.expected_sha256,
            "plan_fingerprint": command.plan_fingerprint,
            "delete_missing": command.delete_missing,
        }
    )


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _schema_version(schema_id: str) -> str:
    return schema_id.rsplit(":", 1)[-1]


def _source_coordinates(
    plan: SchemaBundlePlan, action: SchemaBundlePlanAction
) -> tuple[str, str, str | None, str | None, str]:
    bundle = plan.bundle
    if bundle is None:  # pragma: no cover - a valid plan always has a parsed bundle
        raise SchemaBundleSourceConflict("valid apply plan is missing its parsed bundle")
    by_key = {item.key: (index, item) for index, item in enumerate(bundle.record_schemas)}
    record_key: str | None = None
    if action.target_type == "table":
        record_key = action.external_key
    elif action.target_type in {"attribute", "layout"}:
        record_key = action.parent_external_key
    elif action.target_type == "profile_table_placement" and action.projected is not None:
        record_key = cast(str, action.projected["table_key"])
    if record_key is not None and record_key in by_key:
        index, record = by_key[record_key]
        pointer = f"/record_schemas/{index}"
        origin = record.schema.get("x-source-origin")
        if action.target_type == "attribute" and action.projected is not None:
            projected = action.projected
            return (
                cast(str, projected.get("source_schema_id") or record.schema_id),
                cast(
                    str,
                    projected.get("source_schema_version")
                    or _schema_version(record.schema_id),
                ),
                cast(str | None, projected.get("source_file")),
                cast(str | None, projected.get("source_file_sha256")),
                cast(str, projected.get("source_pointer") or pointer),
            )
        if isinstance(origin, dict):
            return (
                cast(str, origin["schema_id"]),
                cast(str, origin["schema_version"]),
                cast(str, origin["file"]),
                cast(str, origin["file_sha256"]),
                cast(str, origin["pointer"]),
            )
        return record.schema_id, _schema_version(record.schema_id), None, None, pointer
    if action.target_type == "link_type":
        for index, record in enumerate(bundle.record_schemas):
            pending: list[tuple[str, object]] = [(f"/record_schemas/{index}/schema", record.schema)]
            while pending:
                pointer, value = pending.pop()
                if isinstance(value, dict):
                    reference = value.get("x-reference")
                    if (
                        isinstance(reference, dict)
                        and reference.get("link_key") == action.external_key
                    ):
                        origin = value.get("x-source-origin")
                        if isinstance(origin, dict):
                            return (
                                cast(str, origin["schema_id"]),
                                cast(str, origin["schema_version"]),
                                cast(str, origin["file"]),
                                cast(str, origin["file_sha256"]),
                                cast(str, origin["pointer"]),
                            )
                        return (
                            record.schema_id,
                            _schema_version(record.schema_id),
                            None,
                            None,
                            pointer,
                        )
                    pending.extend(
                        (f"{pointer}/{_escape_pointer(str(key))}", child)
                        for key, child in value.items()
                    )
                elif isinstance(value, list):
                    pending.extend(
                        (f"{pointer}/{index}", child) for index, child in enumerate(value)
                    )
    pointer = {
        "database": "/catalog/database",
        "profile": "/catalog/profile",
    }.get(action.target_type, "/")
    return BUNDLE_CONTRACT_ID, bundle.bundle_version, None, None, pointer


def _require_actor_type(session: Session) -> AuditActorType:
    principal_type = session.scalar(sa.text("SELECT current_setting('cmp.principal_type', true)"))
    if principal_type not in {"user", "service"}:
        raise ProvenanceConflict("Schema Bundle apply actor type is unavailable")
    return AuditActorType(str(principal_type))


class ArtifactTransactionReader(Protocol):
    def record_in(self, session: Session, artifact_id: UUID) -> ArtifactRecord: ...


class SchemaBundleProvenanceTransactionWriter(Protocol):
    def ensure_source(
        self,
        session: Session,
        *,
        context: SecurityContext,
        classification: DataClassification,
        artifact_id: UUID,
        artifact_sha256: str,
        artifact_created_at: datetime,
        recorded_at: datetime,
    ) -> UUID: ...

    def attach_source(
        self,
        session: Session,
        *,
        source_entity_id: UUID,
        revision: RevisionRecord,
    ) -> None: ...


class AuditTransactionWriter(Protocol):
    def append(self, session: Session, draft: AuditEventDraft) -> object: ...


class OutboxTransactionWriter(Protocol):
    def append(
        self,
        session: Session,
        draft: CloudEventDraft,
        *,
        recorded_at: datetime,
    ) -> object: ...


class SqlAlchemySchemaBundleApplicationRepository:
    """Re-plan and apply a bundle inside one locked, RLS-bound transaction."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: RlsContext,
        snapshots: SqlAlchemySchemaBundleSnapshotRepository,
        artifacts: ArtifactTransactionReader,
        provenance: SchemaBundleProvenanceTransactionWriter,
        audit: AuditTransactionWriter,
        outbox: OutboxTransactionWriter,
        revision_hooks: Sequence[SqlRevisionHook] = (),
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
        failure_injector: Callable[[int], None] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._snapshots = snapshots
        self._artifacts = artifacts
        self._provenance = provenance
        self._audit = audit
        self._outbox = outbox
        self._hooks = tuple(revision_hooks)
        self._id = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._failure_injector = failure_injector

    @staticmethod
    def _lock_project(session: Session, context: SecurityContext) -> None:
        session.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": f"catalog.schema-bundle:{context.organization_id}:{context.project_id}"},
        )
        session.execute(
            sa.text(
                "LOCK TABLE "
                "catalog.database, catalog.database_revision, "
                "catalog.profile, catalog.profile_revision, "
                "catalog.schema_table, catalog.schema_table_revision, "
                "catalog.attribute_definition, catalog.attribute_definition_revision, "
                "catalog.layout, catalog.layout_revision, catalog.layout_item, "
                "catalog.table_profile_placement, catalog.link_type, catalog.link_type_revision, "
                "catalog.publication_marker, catalog.catalog_record, "
                "catalog.catalog_record_revision, catalog.record_number_value, "
                "catalog.record_integer_value, catalog.record_text_value, "
                "catalog.record_boolean_value, catalog.record_date_value, "
                "catalog.record_discrete_value, catalog.record_file_value, "
                "catalog.record_curve_value, catalog.record_reference_value, "
                "catalog.schema_definition_bundle, catalog.schema_definition_bundle_version, "
                "catalog.schema_definition_bundle_application, "
                "catalog.schema_definition_bundle_binding, artifact.artifact, "
                "artifact.integrity_projection IN SHARE ROW EXCLUSIVE MODE"
            )
        )

    def _locked_artifact(
        self,
        session: Session,
        context: SecurityContext,
        source: SourceArtifactIdentity,
    ) -> ArtifactRecord:
        try:
            record = self._artifacts.record_in(session, source.artifact_id)
        except ArtifactNotFound as error:
            raise SchemaBundleSourceConflict(
                "Artifact identity, checksum, tenant, or verification state changed before apply"
            ) from error
        artifact = record.artifact
        observed = (
            artifact.id,
            artifact.organization_id,
            artifact.project_id,
            artifact.classification.value,
            artifact.media_type,
            artifact.size_bytes,
            artifact.sha256,
            record.integrity_status.value,
        )
        expected = (
            source.artifact_id,
            source.organization_id,
            source.project_id,
            source.classification.value,
            source.media_type,
            source.size_bytes,
            source.sha256,
            IntegrityStatus.VERIFIED.value,
        )
        if observed != expected:
            raise SchemaBundleSourceConflict(
                "Artifact identity, checksum, tenant, or verification state changed before apply"
            )
        return record

    def _store[ContentT](
        self, tables: TypedRevisionTables[ContentT]
    ) -> SqlAlchemyRevisionStore[ContentT]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=tables,
            hooks=self._hooks,
        )

    def _write_revision[ContentT](
        self,
        *,
        session: Session,
        action: SchemaBundlePlanAction,
        aggregate_type: str,
        tables: TypedRevisionTables[ContentT],
        schema_id: str,
        content: ContentT,
        scope: TenantScope,
        context: SecurityContext,
    ) -> RevisionRecord:
        store = self._store(tables)
        service = RevisionService(
            aggregate_type=aggregate_type,
            store=store,
            id_factory=self._id,
            clock=self._clock,
        )
        transaction = store.transaction_in(session)
        reason = (
            "Apply Schema Definition Bundle projection "
            f"for {action.target_type}:{action.external_key}"
        )
        if action.disposition is PlanDisposition.CREATE:
            return service.create_in(
                transaction,
                CreateRevisionedAggregate(
                    aggregate_id=self._id(),
                    scope=scope,
                    schema_id=schema_id,
                    schema_version=SCHEMA_VERSION,
                    content=content,
                    created_by=context.principal.id,
                    change_reason=reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                ),
            )
        if action.disposition is not PlanDisposition.UPDATE or action.current is None:
            raise SchemaBundleSourceConflict("apply attempted a non-revision plan action")
        if action.current.object_id is None or action.current.revision_id is None:
            raise SchemaBundleSourceConflict("update plan action is missing its exact current head")
        return service.revise_in(
            transaction,
            ReviseAggregate(
                aggregate_id=action.current.object_id,
                scope=scope,
                expected_current_revision_id=action.current.revision_id,
                based_on_revision_id=action.current.revision_id,
                schema_id=schema_id,
                schema_version=SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            ),
        )

    @staticmethod
    def _resolved(
        resolved: Mapping[tuple[str, str | None, str], tuple[UUID | None, UUID | None, str]],
        target_type: str,
        parent_external_key: str | None,
        external_key: str,
    ) -> tuple[UUID, UUID, str]:
        value = resolved.get((target_type, parent_external_key, external_key))
        if value is None or value[0] is None or value[1] is None:
            raise SchemaBundleSourceConflict(
                f"projected dependency is unresolved: {target_type}:{external_key}"
            )
        return value[0], value[1], value[2]

    def _content(
        self,
        action: SchemaBundlePlanAction,
        resolved: Mapping[tuple[str, str | None, str], tuple[UUID | None, UUID | None, str]],
    ) -> object:
        projected = action.projected
        if projected is None:
            raise SchemaBundleSourceConflict("valid action is missing server projection")
        if action.target_type == "database":
            return CatalogDatabaseContent(
                cast(str, projected["key"]),
                cast(str, projected["name"]),
                cast(str | None, projected["description"]),
            )
        if action.target_type == "profile":
            database_id, database_revision_id, _ = self._resolved(
                resolved, "database", None, cast(str, projected["database_key"])
            )
            return CatalogProfileContent(
                database_id,
                database_revision_id,
                cast(str, projected["key"]),
                cast(str, projected["name"]),
                cast(str | None, projected["description"]),
            )
        if action.target_type == "table":
            category = cast(str | None, projected.get("data_category"))
            return CatalogTableContent(
                cast(str, projected["key"]),
                cast(str, projected["name"]),
                cast(str | None, projected["description"]),
                CatalogDataCategory(category) if category is not None else None,
            )
        if action.target_type == "attribute":
            assert action.parent_external_key is not None
            table_id, table_revision_id, _ = self._resolved(
                resolved, "table", None, action.parent_external_key
            )
            reference_key = cast(str | None, projected["reference_table_key"])
            reference_id = (
                self._resolved(resolved, "table", None, reference_key)[0]
                if reference_key is not None
                else None
            )
            return AttributeDefinitionContent(
                table_id=table_id,
                table_revision_id=table_revision_id,
                key=cast(str, projected["key"]),
                name=cast(str, projected["name"]),
                data_type=AttributeDataType(cast(str, projected["data_type"])),
                required=cast(bool, projected["required"]),
                quantity_semantics=cast(str | None, projected["quantity_semantics"]),
                normalized_unit=cast(str | None, projected["normalized_unit"]),
                minimum_number=cast(float | None, projected["minimum_number"]),
                maximum_number=cast(float | None, projected["maximum_number"]),
                minimum_length=cast(int | None, projected["minimum_length"]),
                maximum_length=cast(int | None, projected["maximum_length"]),
                pattern=cast(str | None, projected["pattern"]),
                allowed_values=tuple(cast(list[str], projected["allowed_values"])),
                reference_table_id=reference_id,
                help_text=cast(str | None, projected["help_text"]),
                business_key=projected.get("business_key") is True,
            )
        if action.target_type == "layout":
            assert action.parent_external_key is not None
            table_id, table_revision_id, _ = self._resolved(
                resolved, "table", None, action.parent_external_key
            )
            items = tuple(
                LayoutItem(
                    *self._resolved(
                        resolved,
                        "attribute",
                        action.parent_external_key,
                        cast(str, item["attribute_key"]),
                    )[:2],
                    cast(str, item["section"]),
                    cast(int, item["ordinal"]),
                )
                for item in cast(list[dict[str, object]], projected["items"])
            )
            return LayoutContent(
                table_id,
                table_revision_id,
                cast(str, projected["name"]),
                cast(str | None, projected["description"]),
                items,
            )
        if action.target_type == "link_type":
            source_id, source_revision_id, _ = self._resolved(
                resolved, "table", None, cast(str, projected["source_table_key"])
            )
            target_id, target_revision_id, _ = self._resolved(
                resolved, "table", None, cast(str, projected["target_table_key"])
            )
            return LinkTypeContent(
                key=cast(str, projected["key"]),
                name=cast(str, projected["name"]),
                source_table_id=source_id,
                source_table_revision_id=source_revision_id,
                target_table_id=target_id,
                target_table_revision_id=target_revision_id,
                forward_label=cast(str, projected["forward_label"]),
                reverse_label=cast(str, projected["reverse_label"]),
                source_cardinality=LinkCardinality(cast(str, projected["source_cardinality"])),
                target_cardinality=LinkCardinality(cast(str, projected["target_cardinality"])),
                description=cast(str | None, projected["description"]),
            )
        raise SchemaBundleSourceConflict(f"unsupported apply target type: {action.target_type}")

    @staticmethod
    def _current_record_count(session: Session, table_id: UUID) -> int:
        return int(
            session.scalar(
                sa.select(sa.func.count())
                .select_from(
                    catalog_record.join(
                        catalog_record_revision,
                        sa.and_(
                            catalog_record_revision.c.id == catalog_record.c.current_revision_id,
                            catalog_record_revision.c.aggregate_id == catalog_record.c.id,
                            catalog_record_revision.c.organization_id
                            == catalog_record.c.organization_id,
                            catalog_record_revision.c.project_id == catalog_record.c.project_id,
                        ),
                    )
                )
                .where(catalog_record_revision.c.table_id == table_id)
            )
            or 0
        )

    @staticmethod
    def _current_attribute_value_count(
        session: Session,
        attribute_id: UUID,
    ) -> int:
        count = 0
        for value_table in _VALUE_TABLES:
            count += int(
                session.scalar(
                    sa.select(sa.func.count())
                    .select_from(
                        value_table.join(
                            catalog_record,
                            sa.and_(
                                catalog_record.c.id == value_table.c.record_id,
                                catalog_record.c.organization_id == value_table.c.organization_id,
                                catalog_record.c.project_id == value_table.c.project_id,
                                catalog_record.c.current_revision_id
                                == value_table.c.record_revision_id,
                            ),
                        )
                    )
                    .where(value_table.c.attribute_definition_id == attribute_id)
                )
                or 0
            )
        return count

    def _require_record_compatibility(
        self,
        session: Session,
        plan: SchemaBundlePlan,
    ) -> None:
        current_tables = {
            (item.external_key): item
            for item in plan.actions
            if item.target_type == "table" and item.current is not None
        }
        for action in plan.actions:
            if action.disposition not in {PlanDisposition.CREATE, PlanDisposition.UPDATE}:
                continue
            if action.target_type == "table" and action.disposition is PlanDisposition.UPDATE:
                assert action.current is not None and action.current.object_id is not None
                if self._current_record_count(session, action.current.object_id):
                    raise SchemaBundleMigrationRequired(
                        f"Table '{action.external_key}' has current Records "
                        "that pin its old revision"
                    )
            if action.target_type != "attribute":
                continue
            if action.disposition is PlanDisposition.UPDATE:
                assert action.current is not None and action.current.object_id is not None
                if self._current_attribute_value_count(session, action.current.object_id):
                    raise SchemaBundleMigrationRequired(
                        f"Attribute '{action.external_key}' has current values "
                        "pinned to its old revision"
                    )
            if (
                action.disposition is PlanDisposition.CREATE
                and action.projected is not None
                and action.projected.get("required") is True
                and action.parent_external_key in current_tables
            ):
                table = current_tables[action.parent_external_key]
                assert table.current is not None and table.current.object_id is not None
                if self._current_record_count(session, table.current.object_id):
                    raise SchemaBundleMigrationRequired(
                        f"Required Attribute '{action.external_key}' is missing "
                        "from current Records"
                    )

    @staticmethod
    def _application_statement() -> sa.Select[Any]:
        application = schema_definition_bundle_application
        bundle = schema_definition_bundle
        version = schema_definition_bundle_version
        return sa.select(
            application,
            bundle.c.bundle_key,
            version.c.bundle_version,
            version.c.canonical_bundle_sha256,
        ).select_from(
            application.join(
                bundle,
                sa.and_(
                    bundle.c.id == application.c.bundle_id,
                    bundle.c.organization_id == application.c.organization_id,
                    bundle.c.project_id == application.c.project_id,
                ),
            ).join(
                version,
                sa.and_(
                    version.c.id == application.c.bundle_version_id,
                    version.c.bundle_id == bundle.c.id,
                    version.c.organization_id == application.c.organization_id,
                    version.c.project_id == application.c.project_id,
                ),
            )
        )

    @staticmethod
    def _application_from_rows(
        row: RowMapping,
        source: SourceArtifactIdentity,
        bindings: Sequence[RowMapping],
        *,
        replayed: bool = False,
    ) -> SchemaBundleApplication:
        results = tuple(
            AppliedSchemaObject(
                sequence=cast(int, binding["sequence"]),
                disposition=PlanDisposition(cast(str, binding["disposition"])),
                target_type=cast(str, binding["target_type"]),
                external_key=cast(str, binding["external_key"]),
                parent_external_key=cast(str | None, binding["parent_external_key"]),
                aggregate_id=cast(UUID | None, binding["aggregate_id"]),
                revision_id=cast(UUID | None, binding["revision_id"]),
                content_hash=cast(str, binding["content_hash"]),
                published=cast(bool, binding["published"]),
                source_schema_id=cast(str, binding["source_schema_id"]),
                source_schema_version=cast(str, binding["source_schema_version"]),
                source_file=cast(str | None, binding["source_file"]),
                source_file_sha256=cast(str | None, binding["source_file_sha256"]),
                source_pointer=cast(str, binding["source_pointer"]),
            )
            for binding in bindings
        )
        return SchemaBundleApplication(
            application_id=cast(UUID, row["id"]),
            bundle_id=cast(UUID, row["bundle_id"]),
            bundle_key=cast(str, row["bundle_key"]),
            bundle_version=cast(str, row["bundle_version"]),
            classification=cast(str, row["classification"]),
            source_artifact=source,
            plan_fingerprint=cast(str, row["plan_fingerprint"]),
            before_snapshot_fingerprint=cast(str, row["before_snapshot_fingerprint"]),
            after_snapshot_fingerprint=cast(str, row["after_snapshot_fingerprint"]),
            results=results,
            mutations_applied=cast(bool, row["mutations_applied"]),
            applied_at=cast(datetime, row["applied_at"]),
            applied_by=cast(UUID, row["applied_by"]),
            idempotency_key=cast(str, row["idempotency_key"]),
            replayed=replayed,
        )

    def _load_application(
        self,
        session: Session,
        *,
        context: SecurityContext,
        application_id: UUID | None = None,
        idempotency_key: str | None = None,
        replayed: bool = False,
    ) -> tuple[SchemaBundleApplication, str, str]:
        statement = self._application_statement().where(
            schema_definition_bundle_application.c.organization_id == context.organization_id,
            schema_definition_bundle_application.c.project_id == context.project_id,
        )
        if application_id is not None:
            statement = statement.where(schema_definition_bundle_application.c.id == application_id)
        elif idempotency_key is not None:
            statement = statement.where(
                schema_definition_bundle_application.c.idempotency_key == idempotency_key
            )
        else:  # pragma: no cover - internal guard
            raise ValueError("application lookup requires an id or idempotency key")
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise SchemaBundleApplicationNotFound("Schema Bundle application was not found")
        try:
            artifact_record = self._artifacts.record_in(
                session, cast(UUID, row["source_artifact_id"])
            )
        except ArtifactNotFound as error:
            raise SchemaBundleSourceConflict("applied source Artifact is unavailable") from error
        artifact = artifact_record.artifact
        expected_source = (
            cast(UUID, row["source_artifact_id"]),
            cast(UUID, row["organization_id"]),
            cast(UUID, row["project_id"]),
            cast(str, row["classification"]),
            cast(str, row["source_artifact_sha256"]),
        )
        observed_source = (
            artifact.id,
            artifact.organization_id,
            artifact.project_id,
            artifact.classification.value,
            artifact.sha256,
        )
        if observed_source != expected_source:
            raise SchemaBundleSourceConflict(
                "applied source Artifact identity no longer matches its application"
            )
        source = SourceArtifactIdentity(
            artifact.id,
            artifact.organization_id,
            artifact.project_id,
            artifact.classification,
            artifact.media_type,
            artifact.size_bytes,
            artifact.sha256,
        )
        bindings = session.execute(
            sa.select(schema_definition_bundle_binding)
            .where(
                schema_definition_bundle_binding.c.organization_id == context.organization_id,
                schema_definition_bundle_binding.c.project_id == context.project_id,
                schema_definition_bundle_binding.c.application_id == row["id"],
            )
            .order_by(schema_definition_bundle_binding.c.sequence)
        ).mappings()
        return (
            self._application_from_rows(row, source, list(bindings), replayed=replayed),
            cast(str, row["request_digest"]),
            cast(str, row["canonical_bundle_sha256"]),
        )

    def _publish(
        self,
        session: Session,
        *,
        context: SecurityContext,
        classification: DataClassification,
        target_type: str,
        aggregate_id: UUID,
        revision_id: UUID,
        recorded_at: datetime,
    ) -> bool:
        aggregate_type, _ = _PUBLISHABLE[target_type]
        inserted = session.execute(
            postgresql.insert(publication_marker)
            .values(
                organization_id=context.organization_id,
                project_id=context.project_id,
                classification=classification.value,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                revision_id=revision_id,
                published_at=recorded_at,
                published_by=context.principal.id,
            )
            .on_conflict_do_nothing()
        )
        return getattr(inserted, "rowcount", 0) == 1

    def _write_action(
        self,
        session: Session,
        *,
        context: SecurityContext,
        plan: SchemaBundlePlan,
        action: SchemaBundlePlanAction,
        resolved: dict[tuple[str, str | None, str], tuple[UUID | None, UUID | None, str]],
        source_entity_id: UUID,
        recorded_at: datetime,
    ) -> tuple[AppliedSchemaObject, bool]:
        bundle = plan.bundle
        assert bundle is not None
        source_schema_id, source_version, source_file, source_file_sha256, source_pointer = (
            _source_coordinates(plan, action)
        )
        key = (action.target_type, action.parent_external_key, action.external_key)
        if action.disposition is PlanDisposition.NO_OP:
            if action.current is None:
                raise SchemaBundleSourceConflict(
                    "no-op plan action is missing its current identity"
                )
            aggregate_id = action.current.object_id
            revision_id = action.current.revision_id
            content_hash = action.current.content_hash
            published = action.current.published
            publication_added = False
            if action.target_type in _PUBLISHABLE:
                if aggregate_id is None or revision_id is None:
                    raise SchemaBundleSourceConflict(
                        "publishable no-op action is not revision-pinned"
                    )
                publication_added = self._publish(
                    session,
                    context=context,
                    classification=bundle.scope.classification,
                    target_type=action.target_type,
                    aggregate_id=aggregate_id,
                    revision_id=revision_id,
                    recorded_at=recorded_at,
                )
                published = True
            resolved[key] = (aggregate_id, revision_id, content_hash)
            return (
                AppliedSchemaObject(
                    action.sequence,
                    action.disposition,
                    action.target_type,
                    action.external_key,
                    action.parent_external_key,
                    aggregate_id,
                    revision_id,
                    content_hash,
                    published,
                    source_schema_id,
                    source_version,
                    source_file,
                    source_file_sha256,
                    source_pointer,
                ),
                publication_added,
            )
        if action.target_type == "profile_table_placement":
            if action.projected is None:
                raise SchemaBundleSourceConflict("placement projection is missing")
            profile_id, profile_revision_id, _ = self._resolved(
                resolved,
                "profile",
                bundle.database.key,
                cast(str, action.projected["profile_key"]),
            )
            table_id, table_revision_id, _ = self._resolved(
                resolved, "table", None, cast(str, action.projected["table_key"])
            )
            inserted = session.execute(
                postgresql.insert(table_profile_placement)
                .values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=bundle.scope.classification.value,
                    table_id=table_id,
                    table_revision_id=table_revision_id,
                    profile_id=profile_id,
                    profile_revision_id=profile_revision_id,
                    created_at=recorded_at,
                    created_by=context.principal.id,
                )
                .on_conflict_do_nothing()
            )
            content_hash = content_sha256(action.projected)
            resolved[key] = (None, None, content_hash)
            return (
                AppliedSchemaObject(
                    action.sequence,
                    action.disposition,
                    action.target_type,
                    action.external_key,
                    action.parent_external_key,
                    None,
                    None,
                    content_hash,
                    False,
                    source_schema_id,
                    source_version,
                    source_file,
                    source_file_sha256,
                    source_pointer,
                ),
                getattr(inserted, "rowcount", 0) == 1,
            )
        content = self._content(action, resolved)
        bindings: dict[str, tuple[str, TypedRevisionTables[Any], str]] = {
            "database": (DATABASE_AGGREGATE_TYPE, _DATABASES, DATABASE_SCHEMA_ID),
            "profile": (PROFILE_AGGREGATE_TYPE, _PROFILES, PROFILE_SCHEMA_ID),
            "table": (TABLE_AGGREGATE_TYPE, _TABLES, TABLE_SCHEMA_ID),
            "attribute": (ATTRIBUTE_AGGREGATE_TYPE, _ATTRIBUTES, ATTRIBUTE_SCHEMA_ID),
            "layout": (LAYOUT_AGGREGATE_TYPE, _LAYOUTS, LAYOUT_SCHEMA_ID),
            "link_type": (LINK_TYPE_AGGREGATE_TYPE, _LINK_TYPES, LINK_TYPE_SCHEMA_ID),
        }
        aggregate_type, tables, schema_id = bindings[action.target_type]
        revision = self._write_revision(
            session=session,
            action=action,
            aggregate_type=aggregate_type,
            tables=tables,
            schema_id=schema_id,
            content=content,
            scope=TenantScope(
                context.organization_id,
                context.project_id,
                bundle.scope.classification.value,
            ),
            context=context,
        )
        self._provenance.attach_source(
            session,
            source_entity_id=source_entity_id,
            revision=revision,
        )
        self._publish(
            session,
            context=context,
            classification=bundle.scope.classification,
            target_type=action.target_type,
            aggregate_id=revision.aggregate_id,
            revision_id=revision.revision_id,
            recorded_at=recorded_at,
        )
        resolved[key] = (revision.aggregate_id, revision.revision_id, revision.content_hash)
        return (
            AppliedSchemaObject(
                action.sequence,
                action.disposition,
                action.target_type,
                action.external_key,
                action.parent_external_key,
                revision.aggregate_id,
                revision.revision_id,
                revision.content_hash,
                True,
                source_schema_id,
                source_version,
                source_file,
                source_file_sha256,
                source_pointer,
            ),
            True,
        )

    def apply(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ApplySchemaDefinitionBundle,
        source: SourceArtifactIdentity,
        raw_bytes: bytes | None,
        source_diagnostics: tuple[BundleDiagnostic, ...] = (),
    ) -> SchemaBundleApplication:
        request_digest = _request_digest(command)
        with self._sessions() as session, session.begin():
            session.execute(sa.text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            self._lock_project(session, context)
            self._rls.bind_authorization(session, context, decision)
            artifact_record = self._locked_artifact(session, context, source)
            existing = session.scalar(
                sa.select(schema_definition_bundle_application.c.id).where(
                    schema_definition_bundle_application.c.organization_id
                    == context.organization_id,
                    schema_definition_bundle_application.c.project_id == context.project_id,
                    schema_definition_bundle_application.c.idempotency_key
                    == command.idempotency_key,
                )
            )
            if existing is not None:
                application, stored_digest, _ = self._load_application(
                    session,
                    context=context,
                    application_id=cast(UUID, existing),
                    replayed=True,
                )
                if stored_digest != request_digest:
                    raise SchemaBundleIdempotencyConflict(
                        "idempotency key was reused with different apply evidence"
                    )
                return application

            before = self._snapshots.read_snapshot(
                context=context,
                decision=decision,
                session=session,
            )
            plan = build_schema_bundle_plan(
                source=source,
                raw_bytes=raw_bytes,
                snapshot=before,
                organization_id=context.organization_id,
                project_id=context.project_id,
                classification_allowed=lambda classification: decision.allows(
                    context.organization_id,
                    context.project_id,
                    classification,
                ),
                source_diagnostics=source_diagnostics,
            )
            if any("record_migration_required" in action.reason_codes for action in plan.actions):
                raise SchemaBundleMigrationRequired(
                    "current Records require an approved migration before this bundle can apply"
                )
            if not plan.valid or plan.bundle is None:
                raise SchemaBundleSourceConflict(
                    "server re-plan is invalid against the locked current Catalog snapshot"
                )
            if plan.plan_fingerprint != command.plan_fingerprint:
                raise SchemaBundleStalePlan(
                    "approved plan_fingerprint differs from the server re-plan"
                )
            self._require_record_compatibility(session, plan)
            bundle = plan.bundle
            assert raw_bytes is not None
            canonical_document = json.loads(raw_bytes)
            canonical_bundle_sha256 = content_sha256(canonical_document)
            now = self._clock()

            bundle_row = (
                session.execute(
                    sa.select(schema_definition_bundle)
                    .where(
                        schema_definition_bundle.c.organization_id == context.organization_id,
                        schema_definition_bundle.c.project_id == context.project_id,
                        schema_definition_bundle.c.bundle_key == bundle.bundle_key,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if bundle_row is None:
                bundle_id = self._id()
                session.execute(
                    sa.insert(schema_definition_bundle).values(
                        id=bundle_id,
                        organization_id=context.organization_id,
                        project_id=context.project_id,
                        classification=bundle.scope.classification.value,
                        bundle_key=bundle.bundle_key,
                        current_application_id=None,
                        created_at=now,
                        created_by=context.principal.id,
                        updated_at=now,
                    )
                )
            else:
                bundle_id = cast(UUID, bundle_row["id"])
                if bundle_row["classification"] != bundle.scope.classification.value:
                    raise SchemaBundleVersionConflict(
                        "bundle stable identity cannot change classification"
                    )

            version_row = (
                session.execute(
                    sa.select(schema_definition_bundle_version)
                    .where(
                        schema_definition_bundle_version.c.organization_id
                        == context.organization_id,
                        schema_definition_bundle_version.c.project_id == context.project_id,
                        schema_definition_bundle_version.c.bundle_id == bundle_id,
                        schema_definition_bundle_version.c.bundle_version == bundle.bundle_version,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if version_row is None:
                version_id = self._id()
                session.execute(
                    sa.insert(schema_definition_bundle_version).values(
                        id=version_id,
                        bundle_id=bundle_id,
                        organization_id=context.organization_id,
                        project_id=context.project_id,
                        classification=bundle.scope.classification.value,
                        bundle_version=bundle.bundle_version,
                        canonical_bundle_sha256=canonical_bundle_sha256,
                        first_source_artifact_id=source.artifact_id,
                        first_source_artifact_sha256=source.sha256,
                        created_at=now,
                        created_by=context.principal.id,
                    )
                )
            else:
                version_id = cast(UUID, version_row["id"])
                if version_row["canonical_bundle_sha256"] != canonical_bundle_sha256:
                    raise SchemaBundleVersionConflict(
                        "bundle_version already identifies different canonical bundle content"
                    )

            source_entity_id = self._provenance.ensure_source(
                session,
                context=context,
                classification=source.classification,
                artifact_id=source.artifact_id,
                artifact_sha256=source.sha256,
                artifact_created_at=artifact_record.artifact.created_at,
                recorded_at=now,
            )
            resolved: dict[tuple[str, str | None, str], tuple[UUID | None, UUID | None, str]] = {}
            results: list[AppliedSchemaObject] = []
            mutations_applied = False
            for action in plan.actions:
                if action.disposition not in {
                    PlanDisposition.CREATE,
                    PlanDisposition.UPDATE,
                    PlanDisposition.NO_OP,
                }:
                    raise SchemaBundleSourceConflict("server plan contains a non-applicable action")
                result, mutated = self._write_action(
                    session,
                    context=context,
                    plan=plan,
                    action=action,
                    resolved=resolved,
                    source_entity_id=source_entity_id,
                    recorded_at=now,
                )
                results.append(result)
                mutations_applied = mutations_applied or mutated
                if self._failure_injector is not None:
                    self._failure_injector(action.sequence)

            layout_keys = {
                result.aggregate_id: result.external_key
                for result in results
                if result.target_type == "layout" and result.aggregate_id is not None
            }
            after = self._snapshots.read_snapshot(
                context=context,
                decision=decision,
                session=session,
                layout_external_keys=layout_keys,
            )
            application_id = self._id()
            session.execute(
                sa.insert(schema_definition_bundle_application).values(
                    id=application_id,
                    bundle_id=bundle_id,
                    bundle_version_id=version_id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=bundle.scope.classification.value,
                    source_artifact_id=source.artifact_id,
                    source_artifact_sha256=source.sha256,
                    plan_fingerprint=plan.plan_fingerprint,
                    before_snapshot_fingerprint=before.fingerprint,
                    after_snapshot_fingerprint=after.fingerprint,
                    idempotency_key=command.idempotency_key,
                    request_digest=request_digest,
                    mutations_applied=mutations_applied,
                    delete_missing=False,
                    applied_at=now,
                    applied_by=context.principal.id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            session.execute(
                sa.insert(schema_definition_bundle_binding),
                [
                    {
                        "organization_id": context.organization_id,
                        "project_id": context.project_id,
                        "classification": bundle.scope.classification.value,
                        "application_id": application_id,
                        **result.canonical(),
                    }
                    for result in results
                ],
            )
            session.execute(
                sa.update(schema_definition_bundle)
                .where(
                    schema_definition_bundle.c.organization_id == context.organization_id,
                    schema_definition_bundle.c.project_id == context.project_id,
                    schema_definition_bundle.c.id == bundle_id,
                )
                .values(current_application_id=application_id, updated_at=now)
            )

            application = SchemaBundleApplication(
                application_id=application_id,
                bundle_id=bundle_id,
                bundle_key=bundle.bundle_key,
                bundle_version=bundle.bundle_version,
                classification=bundle.scope.classification.value,
                source_artifact=source,
                plan_fingerprint=plan.plan_fingerprint,
                before_snapshot_fingerprint=before.fingerprint,
                after_snapshot_fingerprint=after.fingerprint,
                results=tuple(results),
                mutations_applied=mutations_applied,
                applied_at=now,
                applied_by=context.principal.id,
                idempotency_key=command.idempotency_key,
            )
            actor_type = _require_actor_type(session)
            self._audit.append(
                session,
                AuditEventDraft(
                    id=self._id(),
                    scope=AuditScope(context.organization_id, context.project_id),
                    occurred_at=now,
                    actor_type=actor_type,
                    actor_id=context.principal.id,
                    action="catalog.schema_definition_bundle.apply",
                    target_type="catalog.schema_definition_bundle",
                    target_id=bundle_id,
                    outcome=AuditOutcome.SUCCESS,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                    ip_or_client=redact_ip_or_client(None),
                    reason=(
                        "Apply approved plan_fingerprint "
                        f"{plan.plan_fingerprint} from Artifact {source.artifact_id}"
                    ),
                ),
            )
            event_data = {
                "contract_version": APPLICATION_CONTRACT_VERSION,
                "application_id": str(application_id),
                "bundle_id": str(bundle_id),
                "bundle_key": bundle.bundle_key,
                "bundle_version": bundle.bundle_version,
                "source_artifact_id": str(source.artifact_id),
                "source_artifact_sha256": source.sha256,
                "plan_fingerprint": plan.plan_fingerprint,
                "before_snapshot_fingerprint": before.fingerprint,
                "after_snapshot_fingerprint": after.fingerprint,
                "mutations_applied": mutations_applied,
                "delete_missing": False,
            }
            self._outbox.append(
                session,
                CloudEventDraft(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=bundle.scope.classification,
                    aggregate_type="catalog.schema_definition_bundle",
                    aggregate_id=bundle_id,
                    event_type=APPLIED_EVENT_TYPE,
                    source="https://cmp.example/catalog/schema-definition-bundles",
                    subject=f"schema-definition-bundle/{bundle_id}/applications/{application_id}",
                    data_schema=APPLIED_EVENT_SCHEMA,
                    data=event_data,
                    occurred_at=now,
                    recorded_by=context.principal.id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                    deduplication_key=f"schema-bundle-apply:{application_id}",
                ),
                recorded_at=now,
            )
            return application

    def get_application(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        application_id: UUID,
    ) -> SchemaBundleApplication:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            application, _, _ = self._load_application(
                session,
                context=context,
                application_id=application_id,
            )
            return application

    def resolve_export(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        bundle_key: str,
    ) -> SchemaBundleExportDescriptor:
        with self._sessions() as session, session.begin():
            session.execute(sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            self._rls.bind_authorization(session, context, decision)
            application_id = session.scalar(
                sa.select(schema_definition_bundle.c.current_application_id).where(
                    schema_definition_bundle.c.organization_id == context.organization_id,
                    schema_definition_bundle.c.project_id == context.project_id,
                    schema_definition_bundle.c.bundle_key == bundle_key,
                )
            )
            if application_id is None:
                raise SchemaBundleApplicationNotFound("Schema Bundle was not found")
            application, _, canonical_digest = self._load_application(
                session,
                context=context,
                application_id=cast(UUID, application_id),
            )
            snapshot = self._snapshots.read_snapshot(
                context=context,
                decision=decision,
                session=session,
            )
            current = {item.key(): item for item in snapshot.objects}
            for result in application.results:
                item = current.get(
                    (result.target_type, result.parent_external_key, result.external_key)
                )
                if item is None:
                    raise SchemaBundleExportConflict(
                        f"applied target is absent: {result.target_type}:{result.external_key}"
                    )
                if (
                    item.object_id != result.aggregate_id
                    or item.revision_id != result.revision_id
                    or item.content_hash != result.content_hash
                    or item.published != result.published
                ):
                    raise SchemaBundleExportConflict(
                        f"applied target drifted: {result.target_type}:{result.external_key}"
                    )
            return SchemaBundleExportDescriptor(application, canonical_digest)


__all__ = [
    "SqlAlchemySchemaBundleApplicationRepository",
    "schema_definition_bundle",
    "schema_definition_bundle_application",
    "schema_definition_bundle_binding",
    "schema_definition_bundle_version",
]
