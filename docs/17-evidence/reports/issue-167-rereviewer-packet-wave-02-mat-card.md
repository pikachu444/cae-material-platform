# Issue #167 fresh re-review packet — WAVE-02 / MAT-CARD

Date: 2026-07-29  
Review mode: fresh, independent, read-only

## Issue acceptance

Freeze MAT-CARD exact native preview at 1366×768, 1440×900 and 1920×1080 plus the canonical
1440×900 approximation and unsupported blocks. Same-topology long/loading/error evidence must
cover all three viewports. Evaluate the known-Material-to-card task, approved Materials shell and
selected Record continuity, native-preview dominance, exact/review/blocked distinctions, action
consequences, recovery, accessibility, readability, and absence of overlap, clipping and overflow.

Score V-01–V-16 from `docs/01-product/visual-acceptance-matrix.md`. Passing requires at least
28/32, no hard-gate zero and complete, truthful evidence. Return only `approve` or
`changes_requested`, the scores, hard-gate failures, actionable findings with direct paths, and
residual concerns. Do not modify files.

## Approved references

- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png`
  — `362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png`
  — `c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png`
  — `eda9da6037d7dec12fd4c4c5ce5fa77e993a1faa37f5853b3da5c2203bd35849`

## Candidate and comparison captures

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

Responsive comparison siblings, measurements and same-topology evidence are registered by
`docs/01-product/service-reference-manifest.yaml`. The error/recovery evidence is:
`docs/00-research/ux-service-reference/materials-card-wave02.state-evidence.json`.

## Implementation diff

Review only:

- `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`
- regenerated MAT-CARD state evidence, staging data and measurements
- the five candidate images and their manifest rows

The previous reviewer found that error evidence was recorded after Retry and therefore reported a
normal state. The user-authorized second correction now screenshots and snapshots the actual
pre-retry error state first, then stores Retry recovery as a separate nested record. The validator
requires `state: error`, visible error and Retry, retained native preview/task context, zero
overflow and unclipped decision text at all three viewports; it separately requires recovered
`state: normal`, announced Retry, hidden error and retained preview/context. Approval-image bytes
did not change.

## Interaction and test results

```text
MAT-CARD family capture from final sources                     pass
pending-lifecycle family validator                             pass
inventory, Ruff and git diff checks                            pass
pre-retry error state/error/Retry at 1366/1440/1920            pass
separate normal recovery with preview/context retained         pass
error/recovery overflow, clipped decision text, browser errors zero
main-agent original-resolution inspection of all five PNGs     pass
approval image SHA-256 / manifest binding                      pass
manifest lifecycle                                             pending / accepted / approval absent
```
