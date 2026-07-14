# ADR-015: Immutable review lifecycle for candidate revisions

Status: accepted

## Context

T-28 produces reference validation evidence, but a numerical verdict is not a human acceptance or
release decision. The platform needs a tenant-scoped review boundary that can consume any bounded
candidate manifest without importing Material, Dataset, solver, or calibration internals.

## Decision

1. A Review Request pins `aggregate_type`, stable `aggregate_id`, exact `revision_id`, and a
   lowercase SHA-256 `manifest_sha256`. The request is accepted only while that revision's
   lifecycle projection is `draft`.
2. The request transition is `draft -> review`. A decision is an immutable row and a lifecycle
   event in the same PostgreSQL transaction. `approved` transitions to `approved`;
   `changes_requested` transitions to `changes_requested`.
3. A request has one decision. A request author cannot decide their own request, and only a
   `domain_reviewer` authorization role may record a decision. The required role is fixed for this
   MVP; a configurable approval matrix is a later product decision.
4. A decision must present the exact request manifest digest. If a newer revision was created for
   the same aggregate after the request, the old request is stale and cannot be approved.
5. `changes_requested` never mutates the rejected revision. Resubmission is possible only through
   the new immutable revision's initial `draft` lifecycle projection.
6. Review requests and decisions use explicit PostgreSQL tables, composite tenant keys, forced
   RLS, immutable triggers, and no generic EAV or opaque business payload.

## Consequences

- Review state is queryable through the existing lifecycle projection and event history.
- Candidate domain modules remain independent of governance storage and APIs.
- T-30 can consume approved requests and verify the exact digest before composing a Release.
- Comments, evidence attachments, legal signatures, configurable multi-role approvals, and Release
  publication remain outside T-29.

