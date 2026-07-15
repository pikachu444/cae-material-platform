"""PostgreSQL adapter for explicit shear-relaxation Recipe revisions and Runs."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.artifacts.domain.content import ArtifactRecord
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.shear_relaxation import (
    SHEAR_RELAXATION_RECIPE_AGGREGATE_TYPE,
    RevisionSnapshot,
    ShearRelaxationProcessingRun,
)
from cmp.modules.processing.domain.reference_shear_relaxation_crop import (
    REFERENCE_SHEAR_RELAXATION_CROP_INPUT_SCHEMA,
    REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA,
    REFERENCE_SHEAR_RELAXATION_CROP_RECIPE_KIND,
    ReferenceShearRelaxationCropRecipeContent,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    ProcessingConflict,
    ProcessingNotFound,
    ProcessingRunStatus,
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
shear_relaxation_recipe_table = sa.Table(
    "shear_relaxation_recipe",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("recipe_label", sa.String(160), nullable=False),
    sa.Column("recipe_kind", sa.String(100), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="processing",
)
shear_relaxation_recipe_revision_table = sa.Table(
    "shear_relaxation_recipe_revision",
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
    sa.Column("recipe_kind", sa.String(100), nullable=False),
    sa.Column("step_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("minimum_time_s", sa.Double(), nullable=False),
    sa.Column("maximum_time_s", sa.Double(), nullable=False),
    sa.Column("input_schema_ref", sa.String(500), nullable=False),
    sa.Column("output_schema_ref", sa.String(500), nullable=False),
    schema="processing",
)
shear_relaxation_run_table = sa.Table(
    "shear_relaxation_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("recipe_id", sa.Uuid(), nullable=False),
    sa.Column("recipe_revision_id", sa.Uuid(), nullable=False),
    sa.Column("input_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("input_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("input_point_count", sa.BigInteger(), nullable=False),
    sa.Column("output_point_count", sa.BigInteger(), nullable=True),
    sa.Column("removed_point_count", sa.BigInteger(), nullable=True),
    sa.Column("result_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("result_sha256", sa.CHAR(64), nullable=True),
    sa.Column("output_dataset_id", sa.Uuid(), nullable=True),
    sa.Column("output_dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("change_reason", sa.Text(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="processing",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=SHEAR_RELAXATION_RECIPE_AGGREGATE_TYPE,
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


def _content(row: Any) -> ReferenceShearRelaxationCropRecipeContent:
    if (
        str(row["recipe_kind"]) != REFERENCE_SHEAR_RELAXATION_CROP_RECIPE_KIND
        or int(row["step_ordinal"]) != 0
        or str(row["input_schema_ref"]) != REFERENCE_SHEAR_RELAXATION_CROP_INPUT_SCHEMA
        or str(row["output_schema_ref"]) != REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA
    ):
        raise ProcessingConflict("shear-relaxation Recipe violates its typed contract")
    return ReferenceShearRelaxationCropRecipeContent(
        recipe_label=str(row["recipe_label"]),
        minimum_time_s=float(row["minimum_time_s"]),
        maximum_time_s=float(row["maximum_time_s"]),
    )


_TABLES = TypedRevisionTables[ReferenceShearRelaxationCropRecipeContent](
    aggregate_type=SHEAR_RELAXATION_RECIPE_AGGREGATE_TYPE,
    identity_table=shear_relaxation_recipe_table,
    revision_table=shear_relaxation_recipe_revision_table,
    canonical_content=lambda value: value.canonical(),
    content_values=lambda value: {
        "recipe_kind": REFERENCE_SHEAR_RELAXATION_CROP_RECIPE_KIND,
        "step_ordinal": 0,
        "minimum_time_s": value.minimum_time_s,
        "maximum_time_s": value.maximum_time_s,
        "input_schema_ref": REFERENCE_SHEAR_RELAXATION_CROP_INPUT_SCHEMA,
        "output_schema_ref": REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA,
    },
    identity_values=lambda value: {
        "recipe_label": value.recipe_label,
        "recipe_kind": REFERENCE_SHEAR_RELAXATION_CROP_RECIPE_KIND,
    },
)


def _run(row: Any) -> ShearRelaxationProcessingRun:
    return ShearRelaxationProcessingRun(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        recipe_id=cast(UUID, row["recipe_id"]),
        recipe_revision_id=cast(UUID, row["recipe_revision_id"]),
        input_dataset_id=cast(UUID, row["input_dataset_id"]),
        input_dataset_revision_id=cast(UUID, row["input_dataset_revision_id"]),
        status=ProcessingRunStatus(str(row["status"])),
        input_point_count=int(row["input_point_count"]),
        output_point_count=(
            int(row["output_point_count"])
            if row["output_point_count"] is not None
            else None
        ),
        removed_point_count=(
            int(row["removed_point_count"])
            if row["removed_point_count"] is not None
            else None
        ),
        result_artifact_id=cast(UUID | None, row["result_artifact_id"]),
        result_sha256=(str(row["result_sha256"]) if row["result_sha256"] else None),
        output_dataset_id=cast(UUID | None, row["output_dataset_id"]),
        output_dataset_revision_id=cast(UUID | None, row["output_dataset_revision_id"]),
        failure_code=(str(row["failure_code"]) if row["failure_code"] else None),
        change_reason=str(row["change_reason"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


class SqlAlchemyShearRelaxationProcessingRepository:
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

    @contextmanager
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    def recipe_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceShearRelaxationCropRecipeContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._rls.bind_authorization(
                session, context, decision
            ),
        )

    def get_recipe_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        recipe_revision_id: UUID,
    ) -> RevisionSnapshot:
        identity = shear_relaxation_recipe_table
        revision = shear_relaxation_recipe_revision_table
        statement = (
            sa.select(identity.c.recipe_label, *revision.c)
            .select_from(
                identity.join(
                    revision,
                    sa.and_(
                        revision.c.aggregate_id == identity.c.id,
                        revision.c.organization_id == identity.c.organization_id,
                        revision.c.project_id == identity.c.project_id,
                    ),
                )
            )
            .where(
                identity.c.organization_id == context.organization_id,
                identity.c.project_id == context.project_id,
                identity.c.id == recipe_id,
                revision.c.id == recipe_revision_id,
            )
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise ProcessingNotFound("shear-relaxation Recipe revision is not visible")
        return RevisionSnapshot(_record(row), _content(row))

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ShearRelaxationProcessingRun,
    ) -> ShearRelaxationProcessingRun:
        values = {
            "id": run.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
            "recipe_id": run.recipe_id,
            "recipe_revision_id": run.recipe_revision_id,
            "input_dataset_id": run.input_dataset_id,
            "input_dataset_revision_id": run.input_dataset_revision_id,
            "status": run.status.value,
            "input_point_count": run.input_point_count,
            "output_point_count": None,
            "removed_point_count": None,
            "result_artifact_id": None,
            "result_sha256": None,
            "output_dataset_id": None,
            "output_dataset_revision_id": None,
            "failure_code": None,
            "change_reason": run.change_reason,
            "started_at": run.started_at,
            "ended_at": None,
            "created_by": run.created_by,
            "request_id": run.request_id,
            "trace_id": run.trace_id,
        }
        try:
            with self._session(context, decision) as session:
                session.execute(sa.insert(shear_relaxation_run_table).values(**values))
        except (IntegrityError, DBAPIError) as error:
            raise ProcessingConflict("shear-relaxation Run pins were rejected") from error
        return run

    def _terminal(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        values: dict[str, object],
    ) -> ShearRelaxationProcessingRun:
        statement = (
            sa.update(shear_relaxation_run_table)
            .where(
                shear_relaxation_run_table.c.organization_id == context.organization_id,
                shear_relaxation_run_table.c.project_id == context.project_id,
                shear_relaxation_run_table.c.id == run_id,
                shear_relaxation_run_table.c.status == ProcessingRunStatus.EXECUTING.value,
            )
            .values(**values, ended_at=datetime.now(UTC))
            .returning(*shear_relaxation_run_table.c)
        )
        try:
            with self._session(context, decision) as session:
                row = session.execute(statement).mappings().one_or_none()
        except (IntegrityError, DBAPIError) as error:
            raise ProcessingConflict("shear-relaxation Run terminal state was rejected") from error
        if row is None:
            raise ProcessingConflict("shear-relaxation Run is no longer executing")
        return _run(row)

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        artifact: ArtifactRecord,
        output_dataset_id: UUID,
        output_dataset_revision_id: UUID,
        output_point_count: int,
        removed_point_count: int,
    ) -> ShearRelaxationProcessingRun:
        return self._terminal(
            context=context,
            decision=decision,
            run_id=run_id,
            values={
                "status": ProcessingRunStatus.SUCCEEDED.value,
                "result_artifact_id": artifact.artifact.id,
                "result_sha256": artifact.artifact.sha256,
                "output_dataset_id": output_dataset_id,
                "output_dataset_revision_id": output_dataset_revision_id,
                "output_point_count": output_point_count,
                "removed_point_count": removed_point_count,
                "failure_code": None,
            },
        )

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        artifact: ArtifactRecord | None,
        failure_code: str,
    ) -> ShearRelaxationProcessingRun:
        return self._terminal(
            context=context,
            decision=decision,
            run_id=run_id,
            values={
                "status": ProcessingRunStatus.FAILED.value,
                "result_artifact_id": artifact.artifact.id if artifact else None,
                "result_sha256": artifact.artifact.sha256 if artifact else None,
                "output_dataset_id": None,
                "output_dataset_revision_id": None,
                "output_point_count": None,
                "removed_point_count": None,
                "failure_code": failure_code,
            },
        )

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ShearRelaxationProcessingRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(shear_relaxation_run_table).where(
                        shear_relaxation_run_table.c.organization_id
                        == context.organization_id,
                        shear_relaxation_run_table.c.project_id == context.project_id,
                        shear_relaxation_run_table.c.id == run_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise ProcessingNotFound("shear-relaxation Run is not visible")
        return _run(row)
