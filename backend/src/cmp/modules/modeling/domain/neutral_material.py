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
from itertools import pairwise
from typing import Any, cast
from uuid import UUID

from cmp.modules.modeling.domain.fit_decision_evidence import (
    FitDecisionEvidence,
    fit_decision_evidence_from_canonical,
)
from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily

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
    PROCESSED = "processed"
    FITTED = "fitted"
    EXTRAPOLATED = "extrapolated"
    RESIDUAL = "residual"


HYPERELASTIC_CURVE_STAGES = (
    CurveStage.NORMALIZED,
    CurveStage.FITTED,
    CurveStage.RESIDUAL,
)


class NeutralDatasetRole(StrEnum):
    CALIBRATION = "calibration"
    HOLDOUT = "holdout"
    PROCESSING_INPUT = "processing_input"


class NeutralDatasetKind(StrEnum):
    GOVERNED_DATASET = "governed_dataset"
    TEST_DATA_DOCUMENT = "test_data_document"
    SHEAR_RELAXATION_DATASET = "shear_relaxation_dataset"


class NeutralTestMode(StrEnum):
    UNIAXIAL_TENSION = "uniaxial_tension"
    PLANAR_TENSION = "planar_tension"
    BIAXIAL_TENSION = "biaxial_tension"
    STRESS_RELAXATION = "stress_relaxation"
    DMA_FREQUENCY = "dma_frequency"


class NeutralModelFamily(StrEnum):
    HYPERELASTIC = "hyperelastic"
    ISOTROPIC_TABULATED_PLASTICITY = "isotropic_tabulated_plasticity"
    GENERALIZED_MAXWELL = "generalized_maxwell"


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
    role: NeutralDatasetRole
    test_mode: NeutralTestMode
    normalized_artifact_id: UUID
    normalized_artifact_sha256: str
    source_kind: NeutralDatasetKind = NeutralDatasetKind.GOVERNED_DATASET

    def __post_init__(self) -> None:
        _uuid("normalized_artifact_id", self.normalized_artifact_id)
        _sha("normalized_artifact_sha256", self.normalized_artifact_sha256)

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {
            "dataset": self.dataset.canonical(),
            "role": self.role.value,
            "test_mode": self.test_mode.value,
            "normalized_artifact": {
                "artifact_id": str(self.normalized_artifact_id),
                "sha256": self.normalized_artifact_sha256,
            },
        }
        # Omit the original governed Dataset discriminator so immutable 1.0.0
        # hyperelastic documents retain their exact canonical bytes.
        if self.source_kind is not NeutralDatasetKind.GOVERNED_DATASET:
            result["source_kind"] = self.source_kind.value
        return result


@dataclass(frozen=True, slots=True)
class NeutralCurve:
    stage: CurveStage
    dataset_revision_id: UUID
    test_mode: NeutralTestMode
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
class NeutralArtifactReference:
    artifact_id: UUID
    sha256: str
    schema_ref: str
    point_count: int

    def __post_init__(self) -> None:
        _uuid("artifact_id", self.artifact_id)
        _sha("artifact sha256", self.sha256)
        _text("artifact schema_ref", self.schema_ref, 255)
        if not 1 <= self.point_count <= 50_000:
            raise InvalidNeutralMaterial("artifact point_count must be within 1..50000")

    def canonical(self) -> dict[str, object]:
        return {
            "artifact_id": str(self.artifact_id),
            "sha256": self.sha256,
            "schema_ref": self.schema_ref,
            "point_count": self.point_count,
        }


@dataclass(frozen=True, slots=True)
class NeutralPronyTerm:
    ordinal: int
    g_ratio: float
    k_ratio: float
    relaxation_time_s: float

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise InvalidNeutralMaterial("Prony ordinal must be positive")
        for name, value in (("g_ratio", self.g_ratio), ("k_ratio", self.k_ratio)):
            if not math.isfinite(value) or not 0 <= value < 1:
                raise InvalidNeutralMaterial(f"{name} must be finite within [0,1)")
        _finite("relaxation_time_s", self.relaxation_time_s, positive=True)

    def canonical(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "g_ratio": self.g_ratio,
            "k_ratio": self.k_ratio,
            "relaxation_time": {"value": self.relaxation_time_s, "unit": "s"},
        }


@dataclass(frozen=True, slots=True)
class NeutralPronyOverlay:
    status: EvidenceStatus
    reason: str
    terms: tuple[NeutralPronyTerm, ...] = ()
    source_model: RevisionReference | None = None

    def __post_init__(self) -> None:
        _text("Prony overlay reason", self.reason, 500)
        exact = self.status is EvidenceStatus.EXACT_REVISION
        if exact != (self.source_model is not None):
            raise InvalidNeutralMaterial(
                "exact Prony overlay requires a source model; not_applicable forbids one"
            )
        if exact:
            _validate_prony_terms(self.terms)
        elif self.terms:
            raise InvalidNeutralMaterial("not_applicable Prony overlay forbids terms")

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {"status": self.status.value, "reason": self.reason}
        if self.source_model is not None:
            result["source_model"] = self.source_model.canonical()
            result["terms"] = [term.canonical() for term in self.terms]
        return result


def _validate_prony_terms(terms: tuple[NeutralPronyTerm, ...]) -> None:
    if not 1 <= len(terms) <= 10:
        raise InvalidNeutralMaterial("Prony term count must be within 1..10")
    if tuple(term.ordinal for term in terms) != tuple(range(1, len(terms) + 1)):
        raise InvalidNeutralMaterial("Prony ordinals must be contiguous from one")
    times = tuple(term.relaxation_time_s for term in terms)
    if any(right <= left for left, right in pairwise(times)):
        raise InvalidNeutralMaterial("Prony relaxation times must be strictly increasing")
    if sum(term.g_ratio for term in terms) >= 1 or sum(term.k_ratio for term in terms) >= 1:
        raise InvalidNeutralMaterial("Prony shear and bulk ratio sums must remain below one")


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
class NeutralProcessingSelection:
    processing_output: RevisionReference
    processing_output_sha256: str
    reason: str
    selected_series: str
    candidate_families: tuple[str, ...]
    primary_family: str
    secondary_family: str | None
    primary_weight: float | None
    fit_decision: FitDecisionEvidence | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _sha("processing_output_sha256", self.processing_output_sha256)
        _text("processing selection reason", self.reason)
        _text("selected_series", self.selected_series, 160)
        if not 2 <= len(self.candidate_families) <= 4 or len(set(self.candidate_families)) != len(
            self.candidate_families
        ):
            raise InvalidNeutralMaterial("processing candidate families must be 2..4 unique IDs")
        if self.primary_family not in self.candidate_families or (
            self.secondary_family is not None
            and self.secondary_family not in self.candidate_families
        ):
            raise InvalidNeutralMaterial("processing selected families must be candidates")
        if self.primary_weight is not None and (
            not math.isfinite(self.primary_weight) or not 0 <= self.primary_weight <= 1
        ):
            raise InvalidNeutralMaterial("processing primary_weight must be within [0,1]")
        if (self.secondary_family is None) != (self.primary_weight is None):
            raise InvalidNeutralMaterial(
                "processing secondary family and weight must both be present only for a blend"
            )
        if self.fit_decision is not None and (
            self.fit_decision.primary_law != self.primary_family
            or self.fit_decision.secondary_law != self.secondary_family
            or self.fit_decision.primary_weight != self.primary_weight
        ):
            raise InvalidNeutralMaterial(
                "processing fit evidence must match the Neutral selection"
            )
        if len(self.warnings) > 64 or any(
            not value or value != value.strip() for value in self.warnings
        ):
            raise InvalidNeutralMaterial("processing warnings must be trimmed and bounded")

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {
            "kind": "processing_output_selection",
            "processing_output": self.processing_output.canonical(),
            "processing_output_sha256": self.processing_output_sha256,
            "reason": self.reason,
            "selected_series": self.selected_series,
            "candidate_families": list(self.candidate_families),
            "primary_family": self.primary_family,
            "secondary_family": self.secondary_family,
            "primary_weight": self.primary_weight,
            "warnings": list(self.warnings),
        }
        if self.fit_decision is not None:
            result["fit_decision"] = self.fit_decision.canonical()
            result["fit_decision_digest"] = self.fit_decision.digest
        return result


@dataclass(frozen=True, slots=True)
class NeutralPronyProcessingSelection:
    processing_output: RevisionReference
    processing_output_sha256: str
    reason: str
    selected_series: str
    selection_mode: str
    selected_term_count: int
    normalized_rmse: float
    bic: float
    fitted_instantaneous_shear_modulus_pa: float
    catalog_instantaneous_shear_modulus_pa: float
    instantaneous_modulus_relative_mismatch: float
    acknowledged_maximum_relative_mismatch: float
    fit_decision: FitDecisionEvidence | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _sha("processing_output_sha256", self.processing_output_sha256)
        _text("Prony processing selection reason", self.reason)
        _text("selected_series", self.selected_series, 160)
        if self.selection_mode not in {"automatic_bic", "manual"}:
            raise InvalidNeutralMaterial("Prony selection mode is unsupported")
        if not 1 <= self.selected_term_count <= 10:
            raise InvalidNeutralMaterial("selected Prony term count must be within 1..10")
        for name, value in (
            ("normalized_rmse", self.normalized_rmse),
            (
                "instantaneous_modulus_relative_mismatch",
                self.instantaneous_modulus_relative_mismatch,
            ),
            (
                "acknowledged_maximum_relative_mismatch",
                self.acknowledged_maximum_relative_mismatch,
            ),
        ):
            _finite(name, value)
            if value < 0:
                raise InvalidNeutralMaterial(f"{name} must be non-negative")
        _finite("bic", self.bic)
        _finite(
            "fitted_instantaneous_shear_modulus_pa",
            self.fitted_instantaneous_shear_modulus_pa,
            positive=True,
        )
        _finite(
            "catalog_instantaneous_shear_modulus_pa",
            self.catalog_instantaneous_shear_modulus_pa,
            positive=True,
        )
        if self.instantaneous_modulus_relative_mismatch > (
            self.acknowledged_maximum_relative_mismatch
        ):
            raise InvalidNeutralMaterial("Prony modulus mismatch exceeds the acknowledged maximum")
        if self.fit_decision is not None and (
            self.fit_decision.primary_law != "generalized_maxwell"
            or self.fit_decision.actual_term_count != self.selected_term_count
            or self.fit_decision.requested_term_policy != self.selection_mode
            or self.fit_decision.metric_definition != "normalized_rmse"
            or self.fit_decision.metric_value != self.normalized_rmse
        ):
            raise InvalidNeutralMaterial(
                "Prony fit evidence must match the Neutral selection"
            )
        if len(self.warnings) > 64 or any(
            not value or value != value.strip() for value in self.warnings
        ):
            raise InvalidNeutralMaterial("Prony processing warnings must be trimmed and bounded")

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {
            "kind": "prony_processing_output_selection",
            "processing_output": self.processing_output.canonical(),
            "processing_output_sha256": self.processing_output_sha256,
            "reason": self.reason,
            "selected_series": self.selected_series,
            "selection_mode": self.selection_mode,
            "selected_term_count": self.selected_term_count,
            "normalized_rmse": self.normalized_rmse,
            "bic": self.bic,
            "fitted_instantaneous_shear_modulus_pa": (self.fitted_instantaneous_shear_modulus_pa),
            "catalog_instantaneous_shear_modulus_pa": (self.catalog_instantaneous_shear_modulus_pa),
            "instantaneous_modulus_relative_mismatch": (
                self.instantaneous_modulus_relative_mismatch
            ),
            "acknowledged_maximum_relative_mismatch": (self.acknowledged_maximum_relative_mismatch),
            "warnings": list(self.warnings),
        }
        if self.fit_decision is not None:
            result["fit_decision"] = self.fit_decision.canonical()
            result["fit_decision_digest"] = self.fit_decision.digest
        return result


@dataclass(frozen=True, slots=True)
class NeutralHyperelasticIR:
    model: RevisionReference
    schema_id: str
    schema_version: str
    model_schema_digest: str
    parameters: NeutralHyperelasticParameters
    density_kg_per_m3: float
    volumetric_response: str
    prony_overlay: NeutralPronyOverlay | None = None
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

    @property
    def family(self) -> NeutralModelFamily:
        return NeutralModelFamily.HYPERELASTIC

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {
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
        if self.prony_overlay is not None:
            result["model_family"] = self.family.value
            result["prony_overlay"] = self.prony_overlay.canonical()
        return result


@dataclass(frozen=True, slots=True)
class NeutralElastoplasticIR:
    model: RevisionReference
    schema_id: str
    schema_version: str
    model_schema_digest: str
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    initial_yield_stress_pa: float
    hardening_curve: NeutralArtifactReference
    candidate_families: tuple[str, ...]
    primary_family: str
    secondary_family: str | None
    primary_weight: float | None
    characterized_max_true_plastic_strain: float
    extension_max_true_plastic_strain: float
    extrapolation_policy: str
    approximation_acknowledged: bool
    fit_decision: FitDecisionEvidence | None = None
    maturity: ModelMaturity = ModelMaturity.REFERENCE
    non_production: bool = True

    def __post_init__(self) -> None:
        for name in ("schema_id", "schema_version", "extrapolation_policy"):
            _text(name, cast(str, getattr(self, name)), 255)
        _sha("model_schema_digest", self.model_schema_digest)
        for name, value in (
            ("density_kg_per_m3", self.density_kg_per_m3),
            ("youngs_modulus_pa", self.youngs_modulus_pa),
            ("initial_yield_stress_pa", self.initial_yield_stress_pa),
        ):
            _finite(name, value, positive=True)
        if not math.isfinite(self.poisson_ratio) or not -1 < self.poisson_ratio < 0.5:
            raise InvalidNeutralMaterial("poisson_ratio must remain within (-1,0.5)")
        if not 2 <= len(self.candidate_families) <= 4 or len(set(self.candidate_families)) != len(
            self.candidate_families
        ):
            raise InvalidNeutralMaterial("metal candidate families must contain 2..4 unique IDs")
        if self.primary_family not in self.candidate_families or (
            self.secondary_family is not None
            and self.secondary_family not in self.candidate_families
        ):
            raise InvalidNeutralMaterial("selected hardening families must be candidates")
        if self.primary_weight is not None and (
            not math.isfinite(self.primary_weight) or not 0 <= self.primary_weight <= 1
        ):
            raise InvalidNeutralMaterial("hardening primary_weight must be within [0,1]")
        if (self.secondary_family is None) != (self.primary_weight is None):
            raise InvalidNeutralMaterial(
                "hardening secondary family and weight must both be present only for a blend"
            )
        if self.fit_decision is not None and (
            self.fit_decision.primary_law != self.primary_family
            or self.fit_decision.secondary_law != self.secondary_family
            or self.fit_decision.primary_weight != self.primary_weight
        ):
            raise InvalidNeutralMaterial("fit evidence must match the hardening IR selection")
        if not (
            0 < self.characterized_max_true_plastic_strain < self.extension_max_true_plastic_strain
        ):
            raise InvalidNeutralMaterial("metal characterized and extension domains are invalid")
        if not self.approximation_acknowledged:
            raise InvalidNeutralMaterial("metal extrapolation approximation must be acknowledged")
        if self.maturity is not ModelMaturity.REFERENCE or not self.non_production:
            raise InvalidNeutralMaterial("T-63 metal output must remain a non-production reference")

    @property
    def family(self) -> NeutralModelFamily:
        return NeutralModelFamily.ISOTROPIC_TABULATED_PLASTICITY

    def canonical(self) -> dict[str, object]:
        selection: dict[str, object] = {
            "candidate_families": list(self.candidate_families),
            "primary_family": self.primary_family,
            "secondary_family": self.secondary_family,
            "primary_weight": self.primary_weight,
        }
        if self.fit_decision is not None:
            selection["fit_decision"] = self.fit_decision.canonical()
            selection["fit_decision_digest"] = self.fit_decision.digest
        return {
            "model": self.model.canonical(),
            "model_family": self.family.value,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "model_schema_digest": self.model_schema_digest,
            "constitutive_model": {
                "family": self.family.value,
                "parameters": {
                    "youngs_modulus": {"value": self.youngs_modulus_pa, "unit": "Pa"},
                    "poisson_ratio": {"value": self.poisson_ratio, "unit": "1"},
                    "initial_yield_stress": {
                        "value": self.initial_yield_stress_pa,
                        "unit": "Pa",
                    },
                },
                "hardening_curve": self.hardening_curve.canonical(),
                "selection": selection,
                "domain": {
                    "characterized_maximum_true_plastic_strain": (
                        self.characterized_max_true_plastic_strain
                    ),
                    "extension_maximum_true_plastic_strain": self.extension_max_true_plastic_strain,
                    "unit": "1",
                },
                "extrapolation": {
                    "policy": self.extrapolation_policy,
                    "approximation_acknowledged": self.approximation_acknowledged,
                },
            },
            "density": {"value": self.density_kg_per_m3, "unit": "kg/m3"},
            "maturity": self.maturity.value,
            "non_production": self.non_production,
        }


@dataclass(frozen=True, slots=True)
class NeutralLinearViscoelasticIR:
    model: RevisionReference
    schema_id: str
    schema_version: str
    model_schema_digest: str
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    bulk_relaxation_status: str
    terms: tuple[NeutralPronyTerm, ...]
    reference_temperature_k: float
    fit_decision: FitDecisionEvidence | None = None
    maturity: ModelMaturity = ModelMaturity.REFERENCE
    non_production: bool = True

    def __post_init__(self) -> None:
        for name in ("schema_id", "schema_version", "bulk_relaxation_status"):
            _text(name, cast(str, getattr(self, name)), 255)
        _sha("model_schema_digest", self.model_schema_digest)
        _finite("density_kg_per_m3", self.density_kg_per_m3, positive=True)
        _finite("youngs_modulus_pa", self.youngs_modulus_pa, positive=True)
        _finite("reference_temperature_k", self.reference_temperature_k, positive=True)
        if not math.isfinite(self.poisson_ratio) or not -1 < self.poisson_ratio < 0.5:
            raise InvalidNeutralMaterial("poisson_ratio must remain within (-1,0.5)")
        if self.bulk_relaxation_status not in {"characterized", "not_characterized"}:
            raise InvalidNeutralMaterial("bulk_relaxation_status is unsupported")
        _validate_prony_terms(self.terms)
        bulk_sum = sum(term.k_ratio for term in self.terms)
        if self.bulk_relaxation_status == "not_characterized" and bulk_sum != 0:
            raise InvalidNeutralMaterial("uncharacterized bulk relaxation requires zero k ratios")
        if self.bulk_relaxation_status == "characterized" and bulk_sum == 0:
            raise InvalidNeutralMaterial("characterized bulk relaxation requires positive k ratios")
        if self.maturity is not ModelMaturity.REFERENCE or not self.non_production:
            raise InvalidNeutralMaterial(
                "T-63 polymer output must remain a non-production reference"
            )
        if self.fit_decision is not None and (
            self.fit_decision.primary_law != "generalized_maxwell"
            or self.fit_decision.actual_term_count != len(self.terms)
        ):
            raise InvalidNeutralMaterial(
                "fit evidence must match the generalized-Maxwell IR terms"
            )

    @property
    def family(self) -> NeutralModelFamily:
        return NeutralModelFamily.GENERALIZED_MAXWELL

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {
            "model": self.model.canonical(),
            "model_family": self.family.value,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "model_schema_digest": self.model_schema_digest,
            "constitutive_model": {
                "family": self.family.value,
                "elastic_moduli_convention": "instantaneous",
                "parameters": {
                    "youngs_modulus": {"value": self.youngs_modulus_pa, "unit": "Pa"},
                    "poisson_ratio": {"value": self.poisson_ratio, "unit": "1"},
                },
                "bulk_relaxation_status": self.bulk_relaxation_status,
                "prony_terms": [term.canonical() for term in self.terms],
            },
            "density": {"value": self.density_kg_per_m3, "unit": "kg/m3"},
            "reference_temperature": {"value": self.reference_temperature_k, "unit": "K"},
            "maturity": self.maturity.value,
            "non_production": self.non_production,
        }
        if self.fit_decision is not None:
            result["fit_decision"] = self.fit_decision.canonical()
            result["fit_decision_digest"] = self.fit_decision.digest
        return result


@dataclass(frozen=True, slots=True)
class NeutralMaterialDocument:
    document_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: str
    material: RevisionReference
    material_state: RevisionReference
    property_set: RevisionReference
    calibration_plan: RevisionReference | OptionalRevisionEvidence
    scientific_profile: RevisionReference | OptionalRevisionEvidence
    mapping_profile: OptionalRevisionEvidence
    processing_recipe: OptionalRevisionEvidence
    source_datasets: tuple[NeutralDatasetSource, ...]
    curves: tuple[NeutralCurve, ...]
    selection: (
        NeutralCandidateSelection | NeutralProcessingSelection | NeutralPronyProcessingSelection
    )
    material_model_ir: NeutralHyperelasticIR | NeutralElastoplasticIR | NeutralLinearViscoelasticIR
    applicable_strain_min: float | None
    applicable_strain_max: float | None
    validation_status: str
    applicable_time_min_s: float | None = None
    applicable_time_max_s: float | None = None
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
        family = self.material_model_ir.family
        expected_source_kind = {
            NeutralModelFamily.HYPERELASTIC: NeutralDatasetKind.GOVERNED_DATASET,
            NeutralModelFamily.ISOTROPIC_TABULATED_PLASTICITY: (
                NeutralDatasetKind.TEST_DATA_DOCUMENT
            ),
            NeutralModelFamily.GENERALIZED_MAXWELL: (
                NeutralDatasetKind.TEST_DATA_DOCUMENT
                if isinstance(self.selection, NeutralPronyProcessingSelection)
                else NeutralDatasetKind.SHEAR_RELAXATION_DATASET
            ),
        }[family]
        if any(item.source_kind is not expected_source_kind for item in self.source_datasets):
            raise InvalidNeutralMaterial(
                f"{family.value} requires {expected_source_kind.value} source revisions"
            )
        if family is NeutralModelFamily.ISOTROPIC_TABULATED_PLASTICITY:
            if not isinstance(self.selection, NeutralProcessingSelection):
                raise InvalidNeutralMaterial("metal Neutral IR requires a Processing selection")
            if not isinstance(self.material_model_ir, NeutralElastoplasticIR):
                raise InvalidNeutralMaterial("metal family requires an elastoplastic IR")
            if self.selection.fit_decision != self.material_model_ir.fit_decision:
                raise InvalidNeutralMaterial(
                    "metal Neutral selection and IR must retain the same fit evidence"
                )
        elif family is NeutralModelFamily.GENERALIZED_MAXWELL:
            if not isinstance(
                self.selection,
                (NeutralCandidateSelection, NeutralPronyProcessingSelection),
            ):
                raise InvalidNeutralMaterial(
                    "generalized Maxwell Neutral IR requires Candidate or Processing selection"
                )
            if (
                isinstance(self.selection, NeutralPronyProcessingSelection)
                and (
                    not isinstance(self.material_model_ir, NeutralLinearViscoelasticIR)
                    or self.selection.fit_decision != self.material_model_ir.fit_decision
                )
            ):
                raise InvalidNeutralMaterial(
                    "polymer Neutral selection and IR must retain the same fit evidence"
                )
        elif not isinstance(self.selection, NeutralCandidateSelection):
            raise InvalidNeutralMaterial(
                f"{family.value} Neutral IR requires a calibration Candidate selection"
            )
        stages = {item.stage for item in self.curves}
        required_stages = (
            {
                CurveStage.NORMALIZED,
                CurveStage.PROCESSED,
                CurveStage.FITTED,
                CurveStage.EXTRAPOLATED,
            }
            if family is NeutralModelFamily.ISOTROPIC_TABULATED_PLASTICITY
            else {CurveStage.NORMALIZED, CurveStage.FITTED, CurveStage.RESIDUAL}
        )
        if not required_stages.issubset(stages):
            if family is not NeutralModelFamily.ISOTROPIC_TABULATED_PLASTICITY:
                raise InvalidNeutralMaterial(
                    "normalized, fitted, and residual curve stages are required"
                )
            raise InvalidNeutralMaterial(f"{family.value} curve stages omit required values")
        if family is NeutralModelFamily.GENERALIZED_MAXWELL:
            if self.applicable_strain_min is not None or self.applicable_strain_max is not None:
                raise InvalidNeutralMaterial(
                    "generalized Maxwell applicability uses time, not strain"
                )
            if self.applicable_time_min_s is None or self.applicable_time_max_s is None:
                raise InvalidNeutralMaterial("generalized Maxwell time applicability is required")
            _finite("applicable_time_min_s", self.applicable_time_min_s)
            _finite("applicable_time_max_s", self.applicable_time_max_s)
            if (
                self.applicable_time_min_s < 0
                or self.applicable_time_max_s <= self.applicable_time_min_s
            ):
                raise InvalidNeutralMaterial(
                    "applicable time interval must be increasing and non-negative"
                )
        else:
            if self.applicable_time_min_s is not None or self.applicable_time_max_s is not None:
                raise InvalidNeutralMaterial("strain-based families forbid time applicability")
            if self.applicable_strain_min is None or self.applicable_strain_max is None:
                raise InvalidNeutralMaterial("strain-based family applicability is required")
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
            "applicability": self._applicability(),
            "validation": {"status": self.validation_status},
        }

    def _applicability(self) -> dict[str, object]:
        if self.material_model_ir.family is NeutralModelFamily.GENERALIZED_MAXWELL:
            return {
                "time": {
                    "minimum": self.applicable_time_min_s,
                    "maximum": self.applicable_time_max_s,
                    "unit": "s",
                }
            }
        return {
            "engineering_strain": {
                "minimum": self.applicable_strain_min,
                "maximum": self.applicable_strain_max,
                "unit": "1",
            }
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


def _revision_evidence(
    value: dict[str, Any],
) -> RevisionReference | OptionalRevisionEvidence:
    return _optional(value) if "status" in value else _reference(value)


def _artifact(value: dict[str, Any]) -> NeutralArtifactReference:
    return NeutralArtifactReference(
        UUID(value["artifact_id"]),
        str(value["sha256"]),
        str(value["schema_ref"]),
        int(value["point_count"]),
    )


def _prony_terms(values: list[dict[str, Any]]) -> tuple[NeutralPronyTerm, ...]:
    return tuple(
        NeutralPronyTerm(
            ordinal=int(item["ordinal"]),
            g_ratio=float(item["g_ratio"]),
            k_ratio=float(item["k_ratio"]),
            relaxation_time_s=float(item["relaxation_time"]["value"]),
        )
        for item in values
    )


def _selection(
    value: dict[str, Any],
) -> NeutralCandidateSelection | NeutralProcessingSelection | NeutralPronyProcessingSelection:
    if value.get("kind") == "processing_output_selection":
        return NeutralProcessingSelection(
            processing_output=_reference(value["processing_output"]),
            processing_output_sha256=str(value["processing_output_sha256"]),
            reason=str(value["reason"]),
            selected_series=str(value["selected_series"]),
            candidate_families=tuple(str(item) for item in value["candidate_families"]),
            primary_family=str(value["primary_family"]),
            secondary_family=(
                None if value["secondary_family"] is None else str(value["secondary_family"])
            ),
            primary_weight=(
                None if value["primary_weight"] is None else float(value["primary_weight"])
            ),
            fit_decision=fit_decision_evidence_from_canonical(value.get("fit_decision")),
            warnings=tuple(str(item) for item in value["warnings"]),
        )
    if value.get("kind") == "prony_processing_output_selection":
        return NeutralPronyProcessingSelection(
            processing_output=_reference(value["processing_output"]),
            processing_output_sha256=str(value["processing_output_sha256"]),
            reason=str(value["reason"]),
            selected_series=str(value["selected_series"]),
            selection_mode=str(value["selection_mode"]),
            selected_term_count=int(value["selected_term_count"]),
            normalized_rmse=float(value["normalized_rmse"]),
            bic=float(value["bic"]),
            fitted_instantaneous_shear_modulus_pa=float(
                value["fitted_instantaneous_shear_modulus_pa"]
            ),
            catalog_instantaneous_shear_modulus_pa=float(
                value["catalog_instantaneous_shear_modulus_pa"]
            ),
            instantaneous_modulus_relative_mismatch=float(
                value["instantaneous_modulus_relative_mismatch"]
            ),
            acknowledged_maximum_relative_mismatch=float(
                value["acknowledged_maximum_relative_mismatch"]
            ),
            fit_decision=fit_decision_evidence_from_canonical(value.get("fit_decision")),
            warnings=tuple(str(item) for item in value["warnings"]),
        )
    return NeutralCandidateSelection(
        calibration_run_id=UUID(value["calibration_run_id"]),
        candidate_id=UUID(value["candidate_id"]),
        candidate_sha256=str(value["candidate_sha256"]),
        diagnostics_artifact_id=UUID(value["diagnostics_artifact_id"]),
        diagnostics_sha256=str(value["diagnostics_sha256"]),
        reason=str(value["reason"]),
        objective_total=float(value["objective_total"]),
        calibration_normalized_rmse=float(value["calibration_normalized_rmse"]),
        holdout_normalized_rmse=(
            float(value["holdout_normalized_rmse"])
            if value["holdout_normalized_rmse"] is not None
            else None
        ),
        stability_status=str(value["stability_status"]),
        warnings=tuple(str(item) for item in value["warnings"]),
    )


def _material_ir(
    value: dict[str, Any],
) -> NeutralHyperelasticIR | NeutralElastoplasticIR | NeutralLinearViscoelasticIR:
    family = NeutralModelFamily(value.get("model_family", "hyperelastic"))
    model = _reference(value["model"])
    schema_id = str(value["schema_id"])
    schema_version = str(value["schema_version"])
    model_schema_digest = str(value["model_schema_digest"])
    density_kg_per_m3 = float(value["density"]["value"])
    maturity = ModelMaturity(value["maturity"])
    non_production = bool(value["non_production"])
    constitutive = value["constitutive_model"]
    if family is NeutralModelFamily.HYPERELASTIC:
        raw_overlay = value.get("prony_overlay")
        overlay = None
        if isinstance(raw_overlay, dict):
            source = raw_overlay.get("source_model")
            overlay = NeutralPronyOverlay(
                status=EvidenceStatus(raw_overlay["status"]),
                reason=str(raw_overlay["reason"]),
                terms=_prony_terms(raw_overlay.get("terms", [])),
                source_model=_reference(source) if isinstance(source, dict) else None,
            )
        return NeutralHyperelasticIR(
            model=model,
            schema_id=schema_id,
            schema_version=schema_version,
            model_schema_digest=model_schema_digest,
            parameters=_parameters(constitutive),
            density_kg_per_m3=density_kg_per_m3,
            volumetric_response=str(value["volumetric_response"]),
            prony_overlay=overlay,
            maturity=maturity,
            non_production=non_production,
        )
    if family is NeutralModelFamily.ISOTROPIC_TABULATED_PLASTICITY:
        parameters = constitutive["parameters"]
        selection = constitutive["selection"]
        domain = constitutive["domain"]
        extrapolation = constitutive["extrapolation"]
        return NeutralElastoplasticIR(
            model=model,
            schema_id=schema_id,
            schema_version=schema_version,
            model_schema_digest=model_schema_digest,
            density_kg_per_m3=density_kg_per_m3,
            youngs_modulus_pa=float(parameters["youngs_modulus"]["value"]),
            poisson_ratio=float(parameters["poisson_ratio"]["value"]),
            initial_yield_stress_pa=float(parameters["initial_yield_stress"]["value"]),
            hardening_curve=_artifact(constitutive["hardening_curve"]),
            candidate_families=tuple(str(item) for item in selection["candidate_families"]),
            primary_family=str(selection["primary_family"]),
            secondary_family=(
                None
                if selection["secondary_family"] is None
                else str(selection["secondary_family"])
            ),
            primary_weight=(
                None if selection["primary_weight"] is None else float(selection["primary_weight"])
            ),
            characterized_max_true_plastic_strain=float(
                domain["characterized_maximum_true_plastic_strain"]
            ),
            extension_max_true_plastic_strain=float(
                domain["extension_maximum_true_plastic_strain"]
            ),
            extrapolation_policy=str(extrapolation["policy"]),
            approximation_acknowledged=bool(extrapolation["approximation_acknowledged"]),
            fit_decision=fit_decision_evidence_from_canonical(
                selection.get("fit_decision")
            ),
            maturity=maturity,
            non_production=non_production,
        )
    parameters = constitutive["parameters"]
    return NeutralLinearViscoelasticIR(
        model=model,
        schema_id=schema_id,
        schema_version=schema_version,
        model_schema_digest=model_schema_digest,
        density_kg_per_m3=density_kg_per_m3,
        youngs_modulus_pa=float(parameters["youngs_modulus"]["value"]),
        poisson_ratio=float(parameters["poisson_ratio"]["value"]),
        bulk_relaxation_status=str(constitutive["bulk_relaxation_status"]),
        terms=_prony_terms(constitutive["prony_terms"]),
        reference_temperature_k=float(value["reference_temperature"]["value"]),
        fit_decision=fit_decision_evidence_from_canonical(value.get("fit_decision")),
        maturity=maturity,
        non_production=non_production,
    )


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
    applicability = raw["applicability"]
    strain = applicability.get("engineering_strain")
    time = applicability.get("time")
    datasets = tuple(
        NeutralDatasetSource(
            dataset=_reference(item["dataset"]),
            role=NeutralDatasetRole(item["role"]),
            test_mode=NeutralTestMode(item["test_mode"]),
            normalized_artifact_id=UUID(item["normalized_artifact"]["artifact_id"]),
            normalized_artifact_sha256=str(item["normalized_artifact"]["sha256"]),
            source_kind=NeutralDatasetKind(
                item.get("source_kind", NeutralDatasetKind.GOVERNED_DATASET.value)
            ),
        )
        for item in sources["datasets"]
    )
    curves = tuple(
        NeutralCurve(
            stage=CurveStage(item["stage"]),
            dataset_revision_id=UUID(item["dataset_revision_id"]),
            test_mode=NeutralTestMode(item["test_mode"]),
            x_quantity=str(item["x_quantity"]),
            x_unit=str(item["x_unit"]),
            y_quantity=str(item["y_quantity"]),
            y_unit=str(item["y_unit"]),
            x=tuple(float(number) for number in item["x"]),
            y=tuple(float(number) for number in item["y"]),
        )
        for item in raw["curve_stages"]
    )
    return NeutralMaterialDocument(
        document_id=UUID(raw["document_id"]),
        organization_id=UUID(scope["organization_id"]),
        project_id=UUID(scope["project_id"]),
        classification=str(scope["classification"]),
        material=_reference(sources["material"]),
        material_state=_reference(sources["material_state"]),
        property_set=_reference(sources["property_set"]),
        calibration_plan=_revision_evidence(sources["calibration_plan"]),
        scientific_profile=_revision_evidence(sources["scientific_profile"]),
        mapping_profile=_optional(sources["mapping_profile"]),
        processing_recipe=_optional(sources["processing_recipe"]),
        source_datasets=datasets,
        curves=curves,
        selection=_selection(selection),
        material_model_ir=_material_ir(ir),
        applicable_strain_min=float(strain["minimum"]) if isinstance(strain, dict) else None,
        applicable_strain_max=float(strain["maximum"]) if isinstance(strain, dict) else None,
        validation_status=str(raw["validation"]["status"]),
        applicable_time_min_s=float(time["minimum"]) if isinstance(time, dict) else None,
        applicable_time_max_s=float(time["maximum"]) if isinstance(time, dict) else None,
        document_type=str(raw["document_type"]),
        schema_version=str(raw["schema_version"]),
    )
