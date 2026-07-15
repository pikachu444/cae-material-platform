# ADR-0023: bounded Ogden–Prony IR and LAW62 mapping

- Status: Accepted
- Date: 2026-07-16
- Scope: P2 product vertical, reference/non-production

## Context

Steel remains represented by the separate rate-independent isotropic elastoplastic family. Polymer
linear relaxation remains represented by the separate generalized-Maxwell/linear-Prony family.
Neither contract can be silently reused for finite-strain elastomer hyper-viscoelasticity or
OpenRadioss LAW62.

The product needs a small but executable elastomer vertical: save one solver-neutral model,
inspect every mapping disposition, and download an Abaqus or OpenRadioss card. The mapping must be
independently derived from public solver documentation and must not imply solver qualification.

## Decision

1. Add a separate `urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0` family for explicitly
   `elastomer` Material revisions only.
2. Limit the reference model to one Ogden term, one to five ordered normalized shear-Prony terms,
   an instantaneous-modulus convention, temperature-independent response, and an incompressible
   volumetric response.
3. Keep Catalog E and ν only as pinned source-property provenance. Ogden μ/α and each Prony term
   are stored in explicit immutable relational tables; they are not encoded as EAV or an opaque
   JSON payload.
4. Abaqus 2025 uses `*HYPERELASTIC, OGDEN, N=1, MODULI=INSTANTANEOUS`, `D1=0`, followed by
   `*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC`. The incompressible volumetric mapping is `exact`.
5. OpenRadioss 2025 uses `/MAT/LAW62` with `N=1`, `M=term_count`, `Flag_Visc=0`, `Form=1`, the
   pinned Ogden μ/α, and normalized γ/τ pairs. Since LAW62 receives ν=0.495 instead of the IR's
   exact incompressibility, volumetric response is always `approximated` and cannot be hidden.
6. Card creation requires the exact current preflight SHA-256. Both cards are immutable revisions
   linked to the exact source model revision, with byte SHA-256, preview, download, and golden
   regression fixtures.
7. This is a reference/non-production mapping. External solver execution, numerical equivalence,
   version qualification, temperature dependence, compressible Ogden data, multiple Ogden terms,
   and production parameter calibration are excluded.

## Public mapping basis

- [Abaqus 2024 `*HYPERELASTIC`](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEKEYRefMap/simakey-r-hyperelastic.htm)
- [Abaqus time-domain viscoelasticity](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEMATRefMap/simamat-c-timevisco.htm)
- [Abaqus `*VISCOELASTIC`](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEKEYRefMap/simakey-r-viscoelastic.htm)
- [OpenRadioss 2025 `/MAT/LAW62`](https://2025.help.altair.com/2025/hwsolvers/rad/topics/solvers/rad/mat_law62_visc_hyp_starter_r.htm)

## Consequences

- Linear-Prony cards cannot be routed to LAW62.
- LAW62 users see and acknowledge the ν=0.495 approximation before card creation.
- Abaqus and OpenRadioss outputs share one immutable IR but retain distinct exporter identities,
  manifests, mapping reports, card identities, and byte fixtures.
- A future compressible or calibrated hyper-viscoelastic family requires a new schema decision;
  this reference schema is not widened in place.
