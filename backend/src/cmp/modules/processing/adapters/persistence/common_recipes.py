"""PostgreSQL adapter for versioned common Processing Recipes (T-54)."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_recipes import (
    COMMON_RECIPE_AGGREGATE_TYPE,
    CommonRecipeNotFound,
    CommonRecipeRepository,
    CommonRecipeSnapshot,
)
from cmp.modules.processing.domain.common_pipeline import ProcessingStep
from cmp.modules.processing.domain.common_recipes import (
    CommonProcessingRecipeContent,
    RecipeLifecycle,
    common_processing_recipe_canonical,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import (
    RevisionDraft,
    RevisionRecord,
    TenantScope,
    content_sha256,
)


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


metadata = sa.MetaData()
recipe_table = sa.Table(
    "common_processing_recipe",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("recipe_key", sa.String(160), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="processing",
)
revision_table = sa.Table(
    "common_processing_recipe_revision",
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
    sa.Column("recipe_key", sa.String(160), nullable=False),
    sa.Column("label", sa.String(200), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("mapping_profile_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_profile_sha256", sa.CHAR(64), nullable=False),
    sa.Column("step_count", sa.Integer(), nullable=False),
    sa.Column("lifecycle_state", sa.String(32), nullable=False),
    schema="processing",
)
step_table = sa.Table(
    "common_processing_recipe_step",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("recipe_id", sa.Uuid(), nullable=False),
    sa.Column("recipe_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("method_id", sa.String(160), nullable=False),
    sa.Column("method_version", sa.String(64), nullable=False),
    sa.Column("options_sha256", sa.CHAR(64), nullable=False),
    sa.Column("options", postgresql.JSONB(), nullable=False),
    schema="processing",
)


def _values(value: CommonProcessingRecipeContent) -> dict[str, object]:
    return {
        "recipe_key": value.recipe_key,
        "label": value.label,
        "description": value.description,
        "mapping_profile_id": value.mapping_profile_id,
        "mapping_profile_revision_id": value.mapping_profile_revision_id,
        "mapping_profile_sha256": value.mapping_profile_sha256,
        "step_count": len(value.steps),
        "lifecycle_state": value.lifecycle_state.value,
    }


def _write_steps(
    session: Session, draft: RevisionDraft[CommonProcessingRecipeContent]
) -> None:
    common = {
        "organization_id": draft.scope.organization_id,
        "project_id": draft.scope.project_id,
        "classification": draft.scope.classification,
        "recipe_id": draft.aggregate_id,
        "recipe_revision_id": draft.revision_id,
    }
    session.execute(
        sa.insert(step_table),
        [
            {
                **common,
                "ordinal": ordinal,
                "method_id": step.method_id,
                "method_version": step.method_version,
                "options_sha256": content_sha256(step.options),
                "options": step.options,
            }
            for ordinal, step in enumerate(draft.content.steps)
        ],
    )


_TABLES = TypedRevisionTables(
    aggregate_type=COMMON_RECIPE_AGGREGATE_TYPE,
    identity_table=recipe_table,
    revision_table=revision_table,
    canonical_content=common_processing_recipe_canonical,
    content_values=_values,
    identity_values=lambda value: {"recipe_key": value.recipe_key},
    revision_content_writer=_write_steps,
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=COMMON_RECIPE_AGGREGATE_TYPE,
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


def _content(row: Any, steps: Sequence[Any]) -> CommonProcessingRecipeContent:
    return CommonProcessingRecipeContent(
        recipe_key=str(row["recipe_key"]),
        label=str(row["label"]),
        description=cast(str | None, row["description"]),
        mapping_profile_id=cast(UUID, row["mapping_profile_id"]),
        mapping_profile_revision_id=cast(UUID, row["mapping_profile_revision_id"]),
        mapping_profile_sha256=str(row["mapping_profile_sha256"]),
        steps=tuple(
            ProcessingStep(
                method_id=str(item["method_id"]),
                method_version=str(item["method_version"]),
                options=dict(item["options"]),
            )
            for item in steps
        ),
        lifecycle_state=RecipeLifecycle(str(row["lifecycle_state"])),
    )


class SqlAlchemyCommonRecipeRepository(CommonRecipeRepository):
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

    def recipe_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[CommonProcessingRecipeContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _snapshot(session: Session, row: Any) -> CommonRecipeSnapshot:
        revision_id = cast(UUID, row["id"])
        steps = (
            session.execute(
                sa.select(step_table)
                .where(step_table.c.recipe_revision_id == revision_id)
                .order_by(step_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        record = _record(row)
        return CommonRecipeSnapshot(record.aggregate_id, record, _content(row, steps))

    def get_recipe(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
    ) -> CommonRecipeSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(revision_table)
                    .join(
                        recipe_table,
                        sa.and_(
                            recipe_table.c.organization_id
                            == revision_table.c.organization_id,
                            recipe_table.c.project_id == revision_table.c.project_id,
                            recipe_table.c.id == revision_table.c.aggregate_id,
                            recipe_table.c.current_revision_id == revision_table.c.id,
                        ),
                    )
                    .where(recipe_table.c.id == recipe_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise CommonRecipeNotFound("common Processing Recipe is not visible")
            return self._snapshot(session, row)

    def get_recipe_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        revision_id: UUID,
    ) -> CommonRecipeSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(revision_table).where(
                        revision_table.c.aggregate_id == recipe_id,
                        revision_table.c.id == revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise CommonRecipeNotFound("common Processing Recipe revision is not visible")
            return self._snapshot(session, row)

    def list_recipes(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[CommonRecipeSnapshot, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(revision_table)
                    .join(
                        recipe_table,
                        sa.and_(
                            recipe_table.c.organization_id
                            == revision_table.c.organization_id,
                            recipe_table.c.project_id == revision_table.c.project_id,
                            recipe_table.c.id == revision_table.c.aggregate_id,
                            recipe_table.c.current_revision_id == revision_table.c.id,
                        ),
                    )
                    .order_by(recipe_table.c.updated_at.desc(), recipe_table.c.id)
                )
                .mappings()
                .all()
            )
            return tuple(self._snapshot(session, row) for row in rows)
