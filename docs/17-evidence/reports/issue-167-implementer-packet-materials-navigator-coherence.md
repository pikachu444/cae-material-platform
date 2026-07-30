# Issue #167 implementer packet — Materials navigator coherence

Date: 2026-07-30
Owner: active `/root` main agent
Scope: product-owner-authorized correction of the shared Materials `Browse catalog` navigator

## 1. Product-owner finding and acceptance boundary

The 1920×1080 MAT-DETAIL candidate still uses the earlier trailing word labels
`Database/Profile/Table/Folder/Record` and ellipsizes the selected Record. It therefore does not
carry forward the later cumulative Materials-tree decisions demonstrated by
`materials-search-long-1440x900.png`: economical indentation, one compact kind glyph, complete
stored identities and visible reserved local scroll controls only when real overflow exists.

Correct the normal MAT-EXP and MAT-DETAIL navigators as one shared visual grammar. This correction
may replace the six normal approval images below and requires renewed product-owner approval for
each changed image. Do not change production React/CSS, the common manifest, inventory, product
policy, shared evidence report, GitHub state, commits or pushes.

## 2. Authority and comparison evidence

Read and follow:

- GitHub #167;
- `AGENTS.md`;
- `docs/01-product/desktop-engineering-ui-product-spec.md`, especially 4.2.1 and 5.1–5.3;
- `docs/01-product/desktop-engineering-ui-spec.md`, especially 3.4, 4.1–4.2 and 5.1;
- `docs/01-product/visual-acceptance-matrix.md`, especially Q-01–Q-03, Q-09 and Q-20;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`;
- current source and capture/validator files named below;
- production contract references `apps/web/src/materials-browse-tree.tsx`,
  `apps/web/src/material-library.tsx` and `apps/web/src/design/layout.css`.

Comparison images:

- `docs/17-evidence/images/issue-167-service-reference/materials-search-long-1440x900.png`
  (`43f146e60baf2d933265d952e22fce5cd0c1e2ca0e9145eea0e72a9677da2484`);
- its 1366/1920 responsive siblings and the complete MAT-EXP state evidence;
- the six current normal images being replaced;
- `docs/user-guide/images/current/materials-search-1920x1080.png`.

The exceptional long-state source is comparison evidence for the cumulative owner findings, not
permission to change its result/list topology. Preserve both exceptional approval images and every
existing exceptional responsive/state image byte-for-byte.

## 3. Exact user task and preserved contracts

The user searches or browses Database → Profile → Table → Folder → Record, can read the complete
stored identity, selects a Record in place, and opens its exact-revision datasheet without losing
the navigator.

Preserve:

- `Browse | Filters | Subsets`, Database/Profile/Table scope and local tree search;
- 24–26 px compact tree rows, selection accent and exact revision consequence;
- 200–360 px keyboard-resizable navigator and existing context/datasheet topology;
- search query/result/selected-context behavior, governed columns and at least 720 px result width;
- datasheet identity, tabs, properties, graph, application condition and solver-card actions;
- URL/selection/back state and production API sources:
  tables, lazy children/folders, saved subsets, scoped record search, exact Record and workflow
  graph;
- the 1920/2560/3840 responsive graph geometry already accepted internally.

## 4. Required implementation

Build one reusable static-reference navigator treatment used by both normal search and datasheet:

1. Replace trailing visible kind words with a fixed compact kind-glyph column before the identity.
   Keep the semantic kind in `data-kind`, accessible name or status text; do not append it to the
   visible stored identity.
2. Use economical indentation equivalent to the cumulative long-tree treatment. A row contains
   disclosure, kind glyph and one-line identity; ordinary row weight stays regular.
3. Do not ellipsize a stored identity merely to preserve the old trailing word column. At the normal
   default widths, the complete DP780/DP600 identities must be visible.
4. A genuinely longer identity uses a max-content tree and a conditional horizontal scrollbar.
   More rows than the pane height use a conditional vertical scrollbar. Both controls:
   - occupy reserved gutters outside row text;
   - have a distinct track and proportional thumb in captured pixels;
   - synchronize ARIA min/max/now with the real scroller;
   - support pointer track/thumb, wheel, Arrow, Page, Home and End consequences;
   - appear only for real overflow. Short normal trees must not show fake rails.
5. Recompute overflow and thumb geometry after viewport/splitter/content changes. At the 200 px
   navigator minimum, conditional horizontal overflow is acceptable and must remain usable; it
   must not be replaced by clipping.
6. Keep scope selectors/search/headings compact and visually identical between search and
   datasheet. Do not introduce a nested card, extra browser pane, verbose helper copy or permanent
   scrollbar when no overflow exists.
7. Preserve the long/empty exceptional images byte-identically. Prefer extracting/reusing the
   already proven navigator primitive where safe; do not repeat a route-specific visual override
   that drifts between MAT-EXP and MAT-DETAIL.

## 5. Approval and supporting captures

Recapture and measure:

- `materials-search-normal-1366x768.png`;
- `materials-search-normal-1440x900.png`;
- `materials-search-normal-1920x1080.png`;
- `materials-datasheet-overview-normal-1366x768.png`;
- `materials-datasheet-overview-normal-1440x900.png`;
- `materials-datasheet-overview-normal-1920x1080.png`;
- 2560×1440 and 3840×2160 supporting evidence for both normal search and normal datasheet.

Do not add inventory items for 2560/3840 unless topology differs from 1920. Preserve the current
exceptional long/empty images and their responsive/state evidence exactly.

## 6. Deterministic evidence

Extend capture/validation only within the owned Materials family paths. Assertions must include:

- six target dimensions/hashes and four wide-support dimensions/hashes;
- exceptional long/empty and all existing responsive/state hashes unchanged;
- default 1366/1440/1920 rows show full DP780 and DP600 identities;
- no trailing visible kind words and one aligned kind glyph per row;
- normal short tree: no vertical or horizontal application scrollbar;
- injected/fixture long-tree state: both reserved rails visible, proportional and outside text;
- splitter default/+8/Home/End at all three normal viewports; actual width and ARIA synchronized;
- local horizontal Arrow/Home/End and vertical wheel/PageDown/End consequences;
- full long identity becomes reachable at horizontal End;
- zero document/body overflow, row/rail overlap, clipping, console error and page error;
- unchanged search selection/context and datasheet tree/search/tab/back/card interactions;
- graph viewBox/rendered-box parity and data-relative headroom remain unchanged.

Run every relevant capture/validator `--help` command first, then the bounded captures and validators,
Ruff, Python compilation, `node --check`, inventory validation and `git diff --check`.

## 7. Owned paths and forbidden writes

Owned paths are the Materials normal static HTML/CSS/JavaScript, their viewport overrides,
Materials normal capture/validator/staging helpers, and the exact normal/wide image/measurement
outputs described above. The implementer may minimally refactor a shared Materials navigator helper
inside this same source family.

Do not edit:

- `apps/web/**`;
- Administration, Modeling or Activity sources/evidence;
- `docs/01-product/service-reference-manifest.yaml`;
- `docs/01-product/service-reference-inventory.yaml`;
- product/UI policy or the common freeze report;
- exceptional approval/responsive/state image bytes;
- GitHub, commits, pushes, PRs or branches.

Return changed paths, new hashes, preservation hashes, gate results and residual risks only.
