# Issue #167 reviewer packet — WAVE-02 / MAT-CARD

Date: 2026-07-29  
Review mode: fresh, independent, read-only

## Issue acceptance boundary

Freeze the complete MAT-CARD reference family before any production visual work:

- exact native card preview at 1366×768, 1440×900 and 1920×1080;
- approximation acknowledgement/download block at 1440×900;
- unsupported preflight/artifact block at 1440×900;
- deterministic long/loading/error and exceptional responsive evidence at 1366×768, 1440×900
  and 1920×1080.

Evaluate the full-screen known-Material-to-card task, approved Materials shell continuity, selected
Record context, native-preview dominance, delivery-sheet restraint, exact/review/blocked
distinction, action consequences, readability, accessibility and absence of overlap, clipping and
overflow. Score V-01–V-16 from `docs/01-product/visual-acceptance-matrix.md`. Passing requires at
least 28/32, no hard-gate zero and complete evidence. Do not modify files.

## Approved references

- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png`
  — `362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png`
  — `c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png`
  — `eda9da6037d7dec12fd4c4c5ce5fa77e993a1faa37f5853b3da5c2203bd35849`

## Candidate images

- `docs/17-evidence/images/issue-167-service-reference/materials-card-preview-normal-1366x768.png`
  — `60497b5fef2239cd17a468b4e8fcf1316e0bccca5b753600aff5f240b21a4372`
- `docs/17-evidence/images/issue-167-service-reference/materials-card-preview-normal-1440x900.png`
  — `74f06d51955b1d7b8f95fed9aaa8f17af147ca00435d7e04f619638c977b2f21`
- `docs/17-evidence/images/issue-167-service-reference/materials-card-preview-normal-1920x1080.png`
  — `8b9758160f441197c440aa11c8c5886cae75ce5e07e001a2aa4cf2fee60a1513`
- `docs/17-evidence/images/issue-167-service-reference/materials-card-approximation-blocked-1440x900.png`
  — `2ea15b1bb5d0984296bab458a7d8572111f816c12f87ba5830ec3cbef7d7be92`
- `docs/17-evidence/images/issue-167-service-reference/materials-card-unsupported-blocked-1440x900.png`
  — `688a0fd8bd9d4d72042f2ad21813df3b8f7ede78b128f75d3cfb1a6c63466d6d`

Responsive comparison uses the canonical 1440×900 exception plus its
`.responsive-{1366x768,1920x1080}.{png,measurements.json}` siblings. Same-topology long/loading/error
results are in
`docs/00-research/ux-service-reference/materials-card-wave02.state-evidence.json`.

## Implementation diff

Review only:

- `docs/00-research/ux-service-reference/materials-card-preview-normal.html`
- `docs/00-research/ux-service-reference/materials-card-preview.css`
- `docs/00-research/ux-service-reference/materials-card-preview.js`
- `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`
- `docs/17-evidence/images/issue-167-service-reference/materials-card-wave02.staging.json`
- the five integrated MAT-CARD manifest rows;
- the five candidate images, measurements and responsive/state evidence named above.

The sole correction made native preview height equal the available pane height at every normal
viewport and removed redundant clipped exceptional-state delivery-header status. Approved parent
assets and production code were not changed.

## Interaction and test results

```text
family capture from final sources                              pass
pending-lifecycle family validator                             pass
inventory, Ruff, Node and diff checks                          pass
main-agent original-resolution inspection of all five PNGs     pass
normal exact mapping / one enabled filled Download             pass
approximation unchecked → Download disabled → checked enabled  pass
unsupported no artifact / no bypass / safe recovery            pass
keyboard tabs, disclosure, splitter and recovery consequences  pass
native preview rendered/available height                       443/443, 569/569, 749/749
clipped decision text / console errors / page overflow          zero
manifest image hashes                                           pass
manifest lifecycle                                              pending / accepted / approval absent
```

Return one disposition (`approve` or `changes_requested`), V-01–V-16 scores, hard-gate failures,
actionable findings with direct file/evidence paths, and residual concerns. Do not edit.
