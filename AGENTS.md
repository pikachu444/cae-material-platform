# Implementation Instructions

## Read first

1. `README.md`
2. `docs/02-requirements/requirements.md`
3. `docs/03-domain/canonical-domain-model.md`
4. `docs/04-provenance/revision-and-provenance.md`
5. `docs/05-architecture/system-architecture.md`
6. the task in `docs/13-delivery/backlog.md`
7. relevant plugin/IR/API/test/security documents

## Non-negotiable invariants

- Raw bytes and released artifacts are immutable.
- Stable identities and immutable revisions are separate.
- Runs reference concrete revisions, never `latest`.
- Original unit text, normalized unit, and quantity semantics are preserved.
- Outliers are never deleted; candidate and adjudication are separate records.
- Every derived entity has input usage, generation activity, and responsible agents.
- A production solver card requires a Material Model IR revision.
- Exporters must report exact/transformed/approximated/unsupported mappings.
- Core code must not import domain plugin implementations.
- Organization/project authorization is enforced at service and database levels.

## Do not decide TBD domain items

Do not choose or imply a production tensile standard, material family, constitutive model, optimizer policy, solver card, virtual specimen, or validation threshold. Use synthetic non-production reference plugins until the relevant open questions are resolved.

## Work by task

- Implement one backlog Task or a clearly bounded subset.
- Link requirement, ADR, and Task IDs in code/PR documentation.
- Define or update contracts before adapters.
- Add unit, integration, and regression tests listed by the Task.
- Obtain domain approval for numeric reference results, IR payload schemas, solver mappings, and golden files.

## Forbidden shortcuts

- Generic EAV tables for core domain data
- Row-per-point storage for large curves
- Mutable raw or released object keys
- Hidden unit conversion, resampling, smoothing, or manual curve edits
- Direct plugin database access
- In-process loading of production plugins by the API
- Silent solver mapping defaults or approximation
- Golden snapshot updates without software and domain review
- Real confidential test data in source control

