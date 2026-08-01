# Issue #167 reviewer packet — MAT-DETAIL wide correction

Date: 2026-07-30
Reviewer: one fresh configured `reviewer_terra_high`, read-only
Issue: GitHub #167

## Acceptance boundary

Review only the corrected `Materials / datasheet / normal / 1920×1080` target and its deterministic
2560×1440/3840×2160 wide evidence. The frozen approved 1366×768 and 1440×900 images are comparison
authority and must remain byte-identical. This review does not authorize production React/CSS,
manifest writes, capture regeneration, commits, pushes or GitHub changes.

The target must preserve the continuous navigator/datasheet topology, exact DP780 synthetic Record,
four typed property rows, application condition, two native solver-card actions, the synthetic
engineering stress–strain data and data-relative domains. At every wide viewport, bounded rails
remain readable while the graph uses the elastic result region. SVG box/viewBox/axes/ticks/titles/
path/legend must use one recomputed coordinate system; non-uniform stretching, collision, avoidable
blank space and fabricated filler fail.

## Approved comparison assets

- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png`
  — `362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png`
  — `c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8`

## Candidate and direct evidence

- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png`
  — `4ceec3f13fc2a6ef5731ccaf46c90ba25e793fc6ccb9831c0b96caaeddde4220`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.wide-evidence-2560x1440.png`
  — `3018b68b21b1e545cd86f7ccc7678070623173ee9659ec92e7b4dadda8f86460`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.wide-evidence-3840x2160.png`
  — `7d6906e275912e50951529182c83e9c5b800ea69f6b72bc147ce6888c35ce9aa`

Measurements sit beside each PNG. The bounded implementation diff is:

- `materials-datasheet-overview-normal-1920x1080.css`
- `materials-datasheet-overview-normal-1920x1080.js`
- `capture_materials_datasheet_wave01.py`
- `validate_materials_datasheet_wave01.py`
- `materials-datasheet-wave01.staging.json`
- the canonical/wide PNG and measurement files above
- the main-agent lifecycle/policy/evidence changes recorded in the common diff.

## Gate results supplied to review

- wide target/evidence validator: pass;
- complete MAT-DETAIL family validator: pass;
- 1366/1440 SHA preservation: pass;
- rendered-box/viewBox aspect delta: zero at 1920/2560/3840;
- graph heights: 480 / 840 / 1,542.23 px;
- response endpoint remains inside the frame with right/top headroom at all viewports;
- page/body overflow, title/tick/frame collision, console errors and page errors: zero;
- Ruff, Python compilation, `node --check`, inventory validation and `git diff --check`: pass.

## Required independent review

Open all five comparison/candidate images at original resolution. Inspect the bounded source diff and
measurement evidence. Rerun non-mutating validators. Complete V-01–V-16 and every Q-01–Q-20 item as
`pass`, `fail` or topology-specific `not-applicable`, with direct image/path evidence. A numeric pass
cannot override qualitative plot, information-priority, typography, whitespace or state-contract
failure. Return `approve` or `changes_requested`, actionable findings first, hard-gate result,
scores/checklist and residual concerns. Do not edit any file.
