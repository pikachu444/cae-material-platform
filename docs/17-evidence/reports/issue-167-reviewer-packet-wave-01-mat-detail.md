# Issue #167 reviewer packet — WAVE-01 / MAT-DETAIL

Date: 2026-07-29
Review mode: fresh, independent, read-only

## Issue acceptance boundary

Freeze the remaining MAT-DETAIL reference targets before production visual work:

- normal Material Datasheet at 1920×1080;
- Related with long forward/reverse Link Type and Record labels at 1440×900;
- truthful selected-Record Empty at 1440×900;
- deterministic exceptional-state containment evidence at 1366×768, 1440×900 and 1920×1080.

Evaluate full-screen task flow, topology, information priority, readability, property/graph/table
dominance, control-result continuity, role terminology, and absence of overlap, clipping and
overflow. Score V-01–V-16 from `docs/01-product/visual-acceptance-matrix.md`. Passing requires at
least 28/32, no hard-gate zero and complete evidence. Do not modify files.

## Approved references

- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png`
  — `c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png`
  — `362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.png`
  — `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`

## Candidate images

- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png`
  — `eda9da6037d7dec12fd4c4c5ce5fa77e993a1faa37f5853b3da5c2203bd35849`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-related-long-1440x900.png`
  — `810394678a9a77c1c35adc4a1848ca45eadd71a1a95a69ea94af7266405079b6`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-empty-1440x900.png`
  — `8df98559459f03db925e02251e10a84265b9ff1e21cd8f4573dd9d2a090548e6`

Responsive comparison uses the canonical 1440×900 image plus
`*.responsive-{1366x768,1920x1080}.{png,measurements.json}` siblings of the Related and Empty
canonical paths.

## Implementation diff

Review only:

- `materials-datasheet-overview-normal-1920x1080.{css,js}`
- `materials-datasheet-related-long-1440x900.{css,js}`
- `materials-datasheet-empty-1440x900.{css,js}`
- `capture_materials_datasheet_wave01.py`
- `validate_materials_datasheet_wave01.py`
- the eight integrated manifest rows only as relevant to this family;
- the three canonical and exceptional responsive evidence files.

All source paths are under `docs/00-research/ux-service-reference/`; image evidence is under
`docs/17-evidence/images/issue-167-service-reference/`. The sole correction restored the Empty
Record header and replaced generic Related direction labels with long human Link Type wording.
Approved parent assets and production code were not changed.

## Interaction and test results

```text
family recapture from final sources                            pass
accepted-lifecycle family validator                            pass
approved 1366/1440 parent validators                           pass
inventory, Ruff, Node and diff checks                          pass
independent native Playwright                                  pass
  normal 1920 splitter actual/ARIA 280 → 288
  Related row selection → context → exact Record URL hash
  Empty one primary Back to results consequence
  Record header/tabs/tree preserved
  long labels contained at three evidence viewports
console/page errors and horizontal overflow                    zero
main-agent visual disposition                                  32/32 accepted
manifest lifecycle                                              pending / accepted / approval absent
```

Return one disposition (`approve` or `changes_requested`), V-01–V-16 scores, hard-gate failures,
actionable findings with direct file/evidence paths, and residual concerns. Do not edit.
