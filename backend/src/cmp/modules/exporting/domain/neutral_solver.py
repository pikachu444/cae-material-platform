"""T-64 family-neutral solver mappings from exact Neutral Material revisions.

The T-57 rate-independent hyperelastic contract remains byte-for-byte compatible.  This module
dispatches that legacy path unchanged and adds explicit metal, linear-viscoelastic, and
hyper-viscoelastic projections without selecting a latest revision or inventing missing data.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from cmp.modules.exporting.domain.neutral_hyperelastic import (
    ABAQUS_DOCUMENTATION,
    InvalidNeutralHyperelasticExport,
    MappingStatus,
    NeutralHyperelasticExportTarget,
    NeutralHyperelasticMappingItem,
    NeutralHyperelasticMappingReport,
    NeutralHyperelasticMappingReportMismatch,
    NeutralHyperelasticSolverCardContent,
    build_neutral_hyperelastic_solver_card,
    preflight_neutral_hyperelastic_export,
    render_abaqus_neutral_hyperelastic_card,
)
from cmp.modules.exporting.domain.reference_isotropic_tabulated_plasticity import (
    ABAQUS_PLASTIC_EXPORTER_ID,
    ABAQUS_PLASTIC_EXPORTER_VERSION,
    OPENRADIOSS_LAW36_EXPORTER_ID,
    OPENRADIOSS_LAW36_EXPORTER_VERSION,
    render_reference_abaqus_plastic_card,
    render_reference_openradioss_law36_card,
)
from cmp.modules.exporting.domain.reference_linear_viscoelasticity import (
    ABAQUS_PRONY_EXPORTER_ID,
    ABAQUS_PRONY_EXPORTER_VERSION,
    render_abaqus_linear_viscoelastic_card,
)
from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily
from cmp.modules.modeling.domain.neutral_material import (
    CurveStage,
    EvidenceStatus,
    NeutralArtifactReference,
    NeutralElastoplasticIR,
    NeutralHyperelasticIR,
    NeutralHyperelasticParameters,
    NeutralLinearViscoelasticIR,
    NeutralMaterialDocument,
    NeutralModelFamily,
    NeutralPronyTerm,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    HardeningCurvePoint,
    HardeningPointOrigin,
    validate_hardening_curve,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
)
from cmp.shared.domain.revisions import content_sha256

type NeutralMappingReport = NeutralHyperelasticMappingReport | NeutralFamilyMappingReport
type NeutralCardContent = NeutralHyperelasticSolverCardContent | NeutralFamilySolverCardContent

GENERIC_EXPORTER_VERSION = "2.0.0"
ABAQUS_PLASTIC_DOCUMENTATION = (
    "https://docs.software.vt.edu/abaqusv2024/English/SIMACAEKEYRefMap/simakey-r-plastic.htm"
)
ABAQUS_VISCOELASTIC_DOCUMENTATION = (
    "https://docs.software.vt.edu/abaqusv2024/English/SIMACAEKEYRefMap/simakey-r-viscoelastic.htm"
)
OPENRADIOSS_LAW36_DOCUMENTATION = (
    "https://help.altair.com/hwsolvers/rad/topics/solvers/rad/mat_law36_plas_tab_starter_r.htm"
)
OPENRADIOSS_LAW62_DOCUMENTATION = (
    "https://2025.help.altair.com/2025/hwsolvers/rad/topics/solvers/rad/mat_law62_starter_r.htm"
)


def _model_family(source: NeutralMaterialDocument) -> NeutralModelFamily:
    return source.material_model_ir.family


def _family_label(source: NeutralMaterialDocument) -> str:
    ir = source.material_model_ir
    if isinstance(ir, NeutralHyperelasticIR):
        return ir.parameters.family.value
    return ir.family.value


def _documentation(source: NeutralMaterialDocument, target: NeutralHyperelasticExportTarget) -> str:
    ir = source.material_model_ir
    if isinstance(ir, NeutralElastoplasticIR):
        return ABAQUS_PLASTIC_DOCUMENTATION if target.is_abaqus else OPENRADIOSS_LAW36_DOCUMENTATION
    if isinstance(ir, NeutralLinearViscoelasticIR):
        return ABAQUS_VISCOELASTIC_DOCUMENTATION
    if isinstance(ir, NeutralHyperelasticIR) and ir.prony_overlay is not None:
        return (
            ABAQUS_VISCOELASTIC_DOCUMENTATION
            if target.is_abaqus
            else OPENRADIOSS_LAW62_DOCUMENTATION
        )
    return ABAQUS_DOCUMENTATION


def _exporter_identity(
    source: NeutralMaterialDocument, target: NeutralHyperelasticExportTarget
) -> tuple[str, str, str]:
    ir = source.material_model_ir
    if isinstance(ir, NeutralElastoplasticIR):
        exporter_id = (
            ABAQUS_PLASTIC_EXPORTER_ID if target.is_abaqus else OPENRADIOSS_LAW36_EXPORTER_ID
        )
        version = (
            ABAQUS_PLASTIC_EXPORTER_VERSION
            if target.is_abaqus
            else OPENRADIOSS_LAW36_EXPORTER_VERSION
        )
    elif isinstance(ir, NeutralLinearViscoelasticIR):
        exporter_id, version = ABAQUS_PRONY_EXPORTER_ID, ABAQUS_PRONY_EXPORTER_VERSION
    else:
        exporter_id = (
            "cmp.reference.abaqus-neutral-hyper-viscoelastic"
            if target.is_abaqus
            else "cmp.reference.openradioss-neutral-law62"
        )
        version = GENERIC_EXPORTER_VERSION
    digest = content_sha256(
        {
            "exporter_id": exporter_id,
            "exporter_version": version,
            "model_family": _model_family(source).value,
            "model_schema_digest": ir.model_schema_digest,
            "target": {
                "solver": target.solver,
                "version": target.version,
                "unit_system": target.unit_system,
            },
            "non_production": True,
        }
    )
    return exporter_id, version, digest


@dataclass(frozen=True, slots=True)
class NeutralFamilyMappingReport:
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    neutral_material_sha256: str
    model_family: NeutralModelFamily
    family: str
    model_schema_digest: str
    target: NeutralHyperelasticExportTarget
    items: tuple[NeutralHyperelasticMappingItem, ...]
    exporter_id: str
    exporter_version: str
    exporter_digest: str
    documentation_url: str

    @property
    def exportable(self) -> bool:
        return not any(item.status in {"unsupported", "ignored"} for item in self.items)

    def canonical(self) -> dict[str, object]:
        return {
            "neutral_material_id": str(self.neutral_material_id),
            "neutral_material_revision_id": str(self.neutral_material_revision_id),
            "neutral_material_sha256": self.neutral_material_sha256,
            "model_family": self.model_family.value,
            "family": self.family,
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
                "documentation_url": self.documentation_url,
            },
            "non_production": True,
        }

    @property
    def digest(self) -> str:
        return content_sha256(self.canonical())


def _item(
    name: str, path: str, target: str | None, status: MappingStatus, detail: str
) -> NeutralHyperelasticMappingItem:
    return NeutralHyperelasticMappingItem(name, path, target, status, detail)


def _unsupported(detail: str) -> tuple[NeutralHyperelasticMappingItem, ...]:
    return (_item("target", "/target", None, "unsupported", detail),)


def _metal_items(
    target: NeutralHyperelasticExportTarget,
) -> tuple[NeutralHyperelasticMappingItem, ...]:
    if not target.supported:
        return _unsupported("Only Abaqus 2025 and OpenRadioss 2025 kg-m-s are declared.")
    abaqus = target.is_abaqus
    return (
        _item(
            "density",
            "/material_model_ir/density",
            "*DENSITY" if abaqus else "/MAT/LAW36/RHO_I",
            "exact",
            "SI density is emitted unchanged.",
        ),
        _item(
            "isotropic_elasticity",
            "/material_model_ir/constitutive_model/parameters",
            "*ELASTIC" if abaqus else "/MAT/LAW36/E,nu",
            "exact",
            "Young's modulus and Poisson ratio map directly.",
        ),
        _item(
            "initial_yield",
            "/material_model_ir/constitutive_model/parameters/initial_yield_stress",
            "*PLASTIC first row" if abaqus else "/FUNCT first point",
            "transformed",
            "The zero-plastic-strain anchor becomes the first hardening row.",
        ),
        _item(
            "isotropic_hardening_curve",
            "/curve_stages/fitted|extrapolated",
            "*PLASTIC" if abaqus else "/FUNCT",
            "transformed",
            "Exact Neutral curve stages are rendered as native ASCII rows.",
        ),
        _item(
            "post_necking_extension",
            "/material_model_ir/constitutive_model/extrapolation",
            "EXTRAPOLATION=CONSTANT" if abaqus else "/FUNCT final point",
            "approximated",
            "The acknowledged bounded extension is emitted through its final point.",
        ),
        _item(
            "temperature_dependence",
            "/applicability/temperature",
            None,
            "not_applicable",
            "This bounded Neutral model has no temperature dependency.",
        ),
        _item(
            "strain_rate_dependence",
            "/applicability/strain_rate",
            None,
            "not_applicable",
            "This bounded Neutral model is rate-independent.",
        ),
        _item(
            "unit_system",
            "/material_model_ir/*/unit",
            "kg-m-s comment" if abaqus else "/UNIT/1",
            "transformed" if abaqus else "exact",
            "Native syntax uses the declared kg-m-s convention.",
        ),
    )


def _linear_viscoelastic_items(
    target: NeutralHyperelasticExportTarget, ir: NeutralLinearViscoelasticIR
) -> tuple[NeutralHyperelasticMappingItem, ...]:
    if not target.is_abaqus:
        return _unsupported(
            "Generalized-Maxwell Neutral IR is declared only for Abaqus 2025; "
            "OpenRadioss LAW62 requires a hyperelastic Ogden base."
        )
    bulk_status: MappingStatus = (
        "exact" if ir.bulk_relaxation_status == "characterized" else "not_applicable"
    )
    return (
        _item(
            "density",
            "/material_model_ir/density",
            "*DENSITY",
            "exact",
            "SI density is emitted unchanged.",
        ),
        _item(
            "instantaneous_isotropic_elasticity",
            "/material_model_ir/constitutive_model/parameters",
            "*ELASTIC",
            "exact",
            "Instantaneous Young's modulus and Poisson ratio map directly.",
        ),
        _item(
            "shear_prony_terms",
            "/material_model_ir/constitutive_model/terms",
            "*VISCOELASTIC, TIME=PRONY",
            "exact",
            "Ordered shear ratios and relaxation times map directly.",
        ),
        _item(
            "bulk_relaxation",
            "/material_model_ir/constitutive_model/terms/*/k_ratio",
            "*VISCOELASTIC second field",
            bulk_status,
            "Bulk ratios remain explicit, including uncharacterized zero data.",
        ),
        _item(
            "temperature_dependence",
            "/material_model_ir/reference_temperature",
            None,
            "not_applicable",
            "Reference temperature is applicability evidence, not a shift table.",
        ),
        _item(
            "unit_system",
            "/material_model_ir/*/unit",
            "Abaqus consistent-unit comment",
            "transformed",
            "Abaqus syntax omits units; SI remains explicit in the sidecar.",
        ),
    )


def _hyper_viscoelastic_items(
    target: NeutralHyperelasticExportTarget, ir: NeutralHyperelasticIR
) -> tuple[NeutralHyperelasticMappingItem, ...]:
    overlay = ir.prony_overlay
    assert overlay is not None
    if not target.supported:
        return _unsupported("Only Abaqus 2025 and OpenRadioss 2025 kg-m-s are declared.")
    if target.is_openradioss and ir.parameters.family is not HyperelasticFamily.OGDEN_1:
        return _unsupported(
            "OpenRadioss Prony overlay is declared only for one-term Ogden LAW62; "
            "no silent conversion from another potential is allowed."
        )
    base = (
        _item(
            "density",
            "/material_model_ir/density",
            "*DENSITY" if target.is_abaqus else "/MAT/LAW62/RHO_I",
            "exact",
            "SI density is emitted unchanged.",
        ),
        _item(
            "constitutive_parameters",
            "/material_model_ir/constitutive_model",
            "*HYPERELASTIC" if target.is_abaqus else "/MAT/LAW62 Ogden",
            "exact",
            "Reviewed hyperelastic coefficients map without refitting.",
        ),
        _item(
            "shear_prony_overlay",
            "/material_model_ir/prony_overlay/terms",
            "*VISCOELASTIC, TIME=PRONY" if target.is_abaqus else "/MAT/LAW62 GAMMA_i,TAU_i",
            "exact",
            "Ordered terms from the exact baseline revision map directly.",
        ),
        _item(
            "bulk_relaxation",
            "/material_model_ir/prony_overlay/terms/*/k_ratio",
            "*VISCOELASTIC second field" if target.is_abaqus else None,
            "exact"
            if target.is_abaqus and any(term.k_ratio > 0 for term in overlay.terms)
            else "not_applicable",
            "Bulk ratios are explicit; LAW62 invents no bulk relaxation terms.",
        ),
        _item(
            "volumetric_response",
            "/material_model_ir/volumetric_response",
            "D coefficients" if target.is_abaqus else "LAW62 nu=0.495",
            "exact" if target.is_abaqus else "approximated",
            "LAW62 uses acknowledged nearly-incompressible behavior."
            if target.is_openradioss
            else "Incompressibility maps to explicit zero volumetric coefficients.",
        ),
        _item(
            "applicability",
            "/applicability/engineering_strain",
            "card comments and sidecar",
            "transformed",
            "The fitted strain interval remains explicit provenance.",
        ),
        _item(
            "unit_system",
            "/material_model_ir/*/unit",
            "consistent-unit comment",
            "transformed",
            "Solver syntax omits some units; kg-m-s remains explicit.",
        ),
    )
    return base


def preflight_neutral_solver_export(
    *,
    neutral_material_id: UUID,
    neutral_material_revision_id: UUID,
    source: NeutralMaterialDocument,
    target: NeutralHyperelasticExportTarget,
) -> NeutralMappingReport:
    ir = source.material_model_ir
    if isinstance(ir, NeutralHyperelasticIR) and ir.prony_overlay is None:
        return preflight_neutral_hyperelastic_export(
            neutral_material_id=neutral_material_id,
            neutral_material_revision_id=neutral_material_revision_id,
            source=source,
            target=target,
        )
    if isinstance(ir, NeutralElastoplasticIR):
        items = _metal_items(target)
    elif isinstance(ir, NeutralLinearViscoelasticIR):
        items = _linear_viscoelastic_items(target, ir)
    else:
        assert isinstance(ir, NeutralHyperelasticIR)
        items = _hyper_viscoelastic_items(target, ir)
    supported = not any(item.status == "unsupported" for item in items)
    exporter = (
        _exporter_identity(source, target)
        if supported
        else ("cmp.reference.unsupported", "0", "0" * 64)
    )
    return NeutralFamilyMappingReport(
        neutral_material_id,
        neutral_material_revision_id,
        source.content_sha256,
        ir.family,
        _family_label(source),
        ir.model_schema_digest,
        target,
        items,
        exporter[0],
        exporter[1],
        exporter[2],
        _documentation(source, target) if supported else "",
    )


def _hardening_points(source: NeutralMaterialDocument) -> tuple[HardeningCurvePoint, ...]:
    ir = cast(NeutralElastoplasticIR, source.material_model_ir)
    stages = {
        curve.stage: curve
        for curve in source.curves
        if curve.x_quantity == "strain.true_plastic"
        and curve.y_quantity == "stress.hardening.selected"
    }
    fitted = stages.get(CurveStage.FITTED)
    extension = stages.get(CurveStage.EXTRAPOLATED)
    if fitted is None or extension is None:
        raise InvalidNeutralHyperelasticExport(
            "metal Neutral export requires fitted and extrapolated hardening stages"
        )
    points = tuple(
        HardeningCurvePoint(x, y, HardeningPointOrigin.PROCESSING_SELECTED_SAMPLE)
        for x, y in zip(fitted.x, fitted.y, strict=True)
    ) + tuple(
        HardeningCurvePoint(x, y, HardeningPointOrigin.PROCESSING_SELECTED_SAMPLE)
        for x, y in zip(extension.x, extension.y, strict=True)
    )
    if points[0].true_plastic_strain > 0:
        points = (
            HardeningCurvePoint(
                0.0, ir.initial_yield_stress_pa, HardeningPointOrigin.CATALOG_YIELD_ANCHOR
            ),
            *points,
        )
    validate_hardening_curve(points)
    if len(points) != ir.hardening_curve.point_count:
        raise InvalidNeutralHyperelasticExport(
            "Neutral hardening stages do not reproduce the exact curve point count"
        )
    return points


def _linear_source(source: NeutralMaterialDocument) -> ReferenceLinearViscoelasticContent:
    ir = cast(NeutralLinearViscoelasticIR, source.material_model_ir)
    return ReferenceLinearViscoelasticContent(
        material_id=source.material.object_id,
        material_revision_id=source.material.revision_id,
        material_state_id=source.material_state.object_id,
        material_state_revision_id=source.material_state.revision_id,
        property_set_id=source.property_set.object_id,
        property_set_revision_id=source.property_set.revision_id,
        density_kg_per_m3=ir.density_kg_per_m3,
        youngs_modulus_pa=ir.youngs_modulus_pa,
        poisson_ratio=ir.poisson_ratio,
        bulk_relaxation_status=BulkRelaxationStatus(ir.bulk_relaxation_status),
        terms=tuple(
            PronyTerm(term.g_ratio, term.k_ratio, term.relaxation_time_s) for term in ir.terms
        ),
        reference_temperature_k=ir.reference_temperature_k,
    )


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise InvalidNeutralHyperelasticExport("card values must be finite")
    return f"{value:.12e}"


def _render_hyper_viscoelastic(
    source: NeutralMaterialDocument,
    target: NeutralHyperelasticExportTarget,
    solver_material_id: int,
    material_name: str,
) -> str:
    ir = cast(NeutralHyperelasticIR, source.material_model_ir)
    overlay = ir.prony_overlay
    assert overlay is not None and overlay.status is EvidenceStatus.EXACT_REVISION
    if target.is_abaqus:
        base = render_abaqus_neutral_hyperelastic_card(material_name=material_name, source=source)
        return (
            base
            + "*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC\n"
            + "".join(
                f"{_number(term.g_ratio)}, {_number(term.k_ratio)}, "
                f"{_number(term.relaxation_time_s)}\n"
                for term in overlay.terms
            )
        )
    parameters = ir.parameters
    if parameters.family is not HyperelasticFamily.OGDEN_1:
        raise InvalidNeutralHyperelasticExport("OpenRadioss Prony export requires Ogden N=1")
    assert parameters.mu_pa is not None and parameters.alpha is not None
    lines = [
        "# CMP reference/non-production Neutral LAW62 card",
        "# Consistent units: kg, m, s, Pa",
        "# nu=0.495 is an acknowledged incompressibility approximation",
        f"/MAT/LAW62/{solver_material_id}/1",
        material_name,
        "#              RHO_I",
        _number(ir.density_kg_per_m3),
        "#                 NU         N         M              mu_max Flag_Visc      Form",
        (
            f"{_number(0.495)}         1         {len(overlay.terms)} "
            f"{_number(0.0)}         0         1"
        ),
        "#                MU1",
        _number(parameters.mu_pa),
        "#             ALPHA1",
        _number(parameters.alpha),
        "# normalized shear relaxation ratios GAMMA_i",
        " ".join(_number(term.g_ratio) for term in overlay.terms),
        "# relaxation times TAU_i",
        " ".join(_number(term.relaxation_time_s) for term in overlay.terms),
    ]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class NeutralFamilySolverCardContent:
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    neutral_material_sha256: str
    model_family: NeutralModelFamily
    family: str
    model_schema_digest: str
    target: NeutralHyperelasticExportTarget
    solver_material_id: int
    material_name: str
    density_kg_per_m3: float
    hyperelastic_parameters: NeutralHyperelasticParameters | None
    youngs_modulus_pa: float | None
    poisson_ratio: float | None
    initial_yield_stress_pa: float | None
    hardening_curve: NeutralArtifactReference | None
    prony_terms: tuple[NeutralPronyTerm, ...]
    bulk_relaxation_status: str | None
    reference_temperature_k: float | None
    applicable_strain_min: float | None
    applicable_strain_max: float | None
    applicable_time_min_s: float | None
    applicable_time_max_s: float | None
    mapping_statuses: tuple[tuple[str, MappingStatus], ...]
    mapping_report_sha256: str
    card_text: str
    card_sha256: str
    exporter_id: str
    exporter_version: str
    exporter_digest: str

    def canonical(self) -> dict[str, object]:
        constitutive: dict[str, object] = {"family": self.family}
        if self.hyperelastic_parameters is not None:
            constitutive["parameters"] = self.hyperelastic_parameters.canonical()["parameters"]
        elif self.model_family is NeutralModelFamily.ISOTROPIC_TABULATED_PLASTICITY:
            constitutive["parameters"] = {
                "youngs_modulus_pa": self.youngs_modulus_pa,
                "poisson_ratio": self.poisson_ratio,
                "initial_yield_stress_pa": self.initial_yield_stress_pa,
            }
            assert self.hardening_curve is not None
            constitutive["hardening_curve"] = self.hardening_curve.canonical()
        else:
            constitutive["parameters"] = {
                "youngs_modulus_pa": self.youngs_modulus_pa,
                "poisson_ratio": self.poisson_ratio,
                "bulk_relaxation_status": self.bulk_relaxation_status,
                "reference_temperature_k": self.reference_temperature_k,
            }
        if self.prony_terms:
            constitutive["prony_terms"] = [term.canonical() for term in self.prony_terms]
        applicability: dict[str, object] = {}
        if self.applicable_strain_min is not None:
            applicability["engineering_strain"] = {
                "minimum": self.applicable_strain_min,
                "maximum": self.applicable_strain_max,
                "unit": "1",
            }
        if self.applicable_time_min_s is not None:
            applicability["time"] = {
                "minimum": self.applicable_time_min_s,
                "maximum": self.applicable_time_max_s,
                "unit": "s",
            }
        return {
            "neutral_material_id": str(self.neutral_material_id),
            "neutral_material_revision_id": str(self.neutral_material_revision_id),
            "neutral_material_sha256": self.neutral_material_sha256,
            "model_family": self.model_family.value,
            "model_schema_digest": self.model_schema_digest,
            "family": self.family,
            "target": {
                "solver": self.target.solver,
                "version": self.target.version,
                "unit_system": self.target.unit_system,
            },
            "solver_material_id": self.solver_material_id,
            "material_name": self.material_name,
            "density_kg_per_m3": self.density_kg_per_m3,
            "constitutive_model": constitutive,
            "applicability": applicability,
            "mapping_statuses": dict(self.mapping_statuses),
            "mapping_report_sha256": self.mapping_report_sha256,
            "card_sha256": self.card_sha256,
            "exporter": {
                "id": self.exporter_id,
                "version": self.exporter_version,
                "digest": self.exporter_digest,
            },
            "non_production": True,
        }


def build_neutral_solver_card(
    *,
    neutral_material_id: UUID,
    neutral_material_revision_id: UUID,
    source: NeutralMaterialDocument,
    target: NeutralHyperelasticExportTarget,
    expected_mapping_report_sha256: str,
    solver_material_id: int,
    material_name: str,
) -> tuple[NeutralMappingReport, NeutralCardContent]:
    ir = source.material_model_ir
    if isinstance(ir, NeutralHyperelasticIR) and ir.prony_overlay is None:
        return build_neutral_hyperelastic_solver_card(
            neutral_material_id=neutral_material_id,
            neutral_material_revision_id=neutral_material_revision_id,
            source=source,
            target=target,
            expected_mapping_report_sha256=expected_mapping_report_sha256,
            solver_material_id=solver_material_id,
            material_name=material_name,
        )
    report = cast(
        NeutralFamilyMappingReport,
        preflight_neutral_solver_export(
            neutral_material_id=neutral_material_id,
            neutral_material_revision_id=neutral_material_revision_id,
            source=source,
            target=target,
        ),
    )
    if not report.exportable:
        raise InvalidNeutralHyperelasticExport("target is unsupported for this Neutral family")
    if report.digest != expected_mapping_report_sha256:
        raise NeutralHyperelasticMappingReportMismatch("mapping report digest is stale or absent")
    if not 1 <= solver_material_id <= 9_999_999_999:
        raise InvalidNeutralHyperelasticExport("solver_material_id is out of range")
    youngs_modulus_pa: float | None
    poisson_ratio: float | None
    initial_yield_stress_pa: float | None
    if isinstance(ir, NeutralElastoplasticIR):
        points = _hardening_points(source)
        card_text = (
            render_reference_abaqus_plastic_card(
                material_model_revision_id=neutral_material_revision_id,
                mapping_report_sha256=report.digest,
                material_name=material_name,
                density_kg_per_m3=ir.density_kg_per_m3,
                youngs_modulus_pa=ir.youngs_modulus_pa,
                poisson_ratio=ir.poisson_ratio,
                points=points,
            )
            if target.is_abaqus
            else render_reference_openradioss_law36_card(
                material_model_revision_id=neutral_material_revision_id,
                mapping_report_sha256=report.digest,
                solver_material_id=solver_material_id,
                material_name=material_name,
                density_kg_per_m3=ir.density_kg_per_m3,
                youngs_modulus_pa=ir.youngs_modulus_pa,
                poisson_ratio=ir.poisson_ratio,
                points=points,
            )
        )
        hyperelastic_parameters = None
        youngs_modulus_pa, poisson_ratio = ir.youngs_modulus_pa, ir.poisson_ratio
        initial_yield_stress_pa, hardening_curve = ir.initial_yield_stress_pa, ir.hardening_curve
        prony_terms: tuple[NeutralPronyTerm, ...] = ()
        bulk_status = None
        reference_temperature_k = None
    elif isinstance(ir, NeutralLinearViscoelasticIR):
        card_text = render_abaqus_linear_viscoelastic_card(
            material_name=material_name, source=_linear_source(source)
        )
        hyperelastic_parameters = None
        youngs_modulus_pa, poisson_ratio = ir.youngs_modulus_pa, ir.poisson_ratio
        initial_yield_stress_pa = None
        hardening_curve = None
        prony_terms = ir.terms
        bulk_status = ir.bulk_relaxation_status
        reference_temperature_k = ir.reference_temperature_k
    else:
        assert isinstance(ir, NeutralHyperelasticIR)
        card_text = _render_hyper_viscoelastic(source, target, solver_material_id, material_name)
        hyperelastic_parameters = ir.parameters
        youngs_modulus_pa = poisson_ratio = initial_yield_stress_pa = None
        hardening_curve = None
        assert ir.prony_overlay is not None
        prony_terms = ir.prony_overlay.terms
        bulk_status = None
        reference_temperature_k = None
    content = NeutralFamilySolverCardContent(
        neutral_material_id,
        neutral_material_revision_id,
        source.content_sha256,
        ir.family,
        _family_label(source),
        ir.model_schema_digest,
        target,
        solver_material_id,
        material_name,
        ir.density_kg_per_m3,
        hyperelastic_parameters,
        youngs_modulus_pa,
        poisson_ratio,
        initial_yield_stress_pa,
        hardening_curve,
        prony_terms,
        bulk_status,
        reference_temperature_k,
        source.applicable_strain_min,
        source.applicable_strain_max,
        source.applicable_time_min_s,
        source.applicable_time_max_s,
        tuple((item.name, item.status) for item in report.items),
        report.digest,
        card_text,
        hashlib.sha256(card_text.encode("utf-8")).hexdigest(),
        report.exporter_id,
        report.exporter_version,
        report.exporter_digest,
    )
    return report, content


def neutral_solver_capability_manifest() -> dict[str, object]:
    payload = {
        "manifest_id": "cmp.reference.neutral-solver-capability",
        "manifest_version": GENERIC_EXPORTER_VERSION,
        "mapping_statuses": [
            "approximated",
            "exact",
            "ignored",
            "not_applicable",
            "transformed",
            "unsupported",
        ],
        "families": {
            "isotropic_tabulated_plasticity": {"abaqus": "exact", "openradioss": "exact"},
            "generalized_maxwell": {"abaqus": "exact", "openradioss": "unsupported"},
            "hyperelastic": {"abaqus": "exact", "openradioss": "family_dependent"},
            "hyperelastic_prony_overlay": {"abaqus": "exact", "openradioss": "ogden_1_only"},
        },
        "non_production": True,
    }
    return {**payload, "manifest_sha256": content_sha256(payload)}
