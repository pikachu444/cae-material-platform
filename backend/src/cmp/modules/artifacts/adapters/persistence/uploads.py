"""RLS-bound PostgreSQL implementation of the T-09 upload repository."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.artifacts.application.uploads import RawAssetCompletion
from cmp.modules.artifacts.domain.uploads import (
    CompletedObject,
    IngestionEvent,
    InvalidUpload,
    RawAsset,
    RawAssetStorageState,
    StoredPart,
    UploadConflict,
    UploadNotFound,
    UploadPart,
    UploadSession,
    UploadState,
    UploadStateError,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext

metadata = sa.MetaData()
uuid_type = postgresql.UUID(as_uuid=True)

upload_session_table = sa.Table(
    "upload_session",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("original_filename", sa.String(255), nullable=False),
    sa.Column("media_type", sa.String(255), nullable=False),
    sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("expected_sha256", sa.CHAR(64), nullable=False),
    sa.Column("part_size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("expected_part_count", sa.Integer(), nullable=False),
    sa.Column("test_run_revision_id", uuid_type, nullable=True),
    sa.Column("staging_object_key", sa.String(1024), nullable=False),
    sa.Column("object_upload_id", sa.String(1024), nullable=False),
    sa.Column("idempotency_key", sa.String(255), nullable=False),
    sa.Column("submission_digest", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", uuid_type, nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("raw_asset_id", uuid_type, nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    schema="artifact",
)

upload_part_table = sa.Table(
    "upload_part",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("upload_session_id", uuid_type, nullable=False),
    sa.Column("part_number", sa.Integer(), nullable=False),
    sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("sha256", sa.CHAR(64), nullable=False),
    sa.Column("storage_etag", sa.String(255), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_by", uuid_type, nullable=False),
    schema="artifact",
)

raw_asset_table = sa.Table(
    "raw_asset",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("sha256", sa.CHAR(64), nullable=False),
    sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("media_type", sa.String(255), nullable=False),
    sa.Column("original_filename", sa.String(255), nullable=False),
    sa.Column("storage_state", sa.String(32), nullable=False),
    sa.Column("staging_object_key", sa.String(1024), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", uuid_type, nullable=False),
    schema="artifact",
)

ingestion_event_table = sa.Table(
    "ingestion_event",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("raw_asset_id", uuid_type, nullable=False),
    sa.Column("upload_session_id", uuid_type, nullable=False),
    sa.Column("test_run_revision_id", uuid_type, nullable=True),
    sa.Column("duplicate_content", sa.Boolean(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("actor_id", uuid_type, nullable=False),
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


def _raw(row: RowMapping) -> RawAsset:
    return RawAsset(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        sha256=str(row["sha256"]),
        size_bytes=int(row["size_bytes"]),
        media_type=str(row["media_type"]),
        original_filename=str(row["original_filename"]),
        storage_state=RawAssetStorageState(str(row["storage_state"])),
        staging_object_key=str(row["staging_object_key"]),
        created_at=row["created_at"],
        created_by=cast(UUID, row["created_by"]),
    )


def _event(row: RowMapping) -> IngestionEvent:
    return IngestionEvent(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        raw_asset_id=cast(UUID, row["raw_asset_id"]),
        upload_session_id=cast(UUID, row["upload_session_id"]),
        test_run_revision_id=cast(UUID | None, row["test_run_revision_id"]),
        duplicate_content=bool(row["duplicate_content"]),
        occurred_at=row["occurred_at"],
        actor_id=cast(UUID, row["actor_id"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


class SqlAlchemyUploadRepository:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    def _bind(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @staticmethod
    def _parts(session: Session, upload_id: UUID) -> tuple[UploadPart, ...]:
        return tuple(
            UploadPart(
                organization_id=cast(UUID, row["organization_id"]),
                project_id=cast(UUID, row["project_id"]),
                classification=DataClassification(str(row["classification"])),
                upload_session_id=cast(UUID, row["upload_session_id"]),
                part_number=int(row["part_number"]),
                size_bytes=int(row["size_bytes"]),
                sha256=str(row["sha256"]),
                storage_etag=str(row["storage_etag"]),
                recorded_at=row["recorded_at"],
                recorded_by=cast(UUID, row["recorded_by"]),
            )
            for row in session.execute(
                sa.select(upload_part_table)
                .where(upload_part_table.c.upload_session_id == upload_id)
                .order_by(upload_part_table.c.part_number)
            ).mappings()
        )

    @classmethod
    def _upload(cls, session: Session, row: RowMapping) -> UploadSession:
        return UploadSession(
            id=cast(UUID, row["id"]),
            organization_id=cast(UUID, row["organization_id"]),
            project_id=cast(UUID, row["project_id"]),
            classification=DataClassification(str(row["classification"])),
            state=UploadState(str(row["state"])),
            original_filename=str(row["original_filename"]),
            media_type=str(row["media_type"]),
            expected_size_bytes=int(row["expected_size_bytes"]),
            expected_sha256=str(row["expected_sha256"]),
            part_size_bytes=int(row["part_size_bytes"]),
            expected_part_count=int(row["expected_part_count"]),
            test_run_revision_id=cast(UUID | None, row["test_run_revision_id"]),
            staging_object_key=str(row["staging_object_key"]),
            object_upload_id=str(row["object_upload_id"]),
            idempotency_key=str(row["idempotency_key"]),
            submission_digest=str(row["submission_digest"]),
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            created_by=cast(UUID, row["created_by"]),
            request_id=cast(UUID, row["request_id"]),
            trace_id=str(row["trace_id"]),
            updated_at=row["updated_at"],
            terminal_at=row["terminal_at"],
            raw_asset_id=cast(UUID | None, row["raw_asset_id"]),
            failure_code=(
                str(row["failure_code"]) if row["failure_code"] is not None else None
            ),
            parts=cls._parts(session, cast(UUID, row["id"])),
        )

    @classmethod
    def _upload_row(
        cls,
        session: Session,
        upload_id: UUID,
        *,
        lock: bool = False,
    ) -> RowMapping:
        statement = sa.select(upload_session_table).where(
            upload_session_table.c.id == upload_id
        )
        if lock:
            statement = statement.with_for_update()
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise UploadNotFound(str(upload_id))
        return row

    @staticmethod
    def _raw_row(session: Session, raw_asset_id: UUID) -> RowMapping:
        row = session.execute(
            sa.select(raw_asset_table).where(raw_asset_table.c.id == raw_asset_id)
        ).mappings().one_or_none()
        if row is None:
            raise UploadNotFound(str(raw_asset_id))
        return row

    def create(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        session: UploadSession,
    ) -> tuple[UploadSession, bool]:
        with self._sessions() as database, database.begin():
            self._bind(database, context, decision)
            inserted = database.execute(
                postgresql.insert(upload_session_table)
                .values(
                    organization_id=session.organization_id,
                    project_id=session.project_id,
                    id=session.id,
                    classification=session.classification.value,
                    state=session.state.value,
                    original_filename=session.original_filename,
                    media_type=session.media_type,
                    expected_size_bytes=session.expected_size_bytes,
                    expected_sha256=session.expected_sha256,
                    part_size_bytes=session.part_size_bytes,
                    expected_part_count=session.expected_part_count,
                    test_run_revision_id=session.test_run_revision_id,
                    staging_object_key=session.staging_object_key,
                    object_upload_id=session.object_upload_id,
                    idempotency_key=session.idempotency_key,
                    submission_digest=session.submission_digest,
                    created_at=session.created_at,
                    expires_at=session.expires_at,
                    created_by=session.created_by,
                    request_id=session.request_id,
                    trace_id=session.trace_id,
                    updated_at=session.updated_at,
                )
                .on_conflict_do_nothing()
                .returning(upload_session_table.c.id)
            ).scalar_one_or_none()
            if inserted is not None:
                return self._upload(
                    database, self._upload_row(database, cast(UUID, inserted))
                ), False
            existing = database.execute(
                sa.select(upload_session_table).where(
                    upload_session_table.c.idempotency_key == session.idempotency_key
                )
            ).mappings().one_or_none()
            if existing is None:
                raise UploadConflict("upload identity is already in use")
            if existing["created_by"] != context.principal.id:
                raise UploadConflict("idempotency key is already in use")
            if existing["submission_digest"] != session.submission_digest:
                raise UploadConflict("idempotency key was reused with different upload metadata")
            return self._upload(database, existing), True

    def get_upload(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
    ) -> UploadSession:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            return self._upload(session, self._upload_row(session, upload_id))

    def record_part(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        part: StoredPart,
        now: datetime,
    ) -> UploadSession:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            upload = self._upload_row(session, upload_id, lock=True)
            if UploadState(str(upload["state"])) is not UploadState.OPEN:
                raise UploadStateError("upload is not open for new parts")
            expected_count = int(upload["expected_part_count"])
            if not 1 <= part.part_number <= expected_count:
                raise InvalidUpload("part number is outside the upload manifest")
            part_size = int(upload["part_size_bytes"])
            expected_size = (
                part_size
                if part.part_number < expected_count
                else int(upload["expected_size_bytes"])
                - part_size * (expected_count - 1)
            )
            if part.size_bytes != expected_size:
                raise InvalidUpload("part size differs from the upload manifest")
            existing = session.execute(
                sa.select(upload_part_table).where(
                    upload_part_table.c.upload_session_id == upload_id,
                    upload_part_table.c.part_number == part.part_number,
                )
            ).mappings().one_or_none()
            if existing is not None:
                if (
                    existing["sha256"] != part.sha256
                    or int(existing["size_bytes"]) != part.size_bytes
                    or existing["storage_etag"] != part.etag
                ):
                    raise UploadConflict(
                        "part number is already bound to different immutable bytes"
                    )
                return self._upload(session, upload)
            session.execute(
                sa.insert(upload_part_table).values(
                    organization_id=upload["organization_id"],
                    project_id=upload["project_id"],
                    classification=upload["classification"],
                    upload_session_id=upload_id,
                    part_number=part.part_number,
                    size_bytes=part.size_bytes,
                    sha256=part.sha256,
                    storage_etag=part.etag,
                    recorded_at=now,
                    recorded_by=context.principal.id,
                )
            )
            return self._upload(session, self._upload_row(session, upload_id))

    def begin_completion(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        now: datetime,
    ) -> UploadSession:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = self._upload_row(session, upload_id, lock=True)
            state = UploadState(str(row["state"]))
            if state not in {UploadState.OPEN, UploadState.COMPLETING}:
                raise UploadStateError("upload cannot enter completion from its current state")
            value = self._upload(session, row)
            expected_numbers = tuple(range(1, value.expected_part_count + 1))
            if tuple(item.part_number for item in value.parts) != expected_numbers or any(
                item.size_bytes != value.expected_part_size(item.part_number)
                for item in value.parts
            ):
                raise InvalidUpload("upload part manifest is incomplete")
            if state is UploadState.OPEN:
                session.execute(
                    sa.update(upload_session_table)
                    .where(
                        upload_session_table.c.organization_id == row["organization_id"],
                        upload_session_table.c.project_id == row["project_id"],
                        upload_session_table.c.id == upload_id,
                        upload_session_table.c.state == UploadState.OPEN.value,
                    )
                    .values(state=UploadState.COMPLETING.value, updated_at=now)
                )
            return self._upload(session, self._upload_row(session, upload_id))

    @staticmethod
    def _completion(session: Session, upload_id: UUID) -> RawAssetCompletion:
        upload_row = SqlAlchemyUploadRepository._upload_row(session, upload_id)
        if UploadState(str(upload_row["state"])) is not UploadState.COMPLETED:
            raise UploadStateError("upload has no committed Raw Asset")
        event_row = session.execute(
            sa.select(ingestion_event_table).where(
                ingestion_event_table.c.upload_session_id == upload_id
            )
        ).mappings().one_or_none()
        if event_row is None:
            raise RuntimeError("completed upload lost its ingestion event")
        raw_row = SqlAlchemyUploadRepository._raw_row(
            session, cast(UUID, event_row["raw_asset_id"])
        )
        return RawAssetCompletion(
            SqlAlchemyUploadRepository._upload(session, upload_row),
            _raw(raw_row),
            _event(event_row),
            bool(event_row["duplicate_content"]),
        )

    def complete(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        completed: CompletedObject,
        raw_asset_id: UUID,
        ingestion_event_id: UUID,
        now: datetime,
    ) -> RawAssetCompletion:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            upload = self._upload_row(session, upload_id, lock=True)
            if UploadState(str(upload["state"])) is UploadState.COMPLETED:
                return self._completion(session, upload_id)
            if UploadState(str(upload["state"])) is not UploadState.COMPLETING:
                raise UploadStateError("upload is not ready to commit a Raw Asset")
            if (
                completed.object_key != upload["staging_object_key"]
                or completed.size_bytes != int(upload["expected_size_bytes"])
                or completed.sha256 != upload["expected_sha256"]
            ):
                raise InvalidUpload("completed object differs from the upload manifest")
            inserted_id = session.execute(
                postgresql.insert(raw_asset_table)
                .values(
                    organization_id=upload["organization_id"],
                    project_id=upload["project_id"],
                    id=raw_asset_id,
                    classification=upload["classification"],
                    sha256=completed.sha256,
                    size_bytes=completed.size_bytes,
                    media_type=upload["media_type"],
                    original_filename=upload["original_filename"],
                    storage_state=RawAssetStorageState.STAGED_VERIFIED.value,
                    staging_object_key=completed.object_key,
                    created_at=now,
                    created_by=context.principal.id,
                )
                .on_conflict_do_nothing()
                .returning(raw_asset_table.c.id)
            ).scalar_one_or_none()
            duplicate = inserted_id is None
            if inserted_id is None:
                raw_row = session.execute(
                    sa.select(raw_asset_table).where(
                        raw_asset_table.c.classification == upload["classification"],
                        raw_asset_table.c.sha256 == completed.sha256,
                        raw_asset_table.c.size_bytes == completed.size_bytes,
                    )
                ).mappings().one_or_none()
                if raw_row is None:
                    raise UploadConflict("Raw Asset identity is already in use")
            else:
                raw_row = self._raw_row(session, cast(UUID, inserted_id))
            resolved_raw_id = cast(UUID, raw_row["id"])
            session.execute(
                sa.insert(ingestion_event_table).values(
                    organization_id=upload["organization_id"],
                    project_id=upload["project_id"],
                    id=ingestion_event_id,
                    classification=upload["classification"],
                    raw_asset_id=resolved_raw_id,
                    upload_session_id=upload_id,
                    test_run_revision_id=upload["test_run_revision_id"],
                    duplicate_content=duplicate,
                    occurred_at=now,
                    actor_id=context.principal.id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            updated = session.execute(
                sa.update(upload_session_table)
                .where(
                    upload_session_table.c.organization_id == upload["organization_id"],
                    upload_session_table.c.project_id == upload["project_id"],
                    upload_session_table.c.id == upload_id,
                    upload_session_table.c.state == UploadState.COMPLETING.value,
                )
                .values(
                    state=UploadState.COMPLETED.value,
                    raw_asset_id=resolved_raw_id,
                    terminal_at=now,
                    updated_at=now,
                )
            )
            if getattr(updated, "rowcount", None) != 1:
                raise UploadConflict("upload completion changed concurrently")
            return self._completion(session, upload_id)

    def fail(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        failure_code: str,
        now: datetime,
    ) -> UploadSession:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = self._upload_row(session, upload_id, lock=True)
            state = UploadState(str(row["state"]))
            if state is UploadState.FAILED:
                if row["failure_code"] != failure_code:
                    raise UploadConflict("upload already failed for a different reason")
                return self._upload(session, row)
            if state not in {UploadState.OPEN, UploadState.COMPLETING}:
                raise UploadStateError("terminal upload cannot be marked failed")
            session.execute(
                sa.update(upload_session_table)
                .where(
                    upload_session_table.c.organization_id == row["organization_id"],
                    upload_session_table.c.project_id == row["project_id"],
                    upload_session_table.c.id == upload_id,
                    upload_session_table.c.state == state.value,
                )
                .values(
                    state=UploadState.FAILED.value,
                    failure_code=failure_code,
                    terminal_at=now,
                    updated_at=now,
                )
            )
            return self._upload(session, self._upload_row(session, upload_id))

    def cancel(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        now: datetime,
    ) -> UploadSession:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = self._upload_row(session, upload_id, lock=True)
            state = UploadState(str(row["state"]))
            if state is UploadState.CANCELLED:
                return self._upload(session, row)
            if state not in {UploadState.OPEN, UploadState.COMPLETING}:
                raise UploadStateError("terminal upload cannot be cancelled")
            session.execute(
                sa.update(upload_session_table)
                .where(
                    upload_session_table.c.organization_id == row["organization_id"],
                    upload_session_table.c.project_id == row["project_id"],
                    upload_session_table.c.id == upload_id,
                    upload_session_table.c.state == state.value,
                )
                .values(
                    state=UploadState.CANCELLED.value,
                    terminal_at=now,
                    updated_at=now,
                )
            )
            return self._upload(session, self._upload_row(session, upload_id))

    def get_raw_asset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        raw_asset_id: UUID,
    ) -> RawAsset:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            return _raw(self._raw_row(session, raw_asset_id))

    def get_completion(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
    ) -> RawAssetCompletion:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            return self._completion(session, upload_id)
