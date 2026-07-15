"""Explicit Abaqus and OpenRadioss mappings for the reference Ogden-Prony IR."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from cmp.modules.modeling.domain.reference_ogden_prony import (
    REFERENCE_OGDEN_PRONY_SCHEMA_DIGEST,
    ReferenceOgdenPronyContent,
    ReferenceShearPronyTerm,
)
from cmp.shared.domain.revisions import content_sha256

ABAQUS_SOLVER = "abaqus"
OPENRADIOSS_SOLVER = "openradioss"
REFERENCE_SOLVER_VERSION = "2025"
REFERENCE_UNIT_SYSTEM = "kg_m_s"
ABAQUS_EXPORTER_ID = "cmp.reference.abaqus-ogden-prony"
OPENRADIOSS_EXPORTER_ID = "cmp.reference.openradioss-law62"
EXPORTER_VERSION = "1.0.0"

MappingStatus = Literal[
    "exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"
]
_STATUSES = frozenset(
    {"exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"}
)
_MATERIAL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")


class OgdenPronyExportError(Exception):
    """Base error for the bounded hyper-viscoelastic exporters."""


class InvalidOgdenPronyExport(OgdenPronyExportError, ValueError):
    """The target or output request violates the reference contract."""


class OgdenPronyMappingReportMismatch(OgdenPronyExportError):
    """The caller did not acknowledge the current mapping report."""


class OgdenPronySolverCardNotFound(OgdenPronyExportError):
    """A card is unavailable in the active tenant scope."""


class OgdenPronySolverCardConflict(OgdenPronyExportError):
    """The immutable card request conflicts with its source or identity."""


def _sha256(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidOgdenPronyExport(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class OgdenPronyExportTarget:
    solver: str
    version: str
    unit_system: str

    @property
    def is_abaqus(self) -> bool:
        return (
            self.solver == ABAQUS_SOLVER
            and self.version == REFERENCE_SOLVER_VERSION
            and self.unit_system == REFERENCE_UNIT_SYSTEM
        )

    @property
    def is_openradioss(self) -> bool:
        return (
            self.solver == OPENRADIOSS_SOLVER
            and self.version == REFERENCE_SOLVER_VERSION
            and self.unit_system == REFERENCE_UNIT_SYSTEM
        )

    @property
    def supported(self) -> bool:
        return self.is_abaqus or self.is_openradioss


def _exporter_digest(exporter_id: str, keyword: str) -> str:
    return content_sha256(
        {
            "exporter_id": exporter_id,
            "exporter_version": EXPORTER_VERSION,
            "keyword": keyword,
            "model_schema_digest": REFERENCE_OGDEN_PRONY_SCHEMA_DIGEST,
            "mapping_statuses": sorted(_STATUSES),
            "non_production": True,
        }
    )


ABAQUS_EXPORTER_DIGEST = _exporter_digest(ABAQUS_EXPORTER_ID, "*HYPERELASTIC/*VISCOELASTIC")
OPENRADIOSS_EXPORTER_DIGEST = _exporter_digest(OPENRADIOSS_EXPORTER_ID, "/MAT/LAW62")


@dataclass(frozen=True, slots=True)
class OgdenPronyMappingItem:
    name: str
    ir_path: str
    target_representation: str | None
    status: MappingStatus
    detail: str

    def canonical(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ir_path": self.ir_path,
            "target_representation": self.target_representation,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class OgdenPronyMappingReport:
    material_model_id: UUID
    material_model_revision_id: UUID
    target: OgdenPronyExportTarget
    items: tuple[OgdenPronyMappingItem, ...]
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    model_schema_digest: str = REFERENCE_OGDEN_PRONY_SCHEMA_DIGEST
    non_production: bool = True

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
    target: OgdenPronyExportTarget,
) -> tuple[OgdenPronyMappingItem, ...]:
    if not target.supported:
        return (
            OgdenPronyMappingItem(
                "target",
                "/target",
                None,
                "unsupported",
                "Only Abaqus 2025 and OpenRadioss 2025 kg-m-s are declared by "
                "this reference family.",
            ),
        )
    common = (
        OgdenPronyMappingItem(
            "density", "/density_kg_per_m3", "density", "exact", "SI density is unchanged."
        ),
        OgdenPronyMappingItem(
            "ogden_term",
            "/ogden_terms/0",
            "Ogden N=1",
            "exact",
            "The one-term mu and alpha pair uses the pinned two-mu-over-alpha-squared potential.",
        ),
        OgdenPronyMappingItem(
            "shear_prony_terms",
            "/prony_terms",
            "normalized shear Prony terms",
            "exact",
            "Ordered shear ratios and relaxation times map without fitted defaults.",
        ),
        OgdenPronyMappingItem(
            "temperature_dependence",
            "/reference_temperature_k",
            None,
            "not_applicable",
            "The reference temperature is provenance only; no temperature shift law "
            "is represented.",
        ),
        OgdenPronyMappingItem(
            "unit_system",
            "/semantics/units",
            "solver consistent-unit convention",
            "transformed",
            "Solver syntax does not encode units; SI values are emitted with kg-m-s comments.",
        ),
    )
    if target.is_abaqus:
        volumetric = OgdenPronyMappingItem(
            "volumetric_response",
            "/volumetric_response",
            "D1=0",
            "exact",
            "The IR incompressible response maps to Abaqus D1=0.",
        )
    else:
        volumetric = OgdenPronyMappingItem(
            "volumetric_response",
            "/volumetric_response|law62_poisson_ratio",
            "LAW62 nu=0.495",
            "approximated",
            "LAW62 receives the acknowledged nearly-incompressible Poisson-ratio approximation.",
        )
    return (*common[:3], volumetric, *common[3:])


def preflight_reference_ogden_prony_export(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    source: ReferenceOgdenPronyContent,
    target: OgdenPronyExportTarget,
) -> OgdenPronyMappingReport:
    del source  # Its construction already validates the pinned IR invariants.
    if target.is_abaqus:
        exporter = (ABAQUS_EXPORTER_ID, ABAQUS_EXPORTER_DIGEST)
    elif target.is_openradioss:
        exporter = (OPENRADIOSS_EXPORTER_ID, OPENRADIOSS_EXPORTER_DIGEST)
    else:
        exporter = ("cmp.reference.unsupported", "0" * 64)
    return OgdenPronyMappingReport(
        material_model_id,
        material_model_revision_id,
        target,
        _mapping_items(target),
        exporter[0],
        EXPORTER_VERSION if target.supported else "0",
        exporter[1],
    )


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise InvalidOgdenPronyExport("card values must be finite")
    return f"{value:.12e}"


def _validate_name(material_name: str) -> None:
    if _MATERIAL_NAME.fullmatch(material_name) is None:
        raise InvalidOgdenPronyExport("material_name is invalid")


def render_abaqus_ogden_prony_card(
    *, material_name: str, source: ReferenceOgdenPronyContent
) -> str:
    _validate_name(material_name)
    lines = [
        "** CMP reference/non-production Ogden-Prony card",
        "** Consistent units: kg, m, s, Pa",
        "** Incompressible N=1 Ogden; instantaneous shear Prony convention",
        f"*MATERIAL, NAME={material_name}",
        "*DENSITY",
        _number(source.density_kg_per_m3),
        "*HYPERELASTIC, OGDEN, N=1, MODULI=INSTANTANEOUS",
        f"{_number(source.ogden_term.mu_pa)}, {_number(source.ogden_term.alpha)}, {_number(0.0)}",
        "*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC",
    ]
    lines.extend(
        f"{_number(term.g_ratio)}, {_number(0.0)}, {_number(term.relaxation_time_s)}"
        for term in source.prony_terms
    )
    return "\n".join(lines) + "\n"


def render_openradioss_law62_card(
    *, solver_material_id: int, material_name: str, source: ReferenceOgdenPronyContent
) -> str:
    _validate_name(material_name)
    if not 1 <= solver_material_id <= 9_999_999_999:
        raise InvalidOgdenPronyExport("solver_material_id is out of range")
    terms = source.prony_terms
    lines = [
        "# CMP reference/non-production LAW62 card",
        "# Consistent units: kg, m, s, Pa",
        "# nu=0.495 is an acknowledged incompressibility approximation",
        f"/MAT/LAW62/{solver_material_id}/1",
        material_name,
        "#              RHO_I",
        _number(source.density_kg_per_m3),
        "#                 NU         N         M              mu_max Flag_Visc      Form",
        (
            f"{_number(source.law62_poisson_ratio)}         1         {len(terms)} "
            f"{_number(0.0)}         0         1"
        ),
        "#                MU1",
        _number(source.ogden_term.mu_pa),
        "#             ALPHA1",
        _number(source.ogden_term.alpha),
        "# normalized shear relaxation ratios GAMMA_i",
        " ".join(_number(term.g_ratio) for term in terms),
        "# relaxation times TAU_i",
        " ".join(_number(term.relaxation_time_s) for term in terms),
    ]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class ReferenceOgdenPronySolverCardContent:
    material_model_id: UUID
    material_model_revision_id: UUID
    target: OgdenPronyExportTarget
    solver_material_id: int
    material_name: str
    density_kg_per_m3: float
    catalog_youngs_modulus_pa: float
    catalog_poisson_ratio: float
    ogden_mu_pa: float
    ogden_alpha: float
    law62_poisson_ratio: float
    prony_terms: tuple[ReferenceShearPronyTerm, ...]
    density_mapping_status: MappingStatus
    ogden_mapping_status: MappingStatus
    prony_mapping_status: MappingStatus
    volumetric_mapping_status: MappingStatus
    temperature_mapping_status: MappingStatus
    unit_system_mapping_status: MappingStatus
    mapping_report_sha256: str
    card_text: str
    card_sha256: str
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    model_schema_digest: str = REFERENCE_OGDEN_PRONY_SCHEMA_DIGEST
    non_production: bool = True

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
            "catalog_youngs_modulus_pa": self.catalog_youngs_modulus_pa,
            "catalog_poisson_ratio": self.catalog_poisson_ratio,
            "ogden_mu_pa": self.ogden_mu_pa,
            "ogden_alpha": self.ogden_alpha,
            "law62_poisson_ratio": self.law62_poisson_ratio,
            "prony_terms": [
                {
                    "ordinal": ordinal,
                    "g_ratio": term.g_ratio,
                    "relaxation_time_s": term.relaxation_time_s,
                }
                for ordinal, term in enumerate(self.prony_terms, 1)
            ],
            "mapping_statuses": {
                "density": self.density_mapping_status,
                "ogden_term": self.ogden_mapping_status,
                "shear_prony_terms": self.prony_mapping_status,
                "volumetric_response": self.volumetric_mapping_status,
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


def build_reference_ogden_prony_solver_card(
    *,
    material_model_id: UUID,
    material_model_revision_id: UUID,
    source: ReferenceOgdenPronyContent,
    target: OgdenPronyExportTarget,
    expected_mapping_report_sha256: str,
    solver_material_id: int,
    material_name: str,
) -> tuple[OgdenPronyMappingReport, ReferenceOgdenPronySolverCardContent]:
    report = preflight_reference_ogden_prony_export(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        source=source,
        target=target,
    )
    if not report.exportable:
        raise InvalidOgdenPronyExport("target is unsupported for the Ogden-Prony family")
    if expected_mapping_report_sha256 != report.digest:
        raise OgdenPronyMappingReportMismatch("mapping report digest is stale or absent")
    if target.is_abaqus:
        card_text = render_abaqus_ogden_prony_card(material_name=material_name, source=source)
    else:
        card_text = render_openradioss_law62_card(
            solver_material_id=solver_material_id,
            material_name=material_name,
            source=source,
        )
    statuses = {item.name: item.status for item in report.items}
    card = ReferenceOgdenPronySolverCardContent(
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        target=target,
        solver_material_id=solver_material_id,
        material_name=material_name,
        density_kg_per_m3=source.density_kg_per_m3,
        catalog_youngs_modulus_pa=source.catalog_youngs_modulus_pa,
        catalog_poisson_ratio=source.catalog_poisson_ratio,
        ogden_mu_pa=source.ogden_term.mu_pa,
        ogden_alpha=source.ogden_term.alpha,
        law62_poisson_ratio=source.law62_poisson_ratio,
        prony_terms=source.prony_terms,
        density_mapping_status=statuses["density"],
        ogden_mapping_status=statuses["ogden_term"],
        prony_mapping_status=statuses["shear_prony_terms"],
        volumetric_mapping_status=statuses["volumetric_response"],
        temperature_mapping_status=statuses["temperature_dependence"],
        unit_system_mapping_status=statuses["unit_system"],
        mapping_report_sha256=report.digest,
        card_text=card_text,
        card_sha256=hashlib.sha256(card_text.encode("utf-8")).hexdigest(),
        exporter_id=report.exporter_id,
        exporter_version=report.exporter_version,
        exporter_digest=report.exporter_digest,
    )
    _sha256("card_sha256", card.card_sha256)
    return report, card
