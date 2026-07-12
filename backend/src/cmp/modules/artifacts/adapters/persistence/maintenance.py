"""PostgreSQL T-16 reconciliation schedule, run history, and cleanup receipts."""

from datetime import datetime, timedelta
from typing import Protocol, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.artifacts.application.content import ReconciliationResult
from cmp.modules.artifacts.application.maintenance import (
    ReconciliationLease,
    StagingCleanupCandidate,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext

metadata = sa.MetaData()
uuid_type = postgresql.UUID(as_uuid=True)

schedule_table = sa.Table(
    "reconciliation_schedule",
    metadata,
    *(sa.Column(name, uuid_type) for name in ("organization_id", "project_id")),
    sa.Column("classification", sa.String()),
    sa.Column("id", uuid_type),
    sa.Column("interval_seconds", sa.Integer()),
    sa.Column("retention_seconds", sa.Integer()),
    sa.Column("next_run_at", sa.DateTime(timezone=True)),
    sa.Column("enabled", sa.Boolean()),
    sa.Column("lease_token", uuid_type),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
    sa.Column("current_run_id", uuid_type),
    sa.Column("failure_count", sa.Integer()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", uuid_type),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    schema="artifact",
)
run_table = sa.Table(
    "reconciliation_run",
    metadata,
    *(sa.Column(name, uuid_type) for name in ("organization_id", "project_id")),
    sa.Column("classification", sa.String()),
    sa.Column("id", uuid_type),
    sa.Column("schedule_id", uuid_type),
    sa.Column("lease_token", uuid_type),
    sa.Column("state", sa.String()),
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
    sa.Column("artifacts_checked", sa.Integer()),
    sa.Column("pending_recovered", sa.Integer()),
    sa.Column("issues_recorded", sa.Integer()),
    sa.Column("staging_cleaned", sa.Integer()),
    sa.Column("failure_code", sa.String()),
    sa.Column("executed_by", uuid_type),
    sa.Column("request_id", uuid_type),
    sa.Column("trace_id", sa.String()),
    schema="artifact",
)
cleanup_table = sa.Table(
    "staging_cleanup",
    metadata,
    *(sa.Column(name, uuid_type) for name in ("organization_id", "project_id")),
    sa.Column("classification", sa.String()),
    sa.Column("pending_artifact_id", uuid_type),
    sa.Column("staging_object_key", sa.String()),
    sa.Column("cleaned_at", sa.DateTime(timezone=True)),
    sa.Column("cleaned_by", uuid_type),
    sa.Column("run_id", uuid_type),
    schema="artifact",
)


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


class SqlAlchemyArtifactMaintenanceRepository:
    def __init__(self, *, session_factory: sessionmaker[Session], rls_context: RlsContext) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    def _bind(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    def ensure_schedule(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        interval: timedelta,
        retention: timedelta,
        now: datetime,
    ) -> UUID:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            identifier = uuid4()
            inserted = session.execute(
                postgresql.insert(schedule_table)
                .values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=classification.value,
                    id=identifier,
                    interval_seconds=int(interval.total_seconds()),
                    retention_seconds=int(retention.total_seconds()),
                    next_run_at=now,
                    enabled=True,
                    lease_token=None,
                    lease_expires_at=None,
                    current_run_id=None,
                    failure_count=0,
                    created_at=now,
                    created_by=context.principal.id,
                    updated_at=now,
                )
                .on_conflict_do_nothing()
                .returning(schedule_table.c.id)
            ).scalar_one_or_none()
            if inserted is not None:
                return cast(UUID, inserted)
            existing = (
                session.execute(
                    sa.select(schedule_table).where(
                        schedule_table.c.organization_id == context.organization_id,
                        schedule_table.c.project_id == context.project_id,
                        schedule_table.c.classification == classification.value,
                    )
                )
                .mappings()
                .one()
            )
            if int(existing["interval_seconds"]) != int(interval.total_seconds()) or int(
                existing["retention_seconds"]
            ) != int(retention.total_seconds()):
                raise ValueError("reconciliation schedule policy conflicts with existing state")
            return cast(UUID, existing["id"])

    def claim(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        lease_duration: timedelta,
        now: datetime,
    ) -> ReconciliationLease | None:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = (
                session.execute(
                    sa.select(schedule_table)
                    .where(
                        schedule_table.c.organization_id == context.organization_id,
                        schedule_table.c.project_id == context.project_id,
                        schedule_table.c.enabled.is_(True),
                        sa.or_(
                            sa.and_(
                                schedule_table.c.lease_token.is_(None),
                                schedule_table.c.next_run_at <= now,
                            ),
                            schedule_table.c.lease_expires_at <= now,
                        ),
                    )
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            if row["current_run_id"] is not None:
                session.execute(
                    sa.update(run_table)
                    .where(run_table.c.id == row["current_run_id"], run_table.c.state == "running")
                    .values(state="timed_out", finished_at=now, failure_code="lease_expired")
                )
            run_id, token = uuid4(), uuid4()
            expires = now + lease_duration
            session.execute(
                sa.insert(run_table).values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=row["classification"],
                    id=run_id,
                    schedule_id=row["id"],
                    lease_token=token,
                    state="running",
                    started_at=now,
                    finished_at=None,
                    artifacts_checked=None,
                    pending_recovered=None,
                    issues_recorded=None,
                    staging_cleaned=None,
                    failure_code=None,
                    executed_by=context.principal.id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            session.execute(
                sa.update(schedule_table)
                .where(schedule_table.c.id == row["id"])
                .values(
                    lease_token=token,
                    lease_expires_at=expires,
                    current_run_id=run_id,
                    updated_at=now,
                )
            )
            return ReconciliationLease(
                row["id"],
                run_id,
                token,
                expires,
                timedelta(seconds=row["retention_seconds"]),
                DataClassification(str(row["classification"])),
            )

    def cleanup_candidates(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        cutoff: datetime,
        limit: int,
    ) -> tuple[StagingCleanupCandidate, ...]:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            rows = session.execute(
                sa.text("""
                SELECT pending.id, pending.staging_object_key
                FROM artifact.artifact_pending AS pending
                LEFT JOIN artifact.staging_cleanup AS cleanup
                  ON cleanup.organization_id = pending.organization_id
                 AND cleanup.project_id = pending.project_id
                 AND cleanup.pending_artifact_id = pending.id
                WHERE pending.organization_id = :organization_id
                  AND pending.project_id = :project_id
                  AND pending.classification = :classification
                  AND pending.state IN ('available', 'rejected')
                  AND pending.terminal_at <= :cutoff
                  AND pending.staging_object_key <> pending.final_object_key
                  AND cleanup.pending_artifact_id IS NULL
                ORDER BY pending.terminal_at, pending.id LIMIT :limit
            """),
                {
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                    "classification": classification.value,
                    "cutoff": cutoff,
                    "limit": limit,
                },
            ).mappings()
            return tuple(
                StagingCleanupCandidate(cast(UUID, row["id"]), str(row["staging_object_key"]))
                for row in rows
            )

    def record_cleanup(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        lease: ReconciliationLease,
        candidate: StagingCleanupCandidate,
        cleaned_at: datetime,
    ) -> bool:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            active = session.scalar(
                sa.select(schedule_table.c.id).where(
                    schedule_table.c.id == lease.schedule_id,
                    schedule_table.c.lease_token == lease.lease_token,
                )
            )
            if active is None:
                raise RuntimeError("reconciliation lease was lost")
            inserted = session.execute(
                postgresql.insert(cleanup_table)
                .values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=lease.classification.value,
                    pending_artifact_id=candidate.pending_artifact_id,
                    staging_object_key=candidate.staging_object_key,
                    cleaned_at=cleaned_at,
                    cleaned_by=context.principal.id,
                    run_id=lease.run_id,
                )
                .on_conflict_do_nothing()
                .returning(cleanup_table.c.pending_artifact_id)
            ).scalar_one_or_none()
            return inserted is not None

    def complete(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        lease: ReconciliationLease,
        result: ReconciliationResult,
        staging_cleaned: int,
        now: datetime,
    ) -> None:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = (
                session.execute(
                    sa.select(schedule_table)
                    .where(
                        schedule_table.c.id == lease.schedule_id,
                        schedule_table.c.lease_token == lease.lease_token,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise RuntimeError("reconciliation lease was lost")
            updated = session.execute(
                sa.update(schedule_table)
                .where(
                    schedule_table.c.id == lease.schedule_id,
                    schedule_table.c.lease_token == lease.lease_token,
                )
                .values(
                    lease_token=None,
                    lease_expires_at=None,
                    current_run_id=None,
                    next_run_at=now + timedelta(seconds=int(row["interval_seconds"])),
                    failure_count=0,
                    updated_at=now,
                )
            )
            if getattr(updated, "rowcount", None) != 1:
                raise RuntimeError("reconciliation lease was lost")
            session.execute(
                sa.update(run_table)
                .where(
                    run_table.c.id == lease.run_id,
                    run_table.c.lease_token == lease.lease_token,
                    run_table.c.state == "running",
                )
                .values(
                    state="succeeded",
                    finished_at=now,
                    artifacts_checked=result.artifacts_checked,
                    pending_recovered=result.pending_recovered,
                    issues_recorded=result.issues_recorded,
                    staging_cleaned=staging_cleaned,
                )
            )

    def fail(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        lease: ReconciliationLease,
        failure_code: str,
        now: datetime,
    ) -> None:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = (
                session.execute(
                    sa.select(schedule_table)
                    .where(
                        schedule_table.c.id == lease.schedule_id,
                        schedule_table.c.lease_token == lease.lease_token,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return
            session.execute(
                sa.update(run_table)
                .where(run_table.c.id == lease.run_id, run_table.c.state == "running")
                .values(state="failed", finished_at=now, failure_code=failure_code)
            )
            session.execute(
                sa.update(schedule_table)
                .where(schedule_table.c.id == lease.schedule_id)
                .values(
                    lease_token=None,
                    lease_expires_at=None,
                    current_run_id=None,
                    next_run_at=now
                    + timedelta(seconds=min(3600, 60 * (2 ** min(int(row["failure_count"]), 6)))),
                    failure_count=int(row["failure_count"]) + 1,
                    updated_at=now,
                )
            )
