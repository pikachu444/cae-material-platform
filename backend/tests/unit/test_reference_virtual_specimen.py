from __future__ import annotations

import json
from uuid import UUID

import pytest
from cmp.modules.validation.domain.reference_virtual_specimen import (
    InvalidNativeResult,
    InvalidValidationTemplate,
    ReferenceRunnerOutcome,
    ReferenceValidationPlanContent,
    ReferenceVirtualSpecimenTemplateContent,
    SolverTerminationStatus,
    ValidationArtifactReference,
    ValidationConflict,
    ValidationExecutionMode,
    ValidationRunResultManifestContent,
    map_reference_runner_outcome,
    reference_mock_native_result_bytes,
    render_reference_deck,
    result_manifest_bytes,
    result_manifest_sha256,
    validate_external_job_reference,
    validate_reference_native_result_bytes,
)

TEMPLATE = UUID("27000000-0000-4000-8000-000000000001")
TEMPLATE_REVISION = UUID("27000000-0000-4000-8000-000000000002")
MODEL = UUID("27000000-0000-4000-8000-000000000003")
MODEL_REVISION = UUID("27000000-0000-4000-8000-000000000004")
CARD = UUID("27000000-0000-4000-8000-000000000005")
CARD_REVISION = UUID("27000000-0000-4000-8000-000000000006")
SELECTION = UUID("27000000-0000-4000-8000-000000000007")
SELECTION_REVISION = UUID("27000000-0000-4000-8000-000000000008")
RUN = UUID("27000000-0000-4000-8000-000000000009")
DECK = UUID("27000000-0000-4000-8000-00000000000a")
STDOUT = UUID("27000000-0000-4000-8000-00000000000b")
STDERR = UUID("27000000-0000-4000-8000-00000000000c")
NATIVE = UUID("27000000-0000-4000-8000-00000000000d")


def _template(**overrides: object) -> ReferenceVirtualSpecimenTemplateContent:
    values: dict[str, object] = {
        "template_label": "Reference tensile virtual specimen",
        "gauge_length_m": 0.05,
        "cross_section_area_m2": 1.0e-5,
        "axial_element_count": 10,
        "axial_displacement_end_m": 0.001,
        "output_sample_count": 5,
    }
    values.update(overrides)
    return ReferenceVirtualSpecimenTemplateContent(**values)  # type: ignore[arg-type]


def _plan(**overrides: object) -> ReferenceValidationPlanContent:
    values: dict[str, object] = {
        "plan_label": "Reference tensile validation",
        "template_id": TEMPLATE,
        "template_revision_id": TEMPLATE_REVISION,
        "material_model_id": MODEL,
        "material_model_revision_id": MODEL_REVISION,
        "solver_card_id": CARD,
        "solver_card_revision_id": CARD_REVISION,
        "experimental_selection_id": SELECTION,
        "experimental_selection_revision_id": SELECTION_REVISION,
    }
    values.update(overrides)
    return ReferenceValidationPlanContent(**values)  # type: ignore[arg-type]


def _artifact(value: UUID, digest: str) -> ValidationArtifactReference:
    return ValidationArtifactReference(value, digest)


def test_reference_template_and_plan_are_typed_non_production_contracts() -> None:
    template = _template()
    plan = _plan()

    assert template.canonical()["target"] == {
        "solver": "openradioss",
        "version": "2025",
        "unit_system": "kg_m_s",
    }
    assert template.canonical()["non_production"] is True
    assert plan.runner_id == "cmp.reference.inline-mock-runner"
    assert plan.canonical()["non_production"] is True

    with pytest.raises(InvalidValidationTemplate, match="below gauge_length"):
        _template(axial_displacement_end_m=0.05)


@pytest.mark.parametrize(
    ("outcome", "status", "failure", "termination", "native"),
    [
        (ReferenceRunnerOutcome.SUCCEEDED, "succeeded", None, "normal", True),
        (
            ReferenceRunnerOutcome.LICENSE_UNAVAILABLE,
            "failed",
            "license_unavailable",
            "not_available",
            False,
        ),
        (
            ReferenceRunnerOutcome.QUEUE_TIMEOUT,
            "failed",
            "queue_timeout",
            "not_available",
            False,
        ),
        (
            ReferenceRunnerOutcome.SOLVER_FAILED,
            "failed",
            "solver_failed",
            "abnormal",
            False,
        ),
    ],
)
def test_reference_mock_outcomes_are_explicit_and_never_silent(
    outcome: ReferenceRunnerOutcome,
    status: str,
    failure: str | None,
    termination: str,
    native: bool,
) -> None:
    transition = map_reference_runner_outcome(outcome)

    assert transition.status.value == status
    assert transition.failure_code == failure
    assert transition.termination.value == termination
    assert transition.native_result_available is native


def test_deck_regression_keeps_frozen_card_and_rejects_shell_like_job_references() -> None:
    deck = render_reference_deck(
        run_id=RUN,
        template=_template(),
        card_text="/MAT/ELAST/1\n# frozen reference card\n",
        card_sha256="a" * 64,
    ).decode("utf-8")

    assert "source_solver_card_sha256: " + "a" * 64 in deck
    assert "/MAT/ELAST/1" in deck
    assert "never executed here" in deck
    assert validate_external_job_reference("external/openradioss:job-42") == (
        "external/openradioss:job-42"
    )
    with pytest.raises(ValidationConflict, match="unsupported characters"):
        validate_external_job_reference("openradioss -i deck.rad; rm -rf /")


def test_native_result_requires_matching_target_and_manifest_hash_is_deterministic() -> None:
    template = _template()
    native_bytes = reference_mock_native_result_bytes(
        template=template,
        youngs_modulus_pa=210_000_000_000.0,
    )

    descriptor = validate_reference_native_result_bytes(native_bytes, template=template)
    assert descriptor.solver_termination is SolverTerminationStatus.NORMAL
    assert descriptor.point_count == 5

    invalid_document = json.loads(native_bytes)
    invalid_document["target"]["version"] = "2024"
    with pytest.raises(InvalidNativeResult, match="does not match"):
        validate_reference_native_result_bytes(
            json.dumps(invalid_document).encode("utf-8"), template=template
        )

    content = ValidationRunResultManifestContent(
        validation_run_id=RUN,
        execution_mode=ValidationExecutionMode.REFERENCE_INLINE_MOCK,
        solver_termination=SolverTerminationStatus.NORMAL,
        external_job_reference=None,
        deck=_artifact(DECK, "b" * 64),
        stdout=_artifact(STDOUT, "c" * 64),
        stderr=_artifact(STDERR, "d" * 64),
        native_result=_artifact(NATIVE, "e" * 64),
        native_result_state="available",
    )
    assert result_manifest_sha256(content) == result_manifest_sha256(content)
    assert result_manifest_bytes(content) == result_manifest_bytes(content)

    with pytest.raises(ValidationConflict, match="state does not match"):
        ValidationRunResultManifestContent(
            validation_run_id=RUN,
            execution_mode=ValidationExecutionMode.REFERENCE_INLINE_MOCK,
            solver_termination=SolverTerminationStatus.NORMAL,
            external_job_reference=None,
            deck=_artifact(DECK, "b" * 64),
            stdout=_artifact(STDOUT, "c" * 64),
            stderr=_artifact(STDERR, "d" * 64),
            native_result=None,
            native_result_state="available",
        )
