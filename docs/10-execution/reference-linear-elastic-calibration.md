# Reference linear-elastic calibration slice

Status: implemented non-production reference subset (`T-23`, 2026-07-19)

This document records the executable contract for the first calibration slice. It supplements the
future-oriented fitting/validation design in [fitting-validation.md](fitting-validation.md) and
does not approve a production material model, optimizer, or solver validation policy.

## Scope

The slice accepts exactly one immutable normalized or processed reference uniaxial-tensile Dataset
Selection revision and exactly one immutable reference isotropic-linear-elastic Material Model IR
revision. The Selection's Test Run must resolve to the same Material State as the IR. All inputs
must share organization, project, and classification scope.

The evaluator is closed-form engineering uniaxial elasticity:

```text
sigma = E * epsilon
```

The only parameter is `youngs_modulus_pa`. The implementation is explicitly `non_production` and
uses evaluation mode `closed_form_curve`.

## Immutable Plan contract

A stable Calibration Plan has append-only revisions. A Plan revision contains concrete identity and
revision IDs for the Selection and Material Model and explicitly records:

- Young's-modulus lower bound, initial value, and upper bound in Pa;
- stress normalization scale in Pa;
- uniform point weight, mean normalized-squared-residual aggregation, all-observed-point domain,
  and reject-on-missing-data policy;
- multistart count (1–16) and a signed 64-bit random seed;
- evaluator/calibrator identifiers and versions;
- fixed reference model schema family/version/digest; and
- the non-production declaration.

No moving head, generic parameter store, generic optimizer JSON, silent weight, or implicit
normalization is allowed. Revisions are created through the common revision kernel and retain
audit/provenance facts.

## Execution and diagnostics

The reference calibrator computes the bounded analytic weighted least-squares slope. The first
Attempt uses the explicit initial value; additional deterministic starts are derived from the
recorded seed and attempt ordinal. Although the analytic solution does not depend on its start,
preserving every start/Attempt exercises the durable execution boundary without pretending that a
future numerical optimizer has been chosen.

A Calibration Run pins the exact Plan, Selection, Dataset, and Model revisions and records the
reference environment digest and reproducibility level `R3`. It remains `executing` until terminal
state is committed. Failed inputs/Artifacts produce a durable failed Run and failed Attempt rather
than deleting evidence.

Each successful Attempt creates a separate immutable Candidate and a typed Parquet diagnostics
Artifact with these channels:

| Channel | Unit | Meaning |
| --- | --- | --- |
| `engineering_strain` | `1` | observed x coordinate |
| `observed_engineering_stress_pa` | `Pa` | source curve response |
| `predicted_engineering_stress_pa` | `Pa` | `E * strain` response |
| `residual_engineering_stress_pa` | `Pa` | predicted minus observed |
| `normalized_residual` | `1` | residual divided by declared scale |

Candidates also retain total objective, residual RMS/mean, bound-sticking, convergence reason,
and explicit `not_assessed_reference_one_parameter` / `not_estimated_reference` diagnostic
statuses. These statuses are evidence of what the slice does not claim, not hidden missing data.

## Storage and API boundary

PostgreSQL relations are explicit:

```text
modeling.calibration_plan
modeling.calibration_plan_revision
modeling.calibration_run
modeling.calibration_attempt
modeling.calibration_candidate
```

They use composite organization/project/classification foreign keys, tenant/classification RLS,
immutable-row and head guards, same-input coherence checks, terminal state guards, and indexes for
tenant-scoped Plan/Run/Candidate lookup. The module does not use a generic EAV relation or a
free-form core numeric payload.

Protected endpoints are:

```text
POST  /api/v1/calibration-plans
PATCH /api/v1/calibration-plans/{plan_id}
GET   /api/v1/calibration-plans
GET   /api/v1/calibration-plans/{plan_id}
POST  /api/v1/calibration-runs
GET   /api/v1/calibration-runs/{run_id}
GET   /api/v1/calibration-candidates/{candidate_id}/diagnostics-preview
```

The Material State web workbench invokes these APIs directly. It exposes pinned inputs and
numerical conventions, creates/executes a Plan, and renders candidate diagnostics. Browser plots
are previews only; the typed Artifact remains the calculation evidence.

## Explicit non-goals

This slice does not provide a production constitutive model, a SciPy or other production optimizer
selection, parameter transforms/scaling beyond the stated reference convention, uncertainty or
identifiability estimation, material-point integration, holdout validation, virtual specimen
execution, solver execution, candidate auto-acceptance, or IR mutation/promotion. `T-24` owns
human candidate selection with a reason and append-only IR promotion evidence.
