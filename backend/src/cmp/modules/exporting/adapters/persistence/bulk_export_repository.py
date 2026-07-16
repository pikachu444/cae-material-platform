"""PostgreSQL persistence for immutable Bulk Export Selections, Jobs, and Bundles."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.exporting.application.bulk_export import (
    BulkExportBundle,
    BulkExportJob,
    BulkExportRepository,
    CommittedBulkExportOutput,
    ExportSelectionSnapshot,
)
from cmp.modules.exporting.domain.bulk_bundle import (
    BulkExportArchiveEvidence,
    BulkExportConflict,
    BulkExportJobState,
    BulkExportNotFound,
    ExportMemberKind,
    ExportSelectionContent,
    ExportSelectionMember,
    ExportSelectionOmission,
    ExportSourceRef,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.adapters.persistence.revisions import SqlRevisionHook
from cmp.shared.domain.revisions import RevisionCreated, RevisionRecord, TenantScope


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


metadata = sa.MetaData()
selection_table = sa.Table(
    "export_selection",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_label", sa.String(160), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="exporting",
)
selection_revision_table = sa.Table(
    "export_selection_revision",
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
    sa.Column("selection_label", sa.String(160), nullable=False),
    sa.Column("member_count", sa.Integer(), nullable=False),
    sa.Column("omission_count", sa.Integer(), nullable=False),
    sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
    schema="exporting",
)
member_table = sa.Table(
    "export_selection_member",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("member_kind", sa.String(64), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=True),
    sa.Column("artifact_id", sa.Uuid(), nullable=True),
    sa.Column("dataset_id", sa.Uuid(), nullable=True),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("material_model_id", sa.Uuid(), nullable=True),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=True),
    sa.Column("solver_card_id", sa.Uuid(), nullable=True),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=True),
    sa.Column("archive_path", sa.String(512), nullable=False),
    sa.Column("source_sha256", sa.CHAR(64), nullable=False),
    sa.Column("source_size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("media_type", sa.String(255), nullable=False),
    sa.Column("label", sa.String(255), nullable=False),
    schema="exporting",
)
omission_table = sa.Table(
    "export_selection_omission",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("member_kind", sa.String(64), nullable=False),
    sa.Column("raw_asset_id", sa.Uuid(), nullable=True),
    sa.Column("artifact_id", sa.Uuid(), nullable=True),
    sa.Column("dataset_id", sa.Uuid(), nullable=True),
    sa.Column("dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("material_model_id", sa.Uuid(), nullable=True),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=True),
    sa.Column("solver_card_id", sa.Uuid(), nullable=True),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=True),
    sa.Column("reason_code", sa.String(80), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    schema="exporting",
)
job_table = sa.Table(
    "bulk_export_job",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("bundle_id", sa.Uuid(), nullable=True),
    sa.Column("failure_code", sa.String(80), nullable=True),
    sa.Column("failure_detail", sa.Text(), nullable=True),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("submitted_by", sa.Uuid(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("lease_token", sa.Uuid(), nullable=True),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    schema="exporting",
)
bundle_table = sa.Table(
    "bulk_export_bundle",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("archive_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("archive_sha256", sa.CHAR(64), nullable=False),
    sa.Column("archive_size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("manifest_sha256", sa.CHAR(64), nullable=False),
    sa.Column("component_count", sa.Integer(), nullable=False),
    sa.Column("omission_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    schema="exporting",
)
output_commit_table = sa.Table(
    "bulk_export_output_commit",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("job_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("archive_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("archive_sha256", sa.CHAR(64), nullable=False),
    sa.Column("archive_size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("manifest_sha256", sa.CHAR(64), nullable=False),
    sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("committed_by", sa.Uuid(), nullable=False),
    schema="exporting",
)


def _source(row: Any) -> ExportSourceRef:
    return ExportSourceRef(
        ExportMemberKind(str(row["member_kind"])),
        cast(UUID | None, row["raw_asset_id"]),
        cast(UUID | None, row["artifact_id"]),
        cast(UUID | None, row["dataset_id"]),
        cast(UUID | None, row["dataset_revision_id"]),
        cast(UUID | None, row["material_model_id"]),
        cast(UUID | None, row["material_model_revision_id"]),
        cast(UUID | None, row["solver_card_id"]),
        cast(UUID | None, row["solver_card_revision_id"]),
    )


def _source_values(source: ExportSourceRef) -> dict[str, object]:
    return {
        "member_kind": source.kind.value,
        "raw_asset_id": source.raw_asset_id,
        "artifact_id": source.artifact_id,
        "dataset_id": source.dataset_id,
        "dataset_revision_id": source.dataset_revision_id,
        "material_model_id": source.material_model_id,
        "material_model_revision_id": source.material_model_revision_id,
        "solver_card_id": source.solver_card_id,
        "solver_card_revision_id": source.solver_card_revision_id,
    }


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        cast(UUID, row["id"]),
        "exporting.bulk_export_selection",
        cast(UUID, row["aggregate_id"]),
        TenantScope(
            cast(UUID, row["organization_id"]),
            cast(UUID, row["project_id"]),
            str(row["classification"]),
        ),
        int(row["revision_no"]),
        cast(UUID | None, row["based_on_revision_id"]),
        str(row["schema_id"]),
        str(row["schema_version"]),
        str(row["content_hash"]),
        row["created_at"],
        cast(UUID, row["created_by"]),
        str(row["change_reason"]),
        cast(UUID, row["request_id"]),
        str(row["trace_id"]),
    )


def _job(row: Any) -> BulkExportJob:
    return BulkExportJob(
        cast(UUID, row["id"]),
        cast(UUID, row["organization_id"]),
        cast(UUID, row["project_id"]),
        DataClassification(str(row["classification"])),
        cast(UUID, row["selection_id"]),
        cast(UUID, row["selection_revision_id"]),
        BulkExportJobState(str(row["state"])),
        int(row["attempt_count"]),
        cast(UUID | None, row["bundle_id"]),
        cast(str | None, row["failure_code"]),
        cast(str | None, row["failure_detail"]),
        row["submitted_at"],
        cast(UUID, row["submitted_by"]),
        row["started_at"],
        row["completed_at"],
        cast(UUID | None, row["lease_token"]),
        cast(datetime | None, row["lease_expires_at"]),
        cast(datetime | None, row["heartbeat_at"]),
    )


def _assert_lease(row: Any, lease_token: UUID | None, now: datetime) -> None:
    current_token = cast(UUID | None, row["lease_token"])
    if current_token is None:
        if lease_token is not None:
            raise BulkExportConflict("Bulk Export Job lease fencing token is stale")
        return
    expires_at = cast(datetime | None, row["lease_expires_at"])
    if lease_token != current_token or expires_at is None or expires_at <= now:
        raise BulkExportConflict("Bulk Export Job lease was lost or expired")


def _bundle(row: Any) -> BulkExportBundle:
    return BulkExportBundle(
        cast(UUID, row["id"]),
        cast(UUID, row["organization_id"]),
        cast(UUID, row["project_id"]),
        DataClassification(str(row["classification"])),
        cast(UUID, row["selection_id"]),
        cast(UUID, row["selection_revision_id"]),
        cast(UUID, row["archive_artifact_id"]),
        str(row["archive_sha256"]),
        int(row["archive_size_bytes"]),
        str(row["manifest_sha256"]),
        int(row["component_count"]),
        int(row["omission_count"]),
        row["created_at"],
        cast(UUID, row["created_by"]),
    )


def _output_commit(row: Any) -> CommittedBulkExportOutput:
    return CommittedBulkExportOutput(
        cast(UUID, row["id"]),
        cast(UUID, row["organization_id"]),
        cast(UUID, row["project_id"]),
        DataClassification(str(row["classification"])),
        cast(UUID, row["job_id"]),
        cast(UUID, row["selection_revision_id"]),
        cast(UUID, row["archive_artifact_id"]),
        str(row["archive_sha256"]),
        int(row["archive_size_bytes"]),
        str(row["manifest_sha256"]),
        row["committed_at"],
        cast(UUID, row["committed_by"]),
    )


class SqlAlchemyBulkExportRepository(BulkExportRepository):
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
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    @staticmethod
    def _member_values(
        selection_id: UUID,
        revision_id: UUID,
        member: ExportSelectionMember,
        context: SecurityContext,
    ) -> dict[str, object]:
        return {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": member.classification.value,
            "selection_id": selection_id,
            "selection_revision_id": revision_id,
            "ordinal": member.ordinal,
            **_source_values(member.source),
            "archive_path": member.archive_path,
            "source_sha256": member.source_sha256,
            "source_size_bytes": member.source_size_bytes,
            "media_type": member.media_type,
            "label": member.label,
        }

    @staticmethod
    def _omission_values(
        selection_id: UUID,
        revision_id: UUID,
        omission: ExportSelectionOmission,
        context: SecurityContext,
        classification: DataClassification,
    ) -> dict[str, object]:
        return {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": classification.value,
            "selection_id": selection_id,
            "selection_revision_id": revision_id,
            "ordinal": omission.ordinal,
            **_source_values(omission.source),
            "reason_code": omission.reason_code,
            "reason": omission.reason,
        }

    def create_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        revision_id: UUID,
        content: ExportSelectionContent,
        schema_id: str,
        schema_version: str,
        change_reason: str,
        now: Any,
    ) -> ExportSelectionSnapshot:
        scope = {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": content.classification.value,
        }
        with self._session(context, decision) as session:
            session.execute(
                sa.insert(selection_table).values(
                    id=selection_id,
                    **scope,
                    current_revision_id=revision_id,
                    selection_label=content.selection_label,
                    created_at=now,
                    created_by=context.principal.id,
                    updated_at=now,
                )
            )
            session.execute(
                sa.insert(selection_revision_table).values(
                    id=revision_id,
                    aggregate_id=selection_id,
                    **scope,
                    revision_no=1,
                    based_on_revision_id=None,
                    schema_id=schema_id,
                    schema_version=schema_version,
                    content_hash=content.digest,
                    created_at=now,
                    created_by=context.principal.id,
                    change_reason=change_reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                    selection_label=content.selection_label,
                    member_count=len(content.members),
                    omission_count=len(content.omissions),
                    expected_size_bytes=content.expected_size_bytes,
                )
            )
            if content.members:
                session.execute(
                    sa.insert(member_table),
                    [
                        self._member_values(selection_id, revision_id, member, context)
                        for member in content.members
                    ],
                )
            if content.omissions:
                session.execute(
                    sa.insert(omission_table),
                    [
                        self._omission_values(
                            selection_id,
                            revision_id,
                            omission,
                            context,
                            content.classification,
                        )
                        for omission in content.omissions
                    ],
                )
            event = RevisionCreated(
                RevisionRecord(
                    revision_id,
                    "exporting.bulk_export_selection",
                    selection_id,
                    TenantScope(
                        context.organization_id,
                        context.project_id,
                        content.classification.value,
                    ),
                    1,
                    None,
                    schema_id,
                    schema_version,
                    content.digest,
                    now,
                    context.principal.id,
                    change_reason,
                    context.request_id,
                    context.trace_id,
                ),
                "draft",
            )
            for hook in self._hooks:
                hook(session, event)
        return self.get_selection(context=context, decision=decision, selection_id=selection_id)

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> ExportSelectionSnapshot:
        statement = (
            sa.select(*selection_revision_table.c)
            .select_from(
                selection_table.join(
                    selection_revision_table,
                    sa.and_(
                        selection_revision_table.c.aggregate_id == selection_table.c.id,
                        selection_revision_table.c.id == selection_table.c.current_revision_id,
                    ),
                )
            )
            .where(
                selection_table.c.id == selection_id,
                selection_table.c.organization_id == context.organization_id,
                selection_table.c.project_id == context.project_id,
            )
        )
        with self._session(context, decision) as session:
            try:
                revision = session.execute(statement).mappings().one_or_none()
                if revision is None:
                    raise BulkExportNotFound("Export Selection is not visible")
                members = session.execute(
                    sa.select(member_table)
                    .where(member_table.c.selection_revision_id == revision["id"])
                    .order_by(member_table.c.ordinal)
                ).mappings()
                omissions = session.execute(
                    sa.select(omission_table)
                    .where(omission_table.c.selection_revision_id == revision["id"])
                    .order_by(omission_table.c.ordinal)
                ).mappings()
                content = ExportSelectionContent(
                    str(revision["selection_label"]),
                    tuple(
                        ExportSelectionMember(
                            int(row["ordinal"]),
                            _source(row),
                            str(row["archive_path"]),
                            str(row["source_sha256"]),
                            int(row["source_size_bytes"]),
                            str(row["media_type"]),
                            DataClassification(str(row["classification"])),
                            str(row["label"]),
                        )
                        for row in members
                    ),
                    tuple(
                        ExportSelectionOmission(
                            int(row["ordinal"]),
                            _source(row),
                            str(row["reason_code"]),
                            str(row["reason"]),
                        )
                        for row in omissions
                    ),
                )
            except DBAPIError as error:
                raise BulkExportNotFound("Export Selection is unavailable") from error
        if content.digest != str(revision["content_hash"]):
            raise RuntimeError("Export Selection content hash drifted")
        return ExportSelectionSnapshot(selection_id, _record(revision), content)

    def create_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        selection: ExportSelectionSnapshot,
        now: Any,
    ) -> BulkExportJob:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.insert(job_table)
                    .values(
                        id=job_id,
                        organization_id=context.organization_id,
                        project_id=context.project_id,
                        classification=selection.content.classification.value,
                        selection_id=selection.id,
                        selection_revision_id=selection.current.revision_id,
                        state=BulkExportJobState.QUEUED.value,
                        attempt_count=1,
                        bundle_id=None,
                        failure_code=None,
                        failure_detail=None,
                        submitted_at=now,
                        submitted_by=context.principal.id,
                        started_at=None,
                        completed_at=None,
                        lease_token=None,
                        lease_expires_at=None,
                        heartbeat_at=None,
                    )
                    .returning(*job_table.c)
                )
                .mappings()
                .one()
            )
        return _job(row)

    def mark_job_running(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        now: Any,
    ) -> BulkExportJob:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.update(job_table)
                    .where(job_table.c.id == job_id, job_table.c.state == "queued")
                    .values(state="running", started_at=now)
                    .returning(*job_table.c)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise BulkExportNotFound("queued Bulk Export Job is not visible")
        return _job(row)

    def claim_next_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        lease_token: UUID,
        lease_duration: timedelta,
        now: Any,
    ) -> BulkExportJob | None:
        with self._session(context, decision) as session:
            current = (
                session.execute(
                    sa.select(job_table)
                    .where(
                        sa.or_(
                            job_table.c.state.in_(("reconciliation_required", "queued")),
                            sa.and_(
                                job_table.c.state.in_(("running", "reconciling")),
                                job_table.c.lease_token.is_not(None),
                                job_table.c.lease_expires_at <= now,
                            ),
                        )
                    )
                    .order_by(
                        sa.case(
                            (job_table.c.state == "reconciliation_required", 0),
                            (job_table.c.state.in_(("running", "reconciling")), 1),
                            else_=2,
                        ),
                        job_table.c.submitted_at,
                        job_table.c.id,
                    )
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if current is None:
                return None
            lease_expires_at = now + lease_duration
            if current["state"] == "queued":
                values: dict[str, object] = {
                    "state": "running",
                    "started_at": now,
                    "lease_token": lease_token,
                    "lease_expires_at": lease_expires_at,
                    "heartbeat_at": now,
                }
            elif current["state"] == "reconciliation_required":
                values = {
                    "state": "reconciling",
                    "attempt_count": int(current["attempt_count"]) + 1,
                    "failure_code": None,
                    "failure_detail": None,
                    "completed_at": None,
                    "lease_token": lease_token,
                    "lease_expires_at": lease_expires_at,
                    "heartbeat_at": now,
                }
            else:
                values = {
                    "attempt_count": int(current["attempt_count"]) + 1,
                    "lease_token": lease_token,
                    "lease_expires_at": lease_expires_at,
                    "heartbeat_at": now,
                }
            row = (
                session.execute(
                    sa.update(job_table)
                    .where(
                        job_table.c.id == current["id"],
                        job_table.c.state == current["state"],
                    )
                    .values(**values)
                    .returning(*job_table.c)
                )
                .mappings()
                .one()
            )
        return _job(row)

    def renew_job_lease(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        lease_token: UUID,
        lease_duration: timedelta,
        now: datetime,
    ) -> BulkExportJob:
        with self._session(context, decision) as session:
            current = (
                session.execute(
                    sa.select(job_table).where(job_table.c.id == job_id).with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if current is None or current["state"] not in ("running", "reconciling"):
                raise BulkExportNotFound("leased Bulk Export Job is not visible")
            _assert_lease(current, lease_token, now)
            lease_expires_at = now + lease_duration
            if lease_expires_at <= cast(datetime, current["lease_expires_at"]):
                return _job(current)
            row = (
                session.execute(
                    sa.update(job_table)
                    .where(job_table.c.id == job_id)
                    .values(heartbeat_at=now, lease_expires_at=lease_expires_at)
                    .returning(*job_table.c)
                )
                .mappings()
                .one()
            )
        return _job(row)

    def record_output_commit(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
        job_id: UUID,
        archive_artifact_id: UUID,
        evidence: BulkExportArchiveEvidence,
        lease_token: UUID | None,
        now: Any,
    ) -> CommittedBulkExportOutput:
        with self._session(context, decision) as session:
            current = (
                session.execute(
                    sa.select(job_table).where(job_table.c.id == job_id).with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if current is None or current["state"] not in ("running", "reconciling"):
                raise BulkExportNotFound("running Bulk Export Job is not visible")
            _assert_lease(current, lease_token, now)
            existing = (
                session.execute(
                    sa.select(output_commit_table).where(
                        output_commit_table.c.job_id == job_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is None:
                existing = (
                    session.execute(
                        sa.insert(output_commit_table)
                        .values(
                            id=output_id,
                            organization_id=context.organization_id,
                            project_id=context.project_id,
                            classification=current["classification"],
                            job_id=job_id,
                            selection_revision_id=current["selection_revision_id"],
                            archive_artifact_id=archive_artifact_id,
                            archive_sha256=evidence.archive_sha256,
                            archive_size_bytes=evidence.archive_size_bytes,
                            manifest_sha256=evidence.manifest_sha256,
                            committed_at=now,
                            committed_by=context.principal.id,
                        )
                        .returning(*output_commit_table.c)
                    )
                    .mappings()
                    .one()
                )
            elif (
                existing["archive_artifact_id"] != archive_artifact_id
                or existing["archive_sha256"] != evidence.archive_sha256
                or int(existing["archive_size_bytes"]) != evidence.archive_size_bytes
                or existing["manifest_sha256"] != evidence.manifest_sha256
            ):
                raise BulkExportConflict("Bulk Export Job already committed different output")
        return _output_commit(existing)

    def get_output_commit(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
    ) -> CommittedBulkExportOutput | None:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(output_commit_table).where(
                        output_commit_table.c.job_id == job_id
                    )
                )
                .mappings()
                .one_or_none()
            )
        return _output_commit(row) if row is not None else None

    def complete_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        bundle_id: UUID,
        archive_artifact_id: UUID,
        evidence: BulkExportArchiveEvidence,
        content: ExportSelectionContent,
        lease_token: UUID | None,
        now: Any,
    ) -> tuple[BulkExportJob, BulkExportBundle]:
        with self._session(context, decision) as session:
            current = (
                session.execute(
                    sa.select(job_table).where(job_table.c.id == job_id).with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if current is None or current["state"] not in ("running", "reconciling"):
                raise BulkExportNotFound("running Bulk Export Job is not visible")
            _assert_lease(current, lease_token, now)
            output = (
                session.execute(
                    sa.select(output_commit_table).where(
                        output_commit_table.c.job_id == job_id,
                        output_commit_table.c.archive_artifact_id == archive_artifact_id,
                        output_commit_table.c.archive_sha256 == evidence.archive_sha256,
                        output_commit_table.c.archive_size_bytes
                        == evidence.archive_size_bytes,
                        output_commit_table.c.manifest_sha256 == evidence.manifest_sha256,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if output is None:
                raise BulkExportConflict("committed Bundle output evidence is missing")
            existing = (
                session.execute(
                    sa.select(bundle_table).where(
                        bundle_table.c.selection_revision_id == current["selection_revision_id"],
                        bundle_table.c.archive_sha256 == evidence.archive_sha256,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is None:
                existing = (
                    session.execute(
                        sa.insert(bundle_table)
                        .values(
                            id=bundle_id,
                            organization_id=context.organization_id,
                            project_id=context.project_id,
                            classification=content.classification.value,
                            selection_id=current["selection_id"],
                            selection_revision_id=current["selection_revision_id"],
                            archive_artifact_id=archive_artifact_id,
                            archive_sha256=evidence.archive_sha256,
                            archive_size_bytes=evidence.archive_size_bytes,
                            manifest_sha256=evidence.manifest_sha256,
                            component_count=len(content.members),
                            omission_count=len(content.omissions),
                            created_at=now,
                            created_by=context.principal.id,
                        )
                        .returning(*bundle_table.c)
                    )
                    .mappings()
                    .one()
                )
            job_row = (
                session.execute(
                    sa.update(job_table)
                    .where(
                        job_table.c.id == job_id,
                        job_table.c.state.in_(("running", "reconciling")),
                    )
                    .values(
                        state="succeeded",
                        bundle_id=existing["id"],
                        failure_code=None,
                        failure_detail=None,
                        completed_at=now,
                        lease_token=None,
                        lease_expires_at=None,
                        heartbeat_at=None,
                    )
                    .returning(*job_table.c)
                )
                .mappings()
                .one()
            )
        return _job(job_row), _bundle(existing)

    def fail_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        failure_code: str,
        failure_detail: str,
        lease_token: UUID | None,
        now: Any,
    ) -> BulkExportJob:
        with self._session(context, decision) as session:
            current = (
                session.execute(
                    sa.select(job_table).where(job_table.c.id == job_id).with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if current is None or current["state"] not in ("running", "reconciling"):
                raise BulkExportNotFound("running Bulk Export Job is not visible")
            _assert_lease(current, lease_token, now)
            row = (
                session.execute(
                    sa.update(job_table)
                    .where(
                        job_table.c.id == job_id,
                        job_table.c.state.in_(("running", "reconciling")),
                    )
                    .values(
                        state="failed",
                        failure_code=failure_code,
                        failure_detail=failure_detail,
                        completed_at=now,
                        lease_token=None,
                        lease_expires_at=None,
                        heartbeat_at=None,
                    )
                    .returning(*job_table.c)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise BulkExportNotFound("running Bulk Export Job is not visible")
        return _job(row)

    def require_output_reconciliation(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        failure_detail: str,
        lease_token: UUID | None,
        now: Any,
    ) -> BulkExportJob:
        with self._session(context, decision) as session:
            current = (
                session.execute(
                    sa.select(job_table).where(job_table.c.id == job_id).with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if current is None or current["state"] not in ("running", "reconciling"):
                raise BulkExportNotFound("running Bulk Export Job is not visible")
            _assert_lease(current, lease_token, now)
            row = (
                session.execute(
                    sa.update(job_table)
                    .where(
                        job_table.c.id == job_id,
                        job_table.c.state.in_(("running", "reconciling")),
                        sa.exists(
                            sa.select(output_commit_table.c.id).where(
                                output_commit_table.c.job_id == job_id
                            )
                        ),
                    )
                    .values(
                        state="reconciliation_required",
                        failure_code="committed_output_pending",
                        failure_detail=failure_detail,
                        completed_at=now,
                        lease_token=None,
                        lease_expires_at=None,
                        heartbeat_at=None,
                    )
                    .returning(*job_table.c)
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise BulkExportNotFound("committed output requiring reconciliation is not visible")
        return _job(row)

    def get_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
    ) -> BulkExportJob:
        with self._session(context, decision) as session:
            row = (
                session.execute(sa.select(job_table).where(job_table.c.id == job_id))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise BulkExportNotFound("Bulk Export Job is not visible")
        return _job(row)

    def list_jobs(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[BulkExportJob, ...]:
        with self._session(context, decision) as session:
            rows = session.execute(
                sa.select(job_table).order_by(
                    job_table.c.submitted_at.desc(), job_table.c.id
                )
            ).mappings()
            return tuple(_job(row) for row in rows)

    def get_bundle(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        bundle_id: UUID,
    ) -> BulkExportBundle:
        with self._session(context, decision) as session:
            row = (
                session.execute(sa.select(bundle_table).where(bundle_table.c.id == bundle_id))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise BulkExportNotFound("Bulk Export Bundle is not visible")
        return _bundle(row)

    def list_bundles(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[BulkExportBundle, ...]:
        with self._session(context, decision) as session:
            rows = session.execute(
                sa.select(bundle_table).order_by(
                    bundle_table.c.created_at.desc(), bundle_table.c.id
                )
            ).mappings()
            return tuple(_bundle(row) for row in rows)
