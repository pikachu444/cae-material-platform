from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
import yaml
from cmp.modules.exporting.domain.reference_linear_viscoelasticity import (
    InvalidLinearViscoelasticExport,
    LinearViscoelasticExportTarget,
    LinearViscoelasticMappingReportMismatch,
    build_reference_linear_viscoelastic_solver_card,
    preflight_reference_linear_viscoelastic_export,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
)

ROOT = Path(__file__).parents[3]
REFERENCE_PATH = ROOT / "fixtures/synthetic/linear-viscoelastic-abaqus-reference-v1.json"
MANIFEST_PATH = ROOT / "fixtures/manifests/linear-viscoelastic-abaqus-reference-v1.yaml"


def _reference() -> dict[str, Any]:
    source = REFERENCE_PATH.read_bytes()
    fixture = cast(dict[str, Any], json.loads(source))
    manifest = cast(dict[str, Any], yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")))
    assert manifest["fixture"]["path"] == REFERENCE_PATH.relative_to(ROOT).as_posix()
    assert manifest["fixture"]["classification"] == fixture["classification"]
    assert manifest["fixture"]["non_production"] is fixture["non_production"] is True
    assert manifest["license"]["fixture_data"]
    assert all(source["redistribution"] for source in manifest["sources"])
    assert manifest["boundaries"]["public_experiment_values_used"] == []
    assert manifest["fixture"]["digest"] == {
        "algorithm": "sha256",
        "value": hashlib.sha256(source).hexdigest(),
        "byte_contract": (
            "UTF-8, LF line endings, two-space JSON indentation, final newline included"
        ),
    }
    expected_export = cast(dict[str, Any], manifest["expected_export"])
    golden_path = ROOT / expected_export["path"]
    golden_text = golden_path.read_text(encoding="utf-8")
    assert hashlib.sha256(golden_text.encode("utf-8")).hexdigest() == expected_export["sha256"]
    assert all(
        keyword in golden_text
        for keyword in expected_export["exact_keywords"]
    )
    assert "golden_card_path" not in fixture["export"]
    assert "golden_card_sha256" not in fixture["export"]
    fixture["expected_export"] = expected_export
    return fixture


def _id(value: int) -> UUID:
    return UUID(int=value)


def _source(
    *,
    status: BulkRelaxationStatus | None = None,
    terms: tuple[PronyTerm, ...] | None = None,
) -> ReferenceLinearViscoelasticContent:
    material = cast(dict[str, Any], _reference()["material"])
    declared_terms = cast(list[dict[str, str]], material["prony_terms"])
    return ReferenceLinearViscoelasticContent(
        material_id=_id(1),
        material_revision_id=_id(2),
        material_state_id=_id(3),
        material_state_revision_id=_id(4),
        property_set_id=_id(5),
        property_set_revision_id=_id(6),
        density_kg_per_m3=float(material["density"]["value"]),
        youngs_modulus_pa=float(material["youngs_modulus"]["value"]),
        poisson_ratio=float(material["poisson_ratio"]["value"]),
        bulk_relaxation_status=(
            status
            if status is not None
            else BulkRelaxationStatus(material["bulk_relaxation_status"])
        ),
        terms=(
            terms
            if terms is not None
            else tuple(
                PronyTerm(
                    float(term["shear_ratio"]),
                    float(term["bulk_ratio"]),
                    float(term["relaxation_time"]),
                )
                for term in declared_terms
            )
        ),
    )


def _target() -> LinearViscoelasticExportTarget:
    export = cast(dict[str, Any], _reference()["export"])
    return LinearViscoelasticExportTarget(
        export["solver"], export["solver_version"], export["unit_system"]
    )


def test_synthetic_abaqus_reference_records_complete_nonproduction_properties() -> None:
    fixture = _reference()
    material = fixture["material"]
    terms = material["prony_terms"]

    assert float(material["density"]["value"]) > 0
    assert float(material["youngs_modulus"]["value"]) > 0
    assert -1 < float(material["poisson_ratio"]["value"]) < 0.5
    assert sum(float(term["shear_ratio"]) for term in terms) < 1
    assert [float(term["relaxation_time"]) for term in terms] == sorted(
        float(term["relaxation_time"]) for term in terms
    )
    assert fixture["non_production"] is True


def test_abaqus_preflight_is_explicit_and_deterministic() -> None:
    source = _source()
    first = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
    )
    second = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
    )

    assert first.exportable is True
    assert first.digest == second.digest
    statuses = {item.name: item.status for item in first.items}
    assert statuses == {
        "density": "exact",
        "instantaneous_isotropic_elasticity": "exact",
        "shear_prony_terms": "exact",
        "bulk_relaxation": "not_applicable",
        "temperature_dependence": "not_applicable",
        "unit_system": "transformed",
    }


def test_abaqus_card_matches_golden_fixture_and_byte_digest() -> None:
    source = _source()
    reference = _reference()
    export = cast(dict[str, Any], reference["export"])
    expected_export = cast(dict[str, Any], reference["expected_export"])
    report = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
    )
    _, card = build_reference_linear_viscoelastic_solver_card(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
        expected_mapping_report_sha256=report.digest,
        solver_material_id=int(export["solver_material_id"]),
        material_name=export["material_name"],
    )

    fixture = ROOT / expected_export["path"]
    assert card.card_text == fixture.read_text(encoding="utf-8")
    assert card.card_sha256 == expected_export["sha256"]
    assert all(keyword in card.card_text for keyword in expected_export["exact_keywords"])
    assert card.card_text.count("0.000000000000e+00") == len(source.terms)

    with pytest.raises(InvalidLinearViscoelasticExport, match="mapping statuses"):
        replace(card, prony_terms_mapping_status="approximated")


def test_characterized_bulk_ratios_map_exactly() -> None:
    source = _source(
        status=BulkRelaxationStatus.CHARACTERIZED,
        terms=(PronyTerm(0.2, 0.1, 1.0),),
    )
    report = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=source,
        target=_target(),
    )
    assert next(item for item in report.items if item.name == "bulk_relaxation").status == "exact"


def test_card_requires_exact_preflight_acknowledgement() -> None:
    with pytest.raises(LinearViscoelasticMappingReportMismatch):
        build_reference_linear_viscoelastic_solver_card(
            material_model_id=_id(10),
            material_model_revision_id=_id(11),
            source=_source(),
            target=_target(),
            expected_mapping_report_sha256="f" * 64,
            solver_material_id=42,
            material_name="POLYMER_REFERENCE",
        )


def test_openradioss_law62_is_not_silently_used_for_linear_prony() -> None:
    target = LinearViscoelasticExportTarget("openradioss", "2025", "kg_m_s")
    report = preflight_reference_linear_viscoelastic_export(
        material_model_id=_id(10),
        material_model_revision_id=_id(11),
        source=_source(),
        target=target,
    )
    assert report.exportable is False
    assert report.items[0].status == "unsupported"
    assert "Ogden-Prony" in report.items[0].detail
