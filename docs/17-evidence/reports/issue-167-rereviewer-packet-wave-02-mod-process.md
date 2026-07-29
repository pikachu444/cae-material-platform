# Issue #167 fresh re-review packet — WAVE-02 / MOD-PROCESS

Date: 2026-07-29  
Review mode: fresh, independent, read-only

## Issue acceptance

Freeze Process current-preview at 1366×768, 1440×900 and 1920×1080 plus the canonical 1440×900
missing-prerequisite block. Same-topology long, preview/commit loading and preview/commit error
evidence must cover all three viewports. Evaluate the approved Modeling shell, curve/operation
rail, distinct inclusion/selection/visibility semantics, shallow operation controls, persistent
graph dominance, source/before/after continuity, preview-versus-save distinction, data-relative
range headroom, recovery, accessibility, readability, and absence of overlap, clipping and
overflow.

Score V-01–V-16 from `docs/01-product/visual-acceptance-matrix.md`. Passing requires at least
28/32, no hard-gate zero and complete evidence. Return only `approve` or `changes_requested`, the
scores, hard-gate failures, actionable findings with direct paths, and residual concerns. Do not
modify files.

## Approved references

- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1366x768.png`
  — `07ca35cd91a01b10616d171ff2f7efb68f1f0adb4e73fa77e381cf6853693e95`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1440x900.png`
  — `fa4c2bbae72a56fcbeac21e7b62a7471be44fb7f602058c155d0a128cb5bdb6f`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1920x1080.png`
  — `b75163296be31a39b567943ccecd8a85005647ae692272f2cdf7d134b0ea27f5`

## Candidate and comparison captures

- `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1366x768.png`
  — `1ff458abf035810ed9ad41c7a157e26010f734477c53993de886970c1cb51c8a`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1440x900.png`
  — `670075447a9e24848ac65efef5c996c8d601eda3917fb62d5b1d5f5a5a6f4dc4`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1920x1080.png`
  — `d959b4a3d229b43b5062db67881823c38bec47b14d6601addf5baeff71c00eb6`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-prerequisite-blocked-1440x900.png`
  — `533f19b7bfc9c1bec1a6cc97a37a3666df50482196f0a0c905e13f4200c08bdd`

Blocked responsive siblings, measurements and same-topology evidence are registered by
`docs/01-product/service-reference-manifest.yaml` and stored under
`docs/17-evidence/images/issue-167-service-reference/`.

## Implementation diff

Review only:

- `docs/00-research/ux-service-reference/modeling-process-normal.html`
- `docs/00-research/ux-service-reference/modeling-process.css`
- `docs/00-research/ux-service-reference/modeling-process.js`
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`
- regenerated MOD-PROCESS approval/responsive/state evidence, measurements and staging data
- the four candidate manifest rows

The previous reviewer found a focusable `role="button"` curve-row wrapping a checkbox and
visibility button. The user-authorized second correction makes the row non-interactive and keeps a
native inclusion checkbox, native curve-selection button and native visibility button as semantic
siblings. Curve selection has distinct accessible names and keyboard behavior. The divider
resizer and collapse button are likewise semantic siblings. Capture/validation now require one
exact `Hide Specimen 02 from plot` button, one distinctly named `Select Specimen 02 curve` button,
zero nested interactive elements, and keyboard curve selection that leaves inclusion and
visibility unchanged.

## Interaction and test results

```text
MOD-PROCESS family capture from final sources                  pass
pending-lifecycle family validator                             pass
inventory, Ruff, Node syntax and git diff checks               pass
Hide Specimen 02 exact-role button count                       1
Select Specimen 02 curve exact-role button count/name          1 / distinct
nested interactive descendants                                0
pointer selection / keyboard selection / control preservation  pass
responsive/state/range/action/overflow/clipping assertions     pass
main-agent original-resolution inspection of all four PNGs     pass
approval image SHA-256 / manifest binding                      pass
manifest lifecycle                                             pending / accepted / approval absent
```
