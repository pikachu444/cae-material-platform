# ADR-0028: configurable material information system and dual explorer

- Status: Accepted
- Date: 2026-07-17
- Related: ADR-0006, ADR-0024, ADR-0025; T-48 through T-51

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

## Consequences

- Users can create new record attributes and relationships without a deployment.
- Typed indexes and unit-aware search remain possible without a generic EAV value bucket.
- A record may be reached through a stable current-record route, but every relationship and
  calculation continues to pin an immutable revision.

