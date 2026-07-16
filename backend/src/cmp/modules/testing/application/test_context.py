"""Application service for governed Campaign, Instrument, condition, and Run context."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.domain.reference_tensile import TestingConflict, TestRunContent
from cmp.modules.testing.domain.test_context import (
    InstrumentCalibrationContent,
    InstrumentContent,
    TestCampaignContent,
    TestConditionContent,
    TestRunContextContent,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

CAMPAIGN_AGGREGATE_TYPE = "testing.test_campaign"
INSTRUMENT_AGGREGATE_TYPE = "testing.instrument"
CALIBRATION_AGGREGATE_TYPE = "testing.instrument_calibration"
CONDITION_AGGREGATE_TYPE = "testing.test_condition_snapshot"
RUN_CONTEXT_AGGREGATE_TYPE = "testing.test_run_context"

CAMPAIGN_SCHEMA_ID = "urn:cmp:testing:test-campaign:1.0.0"
INSTRUMENT_SCHEMA_ID = "urn:cmp:testing:instrument:1.0.0"
CALIBRATION_SCHEMA_ID = "urn:cmp:testing:instrument-calibration:1.0.0"
CONDITION_SCHEMA_ID = "urn:cmp:testing:test-condition-snapshot:1.0.0"
RUN_CONTEXT_SCHEMA_ID = "urn:cmp:testing:test-run-context:1.0.0"


@dataclass(frozen=True, slots=True)
class ContextRevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class CampaignSnapshot:
    id: UUID
    current: ContextRevisionSnapshot[TestCampaignContent]


@dataclass(frozen=True, slots=True)
class InstrumentSnapshot:
    id: UUID
    current: ContextRevisionSnapshot[InstrumentContent]


@dataclass(frozen=True, slots=True)
class CalibrationSnapshot:
    id: UUID
    instrument_id: UUID
    current: ContextRevisionSnapshot[InstrumentCalibrationContent]


@dataclass(frozen=True, slots=True)
class ConditionSnapshot:
    id: UUID
    current: ContextRevisionSnapshot[TestConditionContent]


@dataclass(frozen=True, slots=True)
class RunContextSnapshot:
    id: UUID
    test_run_id: UUID
    current: ContextRevisionSnapshot[TestRunContextContent]


@dataclass(frozen=True, slots=True)
class ExactSource[ContentT]:
    classification: DataClassification
    content: ContentT


@dataclass(frozen=True, slots=True)
class CreateCampaign:
    content: TestCampaignContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateInstrument:
    classification: DataClassification
    content: InstrumentContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateCalibration:
    content: InstrumentCalibrationContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateCondition:
    content: TestConditionContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateRunContext:
    content: TestRunContextContent
    change_reason: str


class TestContextRepository(Protocol):
    def campaign_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestCampaignContent]: ...

    def instrument_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[InstrumentContent]: ...

    def calibration_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[InstrumentCalibrationContent]: ...

    def condition_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestConditionContent]: ...

    def run_context_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestRunContextContent]: ...

    def load_test_method_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
        test_method_revision_id: UUID,
    ) -> ExactSource[object]: ...

    def load_test_run_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> ExactSource[TestRunContent]: ...

    def load_campaign_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        campaign_id: UUID,
        campaign_revision_id: UUID,
    ) -> ExactSource[TestCampaignContent]: ...

    def load_instrument_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        instrument_id: UUID,
        instrument_revision_id: UUID,
    ) -> ExactSource[InstrumentContent]: ...

    def load_calibration_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        calibration_id: UUID,
        calibration_revision_id: UUID,
    ) -> ExactSource[InstrumentCalibrationContent]: ...

    def load_condition_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        condition_id: UUID,
        condition_revision_id: UUID,
    ) -> ExactSource[TestConditionContent]: ...

    def list_campaigns(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[CampaignSnapshot, ...]: ...

    def list_instruments(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[InstrumentSnapshot, ...]: ...

    def list_calibrations(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        instrument_id: UUID,
    ) -> tuple[CalibrationSnapshot, ...]: ...

    def list_conditions(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ConditionSnapshot, ...]: ...

    def get_run_context_for_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> RunContextSnapshot | None: ...


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise TestingConflict("authorization decision does not match Test Context request")


class TestContextService:
    def __init__(
        self,
        *,
        repository: TestContextRepository,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("Test Context id_factory returned a zero UUID")
        return value

    @staticmethod
    def _scope(context: SecurityContext, classification: DataClassification) -> TenantScope:
        return TenantScope(context.organization_id, context.project_id, classification.value)

    def _create[ContentT](
        self,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        schema_id: str,
        classification: DataClassification,
        content: ContentT,
        change_reason: str,
        store: RevisionStore[ContentT],
        context: SecurityContext,
    ) -> RevisionRecord:
        return RevisionService(aggregate_type=aggregate_type, store=store).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=self._scope(context, classification),
                schema_id=schema_id,
                schema_version="1.0.0",
                content=content,
                created_by=context.principal.id,
                change_reason=change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )

    def create_campaign(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateCampaign,
    ) -> CampaignSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        method = self._repository.load_test_method_revision(
            context,
            decision,
            command.content.test_method_id,
            command.content.test_method_revision_id,
        )
        aggregate_id = self._id()
        record = self._create(
            aggregate_type=CAMPAIGN_AGGREGATE_TYPE,
            aggregate_id=aggregate_id,
            schema_id=CAMPAIGN_SCHEMA_ID,
            classification=method.classification,
            content=command.content,
            change_reason=command.change_reason,
            store=self._repository.campaign_store(context, decision),
            context=context,
        )
        return CampaignSnapshot(aggregate_id, ContextRevisionSnapshot(record, command.content))

    def create_instrument(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateInstrument,
    ) -> InstrumentSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        aggregate_id = self._id()
        record = self._create(
            aggregate_type=INSTRUMENT_AGGREGATE_TYPE,
            aggregate_id=aggregate_id,
            schema_id=INSTRUMENT_SCHEMA_ID,
            classification=command.classification,
            content=command.content,
            change_reason=command.change_reason,
            store=self._repository.instrument_store(context, decision),
            context=context,
        )
        return InstrumentSnapshot(aggregate_id, ContextRevisionSnapshot(record, command.content))

    def create_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateCalibration,
    ) -> CalibrationSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        instrument = self._repository.load_instrument_revision(
            context,
            decision,
            command.content.instrument_id,
            command.content.instrument_revision_id,
        )
        for current in self._repository.list_calibrations(
            context, decision, command.content.instrument_id
        ):
            if command.content.overlaps(current.current.content):
                raise TestingConflict("usable Instrument calibration intervals cannot overlap")
        aggregate_id = self._id()
        record = self._create(
            aggregate_type=CALIBRATION_AGGREGATE_TYPE,
            aggregate_id=aggregate_id,
            schema_id=CALIBRATION_SCHEMA_ID,
            classification=instrument.classification,
            content=command.content,
            change_reason=command.change_reason,
            store=self._repository.calibration_store(context, decision),
            context=context,
        )
        return CalibrationSnapshot(
            aggregate_id,
            command.content.instrument_id,
            ContextRevisionSnapshot(record, command.content),
        )

    def create_condition(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateCondition,
    ) -> ConditionSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        method = self._repository.load_test_method_revision(
            context,
            decision,
            command.content.test_method_id,
            command.content.test_method_revision_id,
        )
        aggregate_id = self._id()
        record = self._create(
            aggregate_type=CONDITION_AGGREGATE_TYPE,
            aggregate_id=aggregate_id,
            schema_id=CONDITION_SCHEMA_ID,
            classification=method.classification,
            content=command.content,
            change_reason=command.change_reason,
            store=self._repository.condition_store(context, decision),
            context=context,
        )
        return ConditionSnapshot(aggregate_id, ContextRevisionSnapshot(record, command.content))

    def create_run_context(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateRunContext,
    ) -> RunContextSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        value = command.content
        if self._repository.get_run_context_for_run(context, decision, value.test_run_id):
            raise TestingConflict("Test Run already has a stable Context identity")
        run = self._repository.load_test_run_revision(
            context, decision, value.test_run_id, value.test_run_revision_id
        )
        campaign = self._repository.load_campaign_revision(
            context, decision, value.test_campaign_id, value.test_campaign_revision_id
        )
        condition = self._repository.load_condition_revision(
            context, decision, value.test_condition_id, value.test_condition_revision_id
        )
        instrument = self._repository.load_instrument_revision(
            context, decision, value.instrument_id, value.instrument_revision_id
        )
        calibration = self._repository.load_calibration_revision(
            context, decision, value.calibration_id, value.calibration_revision_id
        )
        classifications = {
            item.classification for item in (run, campaign, condition, instrument, calibration)
        }
        if len(classifications) != 1:
            raise TestingConflict("Test Run Context references cannot cross classification")
        if (
            campaign.content.test_method_id != run.content.test_method_id
            or campaign.content.test_method_revision_id != run.content.test_method_revision_id
            or condition.content.test_method_id != run.content.test_method_id
            or condition.content.test_method_revision_id != run.content.test_method_revision_id
        ):
            raise TestingConflict("Campaign and Condition must pin the Test Run Method revision")
        if (
            calibration.content.instrument_id != value.instrument_id
            or calibration.content.instrument_revision_id != value.instrument_revision_id
        ):
            raise TestingConflict("Calibration must pin the selected Instrument revision")
        if not calibration.content.covers(run.content.performed_at):
            raise TestingConflict("Calibration is not usable at the Test Run execution time")
        classification = next(iter(classifications))
        aggregate_id = self._id()
        record = self._create(
            aggregate_type=RUN_CONTEXT_AGGREGATE_TYPE,
            aggregate_id=aggregate_id,
            schema_id=RUN_CONTEXT_SCHEMA_ID,
            classification=classification,
            content=value,
            change_reason=command.change_reason,
            store=self._repository.run_context_store(context, decision),
            context=context,
        )
        return RunContextSnapshot(
            aggregate_id, value.test_run_id, ContextRevisionSnapshot(record, value)
        )

    def list_campaigns(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[CampaignSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_campaigns(context, decision)

    def list_instruments(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[InstrumentSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_instruments(context, decision)

    def list_calibrations(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        instrument_id: UUID,
    ) -> tuple[CalibrationSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_calibrations(context, decision, instrument_id)

    def list_conditions(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ConditionSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_conditions(context, decision)

    def get_run_context_for_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> RunContextSnapshot | None:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.get_run_context_for_run(context, decision, test_run_id)
