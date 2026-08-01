# Issue #167 implementer packet — MAT-EXP wide result density

Date: 2026-07-30
Writer: one configured `implementer_luna_max`
Owner: active `/root` main agent

## Authorization and corrected objective

The product owner initiated a cross-family large-display correction after Administration exposed
avoidable blank regions, then explicitly reminded the active main agent that the same review applies
to existing #167 references. The earlier request to approve six Search/Datasheet images is withdrawn.

This packet corrects only `Materials / search-results / normal`. Datasheet remains a dependent,
separate decision after MAT-EXP approval. Do not edit production React/CSS, Datasheet,
Administration, Modeling, Activity, the common manifest/inventory/evidence report, GitHub state,
commits, pushes, PRs or merges.

## Main-agent inspection and finding

The main agent reopened the 1366×768, 1440×900 and 1920×1080 candidates plus 2560×1440 and
3840×2160 supporting images at original resolution. The current six-row fixture leaves most of the
main result grid blank from 1440 upward and nearly the entire engineering workspace blank at 2560
and 3840. The previous Q-20 rationale that this was a truthful sparse state is rejected.

The current production contract proves a denser truthful projection already exists:

- `apps/web/src/material-library.tsx` requests one server-scoped page with `limit: 50`;
- `apps/web/src/api.ts` exposes `MaterialSearchResponse.items`, `total_count`, `offset`, `limit` and
  scoped family facets;
- `MaterialSearchPage` renders those rows without per-row detail enrichment and displays
  Previous/Next pagination when `total_count` exceeds the page;
- the production test exercises exactly 50 items out of 10,000 and asserts no detail request.

Therefore the normal reference must exercise a complete 50-row synthetic non-production page, not
invent a companion panel or stretch six rows.

## User task and preserved contracts

The user searches for `steel`, scans and sorts a dense result page, selects or compares a material,
browses Database → Profile → Table → Folder → Record, and opens the selected datasheet.

Preserve:

- the shared compact Materials navigator, complete DP780/DP600 identities, splitter behavior and
  conditional tree rails;
- the existing server-backed columns only:
  `Compare | Material / grade | Family | Description | Status`;
- the selected DP780 material, selected-context identity/description/family/status and one
  `Open datasheet` action;
- bidirectional tree Record/result/context synchronization, non-Record context preservation,
  result pointer/Enter behavior and Compare limit;
- query/facet/row consistency and the absence of Yield, card-readiness, provider or other fields not
  projected by this response;
- 36 px result rows, sticky header, tabular/compact engineering typography and flat divider grammar;
- every approved exceptional-state image byte-for-byte.

## Required correction

1. Replace the six-row normal fixture with one deterministic 50-row synthetic non-production server
   page. Keep DP780 and DP600 as the first two rows so tree synchronization remains exact. Every
   remaining row must have a distinct concise stored identity/code and truthful demo disclaimer; do
   not use lorem ipsum, production claims or real confidential data.
2. Display the response as rows `1–50 of 10,000 matches`, matching the current production paging
   contract. Include a compact page footer with the current range and available next-page
   consequence; do not fabricate a loaded second page.
3. Keep row height fixed at 36 px. Never stretch rows, prose, fonts or the selected context merely
   to occupy a larger display.
4. Make the result body an independent local scroll region with a sticky header and a reserved,
   perceptually visible proportional vertical rail whenever 50 rows overflow. The rail must sit
   outside cell text and support pointer track/thumb, wheel, Arrow, Page, Home and End. At a viewport
   where all 50 rows genuinely fit, hide the rail rather than displaying a fake one.
5. Keep pagination/range context visible and outside the scrolling row body. The header, selection,
   footer and status bar must not scroll away with rows.
6. At 1366, 1440, 1920, 2560 and 3840, the real result rows—not filler panels—must use the vertical
   workspace. Preserve bounded navigator/context widths and let the Description column use elastic
   horizontal space without stretching text.
7. Do not add a result-detail fetch, property/card data, chart, dashboard tile, explanatory banner
   or decorative summary to fill space.

## Exact owned paths

The writer may change only:

- `docs/00-research/ux-service-reference/materials-search-normal.html`;
- `docs/00-research/ux-service-reference/reference.css`;
- `docs/00-research/ux-service-reference/reference.js`;
- `docs/00-research/ux-service-reference/capture_reference.py`;
- `docs/00-research/ux-service-reference/validate_reference.py`;
- `docs/00-research/ux-service-reference/validate_materials_search_wave03.py`;
- the three normal MAT-EXP PNG/measurement files;
- the two MAT-EXP wide-support PNG/measurement files;
- a MAT-EXP staging file if the existing capture flow requires it.

Do not edit `materials-navigator.css`, `materials-navigator.js`, any Datasheet path or any shared
manifest/evidence path. Other agents and the user own unrelated dirty-worktree changes; do not
revert, overwrite or reformat them.

## Required deterministic evidence

- Run every affected capture/validator `--help` command before capture.
- Capture 1366×768, 1440×900, 1920×1080 and supporting 2560×1440/3840×2160.
- Assert 50 distinct rows, `1–50 of 10,000`, fixed 36 px row density and correct first/last identity.
- Assert local result overflow, reserved track/thumb geometry and pointer/wheel/keyboard/ARIA
  consequences at every viewport where overflow exists; assert no fake rail where it does not.
- Assert the selected row remains visible initially and after tree DP600/DP780 synchronization.
- Assert sticky header and fixed pagination/footer before and after scrolling to End.
- Assert zero page/body overflow, scrollbar/text collision, clipped identity, console/page error and
  nested persistent card.
- Assert all approved long/empty/loading/error and responsive hashes remain exact.
- Rerun the full MAT-EXP family validators, JavaScript syntax, Python compilation, Ruff, inventory
  and `git diff --check`.

Return changed paths, final hashes, gate results and residual risks. Do not commit or publish.
