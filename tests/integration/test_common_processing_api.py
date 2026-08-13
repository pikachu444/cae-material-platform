from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import httpx
import pytest
from cmp.modules.datasets.application.canonical_test_data import (
    ExactRevisionRef,
    GovernedTestDataSource,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.processing.adapters.api.common_pipeline import install_common_processing_api
from cmp.modules.processing.application.common_outputs import (
    CommitProcessingOutput,
    validate_workup_overrides,
)
from fastapi import FastAPI, Request


async def _allow() -> object:
    return object()


_NOW = datetime(2026, 7, 24, tzinfo=UTC)
_ORG = UUID("d5400000-0000-4000-8000-000000000001")
_PROJECT = UUID("d5400000-0000-4000-8000-000000000002")
_ACTOR = UUID("d5400000-0000-4000-8000-000000000003")
_CONTEXT = SecurityContext(
    principal=Principal(_ACTOR, PrincipalType.USER, "Modeler", True),
    organization_id=_ORG,
    project_id=_PROJECT,
    issuer="urn:cmp:test",
    subject=str(_ACTOR),
    token_id="output-workup-test",
    groups=(),
    scopes=("openid",),
    request_id=UUID("d5400000-0000-4000-8000-000000000004"),
    trace_id="00-0000000000000000000000000000d540-000000000000d540-01",
    authenticated_at=_NOW,
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
    decided_at=_NOW,
)


def _output_scope(request: Request) -> None:
    request.state.security_context = _CONTEXT
    request.state.authorization_decision = _DECISION


class _ValidatingOutputService:
    async def commit(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CommitProcessingOutput,
    ) -> SimpleNamespace:
        assert context is _CONTEXT and decision is _DECISION
        validate_workup_overrides(command.steps, command.workup_overrides)
        override = command.workup_overrides
        revision = SimpleNamespace(
            revision_id=UUID("d5400000-0000-4000-8000-000000000011"),
            aggregate_id=UUID("d5400000-0000-4000-8000-000000000010"),
            revision_no=1,
            based_on_revision_id=None,
            schema_id="urn:cmp:processing:common-output:1.1.0",
            schema_version="1.1.0",
            content_hash="a" * 64,
            created_at=_NOW,
            created_by=_ACTOR,
            change_reason=command.change_reason,
            request_id=_CONTEXT.request_id,
            trace_id=_CONTEXT.trace_id,
            scope=SimpleNamespace(
                organization_id=_ORG,
                project_id=_PROJECT,
                classification=DataClassification.INTERNAL.value,
            ),
        )
        content = SimpleNamespace(
            label=command.label,
            source_document=command.source_document,
            source_document_sha256="b" * 64,
            source_canonical_artifact_sha256="c" * 64,
            mapping_profile=command.mapping_profile,
            mapping_profile_sha256="d" * 64,
            steps=command.steps,
            independent_quantity="strain.engineering",
            stage_count=len(command.steps) + 1,
            final_point_count=3,
            output_artifact_id=UUID("d5400000-0000-4000-8000-000000000012"),
            output_sha256="e" * 64,
            workup_overrides=override,
            export_provenance=GovernedTestDataSource(
                material=ExactRevisionRef(
                    UUID("d5400000-0000-4000-8000-000000000030"),
                    UUID("d5400000-0000-4000-8000-000000000031"),
                ),
                material_state=ExactRevisionRef(
                    UUID("d5400000-0000-4000-8000-000000000032"),
                    UUID("d5400000-0000-4000-8000-000000000033"),
                ),
                test_run=ExactRevisionRef(
                    UUID("d5400000-0000-4000-8000-000000000034"),
                    UUID("d5400000-0000-4000-8000-000000000035"),
                ),
            ),
        )
        return SimpleNamespace(id=revision.aggregate_id, current=revision, content=content)


def _app() -> FastAPI:
    app = FastAPI()
    install_common_processing_api(
        app,
        security_dependency=_allow,
        read_dependency=_allow,
        execute_dependency=_allow,
    )
    return app


def _output_app() -> FastAPI:
    app = FastAPI()
    install_common_processing_api(
        app,
        output_service=_ValidatingOutputService(),  # type: ignore[arg-type]
        security_dependency=_output_scope,
        read_dependency=_output_scope,
        execute_dependency=_output_scope,
    )
    return app


def _document() -> dict[str, object]:
    path = Path("contracts/examples/positive/canonical-test-data.json")
    value: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return value


async def _request(method: str, url: str, *, json_body: object | None = None) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        return await client.request(method, url, json=json_body)


async def _output_request(json_body: object) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_output_app()), base_url="http://test"
    ) as client:
        return await client.post("/api/v1/processing-outputs", json=json_body)


def test_method_registry_and_preview_share_the_versioned_contract() -> None:
    import asyncio

    methods = asyncio.run(_request("GET", "/api/v1/processing-methods"))
    assert methods.status_code == 200
    assert len(methods.json()["items"]) == 16
    assert methods.json()["items"][0]["method_id"] == "rows.sort_unique"
    toe = next(
        item
        for item in methods.json()["items"]
        if item["method_id"] == "tensile.toe_zero_intercept"
    )
    assert toe["version"] == "1.0.0"
    assert toe["option_schema"]["properties"]["equipment_compliance"] == {"const": "not_provided"}

    preview = asyncio.run(
        _request(
            "POST",
            "/api/v1/processing:preview",
            json_body={
                "document": _document(),
                "mapping_profile": {
                    "profile_key": "tensile-normalized",
                    "label": "Normalized tensile channels",
                    "independent_quantity": "strain.engineering",
                    "missing_data_policy": "drop_any",
                    "bindings": [
                        {
                            "channel_key": "engineering_strain",
                            "target_quantity": "strain.engineering",
                            "accepted_normalized_units": ["1"],
                        },
                        {
                            "channel_key": "engineering_stress",
                            "target_quantity": "stress.engineering",
                            "accepted_normalized_units": ["Pa"],
                        },
                    ],
                },
                "steps": [
                    {
                        "method_id": "rows.sort_unique",
                        "method_version": "1.0.0",
                        "options": {"duplicate_policy": "reject"},
                    },
                    {
                        "method_id": "curve.resample_linear",
                        "method_version": "1.0.0",
                        "options": {
                            "start": 0.0,
                            "end": 0.001,
                            "count": 5,
                            "extrapolation": "reject",
                        },
                    },
                ],
            },
        )
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["execution_mode"] == "preview"
    assert body["promotable"] is False
    assert [stage["method_id"] for stage in body["stages"]] == [
        "mapping",
        "rows.sort_unique",
        "curve.resample_linear",
    ]
    assert body["stages"][-1]["point_count"] == 5


def test_toe_preview_returns_corrected_curve_and_quality_evidence() -> None:
    import asyncio

    document = cast(dict[str, Any], _document())
    source_strain = [0.0003, 0.0007, 0.0011, 0.0015, 0.0019, 0.0023]
    source_stress = [0, 80e6, 160e6, 240e6, 320e6, 400e6]
    document["channels"][0]["original_values"] = [str(value * 100) for value in source_strain]
    document["channels"][0]["normalized_values"] = [str(value) for value in source_strain]
    document["channels"][0]["missing_reasons"] = [None] * len(source_strain)
    document["channels"][1]["original_values"] = [str(value / 1e6) for value in source_stress]
    document["channels"][1]["normalized_values"] = [str(value) for value in source_stress]
    document["channels"][1]["missing_reasons"] = [None] * len(source_stress)

    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/processing:preview",
            json_body={
                "document": document,
                "mapping_profile": {
                    "profile_key": "tensile-toe",
                    "label": "Tensile toe quantities",
                    "independent_quantity": "strain.engineering",
                    "missing_data_policy": "reject",
                    "bindings": [
                        {
                            "channel_key": "engineering_strain",
                            "target_quantity": "strain.engineering",
                            "accepted_normalized_units": ["1"],
                        },
                        {
                            "channel_key": "engineering_stress",
                            "target_quantity": "stress.engineering",
                            "accepted_normalized_units": ["Pa"],
                        },
                    ],
                },
                "steps": [
                    {
                        "method_id": "tensile.toe_zero_intercept",
                        "method_version": "1.0.0",
                        "options": {
                            "strain_quantity": "strain.engineering",
                            "stress_quantity": "stress.engineering",
                            "minimum_strain": 0.0003,
                            "maximum_strain": 0.0023,
                            "equipment_compliance": "not_provided",
                            "warning_acknowledged": False,
                        },
                    }
                ],
            },
        )
    )

    assert response.status_code == 200, response.text
    stage = response.json()["stages"][-1]
    scalars = {item["key"]: item["value"] for item in stage["scalar_results"]}
    series = {item["quantity"]: item["values"] for item in stage["series"]}
    assert scalars["toe_strain_offset"] == pytest.approx(0.0003, abs=1e-12)
    assert scalars["toe_r_squared"] == pytest.approx(1.0)
    assert series["strain.engineering"][0] == pytest.approx(0.0, abs=1e-12)
    assert series["stress.engineering"] == source_stress
    assert stage["diagnostics"][0] == "toe.method=tensile.toe_zero_intercept@1.0.0"


def test_preview_rejects_unknown_method_and_hidden_extrapolation() -> None:
    import asyncio

    base = {
        "document": _document(),
        "mapping_profile": {
            "profile_key": "tensile-normalized",
            "label": "Normalized tensile channels",
            "independent_quantity": "strain.engineering",
            "missing_data_policy": "drop_any",
            "bindings": [
                {
                    "channel_key": "engineering_strain",
                    "target_quantity": "strain.engineering",
                    "accepted_normalized_units": ["1"],
                },
                {
                    "channel_key": "engineering_stress",
                    "target_quantity": "stress.engineering",
                    "accepted_normalized_units": ["Pa"],
                },
            ],
        },
    }
    unknown = asyncio.run(
        _request(
            "POST",
            "/api/v1/processing:preview",
            json_body={
                **base,
                "steps": [{"method_id": "solver.secret", "method_version": "1.0.0", "options": {}}],
            },
        )
    )
    assert unknown.status_code == 422
    assert "unknown processing method" in unknown.text

    extrapolation = asyncio.run(
        _request(
            "POST",
            "/api/v1/processing:preview",
            json_body={
                **base,
                "steps": [
                    {
                        "method_id": "rows.sort_unique",
                        "method_version": "1.0.0",
                        "options": {"duplicate_policy": "reject"},
                    },
                    {
                        "method_id": "curve.resample_linear",
                        "method_version": "1.0.0",
                        "options": {
                            "start": -0.01,
                            "end": 0.001,
                            "count": 5,
                            "extrapolation": "reject",
                        },
                    },
                ],
            },
        )
    )
    assert extrapolation.status_code == 422
    assert "extrapolate" in extrapolation.text


def _manual_output_body() -> dict[str, object]:
    return {
        "classification": "internal",
        "label": "Manual workup evidence",
        "source_document": {
            "aggregate_id": "d5400000-0000-4000-8000-000000000020",
            "revision_id": "d5400000-0000-4000-8000-000000000021",
        },
        "mapping_profile": {
            "aggregate_id": "d5400000-0000-4000-8000-000000000022",
            "revision_id": "d5400000-0000-4000-8000-000000000023",
        },
        "steps": [
            {
                "method_id": "metal.elastic_modulus",
                "method_version": "1.0.0",
                "options": {"method": "manual", "manual_modulus_pa": 205000000000},
            },
            {
                "method_id": "metal.engineering_to_true_plastic",
                "method_version": "1.0.0",
                "options": {"necking_policy": "manual_index", "manual_necking_index": 4},
            },
        ],
        "workup_overrides": [
            {
                "kind": "youngs_modulus",
                "original_value": 205,
                "original_unit": "GPa",
                "canonical_value": 205000000000,
                "canonical_unit": "Pa",
                "reason": "Reconcile the measured elastic range.",
            },
            {
                "kind": "necking_boundary",
                "original_value": 4,
                "original_unit": "observed-point-index",
                "canonical_value": 4,
                "canonical_unit": "observed-point-index",
                "reason": "Selected the observed necking boundary.",
            },
        ],
        "change_reason": "Save manual workup evidence.",
    }


def test_processing_output_api_binds_manual_workup_provenance_to_executed_options() -> None:
    import asyncio

    valid = asyncio.run(_output_request(_manual_output_body()))
    assert valid.status_code == 201, valid.text
    assert [item["kind"] for item in valid.json()["workup_overrides"]] == [
        "youngs_modulus",
        "necking_boundary",
    ]
    assert valid.json()["export_provenance"] == {
        "material": {
            "aggregate_id": "d5400000-0000-4000-8000-000000000030",
            "revision_id": "d5400000-0000-4000-8000-000000000031",
        },
        "material_state": {
            "aggregate_id": "d5400000-0000-4000-8000-000000000032",
            "revision_id": "d5400000-0000-4000-8000-000000000033",
        },
        "test_run": {
            "aggregate_id": "d5400000-0000-4000-8000-000000000034",
            "revision_id": "d5400000-0000-4000-8000-000000000035",
        },
    }

    duplicate = _manual_output_body()
    duplicate["workup_overrides"] = [
        duplicate["workup_overrides"][0],  # type: ignore[index]
        duplicate["workup_overrides"][0],  # type: ignore[index]
    ]
    mismatch = _manual_output_body()
    mismatch["workup_overrides"][0]["canonical_value"] = 210000000000  # type: ignore[index]
    unsupported = _manual_output_body()
    unsupported["steps"][0]["options"]["method"] = "robust_huber"  # type: ignore[index]
    missing = _manual_output_body()
    missing["workup_overrides"] = [missing["workup_overrides"][0]]  # type: ignore[index]

    for body, phrase in (
        (duplicate, "one override per kind"),
        (mismatch, "must match the executed manual_modulus_pa"),
        (unsupported, "requires an executed manual modulus step"),
        (missing, "manual necking boundary"),
    ):
        rejected = asyncio.run(_output_request(body))
        assert rejected.status_code == 422, rejected.text
        assert phrase in rejected.text


def test_ensemble_registry_alignment_and_pointwise_statistics_contract() -> None:
    import asyncio

    methods = asyncio.run(_request("GET", "/api/v1/processing-ensemble-methods"))
    assert methods.status_code == 200
    assert [item["method_id"] for item in methods.json()["items"]] == [
        "curves.align_linear_intersection",
        "curves.pointwise_statistics",
    ]
    first = _document()
    second = json.loads(json.dumps(first))
    second["document_id"] = "DP600-TENSILE-REPLICATE-02"
    response = asyncio.run(
        _request(
            "POST",
            "/api/v1/processing:preview-ensemble",
            json_body={
                "documents": [first, second],
                "mapping_profile": {
                    "profile_key": "tensile-normalized",
                    "label": "Normalized tensile channels",
                    "independent_quantity": "strain.engineering",
                    "missing_data_policy": "drop_any",
                    "bindings": [
                        {
                            "channel_key": "engineering_strain",
                            "target_quantity": "strain.engineering",
                            "accepted_normalized_units": ["1"],
                        },
                        {
                            "channel_key": "engineering_stress",
                            "target_quantity": "stress.engineering",
                            "accepted_normalized_units": ["Pa"],
                        },
                    ],
                },
                "preprocessing_steps": [
                    {
                        "method_id": "rows.sort_unique",
                        "method_version": "1.0.0",
                        "options": {"duplicate_policy": "reject"},
                    }
                ],
                "alignment": {
                    "point_count": 3,
                    "domain_policy": "intersection",
                    "extrapolation": "reject",
                },
            },
        )
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["promotable"] is False
    assert len(body["members"]) == 2
    assert body["members"][0]["stage"]["method_id"] == "curves.align_linear_intersection"
    assert body["statistics"][0]["quantity"] == "stress.engineering"
    assert body["statistics"][0]["standard_deviation"] == [0.0, 0.0, 0.0]
