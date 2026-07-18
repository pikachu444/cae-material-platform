"""Canonical ``cmp.neutral-material`` exchange document.

The document is a deterministic, user-facing envelope around one solver-neutral Material
Model IR revision.  It deliberately keeps model-family parameters typed instead of accepting
an arbitrary parameter map, and it pins every scientific input to an immutable revision and
digest.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily
from cmp.modules.modeling.domain.reference_ogden_calibration import (
    OgdenCalibrationRole,
    OgdenTestMode,
)

NEUTRAL_MATERIAL_DOCUMENT_TYPE = "cmp.neutral-material"
NEUTRAL_MATERIAL_SCHEMA_VERSION = "1.0.0"
NEUTRAL_MATERIAL_SCHEMA_REF = "https://cmp.example/contracts/modeling/neutral-material.schema.json"
NEUTRAL_HYPERELASTIC_IR_SCHEMA_ID = "urn:cmp:modeling:neutral-hyperelastic-ir:1.0.0"
NEUTRAL_HYPERELASTIC_IR_SCHEMA_VERSION = "1.0.0"
NEUTRAL_HYPERELASTIC_IR_SCHEMA_DIGEST = hashlib.sha256(
    json.dumps(
        {
            "families": [item.value for item in HyperelasticFamily],
            "parameter_contracts": {
                "neo_hookean": ["c10_pa"],
                "mooney_rivlin": ["c10_pa", "c01_pa"],
                "yeoh": ["c10_pa", "c20_pa", "c30_pa"],
                "ogden_1": ["mu_pa", "alpha"],
            },
            "volumetric_response": "incompressible",
            "maturity": "reference",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


class InvalidNeutralMaterial(ValueError):
    """The exchange document is incomplete, ambiguous, or internally inconsistent."""


class EvidenceStatus(StrEnum):
    EXACT_REVISION = "exact_revision"
    NOT_APPLICABLE = "not_applicable"


class CurveStage(StrEnum):
    NORMALIZED = "normalized"
    FITTED = "fitted"
    RESIDUAL = "residual"


class ModelMaturity(StrEnum):
    REFERENCE = "reference"
    VALIDATED = "validated"
    PRODUCTION_APPROVED = "production_approved"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidNeutralMaterial(f"{name} must be a non-zero UUID")


def _sha(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidNeutralMaterial(f"{name} must be a lowercase SHA-256")


def _text(name: str, value: str, maximum: int = 2000) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidNeutralMaterial(f"{name} must be trimmed and contain 1..{maximum} characters")


def _finite(name: str, value: float, *, positive: bool = False) -> None:
    if not math.isfinite(value) or (positive and value <= 0):
        qualifier = "finite and greater than zero" if positive else "finite"
        raise InvalidNeutralMaterial(f"{name} must be {qualifier}")


@dataclass(frozen=True, slots=True)
class RevisionReference:
    object_id: UUID
    revision_id: UUID

    def __post_init__(self) -> None:
        _uuid("object_id", self.object_id)
        _uuid("revision_id", self.revision_id)

    def canonical(self) -> dict[str, str]:
        return {"id": str(self.object_id), "revision_id": str(self.revision_id)}


@dataclass(frozen=True, slots=True)
class OptionalRevisionEvidence:
    """Explicitly distinguish an exact optional input from an inapplicable input."""

    status: EvidenceStatus
    reason: str
    reference: RevisionReference | None = None

    def __post_init__(self) -> None:
        _text("optional evidence reason", self.reason, 500)
        if (self.status is EvidenceStatus.EXACT_REVISION) != (self.reference is not None):
            raise InvalidNeutralMaterial(
                "exact_revision evidence requires a reference; not_applicable forbids one"
            )

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {"status": self.status.value, "reason": self.reason}
        if self.reference is not None:
            result["reference"] = self.reference.canonical()
        return result


@dataclass(frozen=True, slots=True)
class NeutralDatasetSource:
    dataset: RevisionReference
    role: OgdenCalibrationRole
    test_mode: OgdenTestMode
    normalized_artifact_id: UUID
    normalized_artifact_sha256: str

    def __post_init__(self) -> None:
        _uuid("normalized_artifact_id", self.normalized_artifact_id)
        _sha("normalized_artifact_sha256", self.normalized_artifact_sha256)

    def canonical(self) -> dict[str, object]:
        return {
            "dataset": self.dataset.canonical(),
            "role": self.role.value,
            "test_mode": self.test_mode.value,
            "normalized_artifact": {
                "artifact_id": str(self.normalized_artifact_id),
                "sha256": self.normalized_artifact_sha256,
            },
        }


@dataclass(frozen=True, slots=True)
class NeutralCurve:
    stage: CurveStage
    dataset_revision_id: UUID
    test_mode: OgdenTestMode
    x_quantity: str
    x_unit: str
    y_quantity: str
    y_unit: str
    x: tuple[float, ...]
    y: tuple[float, ...]

    def __post_init__(self) -> None:
        _uuid("curve dataset_revision_id", self.dataset_revision_id)
        for name, value in (
            ("x_quantity", self.x_quantity),
            ("x_unit", self.x_unit),
            ("y_quantity", self.y_quantity),
            ("y_unit", self.y_unit),
        ):
            _text(name, value, 160)
        if not self.x or len(self.x) != len(self.y) or len(self.x) > 50_000:
            raise InvalidNeutralMaterial("curve x/y arrays must have an equal length of 1..50000")
        for curve_value in (*self.x, *self.y):
            _finite("curve value", curve_value)

    def canonical(self) -> dict[str, object]:
        return {
            "stage": self.stage.value,
            "dataset_revision_id": str(self.dataset_revision_id),
            "test_mode": self.test_mode.value,
            "x_quantity": self.x_quantity,
            "x_unit": self.x_unit,
            "y_quantity": self.y_quantity,
            "y_unit": self.y_unit,
            "x": list(self.x),
            "y": list(self.y),
        }


@dataclass(frozen=True, slots=True)
class NeutralHyperelasticParameters:
    """Closed union for the four T-55E families; absent fields are not defaulted."""

    family: HyperelasticFamily
    c10_pa: float | None = None
    c01_pa: float | None = None
    c20_pa: float | None = None
    c30_pa: float | None = None
    mu_pa: float | None = None
    alpha: float | None = None

    def __post_init__(self) -> None:
        expected = {
            HyperelasticFamily.NEO_HOOKEAN: {"c10_pa"},
            HyperelasticFamily.MOONEY_RIVLIN: {"c10_pa", "c01_pa"},
            HyperelasticFamily.YEOH: {"c10_pa", "c20_pa", "c30_pa"},
            HyperelasticFamily.OGDEN_1: {"mu_pa", "alpha"},
        }[self.family]
        actual = {
            name
            for name in ("c10_pa", "c01_pa", "c20_pa", "c30_pa", "mu_pa", "alpha")
            if getattr(self, name) is not None
        }
        if actual != expected:
            raise InvalidNeutralMaterial(
                f"{self.family.value} requires exactly {sorted(expected)} parameters"
            )
        for name in actual:
            value = cast(float, getattr(self, name))
            _finite(name, value)
        if self.c10_pa is not None and self.c10_pa <= 0:
            raise InvalidNeutralMaterial("c10_pa must be greater than zero")
        if self.mu_pa is not None and self.mu_pa <= 0:
            raise InvalidNeutralMaterial("mu_pa must be greater than zero")
        if self.alpha is not None and self.alpha <= 0:
            raise InvalidNeutralMaterial("alpha must be greater than zero")

    def canonical(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "parameters": {
                name: {"value": getattr(self, name), "unit": "1" if name == "alpha" else "Pa"}
                for name in ("c10_pa", "c01_pa", "c20_pa", "c30_pa", "mu_pa", "alpha")
                if getattr(self, name) is not None
            },
        }


@dataclass(frozen=True, slots=True)
class NeutralCandidateSelection:
    calibration_run_id: UUID
    candidate_id: UUID
    candidate_sha256: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    reason: str
    objective_total: float
    calibration_normalized_rmse: float
    holdout_normalized_rmse: float | None
    stability_status: str
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("calibration_run_id", "candidate_id", "diagnostics_artifact_id"):
            _uuid(name, cast(UUID, getattr(self, name)))
        _sha("candidate_sha256", self.candidate_sha256)
        _sha("diagnostics_sha256", self.diagnostics_sha256)
        _text("selection reason", self.reason)
        _text("stability_status", self.stability_status, 120)
        _finite("objective_total", self.objective_total)
        _finite("calibration_normalized_rmse", self.calibration_normalized_rmse)
        if self.holdout_normalized_rmse is not None:
            _finite("holdout_normalized_rmse", self.holdout_normalized_rmse)
        if len(self.warnings) > 64 or any(
            not item or item != item.strip() for item in self.warnings
        ):
            raise InvalidNeutralMaterial("selection warnings must be trimmed and bounded")

    def canonical(self) -> dict[str, object]:
        return {
            "calibration_run_id": str(self.calibration_run_id),
            "candidate_id": str(self.candidate_id),
            "candidate_sha256": self.candidate_sha256,
            "diagnostics_artifact_id": str(self.diagnostics_artifact_id),
            "diagnostics_sha256": self.diagnostics_sha256,
            "reason": self.reason,
            "objective_total": self.objective_total,
            "calibration_normalized_rmse": self.calibration_normalized_rmse,
            "holdout_normalized_rmse": self.holdout_normalized_rmse,
            "stability_status": self.stability_status,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class NeutralHyperelasticIR:
    model: RevisionReference
    schema_id: str
    schema_version: str
    model_schema_digest: str
    parameters: NeutralHyperelasticParameters
    density_kg_per_m3: float
    volumetric_response: str
    maturity: ModelMaturity = ModelMaturity.REFERENCE
    non_production: bool = True

    def __post_init__(self) -> None:
        _text("schema_id", self.schema_id, 255)
        _text("schema_version", self.schema_version, 64)
        _sha("model_schema_digest", self.model_schema_digest)
        _finite("density_kg_per_m3", self.density_kg_per_m3, positive=True)
        if self.volumetric_response != "incompressible":
            raise InvalidNeutralMaterial("T-56 reference hyperelastic IR must be incompressible")
        if self.maturity is not ModelMaturity.REFERENCE or not self.non_production:
            raise InvalidNeutralMaterial("T-56 output must remain a non-production reference model")

    def canonical(self) -> dict[str, object]:
        return {
            "model": self.model.canonical(),
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "model_schema_digest": self.model_schema_digest,
            "constitutive_model": self.parameters.canonical(),
            "density": {"value": self.density_kg_per_m3, "unit": "kg/m3"},
            "volumetric_response": self.volumetric_response,
            "maturity": self.maturity.value,
            "non_production": self.non_production,
        }


@dataclass(frozen=True, slots=True)
class NeutralMaterialDocument:
    document_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: str
    material: RevisionReference
    material_state: RevisionReference
    property_set: RevisionReference
    calibration_plan: RevisionReference
    scientific_profile: RevisionReference
    mapping_profile: OptionalRevisionEvidence
    processing_recipe: OptionalRevisionEvidence
    source_datasets: tuple[NeutralDatasetSource, ...]
    curves: tuple[NeutralCurve, ...]
    selection: NeutralCandidateSelection
    material_model_ir: NeutralHyperelasticIR
    applicable_strain_min: float
    applicable_strain_max: float
    validation_status: str
    document_type: str = NEUTRAL_MATERIAL_DOCUMENT_TYPE
    schema_version: str = NEUTRAL_MATERIAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("document_id", "organization_id", "project_id"):
            _uuid(name, cast(UUID, getattr(self, name)))
        _text("classification", self.classification, 64)
        if self.document_type != NEUTRAL_MATERIAL_DOCUMENT_TYPE:
            raise InvalidNeutralMaterial("document_type must be cmp.neutral-material")
        if self.schema_version != NEUTRAL_MATERIAL_SCHEMA_VERSION:
            raise InvalidNeutralMaterial("unsupported neutral material schema_version")
        if not self.source_datasets or len(self.source_datasets) > 24:
            raise InvalidNeutralMaterial("source_datasets must contain 1..24 exact inputs")
        revisions = tuple(item.dataset.revision_id for item in self.source_datasets)
        if len(revisions) != len(set(revisions)):
            raise InvalidNeutralMaterial("source Dataset revisions must be unique")
        source_revisions = set(revisions)
        if not self.curves or any(
            item.dataset_revision_id not in source_revisions for item in self.curves
        ):
            raise InvalidNeutralMaterial(
                "every curve must belong to an exact source Dataset revision"
            )
        stages = {item.stage for item in self.curves}
        if not {CurveStage.NORMALIZED, CurveStage.FITTED, CurveStage.RESIDUAL}.issubset(stages):
            raise InvalidNeutralMaterial(
                "normalized, fitted, and residual curve stages are required"
            )
        _finite("applicable_strain_min", self.applicable_strain_min)
        _finite("applicable_strain_max", self.applicable_strain_max)
        if (
            self.applicable_strain_min < 0
            or self.applicable_strain_max <= self.applicable_strain_min
        ):
            raise InvalidNeutralMaterial(
                "applicable strain interval must be increasing and non-negative"
            )
        _text("validation_status", self.validation_status, 160)

    def payload(self) -> dict[str, object]:
        return {
            "document_type": self.document_type,
            "schema_version": self.schema_version,
            "document_id": str(self.document_id),
            "scope": {
                "organization_id": str(self.organization_id),
                "project_id": str(self.project_id),
                "classification": self.classification,
            },
            "sources": {
                "material": self.material.canonical(),
                "material_state": self.material_state.canonical(),
                "property_set": self.property_set.canonical(),
                "calibration_plan": self.calibration_plan.canonical(),
                "scientific_profile": self.scientific_profile.canonical(),
                "mapping_profile": self.mapping_profile.canonical(),
                "processing_recipe": self.processing_recipe.canonical(),
                "datasets": [item.canonical() for item in self.source_datasets],
            },
            "curve_stages": [item.canonical() for item in self.curves],
            "candidate_selection": self.selection.canonical(),
            "material_model_ir": self.material_model_ir.canonical(),
            "applicability": {
                "engineering_strain": {
                    "minimum": self.applicable_strain_min,
                    "maximum": self.applicable_strain_max,
                    "unit": "1",
                }
            },
            "validation": {"status": self.validation_status},
        }

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(_canonical_bytes(self.payload())).hexdigest()

    def canonical(self) -> dict[str, object]:
        return {**self.payload(), "content_sha256": self.content_sha256}

    def to_json_bytes(self) -> bytes:
        return _canonical_bytes(self.canonical())


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def neutral_material_from_json_bytes(value: bytes) -> NeutralMaterialDocument:
    """Parse a canonical document and reject hidden defaults or a mismatched digest."""

    try:
        raw = cast(dict[str, Any], json.loads(value.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidNeutralMaterial("neutral material must be UTF-8 JSON") from error
    if not isinstance(raw, dict):
        raise InvalidNeutralMaterial("neutral material root must be an object")
    declared_digest = raw.pop("content_sha256", None)
    if not isinstance(declared_digest, str):
        raise InvalidNeutralMaterial("content_sha256 is required")
    actual_digest = hashlib.sha256(_canonical_bytes(raw)).hexdigest()
    if declared_digest != actual_digest:
        raise InvalidNeutralMaterial("content_sha256 does not match the canonical payload")
    try:
        document = _document_from_mapping(raw)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, InvalidNeutralMaterial):
            raise
        raise InvalidNeutralMaterial("neutral material structure is invalid") from error
    if document.content_sha256 != declared_digest:
        raise InvalidNeutralMaterial("neutral material round-trip changed canonical content")
    return document


def _reference(value: dict[str, Any]) -> RevisionReference:
    return RevisionReference(UUID(value["id"]), UUID(value["revision_id"]))


def _optional(value: dict[str, Any]) -> OptionalRevisionEvidence:
    reference = value.get("reference")
    return OptionalRevisionEvidence(
        EvidenceStatus(value["status"]),
        str(value["reason"]),
        _reference(reference) if isinstance(reference, dict) else None,
    )


def _parameters(value: dict[str, Any]) -> NeutralHyperelasticParameters:
    family = HyperelasticFamily(value["family"])
    raw_parameters = value["parameters"]
    allowed = {"c10_pa", "c01_pa", "c20_pa", "c30_pa", "mu_pa", "alpha"}
    if not isinstance(raw_parameters, dict) or set(raw_parameters) - allowed:
        raise InvalidNeutralMaterial("constitutive parameters contain unsupported fields")
    parsed: dict[str, float] = {}
    for name, item in raw_parameters.items():
        expected_unit = "1" if name == "alpha" else "Pa"
        if (
            not isinstance(item, dict)
            or set(item) != {"value", "unit"}
            or item["unit"] != expected_unit
        ):
            raise InvalidNeutralMaterial(f"{name} requires explicit unit {expected_unit}")
        parsed[name] = float(item["value"])
    return NeutralHyperelasticParameters(family=family, **parsed)


def _document_from_mapping(raw: dict[str, Any]) -> NeutralMaterialDocument:
    required = {
        "document_type",
        "schema_version",
        "document_id",
        "scope",
        "sources",
        "curve_stages",
        "candidate_selection",
        "material_model_ir",
        "applicability",
        "validation",
    }
    if set(raw) != required:
        raise InvalidNeutralMaterial("neutral material root has missing or unsupported fields")
    scope = raw["scope"]
    sources = raw["sources"]
    selection = raw["candidate_selection"]
    ir = raw["material_model_ir"]
    strain = raw["applicability"]["engineering_strain"]
    datasets = tuple(
        NeutralDatasetSource(
            dataset=_reference(item["dataset"]),
            role=OgdenCalibrationRole(item["role"]),
            test_mode=OgdenTestMode(item["test_mode"]),
            normalized_artifact_id=UUID(item["normalized_artifact"]["artifact_id"]),
            normalized_artifact_sha256=str(item["normalized_artifact"]["sha256"]),
        )
        for item in sources["datasets"]
    )
    curves = tuple(
        NeutralCurve(
            stage=CurveStage(item["stage"]),
            dataset_revision_id=UUID(item["dataset_revision_id"]),
            test_mode=OgdenTestMode(item["test_mode"]),
            x_quantity=str(item["x_quantity"]),
            x_unit=str(item["x_unit"]),
            y_quantity=str(item["y_quantity"]),
            y_unit=str(item["y_unit"]),
            x=tuple(float(number) for number in item["x"]),
            y=tuple(float(number) for number in item["y"]),
        )
        for item in raw["curve_stages"]
    )
    parameters = _parameters(ir["constitutive_model"])
    return NeutralMaterialDocument(
        document_id=UUID(raw["document_id"]),
        organization_id=UUID(scope["organization_id"]),
        project_id=UUID(scope["project_id"]),
        classification=str(scope["classification"]),
        material=_reference(sources["material"]),
        material_state=_reference(sources["material_state"]),
        property_set=_reference(sources["property_set"]),
        calibration_plan=_reference(sources["calibration_plan"]),
        scientific_profile=_reference(sources["scientific_profile"]),
        mapping_profile=_optional(sources["mapping_profile"]),
        processing_recipe=_optional(sources["processing_recipe"]),
        source_datasets=datasets,
        curves=curves,
        selection=NeutralCandidateSelection(
            calibration_run_id=UUID(selection["calibration_run_id"]),
            candidate_id=UUID(selection["candidate_id"]),
            candidate_sha256=str(selection["candidate_sha256"]),
            diagnostics_artifact_id=UUID(selection["diagnostics_artifact_id"]),
            diagnostics_sha256=str(selection["diagnostics_sha256"]),
            reason=str(selection["reason"]),
            objective_total=float(selection["objective_total"]),
            calibration_normalized_rmse=float(selection["calibration_normalized_rmse"]),
            holdout_normalized_rmse=(
                float(selection["holdout_normalized_rmse"])
                if selection["holdout_normalized_rmse"] is not None
                else None
            ),
            stability_status=str(selection["stability_status"]),
            warnings=tuple(str(item) for item in selection["warnings"]),
        ),
        material_model_ir=NeutralHyperelasticIR(
            model=_reference(ir["model"]),
            schema_id=str(ir["schema_id"]),
            schema_version=str(ir["schema_version"]),
            model_schema_digest=str(ir["model_schema_digest"]),
            parameters=parameters,
            density_kg_per_m3=float(ir["density"]["value"]),
            volumetric_response=str(ir["volumetric_response"]),
            maturity=ModelMaturity(ir["maturity"]),
            non_production=bool(ir["non_production"]),
        ),
        applicable_strain_min=float(strain["minimum"]),
        applicable_strain_max=float(strain["maximum"]),
        validation_status=str(raw["validation"]["status"]),
        document_type=str(raw["document_type"]),
        schema_version=str(raw["schema_version"]),
    )
