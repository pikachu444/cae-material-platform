"""PostgreSQL persistence for append-only common Processing Batch evidence (T-54)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Literal, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_batches import (
    CommonBatchNotFound,
    CommonBatchRepository,
    ProcessingExecutionOrigin,
)
from cmp.modules.processing.application.common_outputs import (
    FitDecisionParameter,
    FitDecisionParameterSet,
    FitDecisionSnapshot,
    ProcessingWorkupOverride,
    fit_decision_canonical,
)
from cmp.modules.processing.domain.common_batches import (
    BatchAttempt,
    BatchAttemptStatus,
    BatchMemberPlan,
    BatchRevisionPin,
    CommonProcessingBatch,
)
from cmp.shared.domain.revisions import TenantScope


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


metadata = sa.MetaData()
batch_table = sa.Table(
    "common_processing_batch",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("label", sa.String(200), nullable=False),
    sa.Column("recipe_id", sa.Uuid(), nullable=False),
    sa.Column("recipe_revision_id", sa.Uuid(), nullable=False),
    sa.Column("recipe_sha256", sa.CHAR(64), nullable=False),
    sa.Column("member_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="processing",
)
member_table = sa.Table(
    "common_processing_batch_member",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("batch_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("source_document_id", sa.Uuid(), nullable=False),
    sa.Column("source_document_revision_id", sa.Uuid(), nullable=False),
    sa.Column("source_document_sha256", sa.CHAR(64), nullable=False),
    sa.Column("workup_overrides", JSONB(), nullable=False),
    sa.Column("fit_decision", JSONB(none_as_null=True), nullable=True),
    schema="processing",
)
attempt_table = sa.Table(
    "common_processing_batch_attempt",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("batch_id", sa.Uuid(), nullable=False),
    sa.Column("member_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("attempt_no", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("output_id", sa.Uuid(), nullable=True),
    sa.Column("output_revision_id", sa.Uuid(), nullable=True),
    sa.Column("error_code", sa.String(160), nullable=True),
    sa.Column("error_detail", sa.Text(), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    schema="processing",
)


def _workup_overrides(value: Any) -> tuple[ProcessingWorkupOverride, ...]:
    if value is None:
        return ()
    return tuple(
        ProcessingWorkupOverride(
            kind=cast(Literal["youngs_modulus", "necking_boundary"], str(item["kind"])),
            original_value=float(item["original_value"]),
            original_unit=str(item["original_unit"]),
            canonical_value=float(item["canonical_value"]),
            canonical_unit=str(item["canonical_unit"]),
            reason=str(item["reason"]),
        )
        for item in value
    )


def _fit_decision(value: Any) -> FitDecisionSnapshot | None:
    if value is None:
        return None
    return FitDecisionSnapshot(
        candidate_key=str(value["candidate_key"]),
        mode=cast(Literal["single", "blend"], str(value["mode"])),
        primary_law=str(value["primary_law"]),
        secondary_law=value["secondary_law"],
        primary_weight=value["primary_weight"],
        parameter_sets=tuple(
            FitDecisionParameterSet(
                law=str(item["law"]),
                parameters=tuple(
                    FitDecisionParameter(
                        name=str(parameter["name"]),
                        value=float(parameter["value"]),
                        unit=str(parameter["unit"]),
                        lower=(
                            None
                            if parameter["lower"] is None
                            else float(parameter["lower"])
                        ),
                        upper=(
                            None
                            if parameter["upper"] is None
                            else float(parameter["upper"])
                        ),
                    )
                    for parameter in item["parameters"]
                ),
            )
            for item in value["parameter_sets"]
        ),
        fit_minimum=float(value["fit_minimum"]),
        fit_maximum=float(value["fit_maximum"]),
        extrapolation_maximum=(
            None
            if value["extrapolation_maximum"] is None
            else float(value["extrapolation_maximum"])
        ),
        extrapolation_policy=str(value["extrapolation_policy"]),
        metric_definition=str(value["metric_definition"]),
        metric_value=float(value["metric_value"]),
        requested_term_policy=value["requested_term_policy"],
        actual_term_count=value["actual_term_count"],
        selection_reason=str(value["selection_reason"]),
        warning_acknowledged=bool(value["warning_acknowledged"]),
    )


class SqlAlchemyCommonBatchRepository(CommonBatchRepository):
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

    def create_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch: CommonProcessingBatch,
    ) -> None:
        common = {
            "organization_id": batch.scope.organization_id,
            "project_id": batch.scope.project_id,
            "classification": batch.scope.classification,
        }
        with self._session(context, decision) as session:
            session.execute(
                sa.insert(batch_table).values(
                    **common,
                    id=batch.batch_id,
                    label=batch.label,
                    recipe_id=batch.recipe.aggregate_id,
                    recipe_revision_id=batch.recipe.revision_id,
                    recipe_sha256=batch.recipe_sha256,
                    member_count=len(batch.members),
                    created_at=batch.created_at,
                    created_by=batch.created_by,
                    request_id=batch.request_id,
                    trace_id=batch.trace_id,
                )
            )
            session.execute(
                sa.insert(member_table),
                [
                    {
                        **common,
                        "id": member.member_id,
                        "batch_id": batch.batch_id,
                        "ordinal": member.ordinal,
                        "source_document_id": member.source_document.aggregate_id,
                        "source_document_revision_id": member.source_document.revision_id,
                        "source_document_sha256": member.source_document_sha256,
                        "workup_overrides": [
                            {
                                "kind": override.kind,
                                "original_value": override.original_value,
                                "original_unit": override.original_unit,
                                "canonical_value": override.canonical_value,
                                "canonical_unit": override.canonical_unit,
                                "reason": override.reason,
                            }
                            for override in member.workup_overrides
                        ],
                        "fit_decision": fit_decision_canonical(member.fit_decision),
                    }
                    for member in batch.members
                ],
            )

    def append_attempt(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch_id: UUID,
        attempt: BatchAttempt,
    ) -> None:
        with self._session(context, decision) as session:
            member = (
                session.execute(
                    sa.select(member_table).where(
                        member_table.c.batch_id == batch_id,
                        member_table.c.id == attempt.member_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if member is None:
                raise CommonBatchNotFound("Processing Batch member is not visible")
            session.execute(
                sa.insert(attempt_table).values(
                    id=attempt.attempt_id,
                    batch_id=batch_id,
                    member_id=attempt.member_id,
                    organization_id=member["organization_id"],
                    project_id=member["project_id"],
                    classification=member["classification"],
                    attempt_no=attempt.attempt_no,
                    status=attempt.status.value,
                    output_id=(attempt.output.aggregate_id if attempt.output else None),
                    output_revision_id=(attempt.output.revision_id if attempt.output else None),
                    error_code=attempt.error_code,
                    error_detail=attempt.error_detail,
                    started_at=attempt.started_at,
                    completed_at=attempt.completed_at,
                )
            )

    @staticmethod
    def _hydrate(session: Session, row: Any) -> CommonProcessingBatch:
        members = (
            session.execute(
                sa.select(member_table)
                .where(member_table.c.batch_id == row["id"])
                .order_by(member_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        attempts = (
            session.execute(
                sa.select(attempt_table)
                .where(attempt_table.c.batch_id == row["id"])
                .order_by(attempt_table.c.member_id, attempt_table.c.attempt_no)
            )
            .mappings()
            .all()
        )
        return CommonProcessingBatch(
            batch_id=cast(UUID, row["id"]),
            scope=TenantScope(
                cast(UUID, row["organization_id"]),
                cast(UUID, row["project_id"]),
                str(row["classification"]),
            ),
            label=str(row["label"]),
            recipe=BatchRevisionPin(
                cast(UUID, row["recipe_id"]), cast(UUID, row["recipe_revision_id"])
            ),
            recipe_sha256=str(row["recipe_sha256"]),
            members=tuple(
                BatchMemberPlan(
                    member_id=cast(UUID, item["id"]),
                    ordinal=int(item["ordinal"]),
                    source_document=BatchRevisionPin(
                        cast(UUID, item["source_document_id"]),
                        cast(UUID, item["source_document_revision_id"]),
                    ),
                    source_document_sha256=str(item["source_document_sha256"]),
                    workup_overrides=_workup_overrides(item["workup_overrides"]),
                    fit_decision=_fit_decision(item["fit_decision"]),
                )
                for item in members
            ),
            attempts=tuple(
                BatchAttempt(
                    attempt_id=cast(UUID, item["id"]),
                    member_id=cast(UUID, item["member_id"]),
                    attempt_no=int(item["attempt_no"]),
                    status=BatchAttemptStatus(str(item["status"])),
                    output=(
                        BatchRevisionPin(
                            cast(UUID, item["output_id"]),
                            cast(UUID, item["output_revision_id"]),
                        )
                        if item["output_id"] is not None
                        else None
                    ),
                    error_code=cast(str | None, item["error_code"]),
                    error_detail=cast(str | None, item["error_detail"]),
                    started_at=item["started_at"],
                    completed_at=item["completed_at"],
                )
                for item in attempts
            ),
            created_at=row["created_at"],
            created_by=cast(UUID, row["created_by"]),
            request_id=cast(UUID, row["request_id"]),
            trace_id=str(row["trace_id"]),
        )

    def get_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch_id: UUID,
    ) -> CommonProcessingBatch:
        with self._session(context, decision) as session:
            row = (
                session.execute(sa.select(batch_table).where(batch_table.c.id == batch_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise CommonBatchNotFound("Processing Batch is not visible")
            return self._hydrate(session, row)

    def list_batches(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[CommonProcessingBatch, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(batch_table).order_by(
                        batch_table.c.created_at.desc(), batch_table.c.id
                    )
                )
                .mappings()
                .all()
            )
            return tuple(self._hydrate(session, row) for row in rows)

    def find_execution_origin(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
        output_revision_id: UUID,
    ) -> ProcessingExecutionOrigin | None:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(
                        batch_table.c.recipe_id,
                        batch_table.c.recipe_revision_id,
                        batch_table.c.recipe_sha256,
                        batch_table.c.id.label("batch_id"),
                        attempt_table.c.member_id,
                        attempt_table.c.id.label("attempt_id"),
                        attempt_table.c.attempt_no,
                    )
                    .select_from(
                        attempt_table.join(
                            batch_table,
                            sa.and_(
                                batch_table.c.organization_id == attempt_table.c.organization_id,
                                batch_table.c.project_id == attempt_table.c.project_id,
                                batch_table.c.classification == attempt_table.c.classification,
                                batch_table.c.id == attempt_table.c.batch_id,
                            ),
                        )
                    )
                    .where(
                        attempt_table.c.output_id == output_id,
                        attempt_table.c.output_revision_id == output_revision_id,
                        attempt_table.c.status == BatchAttemptStatus.SUCCEEDED.value,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            return ProcessingExecutionOrigin(
                recipe_id=cast(UUID, row["recipe_id"]),
                recipe_revision_id=cast(UUID, row["recipe_revision_id"]),
                recipe_sha256=str(row["recipe_sha256"]),
                batch_id=cast(UUID, row["batch_id"]),
                member_id=cast(UUID, row["member_id"]),
                attempt_id=cast(UUID, row["attempt_id"]),
                attempt_no=int(row["attempt_no"]),
            )
