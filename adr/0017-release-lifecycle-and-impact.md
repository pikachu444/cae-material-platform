# ADR-0017: Append-only Release lifecycle and downstream impact

- Status: accepted
- Date: 2026-07-25
- Scope: T-31 reference Release channel

## Decision

`governance.release`, `release_manifest`, and `release_artifact` remain immutable facts. A
separate `release_lifecycle_projection` records the current lifecycle state, while
`release_lifecycle_event` records the one permitted transition from `released` to either
`superseded` or `withdrawn`. A supersede event must name an explicit successor Release in the
same organization, project, and classification. There is no automatic replacement or deletion.

`release_usage` records explicit package downloads and consume actions. Usage is accepted only
while the lifecycle projection is `released`; a terminal Release can still be read for audit and
impact analysis, but cannot be downloaded or consumed for new work. The impact response exposes
predecessor/successor links, transition history, usage facts, and a warning for terminal states.

## Rationale and boundaries

Keeping lifecycle state outside the immutable Release row preserves stable identity, immutable
revision/package evidence, and the existing T-30 release completeness contract. Explicit typed
tables and composite tenant keys preserve organization/project isolation without a generic EAV or
unbounded JSON payload. Automatic PLM replacement, solver reruns, production object storage, and
cross-tenant release linking are intentionally outside T-31.

## Consequences

- Reads include `lifecycle_state`; clients must not assume every Release is currently usable.
- Download and consume operations create append-only usage facts and fail with a conflict after a
  terminal transition.
- Supersede/withdraw require `release.publish`; impact and usage reads use `release.read`.
- PostgreSQL integration tests must run against a disposable PostgreSQL instance to verify RLS,
  migration constraints, trigger guards, and concurrent transition behavior.
