"""Coherent PostgreSQL read-only snapshot for Schema Definition Bundle planning."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cmp.modules.catalog.adapters.persistence.configurable import (
    RlsContext,
    attribute_definition,
    attribute_definition_revision,
    database,
    database_revision,
    layout,
    layout_item,
    layout_revision,
    profile,
    profile_revision,
    publication_marker,
    schema_table,
    schema_table_revision,
    table_profile_placement,
)
from cmp.modules.catalog.adapters.persistence.links import link_type, link_type_revision
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
from cmp.modules.catalog.application.configurable import (
    ATTRIBUTE_AGGREGATE_TYPE,
    DATABASE_AGGREGATE_TYPE,
    LAYOUT_AGGREGATE_TYPE,
    PROFILE_AGGREGATE_TYPE,
    TABLE_AGGREGATE_TYPE,
)
from cmp.modules.catalog.application.links import LINK_TYPE_AGGREGATE_TYPE
from cmp.modules.catalog.domain.schema_bundles import CatalogSnapshot, CatalogStateObject
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.domain.revisions import content_sha256

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


def _published(
    markers: frozenset[tuple[str, UUID, UUID]],
    aggregate_type: str,
    aggregate_id: UUID,
    revision_id: UUID,
) -> bool:
    return (aggregate_type, aggregate_id, revision_id) in markers


def _number(value: object) -> float | None:
    return float(cast(Any, value)) if value is not None else None


class SqlAlchemySchemaBundleSnapshotRepository:
    """Read every planner-relevant current head in one fail-closed read-only transaction."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: RlsContext,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    def read_snapshot(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        session: Session | None = None,
        layout_external_keys: dict[UUID, str] | None = None,
    ) -> CatalogSnapshot:
        with self._snapshot_session(session) as session:
            self._rls.bind_authorization(session, context, decision)
            database_rows = list(
                session.execute(
                    sa.select(
                        database.c.id,
                        database.c.current_revision_id,
                        database.c.classification,
                        database_revision.c.content_hash,
                        database_revision.c.database_key,
                        database_revision.c.name,
                        database_revision.c.description,
                    )
                    .select_from(_current_join(database, database_revision))
                    .order_by(database_revision.c.database_key, database.c.id)
                ).mappings()
            )
            profile_rows = list(
                session.execute(
                    sa.select(
                        profile.c.id,
                        profile.c.current_revision_id,
                        profile.c.classification,
                        profile_revision.c.content_hash,
                        profile_revision.c.profile_key,
                        profile_revision.c.name,
                        profile_revision.c.description,
                        profile_revision.c.database_id,
                        profile_revision.c.database_revision_id,
                    )
                    .select_from(_current_join(profile, profile_revision))
                    .order_by(profile_revision.c.profile_key, profile.c.id)
                ).mappings()
            )
            table_rows = list(
                session.execute(
                    sa.select(
                        schema_table.c.id,
                        schema_table.c.current_revision_id,
                        schema_table.c.classification,
                        schema_table_revision.c.content_hash,
                        schema_table_revision.c.table_key,
                        schema_table_revision.c.name,
                        schema_table_revision.c.description,
                        schema_table_revision.c.data_category,
                    )
                    .select_from(_current_join(schema_table, schema_table_revision))
                    .order_by(schema_table_revision.c.table_key, schema_table.c.id)
                ).mappings()
            )
            attribute_rows = list(
                session.execute(
                    sa.select(
                        attribute_definition.c.id,
                        attribute_definition.c.current_revision_id,
                        attribute_definition.c.classification,
                        attribute_definition.c.table_id,
                        attribute_definition_revision.c.content_hash,
                        attribute_definition_revision.c.table_revision_id,
                        attribute_definition_revision.c.attribute_key,
                        attribute_definition_revision.c.name,
                        attribute_definition_revision.c.data_type,
                        attribute_definition_revision.c.required,
                        attribute_definition_revision.c.quantity_semantics,
                        attribute_definition_revision.c.normalized_unit,
                        attribute_definition_revision.c.minimum_number,
                        attribute_definition_revision.c.maximum_number,
                        attribute_definition_revision.c.minimum_length,
                        attribute_definition_revision.c.maximum_length,
                        attribute_definition_revision.c.pattern,
                        attribute_definition_revision.c.allowed_values,
                        attribute_definition_revision.c.reference_table_id,
                        attribute_definition_revision.c.help_text,
                        attribute_definition_revision.c.business_key,
                    )
                    .select_from(_current_join(attribute_definition, attribute_definition_revision))
                    .order_by(
                        attribute_definition.c.table_id,
                        attribute_definition_revision.c.attribute_key,
                        attribute_definition.c.id,
                    )
                ).mappings()
            )
            layout_rows = list(
                session.execute(
                    sa.select(
                        layout.c.id,
                        layout.c.current_revision_id,
                        layout.c.classification,
                        layout.c.table_id,
                        layout_revision.c.content_hash,
                        layout_revision.c.table_revision_id,
                        layout_revision.c.name,
                        layout_revision.c.description,
                    )
                    .select_from(_current_join(layout, layout_revision))
                    .order_by(layout.c.table_id, layout_revision.c.name, layout.c.id)
                ).mappings()
            )
            layout_revision_ids = tuple(
                cast(UUID, row["current_revision_id"]) for row in layout_rows
            )
            layout_item_rows = (
                list(
                    session.execute(
                        sa.select(
                            layout_item.c.layout_revision_id,
                            layout_item.c.attribute_definition_id,
                            layout_item.c.attribute_definition_revision_id,
                            layout_item.c.section,
                            layout_item.c.ordinal,
                        )
                        .where(layout_item.c.layout_revision_id.in_(layout_revision_ids))
                        .order_by(layout_item.c.layout_revision_id, layout_item.c.ordinal)
                    ).mappings()
                )
                if layout_revision_ids
                else []
            )
            placement_rows = list(
                session.execute(
                    sa.select(
                        table_profile_placement.c.profile_id,
                        table_profile_placement.c.profile_revision_id,
                        table_profile_placement.c.table_id,
                        table_profile_placement.c.table_revision_id,
                        table_profile_placement.c.classification,
                    ).order_by(
                        table_profile_placement.c.profile_id,
                        table_profile_placement.c.table_id,
                    )
                ).mappings()
            )
            link_rows = list(
                session.execute(
                    sa.select(
                        link_type.c.id,
                        link_type.c.current_revision_id,
                        link_type.c.classification,
                        link_type_revision.c.content_hash,
                        link_type_revision.c.link_key,
                        link_type_revision.c.name,
                        link_type_revision.c.source_table_id,
                        link_type_revision.c.source_table_revision_id,
                        link_type_revision.c.target_table_id,
                        link_type_revision.c.target_table_revision_id,
                        link_type_revision.c.forward_label,
                        link_type_revision.c.reverse_label,
                        link_type_revision.c.source_cardinality,
                        link_type_revision.c.target_cardinality,
                        link_type_revision.c.description,
                    )
                    .select_from(_current_join(link_type, link_type_revision))
                    .order_by(link_type_revision.c.link_key, link_type.c.id)
                ).mappings()
            )
            marker_rows = session.execute(
                sa.select(
                    publication_marker.c.aggregate_type,
                    publication_marker.c.aggregate_id,
                    publication_marker.c.revision_id,
                ).order_by(
                    publication_marker.c.aggregate_type,
                    publication_marker.c.aggregate_id,
                    publication_marker.c.revision_id,
                )
            ).mappings()
            markers = frozenset(
                (
                    cast(str, row["aggregate_type"]),
                    cast(UUID, row["aggregate_id"]),
                    cast(UUID, row["revision_id"]),
                )
                for row in marker_rows
            )
            bundle_layout_rows = session.execute(
                sa.text(
                    "SELECT aggregate_id, external_key FROM ("
                    "SELECT binding.aggregate_id, binding.external_key, "
                    "row_number() OVER (PARTITION BY binding.aggregate_id "
                    "ORDER BY application.applied_at DESC, binding.sequence DESC) AS ordinal "
                    "FROM catalog.schema_definition_bundle_binding AS binding "
                    "JOIN catalog.schema_definition_bundle_application AS application "
                    "ON application.id = binding.application_id "
                    "AND application.organization_id = binding.organization_id "
                    "AND application.project_id = binding.project_id "
                    "WHERE binding.target_type = 'layout' AND binding.aggregate_id IS NOT NULL"
                    ") AS ranked WHERE ordinal = 1"
                )
            ).mappings()
            known_layout_keys = {
                cast(UUID, row["aggregate_id"]): cast(str, row["external_key"])
                for row in bundle_layout_rows
            }
            known_layout_keys.update(layout_external_keys or {})

            database_keys = {
                cast(UUID, row["id"]): cast(str, row["database_key"]) for row in database_rows
            }
            database_heads = {
                cast(UUID, row["id"]): cast(UUID, row["current_revision_id"])
                for row in database_rows
            }
            profile_keys = {
                cast(UUID, row["id"]): cast(str, row["profile_key"]) for row in profile_rows
            }
            profile_heads = {
                cast(UUID, row["id"]): cast(UUID, row["current_revision_id"])
                for row in profile_rows
            }
            table_keys = {cast(UUID, row["id"]): cast(str, row["table_key"]) for row in table_rows}
            table_heads = {
                cast(UUID, row["id"]): cast(UUID, row["current_revision_id"]) for row in table_rows
            }
            attribute_keys = {
                cast(UUID, row["id"]): cast(str, row["attribute_key"]) for row in attribute_rows
            }
            attribute_heads = {
                cast(UUID, row["id"]): cast(UUID, row["current_revision_id"])
                for row in attribute_rows
            }
            items_by_layout: dict[UUID, list[dict[str, Any]]] = {}
            layout_item_heads_match: dict[UUID, bool] = {}
            for row in layout_item_rows:
                attribute_id = cast(UUID, row["attribute_definition_id"])
                if attribute_id not in attribute_keys:
                    raise RuntimeError("Layout snapshot contains an unresolved Attribute identity")
                layout_revision_id = cast(UUID, row["layout_revision_id"])
                items_by_layout.setdefault(layout_revision_id, []).append(
                    {
                        "attribute_key": attribute_keys[attribute_id],
                        "section": row["section"],
                        "ordinal": int(row["ordinal"]),
                    }
                )
                layout_item_heads_match[layout_revision_id] = layout_item_heads_match.get(
                    layout_revision_id, True
                ) and (
                    cast(UUID, row["attribute_definition_revision_id"])
                    == attribute_heads[attribute_id]
                )

            placements_by_identity: dict[tuple[UUID, UUID], list[dict[str, Any]]] = {}
            for row in placement_rows:
                profile_id = cast(UUID, row["profile_id"])
                table_id = cast(UUID, row["table_id"])
                if profile_id not in profile_keys or table_id not in table_keys:
                    raise RuntimeError("Placement snapshot contains an unresolved identity")
                placements_by_identity.setdefault((profile_id, table_id), []).append(dict(row))

            current_record_table_ids = frozenset(
                cast(UUID, row["table_id"])
                for row in session.execute(
                    sa.select(catalog_record_revision.c.table_id)
                    .select_from(
                        catalog_record.join(
                            catalog_record_revision,
                            sa.and_(
                                catalog_record_revision.c.id
                                == catalog_record.c.current_revision_id,
                                catalog_record_revision.c.aggregate_id == catalog_record.c.id,
                                catalog_record_revision.c.organization_id
                                == catalog_record.c.organization_id,
                                catalog_record_revision.c.project_id == catalog_record.c.project_id,
                            ),
                        )
                    )
                    .group_by(catalog_record_revision.c.table_id)
                ).mappings()
            )
            current_value_attribute_ids: set[UUID] = set()
            for value_table in _VALUE_TABLES:
                current_value_attribute_ids.update(
                    cast(UUID, attribute_id)
                    for attribute_id in session.execute(
                        sa.select(value_table.c.attribute_definition_id)
                        .select_from(
                            value_table.join(
                                catalog_record,
                                sa.and_(
                                    catalog_record.c.id == value_table.c.record_id,
                                    catalog_record.c.organization_id
                                    == value_table.c.organization_id,
                                    catalog_record.c.project_id == value_table.c.project_id,
                                    catalog_record.c.current_revision_id
                                    == value_table.c.record_revision_id,
                                ),
                            )
                        )
                        .group_by(value_table.c.attribute_definition_id)
                    ).scalars()
                )

            objects: list[CatalogStateObject] = []
            for row in database_rows:
                object_id = cast(UUID, row["id"])
                revision_id = cast(UUID, row["current_revision_id"])
                objects.append(
                    CatalogStateObject(
                        "database",
                        cast(str, row["database_key"]),
                        None,
                        object_id,
                        revision_id,
                        cast(str, row["content_hash"]),
                        _published(markers, DATABASE_AGGREGATE_TYPE, object_id, revision_id),
                        {
                            "key": row["database_key"],
                            "name": row["name"],
                            "description": row["description"],
                        },
                        classification=DataClassification(cast(str, row["classification"])),
                    )
                )
            for row in profile_rows:
                object_id = cast(UUID, row["id"])
                revision_id = cast(UUID, row["current_revision_id"])
                database_id = cast(UUID, row["database_id"])
                if database_id not in database_keys:
                    raise RuntimeError("Profile snapshot contains an unresolved Database identity")
                database_key = database_keys[database_id]
                objects.append(
                    CatalogStateObject(
                        "profile",
                        cast(str, row["profile_key"]),
                        database_key,
                        object_id,
                        revision_id,
                        cast(str, row["content_hash"]),
                        _published(markers, PROFILE_AGGREGATE_TYPE, object_id, revision_id),
                        {
                            "database_key": database_key,
                            "key": row["profile_key"],
                            "name": row["name"],
                            "description": row["description"],
                        },
                        dependency_heads_match=(
                            cast(UUID, row["database_revision_id"]) == database_heads[database_id]
                        ),
                        classification=DataClassification(cast(str, row["classification"])),
                    )
                )
            for row in table_rows:
                object_id = cast(UUID, row["id"])
                revision_id = cast(UUID, row["current_revision_id"])
                table_content = {
                    "key": row["table_key"],
                    "name": row["name"],
                    "description": row["description"],
                }
                if row["data_category"] is not None:
                    table_content["data_category"] = row["data_category"]
                objects.append(
                    CatalogStateObject(
                        "table",
                        cast(str, row["table_key"]),
                        None,
                        object_id,
                        revision_id,
                        cast(str, row["content_hash"]),
                        _published(markers, TABLE_AGGREGATE_TYPE, object_id, revision_id),
                        table_content,
                        classification=DataClassification(cast(str, row["classification"])),
                        has_current_records=object_id in current_record_table_ids,
                    )
                )
            for row in attribute_rows:
                object_id = cast(UUID, row["id"])
                revision_id = cast(UUID, row["current_revision_id"])
                table_id = cast(UUID, row["table_id"])
                if table_id not in table_keys:
                    raise RuntimeError("Attribute snapshot contains an unresolved Table identity")
                reference_id = cast(UUID | None, row["reference_table_id"])
                reference_key = table_keys.get(reference_id) if reference_id is not None else None
                if reference_id is not None and reference_key is None:
                    raise RuntimeError("Attribute snapshot contains an unresolved reference Table")
                attribute_content = {
                    "key": row["attribute_key"],
                    "name": row["name"],
                    "data_type": row["data_type"],
                    "required": bool(row["required"]),
                    "quantity_semantics": row["quantity_semantics"],
                    "normalized_unit": row["normalized_unit"],
                    "minimum_number": _number(row["minimum_number"]),
                    "maximum_number": _number(row["maximum_number"]),
                    "minimum_length": row["minimum_length"],
                    "maximum_length": row["maximum_length"],
                    "pattern": row["pattern"],
                    "allowed_values": list(row["allowed_values"] or ()),
                    "reference_table_key": reference_key,
                    "help_text": row["help_text"],
                }
                if row["business_key"]:
                    attribute_content["business_key"] = True
                objects.append(
                    CatalogStateObject(
                        "attribute",
                        cast(str, row["attribute_key"]),
                        table_keys[table_id],
                        object_id,
                        revision_id,
                        cast(str, row["content_hash"]),
                        _published(markers, ATTRIBUTE_AGGREGATE_TYPE, object_id, revision_id),
                        attribute_content,
                        dependency_heads_match=(
                            cast(UUID, row["table_revision_id"]) == table_heads[table_id]
                        ),
                        classification=DataClassification(cast(str, row["classification"])),
                        has_current_values=object_id in current_value_attribute_ids,
                    )
                )
            for row in layout_rows:
                object_id = cast(UUID, row["id"])
                revision_id = cast(UUID, row["current_revision_id"])
                table_id = cast(UUID, row["table_id"])
                if table_id not in table_keys:
                    raise RuntimeError("Layout snapshot contains an unresolved Table identity")
                objects.append(
                    CatalogStateObject(
                        "layout",
                        known_layout_keys.get(object_id, f"existing.{object_id}"),
                        table_keys[table_id],
                        object_id,
                        revision_id,
                        cast(str, row["content_hash"]),
                        _published(markers, LAYOUT_AGGREGATE_TYPE, object_id, revision_id),
                        {
                            "name": row["name"],
                            "description": row["description"],
                            "items": items_by_layout.get(revision_id, []),
                        },
                        dependency_heads_match=(
                            cast(UUID, row["table_revision_id"]) == table_heads[table_id]
                            and layout_item_heads_match.get(revision_id, True)
                        ),
                        classification=DataClassification(cast(str, row["classification"])),
                    )
                )
            for profile_id, table_id in sorted(
                placements_by_identity,
                key=lambda value: (profile_keys[value[0]], table_keys[value[1]]),
            ):
                rows = placements_by_identity[(profile_id, table_id)]
                dependency_heads_match = any(
                    cast(UUID, row["profile_revision_id"]) == profile_heads[profile_id]
                    and cast(UUID, row["table_revision_id"]) == table_heads[table_id]
                    for row in rows
                )
                classifications = {
                    DataClassification(cast(str, row["classification"])) for row in rows
                }
                if len(classifications) != 1:
                    raise RuntimeError("Placement history contains inconsistent classifications")
                content = {
                    "profile_key": profile_keys[profile_id],
                    "table_key": table_keys[table_id],
                }
                objects.append(
                    CatalogStateObject(
                        "profile_table_placement",
                        f"{profile_keys[profile_id]}.{table_keys[table_id]}",
                        profile_keys[profile_id],
                        None,
                        None,
                        content_sha256(content),
                        False,
                        content,
                        dependency_heads_match=dependency_heads_match,
                        classification=next(iter(classifications)),
                    )
                )
            for row in link_rows:
                object_id = cast(UUID, row["id"])
                revision_id = cast(UUID, row["current_revision_id"])
                source_id = cast(UUID, row["source_table_id"])
                target_id = cast(UUID, row["target_table_id"])
                if source_id not in table_keys or target_id not in table_keys:
                    raise RuntimeError("Link Type snapshot contains an unresolved Table identity")
                objects.append(
                    CatalogStateObject(
                        "link_type",
                        cast(str, row["link_key"]),
                        None,
                        object_id,
                        revision_id,
                        cast(str, row["content_hash"]),
                        _published(markers, LINK_TYPE_AGGREGATE_TYPE, object_id, revision_id),
                        {
                            "key": row["link_key"],
                            "name": row["name"],
                            "source_table_key": table_keys[source_id],
                            "target_table_key": table_keys[target_id],
                            "forward_label": row["forward_label"],
                            "reverse_label": row["reverse_label"],
                            "source_cardinality": row["source_cardinality"],
                            "target_cardinality": row["target_cardinality"],
                            "description": row["description"],
                        },
                        dependency_heads_match=(
                            cast(UUID, row["source_table_revision_id"]) == table_heads[source_id]
                            and cast(UUID, row["target_table_revision_id"])
                            == table_heads[target_id]
                        ),
                        classification=DataClassification(cast(str, row["classification"])),
                    )
                )
            objects.sort(
                key=lambda item: (
                    item.target_type,
                    item.parent_external_key or "",
                    item.external_key,
                    str(item.object_id) if item.object_id is not None else "",
                )
            )
            return CatalogSnapshot(context.organization_id, context.project_id, tuple(objects))

    @contextmanager
    def _snapshot_session(self, existing: Session | None) -> Iterator[Session]:
        if existing is not None:
            yield existing
            return
        with self._sessions() as session, session.begin():
            session.execute(sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            yield session
