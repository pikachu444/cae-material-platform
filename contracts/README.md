# Public contract baseline

Status: `T-02` + `T-06`, HTTP contract version `0.2.0`.

## Files

- `http/openapi.yaml`: REST source contract
- `http/openapi.baseline.yaml`: last accepted compatibility baseline
- `events/asyncapi.yaml`: asynchronous contract shell; no domain events yet
- `jobs/*.schema.json`: immutable runner envelopes
- `plugins/plugin-manifest.schema.json`: package metadata baseline
- `ir/material-model-ir-envelope.schema.json`: common IR envelope baseline
- `revisions/revision-metadata.schema.json`: content-free typed-revision metadata envelope
- `examples/positive`: examples that must validate
- `examples/negative`: examples that must be rejected

## Versioning policy

- Major: semantic or structural breaking change
- Minor: backward-compatible additive change
- Patch: clarification or non-semantic correction
- OpenAPI removals, response removals, property removals, and optional-to-required changes fail the
  baseline compatibility check.
- JSON Schema and event contracts use their own explicit version fields and immutable schema IDs.
- This baseline contains no production material, test, calibration, or solver semantics.
- Revision content remains resource-specific; the common schema must never gain a generic
  `content`/EAV payload.

Run `make check-contracts` after every contract change. Accepting a breaking change requires a new
major contract, an ADR, and migration guidance; do not overwrite the baseline to hide the break.

