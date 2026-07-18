"""PostgreSQL Mapping Profile identity/revision adapter (T-53)."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.mapping_profiles import (
    MAPPING_PROFILE_AGGREGATE_TYPE,
    MappingProfileNotFound,
    MappingProfileRepository,
    MappingProfileSnapshot,
)
from cmp.modules.processing.domain.common_pipeline import (
    AttributeBinding,
    ChannelBinding,
    MappingProfileContent,
    MissingDataPolicy,
    mapping_profile_canonical,
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
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


metadata = sa.MetaData()
profile_table = sa.Table(
    "mapping_profile",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("profile_key", sa.String(160), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="processing",
)
revision_table = sa.Table(
    "mapping_profile_revision",
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
    sa.Column("profile_key", sa.String(160), nullable=False),
    sa.Column("label", sa.String(200), nullable=False),
    sa.Column("independent_quantity", sa.String(160), nullable=False),
    sa.Column("missing_data_policy", sa.String(32), nullable=False),
    sa.Column("channel_binding_count", sa.Integer(), nullable=False),
    sa.Column("attribute_binding_count", sa.Integer(), nullable=False),
    schema="processing",
)
channel_table = sa.Table(
    "mapping_profile_channel_binding",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("profile_id", sa.Uuid(), nullable=False),
    sa.Column("profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("channel_key", sa.String(160), nullable=False),
    sa.Column("target_quantity", sa.String(160), nullable=False),
    sa.Column("accepted_normalized_units", sa.ARRAY(sa.String(160)), nullable=False),
    sa.Column("required", sa.Boolean(), nullable=False),
    sa.Column("value_scale", sa.Double(), nullable=False),
    sa.Column("value_offset", sa.Double(), nullable=False),
    schema="processing",
)
attribute_table = sa.Table(
    "mapping_profile_attribute_binding",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("profile_id", sa.Uuid(), nullable=False),
    sa.Column("profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("attribute_definition_id", sa.Uuid(), nullable=False),
    sa.Column("attribute_definition_revision_id", sa.Uuid(), nullable=False),
    sa.Column("target_quantity", sa.String(160), nullable=False),
    sa.Column("accepted_normalized_units", sa.ARRAY(sa.String(160)), nullable=False),
    sa.Column("required", sa.Boolean(), nullable=False),
    schema="processing",
)


def _values(value: MappingProfileContent) -> dict[str, object]:
    return {
        "profile_key": value.profile_key,
        "label": value.label,
        "independent_quantity": value.independent_quantity,
        "missing_data_policy": value.missing_data_policy.value,
        "channel_binding_count": len(value.bindings),
        "attribute_binding_count": len(value.attribute_bindings),
    }


def _write_children(session: Session, draft: RevisionDraft[MappingProfileContent]) -> None:
    common = {
        "organization_id": draft.scope.organization_id,
        "project_id": draft.scope.project_id,
        "classification": draft.scope.classification,
        "profile_id": draft.aggregate_id,
        "profile_revision_id": draft.revision_id,
    }
    session.execute(
        sa.insert(channel_table),
        [
            {
                **common,
                "ordinal": ordinal,
                "channel_key": item.channel_key,
                "target_quantity": item.target_quantity,
                "accepted_normalized_units": list(item.accepted_normalized_units),
                "required": item.required,
                "value_scale": item.scale,
                "value_offset": item.offset,
            }
            for ordinal, item in enumerate(draft.content.bindings)
        ],
    )
    if draft.content.attribute_bindings:
        session.execute(
            sa.insert(attribute_table),
            [
                {
                    **common,
                    "ordinal": ordinal,
                    "attribute_definition_id": item.attribute_definition_id,
                    "attribute_definition_revision_id": item.attribute_definition_revision_id,
                    "target_quantity": item.target_quantity,
                    "accepted_normalized_units": list(item.accepted_normalized_units),
                    "required": item.required,
                }
                for ordinal, item in enumerate(draft.content.attribute_bindings)
            ],
        )


_TABLES = TypedRevisionTables(
    aggregate_type=MAPPING_PROFILE_AGGREGATE_TYPE,
    identity_table=profile_table,
    revision_table=revision_table,
    canonical_content=mapping_profile_canonical,
    content_values=_values,
    identity_values=lambda value: {"profile_key": value.profile_key},
    revision_content_writer=_write_children,
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=MAPPING_PROFILE_AGGREGATE_TYPE,
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


def _content(row: Any, channels: Sequence[Any], attributes: Sequence[Any]) -> MappingProfileContent:
    return MappingProfileContent(
        profile_key=str(row["profile_key"]),
        label=str(row["label"]),
        independent_quantity=str(row["independent_quantity"]),
        missing_data_policy=MissingDataPolicy(str(row["missing_data_policy"])),
        bindings=tuple(
            ChannelBinding(
                channel_key=str(item["channel_key"]),
                target_quantity=str(item["target_quantity"]),
                accepted_normalized_units=tuple(
                    str(unit) for unit in item["accepted_normalized_units"]
                ),
                required=bool(item["required"]),
                scale=float(item["value_scale"]),
                offset=float(item["value_offset"]),
            )
            for item in channels
        ),
        attribute_bindings=tuple(
            AttributeBinding(
                attribute_definition_id=cast(UUID, item["attribute_definition_id"]),
                attribute_definition_revision_id=cast(
                    UUID, item["attribute_definition_revision_id"]
                ),
                target_quantity=str(item["target_quantity"]),
                accepted_normalized_units=tuple(
                    str(unit) for unit in item["accepted_normalized_units"]
                ),
                required=bool(item["required"]),
            )
            for item in attributes
        ),
    )


class SqlAlchemyMappingProfileRepository(MappingProfileRepository):
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

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[MappingProfileContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _snapshot(session: Session, row: Any) -> MappingProfileSnapshot:
        revision_id = cast(UUID, row["id"])
        channels = (
            session.execute(
                sa.select(channel_table)
                .where(channel_table.c.profile_revision_id == revision_id)
                .order_by(channel_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        attributes = (
            session.execute(
                sa.select(attribute_table)
                .where(attribute_table.c.profile_revision_id == revision_id)
                .order_by(attribute_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        record = _record(row)
        return MappingProfileSnapshot(
            record.aggregate_id, record, _content(row, channels, attributes)
        )

    def get_profile(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
    ) -> MappingProfileSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(revision_table)
                    .join(
                        profile_table,
                        sa.and_(
                            profile_table.c.organization_id == revision_table.c.organization_id,
                            profile_table.c.project_id == revision_table.c.project_id,
                            profile_table.c.id == revision_table.c.aggregate_id,
                            profile_table.c.current_revision_id == revision_table.c.id,
                        ),
                    )
                    .where(profile_table.c.id == profile_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise MappingProfileNotFound("Mapping Profile is not visible")
            return self._snapshot(session, row)

    def list_profiles(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[MappingProfileSnapshot, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(revision_table)
                    .join(
                        profile_table,
                        sa.and_(
                            profile_table.c.organization_id == revision_table.c.organization_id,
                            profile_table.c.project_id == revision_table.c.project_id,
                            profile_table.c.id == revision_table.c.aggregate_id,
                            profile_table.c.current_revision_id == revision_table.c.id,
                        ),
                    )
                    .order_by(profile_table.c.updated_at.desc(), profile_table.c.id)
                )
                .mappings()
                .all()
            )
            return tuple(self._snapshot(session, row) for row in rows)
