# ADR-0021: Reference shear-relaxation processing creates a separate Dataset identity

- Status: Accepted
- Date: 2026-07-16
- Related: ADR-0007, ADR-0019, ADR-0020; T-19; P2 item 3

## Context

The reference shear-relaxation ingress preserves immutable raw CSV revision 1 and normalized SI
Parquet revision 2. Prony calibration needs an explicit, reproducible input window, but changing
either imported revision or hiding crop/interpolation behavior would violate revision and provenance
invariants.

## Decision

The first shear-relaxation Processing step is an inclusive time crop over observed normalized
points. It never interpolates, resamples, smooths, extrapolates, or edits source bytes.

The platform stores a stable Processing Recipe identity and immutable typed revision, a committed
Run pinned to exact Recipe and normalized Dataset revisions, one immutable derived Parquet Artifact,
and a separate stable processed Dataset identity at revision 1. Dedicated PostgreSQL columns,
tables, checks, composite tenant foreign keys, indexes, forced RLS, immutable revision triggers, and
Run transition guards enforce the contract. No generic EAV or opaque parameter payload is used.
Provenance records both the normalized Dataset revision and Recipe revision as used entities and
binds the generation activity to the concrete Run.

## Consequences

Raw and normalized revision history remains unchanged. Different Processing Runs can produce
independent derived Dataset identities without moving a shared source head. Bounded Prony
calibration can require a concrete `processed` revision and exact processing evidence.

This ADR does not select production Prony term counts, bounds, objective weights, validation
thresholds, or a solver qualification policy. Those remain explicit reference-only decisions in the
next calibration increment.
