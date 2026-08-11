"""PostgreSQL stable identity and immutable revision adapter for Unit Profiles."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.units.application.profiles import (
    UNIT_PROFILE_AGGREGATE_TYPE,
    UnitProfileNotFound,
    UnitProfileRepository,
    UnitProfileSnapshot,
)
from cmp.modules.units.domain.profiles import (
    UnitProfileContent,
    UnitProfileSelection,
    unit_profile_canonical,
)
from cmp.modules.units.domain.system import DimensionId
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
    "unit_profile",
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
    schema="units",
)
revision_table = sa.Table(
    "unit_profile_revision",
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
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    sa.Column("selection_count", sa.Integer(), nullable=False),
    schema="units",
)
selection_table = sa.Table(
    "unit_profile_selection",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("profile_id", sa.Uuid(), nullable=False),
    sa.Column("profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("quantity_semantics", sa.String(160), nullable=False),
    sa.Column("dimension", sa.String(64), nullable=False),
    sa.Column("input_unit_id", sa.String(64), nullable=False),
    sa.Column("display_unit_id", sa.String(64), nullable=False),
    sa.Column("solver_export_unit_id", sa.String(64), nullable=True),
    schema="units",
)


def _values(value: UnitProfileContent) -> dict[str, object]:
    return {
        "profile_key": value.profile_key,
        "label": value.label,
        "description": value.description,
        "non_production": value.non_production,
        "selection_count": len(value.selections),
    }


def _write_children(session: Session, draft: RevisionDraft[UnitProfileContent]) -> None:
    common = {
        "organization_id": draft.scope.organization_id,
        "project_id": draft.scope.project_id,
        "classification": draft.scope.classification,
        "profile_id": draft.aggregate_id,
        "profile_revision_id": draft.revision_id,
    }
    session.execute(
        sa.insert(selection_table),
        [
            {
                **common,
                "ordinal": ordinal,
                "quantity_semantics": selection.quantity_semantics,
                "dimension": selection.dimension.value,
                "input_unit_id": selection.input_unit_id,
                "display_unit_id": selection.display_unit_id,
                "solver_export_unit_id": selection.solver_export_unit_id,
            }
            for ordinal, selection in enumerate(draft.content.selections)
        ],
    )


_TABLES = TypedRevisionTables(
    aggregate_type=UNIT_PROFILE_AGGREGATE_TYPE,
    identity_table=profile_table,
    revision_table=revision_table,
    canonical_content=unit_profile_canonical,
    content_values=_values,
    identity_values=lambda value: {"profile_key": value.profile_key},
    revision_content_writer=_write_children,
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=UNIT_PROFILE_AGGREGATE_TYPE,
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


def _content(row: Any, selections: Sequence[Any]) -> UnitProfileContent:
    return UnitProfileContent(
        profile_key=str(row["profile_key"]),
        label=str(row["label"]),
        description=None if row["description"] is None else str(row["description"]),
        non_production=bool(row["non_production"]),
        selections=tuple(
            UnitProfileSelection(
                quantity_semantics=str(item["quantity_semantics"]),
                dimension=DimensionId(str(item["dimension"])),
                input_unit_id=str(item["input_unit_id"]),
                display_unit_id=str(item["display_unit_id"]),
                solver_export_unit_id=(
                    None
                    if item["solver_export_unit_id"] is None
                    else str(item["solver_export_unit_id"])
                ),
            )
            for item in selections
        ),
    )


class SqlAlchemyUnitProfileRepository(UnitProfileRepository):
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
    ) -> RevisionStore[UnitProfileContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _snapshot(session: Session, row: Any) -> UnitProfileSnapshot:
        revision_id = cast(UUID, row["id"])
        selections = (
            session.execute(
                sa.select(selection_table)
                .where(selection_table.c.profile_revision_id == revision_id)
                .order_by(selection_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        record = _record(row)
        return UnitProfileSnapshot(record.aggregate_id, record, _content(row, selections))

    def get_profile(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
    ) -> UnitProfileSnapshot:
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
                raise UnitProfileNotFound("Unit Profile is not visible")
            return self._snapshot(session, row)

    def get_profile_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        revision_id: UUID,
    ) -> UnitProfileSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(revision_table).where(
                        revision_table.c.aggregate_id == profile_id,
                        revision_table.c.id == revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise UnitProfileNotFound()
            return self._snapshot(session, row)

    def list_profiles(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[UnitProfileSnapshot, ...]:
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


__all__ = ["SqlAlchemyUnitProfileRepository"]
