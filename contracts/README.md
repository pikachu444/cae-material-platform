# Public contract baseline

Status: `T-02` + `T-03` + `T-04` + `T-06` + `T-09` + `T-10` + `T-13` + `T-15` +
`T-17` + `T-18`, HTTP contract version `0.10.0`.

## Files

- `http/openapi.yaml`: REST source contract
- `http/openapi.baseline.yaml`: last accepted compatibility baseline
- `events/asyncapi.yaml`: asynchronous contract shell; no domain events yet
- `jobs/*.schema.json`: immutable runner envelopes
- `artifacts/*.schema.json`: upload/Raw Asset plus immutable Artifact metadata, transfer grant,
  completion, and sanitized problem contracts
- `provenance/*.schema.json`: immutable Entity/completeness lookup and sanitized problem contract
- `plugins/plugin-manifest.schema.json`: package metadata baseline
- `plugins/plugin-package-registration.schema.json`: signed package/SBOM/schema registration input
- `plugins/plugin-package-resource.schema.json`: immutable package and state-history resource
- `plugins/plugin-problem.schema.json`: sanitized registry problem response
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
- Job submission requires an idempotency key and an immutable Job Spec. Retry appends a new
  Attempt/Spec pair; it never rewrites an existing attempt or accepts a moving `latest` input.
- Result manifests remain immutable references and digests. T-10 owns Artifact finalization and
  integrity observations; T-16 owns durable scheduling/outbox rather than the T-15 projection.
- The T-18 Python runner packages exact copies of Job Spec/Result Manifest 1.0. A Result Manifest
  records whether the runtime was non-production; the execution service rejects a mode mismatch.
- Upload creation pins filename/MIME/size/SHA-256 and streams immutable numbered parts. Raw Asset
  responses expose digest and `staged_verified` state but never an internal object-store key;
  completion may return the T-10 available Artifact ID.
- Artifact metadata exposes content digest, semantic role/schema, encryption profile, and current
  integrity status. Staging/final object keys stay internal; byte transfer requires bearer
  authorization plus an actor/tenant/content/expiry-bound capability header.
- Provenance Entity responses expose an immutable typed UUID/digest reference and primary
  generation completeness. No public graph-write or recursive lineage endpoint is part of T-13;
  moving head aliases are rejected and T-14 owns bounded traversal.
- Plugin registration separates a stable Definition from immutable version/digest Packages. A
  package becomes eligible only after an authorized verification event and activation is scoped to
  the selected organization/project; revocation never overwrites package or state-history facts.

Run `make check-contracts` after every contract change. Accepting a breaking change requires a new
major contract, an ADR, and migration guidance; do not overwrite the baseline to hide the break.

