"""Explicit Abaqus time-domain mapping for the reference linear Prony IR."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST,
    BulkRelaxationStatus,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
)
from cmp.shared.domain.revisions import content_sha256

ABAQUS_SOLVER = "abaqus"
ABAQUS_VERSION = "2025"
ABAQUS_UNIT_SYSTEM = "kg_m_s"
ABAQUS_PRONY_EXPORTER_ID = "cmp.reference.abaqus-linear-prony"
ABAQUS_PRONY_EXPORTER_VERSION = "1.0.0"

MappingStatus = Literal[
    "exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"
]
_STATUSES = frozenset(
    {"exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"}
)
_MATERIAL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")


class LinearViscoelasticExportError(Exception):
    """Base error for the bounded Abaqus Prony exporter."""


class InvalidLinearViscoelasticExport(LinearViscoelasticExportError, ValueError):
    """The target, material name, or output request is invalid."""


class LinearViscoelasticMappingReportMismatch(LinearViscoelasticExportError):
    """The caller did not acknowledge the exact current mapping report."""


class LinearViscoelasticSolverCardNotFound(LinearViscoelasticExportError):
    """A card or revision is unavailable in the active tenant scope."""


class LinearViscoelasticSolverCardConflict(LinearViscoelasticExportError):
    """The stable identity or immutable source precondition conflicts."""


def _sha256(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidLinearViscoelasticExport(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class LinearViscoelasticExportTarget:
    solver: str
    version: str
    unit_system: str

    def __post_init__(self) -> None:
        for name, value in (
            ("solver", self.solver),
            ("version", self.version),
            ("unit_system", self.unit_system),
        ):
            if not value or value != value.strip() or len(value) > 64 or "\x00" in value:
                raise InvalidLinearViscoelasticExport(f"{name} must contain 1..64 characters")

    @property
    def is_abaqus(self) -> bool:
        return (
            self.solver == ABAQUS_SOLVER
            and self.version == ABAQUS_VERSION
            and self.unit_system == ABAQUS_UNIT_SYSTEM
        )


def _exporter_digest() -> str:
    return content_sha256(
        {
            "exporter_id": ABAQUS_PRONY_EXPORTER_ID,
            "exporter_version": ABAQUS_PRONY_EXPORTER_VERSION,
            "target": {
                "solver": ABAQUS_SOLVER,
                "version": ABAQUS_VERSION,
                "unit_system": ABAQUS_UNIT_SYSTEM,
                "keywords": ["*MATERIAL", "*DENSITY", "*ELASTIC", "*VISCOELASTIC"],
                "viscoelastic_parameters": ["TIME=PRONY", "TYPE=ISOTROPIC"],
                "data_order": ["g_ratio", "k_ratio", "relaxation_time_s"],
            },
            "model_schema_digest": REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST,
            "mapping_statuses": sorted(_STATUSES),
            "non_production": True,
        }
    )


ABAQUS_PRONY_EXPORTER_DIGEST = _exporter_digest()


@dataclass(frozen=True, slots=True)
class LinearViscoelasticMappingItem:
    name: str
    ir_path: str
    target_representation: str | None
    status: MappingStatus
    detail: str

    def __post_init__(self) -> None:
        if not self.name or not self.ir_path or not self.detail:
            raise InvalidLinearViscoelasticExport("mapping item fields must be non-empty")
        if self.status not in _STATUSES:
            raise InvalidLinearViscoelasticExport("mapping item status is not declared")

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ir_path": self.ir_path,
            "target_representation": self.target_representation,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class LinearViscoelasticMappingReport:
    material_model_id: UUID
    material_model_revision_id: UUID
    target: LinearViscoelasticExportTarget
    items: tuple[LinearViscoelasticMappingItem, ...]
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    model_schema_digest: str = REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
    non_production: bool = True

    def __post_init__(self) -> None:
        if self.material_model_id.int == 0 or self.material_model_revision_id.int == 0:
            raise InvalidLinearViscoelasticExport("model references must be non-zero")
        _sha256("model_schema_digest", self.model_schema_digest)
        _sha256("exporter_digest", self.exporter_digest)
        if not self.items or len({item.name for item in self.items}) != len(self.items):
            raise InvalidLinearViscoelasticExport("mapping items must be non-empty and unique")
        expected = (
            ABAQUS_PRONY_EXPORTER_ID,
            ABAQUS_PRONY_EXPORTER_VERSION,
            ABAQUS_PRONY_EXPORTER_DIGEST,
        )
        unsupported = ("cmp.reference.unsupported", "0", "0" * 64)
        actual = (self.exporter_id, self.exporter_version, self.exporter_digest)
        if actual != (expected if self.target.is_abaqus else unsupported):
            raise InvalidLinearViscoelasticExport("exporter does not own the target")
        if self.model_schema_digest != REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST:
            raise InvalidLinearViscoelasticExport("model schema digest is not exportable")

    @property
    def exportable(self) -> bool:
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


def _mapping_items(
    target: LinearViscoelasticExportTarget,
    source: ReferenceLinearViscoelasticContent,
) -> tuple[LinearViscoelasticMappingItem, ...]:
    if not target.is_abaqus:
        return (
            LinearViscoelasticMappingItem(
                "target",
                "/target",
                None,
                "unsupported",
                "The linear Prony IR supports only Abaqus 2025 kg_m_s; OpenRadioss LAW62 "
                "requires the separate Ogden-Prony hyper-viscoelastic family.",
            ),
        )
    bulk_status: MappingStatus = (
        "exact"
        if source.bulk_relaxation_status is BulkRelaxationStatus.CHARACTERIZED
        else "not_applicable"
    )
    bulk_detail = (
        "Characterized bulk ratios map directly to the second Prony data field."
        if bulk_status == "exact"
        else "Bulk relaxation was explicitly not characterized; every emitted k ratio is zero."
    )
    return (
        LinearViscoelasticMappingItem(
            "density",
            "/density_kg_per_m3",
            "*DENSITY",
            "exact",
            "SI density is emitted without numeric approximation.",
        ),
        LinearViscoelasticMappingItem(
            "instantaneous_isotropic_elasticity",
            "/youngs_modulus_pa|poisson_ratio",
            "*ELASTIC",
            "exact",
            "The IR declares the Catalog elastic moduli as instantaneous.",
        ),
        LinearViscoelasticMappingItem(
            "shear_prony_terms",
            "/terms/*/g_ratio|relaxation_time_s",
            "*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC",
            "exact",
            "Shear ratios and SI relaxation times map directly in ordinal order.",
        ),
        LinearViscoelasticMappingItem(
            "bulk_relaxation",
            "/bulk_relaxation_status|terms/*/k_ratio",
            "*VISCOELASTIC second data field",
            bulk_status,
            bulk_detail,
        ),
        LinearViscoelasticMappingItem(
            "temperature_dependence",
            "/applicability/temperature",
            None,
            "not_applicable",
            "Temperature is an applicability range, not a dependency table.",
        ),
        LinearViscoelasticMappingItem(
            "unit_system",
            "/semantics/units",
            "Abaqus consistent-unit comment",
            "transformed",
            "Abaqus keywords do not encode units; SI values are emitted under kg-m-s comments.",
        ),
    )


def preflight_reference_linear_viscoelastic_export(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    source: ReferenceLinearViscoelasticContent,
    target: LinearViscoelasticExportTarget,
) -> LinearViscoelasticMappingReport:
    exporter = (
        (ABAQUS_PRONY_EXPORTER_ID, ABAQUS_PRONY_EXPORTER_VERSION, ABAQUS_PRONY_EXPORTER_DIGEST)
        if target.is_abaqus
        else ("cmp.reference.unsupported", "0", "0" * 64)
    )
    return LinearViscoelasticMappingReport(
        material_model_id,
        material_model_revision_id,
        target,
        _mapping_items(target, source),
        exporter[0],
        exporter[1],
        exporter[2],
    )


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise InvalidLinearViscoelasticExport("card values must be finite")
    return f"{value:.12e}"


def render_abaqus_linear_viscoelastic_card(
    *, material_name: str, source: ReferenceLinearViscoelasticContent
) -> str:
    if _MATERIAL_NAME.fullmatch(material_name) is None:
        raise InvalidLinearViscoelasticExport(
            "material_name must start with a letter and contain only letters, digits, _ or -"
        )
    lines = [
        "** CMP reference/non-production linear-viscoelastic card",
        "** Consistent units: kg, m, s, Pa",
        f"** Bulk relaxation evidence: {source.bulk_relaxation_status.value}",
        f"*MATERIAL, NAME={material_name}",
        "*DENSITY",
        _number(source.density_kg_per_m3),
        "*ELASTIC",
        f"{_number(source.youngs_modulus_pa)}, {_number(source.poisson_ratio)}",
        "*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC",
    ]
    lines.extend(
        f"{_number(term.g_ratio)}, {_number(term.k_ratio)}, {_number(term.relaxation_time_s)}"
        for term in source.terms
    )
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class ReferenceLinearViscoelasticSolverCardContent:
    material_model_id: UUID
    material_model_revision_id: UUID
    target: LinearViscoelasticExportTarget
    solver_material_id: int
    material_name: str
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    bulk_relaxation_status: BulkRelaxationStatus
    terms: tuple[PronyTerm, ...]
    density_mapping_status: MappingStatus
    elasticity_mapping_status: MappingStatus
    prony_terms_mapping_status: MappingStatus
    bulk_mapping_status: MappingStatus
    temperature_mapping_status: MappingStatus
    unit_system_mapping_status: MappingStatus
    mapping_report_sha256: str
    card_text: str
    card_sha256: str
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    model_schema_digest: str = REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
    non_production: bool = True

    def __post_init__(self) -> None:
        if self.material_model_id.int == 0 or self.material_model_revision_id.int == 0:
            raise InvalidLinearViscoelasticExport("model references must be non-zero")
        if not self.target.is_abaqus:
            raise InvalidLinearViscoelasticExport("stored linear Prony cards must target Abaqus")
        if not 1 <= self.solver_material_id <= 9_999_999_999:
            raise InvalidLinearViscoelasticExport("solver_material_id is out of range")
        if _MATERIAL_NAME.fullmatch(self.material_name) is None:
            raise InvalidLinearViscoelasticExport("material_name is invalid")
        _sha256("mapping_report_sha256", self.mapping_report_sha256)
        _sha256("card_sha256", self.card_sha256)
        _sha256("exporter_digest", self.exporter_digest)
        _sha256("model_schema_digest", self.model_schema_digest)
        if hashlib.sha256(self.card_text.encode("utf-8")).hexdigest() != self.card_sha256:
            raise InvalidLinearViscoelasticExport("card_sha256 does not match card_text bytes")
        if (
            self.exporter_id != ABAQUS_PRONY_EXPORTER_ID
            or self.exporter_version != ABAQUS_PRONY_EXPORTER_VERSION
            or self.exporter_digest != ABAQUS_PRONY_EXPORTER_DIGEST
            or self.model_schema_digest != REFERENCE_LINEAR_VISCOELASTIC_SCHEMA_DIGEST
            or self.non_production is not True
        ):
            raise InvalidLinearViscoelasticExport("stored exporter contract is invalid")
        expected_statuses: tuple[MappingStatus, ...] = (
            "exact",
            "exact",
            "exact",
            (
                "exact"
                if self.bulk_relaxation_status is BulkRelaxationStatus.CHARACTERIZED
                else "not_applicable"
            ),
            "not_applicable",
            "transformed",
        )
        actual_statuses = (
            self.density_mapping_status,
            self.elasticity_mapping_status,
            self.prony_terms_mapping_status,
            self.bulk_mapping_status,
            self.temperature_mapping_status,
            self.unit_system_mapping_status,
        )
        if actual_statuses != expected_statuses:
            raise InvalidLinearViscoelasticExport(
                "stored mapping statuses differ from the Abaqus target contract"
            )
        # Reuse the IR invariants for the exact card projection.
        ReferenceLinearViscoelasticContent(
            material_id=UUID(int=1),
            material_revision_id=UUID(int=2),
            material_state_id=UUID(int=3),
            material_state_revision_id=UUID(int=4),
            property_set_id=UUID(int=5),
            property_set_revision_id=UUID(int=6),
            density_kg_per_m3=self.density_kg_per_m3,
            youngs_modulus_pa=self.youngs_modulus_pa,
            poisson_ratio=self.poisson_ratio,
            bulk_relaxation_status=self.bulk_relaxation_status,
            terms=self.terms,
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
            "solver_material_id": self.solver_material_id,
            "material_name": self.material_name,
            "density_kg_per_m3": self.density_kg_per_m3,
            "youngs_modulus_pa": self.youngs_modulus_pa,
            "poisson_ratio": self.poisson_ratio,
            "bulk_relaxation_status": self.bulk_relaxation_status.value,
            "terms": [
                {
                    "ordinal": ordinal,
                    "g_ratio": term.g_ratio,
                    "k_ratio": term.k_ratio,
                    "relaxation_time_s": term.relaxation_time_s,
                }
                for ordinal, term in enumerate(self.terms, 1)
            ],
            "mapping_statuses": {
                "density": self.density_mapping_status,
                "instantaneous_isotropic_elasticity": self.elasticity_mapping_status,
                "shear_prony_terms": self.prony_terms_mapping_status,
                "bulk_relaxation": self.bulk_mapping_status,
                "temperature_dependence": self.temperature_mapping_status,
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


def build_reference_linear_viscoelastic_solver_card(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    source: ReferenceLinearViscoelasticContent,
    target: LinearViscoelasticExportTarget,
    expected_mapping_report_sha256: str,
    solver_material_id: int,
    material_name: str,
) -> tuple[LinearViscoelasticMappingReport, ReferenceLinearViscoelasticSolverCardContent]:
    report = preflight_reference_linear_viscoelastic_export(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        source=source,
        target=target,
    )
    if not report.exportable:
        raise InvalidLinearViscoelasticExport("target is unsupported for the linear Prony family")
    if expected_mapping_report_sha256 != report.digest:
        raise LinearViscoelasticMappingReportMismatch("mapping report digest is stale or absent")
    if not 1 <= solver_material_id <= 9_999_999_999:
        raise InvalidLinearViscoelasticExport("solver_material_id is out of range")
    card_text = render_abaqus_linear_viscoelastic_card(material_name=material_name, source=source)
    statuses = {item.name: item.status for item in report.items}
    return report, ReferenceLinearViscoelasticSolverCardContent(
        material_model_id,
        material_model_revision_id,
        target,
        solver_material_id,
        material_name,
        source.density_kg_per_m3,
        source.youngs_modulus_pa,
        source.poisson_ratio,
        source.bulk_relaxation_status,
        source.terms,
        statuses["density"],
        statuses["instantaneous_isotropic_elasticity"],
        statuses["shear_prony_terms"],
        statuses["bulk_relaxation"],
        statuses["temperature_dependence"],
        statuses["unit_system"],
        report.digest,
        card_text,
        hashlib.sha256(card_text.encode("utf-8")).hexdigest(),
        report.exporter_id,
        report.exporter_version,
        report.exporter_digest,
    )
