# ADR-0009: Reference pair outlier candidates require explicit human scope decisions

- Status: Accepted
- Date: 2026-07-16
- Decision owners: Product, Data/Statistics, Software
- Related: `T-20`, `T-21`, ADR-007, ADR-008

## Context

The first Statistics/QC slice deliberately accepts exactly two normalized reference-tensile
Dataset Selections from distinct Test Runs.  It calculates one peak engineering-stress feature
per Test Run and preserves both immutable source revisions.  The next workflow must let a user
record a possible outlier without deleting a curve, silently changing a Dataset, or making a
two-sample statistical claim that the method cannot support.

The canonical domain model requires candidate detection and human adjudication to remain
separate, and explicitly prohibits an outlier assessment from modifying Dataset Selection
membership.  Calibration Plans do not yet exist, so a future calibration-specific exclusion
cannot truthfully be persisted in this slice.

## Decision

Implement a narrow reference-pair T-21 flow in the existing `statistics` bounded module.

1. An immutable **Outlier Detection Plan** pins one successful immutable reference-pair
   Statistical Result revision and a declared `relative_peak_difference` threshold.  Its
   detector uses `abs(first_peak - second_peak) / max(first_peak, second_peak)` and records its
   formula/version.  It never reads a moving result head.
2. A committed Detection Run creates zero candidates below the threshold or exactly two
   `review_required` candidates at/above it: one for each pinned Selection/Dataset/Test Run.
   With `n=2`, it must not choose which candidate is a true outlier and must not automatically
   exclude either one.
3. A user creates a new immutable **Outlier Assessment** revision for a candidate.  The only
   reference-slice scope is the exact Statistical Plan revision that produced the result;
   decisions are `retained` or `excluded_from_reference_analysis`, with actor, reason, timestamp,
   and request/trace context.  A later correction is a new Assessment identity, not an update.
4. A typed scope-comparison read model exposes candidate evidence and the latest append-only
   assessment in that exact scope.  It is a decision projection only: it creates no derived
   Selection and never changes source, normalized, processed, or Statistical Result membership.
5. Use explicit typed PostgreSQL tables, foreign keys, check constraints, append-only triggers,
   indexes, tenant/classification RLS, provenance hooks, and audit hooks.  No generic EAV or
   untyped JSON payload holds core candidate, threshold, scope, or decision fields.

## Consequences

- The workflow is useful for QC review but accurately labels a pair discrepancy as a review
  candidate rather than a statistically established outlier.
- Reference-analysis exclusion is local to one immutable Statistical Plan revision.  Future
  `Calibration Plan` scope support requires an explicit schema extension after T-23 exists; it is
  not represented as an unvalidated UUID placeholder today.
- Multi-member Selection, robust multi-replicate methods, automatic deletion, and black-box
  anomaly models remain out of scope.
- Material → State → Property Set → IR → OpenRadioss Card remains an independent completed
  reference vertical flow.  This decision strengthens the Test Data → Statistics portion needed
  by the second demonstration flow; it does not turn the product into a calibration-only tool.

## Revisit trigger

- A domain owner approves a repeat-test group size/method that can identify a specimen rather
  than merely flag both sides of a pair.
- T-23 introduces a concrete immutable Calibration Plan revision to which an exclusion can be
  scoped.
- An approved processing method supplies a different explicit common-grid or scalar feature.
