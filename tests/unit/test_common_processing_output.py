from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from cmp.modules.datasets.domain.canonical_test_data import parse_canonical_test_data
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.processing.application.common_outputs import (
    CommitProcessingOutput,
    CommonPipelineError,
    CommonProcessingOutputService,
    ExactRevisionPin,
    ProcessingWorkupOverride,
    processing_output_document,
    validate_workup_overrides,
)
from cmp.modules.processing.domain.common_pipeline import (
    ChannelBinding,
    MappingProfileContent,
    MissingDataPolicy,
    ProcessingStep,
    preview_pipeline,
)
from cmp.shared.domain.revisions import canonical_json_bytes

_ORG = UUID("d5400000-0000-4000-8000-000000000101")
_PROJECT = UUID("d5400000-0000-4000-8000-000000000102")
_ACTOR = UUID("d5400000-0000-4000-8000-000000000103")
_CONTEXT = SecurityContext(
    principal=Principal(_ACTOR, PrincipalType.USER, "Modeler", True),
    organization_id=_ORG,
    project_id=_PROJECT,
    issuer="urn:cmp:test",
    subject=str(_ACTOR),
    token_id="workup-output-test",
    groups=(),
    scopes=("openid",),
    request_id=UUID("d5400000-0000-4000-8000-000000000104"),
    trace_id="00-0000000000000000000000000000d540-000000000000d540-01",
    authenticated_at=datetime(2026, 7, 24, tzinfo=UTC),
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


class _NoCallPort:
    def __init__(self) -> None:
        self.calls = 0

    async def export_document(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        self.calls += 1
        raise AssertionError("preflight must reject invalid workup evidence before source reads")

    def get_profile_revision(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        self.calls += 1
        raise AssertionError("preflight must reject invalid workup evidence before profile reads")

    async def finalize_derived_bytes(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        self.calls += 1
        raise AssertionError("invalid workup evidence must not finalize an Artifact")

    def output_store(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        self.calls += 1
        raise AssertionError("invalid workup evidence must not persist a revision")


def test_committed_output_document_contains_exact_pins_steps_and_every_stage() -> None:
    document = parse_canonical_test_data(
        json.loads(
            Path("contracts/examples/positive/canonical-test-data.json").read_text(encoding="utf-8")
        )
    )
    profile = MappingProfileContent(
        profile_key="tensile",
        label="Tensile mapping",
        independent_quantity="strain.engineering",
        missing_data_policy=MissingDataPolicy.DROP_ANY,
        bindings=(
            ChannelBinding("engineering_strain", "strain.engineering", ("1",)),
            ChannelBinding("engineering_stress", "stress.engineering", ("Pa",)),
        ),
    )
    steps = (ProcessingStep("rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}),)
    preview = preview_pipeline(document, profile, steps)
    value = processing_output_document(
        output_id=UUID("d5400000-0000-4000-8000-000000000001"),
        source=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000002"),
            UUID("d5400000-0000-4000-8000-000000000003"),
        ),
        source_canonical_sha256="f" * 64,
        profile=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000004"),
            UUID("d5400000-0000-4000-8000-000000000005"),
        ),
        steps=steps,
        preview=preview,
    )
    encoded = canonical_json_bytes(value)
    decoded = json.loads(encoded)
    assert decoded["document_type"] == "cmp.processing-output"
    assert decoded["source_document"]["revision_id"].endswith("0003")
    assert decoded["source_canonical_artifact_sha256"] == "f" * 64
    assert decoded["mapping_profile"]["revision_id"].endswith("0005")
    assert decoded["steps"] == [
        {
            "method_id": "rows.sort_unique",
            "method_version": "1.0.0",
            "options": {"duplicate_policy": "reject"},
        }
    ]
    assert [stage["method_id"] for stage in decoded["result"]["stages"]] == [
        "mapping",
        "rows.sort_unique",
    ]
    assert decoded["result"]["source_document_sha256"] == document.digest


def test_committed_output_document_preserves_structured_manual_workup_evidence() -> None:
    document = parse_canonical_test_data(
        json.loads(
            Path("contracts/examples/positive/canonical-test-data.json").read_text(encoding="utf-8")
        )
    )
    profile = MappingProfileContent(
        profile_key="tensile",
        label="Tensile mapping",
        independent_quantity="strain.engineering",
        missing_data_policy=MissingDataPolicy.DROP_ANY,
        bindings=(
            ChannelBinding("engineering_strain", "strain.engineering", ("1",)),
            ChannelBinding("engineering_stress", "stress.engineering", ("Pa",)),
        ),
    )
    steps = (ProcessingStep("rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}),)
    value = processing_output_document(
        output_id=UUID("d5400000-0000-4000-8000-000000000001"),
        source=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000002"),
            UUID("d5400000-0000-4000-8000-000000000003"),
        ),
        source_canonical_sha256="f" * 64,
        profile=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000004"),
            UUID("d5400000-0000-4000-8000-000000000005"),
        ),
        steps=steps,
        preview=preview_pipeline(document, profile, steps),
        workup_overrides=(
            ProcessingWorkupOverride(
                kind="youngs_modulus",
                original_value=205,
                original_unit="GPa",
                canonical_value=205_000_000_000,
                canonical_unit="Pa",
                reason="Reconcile the measured elastic range.",
            ),
        ),
    )

    assert value["workup_overrides"] == [
        {
            "kind": "youngs_modulus",
            "original_value": 205,
            "original_unit": "GPa",
            "canonical_value": 205_000_000_000,
            "canonical_unit": "Pa",
            "reason": "Reconcile the measured elastic range.",
        }
    ]


def _manual_workup_steps() -> tuple[ProcessingStep, ...]:
    return (
        ProcessingStep(
            "metal.elastic_modulus",
            "1.0.0",
            {
                "method": "manual",
                "manual_modulus_pa": 205_000_000_000,
            },
        ),
        ProcessingStep(
            "metal.engineering_to_true_plastic",
            "1.0.0",
            {
                "necking_policy": "manual_index",
                "manual_necking_index": 4,
            },
        ),
    )


def _manual_workup_overrides() -> tuple[ProcessingWorkupOverride, ...]:
    return (
        ProcessingWorkupOverride(
            kind="youngs_modulus",
            original_value=205,
            original_unit="GPa",
            canonical_value=205_000_000_000,
            canonical_unit="Pa",
            reason="Reconcile the measured elastic range.",
        ),
        ProcessingWorkupOverride(
            kind="necking_boundary",
            original_value=4,
            original_unit="observed-point-index",
            canonical_value=4,
            canonical_unit="observed-point-index",
            reason="Selected the observed necking boundary.",
        ),
    )


def test_workup_overrides_bind_bidirectionally_to_executed_manual_steps() -> None:
    validate_workup_overrides(_manual_workup_steps(), _manual_workup_overrides())


@pytest.mark.parametrize(
    ("steps", "overrides", "message"),
    [
        (
            _manual_workup_steps(),
            (_manual_workup_overrides()[0], _manual_workup_overrides()[0]),
            "one override per kind",
        ),
        (_manual_workup_steps(), (_manual_workup_overrides()[0],), "manual necking boundary"),
        (_manual_workup_steps(), (_manual_workup_overrides()[1],), "manual Young's modulus"),
        (
            (
                ProcessingStep(
                    "metal.elastic_modulus",
                    "1.0.0",
                    {"method": "robust_huber", "manual_modulus_pa": 205_000_000_000},
                ),
            ),
            (_manual_workup_overrides()[0],),
            "requires an executed manual modulus step",
        ),
        (
            (
                ProcessingStep(
                    "metal.elastic_modulus",
                    "1.0.0",
                    {"method": "manual", "manual_modulus_pa": 210_000_000_000},
                ),
            ),
            (_manual_workup_overrides()[0],),
            "must match the executed manual_modulus_pa",
        ),
        (
            (
                ProcessingStep(
                    "metal.engineering_to_true_plastic",
                    "1.0.0",
                    {"necking_policy": "observed_full_domain", "manual_necking_index": 4},
                ),
            ),
            (_manual_workup_overrides()[1],),
            "requires an executed manual-index step",
        ),
    ],
)
def test_workup_override_rejections_are_bound_to_executed_steps(
    steps: tuple[ProcessingStep, ...],
    overrides: tuple[ProcessingWorkupOverride, ...],
    message: str,
) -> None:
    with pytest.raises(Exception, match=message):
        validate_workup_overrides(steps, overrides)


def test_preflight_rejects_missing_manual_workup_evidence_before_artifact_or_revision() -> None:
    import asyncio

    source = _NoCallPort()
    profile = _NoCallPort()
    artifacts = _NoCallPort()
    repository = _NoCallPort()
    service = CommonProcessingOutputService(
        repository=repository,  # type: ignore[arg-type]
        test_data=source,  # type: ignore[arg-type]
        profiles=profile,  # type: ignore[arg-type]
        artifacts=artifacts,  # type: ignore[arg-type]
    )
    command = CommitProcessingOutput(
        classification=DataClassification.INTERNAL,
        label="Missing manual modulus evidence",
        source_document=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000105"),
            UUID("d5400000-0000-4000-8000-000000000106"),
        ),
        mapping_profile=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000107"),
            UUID("d5400000-0000-4000-8000-000000000108"),
        ),
        steps=(_manual_workup_steps()[0],),
        change_reason="Verify preflight rejection is atomic.",
    )

    with pytest.raises(CommonPipelineError, match="requires workup provenance"):
        asyncio.run(service.commit(_CONTEXT, _DECISION, command))

    assert source.calls == profile.calls == artifacts.calls == repository.calls == 0
