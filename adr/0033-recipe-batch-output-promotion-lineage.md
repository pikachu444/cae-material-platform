# ADR-0033: Exact Recipe/Batch execution lineage for promoted Processing Outputs

- Status: Accepted
- Date: 2026-07-19
- Deciders: CMP maintainers
- Related: ADR-0029, ADR-0031, T-54, T-55P, T-67, T-69

## Context

A common Processing Output pins its exact Test Data, Mapping Profile, ordered method versions and
result Artifact. A successful Batch Attempt already pins that Output revision and its Batch pins an
exact published Processing Recipe revision. T-67 could promote the Output to a generalized-Maxwell
IR, but did not resolve this existing execution relation. Consequently its Neutral JSON correctly
described direct steps while failing to prove that the steps came from a saved, reusable Recipe.

Copying Recipe fields onto every Processing Output would duplicate ownership and could diverge from
the append-only Batch Attempt record. Searching only by the current Recipe or Output head would also
break reproducibility.

## Decision

The successful `common_processing_batch_attempt` remains the authoritative relation between an
exact Processing Output revision and the exact published Recipe revision owned by its Batch.
Processing exposes a read port that resolves this relation under the caller's tenant and
classification scope. Modeling consumes that port during reviewed polymer promotion and stores:

- exact Recipe identity, revision and canonical digest;
- exact Batch, Member and successful Attempt identities and attempt number;
- the existing exact Output, Test Data and Mapping Profile evidence.

Migration 080 adds nullable typed columns, composite exact-revision foreign keys, an all-or-none
constraint and a deferred trigger that proves the Attempt succeeded and produced the same Output
revision. The IR canonical schema is `1.3.0` when this origin exists. Historical direct Outputs keep
their `1.2.0` evidence and remain readable.

Neutral promotion maps the exact Recipe revision into `processing_recipe.status=exact_revision`.
The Batch execution identifiers remain in typed IR evidence; the Neutral exchange does not invent a
second Batch schema. Bulk discovery then includes the exact Recipe JSON together with Test JSON,
Mapping Profile, Neutral JSON, reports and both eligible native cards.

## Consequences

- A saved polymer Recipe can be published, batch-executed, reviewed and followed without a `latest`
  alias through IR, Neutral JSON, solver cards and checksum package.
- Direct historical Outputs are not rewritten and clearly report that no Recipe/Batch pin exists.
- An Output produced outside Batch remains promotable for compatibility, but cannot claim Recipe
  reuse evidence.
- No new generic EAV or JSON authority is introduced; PostgreSQL constraints verify the lineage.
