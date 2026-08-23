# Issue #262 FE-07A Materials architecture and UI refinement

Status: Main implementation, visual/runtime acceptance and canonical independent Balanced audit complete; Product Owner visual/geometry approval and merge approval pending.

Scope is FE-07A Materials only. Administration FE-07B, Modeling behavior, backend contracts, database data and released artifacts are unchanged.

## Characterization and bounded result

| Area | Before | FE-07A result |
| --- | --- | --- |
| Search, facets, totals and rows | Complete product behavior, but query orchestration and API projection lived in the root `material-library.tsx` hotspot. | Preserved as one server-scoped query and moved to the Materials controller/API boundary. Direct `?mode=filters` entry now resolves the default Materials table without relying on Browse mounting first. |
| Browse and selection | Complete four-peer-category tree, keyboard navigation and exact item selection; presentation retained a redundant bottom helper. | Preserved categories, focus, local scroll and result/detail selection. Removed only the redundant helper. |
| URL and return continuity | Partial ownership: query parsing, URL serialization, exact pins and session return data were embedded in the root surface. | Materials route state owns query/facet/sort/page/mode/selection, exact Material/Record pins, safe return paths and Browse selection continuity. |
| Exact detail, record and solver-card loading | Complete domain behavior with loading/error boundaries, but loaders and graph/card lineage assembly lived beside Activity UI. | Feature API owns exact/unpinned experience loading, immutable revision filtering, graph verification, representative curves and card lineage. No `latest`, first-item or cross-session fallback was added. |
| Datasheet information hierarchy | Partial: repeated kickers and a separate global Related data region created redundant scanning and a large internal void at 2560/3840. Curves repeated the same linked records without distinguishing their decisions. | Related data is adjacent to the active Overview/Properties/Curves decision. Curves distinguish `Modeling input` from immutable `Exact source records`; CAE delivery is labeled `CAE card applicability`; Evidence retains lineage. |
| Root ownership | Missing FE-07A boundary: the 1,855-line root file owned Materials and Activity. | `material-library.tsx` is 524 lines and owns Activity only. Materials has public `index`, route-state/model, query API, experience loader, controller and page UI boundaries. |

The structural extraction and semantic Materials normalization form one coherent FE-07A change: the state/API ownership move supplies the controller boundaries that the refined UI consumes, while the public routes, DOM contracts needed by regression tests, exact identity and server semantics stay preserved.

## Primary journey and acceptance contract

Setup uses the current worktree Compose web/API/worker against preserved synthetic non-production data. The realistic journey is:

1. Open `/materials`, use Browse or `?mode=filters`, search for DP780 and select the exact result.
2. Inspect Material identity, code, revision, conditions, source, properties and representative curve.
3. Inspect CAE-card applicability and immutable card/source lineage without manufacturing an unavailable card.
4. Open an exact Material or Record URL carrying `record_id`, `record_revision_id` and `material_revision_id`; reload and read the same revision back.
5. Use Results to return to the same query, table, Navigator mode and selected row.
6. Use Start Modeling and read the exact Material revision in the new Modeling session.
7. On a query error, retain the last valid rows and selection, show the cause and Retry, then recover without substituting another record.

Visible outcome: results remain dominant in the explorer/result/datasheet topology; the bounded Navigator and readable datasheet use the full viewport, while related source decisions stay next to the active tab. Persistence/read-back outcome: URL state, exact pins, reload, return path and exact Modeling handoff survive. Recovery outcome: loading, empty, blocked/error and Retry remain distinct; an error cannot erase the last valid result or silently select another revision.

Preserved contracts include the one server-scoped query for rows/totals/facets, query parameter names, exact Material/Record/card pins, Browse category meanings, Material/State/Test Data identity, immutable revision filtering, card lineage, local scroll/focus, API DTOs and Modeling session v4 context. Forbidden shortcuts remain absent: no `latest` or first-item fallback, no global-output/session fallback, no client-computed totals/facets, no route-specific 4K CSS, no CSS zoom/scale, no inferred lineage, no new state/UI framework and no FE-07B change.

Exact acceptance is satisfied when the affected unit/component/integration and browser regressions pass; production and Storybook builds and bundle/architecture guards pass; the five required viewport originals and direct crops have no clipping or page overflow; error/retry, reload/read-back, Results return and Start Modeling exact context pass; and the independent Balanced audit accepts the completed result. Product Owner approval of the original 1920/2560/3840 comparisons and merge remains a separate mandatory gate.

## Responsibility map

| Responsibility | Before owner | FE-07A owner |
| --- | --- | --- |
| Materials public exports | root `material-library.tsx` | `features/materials/index.ts` |
| Search query projection and default table discovery | root `api.ts` plus root page | `features/materials/api/search-materials.ts` |
| Query/facet/scope/sort/page/selection/retry controller | root page | `features/materials/controller/use-materials-search-controller.ts` |
| URL serialization, exact pins and safe return continuity | root page | `features/materials/model/materials-route-state.ts` |
| Exact Material/Record graph, curve and card experience loading | root page | `features/materials/api/load-material-experience.ts` |
| Search/Browse result composition | root page | `features/materials/ui/material-search-page.tsx` |
| Material detail, exact record and card preview | root page | `features/materials/ui/materials-pages.tsx` |
| Activity queue and outcomes | mixed root page | reduced root `material-library.tsx` |

`app.tsx` lazy-loads search independently from detail/exact/card pages, and Activity keeps its separate lazy root. Materials imports the Modeling session contract through the Modeling feature public boundary. The frontend guard baseline was mechanically rebased to the requested `50095db...` merge base, removed 32 stale #261 exceptions and adds only five exact #262 import-responsibility exceptions; enforcement remains at zero violations.

## Product/reference disposition

Current product authority requires four peer Materials categories and keeps Database/Profile/Table/Folder/Record vocabulary in Administration. Older #167 storage-hierarchy references therefore control only their approved explorer/result/datasheet geometry; they do not authorize the stale `CAE Material Database → Engineering Materials Profile` normal-surface vocabulary. The guide and screenshot manifest now describe the peer-category journey, while registered approved detail references continue to govern their target geometry.

The current guide detail captures and their approved geometry references remain directly comparable:

| Viewport | Current product | Approved reference |
| --- | --- | --- |
| 1366×768 | [current](../user-guide/images/current/material-detail-1366x768.png) | [approved #167 reference](images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png) |
| 1440×900 | [current](../user-guide/images/current/material-detail-1440x900.png) | [approved #167 reference](images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png) |
| 1920×1080 | [current](../user-guide/images/current/material-detail-1920x1080.png) | [approved #167 reference](images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png) |
| 2560×1440 | [current](../user-guide/images/current/material-detail-2560x1440.png) | [approved #167 wide-screen reference](images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png) |
| 3840×2160 | [current](../user-guide/images/current/material-detail-3840x2160.png) | [approved #167 wide-screen reference](images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png) |

## Visual evidence

The [structured manifest](images/issue-262-fe07a-materials-architecture-ui/manifest.json) records browser zoom 100%, DPR 1, 20 after geometry records, 20 before/after original pairs, 140 direct 100%-pixel crops, two recovery originals, hashes and exact continuity values. Main opened all 40 before/after originals, all 140 crops and both recovery originals at original resolution.

| State | 1366×768 | 1440×900 | 1920×1080 | 2560×1440 | 3840×2160 |
| --- | --- | --- | --- | --- | --- |
| Search | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-search-1366x768.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-search-1440x900.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-search-1920x1080.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-search-2560x1440.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-search-3840x2160.png) |
| Browse | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-browse-1366x768.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-browse-1440x900.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-browse-1920x1080.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-browse-2560x1440.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/materials-browse-3840x2160.png) |
| Detail | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-detail-1366x768.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-detail-1440x900.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-detail-1920x1080.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-detail-2560x1440.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-detail-3840x2160.png) |
| Curves | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-curves-1366x768.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-curves-1440x900.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-curves-1920x1080.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-curves-2560x1440.png) | [after](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-curves-3840x2160.png) |

The matching before originals use the same filenames under `before/originals/`. Search is intentionally pixel-stable except subpixel/native-scroll timing noise (0–0.0006%). Browse differences remove the redundant helper (0.15–1.43%). Detail and Curves differences are bounded to the datasheet body (6.34–11.44%) and place related data next to the active decision. The [error original](images/issue-262-fe07a-materials-architecture-ui/after/exceptions/materials-search-error-1440x900.png) retains the DP780 row and selection; the [recovered original](images/issue-262-fe07a-materials-architecture-ui/after/exceptions/materials-search-recovered-1440x900.png) truthfully shows the unmatched recovery query.

All 20 measurements have zero page horizontal overflow. The Navigator remains 288 CSS px while the main pane grows from 1,054 to 3,528 CSS px (78% to 92% of the workspace). Local detail/curve scrolling remains inside the main pane. At 3840, Related data now follows the active Overview/Curves content instead of appearing after a large unrelated internal void.

### Q-01 through Q-20

| Item | Result | Evidence and rationale |
| --- | --- | --- |
| Q-01 | not-applicable | The seeded peer-category tree is shorter than its viewport, so a fake rail is correctly absent; [1440 navigator crop](images/issue-262-fe07a-materials-architecture-ui/after/crops/materials-browse-1440x900-navigator-100pct.png). The dedicated long-tree browser regression separately passes. |
| Q-02 | not-applicable | The primary DP780 result is short and correctly has no fake result rail; [1440 search table crop](images/issue-262-fe07a-materials-architecture-ui/after/crops/materials-search-1440x900-table-form-100pct.png). The 50-row browser fixture separately proves genuine overflow. |
| Q-03 | pass | Four peer categories keep compact aligned rows, glyphs and reachable identities at every viewport; [3840 navigator crop](images/issue-262-fe07a-materials-architecture-ui/after/crops/materials-browse-3840x2160-navigator-100pct.png). |
| Q-04 | not-applicable | Modeling Fit is outside FE-07A and unchanged. |
| Q-05 | pass | Curve titles, units, ticks and frame remain collision-free; [1920 graph crop](images/issue-262-fe07a-materials-architecture-ui/after/crops/material-curves-1920x1080-graph-preview-100pct.png). |
| Q-06 | pass | The observed curve identity and deviation status remain compact and separate from task status; [2560 graph crop](images/issue-262-fe07a-materials-architecture-ui/after/crops/material-curves-2560x1440-graph-preview-100pct.png). |
| Q-07 | pass | SVG geometry is recomputed from the available frame with consistent glyph/stroke proportions and no CSS/SVG stretching; [3840 graph crop](images/issue-262-fe07a-materials-architecture-ui/after/crops/material-curves-3840x2160-graph-preview-100pct.png). |
| Q-08 | not-applicable | The displayed contract is engineering stress–strain, not a true-yield-stress response. |
| Q-09 | pass | Genuine detail/curve overflow remains local and keyboard/wheel reachable; empty short lists have no fabricated rails. See [1366 detail crop](images/issue-262-fe07a-materials-architecture-ui/after/crops/material-detail-1366x768-table-form-100pct.png). |
| Q-10 | not-applicable | Modeling Fit legend placement is outside FE-07A and unchanged. |
| Q-11 | not-applicable | Modeling Fit rail is outside FE-07A and unchanged. |
| Q-12 | not-applicable | Modeling Export is outside FE-07A and unchanged. |
| Q-13 | not-applicable | Modeling Export is outside FE-07A and unchanged. |
| Q-14 | not-applicable | Modeling Export is outside FE-07A and unchanged. |
| Q-15 | pass | The curve domain, engineering units, headroom and single compact legend remain correct across all five viewports; [1440 graph crop](images/issue-262-fe07a-materials-architecture-ui/after/crops/material-curves-1440x900-graph-preview-100pct.png). |
| Q-16 | not-applicable | Export native preview is outside FE-07A. Materials card preview/download behavior is regression-covered and unchanged. |
| Q-17 | not-applicable | Administration object lists are FE-07B and unchanged. |
| Q-18 | not-applicable | Administration definition editing is FE-07B and unchanged. |
| Q-19 | pass | Materials preserves exact revision pins and visible one-to-many peer-category related records without flattening lineage; [1920 detail original](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-detail-1920x1080.png). Link Type definition editing remains FE-07B. |
| Q-20 | pass | Full-viewport shell, bounded Navigator, expanding result/datasheet/graph panes, adjacent related regions, zero overflow and no route-specific wide override at 1920/2560/3840; [1920](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-curves-1920x1080.png), [2560](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-curves-2560x1440.png), [3840](images/issue-262-fe07a-materials-architecture-ui/after/originals/material-curves-3840x2160.png). |

### Mandatory #249 synthesis

| Axis | Result | Judgment |
| --- | --- | --- |
| Carbon-level information hierarchy | pass | Flat pane/divider grammar, restrained blue task emphasis, compact tabs and identity-first headings remain. Redundant kickers/helper copy were removed; Evidence keeps technical lineage. |
| COMSOL-style engineering task flow | pass | Search/Browse → exact selection → identity/condition/source/curve → card applicability/lineage → exact preview/download or Start Modeling reads as one task. Modeling input and immutable source actions are distinct. |
| SAP-style responsive/wide-screen composition | pass | Navigator and prose remain bounded while results, graph and exact-record tables use the available workspace. Related data is adjacent rather than stranded below a wide-screen void. |

Automated 3840×2160 CSS geometry is not an actual Windows 4K readability record. Physical Windows 4K at 100%, 150% and 200% remains deferred to #223.

## Web Interface Guidelines audit

The 2026-08-24 audit used Vercel's current official `web-interface-guidelines` source. Changed Materials controls retain labels/names, semantic buttons/tables, keyboard activation, visible focus, `aria-busy`/alert recovery, URL-backed state, empty states and bounded long-text handling. No disabled zoom, `transition: all`, click-only `div`/`span`, unlabeled icon action, blocking paste or unpaired outline removal was introduced. The resizer's inherited `outline: none` is paired with a visible `:focus-visible` border/background replacement. No new guideline finding remains in FE-07A.

## Verification record

| Gate | Result |
| --- | --- |
| Frontend unit/component/integration regression | pass — 72 files, 416 tests |
| Frontend guard tests | pass — 17/17 |
| Frontend guard | pass — 0 violations, 15 registered historical warnings |
| TypeScript and production build | pass — Vite production build and bundle check |
| Bundle budget | pass — 24/24 policy tests; entry 258,379 bytes, Materials pages lazy chunk 64,039 bytes, zero warnings/errors |
| Storybook static build | pass |
| Backend architecture guard | pass |
| Live Compose/browser/reload/read-back | pass — disposable `cmp-issue262-visual`; API/PostgreSQL healthy, data and volumes preserved |
| Targeted browser regression | pass — guided demo, source-v2 categories, M2 Materials ownership and corrected peer-category local-scroll coverage (9 tests) |
| Five-viewport capture and Main original-resolution review | pass — 20 geometry records, 20 pairs, 140 crops, 2 recovery states |
| User-guide contract regression | pass — 48/48 tests |
| User guide, documentation impact and diff hygiene | pass — current guide/manifest verification, worktree documentation impact and `git diff --check` |
| Canonical independent Balanced audit | accepted — no blocking findings; owner decision packet is complete |

The permanent `cmp-local-demo` composition belonged to another worktree and was rejected as stale by preflight. Its containers were stopped without deleting volumes. Evidence used the disposable current-worktree project above; no reset, reseed, `down -v` or released-data mutation occurred.

## Owner decision boundary

The implementation and Main visual/geometry review are complete. Before merge, the Product Owner must open and approve the original 1920×1080, 2560×1440 and 3840×2160 Search/Browse/Detail/Curves comparisons. Merge remains forbidden until that explicit approval; #262 stays open because FE-07B is not part of this PR.
