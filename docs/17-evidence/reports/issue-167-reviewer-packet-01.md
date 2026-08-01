# Issue #167 reviewer packet 01

Status: independently reviewed; approved

## Issue acceptance

Review only the first approval unit for #167:
`Materials / search-results / normal / 1440×900`.

The reference must provide static HTML/CSS, a deterministic image, direct source and measurement
paths, SHA-256, viewport, date, and pending product-owner status. It must show a complete
`Menu/Command → Navigator | Data Grid | optional Inspector → Status` workspace, with results wider
than optional context, flat divider grammar, compact readable data, one filled primary command, no
nested persistent cards, and no overlap, clipping, or page-level overflow.

The normal search projection is limited to the current scoped product query: Material/grade, Family,
Description, and Status. Provider/manufacturer/source, Yield, condition, property values, solver or
card readiness, validation/approval/release, and downloads must not appear. Database/Profile/Table/
Folder/Record navigation and keyboard browsing must remain visible. No production React/CSS,
backend, API, domain data, or current user-guide capture belongs to this unit.

Score the route against V-01 through V-16 in
`docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate zero,
and the required image and measurements. Review the whole screen and task flow, not only test output.

## Registered and historical references

- Current approved product baseline:
  `docs/user-guide/images/current/materials-search-1440x900.png`
- Historical responsive proposal:
  `docs/17-evidence/images/uxc-00d-responsive-design/materials-1440x900.png`
- Historical layout review:
  `docs/17-evidence/images/ux-layout-review/materials-1440x900.jpg`
- Governed tree/list sources:
  `docs/00-research/images/gui-reference/granta-profile.png`
  and `docs/00-research/images/gui-reference/granta-list-results.png`

The new target must preserve the topology and product contracts above; it must not copy historical
commercial branding or the historical proposal's unsupported result fields.

## Diff under review

- `docs/00-research/ux-service-reference/materials-search-normal.html`
- `docs/00-research/ux-service-reference/reference.css`
- `docs/00-research/ux-service-reference/reference.js`
- `docs/00-research/ux-service-reference/capture_reference.py`
- `docs/00-research/ux-service-reference/validate_reference.py`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.measurements.json`

Direct target paths:

- Image:
  [materials-search-normal-1440x900.png](../images/issue-167-service-reference/materials-search-normal-1440x900.png)
- Measurements:
  `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.measurements.json`

## Interaction and deterministic evidence

- exact viewport: 1440×900 at device scale factor 1;
- application/command/search/status heights: 46/38/40/24 px;
- workspace outer margins: 8 px;
- navigator/results/context widths: 264/870/280 px;
- tree/result row heights: 25/36 px;
- selected tree/result rows: one each;
- search shortcut and submit, tree Up/Down/Home/End/Enter, row Enter, in-place context update, and
  keyboard pane resize are implemented;
- six rows and the governed column inventory are deterministic;
- SHA-256:
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`;
- reference validator: 66 initial checks and 67 accepted-lifecycle checks passed;
- user-guide and worktree documentation-impact checks passed;
- Ruff, JavaScript syntax, and whitespace checks passed;
- browser console errors, page errors, nested persistent cards, and page overflow: zero.

## Required reviewer response

Work read-only. Open the target and comparison images at original resolution, inspect the source and
measurements, and return:

1. `approve` or `changes_requested`;
2. V-01 through V-16 scores and total;
3. any hard-gate failure;
4. findings in severity order with exact file/line evidence;
5. any residual usability or reference-authority concern.

Do not edit files, commit, push, open a PR, or write to GitHub.

## Reviewer disposition

Fresh GPT-5.6 Terra High read-only review on 2026-07-28: `approve`.

- V-01 through V-16: 2 each, total 32/32;
- hard-gate result: pass, with no hard-gate zero;
- findings: none;
- residual concern: none for this approval unit;
- subsequent product-owner disposition: approved in conversation on 2026-07-28.
