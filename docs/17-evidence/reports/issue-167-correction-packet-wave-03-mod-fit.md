# #167 WAVE-03 MOD-FIT product-owner correction packet

Date: 2026-07-29
Author: main Sol High agent
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## 1. Authorization and bounded ownership

Apply the single allowed product-owner correction to the four pending MOD-FIT references:

1. `modeling-fit-normal-1366x768`
2. `modeling-fit-normal-1440x900`
3. `modeling-fit-normal-1920x1080`
4. `modeling-fit-candidate-parameters-long-1440x900`

Approved MOD-DATA and MOD-PROCESS references and their sources remain frozen. This correction does
not reopen an approved lifecycle.

Owned paths:

- `docs/00-research/ux-service-reference/modeling-fit-normal.html`
- `docs/00-research/ux-service-reference/modeling-fit.css`
- `docs/00-research/ux-service-reference/modeling-fit.js`
- `docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/modeling-fit-wave03.staging.json`
- the existing MOD-FIT WAVE-03 candidate, measurement and state-evidence files under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit approved Data/Process paths or images, `modeling.html`, `review.css`, the common
manifest/inventory/evidence report, MAT-EXP paths, production paths, or GitHub. Other agents are
working in the same worktree; do not revert or overwrite their work.

## 2. Product judgment

The existing Fit references satisfy the mechanical gates but the plot is not visually dominant
enough. Two stacked candidate bands and an above-plot parameter disclosure compress the engineering
graph; coarse rail rows reduce density; axis titles, units and boundary tick text are inconsistent
and collide.

The supplied GRANTA MI photographs show saved Material/Neutral Material datasheets, not Fit
topology. Do not copy their datasheet sections into Fit. The applicable principle is only disciplined
engineering information density. Fit remains a graph-first decision workspace governed by the
approved Data/Process shell, the product spec and existing Fit state/API contracts.

## 3. Required correction

### Compact rail

- Use compact single-line curve rows, approximately 26–28 px, with identity such as
  `Specimen 01 · r1`. Preserve separate semantic controls for inclusion, curve selection and plot
  visibility; do not nest interactive controls.
- Use 24–26 px operation rows. Replace the visually heavy circular operation number with a compact
  ordinal marker while preserving the configured sequence and active-state clarity.
- Maintain 13 px control/data and 12 px metadata text.
- Keep rail scrolling independent and make its scrollbar visible when actual overflow exists.

### Graph-first vertical topology

- Consolidate Candidate computation and downstream decision status into one shallow command/status
  band. The disabled Save reason must remain adjacent, explicit and readable.
- Remove the separate permanently closed Candidate parameters row.
- Keep one graph-adjacent `Candidate parameters` control with correct `aria-expanded` and
  `aria-controls`.
- When opened, candidate details appear as a bottom drawer below the graph, never above it and never
  as a permanent third inspector. The graph stays mounted.
- Cap the open drawer at approximately 30–35% of the available Fit workspace height and give its
  table/body independent scrolling. Closing it restores the full graph.
- Preserve every existing comparison column and row, explicit candidate selection, non-empty reason,
  applicable warning acknowledgement, and selected-law parameter value/unit/lower/upper bounds.
- At normal viewports the actual plot box, excluding header/legend chrome, must occupy a meaningful
  graph-first share: target at least 45% of the Fit workspace height. In the 1440×900 open-drawer
  state keep a useful plot, target at least 230 px and at least 30% of the workspace height while the
  drawer remains no more than 35%.

### Engineering plot notation

- Axis tick labels are numeric only. Examples: `1,400`, `0.50`; do not append `MPa` or `strain` to
  individual ticks.
- Use centered axis titles `Stress (MPa)` and `Equivalent plastic strain`.
- Center the x title under the plot, not at the right edge or in a detached footer.
- Center/rotate the y title consistently beside the plot. Its bounding box must not collide with y
  ticks, legend, plot marks or clipping boundaries.
- Use consistent plot margins and retain 13 px data/control plus 12 px metadata minimums.
- Preserve the existing finite-data-derived 10% proportional headroom and altered-extrema proof.
  Do not replace it with hard-coded maxima.

### State truth

- Recommendation remains evidence and never silently becomes selection.
- The normal references have no engineer selection and Save remains disabled with its adjacent
  reason.
- After explicit candidate selection in the long state, the status bar must identify the selected
  candidate/task; it must reset when selection is invalidated.
- Empty, calculating, stale/blocked and calculation-error states keep source, rail, ribbon and graph
  mounted with their existing safe recovery.
- Response/Residual/Tangent switching, recomputation, inclusion, visibility, splitter and drawer
  interactions remain operable.

## 4. Deterministic evidence additions

Update capture/validation so the family-local evidence records and asserts:

- Fit workspace, graph region, actual plot-box and drawer pixel heights plus their ratios;
- normal actual plot-box share at each viewport and long-state plot/drawer shares;
- drawer independent `clientHeight`/`scrollHeight`, overflow mode, visible scrollbar treatment and
  wheel/PageDown `scrollTop` consequence;
- curve and operation row-height ranges, rail overflow and local scroll consequence when present;
- exact axis title/tick text, title centering relative to the plot box, and bounding-box
  non-intersection between titles, ticks, legend and plot;
- finite extrema, 10% data-relative headroom, derived limits and altered-extrema response;
- normal no-selection status and long selected-candidate status-bar text;
- zero browser/page errors, nested controls, clipping and document/body overflow.

Recreate all existing MOD-FIT WAVE-03 approval and state images so hashes/measurements describe the
corrected source. Approved Data/Process hashes must remain unchanged.

## 5. Required gates and return

Run:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py --all-packet-targets
uv run --with playwright python docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py --all-packet-targets --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_modeling_data.py --all-packet-targets --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --all-packet-targets --expect-main-agent-status pending
uv run ruff check docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py
node --check docs/00-research/ux-service-reference/modeling-fit.js
git diff --check
```

Open all 16 recreated MOD-FIT images at original resolution. Return changed paths, exact gate
results, four approval-image hashes and residual risks. Do not edit common lifecycle evidence or
request product-owner approval.
