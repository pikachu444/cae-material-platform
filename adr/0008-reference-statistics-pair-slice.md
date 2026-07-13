# ADR-008: Reference two-selection Statistics/QC slice

- Status: Accepted
- Date: 2026-07-16

## Context

ADR-007 deliberately kept `Selection` narrow: one immutable normalized reference tensile Dataset
revision per Selection. The next useful product step is repeat-test QC and descriptive statistics,
but broadening Selection into an unbounded group or silently aligning curves would hide a material
and test-data decision inside a calculation.

The product remains a material-data and CAE-use platform. Statistics is a bounded capability on the
path from Test Data to Material Model; it is not a separate MCalibration-style product or a generic
analytics/EAV subsystem.

## Decision

1. The first Statistics Plan has a stable identity and immutable revisions. Each revision pins
   exactly two existing one-member normalized Dataset Selection revisions. It does not follow a
   moving Dataset head and does not change the T-19 Selection contract.
2. Both pinned inputs must be in the same organization/project/classification scope and resolve to
   distinct Test Runs. The sample unit is the Test Run/specimen, not individual curve points.
3. Pointwise curve statistics are allowed only when normalized observed engineering-strain values
   and point counts match exactly. This slice performs no interpolation, resampling, smoothing,
   extrapolation, or browser-side alignment.
4. Scalar statistics use one peak engineering-stress value per Test Run. For the fixed `n=2`
   reference method, the Result records mean, sample standard deviation, median, MAD, IQR,
   minimum, maximum, and coefficient of variation. It explicitly records
   `not_provided_reference_pair` instead of inferring a confidence interval.
5. A committed Statistical Run is durable and append-only. Failed input/QC outcomes retain typed
   QC observations; a successful run creates a separate immutable Statistical Result revision and
   typed Parquet curve Artifact. Source Dataset revisions and Artifacts are never modified.
6. PostgreSQL uses explicit Statistics, Result, Run, and QC columns, composite tenant/classification
   foreign keys, indexes, forced RLS, immutable-row/head guards, and trigger cross-checks. Generic
   EAV and free-form core result payloads are not introduced.
7. Provenance records Plan and both Selection-revision inputs for the Result activity, and existing
   revision lifecycle/audit hooks remain mandatory. The workbench displays the input boundary, QC,
   scalar result, and curve result through the protected API.

## Consequences

- The first Statistics UI is intentionally useful only after users create two normalized Dataset
  Selections from separate Test Runs. It gives a real vertical result without inventing data
  alignment policy.
- Grouping beyond a pair, confidence intervals, outlier assessment, and processing methods that
  explicitly create a common grid require later domain decisions and versioned recipes/plans.
- Calibration, when added, consumes these pinned Dataset/Processing/Selection/Statistics revisions;
  it does not create a separate MCalibration-shaped application boundary.

## Revisit trigger

- A domain owner approves a repeat-test grouping, strain-domain, alignment, or uncertainty profile.
- A reference test format needs more than exactly two specimens or an approved pointwise band
  interpretation.
- Outlier assessment or calibration needs a scoped selection that must remain distinct from raw
  and normalized source preservation.
