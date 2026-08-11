# Issue #184 → #223 actual Windows 4K handoff matrix

## Handoff status

- source implementation: #184 P2 production transplant merged by PR #231 at
  `main@ab27e3947817cefa997e49c5dc1d237ec5035adb`
- available displays: 2560×1440@59Hz external, 2560×1600@165Hz integrated
- Windows scale during #184 capture: 100%, applied DPI 96
- actual 3840×2160 display: unavailable
- physical readability disposition for every row below: **`DEFERRED_TO_223`**

The five CSS viewport captures and browser zoom 200% audit in
[the #184 evidence](issue-184-high-dpi-global-implementation.md) prove deterministic geometry and
accessibility behavior only. They are not actual Windows 4K 100%/150%/200% evidence.

## #184 fixture evidence gate inherited by #223

The product owner completed #184 on 2026-08-11 without converting the independent audit's
`CHANGES_REQUESTED` disposition or `INCOMPLETE_BASELINE_FIXTURE_BLOCKER` into a pass. Before the
actual-device matrix below can receive final approval, #223 must recapture these exact 10 states in
each of `Compact`, `Standard`, and `Large` (30 originals total):

- `material-cae-cards-1440x900.png`
- `material-detail-1366x768.png`
- `material-detail-1440x900.png`
- `material-detail-1920x1080.png`
- `material-detail-2560x1440.png`
- `material-detail-3840x2160.png`
- `modeling-export-delivered-1440x900.png`
- `solver-card-preview-1366x768.png`
- `solver-card-preview-1440x900.png`
- `solver-card-preview-1920x1080.png`

The blocker record remains `CMP-CATALOG-0015` in the canonical append-only fixture, with the clean
seed boundary `CMP-CATALOG-0004` and full-demo verifier result
`FAIL_POLYMER_BULK_ZIP_NOT_GENERATED`. #223 must not reset data or relax the verifier. It must restore
the fixture through a bounded fix if needed, rebuild the structured manifest with SHA-256, original
dimensions, capture commit, viewport, DPR, browser zoom, density, and state fingerprint, then obtain a
new independent read-only audit of every recaptured original at native resolution. This gate is an
explicit one-time evidence carryover, not permission to defer a known geometry, clipping, overflow, or
interaction defect.

## Required actual-device matrix

For each row, #223 records monitor manufacturer/model/physical size/native resolution, Windows scale,
browser zoom, CSS viewport, DPR, selected density, exact route/state fingerprint, full-screen original,
direct 1:1 crops, qualitative disposition and any bounded common-token correction.

| Route / state | 100% | 150% | 200% | Required direct actions and observations |
| --- | --- | --- | --- | --- |
| Materials explorer/result | DEFERRED | DEFERRED | DEFERRED | search, select, keyboard browse, Open datasheet; navigator/table/gutter/readability |
| Materials Browse tree + long local scroll | DEFERRED | DEFERRED | DEFERRED | disclosure, keyboard traversal, true scrollbar and splitter hit region |
| Materials datasheet + five tabs | DEFERRED | DEFERRED | DEFERRED | Properties/Curves/CAE Cards/Evidence, direct preview/download, no exact-revision fallback |
| Materials context allocation overlay | DEFERRED | DEFERRED | DEFERRED | open, Close/Escape, focus return, direct Open datasheet |
| Modeling Data normal/empty | DEFERRED | DEFERRED | DEFERRED | include/show curve, collapsed/expanded navigator, graph reachable |
| Modeling Data invalid mapping/file input | DEFERRED | DEFERRED | DEFERRED | local scroll, invalid field recovery, file input and primary action reachability |
| Modeling Process normal/manual/error | DEFERRED | DEFERRED | DEFERRED | method controls, local scroll, Save, Retry/Back to Data, persistent graph |
| Modeling Fit normal/long evidence/error | DEFERRED | DEFERRED | DEFERRED | candidate controls, evidence overlay, selection/save/retry and graph labels |
| Modeling Export normal/blocked/delivered | DEFERRED | DEFERRED | DEFERRED | native preview, mapping context, approximation acknowledgement, delivery action |
| Activity role-aware request queue | DEFERRED | DEFERRED | DEFERRED | identity/status/action columns, Review or role-correct absence, no page H overflow |
| Activity long Recent outcomes | DEFERRED | DEFERRED | DEFERRED | genuine local scrollbar, final row/action reachability |
| Activity decision error/recovery | DEFERRED | DEFERRED | DEFERRED | retained reason/selection, exact selection recovery |
| Administration Database design | DEFERRED | DEFERRED | DEFERRED | semantic three-pane, long list/table, bounded property form, Add/Edit controls |
| Administration Records | DEFERRED | DEFERRED | DEFERRED | table/layout selection, checked multi-row registration, file input/local scroll |
| Administration Users & access | DEFERRED | DEFERRED | DEFERRED | role control keyboard selection, disabled state and save reachability |
| Display density utility | DEFERRED | DEFERRED | DEFERRED | Compact/Standard/Large, Escape focus return, reset, reload and route persistence |
| Pane interactions product-wide | DEFERRED | DEFERRED | DEFERRED | resize/collapse/reset/persistence; splitter and scrollbar pointer targets |
| Graph/native preview after density/pane change | DEFERRED | DEFERRED | DEFERRED | frame/viewBox/axis/legend/label/hit region and preview minimum height |

## #223 pass boundary

#223 may approve the inherited evidence and actual-device readability only after the 30-original fixture
gate is complete and all three Windows scales have original-resolution screens and direct crops, normal
actions remain reachable, text/controls are physically readable, and no known geometry, clipping,
overlap, page horizontal overflow or graph interaction mismatch remains. Route-
specific 4K overrides, private density values, CSS scaling, automatic DPR/resolution tier selection and
non-uniform SVG stretching remain forbidden; any correction must use the shared production contract and
repeat the affected matrix rows.
