# ADR-0013: Reference Validation Template and Runner preserve evidence before verdicts

- Status: Accepted
- Date: 2026-07-21
- Decision owners: Product, CAE Domain, Scientific Software
- Related: `T-27`, `T-28`, `T-25`, `T-26`, ADR-006, ADR-011, ADR-012

## Context

The platform already has a narrow non-production chain from Material State and typed properties to
an immutable reference linear-elastic Material Model IR and an OpenRadioss 2025 `/MAT/ELAST` Solver
Card. Calibration may append a new IR revision, but neither a generated card nor a numerically
converged candidate proves that a solver run was healthy or that it agrees with experimental data.

Validation therefore needs to preserve an exact execution input tuple and all output evidence before
any numerical-health or experimental-comparison verdict is considered. A real solver/HPC adapter is
not available or qualified in this product slice. Treating a shell command, an opaque job ID, or a
successful mock response as a solver-validation result would overstate the product capability.

## Decision

1. `T-27` introduces only a versioned reference one-dimensional tensile virtual-specimen Template,
   a revisioned Validation Plan, a durable Validation Run, and an immutable Result Manifest. Stable
   identities and immutable revisions remain separate; no source Template, Plan, IR, Card, Dataset
   Selection, or prior Manifest is updated or overwritten.
2. The Plan pins exact revisions of the Template, Material Model IR, Solver Card, and experimental
   Dataset Selection. PostgreSQL composite organization/project/classification foreign keys, RLS,
   explicit target checks, and triggers reject mixed tenant/classification, Card-to-IR, Card-to-
   Template target, and Material-State mismatches.
3. The initial target remains the existing reference OpenRadioss 2025 `kg_m_s` card dialect. The
   template uses a documented one-dimensional axial-bar geometry/mesh/displacement/output profile,
   but the generated deck is explicitly a **non-production reference deck assembly**, not a claimed
   executable or qualified OpenRadioss model.
4. The only managed execution is `reference_inline_mock`; it maps an explicit caller-selected
   outcome to a durable state and writes synthetic bounded native JSON only for a mock success. A
   manual mode accepts an opaque, allowlisted external job reference plus bounded logs/native JSON.
   Neither mode accepts a command line, shell expression, arbitrary solver configuration, or a
   moving source head.
5. Both modes write the same typed Result Manifest shape: immutable deck, stdout, stderr, optional
   native result, manifest Artifact, digests, termination state, and source tuple. The terminal
   transaction records the same provenance graph and audit fact for either execution path.
6. `T-27` has no numerical-health report, extracted response, metric, threshold, validation pass,
   approval, release, or production qualification. `T-28` owns response extraction, health,
   comparison metrics, and verdicts. A normal termination is evidence only, never a pass.
7. The Material State web workbench exposes actual protected API actions for creating a Template,
   pinning a Plan, submitting/collecting mock evidence, or attaching manual evidence. It labels the
   boundary as non-production and shows that no `T-28` verdict exists yet.

## Consequences

- The durable evidence path is available now without coupling core code to a specific commercial
  solver binary, HPC scheduler, material family, test importer, or a generic EAV/options payload.
- Result Manifest provenance is complete for mock and manual branches, including failed runs with
  deck/log evidence when a native result is not available.
- A future qualified runner must receive its own capability decision, environment attestation,
  scheduler adapter, retry/reconciliation policy, and CAE-domain-approved template settings. It
  must still emit the same immutable result evidence boundary rather than mutating a `T-27` run.

## Revisit trigger

- A CAE domain owner approves a real OpenRadioss executable/template and a controlled execution
  environment.
- A second solver/version needs a separately documented target/template mapping.
- `T-28` requires a typed extracted response, numerical-health profile, metric/threshold profile,
  or experimental verdict beyond this evidence-only boundary.
