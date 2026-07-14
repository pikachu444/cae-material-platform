# ADR-0018: Reference tensile-to-elastoplastic IR supports explicit OpenRadioss and Abaqus mappings

- Status: Accepted for bounded non-production implementation
- Date: 2026-07-14
- Related tasks: T-19, T-22, T-25, T-26, T-D01, T-D03

## Context

The existing product vertical creates a typed linear-elastic Material Model IR and an immutable
OpenRadioss `/MAT/ELAST` card. That path proves identity, revision, provenance, preflight, and
download boundaries, but it does not turn an actual tensile curve into an elastoplastic material
law. Users need the same immutable Material/Dataset workflow to produce useful nonlinear solver
inputs without waiting for a general calibration framework.

The first extension must remain independent of a proprietary calibration product. It must also
avoid storing a large curve as database rows, hiding smoothing or extrapolation, embedding solver
keywords in the neutral IR, or treating a generated card as solver qualification.

The product owner requested both OpenRadioss and Abaqus support for the first elastoplastic slice.

## Decision

1. Add a bounded model family,
   `urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0`, for rate-independent isotropic
   hardening derived from one immutable normalized or processed uniaxial-tensile Dataset revision.
   It remains explicitly non-production until domain and solver validation evidence is approved.
2. The source Catalog Property Set revision supplies density, Young's modulus, Poisson ratio, and
   a required positive yield stress. The Dataset supplies SI engineering strain and engineering
   stress. Both concrete revisions are pinned in the IR.
3. The declared transformation profile converts only observations up to the first global maximum
   engineering stress:
   - `true_stress = engineering_stress * (1 + engineering_strain)`;
   - `true_total_strain = ln(1 + engineering_strain)`;
   - `true_plastic_strain = true_total_strain - true_stress / E`.
   Pre-yield observations are excluded by an explicit rule. Non-monotone plastic strain, softening
   before the selected necking point, invalid units, or inconsistent source scope fail closed.
   The immutable revision also records the source point count, excluded pre-yield/post-necking
   counts, and the exact source index selected as necking evidence.
4. The first hardening point is the Catalog yield stress at zero plastic strain. The source curve
   ends at the selected necking observation. A caller must explicitly acknowledge and provide the
   maximum plastic strain for a constant-stress extension. The extension is retained as
   `approved_constant_true_stress`; no hidden smoothing, fitting, resampling, or failure
   law is introduced.
5. Hardening points are stored in a content-addressed Parquet Artifact. PostgreSQL stores explicit
   source revision IDs, Artifact ID/digest/schema, point count, transformation profile, necking
   observation, characterized range, extension range, and acknowledgement. It does not store a
   generic EAV payload or one row per curve point.
6. Add two explicit exporter targets:
   - OpenRadioss 2025 `kg_m_s`: `/MAT/LAW36 (PLAS_TAB)` plus one `/FUNCT` hardening curve;
   - Abaqus 2025 `kg_m_s` consistent units: `*DENSITY`, `*ELASTIC`, and
     `*PLASTIC, HARDENING=ISOTROPIC, EXTRAPOLATION=CONSTANT`.
   Abaqus has no unit declaration in the input keywords, so the card and mapping report state the
   chosen consistent unit convention explicitly.
7. Each exporter has a versioned capability identity, deterministic mapping report, mapping-report
   acknowledgement, immutable card digest, golden fixture, and field-level mapping status. The
   post-necking extension is reported as `approximated`, remains exportable only through the
   explicit mapping-report digest acknowledgement, and is never relabeled as an exact mapping. The
   neutral IR contains no `/MAT`, `/FUNCT`, `*ELASTIC`, or `*PLASTIC` keywords.
8. The existing linear-elastic reference model and `/MAT/ELAST` exporter remain unchanged and
   continue to serve as regression baselines. Existing read APIs filter to their declared family;
   the new bounded family is exposed through explicit elastoplastic endpoints.

## Consequences

- A real tensile curve can produce two solver representations from one frozen IR without a
  parametric fitting step.
- The same transformed hardening Artifact is used by both exporters, so differences are visible in
  mapping rather than hidden in duplicate preprocessing.
- Constant post-necking extension is an acknowledged approximation in the IR evidence, not a
  silent exporter default.
- Generated cards are useful review artifacts but are not production-qualified. Abaqus execution,
  OpenRadioss execution, element formulation, failure behavior, domain acceptance limits, and
  release policy require separate validation evidence.
- Temperature dependence, multiple strain-rate curves, kinematic/combined hardening, damage and
  failure, inverse post-necking identification, and additional solvers remain outside this slice.

## Revisit triggers

- A domain owner approves a different yield definition or post-necking identification method.
- Multiple temperature or strain-rate curves require a typed multidimensional hardening schema.
- Abaqus or OpenRadioss execution fixtures establish a production qualification profile.
- A second constitutive family requires a different test-mode adapter or objective/calibration
  contract.

## Public mapping references

- [OpenRadioss `/MAT/LAW36 (PLAS_TAB)` reference](https://help.altair.com/hwsolvers/rad/topics/solvers/rad/mat_law36_plas_tab_starter_r.htm)
- [OpenRadioss tensile characterization example](https://openradioss.atlassian.net/wiki/spaces/OPENRADIOSS/pages/11075620)
- [Abaqus classical metal plasticity](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEMATRefMap/simamat-c-metalplastic.htm)
- [Abaqus `*PLASTIC` keyword](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEKEYRefMap/simakey-r-plastic.htm)
