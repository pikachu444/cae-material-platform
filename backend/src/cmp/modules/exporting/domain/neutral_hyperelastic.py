"""Versioned solver mappings for the canonical T-56 hyperelastic Neutral Material IR."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily
from cmp.modules.modeling.domain.neutral_material import (
    NEUTRAL_HYPERELASTIC_IR_SCHEMA_DIGEST,
    NeutralHyperelasticIR,
    NeutralHyperelasticParameters,
    NeutralMaterialDocument,
)
from cmp.shared.domain.revisions import content_sha256

ABAQUS_SOLVER = "abaqus"
OPENRADIOSS_SOLVER = "openradioss"
REFERENCE_SOLVER_VERSION = "2025"
REFERENCE_UNIT_SYSTEM = "kg_m_s"
EXPORTER_VERSION = "1.0.0"
ABAQUS_EXPORTER_ID = "cmp.reference.abaqus-neutral-hyperelastic"
OPENRADIOSS_EXPORTER_ID = "cmp.reference.openradioss-neutral-hyperelastic"

ABAQUS_DOCUMENTATION = (
    "https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-hyperelastic.htm"
)
OPENRADIOSS_LAW82_DOCUMENTATION = (
    "https://2025.help.altair.com/2025/hwsolvers/rad/topics/solvers/rad/mat_law82_starter_r.htm"
)
OPENRADIOSS_LAW94_DOCUMENTATION = (
    "https://2025.help.altair.com/2025/hwsolvers/rad/topics/solvers/rad/mat_law94_starter_r.htm"
)

MappingStatus = Literal[
    "exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"
]
_STATUSES = frozenset(
    {"exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"}
)
_MATERIAL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")


def _hyperelastic_ir(source: NeutralMaterialDocument) -> NeutralHyperelasticIR:
    value = source.material_model_ir
    if not isinstance(value, NeutralHyperelasticIR):
        raise InvalidNeutralHyperelasticExport(
            "the hyperelastic exporter requires a hyperelastic Neutral Material IR"
        )
    if source.applicable_strain_min is None or source.applicable_strain_max is None:
        raise InvalidNeutralHyperelasticExport("hyperelastic strain applicability is required")
    return value


class NeutralHyperelasticExportError(Exception):
    pass


class InvalidNeutralHyperelasticExport(NeutralHyperelasticExportError, ValueError):
    pass


class NeutralHyperelasticMappingReportMismatch(NeutralHyperelasticExportError):
    pass


class NeutralHyperelasticSolverCardNotFound(NeutralHyperelasticExportError):
    pass


class NeutralHyperelasticSolverCardConflict(NeutralHyperelasticExportError):
    pass


@dataclass(frozen=True, slots=True)
class NeutralHyperelasticExportTarget:
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


def _keyword(target: NeutralHyperelasticExportTarget, family: HyperelasticFamily) -> str:
    if target.is_abaqus:
        return {
            HyperelasticFamily.NEO_HOOKEAN: "*HYPERELASTIC, NEO HOOKE",
            HyperelasticFamily.MOONEY_RIVLIN: "*HYPERELASTIC, MOONEY-RIVLIN",
            HyperelasticFamily.YEOH: "*HYPERELASTIC, YEOH",
            HyperelasticFamily.OGDEN_1: "*HYPERELASTIC, OGDEN, N=1",
        }[family]
    return (
        "/MAT/LAW94"
        if family in {HyperelasticFamily.NEO_HOOKEAN, HyperelasticFamily.YEOH}
        else "/MAT/LAW82"
    )


def _documentation(target: NeutralHyperelasticExportTarget, family: HyperelasticFamily) -> str:
    if target.is_abaqus:
        return ABAQUS_DOCUMENTATION
    return (
        OPENRADIOSS_LAW94_DOCUMENTATION
        if family in {HyperelasticFamily.NEO_HOOKEAN, HyperelasticFamily.YEOH}
        else OPENRADIOSS_LAW82_DOCUMENTATION
    )


@dataclass(frozen=True, slots=True)
class NeutralHyperelasticCapability:
    solver: str
    version: str
    unit_system: str
    family: HyperelasticFamily
    keyword: str
    documentation_url: str
    parameter_mapping: MappingStatus
    volumetric_mapping: MappingStatus

    def canonical(self) -> dict[str, object]:
        return {
            "target": {
                "solver": self.solver,
                "version": self.version,
                "unit_system": self.unit_system,
            },
            "family": self.family.value,
            "keyword": self.keyword,
            "documentation_url": self.documentation_url,
            "parameter_mapping": self.parameter_mapping,
            "volumetric_mapping": self.volumetric_mapping,
        }


def neutral_hyperelastic_capability_manifest() -> dict[str, object]:
    capabilities: list[NeutralHyperelasticCapability] = []
    for target in (
        NeutralHyperelasticExportTarget(ABAQUS_SOLVER, "2025", REFERENCE_UNIT_SYSTEM),
        NeutralHyperelasticExportTarget(OPENRADIOSS_SOLVER, "2025", REFERENCE_UNIT_SYSTEM),
    ):
        for family in HyperelasticFamily:
            parameter_status: MappingStatus = "exact"
            volumetric_status: MappingStatus = "exact"
            if target.is_openradioss and family in {
                HyperelasticFamily.NEO_HOOKEAN,
                HyperelasticFamily.MOONEY_RIVLIN,
            }:
                parameter_status = "transformed"
            if target.is_openradioss and family in {
                HyperelasticFamily.MOONEY_RIVLIN,
                HyperelasticFamily.OGDEN_1,
            }:
                volumetric_status = "approximated"
            capabilities.append(
                NeutralHyperelasticCapability(
                    target.solver,
                    target.version,
                    target.unit_system,
                    family,
                    _keyword(target, family),
                    _documentation(target, family),
                    parameter_status,
                    volumetric_status,
                )
            )
    payload = {
        "manifest_id": "cmp.reference.neutral-hyperelastic-capability",
        "manifest_version": EXPORTER_VERSION,
        "model_schema_digest": NEUTRAL_HYPERELASTIC_IR_SCHEMA_DIGEST,
        "mapping_statuses": sorted(_STATUSES),
        "capabilities": [item.canonical() for item in capabilities],
        "non_production": True,
    }
    return {**payload, "manifest_sha256": content_sha256(payload)}


def _exporter_digest(target: NeutralHyperelasticExportTarget) -> str:
    exporter_id = ABAQUS_EXPORTER_ID if target.is_abaqus else OPENRADIOSS_EXPORTER_ID
    return content_sha256(
        {
            "exporter_id": exporter_id,
            "exporter_version": EXPORTER_VERSION,
            "capability_manifest_sha256": neutral_hyperelastic_capability_manifest()[
                "manifest_sha256"
            ],
            "model_schema_digest": NEUTRAL_HYPERELASTIC_IR_SCHEMA_DIGEST,
            "non_production": True,
        }
    )


@dataclass(frozen=True, slots=True)
class NeutralHyperelasticMappingItem:
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
class NeutralHyperelasticMappingReport:
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    neutral_material_sha256: str
    family: HyperelasticFamily
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
            "model_schema_digest": NEUTRAL_HYPERELASTIC_IR_SCHEMA_DIGEST,
            "family": self.family.value,
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


def _mapping_items(
    target: NeutralHyperelasticExportTarget,
    family: HyperelasticFamily,
) -> tuple[NeutralHyperelasticMappingItem, ...]:
    if not target.supported:
        return (
            NeutralHyperelasticMappingItem(
                "target",
                "/target",
                None,
                "unsupported",
                "Only declared Abaqus 2025 and OpenRadioss 2025 kg-m-s targets are supported.",
            ),
        )
    parameter_status: MappingStatus = "exact"
    parameter_detail = "Typed family coefficients map without numerical change."
    if target.is_openradioss and family is HyperelasticFamily.NEO_HOOKEAN:
        parameter_status = "transformed"
        parameter_detail = "Neo-Hookean maps to LAW94 with C20=C30=0 by documented equivalence."
    elif target.is_openradioss and family is HyperelasticFamily.MOONEY_RIVLIN:
        parameter_status = "transformed"
        parameter_detail = (
            "C10/C01 map to LAW82 mu=(2*C10,2*C01), alpha=(2,-2) by exact "
            "strain-energy equivalence."
        )
    volumetric_status: MappingStatus = "exact"
    volumetric_detail = "The incompressible IR maps to explicit zero volumetric coefficients."
    if target.is_openradioss and family in {
        HyperelasticFamily.MOONEY_RIVLIN,
        HyperelasticFamily.OGDEN_1,
    }:
        volumetric_status = "approximated"
        volumetric_detail = (
            "LAW82 uses the explicit nu=0.495 nearly-incompressible convention; no silent "
            "default is used."
        )
    return (
        NeutralHyperelasticMappingItem(
            "density",
            "/material_model_ir/density",
            "density",
            "exact",
            "kg/m3 density is emitted unchanged.",
        ),
        NeutralHyperelasticMappingItem(
            "constitutive_parameters",
            "/material_model_ir/constitutive_model",
            _keyword(target, family),
            parameter_status,
            parameter_detail,
        ),
        NeutralHyperelasticMappingItem(
            "volumetric_response",
            "/material_model_ir/volumetric_response",
            "D coefficients or explicit LAW82 nu",
            volumetric_status,
            volumetric_detail,
        ),
        NeutralHyperelasticMappingItem(
            "applicability",
            "/applicability/engineering_strain",
            "card comments and mapping report",
            "transformed",
            "The fitted strain interval remains an explicit comment and sidecar field.",
        ),
        NeutralHyperelasticMappingItem(
            "calibration_evidence",
            "/candidate_selection",
            None,
            "not_applicable",
            "Calibration evidence stays in Neutral JSON and is not solver keyword data.",
        ),
        NeutralHyperelasticMappingItem(
            "unit_system",
            "/material_model_ir/*/unit",
            "consistent-unit convention",
            "transformed",
            "Solver syntax does not encode units; explicit kg-m-s comments are emitted.",
        ),
    )


def preflight_neutral_hyperelastic_export(
    *,
    neutral_material_id: UUID,
    neutral_material_revision_id: UUID,
    source: NeutralMaterialDocument,
    target: NeutralHyperelasticExportTarget,
) -> NeutralHyperelasticMappingReport:
    family = _hyperelastic_ir(source).parameters.family
    exporter_id = (
        ABAQUS_EXPORTER_ID
        if target.is_abaqus
        else OPENRADIOSS_EXPORTER_ID
        if target.is_openradioss
        else "cmp.reference.unsupported"
    )
    return NeutralHyperelasticMappingReport(
        neutral_material_id,
        neutral_material_revision_id,
        source.content_sha256,
        family,
        target,
        _mapping_items(target, family),
        exporter_id,
        EXPORTER_VERSION if target.supported else "0",
        _exporter_digest(target) if target.supported else "0" * 64,
        _documentation(target, family) if target.supported else "",
    )


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise InvalidNeutralHyperelasticExport("card values must be finite")
    return f"{value:.12e}"


def _parameter(parameters: NeutralHyperelasticParameters, name: str) -> float:
    value = getattr(parameters, name)
    if value is None:
        raise InvalidNeutralHyperelasticExport(f"{name} is absent from the typed family")
    return cast(float, value)


def _validate_output(solver_material_id: int, material_name: str) -> None:
    if not 1 <= solver_material_id <= 9_999_999_999:
        raise InvalidNeutralHyperelasticExport("solver_material_id is out of range")
    if _MATERIAL_NAME.fullmatch(material_name) is None:
        raise InvalidNeutralHyperelasticExport("material_name is invalid")


def render_abaqus_neutral_hyperelastic_card(
    *, material_name: str, source: NeutralMaterialDocument
) -> str:
    _validate_output(1, material_name)
    ir = _hyperelastic_ir(source)
    parameters = ir.parameters
    family = parameters.family
    values: tuple[float, ...]
    if family is HyperelasticFamily.NEO_HOOKEAN:
        values = (_parameter(parameters, "c10_pa"), 0.0)
    elif family is HyperelasticFamily.MOONEY_RIVLIN:
        values = (
            _parameter(parameters, "c10_pa"),
            _parameter(parameters, "c01_pa"),
            0.0,
        )
    elif family is HyperelasticFamily.YEOH:
        values = (
            _parameter(parameters, "c10_pa"),
            _parameter(parameters, "c20_pa"),
            _parameter(parameters, "c30_pa"),
            0.0,
            0.0,
            0.0,
        )
    else:
        values = (
            _parameter(parameters, "mu_pa"),
            _parameter(parameters, "alpha"),
            0.0,
        )
    lines = [
        "** CMP reference/non-production Neutral Material card",
        "** Consistent units: kg, m, s, Pa",
        (
            "** Validated only over engineering strain "
            f"[{source.applicable_strain_min:.12g}, {source.applicable_strain_max:.12g}]"
        ),
        f"*MATERIAL, NAME={material_name}",
        "*DENSITY",
        _number(ir.density_kg_per_m3),
        _keyword(NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s"), family),
        ", ".join(_number(item) for item in values),
    ]
    return "\n".join(lines) + "\n"


def render_openradioss_neutral_hyperelastic_card(
    *, solver_material_id: int, material_name: str, source: NeutralMaterialDocument
) -> str:
    _validate_output(solver_material_id, material_name)
    ir = _hyperelastic_ir(source)
    parameters = ir.parameters
    family = parameters.family
    common = [
        "# CMP reference/non-production Neutral Material card",
        "# Consistent units: kg, m, s, Pa",
        (
            "# Validated only over engineering strain "
            f"[{source.applicable_strain_min:.12g}, {source.applicable_strain_max:.12g}]"
        ),
    ]
    if family in {HyperelasticFamily.NEO_HOOKEAN, HyperelasticFamily.YEOH}:
        c10 = _parameter(parameters, "c10_pa")
        c20 = 0.0 if family is HyperelasticFamily.NEO_HOOKEAN else _parameter(parameters, "c20_pa")
        c30 = 0.0 if family is HyperelasticFamily.NEO_HOOKEAN else _parameter(parameters, "c30_pa")
        lines = [
            *common,
            f"/MAT/LAW94/{solver_material_id}/1",
            material_name,
            "#              RHO_I",
            _number(ir.density_kg_per_m3),
            "# Blank",
            "",
            "#                C10                 C20                 C30",
            " ".join(_number(item) for item in (c10, c20, c30)),
            "#                 D1                  D2                  D3",
            " ".join(_number(0.0) for _ in range(3)),
        ]
    else:
        mu: tuple[float, ...]
        alpha: tuple[float, ...]
        if family is HyperelasticFamily.MOONEY_RIVLIN:
            mu = (
                2.0 * _parameter(parameters, "c10_pa"),
                2.0 * _parameter(parameters, "c01_pa"),
            )
            alpha = (2.0, -2.0)
        else:
            mu = (_parameter(parameters, "mu_pa"),)
            alpha = (_parameter(parameters, "alpha"),)
        lines = [
            *common,
            "# nu=0.495 is an explicit acknowledged incompressibility approximation",
            f"/MAT/LAW82/{solver_material_id}/1",
            material_name,
            "#              RHO_I",
            _number(ir.density_kg_per_m3),
            "#        N                            Nu",
            f"{len(mu)} {_number(0.495)}",
            "#               Mu_i",
            " ".join(_number(item) for item in mu),
            "#            Alpha_i",
            " ".join(_number(item) for item in alpha),
            "#                D_i",
            " ".join(_number(0.0) for _ in mu),
        ]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class NeutralHyperelasticSolverCardContent:
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    neutral_material_sha256: str
    family: HyperelasticFamily
    target: NeutralHyperelasticExportTarget
    solver_material_id: int
    material_name: str
    density_kg_per_m3: float
    parameters: NeutralHyperelasticParameters
    applicable_strain_min: float
    applicable_strain_max: float
    mapping_statuses: tuple[tuple[str, MappingStatus], ...]
    mapping_report_sha256: str
    card_text: str
    card_sha256: str
    exporter_id: str
    exporter_version: str
    exporter_digest: str

    def canonical(self) -> dict[str, object]:
        return {
            "neutral_material_id": str(self.neutral_material_id),
            "neutral_material_revision_id": str(self.neutral_material_revision_id),
            "neutral_material_sha256": self.neutral_material_sha256,
            "model_schema_digest": NEUTRAL_HYPERELASTIC_IR_SCHEMA_DIGEST,
            "family": self.family.value,
            "target": {
                "solver": self.target.solver,
                "version": self.target.version,
                "unit_system": self.target.unit_system,
            },
            "solver_material_id": self.solver_material_id,
            "material_name": self.material_name,
            "density_kg_per_m3": self.density_kg_per_m3,
            "constitutive_model": self.parameters.canonical(),
            "applicability": {
                "engineering_strain": {
                    "minimum": self.applicable_strain_min,
                    "maximum": self.applicable_strain_max,
                    "unit": "1",
                }
            },
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


def build_neutral_hyperelastic_solver_card(
    *,
    neutral_material_id: UUID,
    neutral_material_revision_id: UUID,
    source: NeutralMaterialDocument,
    target: NeutralHyperelasticExportTarget,
    expected_mapping_report_sha256: str,
    solver_material_id: int,
    material_name: str,
) -> tuple[NeutralHyperelasticMappingReport, NeutralHyperelasticSolverCardContent]:
    report = preflight_neutral_hyperelastic_export(
        neutral_material_id=neutral_material_id,
        neutral_material_revision_id=neutral_material_revision_id,
        source=source,
        target=target,
    )
    if not report.exportable:
        raise InvalidNeutralHyperelasticExport("target is unsupported")
    if expected_mapping_report_sha256 != report.digest:
        raise NeutralHyperelasticMappingReportMismatch("mapping report digest is stale or absent")
    _validate_output(solver_material_id, material_name)
    ir = _hyperelastic_ir(source)
    assert source.applicable_strain_min is not None
    assert source.applicable_strain_max is not None
    card_text = (
        render_abaqus_neutral_hyperelastic_card(material_name=material_name, source=source)
        if target.is_abaqus
        else render_openradioss_neutral_hyperelastic_card(
            solver_material_id=solver_material_id,
            material_name=material_name,
            source=source,
        )
    )
    card = NeutralHyperelasticSolverCardContent(
        neutral_material_id,
        neutral_material_revision_id,
        source.content_sha256,
        ir.parameters.family,
        target,
        solver_material_id,
        material_name,
        ir.density_kg_per_m3,
        ir.parameters,
        source.applicable_strain_min,
        source.applicable_strain_max,
        tuple((item.name, item.status) for item in report.items),
        report.digest,
        card_text,
        hashlib.sha256(card_text.encode("utf-8")).hexdigest(),
        report.exporter_id,
        report.exporter_version,
        report.exporter_digest,
    )
    return report, card
