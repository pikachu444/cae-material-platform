# #167 WAVE-03 product-owner rebuild packet

Date: 2026-07-29  
Author and writer: main Sol High agent, continuing the product-owner-authorized direct correction  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## 1. Authorization and lifecycle

Rebuild the six still-unapproved WAVE-03 candidates after the product owner rejected the preceding
main-agent/reviewer acceptance:

1. `materials-search-long-1440x900`
2. `materials-search-empty-1440x900`
3. `modeling-fit-normal-1366x768`
4. `modeling-fit-normal-1440x900`
5. `modeling-fit-normal-1920x1080`
6. `modeling-fit-candidate-parameters-long-1440x900`

This is a continuation of the explicit exception that assigned the correction to the main Sol High
agent. Do not call or substitute another writing model. After deterministic and direct image gates,
use one fresh configured `reviewer_terra_high` in read-only mode.

The six prior PNGs and hashes remain historical unapproved evidence until replaced in their existing
candidate paths. Their lifecycle stays `pending`; product-owner approval stays `absent`. Do not
change an approved parent, production React/CSS, inventory denominator, commit, push, PR or merge.

## 2. Authority inspected by the main agent

- `AGENTS.md`, `.codex/config.toml`, `.codex/agents/*.toml`
- GitHub issue #167
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/01-product/service-reference-inventory.yaml`
- `docs/01-product/service-reference-manifest.yaml`
- the existing MAT-EXP and MOD-FIT source, capture, validation, staging and evidence files
- the three product-owner-supplied GRANTA MI photographs
- current React/API/domain contracts, including
  `apps/web/src/engineering-curve-plot.tsx`,
  `contracts/modeling/reference-tabulated-plasticity-resources.schema.json`,
  `contracts/modeling/reference-voce-calibration-resources.schema.json`, and
  `backend/src/cmp/modules/processing/domain/metal_hardening.py`

The photographs are saved Material or Neutral Material datasheets, not a Fit screen topology.
Applicable lessons are readable density, local scrolling, compact engineering notation and direct
saved-record links. Fit remains a graph-first decision workspace.

## 3. Consolidated product-owner findings

The rebuild must address the original six findings, the two later semantic/rendering findings, the
two tree/legend findings and the final Modeling-rail consistency finding as one cumulative system:

1. Long navigator trees need a visible, independent local scrollbar.
2. Long result lists need a visible, independent local scrollbar; empty results must not show a fake
   result scrollbar.
3. The Materials navigator is too coarse and long identities lose too much useful text. Reduce
   indentation/type-glyph tax, keep 24–26 px rows, expose the complete accessible identity and let
   users reach the full label without a scrollbar painting over it.
4. Fit controls and decision status must not squeeze the graph. Keep one shallow ribbon, move
   candidate parameters to an on-demand bounded drawer and preserve a useful graph in every state.
5. Axis values, axis titles and plot frame must use compact professional engineering typography:
   no collision, no oversized default-chart appearance, no detached x title, units only in titles,
   and materially smaller whitespace.
6. Multiple curve identities must not consume a wide horizontal footer row. Keep the curve legend
   compact and separate from recommendation/selection workflow status.
7. Responsive rendering must preserve actual glyph and stroke proportions. Do not stretch a fixed
   SVG with non-uniform x/y scale; measure the real plot viewport and recompute data geometry.
8. The plot is a true-yield-stress versus true-plastic-strain hardening response. At zero plastic
   strain the first value is the positive initial yield stress, not `(0, 0)`. Do not disguise a
   total stress–total strain curve as a plastic hardening curve.
9. A technically scrollable pane is not enough when its scrollbar disappears in screenshots.
   Overflowing Materials tree and result panes need visibly distinct reserved tracks and
   proportional thumbs, with pointer, wheel and keyboard consequences. The tree uses concise stored
   identities and aligned disclosure/type glyphs; explanation is not appended to every node.
10. The Fit legend belongs inside a demonstrably curve-free plot quadrant, lower-right for the
    current response. It must recover the former external-column width and use geometry-aware
    alternate placement or a compact docked fallback when data would collide.
11. The Fit left rail is functionally correct but visually cramped and disconnected from the
    approved Materials navigator. Preserve its curve-specific checkbox, color sample and visibility
    command, while adopting the same flat pane rhythm: sentence-case sections, regular identity
    weight, aligned parent/child indentation, secondary revision text and a restrained leading-accent
    selection. Do not widen the rail or imitate the catalog hierarchy merely to obtain similarity.

## 4. MAT-EXP rebuild contract

Owned family paths remain the existing MAT-EXP HTML/CSS/JS, capture/validator, staging JSON and
family-local images/measurements/state evidence.

- Preserve continuous navigator/results/context topology and the approved normal Materials family.
- Use application-owned, reserved scroll rails synchronized to native `.tree-scroll` and
  `.results-table-scroll` overflow so the captured pixels always show an operational track and
  proportional thumb when overflow exists. Hide the native rail to avoid duplication; the custom
  control must expose `role="scrollbar"`, orientation, value range and keyboard behavior. No rail
  may overlay tree or result text.
- Render concise stored object identities with regular disclosure/type glyph alignment. Keep a few
  realistic genuinely long identities, make the tree intrinsically wide enough for their complete
  labels and provide conditional local horizontal navigation rather than permanently ellipsizing
  them. Retain `title` and full `aria-label` values.
- Keep indentation increments compact and row height 24–26 px.
- Long state retains 50 of 126 rows, one selected result and context, local wheel and PageDown
  consequences for tree and results, plus local horizontal tree scroll consequence.
- Empty state retains zero results/selections and no result scrollbar; `Find` is the sole filled
  action and `Clear search` is secondary recovery.
- Capture and validation must prove client/scroll dimensions, rendered track/thumb contrast and
  geometry, text/rail separation, conditional rail visibility, full-label scroll width,
  keyboard/pointer/wheel scrolling and zero document/body overflow.

## 5. MOD-FIT rebuild contract

Owned family paths remain the existing MOD-FIT HTML/CSS/JS, capture/validator, staging JSON and
family-local images/measurements/state evidence.

### Data and quantities

- Use finite synthetic non-production hardening data generated from declared public law parameters.
- The response axes are `True plastic strain [1]` and `True yield stress (MPa)`.
- Every candidate and observed response starts at plastic strain `0` with a positive initial yield
  stress. The visible data, accessible description and recorded extrema must agree.
- Derive both lower and upper limits from finite plotted values using proportional padding and nice
  ticks. Do not hard-code a viewport-specific min/max. The lower limit may be below the minimum
  yield response but must not replace the response with an artificial origin.
- Preserve altered-extrema proof so a changed data maximum changes the derived range.

### Responsive graph

- Remove `preserveAspectRatio="none"` and all duplicate HTML overlay tick/title geometry.
- Measure the actual SVG client width/height, set a matching viewBox and recompute plot frame, grid,
  ticks, boundary, labels and series coordinates after resize. Text and strokes remain undistorted
  CSS-pixel-sized primitives.
- Use compact numeric ticks with tabular numerals; approximately 11 px ticks and 11.5–12 px axis
  titles. Keep title/tick/axis gaps compact and non-intersecting.
- Put the x title directly beneath the x ticks and the rotated y title directly beside the y ticks.
- Use proportional data headroom on all applicable sides. Keep plotted response inside the frame.
- Overlay the compact curve-only legend inside the measured plot stage. Use the lower-right region
  for the current response because no curve occupies it; check all current series, observed
  boundary, axes/titles and graph-state overlays before placing it. Try other safe quadrants when
  data changes and use a compact docked fallback only if no internal region is collision-free.
  Do not reserve a permanent legend column. Legend entries remain individually readable and do not
  merge distinct law identities.
- Eliminate unused top/bottom SVG space and keep the plot dominant.

### Controls and drawer

- Retain the six control groups but make the ribbon shallower through compact alignment, not hidden
  semantics.
- Consolidate recommendation, explicit selection and save reason in one shallow decision band.
- Candidate parameters remain an on-demand drawer with its own scrolling. Normal images keep it
  closed. The 1440 long state keeps a useful graph while exposing the complete comparison and
  selected decision evidence through drawer scrolling.
- Preserve curve inclusion/selection/visibility, operation order, candidate calculation,
  recommendation-versus-selection distinction, reason/warning save gate, response/residual/tangent
  controls, splitter behavior and all exceptional-state recovery.

### Curve and sequence navigator

- Keep the approved 184/192/208 px responsive widths and resizable/collapsible behavior so graph
  dominance does not regress.
- Replace the crowded bold row treatment with regular 12.5 px specimen identities and secondary
  revision text. Use a narrow vertical plot-color sample, not a circular badge.
- Use one consistent parent/child indent, sentence-case section headings and the same restrained
  selected-row fill/leading accent as Materials.
- Keep inclusion, row selection and plot visibility as three separate keyboard-operable decisions.
- Prove that all three normal specimen identities remain unclipped at 184 px, the method parent is
  visually distinct from its children, and injected long rail content scrolls locally without
  changing graph width.

## 6. Deterministic and visual gates

Update the family capture/validators to reject:

- any absent or visually undiscoverable overflow rail/thumb, scrollbar/text collision, inoperable
  pointer/keyboard/wheel scroll or unreachable full tree label;
- any non-uniform SVG scale or mismatch between viewBox and measured plot viewport;
- any zero-stress point at zero true plastic strain;
- mislabeled quantities or unit-bearing tick labels;
- hard-coded axis bounds that do not respond to changed extrema;
- distorted text, tick/title/legend collision, curve/boundary/legend collision, missing x title,
  permanent external legend width tax or excessive plot insets;
- uppercase/coarse Modeling rail chrome, bold or clipped specimen identity, missing parent/child
  indentation, decorative color badges or merged inclusion/selection/visibility semantics;
- plot/legend/drawer overflow, graph collapse, nested interactive controls, browser errors or page
  overflow.

Run both family captures, both family validators, approved-parent validators, Ruff, Node syntax,
inventory validation, web-guideline audit and `git diff --check`. The main agent opens all six
approval candidates plus every regenerated responsive/state image at original resolution before
authoring the reviewer packet.
