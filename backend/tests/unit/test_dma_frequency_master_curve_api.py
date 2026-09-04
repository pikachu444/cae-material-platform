from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from cmp.modules.datasets.domain.governed_tabular import GovernedImportNotFound
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
from cmp.modules.processing.domain.dma_multi_frequency_tts import (
    DmaMultiFrequencyStartingSuggestion,
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
        self.multi_recommendation_calls = 0
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

    async def recommend_multi(self, context: object, decision: object, command: object) -> object:
        self.multi_recommendation_calls += 1
        return _multi_suggestion()

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


class _NotFoundService:
    async def recommend(self, context: object, decision: object, command: object) -> object:
        raise GovernedImportNotFound("secret governed import")

    async def recommend_multi(self, context: object, decision: object, command: object) -> object:
        raise GovernedImportNotFound("secret governed import")

    async def create(self, context: object, decision: object, command: object) -> object:
        raise GovernedImportNotFound("secret governed import")


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


def _multi_suggestion() -> DmaMultiFrequencyStartingSuggestion:
    return DmaMultiFrequencyStartingSuggestion(
        input_mode="multi_frequency_isotherms",
        source_evidence={
            "test_data_document_id": "da100000-0000-4000-8000-000000000021",
            "test_data_revision_id": "da100000-0000-4000-8000-000000000022",
            "test_data_content_sha256": "a" * 64,
            "import_profile_id": "da100000-0000-4000-8000-000000000023",
            "import_profile_revision_id": "da100000-0000-4000-8000-000000000024",
            "import_profile_content_sha256": "b" * 64,
            "source_normalized_artifact_id": "da100000-0000-4000-8000-000000000025",
            "source_normalized_artifact_sha256": "c" * 64,
        },
        sweeps=(
            {
                "source_sweep_ordinal": 11,
                "representative_temperature_k": 300.0,
                "point_count": 3,
                "source_frequency_min_hz": 1.0,
                "source_frequency_max_hz": 100.0,
            },
            {
                "source_sweep_ordinal": 27,
                "representative_temperature_k": 310.0,
                "point_count": 3,
                "source_frequency_min_hz": 1.0,
                "source_frequency_max_hz": 100.0,
            },
            {
                "source_sweep_ordinal": 42,
                "representative_temperature_k": 320.0,
                "point_count": 3,
                "source_frequency_min_hz": 1.0,
                "source_frequency_max_hz": 100.0,
            },
        ),
        reference_sweep_ordinal=11,
        reference_temperature_k=300.0,
        sweep_dispositions=(
            {
                "source_sweep_ordinal": 11,
                "representative_temperature_k": 300.0,
                "partition": "CALIBRATION",
                "exclusion_reason": None,
            },
            {
                "source_sweep_ordinal": 27,
                "representative_temperature_k": 310.0,
                "partition": "CALIBRATION",
                "exclusion_reason": None,
            },
            {
                "source_sweep_ordinal": 42,
                "representative_temperature_k": 320.0,
                "partition": "HOLDOUT",
                "exclusion_reason": None,
            },
        ),
        shift_law={
            "kind": "wlf_fit",
            "reference_temperature_k": 300.0,
            "initial_parameters": [17.44, 51.6],
            "lower_bounds": [1e-8, 1.0],
            "upper_bounds": [1000.0, 5000.0],
        },
        scoring={
            "minimum_overlap_decades": 0.25,
            "scoring_point_count": 101,
            "storage_weight": 0.5,
            "loss_weight": 0.5,
        },
        adjacent_optimizer={
            "relative_shift_lower_bound_log10": -12.0,
            "relative_shift_upper_bound_log10": 12.0,
            "xatol": 1e-10,
            "maxiter": 1000,
            "seed": None,
        },
        law_optimizer={
            "initial_parameters": [17.44, 51.6],
            "lower_bounds": [1e-8, 1.0],
            "upper_bounds": [1000.0, 5000.0],
            "ftol": 1e-12,
            "xtol": 1e-12,
            "gtol": 1e-12,
            "max_nfev": 5000,
            "seed": None,
        },
        profile_id="cmp.dma_tts.multi_frequency_wlf_starting_profile",
        profile_version="1.0.0",
        material_specific=False,
        production_readiness="non_production",
        requires_confirmation=True,
        recommendation_sha256="d" * 64,
    )


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


def test_multi_recommendation_endpoint_returns_exact_defaults_evidence_and_holdout() -> None:
    service = _Service()
    response = _client(service).post(
        "/api/v1/processing/dma-frequency-master-curves/recommendations/multi-frequency",
        json={**_pins(), "reference_sweep_ordinal": 11},
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["input_mode"] == "multi_frequency_isotherms"
    assert body["reference_sweep_ordinal"] == 11
    assert body["reference_temperature_k"] == 300.0
    assert [item["partition"] for item in body["sweep_dispositions"]] == [
        "CALIBRATION",
        "CALIBRATION",
        "HOLDOUT",
    ]
    assert body["law_optimizer"]["seed"] is None
    assert body["adjacent_optimizer"]["xatol"] == 1e-10
    import_profile_pin = cast(dict[str, object], _pins()["import_profile"])
    assert body["source_evidence"]["import_profile_id"] == import_profile_pin["profile_id"]
    assert body["recommendation_sha256"] == "d" * 64
    assert service.multi_recommendation_calls == 1
    assert service.create_calls == 0


@pytest.mark.parametrize(
    ("path", "body"),
    (
        (
            "/api/v1/processing/dma-frequency-master-curves/recommendations",
            _pins(),
        ),
        (
            "/api/v1/processing/dma-frequency-master-curves/recommendations/multi-frequency",
            {**_pins(), "reference_sweep_ordinal": 11},
        ),
        (
            "/api/v1/processing/dma-frequency-master-curves",
            {
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
                "change_reason": "Create the confirmed DMA TTS output.",
            },
        ),
    ),
)
def test_governed_import_not_found_is_a_non_enumerating_404(
    path: str, body: dict[str, object]
) -> None:
    response = _client(cast(_Service, _NotFoundService())).post(path, json=body)

    assert response.status_code == 404, response.json()
    assert response.json()["error"]["code"] == "CMP-PROCESSING-4040"
    assert "secret governed import" not in response.text
    assert "da100000-0000-4000-8000-000000000021" not in response.text


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
