# Issue #167 reviewer packet — WAVE-02 / MOD-PROCESS

Date: 2026-07-29
Review mode: fresh, independent, read-only

## Issue acceptance boundary

Freeze the complete MOD-PROCESS reference family before any production visual work:

- Process operations/current preview at 1366×768, 1440×900 and 1920×1080;
- missing exact Test Data/Mapping Profile prerequisite block at 1440×900;
- deterministic long-rail, preview/commit loading and preview/commit error evidence at 1366×768,
  1440×900 and 1920×1080.

Evaluate full-screen Process task flow, approved Modeling shell continuity, curve/operation rail,
include-versus-visibility semantics, shallow selected-operation controls, persistent graph
dominance, source/before/after continuity, preview-versus-immutable-save distinction,
data-relative range headroom, recovery, readability, accessibility and absence of overlap,
clipping and overflow. Score V-01–V-16 from
`docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate zero
and complete evidence. Do not modify files.

## Approved references

- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1366x768.png`
  — `07ca35cd91a01b10616d171ff2f7efb68f1f0adb4e73fa77e381cf6853693e95`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1440x900.png`
  — `fa4c2bbae72a56fcbeac21e7b62a7471be44fb7f602058c155d0a128cb5bdb6f`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1920x1080.png`
  — `b75163296be31a39b567943ccecd8a85005647ae692272f2cdf7d134b0ea27f5`

## Candidate images

- `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1366x768.png`
  — `07e7c5f0dd913ac69d17a5c650f48ccd8e4a1930254a5e2d370987ecd3bf3358`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1440x900.png`
  — `f1afcc0c0fbde30d255405abe31777c9642d08cbab779cabe2e16b7a513137d9`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1920x1080.png`
  — `6354707d8e11e31808326e975a62ad9ca062297dd96aa437351b143076d57533`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-prerequisite-blocked-1440x900.png`
  — `9511259e95654421a71c70bd198ccbf005a1df060cd40a0ab182c4bd0a03c76c`

Responsive comparison uses the canonical blocked image plus
`modeling-process-prerequisite-blocked-responsive-{1366x768,1920x1080}.png` and
`modeling-process-responsive-evidence.json`. Same-topology loading/error/long-rail results are in
`modeling-process-state-evidence.json`, all under
`docs/17-evidence/images/issue-167-service-reference/`.

## Implementation diff

Review only:

- `docs/00-research/ux-service-reference/modeling-process-normal.html`
- `docs/00-research/ux-service-reference/modeling-process.css`
- `docs/00-research/ux-service-reference/modeling-process.js`
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/modeling-process-wave02.staging.json`
- the four integrated MOD-PROCESS manifest rows;
- the four candidate images, measurements and responsive/state evidence named above.

The sole correction separated axis-label and legend/status footer lanes at every viewport and
removed the duplicate settings-band Preview while retaining the title-row Preview and the sole
filled `Save processed curves` action. Approved parent assets and production code were not changed.

## Interaction and test results

```text
family capture from final sources                              pass
pending-lifecycle family validator                             pass
inventory, Ruff, Node and diff checks                          pass
main-agent original-resolution inspection of all four PNGs     pass
184/192/208 rail defaults, keyboard resize/collapse/restore    pass
three curves / two included / separate plot visibility         pass
five ordered Process operations / Elastic modulus selected     pass
one Preview / one filled Save / downstream stale consequence   pass
data-relative x/y bounds and visible headroom                   pass
axis-label / legend bbox containment and non-intersection       pass
blocked no fallback/result / one Back to Data recovery          pass
long/loading/error context preservation                         pass
console errors / page overflow / clipped decision text          zero
manifest image hashes                                           pass
manifest lifecycle                                              pending / accepted / approval absent
```

Return one disposition (`approve` or `changes_requested`), V-01–V-16 scores, hard-gate failures,
actionable findings with direct file/evidence paths, and residual concerns. Do not edit.
