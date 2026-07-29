# Issue #167 reviewer packet — WAVE-01 / MOD-DATA

Date: 2026-07-29  
Review mode: fresh, independent, read-only

## Issue acceptance boundary

Freeze Modeling Data references before production visual work:

- normal at 1366×768, 1440×900 and 1920×1080;
- truthful new-session Empty and long invalid-mapping blocked at canonical 1440×900;
- responsive Empty/Invalid evidence at all three viewports;
- detecting/saving loading and parse/import/save error evidence at all three viewports.

The required topology is a 184–210 px curve/source rail, one divider, shallow Data controls and a
dominant persistent graph with no permanent third inspector. Test Data exact revision, inclusion
versus visibility, original/normalized unit semantics, unsaved preview and blocked-save boundaries
must remain explicit. Score V-01–V-16 from
`docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate zero and
complete evidence. Do not modify files.

## Approved and current comparison references

- approved structure:
  `docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png`
- approved lower source:
  `docs/00-research/ux-layout-review/modeling.html` and
  `docs/00-research/ux-layout-review/review.css`
- current contract captures:
  - `docs/user-guide/images/current/modeling-data-1366x768.png`
  - `docs/user-guide/images/current/modeling-data-1440x900.png`
  - `docs/user-guide/images/current/modeling-data-1920x1080.png`

## Candidate images

- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1366x768.png`
  — `07ca35cd91a01b10616d171ff2f7efb68f1f0adb4e73fa77e381cf6853693e95`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1440x900.png`
  — `fa4c2bbae72a56fcbeac21e7b62a7471be44fb7f602058c155d0a128cb5bdb6f`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1920x1080.png`
  — `b75163296be31a39b567943ccecd8a85005647ae692272f2cdf7d134b0ea27f5`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-empty-new-session-1440x900.png`
  — `d646d6bca74671114f46504d43a86f6115b6163607cbb0c9cb124962a31cf668`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-long-invalid-mapping-blocked-1440x900.png`
  — `9ea42420431f3b220ce94d6dbe33c23548a589fc4fda68f63129e021f09e53f1`

Responsive comparison uses each exceptional state's canonical 1440×900 image plus
`modeling-data-*-responsive-{1366x768,1920x1080}.png` siblings. Combined deterministic state
results are in
`docs/17-evidence/images/issue-167-service-reference/modeling-data-state-evidence.json`.

## Implementation diff

Review only:

- `docs/00-research/ux-service-reference/modeling-data-normal.html`
- `docs/00-research/ux-service-reference/modeling-data.css`
- `docs/00-research/ux-service-reference/modeling-data.js`
- `docs/00-research/ux-service-reference/capture_modeling_data.py`
- `docs/00-research/ux-service-reference/validate_modeling_data.py`
- the eight integrated manifest rows only as relevant to this family;
- the five canonical and exceptional responsive/state evidence files.

Production React/API sources are comparison contracts only and were not changed.

## Interaction and test results

```text
family recapture from final sources                            pass
accepted-lifecycle family validator                            pass
inventory, Ruff, Node and diff checks                          pass
independent native Playwright                                  pass
  normal rail/graph 184/1177, 192/1243, 208/1707
  exact dataset selection updates graph context
  source tabs, graph controls and Advanced consequence
  keyboard divider actual/ARIA +8 at all normal viewports
  Empty has no visible curves/datasets and opens Local file
  Invalid has raw inspector, two mapping rows, adjacent conflict,
    disabled preview/save and stale last-valid graph
  error-save preserves source/graph context and exposes recovery copy
console/page errors and horizontal overflow                    zero
main-agent visual disposition                                  32/32 accepted
manifest lifecycle                                              pending / accepted / approval absent
```

Return one disposition (`approve` or `changes_requested`), V-01–V-16 scores, hard-gate failures,
actionable findings with direct file/evidence paths, and residual concerns. Do not edit.
