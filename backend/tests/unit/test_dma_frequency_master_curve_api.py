from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.processing.adapters.api.dma_frequency_master_curve import (
    install_dma_frequency_master_curve_api,
)
from cmp.modules.processing.application.common_outputs import ProcessingOutputSnapshot
from cmp.modules.processing.application.dma_frequency_master_curve import (
    CreatedDmaFrequencyMasterCurve,
    DmaFrequencyMasterCurveService,
)
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
    DmaProcessingError,
    DmaWlfStartingSuggestion,
)
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

_ORG = UUID("da100000-0000-4000-8000-000000000001")
_PROJECT = UUID("da100000-0000-4000-8000-000000000002")
_ACTOR = UUID("da100000-0000-4000-8000-000000000003")
_CONTEXT = SecurityContext(
    principal=Principal(_ACTOR, PrincipalType.USER, "Modeler", True),
    organization_id=_ORG,
    project_id=_PROJECT,
    issuer="urn:cmp:test",
    subject=str(_ACTOR),
    token_id="dma-tts-api",
    groups=(),
    scopes=("openid",),
    request_id=UUID("da100000-0000-4000-8000-000000000004"),
    trace_id="00-da100000000000000000000000000000-da10000000000000-01",
    authenticated_at=datetime(2026, 8, 30, tzinfo=UTC),
)
_DECISION = AuthorizationDecision(
    principal_id=_ACTOR,
    organization_id=_ORG,
    project_id=_PROJECT,
    permission=Permission.PROCESSING_EXECUTE,
    roles=(Role.MATERIAL_MODELER,),
    database_permissions=database_permissions_for(Permission.PROCESSING_EXECUTE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=_CONTEXT.request_id,
    trace_id=_CONTEXT.trace_id,
    decided_at=_CONTEXT.authenticated_at,
)


class _Service:
    def __init__(self) -> None:
        self.recommendation_calls = 0
        self.create_calls = 0

    async def recommend(self, context: object, decision: object, command: object) -> object:
        self.recommendation_calls += 1
        return DmaWlfStartingSuggestion(
            source_evidence={"test_data_sha256": "a" * 64},
            reference_temperature_k=313.15,
            source_ordinal=2,
            c1=17.44,
            c2_k=51.6,
            value_origin="generic_wlf_at_tg_starting_suggestion",
            material_specific=False,
            requires_confirmation=True,
            rule_id="polymer.dma_wlf_starting_suggestion",
            rule_version="1.0.0",
            recommendation_sha256="c" * 64,
        )

    async def create(self, context: object, decision: object, command: object) -> object:
        self.create_calls += 1
        content = SimpleNamespace(
            output_artifact_id=UUID("da100000-0000-4000-8000-000000000011"),
            output_sha256="d" * 64,
            result_artifact_id=UUID("da100000-0000-4000-8000-000000000012"),
            result_sha256="e" * 64,
            result_schema_ref=DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
            result_media_type="application/vnd.apache.parquet",
        )
        snapshot = SimpleNamespace(
            id=UUID("da100000-0000-4000-8000-000000000010"),
            current=SimpleNamespace(
                revision_id=UUID("da100000-0000-4000-8000-000000000013"),
                content_hash="f" * 64,
            ),
            content=content,
        )
        return CreatedDmaFrequencyMasterCurve(cast(ProcessingOutputSnapshot, snapshot))


class _ErrorService:
    def __init__(self, error: DmaProcessingError) -> None:
        self.error = error

    async def create(self, context: object, decision: object, command: object) -> object:
        raise self.error


def _client(service: _Service) -> TestClient:
    application = FastAPI()

    def security(request: Request) -> SecurityContext:
        request.state.security_context = _CONTEXT
        return _CONTEXT

    def execute(request: Request) -> AuthorizationDecision:
        request.state.authorization_decision = _DECISION
        return _DECISION

    install_dma_frequency_master_curve_api(
        application,
        service=cast(DmaFrequencyMasterCurveService, service),
        security_dependency=security,
        execute_dependency=execute,
    )
    return TestClient(application)


def _pins() -> dict[str, object]:
    return {
        "test_data": {
            "document_id": "da100000-0000-4000-8000-000000000021",
            "revision_id": "da100000-0000-4000-8000-000000000022",
            "content_sha256": "a" * 64,
        },
        "import_profile": {
            "profile_id": "da100000-0000-4000-8000-000000000023",
            "revision_id": "da100000-0000-4000-8000-000000000024",
            "content_sha256": "b" * 64,
        },
    }


def test_recommendation_endpoint_is_read_only_and_returns_confirmation_evidence() -> None:
    service = _Service()
    response = _client(service).post(
        "/api/v1/processing/dma-frequency-master-curves/recommendations",
        json=_pins(),
    )

    assert response.status_code == 200, response.json()
    assert response.json()["requires_confirmation"] is True
    assert response.json()["value_origin"] == "generic_wlf_at_tg_starting_suggestion"
    assert service.recommendation_calls == 1
    assert service.create_calls == 0


def test_create_endpoint_preserves_explicit_policy_and_returns_exact_artifact_pins() -> None:
    service = _Service()
    body = {
        **_pins(),
        "classification": "internal",
        "label": "DMA frequency master curve",
        "input_mode": "fixed_frequency_temperature_sweep",
        "row_dispositions": [
            {"source_ordinal": 0, "partition": "CALIBRATION"},
            {"source_ordinal": 1, "partition": "HOLDOUT"},
        ],
        "shift_law": {
            "kind": "wlf",
            "reference_temperature_k": 313.15,
            "c1": 17.44,
            "c2_k": 51.6,
        },
        "confirmation": {"confirmed": True, "reason": "Engineer accepted the settings."},
        "recommendation_sha256": "c" * 64,
        "change_reason": "Create the confirmed DMA TTS output.",
    }
    response = _client(service).post(
        "/api/v1/processing/dma-frequency-master-curves",
        json=body,
    )

    assert response.status_code == 201, response.json()
    output = response.json()["master_curve_output"]
    assert output["content_sha256"] == "f" * 64
    assert output["result_schema_ref"] == DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID
    assert output["result_media_type"] == "application/vnd.apache.parquet"
    assert service.create_calls == 1


@pytest.mark.parametrize(
    ("code", "status_code"),
    (("CMP-PROCESSING-4030", 403), ("CMP-PROCESSING-4317", 409)),
)
def test_create_endpoint_preserves_authorization_and_integrity_status_boundary(
    code: str,
    status_code: int,
) -> None:
    service = _ErrorService(
        DmaProcessingError(code, "The persistence boundary rejected the request.", "Retry safely.")
    )
    body = {
        **_pins(),
        "classification": "internal",
        "label": "DMA frequency master curve",
        "input_mode": "fixed_frequency_temperature_sweep",
        "row_dispositions": [
            {"source_ordinal": 0, "partition": "CALIBRATION"},
            {"source_ordinal": 1, "partition": "HOLDOUT"},
        ],
        "shift_law": {
            "kind": "wlf",
            "reference_temperature_k": 313.15,
            "c1": 17.44,
            "c2_k": 51.6,
        },
        "confirmation": {"confirmed": True, "reason": "Engineer accepted the settings."},
        "recommendation_sha256": "c" * 64,
        "change_reason": "Create the confirmed DMA TTS output.",
    }

    response = _client(cast(_Service, service)).post(
        "/api/v1/processing/dma-frequency-master-curves",
        json=body,
    )

    assert response.status_code == status_code, response.json()
    assert response.json()["error"]["code"] == code
