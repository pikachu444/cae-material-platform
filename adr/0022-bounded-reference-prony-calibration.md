# ADR-0022: Bounded reference Prony calibration does not select or promote automatically

- Status: Accepted
- Date: 2026-07-16
- Related: ADR-0007, ADR-0020, ADR-0021; T-23, T-24; P2 item 3

## Context

The platform now preserves normalized shear-relaxation evidence and explicit processed Dataset
revisions. A usable calibration increment must fit data reproducibly without turning one numerical
minimum into an unreviewed engineering decision or overwriting the manual baseline IR.

## Decision

The first calibration is a non-production, solver-neutral, two-term generalized-Maxwell reference
model. A revisioned Plan pins one exact processed Dataset revision and one exact baseline
linear-viscoelastic IR revision. The baseline supplies the instantaneous shear modulus and must
declare bulk relaxation `not_characterized`; this shear-only workflow never invents bulk terms.

The fitted parameters are total shear ratio, fast-term fraction, fast relaxation time and slow
relaxation time. Ratio parameters are bounded in physical coordinates. Time constants use a log
transform and disjoint fast/slow bounds. SciPy `least_squares(method="trf")` and NumPy PCG64 provide
the fixed reference optimizer and deterministic multistart contract. Uniform normalized modulus
residuals are the only objective in this increment.

Plan revisions, Runs, Attempts and Candidates use dedicated PostgreSQL tables and composite tenant
foreign keys. Observed, predicted and residual points are immutable Parquet Artifacts. Each
Candidate records objective, RMSE, mean residual, convergence reason, evaluation counts, bound
warning, Jacobian-rank identifiability status and an explicit `not_assessed_reference` uncertainty
status. Database guards require a processed Dataset, the exact baseline model family, matching
Material State revision, and missing bulk characterization.

Execution returns all Candidates and does not create a Candidate Selection or Material Model
revision. The UI may sort Candidates by objective for inspection but may not label the first row as
approved or promote it automatically.

## Consequences

Repeated Runs with the same Plan and environment are reproducible and leave auditable numerical
evidence. Bounds, rank deficiency and missing uncertainty remain visible. A subsequent explicit
human action must record the chosen Candidate and reason before appending a new immutable
linear-Prony IR revision. Abaqus export then pins that promoted revision through the existing
preflight/card boundary.

This ADR does not define production term-count selection, time-temperature superposition,
frequency-domain fitting, nonlinear hyperelasticity, solver execution qualification, or
OpenRadioss LAW62. Ogden-Prony/LAW62 is a separate model family and vertical feature.
