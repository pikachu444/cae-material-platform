# Issue #167 wide-screen correction packet — MAT-DETAIL

Date: 2026-07-30
Writer: one configured `implementer_luna_max`
Authority: GitHub #167, `AGENTS.md`, the approved MAT-DETAIL 1366×768/1440×900 references, and the
current cumulative checklist in `docs/01-product/visual-acceptance-matrix.md`.

## Bounded objective

Correct only the approved `Materials / datasheet / normal / 1920×1080` reference whose 1,293 px-wide
graph is still rendered in a fixed 190 px-high SVG viewport, leaving the plot visually compressed and
most of the first viewport unused. Preserve the already approved 1366×768 and 1440×900 pixels and all
Materials task, state, data and interaction contracts.

The corrected 1920 reference becomes a new pending product-owner candidate. Capture 2560×1440 and
3840×2160 as deterministic wide-screen evidence without adding targets to the 72-image inventory.

## Exact owned paths

The writer may change only:

- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.css`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.js`
- `docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py`
- `docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-wave01.staging.json`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png`
- its `.measurements.json`
- new, clearly named 2560×1440 and 3840×2160 wide-evidence PNG/measurement siblings for that target.

Do not edit shared product policy, the common manifest, the common issue report, production React/CSS,
the base datasheet HTML/CSS/JavaScript, or any Administration path. Other agents and the user already
own unrelated worktree changes; do not revert or rewrite them.

## Preserved authority and contracts

- Keep the continuous `catalog navigator ⇆ datasheet` topology, 280 px default navigator, 5 px
  splitter, 300 px condition/delivery context, six tabs, selected DP780 Record and current revision.
- Keep the exact four typed property rows, their value/unit/condition/source semantics, and the two
  solver-card preview/download paths.
- Keep the declared synthetic response extrema: engineering strain `0–0.20`, engineering stress
  `0–850 MPa`; keep data-span-relative 10% upper padding, the zero anchors and resulting nice domains
  `0–0.25` and `0–1,000 MPa`.
- Keep every approved keyboard, splitter, tab, search, preview and download consequence.
- Preserve these approved image bytes exactly:
  - 1366×768 SHA-256 `362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98`
  - 1440×900 SHA-256 `c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8`

## Required correction

1. Replace the wide target's fixed 190 px presentation with a responsive plot box whose height is
   derived from available width/viewport space and remains an engineering-plot proportion at
   1920, 2560 and 3840.
2. Recompute the SVG viewBox, plot frame, axes, ticks, labels and response path from the actual
   rendered plot dimensions. A `ResizeObserver` may schedule the calculation. Batch DOM reads before
   writes and keep one coordinate system; do not use non-uniform CSS stretching.
3. Keep the graph dominant without inventing extra values, cards or prose. Here, the larger graph is
   the additional meaningful use of space because it exposes the existing response data.
4. Use compact, consistent plot typography. The y-axis title is `Engineering stress (MPa)`; tick
   values contain numbers only. The centered x-axis title is `Engineering strain`. Neither title,
   ticks, path nor legend may collide with the plot frame.
5. Preserve data-relative headroom after resize. The endpoint must stay materially clear of the top
   and right frame at all three wide evidence viewports.
6. Preserve the existing compact legend below the plot and the bounded 300 px application/delivery
   column. Do not turn either into a stretched explanatory region.

SVG is the expected solution because this is one low-density curve. If native SVG geometry cannot
pass the required proportion and resize checks, stop and report the exact technical limitation; do
not silently introduce Canvas/WebGL or rasterize the graph.

## Static-to-production mapping

- Wide responsive SVG renderer → later correction of `RepresentativeCurve` in
  `apps/web/src/material-library.tsx`; its points remain the existing `representativeCurve` response.
- Property rows → existing material/property-set projection.
- Application condition → existing applicability/material-state projection.
- Solver-card rows → existing solver-card availability/preview/download contracts.

This packet changes reference authority only. Do not edit production code.

## Deterministic evidence and gates

- Capture the corrected canonical 1920×1080 target and the two wide evidence viewports.
- Record actual SVG CSS box, viewBox, plot-area box, aspect ratio, tick/title boxes, endpoint,
  data-derived axes/headroom, legend box, main/context widths, overflow and console/page errors.
- Assert the rendered-box and viewBox aspect ratios match within tolerance at all three widths.
- Assert graph height increases with the wide viewport and remains within a bounded professional
  range; assert no title/tick/frame collision and no non-uniform glyph/stroke scaling.
- Assert exact 1366/1440 SHA preservation and rerun the existing family gates.
- Run Ruff, JavaScript syntax validation and `git diff --check`.
- Return changed paths, exact commands/results, the three final image paths/hashes and residual risks.

Do not commit, push, open a PR, edit GitHub or request product-owner approval.
