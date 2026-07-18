"""PostgreSQL adapter for T-42 master-curve Plans, Runs, and shift evidence."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.datasets.application.viscoelastic_master import (
    ViscoelasticDerivedDatasetSnapshot,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.viscoelastic_master_curve import (
    VISCOELASTIC_MASTER_PLAN_AGGREGATE_TYPE,
    RevisionSnapshot,
    ViscoelasticMasterRepository,
    ViscoelasticMasterRun,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    ProcessingNotFound,
    ProcessingRunStatus,
)
from cmp.modules.processing.domain.viscoelastic_master_curve import (
    ManualShiftFactor,
    ShiftFactorEvidence,
    ShiftMethod,
    ViscoelasticMasterPlanContent,
    ViscoelasticMasterResult,
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
plan_table = sa.Table(
    "viscoelastic_master_plan",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_label", sa.String(160), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="processing",
)
plan_revision_table = sa.Table(
    "viscoelastic_master_plan_revision",
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
    sa.Column("plan_label", sa.String(160), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("reference_temperature_k", sa.Double(), nullable=False),
    sa.Column("grid_point_count", sa.SmallInteger(), nullable=False),
    sa.Column("shift_method", sa.String(32), nullable=False),
    sa.Column("interpolation", sa.String(64), nullable=False),
    sa.Column("domain_policy", sa.String(64), nullable=False),
    sa.Column("reduced_time_convention", sa.String(64), nullable=False),
    schema="processing",
)
manual_shift_table = sa.Table(
    "viscoelastic_master_plan_manual_shift",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("temperature_k", sa.Double(), nullable=False),
    sa.Column("log10_a_t", sa.Double(), nullable=False),
    schema="processing",
)
run_table = sa.Table(
    "viscoelastic_master_run",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plan_id", sa.Uuid(), nullable=False),
    sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("source_curve_count", sa.SmallInteger(), nullable=False),
    sa.Column("temperature_count", sa.SmallInteger(), nullable=False),
    sa.Column("aligned_row_count", sa.BigInteger(), nullable=True),
    sa.Column("statistics_row_count", sa.BigInteger(), nullable=True),
    sa.Column("master_row_count", sa.BigInteger(), nullable=True),
    sa.Column("aligned_dataset_id", sa.Uuid(), nullable=True),
    sa.Column("aligned_dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("statistics_dataset_id", sa.Uuid(), nullable=True),
    sa.Column("statistics_dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("master_dataset_id", sa.Uuid(), nullable=True),
    sa.Column("master_dataset_revision_id", sa.Uuid(), nullable=True),
    sa.Column("wlf_c1", sa.Double(), nullable=True),
    sa.Column("wlf_c2_k", sa.Double(), nullable=True),
    sa.Column("arrhenius_activation_energy_j_per_mol", sa.Double(), nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("change_reason", sa.Text(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="processing",
)
shift_factor_table = sa.Table(
    "viscoelastic_master_shift_factor",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("processing_run_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("temperature_k", sa.Double(), nullable=False),
    sa.Column("log10_a_t", sa.Double(), nullable=False),
    sa.Column("source", sa.String(32), nullable=False),
    sa.Column("observed_log10_a_t", sa.Double(), nullable=True),
    sa.Column("residual_log10_a_t", sa.Double(), nullable=True),
    sa.Column("alignment_rmse_pa", sa.Double(), nullable=True),
    schema="processing",
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=VISCOELASTIC_MASTER_PLAN_AGGREGATE_TYPE,
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


def _write_manual_shifts(session: Session, draft: Any) -> None:
    content = cast(ViscoelasticMasterPlanContent, draft.content)
    if not content.manual_shift_factors:
        return
    session.execute(
        sa.insert(manual_shift_table),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "plan_id": draft.aggregate_id,
                "plan_revision_id": draft.revision_id,
                "ordinal": ordinal,
                "temperature_k": item.temperature_k,
                "log10_a_t": item.log10_a_t,
            }
            for ordinal, item in enumerate(
                sorted(content.manual_shift_factors, key=lambda value: value.temperature_k)
            )
        ],
    )


_PLAN_TABLES = TypedRevisionTables[ViscoelasticMasterPlanContent](
    aggregate_type=VISCOELASTIC_MASTER_PLAN_AGGREGATE_TYPE,
    identity_table=plan_table,
    revision_table=plan_revision_table,
    canonical_content=lambda value: value.canonical(),
    content_values=lambda value: {
        "plan_label": value.plan_label,
        "selection_id": value.selection_id,
        "selection_revision_id": value.selection_revision_id,
        "reference_temperature_k": value.reference_temperature_k,
        "grid_point_count": value.grid_point_count,
        "shift_method": value.shift_method.value,
        "interpolation": value.interpolation,
        "domain_policy": value.domain_policy,
        "reduced_time_convention": value.reduced_time_convention,
    },
    identity_values=lambda value: {
        "plan_label": value.plan_label,
        "selection_id": value.selection_id,
    },
    revision_content_writer=_write_manual_shifts,
)


def _content(session: Session, row: Any) -> ViscoelasticMasterPlanContent:
    shifts = (
        session.execute(
            sa.select(manual_shift_table)
            .where(manual_shift_table.c.plan_revision_id == row["id"])
            .order_by(manual_shift_table.c.ordinal)
        )
        .mappings()
        .all()
    )
    return ViscoelasticMasterPlanContent(
        plan_label=str(row["plan_label"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        reference_temperature_k=float(row["reference_temperature_k"]),
        grid_point_count=int(row["grid_point_count"]),
        shift_method=ShiftMethod(str(row["shift_method"])),
        manual_shift_factors=tuple(
            ManualShiftFactor(float(item["temperature_k"]), float(item["log10_a_t"]))
            for item in shifts
        ),
        interpolation=str(row["interpolation"]),
        domain_policy=str(row["domain_policy"]),
        reduced_time_convention=str(row["reduced_time_convention"]),
    )


def _shift_factors(session: Session, run_id: UUID) -> tuple[ShiftFactorEvidence, ...]:
    rows = (
        session.execute(
            sa.select(shift_factor_table)
            .where(shift_factor_table.c.processing_run_id == run_id)
            .order_by(shift_factor_table.c.ordinal)
        )
        .mappings()
        .all()
    )
    return tuple(
        ShiftFactorEvidence(
            temperature_k=float(row["temperature_k"]),
            log10_a_t=float(row["log10_a_t"]),
            source=str(row["source"]),
            observed_log10_a_t=(
                float(row["observed_log10_a_t"])
                if row["observed_log10_a_t"] is not None
                else None
            ),
            residual_log10_a_t=(
                float(row["residual_log10_a_t"])
                if row["residual_log10_a_t"] is not None
                else None
            ),
            alignment_rmse_pa=(
                float(row["alignment_rmse_pa"])
                if row["alignment_rmse_pa"] is not None
                else None
            ),
        )
        for row in rows
    )


def _run(session: Session, row: Any) -> ViscoelasticMasterRun:
    return ViscoelasticMasterRun(
        id=cast(UUID, row["id"]),
        scope=TenantScope(
            cast(UUID, row["organization_id"]),
            cast(UUID, row["project_id"]),
            str(row["classification"]),
        ),
        plan_id=cast(UUID, row["plan_id"]),
        plan_revision_id=cast(UUID, row["plan_revision_id"]),
        selection_id=cast(UUID, row["selection_id"]),
        selection_revision_id=cast(UUID, row["selection_revision_id"]),
        status=ProcessingRunStatus(str(row["status"])),
        source_curve_count=int(row["source_curve_count"]),
        temperature_count=int(row["temperature_count"]),
        aligned_row_count=cast(int | None, row["aligned_row_count"]),
        statistics_row_count=cast(int | None, row["statistics_row_count"]),
        master_row_count=cast(int | None, row["master_row_count"]),
        aligned_dataset_id=cast(UUID | None, row["aligned_dataset_id"]),
        aligned_dataset_revision_id=cast(UUID | None, row["aligned_dataset_revision_id"]),
        statistics_dataset_id=cast(UUID | None, row["statistics_dataset_id"]),
        statistics_dataset_revision_id=cast(
            UUID | None, row["statistics_dataset_revision_id"]
        ),
        master_dataset_id=cast(UUID | None, row["master_dataset_id"]),
        master_dataset_revision_id=cast(UUID | None, row["master_dataset_revision_id"]),
        wlf_c1=cast(float | None, row["wlf_c1"]),
        wlf_c2_k=cast(float | None, row["wlf_c2_k"]),
        arrhenius_activation_energy_j_per_mol=cast(
            float | None, row["arrhenius_activation_energy_j_per_mol"]
        ),
        shift_factors=_shift_factors(session, cast(UUID, row["id"])),
        failure_code=cast(str | None, row["failure_code"]),
        change_reason=str(row["change_reason"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_by=cast(UUID, row["created_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


class SqlAlchemyViscoelasticMasterRepository(ViscoelasticMasterRepository):
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
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @contextmanager
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ViscoelasticMasterPlanContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_PLAN_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(plan_revision_table).where(
                        plan_revision_table.c.aggregate_id == plan_id,
                        plan_revision_table.c.id == plan_revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProcessingNotFound("viscoelastic master Plan revision is not visible")
            return RevisionSnapshot(_record(row), _content(session, row))

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ViscoelasticMasterRun,
    ) -> ViscoelasticMasterRun:
        with self._session(context, decision) as session:
            session.execute(
                sa.insert(run_table).values(
                    id=run.id,
                    organization_id=run.scope.organization_id,
                    project_id=run.scope.project_id,
                    classification=run.scope.classification,
                    plan_id=run.plan_id,
                    plan_revision_id=run.plan_revision_id,
                    selection_id=run.selection_id,
                    selection_revision_id=run.selection_revision_id,
                    status=run.status.value,
                    source_curve_count=run.source_curve_count,
                    temperature_count=run.temperature_count,
                    change_reason=run.change_reason,
                    started_at=run.started_at,
                    created_by=run.created_by,
                    request_id=run.request_id,
                    trace_id=run.trace_id,
                )
            )
        return run

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        result: ViscoelasticMasterResult,
        aligned: ViscoelasticDerivedDatasetSnapshot,
        statistics: ViscoelasticDerivedDatasetSnapshot,
        master: ViscoelasticDerivedDatasetSnapshot,
    ) -> ViscoelasticMasterRun:
        with self._session(context, decision) as session:
            current = (
                session.execute(sa.select(run_table).where(run_table.c.id == run_id))
                .mappings()
                .one_or_none()
            )
            if current is None:
                raise ProcessingNotFound("viscoelastic master Run is not visible")
            scope_values = {
                "organization_id": current["organization_id"],
                "project_id": current["project_id"],
                "classification": current["classification"],
            }
            session.execute(
                sa.insert(shift_factor_table),
                [
                    {
                        **scope_values,
                        "processing_run_id": run_id,
                        "ordinal": ordinal,
                        "temperature_k": item.temperature_k,
                        "log10_a_t": item.log10_a_t,
                        "source": item.source,
                        "observed_log10_a_t": item.observed_log10_a_t,
                        "residual_log10_a_t": item.residual_log10_a_t,
                        "alignment_rmse_pa": item.alignment_rmse_pa,
                    }
                    for ordinal, item in enumerate(result.shift_factors)
                ],
            )
            row = (
                session.execute(
                    sa.update(run_table)
                    .where(
                        run_table.c.id == run_id,
                        run_table.c.status == ProcessingRunStatus.EXECUTING.value,
                    )
                    .values(
                        status=ProcessingRunStatus.SUCCEEDED.value,
                        aligned_row_count=aligned.current.content.row_count,
                        statistics_row_count=statistics.current.content.row_count,
                        master_row_count=master.current.content.row_count,
                        aligned_dataset_id=aligned.id,
                        aligned_dataset_revision_id=aligned.current.record.revision_id,
                        statistics_dataset_id=statistics.id,
                        statistics_dataset_revision_id=statistics.current.record.revision_id,
                        master_dataset_id=master.id,
                        master_dataset_revision_id=master.current.record.revision_id,
                        wlf_c1=result.wlf_c1,
                        wlf_c2_k=result.wlf_c2_k,
                        arrhenius_activation_energy_j_per_mol=(
                            result.arrhenius_activation_energy_j_per_mol
                        ),
                        ended_at=datetime.now(UTC),
                    )
                    .returning(run_table)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProcessingNotFound("executing viscoelastic master Run is not visible")
            return _run(session, row)

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> ViscoelasticMasterRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.update(run_table)
                    .where(
                        run_table.c.id == run_id,
                        run_table.c.status == ProcessingRunStatus.EXECUTING.value,
                    )
                    .values(
                        status=ProcessingRunStatus.FAILED.value,
                        failure_code=failure_code,
                        ended_at=datetime.now(UTC),
                    )
                    .returning(run_table)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProcessingNotFound("executing viscoelastic master Run is not visible")
            return _run(session, row)

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ViscoelasticMasterRun:
        with self._session(context, decision) as session:
            row = (
                session.execute(sa.select(run_table).where(run_table.c.id == run_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProcessingNotFound("viscoelastic master Run is not visible")
            return _run(session, row)
