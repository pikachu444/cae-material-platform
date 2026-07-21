# T-95 continuous governed Materials Browse Tree

Date: 2026-07-21

## Bounded implementation slice

This increment replaces the Materials page's legacy `Open Browse Tree` redirect with an integrated,
API-backed navigator. It does not replace or simulate the configurable Catalog. Database and Profile
scope the actual Table list; expanding a Table or Folder calls the existing Catalog Explorer children
contract. Record find and saved Subset application call the existing typed Record-search contract.

The left navigator exposes Filters, Browse, and Subsets as sibling modes. The Browse viewport scrolls
independently beneath fixed scope and find controls. Rows are 26 px high, use 12.5 px regular labels,
12 px depth increments, node-type glyphs, one-line ellipsis/title disclosure, and a selected-row
background plus leading marker. Up/Down/Home/End move focus, Left/Right collapse or expand, Enter
selects, and double-click opens the exact Record revision datasheet.

## Reference-derived interaction principles

| Directly inspected reference | Applied principle |
| --- | --- |
| `docs/00-research/images/gui-reference/granta-contents-tree.png` | Compact persistent hierarchy; selected Record remains legible among folders without card wrappers. |
| `docs/00-research/images/gui-reference/granta-profile.png` | Database/Profile/Table are explicit governed scope, not material-family filter substitutes. |
| `docs/00-research/images/gui-reference/granta-list-results.png` | Tree and dense tabular results remain adjacent on one continuous divided surface. |
| `docs/00-research/ux-reference-gallery/images/material-data-center-search-detail.png` | Search/result/detail continuity; optional context cannot displace the dominant results region at 1366 px. |

Brand color, logo, commercial icons, product names, pixel geometry, and proprietary workflows were
not copied.

## Before and after

- Before: `docs/15-demo/images/ux-layout-review/rejected-materials-1440x900.png` — Tree was not an
  integrated navigator and the page used accumulated panels.
- Approved structural target: `docs/15-demo/images/ux-layout-review/materials-1366x768.png`.
- Live after: `docs/15-demo/images/ux-redesign-v2/materials-browse-tree-1366x768.png`.

Live Docker/Chromium measurement at a 1366×768 viewport:

| Measurement | Result |
| --- | ---: |
| Browser viewport | 1366 × 768 px |
| Usable workspace | 1,304.6 px |
| Outer margin | 23.2 px left / 38.2 px right |
| Explorer | 244 px |
| Result/table region | 1,058.6 px |
| Optional context | closed by the 1366 px policy |
| Tree row / label | 26 px / 12.5 px regular |
| Live DP780 search treeitems | 19 |
| Synthetic 10,000-Record mounted treeitems | under 150 |

The first viewport contains two major data areas: the hierarchical navigator and the Material result
table. It does not permanently allocate a third column. Long Material/family/source values use
column minimums plus ellipsis with full-value title disclosure rather than character-by-character
wrapping.

## User task

Scenario B now stays inside Materials:

1. select Browse Tree;
2. expand Material Library → Metals → Steels → DP780 Dual-Phase Steel;
3. select `DP780 synthetic demo steel`;
4. the same Material result becomes selected and an exact-revision datasheet action appears;
5. Tree-local `DP780` find returns eight workflow Records while retaining their ancestor paths.

The hierarchy path requires five pointer activations from Search mode. Tree find reduces this to
Browse Tree → type/Find → Record selection. No UUID or revision string must be copied.

## Verification

- `npm test --workspace @cmp/web`: 35 files, 86 tests passed.
- 10,000-Record virtualization fixture asserts fewer than 150 mounted `treeitem` nodes.
- Component coverage verifies lazy nested expansion, typed server search, retained ancestors,
  exact-Record selection, double-click datasheet, and keyboard focus movement.
- `npm run build --workspace @cmp/web`: TypeScript, Vite, and bundle budget passed; largest entry
  chunk remains below 300,000 bytes.
- Live clean-demo API/Chromium verified the real hierarchy, eight DP780 matches, selection coupling,
  and the measured widths above.

The final T-95 slice also verifies state continuity:

- `/materials?q=DP780&family=metal&solver=OpenRadioss&selected=…` restores the search input, typed
  filters and selected governed Material after a reload.
- Opening Material Detail stores that exact return path; `← Materials` restores the same query and
  selection rather than returning to an empty search.
- Browse/Subsets mode is URL-backed. The last selected `ConfigurableLinkEndpoint` is stored only in
  session context and, on return, calls the real Record/folder contracts to reopen Database →
  Profile → Table → ancestor Folders → exact Record.
- A component gate restores the exact Record and selected row in under one second while the
  10,000-Record fixture still mounts fewer than 150 `treeitem` nodes.

## Remaining limits

- The under-one-second gate is a deterministic synthetic component fixture, not a production p95
  claim for a remote 10,000-Record database.
- Column resizing is not implemented; key columns instead use minimum widths, sticky identity and
  horizontal scrolling. It remains an optional enhancement rather than a T-95 acceptance blocker.
