"""RLS-bound PostgreSQL persistence for typed Processing recipes and committed runs."""

from __future__ import annotations

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
from cmp.modules.processing.application.service import (
    PROCESSING_RECIPE_AGGREGATE_TYPE,
    ImportRun,
    ProcessingRecipeContent,
    ProcessingRecipeSnapshot,
    ProcessingRepository,
    ProcessingRun,
    RevisionSnapshot,
)
from cmp.modules.processing.domain.reference_import import (
    REFERENCE_IMPORT_EXECUTION_MODE,
    REFERENCE_IMPORT_RUN_KIND,
    ImportRunStatus,
)
from cmp.modules.processing.domain.reference_tensile_alignment import (
    REFERENCE_TENSILE_ALIGNMENT_DIAGNOSTICS_SCHEMA,
    REFERENCE_TENSILE_ALIGNMENT_RECIPE_KIND,
    AlignmentDomainPolicy,
    AlignmentExtrapolationPolicy,
    AlignmentInterpolationPolicy,
    ReferenceTensileAlignmentRecipeContent,
    reference_tensile_alignment_canonical,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    REFERENCE_TENSILE_CROP_DIAGNOSTICS_SCHEMA,
    REFERENCE_TENSILE_CROP_RECIPE_KIND,
    REFERENCE_TENSILE_CROP_SCHEMA_PAIRS,
    ProcessingConflict,
    ProcessingNotFound,
    ProcessingRunStatus,
    ReferenceTensileCropRecipeContent,
    reference_tensile_crop_canonical,
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
processing_recipe_table = sa.Table(
    "processing_recipe",
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
processing_recipe_revision_table = sa.Table(
    "processing_recipe_revision",
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
    sa.Column("minimum_engineering_strain", sa.Double(), nullable=True),
    sa.Column("maximum_engineering_strain", sa.Double(), nullable=True),
    sa.Column("input_schema_ref", sa.String(500), nullable=False),
    sa.Column("output_schema_ref", sa.String(500), nullable=False),
    sa.Column("diagnostics_schema_ref", sa.String(500), nullable=False),
    sa.Column("grid_start_engineering_strain", sa.Double(), nullable=True),
    sa.Column("grid_end_engineering_strain", sa.Double(), nullable=True),
    sa.Column("grid_point_count", sa.BigInteger(), nullable=True),
    sa.Column("domain_policy", sa.String(32), nullable=True),
    sa.Column("interpolation_policy", sa.String(32), nullable=True),
    sa.Column("extrapolation_policy", sa.String(32), nullable=True),
    schema="processing",
)
processing_run_table = sa.Table(
    "processing_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("recipe_id", sa.Uuid(), nullable=False),
    sa.Column("recipe_revision_id", sa.Uuid(), nullable=False),
    sa.Column("input_dataset_id", sa.Uuid(), nullable=False),
    sa.Column("input_dataset_revision_id", sa.Uuid(), nullable=False),
    sa.Column("execution_mode", sa.String(16), nullable=False),
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
    sa.Column("run_kind", sa.String(100), nullable=False),
    sa.Column("batch_id", sa.Uuid(), nullable=True),
    sa.Column("member_ordinal", sa.SmallInteger(), nullable=True),
    schema="processing",
)
import_run_table = sa.Table(
    "import_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("import_kind", sa.String(100), nullable=False),
    sa.Column("execution_mode", sa.String(32), nullable=False),
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=False),
    sa.Column("raw_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("import_mapping_id", sa.Uuid(), nullable=False),
    sa.Column("import_mapping_revision_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_sha256", sa.CHAR(64), nullable=False),
    sa.Column("importer_id", sa.String(255), nullable=False),
    sa.Column("importer_version", sa.String(64), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
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
        aggregate_type=PROCESSING_RECIPE_AGGREGATE_TYPE,
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


def _content(row: Any) -> ProcessingRecipeContent:
    kind = str(row["recipe_kind"])
    if (
        int(row["step_ordinal"]) != 0
        or (
            str(row["input_schema_ref"]),
            str(row["output_schema_ref"]),
        )
        not in REFERENCE_TENSILE_CROP_SCHEMA_PAIRS
    ):
        raise ProcessingConflict("Processing Recipe revision violates its typed contract")
    if kind == REFERENCE_TENSILE_CROP_RECIPE_KIND:
        if str(row["diagnostics_schema_ref"]) != REFERENCE_TENSILE_CROP_DIAGNOSTICS_SCHEMA:
            raise ProcessingConflict("Processing Recipe violates the reference crop contract")
        return ReferenceTensileCropRecipeContent(
            recipe_label=str(row["recipe_label"]),
            minimum_engineering_strain=float(row["minimum_engineering_strain"]),
            maximum_engineering_strain=float(row["maximum_engineering_strain"]),
            input_schema_ref=str(row["input_schema_ref"]),
            output_schema_ref=str(row["output_schema_ref"]),
        )
    if kind == REFERENCE_TENSILE_ALIGNMENT_RECIPE_KIND:
        if str(row["diagnostics_schema_ref"]) != REFERENCE_TENSILE_ALIGNMENT_DIAGNOSTICS_SCHEMA:
            raise ProcessingConflict("Processing Recipe violates the alignment contract")
        return ReferenceTensileAlignmentRecipeContent(
            recipe_label=str(row["recipe_label"]),
            grid_start_engineering_strain=float(row["grid_start_engineering_strain"]),
            grid_end_engineering_strain=float(row["grid_end_engineering_strain"]),
            grid_point_count=int(row["grid_point_count"]),
            domain_policy=AlignmentDomainPolicy(str(row["domain_policy"])),
            interpolation_policy=AlignmentInterpolationPolicy(
                str(row["interpolation_policy"])
            ),
            extrapolation_policy=AlignmentExtrapolationPolicy(
                str(row["extrapolation_policy"])
            ),
            input_schema_ref=str(row["input_schema_ref"]),
            output_schema_ref=str(row["output_schema_ref"]),
        )
    raise ProcessingConflict("Processing Recipe kind is unsupported")


def _values(value: ProcessingRecipeContent) -> dict[str, object]:
    common: dict[str, object] = {
        "step_ordinal": 0,
        "input_schema_ref": value.input_schema_ref,
        "output_schema_ref": value.output_schema_ref,
        "minimum_engineering_strain": None,
        "maximum_engineering_strain": None,
        "grid_start_engineering_strain": None,
        "grid_end_engineering_strain": None,
        "grid_point_count": None,
        "domain_policy": None,
        "interpolation_policy": None,
        "extrapolation_policy": None,
    }
    if isinstance(value, ReferenceTensileCropRecipeContent):
        return common | {
            "recipe_kind": REFERENCE_TENSILE_CROP_RECIPE_KIND,
            "minimum_engineering_strain": value.minimum_engineering_strain,
            "maximum_engineering_strain": value.maximum_engineering_strain,
            "diagnostics_schema_ref": REFERENCE_TENSILE_CROP_DIAGNOSTICS_SCHEMA,
        }
    return common | {
        "recipe_kind": REFERENCE_TENSILE_ALIGNMENT_RECIPE_KIND,
        "grid_start_engineering_strain": value.grid_start_engineering_strain,
        "grid_end_engineering_strain": value.grid_end_engineering_strain,
        "grid_point_count": value.grid_point_count,
        "domain_policy": value.domain_policy.value,
        "interpolation_policy": value.interpolation_policy.value,
        "extrapolation_policy": value.extrapolation_policy.value,
        "diagnostics_schema_ref": REFERENCE_TENSILE_ALIGNMENT_DIAGNOSTICS_SCHEMA,
    }


def _canonical(value: ProcessingRecipeContent) -> dict[str, object]:
    if isinstance(value, ReferenceTensileCropRecipeContent):
        return reference_tensile_crop_canonical(value)
    return reference_tensile_alignment_canonical(value)


def _kind(value: ProcessingRecipeContent) -> str:
    if isinstance(value, ReferenceTensileCropRecipeContent):
        return REFERENCE_TENSILE_CROP_RECIPE_KIND
    return REFERENCE_TENSILE_ALIGNMENT_RECIPE_KIND


_TABLES: TypedRevisionTables[ProcessingRecipeContent] = TypedRevisionTables(
    aggregate_type=PROCESSING_RECIPE_AGGREGATE_TYPE,
    identity_table=processing_recipe_table,
    revision_table=processing_recipe_revision_table,
    canonical_content=_canonical,
    content_values=_values,
    identity_values=lambda value: {
        "recipe_label": value.recipe_label,
        "recipe_kind": _kind(value),
    },
)


def _revision_columns(table: sa.Table) -> tuple[Any, ...]:
    return tuple(
        table.c[name].label(name)
        for name in (
            "id",
            "aggregate_id",
            "organization_id",
            "project_id",
            "classification",
            "revision_no",
            "based_on_revision_id",
            "schema_id",
            "schema_version",
            "content_hash",
            "created_at",
            "created_by",
            "change_reason",
            "request_id",
            "trace_id",
        )
    )


def _run(row: Any) -> ProcessingRun:
    return ProcessingRun(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        recipe_id=cast(UUID, row["recipe_id"]),
        recipe_revision_id=cast(UUID, row["recipe_revision_id"]),
        input_dataset_id=cast(UUID, row["input_dataset_id"]),
        input_dataset_revision_id=cast(UUID, row["input_dataset_revision_id"]),
        status=ProcessingRunStatus(str(row["status"])),
        input_point_count=int(row["input_point_count"]),
        output_point_count=(
            int(row["output_point_count"]) if row["output_point_count"] is not None else None
        ),
        removed_point_count=(
            int(row["removed_point_count"])
            if row["removed_point_count"] is not None
            else None
        ),
        result_artifact_id=cast(UUID | None, row["result_artifact_id"]),
        result_sha256=cast(str | None, row["result_sha256"]),
        output_dataset_id=cast(UUID | None, row["output_dataset_id"]),
        output_dataset_revision_id=cast(UUID | None, row["output_dataset_revision_id"]),
        failure_code=cast(str | None, row["failure_code"]),
        change_reason=str(row["change_reason"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
        run_kind=str(row["run_kind"]),
        batch_id=cast(UUID | None, row["batch_id"]),
        member_ordinal=(
            int(row["member_ordinal"]) if row["member_ordinal"] is not None else None
        ),
    )


def _import_run(row: Any) -> ImportRun:
    if (
        str(row["import_kind"]) != REFERENCE_IMPORT_RUN_KIND
        or str(row["execution_mode"]) != REFERENCE_IMPORT_EXECUTION_MODE
    ):
        raise ProcessingConflict("Import Run violates the reference orchestration contract")
    return ImportRun(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        test_run_id=cast(UUID, row["test_run_id"]),
        test_run_revision_id=cast(UUID, row["test_run_revision_id"]),
        raw_asset_id=cast(UUID, row["raw_asset_id"]),
        raw_artifact_id=cast(UUID, row["raw_artifact_id"]),
        import_mapping_id=cast(UUID, row["import_mapping_id"]),
        import_mapping_revision_id=cast(UUID, row["import_mapping_revision_id"]),
        mapping_sha256=str(row["mapping_sha256"]),
        importer_id=str(row["importer_id"]),
        importer_version=str(row["importer_version"]),
        status=ImportRunStatus(str(row["status"])),
        output_dataset_id=cast(UUID | None, row["output_dataset_id"]),
        output_dataset_revision_id=cast(UUID | None, row["output_dataset_revision_id"]),
        failure_code=cast(str | None, row["failure_code"]),
        change_reason=str(row["change_reason"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


class SqlAlchemyProcessingRepository(ProcessingRepository):
    """Explicit Processing tables; only the Dataset module writes Dataset rows."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        revision_hooks: tuple[SqlRevisionHook, ...] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = revision_hooks

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
    ) -> RevisionStore[ProcessingRecipeContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _current_recipe_statement() -> sa.Select[Any]:
        identity = processing_recipe_table
        revision = processing_recipe_revision_table
        return sa.select(
            identity.c.id.label("identity_id"),
            identity.c.recipe_label,
            *_revision_columns(revision),
            revision.c.recipe_kind,
            revision.c.step_ordinal,
            revision.c.minimum_engineering_strain,
            revision.c.maximum_engineering_strain,
            revision.c.input_schema_ref,
            revision.c.output_schema_ref,
            revision.c.diagnostics_schema_ref,
            revision.c.grid_start_engineering_strain,
            revision.c.grid_end_engineering_strain,
            revision.c.grid_point_count,
            revision.c.domain_policy,
            revision.c.interpolation_policy,
            revision.c.extrapolation_policy,
        ).select_from(
            identity.join(
                revision,
                sa.and_(
                    revision.c.id == identity.c.current_revision_id,
                    revision.c.aggregate_id == identity.c.id,
                    revision.c.organization_id == identity.c.organization_id,
                    revision.c.project_id == identity.c.project_id,
                ),
            )
        )

    @staticmethod
    def _recipe_snapshot(row: Any) -> ProcessingRecipeSnapshot:
        return ProcessingRecipeSnapshot(
            id=cast(UUID, row["identity_id"]),
            current=RevisionSnapshot(_record(row), _content(row)),
        )

    def get_recipe(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
    ) -> ProcessingRecipeSnapshot:
        statement = self._current_recipe_statement().where(
            processing_recipe_table.c.organization_id == context.organization_id,
            processing_recipe_table.c.project_id == context.project_id,
            processing_recipe_table.c.id == recipe_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise ProcessingNotFound("Processing Recipe is not visible in the selected tenant")
        return self._recipe_snapshot(row)

    def get_recipe_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        recipe_id: UUID,
        recipe_revision_id: UUID,
    ) -> RevisionSnapshot[ProcessingRecipeContent]:
        identity = processing_recipe_table
        revision = processing_recipe_revision_table
        statement = sa.select(
            identity.c.recipe_label,
            *_revision_columns(revision),
            revision.c.recipe_kind,
            revision.c.step_ordinal,
            revision.c.minimum_engineering_strain,
            revision.c.maximum_engineering_strain,
            revision.c.input_schema_ref,
            revision.c.output_schema_ref,
            revision.c.diagnostics_schema_ref,
            revision.c.grid_start_engineering_strain,
            revision.c.grid_end_engineering_strain,
            revision.c.grid_point_count,
            revision.c.domain_policy,
            revision.c.interpolation_policy,
            revision.c.extrapolation_policy,
        ).select_from(
            identity.join(
                revision,
                sa.and_(
                    revision.c.aggregate_id == identity.c.id,
                    revision.c.organization_id == identity.c.organization_id,
                    revision.c.project_id == identity.c.project_id,
                ),
            )
        ).where(
            identity.c.organization_id == context.organization_id,
            identity.c.project_id == context.project_id,
            identity.c.id == recipe_id,
            revision.c.id == recipe_revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise ProcessingNotFound(
                "Processing Recipe revision is not visible in the selected tenant"
            )
        return RevisionSnapshot(_record(row), _content(row))

    def list_recipes(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ProcessingRecipeSnapshot, ...]:
        statement = self._current_recipe_statement().where(
            processing_recipe_table.c.organization_id == context.organization_id,
            processing_recipe_table.c.project_id == context.project_id,
        ).order_by(processing_recipe_table.c.created_at.desc()).limit(limit)
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
        return tuple(self._recipe_snapshot(row) for row in rows)

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ProcessingRun,
    ) -> ProcessingRun:
        values = {
            "id": run.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
            "selection_id": run.selection_id,
            "selection_revision_id": run.selection_revision_id,
            "recipe_id": run.recipe_id,
            "recipe_revision_id": run.recipe_revision_id,
            "input_dataset_id": run.input_dataset_id,
            "input_dataset_revision_id": run.input_dataset_revision_id,
            "execution_mode": "committed",
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
            "run_kind": run.run_kind,
            "batch_id": run.batch_id,
            "member_ordinal": run.member_ordinal,
        }
        try:
            with self._session(context, decision) as session:
                session.execute(sa.insert(processing_run_table).values(**values))
        except (IntegrityError, DBAPIError) as error:
            raise ProcessingConflict(
                "Processing Run cannot be created for these pinned inputs"
            ) from error
        return run

    @staticmethod
    def _terminal_values(
        *,
        status: ProcessingRunStatus,
        artifact: ArtifactRecord | None,
        output_dataset_id: UUID | None,
        output_dataset_revision_id: UUID | None,
        output_point_count: int | None,
        removed_point_count: int | None,
        failure_code: str | None,
    ) -> dict[str, object]:
        return {
            "status": status.value,
            "result_artifact_id": artifact.artifact.id if artifact is not None else None,
            "result_sha256": artifact.artifact.sha256 if artifact is not None else None,
            "output_dataset_id": output_dataset_id,
            "output_dataset_revision_id": output_dataset_revision_id,
            "output_point_count": output_point_count,
            "removed_point_count": removed_point_count,
            "failure_code": failure_code,
            "ended_at": datetime.now(UTC),
        }

    def _terminal_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        values: dict[str, object],
    ) -> ProcessingRun:
        statement = (
            sa.update(processing_run_table)
            .where(
                processing_run_table.c.organization_id == context.organization_id,
                processing_run_table.c.project_id == context.project_id,
                processing_run_table.c.id == run_id,
                processing_run_table.c.status == ProcessingRunStatus.EXECUTING.value,
            )
            .values(**values)
            .returning(*processing_run_table.c)
        )
        try:
            with self._session(context, decision) as session:
                row = session.execute(statement).mappings().one_or_none()
        except (IntegrityError, DBAPIError) as error:
            raise ProcessingConflict("Processing Run terminal state was rejected") from error
        if row is None:
            raise ProcessingConflict("Processing Run is no longer executing")
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
        removed_point_count: int | None,
    ) -> ProcessingRun:
        return self._terminal_run(
            context=context,
            decision=decision,
            run_id=run_id,
            values=self._terminal_values(
                status=ProcessingRunStatus.SUCCEEDED,
                artifact=artifact,
                output_dataset_id=output_dataset_id,
                output_dataset_revision_id=output_dataset_revision_id,
                output_point_count=output_point_count,
                removed_point_count=removed_point_count,
                failure_code=None,
            ),
        )

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        artifact: ArtifactRecord | None,
        failure_code: str,
    ) -> ProcessingRun:
        return self._terminal_run(
            context=context,
            decision=decision,
            run_id=run_id,
            values=self._terminal_values(
                status=ProcessingRunStatus.FAILED,
                artifact=artifact,
                output_dataset_id=None,
                output_dataset_revision_id=None,
                output_point_count=None,
                removed_point_count=None,
                failure_code=failure_code,
            ),
        )

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ProcessingRun:
        statement = sa.select(processing_run_table).where(
            processing_run_table.c.organization_id == context.organization_id,
            processing_run_table.c.project_id == context.project_id,
            processing_run_table.c.id == run_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise ProcessingNotFound("Processing Run is not visible in the selected tenant")
        return _run(row)

    def create_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ImportRun,
    ) -> ImportRun:
        values = {
            "id": run.id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": run.classification.value,
            "import_kind": REFERENCE_IMPORT_RUN_KIND,
            "execution_mode": REFERENCE_IMPORT_EXECUTION_MODE,
            "test_run_id": run.test_run_id,
            "test_run_revision_id": run.test_run_revision_id,
            "raw_asset_id": run.raw_asset_id,
            "raw_artifact_id": run.raw_artifact_id,
            "import_mapping_id": run.import_mapping_id,
            "import_mapping_revision_id": run.import_mapping_revision_id,
            "mapping_sha256": run.mapping_sha256,
            "importer_id": run.importer_id,
            "importer_version": run.importer_version,
            "status": run.status.value,
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
                session.execute(sa.insert(import_run_table).values(**values))
        except (IntegrityError, DBAPIError) as error:
            raise ProcessingConflict(
                "Import Run cannot be created for these pinned inputs"
            ) from error
        return run

    def _terminal_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        status: ImportRunStatus,
        output_dataset_id: UUID | None,
        output_dataset_revision_id: UUID | None,
        failure_code: str | None,
    ) -> ImportRun:
        statement = (
            sa.update(import_run_table)
            .where(
                import_run_table.c.organization_id == context.organization_id,
                import_run_table.c.project_id == context.project_id,
                import_run_table.c.id == run_id,
                import_run_table.c.status == ImportRunStatus.EXECUTING.value,
            )
            .values(
                status=status.value,
                output_dataset_id=output_dataset_id,
                output_dataset_revision_id=output_dataset_revision_id,
                failure_code=failure_code,
                ended_at=datetime.now(UTC),
            )
            .returning(*import_run_table.c)
        )
        try:
            with self._session(context, decision) as session:
                row = session.execute(statement).mappings().one_or_none()
        except (IntegrityError, DBAPIError) as error:
            raise ProcessingConflict("Import Run terminal state was rejected") from error
        if row is None:
            raise ProcessingConflict("Import Run is no longer executing")
        return _import_run(row)

    def succeed_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        output_dataset_id: UUID,
        output_dataset_revision_id: UUID,
    ) -> ImportRun:
        return self._terminal_import_run(
            context=context,
            decision=decision,
            run_id=run_id,
            status=ImportRunStatus.SUCCEEDED,
            output_dataset_id=output_dataset_id,
            output_dataset_revision_id=output_dataset_revision_id,
            failure_code=None,
        )

    def fail_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> ImportRun:
        return self._terminal_import_run(
            context=context,
            decision=decision,
            run_id=run_id,
            status=ImportRunStatus.FAILED,
            output_dataset_id=None,
            output_dataset_revision_id=None,
            failure_code=failure_code,
        )

    def get_import_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ImportRun:
        statement = sa.select(import_run_table).where(
            import_run_table.c.organization_id == context.organization_id,
            import_run_table.c.project_id == context.project_id,
            import_run_table.c.id == run_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise ProcessingNotFound("Import Run is not visible in the selected tenant")
        return _import_run(row)
