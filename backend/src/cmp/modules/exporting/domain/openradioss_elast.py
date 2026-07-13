"""Independent non-production mapping for OpenRadioss 2025 ``/MAT/ELAST``.

The module renders a small text card from the solver-neutral reference linear-elastic IR.  It does
not call a solver, use a solver SDK, or contain test/fitting/material-family behavior.  Every
source constituent has a visible mapping disposition; in particular, an optional Catalog yield
value is recorded as not applicable to this strictly linear-elastic reference model.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from cmp.modules.modeling.domain.reference_linear_elasticity import (
    REFERENCE_MODEL_FAMILY_ID,
    REFERENCE_MODEL_SCHEMA_DIGEST,
    REFERENCE_MODEL_SCHEMA_VERSION,
    ReferenceLinearElasticContent,
)
from cmp.shared.domain.revisions import content_sha256

OPENRADIOSS_SOLVER = "openradioss"
OPENRADIOSS_VERSION = "2025"
OPENRADIOSS_UNIT_SYSTEM = "kg_m_s"
OPENRADIOSS_KEYWORD = "/MAT/ELAST"
EXPORTER_ID = "cmp.reference.openradioss-elast"
EXPORTER_VERSION = "1.0.0"
EXPORTER_DIGEST = content_sha256(
    {
        "exporter_id": EXPORTER_ID,
        "exporter_version": EXPORTER_VERSION,
        "target": {
            "solver": OPENRADIOSS_SOLVER,
            "version": OPENRADIOSS_VERSION,
            "unit_system": OPENRADIOSS_UNIT_SYSTEM,
            "keyword": OPENRADIOSS_KEYWORD,
        },
        "supported_model": {
            "family": REFERENCE_MODEL_FAMILY_ID,
            "schema_version": REFERENCE_MODEL_SCHEMA_VERSION,
            "schema_digest": REFERENCE_MODEL_SCHEMA_DIGEST,
        },
        "reference_only": True,
    }
)

MappingStatus = Literal[
    "exact",
    "transformed",
    "approximated",
    "ignored",
    "unsupported",
    "not_applicable",
]

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


class ExportError(Exception):
    """Base error for typed solver export commands."""


class InvalidExportRequest(ExportError, ValueError):
    """A card target, title, mapping acknowledgement, or typed value is invalid."""


class UnsupportedExportTarget(ExportError):
    """The requested solver/version/unit tuple is not in the reference capability manifest."""


class MappingReportMismatch(ExportError):
    """The client acknowledged a report different from the frozen source/target mapping."""


class SolverCardNotFound(ExportError):
    """The requested solver-card identity or concrete IR revision is absent or hidden."""


class SolverCardConflict(ExportError):
    """A stable card parent or immutable card invariant would be violated."""


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidExportRequest(f"{name} must be non-zero")


def _finite_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise InvalidExportRequest(f"{name} must be finite and greater than zero")


def _optional_positive(name: str, value: float | None) -> None:
    if value is not None:
        _finite_positive(name, value)


def _sha256(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidExportRequest(f"{name} must be a lowercase SHA-256 digest")


def _trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidExportRequest(f"{name} must be trimmed and contain 1..{maximum} characters")


@dataclass(frozen=True, slots=True)
class ExportTarget:
    """An explicit solver/version/unit choice; the reference exporter has one supported tuple."""

    solver: str
    version: str
    unit_system: str

    def __post_init__(self) -> None:
        _trimmed("solver", self.solver, 64)
        _trimmed("version", self.version, 64)
        _trimmed("unit_system", self.unit_system, 64)

    @property
    def is_reference_openradioss(self) -> bool:
        return (
            self.solver == OPENRADIOSS_SOLVER
            and self.version == OPENRADIOSS_VERSION
            and self.unit_system == OPENRADIOSS_UNIT_SYSTEM
        )


@dataclass(frozen=True, slots=True)
class MappingItem:
    """One explicit source constituent and its target disposition."""

    name: str
    ir_path: str
    target_representation: str | None
    status: MappingStatus
    detail: str

    def __post_init__(self) -> None:
        _trimmed("mapping item name", self.name, 100)
        _trimmed("mapping item ir_path", self.ir_path, 300)
        if self.target_representation is not None:
            _trimmed("mapping item target_representation", self.target_representation, 300)
        if self.status not in _VALID_MAPPING_STATUSES:
            raise InvalidExportRequest(f"unknown mapping status: {self.status}")
        _trimmed("mapping item detail", self.detail, 1000)

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ir_path": self.ir_path,
            "target_representation": self.target_representation,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ReferenceMappingReport:
    """Deterministic preflight report for one concrete reference IR revision and target tuple."""

    material_model_id: UUID
    material_model_revision_id: UUID
    model_schema_digest: str
    target: ExportTarget
    items: tuple[MappingItem, ...]
    exporter_id: str = EXPORTER_ID
    exporter_version: str = EXPORTER_VERSION
    exporter_digest: str = EXPORTER_DIGEST
    non_production: bool = True

    def __post_init__(self) -> None:
        _nonzero("material_model_id", self.material_model_id)
        _nonzero("material_model_revision_id", self.material_model_revision_id)
        _sha256("model_schema_digest", self.model_schema_digest)
        _trimmed("exporter_id", self.exporter_id, 255)
        _trimmed("exporter_version", self.exporter_version, 64)
        _sha256("exporter_digest", self.exporter_digest)
        if not self.items:
            raise InvalidExportRequest("mapping report must contain at least one explicit item")
        if len({item.name for item in self.items}) != len(self.items):
            raise InvalidExportRequest("mapping report item names must be unique")
        if not self.non_production:
            raise InvalidExportRequest("the reference exporter must remain non-production")

    @property
    def exportable(self) -> bool:
        return self.target.is_reference_openradioss and not any(
            item.status in {"unsupported", "approximated", "ignored"} for item in self.items
        )

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


def _mapping_items(
    *,
    source_yield_stress_pa: float | None,
    applicable_temperature_min_k: float | None,
    applicable_temperature_max_k: float | None,
    applicable_strain_rate_min_per_s: float | None,
    applicable_strain_rate_max_per_s: float | None,
    target: ExportTarget,
) -> tuple[MappingItem, ...]:
    if not target.is_reference_openradioss:
        return (
            MappingItem(
                "target",
                "/target",
                None,
                "unsupported",
                "Only the non-production OpenRadioss 2025 kg_m_s reference target is available.",
            ),
        )
    yield_detail = (
        (
            "Source yield stress is retained for provenance but is not part of isotropic "
            "linear elasticity."
        )
        if source_yield_stress_pa is not None
        else "No source yield stress exists; plasticity is not part of isotropic linear elasticity."
    )
    temperature_detail = (
        (
            "Catalog temperature applicability is retained in IR provenance and is not encoded "
            "by this law."
        )
        if (
            applicable_temperature_min_k is not None
            or applicable_temperature_max_k is not None
        )
        else "No Catalog temperature applicability range is characterized."
    )
    rate_detail = (
        (
            "Catalog strain-rate applicability is retained in IR provenance and is not encoded "
            "by this law."
        )
        if (
            applicable_strain_rate_min_per_s is not None
            or applicable_strain_rate_max_per_s is not None
        )
        else "No Catalog strain-rate applicability range is characterized."
    )
    return (
        MappingItem(
            "density",
            "/payload/density",
            "/MAT/ELAST/RHO_I",
            "exact",
            "SI density maps directly to the OpenRadioss initial density field.",
        ),
        MappingItem(
            "youngs_modulus",
            "/payload/youngs_modulus",
            "/MAT/ELAST/E",
            "exact",
            "SI Young's modulus maps directly to the isotropic elastic modulus field.",
        ),
        MappingItem(
            "poisson_ratio",
            "/payload/poisson_ratio",
            "/MAT/ELAST/nu",
            "exact",
            "Dimensionless Poisson ratio maps directly to the isotropic elastic ratio field.",
        ),
        MappingItem(
            "source_yield_stress",
            "/payload/source_property_disposition/yield_stress",
            None,
            "not_applicable",
            yield_detail,
        ),
        MappingItem(
            "temperature_applicability",
            "/validity_domain/temperature",
            None,
            "not_applicable",
            temperature_detail,
        ),
        MappingItem(
            "strain_rate_applicability",
            "/validity_domain/strain_rate",
            None,
            "not_applicable",
            rate_detail,
        ),
        MappingItem(
            "unit_system",
            "/semantics",
            "/UNIT/1 (kg, m, s)",
            "exact",
            "The card declares the selected SI kg_m_s unit system explicitly.",
        ),
    )


def preflight_reference_openradioss_elast(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    content: ReferenceLinearElasticContent,
    target: ExportTarget,
) -> ReferenceMappingReport:
    """Calculate an explicit mapping report without persisting a card."""

    return ReferenceMappingReport(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        model_schema_digest=REFERENCE_MODEL_SCHEMA_DIGEST,
        target=target,
        items=_mapping_items(
            source_yield_stress_pa=content.source_yield_stress_pa,
            applicable_temperature_min_k=content.applicable_temperature_min_k,
            applicable_temperature_max_k=content.applicable_temperature_max_k,
            applicable_strain_rate_min_per_s=content.applicable_strain_rate_min_per_s,
            applicable_strain_rate_max_per_s=content.applicable_strain_rate_max_per_s,
            target=target,
        ),
    )


def _scientific(value: float) -> str:
    _finite_positive("OpenRadioss numeric value", value)
    return f"{value:.9E}"


def _ratio(value: float) -> str:
    if not math.isfinite(value) or not -1 < value < 0.5:
        raise InvalidExportRequest("poisson_ratio must remain within (-1, 0.5)")
    return f"{value:.9E}"


def render_reference_openradioss_elast_card(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    report: ReferenceMappingReport,
    solver_material_id: int,
    card_title: str,
    density_kg_per_m3: float,
    youngs_modulus_pa: float,
    poisson_ratio: float,
) -> str:
    """Render deterministic OpenRadioss text with explicit units and provenance comments."""

    _nonzero("material_model_id", material_model_id)
    _nonzero("material_model_revision_id", material_model_revision_id)
    if not report.exportable:
        raise UnsupportedExportTarget("the selected target has unsupported or unsafe mapping items")
    if not 1 <= solver_material_id <= 9_999_999_999:
        raise InvalidExportRequest("solver_material_id must be within 1..9999999999")
    _trimmed("card_title", card_title, 100)
    if "\n" in card_title or "\r" in card_title:
        raise InvalidExportRequest("card_title must be a single line")
    return "\n".join(
        (
            "#RADIOSS STARTER",
            f"# CMP reference-only exporter {EXPORTER_ID} {EXPORTER_VERSION}",
            f"# CMP material-model-revision {material_model_revision_id}",
            f"# CMP mapping-report-sha256 {report.digest}",
            "/UNIT/1",
            "CMP_SI_KG_M_S",
            "kg                  m                   s",
            f"{OPENRADIOSS_KEYWORD}/{solver_material_id}/1",
            card_title,
            "#              RHO_I",
            f"{_scientific(density_kg_per_m3):>20}                   0",
            "#                  E                  nu",
            f"{_scientific(youngs_modulus_pa):>20}{_ratio(poisson_ratio):>20}",
            "/END",
            "",
        )
    )


@dataclass(frozen=True, slots=True)
class ReferenceOpenRadiossCardContent:
    """Typed immutable card snapshot; it deliberately has no generic card/options JSON payload."""

    material_model_id: UUID
    material_model_revision_id: UUID
    model_schema_digest: str
    solver_material_id: int
    card_title: str
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    source_yield_stress_pa: float | None
    applicable_temperature_min_k: float | None
    applicable_temperature_max_k: float | None
    applicable_strain_rate_min_per_s: float | None
    applicable_strain_rate_max_per_s: float | None
    density_mapping_status: MappingStatus
    youngs_modulus_mapping_status: MappingStatus
    poisson_ratio_mapping_status: MappingStatus
    source_yield_mapping_status: MappingStatus
    temperature_applicability_mapping_status: MappingStatus
    strain_rate_applicability_mapping_status: MappingStatus
    unit_system_mapping_status: MappingStatus
    mapping_report_sha256: str
    card_text: str
    card_sha256: str
    exporter_id: str = EXPORTER_ID
    exporter_version: str = EXPORTER_VERSION
    exporter_digest: str = EXPORTER_DIGEST
    target_solver: str = OPENRADIOSS_SOLVER
    target_version: str = OPENRADIOSS_VERSION
    target_unit_system: str = OPENRADIOSS_UNIT_SYSTEM
    non_production: bool = True

    def __post_init__(self) -> None:
        _nonzero("material_model_id", self.material_model_id)
        _nonzero("material_model_revision_id", self.material_model_revision_id)
        _sha256("model_schema_digest", self.model_schema_digest)
        if self.model_schema_digest != REFERENCE_MODEL_SCHEMA_DIGEST:
            raise InvalidExportRequest("reference card requires the reference model schema digest")
        _sha256("mapping_report_sha256", self.mapping_report_sha256)
        _sha256("card_sha256", self.card_sha256)
        _trimmed("card_title", self.card_title, 100)
        if "\n" in self.card_title or "\r" in self.card_title:
            raise InvalidExportRequest("card_title must be a single line")
        if not 1 <= self.solver_material_id <= 9_999_999_999:
            raise InvalidExportRequest("solver_material_id must be within 1..9999999999")
        _finite_positive("density_kg_per_m3", self.density_kg_per_m3)
        _finite_positive("youngs_modulus_pa", self.youngs_modulus_pa)
        if not math.isfinite(self.poisson_ratio) or not -1 < self.poisson_ratio < 0.5:
            raise InvalidExportRequest("poisson_ratio must remain within (-1, 0.5)")
        _optional_positive("source_yield_stress_pa", self.source_yield_stress_pa)
        for name, numeric_value in (
            ("applicable_temperature_min_k", self.applicable_temperature_min_k),
            ("applicable_temperature_max_k", self.applicable_temperature_max_k),
            ("applicable_strain_rate_min_per_s", self.applicable_strain_rate_min_per_s),
            ("applicable_strain_rate_max_per_s", self.applicable_strain_rate_max_per_s),
        ):
            if numeric_value is not None and (
                not math.isfinite(numeric_value) or numeric_value < 0
            ):
                raise InvalidExportRequest(f"{name} must be finite and non-negative when supplied")
        if (
            self.applicable_temperature_min_k is not None
            and self.applicable_temperature_max_k is not None
            and self.applicable_temperature_min_k > self.applicable_temperature_max_k
        ):
            raise InvalidExportRequest("applicable temperature bounds are inverted")
        if (
            self.applicable_strain_rate_min_per_s is not None
            and self.applicable_strain_rate_max_per_s is not None
            and self.applicable_strain_rate_min_per_s > self.applicable_strain_rate_max_per_s
        ):
            raise InvalidExportRequest("applicable strain-rate bounds are inverted")
        for name, mapping_status in (
            ("density_mapping_status", self.density_mapping_status),
            ("youngs_modulus_mapping_status", self.youngs_modulus_mapping_status),
            ("poisson_ratio_mapping_status", self.poisson_ratio_mapping_status),
            ("source_yield_mapping_status", self.source_yield_mapping_status),
            (
                "temperature_applicability_mapping_status",
                self.temperature_applicability_mapping_status,
            ),
            (
                "strain_rate_applicability_mapping_status",
                self.strain_rate_applicability_mapping_status,
            ),
            ("unit_system_mapping_status", self.unit_system_mapping_status),
        ):
            if mapping_status not in _VALID_MAPPING_STATUSES:
                raise InvalidExportRequest(f"{name} is not a recognized mapping status")
        if (
            self.exporter_id != EXPORTER_ID
            or self.exporter_version != EXPORTER_VERSION
            or self.exporter_digest != EXPORTER_DIGEST
        ):
            raise InvalidExportRequest("reference card must use the declared exporter identity")
        if (
            self.target_solver != OPENRADIOSS_SOLVER
            or self.target_version != OPENRADIOSS_VERSION
            or self.target_unit_system != OPENRADIOSS_UNIT_SYSTEM
        ):
            raise UnsupportedExportTarget("reference card supports only OpenRadioss 2025 kg_m_s")
        if not self.non_production:
            raise InvalidExportRequest("reference card must remain non-production")
        report = mapping_report_from_card_content(self)
        if report.digest != self.mapping_report_sha256:
            raise InvalidExportRequest("mapping_report_sha256 does not match typed card content")
        expected_statuses = {item.name: item.status for item in report.items}
        actual_statuses = {
            "density": self.density_mapping_status,
            "youngs_modulus": self.youngs_modulus_mapping_status,
            "poisson_ratio": self.poisson_ratio_mapping_status,
            "source_yield_stress": self.source_yield_mapping_status,
            "temperature_applicability": self.temperature_applicability_mapping_status,
            "strain_rate_applicability": self.strain_rate_applicability_mapping_status,
            "unit_system": self.unit_system_mapping_status,
        }
        if actual_statuses != expected_statuses:
            raise InvalidExportRequest("typed mapping statuses do not match the reference profile")
        expected_card_text = render_reference_openradioss_elast_card(
            material_model_id=self.material_model_id,
            material_model_revision_id=self.material_model_revision_id,
            report=report,
            solver_material_id=self.solver_material_id,
            card_title=self.card_title,
            density_kg_per_m3=self.density_kg_per_m3,
            youngs_modulus_pa=self.youngs_modulus_pa,
            poisson_ratio=self.poisson_ratio,
        )
        if self.card_text != expected_card_text:
            raise InvalidExportRequest("card_text does not match the declared reference mapping")
        if hashlib.sha256(self.card_text.encode("utf-8")).hexdigest() != self.card_sha256:
            raise InvalidExportRequest("card_sha256 does not match UTF-8 card_text")

    def canonical(self) -> dict[str, object]:
        return {
            "material_model_id": str(self.material_model_id),
            "material_model_revision_id": str(self.material_model_revision_id),
            "model_schema_digest": self.model_schema_digest,
            "target": {
                "solver": self.target_solver,
                "version": self.target_version,
                "unit_system": self.target_unit_system,
                "solver_material_id": self.solver_material_id,
                "card_title": self.card_title,
            },
            "density_kg_per_m3": self.density_kg_per_m3,
            "youngs_modulus_pa": self.youngs_modulus_pa,
            "poisson_ratio": self.poisson_ratio,
            "source_yield_stress_pa": self.source_yield_stress_pa,
            "applicability": {
                "temperature_min_k": self.applicable_temperature_min_k,
                "temperature_max_k": self.applicable_temperature_max_k,
                "strain_rate_min_per_s": self.applicable_strain_rate_min_per_s,
                "strain_rate_max_per_s": self.applicable_strain_rate_max_per_s,
            },
            "mapping_statuses": {
                "density": self.density_mapping_status,
                "youngs_modulus": self.youngs_modulus_mapping_status,
                "poisson_ratio": self.poisson_ratio_mapping_status,
                "source_yield": self.source_yield_mapping_status,
                "temperature_applicability": self.temperature_applicability_mapping_status,
                "strain_rate_applicability": self.strain_rate_applicability_mapping_status,
                "unit_system": self.unit_system_mapping_status,
            },
            "mapping_report_sha256": self.mapping_report_sha256,
            "card_text": self.card_text,
            "card_sha256": self.card_sha256,
            "exporter": {
                "id": self.exporter_id,
                "version": self.exporter_version,
                "digest": self.exporter_digest,
            },
            "non_production": self.non_production,
        }


def _content_from_report(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    source: ReferenceLinearElasticContent,
    report: ReferenceMappingReport,
    solver_material_id: int,
    card_title: str,
) -> ReferenceOpenRadiossCardContent:
    statuses = {item.name: item.status for item in report.items}
    card_text = render_reference_openradioss_elast_card(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        report=report,
        solver_material_id=solver_material_id,
        card_title=card_title,
        density_kg_per_m3=source.density_kg_per_m3,
        youngs_modulus_pa=source.youngs_modulus_pa,
        poisson_ratio=source.poisson_ratio,
    )
    return ReferenceOpenRadiossCardContent(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        model_schema_digest=REFERENCE_MODEL_SCHEMA_DIGEST,
        solver_material_id=solver_material_id,
        card_title=card_title,
        density_kg_per_m3=source.density_kg_per_m3,
        youngs_modulus_pa=source.youngs_modulus_pa,
        poisson_ratio=source.poisson_ratio,
        source_yield_stress_pa=source.source_yield_stress_pa,
        applicable_temperature_min_k=source.applicable_temperature_min_k,
        applicable_temperature_max_k=source.applicable_temperature_max_k,
        applicable_strain_rate_min_per_s=source.applicable_strain_rate_min_per_s,
        applicable_strain_rate_max_per_s=source.applicable_strain_rate_max_per_s,
        density_mapping_status=statuses["density"],
        youngs_modulus_mapping_status=statuses["youngs_modulus"],
        poisson_ratio_mapping_status=statuses["poisson_ratio"],
        source_yield_mapping_status=statuses["source_yield_stress"],
        temperature_applicability_mapping_status=statuses["temperature_applicability"],
        strain_rate_applicability_mapping_status=statuses["strain_rate_applicability"],
        unit_system_mapping_status=statuses["unit_system"],
        mapping_report_sha256=report.digest,
        card_text=card_text,
        card_sha256=hashlib.sha256(card_text.encode("utf-8")).hexdigest(),
    )


def mapping_report_from_card_content(
    content: ReferenceOpenRadiossCardContent,
) -> ReferenceMappingReport:
    """Reconstruct the stored report only from explicit immutable card columns."""

    target = ExportTarget(
        content.target_solver,
        content.target_version,
        content.target_unit_system,
    )
    return ReferenceMappingReport(
        material_model_id=content.material_model_id,
        material_model_revision_id=content.material_model_revision_id,
        model_schema_digest=content.model_schema_digest,
        target=target,
        items=_mapping_items(
            source_yield_stress_pa=content.source_yield_stress_pa,
            applicable_temperature_min_k=content.applicable_temperature_min_k,
            applicable_temperature_max_k=content.applicable_temperature_max_k,
            applicable_strain_rate_min_per_s=content.applicable_strain_rate_min_per_s,
            applicable_strain_rate_max_per_s=content.applicable_strain_rate_max_per_s,
            target=target,
        ),
        exporter_id=content.exporter_id,
        exporter_version=content.exporter_version,
        exporter_digest=content.exporter_digest,
        non_production=content.non_production,
    )


def build_reference_openradioss_card(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    source: ReferenceLinearElasticContent,
    target: ExportTarget,
    expected_mapping_report_sha256: str,
    solver_material_id: int,
    card_title: str,
) -> tuple[ReferenceMappingReport, ReferenceOpenRadiossCardContent]:
    """Validate an acknowledged preflight and build the immutable typed card content."""

    _sha256("expected_mapping_report_sha256", expected_mapping_report_sha256)
    report = preflight_reference_openradioss_elast(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        content=source,
        target=target,
    )
    if not report.exportable:
        raise UnsupportedExportTarget(
            "the selected target is not exportable by this reference exporter"
        )
    if report.digest != expected_mapping_report_sha256:
        raise MappingReportMismatch(
            "expected_mapping_report_sha256 does not acknowledge the current frozen mapping"
        )
    return report, _content_from_report(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        source=source,
        report=report,
        solver_material_id=solver_material_id,
        card_title=card_title,
    )


def exporter_capability_manifest() -> dict[str, object]:
    """Expose the narrow reference capability without registering a generic plugin abstraction."""

    return {
        "exporter_id": EXPORTER_ID,
        "exporter_version": EXPORTER_VERSION,
        "exporter_digest": f"sha256:{EXPORTER_DIGEST}",
        "non_production": True,
        "targets": [
            {
                "solver": OPENRADIOSS_SOLVER,
                "version": OPENRADIOSS_VERSION,
                "unit_system": OPENRADIOSS_UNIT_SYSTEM,
                "keyword": OPENRADIOSS_KEYWORD,
            }
        ],
        "supported_model_families": [
            {
                "id": REFERENCE_MODEL_FAMILY_ID,
                "schema_version": REFERENCE_MODEL_SCHEMA_VERSION,
                "schema_digest": f"sha256:{REFERENCE_MODEL_SCHEMA_DIGEST}",
            }
        ],
        "mapping_statuses": [
            "exact",
            "transformed",
            "approximated",
            "ignored",
            "unsupported",
            "not_applicable",
        ],
    }
