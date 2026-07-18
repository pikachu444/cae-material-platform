"""Explicit OpenRadioss and Abaqus mappings for the reference elastoplastic IR."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_POST_NECKING_EXTENSION_POLICY,
    REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
    REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST,
    REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
    HardeningCurvePoint,
    ReferenceIsotropicTabulatedPlasticityContent,
    validate_hardening_curve,
)
from cmp.modules.modeling.domain.reference_processed_tabulated_plasticity import (
    REFERENCE_PROCESSED_EXTRAPOLATION_POLICY,
    REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID,
    REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST,
    REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_VERSION,
    ReferenceProcessedTabulatedPlasticityContent,
)
from cmp.modules.modeling.domain.reference_voce_tabulated_plasticity import (
    REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID,
    REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_DIGEST,
    REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
    ReferenceVoceTabulatedPlasticityContent,
)
from cmp.shared.domain.revisions import content_sha256

OPENRADIOSS_SOLVER = "openradioss"
OPENRADIOSS_VERSION = "2025"
OPENRADIOSS_UNIT_SYSTEM = "kg_m_s"
OPENRADIOSS_LAW36_KEYWORD = "/MAT/LAW36"
OPENRADIOSS_LAW36_EXPORTER_ID = "cmp.reference.openradioss-law36"
OPENRADIOSS_LAW36_EXPORTER_VERSION = "1.0.0"

ABAQUS_SOLVER = "abaqus"
ABAQUS_VERSION = "2025"
ABAQUS_UNIT_SYSTEM = "kg_m_s"
ABAQUS_PLASTIC_EXPORTER_ID = "cmp.reference.abaqus-isotropic-plasticity"
ABAQUS_PLASTIC_EXPORTER_VERSION = "1.0.0"

MappingStatus = Literal[
    "exact",
    "transformed",
    "approximated",
    "ignored",
    "unsupported",
    "not_applicable",
]
type ExportableTabulatedPlasticityContent = (
    ReferenceIsotropicTabulatedPlasticityContent
    | ReferenceVoceTabulatedPlasticityContent
    | ReferenceProcessedTabulatedPlasticityContent
)

_VALID_MAPPING_STATUSES = frozenset(
    {
        "exact",
        "transformed",
        "approximated",
        "ignored",
        "unsupported",
        "not_applicable",
    }
)
_MATERIAL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")


def _exporter_digest(exporter_id: str, exporter_version: str, target: dict[str, str]) -> str:
    return content_sha256(
        {
            "exporter_id": exporter_id,
            "exporter_version": exporter_version,
            "target": target,
            "model_family": REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
            "model_schema_version": REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
            "model_schema_digest": REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST,
            "mapping_statuses": sorted(_VALID_MAPPING_STATUSES),
            "non_production": True,
        }
    )


OPENRADIOSS_LAW36_EXPORTER_DIGEST = _exporter_digest(
    OPENRADIOSS_LAW36_EXPORTER_ID,
    OPENRADIOSS_LAW36_EXPORTER_VERSION,
    {
        "solver": OPENRADIOSS_SOLVER,
        "version": OPENRADIOSS_VERSION,
        "unit_system": OPENRADIOSS_UNIT_SYSTEM,
        "keyword": OPENRADIOSS_LAW36_KEYWORD,
        "curve_axes": "true_plastic_strain,true_yield_stress",
        "optional_field_policy": "omit_to_documented_defaults",
    },
)
ABAQUS_PLASTIC_EXPORTER_DIGEST = _exporter_digest(
    ABAQUS_PLASTIC_EXPORTER_ID,
    ABAQUS_PLASTIC_EXPORTER_VERSION,
    {
        "solver": ABAQUS_SOLVER,
        "version": ABAQUS_VERSION,
        "unit_system": ABAQUS_UNIT_SYSTEM,
        "keywords": "*DENSITY|*ELASTIC|*PLASTIC",
        "plastic_data_order": "yield_stress,true_plastic_strain",
        "extrapolation": "constant",
        "consistent_units": "kg,m,s,Pa",
    },
)


class ElastoplasticExportError(Exception):
    """Base error for the bounded multi-solver exporter."""


class InvalidElastoplasticExport(ElastoplasticExportError, ValueError):
    """The target, mapping acknowledgement, or output request is invalid."""


class UnsupportedElastoplasticTarget(ElastoplasticExportError):
    """No explicit exporter owns the requested target tuple."""


class ElastoplasticMappingReportMismatch(ElastoplasticExportError):
    """The caller did not acknowledge the current frozen mapping report."""


class ElastoplasticSolverCardNotFound(ElastoplasticExportError):
    """A card or revision is unavailable in the active scope."""


class ElastoplasticSolverCardConflict(ElastoplasticExportError):
    """A stable identity or immutable revision precondition conflicts."""


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidElastoplasticExport(f"{name} must be non-zero")


def _sha256(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidElastoplasticExport(f"{name} must be a lowercase SHA-256 digest")


def _material_name(value: str) -> None:
    if _MATERIAL_NAME.fullmatch(value) is None:
        raise InvalidElastoplasticExport(
            "material_name must start with a letter and contain only letters, digits, _ or - "
            "within 80 characters"
        )


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise InvalidElastoplasticExport(f"{name} must be finite and greater than zero")


def _optional_nonnegative(name: str, value: float | None) -> None:
    if value is not None and (not math.isfinite(value) or value < 0.0):
        raise InvalidElastoplasticExport(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ElastoplasticExportTarget:
    solver: str
    version: str
    unit_system: str

    def __post_init__(self) -> None:
        for name, value, maximum in (
            ("solver", self.solver, 64),
            ("version", self.version, 64),
            ("unit_system", self.unit_system, 64),
        ):
            if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
                raise InvalidElastoplasticExport(
                    f"{name} must be trimmed and contain 1..{maximum} characters"
                )

    @property
    def is_openradioss(self) -> bool:
        return (
            self.solver == OPENRADIOSS_SOLVER
            and self.version == OPENRADIOSS_VERSION
            and self.unit_system == OPENRADIOSS_UNIT_SYSTEM
        )

    @property
    def is_abaqus(self) -> bool:
        return (
            self.solver == ABAQUS_SOLVER
            and self.version == ABAQUS_VERSION
            and self.unit_system == ABAQUS_UNIT_SYSTEM
        )


@dataclass(frozen=True, slots=True)
class ElastoplasticMappingItem:
    name: str
    ir_path: str
    target_representation: str | None
    status: MappingStatus
    detail: str

    def __post_init__(self) -> None:
        if not self.name or self.name != self.name.strip() or len(self.name) > 80:
            raise InvalidElastoplasticExport("mapping item name is invalid")
        if not self.ir_path.startswith("/") or len(self.ir_path) > 255:
            raise InvalidElastoplasticExport("mapping IR path is invalid")
        if self.status not in _VALID_MAPPING_STATUSES:
            raise InvalidElastoplasticExport("mapping status is invalid")
        if not self.detail or self.detail != self.detail.strip() or len(self.detail) > 1_000:
            raise InvalidElastoplasticExport("mapping detail is invalid")

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ir_path": self.ir_path,
            "target_representation": self.target_representation,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ElastoplasticMappingReport:
    material_model_id: UUID
    material_model_revision_id: UUID
    target: ElastoplasticExportTarget
    items: tuple[ElastoplasticMappingItem, ...]
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    model_schema_digest: str = REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST
    non_production: bool = True

    def __post_init__(self) -> None:
        _uuid("material_model_id", self.material_model_id)
        _uuid("material_model_revision_id", self.material_model_revision_id)
        _sha256("model_schema_digest", self.model_schema_digest)
        _sha256("exporter_digest", self.exporter_digest)
        if not self.items or len({item.name for item in self.items}) != len(self.items):
            raise InvalidElastoplasticExport("mapping report requires unique explicit items")
        expected = _exporter_identity(self.target)
        actual = (self.exporter_id, self.exporter_version, self.exporter_digest)
        unsupported = ("cmp.reference.unsupported", "0", "0" * 64)
        if (expected is None and actual != unsupported) or (
            expected is not None and expected != actual
        ):
            raise InvalidElastoplasticExport("mapping report exporter does not own the target")
        if self.model_schema_digest not in {
            REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST,
            REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_DIGEST,
            REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST,
        }:
            raise InvalidElastoplasticExport("mapping report model schema is not exportable")
        if not self.non_production:
            raise InvalidElastoplasticExport("reference mapping report must remain non-production")

    @property
    def exportable(self) -> bool:
        # An approximation is exportable only through the digest acknowledgement required by
        # build_reference_elastoplastic_solver_card. Unsupported or ignored semantics remain a
        # hard stop; the caller cannot acknowledge data loss into existence.
        return not any(item.status in {"unsupported", "ignored"} for item in self.items)

    def canonical(self) -> dict[str, object]:
        return {
            "material_model_id": str(self.material_model_id),
            "material_model_revision_id": str(self.material_model_revision_id),
            "model_schema_digest": self.model_schema_digest,
            "target": {
                "solver": self.target.solver,
                "version": self.target.version,
                "unit_system": self.target.unit_system,
            },
            "items": [item.canonical() for item in self.items],
            "exporter": {
                "id": self.exporter_id,
                "version": self.exporter_version,
                "digest": self.exporter_digest,
            },
            "non_production": self.non_production,
        }

    @property
    def digest(self) -> str:
        return content_sha256(self.canonical())


def _exporter_identity(target: ElastoplasticExportTarget) -> tuple[str, str, str] | None:
    if target.is_openradioss:
        return (
            OPENRADIOSS_LAW36_EXPORTER_ID,
            OPENRADIOSS_LAW36_EXPORTER_VERSION,
            OPENRADIOSS_LAW36_EXPORTER_DIGEST,
        )
    if target.is_abaqus:
        return (
            ABAQUS_PLASTIC_EXPORTER_ID,
            ABAQUS_PLASTIC_EXPORTER_VERSION,
            ABAQUS_PLASTIC_EXPORTER_DIGEST,
        )
    return None


def _mapping_items(
    target: ElastoplasticExportTarget, *, processed_selection: bool = False
) -> tuple[ElastoplasticMappingItem, ...]:
    if not (target.is_openradioss or target.is_abaqus):
        return (
            ElastoplasticMappingItem(
                "target",
                "/target",
                None,
                "unsupported",
                "Only OpenRadioss 2025 kg_m_s and Abaqus 2025 kg_m_s are declared.",
            ),
        )
    if target.is_openradioss:
        density_target = "/MAT/LAW36/RHO_I"
        elasticity_target = "/MAT/LAW36/E,nu"
        yield_target = "/FUNCT/first point"
        hardening_target = "/FUNCT/plastic-strain,true-stress"
        extension_target = "/FUNCT/final constant-stress segment"
        unit_target = "/UNIT/1 (kg,m,s)"
        unit_status: MappingStatus = "exact"
        unit_detail = "The card declares the kg-m-s unit system with /UNIT/1."
    else:
        density_target = "*DENSITY"
        elasticity_target = "*ELASTIC"
        yield_target = "*PLASTIC/first data line"
        hardening_target = "*PLASTIC/yield-stress,true-plastic-strain"
        extension_target = "*PLASTIC, EXTRAPOLATION=CONSTANT"
        unit_target = "Abaqus consistent units (documented comment)"
        unit_status = "transformed"
        unit_detail = (
            "Abaqus keywords do not encode units; SI values are emitted under an explicit "
            "kg-m-s consistent-unit declaration in comments."
        )
    return (
        ElastoplasticMappingItem(
            "density",
            "/parameters/density",
            density_target,
            "exact",
            "SI density is emitted without numeric approximation.",
        ),
        ElastoplasticMappingItem(
            "isotropic_elasticity",
            "/parameters/youngs_modulus|poisson_ratio",
            elasticity_target,
            "exact",
            "Young's modulus and Poisson ratio map to isotropic elasticity.",
        ),
        ElastoplasticMappingItem(
            "initial_yield",
            "/parameters/initial_yield_stress",
            yield_target,
            "transformed",
            "The yield anchor is the first hardening point at zero plastic strain.",
        ),
        ElastoplasticMappingItem(
            "isotropic_hardening_curve",
            "/hardening_curve",
            hardening_target,
            "transformed",
            "The same immutable true-stress/true-plastic-strain Artifact is rendered as text.",
        ),
        ElastoplasticMappingItem(
            "post_necking_extension",
            "/transformation/post_necking_extension_policy",
            extension_target,
            "approximated",
            (
                "The selected fitted IR curve contains an explicitly acknowledged bounded "
                "extension. The exporter emits those points and declares constant target "
                "behavior only beyond the final emitted point."
                if processed_selection
                else "The IR contains an explicitly acknowledged constant-stress extension "
                "beyond the measured pre-necking range; the exporter preserves it without "
                "adding another default."
            ),
        ),
        ElastoplasticMappingItem(
            "temperature_dependence",
            "/applicability/temperature",
            None,
            "not_applicable",
            "Temperature is a validity range; this first model has no temperature dependency.",
        ),
        ElastoplasticMappingItem(
            "strain_rate_dependence",
            "/applicability/strain_rate",
            None,
            "not_applicable",
            "Strain rate is a validity range; this first model is rate-independent.",
        ),
        ElastoplasticMappingItem(
            "unit_system",
            "/semantics/units",
            unit_target,
            unit_status,
            unit_detail,
        ),
    )


def preflight_reference_elastoplastic_export(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    content: ExportableTabulatedPlasticityContent,
    target: ElastoplasticExportTarget,
) -> ElastoplasticMappingReport:
    exporter = _exporter_identity(target)
    if exporter is None:
        exporter = ("cmp.reference.unsupported", "0", "0" * 64)
    return ElastoplasticMappingReport(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        model_schema_digest=content.model_schema_digest,
        target=target,
        items=_mapping_items(
            target,
            processed_selection=(
                content.model_schema_digest
                == REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST
            ),
        ),
        exporter_id=exporter[0],
        exporter_version=exporter[1],
        exporter_digest=exporter[2],
    )


def _scientific(value: float) -> str:
    _positive("numeric value", value)
    return f"{value:.9E}"


def _ratio(value: float) -> str:
    if not math.isfinite(value) or not -1.0 < value < 0.5:
        raise InvalidElastoplasticExport("poisson_ratio must remain within (-1, 0.5)")
    return f"{value:.9E}"


def render_reference_openradioss_law36_card(
    *,
    material_model_revision_id: UUID,
    mapping_report_sha256: str,
    solver_material_id: int,
    material_name: str,
    density_kg_per_m3: float,
    youngs_modulus_pa: float,
    poisson_ratio: float,
    points: tuple[HardeningCurvePoint, ...],
) -> str:
    _uuid("material_model_revision_id", material_model_revision_id)
    _sha256("mapping_report_sha256", mapping_report_sha256)
    if not 1 <= solver_material_id <= 9_999_999_999:
        raise InvalidElastoplasticExport("solver_material_id must be within 1..9999999999")
    _material_name(material_name)
    _positive("density_kg_per_m3", density_kg_per_m3)
    _positive("youngs_modulus_pa", youngs_modulus_pa)
    validate_hardening_curve(points)
    lines = [
        "#RADIOSS STARTER",
        (
            f"# CMP non-production exporter {OPENRADIOSS_LAW36_EXPORTER_ID} "
            f"{OPENRADIOSS_LAW36_EXPORTER_VERSION}"
        ),
        f"# CMP material-model-revision {material_model_revision_id}",
        f"# CMP mapping-report-sha256 {mapping_report_sha256}",
        "/UNIT/1",
        "CMP_SI_KG_M_S",
        "kg                  m                   s",
        f"/MAT/LAW36/{solver_material_id}/1",
        material_name,
        "#              RHO_I",
        f"{_scientific(density_kg_per_m3):>20}",
        (
            "#                  E                  nu           Eps_p_max"
            "               Eps_t               Eps_m"
        ),
        f"{_scientific(youngs_modulus_pa):>20}{_ratio(poisson_ratio):>20}",
        (
            "#  N_funct  F_smooth              C_hard               F_cut"
            "               Eps_f                  VP"
        ),
        # One quasi-static curve: documented defaults retain full isotropic hardening, do not
        # activate a failure limit, and make strain-rate interpolation inapplicable.
        f"{1:>10}",
        "#  fct_IDp              Fscale   Fct_IDE                EInf                  CE",
        # The official LAW36 example omits this optional data line. Omission retains the
        # documented defaults without activating modulus evolution or pressure scaling.
        "# func_ID1",
        f"{solver_material_id:>10}",
        "#           Fscale_1",
        f"{1.0:>20.9E}",
        "#          Eps_dot_1",
        f"{0.0:>20.9E}",
        f"/FUNCT/{solver_material_id}",
        f"{material_name}_TRUE_STRESS_VS_TRUE_PLASTIC_STRAIN",
        "#                  X                   Y",
    ]
    lines.extend(
        f"{point.true_plastic_strain:>20.12E}{point.true_yield_stress_pa:>20.9E}"
        for point in points
    )
    lines.extend(("/END", ""))
    return "\n".join(lines)


def render_reference_abaqus_plastic_card(
    *,
    material_model_revision_id: UUID,
    mapping_report_sha256: str,
    material_name: str,
    density_kg_per_m3: float,
    youngs_modulus_pa: float,
    poisson_ratio: float,
    points: tuple[HardeningCurvePoint, ...],
) -> str:
    _uuid("material_model_revision_id", material_model_revision_id)
    _sha256("mapping_report_sha256", mapping_report_sha256)
    _material_name(material_name)
    _positive("density_kg_per_m3", density_kg_per_m3)
    _positive("youngs_modulus_pa", youngs_modulus_pa)
    if not math.isfinite(poisson_ratio) or not -1.0 < poisson_ratio < 0.5:
        raise InvalidElastoplasticExport("poisson_ratio must remain within (-1, 0.5)")
    validate_hardening_curve(points)
    lines = [
        (
            f"** CMP non-production exporter {ABAQUS_PLASTIC_EXPORTER_ID} "
            f"{ABAQUS_PLASTIC_EXPORTER_VERSION}"
        ),
        "** Consistent units: kg, m, s, Pa",
        f"** CMP material-model-revision {material_model_revision_id}",
        f"** CMP mapping-report-sha256 {mapping_report_sha256}",
        f"*MATERIAL, NAME={material_name}",
        "*DENSITY",
        f"{density_kg_per_m3:.12E},",
        "*ELASTIC, TYPE=ISOTROPIC",
        f"{youngs_modulus_pa:.12E}, {poisson_ratio:.12E}",
        "*PLASTIC, HARDENING=ISOTROPIC, EXTRAPOLATION=CONSTANT",
    ]
    lines.extend(
        f"{point.true_yield_stress_pa:.12E}, {point.true_plastic_strain:.12E}" for point in points
    )
    lines.append("")
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ReferenceElastoplasticSolverCardContent:
    material_model_id: UUID
    material_model_revision_id: UUID
    target: ElastoplasticExportTarget
    solver_material_id: int
    material_name: str
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    initial_yield_stress_pa: float
    hardening_curve_artifact_id: UUID
    hardening_curve_sha256: str
    hardening_curve_point_count: int
    extension_max_true_plastic_strain: float
    post_necking_extension_policy: str
    applicable_temperature_min_k: float | None
    applicable_temperature_max_k: float | None
    applicable_strain_rate_min_per_s: float | None
    applicable_strain_rate_max_per_s: float | None
    applicability_note: str | None
    density_mapping_status: MappingStatus
    elasticity_mapping_status: MappingStatus
    initial_yield_mapping_status: MappingStatus
    hardening_curve_mapping_status: MappingStatus
    extension_mapping_status: MappingStatus
    temperature_mapping_status: MappingStatus
    strain_rate_mapping_status: MappingStatus
    unit_system_mapping_status: MappingStatus
    mapping_report_sha256: str
    card_text: str
    card_sha256: str
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    model_schema_digest: str = REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST
    non_production: bool = True

    def __post_init__(self) -> None:
        for name in (
            "material_model_id",
            "material_model_revision_id",
            "hardening_curve_artifact_id",
        ):
            _uuid(name, getattr(self, name))
        _material_name(self.material_name)
        if not 1 <= self.solver_material_id <= 9_999_999_999:
            raise InvalidElastoplasticExport("solver_material_id must be within 1..9999999999")
        _positive("density_kg_per_m3", self.density_kg_per_m3)
        _positive("youngs_modulus_pa", self.youngs_modulus_pa)
        _positive("initial_yield_stress_pa", self.initial_yield_stress_pa)
        if not math.isfinite(self.poisson_ratio) or not -1.0 < self.poisson_ratio < 0.5:
            raise InvalidElastoplasticExport("poisson_ratio must remain within (-1, 0.5)")
        _sha256("hardening_curve_sha256", self.hardening_curve_sha256)
        _sha256("mapping_report_sha256", self.mapping_report_sha256)
        _sha256("card_sha256", self.card_sha256)
        _sha256("model_schema_digest", self.model_schema_digest)
        _sha256("exporter_digest", self.exporter_digest)
        if not 2 <= self.hardening_curve_point_count <= 5_000:
            raise InvalidElastoplasticExport("hardening curve point count is outside 2..5000")
        _positive("extension_max_true_plastic_strain", self.extension_max_true_plastic_strain)
        if self.post_necking_extension_policy not in {
            REFERENCE_POST_NECKING_EXTENSION_POLICY,
            REFERENCE_PROCESSED_EXTRAPOLATION_POLICY,
        }:
            raise InvalidElastoplasticExport("post-necking extension policy is not recognized")
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
            raise InvalidElastoplasticExport("applicable temperature bounds are inverted")
        if (
            self.applicable_strain_rate_min_per_s is not None
            and self.applicable_strain_rate_max_per_s is not None
            and self.applicable_strain_rate_min_per_s > self.applicable_strain_rate_max_per_s
        ):
            raise InvalidElastoplasticExport("applicable strain-rate bounds are inverted")
        if self.applicability_note is not None and (
            not self.applicability_note.strip()
            or self.applicability_note != self.applicability_note.strip()
            or len(self.applicability_note) > 2_000
            or "\x00" in self.applicability_note
        ):
            raise InvalidElastoplasticExport(
                "applicability_note must be trimmed and contain 1..2000 characters"
            )
        for status in (
            self.density_mapping_status,
            self.elasticity_mapping_status,
            self.initial_yield_mapping_status,
            self.hardening_curve_mapping_status,
            self.extension_mapping_status,
            self.temperature_mapping_status,
            self.strain_rate_mapping_status,
            self.unit_system_mapping_status,
        ):
            if status not in _VALID_MAPPING_STATUSES:
                raise InvalidElastoplasticExport("stored mapping status is invalid")
        expected_exporter = _exporter_identity(self.target)
        if expected_exporter != (
            self.exporter_id,
            self.exporter_version,
            self.exporter_digest,
        ):
            raise InvalidElastoplasticExport("stored exporter identity does not own the target")
        expected_report = ElastoplasticMappingReport(
            material_model_id=self.material_model_id,
            material_model_revision_id=self.material_model_revision_id,
            model_schema_digest=self.model_schema_digest,
            target=self.target,
            items=_mapping_items(
                self.target,
                processed_selection=(
                    self.model_schema_digest
                    == REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST
                ),
            ),
            exporter_id=self.exporter_id,
            exporter_version=self.exporter_version,
            exporter_digest=self.exporter_digest,
        )
        expected_statuses = {item.name: item.status for item in expected_report.items}
        stored_statuses = {
            "density": self.density_mapping_status,
            "isotropic_elasticity": self.elasticity_mapping_status,
            "initial_yield": self.initial_yield_mapping_status,
            "isotropic_hardening_curve": self.hardening_curve_mapping_status,
            "post_necking_extension": self.extension_mapping_status,
            "temperature_dependence": self.temperature_mapping_status,
            "strain_rate_dependence": self.strain_rate_mapping_status,
            "unit_system": self.unit_system_mapping_status,
        }
        if stored_statuses != expected_statuses:
            raise InvalidElastoplasticExport(
                "stored mapping statuses differ from the target contract"
            )
        if self.mapping_report_sha256 != expected_report.digest:
            raise InvalidElastoplasticExport("stored mapping report digest is inconsistent")
        if not self.card_text or len(self.card_text) > 2_000_000:
            raise InvalidElastoplasticExport("card_text must contain 1..2000000 characters")
        if hashlib.sha256(self.card_text.encode("utf-8")).hexdigest() != self.card_sha256:
            raise InvalidElastoplasticExport("card_sha256 does not match UTF-8 card_text")
        if self.model_schema_digest not in {
            REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST,
            REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_DIGEST,
            REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST,
        }:
            raise InvalidElastoplasticExport("stored model schema is not exportable")
        if not self.non_production:
            raise InvalidElastoplasticExport("reference solver card must remain non-production")

    def canonical(self) -> dict[str, object]:
        return {
            "material_model_id": str(self.material_model_id),
            "material_model_revision_id": str(self.material_model_revision_id),
            "model_schema_digest": self.model_schema_digest,
            "target": {
                "solver": self.target.solver,
                "version": self.target.version,
                "unit_system": self.target.unit_system,
                "solver_material_id": self.solver_material_id,
                "material_name": self.material_name,
            },
            "parameters": {
                "density_kg_per_m3": self.density_kg_per_m3,
                "youngs_modulus_pa": self.youngs_modulus_pa,
                "poisson_ratio": self.poisson_ratio,
                "initial_yield_stress_pa": self.initial_yield_stress_pa,
            },
            "hardening_curve": {
                "artifact_id": str(self.hardening_curve_artifact_id),
                "sha256": self.hardening_curve_sha256,
                "point_count": self.hardening_curve_point_count,
                "extension_max_true_plastic_strain": (self.extension_max_true_plastic_strain),
                "post_necking_extension_policy": self.post_necking_extension_policy,
            },
            "applicability": {
                "temperature_min_k": self.applicable_temperature_min_k,
                "temperature_max_k": self.applicable_temperature_max_k,
                "strain_rate_min_per_s": self.applicable_strain_rate_min_per_s,
                "strain_rate_max_per_s": self.applicable_strain_rate_max_per_s,
                "note": self.applicability_note,
            },
            "mapping_statuses": {
                "density": self.density_mapping_status,
                "isotropic_elasticity": self.elasticity_mapping_status,
                "initial_yield": self.initial_yield_mapping_status,
                "isotropic_hardening_curve": self.hardening_curve_mapping_status,
                "post_necking_extension": self.extension_mapping_status,
                "temperature_dependence": self.temperature_mapping_status,
                "strain_rate_dependence": self.strain_rate_mapping_status,
                "unit_system": self.unit_system_mapping_status,
            },
            "mapping_report_sha256": self.mapping_report_sha256,
            "card_sha256": self.card_sha256,
            "exporter": {
                "id": self.exporter_id,
                "version": self.exporter_version,
                "digest": self.exporter_digest,
            },
            "non_production": self.non_production,
        }


def _statuses(report: ElastoplasticMappingReport) -> dict[str, MappingStatus]:
    return {item.name: item.status for item in report.items}


def build_reference_elastoplastic_solver_card(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    source: ExportableTabulatedPlasticityContent,
    points: tuple[HardeningCurvePoint, ...],
    target: ElastoplasticExportTarget,
    expected_mapping_report_sha256: str,
    solver_material_id: int,
    material_name: str,
) -> tuple[ElastoplasticMappingReport, ReferenceElastoplasticSolverCardContent]:
    _sha256("expected_mapping_report_sha256", expected_mapping_report_sha256)
    validate_hardening_curve(points)
    if len(points) != source.hardening_curve_point_count:
        raise InvalidElastoplasticExport("hardening Artifact point count differs from the IR")
    if points[0].true_yield_stress_pa != source.initial_yield_stress_pa:
        raise InvalidElastoplasticExport("hardening Artifact yield anchor differs from the IR")
    if points[-1].true_plastic_strain != source.extension_max_true_plastic_strain:
        raise InvalidElastoplasticExport("hardening Artifact extension differs from the IR")
    report = preflight_reference_elastoplastic_export(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        content=source,
        target=target,
    )
    if not report.exportable:
        raise UnsupportedElastoplasticTarget("target has unsupported or unsafe mapping items")
    if report.digest != expected_mapping_report_sha256:
        raise ElastoplasticMappingReportMismatch(
            "expected_mapping_report_sha256 does not acknowledge the frozen mapping"
        )
    if target.is_openradioss:
        card_text = render_reference_openradioss_law36_card(
            material_model_revision_id=material_model_revision_id,
            mapping_report_sha256=report.digest,
            solver_material_id=solver_material_id,
            material_name=material_name,
            density_kg_per_m3=source.density_kg_per_m3,
            youngs_modulus_pa=source.youngs_modulus_pa,
            poisson_ratio=source.poisson_ratio,
            points=points,
        )
    elif target.is_abaqus:
        card_text = render_reference_abaqus_plastic_card(
            material_model_revision_id=material_model_revision_id,
            mapping_report_sha256=report.digest,
            material_name=material_name,
            density_kg_per_m3=source.density_kg_per_m3,
            youngs_modulus_pa=source.youngs_modulus_pa,
            poisson_ratio=source.poisson_ratio,
            points=points,
        )
    else:
        raise UnsupportedElastoplasticTarget("target is not supported")
    statuses = _statuses(report)
    return report, ReferenceElastoplasticSolverCardContent(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        target=target,
        solver_material_id=solver_material_id,
        material_name=material_name,
        density_kg_per_m3=source.density_kg_per_m3,
        youngs_modulus_pa=source.youngs_modulus_pa,
        poisson_ratio=source.poisson_ratio,
        initial_yield_stress_pa=source.initial_yield_stress_pa,
        hardening_curve_artifact_id=source.hardening_curve_artifact_id,
        hardening_curve_sha256=source.hardening_curve_sha256,
        hardening_curve_point_count=source.hardening_curve_point_count,
        extension_max_true_plastic_strain=source.extension_max_true_plastic_strain,
        post_necking_extension_policy=source.post_necking_extension_policy,
        applicable_temperature_min_k=source.applicable_temperature_min_k,
        applicable_temperature_max_k=source.applicable_temperature_max_k,
        applicable_strain_rate_min_per_s=source.applicable_strain_rate_min_per_s,
        applicable_strain_rate_max_per_s=source.applicable_strain_rate_max_per_s,
        applicability_note=source.applicability_note,
        density_mapping_status=statuses["density"],
        elasticity_mapping_status=statuses["isotropic_elasticity"],
        initial_yield_mapping_status=statuses["initial_yield"],
        hardening_curve_mapping_status=statuses["isotropic_hardening_curve"],
        extension_mapping_status=statuses["post_necking_extension"],
        temperature_mapping_status=statuses["temperature_dependence"],
        strain_rate_mapping_status=statuses["strain_rate_dependence"],
        unit_system_mapping_status=statuses["unit_system"],
        mapping_report_sha256=report.digest,
        card_text=card_text,
        card_sha256=hashlib.sha256(card_text.encode("utf-8")).hexdigest(),
        exporter_id=report.exporter_id,
        exporter_version=report.exporter_version,
        exporter_digest=report.exporter_digest,
        model_schema_digest=source.model_schema_digest,
    )


def validate_reference_elastoplastic_card_with_curve(
    content: ReferenceElastoplasticSolverCardContent,
    points: tuple[HardeningCurvePoint, ...],
) -> None:
    report = ElastoplasticMappingReport(
        material_model_id=content.material_model_id,
        material_model_revision_id=content.material_model_revision_id,
        model_schema_digest=content.model_schema_digest,
        target=content.target,
        items=_mapping_items(
            content.target,
            processed_selection=(
                content.model_schema_digest
                == REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST
            ),
        ),
        exporter_id=content.exporter_id,
        exporter_version=content.exporter_version,
        exporter_digest=content.exporter_digest,
    )
    if report.digest != content.mapping_report_sha256:
        raise InvalidElastoplasticExport("stored mapping report digest is inconsistent")
    if content.target.is_openradioss:
        expected = render_reference_openradioss_law36_card(
            material_model_revision_id=content.material_model_revision_id,
            mapping_report_sha256=report.digest,
            solver_material_id=content.solver_material_id,
            material_name=content.material_name,
            density_kg_per_m3=content.density_kg_per_m3,
            youngs_modulus_pa=content.youngs_modulus_pa,
            poisson_ratio=content.poisson_ratio,
            points=points,
        )
    elif content.target.is_abaqus:
        expected = render_reference_abaqus_plastic_card(
            material_model_revision_id=content.material_model_revision_id,
            mapping_report_sha256=report.digest,
            material_name=content.material_name,
            density_kg_per_m3=content.density_kg_per_m3,
            youngs_modulus_pa=content.youngs_modulus_pa,
            poisson_ratio=content.poisson_ratio,
            points=points,
        )
    else:
        raise UnsupportedElastoplasticTarget("stored target is not supported")
    if expected != content.card_text:
        raise InvalidElastoplasticExport("stored card text differs from its IR mapping")


def elastoplastic_exporter_capability_manifest() -> dict[str, object]:
    return {
        "non_production": True,
        "model_families": [
            {
                "id": REFERENCE_TABULATED_PLASTICITY_FAMILY_ID,
                "schema_version": REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
                "schema_digest": f"sha256:{REFERENCE_TABULATED_PLASTICITY_SCHEMA_DIGEST}",
                "origin": "single_tensile_reduction",
            },
            {
                "id": REFERENCE_VOCE_TABULATED_PLASTICITY_FAMILY_ID,
                "schema_version": REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
                "schema_digest": f"sha256:{REFERENCE_VOCE_TABULATED_PLASTICITY_SCHEMA_DIGEST}",
                "origin": "accepted_multi_curve_voce_candidate",
            },
            {
                "id": REFERENCE_PROCESSED_TABULATED_PLASTICITY_FAMILY_ID,
                "schema_version": REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_VERSION,
                "schema_digest": (
                    f"sha256:{REFERENCE_PROCESSED_TABULATED_PLASTICITY_SCHEMA_DIGEST}"
                ),
                "origin": "exact_processing_output_selected_hardening",
            },
        ],
        "exporters": [
            {
                "id": OPENRADIOSS_LAW36_EXPORTER_ID,
                "version": OPENRADIOSS_LAW36_EXPORTER_VERSION,
                "digest": f"sha256:{OPENRADIOSS_LAW36_EXPORTER_DIGEST}",
                "target": {
                    "solver": OPENRADIOSS_SOLVER,
                    "version": OPENRADIOSS_VERSION,
                    "unit_system": OPENRADIOSS_UNIT_SYSTEM,
                    "keyword": OPENRADIOSS_LAW36_KEYWORD,
                },
            },
            {
                "id": ABAQUS_PLASTIC_EXPORTER_ID,
                "version": ABAQUS_PLASTIC_EXPORTER_VERSION,
                "digest": f"sha256:{ABAQUS_PLASTIC_EXPORTER_DIGEST}",
                "target": {
                    "solver": ABAQUS_SOLVER,
                    "version": ABAQUS_VERSION,
                    "unit_system": ABAQUS_UNIT_SYSTEM,
                    "keywords": ["*DENSITY", "*ELASTIC", "*PLASTIC"],
                },
            },
        ],
        "mapping_statuses": sorted(_VALID_MAPPING_STATUSES),
    }
