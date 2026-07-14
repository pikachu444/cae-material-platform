"""RLS-bound PostgreSQL persistence and completeness gate for T-30 reference releases."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.review_release.application.release_service import ReleaseRepository
from cmp.modules.review_release.domain.release import (
    RELEASE_PACKAGE_MEDIA_TYPE,
    CreateRelease,
    RecordReleaseUsage,
    ReleaseConflict,
    ReleaseImpactRecord,
    ReleaseLifecycleState,
    ReleaseManifestRecord,
    ReleaseNotFound,
    ReleaseRecord,
    ReleaseState,
    ReleaseTransitionKind,
    ReleaseTransitionRecord,
    ReleaseUsageKind,
    ReleaseUsageRecord,
    SupersedeRelease,
    WithdrawRelease,
    candidate_manifest_sha256,
    release_manifest_document,
)
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


metadata = sa.MetaData()

release_table = sa.Table(
    "release",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("release_code", sa.String(100), nullable=False),
    sa.Column("title", sa.String(255), nullable=False),
    sa.Column("channel", sa.String(32), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="governance",
)

release_manifest_table = sa.Table(
    "release_manifest",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("release_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("manifest_sha256", sa.CHAR(64), nullable=False),
    sa.Column("package_sha256", sa.CHAR(64), nullable=False),
    sa.Column("package_size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("package_media_type", sa.String(128), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_content_sha256", sa.CHAR(64), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_content_sha256", sa.CHAR(64), nullable=False),
    sa.Column("mapping_report_sha256", sa.CHAR(64), nullable=False),
    sa.Column("card_sha256", sa.CHAR(64), nullable=False),
    sa.Column("validation_result_id", sa.Uuid(), nullable=False),
    sa.Column("validation_result_sha256", sa.CHAR(64), nullable=False),
    sa.Column("review_request_id", sa.Uuid(), nullable=False),
    sa.Column("review_manifest_sha256", sa.CHAR(64), nullable=False),
    sa.Column("provenance_snapshot_sha256", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    schema="governance",
)

release_artifact_table = sa.Table(
    "release_artifact",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("release_id", sa.Uuid(), nullable=False),
    sa.Column("release_manifest_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("media_type", sa.String(128), nullable=False),
    sa.Column("sha256", sa.CHAR(64), nullable=False),
    sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("content_text", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="governance",
)

release_lifecycle_projection_table = sa.Table(
    "release_lifecycle_projection",
    metadata,
    sa.Column("release_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("sequence_no", sa.Integer(), nullable=False),
    sa.Column("last_event_id", sa.Uuid(), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="governance",
)

release_lifecycle_event_table = sa.Table(
    "release_lifecycle_event",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("release_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("sequence_no", sa.Integer(), nullable=False),
    sa.Column("kind", sa.String(32), nullable=False),
    sa.Column("from_state", sa.String(32), nullable=False),
    sa.Column("to_state", sa.String(32), nullable=False),
    sa.Column("successor_release_id", sa.Uuid(), nullable=True),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("occurred_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="governance",
)

release_usage_table = sa.Table(
    "release_usage",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("release_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("usage_kind", sa.String(32), nullable=False),
    sa.Column("lifecycle_state", sa.String(32), nullable=False),
    sa.Column("used_by", sa.Uuid(), nullable=False),
    sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="governance",
)

model_revision_table = sa.Table(
    "material_model_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("content_hash", sa.CHAR(64), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_id", sa.Uuid(), nullable=False),
    sa.Column("property_set_revision_id", sa.Uuid(), nullable=False),
    schema="modeling",
)

solver_card_revision_table = sa.Table(
    "solver_card_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("content_hash", sa.CHAR(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("density_mapping_status", sa.String(32), nullable=False),
    sa.Column("youngs_modulus_mapping_status", sa.String(32), nullable=False),
    sa.Column("poisson_ratio_mapping_status", sa.String(32), nullable=False),
    sa.Column("source_yield_mapping_status", sa.String(32), nullable=False),
    sa.Column("temperature_applicability_mapping_status", sa.String(32), nullable=False),
    sa.Column("strain_rate_applicability_mapping_status", sa.String(32), nullable=False),
    sa.Column("unit_system_mapping_status", sa.String(32), nullable=False),
    sa.Column("mapping_report_sha256", sa.CHAR(64), nullable=False),
    sa.Column("card_sha256", sa.CHAR(64), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="exporting",
)

validation_result_table = sa.Table(
    "validation_result",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("verdict", sa.String(32), nullable=False),
    sa.Column("holdout_independence", sa.String(64), nullable=False),
    sa.Column("result_sha256", sa.CHAR(64), nullable=False),
    schema="validation",
)

review_request_table = sa.Table(
    "review_request",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("aggregate_type", sa.String(100), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("revision_id", sa.Uuid(), nullable=False),
    sa.Column("manifest_sha256", sa.CHAR(64), nullable=False),
    schema="governance",
)

review_decision_table = sa.Table(
    "review_decision",
    metadata,
    sa.Column("review_request_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("decision", sa.String(64), nullable=False),
    sa.Column("manifest_sha256", sa.CHAR(64), nullable=False),
    schema="governance",
)


def _scope_clause(table: sa.Table, context: SecurityContext) -> sa.ColumnElement[bool]:
    return sa.and_(
        table.c.organization_id == context.organization_id,
        table.c.project_id == context.project_id,
    )


def _digest_match(name: str, expected: str, actual: Any) -> None:
    if str(actual) != expected:
        raise ReleaseConflict(f"{name} digest does not match the immutable source")


def _release_manifest_row(row: Any) -> ReleaseManifestRecord:
    return ReleaseManifestRecord(
        id=cast(UUID, row["manifest_id"]),
        release_id=cast(UUID, row["release_id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        manifest_sha256=str(row["manifest_sha256"]),
        package_sha256=str(row["package_sha256"]),
        package_size_bytes=int(row["package_size_bytes"]),
        package_media_type=str(row["package_media_type"]),
        material_id=cast(UUID, row["material_id"]),
        material_revision_id=cast(UUID, row["material_revision_id"]),
        material_state_id=cast(UUID, row["material_state_id"]),
        material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
        property_set_id=cast(UUID, row["property_set_id"]),
        property_set_revision_id=cast(UUID, row["property_set_revision_id"]),
        material_model_id=cast(UUID, row["material_model_id"]),
        material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
        material_model_content_sha256=str(row["material_model_content_sha256"]),
        solver_card_id=cast(UUID, row["solver_card_id"]),
        solver_card_revision_id=cast(UUID, row["solver_card_revision_id"]),
        solver_card_content_sha256=str(row["solver_card_content_sha256"]),
        mapping_report_sha256=str(row["mapping_report_sha256"]),
        card_sha256=str(row["card_sha256"]),
        validation_result_id=cast(UUID, row["validation_result_id"]),
        validation_result_sha256=str(row["validation_result_sha256"]),
        review_request_id=cast(UUID, row["review_request_id"]),
        review_manifest_sha256=str(row["review_manifest_sha256"]),
        provenance_snapshot_sha256=str(row["provenance_snapshot_sha256"]),
        created_at=cast(datetime, row["manifest_created_at"]),
        created_by=cast(UUID, row["manifest_created_by"]),
        reason=str(row["reason"]),
        state=ReleaseState(str(row["manifest_state"])),
    )


def _release_record(row: Any) -> ReleaseRecord:
    return ReleaseRecord(
        id=cast(UUID, row["release_id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        release_code=str(row["release_code"]),
        title=str(row["title"]),
        channel=str(row["channel"]),
        created_at=cast(datetime, row["created_at"]),
        created_by=cast(UUID, row["created_by"]),
        manifest=_release_manifest_row(row),
        package_text=str(row["content_text"]),
        lifecycle_state=ReleaseLifecycleState(str(row["lifecycle_state"])),
    )


def _usage_record(row: Any) -> ReleaseUsageRecord:
    return ReleaseUsageRecord(
        id=cast(UUID, row["usage_id"]),
        release_id=cast(UUID, row["release_id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        usage_kind=ReleaseUsageKind(str(row["usage_kind"])),
        used_by=cast(UUID, row["used_by"]),
        used_at=cast(datetime, row["used_at"]),
        reason=str(row["reason"]),
    )


def _transition_record(row: Any) -> ReleaseTransitionRecord:
    return ReleaseTransitionRecord(
        id=cast(UUID, row["transition_id"]),
        release_id=cast(UUID, row["release_id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        kind=ReleaseTransitionKind(str(row["kind"])),
        from_state=ReleaseLifecycleState(str(row["from_state"])),
        to_state=ReleaseLifecycleState(str(row["to_state"])),
        successor_release_id=cast(UUID | None, row["successor_release_id"]),
        reason=str(row["reason"]),
        occurred_at=cast(datetime, row["occurred_at"]),
        occurred_by=cast(UUID, row["occurred_by"]),
    )


class SqlAlchemyReleaseRepository(ReleaseRepository):
    """Persist a digest-fixed reference package after all typed gates pass."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    @staticmethod
    def _select_release() -> sa.Select[Any]:
        return sa.select(
            release_table.c.id.label("release_id"),
            release_table.c.organization_id,
            release_table.c.project_id,
            release_table.c.classification,
            release_table.c.release_code,
            release_table.c.title,
            release_table.c.channel,
            sa.func.coalesce(
                release_lifecycle_projection_table.c.state,
                release_table.c.state,
            ).label("lifecycle_state"),
            release_table.c.created_at,
            release_table.c.created_by,
            release_manifest_table.c.id.label("manifest_id"),
            release_manifest_table.c.manifest_sha256,
            release_manifest_table.c.package_sha256,
            release_manifest_table.c.package_size_bytes,
            release_manifest_table.c.package_media_type,
            release_manifest_table.c.material_id,
            release_manifest_table.c.material_revision_id,
            release_manifest_table.c.material_state_id,
            release_manifest_table.c.material_state_revision_id,
            release_manifest_table.c.property_set_id,
            release_manifest_table.c.property_set_revision_id,
            release_manifest_table.c.material_model_id,
            release_manifest_table.c.material_model_revision_id,
            release_manifest_table.c.material_model_content_sha256,
            release_manifest_table.c.solver_card_id,
            release_manifest_table.c.solver_card_revision_id,
            release_manifest_table.c.solver_card_content_sha256,
            release_manifest_table.c.mapping_report_sha256,
            release_manifest_table.c.card_sha256,
            release_manifest_table.c.validation_result_id,
            release_manifest_table.c.validation_result_sha256,
            release_manifest_table.c.review_request_id,
            release_manifest_table.c.review_manifest_sha256,
            release_manifest_table.c.provenance_snapshot_sha256,
            release_manifest_table.c.created_at.label("manifest_created_at"),
            release_manifest_table.c.created_by.label("manifest_created_by"),
            release_manifest_table.c.reason,
            release_manifest_table.c.state.label("manifest_state"),
            release_artifact_table.c.content_text,
        ).select_from(
            release_table.join(
                release_manifest_table,
                sa.and_(
                    release_manifest_table.c.organization_id == release_table.c.organization_id,
                    release_manifest_table.c.project_id == release_table.c.project_id,
                    release_manifest_table.c.release_id == release_table.c.id,
                ),
            )
            .join(
                release_artifact_table,
                sa.and_(
                    release_artifact_table.c.organization_id
                    == release_manifest_table.c.organization_id,
                    release_artifact_table.c.project_id == release_manifest_table.c.project_id,
                    release_artifact_table.c.release_manifest_id == release_manifest_table.c.id,
                ),
            )
            .outerjoin(
                release_lifecycle_projection_table,
                sa.and_(
                    release_lifecycle_projection_table.c.organization_id
                    == release_table.c.organization_id,
                    release_lifecycle_projection_table.c.project_id == release_table.c.project_id,
                    release_lifecycle_projection_table.c.release_id == release_table.c.id,
                ),
            )
        )

    def _load(
        self,
        session: Session,
        *,
        context: SecurityContext,
        release_id: UUID,
    ) -> Any | None:
        return (
            session.execute(
                self._select_release().where(
                    _scope_clause(release_table, context),
                    release_table.c.id == release_id,
                )
            )
            .mappings()
            .one_or_none()
        )

    def _ensure_projection(
        self,
        session: Session,
        *,
        context: SecurityContext,
        release_id: UUID,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> Any:
        """Lock and return the lifecycle projection, backfilling old T-30 rows if needed."""

        release = (
            session.execute(
                sa.select(release_table)
                .where(_scope_clause(release_table, context), release_table.c.id == release_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if release is None:
            raise ReleaseNotFound("release is not visible")
        projection = (
            session.execute(
                sa.select(release_lifecycle_projection_table)
                .where(
                    _scope_clause(release_lifecycle_projection_table, context),
                    release_lifecycle_projection_table.c.release_id == release_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if projection is not None:
            return projection
        values = {
            "release_id": release_id,
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": release["classification"],
            "state": "released",
            "sequence_no": 0,
            "last_event_id": None,
            "updated_at": cast(datetime, release["created_at"]),
            "updated_by": cast(UUID, release["created_by"]),
            "request_id": cast(UUID, release["request_id"]),
            "trace_id": str(release["trace_id"]),
        }
        session.execute(sa.insert(release_lifecycle_projection_table).values(**values))
        return values

    def _transition(
        self,
        session: Session,
        *,
        context: SecurityContext,
        release_id: UUID,
        transition_id: UUID,
        kind: ReleaseTransitionKind,
        successor_release_id: UUID | None,
        reason: str,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReleaseRecord:
        successor: Any | None = None
        if successor_release_id is not None and successor_release_id.int < release_id.int:
            successor = self._ensure_projection(
                session,
                context=context,
                release_id=successor_release_id,
                actor_id=actor_id,
                occurred_at=occurred_at,
            )
        source = self._ensure_projection(
            session,
            context=context,
            release_id=release_id,
            actor_id=actor_id,
            occurred_at=occurred_at,
        )
        source_state = ReleaseLifecycleState(str(source["state"]))
        if source_state is not ReleaseLifecycleState.RELEASED:
            raise ReleaseConflict("only a released Release can transition")
        source_row = (
            session.execute(
                sa.select(release_table.c.classification).where(
                    _scope_clause(release_table, context), release_table.c.id == release_id
                )
            )
            .mappings()
            .one()
        )
        source_classification: Any = source_row["classification"]
        if successor_release_id is not None:
            if successor_release_id == release_id:
                raise ReleaseConflict("a Release cannot supersede itself")
            if successor is None:
                successor = self._ensure_projection(
                    session,
                    context=context,
                    release_id=successor_release_id,
                    actor_id=actor_id,
                    occurred_at=occurred_at,
                )
            if ReleaseLifecycleState(str(successor["state"])) is not ReleaseLifecycleState.RELEASED:
                raise ReleaseConflict("successor Release must be released")
            if successor["classification"] != source_classification:
                raise ReleaseConflict("successor Release classification must match")
            already_successor = session.execute(
                sa.select(release_lifecycle_event_table.c.id).where(
                    _scope_clause(release_lifecycle_event_table, context),
                    release_lifecycle_event_table.c.successor_release_id == successor_release_id,
                )
            ).scalar_one_or_none()
            if already_successor is not None:
                raise ReleaseConflict("successor Release is already linked")
        to_state = (
            ReleaseLifecycleState.SUPERSEDED
            if kind is ReleaseTransitionKind.SUPERSEDE
            else ReleaseLifecycleState.WITHDRAWN
        )
        session.execute(
            sa.insert(release_lifecycle_event_table).values(
                id=transition_id,
                release_id=release_id,
                organization_id=context.organization_id,
                project_id=context.project_id,
                classification=source_classification,
                sequence_no=int(source["sequence_no"]) + 1,
                kind=kind.value,
                from_state=ReleaseLifecycleState.RELEASED.value,
                to_state=to_state.value,
                successor_release_id=successor_release_id,
                reason=reason,
                occurred_at=occurred_at,
                occurred_by=actor_id,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        session.execute(
            sa.update(release_lifecycle_projection_table)
            .where(
                _scope_clause(release_lifecycle_projection_table, context),
                release_lifecycle_projection_table.c.release_id == release_id,
                release_lifecycle_projection_table.c.state == ReleaseLifecycleState.RELEASED.value,
                release_lifecycle_projection_table.c.sequence_no == int(source["sequence_no"]),
            )
            .values(
                state=to_state.value,
                sequence_no=int(source["sequence_no"]) + 1,
                last_event_id=transition_id,
                updated_at=occurred_at,
                updated_by=actor_id,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        row = self._load(session, context=context, release_id=release_id)
        if row is None:
            raise ReleaseConflict("transitioned Release could not be reloaded")
        return _release_record(row)

    def _validate_inputs(
        self,
        session: Session,
        *,
        context: SecurityContext,
        command: CreateRelease,
    ) -> str:
        model = (
            session.execute(
                sa.select(model_revision_table).where(
                    _scope_clause(model_revision_table, context),
                    model_revision_table.c.classification == command.classification.value,
                    model_revision_table.c.aggregate_id == command.material_model_id,
                    model_revision_table.c.id == command.material_model_revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if model is None:
            raise ReleaseNotFound("material model revision is not visible")
        _digest_match(
            "material_model_content_sha256",
            command.material_model_content_sha256,
            model["content_hash"],
        )
        for name in (
            "material_id",
            "material_revision_id",
            "material_state_id",
            "material_state_revision_id",
            "property_set_id",
            "property_set_revision_id",
        ):
            if model[name] != getattr(command, name):
                raise ReleaseConflict(f"{name} does not match the immutable material model lineage")

        card = (
            session.execute(
                sa.select(solver_card_revision_table).where(
                    _scope_clause(solver_card_revision_table, context),
                    solver_card_revision_table.c.classification == command.classification.value,
                    solver_card_revision_table.c.aggregate_id == command.solver_card_id,
                    solver_card_revision_table.c.id == command.solver_card_revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if card is None:
            raise ReleaseNotFound("solver card revision is not visible")
        _digest_match(
            "solver_card_content_sha256", command.solver_card_content_sha256, card["content_hash"]
        )
        if (
            card["material_model_id"] != command.material_model_id
            or card["material_model_revision_id"] != command.material_model_revision_id
        ):
            raise ReleaseConflict(
                "solver card does not reference the selected material model revision"
            )
        if not bool(card["non_production"]):
            raise ReleaseConflict("reference release requires the declared non-production card")
        for name in (
            "mapping_report_sha256",
            "card_sha256",
        ):
            _digest_match(name, getattr(command, name), card[name])
        for name in (
            "density_mapping_status",
            "youngs_modulus_mapping_status",
            "poisson_ratio_mapping_status",
            "source_yield_mapping_status",
            "temperature_applicability_mapping_status",
            "strain_rate_applicability_mapping_status",
            "unit_system_mapping_status",
        ):
            if str(card[name]) in {"unsupported", "approximated"}:
                raise ReleaseConflict(f"solver mapping {name} is not releaseable")

        result = (
            session.execute(
                sa.select(validation_result_table).where(
                    _scope_clause(validation_result_table, context),
                    validation_result_table.c.classification == command.classification.value,
                    validation_result_table.c.id == command.validation_result_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if result is None:
            raise ReleaseNotFound("validation result is not visible")
        _digest_match(
            "validation_result_sha256", command.validation_result_sha256, result["result_sha256"]
        )
        if result["verdict"] != "passed":
            raise ReleaseConflict("only a passed validation result can enter a reference release")

        candidate_sha = candidate_manifest_sha256(command)
        if command.review_manifest_sha256 != candidate_sha:
            raise ReleaseConflict(
                "review manifest digest does not match the explicit candidate manifest"
            )
        review = (
            session.execute(
                sa.select(
                    review_request_table,
                    review_decision_table.c.decision.label("review_decision"),
                    review_decision_table.c.manifest_sha256.label("decision_manifest_sha256"),
                )
                .select_from(
                    review_request_table.outerjoin(
                        review_decision_table,
                        sa.and_(
                            review_decision_table.c.organization_id
                            == review_request_table.c.organization_id,
                            review_decision_table.c.project_id == review_request_table.c.project_id,
                            review_decision_table.c.review_request_id == review_request_table.c.id,
                        ),
                    )
                )
                .where(
                    _scope_clause(review_request_table, context),
                    review_request_table.c.id == command.review_request_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if review is None:
            raise ReleaseNotFound("review request is not visible")
        if (
            review["classification"] != command.classification.value
            or review["aggregate_type"] != "exporting.solver_card"
            or review["aggregate_id"] != command.solver_card_id
            or review["revision_id"] != command.solver_card_revision_id
            or review["manifest_sha256"] != candidate_sha
            or review["review_decision"] != "approved"
            or review["decision_manifest_sha256"] != candidate_sha
        ):
            raise ReleaseConflict(
                "review approval does not cover the exact release candidate manifest"
            )
        return candidate_sha

    def create(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        release_id: UUID,
        manifest_id: UUID,
        artifact_id: UUID,
        command: CreateRelease,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReleaseRecord:
        with self._session(context, decision) as session:
            candidate_sha = self._validate_inputs(session, context=context, command=command)
            existing = session.execute(
                sa.select(release_table.c.id).where(
                    _scope_clause(release_table, context),
                    release_table.c.release_code == command.release_code,
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise ReleaseConflict("release_code already exists in this tenant")
            base_document = release_manifest_document(command, "0" * 64)
            base_document.pop("manifest_sha256", None)
            manifest_sha = content_sha256(base_document)
            manifest_document = release_manifest_document(command, manifest_sha)
            package_bytes = canonical_json_bytes(manifest_document)
            package_text = package_bytes.decode("utf-8")
            package_sha = hashlib.sha256(package_bytes).hexdigest()
            session.execute(
                sa.insert(release_table).values(
                    id=release_id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=command.classification.value,
                    release_code=command.release_code,
                    title=command.title,
                    channel="reference",
                    state="released",
                    created_at=occurred_at,
                    created_by=actor_id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            session.execute(
                sa.insert(release_manifest_table).values(
                    id=manifest_id,
                    release_id=release_id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=command.classification.value,
                    manifest_sha256=manifest_sha,
                    package_sha256=package_sha,
                    package_size_bytes=len(package_bytes),
                    package_media_type=RELEASE_PACKAGE_MEDIA_TYPE,
                    material_id=command.material_id,
                    material_revision_id=command.material_revision_id,
                    material_state_id=command.material_state_id,
                    material_state_revision_id=command.material_state_revision_id,
                    property_set_id=command.property_set_id,
                    property_set_revision_id=command.property_set_revision_id,
                    material_model_id=command.material_model_id,
                    material_model_revision_id=command.material_model_revision_id,
                    material_model_content_sha256=command.material_model_content_sha256,
                    solver_card_id=command.solver_card_id,
                    solver_card_revision_id=command.solver_card_revision_id,
                    solver_card_content_sha256=command.solver_card_content_sha256,
                    mapping_report_sha256=command.mapping_report_sha256,
                    card_sha256=command.card_sha256,
                    validation_result_id=command.validation_result_id,
                    validation_result_sha256=command.validation_result_sha256,
                    review_request_id=command.review_request_id,
                    review_manifest_sha256=candidate_sha,
                    provenance_snapshot_sha256=command.provenance_snapshot_sha256,
                    created_at=occurred_at,
                    created_by=actor_id,
                    reason=command.reason,
                    state="released",
                )
            )
            session.execute(
                sa.insert(release_artifact_table).values(
                    id=artifact_id,
                    release_id=release_id,
                    release_manifest_id=manifest_id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=command.classification.value,
                    media_type=RELEASE_PACKAGE_MEDIA_TYPE,
                    sha256=package_sha,
                    size_bytes=len(package_bytes),
                    content_text=package_text,
                    created_at=occurred_at,
                    created_by=actor_id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            session.execute(
                sa.insert(release_lifecycle_projection_table).values(
                    release_id=release_id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=command.classification.value,
                    state=ReleaseLifecycleState.RELEASED.value,
                    sequence_no=0,
                    last_event_id=None,
                    updated_at=occurred_at,
                    updated_by=actor_id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            row = self._load(session, context=context, release_id=release_id)
            if row is None:
                raise ReleaseConflict("created release could not be reloaded")
            return _release_record(row)

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        release_id: UUID,
    ) -> ReleaseRecord:
        with self._session(context, decision) as session:
            row = self._load(session, context=context, release_id=release_id)
            if row is None:
                raise ReleaseNotFound("release is not visible")
            return _release_record(row)

    def list(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ReleaseRecord, ...]:
        with self._session(context, decision) as session:
            ids = tuple(
                session.execute(
                    sa.select(release_table.c.id)
                    .where(_scope_clause(release_table, context))
                    .order_by(release_table.c.created_at.desc())
                    .limit(limit)
                ).scalars()
            )
            values: list[ReleaseRecord] = []
            for release_id in ids:
                row = self._load(session, context=context, release_id=cast(UUID, release_id))
                if row is not None:
                    values.append(_release_record(row))
            return tuple(values)

    def supersede(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        release_id: UUID,
        transition_id: UUID,
        command: SupersedeRelease,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReleaseRecord:
        with self._session(context, decision) as session:
            return self._transition(
                session,
                context=context,
                release_id=release_id,
                transition_id=transition_id,
                kind=ReleaseTransitionKind.SUPERSEDE,
                successor_release_id=command.successor_release_id,
                reason=command.reason,
                actor_id=actor_id,
                occurred_at=occurred_at,
            )

    def withdraw(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        release_id: UUID,
        transition_id: UUID,
        command: WithdrawRelease,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReleaseRecord:
        with self._session(context, decision) as session:
            return self._transition(
                session,
                context=context,
                release_id=release_id,
                transition_id=transition_id,
                kind=ReleaseTransitionKind.WITHDRAW,
                successor_release_id=None,
                reason=command.reason,
                actor_id=actor_id,
                occurred_at=occurred_at,
            )

    def record_usage(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        release_id: UUID,
        usage_id: UUID,
        command: RecordReleaseUsage,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> ReleaseUsageRecord:
        with self._session(context, decision) as session:
            projection = self._ensure_projection(
                session,
                context=context,
                release_id=release_id,
                actor_id=actor_id,
                occurred_at=occurred_at,
            )
            if (
                ReleaseLifecycleState(str(projection["state"]))
                is not ReleaseLifecycleState.RELEASED
            ):
                raise ReleaseConflict("only a released Release can be consumed")
            release = (
                session.execute(
                    sa.select(release_table.c.classification).where(
                        _scope_clause(release_table, context), release_table.c.id == release_id
                    )
                )
                .mappings()
                .one()
            )
            values = {
                "id": usage_id,
                "release_id": release_id,
                "organization_id": context.organization_id,
                "project_id": context.project_id,
                "classification": release["classification"],
                "usage_kind": command.usage_kind.value,
                "lifecycle_state": ReleaseLifecycleState.RELEASED.value,
                "used_by": actor_id,
                "used_at": occurred_at,
                "reason": command.reason,
                "request_id": context.request_id,
                "trace_id": context.trace_id,
            }
            session.execute(sa.insert(release_usage_table).values(**values))
            return _usage_record(
                {
                    "usage_id": usage_id,
                    "release_id": release_id,
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                    "classification": release["classification"],
                    "usage_kind": command.usage_kind.value,
                    "used_by": actor_id,
                    "used_at": occurred_at,
                    "reason": command.reason,
                }
            )

    def impact(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        release_id: UUID,
    ) -> ReleaseImpactRecord:
        with self._session(context, decision) as session:
            release_row = self._load(session, context=context, release_id=release_id)
            if release_row is None:
                raise ReleaseNotFound("release is not visible")
            release = _release_record(release_row)
            successor = session.execute(
                sa.select(release_lifecycle_event_table.c.successor_release_id).where(
                    _scope_clause(release_lifecycle_event_table, context),
                    release_lifecycle_event_table.c.release_id == release_id,
                    release_lifecycle_event_table.c.kind == ReleaseTransitionKind.SUPERSEDE.value,
                )
            ).scalar_one_or_none()
            predecessor = session.execute(
                sa.select(release_lifecycle_event_table.c.release_id).where(
                    _scope_clause(release_lifecycle_event_table, context),
                    release_lifecycle_event_table.c.successor_release_id == release_id,
                )
            ).scalar_one_or_none()
            transition_rows = (
                session.execute(
                    sa.select(
                        release_lifecycle_event_table.c.id.label("transition_id"),
                        release_lifecycle_event_table.c.release_id,
                        release_lifecycle_event_table.c.organization_id,
                        release_lifecycle_event_table.c.project_id,
                        release_lifecycle_event_table.c.classification,
                        release_lifecycle_event_table.c.kind,
                        release_lifecycle_event_table.c.from_state,
                        release_lifecycle_event_table.c.to_state,
                        release_lifecycle_event_table.c.successor_release_id,
                        release_lifecycle_event_table.c.reason,
                        release_lifecycle_event_table.c.occurred_at,
                        release_lifecycle_event_table.c.occurred_by,
                    )
                    .where(
                        _scope_clause(release_lifecycle_event_table, context),
                        sa.or_(
                            release_lifecycle_event_table.c.release_id == release_id,
                            release_lifecycle_event_table.c.successor_release_id == release_id,
                        ),
                    )
                    .order_by(release_lifecycle_event_table.c.sequence_no.asc())
                )
                .mappings()
                .all()
            )
            usage_rows = (
                session.execute(
                    sa.select(
                        release_usage_table.c.id.label("usage_id"),
                        release_usage_table.c.release_id,
                        release_usage_table.c.organization_id,
                        release_usage_table.c.project_id,
                        release_usage_table.c.classification,
                        release_usage_table.c.usage_kind,
                        release_usage_table.c.used_by,
                        release_usage_table.c.used_at,
                        release_usage_table.c.reason,
                    )
                    .where(
                        _scope_clause(release_usage_table, context),
                        release_usage_table.c.release_id == release_id,
                    )
                    .order_by(release_usage_table.c.used_at.asc(), release_usage_table.c.id.asc())
                )
                .mappings()
                .all()
            )
            warning = None
            if release.lifecycle_state is ReleaseLifecycleState.SUPERSEDED:
                warning = (
                    "Release has been superseded; consumers must explicitly select its successor "
                    "and must not silently substitute it."
                )
            elif release.lifecycle_state is ReleaseLifecycleState.WITHDRAWN:
                warning = "Release has been withdrawn; do not use it for new solver runs."
            return ReleaseImpactRecord(
                release=release,
                predecessor_release_id=cast(UUID | None, predecessor),
                successor_release_id=cast(UUID | None, successor),
                usages=tuple(_usage_record(row) for row in usage_rows),
                transitions=tuple(_transition_record(row) for row in transition_rows),
                warning=warning,
            )
