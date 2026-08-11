"""Explicit Unit Profile applications for the bounded kg-m-s solver exporters."""

from __future__ import annotations

from cmp.modules.modeling.domain.neutral_material import (
    NeutralElastoplasticIR,
    NeutralHyperelasticIR,
    NeutralLinearViscoelasticIR,
    NeutralMaterialDocument,
)
from cmp.modules.units.domain.profiles import (
    UnitApplication,
    UnitApplicationRole,
    UnitProfileContent,
    applications_for_profile,
)
from cmp.modules.units.domain.system import KG_M_S_COMPATIBILITY_UNITS, DimensionId, UnitError


def neutral_solver_unit_applications(
    source: NeutralMaterialDocument,
    profile: UnitProfileContent,
) -> tuple[UnitApplication, ...]:
    """Resolve only quantities the existing kg-m-s cards actually emit.

    Poisson ratio, Prony ratios, and Ogden alpha remain ordinary dimensionless
    parameters.  They are deliberately not relabelled as strain.
    """

    uses: list[tuple[str, UnitApplicationRole, str, DimensionId]] = [
        (
            "solver_card.density",
            UnitApplicationRole.SOLVER_EXPORT,
            "mass.density",
            DimensionId.MASS_PER_VOLUME,
        )
    ]
    model = source.material_model_ir
    if isinstance(model, NeutralHyperelasticIR):
        uses.extend(
            (
                (
                    "solver_card.constitutive_parameters",
                    UnitApplicationRole.SOLVER_EXPORT,
                    "hyperelastic.coefficient",
                    DimensionId.FORCE_PER_AREA,
                ),
                (
                    "solver_card.applicability.engineering_strain",
                    UnitApplicationRole.SOLVER_EXPORT,
                    "strain.engineering",
                    DimensionId.STRAIN,
                ),
            )
        )
        if model.prony_overlay is not None and model.prony_overlay.terms:
            uses.append(
                (
                    "solver_card.prony.relaxation_time",
                    UnitApplicationRole.SOLVER_EXPORT,
                    "time.relaxation",
                    DimensionId.TIME,
                )
            )
    elif isinstance(model, NeutralElastoplasticIR):
        uses.extend(
            (
                (
                    "solver_card.elastic.youngs_modulus",
                    UnitApplicationRole.SOLVER_EXPORT,
                    "modulus.young",
                    DimensionId.FORCE_PER_AREA,
                ),
                (
                    "solver_card.hardening.stress",
                    UnitApplicationRole.SOLVER_EXPORT,
                    "stress.true",
                    DimensionId.FORCE_PER_AREA,
                ),
                (
                    "solver_card.hardening.true_plastic_strain",
                    UnitApplicationRole.SOLVER_EXPORT,
                    "strain.true_plastic",
                    DimensionId.STRAIN,
                ),
            )
        )
    elif isinstance(model, NeutralLinearViscoelasticIR):
        uses.extend(
            (
                (
                    "solver_card.elastic.youngs_modulus",
                    UnitApplicationRole.SOLVER_EXPORT,
                    "modulus.young",
                    DimensionId.FORCE_PER_AREA,
                ),
                (
                    "solver_card.prony.relaxation_time",
                    UnitApplicationRole.SOLVER_EXPORT,
                    "time.relaxation",
                    DimensionId.TIME,
                ),
            )
        )
    else:  # pragma: no cover - the Neutral document union is closed above
        raise UnitError(
            code="CMP-UNIT-0006",
            message="Neutral Material family has no common-unit export contract",
            location="solver_card.material_model_ir",
        )
    applications = applications_for_profile(profile, uses=tuple(uses))
    for application in applications:
        required = KG_M_S_COMPATIBILITY_UNITS[application.dimension]
        if application.unit_id != required:
            raise UnitError(
                code="CMP-UNIT-0006",
                message=(
                    "the existing solver-card contract supports only the explicit kg_m_s "
                    f"unit {required} at {application.location}"
                ),
                location=application.location,
                source_dimension=application.dimension,
                target_dimension=application.dimension,
            )
    return applications


__all__ = ["neutral_solver_unit_applications"]
