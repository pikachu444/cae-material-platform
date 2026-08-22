# Issue #261 M2 — Materials CSS ownership evidence

Status: Main acceptance PASS; independent Full reviewer APPROVE. The production change is an
ownership-only extraction. It does not redesign Materials or change React, state, API, domain, copy,
tokens, navigation, or breakpoints.

## Frozen disposition

M2 uses the v4 packet in
[`issue-261-m2-materials-css-ownership.json`](../../scripts/fixtures/issue-261-m2-materials-css-ownership.json)
and the exact 257 Materials selector rows from the final CSS inventory. The extraction moved 199
complete rule groups and split 22 mixed groups without changing selector text, declaration text,
rule order, or at-context. The import order remains `styles → tokens → typography → primitives →
layout → materials → shell`.

| Frozen check | Result |
| --- | ---: |
| Historical roster | 405 rows: M2 257, Activity/M3B 76, Modeling/M1D 1, M4 13, HOLD 58 |
| Materials moved | 257 selector rows / 221 rule groups |
| Complete / mixed groups | 199 / 22 |
| Post-migration rows / groups | 3,117 / 2,500 |
| Post `layout.css` rows / groups | 1,445 / 1,118 |
| Post `styles.css` rows / groups | 1,672 / 1,382 |
| Mixed residual rows | 29 rows remain in `layout.css` by exact mixed-group disposition |
| M2 CSS bytes | 29,819 (`materials.css`) |
| Layout CSS SHA-256 | `04e367a926d8e2167695b820b2166882b79a5e5d45e2453c437e272040a5a81a` |
| Materials CSS SHA-256 | `4da1a8483ae6cf448a025e19d28d7aa0622d04f999b4d4b7e126386861c4226e` |

The classifier uses exact source path, selector, and at-context override tuples. Historical rule and
selector indices are evidence only; they are not used as post-extraction ownership keys. The M2
regression test proves exhaustive roster coverage, mixed-rule indices, exact tuple matching, import
order, source hashes, and disjoint external ownership. No temporary extractor remains.

## Guard-delta proof and boundary

The extraction relocates pre-existing guard categories with the declaration and at-context intact.
The current Materials file reports 14 pre-existing `font-weight` findings, 13 pre-existing raw-color
findings, and 6 pre-existing `min-width:1800px` wide-media findings. The current `frontend-guard`
run reports 85 findings because changed line/path coordinates are compared with the historical
baseline; this is a path/line relocation diagnostic, not a new cascade or product violation. No
guard exception was transferred or broadened. Per the user-service-value acceptance boundary, these
path/line relocation findings and historical line-ending diagnostics are deferred to combined-tree
governance regeneration. Actual clipping, overflow, unreachable controls, incorrect cascade,
state/behavior regression, or authorization failure would still block; none was observed.

## Primary journey and acceptance

The task-owned browser spec is
[`issue-261-m2-materials-css-ownership.spec.ts`](../../apps/web/e2e/issue-261-m2-materials-css-ownership.spec.ts).
It reuses the exact revision and Neutral Solver Card response shapes from the pinned Materials and
solver-card delivery tests. Its journey is:

1. Open Materials Browse, switch to Search, find the governed synthetic reference, and verify the
   search URL state.
2. Open the selected Material, assert `record_id`, `record_revision_id`, and
   `material_revision_id` pins, reload, and return to the same pinned result.
3. Open CAE Cards, preview the exact card, assert preview/download requests retain the card revision,
   and verify the download filename.
4. Open a no-card exact Material and verify Start Modeling hands off the exact metal context to
   `/modeling?stage=data&family=metal`.
5. At 1440×900 only, exercise an invalid record revision and require an alert instead of current-head
   fallback. The test also captures a cumulative search/detail/card matrix at 1366×768, 1440×900,
   1920×1080, 2560×1440, and 3840×2160, with browser zoom fixed at 100%.

Two isolated Compose projects supplied a base build at `http://127.0.0.1:32768` and the current build
at `http://127.0.0.1:32770`. The real seeded database does not associate its solver-card fixture with
the selected Material; therefore real live evidence covers search and detail, while the task-owned
contract fixture covers exact card preview/download and Start Modeling. The fixture is not claimed as
a production domain record. Browser zoom was 100%, CSS viewports were the five sizes above, and the
automated browser device pixel ratio was 1.

## Live and contract evidence

The real live search/detail originals are paired under `before/live` and `after/live`:

- [search 1366×768](images/issue-261-fe06-m2-materials-css-ownership/before/live/materials-search-1366x768.png)
- [search 1440×900](images/issue-261-fe06-m2-materials-css-ownership/before/live/materials-search-1440x900.png)
- [search 1920×1080](images/issue-261-fe06-m2-materials-css-ownership/before/live/materials-search-1920x1080.png)
- [search 2560×1440](images/issue-261-fe06-m2-materials-css-ownership/before/live/materials-search-2560x1440.png)
- [search 3840×2160](images/issue-261-fe06-m2-materials-css-ownership/before/live/materials-search-3840x2160.png)
- [detail 1366×768](images/issue-261-fe06-m2-materials-css-ownership/before/live/material-detail-1366x768.png)
- [detail 1440×900](images/issue-261-fe06-m2-materials-css-ownership/before/live/material-detail-1440x900.png)
- [detail 1920×1080](images/issue-261-fe06-m2-materials-css-ownership/before/live/material-detail-1920x1080.png)
- [detail 2560×1440](images/issue-261-fe06-m2-materials-css-ownership/before/live/material-detail-2560x1440.png)
- [detail 3840×2160](images/issue-261-fe06-m2-materials-css-ownership/before/live/material-detail-3840x2160.png)

- [after search 1366×768](images/issue-261-fe06-m2-materials-css-ownership/after/live/materials-search-1366x768.png)
- [after search 1440×900](images/issue-261-fe06-m2-materials-css-ownership/after/live/materials-search-1440x900.png)
- [after search 1920×1080](images/issue-261-fe06-m2-materials-css-ownership/after/live/materials-search-1920x1080.png)
- [after search 2560×1440](images/issue-261-fe06-m2-materials-css-ownership/after/live/materials-search-2560x1440.png)
- [after search 3840×2160](images/issue-261-fe06-m2-materials-css-ownership/after/live/materials-search-3840x2160.png)
- [after detail 1366×768](images/issue-261-fe06-m2-materials-css-ownership/after/live/material-detail-1366x768.png)
- [after detail 1440×900](images/issue-261-fe06-m2-materials-css-ownership/after/live/material-detail-1440x900.png)
- [after detail 1920×1080](images/issue-261-fe06-m2-materials-css-ownership/after/live/material-detail-1920x1080.png)
- [after detail 2560×1440](images/issue-261-fe06-m2-materials-css-ownership/after/live/material-detail-2560x1440.png)
- [after detail 3840×2160](images/issue-261-fe06-m2-materials-css-ownership/after/live/material-detail-3840x2160.png)

The [CSS visual-preservation manifest](images/issue-261-fe06-m2-materials-css-ownership/manifest.json)
links the current guide capture and a byte-identical canonical pair at every mandatory viewport:

| Viewport | Canonical before | Canonical after |
| --- | --- | --- |
| 1366×768 | [before](images/issue-261-fe06-m2-materials-css-ownership/before/canonical/materials-search-1366x768.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/after/canonical/materials-search-1366x768.png) |
| 1440×900 | [before](images/issue-261-fe06-m2-materials-css-ownership/before/canonical/materials-search-1440x900.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/after/canonical/materials-search-1440x900.png) |
| 1920×1080 | [before](images/issue-261-fe06-m2-materials-css-ownership/before/canonical/materials-search-1920x1080.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/after/canonical/materials-search-1920x1080.png) |
| 2560×1440 | [before](images/issue-261-fe06-m2-materials-css-ownership/before/canonical/materials-search-2560x1440.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/after/canonical/materials-search-2560x1440.png) |
| 3840×2160 | [before](images/issue-261-fe06-m2-materials-css-ownership/before/canonical/materials-search-3840x2160.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/after/canonical/materials-search-3840x2160.png) |

The deterministic contract matrix is indexed below. All ten real-live pairs and all sixteen contract
pairs have identical decoded pixels (`0` changed pixels); differing PNG metadata in five real-live
pairs is non-visual and not a product regression.

| State / viewport | Before | After |
| --- | --- | --- |
| Search 1366×768 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/search-1366x768.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/search-1366x768.png) |
| Search 1440×900 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/search-1440x900.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/search-1440x900.png) |
| Search 1920×1080 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/search-1920x1080.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/search-1920x1080.png) |
| Search 2560×1440 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/search-2560x1440.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/search-2560x1440.png) |
| Search 3840×2160 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/search-3840x2160.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/search-3840x2160.png) |
| Detail 1366×768 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/detail-1366x768.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/detail-1366x768.png) |
| Detail 1440×900 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/detail-1440x900.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/detail-1440x900.png) |
| Detail 1920×1080 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/detail-1920x1080.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/detail-1920x1080.png) |
| Detail 2560×1440 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/detail-2560x1440.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/detail-2560x1440.png) |
| Detail 3840×2160 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/detail-3840x2160.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/detail-3840x2160.png) |
| Card preview 1366×768 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/card-preview-1366x768.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/card-preview-1366x768.png) |
| Card preview 1440×900 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/card-preview-1440x900.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/card-preview-1440x900.png) |
| Card preview 1920×1080 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/card-preview-1920x1080.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/card-preview-1920x1080.png) |
| Card preview 2560×1440 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/card-preview-2560x1440.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/card-preview-2560x1440.png) |
| Card preview 3840×2160 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/card-preview-3840x2160.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/card-preview-3840x2160.png) |
| Missing revision 1440×900 | [before](images/issue-261-fe06-m2-materials-css-ownership/matrix/before/exception-revision-mismatch-1440x900.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/matrix/after/exception-revision-mismatch-1440x900.png) |

Direct 100%-pixel crops of the representative 1440×900 surfaces are indexed here:

| Crop | Before | After |
| --- | --- | --- |
| Header | [before](images/issue-261-fe06-m2-materials-css-ownership/crops/before/header-1440x900-100pct.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/crops/after/header-1440x900-100pct.png) |
| Navigator | [before](images/issue-261-fe06-m2-materials-css-ownership/crops/before/navigator-1440x900-100pct.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/crops/after/navigator-1440x900-100pct.png) |
| Table controls | [before](images/issue-261-fe06-m2-materials-css-ownership/crops/before/table-controls-1440x900-100pct.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/crops/after/table-controls-1440x900-100pct.png) |
| Native preview | [before](images/issue-261-fe06-m2-materials-css-ownership/crops/before/native-preview-1440x900-100pct.png) | [after](images/issue-261-fe06-m2-materials-css-ownership/crops/after/native-preview-1440x900-100pct.png) |

All 62 full-size before/after images and all eight crops were opened at original resolution.

## #249 visual review record

Main review passes all three inherited axes:

- **Information hierarchy — PASS:** results remain dominant; exact Material/card identity and revision
  stay visible; delivery details remain subordinate to the native preview; no competing inspector is
  introduced.
- **Engineering task flow — PASS:** Search/Browse → exact Material → reload/read-back → exact card
  preview/download or Start Modeling remains operable. A missing record revision fails closed with a
  visible recovery action, and no `latest` or current-head fallback appears.
- **Responsive/wide-screen composition — PASS for this ownership move:** the five CSS viewports show no
  new clipping, overflow, wrapping loss, unreachable control, one-sided work island, CSS zoom, or
  fabricated filler. The established product-wide fixed-density readability at the 3840×2160 CSS
  viewport is pixel-identical to the base and is not redesigned here; actual Windows 4K 100/150/200%
  physical readability remains the separate #223 gate.

## Quality gates

| Gate | Main acceptance result |
| --- | --- |
| M2 ownership test | PASS — 4/4 tests; approved base SHA is pinned so the test remains valid after local commits |
| Inventory CLI and generated JSON | PASS — 257 Materials rows / 221 groups; M2 legacy remainder 0 |
| Shared inventory test | 18/19; the sole Windows CRLF-sensitive M1A8 optional-channel assertion is identical at the approved base and deferred |
| Build and affected component tests | PASS — production build; 10 files / 64 tests |
| Frontend guard regression suite | PASS — 17/17 tests |
| Frontend guard report | 85 findings / 15 warnings; deferred path/line relocation diagnostic, with no exception transfer |
| Browser exact journey | PASS on base and current isolated stacks — 1/1 each, including reload, exact download, Start Modeling, and fail-closed recovery |
| Five-viewport visual geometry | PASS — 26/26 before/after pairs have 0 changed decoded pixels; originals and direct crops reviewed |
| Compose/database | PASS in isolated base/current projects; canonical preflight was left untouched because it belongs to another worktree |
| Physical Windows 4K | Deferred to #223; CSS viewport evidence does not claim actual-device readability |
| User-guide hook | PASS — 20 guides, 3,130 local links, 4,287 images |
| Documentation impact | DEFERRED to combined-tree regeneration: the stacked PR #311 history contains Modeling visual-preservation manifests for `layout.css + modeling-data-stage.css`, while this branch's current proof covers `layout.css + materials.css`; the checker requires every historical manifest to name the same CSS files. Editing another task's evidence or bypassing the checker is forbidden, and this is not a product regression. |
| Publication / commit / PR / merge | Local commits only are authorized; push/PR/merge remain forbidden |

## Independent Full review

The independent `reviewer_terra_high` verdict is **APPROVE**, with no blocker, major, or
material-minor finding. The reviewer independently confirmed all 257 approved Materials
selector/declaration/at-context tuples, selector order, and 221 resulting rule groups; re-ran the
task ownership test (4/4), production build, and frontend guard suite (17/17); and reviewed the
original-resolution search, detail, card, recovery, and 100%-pixel crop evidence. No introduced
clipping, overflow, inaccessible control, wrong cascade, state/behavior regression, or full-screen
cap was found. The shared CRLF assertion, guard relocation diagnostics, historical manifest mismatch,
and physical 4K readability remain the already-recorded integration deferrals and do not change the
bounded verdict.

Activity/M3B's 76 rows, Modeling/M1D `CSS-2331`, M4, HOLD, and every non-M2 owner file remain
untouched. Later Balanced integration must regenerate shared inventory, guard, manifest, and guide
artifacts from the combined tree rather than blindly cherry-picking them.
