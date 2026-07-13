# Public contract baseline

Status: foundation `T-02` through `T-18`, plus reference vertical subsets `T-07`, `T-08`,
`T-12`, `T-19`, `T-22`, `T-25`, `T-26`, and the `T-32` workbench. HTTP contract version
`0.18.0`.

## Files

- `http/openapi.yaml`: REST source contract
- `http/openapi.baseline.yaml`: last accepted compatibility baseline
- `events/asyncapi.yaml`: CloudEvents 1.0 ArtifactAvailable event and at-least-once delivery contract
- `events/*.schema.json`: immutable event payload/envelope contracts without storage keys
- `jobs/*.schema.json`: immutable runner envelopes
- `artifacts/*.schema.json`: upload/Raw Asset plus immutable Artifact metadata, transfer grant,
  completion, and sanitized problem contracts
- `provenance/*.schema.json`: immutable Entity, bounded lineage/impact, generic provenance
  completeness, and sanitized problem contracts
- `audit/*.schema.json`: payload-free audit event page, bounded export, integrity report, and
  sanitized problem contracts
- `plugins/plugin-manifest.schema.json`: package metadata baseline
- `plugins/plugin-package-registration.schema.json`: signed package/SBOM/schema registration input
- `plugins/plugin-package-resource.schema.json`: immutable package and state-history resource
- `plugins/plugin-problem.schema.json`: sanitized registry problem response
- `ir/material-model-ir-envelope.schema.json`: common IR envelope baseline
- `datasets/reference-tensile-resources.schema.json`: typed reference tensile Dataset, curve, and
  immutable one-member Selection resources
- `processing/reference-tensile-crop-resources.schema.json`: typed crop Recipe and committed Run
  resources for the reference Processing slice
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
- These contracts contain only explicitly marked non-production reference material, tensile,
  processing, IR, and solver semantics; they make no production qualification claim.
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
- Provenance Entity responses expose immutable typed UUID/digest references and primary-generation
  completeness. T-14 lineage/impact responses are read-only, bounded, deterministically ordered,
  and cursor-paginated; completeness is eligible only when no issue remains. Moving heads and
  graph writes are rejected, and Release-specific policy remains outside this contract.
- ArtifactAvailable is emitted from the same transaction as Artifact commit, uses aggregate
  sequence and tenant/classification CloudEvent extensions, and exposes content metadata but no
  staging/final object key. Duplicate delivery is expected and consumer inbox deduplication is
  mandatory.
- Plugin registration separates a stable Definition from immutable version/digest Packages. A
  package becomes eligible only after an authorized verification event and activation is scoped to
  the selected organization/project; revocation never overwrites package or state-history facts.
- Audit access is read-only and requires `audit.read`. Events expose explicit actor/action/target,
  outcome, request/trace, redacted client, reason, and hash fields; raw payloads, secrets, and object
  keys are forbidden. Export is capped at 10000 events and includes its chain anchor and roots.
- A reference Processing Run pins one normalized Dataset revision and one typed crop Recipe revision.
  Its processed output is a separate immutable Dataset identity, never a replacement for raw or
  normalized source bytes. Generic processing payloads and implicit interpolation are forbidden.

Run `make check-contracts` after every contract change. Accepting a breaking change requires a new
major contract, an ADR, and migration guidance; do not overwrite the baseline to hide the break.

