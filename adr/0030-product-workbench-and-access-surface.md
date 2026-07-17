# ADR-0030: material modeling workbench and simplified product access surface

- Status: Accepted
- Date: 2026-07-17
- Related: ADR-0018, ADR-0020 through ADR-0023, ADR-0025; T-53 through T-60

## Context

Reference steel, polymer and elastomer flows exist, but each exposes a bounded workflow rather than
one configurable Material Modeling Workbench. Internal authorization concepts also dominate parts
of the product surface even though ordinary users need a simpler mental model.

## Decision

1. Build one method-driven Workbench for mapping, crop, scale/shift, resampling, smoothing,
   alignment, statistics, fitting, extrapolation and candidate comparison. Every committed change
   is an explicit Recipe step and output revision.
2. Deepen three reference tracks in parallel: metal elastoplasticity, polymer linear
   viscoelasticity and elastomer hyperelastic/hyper-viscoelasticity. Public equations and official
   solver documentation are the only numeric and mapping sources.
3. Promote selected results to solver-neutral IR before generating an Abaqus or OpenRadioss card.
   Preserve the six mapping states and prohibit silent defaults or approximations.
4. Expose two product roles, `Administrator` and `User`, with feature grants for schema management,
   catalog editing, processing/calibration, model approval and card export. Existing fine-grained
   permissions and RLS remain implementation controls and compatibility inputs.
5. Every GUI-changing increment updates the task-oriented user/admin guide and deterministic
   screenshot evidence. Actual licensed solver execution remains out of scope.

## Consequences

- The platform foregrounds material discovery and scientific work instead of infrastructure
  vocabulary.
- Existing bounded APIs and models are extended behind common contracts rather than rebuilt.
- `reference`, `validated` and `production-approved` remain distinct user-visible states.
