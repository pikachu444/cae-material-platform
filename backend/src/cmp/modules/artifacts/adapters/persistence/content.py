"""RLS-bound PostgreSQL implementation of the T-10 Artifact repository."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.artifacts.application.content import ArtifactCommitHook, FinalizedArtifact
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactConflict,
    ArtifactKind,
    ArtifactNotFound,
    ArtifactRecord,
    ArtifactStateError,
    IntegrityCheckKind,
    IntegrityObservation,
    IntegrityStatus,
    PendingArtifact,
    PendingArtifactState,
    ReconciliationIssue,
    ReconciliationIssueType,
    StoredObject,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext

metadata = sa.MetaData()
uuid_type = postgresql.UUID(as_uuid=True)

artifact_pending_table = sa.Table(
    "artifact_pending",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("artifact_kind", sa.String(32), nullable=False),
    sa.Column("artifact_role", sa.String(100), nullable=False),
    sa.Column("schema_ref", sa.String(500), nullable=True),
    sa.Column("media_type", sa.String(255), nullable=False),
    sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("expected_sha256", sa.CHAR(64), nullable=False),
    sa.Column("staging_object_key", sa.String(1024), nullable=False),
    sa.Column("final_object_key", sa.String(1024), nullable=False),
    sa.Column("encryption_profile", sa.String(255), nullable=False),
    sa.Column("source_raw_asset_id", uuid_type, nullable=True),
    sa.Column("idempotency_key", sa.String(255), nullable=False),
    sa.Column("submission_digest", sa.CHAR(64), nullable=False),
    sa.Column("reserved_artifact_id", uuid_type, nullable=False),
    sa.Column("available_artifact_id", uuid_type, nullable=True),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", uuid_type, nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
    schema="artifact",
)

artifact_table = sa.Table(
    "artifact",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("artifact_kind", sa.String(32), nullable=False),
    sa.Column("artifact_role", sa.String(100), nullable=False),
    sa.Column("schema_ref", sa.String(500), nullable=True),
    sa.Column("media_type", sa.String(255), nullable=False),
    sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("sha256", sa.CHAR(64), nullable=False),
    sa.Column("storage_key", sa.String(1024), nullable=False),
    sa.Column("encryption_profile", sa.String(255), nullable=False),
    sa.Column("source_raw_asset_id", uuid_type, nullable=True),
    sa.Column("source_pending_id", uuid_type, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", uuid_type, nullable=False),
    schema="artifact",
)

integrity_observation_table = sa.Table(
    "integrity_observation",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("artifact_id", uuid_type, nullable=False),
    sa.Column("check_kind", sa.String(32), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("expected_sha256", sa.CHAR(64), nullable=False),
    sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("observed_sha256", sa.CHAR(64), nullable=True),
    sa.Column("observed_size_bytes", sa.BigInteger(), nullable=True),
    sa.Column("object_version_id", sa.String(1024), nullable=True),
    sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("checked_by", uuid_type, nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="artifact",
)

integrity_projection_table = sa.Table(
    "integrity_projection",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("artifact_id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("last_observation_id", uuid_type, nullable=False),
    sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="artifact",
)

reconciliation_issue_table = sa.Table(
    "reconciliation_issue",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("issue_type", sa.String(64), nullable=False),
    sa.Column("artifact_id", uuid_type, nullable=True),
    sa.Column("pending_artifact_id", uuid_type, nullable=True),
    sa.Column("object_key", sa.String(1024), nullable=False),
    sa.Column("expected_sha256", sa.CHAR(64), nullable=True),
    sa.Column("expected_size_bytes", sa.BigInteger(), nullable=True),
    sa.Column("observed_sha256", sa.CHAR(64), nullable=True),
    sa.Column("observed_size_bytes", sa.BigInteger(), nullable=True),
    sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("detected_by", uuid_type, nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="artifact",
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


def _pending(row: RowMapping) -> PendingArtifact:
    return PendingArtifact(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        state=PendingArtifactState(str(row["state"])),
        artifact_kind=ArtifactKind(str(row["artifact_kind"])),
        artifact_role=str(row["artifact_role"]),
        schema_ref=str(row["schema_ref"]) if row["schema_ref"] is not None else None,
        media_type=str(row["media_type"]),
        expected_size_bytes=int(row["expected_size_bytes"]),
        expected_sha256=str(row["expected_sha256"]),
        staging_object_key=str(row["staging_object_key"]),
        final_object_key=str(row["final_object_key"]),
        encryption_profile=str(row["encryption_profile"]),
        source_raw_asset_id=cast(UUID | None, row["source_raw_asset_id"]),
        idempotency_key=str(row["idempotency_key"]),
        submission_digest=str(row["submission_digest"]),
        reserved_artifact_id=cast(UUID, row["reserved_artifact_id"]),
        available_artifact_id=cast(UUID | None, row["available_artifact_id"]),
        attempt_count=int(row["attempt_count"]),
        failure_code=(str(row["failure_code"]) if row["failure_code"] is not None else None),
        created_at=row["created_at"],
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
        updated_at=row["updated_at"],
        terminal_at=row["terminal_at"],
    )


def _artifact(row: RowMapping) -> Artifact:
    return Artifact(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        artifact_kind=ArtifactKind(str(row["artifact_kind"])),
        artifact_role=str(row["artifact_role"]),
        schema_ref=str(row["schema_ref"]) if row["schema_ref"] is not None else None,
        media_type=str(row["media_type"]),
        size_bytes=int(row["size_bytes"]),
        sha256=str(row["sha256"]),
        storage_key=str(row["storage_key"]),
        encryption_profile=str(row["encryption_profile"]),
        source_raw_asset_id=cast(UUID | None, row["source_raw_asset_id"]),
        source_pending_id=cast(UUID, row["source_pending_id"]),
        created_at=row["created_at"],
        created_by=cast(UUID, row["created_by"]),
    )


def _observation(row: RowMapping) -> IntegrityObservation:
    return IntegrityObservation(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        artifact_id=cast(UUID, row["artifact_id"]),
        check_kind=IntegrityCheckKind(str(row["check_kind"])),
        status=IntegrityStatus(str(row["status"])),
        expected_sha256=str(row["expected_sha256"]),
        expected_size_bytes=int(row["expected_size_bytes"]),
        observed_sha256=(
            str(row["observed_sha256"]) if row["observed_sha256"] is not None else None
        ),
        observed_size_bytes=(
            int(row["observed_size_bytes"]) if row["observed_size_bytes"] is not None else None
        ),
        object_version_id=(
            str(row["object_version_id"]) if row["object_version_id"] is not None else None
        ),
        checked_at=row["checked_at"],
        checked_by=cast(UUID, row["checked_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _issue(row: RowMapping) -> ReconciliationIssue:
    return ReconciliationIssue(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        issue_type=ReconciliationIssueType(str(row["issue_type"])),
        artifact_id=cast(UUID | None, row["artifact_id"]),
        pending_artifact_id=cast(UUID | None, row["pending_artifact_id"]),
        object_key=str(row["object_key"]),
        expected_sha256=(
            str(row["expected_sha256"]) if row["expected_sha256"] is not None else None
        ),
        expected_size_bytes=(
            int(row["expected_size_bytes"]) if row["expected_size_bytes"] is not None else None
        ),
        observed_sha256=(
            str(row["observed_sha256"]) if row["observed_sha256"] is not None else None
        ),
        observed_size_bytes=(
            int(row["observed_size_bytes"]) if row["observed_size_bytes"] is not None else None
        ),
        detected_at=row["detected_at"],
        detected_by=cast(UUID, row["detected_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


class SqlAlchemyArtifactRepository:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        available_hooks: Sequence[Callable[[Session, FinalizedArtifact], None]] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._available_hooks = tuple(available_hooks)

    def _bind(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @staticmethod
    def _pending_row(
        session: Session,
        pending_id: UUID,
        *,
        lock: bool = False,
    ) -> RowMapping:
        statement = sa.select(artifact_pending_table).where(
            artifact_pending_table.c.id == pending_id
        )
        if lock:
            statement = statement.with_for_update()
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise ArtifactNotFound(str(pending_id))
        return row

    @staticmethod
    def _artifact_row(session: Session, artifact_id: UUID) -> RowMapping:
        row = (
            session.execute(sa.select(artifact_table).where(artifact_table.c.id == artifact_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ArtifactNotFound(str(artifact_id))
        return row

    @classmethod
    def _record(cls, session: Session, artifact_id: UUID) -> ArtifactRecord:
        artifact_row = cls._artifact_row(session, artifact_id)
        projection = (
            session.execute(
                sa.select(integrity_projection_table).where(
                    integrity_projection_table.c.artifact_id == artifact_id
                )
            )
            .mappings()
            .one_or_none()
        )
        if projection is None:
            raise RuntimeError("available Artifact lost its integrity projection")
        return ArtifactRecord(
            artifact=_artifact(artifact_row),
            integrity_status=IntegrityStatus(str(projection["status"])),
            last_checked_at=projection["last_checked_at"],
            last_observation_id=cast(UUID, projection["last_observation_id"]),
        )

    def prepare(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending: PendingArtifact,
    ) -> tuple[PendingArtifact, bool]:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            inserted = session.execute(
                postgresql.insert(artifact_pending_table)
                .values(
                    organization_id=pending.organization_id,
                    project_id=pending.project_id,
                    id=pending.id,
                    classification=pending.classification.value,
                    state=pending.state.value,
                    artifact_kind=pending.artifact_kind.value,
                    artifact_role=pending.artifact_role,
                    schema_ref=pending.schema_ref,
                    media_type=pending.media_type,
                    expected_size_bytes=pending.expected_size_bytes,
                    expected_sha256=pending.expected_sha256,
                    staging_object_key=pending.staging_object_key,
                    final_object_key=pending.final_object_key,
                    encryption_profile=pending.encryption_profile,
                    source_raw_asset_id=pending.source_raw_asset_id,
                    idempotency_key=pending.idempotency_key,
                    submission_digest=pending.submission_digest,
                    reserved_artifact_id=pending.reserved_artifact_id,
                    available_artifact_id=None,
                    attempt_count=0,
                    failure_code=None,
                    created_at=pending.created_at,
                    created_by=pending.created_by,
                    request_id=pending.request_id,
                    trace_id=pending.trace_id,
                    updated_at=pending.updated_at,
                    terminal_at=None,
                )
                .on_conflict_do_nothing()
                .returning(artifact_pending_table.c.id)
            ).scalar_one_or_none()
            if inserted is not None:
                return _pending(self._pending_row(session, cast(UUID, inserted))), False
            existing = (
                session.execute(
                    sa.select(artifact_pending_table).where(
                        artifact_pending_table.c.idempotency_key == pending.idempotency_key
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is None:
                raise ArtifactConflict("pending Artifact identity is already in use")
            same_raw_asset = (
                existing["source_raw_asset_id"] is not None
                and existing["source_raw_asset_id"] == pending.source_raw_asset_id
            )
            if existing["created_by"] != context.principal.id and not same_raw_asset:
                raise ArtifactConflict("Artifact idempotency key is already in use")
            if existing["submission_digest"] != pending.submission_digest:
                raise ArtifactConflict(
                    "Artifact idempotency key was reused with a different manifest"
                )
            return _pending(existing), True

    def begin_promotion(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending_id: UUID,
        now: datetime,
    ) -> PendingArtifact:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = self._pending_row(session, pending_id, lock=True)
            state = PendingArtifactState(str(row["state"]))
            if state in {PendingArtifactState.AVAILABLE, PendingArtifactState.REJECTED}:
                return _pending(row)
            if state is PendingArtifactState.PROMOTING:
                return _pending(row)
            if state not in {
                PendingArtifactState.PENDING,
                PendingArtifactState.RETRYABLE,
            }:
                raise ArtifactStateError("pending Artifact cannot enter promotion")
            session.execute(
                sa.update(artifact_pending_table)
                .where(
                    artifact_pending_table.c.organization_id == row["organization_id"],
                    artifact_pending_table.c.project_id == row["project_id"],
                    artifact_pending_table.c.id == pending_id,
                    artifact_pending_table.c.state == state.value,
                )
                .values(
                    state=PendingArtifactState.PROMOTING.value,
                    attempt_count=int(row["attempt_count"]) + 1,
                    failure_code=None,
                    updated_at=now,
                )
            )
            return _pending(self._pending_row(session, pending_id))

    def mark_retryable(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending_id: UUID,
        failure_code: str,
        now: datetime,
    ) -> PendingArtifact:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = self._pending_row(session, pending_id, lock=True)
            state = PendingArtifactState(str(row["state"]))
            if state is PendingArtifactState.RETRYABLE:
                if row["failure_code"] != failure_code:
                    raise ArtifactConflict("retryable failure code changed")
                return _pending(row)
            if state is not PendingArtifactState.PROMOTING:
                raise ArtifactStateError("only a promoting Artifact can become retryable")
            session.execute(
                sa.update(artifact_pending_table)
                .where(
                    artifact_pending_table.c.organization_id == row["organization_id"],
                    artifact_pending_table.c.project_id == row["project_id"],
                    artifact_pending_table.c.id == pending_id,
                    artifact_pending_table.c.state == PendingArtifactState.PROMOTING.value,
                )
                .values(
                    state=PendingArtifactState.RETRYABLE.value,
                    failure_code=failure_code,
                    updated_at=now,
                )
            )
            return _pending(self._pending_row(session, pending_id))

    def reject(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending_id: UUID,
        failure_code: str,
        now: datetime,
    ) -> PendingArtifact:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = self._pending_row(session, pending_id, lock=True)
            state = PendingArtifactState(str(row["state"]))
            if state is PendingArtifactState.REJECTED:
                if row["failure_code"] != failure_code:
                    raise ArtifactConflict("rejection failure code changed")
                return _pending(row)
            if state is PendingArtifactState.AVAILABLE:
                raise ArtifactStateError("available Artifact cannot be rejected")
            if state in {
                PendingArtifactState.PENDING,
                PendingArtifactState.RETRYABLE,
            }:
                session.execute(
                    sa.update(artifact_pending_table)
                    .where(
                        artifact_pending_table.c.organization_id == row["organization_id"],
                        artifact_pending_table.c.project_id == row["project_id"],
                        artifact_pending_table.c.id == pending_id,
                        artifact_pending_table.c.state == state.value,
                    )
                    .values(
                        state=PendingArtifactState.PROMOTING.value,
                        attempt_count=int(row["attempt_count"]) + 1,
                        failure_code=None,
                        updated_at=now,
                    )
                )
                row = self._pending_row(session, pending_id, lock=True)
            if PendingArtifactState(str(row["state"])) is not PendingArtifactState.PROMOTING:
                raise ArtifactStateError("pending Artifact cannot be rejected")
            session.execute(
                sa.update(artifact_pending_table)
                .where(
                    artifact_pending_table.c.organization_id == row["organization_id"],
                    artifact_pending_table.c.project_id == row["project_id"],
                    artifact_pending_table.c.id == pending_id,
                    artifact_pending_table.c.state == PendingArtifactState.PROMOTING.value,
                )
                .values(
                    state=PendingArtifactState.REJECTED.value,
                    failure_code=failure_code,
                    terminal_at=now,
                    updated_at=now,
                )
            )
            return _pending(self._pending_row(session, pending_id))

    def commit_available(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending_id: UUID,
        stored: StoredObject,
        observation_id: UUID,
        now: datetime,
        commit_hook: ArtifactCommitHook | None = None,
    ) -> FinalizedArtifact:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = self._pending_row(session, pending_id, lock=True)
            state = PendingArtifactState(str(row["state"]))
            if state is PendingArtifactState.AVAILABLE:
                available_id = cast(UUID | None, row["available_artifact_id"])
                if available_id is None:
                    raise RuntimeError("available pending Artifact lost its identity")
                return FinalizedArtifact(_pending(row), self._record(session, available_id), True)
            if state is not PendingArtifactState.PROMOTING:
                raise ArtifactStateError("pending Artifact is not promoting")
            if (
                stored.object_key != row["final_object_key"]
                or stored.sha256 != row["expected_sha256"]
                or stored.size_bytes != int(row["expected_size_bytes"])
            ):
                raise ArtifactConflict("stored object differs from pending manifest")
            artifact_id = cast(UUID, row["reserved_artifact_id"])
            session.execute(
                sa.insert(artifact_table).values(
                    organization_id=row["organization_id"],
                    project_id=row["project_id"],
                    id=artifact_id,
                    classification=row["classification"],
                    artifact_kind=row["artifact_kind"],
                    artifact_role=row["artifact_role"],
                    schema_ref=row["schema_ref"],
                    media_type=row["media_type"],
                    size_bytes=stored.size_bytes,
                    sha256=stored.sha256,
                    storage_key=stored.object_key,
                    encryption_profile=row["encryption_profile"],
                    source_raw_asset_id=row["source_raw_asset_id"],
                    source_pending_id=pending_id,
                    created_at=now,
                    created_by=context.principal.id,
                )
            )
            session.execute(
                sa.insert(integrity_observation_table).values(
                    organization_id=row["organization_id"],
                    project_id=row["project_id"],
                    id=observation_id,
                    classification=row["classification"],
                    artifact_id=artifact_id,
                    check_kind=IntegrityCheckKind.FINALIZATION.value,
                    status=IntegrityStatus.VERIFIED.value,
                    expected_sha256=stored.sha256,
                    expected_size_bytes=stored.size_bytes,
                    observed_sha256=stored.sha256,
                    observed_size_bytes=stored.size_bytes,
                    object_version_id=stored.version_id,
                    checked_at=now,
                    checked_by=context.principal.id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            session.execute(
                sa.insert(integrity_projection_table).values(
                    organization_id=row["organization_id"],
                    project_id=row["project_id"],
                    artifact_id=artifact_id,
                    classification=row["classification"],
                    status=IntegrityStatus.VERIFIED.value,
                    last_observation_id=observation_id,
                    last_checked_at=now,
                    updated_at=now,
                )
            )
            session.execute(
                sa.update(artifact_pending_table)
                .where(
                    artifact_pending_table.c.organization_id == row["organization_id"],
                    artifact_pending_table.c.project_id == row["project_id"],
                    artifact_pending_table.c.id == pending_id,
                    artifact_pending_table.c.state == PendingArtifactState.PROMOTING.value,
                )
                .values(
                    state=PendingArtifactState.AVAILABLE.value,
                    available_artifact_id=artifact_id,
                    terminal_at=now,
                    updated_at=now,
                )
            )
            result = FinalizedArtifact(
                _pending(self._pending_row(session, pending_id)),
                self._record(session, artifact_id),
                False,
            )
            for hook in self._available_hooks:
                hook(session, result)
            if commit_hook is not None:
                commit_hook(session, result)
            return result

    def get_artifact(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
    ) -> ArtifactRecord:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            return self._record(session, artifact_id)

    def record_integrity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        observation: IntegrityObservation,
    ) -> ArtifactRecord:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            artifact_row = self._artifact_row(session, observation.artifact_id)
            if (
                artifact_row["classification"] != observation.classification.value
                or artifact_row["sha256"] != observation.expected_sha256
                or int(artifact_row["size_bytes"]) != observation.expected_size_bytes
            ):
                raise ArtifactConflict("integrity observation differs from immutable Artifact")
            session.execute(
                sa.insert(integrity_observation_table).values(
                    organization_id=observation.organization_id,
                    project_id=observation.project_id,
                    id=observation.id,
                    classification=observation.classification.value,
                    artifact_id=observation.artifact_id,
                    check_kind=observation.check_kind.value,
                    status=observation.status.value,
                    expected_sha256=observation.expected_sha256,
                    expected_size_bytes=observation.expected_size_bytes,
                    observed_sha256=observation.observed_sha256,
                    observed_size_bytes=observation.observed_size_bytes,
                    object_version_id=observation.object_version_id,
                    checked_at=observation.checked_at,
                    checked_by=observation.checked_by,
                    request_id=observation.request_id,
                    trace_id=observation.trace_id,
                )
            )
            updated = session.execute(
                sa.update(integrity_projection_table)
                .where(
                    integrity_projection_table.c.organization_id == observation.organization_id,
                    integrity_projection_table.c.project_id == observation.project_id,
                    integrity_projection_table.c.artifact_id == observation.artifact_id,
                )
                .values(
                    status=observation.status.value,
                    last_observation_id=observation.id,
                    last_checked_at=observation.checked_at,
                    updated_at=observation.checked_at,
                )
            )
            if getattr(updated, "rowcount", None) != 1:
                raise RuntimeError("Artifact integrity projection is missing")
            return self._record(session, observation.artifact_id)

    def list_artifacts(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ArtifactRecord, ...]:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            ids = session.execute(
                sa.select(artifact_table.c.id)
                .order_by(artifact_table.c.created_at, artifact_table.c.id)
                .limit(limit)
            ).scalars()
            return tuple(self._record(session, cast(UUID, value)) for value in ids)

    def list_unfinished(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[PendingArtifact, ...]:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            return tuple(
                _pending(row)
                for row in session.execute(
                    sa.select(artifact_pending_table)
                    .where(
                        artifact_pending_table.c.state.in_(
                            (
                                PendingArtifactState.PENDING.value,
                                PendingArtifactState.PROMOTING.value,
                                PendingArtifactState.RETRYABLE.value,
                            )
                        )
                    )
                    .order_by(
                        artifact_pending_table.c.created_at,
                        artifact_pending_table.c.id,
                    )
                    .limit(limit)
                ).mappings()
            )

    def known_final_keys(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> frozenset[str]:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            artifact_keys = session.execute(sa.select(artifact_table.c.storage_key)).scalars()
            pending_keys = session.execute(
                sa.select(artifact_pending_table.c.final_object_key).where(
                    artifact_pending_table.c.state != PendingArtifactState.REJECTED.value
                )
            ).scalars()
            return frozenset(str(value) for value in (*artifact_keys, *pending_keys))

    def record_issue(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        issue: ReconciliationIssue,
    ) -> ReconciliationIssue:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = (
                session.execute(
                    sa.insert(reconciliation_issue_table)
                    .values(
                        organization_id=issue.organization_id,
                        project_id=issue.project_id,
                        id=issue.id,
                        classification=issue.classification.value,
                        issue_type=issue.issue_type.value,
                        artifact_id=issue.artifact_id,
                        pending_artifact_id=issue.pending_artifact_id,
                        object_key=issue.object_key,
                        expected_sha256=issue.expected_sha256,
                        expected_size_bytes=issue.expected_size_bytes,
                        observed_sha256=issue.observed_sha256,
                        observed_size_bytes=issue.observed_size_bytes,
                        detected_at=issue.detected_at,
                        detected_by=issue.detected_by,
                        request_id=issue.request_id,
                        trace_id=issue.trace_id,
                    )
                    .returning(reconciliation_issue_table)
                )
                .mappings()
                .one()
            )
            return _issue(row)
