# Issue #207 — Schema Definition Bundle apply/export evidence

## Boundary and starting state

This packet records bounded implementation evidence for GitHub issue #207. Work started from fetched
`origin/main` `4c272cd35990a4b3db8a62da9b57c5262cdbf191` on branch
`agent/issue-207-schema-bundle-apply-export` in managed worktree
`C:\SourceCodes\cae-material-platform-issue207`. The original checkout remained clean at the same SHA
and was not modified. #207 was the first unfinished #117/backlog unit; #210 is the next unit and is
not part of this work.

The issue body, active owner instructions, root `AGENTS.md`, backlog row 21, affected contracts and
ADR-0028 are authority. From #204 evidence, this work uses only its implemented contract and Scope
handoff; the old draft/merge status is not current delivery evidence. The active product decision is
that the same Schema Administrator may approve Apply, and that successful bundle Apply atomically
publishes the exact projected revisions. General direct single-revision publication remains disabled.

Initial implementation classification was:

| Classification | Starting `main` state |
| --- | --- |
| Complete | Bundle/plan `1.0.0`, strict bundle-local resolver, deterministic no-write planner and RLS repeatable-read snapshot; configurable Catalog revision/publication; Artifact, provenance, audit and outbox foundations |
| Partial | Per-object Catalog CRUD and revision hooks each owned a transaction; layouts had no stable bundle-owned key outside planner memory |
| Missing | Apply/read-back/export API and permission, transaction-scoped revision boundary, bundle/version/application/binding persistence, server re-plan and locking, retry idempotency, Record migration block, exact source-to-revision lineage and applied event |

## Primary user journey and acceptance

| Part | Issue-owned journey |
| --- | --- |
| Setup | A Schema Administrator stores the synthetic three-record Bundle as one verified immutable Artifact in the selected organization/project and requests its no-write plan. Existing unrelated Catalog objects are present. |
| Actions | Inspect the ordered plan, approve the exact Artifact ID/SHA-256 and `plan_fingerprint`, submit Apply with `delete_missing=false` and a new idempotency key, read the returned Location, export the current bundle, upload that JSON and plan it again. |
| Visible/API outcome | Apply returns 201 with ordered create/update/no-op results and exact publication/source coordinates. Exact replay returns 200 and the same application. Export returns canonical Bundle JSON and source/digest headers; re-plan is all no-op. |
| Persistence/read-back | Stable bundle/version, immutable application and per-object bindings retain source Artifact, before/after snapshot fingerprints, exact revisions/content hashes/publication state, actor and idempotency evidence. Every newly created revision has a derivation from the exact source Artifact. |
| Preserved state | Previous revisions and unrelated objects remain; absent bundle members are not deleted; `delete_missing=false`; direct publication stays disabled; canonical Material/Test Data/IR aggregates are not replaced; no default Unit Profile or production semantics is selected. |
| Recovery | Stale fingerprint requires a new plan. Checksum/tenant/integrity mismatch, reused key with different evidence, semantic-version reuse, binding drift or current Record conflict fails closed. Any injected write failure rolls revisions, heads, publication, provenance, application, audit and outbox back together. |
| Owned scope | Catalog bundle application service/API/PostgreSQL adapter and migration, shared transaction-scoped revision entry point, apply permission, additive contracts/event, focused tests, affected current/authority docs and this evidence. |
| Forbidden shortcuts | No duplicate plan token; no client action/projected-content execution; no sequential per-object commits; no in-place revision mutation, auto-delete, user migration code, generic EAV, direct plugin DB access, UI work or #210 implementation. |
| Exact acceptance | Issue completion criteria and required tests; HTTP/runtime/schema parity; migration head; affected Ruff/Mypy/architecture/contracts/docs/pre-publish gates; one independent Balanced audit of the exact final SHA with no blocking or material finding before ready/merge. |

## Implemented transaction and idempotency boundary

Apply has a distinct `catalog.schema.apply` command permission granted through the Administrator
Schema configuration preset. The request contract contains only Artifact ID, lowercase Artifact
SHA-256, the existing `plan_fingerprint`, fixed `delete_missing=false`, and a required visible-ASCII
`Idempotency-Key`; Pydantic rejects extra client actions or projections.

The service reads exact verified Artifact bytes, then the PostgreSQL adapter opens one explicit
transaction. It takes a tenant/project advisory transaction lock and `SHARE ROW EXCLUSIVE` locks on
all affected Catalog schema/Record/publication/application and Artifact/integrity tables. Under those
locks it rechecks Artifact identity, digest, scope and verified state, reads the current RLS snapshot,
and runs the existing planner again. Only that server-owned plan executes. A different fingerprint or
invalid plan exits before writes. The lock mode conflicts with existing CRUD row writes, so no
validation-to-write window remains even though legacy CRUD calls keep their own transaction boundary.

`RevisionService.create_in/revise_in` and `SqlAlchemyRevisionStore.transaction_in` let bundle Apply
stage typed revision hooks in the caller transaction. Artifact manifest reads and provenance, audit
and outbox writes are injected transaction participants rather than cross-module private imports.
Dependency-ordered Catalog revisions/current heads, exact publication markers, placement, source
Artifact usage/derivation, stable bundle/version, immutable application/bindings, audit and the
applied outbox event commit together. A current Record blocks Table revision; current Attribute
values block Attribute revision; a new required Attribute blocks when current Records exist. No
migration code runs.

Idempotency is scoped by organization/project and key. The stored request digest covers exact
Artifact ID/SHA-256, `plan_fingerprint` and `delete_missing`. Same key/same digest returns the original
application before a new plan or write; same key/different digest is a conflict. A fresh key after a
fully applied bundle stores a no-op application but creates no revision or publication marker.
Concurrent same-key requests serialize at the project lock and converge on one application.

## Contracts, migration and export

- Bundle and plan remain `1.0.0`; application/read-back and applied CloudEvent are additive `1.0.0`
  contracts. HTTP/OpenAPI is `0.36.0`; AsyncAPI is `0.3.0`.
- Migration `20260928_097_issue207_bundle` adds four normalized RLS tables for stable Bundle,
  semantic Version, immutable Application and ordered Binding. Source Artifact FKs use `RESTRICT`,
  immutable rows have mutation-rejecting triggers, and downgrade refuses while application evidence
  exists.
- Apply publishes exact projected Database/Profile/Table/Attribute/Layout/Link Type revisions inside
  the bundle transaction. Profile/Table placement stays append-only and has no fabricated revision.
- Each binding records exact source schema ID/version and JSON Pointer. The application pins the
  immutable source Artifact ID/SHA-256 and before/after Catalog fingerprints. One
  `io.cmp.catalog.schema-definition-bundle.applied.v1` outbox event carries only bounded identities
  and digests.
- Export first checks every current head, revision/content hash and publication marker against the
  current application. It then re-verifies and canonicalizes the exact source Artifact. Drift or a
  missing retained source fails closed rather than reconstructing authority from mutable heads.
- Backup/restore must therefore preserve the four application tables, bound Catalog revisions and
  publication, source Artifact metadata/integrity/object bytes, provenance, audit and outbox at one
  recovery point. Retention duration remains `OQ-SEC-004`; this issue chooses no new duration.

## Verification record

| Gate | Result |
| --- | --- |
| API apply/read-back/export, extra-field rejection and stale error mapping | PASS — focused API suite, 6 tests |
| PostgreSQL plan/apply/idempotency/rollback/round-trip/concurrency/tenant/Record conflict | PASS — isolated PostgreSQL 16, 3 tests |
| Exact revision publication and Artifact provenance | PASS — integration asserts every created revision has the source derivation and all revision targets are published |
| Existing #204 planner, bundle domain, authorization and API regression | PASS — focused unit/contract/API/migration set, 113 tests; repository suite, 1,500 passed and 95 PostgreSQL skips |
| Contract/schema/runtime/generated client and migration | PASS — contract lint and OpenAPI compatibility; runtime parity; deterministic client regeneration; migration static checks and PostgreSQL upgrade → downgrade `096` → upgrade `097` |
| Ruff, architecture, user-guide, docs impact and diff | PASS — full Ruff; architecture; 20 guides/560 links; 0 visual sources; `git diff --check` |
| Mypy | BASELINE-EQUIVALENT — feature and untouched starting main both report the same pre-existing 31 errors in 7 files; targeted #207 paths add no error |
| Full pytest baseline boundary | PASS WITH EXACT DESELECT — 1,500 passed, 95 PostgreSQL skips, 3 deselected. Two AGENTS/backlog assertions fail unchanged on starting main; the #184 crop test embeds the original checkout absolute path and passes there but not in this managed worktree. None intersects #207 paths. |
| Pre-publish | PENDING clean committed feature SHA |
| Canonical Compose | BLOCKED AS CANONICAL EVIDENCE — `make` is unavailable and fallback preflight found running canonical containers owned by preserved #204/#206 worktrees. They were not stopped, recreated or deleted. An issue-owned standalone PostgreSQL 16 container is used only for DB integration. |
| Browser/viewport/visual | N/A — no React/CSS, navigation or user-visible UI change; Administration UI is #208 |
| Independent exact-SHA Balanced audit | PENDING until all modifications and automatic gates finish |

The issue-owned PostgreSQL container is `cmp-issue207-postgres`, using a dynamically published local
port and disposable per-test databases/roles. It is not acceptance evidence for canonical Compose
health, but it exercises migrations, NOSUPERUSER/NOBYPASSRLS application-role policies and actual
transaction rollback without touching another worktree's volumes.

## Publication and handoff

Feature PR, exact audited SHA, CI result and squash merge SHA are recorded after publication. Any
post-audit source or documentation change requires the same independent auditor to review the new
SHA. After the feature merge, the separately approved tracking-only PR records the actual merge SHA
in backlog/issue/parent state. The next backlog task is #210; its implementation is not started here.
