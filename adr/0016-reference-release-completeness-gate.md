# ADR-0016: Reference Release completeness gate and immutable package

- Status: Accepted
- Date: 2026-07-24
- Scope: T-30 reference Release channel

## Context

The platform already stores immutable Material Model IR, Solver Card, Validation Result, and
review evidence, but those facts were not yet composed into a user-visible CAE delivery artifact.
T-30 must provide a small end-to-end Release flow without turning the platform into a generic
payload store or claiming production solver qualification.

## Decision

1. The first Release channel is explicitly `reference` and has only the `released` state. A stable
   Release identity is separate from an immutable `release_manifest` and immutable
   `release_artifact` package row.
2. A publish command names one Material/State/Property lineage, Material Model revision, Solver
   Card revision, Validation Result, T-29 Review Request, and provenance snapshot. Each source is
   checked in the same organization/project/classification scope and by its SHA-256 digest.
3. Publication fails closed unless the Validation Result is `passed`, the Review decision is
   `approved` for the exact candidate digest, the Solver Card is the declared non-production
   reference card, and every typed mapping status is neither `unsupported` nor `approximated`.
4. PostgreSQL uses explicit typed tables, composite tenant foreign keys, unique identities,
   indexes, forced RLS, and the existing immutable-row trigger. No generic EAV, key/value, or
   catch-all release JSON column is introduced. The package document is a small explicit manifest;
   its digest and byte length are stored alongside it.
5. The protected API exposes create/list/read/download and the React workbench exposes the same
   reference channel. Download returns the stored package digest as a strong ETag.

## Consequences

- A Release is reproducible and cannot silently substitute a newer model/card/result/review.
- The database-backed package is intentionally a reference/development delivery adapter. A
  production object-store artifact, signed distribution, supersede/withdraw lifecycle, retention,
  and release approval matrix remain T-31+ decisions.
- The gate currently consumes the existing T-22/T-25/T-28/T-29 reference records and therefore
  does not add Material, importer, fitting, or solver-specific domain behavior.
