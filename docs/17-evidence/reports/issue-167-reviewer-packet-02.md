# Issue #167 reviewer packet 02

Status: independently reviewed; approved

## Issue acceptance

Review only:
`Materials / search-results / normal / 1366×768`.

The product owner already approved the shared 1440×900 source/image. At 1366 px the registered
reference must apply its approved compact rule: 244 px governed navigator, dominant result grid, and
optional selected Context collapsed before the grid is compressed. It must keep query, result total,
six governed rows, selected row/tree Record, task status, and row-Enter datasheet consequence without
inventing compact-only content. It must have one filled primary command, flat dividers, compact
readable rows, no nested persistent cards, and no overlap, clipping, or page overflow.

The normal search projection remains limited to Material/grade, Family, Description, and Status.
Provider/manufacturer/source, Yield, condition, property values, solver/card readiness,
validation/approval/release, and downloads must not appear. No production React/CSS, backend, API,
domain data, or current user-guide capture belongs to this unit.

Score V-01 through V-16 in
`docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate zero,
and the registered image/measurements. Review the whole compact task flow, not test output alone.

## Approved and comparison references

- Frozen approved source image:
  `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
- Current compact product capture:
  `docs/user-guide/images/current/materials-search-1366x768.png`
- Historical compact responsive proposal:
  `docs/17-evidence/images/uxc-00d-responsive-design/materials-1366x768.png`
- Governed navigator/list inputs:
  `docs/00-research/images/gui-reference/granta-profile.png` and
  `docs/00-research/images/gui-reference/granta-list-results.png`

The 1366 target must preserve the frozen reference's task, data limits, and visual grammar while
applying the registered compact collapse rule. Historical commercial branding or unsupported result
fields are not authority.

## Diff under review

- `docs/00-research/ux-service-reference/capture_reference.py`
- `docs/00-research/ux-service-reference/validate_reference.py`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.measurements.json`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`

The shared approved `materials-search-normal.html`, `reference.css`, and `reference.js` were not
changed. The approved 1440 PNG SHA-256 remains
`8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`.

Direct target paths:

- Image:
  [materials-search-normal-1366x768.png](../images/issue-167-service-reference/materials-search-normal-1366x768.png)
- Measurements:
  `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.measurements.json`

## Interaction and deterministic evidence

- exact viewport: 1366×768 at device scale factor 1;
- application/command/search/status heights: 46/38/40/24 px;
- workspace outer margins: 8 px;
- navigator/results/Context: 244/1,101/collapsed;
- visible divider: one 5 px hit region with a 1 px visual rule;
- tree/result row heights: 25/36 px;
- selected tree/result rows: one each;
- search shortcut and submit, tree Up/Down/Home/End/Enter, and row Enter pass;
- six rows and governed column inventory are deterministic;
- SHA-256:
  `e835d486d04e643d009e15cd6cb02b0009fdcafae75a950940ad5220970c63ea`;
- 1366 validator: 84/84 checks passed with main-agent accepted and owner approval unset;
- frozen 1440 validator: 86/86 checks passed with its registered hash unchanged;
- user-guide, documentation-impact, Ruff, JavaScript syntax, and whitespace checks passed;
- browser console errors, page errors, nested persistent cards, and page overflow: zero;
- latest Web Interface Guidelines audit found no new issue; approved shared UI source was unchanged.

## Required reviewer response

Work read-only. Read only this packet and the exact evidence it names. Open the target and comparison
images at original resolution, inspect the bounded scripts, manifest and measurements, and return:

1. `approve` or `changes_requested`;
2. V-01 through V-16 scores and total;
3. any hard-gate failure;
4. findings in severity order with exact file/line evidence;
5. any residual compact-usability or reference-authority concern.

Do not edit files, commit, push, open a PR, write to GitHub, or request product-owner approval.

## Reviewer disposition

Fresh `reviewer_terra_high` read-only review on 2026-07-28: `approve`.

- V-01 through V-16: 2 each, total 32/32;
- hard-gate result: pass, with no hard-gate zero;
- independently rerun validators: 1366 84/84 and frozen 1440 86/86, with both hashes matching;
- findings: none;
- residual compact-usability or reference-authority concern: none;
- product-owner approval remains unset.
