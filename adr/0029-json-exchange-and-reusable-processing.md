# ADR-0029: JSON exchange, mapping profiles and reusable processing recipes

- Status: Accepted
- Date: 2026-07-17
- Related: ADR-0003, ADR-0007 through ADR-0012, ADR-0027; T-52 through T-58

## Context

The platform currently preserves raw files and canonical columnar artifacts and exposes several
bounded processing/calibration workflows. Users also need a documented exchange format and a
general way to save a configured processing method, apply it again and execute it over a selection.

## Decision

1. `cmp.test-data` JSON is the canonical user exchange document for test metadata, channel
   semantics, original/normalized units and column-oriented observations. CSV/TSV/XLSX importers
   adapt into this contract; the original source remains immutable.
2. `Mapping Profile` is a revisioned mapping from configurable record attributes and test channels
   to calculation quantities. Calculations pin one exact profile revision.
3. `Processing Recipe` is a stable identity with immutable revisions. A revision contains ordered
   steps, exact method versions, JSON-Schema-validated options, input/output contracts and
   applicability predicates.
4. Preview is non-authoritative. A committed run pins Dataset, Mapping Profile and Recipe revisions.
   A batch pins an ordered input selection, performs compatibility preflight and records each member
   result without overwriting inputs or prior runs.
5. `cmp.neutral-material` JSON carries source digests, mapping and recipe revisions, intermediate
   curve stages, candidates, selected IR, applicability and solver mapping evidence. It can be
   validated, imported and exported.
6. A single document up to 25 MiB is delivered as JSON. Larger or multi-document transfers use a
   deterministic JSON+ZIP package with manifest and SHA-256 checksums. PostgreSQL and Parquet remain
   internal storage formats.
7. Solver cards remain solver-native ASCII files; they are not embedded as card strings in the
   neutral JSON.

## Consequences

- A user can exchange human-readable canonical data without making large JSON arrays the database
  execution format.
- Existing tabular and Bundle implementations become adapters and package infrastructure rather
  than being discarded.
- Method version and compatibility checks make saved and batch processing reproducible.

