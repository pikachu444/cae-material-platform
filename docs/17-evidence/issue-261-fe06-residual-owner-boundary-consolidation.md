# Issue #261 FE-06 — residual owner-boundary consolidation

Status: **Main live/browser/original-resolution acceptance passed**. The corrected candidate is
based on `599278067ab5f69d46ea59559344499399b51fed` (PR #317) and remains uncommitted for the
Balanced independent completed-result audit.

## Frozen scope and oracle

The frozen source-order oracle is
[`issue-261-residual-owner-boundary.json`](../../scripts/fixtures/issue-261-residual-owner-boundary.json).
It records every target tuple as `(id, source, source-group, selector, at-context, declaration
hash)` and is regenerated only from the committed base inventory. The first live cold-route audit
corrected the broad subject-token routing defect, retained 11 additional shared primitives at their
exact eager layout rank, and added 27 selectors with no exact current production DOM topology to
the M6 handoff:

| Frozen disposition | Rows | Groups | Tuple digest |
| --- | ---: | ---: | --- |
| Audited owner migration | 525 | 438 | `79813edef612bbf1c1123dd58e21b74480f0e8814ee34f9b89ae3d592c57ed68` |
| Accepted in place | 22 | — | 11 prior + 11 cascade-rank-preserving shared rows |
| Original M6 oracle | 529 | 475 | `5108b2a5b1e58072f295a199e7b8b4072f1c30c7ca27c0a0b8061405830953d7` |
| Corrected M6 handoff | 556 | 495 | `41a6cda0826c330fbf430462e8dbfc0de8041f2cd9344baf9ce1c08c66ffc900` |

The target tuples were assigned to existing owner CSS without changing selector text, declaration
text, at-context, relative source order, React/DOM/API/routes/copy/state, or exact-revision
contracts. The implementation moves complete peer groups where safe and splits only mixed groups
using the source-order oracle. No M6 row is deleted or rewritten; the 27 audit-proven
zero-topology rows are preserved in source and explicitly added to the M6 handoff.

## Owner boundary

The regenerated owner accounting is:

| Owner | Rows | Groups |
| --- | ---: | ---: |
| Materials | 65 | 60 |
| Activity | 4 | 4 |
| Shared primitives | 49 | 42 |
| Modeling Process stage | 39 | 27 |
| Modeling core | 5 | 5 |
| Modeling validation | 1 | 1 |
| Materials curve contract | 1 | 1 |
| Administration | 23 | 22 |
| Modeling Fit stage | 6 | 6 |
| Modeling stage normalization | 13 | 3 |
| Modeling Data stage | 1 | 1 |
| Modeling engineering plot | 16 | 10 |
| Test Data governed import | 22 | 18 |
| Test Data canonical | 37 | 33 |
| Modeling scalar distribution | 135 | 113 |
| Shared shell | 4 | 4 |
| Shared typography | 15 | 11 |
| Modeling calibration | 20 | 20 |
| Modeling Export stage | 24 | 19 |
| Modeling Export/delivery | 16 | 13 |
| Modeling viscoelastic | 18 | 18 |
| Domain workflow links | 11 | 8 |

All counts are derived from the fixture rather than manually maintained selector lists. The
post-migration inventory is 578 legacy selector rows / 517 rule groups: 22 accepted in place and
556 M6 candidates, with zero FE-06 target rows remaining. The original 529-row M6 oracle is
byte-for-byte preserved; the 27 added rows remain present and are not deleted by this unit.

## Primary journey and preserved contracts

The preserved journey is Materials Browse/Search → exact Material revision → Start Modeling →
Test Data → Process → Fit → reviewed Export, with Materials read-back where applicable. This unit
only relocates CSS ownership. It does not alter selected Material/State/Test Data identity,
revision/hash pointers, saved result state, API payloads, route parameters, keyboard behavior, or
recovery behavior. The source transformer and regression test prove the exact target tuple set is
owned once, source order is preserved, and every M6 tuple remains present once.

Forbidden shortcuts were not used: there is no selector copy, generic EAV, CSS framework, route
one-off, zoom/scale, golden masking, or arbitrary normalization. Existing owner imports and shared
design contracts are retained.

## #249 synthesis review record

- Information hierarchy: **PASS by live preservation review**. Results, exact identity/revision, dominant graph
  or native preview, and subordinate evidence/delivery surfaces retain their existing hierarchy;
  this unit adds no competing inspector or nested card treatment.
- Engineering task flow: **PASS by live preservation review**. Materials-to-Modeling handoff and the exact
  Data → Process → Fit → Export sequence remain unchanged; the moved rules are routed to the
  feature that already owns the corresponding surface.
- Responsive/wide-screen composition: **PASS** at 1366×768, 1440×900, 1920×1080, 2560×1440,
  and 3840×2160 at zoom 100% / DPR 1. Thirteen cold-route topologies, their required crops, and
  305 before/after pairs passed; physical Windows 4K readability remains deferred to #223.

The fresh live packet is registered at
[`images/issue-261-fe06-residual-owner-boundary-consolidation/live/manifest.json`](images/issue-261-fe06-residual-owner-boundary-consolidation/live/manifest.json).
The established M4 capture schema was reused only as the 13-topology/five-viewport harness; this
document and the FE-06 fixture are authoritative for corrected ownership counts.

## Gates run

- `node scripts/check_issue_261_residual_owner_boundary.test.mjs`: **PASS**, 4/4.
- `node scripts/check_issue_261_css_inventory.mjs`: **PASS**, 578 rows / 517 groups; M6 556.
- `node scripts/check_frontend_guard.mjs`: **PASS**, 0 violations / 15 baseline warnings.
- `npm run test:web`: **PASS**, 71 files / 412 tests.
- `npm run build`: **PASS**, TypeScript, Vite production build, bundle check.
- `npm run test:bundle-budget --workspace @cmp/web`: **PASS**, 24/24.
- Fresh live capture/comparison/check: **PASS**, 13 topologies × 5 viewports, 610 images,
  305 pairs, 229 pixel-identical; status `ACCEPTED_MAIN_VISUAL_AND_RUNTIME`.
- `npm run check:storybook --workspace @cmp/web`: **PASS**; existing chunk-size warnings only.
- `uv run cmp-check-user-guide --root .`: **PASS**, 20 guides / 124 current captures.
- `uv run cmp-check-doc-impact --root . --mode worktree`: **PASS**, 30 changed files / 19
  visual sources / 19 byte-identical CSS sources.
- `git diff --check`: **PASS** (Git reports only existing LF→CRLF normalization warnings).

The root `npm test` command is **not applicable/blocked** because the root package exposes no
`test` script; the workspace web test command above is the repository's declared frontend gate.
The broad historical command `node --test scripts/check_issue_261*.test.mjs` was also exercised:
44 of 55 cases passed, including all three FE-06 tests and the cumulative inventory/M4/M1E handoff
tests. Eleven prior-unit cases rejected the expected later cumulative ownership state (M1E3, M1E4,
M1E5, M2, and M3 frozen-base/complement assertions). Those failures are not reclassified as FE-06
defects; the prior-unit proofs remain historical and their exact frozen-base gates are not rewritten
in this unit.
Canonical disposable Compose seeding, cold-route browser capture, interaction assertions, and
permanent-demo isolation all passed. Physical Windows 4K readability remains deferred to #223.

## Handoff and residual risk

The exact next handoff is M6 zero-consumer audit/removal for 556 rows / 495 groups. It must start
from this regenerated inventory and fixture, prove no live consumer and no cascade peer, then run
the same source-order, guard, browser, and visual gates before deleting any M6 row. Until then the
M6 rows in legacy CSS are intentional and immutable from this unit.

Residual risk is limited to the pending Balanced independent audit and physical Windows 4K
readability deferred to #223. The candidate has no known compile, bundle, frontend-test,
inventory, guard, browser, visual, guide, or documentation-impact failure.
