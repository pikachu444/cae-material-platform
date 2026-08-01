# #167 WAVE-03 final scroll/legend reviewer packet

Date: 2026-07-29
Reviewer role: fresh configured Terra High, read-only
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Acceptance scope

Review the same six pending WAVE-03 references against:

- `AGENTS.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/17-evidence/reports/issue-167-product-owner-rebuild-packet-wave-03.md`

All ten cumulative product-owner findings are binding. In this final amendment, verify especially:

1. overflowing Materials tree/result regions show visually distinct reserved tracks and
   proportional thumbs in captured pixels, remain locally operable, never cover text and do not
   fabricate a result scrollbar in the empty state;
2. the tree uses concise stored identities, aligned disclosure/type glyphs and conditional
   horizontal access to complete genuine long identities;
3. the Fit curve-only legend is inside a measured curve-free plot region, recovers the former
   external-column width and misses curves, boundary, axes, labels and state overlays;
4. findings 1–8 remain intact: graph dominance, compact professional axes, correct true plastic
   strain/true yield stress quantities, positive initial yield, proportional range padding,
   undistorted responsive SVG and bounded candidate details.

No product-owner approval exists. Do not mutate source, evidence, lifecycle, Git or GitHub state.

## Product references

- supplied compact tree:
  `C:/SourceCodes/cae-material-platform/.codex-remote-attachments/019fa7c4-2275-7610-9ece-d689a97d7610/7cef08d8-687a-4773-97d9-144c44f55f30/2-Photo-2.jpg`
- supplied Material Modeler/Fit comparison:
  `C:/SourceCodes/cae-material-platform/.codex-remote-attachments/019fa7c4-2275-7610-9ece-d689a97d7610/7cef08d8-687a-4773-97d9-144c44f55f30/1-Photo-1.jpg`
- approved Materials normal parents:
  `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png`,
  `materials-search-normal-1440x900.png`,
  `materials-search-normal-1920x1080.png`
- approved Modeling parents and current family context:
  `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-*.png` and
  `modeling-process-normal-*.png`

## Pending candidates and hashes

- `docs/17-evidence/images/issue-167-service-reference/materials-search-long-1440x900.png`
  — `43f146e60baf2d933265d952e22fce5cd0c1e2ca0e9145eea0e72a9677da2484`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-empty-1440x900.png`
  — `d9e4fed1d8c17ca86b7c14dfe57909591b44ff8ec300286bb49f3a940fb5e1b1`
- `docs/17-evidence/images/issue-167-service-reference/modeling-fit-normal-1366x768.png`
  — `eb8c23a9df376f1ab9a7604f29088bf022af10f49a0f9310f55c8308fbeb0843`
- `docs/17-evidence/images/issue-167-service-reference/modeling-fit-normal-1440x900.png`
  — `0cacfb3970d015a78f231c160f3f2b8fa15a917653740acdbf51aed874b31fd8`
- `docs/17-evidence/images/issue-167-service-reference/modeling-fit-normal-1920x1080.png`
  — `06ef5ba17d8fdfc6eb2ef80cb592b55d8b18fd0f99067472b81da5fc674fa18b`
- `docs/17-evidence/images/issue-167-service-reference/modeling-fit-candidate-parameters-long-1440x900.png`
  — `ad8166d12a647f0908fbc59997eeb87d063b79fa44a4bb095b45d8ed22346424`

Open every image at original resolution:

- MAT-EXP complete 18-image bundle and hashes:
  `docs/17-evidence/images/issue-167-service-reference/materials-search-wave03.state-evidence.json`
  plus the two canonical measurement JSON files and their four `responsive-*` siblings;
- MOD-FIT complete 16-image bundle and hashes:
  `docs/17-evidence/images/issue-167-service-reference/modeling-fit-state-evidence.json`
  plus the four canonical measurement JSON files.

## Implementation diff

MAT-EXP:

- `docs/00-research/ux-service-reference/materials-search-exceptional.html`
- `docs/00-research/ux-service-reference/materials-search-exceptional.css`
- `docs/00-research/ux-service-reference/materials-search-exceptional.js`
- `docs/00-research/ux-service-reference/capture_materials_search_wave03.py`
- `docs/00-research/ux-service-reference/validate_materials_search_wave03.py`

MOD-FIT:

- `docs/00-research/ux-service-reference/modeling-fit-normal.html`
- `docs/00-research/ux-service-reference/modeling-fit.css`
- `docs/00-research/ux-service-reference/modeling-fit.js`
- `docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py`

Shared serial evidence:

- `docs/01-product/service-reference-manifest.yaml`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`

## Deterministic evidence

- MAT-EXP: 18/18 pass; distinct reserved vertical/horizontal rails; pointer, keyboard and wheel
  consequences pass; empty result has no fake rail.
- MOD-FIT: 4 approval + 12 state captures pass; lower-right placement at all four candidates;
  zero curve/legend collision and 0 px external width tax.
- SVG/viewBox scale, quantities, positive initial yield, proportional ranges, axis containment,
  graph dominance, state continuity, console/page errors, legacy selectors and nested controls pass.
- approved parent hashes/validators, Ruff, JavaScript syntax, inventory, documentation impact and
  `git diff --check` pass.
- fresh Web Interface Guidelines audit of the changed HTML/CSS/JavaScript has no actionable
  finding. The current user-guide image-reference command reports the existing untracked #167
  service-reference set and is not used as a production screenshot gate.

Return one verdict for the integrated six-image bundle, V-01–V-16 scores, total score, hard-gate
result, actionable findings and any non-blocking residual concern.

## Fresh read-only review result

Date: 2026-07-29

The configured fresh Terra High reviewer returned `approve` for product-owner review. This is not
product-owner approval.

- V-01–V-16: 2/2 each
- total: 32/32 (100/100)
- hard gates: pass
- artifact evidence: 34/34 bundle images matched declared dimensions; all six candidate SHA-256
  values matched
- bounded validators, Ruff, JavaScript syntax and `git diff --check`: pass
- actionable findings: none
- non-blocking residual: the seven-entry Fit legend is necessarily compact at 1366×768, but remains
  readable, contained and clear of every curve in the supplied capture
