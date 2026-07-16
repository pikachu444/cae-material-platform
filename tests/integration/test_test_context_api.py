from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.testing.adapters.api.test_context import install_test_context_api
from cmp.modules.testing.adapters.api.testing import install_testing_api
from cmp.modules.testing.application.test_context import (
    CalibrationSnapshot,
    CampaignSnapshot,
    ConditionSnapshot,
    ContextRevisionSnapshot,
    CreateCalibration,
    CreateCampaign,
    CreateCondition,
    CreateInstrument,
    CreateRunContext,
    InstrumentSnapshot,
    RunContextSnapshot,
)
from cmp.modules.testing.application.test_context import (
    TestContextService as _TestContextService,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 16, 9, 0, tzinfo=UTC)
ORG = UUID("49000000-0000-4000-8000-000000000001")
PROJECT = UUID("49000000-0000-4000-8000-000000000002")
ACTOR = UUID("49000000-0000-4000-8000-000000000003")
METHOD = UUID("49000000-0000-4000-8000-000000000004")
METHOD_REVISION = UUID("49000000-0000-4000-8000-000000000005")
RUN = UUID("49000000-0000-4000-8000-000000000006")
RUN_REVISION = UUID("49000000-0000-4000-8000-000000000007")
TRACE = "00-49000000000000000000000000000000-4900000000000000-01"

CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Test engineer", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://test.invalid",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=uuid4(),
    trace_id=TRACE,
    authenticated_at=NOW,
)


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.TEST_ENGINEER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


READ = _decision(Permission.TESTING_READ)
WRITE = _decision(Permission.TESTING_WRITE)


def _record(aggregate_id: UUID, revision_id: UUID, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=f"urn:cmp:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash="4" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="API test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _Service:
    def __init__(self) -> None:
        self.commands: list[object] = []
        self.campaign: CampaignSnapshot | None = None
        self.instrument: InstrumentSnapshot | None = None
        self.calibration: CalibrationSnapshot | None = None
        self.condition: ConditionSnapshot | None = None
        self.context: RunContextSnapshot | None = None

    def create_campaign(
        self, context: object, decision: object, command: CreateCampaign
    ) -> CampaignSnapshot:
        del context, decision
        self.commands.append(command)
        aggregate_id, revision_id = uuid4(), uuid4()
        self.campaign = CampaignSnapshot(
            aggregate_id,
            ContextRevisionSnapshot(
                _record(aggregate_id, revision_id, "testing.test_campaign"), command.content
            ),
        )
        return self.campaign

    def list_campaigns(self, context: object, decision: object) -> tuple[CampaignSnapshot, ...]:
        del context, decision
        return () if self.campaign is None else (self.campaign,)

    def create_instrument(
        self, context: object, decision: object, command: CreateInstrument
    ) -> InstrumentSnapshot:
        del context, decision
        self.commands.append(command)
        aggregate_id, revision_id = uuid4(), uuid4()
        self.instrument = InstrumentSnapshot(
            aggregate_id,
            ContextRevisionSnapshot(
                _record(aggregate_id, revision_id, "testing.instrument"), command.content
            ),
        )
        return self.instrument

    def list_instruments(self, context: object, decision: object) -> tuple[InstrumentSnapshot, ...]:
        del context, decision
        return () if self.instrument is None else (self.instrument,)

    def create_calibration(
        self, context: object, decision: object, command: CreateCalibration
    ) -> CalibrationSnapshot:
        del context, decision
        self.commands.append(command)
        aggregate_id, revision_id = uuid4(), uuid4()
        self.calibration = CalibrationSnapshot(
            aggregate_id,
            command.content.instrument_id,
            ContextRevisionSnapshot(
                _record(aggregate_id, revision_id, "testing.instrument_calibration"),
                command.content,
            ),
        )
        return self.calibration

    def list_calibrations(
        self, context: object, decision: object, instrument_id: UUID
    ) -> tuple[CalibrationSnapshot, ...]:
        del context, decision
        return (
            ()
            if self.calibration is None or self.calibration.instrument_id != instrument_id
            else (self.calibration,)
        )

    def create_condition(
        self, context: object, decision: object, command: CreateCondition
    ) -> ConditionSnapshot:
        del context, decision
        self.commands.append(command)
        aggregate_id, revision_id = uuid4(), uuid4()
        self.condition = ConditionSnapshot(
            aggregate_id,
            ContextRevisionSnapshot(
                _record(aggregate_id, revision_id, "testing.test_condition_snapshot"),
                command.content,
            ),
        )
        return self.condition

    def list_conditions(self, context: object, decision: object) -> tuple[ConditionSnapshot, ...]:
        del context, decision
        return () if self.condition is None else (self.condition,)

    def create_run_context(
        self, context: object, decision: object, command: CreateRunContext
    ) -> RunContextSnapshot:
        del context, decision
        self.commands.append(command)
        aggregate_id, revision_id = uuid4(), uuid4()
        self.context = RunContextSnapshot(
            aggregate_id,
            command.content.test_run_id,
            ContextRevisionSnapshot(
                _record(aggregate_id, revision_id, "testing.test_run_context"), command.content
            ),
        )
        return self.context

    def get_run_context_for_run(
        self, context: object, decision: object, test_run_id: UUID
    ) -> RunContextSnapshot | None:
        del context, decision
        return self.context if self.context and self.context.test_run_id == test_run_id else None


def _application(service: _Service) -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = READ

    def write(request: Request) -> None:
        request.state.authorization_decision = WRITE

    install_testing_api(
        app,
        service=None,
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    install_test_context_api(
        app,
        service=cast(_TestContextService, service),
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    return app


def _request(
    app: FastAPI, method: str, path: str, json: dict[str, object] | None = None
) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_context_api_preserves_exact_revision_pins_end_to_end() -> None:
    service = _Service()
    app = _application(service)
    campaign = _request(
        app,
        "POST",
        "/api/v1/test-campaigns",
        {
            "content": {
                "test_method_id": str(METHOD),
                "test_method_revision_id": str(METHOD_REVISION),
                "campaign_code": "CMP-001",
                "name": "Pilot campaign",
                "objective": "Characterize the current lot",
                "population_description": "Rolling direction coupons",
                "planned_specimen_count": 3,
                "standard_conformance": "conformant",
                "standard_designation": "ISO 6892-1",
                "standard_edition": "2019",
                "reference_only": True,
            },
            "change_reason": "register campaign",
        },
    )
    assert campaign.status_code == 201, campaign.text
    instrument = _request(
        app,
        "POST",
        "/api/v1/instruments",
        {
            "classification": "internal",
            "content": {
                "instrument_code": "UTM-01",
                "name": "Universal tester",
                "serial_number": "SN-01",
                "manufacturer": "Reference",
            },
            "change_reason": "register instrument",
        },
    )
    assert instrument.status_code == 201, instrument.text
    instrument_id = instrument.json()["resource_id"]
    instrument_revision_id = instrument.json()["current_revision"]["id"]
    calibration = _request(
        app,
        "POST",
        f"/api/v1/instruments/{instrument_id}/calibrations",
        {
            "content": {
                "instrument_revision_id": instrument_revision_id,
                "calibration_code": "CAL-01",
                "certificate_reference": "CERT-01",
                "provider": "Reference laboratory",
                "calibrated_at": (NOW - timedelta(days=10)).isoformat(),
                "valid_from": (NOW - timedelta(days=10)).isoformat(),
                "valid_until": (NOW + timedelta(days=355)).isoformat(),
                "result": "passed",
            },
            "change_reason": "record calibration",
        },
    )
    assert calibration.status_code == 201, calibration.text
    condition = _request(
        app,
        "POST",
        "/api/v1/test-conditions",
        {
            "content": {
                "test_method_id": str(METHOD),
                "test_method_revision_id": str(METHOD_REVISION),
                "captured_at": NOW.isoformat(),
                "temperature_observed_k": "296.15",
                "loading_rate_value": "2",
                "loading_rate_unit": "mm/min",
                "orientation": "rolling",
                "medium": "air",
            },
            "change_reason": "capture conditions",
        },
    )
    assert condition.status_code == 201, condition.text
    linked = _request(
        app,
        "POST",
        f"/api/v1/test-runs/{RUN}/context",
        {
            "content": {
                "test_run_revision_id": str(RUN_REVISION),
                "test_campaign_id": campaign.json()["resource_id"],
                "test_campaign_revision_id": campaign.json()["current_revision"]["id"],
                "test_condition_id": condition.json()["resource_id"],
                "test_condition_revision_id": condition.json()["current_revision"]["id"],
                "instrument_id": instrument_id,
                "instrument_revision_id": instrument_revision_id,
                "calibration_id": calibration.json()["resource_id"],
                "calibration_revision_id": calibration.json()["current_revision"]["id"],
            },
            "change_reason": "bind exact execution context",
        },
    )
    assert linked.status_code == 201, linked.text
    content = linked.json()["current_revision"]["content"]
    assert content["test_run_revision_id"] == str(RUN_REVISION)
    assert content["calibration_revision_id"] == calibration.json()["current_revision"]["id"]
    assert (
        _request(app, "GET", f"/api/v1/test-runs/{RUN}/context").json()["resource_id"]
        == linked.json()["resource_id"]
    )
