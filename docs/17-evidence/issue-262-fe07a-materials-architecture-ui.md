# Issue #262 FE-07A Materials architecture and UI refinement

Status: The bounded owner-approved consistency correction is implemented with affected runtime and five-viewport acceptance complete. The final owner report packet contains the five required 1920x1080 originals. The canonical independent Balanced follow-up review accepted the bounded result with no material findings. Merge remains forbidden.

Scope is FE-07A Materials only. Administration FE-07B, Modeling behavior, backend contracts, database data and released artifacts are unchanged.

## Characterization and bounded result

| Area | Before | FE-07A result |
| --- | --- | --- |
| Search, facets, totals and rows | Complete product behavior, but query orchestration and API projection lived in the root `material-library.tsx` hotspot. | Preserved as one server-scoped query and moved to the Materials controller/API boundary. Direct `?mode=filters` entry now resolves the default Materials table without relying on Browse mounting first. |
| Browse and selection | Complete four-peer-category tree, keyboard navigation and exact item selection; presentation retained a redundant bottom helper. | Preserved categories, focus, local scroll and result/detail selection. Removed only the redundant helper. |
| URL and return continuity | Partial ownership: query parsing, URL serialization, exact pins and session return data were embedded in the root surface. | Materials route state owns query/facet/sort/page/mode/selection, exact Material/Record pins, safe return paths and Browse selection continuity. |
| Exact detail, record and solver-card loading | Complete domain behavior with loading/error boundaries, but loaders and graph/card lineage assembly lived beside Activity UI. | Feature API owns exact/unpinned experience loading, immutable revision filtering, graph verification, representative curves and card lineage. No `latest`, first-item or cross-session fallback was added. |
| Datasheet information hierarchy | Partial: repeated kickers and a separate global Related data region created redundant scanning and a large internal void at 2560/3840. Curves repeated the same linked records without distinguishing their decisions. | Related data is adjacent to the active Overview/Properties/Curves decision. Curves distinguish `Modeling input` from immutable `Exact source records`; CAE delivery is labeled `CAE card applicability`; `Source & history` retains lineage. |
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

The current guide detail captures are now the sole geometry references for this route family; the
retired #167 static bundle is no longer a live consumer.

| Viewport | Current product | Approved reference |
| --- | --- | --- |
| 1366×768 | [current](../user-guide/images/current/material-detail-1366x768.png) | current product evidence |
| 1440×900 | [current](../user-guide/images/current/material-detail-1440x900.png) | current product evidence |
| 1920×1080 | [current](../user-guide/images/current/material-detail-1920x1080.png) | current product evidence |
| 2560×1440 | [current](../user-guide/images/current/material-detail-2560x1440.png) | current product evidence |
| 3840×2160 | [current](../user-guide/images/current/material-detail-3840x2160.png) | current product evidence |

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
| Carbon-level information hierarchy | pass | Flat pane/divider grammar, restrained blue task emphasis, compact tabs and identity-first headings remain. Redundant kickers/helper copy were removed; `Source & history` keeps technical lineage. |
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

## Consolidated owner correction

The correction preserves the published FE-07A architecture and exact contracts while revising the normal Materials decision surface as one bounded unit:

- Search now has separate `Material` and `Code` columns. Material contains only the human-facing name; Code contains the exact Catalog `external_key` projected as `material_code`, or an em dash. Code is not described as a grade and is not sortable because the existing server/query contract does not advertise code sorting. The workspace status identifies it explicitly as `Code` rather than repeating an unexplained pale suffix.
- Overview Key properties use a bounded definition layout with each label adjacent to its value. `Applicable conditions and material states` shows Temperature, Strain rate, State and Manufacturing route as explicit rows.
- A representative response is shown only when a stored native artifact proves the response semantics. `True stress–plastic strain response` is projected only from the declared Abaqus `*PLASTIC` or OpenRadioss `/MAT/LAW36/` contracts; the current published Material has neither and therefore receives no fabricated response.
- `Available solver cards` reads target, version, format, unit system, release and permitted action from the existing exact card contract. Generic instruction copy was removed.
- `Related data` remains the canonical concept and groups only stored direct exact links under Technical Data, Test Data, Simulation Data and Solver Cards. Simulation entries use the concrete Processing Output, Selected Material Model or Neutral Material subtype. Selecting a link opens that exact revision in the central Materials workspace.
- Exact Test Data detail projects test kind, condition and truthful channel/axis coverage and units, plus a measured curve when the record contains one. `Open in Modeling` is exposed only when the exact Material, State and Test Data provenance context is qualified. A qualified handoff pins those three exact revisions in both session state and the Modeling URL and opens Process; an unqualified record stays view-only with the exact missing-context reason.
- Search, Browse, Detail and Curves no longer repeat headings, buttons, stage or selection through instructional helper copy. Redundant exact-card kickers and normal-surface revision fragments are also removed. Status, blocking cause, recovery, exact identity and engineering consequence text remain.

### Exact click-flow record

The deterministic live fixture completed every stored direct hop:

1. Search `CMP-DEMO-DP780` selected the exact DP780 Material while displaying `DP780 synthetic reference steel` under Material and `CMP-DEMO-DP780` under Code.
2. The exact Technical Data datasheet retained Material, Record and Material-revision pins through reload. Key properties and the exact Material State/condition were visible.
3. A direct Test Data link opened Record `f7cc35f6-ffa4-4169-ab62-542da6e5df1d`, revision `ded50ad7-c14c-456f-b34b-234269d611e8`, and showed Tensile, 23 °C, strain rate, engineering-strain coverage and engineering-stress units.
4. Browser Back/Forward returned to that same Test Data revision and the pinned Material. Results returned to the same search URL, selected row and table state.
5. Start Modeling created a session at `stage=data&family=metal` carrying the exact Material revision and the unique exact Material State revision in session state and URL pins; reload preserved that context, so known context was not reselected. The provenance-qualified Test Data Process handoff is regression-proven with exact Material, State and Test Data revision pins; the published Test Data fixture lacks that qualification and remains view-only.
6. A direct Simulation Data link opened Record `4adf586a-0837-4b9e-8c72-1a739549dc6a`, revision `330add2c-0f4b-4853-97b2-95a398c9f19c`, visibly typed as Processing Output with its condition and source relationship.
7. The Solver Cards peer root opened Record `03c084fc-90eb-4736-8d0c-69c1b9b73072`, revision `378470c2-dfe6-4be5-9c46-5c183dd492d1`. The exact datasheet showed Abaqus 2025, `.inp`, `kg·m·s`, draft/review state, native preview, acknowledgement-gated download and exact source evidence.
8. Query failure retained the last valid DP780 row and selection with Retry. Recovery reached the truthful empty result without console error, page overflow, clipping or overlap.

### Bounded fixture and contract gaps

- Published direct Test Data records contain test kind, condition and curve-coverage text but no stored curve value or Modeling source. Their exact datasheets correctly remain view-only. Lower-level regression proves the exact Process handoff when qualified context exists.
- Published Material curve values are explicitly view-only, so this fixture has no provenance-qualified Materials `Open in Modeling` action.
- No stored published direct link joins the Processing Output or selected Material Model to a Neutral Material or Solver Card. The exact Solver Card was therefore verified independently through the peer root; no missing link was inferred.
- The Overview API has no family-neutral representative-response semantic. Projection is limited to the two exact native plastic-response declarations above, and the current Material omits the section instead of receiving a family guess.

### Correction visual evidence

The [owner-correction manifest](images/issue-262-fe07a-materials-architecture-ui/owner-correction/manifest.json) is `PARTIAL_PENDING_OWNER_VISUAL_GEOMETRY_APPROVAL`. It registers 20 before and 20 after originals, 70 before and 70 after direct 100%-pixel crops, and two recovery originals (182 PNGs total) at browser zoom 100%, DPR 1 and the five required CSS viewports. Main opened every original and crop at original resolution.

| State | 1366×768 | 1440×900 | 1920×1080 | 2560×1440 | 3840×2160 |
| --- | --- | --- | --- | --- | --- |
| Search | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-search-1366x768.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-search-1440x900.png) | [owner review](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-search-1920x1080.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-search-2560x1440.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-search-3840x2160.png) |
| Browse | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-browse-1366x768.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-browse-1440x900.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-browse-1920x1080.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-browse-2560x1440.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/materials-browse-3840x2160.png) |
| Detail | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-detail-1366x768.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-detail-1440x900.png) | [owner review](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-detail-1920x1080.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-detail-2560x1440.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-detail-3840x2160.png) |
| Curves | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-curves-1366x768.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-curves-1440x900.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-curves-1920x1080.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-curves-2560x1440.png) | [after](images/issue-262-fe07a-materials-architecture-ui/owner-correction/after/originals/material-curves-3840x2160.png) |

All 20 correction measurements have zero page horizontal overflow. The 288 CSS px Navigator stays bounded while the result/datasheet/graph pane expands from 1,054 to 3,528 CSS px. The Key properties and condition forms remain bounded at wider viewports; result tables, related exact rows and graphs use the available comparison space. Local detail and curve scrolling remains inside the main pane.

Q-01/Q-02 remain not applicable for the short seeded tree/result and stay covered by the dedicated overflow regression. Q-03, Q-05–Q-07, Q-09, Q-15, Q-19 and Q-20 pass against the correction originals and direct crops. Q-04, Q-08, Q-10–Q-14 and Q-16–Q-18 remain not applicable to this Materials unit. In particular, Q-19 passes because direct exact one-to-many links remain visible without inferred lineage, and Q-20 passes because forms stay readable while result, related-record and graph regions use wide-screen space without route-specific scaling.

The three mandatory #249 axes pass Main review: Carbon-level hierarchy is strengthened by explicit identity and field grammar; COMSOL-style flow proceeds from exact selection through conditions and stored direct records to truthful downstream actions; SAP-style composition keeps forms bounded and makes results/graphs elastic across all five viewports. Automated 3840×2160 geometry is not physical Windows 4K readability; that record remains deferred to #223.

### Correction verification

| Gate | Result |
| --- | --- |
| Focused correction regression | pass — 3 files, 14 tests; independent reviewer rerun 4 files, 18 tests |
| Full frontend unit/component/integration regression | pass — 72 files, 418 tests with one deterministic worker |
| Frontend guard tests | pass — 17/17 |
| Frontend guard | pass — 0 violations, 15 registered historical warnings; three resolved font-weight exceptions removed from the allowlist |
| TypeScript and production build | pass — entry 258,379 bytes; Materials pages lazy chunk 70,156 bytes; zero production bundle warnings/errors |
| Bundle budget | pass — 24/24 policy tests |
| Storybook static build | pass |
| Backend architecture guard | pass |
| Live Compose/browser/reload/read-back | pass — current-worktree composition healthy and the exact state/return/handoff flow verified |
| Targeted browser regression | pass — 9/9 |
| Five-viewport correction capture | pass — 20 geometry records, 20 before/after pairs, 140 direct crops and 2 recovery originals; 182 registered PNGs |
| User-guide checker | pass — 20 guides, 124 current captures and 9,047 registered images |
| Documentation contract regression | pass — 143/143 |
| Documentation impact and diff hygiene | pass — worktree impact check and `git diff --check` (line-ending notices only) |
| Canonical independent Balanced correction review | **accepted** — no material findings after the bounded Test Data handoff correction |

The canonical reviewer initially found that the fit-input callback could expose an incomplete Test Data handoff. The bounded correction now requires exact Material and State context, prevents session/navigation mutation when it is absent, pins every qualified context in the URL and session, and opens the Process path. Focused and deterministic regressions were rerun; the reviewer re-opened the final source and five-viewport evidence, verified all 182 image files/hashes and accepted the result with no material findings. Physical Windows 4K remains the separate #223 record.

## Owner-approved minor correction

The repeated normal-surface warning was not a React value branch. Its authoritative sources were the demo Material seed descriptions and their governed Catalog projections: `_MATERIAL_DESCRIPTION`, `_METAL_CATALOG_DESCRIPTION`, `_NON_METAL_MATERIAL_DESCRIPTION`, and the non-metal Catalog description fallback. Those demo-only descriptions are now absent. The generic Search and Material Detail renderers still show every genuine stored production description; no warning-string comparison, value-specific suppression or substitute summary was added.

Material Detail now omits the summary paragraph when the stored description is absent instead of showing a generic fallback. The property source remains a labeled exact field on the existing internal `evidence` route. Only the user-facing tab label changes from `Evidence` to `Source & history`; the `MaterialTab` key, path, URL pins, session data and Materials-to-Modeling contracts are unchanged. The guide uses the same user-facing label.

The owner-correction evidence was recaptured against the immediately preceding correction images. Its manifest status is `OWNER_APPROVED_MINOR_CORRECTION_COMPLETE_UNMERGED` and now registers 273 PNGs at zoom 100%/DPR 1: the prior correction evidence plus the 90-image bounded consistency set described below. Main opened the changed Search and Material Detail originals and their table/header/form crops at all five required viewports. The warning is absent, the Description cell truthfully shows an em dash, `Source & history` is visible without wrapping or clipping, and no page overflow, overlap or geometry regression is present. Carbon hierarchy, engineering task flow and responsive/wide-screen composition remain pass; physical Windows 4K remains #223.

The manifest's owner packet at this correction stage contained exactly five distinct 1920x1080 originals: Search, Browse, Detail Overview, Curves and active Source & history. The Source & history capture verified the visible tab was selected while the preserved internal route key remained `evidence`. Other viewports, direct crops and error/recovery states remained internal evidence. The canonical Balanced reviewer reopened those five originals and the updated manifest and returned `APPROVED` with no material findings.

Affected verification is pass: 11 focused frontend tests, 18 seed tests, all five guided-demo scenarios, production TypeScript/Vite build with zero bundle warnings, frontend guard at zero violations, targeted Ruff, preserved-volume Compose reseed, the deterministic exact journey/capture, 143 documentation contract tests, guide integrity, documentation impact and diff hygiene. The canonical independent Balanced follow-up reviewer returned `APPROVED` with no material findings.

## Consolidated owner correction

Search and Browse now label the existing Catalog external identifier as `Material code`; the exact value, server-backed ordering contract, row selection, keyboard interaction, URL state and revision navigation are unchanged. The exact Test Data route loads only its pinned object and revision, then places the canonical measured curve and original-unit point table before the existing scalar summary. Its action is explicitly `Download exact Test Data JSON`; the summary CSV remains separately labeled and is not represented as raw measurements. A failed exact-content request leaves the loaded record summary in place with a bounded retry state.

Simulation Data uses the concrete processing-output document when that is the bound record kind. Its selected true-stress–plastic-strain result is the dominant visual, with the selected model, fitted parameters, authoritative decision metric `0.1772%`, key results and direct exact Test Data link on the normal surface. Candidate diagnostics, processing stages, hashes and full revision detail remain in `Revision history and technical details`. Other Simulation Data binding kinds retain truthful type-specific fallback behavior; no latest, first-row or inferred relationship is used.

Solver Card keeps target, format, unit system, release, exact revision and structured review/download controls above its exact native text. The preview remains locally scrollable and its accessible expand/collapse control is browser-verified to increase the preview height, change to `Collapse preview`, and restore the original height. `Exact source and technical details` preserves the existing provenance without exposing Evidence terminology on the normal surface.

Curves now reads continuously as `Available curves` → selected curve → graph. The presentation-only labels are `Measured tensile curve` and `Repeated-test average and variation`; stored curve keys remain unchanged. Exact workflow-graph Test Data bindings are labeled `Measured test input`, while processing outputs and selected models keep their distinct use labels. The redundant selected-header `View only` label is absent, while source/unit/revision detail remains in `Curve source and technical details`.

The [consolidated affected-state manifest](images/issue-262-fe07a-materials-architecture-ui/owner-correction/simulation-output-correction/manifest.json) records Browse, exact Test Data, Simulation Data, Solver Card and Curves at 1366×768, 1440×900, 1920×1080, 2560×1440 and 3840×2160, including the required 100%-pixel crops. Main opened every original and crop at original resolution. All states have zero page horizontal overflow, bounded navigators and readable wide-screen compositions. Carbon information hierarchy, COMSOL-style engineering flow and SAP-style responsive composition pass; physical Windows 4K readability remains the separate #223 gate.

The final owner packet contains exactly five 1920×1080 originals: Browse, Test Data detail, Simulation Data detail, Solver Card detail and Curves. The deterministic browser run verifies exact selection and revision pins, direct Test Data and Processing Output hops, Back/Forward/Reload restoration, exact Materials-to-Modeling handoff, recovery, Solver Card review/download state and preview expansion/restoration. No backend, API or schema contract changed, and missing fixture relationships remain explicit rather than inferred.

Deterministic verification is pass: all 423 frontend tests, the frontend architecture guard, production TypeScript/Vite build and bundle budget, Storybook build, five-viewport browser/geometry/continuity capture, current-guide integrity, documentation impact and diff hygiene. The same canonical independent Balanced reviewer reopened the final selected-header label removal, current five-viewport evidence and preserved chart/source/Modeling contracts, then returned `APPROVED` with no substantive findings.

## Owner decision boundary

The owner approved this bounded `View only` correction and authorized commit, push, ready transition and merge of PR #320 after the required checks and the same canonical Balanced review pass. After merge, #262 stays open because FE-07B remains outside this PR.
