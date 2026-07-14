# ADR-0011: Reference linear-elastic Calibration keeps numerical execution bounded and evidence-first

- Status: Accepted
- Date: 2026-07-19
- Decision owners: Product, Scientific Software, Material Modeling
- Related: `T-23`, `T-22`, `T-19`, `T-25`, ADR-004, ADR-005, ADR-006, ADR-007

## Context

The product is a material-data and CAE-use platform.  Calibration is a bounded capability on the
path from immutable Test Data and Processing outputs to a Material Model IR; it is not a separate
MCalibration-style application and it cannot be allowed to overwrite Material, Dataset, or IR
revisions.

The current product has one non-production Material Model IR: small-strain isotropic linear
elasticity.  It also has one typed reference tensile Dataset path, including immutable normalized
and processed curve revisions and one-member Selections.  The next useful vertical capability is
to prove that a user can pin those inputs, execute a reproducible candidate calculation, inspect
typed diagnostics, and retain both success and failure evidence.  No approved production
constitutive equation, optimizer, acceptance criterion, or solver-based validation target has
been selected.

## Decision

1. Implement a deliberately narrow, non-production `reference_uniaxial_linear_elasticity`
   Calibration Plan.  A stable Plan identity has immutable revisions.  Each revision pins exactly
   one concrete normalized or processed tensile Selection revision and one concrete reference
   linear-elastic Material Model IR revision.  It never follows a moving Dataset or Model head.
2. The initial evaluator is the public closed-form relation `sigma = E * epsilon` for finite,
   non-negative engineering tensile points.  The only parameter is `youngs_modulus_pa`; its lower
   bound, initial value, upper bound, normalization stress scale, uniform point weight,
   all-observed-points domain, reject-on-missing-data policy, multistart count, and signed seed
   are explicit Plan fields.
3. The initial calibrator is an analytic bounded weighted least-squares reference implementation,
   not SciPy and not a production optimizer choice.  It retains deterministic multistart Attempts
   so the Plan/Run/Attempt/Candidate orchestration can be tested without claiming a generic
   optimizer, uncertainty estimate, material-point integration, or calibrated solver card.
4. A durable Calibration Run records a fixed Plan revision, Selection revision, Dataset revision,
   Model revision, R3 reference environment digest, and every Attempt.  A successful Attempt
   creates a typed Candidate and an immutable Parquet diagnostics Artifact containing observed,
   predicted, residual, and normalized-residual channels.  Failed Attempts and failed terminal
   Runs remain visible; source inputs are never changed.
5. PostgreSQL uses explicit `modeling.calibration_plan`, `_revision`, `calibration_run`,
   `calibration_attempt`, and `calibration_candidate` relations.  Composite
   organization/project/classification foreign keys, indexes, forced RLS, append-only guards, and
   trigger checks enforce same-scope input coherence and prohibit candidate mutation.  No generic
   EAV or optimizer/settings JSON store is introduced.
6. The protected API and Material State workbench expose the exact pinning, numerical conventions,
   Run state, Candidate summary, and bounded diagnostics preview.  They label the workflow
   non-production.  Candidate selection and promotion to a new IR revision are intentionally a
   separate human decision in `T-24`.

## Consequences

- The user can traverse `Material State -> Dataset Selection -> Calibration Plan -> Run ->
  Candidate diagnostics` through the same tenant-scoped web workbench that already owns Material
  and Test Data workflows.
- Calibration does not alter a Property Set, Material Model IR, Raw Asset, normalized Dataset,
  processed Dataset, Statistics Result, or Solver Card.  A subsequent IR promotion must append a
  new Model revision with explicit selection evidence.
- Exact equality is not claimed for an unspecified future optimizer or external solver.  The R3
  declaration applies only to the stated reference evaluator/calibrator/environment digest and
  its declared tolerance.
- A selected production model, TestModeAdapter, optimizer, objective weighting policy,
  uncertainty method, domain acceptance rule, and material-point/virtual-specimen validation
  remain explicit domain decisions rather than hidden defaults.

## Revisit trigger

- A Material Modeling owner approves a concrete constitutive model and its parameter semantics.
- An optimizer, transforms/scaling, multistart policy, or uncertainty/identifiability method is
  approved for a declared TestModeAdapter.
- A candidate must be promoted through review/approval to an IR and then validated against a
  target solver/template.
