from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from cmp.modules.datasets.application.canonical_test_data import (
    ExactRevisionRef,
    GovernedTestDataSource,
)
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
    FitDecisionParameter,
    FitDecisionParameterSet,
    FitDecisionSnapshot,
    ProcessingWorkupOverride,
    processing_output_document,
    validate_fit_decision,
    validate_workup_overrides,
)
from cmp.modules.processing.domain.common_pipeline import (
    ChannelBinding,
    CurveStage,
    MappingProfileContent,
    MissingDataPolicy,
    ProcessingPreview,
    ProcessingStep,
    QuantitySeries,
    ScalarResult,
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

_EXPORT_PROVENANCE = GovernedTestDataSource(
    material=ExactRevisionRef(
        UUID("d5400000-0000-4000-8000-000000000111"),
        UUID("d5400000-0000-4000-8000-000000000112"),
    ),
    material_state=ExactRevisionRef(
        UUID("d5400000-0000-4000-8000-000000000113"),
        UUID("d5400000-0000-4000-8000-000000000114"),
    ),
    test_run=ExactRevisionRef(
        UUID("d5400000-0000-4000-8000-000000000115"),
        UUID("d5400000-0000-4000-8000-000000000116"),
    ),
)


def test_fit_decision_snapshot_preserves_single_and_blend_identity() -> None:
    single = FitDecisionSnapshot(
        candidate_key="swift",
        mode="single",
        primary_law="swift",
        secondary_law=None,
        primary_weight=None,
        parameter_sets=(
            FitDecisionParameterSet("swift", (FitDecisionParameter("K", 500e6, "Pa"),)),
        ),
        fit_minimum=0.01,
        fit_maximum=0.12,
        extrapolation_maximum=0.2,
        extrapolation_policy="bounded",
        metric_definition="relative RMSE",
        metric_value=0.012,
        requested_term_policy=None,
        actual_term_count=None,
        selection_reason="Stable observed response.",
        warning_acknowledged=False,
    )
    assert single.mode == "single"
    assert single.parameter_sets[0].law == "swift"

    with pytest.raises(CommonPipelineError, match="blend fit decision"):
        FitDecisionSnapshot(
            candidate_key="swift+voce",
            mode="blend",
            primary_law="swift",
            secondary_law="voce",
            primary_weight=0.5,
            parameter_sets=(
                FitDecisionParameterSet("swift", (FitDecisionParameter("K", 500e6, "Pa"),)),
            ),
            fit_minimum=0.01,
            fit_maximum=0.12,
            extrapolation_maximum=0.2,
            extrapolation_policy="bounded",
            metric_definition="relative RMSE",
            metric_value=0.012,
            requested_term_policy=None,
            actual_term_count=None,
            selection_reason="Need both laws.",
            warning_acknowledged=True,
        )
    with pytest.raises(CommonPipelineError, match="must be trimmed"):
        replace(single, selection_reason=" Stable observed response. ")


def test_fit_preflight_rejects_missing_or_mismatched_decision_before_persistence() -> None:
    step = ProcessingStep(
        "metal.hardening_fit_extrapolate",
        "1.0.0",
        {
            "families": ["swift"],
            "primary_family": "swift",
            "secondary_family": "swift",
            "primary_weight": 0.5,
            "fit_minimum_strain": 0.01,
            "fit_maximum_strain": 0.12,
            "extrapolation_maximum_strain": 0.2,
        },
    )
    preview = ProcessingPreview(
        "a" * 64,
        "b" * 64,
        "strain.plastic",
        (
            CurveStage(
                0,
                "mapping",
                "1.0.0",
                2,
                (
                    QuantitySeries("strain.plastic", "1", (0.0, 0.1)),
                    QuantitySeries("stress", "Pa", (1.0, 2.0)),
                ),
                (),
                (),
            ),
            CurveStage(
                1,
                step.method_id,
                step.method_version,
                2,
                (
                    QuantitySeries("strain.plastic", "1", (0.0, 0.1)),
                    QuantitySeries("stress", "Pa", (1.0, 2.0)),
                ),
                (),
                (ScalarResult("swift.relative_rmse", "statistics.relative_rmse", 0.01, "1"),),
            ),
        ),
    )
    with pytest.raises(CommonPipelineError, match="requires an explicit fit decision"):
        validate_fit_decision((step,), preview, None)


def test_fit_preflight_binds_metal_selection_to_recomputed_scalar_evidence() -> None:
    step = ProcessingStep(
        "metal.hardening_fit_extrapolate",
        "1.0.0",
        {
            "families": ["swift"],
            "primary_family": "swift",
            "secondary_family": "swift",
            "primary_weight": 0.5,
            "fit_minimum_strain": 0.01,
            "fit_maximum_strain": 0.12,
            "extrapolation_maximum_strain": 0.2,
        },
    )
    scalars = (
        ScalarResult("swift.relative_rmse", "statistics.relative_rmse", 0.01, "1"),
        ScalarResult("swift.parameter.K", "model.parameter.K", 500e6, "Pa"),
        ScalarResult("swift.parameter.K.lower", "model.parameter.bound.lower.K", 1.0, "Pa"),
        ScalarResult("swift.parameter.K.upper", "model.parameter.bound.upper.K", 1e9, "Pa"),
        ScalarResult("swift.parameter.epsilon_0", "model.parameter.epsilon_0", 0.002, "1"),
        ScalarResult(
            "swift.parameter.epsilon_0.lower",
            "model.parameter.bound.lower.epsilon_0",
            1e-8,
            "1",
        ),
        ScalarResult(
            "swift.parameter.epsilon_0.upper",
            "model.parameter.bound.upper.epsilon_0",
            1.0,
            "1",
        ),
    )
    stage = CurveStage(1, step.method_id, step.method_version, 2, (), (), scalars)
    preview = ProcessingPreview("a" * 64, "b" * 64, "strain.plastic", (stage, stage))
    decision = FitDecisionSnapshot(
        candidate_key="swift",
        mode="single",
        primary_law="swift",
        secondary_law=None,
        primary_weight=None,
        parameter_sets=(
            FitDecisionParameterSet(
                "swift",
                (
                    FitDecisionParameter("K", 500e6, "Pa", 1.0, 1e9),
                    FitDecisionParameter("epsilon_0", 0.002, "1", 1e-8, 1.0),
                ),
            ),
        ),
        fit_minimum=0.01,
        fit_maximum=0.12,
        extrapolation_maximum=0.2,
        extrapolation_policy="bounded",
        metric_definition="relative_rmse",
        metric_value=0.01,
        requested_term_policy=None,
        actual_term_count=None,
        selection_reason="Stable response.",
        warning_acknowledged=False,
    )
    validate_fit_decision((step,), preview, decision)
    with pytest.raises(CommonPipelineError, match="differs from recomputed"):
        validate_fit_decision((step,), preview, replace(decision, metric_value=0.02))
    with pytest.raises(CommonPipelineError, match="incomplete"):
        validate_fit_decision(
            (step,),
            preview,
            replace(
                decision,
                parameter_sets=(
                    FitDecisionParameterSet(
                        "swift",
                        (FitDecisionParameter("K", 500e6, "Pa", 1.0, 1e9),),
                    ),
                ),
            ),
        )


def test_fit_preflight_binds_polymer_range_and_parameters_to_actual_server_result() -> None:
    step = ProcessingStep(
        "polymer.prony_fit_compare",
        "1.0.0",
        {
            "selection_mode": "automatic_bic",
            "candidate_term_counts": [1, 2],
            "selection_reason": "Compare actual server candidates.",
        },
    )
    scalars = (
        ScalarResult("prony_selected_term_count", "model.prony.term_count", 2, "1"),
        ScalarResult("prony_2_normalized_rmse", "statistics.normalized_rmse", 0.012, "1"),
        ScalarResult("prony_equilibrium_modulus", "modulus.shear.equilibrium", 1e6, "Pa"),
        ScalarResult("prony_g_ratio_1", "model.prony.shear_ratio", 0.2, "1"),
        ScalarResult("prony_relaxation_time_1", "time.relaxation", 0.1, "s"),
        ScalarResult("prony_g_ratio_2", "model.prony.shear_ratio", 0.3, "1"),
        ScalarResult("prony_relaxation_time_2", "time.relaxation", 10, "s"),
    )
    stage = CurveStage(
        1,
        step.method_id,
        step.method_version,
        3,
        (QuantitySeries("time", "s", (0.1, 1, 10)),),
        (),
        scalars,
    )
    preview = ProcessingPreview("a" * 64, "b" * 64, "time", (stage, stage))
    parameters = tuple(
        FitDecisionParameter(item.key, item.value, item.unit)
        for item in scalars
        if item.key == "prony_equilibrium_modulus"
        or item.key.startswith("prony_g_ratio_")
        or item.key.startswith("prony_relaxation_time_")
    )
    decision = FitDecisionSnapshot(
        candidate_key="prony:2",
        mode="single",
        primary_law="generalized_maxwell",
        secondary_law=None,
        primary_weight=None,
        parameter_sets=(FitDecisionParameterSet("generalized_maxwell", parameters),),
        fit_minimum=0.1,
        fit_maximum=10,
        extrapolation_maximum=None,
        extrapolation_policy="observed_only",
        metric_definition="normalized_rmse",
        metric_value=0.012,
        requested_term_policy="automatic_bic",
        actual_term_count=2,
        selection_reason="Select the actual two-term server result.",
        warning_acknowledged=False,
    )
    validate_fit_decision((step,), preview, decision)

    with pytest.raises(CommonPipelineError, match="differs from recomputed"):
        validate_fit_decision((step,), preview, replace(decision, fit_minimum=0.2))

    forged_parameters = (
        replace(parameters[0], value=2e6),
        *parameters[1:],
    )
    with pytest.raises(CommonPipelineError, match="differs from recomputed"):
        validate_fit_decision(
            (step,),
            preview,
            replace(
                decision,
                parameter_sets=(
                    FitDecisionParameterSet("generalized_maxwell", forged_parameters),
                ),
            ),
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
        export_provenance=_EXPORT_PROVENANCE,
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
    assert decoded["export_provenance"] == {
        "material": {
            "aggregate_id": str(_EXPORT_PROVENANCE.material.aggregate_id),
            "revision_id": str(_EXPORT_PROVENANCE.material.revision_id),
        },
        "material_state": {
            "aggregate_id": str(_EXPORT_PROVENANCE.material_state.aggregate_id),
            "revision_id": str(_EXPORT_PROVENANCE.material_state.revision_id),
        },
        "test_run": {
            "aggregate_id": str(_EXPORT_PROVENANCE.test_run.aggregate_id),
            "revision_id": str(_EXPORT_PROVENANCE.test_run.revision_id),
        },
    }


def test_preflight_projects_proof_only_from_the_exact_test_data_revision() -> None:
    import asyncio

    source_bytes = Path("contracts/examples/positive/canonical-test-data.json").read_bytes()
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

    class Source:
        async def export_document(self, *args: object) -> object:
            del args
            return (
                SimpleNamespace(
                    current=SimpleNamespace(
                        scope=SimpleNamespace(classification="internal")
                    ),
                    content=SimpleNamespace(
                        canonical_sha256="c" * 64,
                        governed_source=_EXPORT_PROVENANCE,
                    ),
                ),
                source_bytes,
            )

    class Profiles:
        def get_profile_revision(self, *args: object) -> object:
            del args
            return SimpleNamespace(
                current=SimpleNamespace(scope=SimpleNamespace(classification="internal")),
                content=profile,
            )

    service = CommonProcessingOutputService(
        repository=cast(Any, _NoCallPort()),
        test_data=cast(Any, Source()),
        profiles=cast(Any, Profiles()),
        artifacts=cast(Any, _NoCallPort()),
    )
    command = CommitProcessingOutput(
        classification=DataClassification.INTERNAL,
        label="Exact provenance preflight",
        source_document=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000105"),
            UUID("d5400000-0000-4000-8000-000000000106"),
        ),
        mapping_profile=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000107"),
            UUID("d5400000-0000-4000-8000-000000000108"),
        ),
        steps=(ProcessingStep("rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}),),
        change_reason="Project exact source proof without inference.",
    )

    resolved = asyncio.run(service.preflight(_CONTEXT, _DECISION, command))
    assert resolved.export_provenance == _EXPORT_PROVENANCE


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


def test_preflight_rejects_decision_on_nonfit_before_artifact_or_revision() -> None:
    import asyncio

    source_bytes = Path("contracts/examples/positive/canonical-test-data.json").read_bytes()
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

    class Source:
        async def export_document(self, *args: object) -> object:
            return SimpleNamespace(
                current=SimpleNamespace(
                    scope=SimpleNamespace(classification="internal"),
                    content=SimpleNamespace(canonical_sha256="c" * 64),
                )
            ), source_bytes

    class Profiles:
        def get_profile_revision(self, *args: object) -> object:
            return SimpleNamespace(
                current=SimpleNamespace(scope=SimpleNamespace(classification="internal")),
                content=profile,
            )

    artifacts = _NoCallPort()
    repository = _NoCallPort()
    service = CommonProcessingOutputService(
        repository=cast(Any, repository),
        test_data=cast(Any, Source()),
        profiles=cast(Any, Profiles()),
        artifacts=cast(Any, artifacts),
    )
    decision = FitDecisionSnapshot(
        candidate_key="swift",
        mode="single",
        primary_law="swift",
        secondary_law=None,
        primary_weight=None,
        parameter_sets=(
            FitDecisionParameterSet("swift", (FitDecisionParameter("K", 500e6, "Pa"),)),
        ),
        fit_minimum=0.01,
        fit_maximum=0.12,
        extrapolation_maximum=0.2,
        extrapolation_policy="bounded",
        metric_definition="relative_rmse",
        metric_value=0.01,
        requested_term_policy=None,
        actual_term_count=None,
        selection_reason="This must not attach to a processing-only output.",
        warning_acknowledged=False,
    )
    command = CommitProcessingOutput(
        classification=DataClassification.INTERNAL,
        label="Invalid fit decision",
        source_document=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000105"),
            UUID("d5400000-0000-4000-8000-000000000106"),
        ),
        mapping_profile=ExactRevisionPin(
            UUID("d5400000-0000-4000-8000-000000000107"),
            UUID("d5400000-0000-4000-8000-000000000108"),
        ),
        steps=(ProcessingStep("rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}),),
        change_reason="Reject an arbitrary decision",
        fit_decision=decision,
    )
    with pytest.raises(CommonPipelineError, match="only allowed when committing a fit step"):
        asyncio.run(service.commit(_CONTEXT, _DECISION, command))
    assert artifacts.calls == repository.calls == 0


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
