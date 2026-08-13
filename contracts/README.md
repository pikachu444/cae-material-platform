# Public contract baseline

Status: foundation `T-02` through `T-18`, plus reference vertical subsets `T-07`, `T-08`,
`T-11`, `T-12`, `T-19`, `T-20`, `T-21`, `T-22`, `T-25`, `T-26`, `T-27`, `T-28`, `T-29`,
the `T-32` workbench, and product-depth slices `T-39` through `T-42`. HTTP contract version
`0.38.0`.

## Files

- `http/openapi.yaml`: REST source contract
- `http/openapi.baseline.yaml`: last accepted compatibility baseline
- `events/asyncapi.yaml`: CloudEvents 1.0 ArtifactAvailable and Schema Bundle applied events with
  at-least-once delivery contracts
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
- `catalog/schema-definition-bundle.schema.json`: arbitrary-cardinality Catalog Schema Definition
  Bundle v1 with a closed draft 2020-12 keyword/extension subset and bundle-local references only
- `catalog/schema-definition-plan.schema.json`: exact Artifact-bound deterministic
  `create/update/no-op/conflict/error` dry-run result with an explicit empty write set
- `catalog/schema-definition-bundle-application.schema.json`: immutable apply/read-back evidence and
  the exact Artifact/SHA-256/`plan_fingerprint` request boundary
- `units/unit-resources.schema.json`: bounded common CAE dimension/unit registry, explicit
  conversions, structured errors, and immutable Unit Profile resources; `kg_m_s` remains a
  compatibility identifier rather than a production default
- `datasets/curve-channel-metadata.schema.json`: additive curve definition contract `1.0.0` for
  channel roles and quantity semantics, original/normalized/display units, exact scale/offset,
  typed scalar or pointwise deviation evidence, immutable Artifact/revision/source pins, and
  calculation provenance
- `ir/material-model-ir-envelope.schema.json`: common IR envelope baseline
- `datasets/reference-tensile-resources.schema.json`: typed reference tensile Dataset, curve, and
  immutable one-member Selection resources
- `datasets/viscoelastic-master-resources.schema.json`: ordered exact-revision viscoelastic
  replicate Selections with temperature and explicit outlier-assessment status
- `datasets/governed-import-resources.schema.json`: approved reusable CSV/TSV/XLSX Import
  Profiles, needs-input previews, terminal Import Runs, and raw/normalized typed Dataset metadata
- `testing/reference-import-resources.schema.json`: immutable header-only Detection Report and
  human-confirmed typed Import Mapping identity/revision resources
- `testing/test-context-resources.schema.json`: governed Campaign, Instrument, dated Calibration,
  typed Condition Snapshot, and exact Test Run Context revision resources
- `processing/reference-tensile-crop-resources.schema.json`: typed crop/common-grid Recipes,
  committed member Runs, and grouped replicate alignment output
  resources for the reference Processing slice
- `processing/reference-import-resources.schema.json`: typed pinned reference Import Run resource
  with immutable inputs and terminal Dataset output link
- `processing/viscoelastic-master-curve-resources.schema.json`: explicit manual/WLF shift Plan,
  terminal Run, three typed output revisions, and bounded aligned/statistics/master preview
- `statistics/reference-tensile-pair-resources.schema.json`: typed two-selection reference
  Statistics/QC Plan, committed Run, scalar/curve Result, and bounded curve preview resources
- `statistics/reference-tensile-outlier-resources.schema.json`: typed immutable reference-pair
  Detection Plans, zero-or-two review_required candidates, append-only human Assessments, and
  exact-scope comparison resources without source mutation or automatic exclusion
- `statistics/reference-tensile-replicate-outlier-resources.schema.json`: non-production
  multi-replicate modified-z evidence, append-only human Assessment, and immutable calibration
  input Scope resources that preserve every source Dataset and Selection revision
- `validation/reference-virtual-specimen-resources.schema.json`: typed non-production reference
  virtual-specimen Template/Plan revisions, exact immutable IR/Card/Selection pins, durable Run,
  and shared mock/manual Result Manifest Artifact evidence
- `validation/reference-result-interpretation-resources.schema.json`: typed non-production
  response extraction, numerical-health, observed-grid comparison, and immutable reference verdict
  evidence; it does not claim production model or solver validation
- `governance/review-resources.schema.json`: immutable review request/decision resources with
  manifest-digest pinning, lifecycle state, and separation-of-duties evidence
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
- Schema Definition Bundle v1 preserves its exact immutable Artifact identity and accepts only local
  fragments or exact record `$id` references declared inside the same bundle. Source and bundle
  organization/project/classification must match. Unknown keywords,
  external URL/file/network references and unrepresentable Catalog projection fail closed. Planning
  reads an RLS-bound repeatable read-only snapshot and treats stale exact dependency revision pins as
  updates. It folds append-only placement history by logical Profile/Table key and never deletes
  missing Catalog objects. Apply re-plans under a project/table lock and accepts no client actions;
  its revisions, exact publication markers, immutable application/bindings, Artifact provenance,
  audit and outbox event share one transaction. Export is allowed only while current heads and
  publication still equal the application bindings, then returns canonical JSON from the exact
  retained source Artifact.
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
- The reference importer records header evidence separately from user confirmation. A Detection
  Report always remains `needs_input`; a human-confirmed Mapping revision pins its Raw
  Asset/Artifact and digest, and an Import Run must pin that concrete revision before it can create
  Dataset output. Low-confidence suggestions never become a committed mapping automatically.
- A reference Statistical Plan pins exactly two distinct normalized Selection revisions from distinct
  Test Runs. Curve statistics require identical observed engineering-strain grids; the contract
  explicitly forbids implicit alignment/resampling and marks the two-sample confidence interval as
  `not_provided_reference_pair`.
- A curve preview validates the complete immutable Artifact before producing a same-index bounded
  sample. Contract `1.0.0` distinguishes `declared`, reviewed `legacy_compatible`, and honest
  `absent` metadata. Only an explicit lower/upper pair with one band group is rendered as a band;
  method/version, pointwise or simultaneous coverage, confidence/quantile parameters and source
  counts retain their recorded meanings. Unknown legacy formats remain readable as values without
  inferred channels, units, deviation or Fit eligibility; known-but-corrupt formats fail closed.
- Common-unit quantities use the exact #205 registry and Unit Profile trace. Existing canonical
  quantities outside that closed registry, including `frequency.cyclic`/`Hz`, require their stored
  explicit scale/offset and are neither rejected nor added to the registry by this contract.
- A reference Validation Plan pins concrete Template, Material Model IR, Solver Card, and
  experimental Selection revisions; `reference_inline_mock` and `manual_attach` share one
  immutable Result Manifest shape. T-28 extracts a typed SI response only from bounded native
  evidence, records numerical health separately, and compares at the observed experimental strain
  grid with explicit linear interpolation and no extrapolation. Normal termination alone is not a
  pass; abnormal/unhealthy output and fitted-selection overlap are `not_evaluated`. No shell command
  field is public.

Run `make check-contracts` after every contract change. Accepting a breaking change requires a new
major contract, an ADR, and migration guidance; do not overwrite the baseline to hide the break.

