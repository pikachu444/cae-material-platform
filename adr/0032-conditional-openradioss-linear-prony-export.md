# ADR-0032: Conditional OpenRadioss linear-Prony export

- Status: Accepted
- Date: 2026-07-19
- Deciders: CMP maintainers
- Related: ADR-0029, ADR-0031, T-55P, T-64, T-67, T-68

## Context

CMP already promotes a reviewed generalized-Maxwell Processing Output into a typed linear-
viscoelastic IR and canonical Neutral Material JSON. Abaqus maps that IR directly to
`*VISCOELASTIC, TIME=PRONY`. OpenRadioss LAW62 is a finite-strain hyperelastic material and must not
be used as a silent replacement for a linear-elastic generalized-Maxwell model.

OpenRadioss also publishes `/VISC/LPRONY`, an isotropic Prony-series add-on for total-strain solid
formulations. Its Form 2 consumes instantaneous rigidity, and `flag_visc=2` applies relaxation to the
deviatoric response only. The published equations use `GAMMA_i = G_i/G_0` and `TAU_i`, which are the
same normalized shear terms stored by the CMP Neutral IR. The keyword requires a compatible solid
property using total-strain formulation `I_smstr=10` or `12`; an incompatible base material or
formulation causes the viscosity to be ignored.

## Decision

CMP adds a bounded, non-production OpenRadioss 2025 kg-m-s reference export consisting of
`/MAT/LAW1` plus `/VISC/LPRONY` only when all of these conditions hold:

1. the Neutral family is `generalized_maxwell`;
2. `bulk_relaxation_status` is `not_characterized` and every `k_ratio` is zero;
3. the instantaneous Poisson ratio is at least `0.49` and less than `0.5`;
4. every stored shear ratio and relaxation time already satisfies the Neutral IR constraints.

The exporter uses LPRONY Form 2 and `flag_visc=2`. It does not refit, renormalize, add bulk terms, or
convert the model to LAW62. Density, instantaneous Young's modulus and Poisson ratio are emitted in
LAW1; ordered `g_ratio`/`relaxation_time_s` values are emitted as `GAMMA_i`/`TAU_i`.

The mapping report marks the nearly-incompressible deviatoric-only interpretation and the external
`I_smstr=10 or 12` solid-property prerequisite as `approximated`. The connected UI therefore requires
explicit acknowledgement before card creation. The report links the official LPRONY documentation.
If any eligibility condition fails, preflight returns `unsupported` and no card can be generated.

The resulting `.rad` is a material/viscosity fragment. It does not create or silently modify a
`/PROP` card, and it is not evidence of solver validation or production qualification.

## Consequences

- Existing compressible polymer records remain explicitly unsupported for OpenRadioss.
- Nearly-incompressible shear-relaxation records can generate an auditable native ASCII reference
  fragment from the same exact Neutral revision used for Abaqus.
- Bulk-viscoelastic OpenRadioss support remains absent until a separately modeled and verified path
  exists.
- Solver execution and numerical result comparison remain outside the current product scope.

## Public references

- [OpenRadioss `/VISC/LPRONY`](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/visc_lprony_starter_r.htm)
- [OpenRadioss `/MAT/LAW1`](https://2024.help.altair.com/2024/hwsolvers/rad/topics/solvers/rad/mat_law1_elast_starter_r.htm)
- [OpenRadioss solid property `I_smstr`](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/prop_type14_solid_starter_r.htm)
