# ADR-0020: Route Material workflows by governed class and deliver polymer viscoelasticity in two stages

- Status: Accepted
- Date: 2026-07-15
- Related: ADR-0005, ADR-0006, ADR-0018, ADR-0019; T-07, T-D01, T-D02, T-D03

## Context

The product is a Material data management and CAE-use platform, not an MCalibration clone.
The implemented vertical already supports typed basic properties, tensile data processing,
reference elastoplastic IRs, and OpenRadioss/Abaqus cards. It does not yet distinguish a steel
workflow from polymer or elastomer workflows at the Material revision boundary.

A single small-strain Prony representation maps naturally to Abaqus time-domain viscoelasticity,
but it is not semantically equivalent to OpenRadioss `/MAT/LAW62`, which requires a hyperelastic
base. Treating both as one card would create a silent constitutive approximation.

## Decision

1. Add `material_class` to Material schema v2 with `unclassified`, `metal`, `polymer`,
   `elastomer`, `composite`, `ceramic`, and `other` values.
2. Preserve every v1 revision unchanged. A missing stored class is read as `unclassified`; an
   explicit reclassification is a new Material revision.
3. Material class recommends compatible workflows but never selects a model or exporter by
   inference. Exact IR family, exporter capability, target version, unit system, and mapping
   preflight remain authoritative.
4. Keep the existing steel path: `metal` plus tabulated-plasticity IR can produce the bounded
   OpenRadioss LAW36 and Abaqus isotropic-plasticity reference cards.
5. Deliver polymer viscoelasticity in two independent stages:
   - a solver-neutral linear generalized-Maxwell/Prony IR and Abaqus time-domain card;
   - an Ogden-Prony hyper-viscoelastic IR for Abaqus and OpenRadioss LAW62.
6. Never project the linear Prony IR to LAW62. That target is reported as `unsupported`.
7. Use shear relaxation CSV (`time`, `relaxation shear modulus`) as the first calibration input.
   Bulk relaxation is never inferred from constant Poisson ratio. Missing bulk evidence is an
   explicit `not_characterized` model disposition and an acknowledged approximation where valid.
8. These implementations remain `reference/non-production` until numeric IR schemas, formulas,
   golden cards, and scientific fixtures receive domain approval. Real solver execution
   qualification is out of this delivery wave.

## Persistence and compatibility

`catalog.material_revision.material_class` is nullable only for legacy schema revisions. New v2
revisions store one explicit enum value under a database check and tenant-scoped index. Typed
family-specific modeling tables will hold Prony and Ogden terms; no generic EAV or unrestricted
model JSON is introduced.

## Consequences

- The web catalog can explain why a workflow is available, planned, or unsupported.
- Existing immutable hashes and revision histories remain valid.
- Polymer support cannot accidentally reuse metal plasticity or a non-equivalent solver card.
- Supporting a new class/model still requires an explicit IR schema, capability manifest,
  mapping report, tests, and governance evidence.
