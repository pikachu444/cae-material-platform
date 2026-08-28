# Issue #342 Task 1B — exact JSON Record registration evidence manifest

## Evidence boundary

This manifest records the implemented feature-owned route and Main acceptance evidence. JSON and the
existing CSV/TSV/XLSX paths share the single **Import records** workspace under
`/administration/records`; there is no second peer command. The production implementation preserves
`/catalog/records` compatibility and the shared `Materials | Modeling | Activity` shell.

## Required live states

| State | Route | Required observable evidence |
| --- | --- | --- |
| Installed format detection | `/administration/records` | The operator uses one Import records command and Add files; file bytes choose JSON or the legacy tabular path, and the server detects one exact installed format while the normal surface shows only the detected content name. |
| Multi-file staging | `/administration/records` | Multiple same-format JSON files remain listed by original filename; deterministic package and artifact identity stay in the API/evidence contract rather than the normal surface. |
| Rejected preview | `/administration/records` | Preview stays non-authoritative; rejected filename, stable cause, JSON Pointer and line/column or byte offset are visible with recovery text. |
| Atomic draft result | `/administration/records` | Reason for change plus one local Save action creates a DRAFT batch only; the left step says Save draft and the workspace never exposes a publication action. |
| Exact source read-back | exact Record revision link | Source JSON returns original bytes/name and source CSV uses the fixed source-aware header; both expose exact SHA response evidence. |
| Materials visibility | `/materials` | Only published records and stored approved exact-revision links are visible; draft/unreleased records remain absent while legacy CSV remains available. |

## Main-owned capture matrix

The complete 9-state × 5-viewport original set, shared component/style inventory, normal-surface string
inventory, measurements, and direct crops are registered in
`docs/17-evidence/issue-342-task1b-frontend-design-packet.md` and
`docs/17-evidence/issue-342-ui-acceptance/live/`. Main opened every original at source resolution.
The product owner reviewed the presented 1920/2560/3840 valid-preview originals and approved the corrected
page on 2026-08-28.

## Automated implementation evidence

- Strict JSON/package, contract, migration, source-v2 fixture, architecture, and seed checks passed.
- Feature-owned Administration and Materials tests, production build, deterministic package behavior,
  legacy import compatibility, exact download actions, and the browser flow passed.
- The browser flow covers selection, upload recovery, invalid/valid preview, atomic-save retry, saved
  read-back, five-viewport geometry, hidden surrounding Records surfaces, and no first-record fallback.
- The bounded correction adds an immutable pending-batch association for every finalized curve Artifact.
  A focused failure injection proves that a failed Record transaction leaves no Record, provenance, link,
  token-commit, or ready fact; the open preview, batch, and exact Artifact association remain retryable, and
  retry reuses the same batch/Artifact identities before appending ready once. Backend/migration checks pass
  15 tests and the affected frontend component passes 11 tests.
- Five valid-preview originals at the required viewports use the fully fresh Docker PostgreSQL/API/browser
  run; the other forty state/viewport originals use production React with the repository-standard mocked
  API boundary for deterministic state coverage. Fresh-Docker acceptance passed 15 JSON records in
  3/4/3/2/2/1 batches, six ready latest states, exact source/provenance/name reload read-back, the five
  approved link types only, published-only search visibility, draft JSON/CSV downloads, published-only
  download rejection (409), and mixed valid+invalid atomic rollback (422, provenance 15→15).
