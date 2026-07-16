"""PostgreSQL adapter for typed Test Campaign, Instrument, and Run context revisions."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.adapters.persistence.repository import RlsContext
from cmp.modules.testing.application.test_context import (
    CALIBRATION_AGGREGATE_TYPE,
    CAMPAIGN_AGGREGATE_TYPE,
    CONDITION_AGGREGATE_TYPE,
    INSTRUMENT_AGGREGATE_TYPE,
    RUN_CONTEXT_AGGREGATE_TYPE,
    CalibrationSnapshot,
    CampaignSnapshot,
    ConditionSnapshot,
    ContextRevisionSnapshot,
    ExactSource,
    InstrumentSnapshot,
    RunContextSnapshot,
    TestContextRepository,
)
from cmp.modules.testing.domain.reference_tensile import TestingNotFound, TestRunContent
from cmp.modules.testing.domain.test_context import (
    CalibrationResult,
    InstrumentCalibrationContent,
    InstrumentContent,
    LoadingRateUnit,
    StandardConformance,
    TestCampaignContent,
    TestConditionContent,
    TestRunContextContent,
    calibration_canonical,
    campaign_canonical,
    condition_canonical,
    instrument_canonical,
    run_context_canonical,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

metadata = sa.MetaData()


def _identity_table(name: str, *columns: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        *columns,
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="testing",
    )


def _revision_table(name: str, *columns: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
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
        *columns,
        schema="testing",
    )


campaign_table = _identity_table(
    "test_campaign",
    sa.Column("test_method_id", sa.Uuid(), nullable=False),
    sa.Column("campaign_code", sa.String(100), nullable=False),
)
campaign_revision_table = _revision_table(
    "test_campaign_revision",
    sa.Column("test_method_id", sa.Uuid(), nullable=False),
    sa.Column("test_method_revision_id", sa.Uuid(), nullable=False),
    sa.Column("campaign_code", sa.String(100), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("objective", sa.Text(), nullable=False),
    sa.Column("population_description", sa.Text(), nullable=False),
    sa.Column("planned_specimen_count", sa.Integer(), nullable=False),
    sa.Column("standard_conformance", sa.String(32), nullable=False),
    sa.Column("standard_designation", sa.String(200), nullable=True),
    sa.Column("standard_edition", sa.String(100), nullable=True),
    sa.Column("standard_deviation_reason", sa.Text(), nullable=True),
    sa.Column("reference_only", sa.Boolean(), nullable=False),
)
instrument_table = _identity_table(
    "instrument",
    sa.Column("instrument_code", sa.String(100), nullable=False),
    sa.Column("serial_number", sa.String(200), nullable=False),
)
instrument_revision_table = _revision_table(
    "instrument_revision",
    sa.Column("instrument_code", sa.String(100), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("serial_number", sa.String(200), nullable=False),
    sa.Column("manufacturer", sa.String(200), nullable=True),
    sa.Column("model", sa.String(200), nullable=True),
    sa.Column("location", sa.String(255), nullable=True),
    sa.Column("description", sa.Text(), nullable=True),
)
calibration_table = _identity_table(
    "instrument_calibration",
    sa.Column("instrument_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_code", sa.String(100), nullable=False),
)
calibration_revision_table = _revision_table(
    "instrument_calibration_revision",
    sa.Column("instrument_id", sa.Uuid(), nullable=False),
    sa.Column("instrument_revision_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_code", sa.String(100), nullable=False),
    sa.Column("certificate_reference", sa.String(255), nullable=False),
    sa.Column("provider", sa.String(200), nullable=False),
    sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
    sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
    sa.Column("result", sa.String(32), nullable=False),
    sa.Column("limitation_note", sa.Text(), nullable=True),
)
condition_table = _identity_table(
    "test_condition_snapshot",
    sa.Column("test_method_id", sa.Uuid(), nullable=False),
    sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
)
condition_revision_table = _revision_table(
    "test_condition_snapshot_revision",
    sa.Column("test_method_id", sa.Uuid(), nullable=False),
    sa.Column("test_method_revision_id", sa.Uuid(), nullable=False),
    sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("temperature_setpoint_k", sa.Numeric(18, 8), nullable=True),
    sa.Column("temperature_observed_k", sa.Numeric(18, 8), nullable=True),
    sa.Column("humidity_setpoint_pct", sa.Numeric(18, 8), nullable=True),
    sa.Column("humidity_observed_pct", sa.Numeric(18, 8), nullable=True),
    sa.Column("loading_rate_value", sa.Numeric(30, 12), nullable=True),
    sa.Column("loading_rate_unit", sa.String(32), nullable=True),
    sa.Column("orientation", sa.String(100), nullable=True),
    sa.Column("medium", sa.String(200), nullable=True),
    sa.Column("note", sa.Text(), nullable=True),
)
run_context_table = _identity_table(
    "test_run_context",
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
)
run_context_revision_table = _revision_table(
    "test_run_context_revision",
    sa.Column("test_run_id", sa.Uuid(), nullable=False),
    sa.Column("test_run_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_campaign_id", sa.Uuid(), nullable=False),
    sa.Column("test_campaign_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_condition_id", sa.Uuid(), nullable=False),
    sa.Column("test_condition_revision_id", sa.Uuid(), nullable=False),
    sa.Column("instrument_id", sa.Uuid(), nullable=False),
    sa.Column("instrument_revision_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_revision_id", sa.Uuid(), nullable=False),
    sa.Column("note", sa.Text(), nullable=True),
)

test_method_revision_table = sa.Table(
    "test_method_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    schema="testing",
)
test_run_revision_table = sa.Table(
    "test_run_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("specimen_id", sa.Uuid(), nullable=False),
    sa.Column("specimen_revision_id", sa.Uuid(), nullable=False),
    sa.Column("test_method_id", sa.Uuid(), nullable=False),
    sa.Column("test_method_revision_id", sa.Uuid(), nullable=False),
    sa.Column("run_label", sa.String(160), nullable=False),
    sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("test_temperature_k", sa.Double(), nullable=True),
    sa.Column("crosshead_speed_mm_per_min", sa.Double(), nullable=True),
    sa.Column("reference_only", sa.Boolean(), nullable=False),
    schema="testing",
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


def _record(row: Any, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=aggregate_type,
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


def _campaign(row: Any) -> TestCampaignContent:
    return TestCampaignContent(
        test_method_id=cast(UUID, row["test_method_id"]),
        test_method_revision_id=cast(UUID, row["test_method_revision_id"]),
        campaign_code=str(row["campaign_code"]),
        name=str(row["name"]),
        objective=str(row["objective"]),
        population_description=str(row["population_description"]),
        planned_specimen_count=int(row["planned_specimen_count"]),
        standard_conformance=StandardConformance(str(row["standard_conformance"])),
        standard_designation=(
            str(row["standard_designation"]) if row["standard_designation"] is not None else None
        ),
        standard_edition=(
            str(row["standard_edition"]) if row["standard_edition"] is not None else None
        ),
        standard_deviation_reason=(
            str(row["standard_deviation_reason"])
            if row["standard_deviation_reason"] is not None
            else None
        ),
        reference_only=bool(row["reference_only"]),
    )


def _instrument(row: Any) -> InstrumentContent:
    def optional(name: str) -> str | None:
        return str(row[name]) if row[name] is not None else None

    return InstrumentContent(
        str(row["instrument_code"]),
        str(row["name"]),
        str(row["serial_number"]),
        optional("manufacturer"),
        optional("model"),
        optional("location"),
        optional("description"),
    )


def _calibration(row: Any) -> InstrumentCalibrationContent:
    return InstrumentCalibrationContent(
        instrument_id=cast(UUID, row["instrument_id"]),
        instrument_revision_id=cast(UUID, row["instrument_revision_id"]),
        calibration_code=str(row["calibration_code"]),
        certificate_reference=str(row["certificate_reference"]),
        provider=str(row["provider"]),
        calibrated_at=row["calibrated_at"],
        valid_from=row["valid_from"],
        valid_until=row["valid_until"],
        result=CalibrationResult(str(row["result"])),
        limitation_note=(
            str(row["limitation_note"]) if row["limitation_note"] is not None else None
        ),
    )


def _condition(row: Any) -> TestConditionContent:
    def decimal(name: str) -> Decimal | None:
        return cast(Decimal | None, row[name])

    return TestConditionContent(
        test_method_id=cast(UUID, row["test_method_id"]),
        test_method_revision_id=cast(UUID, row["test_method_revision_id"]),
        captured_at=row["captured_at"],
        temperature_setpoint_k=decimal("temperature_setpoint_k"),
        temperature_observed_k=decimal("temperature_observed_k"),
        humidity_setpoint_pct=decimal("humidity_setpoint_pct"),
        humidity_observed_pct=decimal("humidity_observed_pct"),
        loading_rate_value=decimal("loading_rate_value"),
        loading_rate_unit=(
            LoadingRateUnit(str(row["loading_rate_unit"]))
            if row["loading_rate_unit"] is not None
            else None
        ),
        orientation=str(row["orientation"]) if row["orientation"] is not None else None,
        medium=str(row["medium"]) if row["medium"] is not None else None,
        note=str(row["note"]) if row["note"] is not None else None,
    )


def _run_context(row: Any) -> TestRunContextContent:
    return TestRunContextContent(
        test_run_id=cast(UUID, row["test_run_id"]),
        test_run_revision_id=cast(UUID, row["test_run_revision_id"]),
        test_campaign_id=cast(UUID, row["test_campaign_id"]),
        test_campaign_revision_id=cast(UUID, row["test_campaign_revision_id"]),
        test_condition_id=cast(UUID, row["test_condition_id"]),
        test_condition_revision_id=cast(UUID, row["test_condition_revision_id"]),
        instrument_id=cast(UUID, row["instrument_id"]),
        instrument_revision_id=cast(UUID, row["instrument_revision_id"]),
        calibration_id=cast(UUID, row["calibration_id"]),
        calibration_revision_id=cast(UUID, row["calibration_revision_id"]),
        note=str(row["note"]) if row["note"] is not None else None,
    )


def _campaign_values(value: TestCampaignContent) -> dict[str, object]:
    return {
        **campaign_canonical(value),
        "test_method_id": value.test_method_id,
        "test_method_revision_id": value.test_method_revision_id,
        "standard_conformance": value.standard_conformance.value,
    }


def _instrument_values(value: InstrumentContent) -> dict[str, object]:
    return instrument_canonical(value)


def _calibration_values(value: InstrumentCalibrationContent) -> dict[str, object]:
    return {
        "instrument_id": value.instrument_id,
        "instrument_revision_id": value.instrument_revision_id,
        "calibration_code": value.calibration_code,
        "certificate_reference": value.certificate_reference,
        "provider": value.provider,
        "calibrated_at": value.calibrated_at,
        "valid_from": value.valid_from,
        "valid_until": value.valid_until,
        "result": value.result.value,
        "limitation_note": value.limitation_note,
    }


def _condition_values(value: TestConditionContent) -> dict[str, object]:
    return {
        "test_method_id": value.test_method_id,
        "test_method_revision_id": value.test_method_revision_id,
        "captured_at": value.captured_at,
        "temperature_setpoint_k": value.temperature_setpoint_k,
        "temperature_observed_k": value.temperature_observed_k,
        "humidity_setpoint_pct": value.humidity_setpoint_pct,
        "humidity_observed_pct": value.humidity_observed_pct,
        "loading_rate_value": value.loading_rate_value,
        "loading_rate_unit": value.loading_rate_unit.value if value.loading_rate_unit else None,
        "orientation": value.orientation,
        "medium": value.medium,
        "note": value.note,
    }


def _context_values(value: TestRunContextContent) -> dict[str, object]:
    return {
        "test_run_id": value.test_run_id,
        "test_run_revision_id": value.test_run_revision_id,
        "test_campaign_id": value.test_campaign_id,
        "test_campaign_revision_id": value.test_campaign_revision_id,
        "test_condition_id": value.test_condition_id,
        "test_condition_revision_id": value.test_condition_revision_id,
        "instrument_id": value.instrument_id,
        "instrument_revision_id": value.instrument_revision_id,
        "calibration_id": value.calibration_id,
        "calibration_revision_id": value.calibration_revision_id,
        "note": value.note,
    }


_CAMPAIGN_TABLES = TypedRevisionTables(
    aggregate_type=CAMPAIGN_AGGREGATE_TYPE,
    identity_table=campaign_table,
    revision_table=campaign_revision_table,
    canonical_content=campaign_canonical,
    content_values=_campaign_values,
    identity_values=lambda value: {
        "test_method_id": value.test_method_id,
        "campaign_code": value.campaign_code,
    },
)
_INSTRUMENT_TABLES = TypedRevisionTables(
    aggregate_type=INSTRUMENT_AGGREGATE_TYPE,
    identity_table=instrument_table,
    revision_table=instrument_revision_table,
    canonical_content=instrument_canonical,
    content_values=_instrument_values,
    identity_values=lambda value: {
        "instrument_code": value.instrument_code,
        "serial_number": value.serial_number,
    },
)
_CALIBRATION_TABLES = TypedRevisionTables(
    aggregate_type=CALIBRATION_AGGREGATE_TYPE,
    identity_table=calibration_table,
    revision_table=calibration_revision_table,
    canonical_content=calibration_canonical,
    content_values=_calibration_values,
    identity_values=lambda value: {
        "instrument_id": value.instrument_id,
        "calibration_code": value.calibration_code,
    },
)
_CONDITION_TABLES = TypedRevisionTables(
    aggregate_type=CONDITION_AGGREGATE_TYPE,
    identity_table=condition_table,
    revision_table=condition_revision_table,
    canonical_content=condition_canonical,
    content_values=_condition_values,
    identity_values=lambda value: {
        "test_method_id": value.test_method_id,
        "captured_at": value.captured_at,
    },
)
_RUN_CONTEXT_TABLES = TypedRevisionTables(
    aggregate_type=RUN_CONTEXT_AGGREGATE_TYPE,
    identity_table=run_context_table,
    revision_table=run_context_revision_table,
    canonical_content=run_context_canonical,
    content_values=_context_values,
    identity_values=lambda value: {"test_run_id": value.test_run_id},
)


class SqlAlchemyTestContextRepository(TestContextRepository):
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
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def _store[ContentT](
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        tables: TypedRevisionTables[ContentT],
    ) -> RevisionStore[ContentT]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=tables,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def campaign_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestCampaignContent]:
        return self._store(context, decision, _CAMPAIGN_TABLES)

    def instrument_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[InstrumentContent]:
        return self._store(context, decision, _INSTRUMENT_TABLES)

    def calibration_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[InstrumentCalibrationContent]:
        return self._store(context, decision, _CALIBRATION_TABLES)

    def condition_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestConditionContent]:
        return self._store(context, decision, _CONDITION_TABLES)

    def run_context_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestRunContextContent]:
        return self._store(context, decision, _RUN_CONTEXT_TABLES)

    def _exact(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table: sa.Table,
        aggregate_id: UUID,
        revision_id: UUID,
        content: Any,
    ) -> ExactSource[Any]:
        statement = sa.select(table).where(
            table.c.organization_id == context.organization_id,
            table.c.project_id == context.project_id,
            table.c.aggregate_id == aggregate_id,
            table.c.id == revision_id,
        )
        with self._session(context, decision) as session:
            row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise TestingNotFound("exact Test Context revision is not visible")
        return ExactSource(DataClassification(str(row["classification"])), content(row))

    def load_test_method_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
        test_method_revision_id: UUID,
    ) -> ExactSource[object]:
        return self._exact(
            context,
            decision,
            test_method_revision_table,
            test_method_id,
            test_method_revision_id,
            lambda row: object(),
        )

    def load_test_run_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> ExactSource[TestRunContent]:
        return self._exact(
            context,
            decision,
            test_run_revision_table,
            test_run_id,
            test_run_revision_id,
            lambda row: TestRunContent(
                specimen_id=cast(UUID, row["specimen_id"]),
                specimen_revision_id=cast(UUID, row["specimen_revision_id"]),
                test_method_id=cast(UUID, row["test_method_id"]),
                test_method_revision_id=cast(UUID, row["test_method_revision_id"]),
                run_label=str(row["run_label"]),
                performed_at=row["performed_at"],
                test_temperature_k=float(row["test_temperature_k"])
                if row["test_temperature_k"] is not None
                else None,
                crosshead_speed_mm_per_min=float(row["crosshead_speed_mm_per_min"])
                if row["crosshead_speed_mm_per_min"] is not None
                else None,
                reference_only=bool(row["reference_only"]),
            ),
        )

    def load_campaign_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        campaign_id: UUID,
        campaign_revision_id: UUID,
    ) -> ExactSource[TestCampaignContent]:
        return self._exact(
            context, decision, campaign_revision_table, campaign_id, campaign_revision_id, _campaign
        )

    def load_instrument_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        instrument_id: UUID,
        instrument_revision_id: UUID,
    ) -> ExactSource[InstrumentContent]:
        return self._exact(
            context,
            decision,
            instrument_revision_table,
            instrument_id,
            instrument_revision_id,
            _instrument,
        )

    def load_calibration_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        calibration_id: UUID,
        calibration_revision_id: UUID,
    ) -> ExactSource[InstrumentCalibrationContent]:
        return self._exact(
            context,
            decision,
            calibration_revision_table,
            calibration_id,
            calibration_revision_id,
            _calibration,
        )

    def load_condition_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        condition_id: UUID,
        condition_revision_id: UUID,
    ) -> ExactSource[TestConditionContent]:
        return self._exact(
            context,
            decision,
            condition_revision_table,
            condition_id,
            condition_revision_id,
            _condition,
        )

    @staticmethod
    def _current(
        identity: sa.Table, revision: sa.Table, *content_columns: sa.Column[Any]
    ) -> sa.Select[Any]:
        return sa.select(
            identity.c.id.label("identity_id"), *_revision_columns(revision), *content_columns
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

    def _rows(
        self, context: SecurityContext, decision: AuthorizationDecision, statement: sa.Select[Any]
    ) -> list[Any]:
        with self._session(context, decision) as session:
            return list(session.execute(statement).mappings().all())

    def list_campaigns(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[CampaignSnapshot, ...]:
        statement = (
            self._current(
                campaign_table,
                campaign_revision_table,
                *[
                    campaign_revision_table.c[name]
                    for name in (
                        "test_method_id",
                        "test_method_revision_id",
                        "campaign_code",
                        "name",
                        "objective",
                        "population_description",
                        "planned_specimen_count",
                        "standard_conformance",
                        "standard_designation",
                        "standard_edition",
                        "standard_deviation_reason",
                        "reference_only",
                    )
                ],
            )
            .where(
                campaign_table.c.organization_id == context.organization_id,
                campaign_table.c.project_id == context.project_id,
            )
            .order_by(campaign_table.c.created_at)
        )
        return tuple(
            CampaignSnapshot(
                cast(UUID, row["identity_id"]),
                ContextRevisionSnapshot(_record(row, CAMPAIGN_AGGREGATE_TYPE), _campaign(row)),
            )
            for row in self._rows(context, decision, statement)
        )

    def list_instruments(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[InstrumentSnapshot, ...]:
        statement = (
            self._current(
                instrument_table,
                instrument_revision_table,
                *[
                    instrument_revision_table.c[name]
                    for name in (
                        "instrument_code",
                        "name",
                        "serial_number",
                        "manufacturer",
                        "model",
                        "location",
                        "description",
                    )
                ],
            )
            .where(
                instrument_table.c.organization_id == context.organization_id,
                instrument_table.c.project_id == context.project_id,
            )
            .order_by(instrument_table.c.created_at)
        )
        return tuple(
            InstrumentSnapshot(
                cast(UUID, row["identity_id"]),
                ContextRevisionSnapshot(_record(row, INSTRUMENT_AGGREGATE_TYPE), _instrument(row)),
            )
            for row in self._rows(context, decision, statement)
        )

    def list_calibrations(
        self, context: SecurityContext, decision: AuthorizationDecision, instrument_id: UUID
    ) -> tuple[CalibrationSnapshot, ...]:
        statement = (
            self._current(
                calibration_table,
                calibration_revision_table,
                *[
                    calibration_revision_table.c[name]
                    for name in (
                        "instrument_id",
                        "instrument_revision_id",
                        "calibration_code",
                        "certificate_reference",
                        "provider",
                        "calibrated_at",
                        "valid_from",
                        "valid_until",
                        "result",
                        "limitation_note",
                    )
                ],
            )
            .where(
                calibration_table.c.organization_id == context.organization_id,
                calibration_table.c.project_id == context.project_id,
                calibration_table.c.instrument_id == instrument_id,
            )
            .order_by(calibration_table.c.created_at)
        )
        return tuple(
            CalibrationSnapshot(
                cast(UUID, row["identity_id"]),
                instrument_id,
                ContextRevisionSnapshot(
                    _record(row, CALIBRATION_AGGREGATE_TYPE), _calibration(row)
                ),
            )
            for row in self._rows(context, decision, statement)
        )

    def list_conditions(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ConditionSnapshot, ...]:
        names = (
            "test_method_id",
            "test_method_revision_id",
            "captured_at",
            "temperature_setpoint_k",
            "temperature_observed_k",
            "humidity_setpoint_pct",
            "humidity_observed_pct",
            "loading_rate_value",
            "loading_rate_unit",
            "orientation",
            "medium",
            "note",
        )
        statement = (
            self._current(
                condition_table,
                condition_revision_table,
                *[condition_revision_table.c[name] for name in names],
            )
            .where(
                condition_table.c.organization_id == context.organization_id,
                condition_table.c.project_id == context.project_id,
            )
            .order_by(condition_table.c.created_at)
        )
        return tuple(
            ConditionSnapshot(
                cast(UUID, row["identity_id"]),
                ContextRevisionSnapshot(_record(row, CONDITION_AGGREGATE_TYPE), _condition(row)),
            )
            for row in self._rows(context, decision, statement)
        )

    def get_run_context_for_run(
        self, context: SecurityContext, decision: AuthorizationDecision, test_run_id: UUID
    ) -> RunContextSnapshot | None:
        names = (
            "test_run_id",
            "test_run_revision_id",
            "test_campaign_id",
            "test_campaign_revision_id",
            "test_condition_id",
            "test_condition_revision_id",
            "instrument_id",
            "instrument_revision_id",
            "calibration_id",
            "calibration_revision_id",
            "note",
        )
        statement = self._current(
            run_context_table,
            run_context_revision_table,
            *[run_context_revision_table.c[name] for name in names],
        ).where(
            run_context_table.c.organization_id == context.organization_id,
            run_context_table.c.project_id == context.project_id,
            run_context_table.c.test_run_id == test_run_id,
        )
        rows = self._rows(context, decision, statement)
        if not rows:
            return None
        row = rows[0]
        return RunContextSnapshot(
            cast(UUID, row["identity_id"]),
            test_run_id,
            ContextRevisionSnapshot(_record(row, RUN_CONTEXT_AGGREGATE_TYPE), _run_context(row)),
        )
