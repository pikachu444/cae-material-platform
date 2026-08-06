"""PostgreSQL persistence for metal-specific Fit runs and candidate attempts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_outputs import (
    ExactRevisionPin,
    ProcessingOutputNotFound,
)
from cmp.modules.processing.application.metal_fit_runs import (
    MetalFitAttempt,
    MetalFitAttemptStatus,
    MetalFitRun,
    MetalFitRunRepository,
    MetalFitRunStatus,
    MetalFitTerminalConflict,
)


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


metadata = sa.MetaData()


def _json_value_or_sql_null(value: Any) -> Any:
    """Keep Python ``None`` as SQL NULL for nullable JSON/JSONB evidence."""

    return sa.null() if value is None else value


run_table = sa.Table(
    "metal_fit_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("source_processing_output_id", sa.Uuid(), nullable=False),
    sa.Column("source_processing_output_revision_id", sa.Uuid(), nullable=False),
    sa.Column("source_processing_output_sha256", sa.CHAR(64), nullable=False),
    sa.Column("source_document_id", sa.Uuid(), nullable=False),
    sa.Column("source_document_revision_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_profile_id", sa.Uuid(), nullable=False),
    sa.Column("mapping_profile_revision_id", sa.Uuid(), nullable=False),
    sa.Column("options", sa.JSON(), nullable=False),
    sa.Column("reproducibility_evidence", sa.JSON(), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("failure_code", sa.String(160), nullable=True),
    sa.Column("failure_reason", sa.Text(), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="processing",
)
attempt_table = sa.Table(
    "metal_fit_attempt",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("run_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("family", sa.String(64), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("result", sa.JSON(), nullable=True),
    sa.Column("objective_history", sa.JSON(), nullable=False),
    sa.Column("failure_code", sa.String(160), nullable=True),
    sa.Column("failure_reason", sa.Text(), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="processing",
)


def _run(row: Any) -> MetalFitRun:
    return MetalFitRun(
        id=cast(UUID, row["id"]),
        classification=DataClassification(str(row["classification"])),
        source_processing_output=ExactRevisionPin(
            cast(UUID, row["source_processing_output_id"]),
            cast(UUID, row["source_processing_output_revision_id"]),
        ),
        source_processing_output_sha256=str(row["source_processing_output_sha256"]),
        source_document=ExactRevisionPin(
            cast(UUID, row["source_document_id"]), cast(UUID, row["source_document_revision_id"])
        ),
        mapping_profile=ExactRevisionPin(
            cast(UUID, row["mapping_profile_id"]), cast(UUID, row["mapping_profile_revision_id"])
        ),
        options=dict(row["options"]),
        reproducibility_evidence=dict(row["reproducibility_evidence"]),
        status=MetalFitRunStatus(str(row["status"])),
        failure_code=row["failure_code"],
        failure_reason=row["failure_reason"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_at=row["created_at"],
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _attempt(row: Any) -> MetalFitAttempt:
    return MetalFitAttempt(
        id=cast(UUID, row["id"]),
        run_id=cast(UUID, row["run_id"]),
        ordinal=int(row["ordinal"]),
        family=str(row["family"]),
        status=MetalFitAttemptStatus(str(row["status"])),
        result=None if row["result"] is None else dict(row["result"]),
        objective_history=tuple(float(item) for item in (row["objective_history"] or [])),
        failure_code=row["failure_code"],
        failure_reason=row["failure_reason"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
    )


class SqlAlchemyMetalFitRunRepository(MetalFitRunRepository):
    def __init__(self, *, session_factory: sessionmaker[Session], rls_context: RlsContext) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    def _bind(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @contextmanager
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: MetalFitRun,
    ) -> MetalFitRun:
        with self._session(context, decision) as session:
            session.execute(
                sa.insert(run_table).values(
                    id=run.id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=run.classification.value,
                    source_processing_output_id=run.source_processing_output.aggregate_id,
                    source_processing_output_revision_id=run.source_processing_output.revision_id,
                    source_processing_output_sha256=run.source_processing_output_sha256,
                    source_document_id=run.source_document.aggregate_id,
                    source_document_revision_id=run.source_document.revision_id,
                    mapping_profile_id=run.mapping_profile.aggregate_id,
                    mapping_profile_revision_id=run.mapping_profile.revision_id,
                    options=run.options,
                    reproducibility_evidence=run.reproducibility_evidence,
                    status=run.status.value,
                    failure_code=run.failure_code,
                    failure_reason=run.failure_reason,
                    started_at=run.started_at,
                    ended_at=run.ended_at,
                    created_at=run.created_at,
                    created_by=run.created_by,
                    request_id=run.request_id,
                    trace_id=run.trace_id,
                )
            )
        return run

    def create_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt: MetalFitAttempt,
    ) -> MetalFitAttempt:
        with self._session(context, decision) as session:
            run = (
                session.execute(sa.select(run_table).where(run_table.c.id == attempt.run_id))
                .mappings()
                .one_or_none()
            )
            if run is None:
                raise ProcessingOutputNotFound("metal Fit run is not visible")
            session.execute(
                sa.insert(attempt_table).values(
                    id=attempt.id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=run["classification"],
                    run_id=attempt.run_id,
                    ordinal=attempt.ordinal,
                    family=attempt.family,
                    status=attempt.status.value,
                    result=_json_value_or_sql_null(attempt.result),
                    objective_history=list(attempt.objective_history),
                    failure_code=attempt.failure_code,
                    failure_reason=attempt.failure_reason,
                    started_at=attempt.started_at,
                    ended_at=attempt.ended_at,
                    created_at=attempt.started_at,
                    created_by=context.principal.id,
                )
            )
        return attempt

    def _update_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        **values: Any,
    ) -> MetalFitAttempt:
        if "result" in values:
            values["result"] = _json_value_or_sql_null(values["result"])
        with self._session(context, decision) as session:
            changed = cast(
                CursorResult[Any],
                session.execute(
                    sa.update(attempt_table)
                    .where(
                        attempt_table.c.id == attempt_id,
                        attempt_table.c.status == MetalFitAttemptStatus.EXECUTING.value,
                    )
                    .values(**values)
                ),
            )
            row = (
                session.execute(sa.select(attempt_table).where(attempt_table.c.id == attempt_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProcessingOutputNotFound("metal Fit attempt is not visible")
            if changed.rowcount != 1:
                raise MetalFitTerminalConflict(
                    "metal Fit attempt is immutable after its terminal transition"
                )
            return _attempt(row)

    def succeed_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        result: dict[str, Any],
        objective_history: tuple[float, ...] = (),
    ) -> MetalFitAttempt:
        return self._update_attempt(
            context=context,
            decision=decision,
            attempt_id=attempt_id,
            status=MetalFitAttemptStatus.SUCCEEDED.value,
            result=result,
            objective_history=list(objective_history),
            ended_at=datetime.now(UTC),
        )

    def fail_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        attempt_id: UUID,
        failure_code: str,
        failure_reason: str,
        result: dict[str, Any] | None = None,
        objective_history: tuple[float, ...] = (),
    ) -> MetalFitAttempt:
        return self._update_attempt(
            context=context,
            decision=decision,
            attempt_id=attempt_id,
            status=MetalFitAttemptStatus.FAILED.value,
            failure_code=failure_code,
            failure_reason=failure_reason,
            result=result,
            objective_history=list(objective_history),
            ended_at=datetime.now(UTC),
        )

    def _update_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        **values: Any,
    ) -> MetalFitRun:
        with self._session(context, decision) as session:
            changed = cast(
                CursorResult[Any],
                session.execute(
                    sa.update(run_table)
                    .where(
                        run_table.c.id == run_id,
                        run_table.c.status == MetalFitRunStatus.EXECUTING.value,
                    )
                    .values(**values)
                ),
            )
            row = (
                session.execute(sa.select(run_table).where(run_table.c.id == run_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProcessingOutputNotFound("metal Fit run is not visible")
            if changed.rowcount != 1:
                raise MetalFitTerminalConflict(
                    "metal Fit run is immutable after its terminal transition"
                )
            return _run(row)

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        reproducibility_evidence: dict[str, Any],
    ) -> MetalFitRun:
        return self._update_run(
            context=context,
            decision=decision,
            run_id=run_id,
            status=MetalFitRunStatus.SUCCEEDED.value,
            reproducibility_evidence=reproducibility_evidence,
            ended_at=datetime.now(UTC),
        )

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
        failure_reason: str,
    ) -> MetalFitRun:
        return self._update_run(
            context=context,
            decision=decision,
            run_id=run_id,
            status=MetalFitRunStatus.FAILED.value,
            failure_code=failure_code,
            failure_reason=failure_reason,
            ended_at=datetime.now(UTC),
        )

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> MetalFitRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(sa.select(run_table).where(run_table.c.id == run_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProcessingOutputNotFound("metal Fit run is not visible")
            return _run(row)

    def list_runs(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[MetalFitRun, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(sa.select(run_table).order_by(run_table.c.created_at.desc()))
                .mappings()
                .all()
            )
            return tuple(_run(row) for row in rows)

    def list_attempts(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> tuple[MetalFitAttempt, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(attempt_table)
                    .where(attempt_table.c.run_id == run_id)
                    .order_by(attempt_table.c.ordinal)
                )
                .mappings()
                .all()
            )
            return tuple(_attempt(row) for row in rows)
