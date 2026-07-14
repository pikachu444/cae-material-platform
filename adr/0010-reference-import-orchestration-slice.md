# ADR-0010: Reference import orchestration preserves an explicit human mapping boundary

- Status: Accepted
- Date: 2026-07-18
- Decision owners: Product, Test Data, Software
- Related: `T-11`, `T-08`, `T-12`, ADR-004, ADR-006

## Context

The existing reference tensile Dataset slice requires an explicit CSV mapping and preserves the
Raw Asset plus raw and normalized Dataset revisions.  It intentionally does not infer columns or
units.  That is a useful vertical capability, but it does not yet retain a distinct detection
report, an immutable Mapping revision, or a durable Import Run that pins the approved mapping.

The platform must not decide a production tensile standard, vendor format, or parser merely to
fill this gap.  The plugin runner foundation is also deliberately independent of a production
package/materializer deployment.  The next slice must therefore make the orchestration boundary
real without presenting a reference adapter as a qualified production importer.

## Decision

1. Add a non-production **synthetic CSV-header detection profile**.  It reads only a UTF-8 CSV
   header from a verified Raw Artifact and records an immutable Detection Report.  Any header-name
   suggestion has at most `low` confidence; the report state is always `needs_input`.  It neither
   assigns quantity semantics nor chooses a unit or mapping automatically.
2. Add `testing.import_mapping` stable identities with immutable typed revisions.  A Mapping
   revision pins one Detection Report and its Raw Asset/Artifact, the detector identity/version,
   and the user-confirmed reference tensile strain/stress column and original-unit strings.  A
   correction appends a revision; it never rewrites an approved Mapping or Raw Asset.
3. Add `processing.import_run` records that pin concrete Test Run, Raw Asset/Artifact, and Import
   Mapping revision inputs.  The first reference adapter calls the already bounded T-12 Dataset
   writer only after that human approval, then records the resulting immutable normalized Dataset
   revision.  Its execution is explicitly `reference_inline`, non-production, and not a claim of
   a deployed generic plugin runner.
4. Use explicit PostgreSQL relations, composite tenant/classification foreign keys, RLS, immutable
   revision guards, and terminal-run guards. Existing revision provenance/audit hooks cover Mapping
   revisions, while the T-12 Dataset output retains its Raw Asset provenance; the typed Import Run
   retains the pinned Mapping/Test Run/output link for this bounded slice. Do not use a generic EAV
   mapping or a free-form core JSON payload. Detection header names are a typed report field, not a
   property store.
5. The web workbench uses the same generic sequence visible to users: detect, inspect the report,
   submit a Mapping revision, then run import and inspect its concrete Dataset output.  The prior
   direct reference endpoint remains a compatibility route during this migration; new workbench
   flow uses the versioned orchestration route.

## Consequences

- A user can demonstrate why a particular CSV interpretation was selected and reproduce an
  import from frozen evidence without mutating source bytes.
- The syntactic header profile is not a production tensile parser, a test standard, or an
  authorization to infer engineering/true strain semantics.  A selected production importer must
  arrive as an approved plugin/package decision with its own schema and execution composition.
- The real generic durable plugin-worker deployment remains a separate T-18 composition concern.
  This slice exposes its boundary honestly rather than fabricating package or runner credentials.

## Revisit trigger

- A domain owner approves a concrete production test format and its mapping/normalization policy.
- A package materializer/committer and tenant-scoped worker identity are composed for importer
  plugins.
- More than the two explicit reference tensile channels are required.
