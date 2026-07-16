# ADR-0027: bulk delivery uses an immutable Export Bundle

- Status: Accepted
- Date: 2026-07-16
- Related: T-10, T-13 through T-16, T-25, T-30, T-45

## Context

Individual Artifact and Solver Card downloads exist. A Release currently downloads an immutable
release manifest, not an archive containing selected raw/normalized/processed data, neutral IRs
and cards. Changing Release semantics would mix governed publication with an engineer's bulk data
transfer request.

## Decision

1. Introduce a revisioned `Export Selection` that pins ordered component revisions and requested
   representations. A durable Export Job creates one immutable Export Bundle result.
2. Keep Release and Export Bundle separate. Release is an approved publication; Export Bundle is
   an authorized, audited transfer assembled from explicit immutable inputs.
3. The ZIP contains original raw files, canonical Parquet, readable CSV, IR JSON and schemas,
   mapping reports, native solver cards, `manifest.json`, `checksums.sha256` and a bundle README as
   requested and available.
4. Missing, unsupported or unauthorized required components block preflight. Optional omissions
   appear explicitly in the manifest; nothing is silently dropped.
5. Normalize ZIP ordering and timestamps so identical inputs/options produce identical bytes and
   SHA-256. Each successful retry creates or reuses content by digest without mutating a bundle.
6. Bundle scope is one organization/project and its classification is at least the most restrictive
   included component. Existing short-lived Artifact download authorization is reused.
7. The initial limit is 1,000 components or 5 GiB per bundle and is deployment-configurable.

## Consequences

- Users can transfer experimental, neutral and solver-ready representations together with proof of
  origin and integrity.
- Large assembly remains asynchronous and uses the existing Job/Artifact reconciliation boundary.
- External PLM/CAE connectors can consume the same manifest later without becoming a prerequisite.
