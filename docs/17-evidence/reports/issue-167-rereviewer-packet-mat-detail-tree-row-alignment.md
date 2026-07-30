# Issue #167 fresh re-review packet — MAT-DETAIL tree-row alignment

Date: 2026-07-30
Owner: active `/root` main agent
Reviewer: one fresh configured read-only `reviewer_terra_high`

## Bounded decision

Independently review the sole correction for the pending
`Materials / Datasheet / Overview / normal` bundle. The product-owner finding was that navigator
type glyphs appeared on a different line from their identities. Review the complete five-image
responsive bundle at original resolution, not only the corrected pixels, and return `approve` or
`changes_requested`.

## Authority and exact correction

- `AGENTS.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`, especially 4.2.1, 5.3 and 5.6
- `docs/01-product/desktop-engineering-ui-spec.md`, especially 4.2 and 5
- `docs/01-product/visual-acceptance-matrix.md`, full Q-01–Q-20 checklist
- `docs/17-evidence/reports/issue-167-correction-packet-mat-detail-tree-row-alignment.md`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`, sections 66–70

The failure was not a literal newline. The Datasheet DOM retains
`disclosure → label → type glyph`, while normal navigator CSS assigns columns
`disclosure=1`, `type glyph=2`, `label=3`. The correction adds explicit `grid-row: 1` to all three
normal-navigator components. It does not reorder shared HTML, apply a transform/offset, change
line-height, alter exceptional Datasheet states or change production React/CSS.

Review diff:

- `docs/00-research/ux-service-reference/materials-navigator.css`
- `docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py`
- `docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py`
- five image/measurement pairs and staging JSON named below

## Exact final images

| Viewport | Image | SHA-256 |
| --- | --- | --- |
| 1366×768 | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png` | `d7b0ff64903b655882987ce4feefb9beb456e6cf5709ff8726ec8e293de9f43d` |
| 1440×900 | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png` | `c12ab49d173016db7119f0fc8a898cb66495f0424f3b5629480cd91185c3876b` |
| 1920×1080 | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png` | `8ac1d48195a233d385743d3d9d936bcea8047f25967a63f0cff9a8a984ab06f0` |
| 2560×1440 support | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.wide-evidence-2560x1440.png` | `2bfca07faeb1648b681b52af0fd64a84d10768262418176297db301ea514a8ff` |
| 3840×2160 support | `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.wide-evidence-3840x2160.png` | `357fe5e127a3ec80d2b7857bb2e85d5b66970ef74b11ed05b7e85fed72f3ef68` |

Every measurement records 7 rows, CSS grid rows `1,1,1`, zero same-row failures and maximum vertical
center delta `0 px`. Confirm that the captured pixels agree; measurement success alone is
insufficient.

## Preserved contracts

Verify no regression in:

- compact graph-only topology at 1366/1440;
- dominant graph plus exact synchronized 29-point grid at 1920/2560/3840;
- total Engineering strain / Engineering stress (MPa), intentional zero/zero origin;
- data-span-relative headroom, complete compact axes and uniform SVG geometry;
- bounded 300 px CAE rail;
- real proportional point-grid rail at 1920/2560 and no fake rail when all rows fit at 3840;
- navigator complete identities, local overflow and splitter keyboard states;
- Application condition, CAE delivery, tabs, actions and status context.

The approved Search normal images must remain:

- 1366 `bd400b2f913a0d2c8c1e5dba6565c05b12055118ffbbaac1b9e5845cf6bfff89`
- 1440 `7f96a68d0ff03eb20b95abf831354e6a1052e34f0246871c9318ede0cce367a0`
- 1920 `57f136268f52386c99cb13970f694cf40a30bdb57a6bc3badcab0b70a24ed3ae`

All six approved Datasheet Related/Empty canonical/responsive hashes must remain byte-identical.

## Main-agent gate already completed

The active main agent reran the two Datasheet validators, Node syntax checks, Python compilation,
Ruff and `git diff --check`; all passed. It independently checked the three Search hashes. It then
opened all five final images at original resolution. Q-03 now passes visually: each disclosure,
type glyph and identity shares one row and vertical center. The rest of the Q checklist remains as
recorded for the previous bundle: Q-03, Q-05, Q-06, Q-07, Q-09, Q-15 and Q-20 pass; other items are
not applicable for the same screen-topology reasons.

## Required read-only re-review

Open every image above at original resolution. Independently rerun:

```powershell
python docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py --all-packet-targets --expect-main-agent-status accepted --assert-preserved-hashes
python docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py --target materials-datasheet-overview-normal-1920x1080 --wide-evidence --expect-main-agent-status accepted --assert-preserved-hashes
node --check docs/00-research/ux-service-reference/materials-datasheet.js
node --check docs/00-research/ux-service-reference/materials-navigator.js
python -m py_compile docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py
python -m ruff check docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py
git diff --check
```

Apply the current Web Interface Guidelines and record V-01–V-16 plus every Q-01–Q-20 item as pass,
fail or not-applicable with direct evidence. A Q-03 visual failure, any full-screen qualitative
regression, hash mismatch, clipping/overlap/overflow, or failed gate requires `changes_requested`.
Do not edit files.
