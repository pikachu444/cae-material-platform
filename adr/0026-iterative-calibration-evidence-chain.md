# ADR-0026: iterative calibration appends IR revisions and evidence

- Status: Accepted and implemented for the bounded Ogden Candidate workflow
- Date: 2026-07-16
- Related: ADR-0012, ADR-0022; T-44

## Context

The current linear-Prony reference path correctly prevents a promoted revision from silently
replacing its calibration evidence. Requiring a new Material Model identity for every recalibration
would, however, split the engineering history of one logical model and make card/release impact
analysis harder.

## Decision

1. Recalibration of the same logical model retains the Material Model stable identity and appends
   revision `rN` with `based_on_revision_id` pointing to the exact prior head.
2. Each IR revision owns one immutable promotion-evidence record that pins the Candidate Selection
   revision, Calibration Run, Candidate and diagnostics digests used for that revision.
3. Prior promotion evidence is read through the revision chain; it is never copied over, replaced
   or collapsed into a mutable list.
4. Promotion requires compare-and-swap against the current IR revision and rejects a reused
   Candidate/Selection, stale head, cross-scope evidence or non-converged Candidate.
5. A user reason remains mandatory. Numerical convergence never performs automatic promotion.
6. Cards and releases continue to pin one exact IR revision. A later calibration does not alter an
   earlier card or release.

## Consequences

- Users can compare calibration rounds without losing stable model identity.
- Migration 055, the protected contract and the connected T-44 UI implement this decision for
  governed multi-test Ogden Candidates. The older bounded linear-Prony path retains its original
  single-promotion guard until it is migrated to the same evidence-chain contract.
- Release impact analysis can distinguish a new model revision from a new logical model.
