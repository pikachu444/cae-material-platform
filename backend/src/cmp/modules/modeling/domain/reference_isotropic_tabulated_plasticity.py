"""Typed non-production tensile reduction and isotropic tabulated-plasticity IR.

This module deliberately owns one public, inspectable transformation.  It does not smooth,
resample, fit a constitutive equation, infer a failure law, or silently repair a noisy curve.
Large hardening curves remain immutable Parquet Artifacts; the IR stores their typed identity and
digest rather than one database row per point.
"""

from __future__ import annotations

import io
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import cast
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.shared.domain.revisions import content_sha256

REFERENCE_TABULATED_PLASTICITY_FAMILY_ID = (
    "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0"
)
REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION = "1.0.0"
REFERENCE_TABULATED_PLASTICITY_IR_SCHEMA_ID = (
    "urn:cmp:modeling:reference-isotropic-tabulated-plasticity:1.0.0"
)
REFERENCE_HARDENING_CURVE_SCHEMA = (
    "urn:cmp:modeling:reference-true-stress-plastic-strain-parquet:1.0.0"
)
REFERENCE_TENSILE_REDUCTION_PROFILE_ID = (
    "urn:cmp:processing:reference-pre-necking-true-plastic-reduction:1.0.0"
)
REFERENCE_TENSILE_REDUCTION_PROFILE_VERSION = "1.0.0"
REFERENCE_POST_NECKING_EXTENSION_POLICY = "approved_constant_true_stress"
MAX_REFERENCE_HARDENING_POINTS = 5_000

REFERENCE_TENSILE_REDUCTION_PROFILE_DIGEST = content_sha256(
    {
        "profile_id": REFERENCE_TENSILE_REDUCTION_PROFILE_ID,
        "version": REFERENCE_TENSILE_REDUCTION_PROFILE_VERSION,
        "engineering_to_true_stress": "sigma_true=sigma_eng*(1+epsilon_eng)",
        "engineering_to_true_total_strain": "epsilon_true=ln(1+epsilon_eng)",
        "true_plastic_strain": "epsilon_plastic=epsilon_true-sigma_true/E",
        "necking_policy": "first_global_maximum_engineering_stress",
        "yield_anchor": "catalog_yield_stress_at_zero_plastic_strain",
        "post_necking_extension": REFERENCE_POST_NECKING_EXTENSION_POLICY,
        "smoothing": "none",
        "resampling": "none",
        "softening": "reject",
        "non_production": True,
    }
)

REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST = content_sha256(
    {
        "family": REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
        "schema_version": REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
        "parameters": [
            "density_kg_per_m3",
            "youngs_modulus_pa",
            "poisson_ratio",
            "initial_yield_stress_pa",
        ],
        "hardening_curve": {
            "schema": REFERENCE_HARDENING_CURVE_SCHEMA,
            "independent": "true_plastic_strain",
            "dependent": "true_yield_stress_pa",
            "point_origin": True,
        },
        "source_revisions": [
            "material_revision_id",
            "material_state_revision_id",
            "property_set_revision_id",
            "dataset_revision_id",
        ],
        "transformation_evidence": [
            "source_point_count",
            "pre_yield_excluded_point_count",
            "post_necking_excluded_point_count",
            "necking_source_point_index",
        ],
        "transformation_profile_digest": REFERENCE_TENSILE_REDUCTION_PROFILE_DIGEST,
        "non_production": True,
    }
)

_write_parquet_table = cast(Callable[..., None], pq.write_table)
_read_parquet_table = cast(Callable[..., pa.Table], pq.read_table)


class TabulatedPlasticityError(Exception):
    """Base error for the bounded elastoplastic projection."""


class InvalidTabulatedPlasticity(TabulatedPlasticityError, ValueError):
    """Input data or a declared transformation violates the typed profile."""


class TabulatedPlasticityConflict(TabulatedPlasticityError):
    """Pinned source scope, revision, or immutable state conflicts with a command."""


class TabulatedPlasticityNotFound(TabulatedPlasticityError):
    """A typed elastoplastic IR is unavailable in the active tenant."""


class HardeningPointOrigin(StrEnum):
    CATALOG_YIELD_ANCHOR = "catalog_yield_anchor"
    PRE_NECKING_OBSERVATION = "pre_necking_observation"
    CALIBRATED_VOCE_SAMPLE = "calibrated_voce_sample"
    APPROVED_CONSTANT_EXTENSION = "approved_constant_extension"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidTabulatedPlasticity(f"{name} must be non-zero")


def _sha256(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidTabulatedPlasticity(f"{name} must be a lowercase SHA-256 digest")


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise InvalidTabulatedPlasticity(f"{name} must be finite and greater than zero")


def _optional_nonnegative(name: str, value: float | None) -> None:
    if value is not None and (not math.isfinite(value) or value < 0.0):
        raise InvalidTabulatedPlasticity(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class HardeningCurvePoint:
    true_plastic_strain: float
    true_yield_stress_pa: float
    origin: HardeningPointOrigin

    def __post_init__(self) -> None:
        if not math.isfinite(self.true_plastic_strain) or self.true_plastic_strain < 0.0:
            raise InvalidTabulatedPlasticity(
                "true_plastic_strain must be finite and non-negative"
            )
        _positive("true_yield_stress_pa", self.true_yield_stress_pa)


@dataclass(frozen=True, slots=True)
class TensileReductionOutcome:
    points: tuple[HardeningCurvePoint, ...]
    input_point_count: int
    pre_yield_excluded_count: int
    post_necking_excluded_count: int
    necking_source_index: int
    necking_engineering_strain: float
    necking_engineering_stress_pa: float
    characterized_max_true_plastic_strain: float
    extension_max_true_plastic_strain: float

    def __post_init__(self) -> None:
        validate_hardening_curve(self.points)
        if self.input_point_count < len(self.points) - 2:
            raise InvalidTabulatedPlasticity("reduction point counts are inconsistent")
        if not 0 <= self.necking_source_index < self.input_point_count:
            raise InvalidTabulatedPlasticity("necking_source_index is outside the input curve")
        _optional_nonnegative("necking_engineering_strain", self.necking_engineering_strain)
        _positive("necking_engineering_stress_pa", self.necking_engineering_stress_pa)
        _optional_nonnegative(
            "characterized_max_true_plastic_strain",
            self.characterized_max_true_plastic_strain,
        )
        if self.extension_max_true_plastic_strain <= self.characterized_max_true_plastic_strain:
            raise InvalidTabulatedPlasticity(
                "extension maximum must exceed the characterized plastic-strain range"
            )


@dataclass(frozen=True, slots=True)
class ReferenceIsotropicTabulatedPlasticityContent:
    """One immutable solver-neutral IR revision backed by a hardening-curve Artifact."""

    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    source_dataset_id: UUID
    source_dataset_revision_id: UUID
    hardening_curve_artifact_id: UUID
    hardening_curve_sha256: str
    hardening_curve_point_count: int
    source_point_count: int
    pre_yield_excluded_point_count: int
    post_necking_excluded_point_count: int
    necking_source_point_index: int
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    initial_yield_stress_pa: float
    necking_engineering_strain: float
    characterized_max_true_plastic_strain: float
    extension_max_true_plastic_strain: float
    post_necking_approximation_acknowledged: bool
    applicable_temperature_min_k: float | None = None
    applicable_temperature_max_k: float | None = None
    applicable_strain_rate_min_per_s: float | None = None
    applicable_strain_rate_max_per_s: float | None = None
    applicability_note: str | None = None
    reference_temperature_k: float = 293.15
    model_family_id: str = REFERENCE_TABULATED_PLASTICITY_FAMILY_ID
    model_schema_version: str = REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION
    model_schema_digest: str = REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST
    hardening_curve_schema_ref: str = REFERENCE_HARDENING_CURVE_SCHEMA
    transformation_profile_id: str = REFERENCE_TENSILE_REDUCTION_PROFILE_ID
    transformation_profile_version: str = REFERENCE_TENSILE_REDUCTION_PROFILE_VERSION
    transformation_profile_digest: str = REFERENCE_TENSILE_REDUCTION_PROFILE_DIGEST
    post_necking_extension_policy: str = REFERENCE_POST_NECKING_EXTENSION_POLICY
    non_production: bool = True

    def __post_init__(self) -> None:
        for name in (
            "material_id",
            "material_revision_id",
            "material_state_id",
            "material_state_revision_id",
            "property_set_id",
            "property_set_revision_id",
            "source_dataset_id",
            "source_dataset_revision_id",
            "hardening_curve_artifact_id",
        ):
            _uuid(name, getattr(self, name))
        _sha256("hardening_curve_sha256", self.hardening_curve_sha256)
        if not 2 <= self.hardening_curve_point_count <= MAX_REFERENCE_HARDENING_POINTS:
            raise InvalidTabulatedPlasticity(
                f"hardening curve must contain 2..{MAX_REFERENCE_HARDENING_POINTS} points"
            )
        if not 4 <= self.source_point_count <= MAX_REFERENCE_HARDENING_POINTS:
            raise InvalidTabulatedPlasticity(
                f"source curve must contain 4..{MAX_REFERENCE_HARDENING_POINTS} points"
            )
        if not 0 <= self.pre_yield_excluded_point_count <= self.source_point_count:
            raise InvalidTabulatedPlasticity("pre-yield excluded-point count is invalid")
        if not 0 <= self.post_necking_excluded_point_count < self.source_point_count:
            raise InvalidTabulatedPlasticity("post-necking excluded-point count is invalid")
        if not 0 <= self.necking_source_point_index < self.source_point_count:
            raise InvalidTabulatedPlasticity("necking source-point index is invalid")
        if (
            self.necking_source_point_index
            + self.post_necking_excluded_point_count
            + 1
            != self.source_point_count
        ):
            raise InvalidTabulatedPlasticity(
                "necking index and post-necking excluded-point count are inconsistent"
            )
        expected_hardening_point_count = (
            self.source_point_count
            - self.pre_yield_excluded_point_count
            - self.post_necking_excluded_point_count
            + 2
        )
        if self.hardening_curve_point_count != expected_hardening_point_count:
            raise InvalidTabulatedPlasticity(
                "source, excluded, and hardening-curve point counts are inconsistent"
            )
        _positive("density_kg_per_m3", self.density_kg_per_m3)
        _positive("youngs_modulus_pa", self.youngs_modulus_pa)
        _positive("initial_yield_stress_pa", self.initial_yield_stress_pa)
        if not math.isfinite(self.poisson_ratio) or not -1.0 < self.poisson_ratio < 0.5:
            raise InvalidTabulatedPlasticity("poisson_ratio must remain within (-1, 0.5)")
        _optional_nonnegative("necking_engineering_strain", self.necking_engineering_strain)
        _optional_nonnegative(
            "characterized_max_true_plastic_strain",
            self.characterized_max_true_plastic_strain,
        )
        if self.extension_max_true_plastic_strain <= self.characterized_max_true_plastic_strain:
            raise InvalidTabulatedPlasticity(
                "extension maximum must exceed characterized maximum plastic strain"
            )
        if not self.post_necking_approximation_acknowledged:
            raise InvalidTabulatedPlasticity(
                "constant post-necking extension requires explicit acknowledgement"
            )
        for name, value in (
            ("applicable_temperature_min_k", self.applicable_temperature_min_k),
            ("applicable_temperature_max_k", self.applicable_temperature_max_k),
            ("applicable_strain_rate_min_per_s", self.applicable_strain_rate_min_per_s),
            ("applicable_strain_rate_max_per_s", self.applicable_strain_rate_max_per_s),
        ):
            _optional_nonnegative(name, value)
        if (
            self.applicable_temperature_min_k is not None
            and self.applicable_temperature_max_k is not None
            and self.applicable_temperature_min_k > self.applicable_temperature_max_k
        ):
            raise InvalidTabulatedPlasticity("applicable temperature bounds are inverted")
        if (
            self.applicable_strain_rate_min_per_s is not None
            and self.applicable_strain_rate_max_per_s is not None
            and self.applicable_strain_rate_min_per_s > self.applicable_strain_rate_max_per_s
        ):
            raise InvalidTabulatedPlasticity("applicable strain-rate bounds are inverted")
        if self.applicability_note is not None and (
            not self.applicability_note.strip()
            or self.applicability_note != self.applicability_note.strip()
            or len(self.applicability_note) > 2_000
            or "\x00" in self.applicability_note
        ):
            raise InvalidTabulatedPlasticity(
                "applicability_note must be trimmed and contain 1..2000 characters"
            )
        if (
            self.model_family_id != REFERENCE_TABULATED_PLASTICITY_FAMILY_ID
            or self.model_schema_version != REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION
            or self.model_schema_digest != REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST
            or self.hardening_curve_schema_ref != REFERENCE_HARDENING_CURVE_SCHEMA
            or self.transformation_profile_id != REFERENCE_TENSILE_REDUCTION_PROFILE_ID
            or self.transformation_profile_version
            != REFERENCE_TENSILE_REDUCTION_PROFILE_VERSION
            or self.transformation_profile_digest
            != REFERENCE_TENSILE_REDUCTION_PROFILE_DIGEST
            or self.post_necking_extension_policy
            != REFERENCE_POST_NECKING_EXTENSION_POLICY
            or not self.non_production
        ):
            raise InvalidTabulatedPlasticity(
                "reference tabulated-plasticity IR must retain its fixed typed contract"
            )


def validate_hardening_curve(points: tuple[HardeningCurvePoint, ...]) -> None:
    if not 2 <= len(points) <= MAX_REFERENCE_HARDENING_POINTS:
        raise InvalidTabulatedPlasticity(
            f"hardening curve must contain 2..{MAX_REFERENCE_HARDENING_POINTS} points"
        )
    if points[0].true_plastic_strain != 0.0:
        raise InvalidTabulatedPlasticity("first hardening point must have zero plastic strain")
    if points[0].origin not in {
        HardeningPointOrigin.CATALOG_YIELD_ANCHOR,
        HardeningPointOrigin.CALIBRATED_VOCE_SAMPLE,
    }:
        raise InvalidTabulatedPlasticity(
            "first hardening point must be a Catalog yield anchor or calibrated Voce sample"
        )
    previous_strain = -1.0
    previous_stress = 0.0
    for point in points:
        if point.true_plastic_strain <= previous_strain:
            raise InvalidTabulatedPlasticity("hardening plastic strain must be strictly increasing")
        if point.true_yield_stress_pa < previous_stress:
            raise InvalidTabulatedPlasticity(
                "hardening yield stress must be non-decreasing; softening is not hidden"
            )
        previous_strain = point.true_plastic_strain
        previous_stress = point.true_yield_stress_pa
    if points[-1].origin is not HardeningPointOrigin.APPROVED_CONSTANT_EXTENSION:
        raise InvalidTabulatedPlasticity(
            "last hardening point must retain the approved constant extension evidence"
        )
    if points[-1].true_yield_stress_pa != points[-2].true_yield_stress_pa:
        raise InvalidTabulatedPlasticity("approved extension must retain constant true stress")


def derive_reference_isotropic_hardening_curve(
    points: tuple[CurvePoint, ...],
    *,
    youngs_modulus_pa: float,
    initial_yield_stress_pa: float,
    extension_max_true_plastic_strain: float,
    acknowledge_post_necking_approximation: bool,
) -> TensileReductionOutcome:
    """Convert SI engineering observations to a monotone true-stress/plastic-strain curve.

    The transformation stops at the first global engineering-stress maximum.  It rejects data
    requiring smoothing or point deletion after yielding.  A constant post-necking extension is
    appended only when the caller explicitly acknowledges that approximation.
    """

    _positive("youngs_modulus_pa", youngs_modulus_pa)
    _positive("initial_yield_stress_pa", initial_yield_stress_pa)
    _positive("extension_max_true_plastic_strain", extension_max_true_plastic_strain)
    if not acknowledge_post_necking_approximation:
        raise InvalidTabulatedPlasticity(
            "post-necking constant extension must be explicitly acknowledged"
        )
    if not 4 <= len(points) <= MAX_REFERENCE_HARDENING_POINTS:
        raise InvalidTabulatedPlasticity(
            f"elastoplastic reduction requires 4..{MAX_REFERENCE_HARDENING_POINTS} observations"
        )

    previous_engineering_strain = -1.0
    for point in points:
        if (
            not math.isfinite(point.engineering_strain)
            or not math.isfinite(point.engineering_stress)
            or point.engineering_strain < 0.0
            or point.engineering_stress < 0.0
        ):
            raise InvalidTabulatedPlasticity(
                "tensile reduction requires finite non-negative SI engineering observations"
            )
        if point.engineering_strain <= previous_engineering_strain:
            raise InvalidTabulatedPlasticity(
                "engineering strain must be strictly increasing; resampling is not implicit"
            )
        previous_engineering_strain = point.engineering_strain

    maximum_engineering_stress = max(point.engineering_stress for point in points)
    necking_index = next(
        index
        for index, point in enumerate(points)
        if point.engineering_stress == maximum_engineering_stress
    )
    if necking_index < 2:
        raise InvalidTabulatedPlasticity(
            "first maximum engineering stress occurs too early for a hardening curve"
        )

    hardening: list[HardeningCurvePoint] = [
        HardeningCurvePoint(
            true_plastic_strain=0.0,
            true_yield_stress_pa=initial_yield_stress_pa,
            origin=HardeningPointOrigin.CATALOG_YIELD_ANCHOR,
        )
    ]
    pre_yield_excluded = 0
    plastic_segment_started = False
    for point in points[: necking_index + 1]:
        true_stress = point.engineering_stress * (1.0 + point.engineering_strain)
        true_total_strain = math.log1p(point.engineering_strain)
        true_plastic_strain = true_total_strain - true_stress / youngs_modulus_pa
        if true_stress < initial_yield_stress_pa or true_plastic_strain <= 0.0:
            if plastic_segment_started:
                raise InvalidTabulatedPlasticity(
                    "a post-yield observation returned to the elastic/negative-plastic range"
                )
            pre_yield_excluded += 1
            continue
        plastic_segment_started = True
        candidate = HardeningCurvePoint(
            true_plastic_strain=true_plastic_strain,
            true_yield_stress_pa=true_stress,
            origin=HardeningPointOrigin.PRE_NECKING_OBSERVATION,
        )
        previous = hardening[-1]
        if candidate.true_plastic_strain <= previous.true_plastic_strain:
            raise InvalidTabulatedPlasticity(
                "derived plastic strain is not strictly increasing; "
                "explicit preprocessing is required"
            )
        if candidate.true_yield_stress_pa < previous.true_yield_stress_pa:
            raise InvalidTabulatedPlasticity(
                "derived true stress softens before necking; explicit QC/preprocessing is required"
            )
        hardening.append(candidate)

    if len(hardening) < 3:
        raise InvalidTabulatedPlasticity(
            "at least two observed plastic points are required after the yield anchor"
        )
    characterized_max = hardening[-1].true_plastic_strain
    if extension_max_true_plastic_strain <= characterized_max:
        raise InvalidTabulatedPlasticity(
            "extension_max_true_plastic_strain must exceed the pre-necking characterized range"
        )
    hardening.append(
        HardeningCurvePoint(
            true_plastic_strain=extension_max_true_plastic_strain,
            true_yield_stress_pa=hardening[-1].true_yield_stress_pa,
            origin=HardeningPointOrigin.APPROVED_CONSTANT_EXTENSION,
        )
    )
    result = tuple(hardening)
    validate_hardening_curve(result)
    return TensileReductionOutcome(
        points=result,
        input_point_count=len(points),
        pre_yield_excluded_count=pre_yield_excluded,
        post_necking_excluded_count=len(points) - necking_index - 1,
        necking_source_index=necking_index,
        necking_engineering_strain=points[necking_index].engineering_strain,
        necking_engineering_stress_pa=points[necking_index].engineering_stress,
        characterized_max_true_plastic_strain=characterized_max,
        extension_max_true_plastic_strain=extension_max_true_plastic_strain,
    )


def hardening_curve_parquet_bytes(points: tuple[HardeningCurvePoint, ...]) -> bytes:
    validate_hardening_curve(points)
    table = pa.table(
        {
            "true_plastic_strain": pa.array(
                [point.true_plastic_strain for point in points], type=pa.float64()
            ),
            "true_yield_stress_pa": pa.array(
                [point.true_yield_stress_pa for point in points], type=pa.float64()
            ),
            "point_origin": pa.array([point.origin.value for point in points], type=pa.string()),
        }
    ).replace_schema_metadata(
        {
            b"cmp_schema_ref": REFERENCE_HARDENING_CURVE_SCHEMA.encode("ascii"),
            b"cmp_transformation_profile": REFERENCE_TENSILE_REDUCTION_PROFILE_ID.encode(
                "ascii"
            ),
            b"cmp_transformation_digest": REFERENCE_TENSILE_REDUCTION_PROFILE_DIGEST.encode(
                "ascii"
            ),
        }
    )
    buffer = io.BytesIO()
    _write_parquet_table(table, buffer, compression="zstd", use_dictionary=False)
    return buffer.getvalue()


def hardening_curve_from_parquet(value: bytes) -> tuple[HardeningCurvePoint, ...]:
    if not value:
        raise InvalidTabulatedPlasticity("hardening-curve Artifact bytes are empty")
    try:
        table = _read_parquet_table(io.BytesIO(value))
    except (OSError, pa.ArrowException) as error:
        raise InvalidTabulatedPlasticity("hardening-curve Artifact is not valid Parquet") from error
    if table.column_names != [
        "true_plastic_strain",
        "true_yield_stress_pa",
        "point_origin",
    ]:
        raise InvalidTabulatedPlasticity("hardening-curve Parquet columns are not recognized")
    expected_types = (pa.float64(), pa.float64(), pa.string())
    if tuple(field.type for field in table.schema) != expected_types:
        raise InvalidTabulatedPlasticity("hardening-curve Parquet column types are not recognized")
    metadata = table.schema.metadata or {}
    if metadata.get(b"cmp_schema_ref") != REFERENCE_HARDENING_CURVE_SCHEMA.encode("ascii"):
        raise InvalidTabulatedPlasticity("hardening-curve Parquet schema reference is invalid")
    if metadata.get(
        b"cmp_transformation_digest"
    ) != REFERENCE_TENSILE_REDUCTION_PROFILE_DIGEST.encode("ascii"):
        raise InvalidTabulatedPlasticity("hardening-curve transformation digest is invalid")
    if metadata.get(b"cmp_transformation_profile") != REFERENCE_TENSILE_REDUCTION_PROFILE_ID.encode(
        "ascii"
    ):
        raise InvalidTabulatedPlasticity("hardening-curve transformation profile is invalid")
    try:
        points = tuple(
            HardeningCurvePoint(
                true_plastic_strain=float(strain),
                true_yield_stress_pa=float(stress),
                origin=HardeningPointOrigin(str(origin)),
            )
            for strain, stress, origin in zip(
                table.column("true_plastic_strain").to_pylist(),
                table.column("true_yield_stress_pa").to_pylist(),
                table.column("point_origin").to_pylist(),
                strict=True,
            )
        )
    except (TypeError, ValueError) as error:
        raise InvalidTabulatedPlasticity("hardening-curve Parquet values are invalid") from error
    validate_hardening_curve(points)
    return points


def reference_isotropic_tabulated_plasticity_canonical(
    value: ReferenceIsotropicTabulatedPlasticityContent,
) -> dict[str, object]:
    return {
        "model_family_id": value.model_family_id,
        "model_schema_version": value.model_schema_version,
        "model_schema_digest": value.model_schema_digest,
        "material_id": str(value.material_id),
        "material_revision_id": str(value.material_revision_id),
        "material_state_id": str(value.material_state_id),
        "material_state_revision_id": str(value.material_state_revision_id),
        "property_set_id": str(value.property_set_id),
        "property_set_revision_id": str(value.property_set_revision_id),
        "source_dataset_id": str(value.source_dataset_id),
        "source_dataset_revision_id": str(value.source_dataset_revision_id),
        "parameters": {
            "density": {"value": value.density_kg_per_m3, "unit": "kg/m^3"},
            "youngs_modulus": {"value": value.youngs_modulus_pa, "unit": "Pa"},
            "poisson_ratio": {"value": value.poisson_ratio, "unit": "1"},
            "initial_yield_stress": {
                "value": value.initial_yield_stress_pa,
                "unit": "Pa",
            },
        },
        "hardening_curve": {
            "artifact_id": str(value.hardening_curve_artifact_id),
            "sha256": value.hardening_curve_sha256,
            "schema_ref": value.hardening_curve_schema_ref,
            "point_count": value.hardening_curve_point_count,
            "independent_quantity": "true_plastic_strain",
            "independent_unit": "1",
            "dependent_quantity": "true_yield_stress",
            "dependent_unit": "Pa",
        },
        "transformation": {
            "profile_id": value.transformation_profile_id,
            "profile_version": value.transformation_profile_version,
            "profile_digest": value.transformation_profile_digest,
            "source_point_count": value.source_point_count,
            "pre_yield_excluded_point_count": value.pre_yield_excluded_point_count,
            "post_necking_excluded_point_count": (
                value.post_necking_excluded_point_count
            ),
            "necking_source_point_index": value.necking_source_point_index,
            "necking_engineering_strain": value.necking_engineering_strain,
            "characterized_max_true_plastic_strain": (
                value.characterized_max_true_plastic_strain
            ),
            "post_necking_extension_policy": value.post_necking_extension_policy,
            "extension_max_true_plastic_strain": value.extension_max_true_plastic_strain,
            "approximation_acknowledged": (
                value.post_necking_approximation_acknowledged
            ),
        },
        "applicability": {
            "reference_temperature_k": value.reference_temperature_k,
            "temperature_min_k": value.applicable_temperature_min_k,
            "temperature_max_k": value.applicable_temperature_max_k,
            "strain_rate_min_per_s": value.applicable_strain_rate_min_per_s,
            "strain_rate_max_per_s": value.applicable_strain_rate_max_per_s,
            "note": value.applicability_note,
        },
        "non_production": value.non_production,
    }


def reference_isotropic_tabulated_plasticity_ir(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    content: ReferenceIsotropicTabulatedPlasticityContent,
) -> dict[str, object]:
    _uuid("material_model_id", material_model_id)
    _uuid("material_model_revision_id", material_model_revision_id)
    return {
        "ir_version": "1.0",
        "ir_id": str(material_model_id),
        "ir_revision_id": str(material_model_revision_id),
        "schema_version": content.model_schema_version,
        "scope": "material_state",
        "model": {
            "family": {
                "id": content.model_family_id,
                "schema_version": content.model_schema_version,
                "schema_digest": f"sha256:{content.model_schema_digest}",
            },
            "behavior": "rate_independent_isotropic_tabulated_plasticity",
            "parameters": reference_isotropic_tabulated_plasticity_canonical(content)[
                "parameters"
            ],
            "hardening_curve": reference_isotropic_tabulated_plasticity_canonical(content)[
                "hardening_curve"
            ],
        },
        "source_revisions": {
            "material_revision_id": str(content.material_revision_id),
            "material_state_revision_id": str(content.material_state_revision_id),
            "property_set_revision_id": str(content.property_set_revision_id),
            "dataset_revision_id": str(content.source_dataset_revision_id),
        },
        "transformation_evidence": reference_isotropic_tabulated_plasticity_canonical(content)[
            "transformation"
        ],
        "applicability": reference_isotropic_tabulated_plasticity_canonical(content)[
            "applicability"
        ],
        "non_production": True,
    }
