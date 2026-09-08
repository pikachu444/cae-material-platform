"""RLS-bound persistence for the project Solver Card reader index."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.exporting.adapters.persistence.neutral_hyperelastic_repository import (
    neutral_solver_card_revision_table,
    neutral_solver_card_table,
)
from cmp.modules.exporting.adapters.persistence.repository import (
    solver_card_revision_table,
    solver_card_table,
)
from cmp.modules.exporting.application.project_card_index import (
    ProjectCardIndexRepository,
    ProjectCardIndexRow,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.persistence.neutral_material_repository import (
    neutral_material_revision_table,
)

metadata = sa.MetaData()
material_model_revision_table = sa.Table(
    "material_model_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    schema="modeling",
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


def _common_statement() -> sa.Select[Any]:
    identity = solver_card_table
    revision = solver_card_revision_table
    model_revision = material_model_revision_table
    return (
        sa.select(
            revision.c.aggregate_id.label("solver_card_id"),
            revision.c.id.label("revision_id"),
            revision.c.revision_no,
            revision.c.schema_id,
            revision.c.content_hash,
            sa.func.coalesce(revision.c.material_name, revision.c.card_title).label("title"),
            revision.c.material_model_id,
            revision.c.material_model_revision_id,
            sa.null().label("neutral_material_id"),
            model_revision.c.material_id.label("material_id"),
            revision.c.target_solver,
            revision.c.target_version,
            revision.c.target_unit_system,
            revision.c.solver_material_id,
            revision.c.card_sha256,
            revision.c.exporter_id,
            sa.null().label("model_family"),
            sa.null().label("family"),
            revision.c.created_at,
        )
        .select_from(
            identity.join(
                revision,
                sa.and_(
                    revision.c.id == identity.c.current_revision_id,
                    revision.c.aggregate_id == identity.c.id,
                    revision.c.organization_id == identity.c.organization_id,
                    revision.c.project_id == identity.c.project_id,
                ),
            ).outerjoin(
                model_revision,
                sa.and_(
                    model_revision.c.id == revision.c.material_model_revision_id,
                    model_revision.c.organization_id == revision.c.organization_id,
                    model_revision.c.project_id == revision.c.project_id,
                ),
            )
        )
    )


def _neutral_statement() -> sa.Select[Any]:
    identity = neutral_solver_card_table
    revision = neutral_solver_card_revision_table
    return sa.select(
        revision.c.aggregate_id.label("solver_card_id"),
        revision.c.id.label("revision_id"),
        revision.c.revision_no,
        revision.c.schema_id,
        revision.c.content_hash,
        revision.c.material_name.label("title"),
        sa.null().label("material_model_id"),
        sa.null().label("material_model_revision_id"),
        revision.c.neutral_material_id,
        neutral_material_revision_table.c.material_id.label("material_id"),
        revision.c.target_solver,
        revision.c.target_version,
        revision.c.target_unit_system,
        revision.c.solver_material_id,
        revision.c.card_sha256,
        revision.c.exporter_id,
        revision.c.model_family,
        revision.c.family,
        revision.c.created_at,
    ).select_from(
        identity.join(
            revision,
            sa.and_(
                revision.c.id == identity.c.current_revision_id,
                revision.c.aggregate_id == identity.c.id,
                revision.c.organization_id == identity.c.organization_id,
                revision.c.project_id == identity.c.project_id,
            ),
        ).outerjoin(
            neutral_material_revision_table,
            sa.and_(
                neutral_material_revision_table.c.id == revision.c.neutral_material_revision_id,
                neutral_material_revision_table.c.aggregate_id == revision.c.neutral_material_id,
                neutral_material_revision_table.c.organization_id == revision.c.organization_id,
                neutral_material_revision_table.c.project_id == revision.c.project_id,
            ),
        )
    )


def _row(value: Any) -> ProjectCardIndexRow:
    return ProjectCardIndexRow(
        solver_card_id=cast(UUID, value["solver_card_id"]),
        revision_id=cast(UUID, value["revision_id"]),
        revision_no=int(value["revision_no"]),
        schema_id=str(value["schema_id"]),
        content_hash=str(value["content_hash"]),
        title=str(value["title"] or ""),
        material_model_id=cast(UUID | None, value["material_model_id"]),
        material_model_revision_id=cast(UUID | None, value["material_model_revision_id"]),
        neutral_material_id=cast(UUID | None, value["neutral_material_id"]),
        material_id=cast(UUID | None, value["material_id"]),
        target_solver=str(value["target_solver"]),
        target_version=str(value["target_version"]),
        target_unit_system=str(value["target_unit_system"]),
        solver_material_id=int(value["solver_material_id"]),
        card_sha256=str(value["card_sha256"]),
        exporter_id=None if value["exporter_id"] is None else str(value["exporter_id"]),
        model_family=None if value["model_family"] is None else str(value["model_family"]),
        family=None if value["family"] is None else str(value["family"]),
        created_at=value["created_at"],
    )


class SqlAlchemyProjectCardIndexRepository(ProjectCardIndexRepository):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    @contextmanager
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    def list_current_cards(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[ProjectCardIndexRow, ...]:
        common = _common_statement().where(
            solver_card_table.c.organization_id == context.organization_id,
            solver_card_table.c.project_id == context.project_id,
        )
        neutral = _neutral_statement().where(
            neutral_solver_card_table.c.organization_id == context.organization_id,
            neutral_solver_card_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            common_rows = session.execute(common).mappings().all()
            neutral_rows = session.execute(neutral).mappings().all()
        return tuple(_row(value) for value in (*common_rows, *neutral_rows))


__all__ = ["SqlAlchemyProjectCardIndexRepository"]
