# Issue #167 re-reviewer packet — WAVE-01 / MOD-DATA

Date: 2026-07-29  
Review mode: fresh, independent, read-only  
Review boundary: the sole authorized MOD-DATA correction

## Issue acceptance

Approve only if the corrected invalid-mapping state preserves the complete mapping decision and a
meaningfully usable persistent graph together at 1366×768, 1440×900 and 1920×1080. The graph panel
must occupy at least 42% of the main workspace, with canvas minimums of 210, 265 and 300 px
respectively. There must be no topology change, horizontal overflow, clipped decision text or false
saved/preview implication.

The unchanged family requirements remain:

- 184/192/208 px curve/source rail, one divider, one shallow Data region and no third inspector;
- raw source sample plus two explicit axis/quantity/raw-unit/normalized-unit mapping rows;
- adjacent same-column conflict and human-readable change reason;
- Update preview and Save dataset disabled;
- `Last valid preview · stale · not updated`;
- exact Test Data revision, unsaved preview boundary, data-relative plot headroom and keyboard
  splitter behavior.

Score V-01–V-16 from `docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32,
no hard-gate zero and no route-specific dominant-graph failure. Do not modify files.

## Approved/current comparison

- `docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png`
- `docs/00-research/ux-layout-review/modeling.html`
- `docs/00-research/ux-layout-review/review.css`
- `docs/user-guide/images/current/modeling-data-1366x768.png`
- `docs/user-guide/images/current/modeling-data-1440x900.png`
- `docs/user-guide/images/current/modeling-data-1920x1080.png`

## Final candidate and responsive evidence

- canonical invalid 1440:
  `docs/17-evidence/images/issue-167-service-reference/modeling-data-long-invalid-mapping-blocked-1440x900.png`
  — `9ea42420431f3b220ce94d6dbe33c23548a589fc4fda68f63129e021f09e53f1`
- invalid 1366 responsive:
  `docs/17-evidence/images/issue-167-service-reference/modeling-data-long-invalid-mapping-blocked-responsive-1366x768.png`
  — `e3f9cd8422ef09af0341f106b4959ed173b0cbaa226882b4a8f3c382338f5d82`
- invalid 1920 responsive:
  `docs/17-evidence/images/issue-167-service-reference/modeling-data-long-invalid-mapping-blocked-responsive-1920x1080.png`
  — `65c362806f26a4399a117d3d4477d1ab7a6a221a01258b206ad49f1d5236074b`
- combined geometry/state evidence:
  `docs/17-evidence/images/issue-167-service-reference/modeling-data-state-evidence.json`

The canonical 1440 image is also the middle responsive evidence; no duplicate 1440 PNG is retained.

## Correction diff

Review:

- `docs/17-evidence/reports/issue-167-correction-packet-mod-data-wave-01.md`
- `docs/00-research/ux-service-reference/modeling-data.css`
- `docs/00-research/ux-service-reference/capture_modeling_data.py`
- `docs/00-research/ux-service-reference/validate_modeling_data.py`
- the corrected invalid canonical/responsive/state evidence above
- the MOD-DATA rows in `docs/01-product/service-reference-manifest.yaml`

The invalid-only layout now places the raw inspector beside the mapping decision. Normal and Empty
sources and pixels are unchanged. No production source changed.

## Main-agent verification

```text
corrected family recapture from final source                  pass
integrated accepted-lifecycle MOD-DATA validator              pass
MAT-DETAIL no-regression validator                            pass
inventory, Ruff, JavaScript syntax and diff checks            pass
direct original-resolution inspection at 1366/1440/1920      pass
independent native Playwright                                 pass
  complete raw/mapping/conflict/reason/disabled actions
  stale graph context and three visible plot curves
  keyboard divider actual/ARIA +8
  zero document/body/table horizontal overflow

viewport       ribbon   graph/workspace   canvas
1366×768       338 px   263/622 (42%)     218 px
1440×900       338 px   395/754 (52%)     350 px
1920×1080      320 px   593/934 (63%)     548 px
```

Return one disposition (`approve` or `changes_requested`), V-01–V-16 scores, hard-gate failures,
actionable findings with direct paths, and residual concerns. Do not edit.
