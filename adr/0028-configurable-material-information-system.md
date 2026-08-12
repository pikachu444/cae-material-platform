# ADR-0028: configurable material information system and dual explorer

- Status: Accepted
- Date: 2026-07-17
- Related: ADR-0006, ADR-0024, ADR-0025; T-48 through T-51; Issues #204, #207

## Context

The fixed Material/State/Property vertical proves storage and card delivery, but it does not provide
the configurable tables, attributes, layouts, folders, subsets and record links expected from a
material information system. The existing flat routes and State genealogy are useful bounded views;
they are not a Catalog Contents Tree or a general cross-domain relationship model.

## Decision

1. Add administrator-defined Table, typed Attribute Definition, Layout, Subset and Link Type
   revisions. Adding an attribute must not require a database migration.
2. Store values in type-specific relations for scalar number, integer, text, boolean, date,
   discrete, file/artifact, curve/table and record reference. Do not use one untyped value column or
   one opaque record JSON document as the data authority.
3. Preserve original numeric value/unit text, normalized value/unit and quantity semantics together.
4. Add a Catalog Explorer projection `Workspace -> Table -> Folder -> Record` and a separate
   Material Workflow Explorer projection from exact revision links. Existing flat routes remain.
5. General links pin both endpoint revisions. Link Type declares allowed source/target Tables,
   direction labels and cardinality. Cross-scope links and `latest` aliases are rejected.
6. Fixed Material/State/Property APIs remain compatibility projections while configurable records
   are introduced. Existing identities and revisions are not rewritten.
7. A Schema Definition Bundle is an adapter-owned projection input, not a new Catalog aggregate
   model. Planning and apply both derive Database/Profile/Table/Attribute/Layout/placement/Link Type
   actions on the server. Apply accepts only exact Artifact ID, Artifact SHA-256, the existing
   `plan_fingerprint`, `delete_missing=false`, and an idempotency key; client-returned actions or
   projected content are never execution authority.
8. Apply re-runs the planner against the current RLS-scoped Catalog while holding a project lock and
   conflicting Catalog table locks. The whole revision set, exact publication markers, source
   provenance, immutable application/bindings, audit and outbox event commit in one PostgreSQL
   transaction. A stale fingerprint, current Record conflict or any write failure rolls everything
   back.
9. Bundle apply is the explicit Schema Administrator approval boundary and publishes its exact
   projected revisions atomically. The general single-revision direct-publication endpoint remains
   disabled and governed review behavior is unchanged.
10. Stable bundle identity and semantic versions are explicit normalized rows. A semantic version
    cannot be rebound to different canonical JSON. Applications and object bindings are immutable;
    export reads the exact source Artifact only while every bound Catalog head and publication marker
    still matches. Missing bundle members are never deletion authority.

## Consequences

- Users can create new record attributes and relationships without a deployment.
- Typed indexes and unit-aware search remain possible without a generic EAV value bucket.
- A record may be reached through a stable current-record route, but every relationship and
  calculation continues to pin an immutable revision.
- Bundle retries are replay-safe by tenant-scoped idempotency key, and an export can be uploaded and
  planned again as a semantic no-op. Changes that would strand current Records are reported as
  migration-required; no user migration code runs inside the adapter.

