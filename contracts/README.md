# Public contract baseline

Status: `T-02` + `T-03` + `T-04` + `T-06`, HTTP contract version `0.4.0`.

## Files

- `http/openapi.yaml`: REST source contract
- `http/openapi.baseline.yaml`: last accepted compatibility baseline
- `events/asyncapi.yaml`: asynchronous contract shell; no domain events yet
- `jobs/*.schema.json`: immutable runner envelopes
- `plugins/plugin-manifest.schema.json`: package metadata baseline
- `ir/material-model-ir-envelope.schema.json`: common IR envelope baseline
- `revisions/revision-metadata.schema.json`: content-free typed-revision metadata envelope
- `identity/me-response.schema.json`: authenticated principal and selected tenant context
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
- `/api/v1/me` accepts bearer access tokens; ID tokens are not an interchangeable credential.
- Identity responses require both organization and project UUIDs. `/me` remains an authenticated
  identity/context response and does not imply authorization. Each protected endpoint must bind an
  explicit T-04 permission before opening its resource transaction.
- Role and clearance details are internal policy state rather than a public `/me` field. A future
  role-management API requires its own versioned request/response schema.

Run `make check-contracts` after every contract change. Accepting a breaking change requires a new
major contract, an ADR, and migration guidance; do not overwrite the baseline to hide the break.

